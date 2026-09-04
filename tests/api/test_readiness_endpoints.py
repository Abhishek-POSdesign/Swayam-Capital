"""
Integration tests for Readiness API endpoints and strategy validation gating.
"""

from datetime import date
from fastapi.testclient import TestClient
from swayam.api import app
from swayam.db import db

client = TestClient(app)


def test_get_today_readiness_unlogged_returns_atlas_defaults(mocker) -> None:
    today_str = date.today().strftime("%Y-%m-%d")

    # Mock no existing log in DB
    mock_table = mocker.MagicMock()
    mock_table.select.return_value.eq.return_value.execute.return_value.data = []
    mocker.patch.object(db.client, "table", return_value=mock_table)

    mocker.patch(
        "swayam.api.routes.readiness.get_daily_log_defaults",
        return_value={"sleep_hours": 6.5, "sleep_hours_bucket": "6-7", "workout_in_last_48h": True},
    )

    response = client.get("/api/readiness/today")
    assert response.status_code == 200
    data = response.json()
    assert data["logged"] is False
    assert data["atlas_defaults"]["sleep_hours"] == 6.5


def test_log_readiness_saves_and_returns_verdict(mocker) -> None:
    mock_table = mocker.MagicMock()
    # Mock config table for alcohol streak (outside ramp)
    mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {"value": 200}
    mock_table.upsert.return_value.execute.return_value = mocker.MagicMock()
    mocker.patch.object(db.client, "table", return_value=mock_table)

    payload = {
        "sleep_hours_bucket": "6-7",
        "alcohol_yesterday": False,
        "workout_in_last_48h": True,
        "journal_mood": "focused",
        "life_stressor": "none",
    }

    response = client.post("/api/readiness/log", json=payload)
    assert response.status_code == 200
    verdict = response.json()
    assert verdict["verdict"] == "green"
    assert verdict["trading_allowed"] is True
    assert verdict["size_cap_pct"] == 0.01


def test_readiness_red_verdict_blocks_strategy_validation(mocker) -> None:
    today_str = date.today().strftime("%Y-%m-%d")

    # Mock that today's readiness is RED
    mock_row = {
        "log_date": today_str,
        "verdict": "red",
        "trading_allowed": False,
        "size_cap_pct": None,
        "factors": {"reasons": ["Sleep < 5.0h threshold: Trading blocked."]},
    }
    mock_table = mocker.MagicMock()
    mock_table.select.return_value.eq.return_value.execute.return_value.data = [mock_row]
    mocker.patch.object(db.client, "table", return_value=mock_table)
    mocker.patch("swayam.db.db.get_margin_base_inr", return_value=850000.0)

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
    assert data["passed"] is False
    readiness_check = next((c for c in data["checks"] if c["rule"] == "readiness_gate"), None)
    assert readiness_check is not None
    assert readiness_check["verdict"] == "FAIL"


def test_readiness_yellow_verdict_enforces_reduced_size_cap(mocker) -> None:
    today_str = date.today().strftime("%Y-%m-%d")

    # Mock that today's readiness is YELLOW with 0.0075 (0.75%) sizing cap
    mock_row = {
        "log_date": today_str,
        "verdict": "yellow",
        "trading_allowed": True,
        "size_cap_pct": 0.0075,
        "factors": {"reasons": ["Sleep 5-6h warrants reduced sizing (75%)."]},
    }
    mock_table = mocker.MagicMock()
    mock_table.select.return_value.eq.return_value.execute.return_value.data = [mock_row]
    mocker.patch.object(db.client, "table", return_value=mock_table)
    mocker.patch("swayam.db.db.get_margin_base_inr", return_value=850000.0)

    # 1% cap on ₹8,50,000 = ₹8,500.
    # 0.75% cap on ₹8,50,000 = ₹6,375. With 2% tolerance = ₹6,502.5.
    # We construct a spread with max loss = ₹7,500 (100 pts x 75).
    # Under standard 1% cap (₹8,500), ₹7,500 PASSES.
    # Under Yellow 0.75% cap (₹6,375), ₹7,500 FAILS!
    payload = {
        "strategy_name": "Spread Exceeding Yellow Cap",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24850.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 4,
                "entry_premium": 150.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
            {
                "strike": 24700.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 4,
                "entry_premium": 87.0,
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
    cap_check = next(c for c in data["checks"] if c["rule"] == "realistic_risk")
    assert cap_check["verdict"] == "FAIL"
    assert cap_check["cap_inr"] == 6375.0


def test_log_readiness_raises_503_when_config_db_fails(mocker) -> None:
    mock_table = mocker.MagicMock()
    # Simulate DB network connection failure
    mock_table.select.return_value.eq.return_value.single.return_value.execute.side_effect = ConnectionError("Supabase connection timeout")
    mocker.patch.object(db.client, "table", return_value=mock_table)

    payload = {
        "sleep_hours_bucket": "6-7",
        "alcohol_yesterday": False,
        "workout_in_last_48h": True,
        "journal_mood": "focused",
        "life_stressor": "none",
    }

    response = client.post("/api/readiness/log", json=payload)
    assert response.status_code == 503
    assert "Database unreachable" in response.json()["detail"]
