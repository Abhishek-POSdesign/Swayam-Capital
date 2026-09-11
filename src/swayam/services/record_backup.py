r"""Full logical backup of every swayam_* table, runnable anywhere.

WHY THIS MODULE EXISTS, AND WHAT IT IS NOT
------------------------------------------
`scripts/backup_supabase.py` proved this backup works: its restore drill passed
on 19 tables and 600 rows. But it could only ever run on his PC, for two
reasons: it shells out to the `gcloud` command line, which is not in the Cloud
Run image, and it reads `migrations/000_baseline.sql`, which was not copied
into that image either.

His record must be backed up whether his PC is awake or not. So the logic moved
here, into `src/`, which IS in the image, and the upload now uses the
`google-cloud-storage` client that was already a dependency. The script keeps
working exactly as before; it is now a thin wrapper around this module.

**This is deliberately NOT `backup_service.py`.** That module, which
`functions/cron_backup_db` calls and which was never deployed, silently records
a table it cannot read as an EMPTY table and carries on. A Supabase hiccup on
`swayam_positions` would produce a "successful" backup containing no positions.
The rule here is the opposite and it is the whole point:

    A table that cannot be read FAILS the job.
    An upload that cannot be verified FAILS the job.

A backup that reports success without writing bytes is worse than no backup,
because it stops you looking for the real one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

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
GCS_PREFIX = "supabase"


class BackupError(RuntimeError):
    """Raised whenever a backup cannot be completed and proved."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch_all(client, table: str) -> list[dict]:
    """Reads every row of a table, paging so a large table is not truncated.

    Any failure propagates. A table that cannot be read fails the job.
    """
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


def _baseline_sql(root: Path) -> Path:
    """The schema captured at baseline. Its absence fails the job."""
    candidate = root / "migrations" / "000_baseline.sql"
    if not candidate.exists():
        raise BackupError(
            f"{candidate} is missing; refusing to write a schema-less backup. "
            "In a container this means migrations/ was not copied into the image."
        )
    return candidate


def _upload_folder(folder: Path, bucket_name: str, expected_files: int) -> str:
    """Copies the backup folder to GCS and PROVES the objects arrived.

    Uses the storage client rather than the gcloud command line so this runs
    in the Cloud Run image, which has no gcloud. A short object count raises.
    """
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    prefix = f"{GCS_PREFIX}/{folder.name}"

    for path in sorted(folder.iterdir()):
        if path.is_file():
            bucket.blob(f"{prefix}/{path.name}").upload_from_filename(str(path))

    landed = [
        b.name
        for b in client.list_blobs(bucket_name, prefix=f"{prefix}/")
        if b.name.endswith((".json", ".sql"))
    ]
    if len(landed) != expected_files:
        raise BackupError(
            f"upload incomplete: expected {expected_files} objects under "
            f"gs://{bucket_name}/{prefix}/, found {len(landed)}"
        )
    logger.info("uploaded and verified %d objects to gs://%s/%s/",
                len(landed), bucket_name, prefix)
    return f"gs://{bucket_name}/{prefix}/"


def run_backup(
    *,
    to_gcs: bool = False,
    bucket: str = "swayam-backups",
    root: Optional[Path] = None,
) -> dict:
    """Takes the backup. Raises BackupError rather than returning a falsehood.

    Returns a summary dict: the folder, the table count, the row count and,
    when uploaded, the destination.
    """
    root = root or Path(__file__).resolve().parents[3]
    baseline = _baseline_sql(root)

    from swayam.db import SupabaseDB

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out = root / "data" / "backups" / stamp
    out.mkdir(parents=True, exist_ok=True)

    client = SupabaseDB().client
    manifest: dict = {
        "taken_at_utc": datetime.now(timezone.utc).isoformat(),
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
        logger.info("[ok] %-32s %6d rows", table, len(rows))

    copy = out / "schema.sql"
    copy.write_text(baseline.read_text(encoding="utf-8"), encoding="utf-8")
    manifest["schema_sql_sha256"] = _sha256(copy)
    manifest["total_rows"] = total_rows
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    summary = {
        "folder": str(out),
        "stamp": stamp,
        "tables": len(TABLES),
        "rows": total_rows,
        "destination": None,
    }

    if to_gcs:
        # 19 table files + schema.sql + MANIFEST.json
        summary["destination"] = _upload_folder(out, bucket, len(TABLES) + 2)

    return summary


STALE_AFTER_HOURS = 48


def newest_backup_info(bucket: str = "swayam-backups") -> dict:
    """How old his newest backup actually is, read from the bucket every time.

    **Never a stored constant.** A backup age that comes from anywhere but the
    real object is worse than no figure at all, because it reassures him about
    something that may not have happened. On any failure this returns
    `available: False` with the reason, and the screen says so.
    """
    try:
        from google.cloud import storage

        client = storage.Client()
        stamps = sorted({
            b.name.split("/")[1]
            for b in client.list_blobs(bucket, prefix=f"{GCS_PREFIX}/")
            if len(b.name.split("/")) > 2
        })
        if not stamps:
            return {"available": False, "reason": "no backup exists in the bucket yet"}

        newest = stamps[-1]
        taken = datetime.strptime(newest, "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - taken).total_seconds() / 3600.0

        tables = rows = None
        man = client.bucket(bucket).blob(f"{GCS_PREFIX}/{newest}/MANIFEST.json")
        if man.exists():
            m = json.loads(man.download_as_text())
            tables, rows = len(m.get("tables", {})), m.get("total_rows")

        return {
            "available": True,
            "taken_at_utc": taken.isoformat(),
            "age_hours": round(age_hours, 1),
            "stale": age_hours > STALE_AFTER_HOURS,
            "stale_after_hours": STALE_AFTER_HOURS,
            "tables": tables,
            "rows": rows,
        }
    except Exception as exc:
        return {"available": False, "reason": str(exc)[:200]}


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gcs", action="store_true", help="also upload to Cloud Storage")
    parser.add_argument("--bucket", default="swayam-backups")
    args = parser.parse_args(argv)

    try:
        result = run_backup(to_gcs=args.gcs, bucket=args.bucket)
    except Exception as exc:
        logger.error("BACKUP FAILED: %s", exc)
        return 1

    logger.info("\n[ok] %d tables, %d rows -> %s",
                result["tables"], result["rows"], result["folder"])
    if result["destination"]:
        logger.info("[ok] uploaded to %s", result["destination"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
