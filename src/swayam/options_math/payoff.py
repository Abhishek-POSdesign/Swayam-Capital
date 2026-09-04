"""
Options payoff curve computation engine for Swayam Capital.

Computes dual-horizon payoff curves (T+0 today vs At-Expiry) for single and multi-leg
option spreads across a ±10% underlying spot price range. Calculates exact zero-crossing
breakeven points, maximum profit, maximum loss, and implied reward-to-risk ratio.
"""

from datetime import date
from typing import Optional
from swayam.options_math.engine import black_scholes_price
from swayam.options_math.models import Direction, Leg, OptionType, PayoffCurve, PayoffPoint, Spread


def _leg_intrinsic_value(leg: Leg, spot: float) -> float:
    """Calculates intrinsic value of an option leg at a given spot price."""
    if leg.option_type == OptionType.CALL:
        return max(spot - leg.strike, 0.0)
    elif leg.option_type == OptionType.PUT:
        return max(leg.strike - spot, 0.0)
    raise ValueError(f"Unrecognized option type: {leg.option_type}")


def _leg_expiry_pnl(leg: Leg, spot: float) -> float:
    """Calculates realized P&L for a single leg in rupees if expired at spot."""
    intrinsic = _leg_intrinsic_value(leg, spot)
    qty_shares = leg.quantity_lots * leg.lot_size

    if leg.direction == Direction.BUY:
        return (intrinsic - leg.entry_premium) * qty_shares
    elif leg.direction == Direction.SELL:
        return (leg.entry_premium - intrinsic) * qty_shares
    raise ValueError(f"Unrecognized direction: {leg.direction}")


def _spread_expiry_pnl(spread: Spread, spot: float) -> float:
    """Calculates aggregate at-expiry P&L in rupees for a spread at spot."""
    return sum(_leg_expiry_pnl(leg, spot) for leg in spread.legs)


def compute_net_debit_credit(spread: Spread) -> float:
    """Calculates net cash flow at entry in rupees.

    Returns:
        float: Negative if debit paid, positive if credit received.
    """
    net_inr = 0.0
    for leg in spread.legs:
        qty_shares = leg.quantity_lots * leg.lot_size
        if leg.direction == Direction.BUY:
            net_inr -= leg.entry_premium * qty_shares
        elif leg.direction == Direction.SELL:
            net_inr += leg.entry_premium * qty_shares
    return net_inr


def compute_breakevens(spread: Spread, spot_range: Optional[tuple[float, float]] = None) -> tuple[float, ...]:
    """Finds underlying spot prices where at-expiry P&L crosses zero.

    Args:
        spread: Options spread.
        spot_range: Optional search range (min_spot, max_spot).

    Returns:
        tuple[float, ...]: Sorted list of unique breakeven spot prices.
    """
    if not spread.legs:
        return ()

    strikes = [leg.strike for leg in spread.legs]
    min_strike, max_strike = min(strikes), max(strikes)

    if spot_range is not None:
        low, high = spot_range
    else:
        # Search generously around strikes
        low = max(min_strike * 0.70, 1.0)
        high = max_strike * 1.30

    # Sample 1000 points to detect all zero crossings
    n_samples = 1000
    step = (high - low) / (n_samples - 1)
    breakevens: list[float] = []

    prev_spot = low
    prev_pnl = _spread_expiry_pnl(spread, prev_spot)

    for i in range(1, n_samples):
        curr_spot = low + i * step
        curr_pnl = _spread_expiry_pnl(spread, curr_spot)

        # Check for zero crossing (sign change or edge of flat zero zone)
        if (prev_pnl < 0.0 and curr_pnl > 0.0) or (prev_pnl > 0.0 and curr_pnl < 0.0):
            # Linear interpolation for exact zero crossing
            crossing = prev_spot + (-prev_pnl / (curr_pnl - prev_pnl)) * (curr_spot - prev_spot)
            breakevens.append(round(crossing, 2))
        elif curr_pnl == 0.0 and prev_pnl != 0.0:
            breakevens.append(round(curr_spot, 2))
        elif prev_pnl == 0.0 and curr_pnl != 0.0:
            breakevens.append(round(prev_spot, 2))

        prev_spot = curr_spot
        prev_pnl = curr_pnl

    # Remove duplicates within 0.1 point tolerance
    unique_bes: list[float] = []
    for be in breakevens:
        if not any(abs(be - u) < 0.1 for u in unique_bes):
            unique_bes.append(be)

    return tuple(sorted(unique_bes))


def compute_max_profit_loss(
    spread: Spread,
    spot_range: Optional[tuple[float, float]] = None,
) -> tuple[float, float]:
    """Calculates analytical/numerical max profit and max loss in rupees at expiry.

    Args:
        spread: Options spread.
        spot_range: Optional evaluation range.

    Returns:
        tuple[float, float]: (max_profit_inr, max_loss_inr).
                             max_loss_inr is returned as a positive magnitude.
    """
    if not spread.legs:
        return (0.0, 0.0)

    strikes = [leg.strike for leg in spread.legs]
    min_strike, max_strike = min(strikes), max(strikes)

    if spot_range is not None:
        low, high = spot_range
    else:
        low = max(min_strike * 0.75, 1.0)
        high = max_strike * 1.25

    # Check P&L at all strikes and domain boundaries
    test_points = sorted(set([low, high] + strikes + [s - 100 for s in strikes] + [s + 100 for s in strikes]))
    pnls = [_spread_expiry_pnl(spread, s) for s in test_points]

    max_p = max(pnls)
    min_p = min(pnls)

    max_profit = max(max_p, 0.0)
    max_loss = abs(min(min_p, 0.0))

    return (max_profit, max_loss)


