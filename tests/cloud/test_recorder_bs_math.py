"""The recorder's own Black-Scholes must agree with the terminal's engine.

The recorder is deployed from `cloud/recorder/` alone and carries its own
copy of this maths in the standard library, so that a Cloud Function that runs
every minute of the trading day does not depend on three compiled packages.
That is only safe while the copy and the original agree.

These tests are what makes it safe. If `cloud/recorder/bs_math.py` ever drifts
from `swayam.options_math.engine`, which wraps `vollib`, this file fails and the
recorder is the one that is wrong.
"""

from pathlib import Path
import sys

import pytest

RECORDER_DIR = Path(__file__).resolve().parent.parent.parent / "cloud" / "recorder"
if str(RECORDER_DIR) not in sys.path:
    sys.path.insert(0, str(RECORDER_DIR))

import bs_math  # noqa: E402
from swayam.options_math.engine import black_scholes_price as engine_price  # noqa: E402
from swayam.options_math.engine import greeks as engine_greeks  # noqa: E402
from swayam.options_math.models import OptionType  # noqa: E402

RATE = 0.068
SPOTS = (23000.0, 23431.5, 24500.0)
STRIKES = (22000.0, 23000.0, 23400.0, 23500.0, 24000.0, 25500.0)
# One day to four months: his swings run days to weeks and his calendars are
# squared off the day before expiry, so both ends matter.
MATURITIES = (1 / 365, 3 / 365, 7 / 365, 21 / 365, 45 / 365, 120 / 365)
VOLS = (0.08, 0.12, 0.18, 0.35, 0.80)
TYPES = (("CE", OptionType.CALL), ("PE", OptionType.PUT))


def _grid():
    for spot in SPOTS:
        for strike in STRIKES:
            for tte in MATURITIES:
                for vol in VOLS:
                    for flag, model_type in TYPES:
                        yield spot, strike, tte, vol, flag, model_type


def test_price_matches_the_terminals_engine():
    worst = 0.0
    for spot, strike, tte, vol, flag, model_type in _grid():
        mine = bs_math.black_scholes_price(flag, spot, strike, tte, RATE, vol)
        theirs = engine_price(
            spot=spot, strike=strike, tte_years=tte, iv=vol, r=RATE, option_type=model_type
        )
        assert mine is not None
        worst = max(worst, abs(mine - theirs))
    # A rupee is the unit he trades in. Agreement here is at the tenth decimal.
    assert worst < 1e-9, f"worst price disagreement was {worst}"


@pytest.mark.parametrize("greek", ["delta", "gamma", "theta", "vega"])
def test_greeks_match_the_terminals_engine(greek):
    worst = 0.0
    for spot, strike, tte, vol, flag, model_type in _grid():
        mine = bs_math.greeks(flag, spot, strike, tte, RATE, vol)
        theirs = engine_greeks(
            spot=spot, strike=strike, tte_years=tte, iv=vol, r=RATE, option_type=model_type
        )
        assert mine is not None
        worst = max(worst, abs(mine[greek] - theirs[greek]))
    assert worst < 1e-9, f"worst {greek} disagreement was {worst}"


def test_implied_volatility_recovers_the_volatility_it_was_priced_with():
    """A price built from a known volatility must solve back to that volatility.

    Where it cannot, it must return None rather than a number. The only cases
    that cannot are deep in-the-money options trading at intrinsic value, whose
    price is the same for every volatility.
    """
    checked = 0
    for spot, strike, tte, vol, flag, model_type in _grid():
        price = engine_price(
            spot=spot, strike=strike, tte_years=tte, iv=vol, r=RATE, option_type=model_type
        )
        if price <= 0.05:
            continue  # below a tick; not a real quote
        solved = bs_math.implied_volatility(price, flag, spot, strike, tte, RATE)
        if solved is None:
            sensitivity = bs_math.greeks(flag, spot, strike, tte, RATE, vol)
            assert sensitivity is not None
            assert abs(sensitivity["vega"]) < bs_math.MIN_VEGA_FOR_IV * 1.5, (
                "IV was refused on a contract that does carry volatility information: "
                f"spot={spot} strike={strike} tte={tte} vol={vol} {flag}"
            )
            continue
        checked += 1
        assert abs(solved - vol) < 1e-6, (
            f"spot={spot} strike={strike} tte={tte} {flag}: priced at {vol}, solved {solved}"
        )
    assert checked > 800, f"only {checked} cases actually solved; the grid is not exercising much"


def test_no_implied_volatility_from_a_price_at_intrinsic_value():
    """Deep in the money, the price carries no volatility information.

    A solver will still hand back a number there, and that number would be
    written into his archive as though it meant something. It must be refused.
    """
    # 1000 points in the money with one day left: pure intrinsic, zero vega.
    solved = bs_math.implied_volatility(1004.10, "CE", 23000.0, 22000.0, 1 / 365, RATE)
    assert solved is None


def test_nothing_is_returned_for_impossible_inputs():
    assert bs_math.black_scholes_price("CE", 23000.0, 23000.0, 0.0, RATE, 0.12) is None
    assert bs_math.black_scholes_price("CE", 23000.0, 23000.0, 0.05, RATE, 0.0) is None
    assert bs_math.greeks("PE", 23000.0, 23000.0, -1.0, RATE, 0.12) is None
    assert bs_math.implied_volatility(0.0, "CE", 23000.0, 23000.0, 0.05, RATE) is None
    assert bs_math.implied_volatility(120.0, "CE", 0.0, 23000.0, 0.05, RATE) is None
    # A price above the underlying itself is impossible for a call.
    assert bs_math.implied_volatility(30000.0, "CE", 23000.0, 23000.0, 0.05, RATE) is None


def test_option_type_accepts_the_exchanges_spelling_and_refuses_nonsense():
    at_the_money = dict(spot=23431.5, strike=23450.0, tte_years=6 / 365, rate=RATE, iv=0.11)
    call = bs_math.greeks("CE", **at_the_money)
    same_call = bs_math.greeks("c", **at_the_money)
    assert call == same_call
    assert call["delta"] > 0
    assert bs_math.greeks("PE", **at_the_money)["delta"] < 0
    with pytest.raises(ValueError):
        bs_math.greeks("XX", **at_the_money)
