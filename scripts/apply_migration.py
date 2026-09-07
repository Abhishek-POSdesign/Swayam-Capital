r"""
The migration runner. It actually runs migrations.

What this replaces: a script whose own docstring claimed it executed numbered
SQL migrations, but which read the file, printed its line count, and told you
to paste it into the Supabase web editor. It executed nothing. There was no
version table, so nobody could say which migrations were applied, and the
files on disk are numbered with gaps, which made that worse.

How this one behaves:

  * Every migration runs inside ONE transaction. A failure rolls the whole
    file back. There is no half-applied state.
  * Every applied migration is recorded in swayam_schema_migrations with a
    SHA-256 of the exact text that ran.
  * If a file on disk no longer matches the checksum recorded when it was
    applied, the runner STOPS. Editing an applied migration is how a schema
    silently diverges from its own history.
  * Migrations are applied in numeric order, and only ones not yet recorded.
  * Nothing outside the swayam_ namespace is touched. This database is shared
    with the Biz Research Hub and the B.tech Learning Hub.

Usage:
    .\.venv\Scripts\python.exe scripts/apply_migration.py status
    .\.venv\Scripts\python.exe scripts/apply_migration.py up --dry-run
    .\.venv\Scripts\python.exe scripts/apply_migration.py up
    .\.venv\Scripts\python.exe scripts/apply_migration.py baseline
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import re
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT_DIR / ".env")

from swayam.db_direct import connect, describe_target  # noqa: E402

MIGRATIONS_DIR = ROOT_DIR / "migrations"

VERSION_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS public.swayam_schema_migrations (
  version      text PRIMARY KEY,
  filename     text NOT NULL,
  checksum     text NOT NULL,
  applied_at   timestamp with time zone NOT NULL DEFAULT now(),
  applied_by   text NOT NULL,
  duration_ms  integer NOT NULL,
  notes        text
);
COMMENT ON TABLE public.swayam_schema_migrations IS
  'Which migrations have actually run against this database. Created 2026-09-08; before that, no such record existed.';
"""

# The ten files that were applied by hand before the runner existed,
# reconciled against the live schema on 2026-09-08 and written up in
# migrations/000_baseline.sql.
PRE_EXISTING = (
    "001_initial_schema.sql",
    "002_ai_conversations_and_rule_log.sql",
    "004_readiness_meditation_nullable.sql",
    "005_ai_memory_system.sql",
    "006_swayam_lessons_and_journal_fields.sql",
    "007_allow_archived_status.sql",
    "013_ai_chat_attachments.sql",
    "014_home_snapshot_cache.sql",
    "015_macro_events.sql",
    "016_notification_devices.sql",
)


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _version_of(filename: str) -> str:
    m = re.match(r"^(\d+)_", filename)
    if not m:
        raise SystemExit(f"Migration {filename} does not start with a number")
    return m.group(1)


def _migration_files() -> list[Path]:
    files = [p for p in MIGRATIONS_DIR.glob("*.sql") if re.match(r"^\d+_", p.name)]
    return sorted(files, key=lambda p: (_version_of(p.name), p.name))


def _ensure_version_table(cur) -> None:
    cur.execute(VERSION_TABLE_DDL)


def _applied(cur) -> dict[str, dict]:
    cur.execute(
        "SELECT version, filename, checksum, applied_at FROM public.swayam_schema_migrations"
    )
    return {
        row[0]: {"filename": row[1], "checksum": row[2], "applied_at": row[3]}
        for row in cur.fetchall()
    }


def _drift(files: list[Path], applied: dict[str, dict]) -> list[str]:
    problems = []
    for path in files:
        record = applied.get(_version_of(path.name))
        if not record:
            continue
        if _checksum(path.read_text(encoding="utf-8")) != record["checksum"]:
            problems.append(
                f"{path.name} has changed since it was applied on "
                f"{record['applied_at']:%Y-%m-%d %H:%M}. An applied migration is "
                f"history and must not be edited. Write a new migration instead."
            )
    return problems


