"""
Unit tests for Swayam Capital Bhavcopy & DuckDB Ingestion.
"""

from datetime import date
from pathlib import Path
import pandas as pd
import pytest
from swayam.bhavcopy import BhavcopyDownloader
from swayam.local_db import LocalDB


def test_get_bhavcopy_url_returns_standard_candidates() -> None:
    downloader = BhavcopyDownloader()
    d = date(2026, 8, 28)
    urls = downloader.get_bhavcopy_url(d)
    assert len(urls) >= 2
    assert any("20260828" in u for u in urls)


def test_duckdb_schema_initialization_and_dataframe_insert(tmp_path: Path) -> None:
    test_db = LocalDB(db_path=tmp_path / "test_cache.duckdb")
    assert test_db.get_table_count() >= 1

    # Create dummy options dataframe
    dummy_data = pd.DataFrame([{
        "trade_date": date(2026, 8, 28),
        "symbol": "NIFTY26AUG24500CE",
        "underlying": "NIFTY",
        "expiry_date": date(2026, 8, 28),
        "strike": 24500.0,
        "option_type": "CE",
        "open": 100.0,
        "high": 150.0,
        "low": 90.0,
        "close": 120.0,
        "settle_price": 120.0,
        "volume": 5000,
        "turnover_inr": 600000.0,
        "open_interest": 20000,
        "change_in_oi": 1500,
        "underlying_spot": 24800.0,
    }])

    rows_inserted = test_db.insert_options_df(dummy_data)
    assert rows_inserted == 1
    assert test_db.get_row_count() == 1
    test_db.close()
