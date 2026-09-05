"""
'So Far Today' Grounded Gemini Market Summary Service.

Generates real-time, search-grounded market recaps for discretionary options traders.
Enforces:
- Manual trigger only (never auto-fires on page load)
- 60-minute cache in swayam_home_snapshot
- Daily cap (default 8 calls per trading day)
- Logs usage to swayam_ai_usage_daily
"""

from __future__ import annotations

from datetime import datetime, time, timezone
import logging
from typing import Any, Optional
from zoneinfo import ZoneInfo

from swayam.ai.grounded import generate_grounded_content
from swayam.config import settings
from swayam.db import SupabaseDB

logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Kolkata"


class DailyCapExceededError(Exception):
    """Raised when the daily grounded Gemini call quota has been exhausted."""
    pass


def get_today_ist_start() -> datetime:
    """Returns midnight (00:00:00) IST for today as UTC datetime."""
    tz = ZoneInfo(TIMEZONE)
    now_ist = datetime.now(tz)
    start_of_day = datetime.combine(now_ist.date(), time.min, tzinfo=tz)
    return start_of_day.astimezone(timezone.utc)


def count_grounded_calls_today(db: Optional[SupabaseDB] = None) -> int:
    """Counts so_far_today generations executed since midnight IST today."""
    if db is None:
        db = SupabaseDB()

    start_utc_iso = get_today_ist_start().isoformat()
    try:
        res = (
            db.client.table("swayam_home_snapshot")
            .select("id", count="exact")
            .eq("snapshot_type", "so_far_today")
            .gte("generated_at", start_utc_iso)
            .execute()
        )
        return res.count if res.count is not None else len(res.data)
    except Exception as e:
        logger.warning("Failed to count today's grounded calls: %s", e)
        return 0


def get_cached_so_far_today(
    max_age_minutes: int = 60,
    db: Optional[SupabaseDB] = None,
) -> Optional[dict[str, Any]]:
    """Retrieves the latest generated summary if it is newer than max_age_minutes."""
    if db is None:
        db = SupabaseDB()

    try:
        res = (
            db.client.table("swayam_home_snapshot")
            .select("*")
            .eq("snapshot_type", "so_far_today")
            .order("generated_at", desc=True)
            .limit(1)
            .execute()
        )
        if not res.data or len(res.data) == 0:
            return None

        row = res.data[0]
        gen_time_str = row.get("generated_at")
        if not gen_time_str:
            return None

        gen_time = datetime.fromisoformat(gen_time_str.replace("Z", "+00:00"))
        now_utc = datetime.now(timezone.utc)
        age_seconds = (now_utc - gen_time).total_seconds()
        age_minutes = int(age_seconds // 60)

        calls_today = count_grounded_calls_today(db)

        if age_minutes < max_age_minutes:
            payload = row.get("payload", {})
            payload["is_cached"] = True
            payload["age_minutes"] = age_minutes
            payload["call_count_today"] = calls_today
            payload["daily_cap"] = settings.swayam_ai_daily_grounded_cap
            payload["cap_reached"] = calls_today >= settings.swayam_ai_daily_grounded_cap
            return payload

        return None
    except Exception as e:
        logger.error("Failed to query so_far_today cache: %s", e)
        return None


def generate_so_far_today(
    force: bool = False,
    db: Optional[SupabaseDB] = None,
) -> dict[str, Any]:
    """Generates a fresh grounded market summary, adhering to cache and daily caps."""
    if db is None:
        db = SupabaseDB()

    # 1. Check cache unless forced
    if not force:
        cached = get_cached_so_far_today(max_age_minutes=60, db=db)
        if cached is not None:
            return cached

    # 2. Check daily cap
    calls_today = count_grounded_calls_today(db)
    daily_cap = settings.swayam_ai_daily_grounded_cap
    if calls_today >= daily_cap:
        raise DailyCapExceededError(
            f"Daily cap reached ({daily_cap} calls). Resets at 09:15 IST tomorrow."
        )

    # 3. Construct prompt
    tz = ZoneInfo(TIMEZONE)
    now_ist = datetime.now(tz)
    current_time_str = now_ist.strftime("%H:%M IST")
    today_str = now_ist.strftime("%A, %d %B %Y")

    prompt = (
        f"It is now {current_time_str} on {today_str}. The Indian equity market opened at 09:15 IST today. "
        "Between 09:15 IST and now, summarize: "
        "NIFTY 50 and Bank NIFTY price movement (open, current, range, notable levels tested), "
        "India VIX movement, "
        "top 3 gainers and top 3 losers within Nifty 50, "
        "sector leaders and laggards, "
        "any macro news releases fired since 09:15 IST that affect Indian equities (RBI/SEBI statements, Fed comments, geopolitical events, big corporate news). "
        "Cite sources for macro releases. Be direct — this is for a discretionary options trader. "
        "End with one sentence naming the tape's most interesting feature for a Bear Put Spread or Bull Call Spread setup."
    )

    system_instruction = (
        "You are an institutional Indian equity derivatives market intelligence assistant. "
        "Provide factual, grounded, real-time observations with precise numbers and citations."
    )

    # 4. Invoke grounded Gemini
    result = generate_grounded_content(
        prompt=prompt,
        system_instruction=system_instruction,
        model="gemini-2.5-flash",
    )

    now_utc = datetime.now(timezone.utc)
    new_call_count = calls_today + 1

    payload: dict[str, Any] = {
        "text": result["text"],
        "sources": result["sources"],
        "search_queries": result["search_queries"],
        "generated_at": now_utc.isoformat(),
        "is_cached": False,
        "age_minutes": 0,
        "call_count_today": new_call_count,
        "daily_cap": daily_cap,
        "cap_reached": new_call_count >= daily_cap,
    }

    # 5. Persist to swayam_home_snapshot
    try:
        db.client.table("swayam_home_snapshot").insert({
            "snapshot_type": "so_far_today",
            "generated_at": now_utc.isoformat(),
            "payload": payload,
            "ai_tokens_used": result.get("tokens_used"),
        }).execute()
    except Exception as e:
        logger.error("Failed to persist so_far_today snapshot to Supabase: %s", e)

    # 6. Log usage to swayam_ai_usage_daily
    try:
        today_date_str = now_ist.date().isoformat()
        db.client.table("swayam_ai_usage_daily").insert({
            "day": today_date_str,
            "provider": "vertex",
            "model": "gemini-2.5-flash-grounded",
            "total_input_tokens": result.get("tokens_used") or 500,
            "total_output_tokens": 500,
            "request_count": 1,
            "estimated_cost_inr": 0.25,
        }).execute()
    except Exception as e:
        logger.warning("Could not log to swayam_ai_usage_daily: %s", e)

    return payload
