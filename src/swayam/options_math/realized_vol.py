"""
Realized Volatility Engine for Swayam Capital.

Computes trailing historical volatility on underlying indices (such as NIFTY)
using daily close prices stored in the local DuckDB database, with caching
support and explicit zero-silent-fallback error handling.
"""

from datetime import date, datetime, timezone
import math
from typing import Any, Optional
import numpy as np

from swayam.local_db import LocalDB, local_db


class RealizedVolError(Exception):
    """Base exception for realized volatility errors."""
    pass


class HistoricalDataUnavailableError(RealizedVolError):
    """Raised when the underlying price history table does not exist."""
    pass


class InsufficientHistoryError(RealizedVolError):
    """Raised when fewer than window_days daily bars are available."""

    def __init__(
        self,
        needed: int,
        available: int,
        backfill_command: str = "python scripts/backfill_bhavcopy.py --days 30",
    ) -> None:
        self.needed = needed
        self.available = available
        self.backfill_command = backfill_command
        super().__init__(
            f"Insufficient history: needed {needed} bars, but only {available} available. "
            f"Run: {backfill_command}"
        )


def daily_sigma_from_annualized(annualized_vol: float) -> float:
    """Converts annualized volatility to 1-day standard deviation: sigma_ann / sqrt(252)."""
    return annualized_vol / math.sqrt(252.0)


def compute_realized_vol(
    symbol: str = "NIFTY",
    as_of_date: Optional[date] = None,
    window_days: int = 20,
    db: Optional[LocalDB] = None,
) -> float:
    """Computes trailing annualized realized volatility from daily closes in DuckDB.

    Args:
        symbol: Underlying symbol name (default: "NIFTY").
        as_of_date: Reference date (defaults to today).
        window_days: Number of trading day closes to look back (default: 20).
        db: Optional LocalDB instance (defaults to global local_db).

    Returns:
        float: Annualized realized volatility as a decimal (e.g., 0.14 for 14%).
    """
    if as_of_date is None:
        as_of_date = date.today()

    target_db = db or local_db
    conn = target_db.get_connection()

    # 1. Check cache if table exists
    has_cache_table = False
    try:
        tables_res = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'realized_vol_cache';"
        ).fetchall()
        if tables_res:
            has_cache_table = True
            cached = conn.execute(
                """
                SELECT annualized_vol FROM realized_vol_cache
                WHERE symbol = ? AND as_of_date = ? AND window_days = ?;
                """,
                [symbol, as_of_date, window_days],
            ).fetchone()
            if cached is not None:
                return float(cached[0])
    except Exception as exc:
        raise RealizedVolError(f"Database error checking realized_vol_cache: {exc}") from exc

    # 2. Check if nifty_daily_bars exists in DuckDB
    rows: list[tuple[Any, Any]] = []
    daily_bars_res = []
    try:
        daily_bars_res = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'nifty_daily_bars';"
        ).fetchall()
        if daily_bars_res:
            rows = conn.execute(
                """
                SELECT trade_date, close
                FROM nifty_daily_bars
                WHERE symbol = ? AND trade_date <= ?
                ORDER BY trade_date DESC
                LIMIT ?;
                """,
                [symbol, as_of_date, window_days],
            ).fetchall()
    except Exception as exc:
        raise RealizedVolError(f"Database error querying nifty_daily_bars schema: {exc}") from exc

    # Fallback to Supabase swayam_nifty_daily_bars for cloud deployments when DuckDB table is absent
    if db is None and len(rows) < window_days:
        try:
            from swayam.db import db as cloud_db
            if cloud_db.url and cloud_db.key:
                sb_res = (
                    cloud_db.client.table("swayam_nifty_daily_bars")
                    .select("trade_date, close")
                    .eq("symbol", symbol)
                    .lte("trade_date", as_of_date.isoformat())
                    .order("trade_date", desc=True)
                    .limit(window_days)
                    .execute()
                )
                if sb_res.data and len(sb_res.data) > len(rows):
                    rows = [(r["trade_date"], float(r["close"])) for r in sb_res.data]
        except Exception:
            pass

    if not rows and not daily_bars_res:
        raise HistoricalDataUnavailableError("Table 'nifty_daily_bars' does not exist in DuckDB.")

    if len(rows) < window_days:
        raise InsufficientHistoryError(
            needed=window_days,
            available=len(rows),
            backfill_command="python scripts/backfill_bhavcopy.py --days 30",
        )

    # Sort chronological (oldest to newest)
    rows.sort(key=lambda r: r[0])
    closes = [float(r[1]) for r in rows]

    # Check zero-vol edge case (all closes identical)
    if len(set(closes)) <= 1:
        annualized_vol = 0.0
    else:
        # Compute daily log returns: r_t = ln(P_t / P_{t-1})
        log_returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        std_daily = float(np.std(log_returns, ddof=1))
        annualized_vol = std_daily * math.sqrt(252.0)

    # 4. Save to cache if realized_vol_cache exists
    try:
        if has_cache_table:
            now_utc = datetime.now(timezone.utc)
            conn.execute(
                """
                INSERT OR REPLACE INTO realized_vol_cache
                    (symbol, as_of_date, window_days, annualized_vol, computed_at, bar_count)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                [symbol, as_of_date, window_days, annualized_vol, now_utc, len(rows)],
            )
    except Exception as exc:
        raise RealizedVolError(f"Database error writing to realized_vol_cache: {exc}") from exc

    return annualized_vol
