"""
Statistical Risk Engine for Swayam Capital.

Computes expected worst-case loss under realistic market stress scenarios
(e.g., 2-sigma move based on 20-day trailing realized volatility).
"""

from datetime import date
from typing import Optional
from swayam.options_math.models import Leg
from swayam.options_math.payoff import pnl_at_spot
from swayam.options_math.realized_vol import daily_sigma_from_annualized


def compute_expected_worst_case_loss(
    legs: list[Leg],
    current_spot: float,
    annualized_vol: float,
    stress_sigma: float = 2.0,
    days_to_expiry: Optional[int] = None,
    current_iv_per_leg: Optional[dict[Leg, float]] = None,
    as_of_date: Optional[date] = None,
) -> float:
    """Computes expected worst-case loss in rupees under +/- stress_sigma market move.

    Args:
        legs: Option legs in the spread.
        current_spot: Current underlying index spot price.
        annualized_vol: Annualized realized volatility as a decimal (e.g. 0.15 for 15%).
        stress_sigma: Standard deviation multiplier for the stress test (default: 2.0).
        days_to_expiry: Remaining days to expiration. If None, dynamically calculated from legs at T+1.
        current_iv_per_leg: Optional mapping of leg to IV decimal.
        as_of_date: Optional reference evaluation date.

    Returns:
        float: Expected worst-case loss in rupees as a positive number (0.0 if spread profits).
    """
    daily_sigma = daily_sigma_from_annualized(annualized_vol)

    spot_up = current_spot * (1.0 + stress_sigma * daily_sigma)
    spot_down = current_spot * (1.0 - stress_sigma * daily_sigma)

    pnl_up = pnl_at_spot(
        legs,
        spot_up,
        days_to_expiry=days_to_expiry,
        current_iv_per_leg=current_iv_per_leg,
        as_of_date=as_of_date,
    )
    pnl_down = pnl_at_spot(
        legs,
        spot_down,
        days_to_expiry=days_to_expiry,
        current_iv_per_leg=current_iv_per_leg,
        as_of_date=as_of_date,
    )

    worst_pnl = min(pnl_up, pnl_down)
    # Convert to positive loss figure: positive if loss, 0.0 if profit
    realistic_loss = max(0.0, -worst_pnl)
    return realistic_loss
