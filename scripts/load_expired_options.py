"""Downloads minute-by-minute prices for expired NIFTY option contracts.

This is what lets a backtest price a real structure at 2 pm on a real day, which
end-of-day data cannot do. It is free, it comes from the FYERS account he
already has, and it reaches back to February 2024.

    .\\.venv\\Scripts\\python.exe scripts\\load_expired_options.py --plan
    .\\.venv\\Scripts\\python.exe scripts\\load_expired_options.py --from 2026-01-01
    .\\.venv\\Scripts\\python.exe scripts\\load_expired_options.py --status

Read this before running it
---------------------------
It is long. Roughly a hundred and thirty expiries, each with three to five
hundred contracts. Expect hours, and expect to be interrupted, which is fine:
every expiry is recorded in a manifest as it completes and a second run picks up
where the first stopped.

It shares the FYERS request budget with the live desk, so it refuses to start
inside his trading window unless forced. Run it at night.

`--near N` limits each expiry to the N strikes either side of where NIFTY was,
which is the difference between a download of hours and one of days. The full
chain is available; ask for it deliberately with a large N.

What the candles contain, tested rather than assumed
----------------------------------------------------
Six values: time, open, high, low, close, volume. There is no open interest, no
implied volatility, no Greeks and no bid or ask, whatever the `greeks` flag is
set to. Implied volatility and Greeks are computed afterwards from the NIFTY
level, exactly as the live recorder does.

Nothing is written to the database or the vault.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import logging
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
from swayam.research.contracts import Contract, nearest_strikes, parse_many  # noqa: E402
from swayam.research.fyers_history import (  # noqa: E402
    FyersHistory,
    FyersHistoryError,
    in_his_trading_window,
)
from swayam.research.store import HistoryStore  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("expired-options")

UNDERLYING = "NSE:NIFTY50-INDEX"
PARTS = ("options_1m",)
# Bisected against the live API on 2026-09-09: 29 Feb 2024 had candles, and
# 25 Jan 2024 and everything earlier answered `no_data`.
# RE-PROBED 2026-09-13: FYERS has since backfilled. Full minute candles came
# back for every expiry tested, 2019-12-26, 2020-12-31, 2021-06-24, 2021-12-30,
# 2022-01-06, 2022-06-30, 2022-12-29, 2023-03-29, 2023-09-28, 2023-12-28,
# 2024-01-18 and 2024-01-25. The floor is now at least December 2019.
# The default starts at HIS window, 2022-01-01, not at FYERS' floor: the market
# before and after Corona are different markets (PLAN 2.16.2).
EARLIEST_EXPIRY = date(2022, 1, 1)
# How far before expiry a contract is worth asking for. His swings run days to
# weeks and his calendars use the following month, so six weeks covers both.
LOOKBACK_DAYS = 45
# The expiry-dates endpoint refuses a span much over 180 days with
# "Invalid input". Measured against the live API: 180 is accepted, 181 is
# refused, 365 is refused. 120 leaves room and costs only a few more calls.
EXPIRY_LIST_WINDOW_DAYS = 120

def index_close_near(index_daily: pd.DataFrame, when: date) -> float | None:
    """Where NIFTY was on the last trading day at or before `when`."""
    if index_daily.empty:
        return None
    earlier = index_daily[index_daily["day"] <= when]
    if earlier.empty:
        return None
    return float(earlier.iloc[-1]["close"])


def load_index_daily(store: HistoryStore) -> pd.DataFrame:
    path = store.root / "nifty" / "1d" / "all.parquet"
    if not path.exists():
        return pd.DataFrame(columns=["day", "close"])
    frame = pd.read_parquet(path)
    frame["day"] = frame["bar_start_utc"].dt.tz_convert("Asia/Kolkata").dt.date
    return frame[["day", "close"]].sort_values("day").reset_index(drop=True)


def choose_contracts(
    contracts: list[str], expiry: date, centre: float | None, near: int
) -> tuple[list[Contract], list[str]]:
    """The contracts worth fetching, and the names that could not be read.

    A full expiry carries three to five hundred strikes, most of which never
    traded and none of which he would have used. `near` keeps the ones around
    where the index actually was.

    The parse is anchored to the expiry rather than pattern-matched off the end
    of the name. Doing it the lazy way read `NIFTY2690823450CE` as strike
    823,450, chose sixty-two contracts nobody had ever traded, and reported zero
    rows without an error. See `swayam/research/contracts.py`.

    Whether the expiry is a monthly one is deliberately NOT asserted here. It
    can only be known from every expiry in that month, and the current month's
    monthly has not expired yet, so it cannot be listed. FYERS returns contracts
    for exactly the expiry asked for, so the extra check buys nothing; the guard
    that matters is the caller refusing an expiry whose names it mostly cannot
    read.
    """
    parsed, rejected = parse_many(contracts, expiry)
    if centre is None:
        return sorted(parsed, key=lambda c: (c.strike, c.option_type)), rejected
    return nearest_strikes(parsed, centre, near), rejected


def candles_to_frame(
    candles: list[list[float]], *, symbol: str, expiry: date, strike: float, option_type: str
) -> pd.DataFrame:
    frame = pd.DataFrame(
        candles, columns=["epoch", "open", "high", "low", "close", "volume"]
    )
    frame["bar_start_utc"] = pd.to_datetime(frame["epoch"], unit="s", utc=True)
    frame["symbol"] = symbol
    frame["underlying"] = "NIFTY"
    frame["expiry_date"] = expiry
    frame["strike"] = float(strike)
    frame["option_type"] = option_type
    frame["volume"] = frame["volume"].astype("int64")
    frame["source"] = "fyers_expired"
    return frame[[
        "bar_start_utc", "symbol", "underlying", "expiry_date", "strike",
        "option_type", "open", "high", "low", "close", "volume", "source",
    ]]


def latest_listable(end: date) -> date:
    """The most recent date the expired endpoints will accept as a range end.

    They serve contracts that have EXPIRED, so a range reaching today is refused
    with "Invalid input". Measured against the live API on 2026-09-10: a range
    ending today is refused, one ending yesterday is accepted. Today's own
    contracts have not expired anyway, so nothing is lost.
    """
    return min(end, date.today() - timedelta(days=1))


def list_expiries(client: FyersHistory, start: date, end: date) -> list[date]:
    """Every option expiry FYERS lists in the span, oldest first.

    A window it refuses is logged and skipped rather than allowed to end the
    whole download. Losing one window costs a few expiries; crashing costs the
    hours already spent.
    """
    found: list[date] = []
    cursor = start
    stop = latest_listable(end)
    while cursor <= stop:
        window_end = min(cursor + timedelta(days=EXPIRY_LIST_WINDOW_DAYS - 1), stop)
        try:
            listed = client.expired_expiry_dates(UNDERLYING, cursor, window_end)
        except FyersHistoryError as exc:
            logger.warning("  FYERS would not list %s to %s: %s", cursor, window_end, exc)
            cursor = window_end + timedelta(days=1)
            continue
        for text in listed.get("options") or []:
            try:
                parsed = date.fromisoformat(text)
            except ValueError:
                continue
            if start <= parsed <= stop:
                found.append(parsed)
        cursor = window_end + timedelta(days=1)
    return sorted(set(found))


def download(
    client: FyersHistory,
    store: HistoryStore,
    start: date,
    end: date,
    near: int,
    resolution: str = "1",
    force: bool = False,
) -> int:
    index_daily = load_index_daily(store)
    if index_daily.empty:
        logger.warning(
            "No NIFTY daily history, so strikes cannot be centred on where the index "
            "was. Run scripts/load_nifty_history.py --what 1d first, or pass --near 0 "
            "to take every strike."
        )

    logger.info("Asking FYERS which expiries it lists between %s and %s...", start, end)
    expiries = list_expiries(client, start, end)
    logger.info("%d expiries to work through.\n", len(expiries))

    total_rows = 0
    for position, expiry in enumerate(expiries, 1):
        key = f"{expiry.isoformat()}:near{near}:res{resolution}"
        if not force and store.is_done(*PARTS, key=key):
            logger.info("[%d/%d] %s already held.", position, len(expiries), expiry)
            continue

        try:
            contracts = client.expired_contracts(UNDERLYING, expiry)
        except FyersHistoryError as exc:
            logger.error("[%d/%d] %s could not list contracts: %s", position, len(expiries), expiry, exc)
            if "token" in str(exc).lower():
                return total_rows
            continue

        centre = index_close_near(index_daily, expiry)
        wanted, unreadable = choose_contracts(contracts, expiry, centre, near)
        range_from = expiry - timedelta(days=LOOKBACK_DAYS)
        logger.info(
            "[%d/%d] %s  %d listed, %d wanted around %s%s",
            position, len(expiries), expiry, len(contracts), len(wanted),
            f"{centre:,.0f}" if centre else "the whole chain",
            f", {len(unreadable)} names unreadable" if unreadable else "",
        )
        if unreadable and len(unreadable) > len(contracts) // 2:
            # More than half the chain unreadable means the naming changed, not
            # that the chain was small. Say so rather than record a thin expiry.
            logger.error(
                "    %d of %d contract names could not be read for %s. Sample: %s. "
                "The contract naming may have changed; not recording this expiry.",
                len(unreadable), len(contracts), expiry, unreadable[:3],
            )
            continue

        rows_here = empty_here = 0
        frames: list[pd.DataFrame] = []
        for contract in wanted:
            symbol, strike, option_type = contract.symbol, contract.strike, contract.option_type
            try:
                candles = client.expired_candles(symbol, resolution, range_from, expiry)
            except FyersHistoryError as exc:
                logger.warning("    %s failed: %s", symbol, str(exc)[:100])
                if "token" in str(exc).lower():
                    _flush(store, frames, expiry)
                    return total_rows + rows_here
                continue
            if not candles:
                empty_here += 1
                continue
            frames.append(
                candles_to_frame(
                    candles, symbol=symbol, expiry=expiry,
                    strike=strike, option_type=option_type,
                )
            )
            rows_here += len(candles)

        added = _flush(store, frames, expiry)
        total_rows += added
        store.record(
            *PARTS, key=key,
            entry={"contracts_listed": len(contracts), "contracts_fetched": len(wanted),
                   "contracts_unreadable": len(unreadable),
                   "contracts_empty": empty_here, "rows": rows_here, "added": added},
        )
        logger.info(
            "         %s rows, %d new, %d contracts had nothing. Running total %s.",
            f"{rows_here:,}", added, empty_here, f"{total_rows:,}",
        )

    return total_rows


def _flush(store: HistoryStore, frames: list[pd.DataFrame], expiry: date) -> int:
    """Writes one expiry's contracts to its own file, then forgets them."""
    if not frames:
        return 0
    frame = pd.concat(frames, ignore_index=True)
    result = store.write_parquet(
        frame, *PARTS, f"{expiry.year}", f"{expiry.isoformat()}.parquet",
        dedupe_on=["symbol", "bar_start_utc"],
        sort_on=["symbol", "bar_start_utc"],
    )
    frames.clear()
    return result.rows_added


