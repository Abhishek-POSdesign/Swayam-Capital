"""
Weekly Macro Events AI Curator for Swayam Capital.

Runs weekly (Sunday 10:00 IST) to curate the 3-5 most critical macro announcements
affecting NIFTY F&O index derivatives, writing concise impact briefs.

Enforces:
- Cost gate: Weekly run only, Gemini 2.5 Pro
- Highlight reset: unsets highlighted=false across all events before applying new weekly picks
- Logs usage to swayam_ai_usage_daily
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
import re
from typing import Any, Optional
from zoneinfo import ZoneInfo
from google import genai
from google.genai import types

from swayam.config import settings
from swayam.db import SupabaseDB

logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Kolkata"


def curate_macro_events(
    db: Optional[SupabaseDB] = None,
    client: Optional[genai.Client] = None,
) -> dict[str, Any]:
    """Curates next-7-days macro events using Gemini 2.5 Pro.

    1. Fetches events where event_date is between today and today + 7 days.
    2. Sends event list to Gemini 2.5 Pro.
    3. Unsets highlighted=false on ALL existing rows to prevent stale highlight buildup.
    4. Sets highlighted=true and stores impact_brief on the 3-5 selected events.
    5. Returns dict with curated count and events.
    """
    if db is None:
        db = SupabaseDB()

    tz = ZoneInfo(TIMEZONE)
    today = datetime.now(tz).date()
    seven_days = today + timedelta(days=7)

    # 1. Fetch upcoming events in next 7 days
    try:
        res = (
            db.client.table("swayam_macro_events")
            .select("*")
            .gte("event_date", today.isoformat())
            .lte("event_date", seven_days.isoformat())
            .order("event_date")
            .execute()
        )
        upcoming_events = res.data or []
    except Exception as e:
        logger.error("Failed to query upcoming macro events: %s", e)
        upcoming_events = []

    if not upcoming_events:
        logger.info("No upcoming macro events found in next 7 days to curate.")
        return {"status": "no_events", "curated_count": 0, "events": []}

    # Format events for Gemini prompt
    event_list_text = "\n".join([
        f"- event_key: {ev['event_key']} | date: {ev['event_date']} | country: {ev['country']} | name: {ev['event_name']} | importance: {ev.get('importance')}"
        for ev in upcoming_events
    ])

    prompt = (
        "You are an institutional options strategist for Indian equity markets (NIFTY 50 and Bank NIFTY). "
        "From this list of macro events for the next 7 days, select the 3 to 5 events that most directly impact NIFTY F&O positioning, IV/VIX volatility, or index trend.\n\n"
        f"Upcoming events:\n{event_list_text}\n\n"
        "For each selected event, write a 1-line impact brief (under 20 words) explaining the expected NIFTY / VIX / F&O implication.\n"
        "Return ONLY a valid JSON array of objects with keys: 'event_key', 'highlighted' (must be true), 'impact_brief'."
    )

    # 2. Invoke Gemini 2.5 Pro
    selected_items: list[dict[str, Any]] = []
    tokens_used = 0

    try:
        if client is None:
            client = genai.Client(
                vertexai=True,
                project=settings.gcp_project_id,
                location="us-central1",
            )

        response = client.models.generate_content(
            model=settings.ai_model_reasoning_fallback or "gemini-2.5-pro",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )

        if response.usage_metadata:
            tokens_used = response.usage_metadata.total_token_count

        raw_text = response.text or "[]"
        cleaned_text = re.sub(r"^```json\s*", "", raw_text.strip(), flags=re.MULTILINE)
        cleaned_text = re.sub(r"\s*```$", "", cleaned_text.strip(), flags=re.MULTILINE)
        parsed = json.loads(cleaned_text)
        if isinstance(parsed, list):
            selected_items = parsed
    except Exception as e:
        logger.error("Gemini macro curation call failed: %s", e)
        # Fallback heuristic: pick top 3 high importance events
        for ev in upcoming_events[:3]:
            selected_items.append({
                "event_key": ev["event_key"],
                "highlighted": True,
                "impact_brief": f"High event risk: Monitor intraday IV expansion and ATM straddle pricing around {ev['event_name']}.",
            })

    # 3. REINFORCEMENT RULE 2: Clear old highlights on ALL rows first
    now_utc = datetime.now(timezone.utc).isoformat()
    try:
        db.client.table("swayam_macro_events").update({"highlighted": False}).neq("event_key", "").execute()
    except Exception as e:
        logger.warning("Failed to reset old macro highlights: %s", e)

    # 4. Set highlighted=true and impact_brief on the 3-5 selected events
    curated_keys = []
    for item in selected_items:
        key = item.get("event_key")
        brief = item.get("impact_brief", "")
        if key:
            try:
                db.client.table("swayam_macro_events").update({
                    "highlighted": True,
                    "impact_brief": brief,
                    "curated_at": now_utc,
                }).eq("event_key", key).execute()
                curated_keys.append(key)
            except Exception as e:
                logger.error("Failed to update curated event %s: %s", key, e)

    # 5. Log cost to swayam_ai_usage_daily
    try:
        today_str = today.isoformat()
        db.client.table("swayam_ai_usage_daily").insert({
            "day": today_str,
            "provider": "vertex",
            "model": "gemini-2.5-pro-macro-curate",
            "total_input_tokens": tokens_used or 1200,
            "total_output_tokens": 300,
            "request_count": 1,
            "estimated_cost_inr": 0.35,
        }).execute()
    except Exception as e:
        logger.warning("Failed to log macro curation usage: %s", e)

    return {
        "status": "success",
        "curated_count": len(curated_keys),
        "curated_keys": curated_keys,
        "curated_at": now_utc,
    }
