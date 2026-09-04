"""
Unit tests for Swayam Capital Vault Reader.

Tests Method files parsing from the Obsidian Second Brain and verifies that
all rules are extracted as percentages without rupee hardcodes or silent fallbacks.
"""

from pathlib import Path
import pytest
from swayam.config import settings
from swayam.vault_reader import MethodRulesParseError, VaultReader

VALID_RISK_TEXT = """
- **1% of margin base per trade. Hard CEILING.**
- Phase 1 minimum: 1:2 R:R
- Phase 1 target: 1:2.5 R:R
- Daily loss cap: 2% of margin base.
- Weekly loss cap: 4% of margin base.
- Any single trade whose realized loss exceeds 3% of margin base = system failure.
- cannot lose more than 2% of margin base overnight
### Parameters
- `realistic_risk_cap_pct: 1.0` — the realistic cap as a percentage of margin base
- `blast_radius_pct: 3.0` — the absolute cap as a percentage of margin base
- `realistic_stress_sigma: 2.0` — how many standard deviations the stress test uses
- `realized_vol_window_days: 20` — trailing window for volatility computation
"""

VALID_OP_TEXT = """
| < 5 hours | 🔴 | **No trading.**
| 5–6 hours, quality decent | 🟡 | Position size capped at 75% of normal (0.75% risk instead of 1%) |
The 90-day lockout clock RESTARTS on the last day of consumption.

### Re-entry ramp after a 90-day lockout
- **Days 91–120 (Month 4)**: 0.25% risk per trade cap (¼ of normal)
- **Days 121–150 (Month 5)**: 0.50% risk per trade cap (½ of normal)
- **Days 151–180 (Month 6)**: 0.75% risk per trade cap (¾ of normal)
- **Day 181+**: normal 1% cap resumes
"""

VALID_BRIEF_TEXT = "Margin base ~₹8–9 lakh as of 2026-09-03."


def test_vault_reader_parses_real_method_files_successfully() -> None:
    reader = VaultReader(
        method_dir=settings.trading_method_path,
        brief_file=settings.trading_brief_path,
    )
    rules = reader.load_rules()

    # Verify percentages
    assert rules.per_trade_risk_pct == 0.01
    assert rules.realistic_risk_cap_pct == 0.01
    assert rules.realistic_stress_sigma == 2.0
    assert rules.realized_vol_window_days == 20
    assert rules.rr_minimum == 2.0
    assert rules.rr_target == 2.5
    assert rules.daily_loss_cap_pct == 0.02
    assert rules.weekly_loss_cap_pct == 0.04
    assert rules.blast_radius_pct == 0.03
    assert rules.overnight_hedge_cap_pct == 0.02

    # Verify readiness thresholds
    assert rules.alcohol_lockout_days == 90
    assert rules.sleep_no_trade_threshold_hours == 5.0
    assert rules.sleep_reduced_size_factor == 0.75

    # Verify reentry ramp
    assert len(rules.reentry_ramp) == 4
    assert rules.reentry_ramp[0] == ((91, 120), 0.0025)
    assert rules.reentry_ramp[1] == ((121, 150), 0.0050)
    assert rules.reentry_ramp[2] == ((151, 180), 0.0075)
    assert rules.reentry_ramp[3] == ((181, None), 0.0100)

    # Verify rupee calculation methods
    margin = 850000.0
    assert rules.calculate_per_trade_rupee_cap(margin) == 8500.0
    assert rules.calculate_realistic_risk_rupee_cap(margin) == 8500.0
    assert rules.calculate_daily_loss_rupee_cap(margin) == 17000.0
    assert rules.calculate_weekly_loss_rupee_cap(margin) == 34000.0
    assert rules.calculate_blast_radius_rupee_cap(margin) == 25500.0
    assert rules.calculate_overnight_hedge_rupee_cap(margin) == 17000.0


def test_vault_reader_raises_on_malformed_rule_section() -> None:
    reader = VaultReader(
        method_dir=settings.trading_method_path,
        brief_file=settings.trading_brief_path,
    )
    malformed_risk = "This is a broken risk file with no percentage rules."

    with pytest.raises(MethodRulesParseError, match="Could not parse per_trade_risk_pct"):
        reader._parse_all_rules(malformed_risk, VALID_OP_TEXT, VALID_BRIEF_TEXT)


def test_vault_reader_raises_on_missing_method_files(tmp_path: Path) -> None:
    reader = VaultReader(
        method_dir=tmp_path / "non_existent_method",
        brief_file=tmp_path / "non_existent_brief.md",
    )
    with pytest.raises(MethodRulesParseError, match="Missing mandatory Method file"):
        reader.load_rules()


def test_vault_reader_raises_on_missing_margin_base_range() -> None:
    """If the vault Brief doesn't contain '₹X–Y lakh', reader must raise."""
    reader = VaultReader(
        method_dir=settings.trading_method_path,
        brief_file=settings.trading_brief_path,
    )
    brief_text = "Some brief without a margin range."

    with pytest.raises(MethodRulesParseError, match="margin_base"):
        reader._parse_all_rules(VALID_RISK_TEXT, VALID_OP_TEXT, brief_text)


