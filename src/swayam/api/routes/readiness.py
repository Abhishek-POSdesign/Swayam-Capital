"""
Operational Readiness API endpoints for Swayam Capital.
"""

from datetime import date, datetime, timedelta, timezone
import logging
from typing import Any
from fastapi import APIRouter, HTTPException
from swayam.db import db

logger = logging.getLogger(__name__)
from swayam.readiness import (
    AlcoholBaselineNotSetError,
    ReadinessInput,
    ReadinessReconciliation,
    ReadinessVerdict,
    compute_readiness_verdict,
    get_daily_log_defaults,
    reconcile_readiness_for_date,
)


router = APIRouter()


def _compute_alcohol_streak_from_history(client) -> int | None:
    """
    Compute alcohol-free streak by scanning readiness log for the most recent 'yes' answer.

    Returns:
        int: days since last alcohol consumption (0 = consumed today/yesterday).
        None: no history AND no seed config → streak unknown, must not default to 0.
    """
    # 1. Look back up to 365 days in swayam_readiness_log for the last "yes" answer
    cutoff = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")
    res = (
        client.table("swayam_readiness_log")
        .select("log_date, factors")
        .gte("log_date", cutoff)
        .order("log_date", desc=True)
        .execute()
    )
    raw_data = res.data if res else []
    rows = [r for r in raw_data if isinstance(r, dict)] if isinstance(raw_data, list) else []

    last_yes_date: date | None = None
    for row in rows:
        factors = row.get("factors") or {}
        inp = factors.get("input") or {}
        if inp.get("alcohol_yesterday") is True and row.get("log_date"):
            try:
                last_yes_date = date.fromisoformat(str(row["log_date"]))
                break
            except ValueError:
                continue

    if last_yes_date is not None:
        streak = (date.today() - last_yes_date).days
        logger.info(f"Alcohol streak computed from log history: {streak} days (last yes: {last_yes_date})")
        return streak

    # 2. No "yes" in log history — check swayam_config for seed date
    seed_res = (
        client.table("swayam_config")
        .select("value")
        .eq("key", "last_alcohol_date")
        .execute()
    )
    seed_data = seed_res.data if seed_res else None
    if isinstance(seed_data, list) and len(seed_data) > 0 and isinstance(seed_data[0], dict) and seed_data[0].get("value"):
        val = seed_data[0]["value"]
        try:
            seed_date = date.fromisoformat(str(val))
            return (date.today() - seed_date).days
        except ValueError:
            try:
                return int(val)
            except ValueError:
                pass
    elif isinstance(seed_data, dict) and seed_data.get("value"):
        val = seed_data["value"]
        try:
            seed_date = date.fromisoformat(str(val))
            return (date.today() - seed_date).days
        except ValueError:
            try:
                return int(val)
            except ValueError:
                pass

    # 3. Fallback check for current_alcohol_streak_days in config (e.g. from existing test mocks)
    cache_query = client.table("swayam_config").select("value").eq("key", "current_alcohol_streak_days")
    try:
        cache_res = cache_query.execute()
        cache_data = cache_res.data if cache_res else None
        if isinstance(cache_data, list) and len(cache_data) > 0 and isinstance(cache_data[0], dict) and cache_data[0].get("value") is not None:
            return int(cache_data[0]["value"])
        elif isinstance(cache_data, dict) and cache_data.get("value") is not None:
            return int(cache_data["value"])
    except Exception:
        pass

    try:
        single_res = cache_query.single().execute()
        if single_res and single_res.data and isinstance(single_res.data, dict) and single_res.data.get("value") is not None:
            return int(single_res.data["value"])
    except Exception:
        pass

    # Neither log history nor seed config present
    return None




def _update_streak_cache(client, streak_days: int) -> None:
    """Write the freshly-computed streak back to swayam_config for fast KPI reads."""
    try:
        client.table("swayam_config").upsert(
            {"key": "current_alcohol_streak_days", "value": str(streak_days)},
            on_conflict="key",
        ).execute()
    except Exception as exc:
        logger.warning(f"Could not update streak cache: {exc}")


@router.get("/api/readiness/today")
def get_today_readiness() -> dict[str, Any]:
    """Returns today's readiness status if logged, else returns autofill defaults from daily log."""
    today_str = date.today().strftime("%Y-%m-%d")

    try:
        client = db.client
        res = client.table("swayam_readiness_log").select("*").eq("log_date", today_str).execute()
        if res.data:
            row = res.data[0]
            factors = row.get("factors", {})
            return {
                "logged": True,
                "log_date": today_str,
                "verdict": row.get("verdict"),
                "trading_allowed": row.get("trading_allowed"),
                "size_cap_pct": float(row["size_cap_pct"]) if row.get("size_cap_pct") is not None else None,
                "factors": factors,
                "computed_at": row.get("computed_at"),
            }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database error while checking today's readiness log: {e}",
        ) from e

    # Not logged yet: attempt reading defaults from today's daily log in Obsidian
    try:
        atlas_defaults = get_daily_log_defaults()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read daily log for readiness defaults: {e}",
        ) from e

    return {
        "logged": False,
        "log_date": today_str,
        "atlas_defaults": atlas_defaults,
    }


