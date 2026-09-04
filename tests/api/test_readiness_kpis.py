"""
Tests for GET /api/readiness/kpis endpoint in Swayam Capital (BUILD-9).
"""

from unittest.mock import MagicMock, PropertyMock, patch
from fastapi.testclient import TestClient
from swayam.api.main import app
from swayam.db import db

client = TestClient(app)


def test_get_readiness_kpis_success():
    """Verify GET /api/readiness/kpis returns streak, ratio, and routine metrics."""
    response = client.get("/api/readiness/kpis")
    assert response.status_code == 200
    data = response.json()
    assert "alcohol_streak_days" in data
    assert "ramp_tier_label" in data
    assert "readiness_last_7_days" in data
    assert "readiness_ratio_str" in data
    assert "morning_routine_pct" in data
    assert "morning_routine_sparkline" in data
    assert "has_history" in data


def test_get_readiness_kpis_db_error_returns_503():
    """Verify 503 is returned if Supabase table query raises an error."""
    mock_client = MagicMock()
    mock_client.table.side_effect = Exception("Supabase connection timeout")
    with patch.object(type(db), "client", new_callable=PropertyMock, return_value=mock_client):
        response = client.get("/api/readiness/kpis")
        assert response.status_code == 503
        assert "Failed to fetch readiness KPIs" in response.json()["detail"]
