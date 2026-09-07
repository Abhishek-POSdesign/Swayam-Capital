r"""
Proves that a Swayam backup can actually be restored.

The old restore_from_backup.py counted INSERT lines, checked connectivity and
returned success. It never restored anything. This one rebuilds the schema and
reloads every row, then compares what landed against the backup manifest.

The drill rebuilds into prefixed tables (drill_swayam_*) inside the same
database. That is isolated from the live tables and from the Biz Research Hub
and Learning Hub tables that share this project, and it is dropped when the
drill finishes. It proves the backup artifact is complete and loadable. It does
NOT prove recovery if the whole Supabase project were lost; that needs a second
project, which this account's free tier does not allow.

Usage:
    # 1. generate the schema SQL, then apply 01_schema.sql to the database
    .\.venv\Scripts\python.exe scripts/restore_drill.py generate

    # 2. reload every row from the backup into the drill tables
    .\.venv\Scripts\python.exe scripts/restore_drill.py load

    # 3. compare row counts and per-table checksums against the manifest
    .\.venv\Scripts\python.exe scripts/restore_drill.py verify

    # 4. print the DROP statements to clean up
    .\.venv\Scripts\python.exe scripts/restore_drill.py teardown
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

BACKUP_ROOT = ROOT_DIR / "data" / "backups"
PREFIX = "drill_"

# Parents before children so the foreign keys hold on reload.
LOAD_ORDER = (
    "swayam_positions",
    "swayam_ai_conversations",
    "swayam_ai_messages",
    "swayam_ai_notebook",
    "swayam_ai_pinned_decisions",
    "swayam_ai_session_summaries",
    "swayam_ai_usage_daily",
    "swayam_backtest_runs",
    "swayam_bhavcopy",
    "swayam_config",
    "swayam_home_snapshot",
    "swayam_journal_entries",
    "swayam_lessons",
    "swayam_macro_events",
    "swayam_nifty_daily_bars",
    "swayam_notification_devices",
    "swayam_readiness_log",
    "swayam_rule_evolution_log",
    "swayam_trade_history",
)


def _latest_backup() -> Path:
    candidates = sorted(
        p for p in BACKUP_ROOT.iterdir() if p.is_dir() and (p / "MANIFEST.json").exists()
    )
    if not candidates:
        raise SystemExit(f"No backups found under {BACKUP_ROOT}")
    return candidates[-1]


def _rows(backup: Path, table: str) -> list[dict]:
    return json.loads((backup / f"{table}.json").read_text(encoding="utf-8"))


def _content_hash(rows: list[dict]) -> str:
    """Order-independent, key-order-independent digest of a table's contents."""
    digests = sorted(
        hashlib.sha256(
            json.dumps(r, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        ).hexdigest()
        for r in rows
    )
    return hashlib.sha256("".join(digests).encode("utf-8")).hexdigest()


def cmd_generate(backup: Path) -> int:
    """Writes the DDL that recreates every table under the drill prefix."""
    ddl = (backup / "schema.sql").read_text(encoding="utf-8")
    ddl = ddl.replace("public.swayam_", f"public.{PREFIX}swayam_")
    ddl = ddl.replace("nextval('swayam_", f"nextval('{PREFIX}swayam_")
    ddl = ddl.replace("CONSTRAINT swayam_", f"CONSTRAINT {PREFIX}swayam_")
    ddl = ddl.replace("INDEX idx_", f"INDEX {PREFIX}idx_")
    ddl = ddl.replace("INDEX IF NOT EXISTS idx_", f"INDEX IF NOT EXISTS {PREFIX}idx_")

    out_dir = backup / "restore"
    out_dir.mkdir(exist_ok=True)
    header = (
        f"-- Restore drill schema, generated from backup {backup.name}\n"
        f"-- Tables are created as public.{PREFIX}swayam_* so they cannot collide\n"
        f"-- with the live tables or with the other apps in this project.\n\n"
    )
    (out_dir / "01_schema.sql").write_text(header + ddl, encoding="utf-8")
    print(f"[ok] wrote {out_dir / '01_schema.sql'}")
    print("     apply that file to the database, then run: restore_drill.py load")
    return 0


def cmd_load(backup: Path) -> int:
    """Reloads every backed-up row into the drill tables."""
    from swayam.db import SupabaseDB

    client = SupabaseDB().client
    total = 0
    for table in LOAD_ORDER:
        rows = _rows(backup, table)
        if not rows:
            print(f"[--] {PREFIX}{table:<32} empty")
            continue
        for start in range(0, len(rows), 200):
            client.table(f"{PREFIX}{table}").insert(rows[start : start + 200]).execute()
        total += len(rows)
        print(f"[ok] {PREFIX}{table:<32} {len(rows):>6} rows loaded")
    print(f"\n[ok] {total} rows reloaded from {backup.name}")
    return 0


def cmd_verify(backup: Path) -> int:
    """Compares the restored tables against the backup, row count and content."""
    from swayam.db import SupabaseDB

    client = SupabaseDB().client
    manifest = json.loads((backup / "MANIFEST.json").read_text(encoding="utf-8"))

    print(f"{'table':<34}{'expected':>9}{'restored':>10}  rows  content")
    print("-" * 72)
    all_ok = True
    for table in LOAD_ORDER:
        expected_rows = _rows(backup, table)
        restored: list[dict] = []
        offset = 0
        while True:
            res = (
                client.table(f"{PREFIX}{table}")
                .select("*")
                .range(offset, offset + 999)
                .execute()
            )
            batch = res.data or []
            restored.extend(batch)
            if len(batch) < 1000:
                break
            offset += 1000

        rows_ok = len(restored) == manifest["tables"][table]["rows"] == len(expected_rows)
        content_ok = _content_hash(restored) == _content_hash(expected_rows)
        all_ok = all_ok and rows_ok and content_ok
        print(
            f"{table:<34}{len(expected_rows):>9}{len(restored):>10}"
            f"  {'PASS' if rows_ok else 'FAIL'}  {'PASS' if content_ok else 'FAIL'}"
        )

    print("-" * 72)
    print("RESTORE DRILL:", "PASSED" if all_ok else "FAILED")
    return 0 if all_ok else 1


def cmd_teardown(backup: Path) -> int:
    stmts = "\n".join(f"DROP TABLE IF EXISTS public.{PREFIX}{t} CASCADE;" for t in LOAD_ORDER)
    seqs = "\n".join(
        f"DROP SEQUENCE IF EXISTS public.{PREFIX}{s} CASCADE;"
        for s in (
            "swayam_ai_notebook_id_seq",
            "swayam_ai_pinned_decisions_id_seq",
            "swayam_ai_session_summaries_id_seq",
        )
    )
    path = backup / "restore" / "99_teardown.sql"
    path.write_text(stmts + "\n" + seqs + "\n", encoding="utf-8")
    print(f"[ok] wrote {path}")
    print(stmts)
    print(seqs)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "load", "verify", "teardown"))
    parser.add_argument("--backup", default=None, help="backup folder (default: newest)")
    args = parser.parse_args()

    backup = Path(args.backup) if args.backup else _latest_backup()
    print(f"backup: {backup.name}\n")

    return {
        "generate": cmd_generate,
        "load": cmd_load,
        "verify": cmd_verify,
        "teardown": cmd_teardown,
    }[args.command](backup)


if __name__ == "__main__":
    raise SystemExit(main())
