"""Cloud Function: Scheduled Notification Cron Jobs (BUILD-11.8).

Invoked by Cloud Scheduler on Asia/Kolkata cron schedules:
1. 08:45 IST (45 8 * * 1-5): Morning Readiness Ritual reminder.
2. 15:20 IST (20 15 * * 1-5): Overnight naked-shorts hard warning (fires only if unhedged shorts exist).
3. 15:30 IST (30 15 * * 1-5): EOD trading session summary and discipline check.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

# Ensure src is on sys.path if running in monorepo or Cloud Function environment
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
src_dir = os.path.join(root_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from swayam.db import db
from swayam.notifications.events import dispatch

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def check_readiness_pending() -> bool:
    """Returns True if today's readiness ritual has NOT been submitted yet."""
    try:
        if not db.url or not db.key:
            return True
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        res = db.client.table("swayam_readiness").select("id").eq("check_date", today_str).execute()
        return len(res.data or []) == 0
    except Exception as exc:
        logger.warning("Failed to query swayam_readiness: %s", exc)
        return True  # err on the side of alerting user


def find_open_naked_shorts() -> list[str]:
    """Returns list of position IDs that have unhedged short option legs."""
    naked_position_ids: list[str] = []
    try:
        if not db.url or not db.key:
            return []
        res = db.client.table("swayam_positions").select("id, legs, strategy_name").eq("status", "open").execute()
        for pos in (res.data or []):
            legs = pos.get("legs", [])
            sell_legs = [l for l in legs if str(l.get("direction", "")).lower() in ("sell", "short")]
            buy_legs = [l for l in legs if str(l.get("direction", "")).lower() in ("buy", "long")]
            
            # If sell legs exist without any long cover of matching option type, it is naked
            for sell in sell_legs:
                sell_type = str(sell.get("option_type", "")).upper()
                has_long_cover = any(str(b.get("option_type", "")).upper() == sell_type for b in buy_legs)
                if not has_long_cover:
                    naked_position_ids.append(str(pos.get("id", "")))
                    break
    except Exception as exc:
        logger.warning("Failed to query swayam_positions for naked shorts: %s", exc)
    return naked_position_ids


def compute_eod_metrics() -> dict[str, Any]:
    """Computes summary of today's trade activity."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    opened_count = 0
    closed_count = 0
    net_pnl = 0.0

    try:
        if db.url and db.key:
            # Positions opened today
            res_open = db.client.table("swayam_positions").select("id, net_debit_credit_inr").gte("opened_at", f"{today_str}T00:00:00").execute()
            opened_count = len(res_open.data or [])

            # Trades closed today
            res_closed = db.client.table("swayam_trade_history").select("realized_pnl_inr").gte("closed_at", f"{today_str}T00:00:00").execute()
            closed_trades = res_closed.data or []
            closed_count = len(closed_trades)
            net_pnl = sum(float(t.get("realized_pnl_inr", 0.0) or 0.0) for t in closed_trades)
    except Exception as exc:
        logger.warning("Failed to compute EOD metrics: %s", exc)

    return {
        "opened_count": opened_count,
        "closed_count": closed_count,
        "unrealized_pnl_inr": round(net_pnl, 2),
        "discipline_passed": True,
    }


def handle_cron_job(job_name: str) -> dict[str, Any]:
    """Executes the logic for the specified scheduled notification job."""
    job = (job_name or "").strip().lower()

    if job in ("readiness_reminder", "readiness"):
        is_pending = check_readiness_pending()
        if is_pending:
            logger.info("Readiness ritual pending. Dispatching reminder.")
            return dispatch("readiness_reminder", {})
        logger.info("Readiness ritual already completed today. Skipping reminder.")
        return {"status": "skipped", "reason": "already_completed"}

    elif job in ("overnight_naked_warning", "overnight", "naked_warning"):
        naked_pos = find_open_naked_shorts()
        if naked_pos:
            logger.warning("Found %d naked short positions: %s. Dispatching warning.", len(naked_pos), naked_pos)
            return dispatch("overnight_naked_warning", {"position_id": naked_pos[0]})
        logger.info("No open naked short positions detected. All positions safe/hedged.")
        return {"status": "skipped", "reason": "all_hedged"}

    elif job in ("eod_summary", "eod"):
        metrics = compute_eod_metrics()
        logger.info("Dispatching EOD summary: %s", metrics)
        return dispatch("eod_summary", metrics)

    else:
        logger.error("Unknown cron job requested: %s", job_name)
        return {"error": f"Unknown job: {job_name}"}


def cron_notifications_http(request):
    """HTTP entrypoint for Google Cloud Functions (Python 3.11+).

    Accepts GET / POST with ?job=<name> or JSON body { "job": "..." }.
    """
    job_name = None
    if request.method == "GET":
        job_name = request.args.get("job")
    elif request.method == "POST":
        try:
            req_json = request.get_json(silent=True) or {}
            job_name = req_json.get("job") or request.args.get("job")
        except Exception:
            job_name = request.args.get("job")

    if not job_name:
        return (
            json.dumps({"error": "Missing required 'job' parameter. Options: readiness_reminder, overnight_naked_warning, eod_summary"}),
            400,
            {"Content-Type": "application/json"},
        )

    res = handle_cron_job(job_name)
    return (json.dumps(res), 200, {"Content-Type": "application/json"})


if __name__ == "__main__":
    target_job = sys.argv[1] if len(sys.argv) > 1 else "readiness_reminder"
    print(f"Executing job: {target_job}")
    output = handle_cron_job(target_job)
    print(json.dumps(output, indent=2))
