"""
Strategy preset and payoff computation endpoints for Swayam Capital.
"""

from datetime import date, datetime
import math
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query
from swayam.api.models_api import (
    GreeksResponse,
    LegGreeksItem,
    PayoffCurveResponse,
    PayoffPointResponse,
    StrategyComputeRequest,
    StrategyComputeResponse,
)
from swayam.options_math import (
    Direction,
    Leg,
    OptionType,
    Spread,
    bear_put_spread,
    bull_call_spread,
    calendar_spread,
    compute_payoff_curve,
    compute_position_greeks,
    iron_condor,
)
from swayam.options_math.engine import greeks as calc_greeks
from swayam.options_math.payoff import _spread_expiry_pnl

router = APIRouter()


def build_spread_from_request(req: StrategyComputeRequest) -> tuple[Spread, dict[Leg, float]]:
    """Converts a StrategyComputeRequest into a typed Spread and Leg-to-IV mapping."""
    legs_list: list[Leg] = []
    iv_map: dict[Leg, float] = {}

    for idx, leg_req in enumerate(req.legs):
        opt_type = OptionType.CALL if leg_req.option_type == "CE" else OptionType.PUT
        direction = Direction.BUY if leg_req.direction == "buy" else Direction.SELL
        exp_date = datetime.strptime(leg_req.expiry_date, "%Y-%m-%d").date()

        leg = Leg(
            strike=leg_req.strike,
            option_type=opt_type,
            direction=direction,
            quantity_lots=leg_req.quantity_lots,
            entry_premium=leg_req.entry_premium,
            expiry_date=exp_date,
            lot_size=leg_req.lot_size,
        )
        legs_list.append(leg)

        # Resolve IV for this leg from iv_per_leg dict
        key1 = f"{int(leg.strike)}_{leg.option_type.value}"
        key2 = f"{int(leg.strike)}_{leg_req.option_type}"
        key3 = str(idx)

        iv = req.iv_per_leg.get(key1) or req.iv_per_leg.get(key2) or req.iv_per_leg.get(key3)
        if iv is None:
            # Check if caller passed a general default IV, or fallback to current market baseline (13.5%)
            iv = req.iv_per_leg.get("default", 0.135)
        if iv <= 0.0:
            iv = 0.135

        iv_map[leg] = float(iv)

    spread = Spread(name=req.strategy_name, legs=tuple(legs_list), underlying=req.underlying)
    return spread, iv_map


@router.post("/api/strategy/preset")
def get_strategy_preset(
    name: str = Query(..., description="Preset name: bear_put_spread, bull_call_spread, iron_condor, calendar_spread"),
    expiry: str = Query(..., description="Expiry date in YYYY-MM-DD"),
    spot: float = Query(..., gt=0.0, description="Current spot price"),
    far_expiry: Optional[str] = Query(default=None, description="Far expiry for calendar spread"),
) -> dict[str, Any]:
    """Returns pre-built strategy legs with strikes snapped to 50-point intervals."""
    try:
        exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid expiry format: {e}") from e

    norm_name = name.lower().replace("-", "_").replace(" ", "_")

    if norm_name in ("bear_put_spread", "bear_put"):
        spread = bear_put_spread(current_spot=spot, expiry=exp_date)
    elif norm_name in ("bull_call_spread", "bull_call"):
        spread = bull_call_spread(current_spot=spot, expiry=exp_date)
    elif norm_name in ("iron_condor", "condor"):
        spread = iron_condor(current_spot=spot, expiry=exp_date)
    elif norm_name in ("calendar_spread", "calendar"):
        if not far_expiry:
            raise HTTPException(status_code=400, detail="far_expiry is required for calendar_spread.")
        far_date = datetime.strptime(far_expiry, "%Y-%m-%d").date()
        spread = calendar_spread(current_spot=spot, near_expiry=exp_date, far_expiry=far_date)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown preset name: {name}")

    legs_data = []
    for leg in spread.legs:
        legs_data.append({
            "strike": leg.strike,
            "option_type": leg.option_type.value,
            "direction": leg.direction.value,
            "quantity_lots": leg.quantity_lots,
            "entry_premium": leg.entry_premium,
            "expiry_date": leg.expiry_date.isoformat(),
            "lot_size": leg.lot_size,
        })

    return {
        "strategy_name": spread.name,
        "underlying": spread.underlying,
        "legs": legs_data,
        "spot": spot,
    }


