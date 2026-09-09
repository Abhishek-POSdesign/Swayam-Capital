"""
Writes queued journal notes into the Obsidian vault.

WHY THIS EXISTS
---------------
A trade recorded on the live site cannot write its note to the vault. Cloud Run
is a Linux container in Singapore and `G:\\My Drive\\Second Brain` is a drive
letter that Google Drive for Desktop paints onto Abhishek's own PC. There is no
route from one to the other, and there never will be by that path.

So the note is queued in `swayam_journal_outbox` and the trade succeeds. This
script is what completes it. Run it on a machine where the vault IS reachable,
which today means his PC, and every pending note is written into Obsidian and
indexed.

Once the Drive API path is built, a second drainer will do the same job from
the cloud and this one becomes the fallback. The queue is the architecture;
where it drains from is a detail.

USAGE
-----
    .\\.venv\\Scripts\\python.exe scripts\\drain_journal_outbox.py status
    .\\.venv\\Scripts\\python.exe scripts\\drain_journal_outbox.py drain
    .\\.venv\\Scripts\\python.exe scripts\\drain_journal_outbox.py drain --dry-run

`status` never writes anything. `drain` writes only into the vault and marks
rows done; it never alters a position's own numbers.
"""

from __future__ import annotations

from typing import Optional

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT_DIR / ".env")

from swayam.api.journal_writer import (
    append_leg_block,  # noqa: E402
    append_exit_block,
    write_new_trade_journal,
)
from swayam.config import settings  # noqa: E402
from swayam.db import db  # noqa: E402

OUTBOX = "swayam_journal_outbox"
MAX_ATTEMPTS = 5


def _vault_is_reachable() -> tuple[bool, str]:
    """A drainer that cannot see the vault must say so, not fail row by row."""
    vault = Path(settings.vault_path)
    if not vault.exists():
        return False, f"vault path does not exist here: {vault}"
    if not vault.is_dir():
        return False, f"vault path is not a directory: {vault}"
    return True, str(vault)


def _pending() -> list[dict]:
    res = (
        db.client.table(OUTBOX)
        .select("*")
        .eq("status", "pending")
        .order("created_at")
        .execute()
    )
    return res.data or []


def cmd_status() -> int:
    ok, detail = _vault_is_reachable()
    print(f"vault    : {detail}")
    print(f"reachable: {'yes' if ok else 'NO'}")

    rows = _pending()
    print(f"pending  : {len(rows)}")
    for row in rows[:20]:
        print(
            f"  {row['created_at'][:19]}  {row['kind']:<10} "
            f"position {str(row['position_id'])[:8]}  attempts={row['attempts']}"
        )
    if len(rows) > 20:
        print(f"  ... and {len(rows) - 20} more")

    failed = (
        db.client.table(OUTBOX).select("id").eq("status", "failed").execute().data or []
    )
    if failed:
        print(f"failed   : {len(failed)}  (gave up after {MAX_ATTEMPTS} attempts)")
    return 0


