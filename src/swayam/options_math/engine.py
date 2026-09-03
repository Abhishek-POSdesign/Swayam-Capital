"""
Core Black-Scholes pricing and Greeks calculation wrapper for Swayam Capital.

Uses the institutional-grade Black-Scholes-Merton and Let's-Be-Rational implementation
(via `vollib`) to price options, compute implied volatility, and derive first- and
second-order Greeks. Reads the default risk-free rate dynamically from application settings.
"""

from typing import Optional
from vollib.black_scholes import black_scholes
from vollib.black_scholes.greeks import analytical as bs_greeks
from vollib.black_scholes.implied_volatility import implied_volatility as bs_iv
from swayam.config import settings
from swayam.options_math.models import OptionType


class IVSolveFailed(Exception):
    """Raised when implied volatility solver cannot converge or price violates arbitrage bounds."""
    pass


def _normalize_flag(option_type: OptionType) -> str:
    """Converts OptionType to 'c' or 'p' character flag expected by vollib."""
    if option_type in (OptionType.CALL, "CE", "c", "call"):
        return "c"
    elif option_type in (OptionType.PUT, "PE", "p", "put"):
        return "p"
    raise ValueError(f"Unrecognized option type: {option_type}")


def black_scholes_price(
    spot: float,
    strike: float,
    tte_years: float,
    iv: float,
    r: Optional[float] = None,
    option_type: OptionType = OptionType.CALL,
) -> float:
    """Calculates theoretical Black-Scholes option price per share.

    Args:
        spot: Underlying asset price.
        strike: Option strike price.
        tte_years: Time to expiration in years.
        iv: Annualized implied volatility as a decimal (e.g., 0.15 for 15%).
        r: Annualized risk-free interest rate. If None, read from settings.risk_free_rate.
        option_type: OptionType.CALL (CE) or OptionType.PUT (PE).

    Returns:
        float: Theoretical option premium per share in rupees.

    Raises:
        ValueError: If iv <= 0 or inputs are nonsensical.
    """
    if iv <= 0.0:
        raise ValueError(f"Implied volatility must be positive; got {iv}")

    # Edge case: contract expired or at expiry
    if tte_years <= 0.0:
        if option_type == OptionType.CALL:
            return max(spot - strike, 0.0)
        else:
            return max(strike - spot, 0.0)

    rate = r if r is not None else settings.risk_free_rate
    flag = _normalize_flag(option_type)

    return float(black_scholes(flag, spot, strike, tte_years, rate, iv))


def implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    tte_years: float,
    r: Optional[float] = None,
    option_type: OptionType = OptionType.CALL,
) -> float:
    """Solves for implied volatility given observed market price.

    Args:
        market_price: Observed option premium per share.
        spot: Underlying asset price.
        strike: Option strike price.
        tte_years: Time to expiration in years.
        r: Annualized risk-free interest rate. If None, read from settings.risk_free_rate.
        option_type: OptionType.CALL (CE) or OptionType.PUT (PE).

    Returns:
        float: Solved implied volatility as a decimal.

    Raises:
        ValueError: If market_price <= 0 or tte_years <= 0.
        IVSolveFailed: If solver cannot converge or market price violates arbitrage bounds.
    """
    if market_price <= 0.0:
        raise ValueError(f"Market price must be positive; got {market_price}")
    if tte_years <= 0.0:
        raise ValueError("Cannot calculate implied volatility for expired contract (tte_years <= 0).")

    rate = r if r is not None else settings.risk_free_rate
    flag = _normalize_flag(option_type)

    try:
        solved = bs_iv(market_price, spot, strike, tte_years, rate, flag)
        if solved <= 0.0 or str(solved) == "nan":
            raise IVSolveFailed("Solver produced non-positive or NaN volatility.")
        return float(solved)
    except Exception as e:
        raise IVSolveFailed(
            f"Failed to solve IV for market_price={market_price}, spot={spot}, strike={strike}, "
            f"tte_years={tte_years}, r={rate}, type={option_type}: {e}"
        ) from e


def greeks(
    spot: float,
    strike: float,
    tte_years: float,
    iv: float,
    r: Optional[float] = None,
    option_type: OptionType = OptionType.CALL,
) -> dict[str, float]:
    """Calculates all 5 primary Black-Scholes Greeks per share.

    Args:
        spot: Underlying asset price.
        strike: Option strike price.
        tte_years: Time to expiration in years.
        iv: Annualized implied volatility (e.g. 0.15 for 15%).
        r: Annualized risk-free rate. If None, read from settings.risk_free_rate.
        option_type: OptionType.CALL (CE) or OptionType.PUT (PE).

    Returns:
        dict[str, float]: Dictionary containing:
            - 'delta': Change in option price per 1 point move in underlying.
            - 'gamma': Change in delta per 1 point move in underlying.
            - 'theta': Time decay in rupees per calendar day (already divided by 365).
            - 'vega': Change in option price per 1% change in IV (already scaled by 0.01).
            - 'rho': Change in option price per 1% change in interest rate.

    Raises:
        ValueError: If iv <= 0.
    """
    if iv <= 0.0:
        raise ValueError(f"Implied volatility must be positive; got {iv}")

    # Edge case: contract expired
    if tte_years <= 0.0:
        return {
            "delta": 0.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "rho": 0.0,
        }

    rate = r if r is not None else settings.risk_free_rate
    flag = _normalize_flag(option_type)

    delta_val = float(bs_greeks.delta(flag, spot, strike, tte_years, rate, iv))
    gamma_val = float(bs_greeks.gamma(flag, spot, strike, tte_years, rate, iv))
    theta_val = float(bs_greeks.theta(flag, spot, strike, tte_years, rate, iv))
    vega_val = float(bs_greeks.vega(flag, spot, strike, tte_years, rate, iv))
    rho_val = float(bs_greeks.rho(flag, spot, strike, tte_years, rate, iv))

    return {
        "delta": delta_val,
        "gamma": gamma_val,
        "theta": theta_val,
        "vega": vega_val,
        "rho": rho_val,
    }
