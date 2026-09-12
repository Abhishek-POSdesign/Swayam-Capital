"""Unit tests for the Swayam Options Recorder Cloud Function.

The parsing tests that used to live here asserted a FYERS response shape that
does not exist and passed for a week while the recorder wrote zeros. They have
been replaced by `test_recorder_real_shape.py`, which drives a reply captured
from the live API. What is left here is the machinery around the parse: the
market gate, the append-and-deduplicate write, and the HTTP handler.
"""

from datetime import date, datetime, timezone
import io
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pandas as pd

RECORDER_DIR = Path(__file__).resolve().parent.parent.parent / "cloud" / "recorder"
if str(RECORDER_DIR) not in sys.path:
    sys.path.insert(0, str(RECORDER_DIR))

from fyers_recorder import append_and_dedupe_to_gcs, is_market_open, to_dataframe  # noqa: E402
from main import record_snapshot  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")


def test_is_market_open_weekday_during_hours():
    is_open, reason = is_market_open(datetime(2026, 9, 9, 11, 30, tzinfo=IST))
    assert is_open is True
    assert "Market open" in reason


def test_is_market_open_weekend():
    is_open, reason = is_market_open(datetime(2026, 9, 12, 11, 30, tzinfo=IST))
    assert is_open is False
    assert "Weekend" in reason


def test_is_market_open_before_open():
    is_open, reason = is_market_open(datetime(2026, 9, 7, 8, 30, tzinfo=IST))
    assert is_open is False
    assert "before market open" in reason


def test_is_market_open_after_close():
    is_open, reason = is_market_open(datetime(2026, 9, 7, 16, 0, tzinfo=IST))
    assert is_open is False
    assert "after market close" in reason


def _one_snapshot_row(when: datetime) -> pd.DataFrame:
    """One real row, taken from the live chain on 2026-09-09 night."""
    return to_dataframe([{
        "snapshot_time_utc": when,
        "trade_date": date(2026, 9, 9),
        "symbol": "NSE:NIFTY2691523450CE",
        "underlying": "NIFTY",
        "expiry_date": date(2026, 9, 15),
        "strike": 23450.0,
        "option_type": "CE",
        "open": None, "high": None, "low": None,
        "close": 138.5,
        "settle_price": None,
        "volume": 5529225,
        "turnover_inr": None,
        "open_interest": 2364570,
        "change_in_oi": 2318810,
        "prev_oi": 45760,
        "underlying_spot": 23431.5,
        "bid": 138.15, "ask": 139.45,
        "tte_years": 0.015496,
        "iv": 0.116357, "delta": 0.510173, "gamma": 0.001175,
        "theta": -14.16663, "vega": 11.632687,
    }])


def test_append_and_dedupe_to_gcs_idempotent():
    """A scheduler double-fire must not double the rows."""
    df = _one_snapshot_row(datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc))

    mock_client, mock_bucket, mock_blob = MagicMock(), MagicMock(), MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    mock_blob.exists.return_value = False
    assert append_and_dedupe_to_gcs(mock_client, "test-bucket", df, target_date=date(2026, 9, 9)) == 1

    uploaded_bytes = mock_blob.upload_from_string.call_args[0][0]
    mock_blob.exists.return_value = True
    mock_blob.download_as_bytes.return_value = uploaded_bytes

    assert append_and_dedupe_to_gcs(mock_client, "test-bucket", df, target_date=date(2026, 9, 9)) == 1


def test_the_next_minutes_snapshot_is_added_not_replaced():
    first = _one_snapshot_row(datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc))
    second = _one_snapshot_row(datetime(2026, 9, 9, 10, 1, tzinfo=timezone.utc))

    mock_client, mock_bucket, mock_blob = MagicMock(), MagicMock(), MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    mock_blob.exists.return_value = False
    append_and_dedupe_to_gcs(mock_client, "test-bucket", first, target_date=date(2026, 9, 9))
    mock_blob.exists.return_value = True
    mock_blob.download_as_bytes.return_value = mock_blob.upload_from_string.call_args[0][0]

    assert append_and_dedupe_to_gcs(
        mock_client, "test-bucket", second, target_date=date(2026, 9, 9)
    ) == 2


