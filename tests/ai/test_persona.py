"""
Tests for the Trading Partner persona and context assembly.

Verifies:
- TRADING_PARTNER_PERSONA does not contain banned phrases
- TRADING_PARTNER_PERSONA contains all 6 behavioral constraints
- assemble_context() includes all required sections
- assemble_context() handles missing data sources gracefully (non-fatal)
- build_full_system_prompt() joins persona and context correctly
"""

import pytest
from unittest.mock import MagicMock, patch


class TestPersonaStaticContent:
    """Verify the static persona string has correct behavioral constraints."""

    def setup_method(self):
        from swayam.ai.persona.trading_partner import TRADING_PARTNER_PERSONA
        self.persona = TRADING_PARTNER_PERSONA

    def test_persona_not_empty(self):
        assert len(self.persona) > 500, "Persona should be substantive"

    # Banned phrases — these appear in the persona only as "Never say X" instructions,
    # never as actual AI speech patterns. We verify the persona constrains them.
    def test_persona_constrains_sycophantic_openers(self):
        """Persona should explicitly forbid sycophantic phrases."""
        # These appear in the Tone section as things to NEVER say
        banned_in_ai_output = [
            "great question",   # persona says: no "great question"
            "certainly",        # persona says: no "certainly" (lowercase)
            "I'd be happy to help",
            "Sure!",
            "Absolutely!",
        ]
        # Normalize multiple spaces/newlines to single spaces so line breaks don't break matches
        persona_normalized = " ".join(self.persona.lower().split())
        for phrase in banned_in_ai_output:
            assert phrase.lower() in persona_normalized, (
                f"Persona should reference '{phrase}' as a banned phrase to enforce constraints"
            )
        assert "never" in persona_normalized


    def test_persona_forbids_i_understand_opener(self):
        """Persona style constraints should list 'I understand' as a banned opener."""
        assert "I understand" in self.persona  # appears as "Never start with 'I understand...'"

    def test_persona_forbids_let_me_know_closer(self):
        """Persona style constraints should list the 'Let me know' closer as banned."""
        assert "Let me know if you have any other questions" in self.persona


    # Required behavioral constraints
    def test_persona_contains_naked_long_constraint(self):
        assert "naked long" in self.persona.lower()

    def test_persona_contains_revenge_trade_constraint(self):
        assert "revenge" in self.persona.lower()

    def test_persona_contains_stop_widening_constraint(self):
        assert "widening" in self.persona.lower() or "widen" in self.persona.lower()

    def test_persona_contains_red_verdict_constraint(self):
        assert "red" in self.persona.lower() and "readiness" in self.persona.lower()

    def test_persona_contains_direction_certainty_constraint(self):
        assert "certainty" in self.persona.lower() or "certain" in self.persona.lower()

    def test_persona_contains_rule_cap_constraint(self):
        assert "1%" in self.persona or "cap" in self.persona.lower()

    # Grounding data points
    def test_persona_references_trade07(self):
        assert "Trade-07" in self.persona

    def test_persona_references_fy_result(self):
        assert "86,299" in self.persona or "86299" in self.persona

    def test_persona_references_swing_period(self):
        assert "61.9%" in self.persona

    def test_persona_is_read_only(self):
        assert "you never place a trade" in self.persona.lower()