def compute_probability_of_profit(
    spread: Spread,
    current_spot: float,
    iv_map: dict[Leg, float],
    as_of_date: date,
    breakevens: list[float],
) -> float:
    """Computes Probability of Profit (POP) % under lognormal terminal price distribution."""
    if not spread.legs:
        return 50.0

    min_expiry = min(leg.expiry_date for leg in spread.legs)
    days_to_expiry = max((min_expiry - as_of_date).days, 0)
    tte_years = days_to_expiry / 365.0

    # If at or past expiry, check current P&L directly
    if tte_years <= 0.0:
        pnl = _spread_expiry_pnl(spread, current_spot)
        return 100.0 if pnl >= 0.0 else 0.0

    # Average IV across spread legs
    avg_iv = sum(iv_map.values()) / len(iv_map) if iv_map else 0.15
    if avg_iv <= 0.0:
        avg_iv = 0.15

    r = 0.065  # standard Indian market risk-free rate
    mu = math.log(current_spot) + (r - 0.5 * (avg_iv ** 2)) * tte_years
    s = avg_iv * math.sqrt(tte_years)

    def norm_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    if not breakevens:
        pnl_spot = _spread_expiry_pnl(spread, current_spot)
        return 100.0 if pnl_spot >= 0.0 else 0.0

    if len(breakevens) == 1:
        be = breakevens[0]
        d = (math.log(be) - mu) / s
        p_below = norm_cdf(d)
        if _spread_expiry_pnl(spread, be + 20.0) > 0.0:
            pop = (1.0 - p_below) * 100.0
        else:
            pop = p_below * 100.0
    elif len(breakevens) == 2:
        be1, be2 = sorted(breakevens)[:2]
        d1 = (math.log(be1) - mu) / s
        d2 = (math.log(be2) - mu) / s
        p_between = norm_cdf(d2) - norm_cdf(d1)
        mid = (be1 + be2) / 2.0
        if _spread_expiry_pnl(spread, mid) > 0.0:
            pop = p_between * 100.0
        else:
            pop = (1.0 - p_between) * 100.0
    else:
        # Multiple breakevens: integrate positive payoff regions across lognormal PDF
        low_spot = current_spot * 0.70
        high_spot = current_spot * 1.30
        n_samples = 200
        step = (high_spot - low_spot) / (n_samples - 1)
        pop_accum = 0.0
        for i in range(n_samples):
            test_spot = low_spot + i * step
            if _spread_expiry_pnl(spread, test_spot) >= 0.0:
                d = (math.log(test_spot) - mu) / s
                pdf = (1.0 / (test_spot * s * math.sqrt(2.0 * math.pi))) * math.exp(-0.5 * d * d)
                pop_accum += pdf * step
        pop = pop_accum * 100.0

    return max(0.0, min(100.0, round(pop, 1)))