def cmd_status() -> int:
    files = _migration_files()
    with connect() as conn:
        with conn.cursor() as cur:
            _ensure_version_table(cur)
            applied = _applied(cur)

    print(f"database : {describe_target()}")
    print(f"folder   : {MIGRATIONS_DIR}\n")
    print(f"{'version':<9}{'file':<50}{'state':<10}applied")
    print("-" * 94)
    for path in files:
        version = _version_of(path.name)
        record = applied.get(version)
        if record is None:
            print(f"{version:<9}{path.name:<50}{'PENDING':<10}")
        else:
            changed = _checksum(path.read_text(encoding="utf-8")) != record["checksum"]
            state = "CHANGED" if changed else "applied"
            print(f"{version:<9}{path.name:<50}{state:<10}{record['applied_at']:%Y-%m-%d %H:%M}")

    for version in sorted(set(applied) - {_version_of(p.name) for p in files}):
        print(f"{version:<9}{applied[version]['filename']:<50}{'NO FILE':<10}")

    problems = _drift(files, applied)
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print(f"  - {p}")
        return 1

    pending = [p for p in files if _version_of(p.name) not in applied]
    print(f"\n{len(applied)} applied, {len(pending)} pending")
    return 0


def cmd_baseline() -> int:
    """Records the already-applied migrations without running them."""
    files = {p.name: p for p in _migration_files()}
    recorded = 0
    with connect() as conn:
        with conn.cursor() as cur:
            _ensure_version_table(cur)
            applied = _applied(cur)
            for name in ("000_baseline.sql",) + PRE_EXISTING:
                path = files.get(name)
                if path is None:
                    print(f"[!!] {name} is missing from {MIGRATIONS_DIR}")
                    return 1
                version = _version_of(name)
                if version in applied:
                    print(f"[--] {version} {name} already recorded")
                    continue
                cur.execute(
                    "INSERT INTO public.swayam_schema_migrations "
                    "(version, filename, checksum, applied_by, duration_ms, notes) "
                    "VALUES (%s, %s, %s, %s, 0, %s)",
                    (
                        version,
                        name,
                        _checksum(path.read_text(encoding="utf-8")),
                        getpass.getuser(),
                        "Recorded as already applied when the runner was built on "
                        "2026-09-08. Reconciled against the live schema, not executed.",
                    ),
                )
                recorded += 1
                print(f"[ok] {version} {name} recorded as already applied")
    print(f"\n{recorded} migration(s) recorded. Nothing was executed.")
    return 0


def cmd_up(dry_run: bool) -> int:
    files = _migration_files()
    with connect() as conn:
        with conn.cursor() as cur:
            _ensure_version_table(cur)
            applied = _applied(cur)

        problems = _drift(files, applied)
        if problems:
            print("REFUSING TO RUN. Applied migrations have been edited:")
            for p in problems:
                print(f"  - {p}")
            return 1

        pending = [p for p in files if _version_of(p.name) not in applied]
        if not pending:
            print("Nothing to apply. The database is up to date.")
            return 0

        print(f"database : {describe_target()}")
        print(f"pending  : {', '.join(p.name for p in pending)}\n")
        if dry_run:
            print("Dry run. Nothing was executed.")
            return 0

        for path in pending:
            version = _version_of(path.name)
            sql = path.read_text(encoding="utf-8")
            started = time.perf_counter()
            # One transaction per migration; psycopg rolls back on exception.
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(sql)
                    elapsed = int((time.perf_counter() - started) * 1000)
                    cur.execute(
                        "INSERT INTO public.swayam_schema_migrations "
                        "(version, filename, checksum, applied_by, duration_ms) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (version, path.name, _checksum(sql), getpass.getuser(), elapsed),
                    )
            print(f"[ok] {version} {path.name}  ({elapsed} ms)")

    print(f"\n{len(pending)} migration(s) applied.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Swayam database migrations.")
    parser.add_argument("command", choices=("status", "up", "baseline"))
    parser.add_argument("--dry-run", action="store_true", help="list pending, execute nothing")
    args = parser.parse_args()

    if args.command == "status":
        return cmd_status()
    if args.command == "baseline":
        return cmd_baseline()
    return cmd_up(args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