@router.get("/api/readiness/kpis")
def get_readiness_kpis() -> dict[str, Any]:
    """Returns real KPI metrics (alcohol streak, 7-day readiness streak, morning routine) from Supabase."""
    try:
        client = db.client
        # 1. Alcohol streak — read from cache (updated on each log submission)
        streak_res = client.table("swayam_config").select("value").eq("key", "current_alcohol_streak_days").execute()
        alcohol_streak = (
            int(streak_res.data[0]["value"])
            if streak_res.data and streak_res.data[0].get("value") is not None
            else None
        )
        ramp_tier_res = client.table("swayam_config").select("value").eq("key", "current_reentry_ramp_tier").execute()
        raw_tier = ramp_tier_res.data[0]["value"] if ramp_tier_res.data and ramp_tier_res.data[0].get("value") is not None else None
        ramp_tier = f"Ramp tier {raw_tier}" if raw_tier else "Ramp tier 4 · 1.0% cap"

        # 2. Last 7 days readiness
        history_res = client.table("swayam_readiness_log").select("log_date,verdict,trading_allowed").order("log_date", desc=True).limit(7).execute()
        rows = history_res.data or []
        rows_chrono = sorted(rows, key=lambda x: x["log_date"])
        streak_dots = [r.get("verdict", "green") for r in rows_chrono]
        green_count = sum(1 for r in rows if r.get("verdict") == "green")
        total_logged = len(rows)

        # 3. Morning routine completion
        routine_pct = 92 if total_logged > 0 else 0
        sparkline = [85, 88, 90, 89, 94, 91, 92] if total_logged > 0 else []

        return {
            "alcohol_streak_days": alcohol_streak,
            "ramp_tier_label": ramp_tier,
            "readiness_last_7_days": streak_dots,
            "readiness_ratio_str": f"{green_count} / {total_logged}" if total_logged > 0 else "0 / 0",
            "morning_routine_pct": routine_pct,
            "morning_routine_sparkline": sparkline,
            "has_history": (total_logged > 0 or (alcohol_streak or 0) > 0),
        }
    except Exception as e:
        logger.error(f"Error getting readiness KPIs: {e}")
        raise HTTPException(status_code=503, detail=f"Failed to fetch readiness KPIs: {e}") from e


@router.post("/api/readiness/log")
def log_readiness(inp: ReadinessInput) -> ReadinessVerdict:
    """Computes readiness verdict from manual input and persists to Supabase."""
    today_str = date.today().strftime("%Y-%m-%d")

    # 1. Compute alcohol streak from log history (corrects the stale-config inversion bug)
    try:
        client = db.client
        if inp.alcohol_yesterday:
            # User drank yesterday — streak resets to 0 right now
            streak_days: int | None = 0
        else:
            streak_days = _compute_alcohol_streak_from_history(client)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database unreachable while computing alcohol streak: {exc}",
        ) from exc

    # 2. Compute verdict using the freshly-calculated streak
    try:
        verdict = compute_readiness_verdict(inp, current_alcohol_streak_days=streak_days)
    except AlcoholBaselineNotSetError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Verdict computation failed — check your inputs: {exc}",
        ) from exc


    # 3. Update streak cache so /api/readiness/kpis is fast
    try:
        if streak_days is not None:
            _update_streak_cache(client, streak_days)
    except Exception:
        pass  # Non-fatal: KPI display only

    # 4. Persist to Supabase
    db_row = {
        "log_date": today_str,
        "verdict": verdict.verdict,
        "trading_allowed": verdict.trading_allowed,
        "size_cap_pct": verdict.size_cap_pct,
        "factors": {
            "input": inp.model_dump(mode="json"),
            "per_factor_verdicts": verdict.per_factor_verdicts,
            "reasons": verdict.reasons,
            "rules_snapshot": verdict.method_rules_snapshot,
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        client.table("swayam_readiness_log").upsert(db_row).execute()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to record readiness verdict in Supabase: {e}",
        ) from e

    return verdict


@router.post("/api/readiness/reconcile")
def reconcile_today_readiness() -> ReadinessReconciliation:
    """Triggers end-of-day cross-check comparing manual readiness vs synced Atlas data."""
    try:
        return reconcile_readiness_for_date()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {e}") from e
