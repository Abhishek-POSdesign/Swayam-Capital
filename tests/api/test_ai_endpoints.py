"""
Tests for AI API endpoints.

Tests the full HTTP cycle using FastAPI TestClient:
- POST /api/ai/conversations — create conversation
- GET /api/ai/conversations — list conversations
- GET /api/ai/conversations/{id}/messages — get messages
- POST /api/ai/conversations/{id}/messages — send message (SSE streaming)
- POST /api/ai/conversations/{id}/archive — archive
- DELETE /api/ai/conversations/{id} — hard delete
- GET /api/ai/usage/today — cost tracking

All Supabase and AI calls are mocked.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Returns a TestClient for the Swayam API."""
    from swayam.api.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Mock factories
# ---------------------------------------------------------------------------

def _make_conversation_row(conv_id="conv-123", title=None):
    return {
        "id": conv_id,
        "started_at": "2026-09-05T10:00:00+00:00",
        "last_active_at": "2026-09-05T10:05:00+00:00",
        "title": title,
        "archived": False,
    }


def _make_message_row(msg_id="msg-1", role="user", content="Hello"):
    return {
        "id": msg_id,
        "conversation_id": "conv-123",
        "role": role,
        "content": content,
        "provider": "vertex-gemini-3.1-pro-preview" if role == "assistant" else None,
        "input_tokens": 100 if role == "assistant" else None,
        "output_tokens": 50 if role == "assistant" else None,
        "created_at": "2026-09-05T10:01:00+00:00",
        "context_snapshot": {},
    }


# ---------------------------------------------------------------------------
# Tests: Create conversation
# ---------------------------------------------------------------------------

class TestCreateConversation:
    def test_create_conversation_returns_id(self, client):
        with patch("swayam.api.routes.ai.db") as mock_db:
            mock_db.client.table.return_value.insert.return_value.execute.return_value.data = [
                _make_conversation_row()
            ]
            resp = client.post("/api/ai/conversations", json={"title": None})

        assert resp.status_code == 200
        data = resp.json()
        assert "conversation_id" in data
        assert data["conversation_id"] == "conv-123"

    def test_create_conversation_with_title(self, client):
        with patch("swayam.api.routes.ai.db") as mock_db:
            mock_db.client.table.return_value.insert.return_value.execute.return_value.data = [
                _make_conversation_row(title="Bear Put Spread analysis")
            ]
            resp = client.post("/api/ai/conversations", json={"title": "Bear Put Spread analysis"})

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests: List conversations
# ---------------------------------------------------------------------------

class TestListConversations:
    def test_list_returns_conversations(self, client):
        with patch("swayam.api.routes.ai.db") as mock_db:
            mock_chain = (
                mock_db.client.table.return_value
                .select.return_value.eq.return_value.order.return_value.limit.return_value.execute
            )
            mock_chain.return_value.data = [
                _make_conversation_row("conv-1", "First conv"),
                _make_conversation_row("conv-2", "Second conv"),
            ]
            resp = client.get("/api/ai/conversations")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["conversation_id"] == "conv-1"

    def test_list_returns_empty_when_no_conversations(self, client):
        with patch("swayam.api.routes.ai.db") as mock_db:
            mock_chain = (
                mock_db.client.table.return_value
                .select.return_value.eq.return_value.order.return_value.limit.return_value.execute
            )
            mock_chain.return_value.data = []
            resp = client.get("/api/ai/conversations")

        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Tests: Get messages
# ---------------------------------------------------------------------------

class TestGetMessages:
    def test_get_messages_returns_user_and_assistant_only(self, client):
        with patch("swayam.api.routes.ai.db") as mock_db:
            mock_chain = (
                mock_db.client.table.return_value
                .select.return_value.eq.return_value.in_.return_value
                .order.return_value.execute
            )
            mock_chain.return_value.data = [
                _make_message_row("m1", "user", "Hello"),
                _make_message_row("m2", "assistant", "Hi there"),
            ]
            resp = client.get("/api/ai/conversations/conv-123/messages")

        assert resp.status_code == 200
        messages = resp.json()
        assert len(messages) == 2
        assert all(m["role"] in ("user", "assistant") for m in messages)


# ---------------------------------------------------------------------------
# Tests: Archive and Delete
# ---------------------------------------------------------------------------

class TestArchiveDeleteConversation:
    def test_archive_conversation(self, client):
        with patch("swayam.api.routes.ai.db") as mock_db:
            mock_db.client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
            resp = client.post("/api/ai/conversations/conv-123/archive")

        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    def test_delete_conversation(self, client):
        with patch("swayam.api.routes.ai.db") as mock_db:
            mock_db.client.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()
            resp = client.delete("/api/ai/conversations/conv-123")

        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"


# ---------------------------------------------------------------------------
# Tests: Cost tracking endpoint
# ---------------------------------------------------------------------------

