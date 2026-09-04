import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from swayam.api import app

client = TestClient(app)


def test_ai_session_context_summary_empty():
    with patch("swayam.api.routes.ai.db") as mock_db:
        query_mock = MagicMock()
        query_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        mock_db.client.table.return_value = query_mock

        res = client.get("/api/ai/session/non-existent-session-id/context-summary")
        assert res.status_code == 200
        data = res.json()
        assert data["has_context"] is False
        assert len(data["bullets"]) > 0


def test_ai_session_context_summary_with_messages():
    sid = "test-summary-session-123"
    fake_messages = [
        {"role": "user", "content": "I want to look at a Bear Put Spread on NIFTY around 24,800.", "created_at": "2026-09-05T09:15:00Z"},
        {"role": "assistant", "content": "That aligns well with India VIX at 12.85. Consider 24,900 Long and 24,700 Short.", "created_at": "2026-09-05T09:15:10Z"},
    ]

    with patch("swayam.api.routes.ai.db") as mock_db:
        query_mock = MagicMock()
        query_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=fake_messages)
        mock_db.client.table.return_value = query_mock

        res = client.get(f"/api/ai/session/{sid}/context-summary")
        assert res.status_code == 200
        data = res.json()
        assert data["has_context"] is True
        assert any("Bear Put Spread" in b for b in data["bullets"])
        assert any("24,900 Long" in b or "AI:" in b for b in data["bullets"])
