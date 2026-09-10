"""
Trade execution endpoint for Swayam Capital (Paper mode only).

Enforces pre-trade validation gate, writes execution records to database, and creates
automated trade journal notes in Obsidian Second Brain.

THE EXECUTION TICKET, 2026-09-09 (docs/PLAN.md 2.12, PR 1)
-----------------------------------------------------------
Before this, a paper trade was filled at whatever price the browser sent, the
server silently re-sorted his legs buys-first, the NIFTY spot at entry was never
stored, and the broker margin for the basket was never stored either, so rule 4
could never be tested. All four change here:

  * Every leg is filled by `services/fills.py` against the SERVER'S live quote:
    market at the quote, limit only if the market is at or through it, and no
    quote means no fill. A leg that cannot fill refuses the whole ticket and
    says, for every leg, what he can do.
  * `leg_order = "as_sent"` keeps his order. The default still puts buys first.
  * `spot_at_entry` and `margin_required_inr` are written on the row.
  * `POST /api/positions/{id}/legs` adds a leg to an OPEN trade, which is how
    "execute one by one" keeps one trade identity while its shape changes.
"""

from datetime import date, datetime, timezone
import uuid
from typing import Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import logging
from decimal import Decimal

from swayam.api.journal_writer import (
    append_leg_block,
    append_leg_exit_block,
    write_new_trade_journal,
)
from swayam.services.charges import (
    ChargeScheduleUnavailable,
    charge_for_leg,
    opposite,
    side_from_direction,
)
from swayam.services.exit_refusal import (
    is_his_price,
    price_not_reached,
    reword_if_his_price,
    side_needed,
    will_rest,
)
from swayam.services import order_watcher
from swayam.services import orders as book
from swayam.services.price_band import band_for_leg, check_price
from swayam.services.structure_name import (
    is_open as leg_is_open,
    name_from_legs,
    open_legs,
    resolve_name,
)
from swayam.services.execution_safety import (
    DuplicateExecution,
    ReplayedExecution,
    abandon_execution,
    claim_execution,
    complete_execution,
    mark_journal_status,
    queue_journal_note,
)
from swayam.services.fills import (
    FILL_BASIS,
    Fill,
    FillRefused,
    LegQuote,
    exit_side_of,
    quote_leg,
    resolve_fill,
    spread_cost_inr,
)
from swayam.api.models_api import (
    AddLegRequest,
    ExecuteRequest,
    LegRequest,
    MultiLegPreviewRequest,
    MultiLegPreviewResponse,
    OrderedLegStep,
    StrategyComputeRequest,
)
from swayam.api.routes.strategy import build_spread_from_request
from swayam.api.routes.validation import audit_strategy_rules
from swayam.db import db
from swayam.notifications.events import dispatch
from swayam.options_math import compute_payoff_curve, compute_position_greeks
from swayam.services import capital as capital_service
from swayam.services.capital import CapitalUnavailable
from swayam.services.contract_master import ContractMasterUnavailable, get_lot_size
from swayam.services.margin import MarginLeg, try_get_margin
from swayam.services.phase import provenance_for_new_position

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------- helpers

def _order_legs(legs: list, leg_order: str) -> list:
    """His order when he chose one; otherwise buys first, because that is what
    earns the hedged margin."""
    if (leg_order or "buys_first").lower() == "as_sent":
        return list(legs)
    buys = [l for l in legs if l.direction.lower() == "buy"]
    sells = [l for l in legs if l.direction.lower() == "sell"]
    return buys + sells


def _leg_label(leg: LegRequest) -> str:
    return f"{leg.direction.upper()} {leg.strike:,.0f} {leg.option_type}"


def _fill_for(leg: LegRequest, underlying: str) -> tuple[Fill, LegQuote]:
    """Quotes one leg from the live chain and decides its fill.

    Kept as one small function so a test can stand in a market that is exactly
    at his price, and so the real path is a single place to read.
    """
    quote = quote_leg(
        strike=leg.strike, expiry=leg.expiry_date, option_type=leg.option_type, underlying=underlying,
    )
    limit = _limit_of(leg)
    try:
        fill = resolve_fill(
            direction=leg.direction,
            order_type=leg.order_type,
            limit_price=limit,
            quote=quote,
            leg_label=_leg_label(leg),
        )
    except FillRefused as exc:
        # The book that refused it travels with the refusal, so the caller can
        # tell "his price has not been reached", which now RESTS, from "there
        # is no market", which still refuses. Without this the caller would
        # have to quote the leg a second time, and a second quote is a second
        # FYERS request per leg.
        exc.quote = quote  # type: ignore[attr-defined]
        raise
    return fill, quote


def _limit_of(leg: LegRequest) -> Optional[float]:
    """The price he actually asked for on a limit leg, wherever the ticket put it."""
    limit = leg.limit_price
    if limit is None and (leg.order_type or "").upper() == "LIMIT":
        limit = leg.entry_premium
    return limit


def _fill_all(
    legs: list[LegRequest],
    underlying: str,
    *,
    rest_away: bool = False,
) -> tuple[list[tuple[LegRequest, Fill, LegQuote]], Optional[float], list[dict[str, Any]]]:
    """Fills every leg it can, and says what to do about the ones it cannot.

    Two kinds of leg do not fill, and Build B is the difference between them.

      * **His price.** The book is there, the side he needs is published, and
        the market simply has not come to his number. Since Build B that is
        not a refusal: the leg RESTS as an open order until the book reaches
        it. It comes back in the third return value.
      * **Anything else.** No book at all, a side that is not published, or
        the bell. Those are facts about the market, not about his price, and
        they still refuse the whole ticket, with every leg named and what to
        do about it, exactly as before.

    `rest_away=False` keeps the old behaviour, where his price refuses too. It
    is what the preview and anything not placing an order use.
    """
    filled: list[tuple[LegRequest, Fill, LegQuote]] = []
    refused: list[dict[str, Any]] = []
    to_rest: list[dict[str, Any]] = []
    spot: Optional[float] = None
    for seq, leg in enumerate(legs, start=1):
        limit = _limit_of(leg)
        try:
            fill, quote = _fill_for(leg, underlying)
        except FillRefused as exc:
            quote = getattr(exc, "quote", None) or _quote_of(leg, underlying)
            side_price = quote.ask if leg.direction.lower() == "buy" else quote.bid
            his_price = rest_away and is_his_price(
                order_type=leg.order_type,
                book_is_tradeable=quote.tradeable,
                side_price=side_price,
                limit_price=limit,
            )
            if his_price:
                to_rest.append({
                    "sequence": seq,
                    "leg": leg,
                    "label": _leg_label(leg),
                    "limit_price": float(limit),
                    "book": side_price,
                    "side": side_needed(leg.direction),
                })
                continue
            refused.append({
                "sequence": seq,
                "leg": _leg_label(leg),
                "reason": str(exc),
                "market": exc.market,
            })
            continue
        if spot is None and quote.spot:
            spot = quote.spot
        filled.append((leg, fill, quote))
    if refused:
        raise HTTPException(
            status_code=422,
            detail={
                "error": (
                    "Nothing was sent. "
                    + ("One leg" if len(refused) == 1 else f"{len(refused)} legs")
                    + " could not be filled honestly; every leg is listed below with what to do."
                ),
                "refused_legs": refused,
            },
        )
    if spot is None:
        # Every leg is resting, so no fill carried a spot back. The book that
        # refused them did, and it is the same reading.
        for candidate in to_rest:
            quote = _quote_of(candidate["leg"], underlying)
            if quote.spot:
                spot = quote.spot
                break
    return filled, spot, to_rest


def _quote_of(leg: LegRequest, underlying: str) -> LegQuote:
    """The book for one leg, for deciding WHY it did not fill. Costs no extra call
    while the chain feed already holds the expiry."""
    try:
        return quote_leg(
            strike=leg.strike, expiry=leg.expiry_date,
            option_type=leg.option_type, underlying=underlying,
        )
    except Exception:  # noqa: BLE001
        return LegQuote(None, None, None, None, "unavailable", False, None)


# --------------------------------------------------------------- resting
#
# BUILD B. A limit the book has not reached used to refuse the whole ticket.
# It cost him his strangle on 10 September and gave his condor the name of the
# preset he had loaded first, because he had to rebuild the trade at market.
# His words: "It should not execute if the price is not available, but must be
# sitting in the system till the time the bid and ask reach the price I want."
#
# Nothing below writes a position, a charge or a note. It writes an ORDER, and
# the order becomes a leg only when the watcher fills it, through this same
# file's own paths.


