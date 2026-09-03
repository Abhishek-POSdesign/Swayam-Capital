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
