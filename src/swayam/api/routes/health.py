"""
Health check and rules configuration endpoints for Swayam Capital.
"""

from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query
from swayam.services import capital as capital_service
from swayam.services.capital import CapitalUnavailable
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

    # The rupee caps are percentages of the LIVE FYERS balance. This used to
    # read the stored margin base and fall back to a vault constant; both were
    # invented numbers dressed as caps. Without the balance every rupee cap is
    # null and `capital_unavailable_reason` says why.
    capital_inr: Optional[float] = None
    capital_reason: Optional[str] = None
    try:
        capital_inr = capital_service.get_capital().risk_capital_inr
    except CapitalUnavailable as exc:
        capital_reason = str(exc)

    def cap(pct: float) -> Optional[float]:
        return round(pct * capital_inr, 2) if capital_inr is not None else None

    return {
        "per_trade_risk_pct": rules.per_trade_risk_pct,
        "per_trade_risk_cap_inr": cap(rules.per_trade_risk_pct),
        "realistic_risk_cap_pct": rules.realistic_risk_cap_pct,
        "realistic_risk_cap_inr": cap(rules.realistic_risk_cap_pct),
        "realistic_stress_sigma": rules.realistic_stress_sigma,
        "realized_vol_window_days": rules.realized_vol_window_days,
        "rr_minimum": rules.rr_minimum,
        "rr_target": rules.rr_target,
        "daily_loss_cap_pct": rules.daily_loss_cap_pct,
        "daily_loss_cap_inr": cap(rules.daily_loss_cap_pct),
        "weekly_loss_cap_pct": rules.weekly_loss_cap_pct,
        "weekly_loss_cap_inr": cap(rules.weekly_loss_cap_pct),
        "blast_radius_pct": rules.blast_radius_pct,
        "blast_radius_cap_inr": cap(rules.blast_radius_pct),
        "overnight_hedge_cap_pct": rules.overnight_hedge_cap_pct,
        "overnight_hedge_cap_inr": cap(rules.overnight_hedge_cap_pct),
        "margin_base_min_inr": rules.margin_base_min_inr,
        "margin_base_max_inr": rules.margin_base_max_inr,
        "margin_base_default_inr": rules.margin_base_default_inr,
        "sleep_no_trade_threshold_hours": rules.sleep_no_trade_threshold_hours,
        "sleep_reduced_size_hours_min": rules.sleep_reduced_size_hours_min,
        "sleep_reduced_size_hours_max": rules.sleep_reduced_size_hours_max,
        "sleep_reduced_size_factor": rules.sleep_reduced_size_factor,
        "alcohol_lockout_days": rules.alcohol_lockout_days,
        "reentry_ramp": rules.reentry_ramp,
        "risk_capital_inr": capital_inr,
        "capital_unavailable_reason": capital_reason,
    }
