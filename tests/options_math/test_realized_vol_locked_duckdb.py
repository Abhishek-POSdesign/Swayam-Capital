"""
A locked or absent DuckDB file can never fail the rule check.

Live evidence, 2026-09-08: two Gunicorn workers, one exclusive DuckDB lock,
/api/strategy/validate answering 200, 500, 200, 500. The Supabase fallback
was correct and unreachable because it sat after the line that raised.
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from swayam.options_math import realized_vol as rv


class LockedDB:
    """Stands in for LocalDB when another worker holds the file lock."""

    def get_connection(self):
        raise RuntimeError(
            'IO Error: Could not set lock on file "/app/data/options_cache.duckdb": '
            "Conflicting lock is held in /usr/local/bin/python3.11 (PID 2)"
        )


def _supabase_rows(n=20, start=date(2026, 8, 1)):
    rows = []
    d = start
    price = 24500.0
    for i in range(n):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        price += (-1) ** i * (30 + i)
        rows.append({"trade_date": d.isoformat(), "close": price})
        d += timedelta(days=1)
    rows.reverse()  # the query orders newest first
    return rows


def test_locked_duckdb_falls_through_to_supabase_and_returns_a_real_vol():
    cloud = MagicMock()
    cloud.url, cloud.key = "https://x.supabase.co", "key"
    cloud.client.table.return_value.select.return_value.eq.return_value.lte.return_value \
        .order.return_value.limit.return_value.execute.return_value.data = _supabase_rows()

    with patch.object(rv, "local_db", LockedDB()), patch("swayam.db.db", cloud):
        vol = rv.compute_realized_vol(symbol="NIFTY", as_of_date=date(2026, 9, 1), window_days=20)

    assert 0.01 < vol < 1.0
    cloud.client.table.assert_called_with("swayam_nifty_daily_bars")


def test_locked_duckdb_and_no_supabase_says_why_instead_of_crashing_on_the_lock():
    cloud = MagicMock()
    cloud.url, cloud.key = "", ""

    with patch.object(rv, "local_db", LockedDB()), patch("swayam.db.db", cloud):
        with pytest.raises(rv.HistoricalDataUnavailableError) as exc:
            rv.compute_realized_vol(symbol="NIFTY", as_of_date=date(2026, 9, 1), window_days=20)

    msg = str(exc.value)
    assert "Could not set lock" in msg
    assert "Supabase" in msg


def test_locked_duckdb_with_too_few_supabase_rows_is_insufficient_history():
    cloud = MagicMock()
    cloud.url, cloud.key = "https://x.supabase.co", "key"
    cloud.client.table.return_value.select.return_value.eq.return_value.lte.return_value \
        .order.return_value.limit.return_value.execute.return_value.data = _supabase_rows(8)

    with patch.object(rv, "local_db", LockedDB()), patch("swayam.db.db", cloud):
        with pytest.raises(rv.InsufficientHistoryError) as exc:
            rv.compute_realized_vol(symbol="NIFTY", as_of_date=date(2026, 9, 1), window_days=20)
    assert exc.value.available == 8


def test_an_explicitly_supplied_database_that_cannot_open_is_still_an_error():
    """Local development passes its own LocalDB; a broken one must not be papered over."""
    with pytest.raises(rv.HistoricalDataUnavailableError):
        rv.compute_realized_vol(symbol="NIFTY", as_of_date=date(2026, 9, 1), window_days=20, db=LockedDB())
