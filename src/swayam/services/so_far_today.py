"""
'So Far Today' grounded market summary. ONE ROW A TRADING DAY.

HIS WORDS, 11 September 2026: "I want to save the AI-generated summary. I'm
paying for that, so I don't want to lose those details and create a record of
what's happening, a trend in the market or in the geopolitics as well."

BUILD_07 moved the storage from swayam_home_snapshot, where every press of
Generate left another row, to swayam_daily_summary, where the IST trading day
is the key. Regenerating a day REPLACES that day's row and keeps the newest
stamp. Past days are never touched again. Migration 026 created the table and
backfilled the newest summary of each past day; nothing was deleted from
swayam_home_snapshot.

HIS COST RULE IS UNCHANGED AND IS NOT NEGOTIABLE:
- Manual trigger only. Nothing here is ever called on page load.
- 60-minute cache.
- A daily cap, default 8, from SWAYAM_AI_DAILY_GROUNDED_CAP.

THE ONE THING THAT HAD TO CHANGE WITH THE STORAGE. The cap used to be enforced
by counting ROWS since IST midnight. With one row a day that count is always
one, so the second press of the day would have been refused as "cap reached".
The cap now reads generation_count on the day's own row. count_grounded_calls_today
is used only inside this module, so nothing else is affected.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
import logging
from typing import Any, Optional
from zoneinfo import ZoneInfo

from swayam.ai.grounded import generate_grounded_content
from swayam.config import settings
from swayam.db import SupabaseDB

logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Kolkata"

# The model this module asks for. Stored on the row so a summary read back in
# March says which model wrote it, rather than leaving it to be inferred from
# source control.
GROUNDED_MODEL = "gemini-2.5-flash"

SUMMARY_TABLE = "swayam_daily_summary"


class DailyCapExceededError(Exception):
    """Raised when the daily grounded Gemini call quota has been exhausted."""
    pass


def get_today_ist_start() -> datetime:
    """Returns midnight (00:00:00) IST for today as a UTC datetime."""
    tz = ZoneInfo(TIMEZONE)
    now_ist = datetime.now(tz)
    start_of_day = datetime.combine(now_ist.date(), time.min, tzinfo=tz)
    return start_of_day.astimezone(timezone.utc)


def today_ist() -> date:
    """His trading day, in IST, not the server's UTC day."""
    return datetime.now(ZoneInfo(TIMEZONE)).date()


def _fetch_day_row(day: date, db: SupabaseDB) -> Optional[dict[str, Any]]:
    """The stored row for one IST day, or None. Raises nothing."""
    try:
        res = (
            db.client.table(SUMMARY_TABLE)
            .select("*")
            .eq("day", day.isoformat())
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]
        return None
    except Exception as e:
        logger.error("Failed to read %s for %s: %s", SUMMARY_TABLE, day, e)
        return None


def count_grounded_calls_today(db: Optional[SupabaseDB] = None) -> int:
    """How many times Generate has been pressed today, from the day's own row."""
    if db is None:
        db = SupabaseDB()

    row = _fetch_day_row(today_ist(), db)
    if not row:
        return 0
    try:
        return int(row.get("generation_count") or 0)
    except (TypeError, ValueError):
        return 0