def cmd_drain(dry_run: bool) -> int:
    ok, detail = _vault_is_reachable()
    if not ok:
        print(f"Refusing to drain: {detail}")
        print("Run this on the machine where the vault lives. Nothing was changed.")
        return 1

    rows = _pending()
    if not rows:
        print("Nothing pending. Every journal note is in the vault.")
        return 0

    print(f"vault  : {detail}")
    print(f"pending: {len(rows)}")
    if dry_run:
        print("\nDry run. Nothing will be written.")

    written = 0
    skipped = 0
    for row in rows:
        pid = str(row["position_id"])
        payload = row.get("payload") or {}
        label = f"{row['kind']} for position {pid[:8]}"

        # An index-only row means the markdown already exists on disk and only
        # its row in swayam_journal_entries is missing.
        if payload.get("index_only"):
            if dry_run:
                print(f"  would index  {label}")
                skipped += 1
                continue
            try:
                db.client.table("swayam_journal_entries").insert(
                    {
                        "position_id": pid,
                        "entry_date": payload.get("entry_date"),
                        "entry_type": "entry",
                        "md_path": payload.get("md_path"),
                        "created_at": payload.get("opened_at"),
                    }
                ).execute()
                _mark_done(row["id"], payload.get("md_path"))
                _mark_position(pid, "written")
                print(f"  indexed      {label}")
                written += 1
            except Exception as exc:
                _mark_attempt(row, str(exc))
                print(f"  FAILED       {label}: {exc}")
            continue

        # A CLOSE note appends the exit block to a note that already exists,
        # rather than writing a new one. Queued since 2026-09-09, when the exit
        # side finally stopped returning an error on a trade that had already
        # been recorded. Without this branch such a row would sit in the outbox
        # for ever and his note would never get its result.
        # A LEG ADDED to an open trade. The note's path is resolved now rather
        # than at queue time, because the entry note may have been sitting in
        # this same queue ahead of it.
        if row["kind"] == "add_leg":
            if dry_run:
                print(f"  would append {label}")
                skipped += 1
                continue
            try:
                note_path = _resolve_note_path(pid)
                if not note_path:
                    raise RuntimeError("the entry note has not been written yet; run again after it lands")
                target = append_leg_block(
                    journal_rel_path=note_path,
                    added_at=payload["added_at"],
                    leg=payload["leg"],
                    structure_after=payload.get("structure_after") or {},
                )
                _mark_done(row["id"], note_path)
                _mark_position(pid, "written")
                print(f"  appended     {target}")
                written += 1
            except Exception as exc:
                _mark_attempt(row, str(exc))
                print(f"  FAILED       {label}: {exc}")
            continue

        if row["kind"] == "close":
            if dry_run:
                print(f"  would append {label}")
                skipped += 1
                continue
            try:
                from datetime import datetime

                target = append_exit_block(
                    journal_rel_path=payload["journal_rel_path"],
                    closed_at=datetime.fromisoformat(payload["closed_at"]),
                    close_reason=payload["close_reason"],
                    notes=payload.get("notes"),
                    exit_legs=payload["exit_legs"],
                    gross_pnl_inr=payload["gross_pnl_inr"],
                    charges_inr=payload["charges_inr"],
                    net_pnl_inr=payload["net_pnl_inr"],
                    max_loss_inr=payload["max_loss_inr"],
                    margin_base_inr=payload["margin_base_inr"],
                    holding_days=payload["holding_days"],
                )
                _mark_done(row["id"], payload["journal_rel_path"])
                _mark_position(pid, "written")
                print(f"  appended     {target}")
                written += 1
            except Exception as exc:
                _mark_attempt(row, str(exc))
                print(f"  FAILED       {label}: {exc}")
            continue

        if dry_run:
            print(f"  would write  {label}")
            skipped += 1
            continue

        try:
            rel_path = write_new_trade_journal(
                position_id=pid,
                spread_data=payload["spread_data"],
                validation_data=payload["validation_data"],
                current_spot=payload["current_spot"],
                margin_base_inr=payload["margin_base_inr"],
                # The trade's own opening time. Without it the note stamped the
                # moment the drainer ran, which for trades 02 and 03 of
                # 2026-09-09 was 16:57, after the close.
                opened_at=payload.get("opened_at"),
            )
            db.client.table("swayam_journal_entries").insert(
                {
                    "position_id": pid,
                    "entry_date": str(payload.get("opened_at", ""))[:10] or None,
                    "entry_type": "entry",
                    "md_path": rel_path,
                    "created_at": payload.get("opened_at"),
                }
            ).execute()
            _mark_done(row["id"], rel_path)
            _mark_position(pid, "written")
            print(f"  wrote        {rel_path}")
            written += 1

            # If the trade is ALREADY CLOSED, finish the note now rather than
            # leaving it saying "Exit: to be filled at close" for ever. Two of
            # his trades on 2026-09-09 were opened on the live site, queued
            # here, and closed before this ever ran.
            _append_exit_if_already_closed(pid, rel_path)
        except Exception as exc:
            _mark_attempt(row, str(exc))
            print(f"  FAILED       {label}: {exc}")

    print()
    if dry_run:
        print(f"Dry run. {skipped} note(s) would be written. Nothing was changed.")
    else:
        print(f"{written} note(s) written into the vault.")
        if written:
            print("Google Drive will sync them, and they will appear in Obsidian.")
    return 0


