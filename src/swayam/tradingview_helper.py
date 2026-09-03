"""
TradingView URL Generator & Dual-Screen Helper for Swayam Capital.

This module implements Abhishek's dual-screen charting philosophy: internal charts
are kept minimal (Plotly.js for payoff curves only), while live price action and
technical analysis remain on the primary second screen via TradingView. This helper
generates pre-populated TradingView URLs with symbols, timeframes, and indicators.
"""

from typing import Optional
from urllib.parse import urlencode


def build_tradingview_url(
    symbol: str = "NSE:NIFTY",
    timeframe: str = "60",
    indicators: Optional[list[str]] = None,
    drawings: Optional[list[tuple[str, float, str]]] = None,
) -> str:
    """Builds a formatted TradingView chart URL for external second-screen viewing.

    Args:
        symbol: TradingView symbol identifier (e.g. 'NSE:NIFTY', 'NSE:NIFTY50').
        timeframe: Chart interval ('1', '5', '15', '60', 'D', 'W').
        indicators: Optional list of indicator study names (e.g. ['MA20', 'MA50']).
        drawings: Optional list of tuples (type, price_level, label) for reference lines.

    Returns:
        str: Clickable TradingView URL.
    """
    base_url = "https://www.tradingview.com/chart/"
    params: dict[str, str] = {
        "symbol": symbol,
        "interval": str(timeframe),
    }

    if indicators:
        params["studies"] = ",".join(indicators)

    query_string = urlencode(params)
    url = f"{base_url}?{query_string}"

    if drawings:
        # Append drawings metadata anchor for custom dashboard integration
        drawing_parts = [f"{d_type}:{level}:{label}" for d_type, level, label in drawings]
        url += f"#drawings={';'.join(drawing_parts)}"

    return url


def build_option_strike_url(
    underlying: str,
    expiry_code: str,
    strike: float,
    option_type: str,
    timeframe: str = "5",
) -> str:
    """Constructs a TradingView chart URL for a specific option contract.

    Args:
        underlying: 'NIFTY' or 'BANKNIFTY'.
        expiry_code: Compact expiry format (e.g., '24OCT' or '24926').
        strike: Option strike price (e.g., 25000).
        option_type: 'CE' or 'PE'.
        timeframe: Default interval ('5' for 5-minute).

    Returns:
        str: Direct TradingView chart URL for the derivative contract.
    """
    clean_strike = int(strike) if strike.is_integer() else strike
    symbol = f"NSE:{underlying.upper()}{expiry_code.upper()}{clean_strike}{option_type.upper()}"
    return build_tradingview_url(symbol=symbol, timeframe=timeframe)
