"""
AI Context Builder for Swayam Capital.

Assembles runtime intelligence context (highlighted macro events, risk gates, market regime)
to inject into AI system instructions during conversational planning sessions.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Optional
from zoneinfo import ZoneInfo

from swayam.db import SupabaseDB

logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Kolkata"


def build_planning_context(db: Optional[SupabaseDB] = None) -> str:
    """Builds a concise planning context string containing upcoming highlighted macro events.

    Returns:
        Formatted context string ready for system instruction injection, e.g.:
        "Upcoming macro events (next 7 days):
         - India CPI Inflation (YoY) (2026-09-10): Monitor RBI trajectory; IV crush potential post-release.
         Factor these into any multi-day trade recommendation."
    """
    if db is None:
        db = SupabaseDB()

    tz = ZoneInfo(TIMEZONE)
    today = datetime.now(tz).date()
    seven_days = today + timedelta(days=7)

    events = []
    try:
        res = (
            db.client.table("swayam_macro_events")
            .select("event_name, event_date, country, impact_brief")
            .eq("highlighted", True)
            .gte("event_date", today.isoformat())
            .lte("event_date", seven_days.isoformat())
            .order("event_date")
            .limit(5)
            .execute()
        )
        events = res.data or []
    except Exception as e:
        logger.warning("Failed to fetch highlighted macro events for planning context: %s", e)

    if not events:
        return ""

    lines = ["Upcoming macro events (next 7 days):"]
    for ev in events:
        name = ev.get("event_name")
        d = ev.get("event_date")
        country = ev.get("country", "")
        brief = ev.get("impact_brief") or "High event risk for NIFTY F&O."
        lines.append(f"- [{country}] {name} ({d}): {brief}")

    lines.append("Factor these events into any multi-day trade, spread selection, or overnight carry recommendation.")
    return "\n".join(lines)
