"""
Operational Readiness API endpoints for Swayam Capital.
"""

from datetime import date, datetime, timezone
from typing import Any
from fastapi import APIRouter, HTTPException
from swayam.db import db
from swayam.readiness import (
    ReadinessInput,
    ReadinessReconciliation,
    ReadinessVerdict,
    compute_readiness_verdict,
    get_daily_log_defaults,
    reconcile_readiness_for_date,
)

router = APIRouter()


@router.get("/api/readiness/today")
def get_today_readiness() -> dict[str, Any]:
    """Returns today's readiness status if logged, else returns autofill defaults from daily log."""
    today_str = date.today().strftime("%Y-%m-%d")

    try:
        client = db.client
        res = client.table("swayam_readiness_log").select("*").eq("log_date", today_str).execute()
        if res.data:
            row = res.data[0]
            factors = row.get("factors", {})
            return {
                "logged": True,
                "log_date": today_str,
                "verdict": row.get("verdict"),
                "trading_allowed": row.get("trading_allowed"),
                "size_cap_pct": float(row["size_cap_pct"]) if row.get("size_cap_pct") is not None else None,
                "factors": factors,
                "computed_at": row.get("computed_at"),
            }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database error while checking today's readiness log: {e}",
        ) from e

    # Not logged yet: attempt reading defaults from today's daily log in Obsidian
    try:
        atlas_defaults = get_daily_log_defaults()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read daily log for readiness defaults: {e}",
        ) from e

    return {
        "logged": False,
        "log_date": today_str,
        "atlas_defaults": atlas_defaults,
    }


@router.post("/api/readiness/log")
def log_readiness(inp: ReadinessInput) -> ReadinessVerdict:
    """Computes readiness verdict from manual input and persists to Supabase."""
    today_str = date.today().strftime("%Y-%m-%d")

    # Fetch alcohol streak days from config if present
    streak_days = None
    try:
        client = db.client
        res = client.table("swayam_config").select("*").eq("key", "current_alcohol_streak_days").single().execute()
        if res.data:
            streak_days = int(res.data.get("value", 0))
    except Exception:
        streak_days = None

    verdict = compute_readiness_verdict(inp, current_alcohol_streak_days=streak_days)

    db_row = {
        "log_date": today_str,
        "verdict": verdict.verdict,
        "trading_allowed": verdict.trading_allowed,
        "size_cap_pct": verdict.size_cap_pct,
        "factors": {
            "input": inp.model_dump(mode="json"),
            "per_factor_verdicts": verdict.per_factor_verdicts,
            "reasons": verdict.reasons,
            "rules_snapshot": verdict.method_rules_snapshot,
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        client = db.client
        # Upsert allows re-logging on the same date cleanly
        client.table("swayam_readiness_log").upsert(db_row).execute()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to record readiness verdict in Supabase: {e}",
        ) from e

    return verdict


@router.post("/api/readiness/reconcile")
def reconcile_today_readiness() -> ReadinessReconciliation:
    """Triggers end-of-day cross-check comparing manual readiness vs synced Atlas data."""
    try:
        return reconcile_readiness_for_date()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {e}") from e
