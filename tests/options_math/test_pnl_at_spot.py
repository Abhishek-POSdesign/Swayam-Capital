"""
Unit tests for pnl_at_spot options payoff calculation.
"""

from datetime import date
import pytest

from swayam.options_math.models import Direction, Leg, OptionType
from swayam.options_math.payoff import pnl_at_spot


@pytest.fixture
def bear_put_spread_legs() -> list[Leg]:
    exp = date(2026, 9, 24)
    # Buy 24,850 PE @ 150, Sell 24,100 PE @ 50
    # Net debit = 100/share * 75 = 7,500 INR
    # Width = 750/share
    # Max profit = (750 - 100) * 75 = 48,750 INR
    return [
        Leg(strike=24850.0, option_type=OptionType.PUT, direction=Direction.BUY, quantity_lots=1, entry_premium=150.0, expiry_date=exp, lot_size=75),
        Leg(strike=24100.0, option_type=OptionType.PUT, direction=Direction.SELL, quantity_lots=1, entry_premium=50.0, expiry_date=exp, lot_size=75),
    ]


@pytest.fixture
def iron_condor_legs() -> list[Leg]:
    exp = date(2026, 9, 24)
    # Put spread: Buy 23800 PE @ 30, Sell 24200 PE @ 80 (net credit 50)
    # Call spread: Sell 25200 CE @ 80, Buy 25600 CE @ 30 (net credit 50)
    # Net credit = 100/share * 75 = 7,500 INR
    return [
        Leg(strike=23800.0, option_type=OptionType.PUT, direction=Direction.BUY, quantity_lots=1, entry_premium=30.0, expiry_date=exp, lot_size=75),
        Leg(strike=24200.0, option_type=OptionType.PUT, direction=Direction.SELL, quantity_lots=1, entry_premium=80.0, expiry_date=exp, lot_size=75),
        Leg(strike=25200.0, option_type=OptionType.CALL, direction=Direction.SELL, quantity_lots=1, entry_premium=80.0, expiry_date=exp, lot_size=75),
        Leg(strike=25600.0, option_type=OptionType.CALL, direction=Direction.BUY, quantity_lots=1, entry_premium=30.0, expiry_date=exp, lot_size=75),
    ]


def test_bear_put_spread_at_flat_spot():
    exp = date(2026, 9, 24)
    spot = 24800.0
    iv = 0.15
    tte = 15 / 365.0

    from swayam.options_math.engine import black_scholes_price
    p1 = black_scholes_price(spot=spot, strike=24850.0, tte_years=tte, iv=iv, option_type=OptionType.PUT)
    p2 = black_scholes_price(spot=spot, strike=24100.0, tte_years=tte, iv=iv, option_type=OptionType.PUT)

    legs = [
        Leg(strike=24850.0, option_type=OptionType.PUT, direction=Direction.BUY, quantity_lots=1, entry_premium=p1, expiry_date=exp, lot_size=75),
        Leg(strike=24100.0, option_type=OptionType.PUT, direction=Direction.SELL, quantity_lots=1, entry_premium=p2, expiry_date=exp, lot_size=75),
    ]
    iv_map = {legs[0]: iv, legs[1]: iv}
    pnl = pnl_at_spot(legs, target_spot=spot, days_to_expiry=15, current_iv_per_leg=iv_map)
    assert abs(pnl) < 1.0  # Exactly 0 P&L at flat spot and same evaluation TTE


def test_bear_put_spread_far_below_strikes_matches_max_profit(bear_put_spread_legs):
    # Spot collapses to 22,000 at expiry (days_to_expiry=0)
    pnl = pnl_at_spot(bear_put_spread_legs, target_spot=22000.0, days_to_expiry=0)
    expected_max_profit = (750.0 - 100.0) * 75  # 48,750 INR
    assert pnl == pytest.approx(expected_max_profit, abs=1e-4)


def test_bear_put_spread_far_above_strikes_matches_max_loss(bear_put_spread_legs):
    # Spot rallies to 26,000 at expiry (days_to_expiry=0)
    pnl = pnl_at_spot(bear_put_spread_legs, target_spot=26000.0, days_to_expiry=0)
    expected_max_loss = -100.0 * 75  # -7,500 INR (net debit paid)
    assert pnl == pytest.approx(expected_max_loss, abs=1e-4)


def test_iron_condor_inside_body_matches_max_profit(iron_condor_legs):
    # Spot stays between short strikes (e.g., 24,700) at expiry
    pnl = pnl_at_spot(iron_condor_legs, target_spot=24700.0, days_to_expiry=0)
    expected_max_profit = 100.0 * 75  # 7,500 INR (net credit collected)
    assert pnl == pytest.approx(expected_max_profit, abs=1e-4)
