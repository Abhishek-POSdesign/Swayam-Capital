"""
Macro economic events API routes for Swayam Capital.

Endpoints:
- GET  /api/macro/events  — Returns upcoming curated macro events with staleness metadata
- POST /api/macro/refresh — Protected cron trigger for calendar ingestion and weekly curation
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Optional
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from swayam.config import settings
from swayam.db import SupabaseDB
from swayam.services.macro_calendar import ingest_macro_calendar
from swayam.services.macro_curator import curate_macro_events

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/macro", tags=["Macro Events"])
TIMEZONE = "Asia/Kolkata"


class MacroEventItem(BaseModel):
    event_key: str
    event_name: str
    event_date: str
    event_time_ist: Optional[str] = None
    country: str
    category: Optional[str] = None
    importance: Optional[str] = None
    highlighted: bool
    impact_brief: Optional[str] = None


class MacroEventsResponse(BaseModel):
    events: list[MacroEventItem]
    is_stale: bool
    last_fetched_at: Optional[str] = None
    last_curated_at: Optional[str] = None
    stale_warning: Optional[str] = None


@router.get("/events", response_model=MacroEventsResponse)
def get_macro_events(
    highlighted_only: bool = Query(default=True),
    days_ahead: int = Query(default=14),
) -> dict[str, Any]:
    """Retrieves upcoming macro events with staleness verification."""
    db = SupabaseDB()
    tz = ZoneInfo(TIMEZONE)
    today = datetime.now(tz).date()
    end_date = today + timedelta(days=days_ahead)

    # 1. Query events
    query = (
        db.client.table("swayam_macro_events")
        .select("*")
        .gte("event_date", today.isoformat())
        .lte("event_date", end_date.isoformat())
        .order("event_date")
    )
    if highlighted_only:
        query = query.eq("highlighted", True)

    res = query.execute()
    events = res.data or []

    # If no highlighted events exist yet, fetch upcoming high importance events
    if highlighted_only and not events:
        fallback_res = (
            db.client.table("swayam_macro_events")
            .select("*")
            .gte("event_date", today.isoformat())
            .lte("event_date", end_date.isoformat())
            .order("event_date")
            .limit(5)
            .execute()
        )
        events = fallback_res.data or []

    # 2. Check staleness (last cron > 8 days ago)
    is_stale = False
    last_fetched_at = None
    last_curated_at = None
    stale_warning = None

    try:
        latest_row_res = (
            db.client.table("swayam_macro_events")
            .select("fetched_at, curated_at")
            .order("fetched_at", desc=True)
            .limit(1)
            .execute()
        )
        if latest_row_res.data and len(latest_row_res.data) > 0:
            row = latest_row_res.data[0]
            last_fetched_at = row.get("fetched_at")
            last_curated_at = row.get("curated_at")
            if last_fetched_at:
                f_dt = datetime.fromisoformat(last_fetched_at.replace("Z", "+00:00"))
                now_utc = datetime.now(timezone.utc)
                diff_days = (now_utc - f_dt).total_seconds() / 86400.0
                if diff_days > 8.0:
                    is_stale = True
                    formatted_d = f_dt.astimezone(tz).strftime("%d %b %Y")
                    stale_warning = f"Calendar may be stale — last refreshed {formatted_d}"
    except Exception as e:
        logger.warning("Could not evaluate macro events staleness: %s", e)

    return {
        "events": events,
        "is_stale": is_stale,
        "last_fetched_at": last_fetched_at,
        "last_curated_at": last_curated_at,
        "stale_warning": stale_warning,
    }


@router.post("/refresh")
def refresh_macro_events(
    mode: str = Query(default="all", pattern="^(ingest|curate|all)$"),
    x_cron_secret: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    """Protected cron trigger for calendar ingestion and weekly curation.

    Requires valid X-Cron-Secret header matching CRON_SHARED_SECRET.
    """
    configured_secret = settings.cron_shared_secret or "swayam-cron-internal-secret-2026"
    if not x_cron_secret or x_cron_secret.strip() != configured_secret.strip():
        logger.warning("Unauthorized macro refresh attempt with invalid X-Cron-Secret.")
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid or missing X-Cron-Secret header.",
        )

    results: dict[str, Any] = {"mode": mode, "timestamp": datetime.now(timezone.utc).isoformat()}

    if mode in ("ingest", "all"):
        ingest_res = ingest_macro_calendar()
        results["ingest"] = ingest_res

    if mode in ("curate", "all"):
        curate_res = curate_macro_events()
        results["curate"] = curate_res

    return results
