"""
Tests for live market data endpoints with mocked FYERS client.
"""

from fastapi.testclient import TestClient
from swayam.api import app
from swayam.fyers_client import fyers_client

client = TestClient(app)


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
