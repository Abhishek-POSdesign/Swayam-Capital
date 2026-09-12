"""Downloads India VIX history from TWO independent sources and makes them agree.

India VIX is how his volatility path gets labelled: a calendar when an event is
coming and volatility can rise, a condor or a butterfly when volatility is high
and about to squeeze. Neither judgement can be tested without a volatility
series across the whole window.

Two sources on purpose, which is the discipline that caught the closing-price
problem in the options data (PLAN 2.15.8). One source is a number nobody checked.

    FYERS   NSE:INDIAVIX-INDEX through the ordinary history API.
            Minute from 2018 and daily from at least 2010, measured 2026-09-11.
    NSE     nsearchives.nseindia.com/content/indices/ind_close_all_DDMMYYYY.csv
            The official all-indices close file. One request a trading day,
            carrying India VIX's open, high, low and close.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\load_india_vix.py --what both
    .\\.venv\\Scripts\\python.exe scripts\\load_india_vix.py --what nse
    .\\.venv\\Scripts\\python.exe scripts\\load_india_vix.py --reconcile
    .\\.venv\\Scripts\\python.exe scripts\\load_india_vix.py --status

The default window is 2022-01-01 onwards, which is his window: the market before
and after Corona are different markets (PLAN 2.16.2).

Files land in `data/history/vix/`. Nothing is written to the database or to the
vault. NSE trading days are taken from the NIFTY daily bars already on disk, so
no request is spent on a weekend or a holiday.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import io
import logging
from pathlib import Path
import sys
import time

import pandas as pd
import pyarrow.parquet as pq
import requests

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

logger = logging.getLogger("load_india_vix")

FYERS_SYMBOL = "NSE:INDIAVIX-INDEX"

# His window, and the default for every result. PLAN 2.16.2.
HIS_WINDOW_START = date(2022, 1, 1)

# Measured against the live API on 2026-09-11, not assumed: minute candles exist
# from 2018 and a 2016 request returns nothing at all.
FYERS_MINUTE_FLOOR = date(2018, 1, 1)

NSE_ARCHIVE = "https://nsearchives.nseindia.com/content/indices/ind_close_all_{ddmmyyyy}.csv"
NSE_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
NSE_INDEX_NAME = "india vix"
NSE_PAUSE_SECONDS = 0.35

FYERS_COLUMNS = ["bar_start_utc", "open", "high", "low", "close"]
NSE_COLUMNS = ["trade_date", "open", "high", "low", "close", "source"]


# --------------------------------------------------------------------- FYERS


def candles_to_frame(candles: list[list[float]]) -> pd.DataFrame:
    """FYERS' candles as a frame. Volume is dropped: an index has none."""
    if not candles:
        return pd.DataFrame(columns=FYERS_COLUMNS)
    frame = pd.DataFrame(
        candles, columns=["epoch", "open", "high", "low", "close", "volume"]
    )
    frame["bar_start_utc"] = pd.to_datetime(frame["epoch"], unit="s", utc=True)
    return frame[FYERS_COLUMNS]


