"""Cloud Function: cron_backup_db
Nightly DB Backup (02:00 IST)

Triggered by Cloud Scheduler with X-Cron-Secret header authentication.
Timezone: Asia/Kolkata | Region: asia-southeast1
"""

import json
import logging
import os

try:
    import functions_framework
    _has_ff = True
except ImportError:
    _has_ff = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cron_backup_db")


def cron_backup_db(request):
    """Entry point for Cloud Scheduler HTTP trigger."""
    expected_secret = os.getenv("CRON_SHARED_SECRET", "")
    req_secret = getattr(request, "headers", {}).get("X-Cron-Secret", "")
    if expected_secret and req_secret != expected_secret:
        return (json.dumps({"error": "Unauthorized"}), 401, {"Content-Type": "application/json"})

    try:
        from swayam.services.backup_service import run_nightly_backup
        success = run_nightly_backup()
        return (
            json.dumps({
                "status": "ok" if success else "failed",
                "message": "Backup task completed successfully" if success else "Backup task failed; alert dispatched",
            }),
            200 if success else 500,
            {"Content-Type": "application/json"},
        )
    except Exception as exc:
        logger.error("Execution error in cron_backup_db: %s", exc)
        return (json.dumps({"error": str(exc)}), 500, {"Content-Type": "application/json"})


if _has_ff:
    cron_backup_db = functions_framework.http(cron_backup_db)
