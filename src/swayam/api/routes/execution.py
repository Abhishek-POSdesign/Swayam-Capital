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
import logging
from decimal import Decimal

from swayam.api.journal_writer import append_leg_block, write_new_trade_journal
from swayam.services.charges import (
    ChargeScheduleUnavailable,
    charge_for_leg,
    side_from_direction,
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
    limit = leg.limit_price
    if limit is None and (leg.order_type or "").upper() == "LIMIT":
        limit = leg.entry_premium
    fill = resolve_fill(
        direction=leg.direction,
        order_type=leg.order_type,
        limit_price=limit,
        quote=quote,
        leg_label=_leg_label(leg),
    )
    return fill, quote


def _fill_all(legs: list[LegRequest], underlying: str) -> tuple[list[tuple[LegRequest, Fill, LegQuote]], Optional[float]]:
    """Fills every leg or refuses the whole ticket, naming every leg that cannot fill.

    Nothing is written until every leg has a fill. He sees all the problems at
    once rather than fixing one and hitting the next.
    """
    filled: list[tuple[LegRequest, Fill, LegQuote]] = []
    refused: list[dict[str, Any]] = []
    spot: Optional[float] = None
    for seq, leg in enumerate(legs, start=1):
        try:
            fill, quote = _fill_for(leg, underlying)
        except FillRefused as exc:
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
    return filled, spot


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


@router.post("/api/execute")
def execute_trade(req: ExecuteRequest) -> dict[str, Any]:
    """Executes a trade in paper mode with strict Method rule gating.

    Raises:
        HTTPException(403): If mode == 'real' (broker execution disabled in Phase 1).
        HTTPException(400): If strategy violates Method rules.
        HTTPException(422): If a leg cannot be filled honestly. Nothing is written.
        HTTPException(500): If database or journal writer fails.
    """
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
        return _execute_trade_inner(req, idem_key)
    except HTTPException:
        if idem_key:
            abandon_execution(idem_key, "execution failed")
        raise
    except Exception as exc:
        if idem_key:
            abandon_execution(idem_key, str(exc))
        raise


def _execute_trade_inner(req: ExecuteRequest, idem_key: Optional[str]) -> dict[str, Any]:
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
    filled, spot_from_quotes = _fill_all(req.legs, req.underlying)
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
    db_record = {
        "id": position_id,
        "strategy_name": req.strategy_name,
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

    response = {
        "position_id": position_id,
        "journal_path": journal_rel_path,
        "journal_status": journal_status,
        "status": "opened",
        "message": message,
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
    idem_key = req.idempotency_key
    if idem_key:
        try:
            claim_execution(idem_key, {"position_id": position_id, **req.model_dump(mode="json")})
        except ReplayedExecution as replay:
            return replay.response
        except DuplicateExecution as clash:
            raise HTTPException(status_code=409, detail=str(clash)) from clash
    try:
        return _add_leg_inner(position_id, req, idem_key)
    except HTTPException:
        if idem_key:
            abandon_execution(idem_key, "add leg failed")
        raise
    except Exception as exc:
        if idem_key:
            abandon_execution(idem_key, str(exc))
        raise


def _add_leg_inner(position_id: str, req: AddLegRequest, idem_key: Optional[str]) -> dict[str, Any]:
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
    filled, spot_from_quote = _fill_all([req.leg], underlying)
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

    update = {
        "legs": stored_legs + [leg],
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
