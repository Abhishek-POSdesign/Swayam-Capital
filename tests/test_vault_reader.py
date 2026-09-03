"""
Unit tests for Swayam Capital Vault Reader.

Tests Method files parsing from the Obsidian Second Brain and verifies that
all rules are extracted as percentages without rupee hardcodes.
"""

from pathlib import Path
import pytest
from swayam.config import settings
from swayam.vault_reader import MethodRulesParseError, VaultReader


def test_vault_reader_parses_real_method_files_successfully() -> None:
    reader = VaultReader(
        method_dir=settings.trading_method_path,
        brief_file=settings.trading_brief_path,
    )
    rules = reader.load_rules()

    # Verify percentages
    assert rules.per_trade_risk_pct == 0.01
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

    # Verify rupee calculation methods
    margin = 850000.0
    assert rules.calculate_per_trade_rupee_cap(margin) == 8500.0
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
    op_text = "Sleep < 5 hours. No trading. 90-day lockout."
    brief_text = "Margin base ~₹8–9 lakh."

    with pytest.raises(MethodRulesParseError, match="Could not parse per_trade_risk_pct"):
        reader._parse_all_rules(malformed_risk, op_text, brief_text)


def test_vault_reader_raises_on_missing_method_files(tmp_path: Path) -> None:
    reader = VaultReader(
        method_dir=tmp_path / "non_existent_method",
        brief_file=tmp_path / "non_existent_brief.md",
    )
    with pytest.raises(MethodRulesParseError, match="Missing mandatory Method file"):
        reader.load_rules()
