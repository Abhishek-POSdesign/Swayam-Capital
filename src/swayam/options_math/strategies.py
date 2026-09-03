"""
Strategy template factory presets for Swayam Capital.

Generates structured multi-leg option spreads (Bear Put Spread, Bull Call Spread,
Iron Condor, and Calendar Spread) with strikes automatically snapped to standard
50-point NIFTY interval granularity.
"""

from datetime import date
from swayam.options_math.models import Direction, Leg, OptionType, Spread


def snap_to_strike(raw_price: float, interval: float = 50.0) -> float:
    """Snaps a continuous price level to the nearest strike grid interval.

    Args:
        raw_price: Calculated strike price (e.g. 24867 * 0.98 = 24369.66).
        interval: Strike spacing interval in points (default: 50 for NIFTY).

    Returns:
        float: Snapped strike price (e.g. 24350.0).
    """
    return round(raw_price / interval) * interval


def bear_put_spread(
    current_spot: float,
    expiry: date,
    otm_pct: float = 0.02,
    wing_pct: float = 0.03,
    quantity_lots: int = 1,
    lot_size: int = 75,
) -> Spread:
    """Creates a Bear Put Spread template (Long Higher PE + Short Lower PE).

    Args:
        current_spot: Current underlying spot price.
        expiry: Option expiration date.
        otm_pct: OTM distance for long put (default: 2% below spot).
        wing_pct: Spread width distance for short put (default: 3% further below).
        quantity_lots: Number of lots (default: 1).
        lot_size: Shares per lot (default: 75).

    Returns:
        Spread: Pre-populated Bear Put Spread.
    """
    buy_strike = snap_to_strike(current_spot * (1.0 - otm_pct))
    sell_strike = snap_to_strike(current_spot * (1.0 - otm_pct - wing_pct))

    if sell_strike >= buy_strike:
        sell_strike = buy_strike - 50.0

    leg_buy = Leg(
        strike=buy_strike,
        option_type=OptionType.PUT,
        direction=Direction.BUY,
        quantity_lots=quantity_lots,
        entry_premium=0.0,
        expiry_date=expiry,
        lot_size=lot_size,
    )
    leg_sell = Leg(
        strike=sell_strike,
        option_type=OptionType.PUT,
        direction=Direction.SELL,
        quantity_lots=quantity_lots,
        entry_premium=0.0,
        expiry_date=expiry,
        lot_size=lot_size,
    )

    return Spread(
        name="Bear Put Spread",
        legs=(leg_buy, leg_sell),
        underlying="NIFTY",
    )


def bull_call_spread(
    current_spot: float,
    expiry: date,
    otm_pct: float = 0.02,
    wing_pct: float = 0.03,
    quantity_lots: int = 1,
    lot_size: int = 75,
) -> Spread:
    """Creates a Bull Call Spread template (Long Lower CE + Short Higher CE).

    Args:
        current_spot: Current underlying spot price.
        expiry: Option expiration date.
        otm_pct: OTM distance for long call (default: 2% above spot).
        wing_pct: Spread width distance for short call (default: 3% further above).
        quantity_lots: Number of lots (default: 1).
        lot_size: Shares per lot (default: 75).

    Returns:
        Spread: Pre-populated Bull Call Spread.
    """
    buy_strike = snap_to_strike(current_spot * (1.0 + otm_pct))
    sell_strike = snap_to_strike(current_spot * (1.0 + otm_pct + wing_pct))

    if sell_strike <= buy_strike:
        sell_strike = buy_strike + 50.0

    leg_buy = Leg(
        strike=buy_strike,
        option_type=OptionType.CALL,
        direction=Direction.BUY,
        quantity_lots=quantity_lots,
        entry_premium=0.0,
        expiry_date=expiry,
        lot_size=lot_size,
    )
    leg_sell = Leg(
        strike=sell_strike,
        option_type=OptionType.CALL,
        direction=Direction.SELL,
        quantity_lots=quantity_lots,
        entry_premium=0.0,
        expiry_date=expiry,
        lot_size=lot_size,
    )

    return Spread(
        name="Bull Call Spread",
        legs=(leg_buy, leg_sell),
        underlying="NIFTY",
    )


