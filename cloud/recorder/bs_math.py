"""Black-Scholes pricing, implied volatility and Greeks, with no dependencies.

Why this file exists rather than importing the terminal's engine
---------------------------------------------------------------
`swayam.options_math.engine` is the one authority for this maths in the
terminal, and it wraps `vollib`, which pulls in `lets_be_rational`, `numpy` and
`scipy`. The recorder is a separate Cloud Function deployed from this folder
alone, on a schedule that runs every minute of the trading day. Adding three
compiled dependencies to it to compute one number per row would buy a build
that can fail in ways the terminal's build cannot, on the one service nobody is
watching at 09:15.

So the maths is written out here in the standard library, and
`tests/cloud/test_recorder_bs_math.py` proves it agrees with `vollib` across a
grid of strikes, maturities and volatilities. If the two ever disagree, that
test fails and the recorder is wrong, not the terminal.

Conventions, matched to `vollib` deliberately
---------------------------------------------
- `theta` is per CALENDAR DAY, already divided by 365.
- `vega` is per 1% (100 bps) move in implied volatility, already scaled by 0.01.
- No dividend yield, because `vollib.black_scholes` has none and NIFTY index
  options are priced against the index, not a dividend-adjusted forward.
- Volatility is a decimal: 0.15 means 15%.

Nothing here invents a number. Every function returns None when the inputs
cannot support an answer, and the caller writes NULL.
"""

from __future__ import annotations

import math
from typing import Optional

# The lowest and highest volatility the solver will look between. A NIFTY
# option outside 0.1% and 500% annualised is not a quote, it is a stale print.
IV_LOWER_BOUND = 0.001
IV_UPPER_BOUND = 5.0
IV_MAX_ITERATIONS = 200
# The solver stops when the volatility bracket is this narrow, not when the
# price is close. See `implied_volatility` for why that distinction matters.
IV_SOLVE_TOLERANCE = 1e-10
# Below this vega, in rupees per share per 1% of volatility, no implied
# volatility is recorded. The exchange's tick is 5 paise, so at a vega of 0.01 a
# single tick of price moves the implied volatility by five whole volatility
# points. A number that unstable is not a measurement, and a deep in-the-money
# option trading at its intrinsic value sits far below even this.
MIN_VEGA_FOR_IV = 0.01

SQRT_TWO_PI = math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution, via the error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """Standard normal probability density."""
    return math.exp(-0.5 * x * x) / SQRT_TWO_PI


def _d1_d2(spot: float, strike: float, tte_years: float, rate: float, iv: float) -> tuple[float, float]:
    vol_sqrt_t = iv * math.sqrt(tte_years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * tte_years) / vol_sqrt_t
    return d1, d1 - vol_sqrt_t


def _is_call(option_type: str) -> bool:
    """Accepts the exchange's CE/PE as well as vollib's c/p."""
    normalized = (option_type or "").strip().upper()
    if normalized in ("CE", "C", "CALL"):
        return True
    if normalized in ("PE", "P", "PUT"):
        return False
    raise ValueError(f"Unrecognized option type: {option_type!r}")


