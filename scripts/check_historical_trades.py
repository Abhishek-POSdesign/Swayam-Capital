"""Reads his 21 historical swing trades and says whether they can be backtested.

`ROADMAP.md` §3 milestone 2 makes these trades the acceptance test: the
backtester is not trusted until it reproduces what they actually did. So before
any backtester is written, two questions have to be answered honestly.

  1. Are the notes complete enough to reproduce?
  2. Is the price data for those contracts actually on disk?

    .\\.venv\\Scripts\\python.exe scripts\\check_historical_trades.py
    .\\.venv\\Scripts\\python.exe scripts\\check_historical_trades.py --csv out.csv

READ ONLY, in both directions. It does not write to the vault and it does not
write to the database. It reads his notes and the downloaded Parquet files.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from swayam.config import settings  # noqa: E402
from swayam.research.historical_trades import HistoricalTrade, load_all  # noqa: E402
from swayam.research.store import HistoryStore  # noqa: E402

TRADES_SUBPATH = Path("02 - Projects") / "Trading" / "00 - Reference" / "Historical Swing Trades"


def find_trades_folder() -> Path:
    base = Path(settings.vault_path)
    folder = base / TRADES_SUBPATH
    if folder.exists():
        return folder
    raise SystemExit(
        f"Could not find the historical swing trades at {folder}. "
        "Check VAULT_PATH points at G:\\My Drive\\Second Brain."
    )


def load_eod(store: HistoryStore) -> pd.DataFrame:
    files = sorted((store.root / "options_eod").glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    frame = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    return frame


def coverage_for(trade: HistoricalTrade, eod: pd.DataFrame) -> dict[str, object]:
    """Whether the price data holds the strikes this trade used, on its days."""
    if eod.empty or trade.entry_date is None:
        return {"entry_day_rows": 0, "strikes_found": 0, "strikes_wanted": len(trade.strikes)}

    wanted = set(trade.strikes)
    on_entry = eod[eod["trade_date"] == trade.entry_date]
    found = wanted & set(on_entry["strike"].unique())

    last = trade.last_exit_date or trade.exit_date
    on_exit = eod[eod["trade_date"] == last] if last else eod.iloc[0:0]
    found_exit = wanted & set(on_exit["strike"].unique())

    expiries = sorted(set(on_entry[on_entry["strike"].isin(wanted)]["expiry_date"]))
    return {
        "entry_day_rows": len(on_entry),
        "strikes_wanted": len(wanted),
        "strikes_found": len(found),
        "strikes_found_at_exit": len(found_exit),
        "expiries_available": len(expiries),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", help="Also write the table to this file.")
    parser.add_argument("--root", help="History root. Defaults to data/history.")
    args = parser.parse_args()

    folder = find_trades_folder()
    trades = load_all(folder)
    store = HistoryStore(Path(args.root) if args.root else None)
    eod = load_eod(store)

    print(f"\nHis historical swing trades, read from {folder}")
    print("=" * 78)
    print(f"  notes found            {len(trades)}")
    wins = sum(1 for t in trades if (t.result or "").lower() == "win")
    net = sum(t.pnl_rupees or 0 for t in trades)
    print(f"  wins / losses          {wins} / {len(trades) - wins}")
    print(f"  net profit and loss    ₹{net:,.0f}")
    print(f"  calendars among them   {sum(1 for t in trades if t.is_calendar)}")
    print(f"  legs recorded          {sum(len(t.legs) for t in trades)}")
    print(f"  adjustments recorded   {sum(len(t.adjustments) for t in trades)}")
    print(f"  booked exits recorded  {sum(len(t.exits) for t in trades)}")
    if eod.empty:
        print("\n  NO END-OF-DAY OPTION DATA ON DISK YET, so coverage cannot be checked.")
    else:
        print(f"  end-of-day rows held   {len(eod):,} "
              f"({eod['trade_date'].min()} to {eod['trade_date'].max()})")

    rows = []
    print("\n" + "-" * 78)
    print(f"  {'#':>3}  {'entry':<11}{'exit':<11}{'strategy':<28}{'P&L':>10}  data")
    print("-" * 78)
    for trade in trades:
        cover = coverage_for(trade, eod)
        if eod.empty:
            state = "not checked"
        elif cover["strikes_wanted"] == 0:
            state = "no strikes in note"
        elif cover["strikes_found"] == cover["strikes_wanted"]:
            state = f"all {cover['strikes_wanted']} strikes"
        elif cover["entry_day_rows"] == 0:
            state = "NO DATA that day"
        else:
            state = f"{cover['strikes_found']}/{cover['strikes_wanted']} strikes"
        print(f"  {trade.trade_id:>3}  {str(trade.entry_date):<11}{str(trade.exit_date):<11}"
              f"{trade.strategy[:27]:<28}{(trade.pnl_rupees or 0):>10,.0f}  {state}")
        rows.append({
            "trade_id": trade.trade_id, "entry_date": trade.entry_date,
            "exit_date": trade.exit_date, "last_booked_exit": trade.last_exit_date,
            "strategy": trade.strategy, "result": trade.result,
            "pnl_rupees": trade.pnl_rupees, "is_calendar": trade.is_calendar,
            "legs": len(trade.legs), "adjustments": len(trade.adjustments),
            "exits": len(trade.exits), "strikes": len(trade.strikes),
            "problems": "; ".join(trade.problems()), **cover,
        })

    print("-" * 78)

    flawed = [(t, t.problems()) for t in trades if t.problems()]
    print(f"\n  NOTES THAT WOULD MISLEAD A BACKTESTER: {len(flawed)} of {len(trades)}")
    if flawed:
        for trade, problems in flawed:
            print(f"    Trade-{trade.trade_id:02d}: {'; '.join(problems)}")
        print("\n    These are HIS records. They are reported, never corrected here.")

    calendars = [t for t in trades if t.is_calendar]
    print(f"\n  THE EXPIRY PROBLEM, and it is the big one.")
    print(f"    Not one note records an expiry date. Not on the opening legs, not on")
    print(f"    the adjustments, not on the exits.")
    print(f"    For a vertical spread that is recoverable: both legs share the next")
    print(f"    weekly expiry.")
    print(f"    For a CALENDAR it is the whole trade. Trade-07 sells the 18700 call")
    print(f"    and buys the 18700 call. Same strike. The only thing separating them")
    print(f"    is an expiry that was never written down.")
    print(f"    {len(calendars)} of {len(trades)} trades are calendars: "
          f"{', '.join(f'{t.trade_id:02d}' for t in calendars)}")

    if args.csv:
        pd.DataFrame(rows).to_csv(args.csv, index=False)
        print(f"\n  Table written to {args.csv}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
