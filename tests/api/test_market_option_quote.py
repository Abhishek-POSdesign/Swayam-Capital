import pytest
from fastapi.testclient import TestClient
from swayam.api import app

client = TestClient(app)


def test_get_option_quote_call_success():
    response = client.get("/api/market/option/quote?strike=24900&expiry=2026-09-10&type=CE")
    assert response.status_code == 200
    data = response.json()
    assert data["strike"] == 24900.0
    assert data["option_type"] == "CE"
    assert "ltp" in data and data["ltp"] > 0
    assert "iv" in data
    assert "delta" in data
    assert "theta" in data
    assert "vega" in data
    assert "gamma" in data
    assert data["spot"] > 0


def test_get_option_quote_put_success():
    response = client.get("/api/market/option/quote?strike=24700&expiry=2026-09-10&type=PE")
    assert response.status_code == 200
    data = response.json()
    assert data["strike"] == 24700.0
    assert data["option_type"] == "PE"
    assert data["delta"] <= 0  # Put delta is negative or zero


def test_get_option_quote_invalid_type():
    response = client.get("/api/market/option/quote?strike=24800&expiry=2026-09-10&type=XX")
    assert response.status_code == 400
