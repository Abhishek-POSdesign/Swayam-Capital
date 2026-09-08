"""
Tests for live market data endpoints with mocked FYERS client.
"""

from fastapi.testclient import TestClient
import pytest
from swayam.api import app
from swayam.fyers_client import fyers_client
from swayam.api.routes.market import _candle_cache, _vix_cache, _spot_cache, _chain_cache

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_market_caches():
    from swayam.api.routes.market import _raw_chain_cache
    _raw_chain_cache.clear()
    _candle_cache.clear()
    _vix_cache["data"] = None
    _vix_cache["timestamp"] = 0.0
    _spot_cache["data"] = None
    _spot_cache["timestamp"] = 0.0
    _chain_cache.clear()
    yield
    _candle_cache.clear()
    _vix_cache["data"] = None
    _vix_cache["timestamp"] = 0.0
    _spot_cache["data"] = None
    _spot_cache["timestamp"] = 0.0
    _chain_cache.clear()


def test_get_nifty_spot_returns_price(monkeypatch) -> None:
    monkeypatch.setattr(fyers_client, "get_nifty_spot", lambda: 24867.5)
    response = client.get("/api/nifty/spot")
    assert response.status_code == 200
    data = response.json()
    assert data["spot"] == 24867.5
    assert "as_of" in data


# The real shape of FYERS' optionchain response, captured 2026-09-08. The old
# version of this test mocked a shape FYERS never returns ({"spot", "strikes"}
# already grouped) and called the client with arguments it does not take, so it
# had failed since it was written. It is fixed here against the real shape.
FYERS_CHAIN = {
    "expiryData": [
        {"date": "15-09-2026", "expiry": "1789467000", "expiry_flag": "W"},
        {"date": "29-09-2026", "expiry": "1790676600", "expiry_flag": "M"},
    ],
    "optionsChain": [
        {"symbol": "NSE:NIFTY50-INDEX", "option_type": "", "strike_price": -1, "ltp": 24867.5, "oi": None},
        {"symbol": "NSE:NIFTY26SEP24850CE", "option_type": "CE", "strike_price": 24850, "ltp": 150.0, "oi": 1000,
         "oich": 120, "oichp": 13.6, "volume": 50000, "bid": 149.5, "ask": 150.5, "ltpch": -12.0, "ltpchp": -7.4},
        {"symbol": "NSE:NIFTY26SEP24850PE", "option_type": "PE", "strike_price": 24850, "ltp": 80.0, "oi": 1200,
         "oich": -40, "oichp": -3.2, "volume": 42000, "bid": 79.5, "ask": 80.5, "ltpch": 6.0, "ltpchp": 8.1},
        {"symbol": "NSE:NIFTY26SEP24900CE", "option_type": "CE", "strike_price": 24900, "ltp": 0, "oi": 300,
         "oich": 0, "oichp": 0, "volume": 0, "bid": 0, "ask": 0, "ltpch": 0, "ltpchp": 0},
    ],
}


def test_get_option_chain_returns_strikes(monkeypatch) -> None:
    calls = []

    def fake_chain(underlying="NSE:NIFTY50-INDEX", strike_count=20, timestamp=None):
        calls.append(timestamp)
        return FYERS_CHAIN

    monkeypatch.setattr(fyers_client, "get_option_chain", fake_chain)
    from swayam.api.routes.market import _raw_chain_cache
    _raw_chain_cache.clear()

    response = client.get("/api/option-chain?expiry=2026-09-29&strike_count=10")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["underlying"] == "NIFTY"
    assert data["spot"] == 24867.5
    # The requested expiry was resolved to FYERS' epoch and fetched by it.
    assert data["expiry"] == "2026-09-29"
    assert data["expiry_epoch"] == "1790676600"
    assert calls == [None, "1790676600"]

    assert [s["strike"] for s in data["strikes"]] == [24850.0, 24900.0]
    ce = data["strikes"][0]["ce"]
    pe = data["strikes"][0]["pe"]
    assert ce["ltp"] == 150.0 and ce["oi"] == 1000 and ce["oi_change"] == 120 and ce["volume"] == 50000
    assert ce["bid"] == 149.5 and ce["ask"] == 150.5 and ce["ltp_change"] == -12.0
    assert pe["ltp"] == 80.0 and pe["oi_change"] == -40
    # IV is solved from the traded price, and null where there is no trade.
    assert ce["iv"] is not None and 0.01 < ce["iv"] < 2.0
    assert data["strikes"][1]["ce"]["ltp"] is None
    assert data["strikes"][1]["ce"]["iv"] is None
    # Open-interest totals and the put-call ratio come from the same rows.
    assert data["total_call_oi"] == 1300 and data["total_put_oi"] == 1200
    assert data["pcr"] == round(1200 / 1300, 2)
    assert data["atm_strike"] == 24850.0


