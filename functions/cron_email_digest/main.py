"""Cloud Function for Sunday Weekly Email Digest (BUILD-11.11).

Triggered by Cloud Scheduler every Sunday at 11:00 AM IST.
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
logger = logging.getLogger("cron_email_digest")


def cron_email_digest(request):
    """Entry point for weekly email digest."""
    expected_secret = os.getenv("CRON_SHARED_SECRET", "")
    req_secret = getattr(request, "headers", {}).get("X-Cron-Secret", "")
    if expected_secret and req_secret != expected_secret:
        return (json.dumps({"error": "Unauthorized"}), 401, {"Content-Type": "application/json"})

    try:
        from swayam.services.email_digest import send_weekly_digest
        success = send_weekly_digest()
        return (
            json.dumps({
                "status": "ok" if success else "skipped",
                "message": "Email digest sent" if success else "Email digest skipped (missing credentials or zero dispatches)"
            }),
            200,
            {"Content-Type": "application/json"}
        )
    except Exception as exc:
        logger.error("Failed to execute cron_email_digest: %s", exc)
        return (json.dumps({"error": str(exc)}), 500, {"Content-Type": "application/json"})


if _has_ff:
    cron_email_digest = functions_framework.http(cron_email_digest)

