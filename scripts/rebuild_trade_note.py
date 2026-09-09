"""Rebuild a trade note that the live site reported writing and never wrote.

WHY THIS EXISTS
---------------
On 2026-09-09, Abhishek's first ever paper trade was executed on the live site.
`VAULT_PATH` is unset on Cloud Run, so the config fell back to the Windows path
for his G: drive. On Linux that is not a drive: it is a relative folder whose
name merely contains a colon and backslashes. `mkdir(parents=True)` created it
inside the container, the write succeeded, the row was marked
`journal_status = 'written'`, and the note died with the container.

The writer refuses an unreachable vault now, so from today such a note is queued
in the outbox and the drainer completes it. This script is for the ONE trade
that fell through the gap before that fix landed.

WHAT IT DOES NOT DO
-------------------
It rebuilds the note from what the database actually holds. The Greeks and the
rule-validation results were never stored on the position row, so they are NOT
in the rebuilt note and it says so on its face. Nothing is invented.

    .\\.venv\\Scripts\\python.exe scripts\\rebuild_trade_note.py            # list
    .\\.venv\\Scripts\\python.exe scripts\\rebuild_trade_note.py <id>       # rebuild
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swayam.api.journal_writer import (  # noqa: E402
    JournalWriteError,
    get_journal_dir,
    write_new_trade_journal,
)
from swayam.config import settings  # noqa: E402
from swayam.db import db  # noqa: E402

REBUILD_NOTICE = (
    "This note was REBUILT from the database on a later date, because the live "
    "site reported writing it and never did. The Greeks and the rule-validation "
    "results were never stored on the position row, so they are absent here "
    "rather than guessed. Everything else is exactly what was recorded at entry."
)


def _live_positions() -> list[dict]:
    return db.client.table("swayam_positions").select("*").eq("provenance", "live").execute().data or []


def _note_exists(rel_path: str | None) -> bool:
    if not rel_path:
        return False
    return (settings.vault_path / rel_path).exists()


def _spread_from_row(row: dict) -> dict:
    max_loss = float(row.get("max_loss_inr") or 0.0)
    max_profit = float(row.get("max_profit_inr") or 0.0)
    return {
        "strategy_name": row.get("strategy_name") or "Custom",
        "underlying": row.get("underlying") or "NIFTY",
        "expiry_date": row.get("expiry_date"),
        "legs": row.get("legs") or [],
        "payoff_curve": {
            "max_loss_inr": max_loss,
            "max_profit_inr": max_profit,
            # Computed from the two figures the row does hold, not invented.
            "rr_implied": round(max_profit / max_loss, 2) if max_loss > 0 else 0.0,
            "net_debit_credit_inr": float(row.get("net_debit_credit_inr") or 0.0),
            "breakevens": row.get("breakeven_points") or [],
        },
        # Never stored on the row. An empty mapping prints em dashes.
        "greeks": {},
    }


def main() -> int:
    rows = _live_positions()

    if len(sys.argv) < 2:
        print(f"vault    : {settings.vault_path}")
        print(f"reachable: {'yes' if settings.vault_path.is_dir() else 'NO'}")
        print()
        if not rows:
            print("No positions of your own. Nothing to rebuild.")
            return 0
        print("your positions:")
        for r in rows:
            here = _note_exists(r.get("journal_path"))
            print(
                f"  {r['id']}  {r.get('status'):<8} {r.get('strategy_name'):<20} "
                f"note {'present' if here else 'MISSING'}  {r.get('journal_path') or '(no path recorded)'}"
            )
        print()
        print("Pass an id to rebuild that one's note.")
        return 0

    wanted = sys.argv[1]
    row = next((r for r in rows if str(r["id"]) == wanted), None)
    if row is None:
        print(f"No position of yours with id {wanted}.")
        return 1

    if _note_exists(row.get("journal_path")):
        print(f"The note already exists at {row['journal_path']}. Nothing done.")
        return 0

    if not settings.vault_path.is_dir():
        print(f"Your vault is not reachable at {settings.vault_path}. Run this on your PC.")
        return 1

    # Keep the original filename if one was recorded, so the database, the
    # journal index and the file all agree.
    recorded = row.get("journal_path")
    target_name = Path(recorded).name if recorded else None
    if target_name:
        journal_dir = get_journal_dir()
        if (journal_dir / target_name).exists():
            print(f"{target_name} already exists. Nothing done.")
            return 0

    rel_path = write_new_trade_journal(
        position_id=str(row["id"]),
        spread_data=_spread_from_row(row),
        validation_data={"checks": [], "verdict": "not recorded"},
        current_spot=float(row.get("spot_at_entry") or 0.0),
        margin_base_inr=0.0,
        filename_override=target_name,
        notice=REBUILD_NOTICE,
    )

    print(f"wrote {rel_path}")

    try:
        db.client.table("swayam_positions").update(
            {"journal_path": rel_path, "journal_status": "written"}
        ).eq("id", row["id"]).execute()
        print("linked it to the position row")
    except Exception as exc:  # noqa: BLE001
        print(f"could not link it to the position row: {exc}")

    try:
        existing = (
            db.client.table("swayam_journal_entries")
            .select("id")
            .eq("position_id", row["id"])
            .eq("entry_type", "entry")
            .execute()
        )
        if not (existing.data or []):
            db.client.table("swayam_journal_entries").insert(
                {
                    "position_id": str(row["id"]),
                    "entry_date": str(row.get("opened_at", ""))[:10] or None,
                    "entry_type": "entry",
                    "md_path": rel_path,
                    "created_at": row.get("opened_at"),
                }
            ).execute()
            print("indexed it in swayam_journal_entries")
    except Exception as exc:  # noqa: BLE001
        print(f"could not index it: {exc}")

    print()
    print("The Greeks and the rule checks are NOT in this note. They were never")
    print("stored on the position row, so they are absent rather than guessed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except JournalWriteError as exc:
        print(f"Refused: {exc}")
        raise SystemExit(1) from exc
