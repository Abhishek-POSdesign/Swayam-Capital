"""The holiday calendar must agree with the days NSE actually traded.

On 13 September 2026 the calendar was found wrong on nine weekdays of 2026: five
days it called holidays had a full NSE bhavcopy, and four days it called trading
days had none. It also did not know Monday 14 September was a holiday. Every
existing test checked the calendar against itself. This one checks it against
the exchange's own daily files, which is the test that would have caught it.

The daily files are `data/history/options_eod/<year>.parquet`, NSE's F&O
bhavcopy. They are git-ignored and live on his PC, so a git worktree looks in
the primary folder it belongs to. Where neither has them, this skips and says so.
"""

from datetime import date, timedelta
import json
from pathlib import Path
import subprocess

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CALENDAR = REPO_ROOT / "data" / "nse_holidays_2026.json"


def _history_dir() -> Path | None:
    candidates = [REPO_ROOT / "data" / "history"]
    try:
        common = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        candidates.append(Path(common).parent / "data" / "history")
    except (OSError, subprocess.CalledProcessError):
        pass
    for c in candidates:
        if (c / "options_eod").is_dir():
            return c
    return None


def _calendar_years() -> dict[int, set[date]]:
    raw = json.loads(CALENDAR.read_text(encoding="utf-8"))
    return {
        int(k): {date.fromisoformat(e["date"]) for e in v}
        for k, v in raw.items()
        if str(k).isdigit()
    }


def test_every_weekday_agrees_with_the_nse_bhavcopy():
    history = _history_dir()
    if history is None:
        pytest.skip(
            "data/history/options_eod is not here or in the primary folder; "
            "this check needs NSE's daily files, which live only on his PC."
        )
    pd = pytest.importorskip("pandas")

    checked = 0
    mismatches: list[str] = []
    for year, holidays in sorted(_calendar_years().items()):
        parquet = history / "options_eod" / f"{year}.parquet"
        if not parquet.exists():
            continue
        df = pd.read_parquet(parquet, columns=["trade_date", "underlying"])
        sessions = set(pd.to_datetime(df.loc[df["underlying"] == "NIFTY", "trade_date"]).dt.date)
        assert sessions, f"{parquet} holds no NIFTY rows at all"
        day, last = min(sessions), max(sessions)
        while day <= last:
            if day.weekday() < 5:
                checked += 1
                if day in holidays and day in sessions:
                    mismatches.append(f"{day} is marked a holiday, but NSE has NIFTY rows for it")
                elif day not in holidays and day not in sessions:
                    mismatches.append(f"{day} is not marked a holiday, but NSE has no NIFTY rows for it")
            day += timedelta(days=1)

    if checked == 0:
        pytest.skip(f"No options_eod file in {history} covers a year the calendar lists.")
    assert not mismatches, (
        f"The holiday calendar disagrees with NSE on {len(mismatches)} of {checked} weekdays:\n  "
        + "\n  ".join(mismatches)
    )
