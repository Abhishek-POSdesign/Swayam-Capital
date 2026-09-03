"""
Unit tests for GCS to DuckDB options ingest script.
"""

import argparse
from datetime import date, datetime, timezone
import io
from pathlib import Path
from unittest.mock import MagicMock
import pandas as pd
import pytest

import sys
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from ingest_gcs_to_duckdb import ingest_date, parse_dates_arg
from swayam.local_db import LocalDB


def test_parse_dates_arg_single():
    args = argparse.Namespace(date="2026-09-08", date_range=None)
    dates = parse_dates_arg(args)
    assert dates == [date(2026, 9, 8)]


def test_parse_dates_arg_range():
    args = argparse.Namespace(date=None, date_range="2026-09-08:2026-09-10")
    dates = parse_dates_arg(args)
    assert dates == [date(2026, 9, 8), date(2026, 9, 9), date(2026, 9, 10)]


def test_ingest_date_inserts_and_is_idempotent(tmp_path):
    # Setup temporary DuckDB
    db_path = tmp_path / "test_options.duckdb"
    local_db = LocalDB(db_path=db_path)

    # Create dummy snapshot DataFrame
    now_utc = datetime(2026, 9, 8, 9, 30, 0, tzinfo=timezone.utc)
    sample_data = {
        "snapshot_time_utc": [now_utc, now_utc],
        "trade_date": [date(2026, 9, 8), date(2026, 9, 8)],
        "symbol": ["NSE:NIFTY26SEP24850CE", "NSE:NIFTY26SEP24850PE"],
        "underlying": ["NIFTY", "NIFTY"],
        "expiry_date": [date(2026, 9, 24), date(2026, 9, 24)],
        "strike": [24850.0, 24850.0],
        "option_type": ["CE", "PE"],
        "open": [110.0, 90.0],
        "high": [125.0, 105.0],
        "low": [105.0, 85.0],
        "close": [120.0, 95.0],
        "settle_price": [100.0, 80.0],
        "volume": [1000, 800],
        "turnover_inr": [0.0, 0.0],
        "open_interest": [50000, 40000],
        "change_in_oi": [1200, -500],
        "underlying_spot": [24850.0, 24850.0],
        "bid": [119.5, 94.5],
        "ask": [120.5, 95.5],
        "iv": [0.14, 0.15],
        "delta": [0.52, -0.48],
        "gamma": [0.0012, 0.0012],
        "theta": [-6.5, -6.2],
        "vega": [14.0, 14.1],
    }
    df = pd.DataFrame(sample_data)
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    parquet_bytes = buf.getvalue()

    # Mock storage client and blob
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    mock_blob.exists.return_value = True
    mock_blob.name = "2026/09/08/nifty_chain.parquet"
    mock_blob.size = len(parquet_bytes)
    mock_blob.download_as_bytes.return_value = parquet_bytes

    # 1. First Ingest Run
    count_1 = ingest_date(date(2026, 9, 8), mock_client, local_db)
    assert count_1 == 2
    assert local_db.get_row_count("options_history") == 2

    # Verify ingest_log was written
    conn = local_db.get_connection()
    log_rows = conn.execute("SELECT * FROM ingest_log").fetchall()
    assert len(log_rows) == 1
    assert log_rows[0][0] == date(2026, 9, 8)
    assert log_rows[0][1] == 2

    # 2. Second Ingest Run (Simulating re-running the same date)
    count_2 = ingest_date(date(2026, 9, 8), mock_client, local_db)
    assert count_2 == 2

    # CRITICAL: Due to natural key idempotency, total rows must still be 2, NOT 4!
    assert local_db.get_row_count("options_history") == 2
