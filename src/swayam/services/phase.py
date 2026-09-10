"""Has paper trading started, and what a new position should therefore be called.

WHY THIS EXISTS
---------------
His correction, 2026-09-10: "We have not started the paper trading. We are
doing the testing of how the terminal works. All these paper trades are test
trades... I did not backtest, plan, or review it. It was just clicking the
order and checking how the terminal behaves."

Every position in the record today was a click to see what the terminal would
do. The fills were real, the charges were real, the arithmetic was real, but
none of it was a trade he planned, and none of it belongs in the record his
paper results will be judged against. His words: "how I will play with the
money depends upon how my paper trade will perform."

So there is one timestamp, in one row of `swayam_phase`, and it is null. While
it is null every new position is written with `provenance = 'terminal_test'`.
Once he runs `scripts/start_paper_trading.py` it holds a day, and positions
opened after it are `'live'`.

THE FALLBACK IS DELIBERATE AND IT IS "NOT STARTED".
---------------------------------------------------
If the table cannot be read at all -- the migration is not applied yet, the
database is unreachable, the column is missing -- this answers "paper trading
has not started". That is true today, and it is the safe direction in every
other case too: a terminal test wrongly written as `live` quietly dirties the
record, while a paper trade wrongly written as `terminal_test` is a visible
mistake he can see and a script can correct.

This is NOT a fabricated figure. It is the conservative reading of an unknown,
and `read_phase()` says which of the two it is through `.source`, so anything
that shows it on a screen can say so.

NEVER CACHE THE ANSWER IN A CONSTANT. It changes exactly once, on a day he
chooses, and a module-level constant captured at import would go on calling his
first real paper trade a terminal test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from swayam.db import db

# The three values `swayam_positions.provenance` may hold. `build_test` is set
# by migrations 017 and 018 and by nothing in this module.
PROVENANCE_LIVE = "live"
PROVENANCE_TERMINAL_TEST = "terminal_test"
PROVENANCE_BUILD_TEST = "build_test"


@dataclass(frozen=True)
class Phase:
    """Whether paper trading has begun, and how confidently that is known."""

    paper_trading_started_at: Optional[datetime]
    set_by: Optional[str]
    note: Optional[str]
    #   'table'       - read from swayam_phase, so this is the real answer
    #   'unreadable'  - the table could not be read; treated as not started
    source: str
    unavailable_reason: Optional[str] = None

    @property
    def paper_trading_started(self) -> bool:
        return self.paper_trading_started_at is not None

    @property
    def provenance_for_new_position(self) -> str:
        """What `provenance` a position opened right now should carry."""
        return PROVENANCE_LIVE if self.paper_trading_started else PROVENANCE_TERMINAL_TEST

    @property
    def testing(self) -> bool:
        """True while everything the terminal records is a terminal test."""
        return not self.paper_trading_started

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_trading_started": self.paper_trading_started,
            "paper_trading_started_at": (
                self.paper_trading_started_at.isoformat()
                if self.paper_trading_started_at
                else None
            ),
            "set_by": self.set_by,
            "note": self.note,
            "source": self.source,
            "unavailable_reason": self.unavailable_reason,
        }


def _parse_stamp(value: Any) -> Optional[datetime]:
    """An ISO timestamp from the database, or None. Never guesses a date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        # Postgres hands back '+00:00' or 'Z'; datetime accepts only the first.
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def read_phase() -> Phase:
    """Read the one phase row. Fresh every time; never cached."""
    try:
        res = db.client.table("swayam_phase").select("*").eq("id", 1).limit(1).execute()
        rows = getattr(res, "data", None) or []
    except Exception as exc:  # the table may not exist until 023 is applied
        return Phase(
            paper_trading_started_at=None,
            set_by=None,
            note=None,
            source="unreadable",
            unavailable_reason=str(exc),
        )

    if not rows:
        return Phase(
            paper_trading_started_at=None,
            set_by=None,
            note=None,
            source="unreadable",
            unavailable_reason="swayam_phase has no row 1",
        )

    row = rows[0] or {}
    return Phase(
        paper_trading_started_at=_parse_stamp(row.get("paper_trading_started_at")),
        set_by=row.get("set_by"),
        note=row.get("note"),
        source="table",
    )


def provenance_for_new_position() -> str:
    """`'terminal_test'` while he is still testing, `'live'` once he has said."""
    return read_phase().provenance_for_new_position


def paper_trading_started() -> bool:
    return read_phase().paper_trading_started