def _rest_them(
    to_rest: list[dict[str, Any]],
    *,
    underlying: str,
    strategy_name: Optional[str],
    kind: str,
    position_id: Optional[str],
    group_id: str,
    extra_leg: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Puts the legs that could not fill into the order book, and says so.

    Refuses, sending NOTHING, in two cases, both of them facts rather than
    rules: after 15:30, because a resting order placed then would expire the
    same second; and a price outside the exchange's band for the day or off
    its tick, because no such order could ever be held.

    The band is one FYERS depth call per leg placed. Not per refresh, not per
    leg on the ticket: only the ones that actually rest.
    """
    if not to_rest:
        return []

    if book.session_is_over():
        raise HTTPException(
            status_code=422,
            detail={
                "error": (
                    "Nothing was sent and nothing is resting. The market is shut, and an "
                    "order placed now would expire at once because everything resting "
                    "expires at 15:30. Place it in your window."
                ),
                "refused_legs": [
                    {"leg": c["label"], "reason": price_not_reached(side_hit=c["side"], market=c["book"]),
                     "market": c["book"], "your_price": c["limit_price"]}
                    for c in to_rest
                ],
            },
        )

    # Read every band BEFORE anything is written, so a price the exchange
    # would not hold refuses the whole ticket with nothing half done.
    bands: dict[int, Any] = {}
    band_refusals: list[dict[str, Any]] = []
    for candidate in to_rest:
        leg: LegRequest = candidate["leg"]
        band = band_for_leg(
            underlying=underlying, expiry=leg.expiry_date,
            strike=leg.strike, option_type=leg.option_type,
        )
        bands[candidate["sequence"]] = band
        refusal = check_price(band, float(candidate["limit_price"]))
        if refusal:
            band_refusals.append({
                "leg": candidate["label"],
                "reason": refusal,
                "market": candidate["book"],
                "your_price": candidate["limit_price"],
                "band_source": band.source,
            })
    if band_refusals:
        raise HTTPException(
            status_code=422,
            detail={
                "error": (
                    "Nothing was sent and nothing is resting. "
                    + ("One price" if len(band_refusals) == 1 else f"{len(band_refusals)} prices")
                    + " is outside what the exchange will hold today."
                ),
                "refused_legs": band_refusals,
            },
        )

    provenance = provenance_for_new_position()
    new_orders = []
    for candidate in to_rest:
        leg = candidate["leg"]
        payload = {
            "direction": str(leg.direction).lower(),
            "strike": float(leg.strike),
            "option_type": str(leg.option_type).upper(),
            "expiry_date": str(leg.expiry_date),
            "quantity_lots": int(leg.quantity_lots or 1),
            "underlying": underlying,
        }
        if strategy_name:
            payload["strategy_name"] = strategy_name
        if extra_leg:
            payload.update(extra_leg)
        new_orders.append(book.NewOrder(
            kind=kind,
            leg=payload,
            limit_price=float(candidate["limit_price"]),
            position_id=position_id,
            group_id=group_id,
            band=bands.get(candidate["sequence"]),
            provenance=provenance,
        ))

    try:
        rows = book.place(new_orders)
    except book.OrderBookUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    order_watcher.invalidate()
    out = []
    for row, candidate in zip(rows, to_rest):
        band = bands.get(candidate["sequence"])
        out.append({
            "order_id": str(row.get("id")),
            "sequence": candidate["sequence"],
            "leg": candidate["label"],
            "direction": str(candidate["leg"].direction).upper(),
            "strike": candidate["leg"].strike,
            "option_type": candidate["leg"].option_type,
            "expiry_date": candidate["leg"].expiry_date,
            "quantity_lots": candidate["leg"].quantity_lots,
            "limit_price": float(candidate["limit_price"]),
            "book": candidate["book"],
            "side": candidate["side"],
            "kind": kind,
            "position_id": position_id,
            "band_source": band.source if band else None,
            "band_note": band.describe() if band else None,
            "expires_at": row.get("expires_at"),
            "how": will_rest(
                side_hit=candidate["side"],
                market=candidate["book"],
                limit=float(candidate["limit_price"]),
                band=(band.describe() if band else None),
            ),
        })
    return out


def _resting_message(resting: list[dict[str, Any]]) -> str:
    """The one line that must never be mistaken for a refusal."""
    if not resting:
        return ""
    names = ", ".join(r["leg"] for r in resting)
    one = len(resting) == 1
    return (
        f"{names} {'is' if one else 'are'} resting as {'an open order' if one else 'open orders'} "
        f"until the book reaches your price, and {'it expires' if one else 'they expire'} at 15:30. "
        "They fill only while this terminal is awake and reading prices, so keep a page open."
    )


def _charge_entry(leg_dict: dict[str, Any], contracts: int, on: date) -> None:
    """Costs a leg on its own side at its fill price and records it on the leg."""
    try:
        cost = charge_for_leg(
            side=side_from_direction(leg_dict["direction"]),
            price_per_unit=Decimal(str(leg_dict["entry_premium"])),
            quantity_units=contracts,
            on=on,
        )
    except ChargeScheduleUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Trade not executed: this leg cannot be charged, so its cost "
                f"would be unknown from the moment it opened. {exc}"
            ),
        ) from exc
    leg_dict["entry_charges_inr"] = float(cost.total_inr)
    leg_dict["charges_schedule_version"] = cost.schedule_version


def _margin_for(legs: list[LegRequest], underlying: str) -> dict[str, Any]:
    """The broker's margin for the basket, or why it could not be asked."""
    basket = [
        MarginLeg(
            strike=l.strike,
            option_type=l.option_type,
            direction=l.direction.lower(),
            quantity_lots=l.quantity_lots,
            expiry=datetime.strptime(l.expiry_date, "%Y-%m-%d").date(),
            underlying=underlying,
        )
        for l in legs
    ]
    quote, reason = try_get_margin(basket)
    if quote is None:
        return {"margin_required_inr": None, "margin_quoted_at": None, "margin_source": f"unavailable: {reason}"}
    return {
        "margin_required_inr": round(quote.total_inr, 2),
        "margin_quoted_at": quote.fetched_at.isoformat(),
        "margin_source": quote.source,
    }


def _fill_record(seq: int, leg: LegRequest, fill: Fill, lot_size: int, leg_dict: dict[str, Any]) -> dict[str, Any]:
    """What the ticket shows after a send: one line per leg, nothing hidden."""
    return {
        "sequence": seq,
        "direction": leg.direction.upper(),
        "strike": leg.strike,
        "option_type": leg.option_type,
        "expiry_date": leg.expiry_date,
        "quantity_lots": leg.quantity_lots,
        "lot_size": lot_size,
        "order_type": fill.order_type,
        "limit_price": fill.limit_price,
        "fill_price": fill.price,
        "fill_basis": fill.basis,
        "ltp_at_fill": fill.ltp_at_fill,
        "bid_at_fill": fill.bid_at_fill,
        "ask_at_fill": fill.ask_at_fill,
        "filled_at": fill.filled_at,
        "how": fill.how,
        "side_hit": fill.side_hit,
        "entry_charges_inr": leg_dict.get("entry_charges_inr"),
        # What crossing the spread cost against the traded price. Negative is
        # a cost. His words: charges proved what a hidden cost does; the
        # spread is the other one.
        "spread_cost_inr": spread_cost_inr(
            leg.direction, fill.price, fill.ltp_at_fill, leg.quantity_lots * lot_size
        ),
    }


# ---------------------------------------------------------------- preview

@router.post("/api/execute/preview-order", response_model=MultiLegPreviewResponse)
def preview_order_sequence(req: MultiLegPreviewRequest) -> MultiLegPreviewResponse:
    """Orders the legs, costs each one, and asks the broker what the basket needs.

    Buys first by default because that earns the hedged margin; his own order
    when `leg_order` is `as_sent`.
    """
    buy_legs = [l for l in req.legs if l.direction.lower() == "buy"]
    sell_legs = [l for l in req.legs if l.direction.lower() == "sell"]

    sorted_legs = _order_legs(req.legs, req.leg_order)
    ordered_steps: list[OrderedLegStep] = []

    cumulative_debit = 0.0
    cumulative_credit = 0.0
    charges_total: Optional[float] = 0.0

    for idx, leg in enumerate(sorted_legs):
        seq = idx + 1
        is_buy = leg.direction.lower() == "buy"
        expiry = datetime.strptime(leg.expiry_date, "%Y-%m-%d").date()
        try:
            lot_size = get_lot_size(req.underlying, expiry)
        except ContractMasterUnavailable as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Contract size unavailable for {req.underlying} expiring "
                    f"{expiry:%d %b %Y}, so this order cannot be previewed. {exc}"
                ),
            ) from exc

        contracts = leg.quantity_lots * lot_size
        cost = round(leg.entry_premium * contracts, 2)

        if is_buy:
            cumulative_debit += cost
            note = (
                f"Step {seq}: buy the hedge leg first, debit ₹{cost:,.0f}. "
                f"Ordering buys first is what earns the hedged margin."
            )
        else:
            cumulative_credit += cost
            note = f"Step {seq}: sell leg, collecting ₹{cost:,.0f} credit."

        # What getting into this leg costs, from the versioned schedule. A leg
        # with no price yet cannot be costed and says so with a null.
        entry_charges: Optional[float] = None
        if leg.entry_premium and leg.entry_premium > 0:
            try:
                entry_charges = float(charge_for_leg(
                    side=side_from_direction(leg.direction),
                    price_per_unit=Decimal(str(leg.entry_premium)),
                    quantity_units=contracts,
                    on=date.today(),
                ).total_inr)
            except ChargeScheduleUnavailable:
                entry_charges = None
        if entry_charges is None:
            charges_total = None
        elif charges_total is not None:
            charges_total += entry_charges

        ordered_steps.append(
            OrderedLegStep(
                sequence=seq,
                strike=leg.strike,
                option_type=leg.option_type,
                direction=leg.direction.upper(),
                quantity_lots=leg.quantity_lots,
                lot_size=lot_size,
                entry_premium=leg.entry_premium,
                order_type=leg.order_type,
                estimated_margin_inr=None,  # the broker prices the basket, not the leg
                entry_charges_inr=round(entry_charges, 2) if entry_charges is not None else None,
                action_note=note,
            )
        )

    net_debit_credit = round(cumulative_credit - cumulative_debit, 2)

    # The real broker margin. This used to be two invented constants: ₹32,000
    # per lot hedged and ₹1,15,000 naked. Measured against the live account on
    # 2026-09-07, one lot of NIFTY actually cost ₹66,836 hedged and ₹2,00,441
    # naked, so both understated the requirement by roughly half, in the
    # dangerous direction. If FYERS cannot answer, this returns null with a
    # reason and the interface shows "unavailable" rather than a guess.
    def to_margin_legs(legs) -> list[MarginLeg]:
        return [
            MarginLeg(
                strike=l.strike,
                option_type=l.option_type,
                direction=l.direction.lower(),
                quantity_lots=l.quantity_lots,
                expiry=datetime.strptime(l.expiry_date, "%Y-%m-%d").date(),
                underlying=req.underlying,
            )
            for l in legs
        ]

    quote, reason = try_get_margin(to_margin_legs(sorted_legs))

    unhedged: float | None = None
    if quote is not None and sell_legs and buy_legs:
        unhedged_quote, _ = try_get_margin(to_margin_legs(sell_legs))
        unhedged = unhedged_quote.total_inr if unhedged_quote else None

    saved = None
    if quote is not None and unhedged is not None:
        saved = round(max(0.0, unhedged - quote.total_inr), 2)

    return MultiLegPreviewResponse(
        ordered_legs=ordered_steps,
        buy_count=len(buy_legs),
        sell_count=len(sell_legs),
        total_debit_credit_inr=net_debit_credit,
        entry_charges_total_inr=round(charges_total, 2) if charges_total is not None else None,
        margin_required_inr=round(quote.total_inr, 2) if quote else None,
        margin_if_unhedged_inr=round(unhedged, 2) if unhedged is not None else None,
        margin_saved_by_hedge_inr=saved,
        margin_available_inr=round(quote.available_inr, 2) if quote else None,
        margin_source=quote.source if quote else None,
        margin_fetched_at=quote.fetched_at.isoformat() if quote else None,
        margin_unavailable_reason=reason,
    )


