"""
Trade execution endpoint for Swayam Capital (Paper mode only).

Enforces pre-trade validation gate, writes execution records to database, and creates
automated trade journal notes in Obsidian Second Brain.
"""

from datetime import date, datetime, timezone
import uuid
from typing import Any
from fastapi import APIRouter, HTTPException
import logging
from swayam.api.journal_writer import write_new_trade_journal
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

    legs_dict = [l.model_dump() for l in req.legs]
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

    # Retrieve current margin base — no fallback, fail loudly if unavailable
    try:
        margin_base_inr = db.get_margin_base_inr()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Cannot execute: margin base unavailable from Supabase config table. "
                f"Journal writer needs the live margin_base_inr for % display. "
                f"Underlying error: {e}"
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
        raise HTTPException(
            status_code=500,
            detail=(
                f"Trade recorded in Supabase (position_id={position_id}) but journal file write failed. "
                f"Manually create journal or re-run journal generation for this position_id. "
                f"Underlying error: {e}"
            ),
        ) from e

    # Step 6: Update local record with journal path + insert journal_entries row
    db_record["journal_path"] = journal_rel_path
    try:
        client.table("swayam_journal_entries").insert({
            "position_id": position_id,
            "entry_date": opened_at.split("T")[0],
            "entry_type": "entry",
            "md_path": journal_rel_path,
            "created_at": opened_at,
        }).execute()
    except Exception as e:
        # Position is recorded, journal file exists — this is the only step that's recoverable later
        raise HTTPException(
            status_code=500,
            detail=(
                f"Position {position_id} recorded and journal file written to {journal_rel_path}, "
                f"but swayam_journal_entries index INSERT failed. Reconcile later. Error: {e}"
            ),
        ) from e

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

    return {
        "position_id": position_id,
        "journal_path": journal_rel_path,
        "status": "opened",
        "message": f"Paper trade #{position_id[:8]} opened. Journal at {journal_rel_path}.",
    }
