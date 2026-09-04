"""
Unit tests for statistical risk engine and expected worst-case loss computation.
"""

from datetime import date
import pytest

from swayam.options_math.models import Direction, Leg, OptionType
from swayam.options_math.payoff import pnl_at_spot
from swayam.rule_engine.statistical_risk import compute_expected_worst_case_loss


def test_bear_put_spread_realistic_vs_max_loss():
    exp = date(2026, 9, 24)
    # Buy 24,850 PE @ 220, Sell 24,100 PE @ 50
    # Net debit = 170 * 75 = 12,750 INR = max loss at expiry
    legs = [
        Leg(strike=24850.0, option_type=OptionType.PUT, direction=Direction.BUY, quantity_lots=1, entry_premium=220.0, expiry_date=exp, lot_size=75),
        Leg(strike=24100.0, option_type=OptionType.PUT, direction=Direction.SELL, quantity_lots=1, entry_premium=50.0, expiry_date=exp, lot_size=75),
    ]
    current_spot = 24800.0
    annualized_vol = 0.15  # 15% vol -> daily sigma ~ 0.94% -> 2 sigma ~ 1.89% (~470 points)

    realistic_loss = compute_expected_worst_case_loss(
        legs=legs,
        current_spot=current_spot,
        annualized_vol=annualized_vol,
        stress_sigma=2.0,
        days_to_expiry=15,
    )

    max_loss_inr = 12750.0
    # Realistic worst-case loss at 2-sigma move must be materially smaller than absolute max loss (~4,900 vs 12,750)
    assert realistic_loss < max_loss_inr * 0.60
    assert realistic_loss > 0.0


def test_deep_otm_bull_call_spread():
    exp = date(2026, 9, 24)
    # Spot 24,000; Strikes 26,500 and 27,000 (2,500 points OTM)
    # Entry premium = 5.0 and 1.0 (net debit 4.0 * 75 = 300 INR max loss)
    legs = [
        Leg(strike=26500.0, option_type=OptionType.CALL, direction=Direction.BUY, quantity_lots=1, entry_premium=5.0, expiry_date=exp, lot_size=75),
        Leg(strike=27000.0, option_type=OptionType.CALL, direction=Direction.SELL, quantity_lots=1, entry_premium=1.0, expiry_date=exp, lot_size=75),
    ]
    current_spot = 24000.0
    annualized_vol = 0.14
    iv_map = {legs[0]: 0.25, legs[1]: 0.25}

    realistic_loss = compute_expected_worst_case_loss(
        legs=legs,
        current_spot=current_spot,
        annualized_vol=annualized_vol,
        stress_sigma=2.0,
        days_to_expiry=20,
        current_iv_per_leg=iv_map,
    )
    # Because options are deep OTM and low delta, overnight 2-sigma move doesn't wipe out premium
    assert realistic_loss < 200.0  # minimal realistic loss


def test_zero_vol_day():
    exp = date(2026, 9, 24)
    legs = [
        Leg(strike=24800.0, option_type=OptionType.PUT, direction=Direction.BUY, quantity_lots=1, entry_premium=150.0, expiry_date=exp, lot_size=75),
    ]
    current_spot = 24800.0

    loss = compute_expected_worst_case_loss(
        legs=legs,
        current_spot=current_spot,
        annualized_vol=0.0,
        stress_sigma=2.0,
        days_to_expiry=1,
    )

    expected_pnl = pnl_at_spot(legs, current_spot, days_to_expiry=1)
    expected_loss = max(0.0, -expected_pnl)
    assert loss == pytest.approx(expected_loss, abs=1e-6)


def test_long_straddle_both_stress_moves_profit():
    exp = date(2026, 9, 24)
    # Long ATM Straddle: Buy 24,800 CE @ 120, Buy 24,800 PE @ 120
    legs = [
        Leg(strike=24800.0, option_type=OptionType.CALL, direction=Direction.BUY, quantity_lots=1, entry_premium=120.0, expiry_date=exp, lot_size=75),
        Leg(strike=24800.0, option_type=OptionType.PUT, direction=Direction.BUY, quantity_lots=1, entry_premium=120.0, expiry_date=exp, lot_size=75),
    ]
    current_spot = 24800.0
    # High volatility move: 35% vol, 2.5 sigma -> big move where straddle gains intrinsic
    realistic_loss = compute_expected_worst_case_loss(
        legs=legs,
        current_spot=current_spot,
        annualized_vol=0.35,
        stress_sigma=2.5,
        days_to_expiry=1,
    )
    # Under large moves both sides are profitable, so worst-case loss is 0
    assert realistic_loss == 0.0


def test_short_straddle_both_stress_moves_loss():
    exp = date(2026, 9, 24)
    # Short ATM Straddle: Sell 24,800 CE @ 120, Sell 24,800 PE @ 120
    legs = [
        Leg(strike=24800.0, option_type=OptionType.CALL, direction=Direction.SELL, quantity_lots=1, entry_premium=120.0, expiry_date=exp, lot_size=75),
        Leg(strike=24800.0, option_type=OptionType.PUT, direction=Direction.SELL, quantity_lots=1, entry_premium=120.0, expiry_date=exp, lot_size=75),
    ]
    current_spot = 24800.0

    realistic_loss = compute_expected_worst_case_loss(
        legs=legs,
        current_spot=current_spot,
        annualized_vol=0.15,
        stress_sigma=2.0,
        days_to_expiry=1,
    )
    # Both moves produce significant losses for a short straddle
    assert realistic_loss > 0.0