# ---------------------------------------------------------------- execute

@router.post("/api/execute/multi-leg")
def execute_multi_leg(req: ExecuteRequest) -> dict[str, Any]:
    """Executes a multi-leg paper trade.

    Buys first unless he chose the order himself on the ticket
    (`leg_order = "as_sent"`). Atomic: every leg fills or nothing is written.
    """
    if req.mode.lower() == "real":
        raise HTTPException(
            status_code=403,
            detail="Real execution disabled until Phase 2 begins (per Personal Trading Brief roadmap)",
        )

    req.legs = _order_legs(req.legs, req.leg_order)

    # Removed 2026-09-08: this used to inject a hardcoded implied volatility of
    # 0.14 whenever the request carried none, which meant a trade could be
    # priced, valued and risk-checked off a volatility nobody measured. No
    # audit had listed it. Implied volatility is now solved from each leg's
    # real market price, and a leg that has no price is refused rather than
    # given a number.
    return execute_trade(req)


# WHY THERE ARE TWO DOORS INTO THE SAME TRADE, from 2026-09-11.
#
# Since Build B a limit the book has not reached RESTS instead of refusing.
# That is right when HE presses Send. It is very wrong when the WATCHER
# re-sends an order that is already resting: the market can move away between
# the watcher seeing his price and the fill path re-reading the book, and a
# path that rests would then write a SECOND order for the same leg, answer
# with no position and no fills, and let the watcher mark the original filled
# on an empty fill. A duplicate in his book and an order shown as filled that
# never was.
#
# So the watcher comes in through `*_now`, which means FILL NOW OR REFUSE.
# A moved-away book raises the price refusal exactly as it did before this
# build, and the watcher releases the order back to resting, which is what its
# _PriceMovedAway path always intended.
#
# `allow_resting` is a keyword on the INNER functions only. It is never a
# field on a request model and never a query parameter, so no browser can ask
# for it either way.


@router.post("/api/execute")
def execute_trade(req: ExecuteRequest) -> dict[str, Any]:
    """Executes a trade in paper mode with strict Method rule gating.

    A leg whose limit the book has not reached RESTS as an open order.

    Raises:
        HTTPException(403): If mode == 'real' (broker execution disabled in Phase 1).
        HTTPException(400): If strategy violates Method rules.
        HTTPException(422): If a leg cannot be filled honestly. Nothing is written.
        HTTPException(500): If database or journal writer fails.
    """
    return _execute_claimed(req, allow_resting=True)


def execute_trade_now(req: ExecuteRequest) -> dict[str, Any]:
    """The same trade, but FILL NOW OR REFUSE. For the watcher, and only it.

    Nothing rests here. A limit the book has not reached raises the price
    refusal, so an order that is already resting stays resting rather than
    breeding a second one.
    """
    return _execute_claimed(req, allow_resting=False)


def _execute_claimed(req: ExecuteRequest, *, allow_resting: bool) -> dict[str, Any]:
    if req.mode.lower() == "real":
        raise HTTPException(
            status_code=403,
            detail="Real execution disabled until Phase 2 begins (per Personal Trading Brief roadmap)",
        )

    # Step 0: claim the execution key BEFORE any work, so a double click cannot
    # become two positions. The browser generates the key, keeps it in local
    # storage, and reuses it on every retry until it gets a final answer.
    idem_key = getattr(req, "idempotency_key", None)
    if idem_key:
        try:
            claim_execution(idem_key, req.model_dump(mode="json"))
        except ReplayedExecution as replay:
            # The same trade, sent again. Return the first answer rather than
            # opening a second position. This is a success, not an error.
            return replay.response
        except DuplicateExecution as clash:
            raise HTTPException(status_code=409, detail=str(clash)) from clash

    try:
        return _execute_trade_inner(req, idem_key, allow_resting=allow_resting)
    except HTTPException:
        if idem_key:
            abandon_execution(idem_key, "execution failed")
        raise
    except Exception as exc:
        if idem_key:
            abandon_execution(idem_key, str(exc))
        raise


