"""
Tests for BUILD-9-FIXES-A requirements:
  1. Alcohol streak logic: counts days since last yes, not reset on no.
  2. Stressor severity: YELLOW with 0.5% cap, financial prompt includes paper-trading.
  3. Meditation optional: null meditation_completed_at allows submission without 500.
  4. Error message surfacing: missing alcohol baseline surfaces actionable 400.
"""

from datetime import date, timedelta
from fastapi.testclient import TestClient
from swayam.api import app
from swayam.db import db
from swayam.readiness import AlcoholBaselineNotSetError, ReadinessInput, compute_readiness_verdict

client = TestClient(app)


def test_alcohol_streak_counts_days_since_last_yes_not_reset_on_no(mocker) -> None:
    """Verifies that answering No to alcohol calculates streak from the last Yes row in history."""
    today = date.today()
    last_yes_date = (today - timedelta(days=125)).strftime("%Y-%m-%d")

    mock_table = mocker.MagicMock()
    # Return a history log where user drank 125 days ago
    mock_history_row = {
        "log_date": last_yes_date,
        "factors": {"input": {"alcohol_yesterday": True}},
    }
    mock_table.select.return_value.gte.return_value.order.return_value.execute.return_value.data = [mock_history_row]
    mock_table.upsert.return_value.execute.return_value = mocker.MagicMock()
    mocker.patch.object(db.client, "table", return_value=mock_table)

    payload = {
        "sleep_hours_bucket": "7+",
        "alcohol_yesterday": False,
        "workout_in_last_48h": True,
        "journal_mood": "focused",
        "life_stressor": "none",
    }

    response = client.post("/api/readiness/log", json=payload)
    assert response.status_code == 200
    verdict = response.json()
    assert verdict["trading_allowed"] is True
    assert verdict["verdict"] == "green"
    # Day 125 falls into Month 5 ramp (days 121-150): 0.5% cap
    assert verdict["size_cap_pct"] == 0.0050


def test_stressor_severity_is_yellow_with_half_percent_cap() -> None:
    """Verifies life stressors (family, work, health, financial) are YELLOW with 0.5% cap."""
    for stressor in ["family", "work", "health", "financial"]:
        inp = ReadinessInput(
            sleep_hours_bucket="7+",
            alcohol_yesterday=False,
            workout_in_last_48h=True,
            journal_mood="focused",
            life_stressor=stressor,
            stressor_note="Testing stressor rule",
        )
        verdict = compute_readiness_verdict(inp, current_alcohol_streak_days=200)
        assert verdict.verdict == "yellow", f"{stressor} should be yellow, not red"
        assert verdict.trading_allowed is True
        assert verdict.size_cap_pct == 0.0050, f"{stressor} should cap size at 0.5%"
        assert verdict.per_factor_verdicts["stressor"] == "yellow"

        if stressor == "financial":
            assert any("paper-trading" in r.lower() for r in verdict.reasons)


def test_meditation_completed_at_optional_allows_submission(mocker) -> None:
    """Verifies meditation_completed_at=None submits successfully without server error."""
    mock_table = mocker.MagicMock()
    mock_table.select.return_value.gte.return_value.order.return_value.execute.return_value.data = []
    mock_table.select.return_value.eq.return_value.execute.return_value.data = [{"value": 200}]
    mock_table.upsert.return_value.execute.return_value = mocker.MagicMock()
    mocker.patch.object(db.client, "table", return_value=mock_table)

    payload = {
        "sleep_hours_bucket": "7+",
        "alcohol_yesterday": False,
        "workout_in_last_48h": True,
        "journal_mood": "focused",
        "life_stressor": "none",
        "meditation_completed_at": None,
    }

    response = client.post("/api/readiness/log", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "green"
    assert data["trading_allowed"] is True


def test_alcohol_baseline_not_set_raises_actionable_400(mocker) -> None:
    """Verifies when streak cannot be determined, actionable 400 is raised (not 500 or silent default)."""
    mock_table = mocker.MagicMock()
    # No history in log
    mock_table.select.return_value.gte.return_value.order.return_value.execute.return_value.data = []
    # No seed in config
    mock_table.select.return_value.eq.return_value.execute.return_value.data = []
    mock_table.select.return_value.eq.return_value.single.return_value.execute.return_value.data = None
    mocker.patch.object(db.client, "table", return_value=mock_table)

    payload = {
        "sleep_hours_bucket": "7+",
        "alcohol_yesterday": False,
        "workout_in_last_48h": True,
        "journal_mood": "focused",
        "life_stressor": "none",
    }

    response = client.post("/api/readiness/log", json=payload)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "set_alcohol_baseline.py" in detail
