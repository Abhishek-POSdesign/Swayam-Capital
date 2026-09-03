"""
Method rule compliance validation endpoint for Swayam Capital.

Audits candidate option strategies against Abhishek's strict Obsidian Method rules
using TolerantComparator (2% tolerance band). Prevents rogue or unhedged trade execution.
"""

from typing import Any
from fastapi import APIRouter, HTTPException
from swayam.api.models_api import StrategyComputeRequest, ValidationCheck, ValidationResponse
from swayam.api.routes.strategy import build_spread_from_request
from swayam.db import db
from swayam.options_math import compute_max_profit_loss
from swayam.rules_engine import TolerantComparator
from swayam.vault_reader import vault_reader

router = APIRouter()


def audit_strategy_rules(req: StrategyComputeRequest) -> ValidationResponse:
    """Performs full Method rule audit on a candidate strategy."""
    spread, _ = build_spread_from_request(req)

    # Calculate analytical max profit and loss in rupees
    max_profit, max_loss = compute_max_profit_loss(spread)
    rr_implied = (max_profit / max_loss) if max_loss > 0.0 else 0.0

    # Load live Method rules from vault
    try:
        rules = vault_reader.load_rules(force_reload=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load Method rules from vault: {e}") from e

    # Retrieve live margin base
    try:
        margin_base_inr = db.get_margin_base_inr()
    except Exception:
        margin_base_inr = 850000.0

    comparator = TolerantComparator(tolerance_pct=0.02)
    checks: list[ValidationCheck] = []

    # Check 1: Per-trade risk cap (1.0% of margin base + 2% tolerance)
    per_trade_cap_inr = rules.per_trade_risk_pct * margin_base_inr
    passed_cap = comparator.within_cap(max_loss, per_trade_cap_inr)
    checks.append(
        ValidationCheck(
            rule="per_trade_risk_cap",
            verdict="PASS" if passed_cap else "FAIL",
            actual_inr=round(max_loss, 2),
            cap_inr=round(per_trade_cap_inr, 2),
            tolerance_pct=0.02,
            note=f"Max loss ₹{max_loss:,.0f} vs cap ₹{per_trade_cap_inr:,.0f} (1.0% + 2% tolerance)",
        )
    )

    # Check 2: Reward-to-Risk minimum floor (1:2.0 floor - 2% tolerance)
    passed_rr = comparator.meets_floor(rr_implied, rules.rr_minimum)
    checks.append(
        ValidationCheck(
            rule="rr_minimum",
            verdict="PASS" if passed_rr else "FAIL",
            actual=round(rr_implied, 2),
            floor=rules.rr_minimum,
            tolerance_pct=0.02,
            note=f"R:R ratio {rr_implied:.2f} vs minimum {rules.rr_minimum:.1f}",
        )
    )

    # Check 3: No single-leg rule (at least 2 legs required)
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

    # Check 4: Overnight hedge cap (2.0% of margin base)
    overnight_cap_inr = rules.overnight_hedge_cap_pct * margin_base_inr
    passed_overnight = comparator.within_cap(max_loss, overnight_cap_inr)
    checks.append(
        ValidationCheck(
            rule="overnight_hedge_cap",
            verdict="PASS" if passed_overnight else "FAIL",
            actual_inr=round(max_loss, 2),
            cap_inr=round(overnight_cap_inr, 2),
            tolerance_pct=0.02,
            note=f"Defined risk ₹{max_loss:,.0f} caps overnight catastrophe risk",
        )
    )

    # Check 5: Hedged structure (must contain at least one short leg)
    has_hedge_sell = any(l.direction == "sell" for l in req.legs)
    checks.append(
        ValidationCheck(
            rule="hedged_structure",
            verdict="PASS" if has_hedge_sell else "FAIL",
            note="Spread includes credit hedge leg" if has_hedge_sell else "Spread lacks credit hedge leg",
        )
    )

    all_passed = all(c.verdict == "PASS" for c in checks)
    warnings = []
    if not all_passed:
        failed_names = [c.rule for c in checks if c.verdict == "FAIL"]
        warnings.append(f"Trade violates Method rules: {', '.join(failed_names)}")

    return ValidationResponse(passed=all_passed, checks=checks, warnings=warnings)


@router.post("/api/strategy/validate", response_model=ValidationResponse)
def validate_strategy(req: StrategyComputeRequest) -> ValidationResponse:
    """Validates candidate option strategy against Method rules."""
    return audit_strategy_rules(req)