def iron_condor(
    current_spot: float,
    expiry: date,
    wing_pct: float = 0.04,
    tail_pct: float = 0.06,
    quantity_lots: int = 1,
    lot_size: int = 75,
) -> Spread:
    """Creates a 4-leg Iron Condor template (Short Call Spread + Short Put Spread).

    Args:
        current_spot: Current underlying spot price.
        expiry: Option expiration date.
        wing_pct: Distance for short strikes (default: 4% OTM).
        tail_pct: Distance for protective long strikes (default: 6% OTM).
        quantity_lots: Number of lots (default: 1).
        lot_size: Shares per lot (default: 75).

    Returns:
        Spread: Pre-populated 4-leg Iron Condor.
    """
    sell_ce = snap_to_strike(current_spot * (1.0 + wing_pct))
    buy_ce = snap_to_strike(current_spot * (1.0 + tail_pct))
    if buy_ce <= sell_ce:
        buy_ce = sell_ce + 50.0

    sell_pe = snap_to_strike(current_spot * (1.0 - wing_pct))
    buy_pe = snap_to_strike(current_spot * (1.0 - tail_pct))
    if buy_pe >= sell_pe:
        buy_pe = sell_pe - 50.0

    legs = (
        Leg(strike=sell_ce, option_type=OptionType.CALL, direction=Direction.SELL, quantity_lots=quantity_lots, entry_premium=0.0, expiry_date=expiry, lot_size=lot_size),
        Leg(strike=buy_ce, option_type=OptionType.CALL, direction=Direction.BUY, quantity_lots=quantity_lots, entry_premium=0.0, expiry_date=expiry, lot_size=lot_size),
        Leg(strike=sell_pe, option_type=OptionType.PUT, direction=Direction.SELL, quantity_lots=quantity_lots, entry_premium=0.0, expiry_date=expiry, lot_size=lot_size),
        Leg(strike=buy_pe, option_type=OptionType.PUT, direction=Direction.BUY, quantity_lots=quantity_lots, entry_premium=0.0, expiry_date=expiry, lot_size=lot_size),
    )

    return Spread(
        name="Iron Condor",
        legs=legs,
        underlying="NIFTY",
    )


def calendar_spread(
    current_spot: float,
    near_expiry: date,
    far_expiry: date,
    atm_pct: float = 0.0,
    quantity_lots: int = 1,
    lot_size: int = 75,
) -> Spread:
    """Creates a Calendar Spread template (Short Near-Expiry + Long Far-Expiry at same strike).

    Args:
        current_spot: Current underlying spot price.
        near_expiry: Near-month expiration date.
        far_expiry: Far-month expiration date.
        atm_pct: Distance from spot (default: 0.0 for ATM).
        quantity_lots: Number of lots (default: 1).
        lot_size: Shares per lot (default: 75).

    Returns:
        Spread: Pre-populated Calendar Spread.
    """
    if near_expiry >= far_expiry:
        raise ValueError(f"near_expiry ({near_expiry}) must be strictly earlier than far_expiry ({far_expiry}).")

    strike = snap_to_strike(current_spot * (1.0 + atm_pct))

    leg_near = Leg(
        strike=strike,
        option_type=OptionType.CALL,
        direction=Direction.SELL,
        quantity_lots=quantity_lots,
        entry_premium=0.0,
        expiry_date=near_expiry,
        lot_size=lot_size,
    )
    leg_far = Leg(
        strike=strike,
        option_type=OptionType.CALL,
        direction=Direction.BUY,
        quantity_lots=quantity_lots,
        entry_premium=0.0,
        expiry_date=far_expiry,
        lot_size=lot_size,
    )

    return Spread(
        name="Calendar Spread",
        legs=(leg_near, leg_far),
        underlying="NIFTY",
    )
