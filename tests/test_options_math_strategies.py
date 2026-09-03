"""
Unit tests for Swayam Capital Options Math Engine - Strategy Presets.
"""

from datetime import date
import pytest
from swayam.options_math.models import Direction, OptionType
from swayam.options_math.strategies import (
    bear_put_spread,
    bull_call_spread,
    calendar_spread,
    iron_condor,
    snap_to_strike,
)


def test_snap_to_strike_rounds_to_nearest_fifty() -> None:
    assert snap_to_strike(24369.7) == 24350.0
    assert snap_to_strike(24376.1) == 24400.0
    assert snap_to_strike(24867.0) == 24850.0
    assert snap_to_strike(25000.0) == 25000.0


def test_bear_put_spread_generates_valid_two_leg_pe_spread() -> None:
    expiry = date(2026, 9, 24)
    spread = bear_put_spread(current_spot=24867.0, expiry=expiry)

    assert spread.name == "Bear Put Spread"
    assert len(spread.legs) == 2

    leg_buy, leg_sell = spread.legs

    assert leg_buy.option_type == OptionType.PUT
    assert leg_buy.direction == Direction.BUY
    assert leg_sell.option_type == OptionType.PUT
    assert leg_sell.direction == Direction.SELL

    # Both strikes must snap to 50-point intervals
    assert leg_buy.strike % 50.0 == 0.0
    assert leg_sell.strike % 50.0 == 0.0

    # In Bear Put Spread, long put strike is higher than short put strike
    assert leg_buy.strike > leg_sell.strike


def test_bull_call_spread_generates_valid_two_leg_ce_spread() -> None:
    expiry = date(2026, 9, 24)
    spread = bull_call_spread(current_spot=24867.0, expiry=expiry)

    assert spread.name == "Bull Call Spread"
    assert len(spread.legs) == 2

    leg_buy, leg_sell = spread.legs

    assert leg_buy.option_type == OptionType.CALL
    assert leg_buy.direction == Direction.BUY
    assert leg_sell.option_type == OptionType.CALL
    assert leg_sell.direction == Direction.SELL

    assert leg_buy.strike % 50.0 == 0.0
    assert leg_sell.strike % 50.0 == 0.0

    # In Bull Call Spread, long call strike is lower than short call strike
    assert leg_sell.strike > leg_buy.strike


def test_iron_condor_generates_four_distinct_legs_snapped_to_grid() -> None:
    expiry = date(2026, 9, 24)
    spread = iron_condor(current_spot=24867.0, expiry=expiry)

    assert spread.name == "Iron Condor"
    assert len(spread.legs) == 4

    sell_ce, buy_ce, sell_pe, buy_pe = spread.legs

    assert sell_ce.option_type == OptionType.CALL and sell_ce.direction == Direction.SELL
    assert buy_ce.option_type == OptionType.CALL and buy_ce.direction == Direction.BUY
    assert sell_pe.option_type == OptionType.PUT and sell_pe.direction == Direction.SELL
    assert buy_pe.option_type == OptionType.PUT and buy_pe.direction == Direction.BUY

    for leg in spread.legs:
        assert leg.strike % 50.0 == 0.0

    assert buy_ce.strike > sell_ce.strike
    assert sell_pe.strike > buy_pe.strike


def test_calendar_spread_generates_time_spread_at_same_strike() -> None:
    near = date(2026, 9, 17)
    far = date(2026, 9, 24)
    spread = calendar_spread(current_spot=24867.0, near_expiry=near, far_expiry=far)

    assert spread.name == "Calendar Spread"
    assert len(spread.legs) == 2

    near_leg, far_leg = spread.legs

    assert near_leg.strike == far_leg.strike
    assert near_leg.strike % 50.0 == 0.0
    assert near_leg.direction == Direction.SELL
    assert far_leg.direction == Direction.BUY
    assert near_leg.expiry_date == near
    assert far_leg.expiry_date == far


def test_calendar_spread_rejects_inverted_expiries() -> None:
    near = date(2026, 9, 24)
    far = date(2026, 9, 17)

    with pytest.raises(ValueError, match="must be strictly earlier"):
        calendar_spread(current_spot=24867.0, near_expiry=near, far_expiry=far)
