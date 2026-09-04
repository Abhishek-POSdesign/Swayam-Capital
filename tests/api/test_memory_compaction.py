"""
Tests for 3-tier memory compaction logic (Session Compaction and Trade Compaction).
"""

from datetime import date
from unittest.mock import MagicMock, patch
import pytest

from swayam.ai.memory import compact_session, compact_trade, safety_valve_check


def test_compact_session_idempotent():
    with patch("swayam.ai.memory.db") as mock_db:
        # Existing summary mock
        mock_execute = MagicMock()
        mock_execute.data = [{
            "id": 1,
            "session_date": "2026-09-06",
            "summary_block": {"summary": "Existing summary"},
            "message_count": 12,
        }]
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_execute

        summary = compact_session(date(2026, 9, 6))
        assert summary["session_date"] == "2026-09-06"
        assert summary["summary_block"]["summary"] == "Existing summary"


def test_compact_trade_skips_when_trade_open():
    with patch("swayam.ai.memory.db") as mock_db:
        mock_pos = MagicMock()
        mock_pos.data = [{"id": "pos-1", "status": "open"}]
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_pos

        res = compact_trade("pos-1")
        assert res is None


def test_compact_trade_skips_without_journal():
    with patch("swayam.ai.memory.db") as mock_db:
        def table_side_effect(name):
            mock_table = MagicMock()
            if name == "swayam_positions":
                m = MagicMock()
                m.data = [{"id": "pos-1", "status": "closed"}]
                mock_table.select.return_value.eq.return_value.execute.return_value = m
            elif name == "swayam_trade_history":
                m = MagicMock()
                m.data = [{"id": "th-1", "position_id": "pos-1", "journal_reflection": None, "journal_md_path": None}]
                mock_table.select.return_value.eq.return_value.execute.return_value = m
            return mock_table

        mock_db.client.table.side_effect = table_side_effect
        res = compact_trade("pos-1")
        assert res is None
