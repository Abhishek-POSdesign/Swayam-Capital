"""
Operational Readiness verdict calculator for Swayam Capital.

Evaluates subjective pre-trade inputs against Method rules parsed from the
Obsidian vault using TolerantComparator.
"""

from typing import Literal, Optional
from swayam.config import settings
from swayam.readiness.models import ReadinessInput, ReadinessVerdict
from swayam.rules_engine import TolerantComparator
from swayam.vault_reader import MethodRules, vault_reader


def compute_readiness_verdict(
    inp: ReadinessInput,
    rules: Optional[MethodRules] = None,
    current_alcohol_streak_days: Optional[int] = None,
) -> ReadinessVerdict:
    """Computes operational readiness verdict from user input and live Method rules."""
    if rules is None:
        rules = vault_reader.load_rules(force_reload=False)

    comparator = TolerantComparator(tolerance_pct=settings.default_tolerance_pct)
    per_factor: dict[str, Literal["green", "yellow", "red"]] = {}
    reasons: list[str] = []

    # -------------------------------------------------------------
    # 1. Sleep Evaluation
    # -------------------------------------------------------------
    bucket_ranges = {
        "<3": (0.0, 3.0),
        "3-4": (3.0, 4.0),
        "4-5": (4.0, 5.0),
        "5-6": (5.0, 6.0),
        "6-7": (6.0, 7.0),
        "7+": (7.0, 12.0),
    }
    lower_bound, upper_bound = bucket_ranges.get(inp.sleep_hours_bucket, (0.0, 0.0))

    if comparator.within_cap(lower_bound, rules.sleep_no_trade_threshold_hours - 0.001) and lower_bound < rules.sleep_no_trade_threshold_hours:
        per_factor["sleep"] = "red"
        reasons.append(f"Sleep {inp.sleep_hours_bucket}h is below {rules.sleep_no_trade_threshold_hours:.1f}h threshold: Trading blocked.")
    elif lower_bound >= rules.sleep_reduced_size_hours_min and lower_bound < rules.sleep_reduced_size_hours_max:
        per_factor["sleep"] = "yellow"
        reasons.append(f"Sleep {inp.sleep_hours_bucket}h warrants reduced sizing ({int(rules.sleep_reduced_size_factor * 100)}%).")
    else:
        per_factor["sleep"] = "green"

    # -------------------------------------------------------------
    # 2. Alcohol & Lockout Evaluation
    # -------------------------------------------------------------
    if inp.alcohol_yesterday:
        per_factor["alcohol"] = "red"
        reasons.append(f"Alcohol consumed yesterday: {rules.alcohol_lockout_days}-day lockout active.")
    elif current_alcohol_streak_days is not None and current_alcohol_streak_days < rules.alcohol_lockout_days:
        per_factor["alcohol"] = "red"
        reasons.append(f"Alcohol lockout active: Day {current_alcohol_streak_days} of {rules.alcohol_lockout_days}.")
    else:
        per_factor["alcohol"] = "green"

    # -------------------------------------------------------------
    # 3. Workout Evaluation (Positional Discipline)
    # -------------------------------------------------------------
    if inp.workout_in_last_48h:
        per_factor["workout"] = "green"
    else:
        per_factor["workout"] = "yellow"
        reasons.append("No workout in last 48h: Exercise positional discipline only.")

    # -------------------------------------------------------------
    # 4. Journal / Mood Evaluation
    # -------------------------------------------------------------
    if inp.journal_mood == "angry_grief":
        per_factor["mood"] = "red"
        reasons.append("Mood marked as Angry/Grief: Emotional volatility blocks trading.")
    elif inp.journal_mood in ("tired", "off"):
        per_factor["mood"] = "yellow"
        reasons.append(f"Sub-optimal mood ({inp.journal_mood}): Exercise heightened caution.")
    else:
        per_factor["mood"] = "green"

    # -------------------------------------------------------------
    # 5. Life Stressor Evaluation
    # -------------------------------------------------------------
    if inp.life_stressor != "none":
        per_factor["stressor"] = "yellow"
        note = f" - {inp.stressor_note}" if inp.stressor_note else ""
        reasons.append(f"Active life stressor ({inp.life_stressor}){note}: Tighten stops on positions.")
    else:
        per_factor["stressor"] = "green"

    # -------------------------------------------------------------
    # Composite Verdict & Sizing Calculation
    # -------------------------------------------------------------
    if any(v == "red" for v in per_factor.values()):
        composite_verdict: Literal["green", "yellow", "red"] = "red"
        trading_allowed = False
        size_cap_pct = None
    elif any(v == "yellow" for v in per_factor.values()):
        composite_verdict = "yellow"
        trading_allowed = True
        if per_factor.get("sleep") == "yellow":
            size_cap_pct = rules.per_trade_risk_pct * rules.sleep_reduced_size_factor
        else:
            size_cap_pct = rules.per_trade_risk_pct
    else:
        composite_verdict = "green"
        trading_allowed = True
        size_cap_pct = rules.per_trade_risk_pct

    # Re-entry ramp adjustment if recovering from alcohol lockout
    if current_alcohol_streak_days is not None and current_alcohol_streak_days >= rules.alcohol_lockout_days:
        for (day_min, day_max), tier_cap in rules.reentry_ramp:
            if day_max is not None and day_min <= current_alcohol_streak_days <= day_max:
                if size_cap_pct is not None:
                    size_cap_pct = min(size_cap_pct, tier_cap)
                break

    rules_snapshot = {
        "per_trade_risk_pct": rules.per_trade_risk_pct,
        "sleep_no_trade_threshold_hours": rules.sleep_no_trade_threshold_hours,
        "sleep_reduced_size_factor": rules.sleep_reduced_size_factor,
        "alcohol_lockout_days": rules.alcohol_lockout_days,
    }

    return ReadinessVerdict(
        verdict=composite_verdict,
        trading_allowed=trading_allowed,
        size_cap_pct=round(size_cap_pct, 4) if size_cap_pct is not None else None,
        per_factor_verdicts=per_factor,
        reasons=reasons,
        method_rules_snapshot=rules_snapshot,
    )