def test_the_blank_columns_survive_a_round_trip_through_the_file():
    """What went in as unknown must come back as unknown, not as zero."""
    df = _one_snapshot_row(datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc))
    mock_client, mock_bucket, mock_blob = MagicMock(), MagicMock(), MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mock_blob.exists.return_value = False
    append_and_dedupe_to_gcs(mock_client, "test-bucket", df, target_date=date(2026, 9, 9))

    written = pd.read_parquet(io.BytesIO(mock_blob.upload_from_string.call_args[0][0]))
    for column in ("open", "high", "low", "settle_price", "turnover_inr"):
        assert written[column].isna().all(), f"{column} came back as something other than NULL"
    assert written["underlying_spot"].iloc[0] == 23431.5
    assert written["expiry_date"].iloc[0] == date(2026, 9, 15)


def test_main_record_snapshot_skips_when_closed():
    req = MagicMock()
    req.args = {}
    with patch("main.is_market_open", return_value=(False, "Market closed (Weekend)")):
        resp, status, _ = record_snapshot(req)
        assert status == 200
        assert json.loads(resp)["status"] == "skipped"
        assert "Weekend" in resp


def test_a_dry_run_writes_nothing_and_ignores_the_market_gate():
    """The only way to prove a deployment out of hours, and it must not record."""
    req = MagicMock()
    req.args = {"dry_run": "1"}
    df = _one_snapshot_row(datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc))

    with patch("main.is_market_open", return_value=(False, "closed")) as gate, \
         patch("main.get_fyers_access_token", return_value="token"), \
         patch("main.fetch_options_snapshot", return_value=df), \
         patch("main.storage.Client") as storage_client, \
         patch("main.append_and_dedupe_to_gcs") as writer:
        resp, status, _ = record_snapshot(req)

    body = json.loads(resp)
    assert status == 200
    assert body["status"] == "dry_run"
    assert body["wrote_anything"] is False
    assert body["rows"] == 1
    assert body["underlying_spot"] == 23431.5
    assert body["rows_with_iv"] == 1
    writer.assert_not_called()
    storage_client.assert_not_called()
    gate.assert_not_called()


def test_the_scheduler_never_triggers_a_dry_run():
    """The scheduler POSTs with no query string. That must record, not dry-run."""
    req = MagicMock()
    req.args = {}
    df = _one_snapshot_row(datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc))

    with patch("main.is_market_open", return_value=(True, "open")), \
         patch("main.get_fyers_access_token", return_value="token"), \
         patch("main.fetch_options_snapshot", return_value=df), \
         patch("main.storage.Client"), \
         patch("main.append_and_dedupe_to_gcs", return_value=1) as writer:
        resp, status, _ = record_snapshot(req)

    assert status == 200
    assert json.loads(resp)["status"] == "recorded"
    writer.assert_called_once()


def test_the_gate_can_be_asked_about_a_future_instant_and_does_nothing_else():
    """Proves a holiday on the deployed copy before the morning it matters."""
    req = MagicMock()
    req.args = {"gate_at": "2026-09-14T03:30:00Z"}  # 09:00 IST, Ganesh Chaturthi

    with patch("main.get_fyers_access_token") as token,          patch("main.fetch_options_snapshot") as fetch,          patch("main.storage.Client") as storage_client,          patch("main.append_and_dedupe_to_gcs") as writer:
        resp, status, _ = record_snapshot(req)

    body = json.loads(resp)
    assert status == 200
    assert body["status"] == "gate"
    assert body["market_open"] is False
    assert body["reason"] == "Market closed: 2026-09-14 is an NSE trading holiday."
    assert body["wrote_anything"] is False
    token.assert_not_called()
    fetch.assert_not_called()
    storage_client.assert_not_called()
    writer.assert_not_called()


def test_a_gate_question_without_a_timezone_is_refused():
    req = MagicMock()
    req.args = {"gate_at": "2026-09-14T09:00:00"}
    resp, status, _ = record_snapshot(req)
    assert status == 400
    assert json.loads(resp)["status"] == "error"
