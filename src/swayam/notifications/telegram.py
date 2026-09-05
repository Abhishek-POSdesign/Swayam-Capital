"""Telegram Bot API Notification Sender (BUILD-11.8).

Sends concise, plain-English trade alerts, rule warnings, and daily reminders
directly to Abhishek's private Telegram chat.
"""

import json
import logging
import os
import urllib.request
import urllib.error
from typing import Optional

from swayam.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"


def send_telegram_message(
    text: str,
    chat_id: Optional[str] = None,
    token: Optional[str] = None,
    parse_mode: Optional[str] = None,
    timeout_sec: float = 5.0,
) -> bool:
    """Sends a message via Telegram Bot API.

    Best-effort:
    - If credentials are not configured, logs an info notice and returns False.
    - If network fails or times out, logs a warning and returns False.
    - Never raises an exception to the caller.
    """
    bot_token = token or settings.telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    target_chat = chat_id or settings.telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token or not target_chat:
        logger.info(
            "Telegram notification skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured."
        )
        return False

    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
    payload: dict[str, str] = {
        "chat_id": target_chat,
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            status = resp.getcode()
            if status == 200:
                logger.debug("Telegram notification delivered successfully.")
                return True
            logger.warning("Telegram returned non-200 status code: %d", status)
            return False
    except urllib.error.HTTPError as exc:
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = str(exc)
        logger.warning("Telegram HTTP error %d: %s", exc.code, err_body)
        return False
    except Exception as exc:
        logger.warning("Telegram send failed: %s", exc)
        return False