def download_fyers(
    client: FyersHistory,
    store: HistoryStore,
    resolution: str,
    start: date,
    end: date,
    force: bool = False,
) -> int:
    """One resolution of FYERS' VIX across the span, chunked and resumable."""
    label = "1m" if resolution == "1" else "1d"
    max_days = MAX_DAYS_MINUTE if resolution == "1" else MAX_DAYS_DAILY
    parts = ("vix", label)

    if resolution == "1" and start < FYERS_MINUTE_FLOOR:
        logger.info(
            "FYERS has no minute VIX before %s. Starting there instead of %s.",
            FYERS_MINUTE_FLOOR,
            start,
        )
        start = FYERS_MINUTE_FLOOR

    total_added = 0
    chunks = list(date_chunks(start, end, max_days))
    logger.info("VIX %s: %s to %s, %d requests.", label, start, end, len(chunks))

    for index, (chunk_start, chunk_end) in enumerate(chunks, 1):
        key = f"{chunk_start.isoformat()}..{chunk_end.isoformat()}"
        finished = chunk_end < date.today()
        if finished and not force and store.is_done(*parts, key=key):
            logger.info("  [%d/%d] %s already held.", index, len(chunks), key)
            continue

        try:
            candles = client.candles(FYERS_SYMBOL, resolution, chunk_start, chunk_end)
        except FyersHistoryError as exc:
            logger.error("  [%d/%d] %s FAILED: %s", index, len(chunks), key, exc)
            logger.error("  Stopping. Run the command again to resume here.")
            return total_added

        frame = candles_to_frame(candles)
        if frame.empty:
            logger.info("  [%d/%d] %s no data.", index, len(chunks), key)
            if finished:
                store.record(*parts, key=key, entry={"rows": 0, "note": "no data"})
            continue

        if resolution == "1":
            added = 0
            for year, group in frame.groupby(frame["bar_start_utc"].dt.year):
                result = store.write_parquet(
                    group,
                    *parts,
                    f"{year}.parquet",
                    dedupe_on=["bar_start_utc"],
                    sort_on=["bar_start_utc"],
                )
                added += result.rows_added
        else:
            result = store.write_parquet(
                frame,
                *parts,
                "all.parquet",
                dedupe_on=["bar_start_utc"],
                sort_on=["bar_start_utc"],
            )
            added = result.rows_added

        total_added += added
        if finished:
            store.record(*parts, key=key, entry={"rows": len(frame), "added": added})
        logger.info(
            "  [%d/%d] %s %d candles, %d new.", index, len(chunks), key, len(frame), added
        )

    return total_added


# ----------------------------------------------------------------------- NSE


def nse_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": NSE_USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/all-reports",
        }
    )
    return session


def parse_nse_vix_row(csv_text: str, trade_date: date) -> dict | None:
    """The India VIX row out of NSE's all-indices close file.

    Returns None when the file exists but carries no India VIX row, which is a
    real answer rather than an error.
    """
    try:
        frame = pd.read_csv(io.StringIO(csv_text))
    except Exception:
        return None
    if "Index Name" not in frame.columns:
        return None

    match = frame[
        frame["Index Name"].astype(str).str.strip().str.lower() == NSE_INDEX_NAME
    ]
    if match.empty:
        return None

    row = match.iloc[0]
    try:
        return {
            "trade_date": trade_date,
            "open": float(row["Open Index Value"]),
            "high": float(row["High Index Value"]),
            "low": float(row["Low Index Value"]),
            "close": float(row["Closing Index Value"]),
            "source": "nse_ind_close_all",
        }
    except (KeyError, TypeError, ValueError):
        return None


def trading_days_on_disk(store: HistoryStore, start: date, end: date) -> list[date]:
    """The sessions NSE actually held, taken from the NIFTY daily bars we hold.

    Deriving them rather than walking the calendar keeps about four hundred
    pointless requests off NSE's servers, and means a holiday is never mistaken
    for a download failure.
    """
    path = store.path_for("nifty", "1d", "all.parquet")
    if not path.exists():
        raise SystemExit(
            f"Cannot find {path}. Run scripts/load_nifty_history.py --what 1d first: "
            "the NIFTY daily bars are what tell us which days were sessions."
        )
    frame = pd.read_parquet(path, columns=["bar_start_utc"])
    days = (
        pd.to_datetime(frame["bar_start_utc"], utc=True)
        .dt.tz_convert("Asia/Kolkata")
        .dt.date
    )
    return sorted({d for d in days if start <= d <= end})


