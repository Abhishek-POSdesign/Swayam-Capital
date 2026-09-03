"""
Trade execution endpoint for Swayam Capital (Paper mode only).

Enforces pre-trade validation gate, writes execution records to database, and creates
automated trade journal notes in Obsidian Second Brain.
"""

from datetime import date, datetime, timezone
import uuid
from typing import Any
from fastapi import APIRouter, HTTPException
from swayam.api.journal_writer import write_new_trade_journal
from swayam.api.models_api import ExecuteRequest
from swayam.api.routes.strategy import build_spread_from_request
from swayam.api.routes.validation import audit_strategy_rules
from swayam.db import db
from swayam.options_math import compute_payoff_curve, compute_position_greeks

router = APIRouter()


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
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Trade execution blocked: Strategy violates Method rules.",
                "failing_checks": failing,
            },
        )

    # Step 2: Compute payoff and Greeks for journal and record
    spread, iv_map = build_spread_from_request(req)
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

    return {
        "position_id": position_id,
        "journal_path": journal_rel_path,
        "status": "opened",
        "message": f"Paper trade #{position_id[:8]} opened. Journal at {journal_rel_path}.",
    }
