"""
Script to set the alcohol baseline date in Supabase (swayam_config table).
Used to seed Abhishek's real sobriety start date for streak calculation.

Usage:
    python scripts/set_alcohol_baseline.py --date YYYY-MM-DD
"""

import argparse
from datetime import date
import sys
from swayam.db import db


def set_alcohol_baseline(baseline_date_str: str) -> None:
    try:
        baseline_date = date.fromisoformat(baseline_date_str)
    except ValueError:
        print(f"Error: '{baseline_date_str}' is not a valid date in YYYY-MM-DD format.")
        sys.exit(1)

    today = date.today()
    if baseline_date > today:
        print(f"Error: Baseline date cannot be in the future (today is {today}).")
        sys.exit(1)

    streak_days = (today - baseline_date).days

    client = db.client

    # 1. Upsert last_alcohol_date
    client.table("swayam_config").upsert(
        {"key": "last_alcohol_date", "value": baseline_date_str},
        on_conflict="key",
    ).execute()

    # 2. Upsert current_alcohol_streak_days
    client.table("swayam_config").upsert(
        {"key": "current_alcohol_streak_days", "value": str(streak_days)},
        on_conflict="key",
    ).execute()

    print(
        f"✓ Success: Alcohol baseline set to {baseline_date_str}.\n"
        f"  Current alcohol-free streak: {streak_days} days.\n"
        f"  Supabase table swayam_config updated."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Set alcohol baseline date for Swayam Capital.")
    parser.add_argument("--date", required=True, help="Sobriety start date (or last alcohol date) in YYYY-MM-DD format.")
    args = parser.parse_args()
    set_alcohol_baseline(args.date)
