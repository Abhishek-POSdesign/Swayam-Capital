"""
Tests for GET /api/ai/brief/today endpoint in Swayam Capital (BUILD-9).
"""

from unittest.mock import patch
from fastapi.testclient import TestClient
from swayam.api.main import app

client = TestClient(app)


def test_get_ai_brief_success():
    """Verify GET /api/ai/brief/today returns complete payload with 200."""
    mock_brief = (
        "India VIX at 12.85 confirms low-volatility regime. Premium-selling favorable, "
        "spreads over singles. Prefer setups where realistic risk stays under 1% cap. "
        "Skip trades if event risk within 48 hours."
    )
    with patch("swayam.ai.router.chat_main_turn", return_value=(mock_brief, "gemini-3.1-pro-preview")):
        response = client.get("/api/ai/brief/today")
        assert response.status_code == 200
        data = response.json()
        assert "generated_at" in data
        assert data["brief_text"] == mock_brief
        assert "reading_queue" in data
        assert len(data["reading_queue"]) == 3
        assert "macro_events_next_5_days" in data
        assert len(data["macro_events_next_5_days"]) == 3
        assert "overnight_global" in data
        assert "DJI" in data["overnight_global"]
        assert "SP500" in data["overnight_global"]
        assert "india_vix" in data
        assert data["india_vix"]["value"] == 12.85


def test_get_ai_brief_fails_loudly_with_503_on_ai_failure():
    """Verify GET /api/ai/brief/today fails loudly with HTTP 503 if AI router fails."""
    with patch("swayam.ai.router.chat_main_turn", side_effect=RuntimeError("GCP Vertex rate limit exceeded")):
        response = client.get("/api/ai/brief/today")
        assert response.status_code == 503
        data = response.json()
        assert "AI Trading Partner unavailable" in data["detail"]


def test_get_ai_brief_reading_queue_structure():
    """Verify reading queue contains source, title, read_time_min, and url."""
    mock_brief = "Market calm. Spreads favorable."
    with patch("swayam.ai.router.chat_main_turn", return_value=(mock_brief, "gemini-3.1-pro-preview")):
        response = client.get("/api/ai/brief/today")
        assert response.status_code == 200
        queue = response.json()["reading_queue"]
        for item in queue:
            assert "source" in item
            assert "title" in item
            assert "read_time_min" in item
            assert "url" in item


def test_get_ai_brief_overnight_global_format():
    """Verify overnight global contains all 5 key benchmarks."""
    mock_brief = "Market calm. Spreads favorable."
    with patch("swayam.ai.router.chat_main_turn", return_value=(mock_brief, "gemini-3.1-pro-preview")):
        response = client.get("/api/ai/brief/today")
        assert response.status_code == 200
        global_tickers = response.json()["overnight_global"]
        for ticker in ["DJI", "SP500", "NASDAQ", "USDINR", "BRENT"]:
            assert ticker in global_tickers
            assert "value" in global_tickers[ticker]


def test_get_ai_brief_india_vix_format():
    """Verify india_vix payload contains regime and 20-day sparkline."""
    mock_brief = "Market calm. Spreads favorable."
    with patch("swayam.ai.router.chat_main_turn", return_value=(mock_brief, "gemini-3.1-pro-preview")):
        response = client.get("/api/ai/brief/today")
        assert response.status_code == 200
        vix_data = response.json()["india_vix"]
        assert "regime" in vix_data
        assert "sparkline_20d" in vix_data
        assert len(vix_data["sparkline_20d"]) >= 20