class TestUsageToday:
    def test_usage_returns_zero_when_no_data(self, client):
        with patch("swayam.api.routes.ai.db") as mock_db:
            mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
            resp = client.get("/api/ai/usage/today")

        assert resp.status_code == 200
        data = resp.json()
        assert data["request_count"] == 0
        assert data["estimated_cost_inr"] == 0.0

    def test_usage_returns_aggregate_when_data_exists(self, client):
        with patch("swayam.api.routes.ai.db") as mock_db:
            import datetime
            mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{
                "day": datetime.date.today().isoformat(),
                "provider": "vertex",
                "model": "vertex-gemini-3.1-pro-preview",
                "total_input_tokens": 5000,
                "total_output_tokens": 2000,
                "request_count": 12,
                "estimated_cost_inr": "4.50",
            }]
            resp = client.get("/api/ai/usage/today")

        assert resp.status_code == 200
        data = resp.json()
        assert data["request_count"] == 12
        assert data["estimated_cost_inr"] == 4.50


# ---------------------------------------------------------------------------
# Tests: Send message (streaming)
# ---------------------------------------------------------------------------

class TestSendMessage:
    def _setup_stream_mocks(self, mock_db, mock_router, mock_prompt):
        """Sets up all required mocks for a streaming message test."""
        # History load
        hist_execute = MagicMock()
        hist_execute.data = []

        def table_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "swayam_ai_messages":
                # select().eq().in_().order().execute() for history
                mock_table.select.return_value.eq.return_value.in_.return_value.order.return_value.execute.return_value = hist_execute
                # insert().execute() for persisting
                mock_table.insert.return_value.execute.return_value = MagicMock()
            elif table_name == "swayam_ai_conversations":
                conv_data = MagicMock()
                conv_data.data = [{"title": None}]
                mock_table.select.return_value.eq.return_value.execute.return_value = conv_data
                mock_table.update.return_value.eq.return_value.execute.return_value = MagicMock()
            elif table_name == "swayam_ai_usage_daily":
                daily_data = MagicMock()
                daily_data.data = []  # No existing daily row
                mock_table.select.return_value.eq.return_value.execute.return_value = daily_data
                mock_table.insert.return_value.execute.return_value = MagicMock()
            return mock_table

        mock_db.client.table.side_effect = table_side_effect

        # Context assembly
        mock_prompt.return_value = ("System prompt here", {"margin_base_inr": 850000.0})

        # AI router streaming
        def fake_stream(messages):
            yield "Bear Put Spread analysis: ", "vertex-gemini-3.1-pro-preview"
            yield "the R:R looks good.", "vertex-gemini-3.1-pro-preview"

        mock_router.stream_main_turn.side_effect = fake_stream

    def test_send_message_returns_sse_stream(self, client):
        with (
            patch("swayam.api.routes.ai.db") as mock_db,
            patch("swayam.api.routes.ai.ai_router") as mock_router,
            patch("swayam.api.routes.ai.build_full_system_prompt") as mock_prompt,
        ):
            self._setup_stream_mocks(mock_db, mock_router, mock_prompt)

            resp = client.post(
                "/api/ai/conversations/conv-123/messages",
                json={"content": "Analyse my Bear Put Spread"},
                headers={"Accept": "text/event-stream"},
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        # Parse SSE events from response
        body = resp.text
        assert "data: " in body
        assert "[DONE]" in body

    def test_send_message_sse_contains_deltas(self, client):
        with (
            patch("swayam.api.routes.ai.db") as mock_db,
            patch("swayam.api.routes.ai.ai_router") as mock_router,
            patch("swayam.api.routes.ai.build_full_system_prompt") as mock_prompt,
        ):
            self._setup_stream_mocks(mock_db, mock_router, mock_prompt)

            resp = client.post(
                "/api/ai/conversations/conv-123/messages",
                json={"content": "Should I take this trade?"},
            )

        # Parse all data lines
        events = [
            line[6:] for line in resp.text.split("\n")
            if line.startswith("data: ") and line[6:] != "[DONE]"
        ]
        delta_events = [json.loads(e) for e in events if e.strip()]
        deltas = [e["delta"] for e in delta_events if "delta" in e]
        assert len(deltas) > 0
        full_text = "".join(deltas)
        assert "Bear Put Spread" in full_text or "R:R" in full_text

    def test_send_message_persists_user_and_assistant_messages(self, client):
        """Both user and assistant messages should be inserted to DB."""
        with (
            patch("swayam.api.routes.ai.db") as mock_db,
            patch("swayam.api.routes.ai.ai_router") as mock_router,
            patch("swayam.api.routes.ai.build_full_system_prompt") as mock_prompt,
        ):
            self._setup_stream_mocks(mock_db, mock_router, mock_prompt)

            client.post(
                "/api/ai/conversations/conv-123/messages",
                json={"content": "What do you see?"},
            )

        # Verify the messages table was inserted into (at least twice: user + assistant)
        messages_table_calls = [
            call for call in mock_db.client.table.call_args_list
            if call[0][0] == "swayam_ai_messages"
        ]
        # At minimum, history select + user insert + assistant insert
        assert len(messages_table_calls) >= 2
