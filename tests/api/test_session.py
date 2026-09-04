"""
Tests for AI Session Continuity API endpoints.
"""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest

from swayam.api.main import app

client = TestClient(app)


def test_create_session():
    with patch("swayam.api.routes.session.db") as mock_db:
        mock_execute = MagicMock()
        mock_execute.data = [{
            "id": "11111111-1111-1111-1111-111111111111",
            "started_at": "2026-09-07T09:00:00Z",
        }]
        mock_db.client.table.return_value.insert.return_value.execute.return_value = mock_execute

        resp = client.post("/api/ai/session/new")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "11111111-1111-1111-1111-111111111111"
        assert data["started_at"] == "2026-09-07T09:00:00Z"


def test_get_session_messages():
    with patch("swayam.api.routes.session.db") as mock_db:
        mock_execute = MagicMock()
        mock_execute.data = [{
            "id": "22222222-2222-2222-2222-222222222222",
            "role": "user",
            "content": "Morning view?",
            "created_at": "2026-09-07T09:15:00Z",
            "provider": None,
            "position_id": None,
        }]
        (mock_db.client.table.return_value
         .select.return_value
         .eq.return_value
         .in_.return_value
         .order.return_value
         .execute.return_value) = mock_execute

        resp = client.get("/api/ai/session/11111111-1111-1111-1111-111111111111/messages")
        assert resp.status_code == 200
        messages = resp.json()
        assert len(messages) == 1
        assert messages[0]["content"] == "Morning view?"
