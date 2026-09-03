"""
Unit tests for Swayam Options Recorder Cloud Function.
"""

from datetime import date, datetime, timezone
import io
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo
import pandas as pd
import pytest

import sys
from pathlib import Path

# Add cloud/recorder to sys.path for testing recorder modules
RECORDER_DIR = Path(__file__).resolve().parent.parent.parent / "cloud" / "recorder"
sys.path.insert(0, str(RECORDER_DIR))

from fyers_recorder import append_and_dedupe_to_gcs, fetch_options_snapshot, is_market_open
from main import record_snapshot


def test_is_market_open_weekday_during_hours():
    tz = ZoneInfo("Asia/Kolkata")
    # Wednesday at 11:30 AM IST
    dt = datetime(2026, 9, 9, 11, 30, 0, tzinfo=tz)
    is_open, reason = is_market_open(dt)
    assert is_open is True
    assert "Market open" in reason


def test_is_market_open_weekend():
    tz = ZoneInfo("Asia/Kolkata")
    # Saturday at 11:30 AM IST
    dt = datetime(2026, 9, 12, 11, 30, 0, tzinfo=tz)
    is_open, reason = is_market_open(dt)
    assert is_open is False
    assert "Weekend" in reason


def test_is_market_open_before_open():
    tz = ZoneInfo("Asia/Kolkata")
    # Monday at 08:30 AM IST
    dt = datetime(2026, 9, 7, 8, 30, 0, tzinfo=tz)
    is_open, reason = is_market_open(dt)
    assert is_open is False
    assert "before market open" in reason


def test_is_market_open_after_close():
    tz = ZoneInfo("Asia/Kolkata")
    # Monday at 16:00 PM IST
    dt = datetime(2026, 9, 7, 16, 0, 0, tzinfo=tz)
    is_open, reason = is_market_open(dt)
    assert is_open is False
    assert "after market close" in reason


def test_fetch_options_snapshot_parsing(monkeypatch):
    mock_fyers_instance = MagicMock()
    mock_fyers_instance.optionchain.return_value = {
        "s": "ok",
        "data": {
            "underlyingValue": 24850.50,
            "optionsChain": [
                {
                    "strike_price": 24850.0,
                    "call_symbol": "NSE:NIFTY26SEP24850CE",
                    "call_ltp": 120.50,
                    "call_volume": 50000,
                    "call_oi": 1500000,
                    "call_pdoi": 25000,
                    "call_iv": 0.142,
                    "put_symbol": "NSE:NIFTY26SEP24850PE",
                    "put_ltp": 95.25,
                    "put_volume": 42000,
                    "put_oi": 1200000,
                    "put_pdoi": -15000,
                    "put_iv": 0.148,
                }
            ],
        },
    }

    with patch("fyers_recorder.fyersModel.FyersModel", return_value=mock_fyers_instance):
        df = fetch_options_snapshot(access_token="fake_token")
        assert len(df) == 2
        ce_row = df[df["option_type"] == "CE"].iloc[0]
        pe_row = df[df["option_type"] == "PE"].iloc[0]

        assert ce_row["strike"] == 24850.0
        assert ce_row["close"] == 120.50
        assert ce_row["open_interest"] == 1500000
        assert ce_row["underlying_spot"] == 24850.50

        assert pe_row["strike"] == 24850.0
        assert pe_row["close"] == 95.25
        assert pe_row["open_interest"] == 1200000


def test_append_and_dedupe_to_gcs_idempotent():
    now_utc = datetime(2026, 9, 9, 10, 0, 0, tzinfo=timezone.utc)
    row1 = {
        "snapshot_time_utc": now_utc,
        "trade_date": date(2026, 9, 9),
        "symbol": "NSE:NIFTY26SEP24850CE",
        "underlying": "NIFTY",
        "expiry_date": date(2026, 9, 24),
        "strike": 24850.0,
        "option_type": "CE",
        "open": 100.0,
        "high": 125.0,
        "low": 95.0,
        "close": 120.0,
        "settle_price": 100.0,
        "volume": 1000,
        "turnover_inr": 0.0,
        "open_interest": 5000,
        "change_in_oi": 100,
        "underlying_spot": 24850.0,
        "bid": 119.5,
        "ask": 120.5,
        "iv": 0.14,
        "delta": 0.5,
        "gamma": 0.001,
        "theta": -5.0,
        "vega": 12.0,
    }
    df = pd.DataFrame([row1])

    # Mock storage client and blob
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    # First run: blob does not exist
    mock_blob.exists.return_value = False
    total_1 = append_and_dedupe_to_gcs(mock_client, "test-bucket", df, target_date=date(2026, 9, 9))
    assert total_1 == 1

    # Capture the uploaded parquet bytes
    uploaded_bytes = mock_blob.upload_from_string.call_args[0][0]

    # Second run (e.g. Cloud Scheduler retry): blob now exists with same snapshot
    mock_blob.exists.return_value = True
    mock_blob.download_as_bytes.return_value = uploaded_bytes

    total_2 = append_and_dedupe_to_gcs(mock_client, "test-bucket", df, target_date=date(2026, 9, 9))
    # Deduplication ensures row count remains 1, NOT 2!
    assert total_2 == 1


def test_main_record_snapshot_skips_when_closed():
    req = MagicMock()
    with patch("main.is_market_open", return_value=(False, "Market closed (Weekend)")):
        resp, status, headers = record_snapshot(req)
        assert status == 200
        assert "skipped" in resp
        assert "Weekend" in resp
