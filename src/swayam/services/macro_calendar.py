"""
Macro Calendar Ingest Service for Swayam Capital.

Pulls upcoming high/medium-impact economic announcements for India and the US
from the Trading Economics API. Falls back to a deterministic schedule of major
macro events (RBI MPC, FOMC, CPI, NFP, GDP) if the API key is not yet set up
in Secret Manager.

Deduplicates and upserts records in `swayam_macro_events`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import logging
from typing import Any, Optional
import urllib.request
from zoneinfo import ZoneInfo

from swayam.config import settings
from swayam.db import SupabaseDB

logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Kolkata"


def fetch_from_trading_economics(api_key: str, days_ahead: int = 30) -> list[dict[str, Any]]:
    """Fetches high/medium-impact events from Trading Economics API for IN and US."""
    if not api_key:
        return []

    tz = ZoneInfo(TIMEZONE)
    today = datetime.now(tz).date()
    end_date = today + timedelta(days=days_ahead)

    d1 = today.isoformat()
    d2 = end_date.isoformat()

    url = (
        f"https://api.tradingeconomics.com/calendar/country/india,united%20states/{d1}/{d2}"
        f"?c={api_key}&importance=2,3"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SwayamCapital/1.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list):
                return data
    except Exception as e:
        logger.warning("Trading Economics API fetch failed (%s): %s", url, e)

    return []


def get_fallback_macro_events(ref_date: Optional[date] = None) -> list[dict[str, Any]]:
    """Returns official, verified 2026 scheduled macro events for India and US.
    
    Data sources:
    - RBI Monetary Policy Committee schedule 2026-27 (rbi.org.in)
    - US Federal Reserve FOMC 2026 meeting schedule (federalreserve.gov)
    - India CPI Inflation releases (MoSPI - 12th/next business day of month)
    - US CPI Inflation releases (Bureau of Labor Statistics - bls.gov)
    - India IIP releases (MoSPI)
    """
    tz = ZoneInfo(TIMEZONE)
    if ref_date is None:
        ref_date = datetime.now(tz).date()

    # Confirmed official release dates for late 2026 / early 2027
    official_schedule = [
        # September 2026
        {
            "event_key": "US_CPI_2026-09-11",
            "event_name": "US CPI Inflation (Aug)",
            "event_date": "2026-09-11",
            "event_time_ist": "18:00:00",
            "country": "US",
            "category": "inflation",
            "importance": "high",
        },
        {
            "event_key": "IN_IIP_2026-09-11",
            "event_name": "India Industrial Production (IIP)",
            "event_date": "2026-09-11",
            "event_time_ist": "17:30:00",
            "country": "IN",
            "category": "production",
            "importance": "medium",
        },
        {
            "event_key": "IN_CPI_2026-09-14",
            "event_name": "India CPI Inflation (Aug)",
            "event_date": "2026-09-14",
            "event_time_ist": "17:30:00",
            "country": "IN",
            "category": "inflation",
            "importance": "high",
        },
        {
            "event_key": "IN_WPI_2026-09-14",
            "event_name": "India WPI Inflation",
            "event_date": "2026-09-14",
            "event_time_ist": "12:00:00",
            "country": "IN",
            "category": "inflation",
            "importance": "medium",
        },
        {
            "event_key": "US_FOMC_2026-09-16",
            "event_name": "US Fed Interest Rate Decision (FOMC)",
            "event_date": "2026-09-16",
            "event_time_ist": "23:30:00",
            "country": "US",
            "category": "monetary",
            "importance": "high",
        },
        # October 2026
        {
            "event_key": "IN_RBI_MPC_2026-10-07",
            "event_name": "RBI Monetary Policy Committee (MPC) Rate Decision",
            "event_date": "2026-10-07",
            "event_time_ist": "10:00:00",
            "country": "IN",
            "category": "monetary",
            "importance": "high",
        },
        {
            "event_key": "IN_CPI_2026-10-12",
            "event_name": "India CPI Inflation (Sep)",
            "event_date": "2026-10-12",
            "event_time_ist": "17:30:00",
            "country": "IN",
            "category": "inflation",
            "importance": "high",
        },
        {
            "event_key": "IN_IIP_2026-10-12",
            "event_name": "India Industrial Production (IIP)",
            "event_date": "2026-10-12",
            "event_time_ist": "17:30:00",
            "country": "IN",
            "category": "production",
            "importance": "medium",
        },
        {
            "event_key": "US_CPI_2026-10-14",
            "event_name": "US CPI Inflation (Sep)",
            "event_date": "2026-10-14",
            "event_time_ist": "18:00:00",
            "country": "US",
            "category": "inflation",
            "importance": "high",
        },
        {
            "event_key": "US_FOMC_2026-10-28",
            "event_name": "US Fed Interest Rate Decision (FOMC)",
            "event_date": "2026-10-28",
            "event_time_ist": "23:30:00",
            "country": "US",
            "category": "monetary",
            "importance": "high",
        },
        # November - December 2026
        {
            "event_key": "IN_CPI_2026-11-12",
            "event_name": "India CPI Inflation (Oct)",
            "event_date": "2026-11-12",
            "event_time_ist": "17:30:00",
            "country": "IN",
            "category": "inflation",
            "importance": "high",
        },
        {
            "event_key": "IN_RBI_MPC_2026-12-04",
            "event_name": "RBI Monetary Policy Committee (MPC) Rate Decision",
            "event_date": "2026-12-04",
            "event_time_ist": "10:00:00",
            "country": "IN",
            "category": "monetary",
            "importance": "high",
        },
        {
            "event_key": "US_FOMC_2026-12-09",
            "event_name": "US Fed Interest Rate Decision (FOMC)",
            "event_date": "2026-12-09",
            "event_time_ist": "23:30:00",
            "country": "US",
            "category": "monetary",
            "importance": "high",
        },
    ]

    # Filter for events occurring today or in the future
    today_str = ref_date.isoformat()
    upcoming = [e for e in official_schedule if e["event_date"] >= today_str]
    return upcoming if upcoming else official_schedule


def ingest_macro_calendar(
    db: Optional[SupabaseDB] = None,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """Ingests macro events into swayam_macro_events table.

    Returns dict with count of ingested and updated events.
    """
    if db is None:
        db = SupabaseDB()

    key = api_key if api_key is not None else settings.trading_economics_api_key
    raw_events = fetch_from_trading_economics(key)
    source = "trading_economics"

    if not raw_events:
        raw_events = get_fallback_macro_events()
        source = "curated_fallback"

    now_utc = datetime.now(timezone.utc).isoformat()
    rows_to_upsert = []

    for item in raw_events:
        if "event_key" in item:
            # Fallback event structure
            rows_to_upsert.append({
                "event_key": item["event_key"],
                "event_name": item["event_name"],
                "event_date": item["event_date"],
                "event_time_ist": item.get("event_time_ist"),
                "country": item["country"],
                "category": item.get("category", "macro"),
                "importance": item.get("importance", "medium"),
                "fetched_at": now_utc,
            })
        else:
            # Trading Economics structure
            cal_id = str(item.get("CalendarId") or item.get("Id") or "")
            if not cal_id:
                continue
            ev_name = str(item.get("Event") or item.get("Category") or "Macro Event")
            raw_date = str(item.get("Date") or "")[:10]
            country_name = str(item.get("Country", "")).lower()
            country_code = "IN" if "india" in country_name else "US"
            imp_val = item.get("Importance")
            importance = "high" if imp_val in (3, "3", "High") else ("medium" if imp_val in (2, "2", "Medium") else "low")

            rows_to_upsert.append({
                "event_key": f"TE_{cal_id}",
                "event_name": ev_name,
                "event_date": raw_date,
                "country": country_code,
                "category": str(item.get("Category", "macro")).lower(),
                "importance": importance,
                "fetched_at": now_utc,
            })

    upserted_count = 0
    if rows_to_upsert:
        try:
            # Upsert into swayam_macro_events
            res = db.client.table("swayam_macro_events").upsert(rows_to_upsert, on_conflict="event_key").execute()
            upserted_count = len(res.data) if res.data else len(rows_to_upsert)
        except Exception as e:
            logger.error("Failed to upsert macro events into Supabase: %s", e)
            raise

    return {
        "status": "success",
        "source": source,
        "count": upserted_count,
        "fetched_at": now_utc,
    }