def _execute_trade_inner(
    req: ExecuteRequest, idem_key: Optional[str], *, allow_resting: bool = True
) -> dict[str, Any]:
    """The trade itself. Wrapped by execute_trade, which owns the key."""
    # Step 1: Pre-trade rule audit gate, at the prices on the ticket. Entry is
    # never blocked by a rule; a failing check is recorded, not enforced.
    validation = audit_strategy_rules(req)
    if not validation.passed:
        failing = [c.model_dump() for c in validation.checks if c.verdict == "FAIL"]
        failing_reasons = ", ".join([f"{c.get('rule')}: {c.get('note', '')}" for c in failing])
        rule_id_val = failing[0].get("rule") if failing else "method_rule"
        try:
            dispatch("rule_violation", {
                "rule_id": rule_id_val,
                "rule_name": rule_id_val.replace("_", " ").title(),
                "attempted_action": f"Execute {req.strategy_name}",
                "reason": failing_reasons,
            })
        except Exception as exc:
            logger.warning("Could not dispatch rule_violation event: %s", exc)

        raise HTTPException(
            status_code=400,
            detail={
                "error": "Trade execution blocked: Strategy violates Method rules.",
                "failing_checks": failing,
            },
        )

    # Step 2: FILL every leg against the live market, or refuse the lot.
    #
    # Until 2026-09-09 a paper trade was filled at whatever price the browser
    # sent; a limit of ₹1 on a ₹100 option would have "filled". That is a
    # fabricated fill. A market leg now fills at the server's quote read at
    # this moment, a limit only if the market is at or through it, and a leg
    # with no live price does not fill at all.
    # BUILD B: a leg whose limit the book has not reached does not refuse the
    # ticket any more. It comes back in `to_rest` and becomes an open order.
    filled, spot_from_quotes, to_rest = _fill_all(
        req.legs, req.underlying, rest_away=allow_resting
    )

    # ONE PRESS, ONE GROUP. When nothing fills, every leg rests as an entry
    # order and the FIRST of them to fill opens the trade; the rest join it
    # rather than opening trades of their own. The group is how they find each
    # other.
    group_id = str(uuid.uuid4())

    if not filled:
        if not to_rest:
            raise HTTPException(
                status_code=422,
                detail={"error": "Nothing was sent: this ticket has no legs to fill."},
            )
        resting = _rest_them(
            to_rest,
            underlying=req.underlying,
            strategy_name=req.strategy_name,
            kind=book.ENTRY,
            position_id=None,
            group_id=group_id,
        )
        response = {
            "position_id": None,
            "status": "resting",
            "journal_status": "not_written",
            "fills": [],
            "resting": resting,
            "resting_count": len(resting),
            "message": (
                "No trade is open yet. "
                + _resting_message(resting)
                + " The first one to fill opens the trade and the others join it."
            ),
            # Nothing has been charged, nothing has been valued, and saying so
            # is better than a zero that looks like a figure.
            "entry_charges_inr": 0.0,
            "fill_basis": FILL_BASIS,
        }
        if idem_key:
            complete_execution(idem_key, group_id, response)
        return response

    # The trade that EXISTS is only the legs that actually filled. The payoff,
    # the greeks, the margin and the name are all computed for what he holds,
    # never for what he has asked for and not yet got.
    req.legs = [leg for leg, _fill, _quote in filled]

    for leg, fill, _quote in filled:
        # The fill is the entry. Payoff, greeks, charges and the record are all
        # built from it, not from the price the browser had a moment earlier.
        leg.entry_premium = fill.price

    # NIFTY at entry: the spot FYERS reported alongside the fill where it could,
    # else the spot the ticket was built on. Never stored before this, which is
    # why every note printed a spot of 0.
    spot_at_entry = spot_from_quotes if spot_from_quotes else req.current_spot
    spot_source = "FYERS, read at fill" if spot_from_quotes else "the desk's spot at the time of sending"

    # Step 3: Compute payoff and Greeks for journal and record, at the fills
    spread, iv_map, _iv_available = build_spread_from_request(req)
    curve = compute_payoff_curve(
        spread=spread,
        current_spot=spot_at_entry,
        current_iv_per_leg=iv_map,
        as_of_date=date.today(),
    )
    pos_greeks = compute_position_greeks(
        spread=spread,
        current_spot=spot_at_entry,
        current_iv_per_leg=iv_map,
        as_of_date=date.today(),
    )

    position_id = str(uuid.uuid4())
    opened_at = datetime.now(timezone.utc).isoformat()

    # Two things happen to every leg before it is stored, and both are money.
    #
    # ONE: the contract size stored on the leg is the SERVER'S, resolved from
    # the FYERS contract master by build_spread_from_request. It used to be
    # whatever the request carried, which is None from the desk he actually
    # uses. A leg stored with no contract size CANNOT BE CLOSED: close_position
    # refuses to value it rather than guess, so the trade would open and then
    # never close. Proven on 2026-09-09 with the exact payload the desk sends.
    #
    # TWO: the leg is charged as it is bought or sold, at its own price, on its
    # own side. His instruction, 2026-09-09: "Whenever we buy or sell, the
    # charges will be calculated then and there." Entry charges were not
    # recorded at all before this.
    trade_day = date.today()
    legs_dict: list[dict[str, Any]] = []
    fills_out: list[dict[str, Any]] = []
    entry_charges_total = 0.0
    for seq, ((leg_req, fill, _quote), resolved) in enumerate(zip(filled, spread.legs), start=1):
        leg = leg_req.model_dump()
        leg["lot_size"] = int(resolved.lot_size)
        contracts = int(resolved.quantity_lots) * int(resolved.lot_size)
        # How this leg was filled, on the leg, so the record can show the spread
        # cost once fills move to the bid and ask.
        leg["sequence"] = seq
        leg["order_type"] = fill.order_type
        leg["limit_price"] = fill.limit_price
        leg["fill_basis"] = fill.basis
        leg["ltp_at_fill"] = fill.ltp_at_fill
        leg["bid_at_fill"] = fill.bid_at_fill
        leg["ask_at_fill"] = fill.ask_at_fill
        leg["filled_at"] = fill.filled_at
        leg["side_hit"] = fill.side_hit
        leg["spread_cost_inr"] = spread_cost_inr(leg["direction"], fill.price, fill.ltp_at_fill, contracts)
        _charge_entry(leg, contracts, trade_day)
        entry_charges_total += float(leg["entry_charges_inr"])
        legs_dict.append(leg)
        fills_out.append(_fill_record(seq, leg_req, fill, int(resolved.lot_size), leg))
    entry_charges_total = round(entry_charges_total, 2)
    spread_costs = [f["spread_cost_inr"] for f in fills_out]
    spread_cost_total = round(sum(spread_costs), 2) if all(c is not None for c in spread_costs) else None

    # The broker's margin for the basket, stored so rule 4 can be tested from
    # now on. Unavailable is stored as unavailable, and the trade still happens:
    # entry is never blocked.
    margin = _margin_for(req.legs, req.underlying)

    spread_payload = {
        "strategy_name": req.strategy_name,
        "underlying": req.underlying,
        "legs": legs_dict,
        "payoff_curve": {
            "max_loss_inr": curve.max_loss_inr,
            "max_profit_inr": curve.max_profit_inr,
            "rr_implied": curve.rr_implied,
            "net_debit_credit_inr": curve.net_debit_credit_inr,
            "breakevens": list(curve.breakevens),
        },
        "greeks": {
            "net_delta": pos_greeks.net_delta,
            "net_gamma": pos_greeks.net_gamma,
            "net_theta_per_day": pos_greeks.net_theta_per_day,
            "net_vega": pos_greeks.net_vega,
        },
        "margin_required_inr": margin["margin_required_inr"],
        "fill_basis": FILL_BASIS,
        "spot_source": spot_source,
    }

    # The journal expresses the trade's risk as a percentage of his capital.
    # That used to be `swayam_config.margin_base_inr`, a stored Rs 8,50,000 that
    # was never updated. It is the live FYERS balance now, the same figure the
    # risk gate used a moment ago. No fallback: if the broker cannot be read the
    # trade does not happen, because nothing here may invent a denominator.
    try:
        margin_base_inr = capital_service.get_capital().risk_capital_inr
    except CapitalUnavailable as e:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Cannot execute: the live account balance is unavailable, so the "
                f"journal cannot express this trade as a percentage of capital. {e}"
            ),
        ) from e

    # Step 4: Insert to database FIRST — no silent failure, no orphan file
    expiry_date_val = str(min(l.expiry_date for l in req.legs))
    # THE NAME COMES FROM THE LEGS, NOT FROM THE PRESET HE LOADED FIRST.
    # docs/builds/BUILD_01_DESK_POSITION_AREA.md section 3.2. His condor was
    # stored as "Short Strangle" because the strangle preset had been loaded
    # before he changed his mind, and the name stayed. He had no part in it.
    structure_name = name_from_legs(legs_dict)
    # Read the phase ONCE for this send, so the row and its note cannot
    # disagree about what this trade was.
    new_provenance = provenance_for_new_position()
    is_terminal_test = new_provenance == "terminal_test"
    db_record = {
        "id": position_id,
        # name_source is NOT written here on purpose. Migration 022 gives the
        # column a default of 'structure', so a deploy that reaches the live
        # site before he has run the migration still opens trades instead of
        # failing on a column that is not there yet. Only the rename route
        # writes it, and by then the migration is applied.
        "strategy_name": structure_name,
        # WHAT THIS TRADE IS, in his words. Paper trading has not started, so
        # everything the terminal records today is a terminal test: real fills
        # and real charges, but a click to see how the terminal behaves rather
        # than a trade he planned. Read fresh from swayam_phase on every send,
        # never cached, so the first trade after he runs start_paper_trading.py
        # is written 'live'. The column has defaulted to 'live' since migration
        # 017 and is plain text, so this is safe to write before 023 is applied.
        "provenance": new_provenance,
        "underlying": req.underlying,
        "expiry_date": expiry_date_val,
        "legs": legs_dict,
        "net_debit_credit_inr": curve.net_debit_credit_inr,
        "max_loss_inr": curve.max_loss_inr,
        "max_profit_inr": curve.max_profit_inr,
        "breakeven_points": list(curve.breakevens),
        "risk_at_entry_inr": curve.max_loss_inr,
        "status": "open",
        "mode": "paper",
        "opened_at": opened_at,
        "spot_at_entry": round(float(spot_at_entry), 2),
        "fill_basis": FILL_BASIS,
        "margin_required_inr": margin["margin_required_inr"],
        "margin_quoted_at": margin["margin_quoted_at"],
        "margin_source": margin["margin_source"],
        # What getting in cost, summed from the legs. Replaced at close by the
        # full round trip, so this column always means "what this trade has
        # cost so far".
        "charges_inr": entry_charges_total,
        "notes": "; ".join(filter(None, [
            f"session_id={req.session_id}" if req.session_id else None,
            f"execution_mode={req.execution_mode}" if req.execution_mode else None,
            f"leg_order={req.leg_order}" if req.leg_order else None,
        ])) or None,
    }
    try:
        client = db.client
        client.table("swayam_positions").insert(db_record).execute()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Trade execution blocked: Supabase INSERT to swayam_positions failed. "
                f"No trade recorded. No journal file created. Underlying error: {e}"
            ),
        ) from e

    # Step 5: Track locally in session (memory only)
    from swayam.api.routes.positions import record_local_paper_position
    db_record["journal_path"] = None  # set after journal write succeeds
    record_local_paper_position(db_record)

    # Step 6: Write markdown trade journal to Obsidian vault
    try:
        journal_rel_path = write_new_trade_journal(
            position_id=position_id,
            spread_data=spread_payload,
            validation_data=validation.model_dump(),
            current_spot=spot_at_entry,
            margin_base_inr=margin_base_inr,
            opened_at=opened_at,
            # Same answer the row was written with, so the note lands in
            # "Terminal tests" for exactly the trades the row calls tests.
            terminal_test=is_terminal_test,
        )
    except Exception as e:
        # A note is not a trade. The vault is unreachable from Cloud Run (no
        # route to a Windows path on his PC), and the old behaviour returned
        # HTTP 500 on a trade that had already been recorded, which then made
        # him click again. Queue the note instead and let the trade succeed.
        journal_rel_path = None
        journal_status = "pending"
        queued = queue_journal_note(
            position_id=position_id,
            payload={
                "spread_data": spread_payload,
                "validation_data": validation.model_dump(mode="json"),
                "current_spot": spot_at_entry,
                "margin_base_inr": margin_base_inr,
                "opened_at": opened_at,
            },
            kind="new_trade",
            error=str(e),
        )
        if not queued:
            journal_status = "failed"
        logger.warning(
            "Journal note for %s could not be written (%s); queued=%s",
            position_id, e, queued,
        )
    else:
        journal_status = "written"

    # Step 7: Update local record with journal path + insert journal_entries row
    db_record["journal_path"] = journal_rel_path
    if journal_rel_path is not None:
        try:
            client.table("swayam_journal_entries").insert({
                "position_id": position_id,
                "entry_date": opened_at.split("T")[0],
                "entry_type": "entry",
                "md_path": journal_rel_path,
                "created_at": opened_at,
            }).execute()
        except Exception as e:
            # The note exists on disk but its index row does not. Recoverable,
            # and not worth failing a recorded trade over.
            journal_status = "pending"
            queue_journal_note(
                position_id=position_id,
                payload={"md_path": journal_rel_path, "entry_date": opened_at.split("T")[0],
                         "opened_at": opened_at, "index_only": True},
                kind="new_trade",
                error=f"journal index insert failed: {e}",
            )
            logger.warning("Journal index insert failed for %s: %s", position_id, e)

    # The note's path belongs ON THE POSITION, not only in a local dict.
    #
    # It used to be set on `db_record` after the insert had already happened,
    # so the database row never carried it. At close, `pos.get("journal_path")`
    # was therefore always None and the exit block was never appended: his note
    # would have sat on "Exit: to be filled at close" forever, whatever he did.
    # Found 2026-09-09 while probing the live schema.
    mark_journal_status(position_id, journal_status)
    db_record["journal_status"] = journal_status
    if journal_rel_path is not None:
        try:
            client.table("swayam_positions").update(
                {"journal_path": journal_rel_path}
            ).eq("id", position_id).execute()
        except Exception as exc:
            # A note that exists but is not linked is recoverable: the close
            # falls back to swayam_journal_entries. Never fail a recorded trade
            # over a link.
            logger.warning(
                "Could not link journal path to position %s: %s", position_id, exc
            )

    # Step 8: Best-effort event notification dispatch (Telegram + Browser Push)
    strikes_desc = " / ".join([f"{l.direction.upper()} {l.strike} {l.option_type}" for l in req.legs])
    try:
        dispatch("trade_opened", {
            "position_id": position_id,
            "strategy": req.strategy_name,
            "strikes": strikes_desc,
            "net_debit_inr": curve.net_debit_credit_inr,
            "mode": req.mode or "paper",
            "session_id": req.session_id or position_id[:8],
        })
    except Exception as exc:
        logger.warning("Could not dispatch trade_opened event: %s", exc)

    # THE LEGS THAT DID NOT FILL NOW WAIT, ON THIS TRADE.
    #
    # The trade is already recorded, so this cannot be allowed to raise: a
    # ticket whose fills landed must never report failure. If the orders
    # cannot be written he is told exactly that, in the same answer, rather
    # than being left believing something is waiting when nothing is.
    resting: list[dict[str, Any]] = []
    resting_error: Optional[str] = None
    if to_rest:
        try:
            resting = _rest_them(
                to_rest,
                underlying=req.underlying,
                strategy_name=structure_name,
                kind="add_leg",
                position_id=position_id,
                group_id=group_id,
            )
        except HTTPException as exc:
            detail = exc.detail
            refused = detail.get("refused_legs") if isinstance(detail, dict) else None
            first = refused[0].get("reason") if refused else None
            resting_error = str(first or (detail.get("error") if isinstance(detail, dict) else detail))
        except Exception as exc:  # noqa: BLE001
            resting_error = str(exc)
        if resting_error:
            logger.warning("Legs could not be rested on %s: %s", position_id[:8], resting_error)

    if journal_status == "written":
        message = f"Paper trade #{position_id[:8]} opened. Journal at {journal_rel_path}."
    elif journal_status == "pending":
        message = (
            f"Paper trade #{position_id[:8]} opened and recorded. The journal note "
            f"could not be written to your vault from here, so it is queued and will "
            f"be written when the vault is reachable. The trade itself is safe."
        )
    else:
        message = (
            f"Paper trade #{position_id[:8]} opened and recorded, but the journal note "
            f"could not be written OR queued. Write it by hand for this position."
        )

    if resting:
        message = f"{message} {_resting_message(resting)}"
    elif resting_error:
        message = (
            f"{message} The legs away from the book are NOT waiting: {resting_error} "
            f"Send them again when you want them."
        )

    response = {
        "position_id": position_id,
        "journal_path": journal_rel_path,
        "journal_status": journal_status,
        "status": "opened",
        "message": message,
        # What is waiting, listed on its own so the ticket can show fills and
        # resting orders separately rather than in one blurred list.
        "resting": resting,
        "resting_count": len(resting),
        "resting_error": resting_error,
        "execution_mode": req.execution_mode,
        "fills": fills_out,
        "spot_at_entry": round(float(spot_at_entry), 2),
        "spot_source": spot_source,
        "net_debit_credit_inr": curve.net_debit_credit_inr,
        "max_loss_inr": curve.max_loss_inr,
        "max_profit_inr": curve.max_profit_inr,
        "breakevens": list(curve.breakevens),
        "entry_charges_inr": entry_charges_total,
        "spread_cost_inr": spread_cost_total,
        "fill_basis": FILL_BASIS,
        "margin_required_inr": margin["margin_required_inr"],
        "margin_source": margin["margin_source"],
    }

    # Store the answer so a retry with the same key replays it rather than
    # opening a second position.
    if idem_key:
        complete_execution(idem_key, position_id, response)

    return response


