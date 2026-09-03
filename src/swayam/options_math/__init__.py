"""
Options Math Engine for Swayam Capital.

Public API surface for options pricing, Black-Scholes Greeks, dual-horizon
payoff curve analytics, and standard multi-leg strategy presets.
"""

from swayam.options_math.engine import (
    IVSolveFailed,
    black_scholes_price,
    greeks,
    implied_volatility,
)
from swayam.options_math.greeks import compute_position_greeks
from swayam.options_math.models import (
    Direction,
    GreeksSummary,
    Leg,
    OptionType,
    PayoffCurve,
    PayoffPoint,
    Spread,
)
from swayam.options_math.payoff import (
    compute_breakevens,
    compute_max_profit_loss,
    compute_payoff_curve,
)
from swayam.options_math.strategies import (
    bear_put_spread,
    bull_call_spread,
    calendar_spread,
    iron_condor,
    snap_to_strike,
)

__all__ = [
    "OptionType",
    "Direction",
    "Leg",
    "Spread",
    "GreeksSummary",
    "PayoffPoint",
    "PayoffCurve",
    "black_scholes_price",
    "implied_volatility",
    "greeks",
    "IVSolveFailed",
    "compute_payoff_curve",
    "compute_breakevens",
    "compute_max_profit_loss",
    "compute_position_greeks",
    "bear_put_spread",
    "bull_call_spread",
    "iron_condor",
    "calendar_spread",
    "snap_to_strike",
]
