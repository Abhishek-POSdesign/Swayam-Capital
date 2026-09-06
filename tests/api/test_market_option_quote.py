import pytest
from fastapi.testclient import TestClient
from swayam.api import app
from swayam import fyers_client as fc_module

client = TestClient(app)


def test_get_option_quote_invalid_type():
    r = client.get("/api/market/option/quote?strike=24800&expiry=2026-09-16&type=XX")
    assert r.status_code == 400


def test_get_option_quote_unavailable_is_honest(monkeypatch):
    """No live market/token: must return available:false with null price fields —
    never a fabricated LTP/IV/Delta (Abhishek's no-fake-numbers law)."""
    def boom(*a, **k):
        raise RuntimeError("no live token")

    monkeypatch.setattr(fc_module.fyers_client, "get_nifty_spot", boom)
    monkeypatch.setattr(fc_module.fyers_client, "get_option_chain", boom)

    r = client.get("/api/market/option/quote?strike=24700&expiry=2026-09-16&type=PE")
    assert r.status_code == 200
    d = r.json()
    assert d["available"] is False
    assert d["source"] == "unavailable"
    assert d["ltp"] is None and d["iv"] is None and d["delta"] is None
    assert d["note"]


def test_get_option_quote_real_path_implies_iv_from_ltp(monkeypatch):
    """With a live chain, IV is implied from the real LTP and Delta computed from it."""
    monkeypatch.setattr(fc_module.fyers_client, "get_nifty_spot", lambda: 24842.0)

    def fake_chain(**kwargs):
        return {
            "optionsChain": [
                {"option_type": "", "strike_price": 0, "ltp": 24842.0},
                {"option_type": "PE", "strike_price": 24700, "ltp": 95.0, "oi": 120000, "bid": 94.5, "ask": 95.5},
                {"option_type": "CE", "strike_price": 24900, "ltp": 88.0, "oi": 90000},
            ]
        }

    monkeypatch.setattr(fc_module.fyers_client, "get_option_chain", fake_chain)

    r = client.get("/api/market/option/quote?strike=24700&expiry=2026-09-16&type=PE")
    assert r.status_code == 200
    d = r.json()
    assert d["available"] is True
    assert d["source"] == "market"
    assert d["ltp"] == 95.0
    assert d["iv"] is not None and d["iv"] > 0
    assert d["delta"] is not None and d["delta"] <= 0  # put delta is negative
    assert d["oi"] == 120000
    assert d["spot"] == 24842.0
