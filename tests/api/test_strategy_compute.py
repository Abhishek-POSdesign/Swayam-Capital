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


def test_compute_strategy_with_target_date_and_iv_shift() -> None:
    payload = {
        "strategy_name": "Bull Call Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24800.0,
                "option_type": "CE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 210.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
            {
                "strike": 25100.0,
                "option_type": "CE",
                "direction": "sell",
                "quantity_lots": 1,
                "entry_premium": 75.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
        ],
        "current_spot": 24850.0,
        "target_date": "2026-09-10",
        "iv_shift_pct": 10.0,
        "iv_per_leg": {"24800_CE": 0.14, "25100_CE": 0.14},
    }
    res = client.post("/api/strategy/compute", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "pop" in data
    assert data["pop"] is not None
    assert 0.0 <= data["pop"] <= 100.0
    assert "per_leg" in data
    assert len(data["per_leg"]) == 2
    leg0 = data["per_leg"][0]
    assert "delta" in leg0
    assert "theta" in leg0
    assert "vega" in leg0
    assert "gamma" in leg0


def test_compute_strategy_target_date_after_expiry_raises_400() -> None:
    payload = {
        "strategy_name": "Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24800.0,
                "option_type": "CE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 200.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            }
        ],
        "current_spot": 24850.0,
        "target_date": "2026-09-25",  # Day after expiry
    }
    res = client.post("/api/strategy/compute", json=payload)
    assert res.status_code == 400
    assert "target_date after expiry" in res.json()["detail"]


def test_compute_strategy_invalid_iv_shift_raises_400() -> None:
    base_payload = {
        "strategy_name": "Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24800.0,
                "option_type": "CE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 200.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            }
        ],
        "current_spot": 24850.0,
    }
    # Below -90%
    p1 = {**base_payload, "iv_shift_pct": -95.0}
    r1 = client.post("/api/strategy/compute", json=p1)
    assert r1.status_code == 400
    assert "iv_shift_pct outside" in r1.json()["detail"]

    # Above 200%
    p2 = {**base_payload, "iv_shift_pct": 250.0}
    r2 = client.post("/api/strategy/compute", json=p2)
    assert r2.status_code == 400
    assert "iv_shift_pct outside" in r2.json()["detail"]


def test_compute_strategy_pop_increases_with_favorable_spot() -> None:
    # For a Bull Call Spread, higher spot prices must produce higher POP
    spots = [24400.0, 24850.0, 25300.0]
    pops = []
    for spot in spots:
        payload = {
            "strategy_name": "Bull Call",
            "underlying": "NIFTY",
            "legs": [
                {
                    "strike": 24800.0,
                    "option_type": "CE",
                    "direction": "buy",
                    "quantity_lots": 1,
                    "entry_premium": 210.0,
                    "expiry_date": "2026-09-24",
                    "lot_size": 75,
                },
                {
                    "strike": 25100.0,
                    "option_type": "CE",
                    "direction": "sell",
                    "quantity_lots": 1,
                    "entry_premium": 75.0,
                    "expiry_date": "2026-09-24",
                    "lot_size": 75,
                },
            ],
            "current_spot": spot,
            "iv_per_leg": {"24800_CE": 0.14, "25100_CE": 0.14},
        }
        res = client.post("/api/strategy/compute", json=payload)
        assert res.status_code == 200
        pops.append(res.json()["pop"])

    # Monotonicity check
    assert pops[0] < pops[1] < pops[2]
