"""
Unit tests for Swayam Capital Options Math Engine - Payoff Curve Computation.
"""

from datetime import date, timedelta
import pytest
from swayam.options_math.models import Direction, Leg, OptionType, Spread
from swayam.options_math.payoff import (
    compute_breakevens,
    compute_max_profit_loss,
    compute_payoff_curve,
)


def test_bear_put_spread_payoff_profile() -> None:
    expiry = date(2026, 9, 24)
    # Buy 25000 PE at ₹200, Sell 24500 PE at ₹80 (Lot size 75)
    # Net debit = (200 - 80) = ₹120/share -> ₹9,000 total
    # Max loss = ₹9,000
    # Max profit = (500 - 120) * 75 = ₹28,500
    # Breakeven = 25000 - 120 = 24,880.0
    leg1 = Leg(strike=25000.0, option_type=OptionType.PUT, direction=Direction.BUY, quantity_lots=1, entry_premium=200.0, expiry_date=expiry, lot_size=75)
    leg2 = Leg(strike=24500.0, option_type=OptionType.PUT, direction=Direction.SELL, quantity_lots=1, entry_premium=80.0, expiry_date=expiry, lot_size=75)
    spread = Spread(name="Bear Put Spread Test", legs=(leg1, leg2))

    max_p, max_l = compute_max_profit_loss(spread)
    assert abs(max_p - 28500.0) < 1.0
    assert abs(max_l - 9000.0) < 1.0

    bes = compute_breakevens(spread)
    assert len(bes) == 1
    assert abs(bes[0] - 24880.0) < 5.0  # within 5 points of exact analytical breakeven


def test_bull_call_spread_payoff_profile() -> None:
    expiry = date(2026, 9, 24)
    # Buy 24500 CE at ₹200, Sell 25000 CE at ₹80 (Lot size 75)
    # Net debit = ₹120/share = ₹9,000
    # Max loss = ₹9,000
    # Max profit = (500 - 120) * 75 = ₹28,500
    # Breakeven = 24500 + 120 = 24,620.0
    leg1 = Leg(strike=24500.0, option_type=OptionType.CALL, direction=Direction.BUY, quantity_lots=1, entry_premium=200.0, expiry_date=expiry, lot_size=75)
    leg2 = Leg(strike=25000.0, option_type=OptionType.CALL, direction=Direction.SELL, quantity_lots=1, entry_premium=80.0, expiry_date=expiry, lot_size=75)
    spread = Spread(name="Bull Call Spread Test", legs=(leg1, leg2))

    max_p, max_l = compute_max_profit_loss(spread)
    assert abs(max_p - 28500.0) < 1.0
    assert abs(max_l - 9000.0) < 1.0

    bes = compute_breakevens(spread)
    assert len(bes) == 1
    assert abs(bes[0] - 24620.0) < 5.0


def test_iron_condor_payoff_profile() -> None:
    expiry = date(2026, 9, 24)
    # Sell 25500 CE at 50, Buy 25700 CE at 20 (Credit = 30)
    # Sell 24500 PE at 50, Buy 24300 PE at 20 (Credit = 30)
    # Total credit = 60 * 75 = ₹4,500 (Max profit)
    # Wing width = 200 * 75 = ₹15,000 -> Max loss = 15000 - 4500 = ₹10,500
    legs = (
        Leg(strike=25500.0, option_type=OptionType.CALL, direction=Direction.SELL, quantity_lots=1, entry_premium=50.0, expiry_date=expiry, lot_size=75),
        Leg(strike=25700.0, option_type=OptionType.CALL, direction=Direction.BUY, quantity_lots=1, entry_premium=20.0, expiry_date=expiry, lot_size=75),
        Leg(strike=24500.0, option_type=OptionType.PUT, direction=Direction.SELL, quantity_lots=1, entry_premium=50.0, expiry_date=expiry, lot_size=75),
        Leg(strike=24300.0, option_type=OptionType.PUT, direction=Direction.BUY, quantity_lots=1, entry_premium=20.0, expiry_date=expiry, lot_size=75),
    )
    spread = Spread(name="Iron Condor Test", legs=legs)

    max_p, max_l = compute_max_profit_loss(spread)
    assert abs(max_p - 4500.0) < 1.0
    assert abs(max_l - 10500.0) < 1.0

    bes = compute_breakevens(spread)
    # Iron condor has 2 breakeven points: 24500 - 60 = 24440 and 25500 + 60 = 25560
    assert len(bes) == 2
    assert abs(bes[0] - 24440.0) < 10.0
    assert abs(bes[1] - 25560.0) < 10.0


def test_payoff_curve_n_points_parameter_respected() -> None:
    expiry = date(2026, 9, 24)
    leg = Leg(strike=25000.0, option_type=OptionType.CALL, direction=Direction.BUY, quantity_lots=1, entry_premium=100.0, expiry_date=expiry, lot_size=75)
    spread = Spread(name="Single Leg Test", legs=(leg,))
    iv_map = {leg: 0.15}

    curve_50 = compute_payoff_curve(spread, 25000.0, iv_map, as_of_date=date(2026, 9, 10), n_points=50)
    assert len(curve_50.points) == 50

    curve_100 = compute_payoff_curve(spread, 25000.0, iv_map, as_of_date=date(2026, 9, 10), n_points=100)
    assert len(curve_100.points) == 100


def test_payoff_curve_t_plus_zero_differs_from_at_expiry() -> None:
    as_of = date(2026, 9, 10)
    expiry = as_of + timedelta(days=14)
    leg1 = Leg(strike=25000.0, option_type=OptionType.PUT, direction=Direction.BUY, quantity_lots=1, entry_premium=200.0, expiry_date=expiry, lot_size=75)
    leg2 = Leg(strike=24500.0, option_type=OptionType.PUT, direction=Direction.SELL, quantity_lots=1, entry_premium=80.0, expiry_date=expiry, lot_size=75)
    spread = Spread(name="Spread Curve Test", legs=(leg1, leg2))
    iv_map = {leg1: 0.16, leg2: 0.16}

    curve = compute_payoff_curve(spread, current_spot=24800.0, current_iv_per_leg=iv_map, as_of_date=as_of, n_points=100)
    # Check that T+0 and expiry points are not identical (time value exists)
    differences = [abs(p.pnl_today - p.pnl_at_expiry) for p in curve.points]
    assert max(differences) > 500.0


def test_compute_payoff_curve_raises_on_missing_iv() -> None:
    expiry = date(2026, 9, 24)
    leg = Leg(strike=25000.0, option_type=OptionType.CALL, direction=Direction.BUY, quantity_lots=1, entry_premium=100.0, expiry_date=expiry, lot_size=75)
    spread = Spread(name="Missing IV Test", legs=(leg,))

    with pytest.raises(ValueError, match="Missing implied volatility"):
        compute_payoff_curve(spread, 25000.0, {}, as_of_date=date(2026, 9, 10))
