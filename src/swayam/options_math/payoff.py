"""
Options payoff curve computation engine for Swayam Capital.

Computes dual-horizon payoff curves (T+0 today vs At-Expiry) for single and multi-leg
option spreads across a ±10% underlying spot price range. Calculates exact zero-crossing
breakeven points, maximum profit, maximum loss, and implied reward-to-risk ratio.
"""

import math
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


def net_call_quantity(spread: Spread) -> int:
    """Net long call exposure in shares. Negative means net short calls."""
    total = 0
    for leg in spread.legs:
        if leg.option_type == OptionType.CALL:
            sign = 1 if leg.direction == Direction.BUY else -1
            total += sign * leg.quantity_lots * leg.lot_size
    return total


def net_put_quantity(spread: Spread) -> int:
    """Net long put exposure in shares. Negative means net short puts."""
    total = 0
    for leg in spread.legs:
        if leg.option_type == OptionType.PUT:
            sign = 1 if leg.direction == Direction.BUY else -1
            total += sign * leg.quantity_lots * leg.lot_size
    return total


def loss_is_unbounded(spread: Spread) -> bool:
    """True when the loss at expiry has no ceiling.

    Only the UPSIDE can be truly unbounded: a net short call position loses
    more the higher the underlying goes, forever. The downside is bounded,
    because an index cannot fall below zero, so a net short put position has a
    real, finite, and usually enormous worst case which this module reports
    honestly rather than calling infinite.
    """
    return net_call_quantity(spread) < 0


def unbounded_loss_reason(spread: Spread) -> Optional[str]:
    """Why this structure's loss has no ceiling, in words, or None.

    ROUND 1b, FAULT 0a, from his live test of 11 September 2026. A sold call
    filled at the broker and then could not be recorded: "Out of range float
    values are not JSON compliant". `math.inf` is the honest answer for a net
    short call and it must stay; what it needed was somewhere to go other than
    a numeric column. Storage now writes NULL and stores this sentence beside
    it, so a row read back years from now says WHY it is null rather than
    leaving anyone to guess between unbounded and unknown.
    """
    if not loss_is_unbounded(spread):
        return None
    return (
        "net short calls: above the highest strike the loss has no ceiling, "
        "so there is no worst case at expiry to record"
    )


def bounded_or_none(value: Optional[float]) -> Optional[float]:
    """A number a database column can hold, or None when it is not finite.

    The one place infinity is turned into an absence. Every path that stores or
    returns a risk figure goes through this, so no column and no JSON reply can
    be handed an `Infinity` again.
    """
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if (math.isinf(out) or math.isnan(out)) else out


def compute_max_profit_loss(
    spread: Spread,
    spot_range: Optional[tuple[float, float]] = None,
) -> tuple[float, float]:
    """Max profit and max loss at expiry, in rupees.

    Returns max_loss as a POSITIVE magnitude, or `math.inf` when the loss has
    no ceiling.

    Corrected 2026-09-08. This used to scan a window from 0.75x the lowest
    strike to 1.25x the highest and report the worst point found, which for an
    uncapped structure was not the worst case at all: it was an artefact of the
    window. A short straddle came back as a confident Rs 3,69,200 when the
    honest answer is unlimited, and the black-swan fuse was comparing the
    account against that invented ceiling.

    Now:
      * a net short call position returns math.inf, so any cap comparison
        correctly fails and the interface can render "Unlimited"
      * the downside is evaluated at a spot of zero, which is the real floor
        for an index, rather than at an arbitrary fraction of the low strike
    """
    if not spread.legs:
        return (0.0, 0.0)

    strikes = [leg.strike for leg in spread.legs]
    max_strike = max(strikes)

    if spot_range is not None:
        low, high = spot_range
    else:
        # Zero is the true floor for an index. The upper bound only matters
        # for a bounded structure, where the payoff is flat past the highest
        # strike, so a little beyond it is enough.
        low = 0.0
        high = max_strike * 1.25

    test_points = sorted(
        set([low, high] + strikes + [s - 100 for s in strikes] + [s + 100 for s in strikes])
    )
    test_points = [p for p in test_points if p >= 0.0]
    pnls = [_spread_expiry_pnl(spread, s) for s in test_points]

    max_profit = max(max(pnls), 0.0)

    if loss_is_unbounded(spread):
        return (max_profit, math.inf)

    return (max_profit, abs(min(min(pnls), 0.0)))


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

    # The SAME fault as the maximum loss, one line further on. A structure with
    # no possible loss made this `Infinity`, and it travels into the record
    # beside max_loss_inr. There is no reward-to-risk ratio when there is no
    # risk, and None says that; a number here would be an invention.
    # THERE IS NO REWARD-TO-RISK RATIO WITHOUT A RISK TO DIVIDE BY.
    #
    # Two ways there is none. A structure that cannot lose gives a division by
    # zero, which used to be `Infinity` and travelled into the record beside
    # the maximum loss. And a structure whose loss has NO CEILING gives
    # profit/inf = 0.0, which is worse than useless: "R:R implied 0.00" reads
    # as a measured ratio on a naked short when the truth is that the
    # denominator does not exist. Both are None, and the note says so in words.
    rr_implied = None if (math.isinf(max_loss) or max_loss <= 0.0) else (max_profit / max_loss)
    rr_implied = bounded_or_none(rr_implied)

    return PayoffCurve(
        spot_range=(low_spot, high_spot),
        points=tuple(points),
        breakevens=breakevens,
        max_profit_inr=max_profit,
        # The curve hands out a figure a column and a JSON reply can both hold.
        # `compute_max_profit_loss` still answers `math.inf`, which is the true
        # answer and is what `loss_is_unbounded` and the screens read; it simply
        # stops here rather than travelling into the record.
        max_loss_inr=bounded_or_none(max_loss),
        rr_implied=rr_implied,
        net_debit_credit_inr=net_debit_credit,
    )


def pnl_at_spot(
    legs: list[Leg],
    target_spot: float,
    days_to_expiry: Optional[int] = None,
    current_iv_per_leg: Optional[dict[Leg, float]] = None,
    r: Optional[float] = None,
    as_of_date: Optional[date] = None,
) -> float:
    """Calculates aggregate P&L in rupees across option legs at a target spot price.

    Uses intrinsic value if days_to_expiry is 0 (at expiration), or Black-Scholes
    pricing if days_to_expiry > 0. If days_to_expiry is None, dynamically computes
    remaining days from each leg's expiry_date evaluated at T+1 overnight.

    Args:
        legs: Collection of option legs.
        target_spot: Underlying spot price to evaluate.
        days_to_expiry: Remaining calendar days to expiration (optional).
        current_iv_per_leg: Optional map of leg to implied volatility decimal.
        r: Optional risk-free interest rate (defaults to settings.risk_free_rate).
        as_of_date: Reference evaluation date (defaults to date.today()).

    Returns:
        float: Total P&L in rupees (positive = gain, negative = loss).
    """
    total_pnl = 0.0
    ref_date = as_of_date or date.today()

    for leg in legs:
        qty_shares = leg.quantity_lots * leg.lot_size
        if days_to_expiry is not None:
            leg_days = max(days_to_expiry, 0)
        else:
            leg_days = max((leg.expiry_date - ref_date).days - 1, 0)

        tte_years = leg_days / 365.0

        if leg_days == 0 or tte_years == 0.0:
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
