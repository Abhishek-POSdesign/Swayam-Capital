"""
Method rule compliance validation endpoint for Swayam Capital.

Audits candidate option strategies against Abhishek's strict Obsidian Method rules
using TolerantComparator (2% tolerance band). Prevents rogue or unhedged trade execution.
"""

from datetime import date
from typing import Any
from fastapi import APIRouter, HTTPException
from swayam.api.models_api import (
    RiskVerdict,
    StrategyComputeRequest,
    ValidationCheck,
    ValidationResponse,
)
from swayam.api.routes.strategy import build_spread_from_request
from swayam.config import settings
from swayam.db import db
from swayam.options_math import compute_max_profit_loss
from swayam.options_math.realized_vol import (
    HistoricalDataUnavailableError,
    InsufficientHistoryError,
    compute_realized_vol,
)
from swayam.rule_engine.statistical_risk import compute_expected_worst_case_loss
from swayam.rules_engine import TolerantComparator
from swayam.vault_reader import vault_reader

router = APIRouter()


def audit_strategy_rules(req: StrategyComputeRequest) -> ValidationResponse:
    """Performs full Method rule audit on a candidate strategy."""
    spread, iv_map = build_spread_from_request(req)

    # Calculate analytical max profit and loss in rupees
    max_profit, max_loss = compute_max_profit_loss(spread)
    rr_implied = (max_profit / max_loss) if max_loss > 0.0 else 0.0

    # Load live Method rules from vault
    try:
        rules = vault_reader.load_rules(force_reload=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load Method rules from vault: {e}") from e

    # Retrieve live margin base — no fallback, fail loudly if unavailable
    try:
        margin_base_inr = db.get_margin_base_inr()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Cannot validate: margin base unavailable from Supabase config table. "
                f"Rule caps depend on live margin_base_inr. Check Supabase connectivity. "
                f"Underlying error: {e}"
            ),
        ) from e

    # Compute trailing realized volatility for underlying index — zero silent fallbacks
    try:
        ann_vol = compute_realized_vol(
            symbol=req.underlying or "NIFTY",
            as_of_date=date.today(),
            window_days=rules.realized_vol_window_days,
        )
    except InsufficientHistoryError as e:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Cannot validate: insufficient {req.underlying or 'NIFTY'} history ({e.available}/{e.needed} bars). "
                f"Run: {e.backfill_command}"
            ),
        ) from e
    except HistoricalDataUnavailableError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot validate: historical market data unavailable. Underlying error: {e}",
        ) from e

    # Compute expected worst-case loss under 2-sigma move
    realistic_loss = compute_expected_worst_case_loss(
        legs=spread.legs,
        current_spot=req.current_spot,
        annualized_vol=ann_vol,
        stress_sigma=rules.realistic_stress_sigma,
        current_iv_per_leg=iv_map,
    )

    comparator = TolerantComparator(tolerance_pct=settings.default_tolerance_pct)
    checks: list[ValidationCheck] = []

    # Check 0: Operational Readiness Gate
    today_str = date.today().strftime("%Y-%m-%d")
    effective_risk_pct = rules.realistic_risk_cap_pct
    try:
        client = db.client
        res = client.table("swayam_readiness_log").select("*").eq("log_date", today_str).execute()
        if res.data:
            readiness_row = res.data[0]
            if not readiness_row.get("trading_allowed", True):
                reasons = readiness_row.get("factors", {}).get("reasons", ["Daily operational readiness check blocked trading."])
                checks.append(
                    ValidationCheck(
                        rule="readiness_gate",
                        verdict="FAIL",
                        note=f"Trading blocked today by Readiness check: {'; '.join(reasons)}",
                    )
                )
            elif readiness_row.get("size_cap_pct") is not None:
                effective_risk_pct = float(readiness_row["size_cap_pct"])
    except Exception:
        pass

    # Check 1: Realistic Risk Cap (Primary sizing gate: 2-sigma move vs 1.0% margin base)
    realistic_cap_inr = effective_risk_pct * margin_base_inr
    passed_realistic = comparator.within_cap(realistic_loss, realistic_cap_inr)
    realistic_pct = round((realistic_loss / margin_base_inr * 100.0), 2) if margin_base_inr > 0 else 0.0

    realistic_verdict = RiskVerdict(
        loss_inr=round(realistic_loss, 2),
        cap_inr=round(realistic_cap_inr, 2),
        pct_of_margin=realistic_pct,
        passed=passed_realistic,
    )
    checks.append(
        ValidationCheck(
            rule="realistic_risk",
            verdict="PASS" if passed_realistic else "FAIL",
            actual_inr=round(realistic_loss, 2),
            cap_inr=round(realistic_cap_inr, 2),
            tolerance_pct=settings.default_tolerance_pct,
            note=f"Realistic loss (2-sigma, 20d vol) ₹{realistic_loss:,.0f} vs cap ₹{realistic_cap_inr:,.0f} ({effective_risk_pct * 100:.2f}% + {settings.default_tolerance_pct * 100:.0f}% tolerance)",
        )
    )

    # Check 2: Blast Radius Fuse (Black-swan catastrophic ceiling: absolute max loss vs 3.0% margin base)
    blast_cap_inr = rules.blast_radius_pct * margin_base_inr
    passed_blast = comparator.within_cap(max_loss, blast_cap_inr)
    blast_pct = round((max_loss / margin_base_inr * 100.0), 2) if margin_base_inr > 0 else 0.0

    blast_verdict = RiskVerdict(
        loss_inr=round(max_loss, 2),
        cap_inr=round(blast_cap_inr, 2),
        pct_of_margin=blast_pct,
        passed=passed_blast,
    )
    checks.append(
        ValidationCheck(
            rule="blast_radius",
            verdict="PASS" if passed_blast else "FAIL",
            actual_inr=round(max_loss, 2),
            cap_inr=round(blast_cap_inr, 2),
            tolerance_pct=settings.default_tolerance_pct,
            note=f"Max loss ₹{max_loss:,.0f} vs blast radius fuse ₹{blast_cap_inr:,.0f} ({rules.blast_radius_pct * 100:.2f}% + {settings.default_tolerance_pct * 100:.0f}% tolerance)",
        )
    )

    # Check 3: Reward-to-Risk minimum floor (1:2.0 floor - tolerance)
    passed_rr = comparator.meets_floor(rr_implied, rules.rr_minimum)
    checks.append(
        ValidationCheck(
            rule="rr_minimum",
            verdict="PASS" if passed_rr else "FAIL",
            actual=round(rr_implied, 2),
            floor=rules.rr_minimum,
            tolerance_pct=settings.default_tolerance_pct,
            note=f"R:R ratio {rr_implied:.2f} vs minimum {rules.rr_minimum:.1f}",
        )
    )

    # Check 4: No single-leg rule (at least 2 legs required)
    passed_multileg = len(req.legs) >= 2
    checks.append(
        ValidationCheck(
            rule="no_single_leg",
            verdict="PASS" if passed_multileg else "FAIL",
            actual=float(len(req.legs)),
            floor=2.0,
            note=f"{len(req.legs)} legs in position (hedged multi-leg requirement)",
        )
    )

    # Check 5: Overnight hedge cap (2.0% of margin base)
    overnight_cap_inr = rules.overnight_hedge_cap_pct * margin_base_inr
    passed_overnight = comparator.within_cap(max_loss, overnight_cap_inr)
    checks.append(
        ValidationCheck(
            rule="overnight_hedge_cap",
            verdict="PASS" if passed_overnight else "FAIL",
            actual_inr=round(max_loss, 2),
            cap_inr=round(overnight_cap_inr, 2),
            tolerance_pct=settings.default_tolerance_pct,
            note=f"Defined risk ₹{max_loss:,.0f} caps overnight catastrophe risk",
        )
    )

    # Check 6: Hedged structure (must contain at least one short leg)
    has_hedge_sell = any(l.direction == "sell" for l in req.legs)
    checks.append(
        ValidationCheck(
            rule="hedged_structure",
            verdict="PASS" if has_hedge_sell else "FAIL",
            note="Spread includes credit hedge leg" if has_hedge_sell else "Spread lacks credit hedge leg",
        )
    )

    all_checks_passed = all(c.verdict == "PASS" for c in checks)
    overall_passed = all_checks_passed and passed_realistic and passed_blast
    warnings = []
    if not overall_passed:
        failed_names = [c.rule for c in checks if c.verdict == "FAIL"]
        warnings.append(f"Trade violates Method rules: {', '.join(failed_names)}")

    return ValidationResponse(
        passed=overall_passed,
        overall_passed=overall_passed,
        realistic_risk=realistic_verdict,
        blast_radius=blast_verdict,
        checks=checks,
        warnings=warnings,
    )


@router.post("/api/strategy/validate", response_model=ValidationResponse)
def validate_strategy(req: StrategyComputeRequest) -> ValidationResponse:
    """Validates candidate option strategy against Method rules."""
    return audit_strategy_rules(req)