def _mark_done(row_id: str, md_path: str | None) -> None:
    db.client.table(OUTBOX).update(
        {
            "status": "done",
            "drained_at": datetime.now(timezone.utc).isoformat(),
            "md_path": md_path,
        }
    ).eq("id", row_id).execute()


def _mark_attempt(row: dict, error: str) -> None:
    attempts = int(row.get("attempts") or 0) + 1
    update = {"attempts": attempts, "last_error": error[:2000]}
    if attempts >= MAX_ATTEMPTS:
        update["status"] = "failed"
        _mark_position(str(row["position_id"]), "failed")
    db.client.table(OUTBOX).update(update).eq("id", row["id"]).execute()


def _mark_position(position_id: str, status: str) -> None:
    db.client.table("swayam_positions").update({"journal_status": status}).eq(
        "id", position_id
    ).execute()


def _resolve_note_path(position_id: str) -> Optional[str]:
    """The trade's note, from the row or the journal index. None if neither has it."""
    try:
        rows = (
            db.client.table("swayam_positions").select("journal_path").eq("id", position_id).execute().data
            or []
        )
        if rows and rows[0].get("journal_path"):
            return rows[0]["journal_path"]
        entries = (
            db.client.table("swayam_journal_entries")
            .select("md_path")
            .eq("position_id", position_id)
            .eq("entry_type", "entry")
            .limit(1)
            .execute()
            .data
            or []
        )
        if entries and entries[0].get("md_path"):
            return entries[0]["md_path"]
    except Exception as exc:
        print(f"  could not resolve the note for {position_id[:8]}: {exc}")
    return None


def _append_exit_if_already_closed(position_id: str, rel_path: str) -> None:
    """Completes a note for a trade that closed before its entry note landed.

    Everything needed is already recorded: the result and the per-leg breakdown
    live in swayam_trade_history, the risk lives on the position. Nothing here
    is invented; a figure that cannot be read stops the append rather than
    guessing at it.
    """
    try:
        pos_rows = (
            db.client.table("swayam_positions").select("*").eq("id", position_id).execute().data
            or []
        )
        if not pos_rows or pos_rows[0].get("status") != "closed":
            return
        pos = pos_rows[0]

        hist_rows = (
            db.client.table("swayam_trade_history")
            .select("*")
            .eq("position_id", position_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not hist_rows:
            print(f"  NO EXIT      {position_id[:8]}: closed, but no result row to append")
            return
        hist = hist_rows[0]

        from swayam.services import capital as capital_service

        margin_base = capital_service.get_capital().risk_capital_inr

        gross = float(hist.get("realized_pnl_inr") or 0.0) + float(hist.get("total_charges_inr") or 0.0)
        append_exit_block(
            journal_rel_path=rel_path,
            closed_at=datetime.fromisoformat(str(hist["closed_at"]).replace("Z", "+00:00")),
            close_reason=hist.get("close_reason") or "manual",
            notes=pos.get("exit_rationale"),
            exit_legs=hist.get("exit_legs") or [],
            gross_pnl_inr=gross,
            charges_inr=float(hist.get("total_charges_inr") or 0.0),
            net_pnl_inr=float(hist.get("realized_pnl_inr") or 0.0),
            max_loss_inr=float(pos.get("max_loss_inr") or 0.0),
            margin_base_inr=margin_base,
            holding_days=int(hist.get("holding_days") or 0),
        )
        print(f"  completed    {rel_path} with its exit")
    except Exception as exc:  # noqa: BLE001
        print(f"  NO EXIT      {position_id[:8]}: could not append the exit: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="show what is queued; writes nothing")
    drain = sub.add_parser("drain", help="write every pending note into the vault")
    drain.add_argument("--dry-run", action="store_true", help="show what would be written")

    args = parser.parse_args()
    if args.command == "status":
        return cmd_status()
    return cmd_drain(args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
