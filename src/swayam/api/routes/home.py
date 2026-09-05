"""
Home dashboard endpoints for Swayam Capital.

Exposes:
- GET /api/home/so-far-today: Returns cached grounded session recap if within 60 min
- POST /api/home/so-far-today: Generates fresh grounded market summary with daily cap enforcement
- GET /api/home/nifty-snapshot: Returns comprehensive Cash + F&O snapshot with freshness badges
"""

from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from swayam.services.so_far_today import (
    DailyCapExceededError,
    generate_so_far_today,
    get_cached_so_far_today,
)
from swayam.services.nifty_snapshot import get_nifty_snapshot_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/home", tags=["home"])


class SoFarTodayResponse(BaseModel):
    has_data: bool
    text: str = ""
    sources: list[dict[str, Any]] = []
    search_queries: list[str] = []
    generated_at: str = ""
    is_cached: bool = False
    age_minutes: int = 0
    call_count_today: int = 0
    daily_cap: int = 8
    cap_reached: bool = False
    message: str = ""


@router.get("/so-far-today", response_model=SoFarTodayResponse)
def get_so_far_today_status() -> dict[str, Any]:
    """Retrieves active cached 'So Far Today' market summary if within 60 minutes."""
    cached = get_cached_so_far_today(max_age_minutes=60)
    if cached is not None:
        return {
            "has_data": True,
            **cached,
            "message": "Loaded from active 60-minute cache.",
        }

    return {
        "has_data": False,
        "text": "",
        "sources": [],
        "search_queries": [],
        "generated_at": "",
        "is_cached": False,
        "age_minutes": 0,
        "call_count_today": 0,
        "daily_cap": 8,
        "cap_reached": False,
        "message": "Click Generate to see what the tape has done today so far.",
    }


@router.post("/so-far-today", response_model=SoFarTodayResponse)
def post_generate_so_far_today(force: bool = Query(default=False)) -> dict[str, Any]:
    """Generates fresh Google Search-grounded market summary via Gemini.

    Enforces 8-call daily cap. Returns 429 if cap is exceeded.
    """
    try:
        result = generate_so_far_today(force=force)
        return {
            "has_data": True,
            **result,
            "message": "Successfully generated grounded market summary.",
        }
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
