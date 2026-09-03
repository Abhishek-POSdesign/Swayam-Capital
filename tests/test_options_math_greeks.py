"""
Unit tests for Swayam Capital Options Math Engine - Aggregated Greeks.
"""

from datetime import date, timedelta
import pytest
from swayam.options_math.greeks import compute_position_greeks
from swayam.options_math.models import Direction, Leg, OptionType, Spread


def test_long_call_has_positive_delta_and_short_call_has_negative_delta() -> None:
    as_of = date(2026, 9, 10)
    expiry = as_of + timedelta(days=14)

    long_call = Leg(strike=25000.0, option_type=OptionType.CALL, direction=Direction.BUY, quantity_lots=1, entry_premium=100.0, expiry_date=expiry, lot_size=75)
    short_call = Leg(strike=25000.0, option_type=OptionType.CALL, direction=Direction.SELL, quantity_lots=1, entry_premium=100.0, expiry_date=expiry, lot_size=75)

    greeks_long = compute_position_greeks(Spread(name="Long Call", legs=(long_call,)), 25000.0, {long_call: 0.15}, as_of)
    greeks_short = compute_position_greeks(Spread(name="Short Call", legs=(short_call,)), 25000.0, {short_call: 0.15}, as_of)

    assert greeks_long.net_delta > 0.0
    assert greeks_short.net_delta < 0.0
    assert abs(greeks_long.net_delta + greeks_short.net_delta) < 0.001


def test_long_options_have_positive_vega_and_short_options_negative_vega() -> None:
    as_of = date(2026, 9, 10)
    expiry = as_of + timedelta(days=20)

    long_put = Leg(strike=24800.0, option_type=OptionType.PUT, direction=Direction.BUY, quantity_lots=1, entry_premium=150.0, expiry_date=expiry, lot_size=75)
    short_put = Leg(strike=24800.0, option_type=OptionType.PUT, direction=Direction.SELL, quantity_lots=1, entry_premium=150.0, expiry_date=expiry, lot_size=75)

    greeks_long = compute_position_greeks(Spread(name="Long Put", legs=(long_put,)), 24800.0, {long_put: 0.16}, as_of)
    greeks_short = compute_position_greeks(Spread(name="Short Put", legs=(short_put,)), 24800.0, {short_put: 0.16}, as_of)

    assert greeks_long.net_vega > 0.0
    assert greeks_short.net_vega < 0.0


def test_long_options_have_negative_theta_and_short_options_positive_theta() -> None:
    as_of = date(2026, 9, 10)
    expiry = as_of + timedelta(days=20)

    long_call = Leg(strike=25000.0, option_type=OptionType.CALL, direction=Direction.BUY, quantity_lots=1, entry_premium=120.0, expiry_date=expiry, lot_size=75)
    short_call = Leg(strike=25000.0, option_type=OptionType.CALL, direction=Direction.SELL, quantity_lots=1, entry_premium=120.0, expiry_date=expiry, lot_size=75)

    greeks_long = compute_position_greeks(Spread(name="Long Call", legs=(long_call,)), 25000.0, {long_call: 0.15}, as_of)
    greeks_short = compute_position_greeks(Spread(name="Short Call", legs=(short_call,)), 25000.0, {short_call: 0.15}, as_of)

    # Long options bleed theta (negative ₹/day)
    assert greeks_long.net_theta_per_day < 0.0
    # Short options collect theta (positive ₹/day)
    assert greeks_short.net_theta_per_day > 0.0


def test_symmetric_iron_condor_has_near_zero_delta_and_positive_theta() -> None:
    as_of = date(2026, 9, 10)
    expiry = as_of + timedelta(days=14)
    spot = 25000.0

    # Symmetric Iron Condor: 4% OTM short strikes (24000 PE and 26000 CE), 6% OTM long wings (23500 PE and 26500 CE)
    sell_ce = Leg(strike=26000.0, option_type=OptionType.CALL, direction=Direction.SELL, quantity_lots=1, entry_premium=30.0, expiry_date=expiry, lot_size=75)
    buy_ce = Leg(strike=26500.0, option_type=OptionType.CALL, direction=Direction.BUY, quantity_lots=1, entry_premium=10.0, expiry_date=expiry, lot_size=75)
    sell_pe = Leg(strike=24000.0, option_type=OptionType.PUT, direction=Direction.SELL, quantity_lots=1, entry_premium=30.0, expiry_date=expiry, lot_size=75)
    buy_pe = Leg(strike=23500.0, option_type=OptionType.PUT, direction=Direction.BUY, quantity_lots=1, entry_premium=10.0, expiry_date=expiry, lot_size=75)

    legs = (sell_ce, buy_ce, sell_pe, buy_pe)
    spread = Spread(name="Neutral Condor", legs=legs)
    iv_map = {leg: 0.15 for leg in legs}

    g = compute_position_greeks(spread, spot, iv_map, as_of)

    # Delta should be very small (near delta neutral)
    assert abs(g.net_delta) < 5.0
    # Iron Condor seller earns positive theta (rupees per day)
    assert g.net_theta_per_day > 0.0


def test_position_greeks_raises_on_missing_iv() -> None:
    as_of = date(2026, 9, 10)
    expiry = as_of + timedelta(days=14)
    leg = Leg(strike=25000.0, option_type=OptionType.CALL, direction=Direction.BUY, quantity_lots=1, entry_premium=100.0, expiry_date=expiry, lot_size=75)
    spread = Spread(name="Missing IV Greeks", legs=(leg,))

    with pytest.raises(ValueError, match="Missing implied volatility"):
        compute_position_greeks(spread, 25000.0, {}, as_of)
