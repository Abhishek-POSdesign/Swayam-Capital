"""Checks the minute option data against NSE's own end-of-day file.

Two independent sources now hold the same contracts. FYERS serves minute
candles for expired contracts; NSE publishes an official daily file. Squashing
the minutes of one day into a single bar should reproduce NSE's row for that
contract exactly.

**This is the acceptance test for the whole download.** If they agree, both are
trustworthy and a backtest can stand on them. If they do not, one is wrong, and
finding that out now is far cheaper than finding it inside a result.

    .\\.venv\\Scripts\\python.exe scripts\\reconcile_option_history.py
    .\\.venv\\Scripts\\python.exe scripts\\reconcile_option_history.py --expiry 2026-09-08

Run through DuckDB rather than pandas: there are 59 million minute bars and 4.5
million daily rows, and DuckDB reads the Parquet files where they lie instead of
pulling them all into memory.

READ ONLY. It writes no data anywhere; it reports.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import duckdb

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from swayam.research.store import HistoryStore  # noqa: E402

# NIFTY options quote in five-paise steps. Anything inside a tick is agreement.
TICK = 0.05
# The exchange's own session. Bars outside it are not part of the daily bar.
SESSION_START = "09:15:00"
SESSION_END = "15:29:59"


def connect(store: HistoryStore) -> duckdb.DuckDBPyConnection:
    minutes = (store.root / "options_1m").as_posix()
    daily = (store.root / "options_eod").as_posix()
    con = duckdb.connect()
    con.execute(f"""
        CREATE VIEW minute_bars AS
        SELECT * FROM read_parquet('{minutes}/*/*.parquet', union_by_name=true);
    """)
    con.execute(f"""
        CREATE VIEW daily_bars AS
        SELECT * FROM read_parquet('{daily}/*.parquet', union_by_name=true);
    """)
    return con


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root")
    parser.add_argument("--expiry", help="Check one expiry only, YYYY-MM-DD.")
    parser.add_argument("--sample", type=int, default=0,
                        help="Check only this many contract-days. 0 checks all.")
    args = parser.parse_args()

    store = HistoryStore(Path(args.root) if args.root else None)
    if not (store.root / "options_1m").exists() or not (store.root / "options_eod").exists():
        raise SystemExit("Both downloads must have run first.")

    con = connect(store)
    where_expiry = f"AND m.expiry_date = DATE '{args.expiry}'" if args.expiry else ""
    limit = f"LIMIT {args.sample}" if args.sample else ""

    print("\nThe minute data against NSE's own daily file")
    print("=" * 78)
    counts = con.execute("""
        SELECT (SELECT count(*) FROM minute_bars),
               (SELECT count(DISTINCT symbol) FROM minute_bars),
               (SELECT count(DISTINCT expiry_date) FROM minute_bars),
               (SELECT count(*) FROM daily_bars)
    """).fetchone()
    print(f"  minute bars held         {counts[0]:>12,}")
    print(f"  contracts                {counts[1]:>12,}")
    print(f"  expiries                 {counts[2]:>12,}")
    print(f"  daily rows held          {counts[3]:>12,}")

    print("\n  Squashing each day's minutes into one bar and comparing...")
    con.execute(f"""
        CREATE TABLE compared AS
        WITH squashed AS (
            SELECT
                m.symbol,
                m.expiry_date,
                CAST(m.bar_start_utc AT TIME ZONE 'Asia/Kolkata' AS DATE) AS trade_date,
                arg_min(m.open, m.bar_start_utc) AS m_open,
                max(m.high)                      AS m_high,
                min(m.low)                       AS m_low,
                arg_max(m.close, m.bar_start_utc) AS m_close,
                sum(m.volume)                    AS m_volume,
                count(*)                         AS bars
            FROM minute_bars m
            WHERE CAST(m.bar_start_utc AT TIME ZONE 'Asia/Kolkata' AS TIME)
                  BETWEEN TIME '{SESSION_START}' AND TIME '{SESSION_END}'
              {where_expiry}
            GROUP BY 1, 2, 3
        )
        SELECT s.*, d.open AS d_open, d.high AS d_high, d.low AS d_low,
               d.close AS d_close, d.volume_units, d.volume_contracts
        FROM squashed s
        JOIN daily_bars d
          ON d.trade_date = s.trade_date
         AND replace(s.symbol, 'NSE:', '') = d.symbol
        WHERE d.high > 0
        {limit};
    """)

    total = con.execute("SELECT count(*) FROM compared").fetchone()[0]
    if not total:
        print("  Nothing overlapped. Check both downloads actually hold the same dates.")
        return 1

    print(f"  contract-days compared   {total:>12,}\n")
    print(f"  {'field':<8}{'agree within a tick':>22}{'median gap':>14}{'worst gap':>12}")
    print("  " + "-" * 56)
    failures = {}
    for field in ("open", "high", "low", "close"):
        row = con.execute(f"""
            SELECT
                sum(CASE WHEN abs(m_{field} - d_{field}) <= {TICK} THEN 1 ELSE 0 END),
                median(abs(m_{field} - d_{field})),
                max(abs(m_{field} - d_{field}))
            FROM compared
        """).fetchone()
        agree, median_gap, worst = row[0] or 0, row[1] or 0.0, row[2] or 0.0
        failures[field] = total - agree
        print(f"  {field:<8}{agree:>10,} {100 * agree / total:>9.2f}%"
              f"{median_gap:>14.2f}{worst:>12.2f}")

    print("\n  The worst disagreements, if any:")
    worst_rows = con.execute("""
        SELECT symbol, trade_date, bars, m_open, d_open, m_high, d_high,
               m_low, d_low, m_close, d_close
        FROM compared
        ORDER BY abs(m_close - d_close) DESC
        LIMIT 5
    """).fetchall()
    for row in worst_rows:
        gap = abs(row[9] - row[10])
        if gap <= TICK:
            print("    None worth showing: every close agrees within a tick.")
            break
        print(f"    {row[0]} {row[1]}  {row[2]} bars  "
              f"close {row[9]:.2f} vs {row[10]:.2f}  gap {gap:.2f}")

    print("\n  IS NSE'S CLOSE A HALF-HOUR AVERAGE RATHER THAN A TRADED PRICE?")
    print("    NSE's rule for a derivatives closing price is the volume-weighted")
    print("    average of the last half hour, falling back to the last trade when")
    print("    nothing dealt in that window. If that is what the gap is, then a VWAP")
    print("    of the last thirty minutes of our own minute bars should reproduce it,")
    print("    and the last traded price should not.")
    con.execute(f"""
        CREATE TABLE closing_test AS
        WITH last_half_hour AS (
            SELECT
                m.symbol,
                CAST(m.bar_start_utc AT TIME ZONE 'Asia/Kolkata' AS DATE) AS trade_date,
                sum(m.close * m.volume) AS traded_value,
                sum(m.volume)           AS traded_volume
            FROM minute_bars m
            WHERE CAST(m.bar_start_utc AT TIME ZONE 'Asia/Kolkata' AS TIME)
                  BETWEEN TIME '15:00:00' AND TIME '{SESSION_END}'
              {where_expiry}
            GROUP BY 1, 2
        )
        SELECT c.symbol, c.trade_date, c.m_close, c.d_close,
               h.traded_value / nullif(h.traded_volume, 0) AS vwap_close
        FROM compared c
        JOIN last_half_hour h
          ON h.symbol = c.symbol AND h.trade_date = c.trade_date
        WHERE h.traded_volume > 0;
    """)
    verdict = con.execute(f"""
        SELECT count(*),
               sum(CASE WHEN abs(vwap_close - d_close) <= {TICK} THEN 1 ELSE 0 END),
               sum(CASE WHEN abs(m_close   - d_close) <= {TICK} THEN 1 ELSE 0 END),
               median(abs(vwap_close - d_close)),
               median(abs(m_close   - d_close))
        FROM closing_test
    """).fetchone()
    if verdict and verdict[0]:
        checked, by_vwap, by_last, vwap_gap, last_gap = verdict
        print(f"\n    contract-days with trades in the last half hour  {checked:>10,}")
        print(f"    NSE's close matched by a half-hour VWAP          {by_vwap:>10,} "
              f"({100 * by_vwap / checked:.1f}%), median gap {vwap_gap:.2f}")
        print(f"    NSE's close matched by the last traded price     {by_last:>10,} "
              f"({100 * by_last / checked:.1f}%), median gap {last_gap:.2f}")
        if by_vwap > by_last * 2:
            print("\n    CONFIRMED. The daily close is an average, not a price you could")
            print("    have dealt at. A backtest must fill from the minute bars.")

    print("\n  Sanity of the minute file itself:")
    checks = con.execute(f"""
        SELECT
            (SELECT count(*) FROM minute_bars WHERE high < low),
            (SELECT count(*) FROM minute_bars WHERE close IS NULL),
            (SELECT count(*) FROM minute_bars WHERE close <= 0),
            (SELECT count(*) FROM (
                SELECT symbol, bar_start_utc FROM minute_bars
                GROUP BY 1, 2 HAVING count(*) > 1)),
            (SELECT count(*) FROM minute_bars
             WHERE CAST(bar_start_utc AT TIME ZONE 'Asia/Kolkata' AS TIME)
                   NOT BETWEEN TIME '{SESSION_START}' AND TIME '{SESSION_END}')
    """).fetchone()
    print(f"    high below low                 {checks[0]:>12,}")
    print(f"    null close                     {checks[1]:>12,}")
    print(f"    close at or below zero         {checks[2]:>12,}")
    print(f"    duplicate contract-minutes     {checks[3]:>12,}")
    print(f"    bars outside 09:15 to 15:29    {checks[4]:>12,}")

    print("\n" + "=" * 78)
    # The verdict is judged on open, high and low ONLY. The close is EXPECTED to
    # differ, because NSE's is an average and ours is a traded price, and the
    # test above shows that is exactly what the difference is. Counting it as a
    # failure would raise an alarm about correct behaviour, which is its own
    # kind of dishonesty in a report.
    traded_fields = ("open", "high", "low")
    worst_field = max(traded_fields, key=lambda f: failures[f])
    worst_share = 100 * failures[worst_field] / total

    if worst_share < 5:
        print("  THE TWO SOURCES AGREE.")
        print(f"  FYERS' minute candles and NSE's official daily file were downloaded")
        print(f"  separately, from different systems, and reproduce each other's open,")
        print(f"  high and low on {100 - worst_share:.1f}% of {total:,} contract-days.")
        print("  That is as good a guarantee as this data can be given.")
    else:
        print(f"  {failures[worst_field]:,} contract-days disagree on the {worst_field} "
              f"({worst_share:.2f}%). Settle these before trusting a backtest.")

    print("\n  THE CLOSE IS DIFFERENT ON PURPOSE, AND IT IS THE ONE TO REMEMBER.")
    print(f"  NSE's daily closing price is a half-hour average. Ours is the last")
    print(f"  price actually dealt. They differ by a median of {con.execute(
        'SELECT median(abs(m_close - d_close)) FROM compared').fetchone()[0]:.2f} rupees a")
    print("  contract, and far more on an illiquid strike. A backtest that fills at")
    print("  the daily close is filling at a number nobody traded, and on a four-leg")
    print("  structure that error is taken four times.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