@router.post("/api/strategy/compute", response_model=StrategyComputeResponse)
def compute_strategy(req: StrategyComputeRequest) -> StrategyComputeResponse:
    """Computes dual-horizon payoff curve and portfolio Greeks for a spread."""
    spread, iv_map = build_spread_from_request(req)

    # 1. Validate target_date
    as_of = date.today()
    if req.target_date:
        try:
            as_of = datetime.strptime(req.target_date, "%Y-%m-%d").date()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid target_date format: {e}") from e

    min_expiry = min(leg.expiry_date for leg in spread.legs)
    if as_of > min_expiry:
        raise HTTPException(status_code=400, detail="target_date after expiry")

    # 2. Validate iv_shift_pct
    if req.iv_shift_pct < -90.0 or req.iv_shift_pct > 200.0:
        raise HTTPException(status_code=400, detail="iv_shift_pct outside [-90, +200]")

    if req.iv_shift_pct != 0.0:
        factor = 1.0 + (req.iv_shift_pct / 100.0)
        for leg in list(iv_map.keys()):
            iv_map[leg] = max(iv_map[leg] * factor, 0.001)

    try:
        curve = compute_payoff_curve(
            spread=spread,
            current_spot=req.current_spot,
            current_iv_per_leg=iv_map,
            as_of_date=as_of,
            n_points=100,
        )
        greeks_summary = compute_position_greeks(
            spread=spread,
            current_spot=req.current_spot,
            current_iv_per_leg=iv_map,
            as_of_date=as_of,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Computation error: {e}") from e

    points_resp = [
        PayoffPointResponse(
            spot=round(p.spot, 2),
            pnl_expiry=round(p.pnl_at_expiry, 2),
            pnl_today=round(p.pnl_today, 2),
            pnl=round(p.pnl_today, 2),
        )
        for p in curve.points
    ]

    points_expiry = [
        PayoffPointResponse(
            spot=round(p.spot, 2),
            pnl_expiry=round(p.pnl_at_expiry, 2),
            pnl_today=round(p.pnl_at_expiry, 2),
            pnl=round(p.pnl_at_expiry, 2),
        )
        for p in curve.points
    ]

    points_target = [
        PayoffPointResponse(
            spot=round(p.spot, 2),
            pnl_expiry=round(p.pnl_at_expiry, 2),
            pnl_today=round(p.pnl_today, 2),
            pnl=round(p.pnl_today, 2),
        )
        for p in curve.points
    ]

    breakevens_rounded = [round(b, 2) for b in curve.breakevens]
    payoff_resp = PayoffCurveResponse(
        spot_range=[round(curve.spot_range[0], 2), round(curve.spot_range[1], 2)],
        points=points_resp,
        breakevens=breakevens_rounded,
        max_profit_inr=round(curve.max_profit_inr, 2),
        max_loss_inr=round(curve.max_loss_inr, 2),
        rr_implied=round(curve.rr_implied, 2),
        net_debit_credit_inr=round(curve.net_debit_credit_inr, 2),
    )

    payoff_curve_expiry = PayoffCurveResponse(
        spot_range=[round(curve.spot_range[0], 2), round(curve.spot_range[1], 2)],
        points=points_expiry,
        breakevens=breakevens_rounded,
        max_profit_inr=round(curve.max_profit_inr, 2),
        max_loss_inr=round(curve.max_loss_inr, 2),
        rr_implied=round(curve.rr_implied, 2),
        net_debit_credit_inr=round(curve.net_debit_credit_inr, 2),
    )

    payoff_curve_target = PayoffCurveResponse(
        spot_range=[round(curve.spot_range[0], 2), round(curve.spot_range[1], 2)],
        points=points_target,
        breakevens=breakevens_rounded,
        max_profit_inr=round(curve.max_profit_inr, 2),
        max_loss_inr=round(curve.max_loss_inr, 2),
        rr_implied=round(curve.rr_implied, 2),
        net_debit_credit_inr=round(curve.net_debit_credit_inr, 2),
    )

    # 3. Compute POP
    pop = compute_probability_of_profit(
        spread=spread,
        current_spot=req.current_spot,
        iv_map=iv_map,
        as_of_date=as_of,
        breakevens=breakevens_rounded,
    )

    # 4. Compute per-leg Greeks
    per_leg_items: list[LegGreeksItem] = []
    for leg in spread.legs:
        iv = iv_map[leg]
        days_to_expiry = max((leg.expiry_date - as_of).days, 0)
        tte_years = days_to_expiry / 365.0
        g = calc_greeks(
            spot=req.current_spot,
            strike=leg.strike,
            tte_years=tte_years,
            iv=iv,
            r=None,
            option_type=leg.option_type,
        )
        direction_sign = 1.0 if leg.direction == Direction.BUY else -1.0
        qty_shares = leg.quantity_lots * leg.lot_size * direction_sign
        per_leg_items.append(
            LegGreeksItem(
                strike=leg.strike,
                option_type=leg.option_type.value,
                direction=leg.direction.value,
                delta=round(g["delta"] * direction_sign, 2),
                theta=round(g["theta"] * qty_shares, 1),
                vega=round(g["vega"] * qty_shares, 1),
                gamma=round(g["gamma"] * direction_sign, 4),
            )
        )

    greeks_resp = GreeksResponse(
        net_delta=round(greeks_summary.net_delta, 4),
        net_gamma=round(greeks_summary.net_gamma, 6),
        net_theta_per_day=round(greeks_summary.net_theta_per_day, 2),
        net_vega=round(greeks_summary.net_vega, 2),
        net_rho=round(greeks_summary.net_rho, 2),
        pop=pop,
        per_leg=per_leg_items,
    )

    return StrategyComputeResponse(
        payoff_curve=payoff_curve_expiry,
        payoff_curve_expiry=payoff_curve_expiry,
        payoff_curve_target=payoff_curve_target,
        greeks=greeks_resp,
        pop=pop,
        per_leg=per_leg_items,
    )
