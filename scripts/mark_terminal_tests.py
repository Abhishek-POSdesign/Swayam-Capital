"""Mark the trades he clicked to test the terminal as what they were.

WHY THIS EXISTS
---------------
His correction, 2026-09-10: "We have not started the paper trading. We are
doing the testing of how the terminal works. All these paper trades are test
trades... I did not backtest, plan, or review it. It was just clicking the
order and checking how the terminal behaves."

Every row in his record today says `provenance = 'live'`, because that has been
the column default since migration 017. None of them was a trade he planned.
This moves them to `terminal_test` and moves their notes into
`04 - Journal/Terminal tests/`, so his paper record can start clean on the day
he says.

WHAT IT WILL NOT DO
-------------------
* IT SKIPS AN OPEN TRADE, and says so. His condor 7cd4d017 is open on purpose,
  as the first real subject of the position area. A trade is marked only once
  it is closed, so nothing a script does can disturb a position he is holding.
* It never touches a row already marked `build_test`. Those were quarantined by
  migrations 017 and 018 and are not his.
* It never touches a row opened AFTER paper trading started, if it has.
* It writes nothing at all without `--apply`. The dry run is the default.

HOW IT AVOIDS HALF-DOING A ROW
------------------------------
One row at a time. The note is moved first, then the row, then the journal
index, then any outbox row that names the old path. If the row update fails the
note is moved BACK and the row is reported untouched, so a failure leaves a
trade exactly as it was rather than with its record and its note disagreeing.

    .\\.venv\\Scripts\\python.exe scripts\\mark_terminal_tests.py           # list, change nothing
    .\\.venv\\Scripts\\python.exe scripts\\mark_terminal_tests.py --apply   # do it
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swayam.api.journal_writer import TERMINAL_TESTS_SUBFOLDER  # noqa: E402
from swayam.config import settings  # noqa: E402
from swayam.db import db  # noqa: E402
from swayam.services.phase import (  # noqa: E402
    PROVENANCE_LIVE,
    PROVENANCE_TERMINAL_TEST,
    read_phase,
)

JOURNAL_REL = "02 - Projects/Trading/04 - Journal"
TESTS_REL = f"{JOURNAL_REL}/{TERMINAL_TESTS_SUBFOLDER}"


def candidates(rows: list[dict[str, Any]], started_at) -> tuple[list, list]:
    """Split the record into what this script will mark and what it will leave.

    Pure, so it can be tested against faked rows without a database.
    Returns (to_mark, skipped) where each skipped entry carries its reason.
    """
    to_mark: list[dict[str, Any]] = []
    skipped: list[tuple[dict[str, Any], str]] = []

    for row in rows:
        provenance = str(row.get("provenance") or "").lower()
        status = str(row.get("status") or "").lower()

        if provenance != PROVENANCE_LIVE:
            skipped.append((row, f"already marked {provenance or 'nothing'}"))
            continue
        if status != "closed":
            skipped.append(
                (row, f"still {status or 'open'}; a trade is marked only once it is closed")
            )
            continue
        if started_at is not None:
            opened = str(row.get("opened_at") or "")
            if opened and opened >= started_at.isoformat():
                skipped.append((row, "opened after paper trading started, so it is a paper trade"))
                continue
        to_mark.append(row)

    return to_mark, skipped


def resolve_note(row: dict[str, Any], entry_paths: dict[str, str]) -> Optional[str]:
    """Where this trade's note actually is, the same way the drainer finds it.

    WHY THIS IS NOT JUST `journal_path`
    -----------------------------------
    Four of his five closed trades carry NO `journal_path` on the position row,
    and their notes exist all the same: they were queued in the outbox and
    written later by `scripts/drain_journal_outbox.py`, which records the path
    it wrote in `swayam_journal_entries.md_path` and does not always put it back
    on the row. Reading only the row made this script report "no note recorded"
    for 6b4f364e, 63ce13e6, 03a1b63d and 8030ed03 and it would have marked them
    while leaving four real notes sitting in his journal folder.

    So the row wins when it has one, and the journal index answers when it does
    not. Exactly `_resolve_note_path` in the drainer, which has been finding
    them correctly all along.

    Pure: the index is handed in, so this can be tested against faked rows.
    """
    on_row = row.get("journal_path")
    if on_row:
        return str(on_row).replace("\\", "/")
    from_index = entry_paths.get(str(row.get("id")))
    if from_index:
        return str(from_index).replace("\\", "/")
    return None


def _entry_paths_for(position_ids: list[str]) -> dict[str, str]:
    """The note each trade's journal index points at. One query, not one each."""
    if not position_ids:
        return {}
    try:
        rows = (
            db.client.table("swayam_journal_entries")
            .select("position_id,md_path,entry_type")
            .in_("position_id", position_ids)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print(f"  the journal index could not be read, so only the rows own paths are known: {exc}")
        return {}

    out: dict[str, str] = {}
    for r in rows:
        # The ENTRY note is the file; an exit or adjustment row names the same
        # file, so either will do, but the entry is the one to prefer.
        pid = str(r.get("position_id"))
        path = r.get("md_path")
        if not path:
            continue
        if str(r.get("entry_type") or "") == "entry" or pid not in out:
            out[pid] = str(path)
    return out


def _new_rel_path(old: Optional[str]) -> Optional[str]:
    """The same note, one folder deeper. None when there is no note to move."""
    if not old:
        return None
    old = str(old).replace("\\", "/")
    if f"/{TERMINAL_TESTS_SUBFOLDER}/" in old:
        return old  # already there
    if not old.startswith(JOURNAL_REL + "/"):
        return None  # somewhere this script does not understand; leave it alone
    return f"{TESTS_REL}/{old.rsplit('/', 1)[-1]}"


def _move_note(old_rel: str, new_rel: str) -> tuple[bool, str]:
    """Move one note inside his vault. Never overwrites anything."""
    base = settings.vault_path
    src, dst = base / old_rel, base / new_rel
    if not src.exists():
        return False, f"the note is not at {old_rel}"
    if dst.exists():
        return False, f"a note already sits at {new_rel}; nothing was overwritten"
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    return True, "moved"


def main() -> int:
    ap = argparse.ArgumentParser(description="Mark terminal tests in his record.")
    ap.add_argument("--apply", action="store_true", help="Actually write. Default is a dry run.")
    args = ap.parse_args()

    phase = read_phase()
    if phase.source != "table":
        print("The phase table could not be read, so nothing was changed.")
        print(f"  reason: {phase.unavailable_reason}")
        print("  Apply migration 023 first, then run this again.")
        return 2

    try:
        rows = (
            db.client.table("swayam_positions")
            .select("id,strategy_name,status,provenance,opened_at,closed_at,journal_path")
            .order("opened_at")
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print(f"Could not read the positions, so nothing was changed. {exc}")
        return 2

    to_mark, skipped = candidates(rows, phase.paper_trading_started_at)

    # Resolved ONCE, and the same answers are used for the listing and for the
    # move, so what the dry run shows him is exactly what --apply does.
    entry_paths = _entry_paths_for([str(r.get("id")) for r in to_mark])
    notes = {str(r.get("id")): resolve_note(r, entry_paths) for r in to_mark}

    print(f"Paper trading started: {phase.paper_trading_started_at or 'NOT YET'}")
    print(f"Rows read: {len(rows)}")
    print()

    if skipped:
        print(f"LEFT ALONE ({len(skipped)}):")
        for row, why in skipped:
            print(f"  {str(row.get('id'))[:8]}  {str(row.get('strategy_name') or ''):24}  {why}")
        print()

    if not to_mark:
        print("Nothing to mark.")
        return 0

    print(f"WOULD MARK terminal_test ({len(to_mark)}):" if not args.apply else f"MARKING ({len(to_mark)}):")
    for row in to_mark:
        pid = str(row.get("id"))
        old_rel = notes.get(pid)
        new_rel = _new_rel_path(old_rel)
        where = "" if row.get("journal_path") else " (path from the journal index)"
        note_text = (
            f"note {old_rel} -> {new_rel}{where}"
            if new_rel and new_rel != old_rel
            else ("note already in Terminal tests" if new_rel else "no note recorded")
        )
        print(f"  {pid[:8]}  {str(row.get('strategy_name') or ''):24}  {note_text}")

    if not args.apply:
        print()
        print("Nothing was written. This was a dry run.")
        print("  Run again with --apply when you are ready.")
        return 0

    print()
    done = 0
    failed = 0
    for row in to_mark:
        pid = str(row.get("id"))
        old_rel = notes.get(pid)
        new_rel = _new_rel_path(old_rel)
        moved = False

        if new_rel and new_rel != old_rel:
            ok, why = _move_note(str(old_rel), new_rel)
            if not ok:
                print(f"  FAILED  {pid[:8]}  {why}. The row was NOT changed.")
                failed += 1
                continue
            moved = True

        update: dict[str, Any] = {"provenance": PROVENANCE_TERMINAL_TEST}
        if new_rel:
            update["journal_path"] = new_rel

        try:
            db.client.table("swayam_positions").update(update).eq("id", pid).execute()
        except Exception as exc:
            if moved:
                # Put the note back, so the trade is exactly as it was.
                (settings.vault_path / new_rel).rename(settings.vault_path / str(old_rel))
            print(f"  FAILED  {pid[:8]}  {exc}. The note was put back and the row is untouched.")
            failed += 1
            continue

        # The journal index and the outbox point at the same note. They are
        # best-effort: the trade is already marked correctly, and a stale path
        # in an index is a smaller wrong than a half-marked trade.
        if new_rel:
            for table, column in (("swayam_journal_entries", "md_path"), ("swayam_journal_outbox", "md_path")):
                try:
                    db.client.table(table).update(
                        {column: new_rel, "provenance": PROVENANCE_TERMINAL_TEST}
                        if table == "swayam_journal_entries"
                        else {column: new_rel}
                    ).eq("position_id", pid).execute()
                except Exception as exc:
                    print(f"          {pid[:8]}  {table} not updated: {exc}")

        print(f"  marked  {pid[:8]}  {str(row.get('strategy_name') or '')}")
        done += 1

    print()
    print(f"Marked {done}. Failed {failed}. Left alone {len(skipped)}.")
    if failed:
        print("Every failed row is exactly as it was. Read the reason above and run again.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
