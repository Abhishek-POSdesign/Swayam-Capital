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


def test_get_option_chain_returns_strikes(monkeypatch) -> None:
    mock_chain = {
        "spot": 24867.5,
        "strikes": [
            {
                "strike": 24850.0,
                "ce": {"ltp": 150.0, "iv": 0.15, "oi": 1000},
                "pe": {"ltp": 80.0, "iv": 0.16, "oi": 1200},
            }
        ],
    }
    monkeypatch.setattr(fyers_client, "get_option_chain", lambda symbol, expiry: mock_chain)
    response = client.get("/api/option-chain?expiry=2026-09-24&strike_count=10")
    assert response.status_code == 200
    data = response.json()
    assert data["underlying"] == "NIFTY"
    assert len(data["strikes"]) == 1
    assert data["strikes"][0]["strike"] == 24850.0


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


def test_get_vix_history_baseline_fallback(mocker) -> None:
    mock_table = mocker.MagicMock()
    # Return empty rows to trigger baseline fallback
    mock_table.select.return_value.gte.return_value.order.return_value.execute.return_value.data = []
    mocker.patch("swayam.api.routes.market.db.client.table", return_value=mock_table)

    from swayam.api.routes.market import _vix_cache
    _vix_cache["data"] = None

    response = client.get("/api/market/vix/history?days=60")
    assert response.status_code == 200
    data = response.json()
    assert data["current"] > 0
    assert len(data["history_60d"]["values"]) == 60
