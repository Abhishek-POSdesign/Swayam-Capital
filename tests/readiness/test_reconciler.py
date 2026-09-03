"""
Unit tests for end-of-day readiness reconciler.
"""

from datetime import date
from pathlib import Path
import pytest
from swayam.config import settings
from swayam.db import db
from swayam.readiness.reconciler import reconcile_readiness_for_date


def test_reconciler_detects_sleep_and_workout_discrepancies(mocker, tmp_path: Path) -> None:
    orig_dir = settings.daily_log_dir
    object.__setattr__(settings, "daily_log_dir", str(tmp_path))

    today = date(2026, 9, 3)
    today_str = "2026-09-03"

    # Daily log has 4.5 hours sleep and no workout
    log_content = """# 📅 2026-09-03 Daily Log
## 🌙 Sleep & Recovery
* **Duration**: 4h 30m | **Sleep Score**: 60
## 🏃 Workout & Activity
* **Activity**: none
"""
    (tmp_path / f"{today_str}.md").write_text(log_content, encoding="utf-8")

    # Mock Supabase readiness log where manual entry claimed 6-7h and workout=True
    mock_db_row = {
        "log_date": today_str,
        "verdict": "green",
        "factors": {
            "input": {
                "sleep_hours_bucket": "6-7",
                "workout_in_last_48h": True,
                "alcohol_yesterday": False,
            }
        },
    }

    mock_table = mocker.MagicMock()
    mock_table.select.return_value.eq.return_value.execute.return_value.data = [mock_db_row]
    mock_table.update.return_value.eq.return_value.execute.return_value = mocker.MagicMock()
    mocker.patch.object(db.client, "table", return_value=mock_table)

    try:
        rec = reconcile_readiness_for_date(today)
        assert rec.has_discrepancies is True
        fields = [d.field for d in rec.discrepancies]
        assert "sleep_hours" in fields
        assert "workout_in_last_48h" in fields
    finally:
        object.__setattr__(settings, "daily_log_dir", orig_dir)


def test_reconciler_raises_when_no_readiness_logged(mocker) -> None:
    today = date(2026, 9, 3)
    mock_table = mocker.MagicMock()
    mock_table.select.return_value.eq.return_value.execute.return_value.data = []
    mocker.patch.object(db.client, "table", return_value=mock_table)

    with pytest.raises(ValueError, match="No readiness log found"):
        reconcile_readiness_for_date(today)
