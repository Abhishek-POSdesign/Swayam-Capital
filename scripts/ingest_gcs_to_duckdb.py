"""
Nightly Google Cloud Storage to local DuckDB options ingest tool for Swayam Capital.

Downloads options chain Parquet files recorded by the cloud function and
bulk-inserts them idempotently into the local DuckDB `options_history` table.

Usage:
    python scripts/ingest_gcs_to_duckdb.py
    python scripts/ingest_gcs_to_duckdb.py --date 2026-09-08
    python scripts/ingest_gcs_to_duckdb.py --date-range 2026-09-08:2026-09-12
"""

import argparse
from datetime import date, datetime, timedelta, timezone
import io
from pathlib import Path
import sys
from google.cloud import storage
import pandas as pd

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from swayam.config import settings
from swayam.local_db import LocalDB


def log_message(msg: str) -> None:
    """Prints message to stdout and appends to data/ingest.log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)

    log_file = Path(settings.local_data_dir) / "ingest.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass


def ingest_date(target_date: date, storage_client: storage.Client, local_db: LocalDB) -> int:
    """Downloads Parquet for a specific date from GCS and inserts into DuckDB."""
    bucket_name = settings.gcs_options_bucket or "swayam-capital-options-data"
    bucket = storage_client.bucket(bucket_name)

    paths_to_try = [
        f"{target_date.strftime('%Y/%m/%d')}/nifty_chain.parquet",
        f"{target_date.strftime('%Y-%m-%d')}/nifty_chain.parquet",
    ]

    target_blob = None
    for p in paths_to_try:
        b = bucket.blob(p)
        if b.exists():
            target_blob = b
            break

    if target_blob is None:
        log_message(f"No recording found in gs://{bucket_name}/ for date {target_date}. Skipping.")
        return 0

    log_message(f"Downloading gs://{bucket_name}/{target_blob.name} ({target_blob.size or 0} bytes)...")
    content_bytes = target_blob.download_as_bytes()
    df = pd.read_parquet(io.BytesIO(content_bytes))

    if df.empty:
        log_message(f"Parquet file for {target_date} was empty. 0 rows inserted.")
        return 0

    # Ingest into local DuckDB options_history (strictly idempotent upsert)
    inserted_count = local_db.insert_options_df(df)

    # Record in DuckDB ingest_log table
    conn = local_db.get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ingest_log (
            ingest_date DATE PRIMARY KEY,
            records_ingested INTEGER NOT NULL,
            ingested_at TIMESTAMPTZ NOT NULL,
            source_path TEXT NOT NULL
        );
    """)
    conn.execute("""
        INSERT OR REPLACE INTO ingest_log (ingest_date, records_ingested, ingested_at, source_path)
        VALUES (?, ?, ?, ?);
    """, [target_date, inserted_count, datetime.now(timezone.utc), f"gs://{bucket_name}/{target_blob.name}"])

    log_message(f"Successfully ingested {inserted_count} rows for {target_date} into local DuckDB `options_history`.")
    return inserted_count


def parse_dates_arg(args: argparse.Namespace) -> list[date]:
    """Resolves target dates based on CLI arguments."""
    if args.date_range:
        parts = args.date_range.split(":")
        if len(parts) != 2:
            raise ValueError("Invalid --date-range format. Expected YYYY-MM-DD:YYYY-MM-DD")
        start = datetime.strptime(parts[0].strip(), "%Y-%m-%d").date()
        end = datetime.strptime(parts[1].strip(), "%Y-%m-%d").date()
        curr = start
        dates = []
        while curr <= end:
            dates.append(curr)
            curr += timedelta(days=1)
        return dates
    elif args.date:
        return [datetime.strptime(args.date.strip(), "%Y-%m-%d").date()]
    else:
        return [date.today()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest GCS options Parquet into DuckDB.")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format (default: today)")
    parser.add_argument("--date-range", help="Date range in YYYY-MM-DD:YYYY-MM-DD format for backfilling")
    args = parser.parse_args()

    dates_to_process = parse_dates_arg(args)
    log_message(f"Starting GCS to DuckDB options ingest for {len(dates_to_process)} date(s)...")

    storage_client = storage.Client()
    local_db = LocalDB()

    total_ingested = 0
    for d in dates_to_process:
        total_ingested += ingest_date(d, storage_client, local_db)

    log_message(f"Ingest complete. Total records ingested: {total_ingested}. Local table: `options_history`.")


if __name__ == "__main__":
    main()
