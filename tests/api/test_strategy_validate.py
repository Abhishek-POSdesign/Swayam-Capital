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


def test_validate_raises_503_when_supabase_unreachable_for_margin_base(mocker) -> None:
    """If db.get_margin_base_inr raises, validate returns 503, not silent fallback."""
    from swayam.db import DatabaseError
    mocker.patch("swayam.db.db.get_margin_base_inr", side_effect=DatabaseError("Config row missing"))
    valid_payload = {
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
    response = client.post("/api/strategy/validate", json=valid_payload)
    assert response.status_code == 503
    assert "margin base unavailable" in response.json()["detail"].lower()


def test_validate_uses_settings_tolerance_not_hardcoded_002() -> None:
    """Verify TolerantComparator receives settings.default_tolerance_pct, not 0.02 literal."""
    from swayam.config import settings

    orig_tolerance = settings.default_tolerance_pct
    object.__setattr__(settings, "default_tolerance_pct", 0.05)  # override to 5%
    try:
        # Margin base = ₹8,50,000 -> 1% cap = ₹8,500.
        # At 2% tolerance: cap max = 8500 * 1.02 = 8670.
        # At 5% tolerance: cap max = 8500 * 1.05 = 8925.
        # Max loss = (167.333 - 50.0) * 75 = 8800.0.
        # With 2% tolerance it would FAIL (8800 > 8670).
        # With 5% tolerance it PASSES (8800 <= 8925).
        payload = {
            "strategy_name": "Boundary Spread",
            "underlying": "NIFTY",
            "legs": [
                {
                    "strike": 24850.0,
                    "option_type": "PE",
                    "direction": "buy",
                    "quantity_lots": 1,
                    "entry_premium": 167.33333333333334,
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
        cap_check = next(c for c in data["checks"] if c["rule"] == "per_trade_risk_cap")
        assert cap_check["verdict"] == "PASS"
        assert cap_check["tolerance_pct"] == 0.05
    finally:
        object.__setattr__(settings, "default_tolerance_pct", orig_tolerance)

