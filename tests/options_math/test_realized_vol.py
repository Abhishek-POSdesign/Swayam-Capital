"""
Unit tests for realized volatility computation engine.
"""

from datetime import date, timedelta
import math
import numpy as np
import pytest

from swayam.local_db import LocalDB
from swayam.options_math.realized_vol import (
    compute_realized_vol,
    daily_sigma_from_annualized,
    HistoricalDataUnavailableError,
    InsufficientHistoryError,
)


def _setup_test_db_with_bars(tmp_path, closes: list[float], start_date: date = date(2026, 8, 1)) -> LocalDB:
    db = LocalDB(db_path=tmp_path / "test_vol.duckdb")
    conn = db.get_connection()
    conn.execute("""
        CREATE TABLE nifty_daily_bars (
            trade_date DATE NOT NULL,
            symbol TEXT NOT NULL,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE NOT NULL,
            volume BIGINT,
            PRIMARY KEY (trade_date, symbol)
        );
    """)

    curr_date = start_date
    for c in closes:
        while curr_date.weekday() >= 5:  # skip weekends
            curr_date += timedelta(days=1)
        conn.execute(
            "INSERT INTO nifty_daily_bars VALUES (?, 'NIFTY', ?, ?, ?, ?, 100000);",
            [curr_date, c, c + 20, c - 20, c],
        )
        curr_date += timedelta(days=1)

    return db


def test_compute_realized_vol_happy_path(tmp_path):
    # 20 bars with realistic ~0.5% - 1.0% daily fluctuations around 24,500
    base = 24500.0
    fluctuations = [
        0, 120, -80, 150, -60, 40, -110, 90, -70, 130,
        -50, 80, -100, 60, -40, 110, -90, 70, -30, 50,
    ]
    closes = [base + f for f in fluctuations]
    db = _setup_test_db_with_bars(tmp_path, closes, start_date=date(2026, 8, 1))

    # Reference date is the last bar's date
    conn = db.get_connection()
    last_date = conn.execute("SELECT MAX(trade_date) FROM nifty_daily_bars;").fetchone()[0]

    vol = compute_realized_vol(symbol="NIFTY", as_of_date=last_date, window_days=20, db=db)
    assert 0.05 <= vol <= 0.30  # Sensible index annualized volatility
    assert daily_sigma_from_annualized(vol) == pytest.approx(vol / math.sqrt(252.0), abs=1e-9)


def test_compute_realized_vol_insufficient_history(tmp_path):
    # Only 10 bars available when window_days=20
    closes = [24500.0 + i * 10 for i in range(10)]
    db = _setup_test_db_with_bars(tmp_path, closes)

    with pytest.raises(InsufficientHistoryError) as exc_info:
        compute_realized_vol(symbol="NIFTY", as_of_date=date(2026, 9, 1), window_days=20, db=db)

    err = exc_info.value
    assert err.needed == 20
    assert err.available == 10
    assert "backfill_bhavcopy.py" in err.backfill_command


def test_compute_realized_vol_zero_vol_edge_case(tmp_path):
    # 20 identical closes
    closes = [24800.0] * 20
    db = _setup_test_db_with_bars(tmp_path, closes)
    conn = db.get_connection()
    last_date = conn.execute("SELECT MAX(trade_date) FROM nifty_daily_bars;").fetchone()[0]

    vol = compute_realized_vol(symbol="NIFTY", as_of_date=last_date, window_days=20, db=db)
    assert vol == 0.0
    assert daily_sigma_from_annualized(vol) == 0.0


def test_compute_realized_vol_cache_hit(tmp_path):
    closes = [24000.0 + i * 15 for i in range(20)]
    db = _setup_test_db_with_bars(tmp_path, closes)
    conn = db.get_connection()
    last_date = conn.execute("SELECT MAX(trade_date) FROM nifty_daily_bars;").fetchone()[0]

    # First call: computes and writes to cache
    vol1 = compute_realized_vol(symbol="NIFTY", as_of_date=last_date, window_days=20, db=db)

    # Corrupt or drop nifty_daily_bars table to prove second call reads directly from cache
    conn.execute("DROP TABLE nifty_daily_bars;")

    vol2 = compute_realized_vol(symbol="NIFTY", as_of_date=last_date, window_days=20, db=db)
    assert vol1 == vol2


def test_compute_realized_vol_missing_table(tmp_path):
    db = LocalDB(db_path=tmp_path / "empty.duckdb")
    # Table nifty_daily_bars does not exist

    with pytest.raises(HistoricalDataUnavailableError) as exc_info:
        compute_realized_vol(symbol="NIFTY", as_of_date=date(2026, 9, 1), window_days=20, db=db)
    assert "nifty_daily_bars" in str(exc_info.value)


def test_compute_realized_vol_known_sequence(tmp_path):
    # Exact 5-bar sequence
    closes = [100.0, 105.0, 102.0, 108.0, 104.0]
    db = _setup_test_db_with_bars(tmp_path, closes, start_date=date(2026, 8, 1))
    conn = db.get_connection()
    last_date = conn.execute("SELECT MAX(trade_date) FROM nifty_daily_bars;").fetchone()[0]

    # Hand computation:
    log_returns = [
        math.log(105.0 / 100.0),
        math.log(102.0 / 105.0),
        math.log(108.0 / 102.0),
        math.log(104.0 / 108.0),
    ]
    expected_std = np.std(log_returns, ddof=1)
    expected_ann_vol = expected_std * math.sqrt(252.0)

    vol = compute_realized_vol(symbol="NIFTY", as_of_date=last_date, window_days=5, db=db)
    assert vol == pytest.approx(expected_ann_vol, rel=1e-6)