def test_vault_reader_raises_on_missing_sleep_threshold() -> None:
    """If Operational Readiness Rules doesn't specify sleep threshold, reader must raise."""
    reader = VaultReader(
        method_dir=settings.trading_method_path,
        brief_file=settings.trading_brief_path,
    )
    op_text = """
    | 5–6 hours | 🟡 | 75% of normal |
    90-day lockout
    - **Days 91–120 (Month 4)**: 0.25% risk per trade cap
    - **Days 121–150 (Month 5)**: 0.50% risk per trade cap
    - **Days 151–180 (Month 6)**: 0.75% risk per trade cap
    - **Day 181+**: normal 1% cap resumes
    """
    with pytest.raises(MethodRulesParseError, match="sleep_no_trade_threshold_hours"):
        reader._parse_all_rules(VALID_RISK_TEXT, op_text, VALID_BRIEF_TEXT)


def test_vault_reader_raises_on_missing_sleep_reduced_size() -> None:
    """If Operational Readiness Rules lacks sleep reduced sizing, reader must raise."""
    reader = VaultReader(
        method_dir=settings.trading_method_path,
        brief_file=settings.trading_brief_path,
    )
    op_text = """
    < 5 hours ... No trading
    90-day lockout
    - **Days 91–120 (Month 4)**: 0.25% risk per trade cap
    - **Days 121–150 (Month 5)**: 0.50% risk per trade cap
    - **Days 151–180 (Month 6)**: 0.75% risk per trade cap
    - **Day 181+**: normal 1% cap resumes
    """
    with pytest.raises(MethodRulesParseError, match="sleep_reduced_size"):
        reader._parse_all_rules(VALID_RISK_TEXT, op_text, VALID_BRIEF_TEXT)


def test_vault_reader_raises_on_missing_alcohol_lockout() -> None:
    """If Operational Readiness Rules lacks alcohol lockout days, reader must raise."""
    reader = VaultReader(
        method_dir=settings.trading_method_path,
        brief_file=settings.trading_brief_path,
    )
    op_text = """
    < 5 hours ... No trading
    5–6 hours ... 75% of normal
    - **Days 91–120 (Month 4)**: 0.25% risk per trade cap
    - **Days 121–150 (Month 5)**: 0.50% risk per trade cap
    - **Days 151–180 (Month 6)**: 0.75% risk per trade cap
    - **Day 181+**: normal 1% cap resumes
    """
    with pytest.raises(MethodRulesParseError, match="alcohol_lockout_days"):
        reader._parse_all_rules(VALID_RISK_TEXT, op_text, VALID_BRIEF_TEXT)


def test_vault_reader_parses_reentry_ramp_from_vault() -> None:
    """Verify reentry ramp comes from the actual vault, not hardcoded defaults."""
    reader = VaultReader(
        method_dir=settings.trading_method_path,
        brief_file=settings.trading_brief_path,
    )
    rules = reader.load_rules()
    assert len(rules.reentry_ramp) == 4
    assert rules.reentry_ramp[0] == ((91, 120), 0.0025)
    assert rules.reentry_ramp[3] == ((181, None), 0.0100)


def test_vault_reader_raises_on_missing_reentry_ramp() -> None:
    """If Operational Readiness Rules lacks the reentry ramp section, reader must raise."""
    reader = VaultReader(
        method_dir=settings.trading_method_path,
        brief_file=settings.trading_brief_path,
    )
    op_text = """
    < 5 hours ... No trading
    5–6 hours ... 75% of normal
    90-day lockout
    """
    with pytest.raises(MethodRulesParseError, match="reentry_ramp"):
        reader._parse_all_rules(VALID_RISK_TEXT, op_text, VALID_BRIEF_TEXT)


def test_vault_reader_raises_on_missing_realistic_risk_cap() -> None:
    reader = VaultReader(
        method_dir=settings.trading_method_path,
        brief_file=settings.trading_brief_path,
    )
    bad_risk_text = VALID_RISK_TEXT.replace("realistic_risk_cap_pct: 1.0", "")
    with pytest.raises(MethodRulesParseError, match="realistic_risk_cap_pct"):
        reader._parse_all_rules(bad_risk_text, VALID_OP_TEXT, VALID_BRIEF_TEXT)


def test_vault_reader_raises_on_malformed_realistic_stress_sigma() -> None:
    reader = VaultReader(
        method_dir=settings.trading_method_path,
        brief_file=settings.trading_brief_path,
    )
    bad_risk_text = VALID_RISK_TEXT.replace("realistic_stress_sigma: 2.0", "realistic_stress_sigma: two")
    with pytest.raises(MethodRulesParseError, match="realistic_stress_sigma"):
        reader._parse_all_rules(bad_risk_text, VALID_OP_TEXT, VALID_BRIEF_TEXT)


def test_vault_reader_tolerant_comparator() -> None:
    from swayam.rules_engine import TolerantComparator
    reader = VaultReader(
        method_dir=settings.trading_method_path,
        brief_file=settings.trading_brief_path,
    )
    rules = reader.load_rules()
    comparator = TolerantComparator(tolerance_pct=0.02)
    realistic_cap = rules.calculate_realistic_risk_rupee_cap(850000.0)
    assert comparator.within_cap(8500.0, realistic_cap) is True
    assert comparator.within_cap(8670.0, realistic_cap) is True
    assert comparator.within_cap(8671.0, realistic_cap) is False
