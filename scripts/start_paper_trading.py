"""Declare the day paper trading begins. ABHISHEK RUNS THIS, AND ONLY HE DOES.

WHY THIS EXISTS
---------------
His correction, 2026-09-10: "We have not started the paper trading. We are
doing the testing of how the terminal works. All these paper trades are test
trades... I did not backtest, plan, or review it. It was just clicking the
order and checking how the terminal behaves."

And why the line matters to him: "how I will play with the money depends upon
how my paper trade will perform." The paper record is the evidence he will
judge real money by, so it has to start on a day he chose, with nothing before
it.

WHAT IT DOES
------------
Writes one timestamp into the single row of `swayam_phase`. From that moment,
every new position is written with `provenance = 'live'` and its note goes to
`04 - Journal/` instead of `04 - Journal/Terminal tests/`. Nothing that already
exists is touched, moved or renamed: use `scripts/mark_terminal_tests.py` for
that, and run it BEFORE this one.

IT REFUSES TO RUN TWICE. A second start would move the line under trades
already recorded as paper, which is the one thing this script exists to
prevent. If the day is genuinely wrong, the fix is a deliberate edit to that
one row, not a re-run.

DO NOT RUN THIS UNTIL HE SAYS PAPER TRADING STARTS. No build, no agent and no
test may run it on his behalf.

    .\\.venv\\Scripts\\python.exe scripts\\start_paper_trading.py            # show the state
    .\\.venv\\Scripts\\python.exe scripts\\start_paper_trading.py --start    # declare today
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swayam.db import db  # noqa: E402
from swayam.services.phase import read_phase  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")


def _ist(stamp: datetime) -> str:
    return stamp.astimezone(IST).strftime("%d %b %Y, %H:%M IST")


def main() -> int:
    ap = argparse.ArgumentParser(description="Declare the day paper trading begins.")
    ap.add_argument(
        "--start",
        action="store_true",
        help="Actually declare it. Without this the script only reports the state.",
    )
    ap.add_argument(
        "--note",
        default=None,
        help="A line recorded beside the timestamp, in his own words.",
    )
    args = ap.parse_args()

    phase = read_phase()

    if phase.source != "table":
        print("The phase table could not be read, so nothing was changed.")
        print(f"  reason: {phase.unavailable_reason}")
        print("  Apply migration 023 first, then run this again.")
        return 2

    if phase.paper_trading_started:
        print("PAPER TRADING HAS ALREADY STARTED. Nothing was changed.")
        print(f"  started: {_ist(phase.paper_trading_started_at)}")
        print(f"  set by:  {phase.set_by or 'not recorded'}")
        print(f"  note:    {phase.note or 'none'}")
        print()
        print("  This script refuses to run twice on purpose. Moving the line")
        print("  would reclassify trades already recorded as paper trades.")
        return 1

    if not args.start:
        print("Paper trading has NOT started. Every trade recorded so far is a terminal test.")
        print()
        print("  Nothing was changed. This was a report, not a declaration.")
        print("  Run mark_terminal_tests.py --apply FIRST, so the trades already")
        print("  in the record are marked before the line is drawn.")
        print()
        print("  When you are ready:")
        print("    .\\.venv\\Scripts\\python.exe scripts\\start_paper_trading.py --start")
        return 0

    now = datetime.now(timezone.utc)
    update = {
        "paper_trading_started_at": now.isoformat(),
        "set_by": "Abhishek",
        "note": args.note or "Declared by scripts/start_paper_trading.py.",
    }
    try:
        db.client.table("swayam_phase").update(update).eq("id", 1).execute()
    except Exception as exc:
        print(f"FAILED. Nothing was changed. {exc}")
        return 3

    back = read_phase()
    if not back.paper_trading_started:
        print("The write reported success but the row still says not started.")
        print("Nothing may be treated as a paper trade until this reads back.")
        return 3

    print("PAPER TRADING HAS STARTED.")
    print(f"  from: {_ist(back.paper_trading_started_at)}")
    print(f"  note: {back.note}")
    print()
    print("  From now on a new trade is written as `live` and its note goes")
    print("  into `04 - Journal/`. Everything before this line stays where it is.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
