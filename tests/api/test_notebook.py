"""
Tests for Layer 3 Notebook Memory API endpoints.
"""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest

from swayam.api.main import app

client = TestClient(app)


def test_create_notebook_entry():
    with patch("swayam.api.routes.notebook.db") as mock_db:
        mock_execute = MagicMock()
        mock_execute.data = [{
            "id": 101,
            "entry_text": "Never widen stops on calendar spreads.",
            "source_message_id": None,
            "source_conversation_id": None,
            "created_at": "2026-09-07T10:00:00Z",
            "updated_at": "2026-09-07T10:00:00Z",
        }]
        mock_db.client.table.return_value.insert.return_value.execute.return_value = mock_execute

        resp = client.post(
            "/api/ai/notebook",
            json={"entry_text": "Never widen stops on calendar spreads."},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 101
        assert data["entry_text"] == "Never widen stops on calendar spreads."


def test_list_notebook_entries():
    with patch("swayam.api.routes.notebook.db") as mock_db:
        mock_execute = MagicMock()
        mock_execute.data = [
            {
                "id": 1,
                "entry_text": "Rule 1",
                "source_message_id": None,
                "source_conversation_id": None,
                "created_at": "2026-09-07T10:00:00Z",
                "updated_at": "2026-09-07T10:00:00Z",
            }
        ]
        mock_db.client.table.return_value.select.return_value.order.return_value.execute.return_value = mock_execute

        resp = client.get("/api/ai/notebook")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["id"] == 1


def test_delete_notebook_entry():
    with patch("swayam.api.routes.notebook.db") as mock_db:
        mock_execute = MagicMock()
        mock_db.client.table.return_value.delete.return_value.eq.return_value.execute.return_value = mock_execute

        resp = client.delete("/api/ai/notebook/101")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted", "id": 101}
