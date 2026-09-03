"""
End-of-day readiness reconciler for Swayam Capital.

Cross-checks Abhishek's pre-trade manual readiness self-assessment against the
nightly-synced Atlas data to record pattern-learning discrepancies without modifying
historical trade execution permissions.
"""

from datetime import date, datetime, timezone
from typing import Any, Optional
from swayam.db import db
from swayam.readiness.daily_log_reader import get_daily_log_defaults
from swayam.readiness.models import FieldDelta, ReadinessReconciliation


def reconcile_readiness_for_date(target_date: Optional[date] = None) -> ReadinessReconciliation:
    """Compares manual readiness log row against freshly synced Atlas data for that date."""
    if target_date is None:
        target_date = date.today()

    date_str = target_date.strftime("%Y-%m-%d")

    # 1. Fetch manual entry from Supabase
    client = db.client
    res = client.table("swayam_readiness_log").select("*").eq("log_date", date_str).execute()
    if not res.data:
        raise ValueError(f"No readiness log found in Supabase for date {date_str}.")

    log_row = res.data[0]
    factors = log_row.get("factors", {})
    manual_input = factors.get("input", {})

    # 2. Fetch freshly synced daily log defaults from vault
    atlas_data = get_daily_log_defaults(target_date)

    discrepancies: list[FieldDelta] = []

    # Compare Sleep
    manual_sleep_bucket = manual_input.get("sleep_hours_bucket")
    atlas_sleep_hours = atlas_data.get("sleep_hours")
    if manual_sleep_bucket and atlas_sleep_hours is not None:
        bucket_midpoints = {
            "<3": 2.0,
            "3-4": 3.5,
            "4-5": 4.5,
            "5-6": 5.5,
            "6-7": 6.5,
            "7+": 7.5,
        }
        manual_est = bucket_midpoints.get(manual_sleep_bucket, 6.0)
        delta = round(atlas_sleep_hours - manual_est, 2)
        if abs(delta) >= 1.0:
            discrepancies.append(
                FieldDelta(
                    field="sleep_hours",
                    manual=manual_sleep_bucket,
                    atlas=atlas_sleep_hours,
                    delta=delta,
                    note=f"Manual bucket {manual_sleep_bucket} vs Atlas synced {atlas_sleep_hours}h",
                )
            )

    # Compare Workout
    manual_workout = manual_input.get("workout_in_last_48h")
    atlas_workout = atlas_data.get("workout_in_last_48h")
    if manual_workout is not None and atlas_workout is not None and manual_workout != atlas_workout:
        discrepancies.append(
            FieldDelta(
                field="workout_in_last_48h",
                manual=manual_workout,
                atlas=atlas_workout,
                note="Manual workout assertion diverged from Atlas synced activity log.",
            )
        )

    reconciliation = ReadinessReconciliation(
        log_date=date_str,
        reconciled_at=datetime.now(timezone.utc).isoformat(),
        discrepancies=discrepancies,
        has_discrepancies=len(discrepancies) > 0,
    )

    # 3. Update Supabase record with reconciliation inside factors JSONB
    factors["reconciliation"] = reconciliation.model_dump()
    client.table("swayam_readiness_log").update({"factors": factors}).eq("log_date", date_str).execute()

    return reconciliation