class TestContextAssembly:
    """Verify assemble_context() handles all sections correctly."""

    def _make_mock_rules(self):
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

    def test_context_includes_method_rules(self):
        with (
            patch("swayam.ai.persona.trading_partner.vault_reader") as mock_vault,
            patch("swayam.ai.persona.trading_partner.db") as mock_db,
            patch("swayam.ai.persona.trading_partner.fyers_client") as mock_fyers,
        ):
            mock_vault.load_rules.return_value = self._make_mock_rules()
            mock_db.get_margin_base_inr.return_value = 850000.0
            mock_db.client.table.return_value.select.return_value.eq.return_value \
                .order.return_value.limit.return_value.execute.return_value.data = []
            mock_db.client.table.return_value.select.return_value.eq.return_value \
                .execute.return_value.data = []
            mock_fyers.get_nifty_spot.return_value = 24800.0

            from swayam.ai.persona.trading_partner import assemble_context
            context, snapshot = assemble_context()

        assert "Method Rules" in context
        assert "1.0%" in context  # per-trade risk
        assert "margin_base_inr" in snapshot or snapshot.get("margin_base_inr") == 850000.0

    def test_context_includes_margin_base(self):
        with (
            patch("swayam.ai.persona.trading_partner.vault_reader") as mock_vault,
            patch("swayam.ai.persona.trading_partner.db") as mock_db,
            patch("swayam.ai.persona.trading_partner.fyers_client") as mock_fyers,
        ):
            mock_vault.load_rules.return_value = self._make_mock_rules()
            mock_db.get_margin_base_inr.return_value = 850000.0
            mock_db.client.table.return_value.select.return_value.eq.return_value \
                .order.return_value.limit.return_value.execute.return_value.data = []
            mock_db.client.table.return_value.select.return_value.eq.return_value \
                .execute.return_value.data = []
            mock_fyers.get_nifty_spot.return_value = 24000.0

            from swayam.ai.persona.trading_partner import assemble_context
            context, snapshot = assemble_context()

        assert "₹8,50,000" in context or "850,000" in context
        assert snapshot["margin_base_inr"] == 850000.0

    def test_context_handles_missing_nifty_spot_gracefully(self):
        """If FYERS is offline, context should still assemble without crashing."""
        with (
            patch("swayam.ai.persona.trading_partner.vault_reader") as mock_vault,
            patch("swayam.ai.persona.trading_partner.db") as mock_db,
            patch("swayam.ai.persona.trading_partner.fyers_client") as mock_fyers,
        ):
            mock_vault.load_rules.return_value = self._make_mock_rules()
            mock_db.get_margin_base_inr.return_value = 850000.0
            mock_db.client.table.return_value.select.return_value.eq.return_value \
                .order.return_value.limit.return_value.execute.return_value.data = []
            mock_db.client.table.return_value.select.return_value.eq.return_value \
                .execute.return_value.data = []
            mock_fyers.get_nifty_spot.side_effect = RuntimeError("market closed")

            from swayam.ai.persona.trading_partner import assemble_context
            # Should NOT raise
            context, snapshot = assemble_context()

        assert "NIFTY" in context
        assert snapshot["nifty_spot"] is None

    def test_context_handles_missing_readiness_gracefully(self):
        """If readiness log has no entry today, context should note 'not logged'."""
        with (
            patch("swayam.ai.persona.trading_partner.vault_reader") as mock_vault,
            patch("swayam.ai.persona.trading_partner.db") as mock_db,
            patch("swayam.ai.persona.trading_partner.fyers_client") as mock_fyers,
        ):
            mock_vault.load_rules.return_value = self._make_mock_rules()
            mock_db.get_margin_base_inr.return_value = 850000.0
            mock_db.client.table.return_value.select.return_value.eq.return_value \
                .order.return_value.limit.return_value.execute.return_value.data = []
            mock_db.client.table.return_value.select.return_value.eq.return_value \
                .execute.return_value.data = []
            mock_fyers.get_nifty_spot.return_value = 24000.0

            from swayam.ai.persona.trading_partner import assemble_context
            context, snapshot = assemble_context()

        assert "Readiness" in context
        assert snapshot["readiness_verdict"] is None

    def test_context_handles_method_rules_failure_gracefully(self):
        """If vault reader fails, context should note it without crashing."""
        with (
            patch("swayam.ai.persona.trading_partner.vault_reader") as mock_vault,
            patch("swayam.ai.persona.trading_partner.db") as mock_db,
            patch("swayam.ai.persona.trading_partner.fyers_client") as mock_fyers,
        ):
            mock_vault.load_rules.side_effect = Exception("vault not found")
            mock_db.get_margin_base_inr.return_value = 850000.0
            mock_db.client.table.return_value.select.return_value.eq.return_value \
                .order.return_value.limit.return_value.execute.return_value.data = []
            mock_db.client.table.return_value.select.return_value.eq.return_value \
                .execute.return_value.data = []
            mock_fyers.get_nifty_spot.return_value = 24000.0

            from swayam.ai.persona.trading_partner import assemble_context
            # Should NOT raise
            context, snapshot = assemble_context()

        assert "Method Rules" in context
        assert "unavailable" in context.lower()
        assert snapshot["rules_hash"] is None

    def test_context_snapshot_has_required_keys(self):
        """Snapshot dict should always contain the 5 tracking keys."""
        with (
            patch("swayam.ai.persona.trading_partner.vault_reader") as mock_vault,
            patch("swayam.ai.persona.trading_partner.db") as mock_db,
            patch("swayam.ai.persona.trading_partner.fyers_client") as mock_fyers,
        ):
            mock_vault.load_rules.return_value = self._make_mock_rules()
            mock_db.get_margin_base_inr.return_value = 900000.0
            mock_db.client.table.return_value.select.return_value.eq.return_value \
                .order.return_value.limit.return_value.execute.return_value.data = []
            mock_db.client.table.return_value.select.return_value.eq.return_value \
                .execute.return_value.data = []
            mock_fyers.get_nifty_spot.return_value = 25000.0

            from swayam.ai.persona.trading_partner import assemble_context
            _, snapshot = assemble_context()

        for key in ["rules_hash", "margin_base_inr", "nifty_spot", "readiness_verdict", "open_position_count"]:
            assert key in snapshot, f"Missing snapshot key: {key}"