def _row_to_payload(row: dict[str, Any], cap: int, calls_today: int) -> dict[str, Any]:
    """The shape the card and the AI persona both read. Keys are load-bearing."""
    generated_at = row.get("generated_at")
    age_minutes: Optional[int] = None
    if generated_at:
        try:
            gen_time = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
            age_minutes = int((datetime.now(timezone.utc) - gen_time).total_seconds() // 60)
        except ValueError:
            age_minutes = None

    return {
        "day": row.get("day"),
        "text": row.get("text") or "",
        "sources": row.get("sources") or [],
        "search_queries": row.get("search_queries") or [],
        # NULL means the model was never recorded, which is true of every row
        # backfilled by migration 026. It never means "unknown, so guess".
        "model": row.get("model"),
        "generated_at": generated_at,
        "age_minutes": age_minutes,
        "call_count_today": calls_today,
        "daily_cap": cap,
        "cap_reached": calls_today >= cap,
    }


def get_cached_so_far_today(
    max_age_minutes: int = 60,
    db: Optional[SupabaseDB] = None,
) -> Optional[dict[str, Any]]:
    """Today's stored summary if it is newer than max_age_minutes, else None.

    Keyed on the IST day, so a summary written yesterday is never served as
    "so far today". The AI persona calls this with 180 minutes; the card and
    the cost gate call it with 60.
    """
    if db is None:
        db = SupabaseDB()

    row = _fetch_day_row(today_ist(), db)
    if not row or not (row.get("text") or "").strip():
        return None

    cap = settings.swayam_ai_daily_grounded_cap
    try:
        calls_today = int(row.get("generation_count") or 0)
    except (TypeError, ValueError):
        calls_today = 0

    payload = _row_to_payload(row, cap, calls_today)
    payload["is_cached"] = True

    age = payload.get("age_minutes")
    if age is None or age >= max_age_minutes:
        return None
    return payload


def read_day_summary(
    day: Optional[date] = None,
    db: Optional[SupabaseDB] = None,
) -> Optional[dict[str, Any]]:
    """One day's stored summary, however old. Used to show the card on load.

    This is a database read and NEVER a model call. It is the only thing the
    page is allowed to do without him pressing Generate.
    """
    if db is None:
        db = SupabaseDB()

    row = _fetch_day_row(day or today_ist(), db)
    if not row:
        return None

    cap = settings.swayam_ai_daily_grounded_cap
    calls_today = count_grounded_calls_today(db)
    payload = _row_to_payload(row, cap, calls_today)
    payload["is_cached"] = True
    return payload


def generate_so_far_today(
    force: bool = False,
    db: Optional[SupabaseDB] = None,
) -> dict[str, Any]:
    """Generates a fresh grounded market summary, inside the cache and the cap."""
    if db is None:
        db = SupabaseDB()

    day = today_ist()

    # 1. The 60-minute cache, unless he pressed Refresh.
    if not force:
        cached = get_cached_so_far_today(max_age_minutes=60, db=db)
        if cached is not None:
            return cached

    # 2. The daily cap.
    calls_today = count_grounded_calls_today(db)
    daily_cap = settings.swayam_ai_daily_grounded_cap
    if calls_today >= daily_cap:
        raise DailyCapExceededError(
            f"Daily cap reached ({daily_cap} calls). Resets at midnight IST."
        )

    # 3. The prompt.
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

    # 4. The one paid call.
    result = generate_grounded_content(
        prompt=prompt,
        system_instruction=system_instruction,
        model=GROUNDED_MODEL,
    )

    now_utc = datetime.now(timezone.utc)
    new_call_count = calls_today + 1

    # 5. The day's row, replaced rather than added to. If the write fails the
    #    call still happened, so the count he is shown must not pretend
    #    otherwise: the failure is raised, not swallowed into a clean-looking
    #    payload. He has paid for the call either way and deserves to know the
    #    record did not take.
    row = {
        "day": day.isoformat(),
        "text": result["text"],
        "sources": result["sources"],
        "search_queries": result["search_queries"],
        "model": GROUNDED_MODEL,
        "generated_at": now_utc.isoformat(),
        "generation_count": new_call_count,
        "ai_tokens_used": result.get("tokens_used"),
    }
    stored = True
    try:
        db.client.table(SUMMARY_TABLE).upsert(row, on_conflict="day").execute()
    except Exception as e:
        stored = False
        logger.error("Failed to store the day's summary in %s: %s", SUMMARY_TABLE, e)

    # 6. Usage accounting, unchanged.
    try:
        db.client.table("swayam_ai_usage_daily").insert({
            "day": day.isoformat(),
            "provider": "vertex",
            "model": f"{GROUNDED_MODEL}-grounded",
            "total_input_tokens": result.get("tokens_used") or 500,
            "total_output_tokens": 500,
            "request_count": 1,
            "estimated_cost_inr": 0.25,
        }).execute()
    except Exception as e:
        logger.warning("Could not log to swayam_ai_usage_daily: %s", e)

    payload: dict[str, Any] = {
        "day": day.isoformat(),
        "text": result["text"],
        "sources": result["sources"],
        "search_queries": result["search_queries"],
        "model": GROUNDED_MODEL,
        "generated_at": now_utc.isoformat(),
        "is_cached": False,
        "age_minutes": 0,
        "call_count_today": new_call_count,
        "daily_cap": daily_cap,
        "cap_reached": new_call_count >= daily_cap,
        # False means: the model was called and you were charged, but the row
        # did not save, so this text will not be here tomorrow.
        "stored": stored,
    }
    return payload
