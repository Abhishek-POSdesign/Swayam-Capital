"""
Unit tests for Swayam Capital Options Math Engine - Black-Scholes & Greeks Wrapper.
"""

import pytest
from swayam.config import settings
from swayam.options_math.engine import (
    IVSolveFailed,
    black_scholes_price,
    greeks,
    implied_volatility,
)
from swayam.options_math.models import OptionType


def test_black_scholes_price_matches_known_benchmark() -> None:
    # spot=24500, strike=24500, tte=30 days, iv=15%, r=6.8%, Call
    spot = 24500.0
    strike = 24500.0
    tte = 30.0 / 365.0
    iv = 0.15
    r = 0.068

    price = black_scholes_price(spot, strike, tte, iv, r, OptionType.CALL)
    # Expected benchmark is ~490.93 rupees
    assert abs(price - 490.93) < 1.0


def test_black_scholes_put_price_matches_benchmark() -> None:
    spot = 24500.0
    strike = 24500.0
    tte = 30.0 / 365.0
    iv = 0.15
    r = 0.068

    price = black_scholes_price(spot, strike, tte, iv, r, OptionType.PUT)
    # Check put price validity (non-negative and plausible)
    assert 300.0 < price < 500.0


def test_implied_volatility_round_trip_accuracy() -> None:
    spot = 25000.0
    strike = 25000.0
    tte = 14.0 / 365.0
    original_iv = 0.18
    r = settings.risk_free_rate

    price = black_scholes_price(spot, strike, tte, original_iv, r, OptionType.CALL)
    solved_iv = implied_volatility(price, spot, strike, tte, r, OptionType.CALL)

    assert abs(solved_iv - original_iv) < 0.001


def test_black_scholes_price_returns_intrinsic_at_expiry() -> None:
    # Expired Call ITM
    assert black_scholes_price(25200.0, 25000.0, 0.0, 0.15, 0.068, OptionType.CALL) == 200.0
    # Expired Call OTM
    assert black_scholes_price(24800.0, 25000.0, 0.0, 0.15, 0.068, OptionType.CALL) == 0.0
    # Expired Put ITM
    assert black_scholes_price(24800.0, 25000.0, 0.0, 0.15, 0.068, OptionType.PUT) == 200.0
    # Expired Put OTM
    assert black_scholes_price(25200.0, 25000.0, 0.0, 0.15, 0.068, OptionType.PUT) == 0.0


def test_black_scholes_price_rejects_non_positive_iv() -> None:
    with pytest.raises(ValueError, match="Implied volatility must be positive"):
        black_scholes_price(25000.0, 25000.0, 0.1, -0.05, 0.068, OptionType.CALL)


def test_implied_volatility_raises_on_arbitrage_violating_price() -> None:
    # A market price below intrinsic value (e.g. ₹5 for a deep ITM call with intrinsic ₹1000)
    with pytest.raises(IVSolveFailed):
        implied_volatility(5.0, 26000.0, 25000.0, 0.05, 0.068, OptionType.CALL)


def test_greeks_returns_all_five_standard_sensitivities() -> None:
    g = greeks(25000.0, 25000.0, 10.0 / 365.0, 0.16, 0.068, OptionType.CALL)
    for key in ("delta", "gamma", "theta", "vega", "rho"):
        assert key in g
        assert isinstance(g[key], float)

    # ATM Call Delta should be between 0.45 and 0.55
    assert 0.45 < g["delta"] < 0.55
    # Theta should be negative for long call
    assert g["theta"] < 0.0
    # Vega should be positive for long call
    assert g["vega"] > 0.0


def test_greeks_returns_zeros_for_expired_contract() -> None:
    g = greeks(25000.0, 25000.0, 0.0, 0.16, 0.068, OptionType.CALL)
    assert g["delta"] == 0.0
    assert g["gamma"] == 0.0
    assert g["theta"] == 0.0
    assert g["vega"] == 0.0
    assert g["rho"] == 0.0
