"""
Tests for the context assembly module (standalone, focused on data sourcing).

Tests assemble_context() as a black-box — verifies what sections appear
in the output string given different mock configurations.
"""

import pytest
from unittest.mock import MagicMock, patch


def _make_mock_rules():
    rules = MagicMock()
    rules.per_trade_risk_pct = 0.01
    rules.rr_minimum = 2.0
    rules.rr_target = 2.5
    rules.daily_loss_cap_pct = 0.02
    rules.weekly_loss_cap_pct = 0.04
    rules.blast_radius_pct = 0.03
    rules.overnight_hedge_cap_pct = 0.02
    rules.alcohol_lockout_days = 90
    rules.sleep_no_trade_threshold_hours = 5.0
    rules.sleep_reduced_size_hours_min = 5.0
    rules.sleep_reduced_size_hours_max = 6.0
    rules.sleep_reduced_size_factor = 0.75
    return rules


def _setup_db_mock(mock_db, readiness_data=None, positions_data=None, margin=850000.0):
    """Sets up a DB mock with configurable return values."""
    mock_db.get_margin_base_inr.return_value = margin

    # Build a chainable mock for table().select().eq().order().limit().execute()
    readiness_execute = MagicMock()
    readiness_execute.data = readiness_data or []
    positions_execute = MagicMock()
    positions_execute.data = positions_data or []

    def table_side_effect(table_name):
        mock_table = MagicMock()
        if table_name == "swayam_readiness_log":
            (mock_table.select.return_value
             .eq.return_value.order.return_value.limit.return_value.execute
             .return_value) = readiness_execute
        elif table_name == "swayam_positions":
            mock_table.select.return_value.eq.return_value.execute.return_value = positions_execute
        return mock_table

    mock_db.client.table.side_effect = table_side_effect


class TestContextAssemblyDataSourcing:

    def test_all_nine_sections_present(self):
        """All 9 context sections should be present in the assembled context."""
        with (
            patch("swayam.ai.persona.trading_partner.vault_reader") as mock_vault,
            patch("swayam.ai.persona.trading_partner.db") as mock_db,
            patch("swayam.ai.persona.trading_partner.fyers_client") as mock_fyers,
            patch("swayam.ai.persona.trading_partner._load_personal_trading_brief_summary",
                  return_value="Brief content"),
            patch("swayam.ai.persona.trading_partner._load_historical_trade_journal_summary",
                  return_value="Journal content"),
            patch("swayam.ai.persona.trading_partner._load_historical_swing_trades_summary",
                  return_value="Swing content"),
            patch("swayam.ai.persona.trading_partner._list_recent_journal_entries",
                  return_value=["### 2026-09-04\nTrade notes"]),
        ):
            mock_vault.load_rules.return_value = _make_mock_rules()
            _setup_db_mock(mock_db)
            mock_fyers.get_nifty_spot.return_value = 24800.0

            from swayam.ai.persona.trading_partner import assemble_context
            context, _ = assemble_context()

        expected_sections = [
            "# Current Method Rules",
            "# Current Margin Base",
            "# NIFTY 50 Spot",
            "# Today's Readiness Check",
            "# Open Positions",
            "# Recent Trade Journal",
            "# Personal Trading Brief",
            "# Historical Trade Journal Summary",
            "# Historical Swing Trades Summary",
        ]
        for section in expected_sections:
            assert section in context, f"Missing section: '{section}'"

    def test_readiness_verdict_appears_when_logged(self):
        """When readiness is logged, its verdict should appear in context."""
        with (
            patch("swayam.ai.persona.trading_partner.vault_reader") as mock_vault,
            patch("swayam.ai.persona.trading_partner.db") as mock_db,
            patch("swayam.ai.persona.trading_partner.fyers_client") as mock_fyers,
        ):
            mock_vault.load_rules.return_value = _make_mock_rules()
            _setup_db_mock(
                mock_db,
                readiness_data=[{
                    "verdict": "🟢 GREEN",
                    "score": 9,
                    "reasons": ["Good sleep", "Low stress"],
                    "flagged_factors": [],
                }]
            )
            mock_fyers.get_nifty_spot.return_value = 24000.0

            from swayam.ai.persona.trading_partner import assemble_context
            context, snapshot = assemble_context()

        assert "GREEN" in context
        assert snapshot["readiness_verdict"] == "🟢 GREEN"
        assert snapshot["readiness_score"] == 9

    def test_open_positions_count_in_snapshot(self):
        """Snapshot should record how many open positions exist."""
        with (
            patch("swayam.ai.persona.trading_partner.vault_reader") as mock_vault,
            patch("swayam.ai.persona.trading_partner.db") as mock_db,
            patch("swayam.ai.persona.trading_partner.fyers_client") as mock_fyers,
        ):
            mock_vault.load_rules.return_value = _make_mock_rules()
            _setup_db_mock(
                mock_db,
                positions_data=[
                    {"symbol": "NIFTY24900PE", "direction": "LONG", "quantity": 1,
                     "entry_price": 120, "stop_loss": 60, "target": 300},
                    {"symbol": "NIFTY25000PE", "direction": "SHORT", "quantity": 1,
                     "entry_price": 100, "stop_loss": 150, "target": 30},
                ]
            )
            mock_fyers.get_nifty_spot.return_value = 24900.0

            from swayam.ai.persona.trading_partner import assemble_context
            context, snapshot = assemble_context()

        assert snapshot["open_position_count"] == 2
        assert "2 active" in context

    def test_no_positions_shows_none_message(self):
        """When no positions exist, context should say so."""
        with (
            patch("swayam.ai.persona.trading_partner.vault_reader") as mock_vault,
            patch("swayam.ai.persona.trading_partner.db") as mock_db,
            patch("swayam.ai.persona.trading_partner.fyers_client") as mock_fyers,
        ):
            mock_vault.load_rules.return_value = _make_mock_rules()
            _setup_db_mock(mock_db, positions_data=[])
            mock_fyers.get_nifty_spot.return_value = 24000.0

            from swayam.ai.persona.trading_partner import assemble_context
            context, snapshot = assemble_context()

        assert "No open positions" in context
        assert snapshot["open_position_count"] == 0

    def test_nifty_spot_appears_in_context(self):
        """The NIFTY spot price should be formatted with ₹ and 2 decimal places."""
        with (
            patch("swayam.ai.persona.trading_partner.vault_reader") as mock_vault,
            patch("swayam.ai.persona.trading_partner.db") as mock_db,
            patch("swayam.ai.persona.trading_partner.fyers_client") as mock_fyers,
        ):
            mock_vault.load_rules.return_value = _make_mock_rules()
            _setup_db_mock(mock_db)
            mock_fyers.get_nifty_spot.return_value = 24867.5

            from swayam.ai.persona.trading_partner import assemble_context
            context, snapshot = assemble_context()

        assert "24,867.50" in context or "24867.50" in context
        assert snapshot["nifty_spot"] == 24867.5
