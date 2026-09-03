"""
Data models and typed structures for the Swayam Capital Options Math Engine.

Defines immutable, typed structures for individual option legs, multi-leg spreads,
aggregated Greeks, and dual-horizon (T+0 vs At-Expiry) payoff curves.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional


class OptionType(str, Enum):
    """Option contract type: Call (CE) or Put (PE)."""
    CALL = "CE"
    PUT = "PE"


class Direction(str, Enum):
    """Trade direction: Buy (long) or Sell (short)."""
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class Leg:
    """One option leg in a spread.

    Attributes:
        strike: Option strike price in rupees.
        option_type: CALL or PUT.
        direction: BUY or SELL.
        quantity_lots: Number of lots traded.
        entry_premium: Premium paid (buy) or received (sell), per share in rupees.
        expiry_date: Contract expiration date.
        lot_size: Number of underlying shares per lot (default: 75 for NIFTY).
    """
    strike: float
    option_type: OptionType
    direction: Direction
    quantity_lots: int
    entry_premium: float
    expiry_date: date
    lot_size: int = 75


@dataclass(frozen=True)
class Spread:
    """A multi-leg options position comprising one to N legs.

    Attributes:
        name: Strategy name (e.g., 'Bear Put Spread', 'Iron Condor').
        legs: Tuple of option legs.
        underlying: Underlying index or stock symbol (default: 'NIFTY').
    """
    name: str
    legs: tuple[Leg, ...]
    underlying: str = "NIFTY"


@dataclass(frozen=True)
class GreeksSummary:
    """Aggregated portfolio Greeks across all legs of a spread.

    Attributes:
        net_delta: Total position delta (directional exposure in shares).
        net_gamma: Rate of change of net delta per point move in underlying.
        net_theta_per_day: Net time decay in rupees per calendar day (₹/day).
        net_vega: Net sensitivity in rupees per 1% change in implied volatility.
        net_rho: Net interest rate sensitivity in rupees per 1% rate change.
    """
    net_delta: float
    net_gamma: float
    net_theta_per_day: float
    net_vega: float
    net_rho: float


@dataclass(frozen=True)
class PayoffPoint:
    """A single coordinate point on the options payoff curve.

    Attributes:
        spot: Underlying spot price evaluated.
        pnl_at_expiry: Total P&L in rupees if underlying expires at this spot.
        pnl_today: Total theoretical P&L in rupees as of today (T+0).
    """
    spot: float
    pnl_at_expiry: float
    pnl_today: float


@dataclass(frozen=True)
class PayoffCurve:
    """Complete payoff curve analysis for an options spread.

    Attributes:
        spot_range: Tuple of (min_spot, max_spot) evaluated.
        points: Sequence of PayoffPoints across the spot range.
        breakevens: Spot prices where at-expiry P&L crosses zero.
        max_profit_inr: Maximum achievable profit in rupees.
        max_loss_inr: Maximum possible loss in rupees (positive magnitude).
        rr_implied: Reward-to-risk ratio (max_profit / max_loss).
        net_debit_credit_inr: Net premium flow (negative for debit, positive for credit).
    """
    spot_range: tuple[float, float]
    points: tuple[PayoffPoint, ...]
    breakevens: tuple[float, ...]
    max_profit_inr: float
    max_loss_inr: float
    rr_implied: float
    net_debit_credit_inr: float
