"""
Tests for strategy calculation endpoints in Swayam Capital.
"""

from fastapi.testclient import TestClient
from swayam.api import app

client = TestClient(app)


def test_compute_strategy_returns_dual_curve_and_greeks() -> None:
    payload = {
        "strategy_name": "Bear Put Spread Test",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24850.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 220.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
            {
                "strike": 24100.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 1,
                "entry_premium": 70.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
        ],
        "current_spot": 24867.5,
        "iv_per_leg": {
            "24850_PE": 0.15,
            "24100_PE": 0.15,
        },
    }

    response = client.post("/api/strategy/compute", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "payoff_curve" in data
    assert "greeks" in data

    pc = data["payoff_curve"]
    assert len(pc["points"]) == 100
    assert abs(pc["max_profit_inr"] - 45000.0) < 1.0
    assert abs(pc["max_loss_inr"] - 11250.0) < 1.0
    assert abs(pc["rr_implied"] - 4.0) < 0.1
    assert pc["net_debit_credit_inr"] == -11250.0

    g = data["greeks"]
    assert "net_delta" in g
    assert "net_theta_per_day" in g
    assert "net_vega" in g


def test_get_strategy_preset_returns_snapped_strikes() -> None:
    response = client.post("/api/strategy/preset?name=bear_put_spread&expiry=2026-09-24&spot=24867.5")
    assert response.status_code == 200
    data = response.json()

    assert data["strategy_name"] == "Bear Put Spread"
    assert len(data["legs"]) == 2
    for leg in data["legs"]:
        assert leg["strike"] % 50.0 == 0.0