def test_get_option_chain_refuses_an_expiry_fyers_does_not_list(monkeypatch) -> None:
    """A chain for the wrong expiry is worse than no chain."""
    monkeypatch.setattr(fyers_client, "get_option_chain", lambda **kw: FYERS_CHAIN)
    from swayam.api.routes.market import _raw_chain_cache
    _raw_chain_cache.clear()
    response = client.get("/api/option-chain?expiry=2026-10-06&strike_count=10")
    assert response.status_code == 404
    assert "does not list" in response.json()["detail"]


def test_get_nifty_candles_from_fyers(monkeypatch) -> None:
    mock_candles = {
        "candles": [
            ["2026-09-01", 24800.0, 24900.0, 24750.0, 24850.0, 1000],
            ["2026-09-02", 24850.0, 24950.0, 24820.0, 24920.0, 1200],
        ]
    }
    monkeypatch.setattr(fyers_client, "get_historical_candles", lambda **kwargs: mock_candles)
    response = client.get("/api/market/nifty/candles?timeframe=1d")
    assert response.status_code == 200
    data = response.json()
    assert data["timeframe"] == "1d"
    assert len(data["dates"]) == 2
    assert data["close"][-1] == 24920.0
    assert data["fallback"] is False


def test_get_nifty_candles_fallback_when_fyers_fails(monkeypatch, mocker) -> None:
    monkeypatch.setattr(
        fyers_client, "get_historical_candles", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("Token expired"))
    )
    # Mock db to return daily bars
    mock_table = mocker.MagicMock()
    mock_table.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"date": "2026-09-01", "open": 24800.0, "high": 24900.0, "low": 24750.0, "close": 24850.0},
        {"date": "2026-09-02", "open": 24850.0, "high": 24950.0, "low": 24820.0, "close": 24920.0},
    ]
    mocker.patch("swayam.api.routes.market.db.client.table", return_value=mock_table)

    response = client.get("/api/market/nifty/candles?timeframe=1d")
    assert response.status_code == 200
    data = response.json()
    assert data["timeframe"] == "1d"
    assert len(data["dates"]) == 2
    assert data["fallback"] is True


def test_get_vix_history_returns_percentiles(mocker) -> None:
    mock_table = mocker.MagicMock()
    mock_rows = [{"date": f"2026-08-{i:02d}", "vix_close": 12.0 + (i % 5)} for i in range(1, 26)]
    mock_table.select.return_value.gte.return_value.order.return_value.execute.return_value.data = mock_rows
    mocker.patch("swayam.api.routes.market.db.client.table", return_value=mock_table)

    # Invalidate cache
    from swayam.api.routes.market import _vix_cache
    _vix_cache["data"] = None

    response = client.get("/api/market/vix/history?days=60")
    assert response.status_code == 200
    data = response.json()
    assert "current" in data
    assert "regime" in data
    assert "p10" in data
    assert "p90" in data
    assert len(data["history_60d"]["values"]) == 25


def test_get_vix_history_unavailable_when_no_real_rows(mocker) -> None:
    """No-fake-numbers law: too few real bhavcopy rows must fail loudly (503), never synthesize
    a baseline VIX curve dressed up as live data."""
    mock_table = mocker.MagicMock()
    # Return empty rows — previously this synthesized a fake baseline series; now it must 503.
    mock_table.select.return_value.gte.return_value.order.return_value.execute.return_value.data = []
    mocker.patch("swayam.api.routes.market.db.client.table", return_value=mock_table)

    from swayam.api.routes.market import _vix_cache
    _vix_cache["data"] = None

    response = client.get("/api/market/vix/history?days=60")
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


def test_get_expiries_names_the_next_trading_day(monkeypatch) -> None:
    """The desk defaults to carrying overnight, so it needs the next trading day.

    Computed server-side from the NSE holiday file, never guessed in the browser.
    """
    from datetime import date as _date
    import swayam.api.routes.market as market_module

    class FixedDate(_date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 1)  # Thursday; 2 Oct is Gandhi Jayanti, then the weekend

    monkeypatch.setattr(market_module, "date", FixedDate)
    monkeypatch.setattr(
        market_module,
        "get_expiry_metadata",
        lambda: {"upcoming_expiries": ["2026-10-06"], "weekly_expiry": "2026-10-06", "monthly_expiry": "2026-10-27"},
    )
    data = client.get("/api/market/expiries").json()
    assert data["today"] == "2026-10-01"
    assert data["next_trading_day"] == "2026-10-05"
