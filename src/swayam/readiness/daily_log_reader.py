"""
Obsidian Daily Log reader for extracting pre-trade readiness defaults.

Reads Abhishek's daily logs at {DAILY_LOG_DIR}/{YYYY-MM-DD}.md to extract
sleep hours, workout history, and health streaks.
"""

from datetime import date, timedelta
from pathlib import Path
import re
from typing import Any, Optional
from swayam.config import settings


class DailyLogReaderError(Exception):
    """Raised when daily log directory or file cannot be accessed due to I/O error."""
    pass


def parse_sleep_hours(text: str) -> Optional[float]:
    """Extracts total sleep duration in decimal hours from markdown text."""
    # Pattern: 'Duration: 8h 40m' or 'Duration: 7.5h' or 'Sleep: 6h 15m'
    pattern = re.compile(r"(?:Duration|Sleep)[:\s\*]+(\d+(?:\.\d+)?)\s*h(?:ours?)?(?:\s*(\d+)\s*m(?:inutes?)?)?", re.IGNORECASE)
    match = pattern.search(text)
    if match:
        hours = float(match.group(1))
        minutes = float(match.group(2)) if match.group(2) else 0.0
        return round(hours + (minutes / 60.0), 2)

    # Fallback pattern: '8.5 hours'
    pattern_alt = re.compile(r"(\d+(?:\.\d+)?)\s*hours?\s*sleep", re.IGNORECASE)
    match_alt = pattern_alt.search(text)
    if match_alt:
        return float(match_alt.group(1))

    return None


def map_hours_to_bucket(hours: float) -> str:
    """Maps decimal sleep hours to one of the 6 standardized dropdown buckets."""
    if hours < 3.0:
        return "<3"
    elif hours < 4.0:
        return "3-4"
    elif hours < 5.0:
        return "4-5"
    elif hours < 6.0:
        return "5-6"
    elif hours < 7.0:
        return "6-7"
    else:
        return "7+"


def check_workout_logged(text: str) -> bool:
    """Determines whether a workout or physical activity was recorded in the text."""
    # Look for 'Activity: strength' or 'Activity: walk' or completed workout checkbox
    activity_match = re.search(r"\*\s*\*\*Activity\*\*:\s*([^\n\r]+)", text, re.IGNORECASE)
    if activity_match:
        act = activity_match.group(1).strip().lower()
        if act and act not in ("none", "rest", "no workout", "off"):
            return True

    if re.search(r"\[x\][^\n\r]*(?:workout|gym|exercise|walk|jog|run)", text, re.IGNORECASE):
        return True

    return False


def get_daily_log_defaults(target_date: Optional[date] = None) -> dict[str, Any]:
    """Reads today's daily log (and yesterday's for workout window) to extract defaults.

    Returns:
        dict containing available defaults (or None for unsynced fields).

    Raises:
        DailyLogReaderError: On filesystem permission/access issues.
    """
    if target_date is None:
        target_date = date.today()

    log_dir = Path(settings.daily_log_dir)
    if not log_dir.exists():
        raise DailyLogReaderError(f"Daily log directory does not exist: {log_dir}")

    today_file = log_dir / f"{target_date.strftime('%Y-%m-%d')}.md"
    yesterday_file = log_dir / f"{(target_date - timedelta(days=1)).strftime('%Y-%m-%d')}.md"

    defaults: dict[str, Any] = {
        "sleep_hours": None,
        "sleep_hours_bucket": None,
        "workout_in_last_48h": None,
        "alcohol_yesterday": False,
        "journal_mood": None,       # Must be chosen manually by Abhishek
        "life_stressor": "none",
    }

    # 1. Parse today's log if it exists
    if today_file.exists():
        try:
            content = today_file.read_text(encoding="utf-8")
        except Exception as e:
            raise DailyLogReaderError(f"Failed to read daily log file {today_file}: {e}") from e

        sleep_hrs = parse_sleep_hours(content)
        if sleep_hrs is not None:
            defaults["sleep_hours"] = sleep_hrs
            defaults["sleep_hours_bucket"] = map_hours_to_bucket(sleep_hrs)

        if check_workout_logged(content):
            defaults["workout_in_last_48h"] = True
        else:
            defaults["workout_in_last_48h"] = False

    # 2. Check yesterday's log for 48h workout window if today had no workout logged
    if defaults["workout_in_last_48h"] is False and yesterday_file.exists():
        try:
            content_yest = yesterday_file.read_text(encoding="utf-8")
            if check_workout_logged(content_yest):
                defaults["workout_in_last_48h"] = True
        except Exception as e:
            raise DailyLogReaderError(f"Failed to read yesterday log file {yesterday_file}: {e}") from e

    return defaults
