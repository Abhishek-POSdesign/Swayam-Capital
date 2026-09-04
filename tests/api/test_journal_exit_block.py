"""
Tests for appending exit block to Obsidian trade journal (BUILD-7).

Verifies:
- Frontmatter status changes from 'open' to 'closed'
- closed_at, realized_pnl_inr, close_reason added to frontmatter
- '## Exit (to be filled at close)' placeholder is cleanly replaced (not duplicated)
- Exit legs table is rendered with reversed direction (Buy -> Sell, Sell -> Buy)
- Realized P&L, charges, % of max risk, and % of margin base are formatted properly
- JournalWriteError is raised if file does not exist
"""

from datetime import datetime, timezone
from pathlib import Path
import pytest
from swayam.api.journal_writer import JournalWriteError, append_exit_block, write_new_trade_journal


@pytest.fixture()
def sample_journal(tmp_path: Path):
    """Creates a realistic trade journal file using write_new_trade_journal."""
    spread_data = {
        "strategy_name": "Bear Put Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24850.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 180.0,
                "expiry_date": "2026-09-11",
            },
            {
                "strike": 24100.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 1,
                "entry_premium": 60.0,
                "expiry_date": "2026-09-11",
            },
        ],
        "payoff_curve": {
            "max_loss_inr": 9000.0,
            "max_profit_inr": 47250.0,
            "rr_implied": 5.25,
            "net_debit_credit_inr": -9000.0,
            "breakevens": [24730.0],
        },
        "greeks": {
            "net_delta": -25.5,
            "net_theta_per_day": -420.0,
            "net_vega": -80.0,
            "net_gamma": -0.0003,
        },
    }
    validation_data = {
        "verdict": "PASS",
        "checks": [{"rule": "per_trade_risk", "verdict": "PASS", "note": "Within 1% cap"}],
    }

    rel_path = write_new_trade_journal(
        position_id="test-pos-uuid-123",
        spread_data=spread_data,
        validation_data=validation_data,
        current_spot=24867.5,
        margin_base_inr=850000.0,
        vault_path=tmp_path,
    )
    return tmp_path, rel_path


def test_append_exit_block_updates_frontmatter(sample_journal):
    tmp_path, rel_path = sample_journal
    closed_at = datetime(2026, 9, 8, 15, 15, 0, tzinfo=timezone.utc)

    exit_legs = [
        {"strike": 24850.0, "option_type": "PE", "direction": "buy", "exit_premium": 250.0},
        {"strike": 24100.0, "option_type": "PE", "direction": "sell", "exit_premium": 30.0},
    ]

    target_file = append_exit_block(
        journal_rel_path=rel_path,
        closed_at=closed_at,
        close_reason="target_hit",
        notes="Target achieved ahead of expiry. Smooth trade.",
        exit_legs=exit_legs,
        gross_pnl_inr=7500.0,
        charges_inr=300.0,
        net_pnl_inr=7200.0,
        max_loss_inr=9000.0,
        margin_base_inr=850000.0,
        holding_days=2,
        vault_path=tmp_path,
    )

    content = target_file.read_text(encoding="utf-8")

    # Frontmatter assertions
    assert "status: closed" in content
    assert "status: open" not in content
    assert "close_reason: target_hit" in content
    assert "realized_pnl_inr: 7200.00" in content
    assert "closed_at: 2026-09-08T15:15:00+00:00" in content


def test_append_exit_block_replaces_placeholder_cleanly(sample_journal):
    tmp_path, rel_path = sample_journal
    closed_at = datetime(2026, 9, 8, 15, 15, 0, tzinfo=timezone.utc)

    exit_legs = [
        {"strike": 24850.0, "option_type": "PE", "direction": "buy", "exit_premium": 250.0},
        {"strike": 24100.0, "option_type": "PE", "direction": "sell", "exit_premium": 30.0},
    ]

    target_file = append_exit_block(
        journal_rel_path=rel_path,
        closed_at=closed_at,
        close_reason="target_hit",
        notes="Method target hit",
        exit_legs=exit_legs,
        gross_pnl_inr=7500.0,
        charges_inr=300.0,
        net_pnl_inr=7200.0,
        max_loss_inr=9000.0,
        margin_base_inr=850000.0,
        holding_days=2,
        vault_path=tmp_path,
    )

    content = target_file.read_text(encoding="utf-8")

    # Placeholder must be gone
    assert "## Exit (to be filled at close)" not in content
    # Populated exit section header must exist exactly once
    assert content.count("## Exit\n") == 1

    assert "Time closed" in content
    assert "2 days held" in content
    assert "target_hit" in content
    assert "Method target hit" in content


def test_append_exit_block_reverses_leg_directions(sample_journal):
    tmp_path, rel_path = sample_journal
    closed_at = datetime(2026, 9, 8, 15, 15, 0, tzinfo=timezone.utc)

    exit_legs = [
        {"strike": 24850.0, "option_type": "PE", "direction": "buy", "exit_premium": 250.0},
        {"strike": 24100.0, "option_type": "PE", "direction": "sell", "exit_premium": 30.0},
    ]

    target_file = append_exit_block(
        journal_rel_path=rel_path,
        closed_at=closed_at,
        close_reason="target_hit",
        notes=None,
        exit_legs=exit_legs,
        gross_pnl_inr=7500.0,
        charges_inr=300.0,
        net_pnl_inr=7200.0,
        max_loss_inr=9000.0,
        margin_base_inr=850000.0,
        holding_days=1,
        vault_path=tmp_path,
    )

    content = target_file.read_text(encoding="utf-8")

    # Exit table directions must be reversed
    assert "SELL" in content
    assert "BUY" in content
    assert "₹7,200" in content
    assert "₹300" in content
    assert "80.0%" in content  # 7200 / 9000 = 80.0% of max risk


def test_append_exit_block_raises_on_missing_file(tmp_path: Path):
    with pytest.raises(JournalWriteError, match="does not exist"):
        append_exit_block(
            journal_rel_path="02 - Projects/Trading/04 - Journal/non-existent.md",
            closed_at=datetime.now(),
            close_reason="manual",
            notes=None,
            exit_legs=[],
            gross_pnl_inr=0.0,
            charges_inr=0.0,
            net_pnl_inr=0.0,
            max_loss_inr=1000.0,
            margin_base_inr=100000.0,
            holding_days=0,
            vault_path=tmp_path,
        )
