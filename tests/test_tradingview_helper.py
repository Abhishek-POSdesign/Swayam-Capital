"""
Unit tests for Swayam Capital TradingView Helper.

Verifies construction of external second-screen TradingView chart URLs.
"""

from swayam.tradingview_helper import build_option_strike_url, build_tradingview_url


def test_build_tradingview_url_constructs_valid_default_url() -> None:
    url = build_tradingview_url()
    assert "https://www.tradingview.com/chart/" in url
    assert "symbol=NSE%3ANIFTY" in url or "symbol=NSE:NIFTY" in url
    assert "interval=60" in url


def test_build_tradingview_url_includes_indicators_and_timeframe() -> None:
    url = build_tradingview_url(
        symbol="NSE:NIFTY50-INDEX",
        timeframe="15",
        indicators=["MA20", "MA50"],
    )
    assert "interval=15" in url
    assert "studies=MA20%2CMA50" in url or "studies=MA20,MA50" in url


def test_build_option_strike_url_formats_derivative_symbol() -> None:
    url = build_option_strike_url(
        underlying="NIFTY",
        expiry_code="24OCT",
        strike=25000.0,
        option_type="CE",
        timeframe="5",
    )
    assert "NSE%3ANIFTY24OCT25000CE" in url or "NSE:NIFTY24OCT25000CE" in url
    assert "interval=5" in url
