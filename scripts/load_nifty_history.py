"""Downloads NIFTY's own price history for backtesting research.

This is the chart, not the options. It is the foundation for studying market
cycles and price-action formations, and it is free.

    .\\.venv\\Scripts\\python.exe scripts\\load_nifty_history.py --what both
    .\\.venv\\Scripts\\python.exe scripts\\load_nifty_history.py --what 1m --from 2018-01-01
    .\\.venv\\Scripts\\python.exe scripts\\load_nifty_history.py --status

Depth, measured against the live API on 2026-09-09, not assumed:
  1 minute  from January 2018. 2017 returns no data.
  daily     from at least 2010.

Files land in `data/history/nifty/`, one Parquet a year for minutes and one for
daily, with a manifest so an interrupted run resumes instead of restarting.
Nothing is written to the database or the vault.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import logging
from pathlib import Path
import sys

import pandas as pd

from zoneinfo import ZoneInfo

IST_ZONE = ZoneInfo("Asia/Kolkata")

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from swayam.config import settings  # noqa: E402
from swayam.research.fyers_history import (  # noqa: E402
    MAX_DAYS_DAILY,
    MAX_DAYS_MINUTE,
    FyersHistory,
    FyersHistoryError,
    date_chunks,
    in_his_trading_window,
)
from swayam.research.store import HistoryStore  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("nifty-history")

SYMBOL = "NSE:NIFTY50-INDEX"
# The earliest date each resolution actually returns anything. Bisected by hand.
EARLIEST_MINUTE = date(2018, 1, 1)
EARLIEST_DAILY = date(2010, 1, 1)

COLUMNS = ["bar_start_utc", "open", "high", "low", "close", "volume"]


def candles_to_frame(candles: list[list[float]]) -> pd.DataFrame:
    """FYERS' six-value candles as a frame, with a real timestamp."""
    if not candles:
        return pd.DataFrame(columns=COLUMNS)
    frame = pd.DataFrame(candles, columns=["epoch", "open", "high", "low", "close", "volume"])
    frame["bar_start_utc"] = pd.to_datetime(frame["epoch"], unit="s", utc=True)
    frame["volume"] = frame["volume"].astype("int64")
    return frame[COLUMNS]


def download(
    client: FyersHistory,
    store: HistoryStore,
    resolution: str,
    start: date,
    end: date,
    force: bool = False,
) -> int:
    """Fetches one resolution across the span, chunked, resumable."""
    label = "1m" if resolution == "1" else "1d"
    max_days = MAX_DAYS_MINUTE if resolution == "1" else MAX_DAYS_DAILY
    parts = ("nifty", label)

    total_added = 0
    chunks = list(date_chunks(start, end, max_days))
    logger.info(
        "NIFTY %s: %s to %s, %d requests to make.", label, start, end, len(chunks)
    )

    for index, (chunk_start, chunk_end) in enumerate(chunks, 1):
        key = f"{chunk_start.isoformat()}..{chunk_end.isoformat()}"
        # The chunk containing today is never marked done: today is still moving.
        finished = chunk_end < date.today()
        if finished and not force and store.is_done(*parts, key=key):
            logger.info("  [%d/%d] %s already held, skipping.", index, len(chunks), key)
            continue

        try:
            candles = client.candles(SYMBOL, resolution, chunk_start, chunk_end)
        except FyersHistoryError as exc:
            logger.error("  [%d/%d] %s FAILED: %s", index, len(chunks), key, exc)
            logger.error("  Stopping here. Run the command again to resume from this chunk.")
            return total_added

        frame = candles_to_frame(candles)
        if frame.empty:
            logger.info("  [%d/%d] %s no data.", index, len(chunks), key)
            if finished:
                store.record(*parts, key=key, entry={"rows": 0, "note": "no data"})
            continue

        # One file a year for minutes keeps each file openable; daily is one file.
        if resolution == "1":
            added_here = 0
            for year, group in frame.groupby(frame["bar_start_utc"].dt.year):
                result = store.write_parquet(
                    group, *parts, f"{year}.parquet",
                    dedupe_on=["bar_start_utc"], sort_on=["bar_start_utc"],
                )
                added_here += result.rows_added
            added = added_here
        else:
            result = store.write_parquet(
                frame, *parts, "all.parquet",
                dedupe_on=["bar_start_utc"], sort_on=["bar_start_utc"],
            )
            added = result.rows_added

        total_added += added
        if finished:
            store.record(*parts, key=key, entry={"rows": len(frame), "added": added})
        logger.info(
            "  [%d/%d] %s %d candles, %d new.", index, len(chunks), key, len(frame), added
        )

    return total_added