def compute_payoff_curve(
    spread: Spread,
    current_spot: float,
    current_iv_per_leg: dict[Leg, float],
    as_of_date: date,
    n_points: int = 100,
) -> PayoffCurve:
    """Generates the full dual-horizon payoff curve across a ±10% spot range.

    Args:
        spread: The multi-leg spread being analyzed.
        current_spot: Current underlying index/stock spot price.
        current_iv_per_leg: Mapping of each Leg to its current implied volatility.
        as_of_date: Evaluation date (e.g. today).
        n_points: Number of discrete spot points to compute (default: 100).

    Returns:
        PayoffCurve: Complete analysis with points, breakevens, and risk metrics.

    Raises:
        ValueError: If any leg is missing from current_iv_per_leg, or n_points < 2.
    """
    if n_points < 2:
        raise ValueError(f"n_points must be at least 2; got {n_points}")

    for leg in spread.legs:
        if leg not in current_iv_per_leg:
            raise ValueError(f"Missing implied volatility for leg: {leg}")

    # Step 1: Determine 10% spot window
    low_spot = current_spot * 0.90
    high_spot = current_spot * 1.10
    step = (high_spot - low_spot) / (n_points - 1)

    # Pre-calculate time to expiration per leg
    ttes_years: dict[Leg, float] = {}
    for leg in spread.legs:
        days_to_expiry = (leg.expiry_date - as_of_date).days
        ttes_years[leg] = max(days_to_expiry, 0) / 365.0

    points: list[PayoffPoint] = []

    for i in range(n_points):
        spot = low_spot + i * step
        pnl_expiry = _spread_expiry_pnl(spread, spot)

        # Compute T+0 theoretical P&L
        pnl_today = 0.0
        for leg in spread.legs:
            qty_shares = leg.quantity_lots * leg.lot_size
            iv = current_iv_per_leg[leg]
            tte = ttes_years[leg]

            theo_price = black_scholes_price(
                spot=spot,
                strike=leg.strike,
                tte_years=tte,
                iv=iv,
                r=None,  # reads settings.risk_free_rate
                option_type=leg.option_type,
            )

            if leg.direction == Direction.BUY:
                pnl_today += (theo_price - leg.entry_premium) * qty_shares
            elif leg.direction == Direction.SELL:
                pnl_today += (leg.entry_premium - theo_price) * qty_shares

        points.append(PayoffPoint(spot=spot, pnl_at_expiry=pnl_expiry, pnl_today=pnl_today))

    # Breakevens and risk metrics
    breakevens = compute_breakevens(spread, spot_range=(low_spot, high_spot))
    max_profit, max_loss = compute_max_profit_loss(spread, spot_range=(low_spot, high_spot))
    net_debit_credit = compute_net_debit_credit(spread)

    rr_implied = (max_profit / max_loss) if max_loss > 0.0 else float("inf")

    return PayoffCurve(
        spot_range=(low_spot, high_spot),
        points=tuple(points),
        breakevens=breakevens,
        max_profit_inr=max_profit,
        max_loss_inr=max_loss,
        rr_implied=rr_implied,
        net_debit_credit_inr=net_debit_credit,
    )


def pnl_at_spot(
    legs: list[Leg],
    target_spot: float,
    days_to_expiry: int = 1,
    current_iv_per_leg: Optional[dict[Leg, float]] = None,
    r: Optional[float] = None,
) -> float:
    """Calculates aggregate P&L in rupees across option legs at a target spot price.

    Uses intrinsic value if days_to_expiry is 0 (at expiration), or Black-Scholes
    pricing if days_to_expiry > 0.

    Args:
        legs: Collection of option legs.
        target_spot: Underlying spot price to evaluate.
        days_to_expiry: Remaining calendar days to expiration (default: 1).
        current_iv_per_leg: Optional map of leg to implied volatility decimal.
        r: Optional risk-free interest rate (defaults to settings.risk_free_rate).

    Returns:
        float: Total P&L in rupees (positive = gain, negative = loss).
    """
    total_pnl = 0.0
    tte_years = max(days_to_expiry, 0) / 365.0

    for leg in legs:
        qty_shares = leg.quantity_lots * leg.lot_size
        if days_to_expiry == 0 or tte_years == 0.0:
            current_value = _leg_intrinsic_value(leg, target_spot)
        else:
            iv = 0.15
            if current_iv_per_leg and leg in current_iv_per_leg:
                iv = current_iv_per_leg[leg]
            current_value = black_scholes_price(
                spot=target_spot,
                strike=leg.strike,
                tte_years=tte_years,
                iv=iv,
                r=r,
                option_type=leg.option_type,
            )

        if leg.direction == Direction.BUY:
            total_pnl += (current_value - leg.entry_premium) * qty_shares
        elif leg.direction == Direction.SELL:
            total_pnl += (leg.entry_premium - current_value) * qty_shares

    return total_pnl

