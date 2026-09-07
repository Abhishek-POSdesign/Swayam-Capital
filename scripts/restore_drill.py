r"""
Proves that a Swayam backup can actually be restored.

The old restore_from_backup.py counted INSERT lines, checked connectivity and
returned success. It never restored anything, so recovery had never once been
demonstrated. This script rebuilds the schema from the backup, reloads every
row, and compares what landed against the manifest, row count and content.

The drill rebuilds into an isolated schema (swayam_restore_drill) inside the
same database, then drops it. That keeps it away from the live tables and from
the Biz Research Hub and Learning Hub tables that share this project.

What this proves: the backup artifact is complete, the schema in it is valid
DDL, and every row reloads with identical content.

What it does NOT prove: recovery if the entire Supabase project were lost.
That needs a second project, which this account's two-project free tier does
not allow. Stated here rather than glossed over.

Usage:
    .\.venv\Scripts\python.exe scripts/restore_drill.py run
    .\.venv\Scripts\python.exe scripts/restore_drill.py run --keep
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT_DIR / ".env")

from swayam.db_direct import connect, describe_target  # noqa: E402

BACKUP_ROOT = ROOT_DIR / "data" / "backups"
DRILL_SCHEMA = "swayam_restore_drill"

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


def _normalise(value: object) -> object:
    """Flattens types so a reloaded row compares equal to the backed-up one."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (list, tuple)):
        return [_normalise(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in value.items()}
    return value


def _content_hash(rows: list[dict]) -> str:
    """Order-independent, key-order-independent digest of a table's contents."""
    digests = sorted(
        hashlib.sha256(
            json.dumps(_normalise(r), sort_keys=True, ensure_ascii=False, default=str).encode()
        ).hexdigest()
        for r in rows
    )
    return hashlib.sha256("".join(digests).encode()).hexdigest()


def _drill_ddl(backup: Path) -> str:
    ddl = (backup / "schema.sql").read_text(encoding="utf-8")
    ddl = ddl.replace("public.", f"{DRILL_SCHEMA}.")
    ddl = ddl.replace("nextval('swayam_", f"nextval('{DRILL_SCHEMA}.swayam_")
    return ddl


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run",))
    parser.add_argument("--backup", default=None, help="backup folder (default: newest)")
    parser.add_argument("--keep", action="store_true", help="leave the drill schema behind")
    args = parser.parse_args()

    backup = Path(args.backup) if args.backup else _latest_backup()
    manifest = json.loads((backup / "MANIFEST.json").read_text(encoding="utf-8"))

    print(f"backup   : {backup.name}")
    print(f"database : {describe_target()}")
    print(f"schema   : {DRILL_SCHEMA}\n")

    with connect() as conn:
        with conn.cursor() as cur:
            # 1. rebuild the schema from the backup's own DDL
            cur.execute(f"DROP SCHEMA IF EXISTS {DRILL_SCHEMA} CASCADE")
            cur.execute(f"CREATE SCHEMA {DRILL_SCHEMA}")
            cur.execute(_drill_ddl(backup))
            cur.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema = %s",
                (DRILL_SCHEMA,),
            )
            print(f"[ok] schema rebuilt from backup: {cur.fetchone()[0]} tables\n")

            # Read the real column types rather than guessing which are JSON.
            # A jsonb column that is NOT NULL can legitimately hold the JSON
            # value null, which is not the same thing as a SQL NULL. Guessing
            # that distinction is how the first attempt at this failed, on
            # swayam_config.current_reentry_ramp_tier.
            cur.execute(
                "SELECT table_name, column_name, data_type, is_nullable "
                "FROM information_schema.columns WHERE table_schema = %s",
                (DRILL_SCHEMA,),
            )
            coltype = {
                (t, c): (dt, nullable == "YES") for t, c, dt, nullable in cur.fetchall()
            }

            # 2. reload every row
            loaded = 0
            for table in LOAD_ORDER:
                rows = _rows(backup, table)
                if not rows:
                    continue
                cols = list(rows[0].keys())
                is_json = {c: coltype[(table, c)][0] in ("jsonb", "json") for c in cols}
                nullable = {c: coltype[(table, c)][1] for c in cols}

                placeholders = ", ".join("%s::jsonb" if is_json[c] else "%s" for c in cols)
                stmt = (
                    f'INSERT INTO {DRILL_SCHEMA}."{table}" '
                    f'({", ".join(chr(34) + c + chr(34) for c in cols)}) VALUES ({placeholders})'
                )

                def render(col: str, value: object, _j=is_json, _n=nullable) -> object:
                    if not _j[col]:
                        return value
                    if value is None and _n[col]:
                        return None
                    return json.dumps(value)

                payload = [tuple(render(c, r[c]) for c in cols) for r in rows]
                cur.executemany(stmt, payload)
                loaded += len(rows)
            print(f"[ok] {loaded} rows reloaded\n")

            # 3. verify, row count and content
            print(f"{'table':<34}{'expected':>9}{'restored':>10}   rows  content")
            print("-" * 72)
            all_ok = True
            for table in LOAD_ORDER:
                expected = _rows(backup, table)
                cur.execute(
                    f'SELECT row_to_json(t) FROM {DRILL_SCHEMA}."{table}" t'
                )
                restored = [r[0] for r in cur.fetchall()]

                rows_ok = len(restored) == manifest["tables"][table]["rows"] == len(expected)
                content_ok = _content_hash(restored) == _content_hash(expected)
                all_ok = all_ok and rows_ok and content_ok
                print(
                    f"{table:<34}{len(expected):>9}{len(restored):>10}"
                    f"   {'PASS' if rows_ok else 'FAIL'}  {'PASS' if content_ok else 'FAIL'}"
                )

            print("-" * 72)
            print(f"total rows: {manifest['total_rows']}")
            print("RESTORE DRILL:", "PASSED" if all_ok else "FAILED")

            if not args.keep:
                cur.execute(f"DROP SCHEMA IF EXISTS {DRILL_SCHEMA} CASCADE")
                print(f"[ok] drill schema dropped")

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
