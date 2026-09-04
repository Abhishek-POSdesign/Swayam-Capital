"""
Tests for positions and portfolio endpoints in Swayam Capital.
"""

from fastapi.testclient import TestClient
from swayam.api import app

client = TestClient(app)


def test_get_positions_returns_list() -> None:
    response = client.get("/api/positions?status=open")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_position_pnl_live_raises_404_on_unknown_id() -> None:
    response = client.get("/api/positions/non-existent-uuid/pnl-live")
    assert response.status_code == 404


def test_get_positions_supabase_failure_raises_503(monkeypatch) -> None:
    class MockTable:
        def select(self, *args, **kwargs):
            raise Exception("Database unreachable")

    class MockClient:
        def table(self, *args, **kwargs):
            return MockTable()

    from swayam.db import db
    monkeypatch.setattr(db, "_client", MockClient())

    response = client.get("/api/positions?status=open")
    assert response.status_code == 503
    data = response.json()
    assert "Positions service unavailable" in data["detail"]

