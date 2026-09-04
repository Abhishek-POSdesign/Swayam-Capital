"""
Health check and rules configuration endpoints for Swayam Capital.
"""

from typing import Any
from fastapi import APIRouter, HTTPException, Query
from swayam.db import db
from swayam.vault_reader import vault_reader

router = APIRouter()


@router.get("/health")
def get_health() -> dict[str, str]:
    """Returns application health status and version."""
    return {"status": "ok", "version": "0.3.0"}


@router.get("/api/rules")
def get_rules(force_reload: bool = Query(default=False)) -> dict[str, Any]:
    """Returns current active Method rules parsed directly from Obsidian Second Brain.

    If force_reload=True, the disk cache is cleared and vault files are re-read.
    """
    try:
        rules = vault_reader.load_rules(force_reload=force_reload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read rules from vault: {e}") from e

    # Retrieve current margin base to compute live rupee caps for display
    try:
        margin_base_inr = db.get_margin_base_inr()
    except Exception:
        margin_base_inr = rules.margin_base_default_inr

    return {
        "per_trade_risk_pct": rules.per_trade_risk_pct,
        "per_trade_risk_cap_inr": round(rules.per_trade_risk_pct * margin_base_inr, 2),
        "realistic_risk_cap_pct": rules.realistic_risk_cap_pct,
        "realistic_risk_cap_inr": round(rules.realistic_risk_cap_pct * margin_base_inr, 2),
        "realistic_stress_sigma": rules.realistic_stress_sigma,
        "realized_vol_window_days": rules.realized_vol_window_days,
        "rr_minimum": rules.rr_minimum,
        "rr_target": rules.rr_target,
        "daily_loss_cap_pct": rules.daily_loss_cap_pct,
        "daily_loss_cap_inr": round(rules.daily_loss_cap_pct * margin_base_inr, 2),
        "weekly_loss_cap_pct": rules.weekly_loss_cap_pct,
        "weekly_loss_cap_inr": round(rules.weekly_loss_cap_pct * margin_base_inr, 2),
        "blast_radius_pct": rules.blast_radius_pct,
        "blast_radius_cap_inr": round(rules.blast_radius_pct * margin_base_inr, 2),
        "overnight_hedge_cap_pct": rules.overnight_hedge_cap_pct,
        "overnight_hedge_cap_inr": round(rules.overnight_hedge_cap_pct * margin_base_inr, 2),
        "margin_base_min_inr": rules.margin_base_min_inr,
        "margin_base_max_inr": rules.margin_base_max_inr,
        "margin_base_default_inr": rules.margin_base_default_inr,
        "sleep_no_trade_threshold_hours": rules.sleep_no_trade_threshold_hours,
        "sleep_reduced_size_hours_min": rules.sleep_reduced_size_hours_min,
        "sleep_reduced_size_hours_max": rules.sleep_reduced_size_hours_max,
        "sleep_reduced_size_factor": rules.sleep_reduced_size_factor,
        "alcohol_lockout_days": rules.alcohol_lockout_days,
        "reentry_ramp": rules.reentry_ramp,
        "margin_base_inr": margin_base_inr,
    }
