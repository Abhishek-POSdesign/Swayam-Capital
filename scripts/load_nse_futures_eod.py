"""Downloads NSE's daily NIFTY FUTURES history, from the same free files as the options.

NSE's daily F&O file carries index futures beside the options, and
`load_nse_options_eod.py` throws them away. They are worth keeping:

- **The forward level.** NSE builds India VIX from the NIFTY futures price, not
  the spot (Library A8). Implied volatility computed the same way needs it.
- **The basis.** Futures against spot is the market's own carry, day by day.
- **The calendar's far leg** sits against a later expiry, and the futures curve
  says what the market charges to hold across it.

    .\\.venv\\Scripts\\python.exe scripts\\load_nse_futures_eod.py
    .\\.venv\\Scripts\\python.exe scripts\\load_nse_futures_eod.py --status

**Days come from the NIFTY daily bars already on disk, not from the calendar.**
The options loader walks weekdays and records any missing file as a holiday,
permanently. That lost Thursday 10 September 2026, probably fetched before NSE
published it, and it skipped five weekend special sessions that really traded.
A session that has index bars is a session; a missing file on one is a FAILURE
to retry, never a holiday.

One Parquet a year in `data/history/futures_eod/`, with a manifest so an
interrupted run resumes. Nothing is written to the database or the vault.
"""

from __future__ import annotations

import argparse
from datetime import date
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
from swayam.research.store import HistoryStore  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("nse-futures-eod")

PARTS = ("futures_eod",)
UNDERLYING = "NIFTY"
# His window. The market before and after Corona are different markets.
HIS_WINDOW_START = date(2022, 1, 1)

