"""
Cloud Function entry point for Swayam Live Options Recorder.

Triggered by Cloud Scheduler every 60 seconds during Indian market hours.
"""

from datetime import datetime, timezone
import json
import logging
import traceback
try:
    import functions_framework
    http_decorator = functions_framework.http
except ImportError:
    def http_decorator(func):
        return func

from google.cloud import storage

from config import GCS_OPTIONS_BUCKET, get_fyers_access_token
from fyers_recorder import append_and_dedupe_to_gcs, fetch_options_snapshot, is_market_open

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("swayam-recorder")


@http_decorator
def record_snapshot(request):
    """HTTP Cloud Function handler for recording options chain snapshots."""
    now_utc = datetime.now(timezone.utc)

    # 1. Market Hours Guard
    market_open, reason = is_market_open(now_utc)
    if not market_open:
        logger.info(f"Execution skipped: {reason}")
        return (
            json.dumps({"status": "skipped", "reason": reason, "timestamp": now_utc.isoformat()}),
            200,
            {"Content-Type": "application/json"},
        )

    try:
        # 2. Acquire FYERS Access Token
        token = get_fyers_access_token()

        # 3. Fetch Option Chain Snapshot
        logger.info("Fetching option chain snapshot from FYERS...")
        df = fetch_options_snapshot(access_token=token)
        records_added = len(df)
        logger.info(f"Received {records_added} option rows from FYERS.")

        # 4. Upload and Deduplicate in GCS
        storage_client = storage.Client()
        total_rows = append_and_dedupe_to_gcs(storage_client, GCS_OPTIONS_BUCKET, df)
        logger.info(f"Successfully appended to GCS. Daily total: {total_rows} rows.")

        return (
            json.dumps({
                "status": "recorded",
                "snapshot_time_utc": now_utc.isoformat(),
                "records_added": records_added,
                "total_daily_records": total_rows,
            }),
            200,
            {"Content-Type": "application/json"},
        )

    except Exception as e:
        err_msg = str(e)
        logger.error(f"Snapshot recording failed: {err_msg}\n{traceback.format_exc()}")
        return (
            json.dumps({"status": "error", "error": err_msg, "timestamp": now_utc.isoformat()}),
            500,
            {"Content-Type": "application/json"},
        )