# ---------------------------------------------------------------- add a leg

def add_leg_now(position_id: str, req: AddLegRequest) -> dict[str, Any]:
    """One leg onto an open trade, FILL NOW OR REFUSE. For the watcher only."""
    return _add_leg_claimed(position_id, req, allow_resting=False)


@router.post("/api/positions/{position_id}/legs")
def add_leg_to_position(position_id: str, req: AddLegRequest) -> dict[str, Any]:
    """Adds one leg to a trade that is already open. The trade keeps its identity.

    This is "execute one by one": the first leg opens the trade through
    /api/execute/multi-leg and every later leg lands here. It is also the first
    brick of the campaign model in docs/PLAN.md 2.11, in his words: "every new
    leg I add will be considered in the same trade."

    The leg is filled the same way, charged the same way, and the structure's
    net, max loss, max profit, breakevens and broker margin are recomputed for
    what he now holds. An adjustment block goes on the trade's note, or to the
    outbox when the vault cannot be reached.
    """
    return _add_leg_claimed(position_id, req, allow_resting=True)


def _add_leg_claimed(position_id: str, req: AddLegRequest, *, allow_resting: bool) -> dict[str, Any]:
    idem_key = req.idempotency_key
    if idem_key:
        try:
            claim_execution(idem_key, {"position_id": position_id, **req.model_dump(mode="json")})
        except ReplayedExecution as replay:
            return replay.response
        except DuplicateExecution as clash:
            raise HTTPException(status_code=409, detail=str(clash)) from clash
    try:
        return _add_leg_inner(position_id, req, idem_key, allow_resting=allow_resting)
    except HTTPException:
        if idem_key:
            abandon_execution(idem_key, "add leg failed")
        raise
    except Exception as exc:
        if idem_key:
            abandon_execution(idem_key, str(exc))
        raise


