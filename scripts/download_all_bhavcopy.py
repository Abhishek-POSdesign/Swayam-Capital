"""
Bulk Historical NSE Bhavcopy Downloader & Ingestor for Swayam Capital.

Downloads daily UDiFF Bhavcopy archives from NSE for a specified date range,
extracts NIFTY options, and ingests them into the local DuckDB database.

Usage:
    python scripts/download_all_bhavcopy.py --from 2026-08-01 --to 2026-08-31
"""

import argparse
from datetime import date, datetime, timedelta
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from swayam.bhavcopy import BhavcopyError, bhavcopy_downloader
from swayam.local_db import local_db


def download_range(start_date: date, end_date: date) -> None:
    """Iterates through trading days, downloads Bhavcopies, and ingests into DuckDB.

    Args:
        start_date: Earliest date in range.
        end_date: Latest date in range.
    """
    if start_date > end_date:
        print("[FAIL] Error: --from date cannot be after --to date.")
        sys.exit(1)

    current = start_date
    trading_days: list[date] = []

    while current <= end_date:
        # Skip weekends (Saturday=5, Sunday=6)
        if current.weekday() < 5:
            trading_days.append(current)
        current += timedelta(days=1)

    print(f"[*] Starting bulk Bhavcopy download for {len(trading_days)} weekdays ({start_date} to {end_date})...")

    downloaded = 0
    total_rows = 0
    skipped_or_holiday = 0

    for i, d in enumerate(trading_days, 1):
        d_str = d.strftime("%Y-%m-%d")
        print(f"[{i}/{len(trading_days)}] Fetching {d_str}...", end=" ", flush=True)
        try:
            csv_path = bhavcopy_downloader.download_bhavcopy(d)
            rows = bhavcopy_downloader.ingest_to_duckdb(csv_path)
            downloaded += 1
            total_rows += rows
            print(f"[OK] Ingested ({rows} rows)")
        except BhavcopyError:
            skipped_or_holiday += 1
            print("[WARN] Skipped (Holiday/Unavailable)")
        except Exception as e:
            skipped_or_holiday += 1
            print(f"[ERROR] {e}")

    final_total_records = local_db.get_row_count()
    print("\n" + "=" * 50)
    print("Bhavcopy Bulk Ingestion Summary")
    print("=" * 50)
    print(f"  Weekdays Checked:   {len(trading_days)}")
    print(f"  Sessions Ingested:  {downloaded}")
    print(f"  Holidays/Skipped:   {skipped_or_holiday}")
    print(f"  New Rows Added:     {total_rows}")
    print(f"  Total DuckDB Rows:  {final_total_records}")
    print("=" * 50)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download and ingest NSE Bhavcopies.")
    parser.add_argument("--from", dest="from_date", default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="to_date", default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--days", dest="days", type=int, default=None, help="Number of trailing days to download (e.g. 30)")

    args = parser.parse_args(argv)

    if args.days is not None:
        e_date = date.today()
        s_date = e_date - timedelta(days=args.days)
    elif args.from_date and args.to_date:
        try:
            s_date = datetime.strptime(args.from_date, "%Y-%m-%d").date()
            e_date = datetime.strptime(args.to_date, "%Y-%m-%d").date()
        except ValueError as val_err:
            print(f"[FAIL] Invalid date format: {val_err}. Please use YYYY-MM-DD.")
            return 1
    else:
        # Default to trailing 30 days if no arguments specified
        e_date = date.today()
        s_date = e_date - timedelta(days=30)

    download_range(s_date, e_date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
