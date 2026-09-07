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


def _compliant_payload(quantity_lots: int = 1) -> dict:
    return {
        "strategy_name": "Valid Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24850.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": quantity_lots,
                "entry_premium": 150.0,
                "expiry_date": "2026-09-24",
            },
            {
                "strike": 24100.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": quantity_lots,
                "entry_premium": 50.0,
                "expiry_date": "2026-09-24",
            },
        ],
        "current_spot": 24867.5,
        "iv_per_leg": {"default": 0.15},
    }


def test_readiness_red_verdict_has_no_power_over_the_trade_path(mocker) -> None:
    """A RED readiness day must not appear in the trade gate at all.

    This test used to assert the opposite. Abhishek's decision of 2026-09-07:
    the readiness form is a self-reported questionnaire and can be lied to, so
    it must have zero authority over money. It survives as a ceremonial
    journal. Its old implementation also failed OPEN three separate ways, so
    forgetting to fill it in allowed a full-size trade while filling it in
    honestly could shrink one.
    """
    today_str = date.today().strftime("%Y-%m-%d")
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

    response = client.post("/api/strategy/validate", json=_compliant_payload())
    assert response.status_code == 200
    data = response.json()

    # The check must not exist any more, under any name.
    assert not [c for c in data["checks"] if "readiness" in c["rule"]]

    # And the cap must be the full 1% of live capital, untouched by the RED row.
    cap_check = next(c for c in data["checks"] if c["rule"] == "realistic_risk")
    assert cap_check["cap_inr"] == 9710.02


def test_readiness_size_cap_no_longer_shrinks_the_risk_cap(mocker) -> None:
    """A YELLOW row carrying size_cap_pct must not throttle the cap.

    The old behaviour read size_cap_pct straight into the sizing rule, which is
    how a 0.3% throttle ended up in force without Abhishek choosing it.
    """
    today_str = date.today().strftime("%Y-%m-%d")
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

    response = client.post("/api/strategy/validate", json=_compliant_payload(quantity_lots=4))
    assert response.status_code == 200
    cap_check = next(c for c in response.json()["checks"] if c["rule"] == "realistic_risk")

    # 1% of the live 9,71,002.38, not 0.75% of a stale 8,50,000 (which was 6,375).
    assert cap_check["cap_inr"] == 9710.02



def test_log_readiness_raises_503_when_config_db_fails(mocker) -> None:
    mock_table = mocker.MagicMock()
    # Simulate DB network connection failure
    mock_table.select.side_effect = ConnectionError("Supabase connection timeout")
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