def report(store: HistoryStore) -> None:
    files = sorted((store.root / "options_1m").rglob("*.parquet"))
    if not files:
        print("Nothing downloaded yet.")
        return
    print("\nMinute-level expired NIFTY options held locally")
    print("-" * 68)
    rows = size = 0
    for path in files:
        frame = pd.read_parquet(path, columns=["symbol"])
        rows += len(frame)
        size += path.stat().st_size
    manifest = store.read_manifest(*PARTS).get("entries") or {}
    print(f"  expiries downloaded  {len(files):>8,}")
    print(f"  minute bars          {rows:>8,}")
    print(f"  on disk              {size / 1_048_576:>8.1f} MB")
    if files:
        print(f"  earliest expiry      {files[0].stem}")
        print(f"  latest expiry        {files[-1].stem}")
    print(f"  manifest entries     {len(manifest):>8,}")
    print("-" * 68)


def plan(client: FyersHistory, store: HistoryStore, start: date, end: date, near: int) -> int:
    """Says how big the job is before anyone starts it."""
    listed = list_expiries(client, start, end)
    done = len(store.read_manifest(*PARTS).get("entries") or {})
    per_expiry = near * 2 * 2 + 2 if near else 400
    calls = len(listed) * (1 + per_expiry)

    print("\nWhat this download would do")
    print("=" * 68)
    print(f"  expiries between {start} and {end}   {len(listed):>6,}")
    print(f"  already held                            {done:>6,}")
    print(f"  contracts fetched per expiry            {per_expiry:>6,}   (--near {near})")
    print(f"  FYERS requests, roughly                 {calls:>6,}")
    print(f"  at about one a second, roughly          {calls / 3600:>6.1f} hours")
    print("=" * 68)
    print("  It resumes if interrupted. It refuses to run inside his trading window.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="start", help=f"YYYY-MM-DD. Default {EARLIEST_EXPIRY}.")
    parser.add_argument("--to", dest="end", help="YYYY-MM-DD. Default today.")
    parser.add_argument("--near", type=int, default=15,
                        help="Strikes either side of the index. 0 takes the whole chain. Default 15.")
    parser.add_argument("--resolution", default="1", help="1, 5, 15 or D. Default 1.")
    parser.add_argument("--root")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--plan", action="store_true", help="Say how big the job is and stop.")
    args = parser.parse_args()

    store = HistoryStore(Path(args.root) if args.root else None)
    if args.status:
        report(store)
        return 0

    if in_his_trading_window() and not args.force:
        logger.error(
            "It is inside his trading window. This download shares the FYERS request "
            "budget with the live desk and would blank the prices on his screen. "
            "Run it at night, or pass --force if you are certain."
        )
        return 2

    token = settings.fyers_access_token
    if not token:
        logger.error("No FYERS access token. Run .\\Refresh-Token.ps1 first.")
        return 2

    client = FyersHistory(app_id=settings.fyers_app_id, access_token=token)
    start = date.fromisoformat(args.start) if args.start else EARLIEST_EXPIRY
    end = date.fromisoformat(args.end) if args.end else date.today()

    if args.plan:
        return plan(client, store, max(start, EARLIEST_EXPIRY), end, args.near)

    started = datetime.now(timezone.utc)
    total = download(
        client, store, max(start, EARLIEST_EXPIRY), end,
        near=args.near, resolution=args.resolution, force=args.force,
    )
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    logger.info(
        "\nDone for now. %s new bars in %.0f minutes, %d FYERS calls, %d refusals.",
        f"{total:,}", elapsed / 60, client.calls, client.refusals,
    )
    report(store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