def black_scholes_price(
    option_type: str,
    spot: float,
    strike: float,
    tte_years: float,
    rate: float,
    iv: float,
) -> Optional[float]:
    """Theoretical premium per share, or None if the inputs cannot support one."""
    if spot <= 0.0 or strike <= 0.0 or tte_years <= 0.0 or iv <= 0.0:
        return None
    call = _is_call(option_type)
    d1, d2 = _d1_d2(spot, strike, tte_years, rate, iv)
    discount = math.exp(-rate * tte_years)
    if call:
        return spot * _norm_cdf(d1) - strike * discount * _norm_cdf(d2)
    return strike * discount * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def implied_volatility(
    market_price: float,
    option_type: str,
    spot: float,
    strike: float,
    tte_years: float,
    rate: float,
) -> Optional[float]:
    """Solves volatility from a traded price, or returns None.

    Bisection rather than Newton on purpose. Deep out-of-the-money options have
    a vega near zero, where Newton's step divides by almost nothing and runs
    away. Bisection cannot: the price is monotonic in volatility, so a bracket
    that straddles the market price always closes on the answer, and 200 halvings
    of a range 0.001 to 5.0 is far below the precision the price itself carries.

    Returns None, never a guess, when:
      - the inputs are not usable (no price, no spot, expired);
      - the price is below intrinsic value or above the arbitrage ceiling, which
        happens with a stale last-traded print on an illiquid strike;
      - the price carries too little volatility information to measure. A deep
        in-the-money option trades at its intrinsic value, where every
        volatility reproduces the price equally well; just outside that, a
        single tick of price swings the answer by tens of volatility points. A
        solver will hand back a number in both cases. That number is noise, and
        noise written into his archive as though it were a measurement is
        exactly the fault this project exists to avoid, so it is refused and
        the column says NULL. See `MIN_VEGA_FOR_IV`.
    """
    if market_price <= 0.0 or spot <= 0.0 or strike <= 0.0 or tte_years <= 0.0:
        return None

    low_price = black_scholes_price(option_type, spot, strike, tte_years, rate, IV_LOWER_BOUND)
    high_price = black_scholes_price(option_type, spot, strike, tte_years, rate, IV_UPPER_BOUND)
    if low_price is None or high_price is None:
        return None
    # Outside the bracket there is no volatility that reproduces this price.
    if market_price <= low_price or market_price >= high_price:
        return None

    # Bisection to a converged bracket rather than to a price tolerance. The
    # price is monotonic in volatility, but it is also flat in it far from the
    # money, so stopping when the price is close enough can stop a long way from
    # the right volatility. Stopping when the bracket itself is closed cannot.
    low, high = IV_LOWER_BOUND, IV_UPPER_BOUND
    solved = 0.5 * (low + high)
    for _ in range(IV_MAX_ITERATIONS):
        solved = 0.5 * (low + high)
        if high - low < IV_SOLVE_TOLERANCE:
            break
        price = black_scholes_price(option_type, spot, strike, tte_years, rate, solved)
        if price is None:
            return None
        if price < market_price:
            low = solved
        else:
            high = solved

    sensitivity = greeks(option_type, spot, strike, tte_years, rate, solved)
    if sensitivity is None or abs(sensitivity["vega"]) < MIN_VEGA_FOR_IV:
        return None
    return solved


def greeks(
    option_type: str,
    spot: float,
    strike: float,
    tte_years: float,
    rate: float,
    iv: float,
) -> Optional[dict[str, float]]:
    """Delta, gamma, theta per day and vega per 1% IV, or None.

    Per share, not per lot. A backtest multiplies by the lot size itself, and
    the lot size has changed once already (75 to 65 in January 2026), so it is
    deliberately not baked in here.
    """
    if spot <= 0.0 or strike <= 0.0 or tte_years <= 0.0 or iv <= 0.0:
        return None

    call = _is_call(option_type)
    d1, d2 = _d1_d2(spot, strike, tte_years, rate, iv)
    pdf_d1 = _norm_pdf(d1)
    sqrt_t = math.sqrt(tte_years)
    discount = math.exp(-rate * tte_years)

    delta = _norm_cdf(d1) if call else _norm_cdf(d1) - 1.0
    gamma = pdf_d1 / (spot * iv * sqrt_t)
    vega = spot * pdf_d1 * sqrt_t * 0.01

    decay_term = (spot * pdf_d1 * iv) / (2.0 * sqrt_t)
    if call:
        theta = -(decay_term + rate * strike * discount * _norm_cdf(d2)) / 365.0
    else:
        theta = (-decay_term + rate * strike * discount * _norm_cdf(-d2)) / 365.0

    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega}