def download_nse(
    store: HistoryStore, start: date, end: date, force: bool = False
) -> int:
    """NSE's official daily VIX, one request a trading day, resumable."""
    parts = ("vix", "nse_daily")
    days = trading_days_on_disk(store, start, end)
    logger.info(
        "NSE VIX: %d trading sessions between %s and %s.", len(days), start, end
    )

    session = nse_session()
    collected: list[dict] = []
    added_total = 0
    failures = 0
    missing = 0

    for index, day in enumerate(days, 1):
        key = day.isoformat()
        if not force and store.is_done(*parts, key=key):
            continue

        url = NSE_ARCHIVE.format(ddmmyyyy=day.strftime("%d%m%Y"))
        try:
            response = session.get(url, timeout=30)
        except requests.RequestException as exc:
            failures += 1
            logger.warning("  %s request failed: %s", key, exc)
            time.sleep(2.0)
            continue

        if response.status_code != 200:
            failures += 1
            logger.warning("  %s HTTP %d", key, response.status_code)
            time.sleep(1.0)
            continue

        row = parse_nse_vix_row(response.text, day)
        if row is None:
            missing += 1
            store.record(*parts, key=key, entry={"rows": 0, "note": "no india vix row"})
        else:
            collected.append(row)

        if len(collected) >= 50:
            added_total += _flush_nse(store, parts, collected)
            collected = []
            logger.info("  %d/%d sessions done (%s).", index, len(days), key)

        time.sleep(NSE_PAUSE_SECONDS)

    if collected:
        added_total += _flush_nse(store, parts, collected)
    logger.info(
        "NSE VIX finished. %d refused or unreachable, %d files with no India VIX row.",
        failures,
        missing,
    )
    return added_total


def _flush_nse(store: HistoryStore, parts: tuple[str, ...], rows: list[dict]) -> int:
    """Writes a batch, then marks each day done. Data first, manifest after."""
    frame = pd.DataFrame(rows, columns=NSE_COLUMNS)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    result = store.write_parquet(
        frame, *parts, "all.parquet", dedupe_on=["trade_date"], sort_on=["trade_date"]
    )
    for row in rows:
        store.record(*parts, key=row["trade_date"].isoformat(), entry={"rows": 1})
    return result.rows_added


# ---------------------------------------------------------------- reconcile


def reconcile(store: HistoryStore, start: date, end: date) -> int:
    """Do the two sources agree? Reports, and never repairs either one."""
    fyers_path = store.path_for("vix", "1d", "all.parquet")
    nse_path = store.path_for("vix", "nse_daily", "all.parquet")
    for path in (fyers_path, nse_path):
        if not path.exists():
            print(f"Missing {path}. Download both sources first.")
            return 1

    fyers = pd.read_parquet(fyers_path)
    fyers["trade_date"] = (
        pd.to_datetime(fyers["bar_start_utc"], utc=True)
        .dt.tz_convert("Asia/Kolkata")
        .dt.normalize()
        .dt.tz_localize(None)
    )
    fyers = fyers[["trade_date", "open", "high", "low", "close"]]

    nse = pd.read_parquet(nse_path)
    nse["trade_date"] = pd.to_datetime(nse["trade_date"]).dt.normalize()
    nse = nse[["trade_date", "open", "high", "low", "close"]]

    lo, hi = pd.Timestamp(start), pd.Timestamp(end)
    fyers = fyers[(fyers["trade_date"] >= lo) & (fyers["trade_date"] <= hi)]
    nse = nse[(nse["trade_date"] >= lo) & (nse["trade_date"] <= hi)]

    merged = fyers.merge(nse, on="trade_date", how="inner", suffixes=("_fyers", "_nse"))

    print(f"INDIA VIX, TWO SOURCES, {start} to {end}")
    print(f"  FYERS daily rows      : {len(fyers)}")
    print(f"  NSE official rows     : {len(nse)}")
    print(f"  Days both hold        : {len(merged)}")
    only_fyers = sorted(set(fyers["trade_date"]) - set(nse["trade_date"]))
    only_nse = sorted(set(nse["trade_date"]) - set(fyers["trade_date"]))
    print(f"  Days only FYERS holds : {len(only_fyers)}")
    print(f"  Days only NSE holds   : {len(only_nse)}")
    if only_fyers[:5]:
        print("    FYERS-only sample :", [d.date().isoformat() for d in only_fyers[:5]])
    if only_nse[:5]:
        print("    NSE-only sample   :", [d.date().isoformat() for d in only_nse[:5]])

    if merged.empty:
        print("\nNothing overlaps. The two sources cannot be compared.")
        return 1

    print("\n  Field   exact   within 0.05   median gap   worst gap")
    for field in ("open", "high", "low", "close"):
        gap = (merged[f"{field}_fyers"] - merged[f"{field}_nse"]).abs()
        print(
            f"  {field:6s} {100 * (gap < 1e-9).mean():5.1f}%  "
            f"{100 * (gap <= 0.05).mean():9.1f}%  "
            f"{gap.median():10.4f}  {gap.max():10.4f}"
        )

    worst = merged.assign(
        gap=(merged["close_fyers"] - merged["close_nse"]).abs()
    ).nlargest(5, "gap")
    print("\n  The five days the closes disagree on most:")
    for _, row in worst.iterrows():
        print(
            f"    {row['trade_date'].date()}  FYERS {row['close_fyers']:7.3f}  "
            f"NSE {row['close_nse']:7.3f}  gap {row['gap']:.3f}"
        )

    print(
        "\n  Read this the way PLAN 2.15.8 reads the options reconciliation: two\n"
        "  archives built by different systems. A wide gap is a reason to distrust\n"
        "  a day, not a reason to edit either file. Nothing here was repaired."
    )
    return 0