def _add_leg_inner(
    position_id: str, req: AddLegRequest, idem_key: Optional[str], *, allow_resting: bool = True
) -> dict[str, Any]:
    client = db.client
    try:
        res = client.table("swayam_positions").select("*").eq("id", position_id).execute()
        pos = res.data[0] if res.data else None
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not read position {position_id}: {exc}") from exc
    if pos is None:
        raise HTTPException(status_code=404, detail=f"Position '{position_id}' not found.")
    if pos.get("status") != "open":
        raise HTTPException(
            status_code=400,
            detail="This trade is closed. A new leg would be a new trade: build it on the desk and execute it.",
        )
    if str(pos.get("mode", "paper")).lower() == "real":
        raise HTTPException(status_code=403, detail="Real execution disabled until Phase 2 begins.")

    underlying = pos.get("underlying", "NIFTY")
    stored_legs: list[dict[str, Any]] = list(pos.get("legs") or [])

    # Fill the new leg against the live market, exactly as the ticket does.
    # BUILD B: if his limit is away from the book it rests on THIS trade
    # instead of refusing, which is what "execute one by one" needs: a leg
    # that rests counts as sent, and the next leg can still be sent.
    filled, spot_from_quote, to_rest = _fill_all([req.leg], underlying, rest_away=allow_resting)
    if not filled:
        resting = _rest_them(
            to_rest,
            underlying=underlying,
            strategy_name=pos.get("strategy_name"),
            kind="add_leg",
            position_id=position_id,
            group_id=str(uuid.uuid4()),
        )
        response = {
            "position_id": position_id,
            "status": "resting",
            "journal_status": "not_written",
            "fill": None,
            "resting": resting,
            "resting_count": len(resting),
            "legs_count": len(stored_legs),
            "message": (
                f"Nothing was added to trade #{position_id[:8]} yet. " + _resting_message(resting)
            ),
        }
        if idem_key:
            complete_execution(idem_key, position_id, response)
        return response

    new_leg_req, fill, _quote = filled[0]
    new_leg_req.entry_premium = fill.price
    spot_now = spot_from_quote if spot_from_quote else req.current_spot

    # The structure he now holds: every stored leg at the price it was booked
    # at, plus the new one at its fill. Volatility is implied from those
    # prices, as on the desk.
    combined_reqs: list[LegRequest] = []
    for l in stored_legs:
        combined_reqs.append(LegRequest(
            strike=float(l["strike"]),
            option_type=str(l["option_type"]),
            direction=str(l["direction"]),
            quantity_lots=int(l.get("quantity_lots", 1) or 1),
            entry_premium=float(l.get("entry_premium") or 0.0),
            expiry_date=str(l.get("expiry_date") or pos.get("expiry_date")),
        ))
    combined_reqs.append(new_leg_req)
    compute_req = StrategyComputeRequest(
        strategy_name=pos.get("strategy_name", "Custom"),
        underlying=underlying,
        legs=combined_reqs,
        current_spot=spot_now,
    )
    spread, iv_map, _ = build_spread_from_request(compute_req)
    curve = compute_payoff_curve(spread=spread, current_spot=spot_now, current_iv_per_leg=iv_map, as_of_date=date.today())
    resolved_new = spread.legs[-1]

    leg = new_leg_req.model_dump()
    leg["lot_size"] = int(resolved_new.lot_size)
    contracts = int(resolved_new.quantity_lots) * int(resolved_new.lot_size)
    seq = len(stored_legs) + 1
    added_at = datetime.now(timezone.utc).isoformat()
    leg["sequence"] = seq
    leg["order_type"] = fill.order_type
    leg["limit_price"] = fill.limit_price
    leg["fill_basis"] = fill.basis
    leg["ltp_at_fill"] = fill.ltp_at_fill
    leg["bid_at_fill"] = fill.bid_at_fill
    leg["ask_at_fill"] = fill.ask_at_fill
    leg["filled_at"] = fill.filled_at
    leg["side_hit"] = fill.side_hit
    leg["spread_cost_inr"] = spread_cost_inr(leg["direction"], fill.price, fill.ltp_at_fill, contracts)
    leg["added_at"] = added_at
    _charge_entry(leg, contracts, date.today())

    margin = _margin_for(combined_reqs, underlying)
    charges_so_far = round(float(pos.get("charges_inr") or 0.0) + float(leg["entry_charges_inr"]), 2)

    legs_after = stored_legs + [leg]
    update = {
        "legs": legs_after,
        # A straddle that gains two wings IS a condor from that moment. The
        # name follows unless he typed one of his own.
        "strategy_name": resolve_name(
            legs_after, name_source=pos.get("name_source"), current_name=pos.get("strategy_name")
        ),
        "expiry_date": str(min(l.expiry_date for l in combined_reqs)),
        "net_debit_credit_inr": curve.net_debit_credit_inr,
        "max_loss_inr": curve.max_loss_inr,
        "max_profit_inr": curve.max_profit_inr,
        "breakeven_points": list(curve.breakevens),
        "risk_at_entry_inr": curve.max_loss_inr,
        "charges_inr": charges_so_far,
        "margin_required_inr": margin["margin_required_inr"],
        "margin_quoted_at": margin["margin_quoted_at"],
        "margin_source": margin["margin_source"],
    }
    try:
        client.table("swayam_positions").update(update).eq("id", position_id).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"The leg was filled but could not be recorded on the trade. Nothing changed. {exc}",
        ) from exc

    # Keep the in-memory copy honest, if one exists.
    from swayam.api.routes.positions import _local_paper_positions
    for p in _local_paper_positions:
        if str(p.get("id")) == position_id:
            p.update(update)

    structure_after = {
        "net_debit_credit_inr": curve.net_debit_credit_inr,
        "max_loss_inr": curve.max_loss_inr,
        "max_profit_inr": curve.max_profit_inr,
        "breakevens": list(curve.breakevens),
        "margin_required_inr": margin["margin_required_inr"],
        "legs_count": len(stored_legs) + 1,
    }

    # The note. Appended if the vault is here, queued if it is not; the drainer
    # resolves the note's path at drain time because the entry note itself may
    # still be waiting in the same queue.
    journal_status = "written"
    journal_path = pos.get("journal_path")
    try:
        if not journal_path:
            raise RuntimeError("the entry note has not landed yet")
        append_leg_block(
            journal_rel_path=journal_path,
            added_at=added_at,
            leg=leg,
            structure_after=structure_after,
        )
    except Exception as exc:
        journal_status = "pending"
        queued = queue_journal_note(
            position_id=position_id,
            payload={"added_at": added_at, "leg": leg, "structure_after": structure_after},
            kind="add_leg",
            error=str(exc),
        )
        if not queued:
            journal_status = "failed"
        mark_journal_status(position_id, journal_status)

    response = {
        "position_id": position_id,
        "status": "leg_added",
        "journal_status": journal_status,
        "fill": _fill_record(seq, new_leg_req, fill, int(resolved_new.lot_size), leg),
        "legs_count": len(stored_legs) + 1,
        "spot": round(float(spot_now), 2),
        "entry_charges_inr": charges_so_far,
        **structure_after,
        "message": (
            f"Leg {seq} added to trade #{position_id[:8]}: {fill.how}."
            + ("" if journal_status == "written" else " The note is queued for the vault.")
        ),
    }
    if idem_key:
        complete_execution(idem_key, position_id, response)
    return response


# ---------------------------------------------------- exit a leg, reverse a leg
#
# A TRADE IS A CAMPAIGN, NOT A LEG. His rule, 2026-09-08: "Every leg that I
# square off will have its own profit/loss added, and every new leg I add will
# be considered in the same trade. Once I close all the legs or I say 'the
# trade is closed', then only the trade is closed."
#
# Until this build the only way out was to close everything at once, so a
# condor whose call side had done its work could not be half unwound. That is
# not how he trades. His own words, 2026-09-08: "In options, you have to
# manage the trade... if you don't manage, you won't survive."


class ExitLegRequest(BaseModel):
    """How to get out of ONE leg of an open trade."""

    order_type: str = Field(default="MARKET", description="MARKET or LIMIT")
    limit_price: Optional[float] = None
    close_reason: str = Field(
        default="manual",
        description="Trigger: 'target_hit', 'stop_hit', 'time_exit', 'manual'",
    )
    notes: Optional[str] = None
    idempotency_key: Optional[str] = None


def _find_open_leg(legs: list[dict[str, Any]], sequence: int) -> tuple[int, dict[str, Any]]:
    """The leg with this sequence number, if it is still open.

    Sequence is what the leg was given when it was filled, and it does not
    shift when another leg closes. A stale browser asking to exit a leg that
    has already gone gets a plain answer rather than closing the wrong one.
    """
    for index, leg in enumerate(legs):
        if int(leg.get("sequence") or (index + 1)) == int(sequence):
            if not leg_is_open(leg):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Leg {sequence} is already closed"
                        + (f", at {float(leg['exit_premium']):,.2f}" if leg.get("exit_premium") else "")
                        + ". Refresh the position area to see what is still open."
                    ),
                )
            return index, leg
    raise HTTPException(status_code=404, detail=f"This trade has no leg {sequence}.")


def _exit_charge(direction: str, price: float, contracts: int, on: date) -> float:
    """What getting out of this leg costs, on its own side, at its own price."""
    try:
        cost = charge_for_leg(
            side=opposite(side_from_direction(direction)),
            price_per_unit=Decimal(str(price)),
            quantity_units=contracts,
            on=on,
        )
    except ChargeScheduleUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "This leg cannot be charged, so its result would be unknown and "
                f"nothing was sent. {exc}"
            ),
        ) from exc
    return float(cost.total_inr)


def _exit_leg_request(leg: dict[str, Any], pos: dict[str, Any]) -> LegRequest:
    """A stored leg described as the ORDER that will close it.

    The direction is flipped on purpose: a leg he bought is closed by a SELL,
    so the order waits on the BID. Getting this the wrong way round would have
    the order watching the wrong side of the book for ever.
    """
    return LegRequest(
        strike=float(leg["strike"]),
        option_type=str(leg["option_type"]).upper(),
        direction=exit_side_of(str(leg.get("direction", "buy"))),
        quantity_lots=int(leg.get("quantity_lots", 1) or 1),
        expiry_date=str(leg.get("expiry_date") or pos.get("expiry_date")),
        order_type="LIMIT",
    )


class _ExitShouldRest(Exception):
    """His price on an exit, which the book has not reached. It waits, it does not refuse.

    Carried rather than returned so `_fill_the_exit` keeps one obvious success
    path. `_apply_leg_exit` catches it and writes the order.
    """

    def __init__(self, *, label: str, side: str, book: Optional[float], limit_price: float) -> None:
        super().__init__(label)
        self.label = label
        self.side = side
        self.book = book
        self.limit_price = limit_price


def _fill_the_exit(
    *,
    leg: dict[str, Any],
    underlying: str,
    order_type: str,
    limit_price: Optional[float],
    rest_away: bool = False,
) -> tuple[Fill, LegQuote]:
    """Fills one leg REVERSED, by exactly the rule the entry used.

    A leg he bought is sold at the bid; a leg he sold is bought back at the
    ask. `services/fills.py` decides, unchanged. All this adds is the wording
    when the refusal is about his price rather than about the market.
    """
    direction = str(leg.get("direction", "buy")).lower()
    exit_direction = exit_side_of(direction)
    strike = float(leg.get("strike", 0.0))
    opt_type = str(leg.get("option_type", "CE")).upper()
    label = f"{exit_direction.upper()} {strike:,.0f} {opt_type}"

    quote = quote_leg(
        strike=strike,
        expiry=str(leg.get("expiry_date") or ""),
        option_type=opt_type,
        underlying=underlying,
    )
    side_price = quote.ask if exit_direction == "buy" else quote.bid
    try:
        return resolve_fill(
            direction=exit_direction,
            order_type=order_type,
            limit_price=limit_price,
            quote=quote,
            leg_label=label,
        ), quote
    except FillRefused as exc:
        # BUILD B. His price on the way OUT waits for the book exactly as it
        # does on the way in. Only a fact about the market still refuses.
        if rest_away and is_his_price(
            order_type=order_type,
            book_is_tradeable=quote.tradeable,
            side_price=side_price,
            limit_price=limit_price,
        ):
            raise _ExitShouldRest(
                label=label,
                side=side_needed(exit_direction),
                book=side_price,
                limit_price=float(limit_price),
            ) from exc
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Not exited. {label} could not be filled.",
                "refused_legs": [{
                    "leg": label,
                    "reason": reword_if_his_price(
                        str(exc),
                        direction=exit_direction,
                        order_type=order_type,
                        book_is_tradeable=quote.tradeable,
                        side_price=side_price,
                        limit_price=limit_price,
                    ),
                    "market": exc.market,
                    "your_price": limit_price,
                }],
            },
        ) from exc