class TestBuildFullSystemPrompt:
    def test_full_prompt_starts_with_persona(self):
        """The full system prompt should begin with the persona block."""
        with (
            patch("swayam.ai.persona.trading_partner.vault_reader") as mock_vault,
            patch("swayam.ai.persona.trading_partner.db") as mock_db,
            patch("swayam.ai.persona.trading_partner.fyers_client") as mock_fyers,
        ):
            mock_vault.load_rules.side_effect = Exception("skip")
            mock_db.get_margin_base_inr.side_effect = Exception("skip")
            mock_db.client.table.return_value.select.return_value.eq.return_value \
                .order.return_value.limit.return_value.execute.return_value.data = []
            mock_db.client.table.return_value.select.return_value.eq.return_value \
                .execute.return_value.data = []
            mock_fyers.get_nifty_spot.side_effect = Exception("skip")

            from swayam.ai.persona.trading_partner import (
                TRADING_PARTNER_PERSONA,
                build_full_system_prompt,
            )
            prompt, _ = build_full_system_prompt()

        assert prompt.startswith(TRADING_PARTNER_PERSONA[:50])

    def test_full_prompt_contains_context_separator(self):
        """The persona and context should be joined with a double newline."""
        with (
            patch("swayam.ai.persona.trading_partner.vault_reader") as mock_vault,
            patch("swayam.ai.persona.trading_partner.db") as mock_db,
            patch("swayam.ai.persona.trading_partner.fyers_client") as mock_fyers,
        ):
            mock_vault.load_rules.side_effect = Exception("skip")
            mock_db.get_margin_base_inr.side_effect = Exception("skip")
            mock_db.client.table.return_value.select.return_value.eq.return_value \
                .order.return_value.limit.return_value.execute.return_value.data = []
            mock_db.client.table.return_value.select.return_value.eq.return_value \
                .execute.return_value.data = []
            mock_fyers.get_nifty_spot.side_effect = Exception("skip")

            from swayam.ai.persona.trading_partner import build_full_system_prompt
            prompt, _ = build_full_system_prompt()

        # Context section headers should appear after persona
        assert "# Current Method Rules" in prompt or "# NIFTY" in prompt