COLUMNS = [
    "trade_date", "underlying", "expiry_date", "series",
    "open", "high", "low", "close", "prev_close", "settle_price",
    "volume_contracts", "volume_units", "turnover_inr",
    "open_interest", "change_in_oi", "underlying_spot", "lot_size",
    "source_format",
]


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _int(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").round().astype("Int64")


def normalise_futures(frame: pd.DataFrame) -> pd.DataFrame:
    """One day's NSE file, filtered to NIFTY index futures, in one shape.

    Every placeholder column is built on the filtered rows' own index. Built on
    a fresh 0..n index instead, pandas aligns it into extra all-empty rows,
    which happened on the first test run of this loader.
    """
    if frame.empty:
        return pd.DataFrame(columns=COLUMNS)

    if "FinInstrmTp" in frame.columns:
        rows = frame[
            (frame["TckrSymb"] == UNDERLYING) & (frame["FinInstrmTp"].isin(["IDF", "FUTIDX"]))
        ]
        if rows.empty:
            return pd.DataFrame(columns=COLUMNS)
        out = pd.DataFrame({
            "trade_date": pd.to_datetime(rows["TradDt"]).dt.date,
            "expiry_date": pd.to_datetime(rows["XpryDt"]).dt.date,
            "open": _num(rows["OpnPric"]),
            "high": _num(rows["HghPric"]),
            "low": _num(rows["LwPric"]),
            "close": _num(rows["ClsPric"]),
            "prev_close": _num(rows["PrvsClsgPric"]),
            "settle_price": _num(rows["SttlmPric"]),
            "volume_contracts": pd.Series(pd.NA, index=rows.index, dtype="Int64"),
            "volume_units": _int(rows["TtlTradgVol"]),
            "turnover_inr": _num(rows["TtlTrfVal"]),
            "open_interest": _int(rows["OpnIntrst"]),
            "change_in_oi": _int(rows["ChngInOpnIntrst"]),
            "underlying_spot": _num(rows["UndrlygPric"]),
            "lot_size": _int(rows["NewBrdLotQty"]),
            "source_format": "udiff",
        })
    else:
        rows = frame[(frame["SYMBOL"] == UNDERLYING) & (frame["INSTRUMENT"] == "FUTIDX")]
        if rows.empty:
            return pd.DataFrame(columns=COLUMNS)
        out = pd.DataFrame({
            "trade_date": pd.to_datetime(rows["TIMESTAMP"], format="%d-%b-%Y").dt.date,
            "expiry_date": pd.to_datetime(rows["EXPIRY_DT"], format="%d-%b-%Y").dt.date,
            "open": _num(rows["OPEN"]),
            "high": _num(rows["HIGH"]),
            "low": _num(rows["LOW"]),
            "close": _num(rows["CLOSE"]),
            "prev_close": pd.Series(float("nan"), index=rows.index, dtype="float64"),
            "settle_price": _num(rows["SETTLE_PR"]),
            "volume_contracts": _int(rows["CONTRACTS"]),
            "volume_units": pd.Series(pd.NA, index=rows.index, dtype="Int64"),
            # VAL_INLAKH is lakhs of rupees; one lakh is 100,000.
            "turnover_inr": _num(rows["VAL_INLAKH"]) * 100_000.0,
            "open_interest": _int(rows["OPEN_INT"]),
            "change_in_oi": _int(rows["CHG_IN_OI"]),
            # The legacy file carries neither; left empty, never guessed.
            "underlying_spot": pd.Series(float("nan"), index=rows.index, dtype="float64"),
            "lot_size": pd.Series(pd.NA, index=rows.index, dtype="Int64"),
            "source_format": "legacy",
        })

    out.insert(1, "underlying", UNDERLYING)
    # Near, next and far, by expiry on that day: 1 is the nearest.
    # Rank on real timestamps: a column of date objects ranks to NaN.
    expiry_ts = pd.to_datetime(out["expiry_date"])
    out["series"] = expiry_ts.groupby(out["trade_date"]).rank(method="dense").astype("Int64")
    return out[COLUMNS].sort_values(["trade_date", "expiry_date"]).reset_index(drop=True)


def sessions_on_disk(store: HistoryStore, start: date, end: date) -> list[date]:
    """Every day NIFTY actually traded, special sessions included."""
    path = store.path_for("nifty", "1m")
    files = sorted(path.glob("*.parquet"))
    if not files:
        raise SystemExit("No NIFTY minute bars on disk. Run scripts/load_nifty_history.py first.")
    days: set[date] = set()
    for file in files:
        frame = pd.read_parquet(file, columns=["bar_start_utc"])
        local = pd.to_datetime(frame["bar_start_utc"], utc=True).dt.tz_convert("Asia/Kolkata")
        days.update(local.dt.date.unique())
    return sorted(d for d in days if start <= d <= end)


def download(store: HistoryStore, start: date, end: date, force: bool = False) -> int:
    days = sessions_on_disk(store, start, end)
    logger.info("NSE daily NIFTY futures: %d sessions between %s and %s.", len(days), start, end)

    scratch = Path(tempfile.mkdtemp(prefix="swayam-futures-"))
    downloader = BhavcopyDownloader(output_dir=scratch)
    added = failed = empty = 0
    try:
        for position, day in enumerate(days, 1):
            key = day.isoformat()
            if not force and store.is_done(*PARTS, key=key):
                continue
            try:
                csv_path = downloader.download_bhavcopy(day)
            except BhavcopyError as exc:
                # The index traded, so this is not a holiday. Retry next run.
                failed += 1
                logger.warning("  %s no NSE file although NIFTY traded: %s", key, str(exc)[:100])
                continue
            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.warning("  %s failed: %s", key, str(exc)[:120])
                continue
            try:
                frame = normalise_futures(pd.read_csv(csv_path, low_memory=False))
            finally:
                csv_path.unlink(missing_ok=True)

            if frame.empty:
                empty += 1
                logger.warning("  %s NSE file had no NIFTY futures rows. Not marked done.", key)
                continue

            result = store.write_parquet(
                frame, *PARTS, f"{day.year}.parquet",
                dedupe_on=["trade_date", "expiry_date"],
                sort_on=["trade_date", "expiry_date"],
            )
            added += result.rows_added
            store.record(*PARTS, key=key, entry={"rows": len(frame), "added": result.rows_added,
                                                 "format": str(frame["source_format"].iloc[0])})
            if position % 50 == 0 or position == len(days):
                logger.info("  [%d/%d] %s  %d new rows so far.", position, len(days), key, added)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    logger.info("\nDone. %d new rows. %d sessions failed and will be retried. %d had no futures rows.",
                added, failed, empty)
    return added


def status(store: HistoryStore) -> None:
    files = sorted(store.path_for(*PARTS).glob("*.parquet"))
    if not files:
        print("Nothing downloaded yet.")
        return
    frame = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
    print("\nNSE daily NIFTY futures held locally")
    print("-" * 60)
    frame["year"] = pd.to_datetime(frame["trade_date"]).dt.year
    for year, group in frame.groupby("year"):
        print(f"  {year}  {len(group):>6,} rows  {group['trade_date'].nunique():>4} sessions  "
              f"{'/'.join(sorted(set(group['source_format'])))}")
    print("-" * 60)
    print(f"  total {len(frame):,} rows, {frame['trade_date'].nunique():,} sessions, "
          f"series per day {sorted(frame.groupby('trade_date').size().unique())}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="start", help="YYYY-MM-DD. Default 2022-01-01.")
    parser.add_argument("--to", dest="end", help="YYYY-MM-DD. Default today.")
    parser.add_argument("--root", help="Where to write. Defaults to data/history.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    store = HistoryStore(Path(args.root) if args.root else ROOT_DIR / "data" / "history")
    if args.status:
        status(store)
        return 0
    start = date.fromisoformat(args.start) if args.start else HIS_WINDOW_START
    end = date.fromisoformat(args.end) if args.end else date.today()
    download(store, start, end, force=args.force)
    status(store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
