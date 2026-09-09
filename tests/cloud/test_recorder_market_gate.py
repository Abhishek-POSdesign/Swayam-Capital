"""The recorder must not record on a day the exchange was shut.

On an NSE holiday the scheduler still fires, FYERS still answers, and it answers
with the previous session's frozen prices. Without a holiday check the recorder
wrote a full day of rows that look exactly like a real session until you notice
that nothing moved all day. A backtest reading that file would place trades on a
day the market was closed and believe the fills.

The calendar the recorder carries is a copy of the repository's, because a Cloud
Function is deployed from `cloud/recorder/` alone and cannot read `data/`. These
tests fail if the copy drifts.
"""

from datetime import datetime
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

RECORDER_DIR = Path(__file__).resolve().parent.parent.parent / "cloud" / "recorder"
if str(RECORDER_DIR) not in sys.path:
    sys.path.insert(0, str(RECORDER_DIR))

from fyers_recorder import is_market_open, load_nse_holidays  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REPO_CALENDAR = REPO_ROOT / "data" / "nse_holidays_2026.json"
RECORDER_CALENDAR = RECORDER_DIR / "nse_holidays.json"
IST = ZoneInfo("Asia/Kolkata")


def test_the_recorders_calendar_is_the_repositorys_calendar():
    """One list of holidays, in two places, that must never disagree."""
    assert RECORDER_CALENDAR.exists(), (
        "cloud/recorder/nse_holidays.json is missing; the recorder cannot see data/"
    )
    assert json.loads(RECORDER_CALENDAR.read_text(encoding="utf-8")) == json.loads(
        REPO_CALENDAR.read_text(encoding="utf-8")
    ), "the recorder's holiday calendar has drifted from data/nse_holidays_2026.json"


def test_the_calendar_covers_this_year_and_the_next():
    holidays = load_nse_holidays()
    assert 2026 in holidays and 2027 in holidays
    assert len(holidays[2026]) > 10


def test_it_does_not_record_on_a_trading_holiday():
    # Diwali, Laxmi Pujan, a Tuesday, mid-session.
    diwali = datetime(2026, 11, 10, 11, 30, tzinfo=IST)
    is_open, reason = is_market_open(diwali)
    assert is_open is False
    assert "holiday" in reason.lower()
    assert "2026-11-10" in reason


def test_it_does_record_on_the_working_day_beside_that_holiday():
    day_before = datetime(2026, 11, 9, 11, 30, tzinfo=IST)
    is_open, _ = is_market_open(day_before)
    assert is_open is True


def test_the_ordinary_gates_still_hold():
    assert is_market_open(datetime(2026, 9, 9, 11, 30, tzinfo=IST))[0] is True
    assert is_market_open(datetime(2026, 9, 12, 11, 30, tzinfo=IST))[0] is False  # Saturday
    assert is_market_open(datetime(2026, 9, 7, 8, 30, tzinfo=IST))[0] is False   # before 09:15
    assert is_market_open(datetime(2026, 9, 7, 16, 0, tzinfo=IST))[0] is False   # after 15:30


def test_a_year_the_calendar_does_not_cover_still_records(monkeypatch):
    """It fails OPEN on purpose.

    A stale calendar that stopped recording would lose every trading day of a
    year in silence. A stale calendar that keeps recording loses about fifteen
    days and says so in the log. The second is the smaller loss.
    """
    monkeypatch.setattr("fyers_recorder.load_nse_holidays", lambda: {2026: set()})
    is_open, reason = is_market_open(datetime(2030, 3, 6, 11, 30, tzinfo=IST))
    assert is_open is True, reason