def _close_the_leg(
    leg: dict[str, Any],
    *,
    fill: Fill,
    contracts: int,
    closed_at: datetime,
    opened_on: date,
) -> dict[str, Any]:
    """The leg with its own exit, its own charges and its own result on it."""
    direction = str(leg.get("direction", "buy")).lower()
    is_buy = direction in ("buy", "long")
    entry_prem = float(leg.get("entry_premium", 0.0) or 0.0)
    exit_prem = float(fill.price)
    exit_direction = exit_side_of(direction)

    gross = ((exit_prem - entry_prem) * contracts) if is_buy else ((entry_prem - exit_prem) * contracts)
    exit_charges = _exit_charge(direction, exit_prem, contracts, closed_at.date())

    # What getting in cost. Recorded on the leg since 2026-09-09; rebuilt from
    # the schedule in force on the day it opened for anything older. Rebuilt is
    # not invented, and the leg says which it was.
    recorded_entry = leg.get("entry_charges_inr")
    if recorded_entry is None:
        entry_charges = float(
            charge_for_leg(
                side=side_from_direction(direction),
                price_per_unit=Decimal(str(entry_prem)),
                quantity_units=contracts,
                on=opened_on,
            ).total_inr
        )
        entry_source = "rebuilt from the schedule in force at entry"
    else:
        entry_charges = float(recorded_entry)
        entry_source = "recorded when the leg was opened"

    return {
        **dict(leg),
        "status": "closed",
        "closed_at": closed_at.isoformat(),
        "exit_premium": exit_prem,
        "exit_side_hit": fill.side_hit,
        "exit_ltp": fill.ltp_at_fill,
        "exit_order_type": fill.order_type,
        "exit_limit_price": fill.limit_price,
        "exit_fill_basis": fill.basis,
        "exit_how": fill.how,
        "exit_spread_cost_inr": spread_cost_inr(exit_direction, exit_prem, fill.ltp_at_fill, contracts),
        "entry_charges_inr": round(entry_charges, 2),
        "entry_charges_source": entry_source,
        "exit_charges_inr": round(exit_charges, 2),
        "gross_pnl_inr": round(gross, 2),
        "net_pnl_inr": round(gross - entry_charges - exit_charges, 2),
    }


def _structure_after(
    legs: list[dict[str, Any]],
    pos: dict[str, Any],
    underlying: str,
    spot: Optional[float],
) -> dict[str, Any]:
    """What he holds once the legs have changed: the curve and the margin.

    Only OPEN legs are in it, because that is what he is still carrying. When
    nothing is left open there is no structure to price, and this says so
    rather than pricing an empty one.
    """
    still_open = open_legs(legs)
    if not still_open:
        return {"legs_count": 0, "all_closed": True}

    reqs = [
        LegRequest(
            strike=float(l["strike"]),
            option_type=str(l["option_type"]),
            direction=str(l["direction"]),
            quantity_lots=int(l.get("quantity_lots", 1) or 1),
            entry_premium=float(l.get("entry_premium") or 0.0),
            expiry_date=str(l.get("expiry_date") or pos.get("expiry_date")),
        )
        for l in still_open
    ]
    compute_req = StrategyComputeRequest(
        strategy_name=pos.get("strategy_name", "Custom"),
        underlying=underlying,
        legs=reqs,
        current_spot=spot or (float(pos.get("spot_at_entry") or 0.0) or None),
    )
    spread, iv_map, _ = build_spread_from_request(compute_req)
    curve = compute_payoff_curve(
        spread=spread,
        current_spot=compute_req.current_spot,
        current_iv_per_leg=iv_map,
        as_of_date=date.today(),
    )
    margin = _margin_for(reqs, underlying)
    return {
        "legs_count": len(still_open),
        "all_closed": False,
        "expiry_date": str(min(r.expiry_date for r in reqs)),
        "net_debit_credit_inr": curve.net_debit_credit_inr,
        "max_loss_inr": curve.max_loss_inr,
        "max_profit_inr": curve.max_profit_inr,
        "breakevens": list(curve.breakevens),
        "margin_required_inr": margin["margin_required_inr"],
        "margin_quoted_at": margin["margin_quoted_at"],
        "margin_source": margin["margin_source"],
    }


def _note_the_leg_exit(position_id: str, pos: dict[str, Any], payload: dict[str, Any]) -> str:
    """The Adjustments line for a leg that went on its own.

    A NOTE IS NOT A TRADE. If the vault cannot be reached the block queues and
    HIS ACTION STILL SUCCEEDS. That was settled on the entry side by migration
    019 and on the exit side on 2026-09-09; it holds here from the first day.
    """
    journal_path = pos.get("journal_path")
    try:
        if not journal_path:
            raise RuntimeError("the entry note has not landed yet")
        append_leg_exit_block(journal_rel_path=journal_path, **payload)
        return "written"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Leg exit note for %s went to the outbox: %s", position_id[:8], exc)
        status = "pending"
        if not queue_journal_note(
            position_id=position_id, payload=payload, kind="leg_exit", error=str(exc)
        ):
            status = "failed"
        mark_journal_status(position_id, status)
        return status


