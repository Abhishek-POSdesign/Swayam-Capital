"""
Unit tests for Operational Readiness verdict calculator.
"""

from swayam.readiness.models import ReadinessInput
from swayam.readiness.verdict import compute_readiness_verdict
from swayam.vault_reader import vault_reader


def test_all_green_inputs_yields_green_verdict() -> None:
    rules = vault_reader.load_rules(force_reload=False)
    inp = ReadinessInput(
        sleep_hours_bucket="7+",
        alcohol_yesterday=False,
        workout_in_last_48h=True,
        journal_mood="focused",
        life_stressor="none",
    )
    verdict = compute_readiness_verdict(inp, rules=rules, current_alcohol_streak_days=200)
    assert verdict.verdict == "green"
    assert verdict.trading_allowed is True
    assert verdict.size_cap_pct == rules.per_trade_risk_pct


def test_sleep_below_five_hours_blocks_trading_red() -> None:
    rules = vault_reader.load_rules(force_reload=False)
    inp = ReadinessInput(
        sleep_hours_bucket="4-5",
        alcohol_yesterday=False,
        workout_in_last_48h=True,
        journal_mood="focused",
        life_stressor="none",
    )
    verdict = compute_readiness_verdict(inp, rules=rules, current_alcohol_streak_days=100)
    assert verdict.verdict == "red"
    assert verdict.trading_allowed is False
    assert verdict.size_cap_pct is None
    assert verdict.per_factor_verdicts["sleep"] == "red"


def test_sleep_five_to_six_hours_yields_yellow_with_reduced_size() -> None:
    rules = vault_reader.load_rules(force_reload=False)
    inp = ReadinessInput(
        sleep_hours_bucket="5-6",
        alcohol_yesterday=False,
        workout_in_last_48h=True,
        journal_mood="focused",
        life_stressor="none",
    )
    verdict = compute_readiness_verdict(inp, rules=rules, current_alcohol_streak_days=200)
    assert verdict.verdict == "yellow"
    assert verdict.trading_allowed is True
    expected_cap = round(rules.per_trade_risk_pct * rules.sleep_reduced_size_factor, 4)
    assert verdict.size_cap_pct == expected_cap
    assert verdict.per_factor_verdicts["sleep"] == "yellow"


def test_alcohol_yesterday_triggers_lockout_red() -> None:
    rules = vault_reader.load_rules(force_reload=False)
    inp = ReadinessInput(
        sleep_hours_bucket="7+",
        alcohol_yesterday=True,
        workout_in_last_48h=True,
        journal_mood="focused",
        life_stressor="none",
    )
    verdict = compute_readiness_verdict(inp, rules=rules, current_alcohol_streak_days=150)
    assert verdict.verdict == "red"
    assert verdict.trading_allowed is False
    assert verdict.per_factor_verdicts["alcohol"] == "red"


def test_active_alcohol_lockout_streak_blocks_trading() -> None:
    rules = vault_reader.load_rules(force_reload=False)
    inp = ReadinessInput(
        sleep_hours_bucket="7+",
        alcohol_yesterday=False,
        workout_in_last_48h=True,
        journal_mood="focused",
        life_stressor="none",
    )
    verdict = compute_readiness_verdict(inp, rules=rules, current_alcohol_streak_days=45)
    assert verdict.verdict == "red"
    assert verdict.trading_allowed is False
    assert "alcohol lockout active: day 45 of 90" in verdict.reasons[0].lower()


def test_reentry_ramp_caps_sizing_during_recovery() -> None:
    rules = vault_reader.load_rules(force_reload=False)
    inp = ReadinessInput(
        sleep_hours_bucket="7+",
        alcohol_yesterday=False,
        workout_in_last_48h=True,
        journal_mood="focused",
        life_stressor="none",
    )
    # Day 95 falls in Week 1 (day 91-97), where cap is 0.25% (0.0025)
    verdict = compute_readiness_verdict(inp, rules=rules, current_alcohol_streak_days=95)
    assert verdict.verdict == "green"
    assert verdict.trading_allowed is True
    assert verdict.size_cap_pct == 0.0025


def test_no_workout_yields_yellow_with_standard_size() -> None:
    rules = vault_reader.load_rules(force_reload=False)
    inp = ReadinessInput(
        sleep_hours_bucket="7+",
        alcohol_yesterday=False,
        workout_in_last_48h=False,
        journal_mood="focused",
        life_stressor="none",
    )
    verdict = compute_readiness_verdict(inp, rules=rules, current_alcohol_streak_days=200)
    assert verdict.verdict == "yellow"
    assert verdict.trading_allowed is True
    assert verdict.size_cap_pct == rules.per_trade_risk_pct  # Sizing not reduced by workout factor
    assert verdict.per_factor_verdicts["workout"] == "yellow"


def test_angry_grief_mood_blocks_trading_red() -> None:
    rules = vault_reader.load_rules(force_reload=False)
    inp = ReadinessInput(
        sleep_hours_bucket="7+",
        alcohol_yesterday=False,
        workout_in_last_48h=True,
        journal_mood="angry_grief",
        life_stressor="none",
    )
    verdict = compute_readiness_verdict(inp, rules=rules, current_alcohol_streak_days=100)
    assert verdict.verdict == "red"
    assert verdict.trading_allowed is False
    assert verdict.per_factor_verdicts["mood"] == "red"


def test_active_life_stressor_yields_yellow() -> None:
    rules = vault_reader.load_rules(force_reload=False)
    inp = ReadinessInput(
        sleep_hours_bucket="7+",
        alcohol_yesterday=False,
        workout_in_last_48h=True,
        journal_mood="focused",
        life_stressor="family",
        stressor_note="Family emergency discussion",
    )
    verdict = compute_readiness_verdict(inp, rules=rules, current_alcohol_streak_days=100)
    assert verdict.verdict == "yellow"
    assert verdict.trading_allowed is True
    assert verdict.per_factor_verdicts["stressor"] == "yellow"
    assert "family" in verdict.reasons[0].lower()
