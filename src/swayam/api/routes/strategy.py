"""
Strategy preset and payoff computation endpoints for Swayam Capital.
"""

from datetime import date, datetime
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query
from swayam.api.models_api import (
    GreeksResponse,
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
            # Check if caller passed a general default IV or raise
            if "default" in req.iv_per_leg:
                iv = req.iv_per_leg["default"]
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing implied volatility for leg strike={leg.strike}, type={leg.option_type.value}. Provide key '{key1}' in iv_per_leg.",
                )
        if iv <= 0.0:
            raise HTTPException(status_code=400, detail=f"IV must be positive; got {iv}")

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


@router.post("/api/strategy/compute", response_model=StrategyComputeResponse)
def compute_strategy(req: StrategyComputeRequest) -> StrategyComputeResponse:
    """Computes dual-horizon payoff curve and portfolio Greeks for a spread."""
    spread, iv_map = build_spread_from_request(req)

    try:
        curve = compute_payoff_curve(
            spread=spread,
            current_spot=req.current_spot,
            current_iv_per_leg=iv_map,
            as_of_date=date.today(),
            n_points=100,
        )
        greeks_summary = compute_position_greeks(
            spread=spread,
            current_spot=req.current_spot,
            current_iv_per_leg=iv_map,
            as_of_date=date.today(),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Computation error: {e}") from e

    points_resp = [
        PayoffPointResponse(
            spot=round(p.spot, 2),
            pnl_expiry=round(p.pnl_at_expiry, 2),
            pnl_today=round(p.pnl_today, 2),
        )
        for p in curve.points
    ]

    payoff_resp = PayoffCurveResponse(
        spot_range=[round(curve.spot_range[0], 2), round(curve.spot_range[1], 2)],
        points=points_resp,
        breakevens=[round(b, 2) for b in curve.breakevens],
        max_profit_inr=round(curve.max_profit_inr, 2),
        max_loss_inr=round(curve.max_loss_inr, 2),
        rr_implied=round(curve.rr_implied, 2),
        net_debit_credit_inr=round(curve.net_debit_credit_inr, 2),
    )

    greeks_resp = GreeksResponse(
        net_delta=round(greeks_summary.net_delta, 4),
        net_gamma=round(greeks_summary.net_gamma, 6),
        net_theta_per_day=round(greeks_summary.net_theta_per_day, 2),
        net_vega=round(greeks_summary.net_vega, 2),
        net_rho=round(greeks_summary.net_rho, 2),
    )

    return StrategyComputeResponse(payoff_curve=payoff_resp, greeks=greeks_resp)