def status(store: HistoryStore) -> None:
    print("INDIA VIX ON DISK")
    for parts, name in (
        (("vix", "1m"), "FYERS minute"),
        (("vix", "1d"), "FYERS daily"),
        (("vix", "nse_daily"), "NSE official daily"),
    ):
        folder = store.path_for(*parts)
        files = sorted(folder.glob("*.parquet")) if folder.exists() else []
        if not files:
            print(f"  {name:20s} nothing on disk")
            continue
        # Count from the file's own metadata. `read_parquet(columns=[])` returns
        # a frame with no rows at all on pyarrow, which reported 1,163 real rows
        # as zero on 2026-09-12. A count must never be able to read as empty.
        rows = sum(pq.ParquetFile(p).metadata.num_rows for p in files)
        size = sum(p.stat().st_size for p in files)
        print(
            f"  {name:20s} {rows:>9,} rows across {len(files)} file(s), "
            f"{size / 1e6:.1f} MB"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--what",
        choices=["fyers-1m", "fyers-1d", "fyers", "nse", "both"],
        default="both",
    )
    parser.add_argument("--from", dest="start", help="YYYY-MM-DD. Defaults to 2022-01-01.")
    parser.add_argument("--to", dest="end", help="YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--root", help="Where to write. Defaults to data/history.")
    parser.add_argument("--force", action="store_true", help="Re-fetch units already held.")
    parser.add_argument("--status", action="store_true", help="Report what is on disk.")
    parser.add_argument("--reconcile", action="store_true", help="Compare the two sources.")
    parser.add_argument(
        "--force-window",
        action="store_true",
        help="Download inside his trading window anyway. Spends the desk's budget.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    store = HistoryStore(Path(args.root) if args.root else ROOT_DIR / "data" / "history")

    start = date.fromisoformat(args.start) if args.start else HIS_WINDOW_START
    end = date.fromisoformat(args.end) if args.end else date.today()

    if args.status:
        status(store)
        return 0
    if args.reconcile:
        return reconcile(store, start, end)

    if in_his_trading_window() and not args.force_window:
        print(
            "It is his trading window. A bulk download spends the same FYERS budget\n"
            "the desk uses to quote his legs. Run it after 15:45 IST, or pass\n"
            "--force-window if you mean it."
        )
        return 1

    if args.what in ("fyers", "fyers-1m", "fyers-1d", "both"):
        token = settings.fyers_access_token
        if not token:
            print("No FYERS access token. Run .\\Refresh-Token.ps1 first.")
            return 1
        client = FyersHistory(app_id=settings.fyers_app_id, access_token=token)
        if args.what in ("fyers", "fyers-1d", "both"):
            download_fyers(client, store, "D", start, end, force=args.force)
        if args.what in ("fyers", "fyers-1m", "both"):
            download_fyers(client, store, "1", start, end, force=args.force)
        logger.info("FYERS: %d requests, %d refusals.", client.calls, client.refusals)

    if args.what in ("nse", "both"):
        download_nse(store, start, end, force=args.force)

    print()
    status(store)
    print(f"\nFinished {datetime.now(timezone.utc).isoformat(timespec='seconds')}.")
    print("Now run --reconcile. Neither source is trusted until they agree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
