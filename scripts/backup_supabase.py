r"""
Full logical backup of every swayam_* table in Supabase.

Writes, under data/backups/<UTC timestamp>/:
  - <table>.json         one file per table, rows sorted for a stable checksum
  - schema.sql           the DDL captured at baseline (copied from migrations/000_baseline.sql)
  - MANIFEST.json        row count + SHA-256 for every file, plus totals

Optionally uploads the whole folder to Google Cloud Storage so a copy exists
outside Supabase.

A failed upload fails the job. A table that cannot be read fails the job.
There is no "best effort" here on purpose: a backup that reports success
without writing bytes is worse than no backup.

Usage:
    .\.venv\Scripts\python.exe scripts/backup_supabase.py
    .\.venv\Scripts\python.exe scripts/backup_supabase.py --gcs
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from swayam.db import SupabaseDB  # noqa: E402

# Every swayam_* table, captured from the live database on 2026-09-07.
# Kept explicit rather than discovered so a missing table is a loud failure,
# not a silently smaller backup.
TABLES: tuple[str, ...] = (
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
    "swayam_positions",
    "swayam_readiness_log",
    "swayam_rule_evolution_log",
    "swayam_trade_history",
)

# Column to sort each table by so two backups of identical data checksum alike.
SORT_KEY: dict[str, str] = {
    "swayam_ai_usage_daily": "day",
    "swayam_bhavcopy": "date",
    "swayam_config": "key",
    "swayam_macro_events": "event_key",
    "swayam_nifty_daily_bars": "trade_date",
    "swayam_readiness_log": "log_date",
}

PAGE = 1000


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch_all(client, table: str) -> list[dict]:
    """Reads every row of a table, paging so a large table is not truncated."""
    rows: list[dict] = []
    offset = 0
    while True:
        res = client.table(table).select("*").range(offset, offset + PAGE - 1).execute()
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < PAGE:
            break
        offset += PAGE
    key = SORT_KEY.get(table, "id")
    if rows and key in rows[0]:
        rows.sort(key=lambda r: str(r.get(key)))
    return rows


def _upload_to_gcs(folder: Path, bucket: str, expected_files: int) -> None:
    """Copies the backup folder to GCS and proves the objects arrived.

    A non-zero exit code is a failure, and so is a short object count. The
    old backup service reported success on a failed upload; that is the
    exact bug this function exists to not repeat.
    """
    import subprocess

    dest = f"gs://{bucket}/supabase/"
    proc = subprocess.run(
        ["gcloud", "storage", "cp", "--recursive", str(folder), dest],
        capture_output=True,
        text=True,
        shell=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"GCS upload failed: {proc.stderr.strip()}")

    listing = subprocess.run(
        ["gcloud", "storage", "ls", f"{dest}{folder.name}/"],
        capture_output=True,
        text=True,
        shell=True,
    )
    landed = [ln for ln in listing.stdout.splitlines() if ln.strip().endswith((".json", ".sql"))]
    if len(landed) != expected_files:
        raise RuntimeError(
            f"GCS upload incomplete: expected {expected_files} objects, found {len(landed)}"
        )
    print(f"[ok] uploaded and verified {len(landed)} objects to {dest}{folder.name}/")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gcs", action="store_true", help="also upload to Cloud Storage")
    parser.add_argument("--bucket", default="swayam-backups")
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out = ROOT_DIR / "data" / "backups" / stamp
    out.mkdir(parents=True, exist_ok=True)

    client = SupabaseDB().client
    manifest: dict = {
        "taken_at_utc": datetime.now(timezone.utc).isoformat(),
        "project": "wxijlrwoiaeaupaaqecc",
        "scope": "all swayam_* tables (other apps in this project are deliberately excluded)",
        "tables": {},
    }

    total_rows = 0
    for table in TABLES:
        rows = _fetch_all(client, table)
        path = out / f"{table}.json"
        path.write_text(
            json.dumps(rows, indent=2, ensure_ascii=False, sort_keys=True, default=str),
            encoding="utf-8",
        )
        manifest["tables"][table] = {
            "rows": len(rows),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        total_rows += len(rows)
        print(f"[ok] {table:<32} {len(rows):>6} rows")

    baseline = ROOT_DIR / "migrations" / "000_baseline.sql"
    if baseline.exists():
        copy = out / "schema.sql"
        copy.write_text(baseline.read_text(encoding="utf-8"), encoding="utf-8")
        manifest["schema_sql_sha256"] = _sha256(copy)
    else:
        raise RuntimeError("migrations/000_baseline.sql is missing; refusing to write a schema-less backup")

    manifest["total_rows"] = total_rows
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\n[ok] {len(TABLES)} tables, {total_rows} rows -> {out}")

    if args.gcs:
        # 19 table files + schema.sql + MANIFEST.json
        _upload_to_gcs(out, args.bucket, expected_files=len(TABLES) + 2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
