"""
Expiry calculation service for Swayam Capital.

Authoritative source: FYERS contract master (NSE_FO.csv).
Under SEBI circular, NIFTY derivatives expire weekly on Tuesdays (previously Thursdays),
and monthly on the last Tuesday of the month.
Holidays are adjusted to the previous trading day according to official NSE holiday lists.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
import json
import logging
from pathlib import Path
from typing import Any, Optional
import urllib.request
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Kolkata"
FYERS_NSE_FO_URL = "https://public.fyers.in/sym_details/NSE_FO.csv"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
HOLIDAYS_FILE = REPO_ROOT / "data" / "nse_holidays_2026.json"
CACHE_FILE = REPO_ROOT / "data" / "NSE_FO_cache.csv"

_cached_holidays: Optional[set[date]] = None
_cached_expiries: Optional[tuple[datetime, list[date]]] = None


def get_nse_holidays() -> set[date]:
    """Loads NSE trading holidays from json file."""
    global _cached_holidays
    if _cached_holidays is not None:
        return _cached_holidays

    holidays: set[date] = set()
    if HOLIDAYS_FILE.exists():
        try:
            with open(HOLIDAYS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for year_key, list_items in data.items():
                    for item in list_items:
                        d = date.fromisoformat(item["date"])
                        holidays.add(d)
        except Exception as e:
            logger.error("Failed to load NSE holidays file %s: %e", HOLIDAYS_FILE, e)

    _cached_holidays = holidays
    return holidays


def is_trading_day(d: date, holidays: Optional[set[date]] = None) -> bool:
    """Checks whether a given date is an active NSE trading day (not weekend, not holiday)."""
    if d.weekday() >= 5:  # Saturday or Sunday
        return False
    if holidays is None:
        holidays = get_nse_holidays()
    return d not in holidays


def adjust_to_previous_trading_day(d: date, holidays: Optional[set[date]] = None) -> date:
    """If date is weekend or holiday, steps backward until a trading day is found."""
    if holidays is None:
        holidays = get_nse_holidays()
    curr = d
    while not is_trading_day(curr, holidays):
        curr -= timedelta(days=1)
    return curr


def count_trading_sessions(start_date: date, end_date: date, include_start: bool = True) -> int:
    """Counts trading days between start_date and end_date.

    If start_date == end_date and it's a trading day, returns 1 if include_start else 0.
    """
    if end_date < start_date:
        return 0

    holidays = get_nse_holidays()
    count = 0
    curr = start_date if include_start else start_date + timedelta(days=1)
    while curr <= end_date:
        if is_trading_day(curr, holidays):
            count += 1
        curr += timedelta(days=1)
    return count


def fetch_nifty_expiries_from_fyers() -> list[date]:
    """Reads NIFTY option and future contracts from FYERS NSE_FO master."""
    global _cached_expiries
    now = datetime.now()

    # In-memory cache valid for 6 hours
    if _cached_expiries is not None:
        cache_time, expiries = _cached_expiries
        if (now - cache_time).total_seconds() < 21600:
            return expiries

    csv_data = None
    # 1. Try downloading fresh from FYERS public URL
    try:
        req = urllib.request.Request(
            FYERS_NSE_FO_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
            csv_data = content
            # Save to disk cache
            try:
                CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception as e:
                logger.warning("Could not write to disk cache: %s", e)
    except Exception as e:
        logger.warning("Failed to fetch fresh FYERS contract master from %s: %s", FYERS_NSE_FO_URL, e)
        # 2. Try loading from disk cache
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    csv_data = f.read()
            except Exception as read_err:
                logger.error("Could not read disk cache: %s", read_err)

    tz = ZoneInfo(TIMEZONE)
    extracted_dates: set[date] = set()

    if csv_data:
        reader = csv.reader(csv_data.splitlines())
        for row in reader:
            if len(row) > 13 and row[13] == "NIFTY":
                try:
                    epoch = int(row[8])
                    exp_dt = datetime.fromtimestamp(epoch, tz=tz).date()
                    extracted_dates.add(exp_dt)
                except (ValueError, IndexError):
                    continue

    if not extracted_dates:
        # Fallback heuristic if network and cache both fail
        logger.warning("Falling back to computed Tuesday expiries.")
        extracted_dates = _generate_fallback_tuesdays()

    sorted_expiries = sorted(list(extracted_dates))
    _cached_expiries = (now, sorted_expiries)
    return sorted_expiries


def _generate_fallback_tuesdays() -> set[date]:
    """Fallback generator for Tuesday expiries if contract master is completely unreachable."""
    holidays = get_nse_holidays()
    res = set()
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    curr = today
    # Find next 20 Tuesdays
    while len(res) < 20:
        if curr.weekday() == 1:  # Tuesday
            adjusted = adjust_to_previous_trading_day(curr, holidays)
            res.add(adjusted)
        curr += timedelta(days=1)
    return res


def get_expiry_metadata(ref_date: Optional[date] = None) -> dict[str, Any]:
    """Authoritative expiry metadata provider.

    Returns:
        {
            "weekly_expiry": "2026-09-08",
            "weekly_dte": {
                "calendar_days": 2,
                "trading_sessions": 2,
                "formatted": "2 calendar days · 2 trading sessions"
            },
            "monthly_expiry": "2026-09-29",
            "monthly_dte": {
                "calendar_days": 23,
                "trading_sessions": 16,
                "formatted": "23 calendar days · 16 trading sessions"
            },
            "is_rollover_window": False,
            "upcoming_expiries": ["2026-09-08", "2026-09-15", "2026-09-22", "2026-09-29", ...]
        }
    """
    tz = ZoneInfo(TIMEZONE)
    if ref_date is None:
        ref_date = datetime.now(tz).date()

    all_expiries = fetch_nifty_expiries_from_fyers()
    # Filter upcoming expiries (today or future)
    upcoming = [d for d in all_expiries if d >= ref_date]
    if not upcoming:
        upcoming = sorted(list(_generate_fallback_tuesdays()))

    weekly_expiry = upcoming[0]

    # Find monthly expiry:
    # Monthly expiry is the last expiry of the ref_date's calendar month,
    # or if all expiries of this month have passed, the last expiry of next month.
    current_month_expiries = [d for d in upcoming if d.year == ref_date.year and d.month == ref_date.month]
    if current_month_expiries:
        # Check all expiries in master for this month to get the true last one
        all_month_expiries = [d for d in all_expiries if d.year == ref_date.year and d.month == ref_date.month]
        monthly_expiry = all_month_expiries[-1]
    else:
        # Look for next month's expiries
        next_month_expiries = [d for d in upcoming if (d.year, d.month) > (ref_date.year, ref_date.month)]
        if next_month_expiries:
            target_year, target_month = next_month_expiries[0].year, next_month_expiries[0].month
            month_group = [d for d in all_expiries if d.year == target_year and d.month == target_month]
            monthly_expiry = month_group[-1]
        else:
            monthly_expiry = upcoming[-1]

    # Calculate DTEs
    weekly_cal_days = (weekly_expiry - ref_date).days
    weekly_trading_sessions = count_trading_sessions(ref_date, weekly_expiry, include_start=True)

    monthly_cal_days = (monthly_expiry - ref_date).days
    monthly_trading_sessions = count_trading_sessions(ref_date, monthly_expiry, include_start=True)

    # Rollover window: only shown last 3 sessions before monthly expiry
    is_rollover_window = (monthly_trading_sessions <= 3)

    return {
        "weekly_expiry": weekly_expiry.isoformat(),
        "weekly_dte": {
            "calendar_days": weekly_cal_days,
            "trading_sessions": weekly_trading_sessions,
            "formatted": f"{weekly_cal_days} calendar days · {weekly_trading_sessions} trading sessions",
        },
        "monthly_expiry": monthly_expiry.isoformat(),
        "monthly_dte": {
            "calendar_days": monthly_cal_days,
            "trading_sessions": monthly_trading_sessions,
            "formatted": f"{monthly_cal_days} calendar days · {monthly_trading_sessions} trading sessions",
        },
        "is_rollover_window": is_rollover_window,
        "upcoming_expiries": [d.isoformat() for d in upcoming[:10]],
    }
