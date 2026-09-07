"""
The risk gate: whether a trade is allowed, and the arithmetic behind the answer.

Rewritten 2026-09-08. What changed and why
------------------------------------------
**The readiness form has been removed from the trade path entirely.** It used
to be able to block a trade, and to shrink the size cap through `size_cap_pct`
(which was throttling to 0.3%). Abhishek's decision, recorded 2026-09-07: a
self-reported form can be lied to, so it must not have power over money. It
survives as a ceremonial journal with zero authority here. Its old code also
failed OPEN three ways: a database error was swallowed by `except: pass`, a
missing row skipped the gate, and `trading_allowed` defaulted to True. So
"forgot to log readiness" allowed a full-size trade, while logging it honestly
could shrink one. Both directions were wrong.

**Capital is live, not typed in.** Every cap used to be a percentage of
`margin_base_inr`, a number sitting in the config table reading Rs 8,50,000 and
never updated. The real balance on 2026-09-07 was Rs 9,71,002.38, so the 1% cap
was Rs 8,500 when it should have been Rs 9,710.

**Round-trip costs are inside the primary gate.** A trade whose price loss sits
just under 1% still breaches 1% once both sides are paid for. A gate that
ignores that is not a 1% gate.

**Absolute max loss no longer blocks except through the black-swan fuse.** The
old overnight-hedge check gated on absolute max loss, which contradicted the
stated rule that sizing is governed by the 2 sigma move. It is now reported and
never blocks.

**Hedge geometry is real.** The old check passed any structure containing a
sell leg, so a short strangle passed. See rule_engine/hedge_geometry.py, which
also documents where plan v9's wording was itself wrong.

Fail-closed: capital, volatility, contract size, prices and the charge schedule
are all hard dependencies. If any is unavailable this returns 503 and no trade
happens. There is no `except: pass` anywhere in this file.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from swayam.api.models_api import (
    CapitalContext,
    RiskVerdict,
    StrategyComputeRequest,
    ValidationCheck,
    ValidationResponse,
)
from swayam.api.routes.strategy import build_spread_from_request
from swayam.config import settings
from swayam.options_math import compute_max_profit_loss
from swayam.options_math.realized_vol import (
    HistoricalDataUnavailableError,
    InsufficientHistoryError,
    compute_realized_vol,
)
from swayam.rule_engine.hedge_geometry import GeometryLeg, check_hedge_geometry
from swayam.rule_engine.statistical_risk import compute_expected_worst_case_loss
from swayam.rules_engine import TolerantComparator
from swayam.services.capital import CapitalUnavailable, get_capital
from swayam.services.charges import (
    ChargeableLeg,
    ChargeScheduleUnavailable,
    round_trip_cost_reserve,
)
from swayam.vault_reader import vault_reader

router = APIRouter()


def _money(value: float) -> str:
    return f"₹{value:,.0f}"


def audit_strategy_rules(req: StrategyComputeRequest) -> ValidationResponse:
    """Audits a candidate strategy. Blocks on any missing dependency."""
    spread, iv_map, _iv_available = build_spread_from_request(req)
    max_profit, max_loss = compute_max_profit_loss(spread)
    rr_implied = (max_profit / max_loss) if max_loss > 0.0 else 0.0

    # --- dependencies, every one of which blocks -------------------------
    try:
        rules = vault_reader.load_rules(force_reload=False)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot validate: Method rules could not be loaded. {exc}",
        ) from exc

    try:
        capital = get_capital()
    except CapitalUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Cannot validate: live account capital is unavailable, so the risk "
                f"caps cannot be computed. {exc}"
            ),
        ) from exc

    try:
        ann_vol = compute_realized_vol(
            symbol=req.underlying or "NIFTY",
            as_of_date=date.today(),
            window_days=rules.realized_vol_window_days,
        )
    except InsufficientHistoryError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Cannot validate: insufficient {req.underlying or 'NIFTY'} history "
                f"({exc.available}/{exc.needed} sessions). Run: {exc.backfill_command}"
            ),
        ) from exc
    except HistoricalDataUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot validate: historical market data unavailable. {exc}",
        ) from exc

    # --- the 2 standard deviation adverse move ---------------------------
    price_loss = compute_expected_worst_case_loss(
        legs=spread.legs,
        current_spot=req.current_spot,
        annualized_vol=ann_vol,
        stress_sigma=rules.realistic_stress_sigma,
        current_iv_per_leg=iv_map,
    )

    # --- what it costs to get in and back out ----------------------------
    try:
        cost_reserve = float(
            round_trip_cost_reserve(
                [
                    ChargeableLeg(
                        side="buy" if leg.direction.value == "buy" else "sell",
                        price_per_unit=Decimal(str(leg.entry_premium or 0.0)),
                        quantity_units=leg.quantity_lots * leg.lot_size,
                    )
                    for leg in spread.legs
                ],
                on=date.today(),
            )
        )
    except (ChargeScheduleUnavailable, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot validate: trading costs cannot be computed. {exc}",
        ) from exc

    comparator = TolerantComparator(tolerance_pct=settings.default_tolerance_pct)
    checks: list[ValidationCheck] = []

    # --- Check 1: the primary gate ---------------------------------------
    total_risk = price_loss + cost_reserve
    primary_cap = capital.primary_risk_cap_inr
    passed_primary = comparator.within_cap(total_risk, primary_cap)
    primary_arithmetic = (
        f"{_money(price_loss)} loss at a {rules.realistic_stress_sigma:g} sigma adverse move "
        f"+ {_money(cost_reserve)} round-trip costs = {_money(total_risk)}, "
        f"against a cap of {_money(primary_cap)} (1% of {_money(capital.risk_capital_inr)})"
    )

    realistic_verdict = RiskVerdict(
        loss_inr=round(total_risk, 2),
        cap_inr=round(primary_cap, 2),
        pct_of_margin=round(total_risk / capital.risk_capital_inr * 100.0, 2),
        passed=passed_primary,
        cost_reserve_inr=round(cost_reserve, 2),
        arithmetic=primary_arithmetic,
    )
    checks.append(
        ValidationCheck(
            rule="realistic_risk",
            verdict="PASS" if passed_primary else "FAIL",
            actual_inr=round(total_risk, 2),
            cap_inr=round(primary_cap, 2),
            tolerance_pct=settings.default_tolerance_pct,
            note=primary_arithmetic,
        )
    )

    # --- Check 2: the black-swan fuse ------------------------------------
    fuse_cap = capital.black_swan_fuse_inr
    passed_fuse = comparator.within_cap(max_loss, fuse_cap)
    fuse_arithmetic = (
        f"absolute worst case {_money(max_loss)} against the black-swan fuse of "
        f"{_money(fuse_cap)} (5% of {_money(capital.risk_capital_inr)})"
    )
    blast_verdict = RiskVerdict(
        loss_inr=round(max_loss, 2),
        cap_inr=round(fuse_cap, 2),
        pct_of_margin=round(max_loss / capital.risk_capital_inr * 100.0, 2),
        passed=passed_fuse,
        arithmetic=fuse_arithmetic,
    )
    checks.append(
        ValidationCheck(
            rule="blast_radius",
            verdict="PASS" if passed_fuse else "FAIL",
            actual_inr=round(max_loss, 2),
            cap_inr=round(fuse_cap, 2),
            tolerance_pct=settings.default_tolerance_pct,
            note=fuse_arithmetic,
        )
    )

    # --- Check 3: reward to risk -----------------------------------------
    passed_rr = comparator.meets_floor(rr_implied, rules.rr_minimum)
    checks.append(
        ValidationCheck(
            rule="rr_minimum",
            verdict="PASS" if passed_rr else "FAIL",
            actual=round(rr_implied, 2),
            floor=rules.rr_minimum,
            tolerance_pct=settings.default_tolerance_pct,
            note=f"reward to risk {rr_implied:.2f} against a minimum of {rules.rr_minimum:.1f}",
        )
    )

    # --- Check 4: no single leg ------------------------------------------
    passed_multileg = len(req.legs) >= 2
    checks.append(
        ValidationCheck(
            rule="no_single_leg",
            verdict="PASS" if passed_multileg else "FAIL",
            actual=float(len(req.legs)),
            floor=2.0,
            note=f"{len(req.legs)} leg(s); a hedged structure needs at least two",
        )
    )

    # --- Check 5: real hedge geometry ------------------------------------
    geometry = check_hedge_geometry(
        GeometryLeg(
            option_type=leg.option_type.value,
            direction=leg.direction.value,
            strike=leg.strike,
            quantity_lots=leg.quantity_lots,
            expiry=leg.expiry_date,
        )
        for leg in spread.legs
    )
    checks.append(
        ValidationCheck(
            rule="hedged_structure",
            verdict="PASS" if geometry.hedged else "FAIL",
            note=geometry.reason,
        )
    )

    # --- Informational only: these never block ---------------------------
    checks.append(
        ValidationCheck(
            rule="absolute_max_loss",
            verdict="PASS",
            blocking=False,
            actual_inr=round(max_loss, 2),
            note=(
                f"absolute worst case is {_money(max_loss)}, "
                f"{max_loss / capital.risk_capital_inr * 100.0:.2f}% of capital. "
                f"Informational: sizing is governed by the 2 sigma move, and the "
                f"black-swan fuse is the only cap on this figure."
            ),
        )
    )

    ceiling = capital.deployable_margin_ceiling_inr
    checks.append(
        ValidationCheck(
            rule="deployable_margin_ceiling",
            verdict="PASS",
            blocking=False,
            cap_inr=round(ceiling, 2) if ceiling is not None else None,
            note=(
                f"the broker would allow at most {_money(ceiling)} of margin, "
                f"being twice the cash-equivalent holding"
                if ceiling is not None
                else f"unavailable: {capital.ceiling_unavailable_reason}"
            ),
        )
    )

    # --- Execution blocks that are not rule failures ---------------------
    execution_blocked_reason: Optional[str] = None
    if geometry.is_multi_expiry:
        execution_blocked_reason = (
            "This structure spans more than one expiry. Its payoff is approximate "
            "until multi-expiry valuation lands, so it can be built and studied but "
            "not executed."
        )

    blocking_checks = [c for c in checks if c.blocking]
    overall_passed = all(c.verdict == "PASS" for c in blocking_checks)

    warnings: list[str] = []
    if not overall_passed:
        warnings.append(
            "Trade blocked by: "
            + ", ".join(c.rule for c in blocking_checks if c.verdict == "FAIL")
        )
    if execution_blocked_reason:
        warnings.append(execution_blocked_reason)
    if capital.reconciliation_note:
        warnings.append(capital.reconciliation_note)
    if capital.ceiling_unavailable_reason:
        warnings.append(capital.ceiling_unavailable_reason)

    return ValidationResponse(
        passed=overall_passed,
        overall_passed=overall_passed,
        realistic_risk=realistic_verdict,
        blast_radius=blast_verdict,
        checks=checks,
        warnings=warnings,
        capital=CapitalContext(**capital.as_dict()),
        execution_blocked_reason=execution_blocked_reason,
    )


@router.post("/api/strategy/validate", response_model=ValidationResponse)
def validate_strategy(req: StrategyComputeRequest) -> ValidationResponse:
    """Validates a candidate option strategy against the Method rules."""
    return audit_strategy_rules(req)


@router.get("/api/risk/capital")
def get_capital_context() -> dict[str, Any]:
    """The account figures every cap is computed from, with their provenance."""
    try:
        return get_capital().as_dict()
    except CapitalUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
