"""Firebase Cloud Messaging (FCM) Push Notification Sender (BUILD-11.8).

Sends browser/desktop push notifications for trade executions, rule violations,
and scheduled reminders.

Note: FCM server-side infrastructure ships in BUILD-11.8. Service worker client
registration and PWA manifest land in BUILD-11.11.
"""

import json
import logging
import os
import urllib.request
import urllib.error
from typing import Any, Optional

from swayam.config import settings
from swayam.db import db

logger = logging.getLogger(__name__)

FCM_LEGACY_SEND_URL = "https://fcm.googleapis.com/fcm/send"


def get_registered_device_tokens() -> list[str]:
    """Fetches active device registration tokens from Supabase table swayam_notification_devices.

    Gracefully returns empty list if table does not exist yet (created in BUILD-11.11)
    or if database is unreachable.
    """
    try:
        if not db.url or not db.key:
            return []
        res = db.client.table("swayam_notification_devices").select("device_token").eq("is_active", True).execute()
        if res.data:
            return [row["device_token"] for row in res.data if row.get("device_token")]
    except Exception as exc:
        logger.debug("Could not query swayam_notification_devices (expected prior to 11.11): %s", exc)
    return []


def send_push_notification(
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
    server_key: Optional[str] = None,
    device_tokens: Optional[list[str]] = None,
    timeout_sec: float = 5.0,
) -> bool:
    """Sends browser push notification via FCM.

    Best-effort:
    - If FCM server key is not configured, logs notice and returns False.
    - If no device tokens are registered, logs notice and returns False.
    - If network call fails, logs warning and returns False.
    - Never raises an exception to the caller.
    """
    fcm_key = server_key or settings.fcm_server_key or os.getenv("FCM_SERVER_KEY", "").strip()
    if not fcm_key:
        logger.info("FCM push notification skipped: FCM_SERVER_KEY not configured.")
        return False

    tokens = device_tokens if device_tokens is not None else get_registered_device_tokens()
    if not tokens:
        logger.info("FCM push notification skipped: no active device tokens registered.")
        return False

    success_any = False
    for token in tokens:
        payload = {
            "to": token,
            "notification": {
                "title": title,
                "body": body,
                "icon": "/icons/icon-192.png",
            },
            "data": data or {},
        }

        try:
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                FCM_LEGACY_SEND_URL,
                data=data_bytes,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"key={fcm_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                if resp.getcode() == 200:
                    success_any = True
                else:
                    logger.warning("FCM returned non-200 status %d for token %s...", resp.getcode(), token[:10])
        except Exception as exc:
            logger.warning("FCM push send failed for token %s...: %s", token[:10], exc)

    return success_any
