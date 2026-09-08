"""
Trade execution endpoint for Swayam Capital (Paper mode only).

Enforces pre-trade validation gate, writes execution records to database, and creates
automated trade journal notes in Obsidian Second Brain.
"""

from datetime import date, datetime, timezone
import uuid
from typing import Any, Optional
from fastapi import APIRouter, HTTPException
import logging
from decimal import Decimal

from swayam.api.journal_writer import write_new_trade_journal
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
from swayam.api.models_api import (
    ExecuteRequest,
    MultiLegPreviewRequest,
    MultiLegPreviewResponse,
    OrderedLegStep,
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


@router.post("/api/execute/preview-order", response_model=MultiLegPreviewResponse)
def preview_order_sequence(req: MultiLegPreviewRequest) -> MultiLegPreviewResponse:
    """Pre-orders legs for margin safety: all BUY legs execute first, SELL legs execute last.

    Calculates the margin sequence and estimated savings from hedged ordering.
    """
    buy_legs = [l for l in req.legs if l.direction.lower() == "buy"]
    sell_legs = [l for l in req.legs if l.direction.lower() == "sell"]

    sorted_legs = buy_legs + sell_legs
    ordered_steps: list[OrderedLegStep] = []

    cumulative_debit = 0.0
    cumulative_credit = 0.0

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
        margin_required_inr=round(quote.total_inr, 2) if quote else None,
        margin_if_unhedged_inr=round(unhedged, 2) if unhedged is not None else None,
        margin_saved_by_hedge_inr=saved,
        margin_available_inr=round(quote.available_inr, 2) if quote else None,
        margin_source=quote.source if quote else None,
        margin_fetched_at=quote.fetched_at.isoformat() if quote else None,
        margin_unavailable_reason=reason,
    )


@router.post("/api/execute/multi-leg")
def execute_multi_leg(req: ExecuteRequest) -> dict[str, Any]:
    """Executes a multi-leg paper trade with margin-safe ordering (buys first, sells last).

    Atomic execution: all legs succeed or whole trade aborts.
    """
    if req.mode.lower() == "real":
        raise HTTPException(
            status_code=403,
            detail="Real execution disabled until Phase 2 begins (per Personal Trading Brief roadmap)",
        )

    # Margin-safe re-ordering: Buys FIRST, Sells LAST
    buy_legs = [l for l in req.legs if l.direction.lower() == "buy"]
    sell_legs = [l for l in req.legs if l.direction.lower() == "sell"]
    sorted_legs = buy_legs + sell_legs
    req.legs = sorted_legs

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
    # Step 1: Pre-trade rule audit gate
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

    # Step 2: Compute payoff and Greeks for journal and record
    spread, iv_map, _iv_available = build_spread_from_request(req)
    curve = compute_payoff_curve(
        spread=spread,
        current_spot=req.current_spot,
        current_iv_per_leg=iv_map,
        as_of_date=date.today(),
    )
    pos_greeks = compute_position_greeks(
        spread=spread,
        current_spot=req.current_spot,
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
    legs_dict = []
    entry_charges_total = 0.0
    for leg_req, resolved in zip(req.legs, spread.legs):
        leg = leg_req.model_dump()
        leg["lot_size"] = int(resolved.lot_size)
        contracts = int(resolved.quantity_lots) * int(resolved.lot_size)
        try:
            entry_cost = charge_for_leg(
                side=side_from_direction(leg["direction"]),
                price_per_unit=Decimal(str(leg["entry_premium"])),
                quantity_units=contracts,
                on=trade_day,
            )
        except ChargeScheduleUnavailable as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Trade not executed: this leg cannot be charged, so its cost "
                    f"would be unknown from the moment it opened. {exc}"
                ),
            ) from exc
        leg["entry_charges_inr"] = float(entry_cost.total_inr)
        leg["charges_schedule_version"] = entry_cost.schedule_version
        entry_charges_total += float(entry_cost.total_inr)
        legs_dict.append(leg)
    entry_charges_total = round(entry_charges_total, 2)

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

    # Step 3: Insert to database FIRST — no silent failure, no orphan file
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
        # What getting in cost, summed from the legs. Replaced at close by the
        # full round trip, so this column always means "what this trade has
        # cost so far".
        "charges_inr": entry_charges_total,
        "notes": "; ".join(filter(None, [
            f"session_id={req.session_id}" if req.session_id else None,
            f"order_type={req.order_type}" if req.order_type else None,
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

    # Step 4: Track locally in session (memory only)
    from swayam.api.routes.positions import record_local_paper_position
    db_record["journal_path"] = None  # set after journal write succeeds
    record_local_paper_position(db_record)

    # Step 5: Write markdown trade journal to Obsidian vault
    try:
        journal_rel_path = write_new_trade_journal(
            position_id=position_id,
            spread_data=spread_payload,
            validation_data=validation.model_dump(),
            current_spot=req.current_spot,
            margin_base_inr=margin_base_inr,
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
                "current_spot": req.current_spot,
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

    # Step 6: Update local record with journal path + insert journal_entries row
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

    mark_journal_status(position_id, journal_status)
    db_record["journal_status"] = journal_status

    # Step 7: Best-effort event notification dispatch (Telegram + Browser Push)
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
    }

    # Store the answer so a retry with the same key replays it rather than
    # opening a second position.
    if idem_key:
        complete_execution(idem_key, position_id, response)

    return response
