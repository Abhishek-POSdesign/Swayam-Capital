"""
Aggregated Greeks computation for multi-leg option spreads in Swayam Capital.

Computes total portfolio sensitivities across all legs of a spread, normalized into
clear, actionable units: Net Theta in ₹/day and Net Vega in ₹ per 1% IV move.
"""

from datetime import date
from swayam.options_math.engine import greeks
from swayam.options_math.models import Direction, GreeksSummary, Leg, Spread


def compute_position_greeks(
    spread: Spread,
    current_spot: float,
    current_iv_per_leg: dict[Leg, float],
    as_of_date: date,
) -> GreeksSummary:
    """Computes aggregated position Greeks across all legs of an options spread.

    Units:
    - `net_delta`: Equivalent underlying share exposure.
    - `net_gamma`: Change in net delta per 1 point move in spot.
    - `net_theta_per_day`: Time decay in rupees per calendar day (₹/day).
    - `net_vega`: Rupee gain/loss per 1.0% (100 bps) change in implied volatility.
    - `net_rho`: Rupee sensitivity per 1.0% change in interest rates.

    Args:
        spread: The multi-leg position.
        current_spot: Current underlying spot price.
        current_iv_per_leg: Mapping of each leg to its implied volatility.
        as_of_date: Valuation date (e.g. today).

    Returns:
        GreeksSummary: Aggregated Greeks with standardized units.

    Raises:
        ValueError: If any leg is missing from current_iv_per_leg.
    """
    net_delta = 0.0
    net_gamma = 0.0
    net_theta = 0.0
    net_vega = 0.0
    net_rho = 0.0

    for leg in spread.legs:
        if leg not in current_iv_per_leg:
            raise ValueError(f"Missing implied volatility for leg: {leg}")

        iv = current_iv_per_leg[leg]
        days_to_expiry = (leg.expiry_date - as_of_date).days
        tte_years = max(days_to_expiry, 0) / 365.0

        leg_greeks = greeks(
            spot=current_spot,
            strike=leg.strike,
            tte_years=tte_years,
            iv=iv,
            r=None,  # reads settings.risk_free_rate
            option_type=leg.option_type,
        )

        direction_sign = 1.0 if leg.direction == Direction.BUY else -1.0
        total_shares = leg.quantity_lots * leg.lot_size * direction_sign

        net_delta += leg_greeks["delta"] * total_shares
        net_gamma += leg_greeks["gamma"] * total_shares
        # Note: vollib theta is already per-day per share; multiplying by total_shares gives ₹/day
        net_theta += leg_greeks["theta"] * total_shares
        # Note: vollib vega is already per-1% IV move per share; multiplying by total_shares gives ₹ per 1% IV
        net_vega += leg_greeks["vega"] * total_shares
        net_rho += leg_greeks["rho"] * total_shares

    return GreeksSummary(
        net_delta=round(net_delta, 4),
        net_gamma=round(net_gamma, 6),
        net_theta_per_day=round(net_theta, 2),
        net_vega=round(net_vega, 2),
        net_rho=round(net_rho, 2),
    )
