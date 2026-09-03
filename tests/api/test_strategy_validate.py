"""
Tests for Method rule validation endpoint in Swayam Capital.
"""

from fastapi.testclient import TestClient
from swayam.api import app

client = TestClient(app)


def test_validate_compliant_spread_passes() -> None:
    payload = {
        "strategy_name": "Valid Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24850.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 150.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
            {
                "strike": 24100.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 1,
                "entry_premium": 50.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
        ],
        "current_spot": 24867.5,
        "iv_per_leg": {"default": 0.15},
    }

    response = client.post("/api/strategy/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is True
    assert len(data["checks"]) >= 4


def test_validate_single_leg_fails_no_single_leg_rule() -> None:
    payload = {
        "strategy_name": "Naked Call",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 25000.0,
                "option_type": "CE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 150.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            }
        ],
        "current_spot": 24867.5,
        "iv_per_leg": {"default": 0.15},
    }

    response = client.post("/api/strategy/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is False

    rule_checks = {c["rule"]: c["verdict"] for c in data["checks"]}
    assert rule_checks["no_single_leg"] == "FAIL"


def test_validate_excessive_loss_fails_per_trade_risk_cap() -> None:
    # 20 lots with ₹200 risk = ₹3,00,000 max loss, which blows past 1% cap (~₹8,500)
    payload = {
        "strategy_name": "Excessive Risk Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 25000.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 20,
                "entry_premium": 300.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
            {
                "strike": 24000.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 20,
                "entry_premium": 100.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
        ],
        "current_spot": 24867.5,
        "iv_per_leg": {"default": 0.15},
    }

    response = client.post("/api/strategy/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is False

    rule_checks = {c["rule"]: c["verdict"] for c in data["checks"]}
    assert rule_checks["per_trade_risk_cap"] == "FAIL"
