"""Downloads NSE's daily NIFTY options history for backtesting research.

This is the free, official, end-of-day record, and it is what covers his
profitable run of October 2022 to April 2023. FYERS' minute history does not
reach back that far, so this is the only source for those trades.

    .\\.venv\\Scripts\\python.exe scripts\\load_nse_options_eod.py --from 2022-01-01
    .\\.venv\\Scripts\\python.exe scripts\\load_nse_options_eod.py --status
    .\\.venv\\Scripts\\python.exe scripts\\load_nse_options_eod.py --verify

One Parquet a year in `data/history/options_eod/`, with a manifest so an
interrupted run resumes. Roughly 1,600 NIFTY option rows a day, so a year is
about 400,000 rows and a few megabytes.

The downloaded CSV is thrown away after it is parsed. Keeping them would cost
about six gigabytes for what amounts to five per cent useful rows, and NSE will
serve any of them again.

Nothing is written to the database or the vault.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import logging
from pathlib import Path
import shutil
import sys
import tempfile

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from swayam.bhavcopy import BhavcopyDownloader, BhavcopyError  # noqa: E402
from swayam.research.bhavcopy_normalise import (  # noqa: E402
    fill_underlying_from_index,
    normalise,
)
from swayam.research.store import HistoryStore  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("nse-options-eod")

PARTS = ("options_eod",)
EARLIEST = date(2018, 1, 1)


def index_daily(store: HistoryStore) -> pd.DataFrame:
    """Our own NIFTY daily bars, used to fill the underlying on legacy days."""
    path = store.root / "nifty" / "1d" / "all.parquet"
    if not path.exists():
        logger.warning(
            "No NIFTY daily history yet, so the legacy years will have no underlying "
            "level. Run scripts/load_nifty_history.py --what 1d first."
        )
        return pd.DataFrame(columns=["day", "close"])
    frame = pd.read_parquet(path)
    frame["day"] = frame["bar_start_utc"].dt.tz_convert("Asia/Kolkata").dt.date
    return frame[["day", "close"]]


def trading_days(start: date, end: date) -> list[date]:
    """Weekdays only. A holiday simply returns nothing and is recorded as such."""
    days, cursor = [], start
    while cursor <= end:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def download(store: HistoryStore, start: date, end: date, force: bool = False) -> int:
    days = trading_days(start, end)
    logger.info("NSE daily options: %s to %s, %d weekdays to fetch.", start, end, len(days))

    index = index_daily(store)
    scratch = Path(tempfile.mkdtemp(prefix="swayam-bhavcopy-"))
    downloader = BhavcopyDownloader(output_dir=scratch)

    total_added = holidays = failed = 0
    try:
        for position, day in enumerate(days, 1):
            key = day.isoformat()
            if not force and store.is_done(*PARTS, key=key):
                continue

            try:
                csv_path = downloader.download_bhavcopy(day)
            except BhavcopyError:
                # NSE has no file for a trading holiday. That is an answer.
                holidays += 1
                store.record(*PARTS, key=key, entry={"rows": 0, "note": "no file, holiday"})
                continue
            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.warning("  %s failed: %s", key, str(exc)[:120])
                continue

            try:
                raw = pd.read_csv(csv_path, low_memory=False)
                frame = normalise(raw)
                frame = fill_underlying_from_index(frame, index)
            finally:
                csv_path.unlink(missing_ok=True)

            if frame.empty:
                holidays += 1
                store.record(*PARTS, key=key, entry={"rows": 0, "note": "no NIFTY option rows"})
                continue

            result = store.write_parquet(
                frame, *PARTS, f"{day.year}.parquet",
                dedupe_on=["trade_date", "symbol"],
                sort_on=["trade_date", "expiry_date", "strike", "option_type"],
            )
            total_added += result.rows_added
            store.record(
                *PARTS, key=key,
                entry={"rows": len(frame), "added": result.rows_added,
                       "format": str(frame["source_format"].iloc[0])},
            )
            if position % 25 == 0 or position == len(days):
                logger.info(
                    "  [%d/%d] %s  %d rows this day, %d new in total.",
                    position, len(days), key, len(frame), total_added,
                )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    logger.info(
        "\nDone. %d new rows. %d days had no file (holidays). %d failed and can be retried.",
        total_added, holidays, failed,
    )
    return total_added


def load_all(store: HistoryStore) -> pd.DataFrame:
    files = sorted((store.root / "options_eod").glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)


def report(store: HistoryStore) -> None:
    frame = load_all(store)
    if frame.empty:
        print("Nothing downloaded yet.")
        return
    print("\nNSE daily NIFTY options held locally")
    print("-" * 68)
    frame["year"] = pd.to_datetime(frame["trade_date"]).dt.year
    for year, group in frame.groupby("year"):
        formats = "/".join(sorted(set(group["source_format"])))
        print(f"  {year}  {len(group):>9,} rows  {group['trade_date'].nunique():>4} days  {formats}")
    print("-" * 68)
    print(f"  total {len(frame):,} rows across {frame['trade_date'].nunique():,} days")


def verify(store: HistoryStore) -> int:
    frame = load_all(store)
    if frame.empty:
        print("Nothing to verify yet. Download first.")
        return 1

    print("\nNSE daily NIFTY options, verified")
    print("=" * 68)
    print(f"  rows                    {len(frame):>10,}")
    print(f"  trading days            {frame['trade_date'].nunique():>10,}   "
          f"{frame['trade_date'].min()} to {frame['trade_date'].max()}")
    print(f"  distinct contracts      {frame['symbol'].nunique():>10,}")
    print(f"  duplicate rows          {int(frame.duplicated(['trade_date', 'symbol']).sum()):>10,}")

    traded = frame[
        (frame["volume_units"].fillna(0) > 0) | (frame["volume_contracts"].fillna(0) > 0)
    ]
    print(f"  rows that actually traded {len(traded):>8,}   "
          f"{100 * len(traded) / len(frame):.0f}% of the file")
    print("    The rest carry a closing price the exchange derived for a contract")
    print("    nobody traded. A backtest must not fill at those.")

    have_spot = frame["underlying_spot"].notna()
    print(f"\n  rows with a NIFTY level {int(have_spot.sum()):>10,}   "
          f"{100 * have_spot.mean():.0f}%")
    for source, count in frame.loc[have_spot, "underlying_spot_source"].value_counts().items():
        print(f"    {source:<28} {count:>10,}")
    print("    NSE's own file carries it only from July 2024. Before that it is")
    print("    joined from our downloaded NIFTY daily close, and says so.")

    have_lot = frame["lot_size"].notna()
    print(f"\n  rows with a lot size    {int(have_lot.sum()):>10,}   {100 * have_lot.mean():.0f}%")
    if have_lot.any():
        by_year = frame[have_lot].assign(
            year=pd.to_datetime(frame.loc[have_lot, "trade_date"]).dt.year
        ).groupby("year")["lot_size"].agg(lambda s: sorted(set(s)))
        for year, lots in by_year.items():
            print(f"    {year}  lot sizes seen: {lots}")
    print("    The legacy file does not carry it and it is left NULL, never guessed.")
    print("    A 2022 backtest that assumes today's lot of 65 is wrong by a fifth.")

    print("\n  Sanity of the prices:")
    crossed = int((frame["high"] < frame["low"]).sum())
    negative = int((frame["close"] < 0).sum())
    print(f"    high below low        {crossed:>10,}")
    print(f"    negative close        {negative:>10,}")
    print("=" * 68)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="start", help="YYYY-MM-DD. Default 2018-01-01.")
    parser.add_argument("--to", dest="end", help="YYYY-MM-DD. Default today.")
    parser.add_argument("--root", help="Where to write. Defaults to data/history.")
    parser.add_argument("--force", action="store_true", help="Re-fetch days already held.")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    store = HistoryStore(Path(args.root) if args.root else None)
    if args.status:
        report(store)
        return 0
    if args.verify:
        return verify(store)

    start = date.fromisoformat(args.start) if args.start else EARLIEST
    end = date.fromisoformat(args.end) if args.end else date.today()
    started = datetime.now(timezone.utc)
    download(store, start, end, force=args.force)
    logger.info("Took %.0f seconds.", (datetime.now(timezone.utc) - started).total_seconds())
    report(store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