def _apply_leg_exit(
    position_id: str,
    sequence: int,
    req: ExitLegRequest,
    *,
    reverse: bool,
    allow_resting: bool = True,
) -> dict[str, Any]:
    """Exits one leg, and on a reverse opens the opposite leg in the same breath."""
    client = db.client
    try:
        res = client.table("swayam_positions").select("*").eq("id", position_id).execute()
        pos = res.data[0] if res.data else None
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not read position {position_id}: {exc}") from exc
    if pos is None:
        raise HTTPException(status_code=404, detail=f"Position '{position_id}' not found.")
    if pos.get("status") != "open":
        raise HTTPException(
            status_code=400,
            detail="This trade is closed. Nothing on it can be exited or reversed.",
        )
    if str(pos.get("mode", "paper")).lower() == "real":
        raise HTTPException(status_code=403, detail="Real execution disabled until Phase 2 begins.")

    underlying = str(pos.get("underlying") or "NIFTY")
    stored_legs: list[dict[str, Any]] = list(pos.get("legs") or [])
    index, leg = _find_open_leg(stored_legs, sequence)

    stored_lot = leg.get("lot_size")
    if not stored_lot:
        raise HTTPException(
            status_code=422,
            detail=(
                "This leg has no recorded contract size, so it cannot be valued. "
                "It needs reconciling rather than guessing."
            ),
        )
    contracts = int(leg.get("quantity_lots", 1) or 1) * int(stored_lot)

    closed_at = datetime.now(timezone.utc)
    try:
        opened_on = datetime.fromisoformat(
            str(pos.get("opened_at") or closed_at.isoformat()).replace("Z", "+00:00")
        ).date()
    except Exception:
        opened_on = closed_at.date()

    try:
        fill, exit_quote = _fill_the_exit(
            leg=leg,
            underlying=underlying,
            order_type=(req.order_type or "MARKET").upper(),
            limit_price=req.limit_price,
            rest_away=allow_resting,
        )
    except _ExitShouldRest as waiting:
        # HIS PRICE ON THE WAY OUT. The leg is not closed, the trade is
        # untouched, and an open order now waits for the book. When it fills
        # it comes back through THIS function, so the leg closes, the charges
        # are taken and the note is written by exactly this code.
        resting = _rest_them(
            [{
                "sequence": sequence,
                "leg": _exit_leg_request(leg, pos),
                "label": waiting.label,
                "limit_price": waiting.limit_price,
                "book": waiting.book,
                "side": waiting.side,
            }],
            underlying=underlying,
            strategy_name=pos.get("strategy_name"),
            kind=(book.REVERSE if reverse else book.EXIT_LEG),
            position_id=position_id,
            group_id=str(uuid.uuid4()),
            extra_leg={
                "sequence": int(sequence),
                "close_reason": req.close_reason,
                "notes": req.notes,
            },
        )
        return {
            "position_id": position_id,
            "status": "resting",
            "last_leg": False,
            "journal_status": "not_written",
            "fill": None,
            "resting": resting,
            "resting_count": len(resting),
            "legs_open": len(open_legs(stored_legs)),
            "legs_closed": len(stored_legs) - len(open_legs(stored_legs)),
            "message": (
                f"Nothing was exited. " + _resting_message(resting)
                + " The trade is exactly as it was until it fills."
            ),
        }

    closed_leg = _close_the_leg(
        leg, fill=fill, contracts=contracts, closed_at=closed_at, opened_on=opened_on
    )

    legs_after = list(stored_legs)
    legs_after[index] = closed_leg

    # A REVERSE IS AN EXIT AND THE OPPOSITE LEG, IN ONE REQUEST. Two fills, two
    # charge lines, one execution key. It is how a short call that has run
    # against him becomes a long one without two separate presses.
    opened_leg: Optional[dict[str, Any]] = None
    if reverse:
        flipped = LegRequest(
            strike=float(leg["strike"]),
            option_type=str(leg["option_type"]),
            direction=exit_side_of(str(leg.get("direction", "buy"))),
            quantity_lots=int(leg.get("quantity_lots", 1) or 1),
            expiry_date=str(leg.get("expiry_date") or pos.get("expiry_date")),
            order_type="MARKET",
        )
        try:
            new_fill, _quote = _fill_for(flipped, underlying)
        except FillRefused as exc:
            # The exit has NOT been written yet, so nothing is half done.
            raise HTTPException(
                status_code=422,
                detail={
                    "error": (
                        "Not reversed, and nothing was sent. The leg was not closed either, "
                        "because a reverse is both halves or neither."
                    ),
                    "refused_legs": [{"leg": _leg_label(flipped), "reason": str(exc), "market": exc.market}],
                },
            ) from exc
        flipped.entry_premium = new_fill.price
        opened_leg = flipped.model_dump()
        opened_leg["lot_size"] = int(stored_lot)
        opened_leg["sequence"] = max(
            [int(l.get("sequence") or 0) for l in legs_after] or [0]
        ) + 1
        opened_leg["order_type"] = new_fill.order_type
        opened_leg["limit_price"] = new_fill.limit_price
        opened_leg["fill_basis"] = new_fill.basis
        opened_leg["ltp_at_fill"] = new_fill.ltp_at_fill
        opened_leg["bid_at_fill"] = new_fill.bid_at_fill
        opened_leg["ask_at_fill"] = new_fill.ask_at_fill
        opened_leg["filled_at"] = new_fill.filled_at
        opened_leg["side_hit"] = new_fill.side_hit
        opened_leg["status"] = "open"
        opened_leg["spread_cost_inr"] = spread_cost_inr(
            opened_leg["direction"], new_fill.price, new_fill.ltp_at_fill, contracts
        )
        opened_leg["reversed_from_sequence"] = int(sequence)
        opened_leg["added_at"] = closed_at.isoformat()
        _charge_entry(opened_leg, contracts, closed_at.date())
        legs_after.append(opened_leg)

    structure = _structure_after(legs_after, pos, underlying, exit_quote.spot)
    charges_so_far = round(
        float(pos.get("charges_inr") or 0.0)
        + float(closed_leg["exit_charges_inr"])
        + (float(opened_leg["entry_charges_inr"]) if opened_leg else 0.0),
        2,
    )

    # If that was the last open leg, the TRADE closes, exactly as
    # close_position closes it: one result row, summed over every leg,
    # including the ones squared off days earlier.
    if structure.get("all_closed"):
        from swayam.api.routes.positions import close_trade_from_legs

        closed = close_trade_from_legs(
            position_id=position_id,
            pos=pos,
            legs_after=legs_after,
            closed_at=closed_at,
            close_reason=req.close_reason,
            notes=req.notes,
        )
        # The whole-trade close answers with its own response model. The leg
        # routes answer with a plain object, so it is unwrapped here rather
        # than two shapes leaking out of one button.
        result = closed.model_dump() if hasattr(closed, "model_dump") else dict(closed)
        result["last_leg"] = True
        result["legs_open"] = 0
        result["legs_closed"] = len(legs_after)
        result["fill"] = _exit_fill_record(sequence, closed_leg, fill)
        result["message"] = (
            f"That was the last leg. Trade #{position_id[:8]} is closed and its "
            f"result is in the record: "
            f"{'a profit of ' if float(result.get('realized_pnl_inr') or 0) >= 0 else 'a loss of '}"
            f"Rs {abs(float(result.get('realized_pnl_inr') or 0)):,.2f} after "
            f"Rs {float(result.get('total_charges_inr') or 0):,.2f} of charges."
        )
        return result

    update: dict[str, Any] = {
        "legs": legs_after,
        "charges_inr": charges_so_far,
        # The name follows what is still open, unless he named it himself.
        "strategy_name": resolve_name(
            legs_after, name_source=pos.get("name_source"), current_name=pos.get("strategy_name")
        ),
    }
    for key in (
        "expiry_date", "net_debit_credit_inr", "max_loss_inr", "max_profit_inr",
        "margin_required_inr", "margin_quoted_at", "margin_source",
    ):
        if key in structure:
            update[key] = structure[key]
    if "breakevens" in structure:
        update["breakeven_points"] = structure["breakevens"]
        update["risk_at_entry_inr"] = structure["max_loss_inr"]

    try:
        client.table("swayam_positions").update(update).eq("id", position_id).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "The leg was filled but the trade could not be updated, so nothing "
                f"was recorded. {exc}"
            ),
        ) from exc

    from swayam.api.routes.positions import _local_paper_positions
    for p in _local_paper_positions:
        if str(p.get("id")) == position_id:
            p.update(update)

    journal_status = _note_the_leg_exit(position_id, pos, {
        "closed_at": closed_at.isoformat(),
        "leg": closed_leg,
        "opened_leg": opened_leg,
        "close_reason": req.close_reason,
        "notes": req.notes,
        "structure_after": structure,
    })

    return {
        "position_id": position_id,
        "status": "leg_exited" if not reverse else "leg_reversed",
        "last_leg": False,
        "journal_status": journal_status,
        "fill": _exit_fill_record(sequence, closed_leg, fill),
        "opened_fill": (
            _fill_record(
                int(opened_leg["sequence"]),
                LegRequest(
                    strike=float(opened_leg["strike"]),
                    option_type=str(opened_leg["option_type"]),
                    direction=str(opened_leg["direction"]),
                    quantity_lots=int(opened_leg["quantity_lots"]),
                    expiry_date=str(opened_leg["expiry_date"]),
                ),
                new_fill,
                int(stored_lot),
                opened_leg,
            )
            if opened_leg
            else None
        ),
        "strategy_name": update["strategy_name"],
        "legs_open": structure.get("legs_count", 0),
        "legs_closed": len(legs_after) - structure.get("legs_count", 0),
        "charges_inr": charges_so_far,
        **{k: v for k, v in structure.items() if k not in ("all_closed",)},
        "message": (
            f"{'Reversed' if reverse else 'Exited'} {str(closed_leg.get('direction','')).upper()} "
            f"{float(closed_leg['strike']):,.0f} {closed_leg['option_type']}: {fill.how}. "
            f"That leg booked {'a profit of ' if closed_leg['net_pnl_inr'] >= 0 else 'a loss of '}"
            f"Rs {abs(closed_leg['net_pnl_inr']):,.2f} after charges. "
            f"The trade stays open with {structure.get('legs_count', 0)} leg"
            f"{'' if structure.get('legs_count', 0) == 1 else 's'}."
            + ("" if journal_status == "written" else " The note is queued for the vault.")
        ),
    }


def _exit_fill_record(sequence: int, closed_leg: dict[str, Any], fill: Fill) -> dict[str, Any]:
    """One line describing what the exit actually did."""
    return {
        "sequence": sequence,
        "direction": exit_side_of(str(closed_leg.get("direction", "buy"))).upper(),
        "strike": closed_leg.get("strike"),
        "option_type": closed_leg.get("option_type"),
        "expiry_date": closed_leg.get("expiry_date"),
        "quantity_lots": closed_leg.get("quantity_lots"),
        "lot_size": closed_leg.get("lot_size"),
        "order_type": fill.order_type,
        "limit_price": fill.limit_price,
        "fill_price": fill.price,
        "side_hit": fill.side_hit,
        "ltp_at_fill": fill.ltp_at_fill,
        "how": fill.how,
        "spread_cost_inr": closed_leg.get("exit_spread_cost_inr"),
        "exit_charges_inr": closed_leg.get("exit_charges_inr"),
        "gross_pnl_inr": closed_leg.get("gross_pnl_inr"),
        "net_pnl_inr": closed_leg.get("net_pnl_inr"),
    }


@router.post("/api/positions/{position_id}/legs/{sequence}/exit")
def exit_one_leg(position_id: str, sequence: int, req: ExitLegRequest) -> dict[str, Any]:
    """Squares off ONE leg of an open trade. The trade stays open behind it.

    The leg is filled reversed by the same rule the entry used, charged on its
    own side at its own price, and its result is written on the leg. The
    structure, the name and the broker margin are recomputed for what is still
    open. Only when the last open leg goes does the trade close and one result
    row get written.
    """
    return _claimed(position_id, sequence, req, reverse=False)


@router.post("/api/positions/{position_id}/legs/{sequence}/reverse")
def reverse_one_leg(position_id: str, sequence: int, req: ExitLegRequest) -> dict[str, Any]:
    """Closes one leg and opens the opposite one, in a single request.

    Two fills, two charge lines, one execution key. Both halves or neither: if
    the opposite leg cannot be filled, the first leg is not closed either.
    """
    return _claimed(position_id, sequence, req, reverse=True)


def exit_leg_now(position_id: str, sequence: int, req: ExitLegRequest, *, reverse: bool) -> dict[str, Any]:
    """The same exit, but FILL NOW OR REFUSE. For the watcher, and only it.

    Nothing rests here. If the book has moved away since the watcher looked,
    the price refusal comes back and the order it came from stays resting.
    """
    return _claimed(position_id, sequence, req, reverse=reverse, allow_resting=False)


def _claimed(
    position_id: str, sequence: int, req: ExitLegRequest, *, reverse: bool, allow_resting: bool = True
) -> dict[str, Any]:
    """One press, one exit. The execution key here does what it does at entry."""
    idem_key = req.idempotency_key
    if idem_key:
        try:
            claim_execution(idem_key, {
                "position_id": position_id,
                "sequence": sequence,
                "reverse": reverse,
                **req.model_dump(mode="json"),
            })
        except ReplayedExecution as replay:
            return replay.response
        except DuplicateExecution as clash:
            raise HTTPException(status_code=409, detail=str(clash)) from clash
    try:
        response = _apply_leg_exit(
            position_id, sequence, req, reverse=reverse, allow_resting=allow_resting
        )
    except HTTPException:
        if idem_key:
            abandon_execution(idem_key, "leg exit failed")
        raise
    except Exception as exc:
        if idem_key:
            abandon_execution(idem_key, str(exc))
        raise
    if idem_key:
        complete_execution(idem_key, position_id, response)
    return response
