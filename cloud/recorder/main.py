"""Cloud Function entry point for Swayam Live Options Recorder.

Triggered by Cloud Scheduler every 60 seconds during Indian market hours.

There is a second way in, `?dry_run=1`, which fetches from FYERS and computes
everything but writes NOTHING to the bucket and ignores the market-hours gate.
It exists because of a real problem: this function only does its work between
09:15 and 15:30 IST, so out of hours a deployment can be proved to start and
nothing else. A change to what it RECORDS could not be checked on the deployed
copy until the next morning, by which time it has already written a day.

With the dry run, a deployment can be proved in the cloud the moment it lands:
it returns the row count, the NIFTY level it read, and how many rows came back
with a real implied volatility. The scheduler never sends it, so the recording
path is exactly as it was.

A third way in, `?gate_at=<ISO datetime>`, answers ONE question and does nothing
else: would the market gate let a recording through at that instant. It reads no
token, calls no broker and touches no bucket. It exists because the gate only
ever judges "now", so a holiday could not be asked of the deployed copy until
the morning it mattered. Added on 13 September 2026 to prove, on a Sunday, that
the deployed recorder knew Monday 14 September was Ganesh Chaturthi.
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


def _wants_dry_run(request) -> bool:
    """True only for an explicit `?dry_run=1`. Never the default, never implicit."""
    if request is None:
        return False
    try:
        args = getattr(request, "args", None)
        if args is None:
            return False
        return str(args.get("dry_run", "")).strip().lower() in ("1", "true", "yes")
    except Exception:  # noqa: BLE001 - a malformed request is simply not a dry run
        return False


def _summarise(df) -> dict:
    """What the snapshot actually contains, so a dry run can be judged not trusted."""
    if df is None or df.empty:
        return {"rows": 0}
    spots = df["underlying_spot"].dropna().unique().tolist() if "underlying_spot" in df else []
    expiries = (
        sorted({str(v) for v in df["expiry_date"].dropna().unique()})
        if "expiry_date" in df else []
    )
    return {
        "rows": int(len(df)),
        "expiries": expiries,
        "underlying_spot": float(spots[0]) if spots else None,
        "rows_with_close": int(df["close"].notna().sum()) if "close" in df else 0,
        "rows_with_iv": int(df["iv"].notna().sum()) if "iv" in df else 0,
        "rows_with_delta": int(df["delta"].notna().sum()) if "delta" in df else 0,
        "rows_with_change_in_oi": (
            int(df["change_in_oi"].notna().sum()) if "change_in_oi" in df else 0
        ),
    }


def _gate_at(request) -> str | None:
    """The `?gate_at=` value when one was sent as text, otherwise None."""
    if request is None:
        return None
    try:
        args = getattr(request, "args", None)
        value = args.get("gate_at") if args is not None else None
    except Exception:  # noqa: BLE001 - a malformed request simply does not ask
        return None
    return value.strip() if isinstance(value, str) and value.strip() else None


@http_decorator
def record_snapshot(request):
    """HTTP Cloud Function handler for recording options chain snapshots."""
    now_utc = datetime.now(timezone.utc)

    asked = _gate_at(request)
    if asked is not None:
        try:
            when = datetime.fromisoformat(asked.replace("Z", "+00:00"))
            if when.tzinfo is None:
                raise ValueError("no timezone")
        except ValueError:
            return (
                json.dumps({
                    "status": "error",
                    "error": f"gate_at must be an ISO datetime with a timezone, got {asked!r}",
                }),
                400,
                {"Content-Type": "application/json"},
            )
        market_open, reason = is_market_open(when)
        logger.info(f"Gate asked for {when.isoformat()}: {reason}")
        return (
            json.dumps({
                "status": "gate",
                "gate_at": when.isoformat(),
                "market_open": market_open,
                "reason": reason,
                "wrote_anything": False,
            }),
            200,
            {"Content-Type": "application/json"},
        )

    dry_run = _wants_dry_run(request)

    if not dry_run:
        market_open, reason = is_market_open(now_utc)
        if not market_open:
            logger.info(f"Execution skipped: {reason}")
            return (
                json.dumps({"status": "skipped", "reason": reason, "timestamp": now_utc.isoformat()}),
                200,
                {"Content-Type": "application/json"},
            )

    try:
        token = get_fyers_access_token()

        logger.info("Fetching option chain snapshot from FYERS...")
        df = fetch_options_snapshot(access_token=token)
        records_added = len(df)
        logger.info(f"Received {records_added} option rows from FYERS.")

        if dry_run:
            # Nothing is written. This path exists to prove a deployment, not to record.
            summary = _summarise(df)
            logger.info(f"Dry run complete, nothing written: {summary}")
            return (
                json.dumps({
                    "status": "dry_run",
                    "wrote_anything": False,
                    "snapshot_time_utc": now_utc.isoformat(),
                    **summary,
                }),
                200,
                {"Content-Type": "application/json"},
            )

        storage_client = storage.Client()
        total_rows = append_and_dedupe_to_gcs(storage_client, GCS_OPTIONS_BUCKET, df)
        logger.info(f"Successfully appended to GCS. Daily total: {total_rows} rows.")

        return (
            json.dumps({
                "status": "recorded",
                "snapshot_time_utc": now_utc.isoformat(),
                "records_added": records_added,
                "total_daily_records": total_rows,
                **_summarise(df),
            }),
            200,
            {"Content-Type": "application/json"},
        )

    except Exception as e:
        err_msg = str(e)
        logger.error(f"Snapshot recording failed: {err_msg}\n{traceback.format_exc()}")
        return (
            json.dumps({
                "status": "error",
                "dry_run": dry_run,
                "error": err_msg,
                "timestamp": now_utc.isoformat(),
            }),
            500,
            {"Content-Type": "application/json"},
        )
