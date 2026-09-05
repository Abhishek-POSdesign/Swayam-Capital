"""Notification device registration routes (BUILD-11.11)."""

import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from swayam.db import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class RegisterDeviceRequest(BaseModel):
    device_token: str
    browser_ua: Optional[str] = None
    platform: Optional[str] = None


@router.post("/register-device")
async def register_device(payload: RegisterDeviceRequest):
    """Registers or updates a client device FCM token in swayam_notification_devices."""
    token = payload.device_token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="device_token is required")

    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "device_token": token,
        "browser_ua": payload.browser_ua or "",
        "platform": payload.platform or "web",
        "is_active": True,
        "last_seen_at": now_iso,
    }

    try:
        if db.url and db.key:
            db.client.table("swayam_notification_devices").upsert(
                record, on_conflict="device_token"
            ).execute()
            logger.info("Registered device token %s...", token[:12])
    except Exception as exc:
        logger.error("Failed to persist device registration: %s", exc)
        return {"status": "registered", "device_token": token, "warning": "persisted_locally_or_failed"}

    return {"status": "registered", "device_token": token}


@router.get("/devices")
async def list_devices():
    """Lists active registered notification devices."""
    try:
        if db.url and db.key:
            res = db.client.table("swayam_notification_devices").select("*").eq("is_active", True).execute()
            return {"devices": res.data or []}
    except Exception as exc:
        logger.error("Failed to list devices: %s", exc)
    return {"devices": []}