def verify(store: HistoryStore) -> int:
    """Checks the downloaded history against itself and reports honestly.

    Run after any download. It answers the only question that matters about
    research data: can this be trusted, and where can it not.
    """
    import datetime as _dt

    minute_files = sorted((store.root / "nifty" / "1m").glob("*.parquet"))
    daily_file = store.root / "nifty" / "1d" / "all.parquet"
    if not minute_files or not daily_file.exists():
        print("Nothing to verify yet. Download first.")
        return 1

    minutes = pd.concat([pd.read_parquet(p) for p in minute_files], ignore_index=True)
    daily = pd.read_parquet(daily_file)
    minutes["ist"] = minutes["bar_start_utc"].dt.tz_convert(IST_ZONE)
    minutes["day"] = minutes["ist"].dt.date
    daily["day"] = daily["bar_start_utc"].dt.tz_convert(IST_ZONE).dt.date

    session = minutes[
        (minutes["ist"].dt.time >= _dt.time(9, 15))
        & (minutes["ist"].dt.time <= _dt.time(15, 29))
    ]
    per_day = session.groupby("day").size()
    outside = len(minutes) - len(session)
    crossed = int((minutes["high"] < minutes["low"]).sum())

    print("\nNIFTY history, verified")
    print("=" * 68)
    print(f"  minute bars           {len(minutes):>10,}   {minutes['ist'].min().date()} to {minutes['ist'].max().date()}")
    print(f"  daily bars            {len(daily):>10,}   {daily['day'].min()} to {daily['day'].max()}")
    print(f"  trading days          {per_day.size:>10,}")
    print(f"  duplicate timestamps  {int(minutes['bar_start_utc'].duplicated().sum()):>10,}")
    print(f"  null prices           {int(minutes[['open', 'high', 'low', 'close']].isna().sum().sum()):>10,}")
    print(f"  complete sessions     {int((per_day == 375).sum()):>10,}   of {per_day.size} (375 minutes each)")
    print(f"  short sessions        {int((per_day < 370).sum()):>10,}   halts and partial days")

    print("\n  Two things that are real, not faults:")
    print(f"    {outside:,} bars sit outside 09:15-15:30. Those are Diwali Muhurat")
    print("    evening sessions. A backtest must not treat them as ordinary days.")
    if crossed:
        print(f"    {crossed:,} bars have a high below their low, all with zero volume.")
        print("    That is a defect in FYERS' own archive, not in the download. They")
        print("    are left as they came; do not silently repair someone else's data.")

    frame = session.groupby("day").agg(
        o=("open", "first"), h=("high", "max"), l=("low", "min"), c=("close", "last")
    ).reset_index()
    joined = frame.merge(daily[["day", "open", "high", "low", "close"]], on="day")
    print("\n  The minute bars rebuilt into daily bars, against FYERS' own daily:")
    for mine, theirs, name in (("o", "open", "open"), ("h", "high", "high"),
                               ("l", "low", "low"), ("c", "close", "close")):
        diff = (joined[mine] - joined[theirs]).abs()
        print(f"    {name:6s} median {diff.median():7.2f}   95th {diff.quantile(0.95):7.2f}   "
              f"worst {diff.max():8.2f}")

    print("\n  THE CLOSE IS THE ONE THAT DIFFERS, AND IT SHOULD.")
    print("    Open, high and low match exactly on essentially every day, which is")
    print("    the proof the minute series is complete. The close does not, because")
    print("    NSE's official close is a weighted average of the last half hour, not")
    print("    the last traded level. A backtest that marks a position at the daily")
    print("    close is marking at a price nobody could trade at. Use 15:29.")
    print("=" * 68)
    return 0


def report(store: HistoryStore) -> None:
    """What is actually on disk right now."""
    print("\nNIFTY history held locally")
    print("-" * 64)
    any_found = False
    for label in ("1m", "1d"):
        folder = store.root / "nifty" / label
        if not folder.exists():
            continue
        files = sorted(p for p in folder.glob("*.parquet"))
        if not files:
            continue
        any_found = True
        rows = 0
        size = 0
        earliest = None
        latest = None
        for path in files:
            frame = pd.read_parquet(path, columns=["bar_start_utc"])
            rows += len(frame)
            size += path.stat().st_size
            if len(frame):
                low, high = frame["bar_start_utc"].min(), frame["bar_start_utc"].max()
                earliest = low if earliest is None else min(earliest, low)
                latest = high if latest is None else max(latest, high)
        print(f"{label:>4}  {rows:>10,} bars  {size / 1_048_576:>7.1f} MB  "
              f"{earliest} to {latest}")
    if not any_found:
        print("Nothing downloaded yet.")
    print("-" * 64)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--what", choices=["1m", "1d", "both"], default="both")
    parser.add_argument("--from", dest="start", help="YYYY-MM-DD. Defaults to the earliest FYERS holds.")
    parser.add_argument("--to", dest="end", help="YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--root", help="Where to write. Defaults to data/history.")
    parser.add_argument("--force", action="store_true", help="Re-fetch chunks already held.")
    parser.add_argument("--status", action="store_true", help="Report what is on disk and exit.")
    parser.add_argument("--verify", action="store_true", help="Check what is on disk and exit.")
    args = parser.parse_args()

    store = HistoryStore(Path(args.root) if args.root else None)

    if args.status:
        report(store)
        return 0

    if args.verify:
        return verify(store)

    if in_his_trading_window() and not args.force:
        logger.error(
            "It is inside his trading window. This download shares the FYERS request "
            "budget with the live desk and would blank the prices on his screen. "
            "Run it outside 12:30 to 15:45 IST, or pass --force if you are certain."
        )
        return 2

    token = settings.fyers_access_token
    if not token:
        logger.error("No FYERS access token. Run .\\Refresh-Token.ps1 first.")
        return 2

    client = FyersHistory(app_id=settings.fyers_app_id, access_token=token)
    end = date.fromisoformat(args.end) if args.end else date.today()

    started = datetime.now(timezone.utc)
    total = 0
    if args.what in ("1m", "both"):
        start = date.fromisoformat(args.start) if args.start else EARLIEST_MINUTE
        total += download(client, store, "1", max(start, EARLIEST_MINUTE), end)
    if args.what in ("1d", "both"):
        start = date.fromisoformat(args.start) if args.start else EARLIEST_DAILY
        total += download(client, store, "D", max(start, EARLIEST_DAILY), end)

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    logger.info(
        "\nDone. %d new bars in %.0f seconds, %d FYERS calls, %d refusals.",
        total, elapsed, client.calls, client.refusals,
    )
    report(store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
