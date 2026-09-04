"""
Tests for Layer 3 Pinned Trading Rules API endpoints.
"""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest

from swayam.api.main import app

client = TestClient(app)


def test_pin_rule():
    with patch("swayam.api.routes.pinned.db") as mock_db:
        mock_execute = MagicMock()
        mock_execute.data = [{
            "id": 55,
            "rule_text": "I never trade on RBI meet days",
            "active": True,
            "pinned_at": "2026-09-07T10:00:00Z",
            "source_message_id": None,
        }]
        mock_db.client.table.return_value.insert.return_value.execute.return_value = mock_execute

        resp = client.post(
            "/api/ai/pinned",
            json={"rule_text": "I never trade on RBI meet days"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 55
        assert data["rule_text"] == "I never trade on RBI meet days"
        assert data["active"] is True


def test_list_pinned_rules():
    with patch("swayam.api.routes.pinned.db") as mock_db:
        mock_execute = MagicMock()
        mock_execute.data = [{
            "id": 55,
            "rule_text": "My stop is technical, not percentage",
            "active": True,
            "pinned_at": "2026-09-07T10:00:00Z",
            "source_message_id": None,
        }]
        mock_db.client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_execute

        resp = client.get("/api/ai/pinned")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["rule_text"] == "My stop is technical, not percentage"


def test_unpin_rule():
    with patch("swayam.api.routes.pinned.db") as mock_db:
        mock_execute = MagicMock()
        mock_db.client.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_execute

        resp = client.delete("/api/ai/pinned/55")
        assert resp.status_code == 200
        assert resp.json() == {"status": "unpinned", "id": 55}
