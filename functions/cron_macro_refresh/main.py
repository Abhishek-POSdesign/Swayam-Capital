"""
Google Cloud Function: cron_macro_refresh

Scheduled triggers:
- Nightly Ingest: 02:00 IST daily (pulls Trading Economics 30-day calendar)
- Weekly Curation: 10:00 IST Sundays (Gemini 2.5 Pro selects 3-5 high impact F&O events)

Cloud Scheduler timezone: Asia/Kolkata
Region: asia-southeast1
"""

import json
import logging
import os
import functions_framework
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cron_macro_refresh")

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "https://swayam.abhisheksikka.com")
CRON_SHARED_SECRET = os.getenv("CRON_SHARED_SECRET", "swayam-cron-internal-secret-2026")


@functions_framework.http
def handle_cron_macro(request):
    """Entry point for Cloud Scheduler HTTP target."""
    mode = request.args.get("mode", "ingest")
    logger.info("Executing macro refresh task in mode=%s", mode)

    headers = {
        "X-Cron-Secret": CRON_SHARED_SECRET,
        "Content-Type": "application/json",
    }
    url = f"{BACKEND_BASE_URL}/api/macro/refresh?mode={mode}"

    try:
        resp = requests.post(url, headers=headers, timeout=60)
        logger.info("Backend refresh response code=%d", resp.status_code)
        return (resp.text, resp.status_code, {"Content-Type": "application/json"})
    except Exception as e:
        logger.error("Failed to invoke backend refresh: %s", e)
        return (json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"})
