"""
Home dashboard endpoints for Swayam Capital.

Exposes:
- GET /api/home/so-far-today: Returns the day's SAVED summary, however old. A
  database read, never a model call.
- POST /api/home/so-far-today: Generates a fresh grounded summary, inside the
  60-minute cache and the daily cap.
- GET /api/home/nifty-snapshot: Returns comprehensive Cash + F&O snapshot with freshness badges
- GET /api/home/backup-age: How old his newest backup is, read from the bucket every time
"""

from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from swayam.services.so_far_today import (
    DailyCapExceededError,
    generate_so_far_today,
    read_day_summary,
)
from swayam.services.nifty_snapshot import get_nifty_snapshot_data
from swayam.services.record_backup import newest_backup_info

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/home", tags=["home"])


@router.get("/backup-age")
def get_backup_age() -> dict[str, Any]:
    """How old his newest backup is, read from the real object in the bucket.

    Never a stored constant. If the bucket cannot be read the response says
    `available: false` with the reason, and the screen shows that rather than
    a comforting number nobody checked.
    """
    return newest_backup_info()


class SoFarTodayResponse(BaseModel):
    has_data: bool
    day: str = ""
    text: str = ""
    sources: list[dict[str, Any]] = []
    search_queries: list[str] = []
    # Which model wrote the stored text. Empty means it was never recorded,
    # which is true of every row migration 026 backfilled. Empty never means
    # "unknown, so assume the current one".
    model: str = ""
    generated_at: str = ""
    is_cached: bool = False
    age_minutes: int = 0
    call_count_today: int = 0
    daily_cap: int = 8
    cap_reached: bool = False
    # False only on a POST whose model call succeeded and whose row failed to
    # save. He was charged and the text will not be there tomorrow, so the
    # screen has to say so.
    stored: bool = True
    message: str = ""


def _as_response(payload: dict[str, Any], message: str) -> dict[str, Any]:
    """Normalises a service payload into the response shape. No invented values."""
    return {
        "has_data": bool((payload.get("text") or "").strip()),
        "day": payload.get("day") or "",
        "text": payload.get("text") or "",
        "sources": payload.get("sources") or [],
        "search_queries": payload.get("search_queries") or [],
        "model": payload.get("model") or "",
        "generated_at": payload.get("generated_at") or "",
        "is_cached": bool(payload.get("is_cached")),
        "age_minutes": int(payload.get("age_minutes") or 0),
        "call_count_today": int(payload.get("call_count_today") or 0),
        "daily_cap": int(payload.get("daily_cap") or 8),
        "cap_reached": bool(payload.get("cap_reached")),
        "stored": bool(payload.get("stored", True)),
        "message": message,
    }


@router.get("/so-far-today", response_model=SoFarTodayResponse)
def get_so_far_today_status() -> dict[str, Any]:
    """Returns the day's SAVED summary, whatever its age.

    This is a database read and never a model call, so it is safe on load and
    costs nothing. His decision of 12 September: the summary stays on the card
    until he presses Generate again, so a summary written three hours ago is
    still the summary of today and is still shown, with its age beside it.
    The 60-minute cache is a rule about SPENDING, and it lives on the POST.
    """
    saved = read_day_summary()
    if saved is not None and (saved.get("text") or "").strip():
        age = saved.get("age_minutes")
        stamp = f"Saved summary for today, written {age} minutes ago." if age is not None else "Saved summary for today."
        return _as_response(saved, stamp)

    return {
        "has_data": False,
        "day": "",
        "text": "",
        "sources": [],
        "search_queries": [],
        "model": "",
        "generated_at": "",
        "is_cached": False,
        "age_minutes": 0,
        "call_count_today": saved.get("call_count_today", 0) if saved else 0,
        "daily_cap": saved.get("daily_cap", 8) if saved else 8,
        "cap_reached": saved.get("cap_reached", False) if saved else False,
        "stored": True,
        "message": "Nothing saved for today yet. Press Generate.",
    }


@router.post("/so-far-today", response_model=SoFarTodayResponse)
def post_generate_so_far_today(force: bool = Query(default=False)) -> dict[str, Any]:
    """Generates a fresh Google Search-grounded market summary via Gemini.

    Enforces the 60-minute cache and the daily cap. Returns 429 at the cap.
    """
    try:
        result = generate_so_far_today(force=force)
        if result.get("stored") is False:
            message = (
                "The summary was generated and you were charged for it, but it "
                "did not save to swayam_daily_summary, so it will not be here "
                "tomorrow. The server log has the database error."
            )
        elif result.get("is_cached"):
            message = "Served from the 60-minute cache. No model call was made and nothing was charged."
        else:
            message = "Generated and saved as today's summary."
        return _as_response(result, message)
    except DailyCapExceededError as e:
        raise HTTPException(
            status_code=429,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Error generating so_far_today: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate market summary: {str(e)}",
        )


@router.get("/nifty-snapshot")
def get_nifty_snapshot(refresh: bool = Query(default=False)) -> dict[str, Any]:
    """Returns real-time Cash & F&O NIFTY snapshot with four-state freshness badges."""
    try:
        data = get_nifty_snapshot_data(is_refresh=refresh)
        return data
    except Exception as e:
        logger.error("Failed to generate NIFTY snapshot: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load NIFTY snapshot: {str(e)}",
        )
