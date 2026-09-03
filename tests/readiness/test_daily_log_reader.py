"""
Unit tests for Obsidian daily log reader in Swayam Capital.
"""

from datetime import date
from pathlib import Path
import pytest
from swayam.config import settings
from swayam.readiness.daily_log_reader import (
    DailyLogReaderError,
    check_workout_logged,
    get_daily_log_defaults,
    map_hours_to_bucket,
    parse_sleep_hours,
)


def test_parse_sleep_hours_handles_various_formats() -> None:
    assert parse_sleep_hours("* **Duration**: 8h 40m | **Sleep Score**: 89") == 8.67
    assert parse_sleep_hours("Duration: 7h 15m") == 7.25
    assert parse_sleep_hours("Sleep: 6h") == 6.0
    assert parse_sleep_hours("Had 7.5 hours sleep last night") == 7.5
    assert parse_sleep_hours("No sleep logged") is None


def test_map_hours_to_bucket_standardizes_bins() -> None:
    assert map_hours_to_bucket(2.5) == "<3"
    assert map_hours_to_bucket(3.5) == "3-4"
    assert map_hours_to_bucket(4.8) == "4-5"
    assert map_hours_to_bucket(5.2) == "5-6"
    assert map_hours_to_bucket(6.5) == "6-7"
    assert map_hours_to_bucket(8.0) == "7+"


def test_check_workout_logged_identifies_activity() -> None:
    assert check_workout_logged("* **Activity**: strength (442 kcal)") is True
    assert check_workout_logged("* [x] Evening gym workout") is True
    assert check_workout_logged("* **Activity**: None") is False
    assert check_workout_logged("* **Activity**: rest") is False


def test_get_daily_log_defaults_extracts_from_real_format(tmp_path: Path) -> None:
    orig_dir = settings.daily_log_dir
    object.__setattr__(settings, "daily_log_dir", str(tmp_path))

    today = date(2026, 9, 3)
    log_content = """# 📅 2026-09-03 Daily Log
## 🌙 Sleep & Recovery
* **Duration**: 8h 40m | **Sleep Score**: 89
## 🏃 Workout & Activity
* **Activity**: strength (442 kcal)
"""
    (tmp_path / "2026-09-03.md").write_text(log_content, encoding="utf-8")

    try:
        defaults = get_daily_log_defaults(today)
        assert defaults["sleep_hours"] == 8.67
        assert defaults["sleep_hours_bucket"] == "7+"
        assert defaults["workout_in_last_48h"] is True
        assert defaults["journal_mood"] is None  # Never defaulted
    finally:
        object.__setattr__(settings, "daily_log_dir", orig_dir)


def test_get_daily_log_defaults_raises_when_dir_missing(tmp_path: Path) -> None:
    orig_dir = settings.daily_log_dir
    non_existent = tmp_path / "does_not_exist"
    object.__setattr__(settings, "daily_log_dir", str(non_existent))

    try:
        with pytest.raises(DailyLogReaderError):
            get_daily_log_defaults(date.today())
    finally:
        object.__setattr__(settings, "daily_log_dir", orig_dir)
