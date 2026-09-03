"""
Tests for trade journal markdown writer in Swayam Capital.
"""

from pathlib import Path
import pytest
from swayam.api.journal_writer import (
    JournalWriteError,
    determine_next_trade_sequence,
    write_new_trade_journal,
)


def test_determine_next_trade_sequence_handles_increments(tmp_path: Path) -> None:
    date_str = "2026-09-05"
    assert determine_next_trade_sequence(tmp_path, date_str) == "01"

    # Create dummy trade01 file
    (tmp_path / f"{date_str}-trade01.md").write_text("trade 1")
    assert determine_next_trade_sequence(tmp_path, date_str) == "02"

    (tmp_path / f"{date_str}-trade02.md").write_text("trade 2")
    assert determine_next_trade_sequence(tmp_path, date_str) == "03"


def test_write_new_trade_journal_generates_valid_markdown(tmp_path: Path) -> None:
    spread_data = {
        "strategy_name": "Test Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24800.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 150.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            }
        ],
        "payoff_curve": {
            "max_loss_inr": 11250.0,
            "max_profit_inr": 35000.0,
            "rr_implied": 3.11,
            "net_debit_credit_inr": -11250.0,
            "breakevens": [24650.0],
        },
        "greeks": {
            "net_delta": -25.5,
            "net_theta_per_day": -450.0,
            "net_vega": -85.0,
            "net_gamma": -0.0003,
        },
    }

    val_data = {
        "passed": True,
        "checks": [
            {"rule": "per_trade_risk_cap", "verdict": "PASS", "actual_inr": 11250.0, "cap_inr": 17000.0},
        ],
    }

    rel_path = write_new_trade_journal(
        position_id="test-pos-123",
        spread_data=spread_data,
        validation_data=val_data,
        current_spot=24850.0,
        margin_base_inr=850000.0,
        vault_path=tmp_path,
    )

    full_path = tmp_path / rel_path
    assert full_path.exists()

    content = full_path.read_text(encoding="utf-8")
    assert "trade_id: test-pos-123" in content
    assert "# 2026-" in content
    assert "Test Spread" in content
    assert "Max loss" in content
    assert "₹11,250" in content
    assert "Net Delta: -25.5000" in content
    assert "Per Trade Risk Cap" in content
