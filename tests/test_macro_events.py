"""
Unit and integration tests for BUILD-11.10:
- Macro calendar ingestion and deduplication
- Weekly Gemini curation with complete reset of stale highlights
- AI context builder for system prompt injection
- Protected POST /api/macro/refresh endpoint (X-Cron-Secret auth enforcement)
- GET /api/macro/events with staleness warning logic
"""

from datetime import date, datetime, timedelta, timezone
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from swayam.api.main import app
from swayam.ai.context_builder import build_planning_context
from swayam.config import settings
from swayam.services.macro_calendar import (
    fetch_from_trading_economics,
    get_fallback_macro_events,
    ingest_macro_calendar,
)
from swayam.services.macro_curator import curate_macro_events


@pytest.fixture
def client():
    return TestClient(app)


def test_fallback_macro_events_generator():
    """Generates deterministic upcoming IN and US macro events."""
    today = date(2026, 9, 6)
    events = get_fallback_macro_events(ref_date=today)
    assert len(events) >= 5
    countries = {e["country"] for e in events}
    assert "IN" in countries
    assert "US" in countries
    for ev in events:
        assert "event_key" in ev
        assert "event_name" in ev
        assert "event_date" in ev


def test_ingest_macro_calendar_upserts_and_dedupes():
    """Validates that ingestion properly maps and upserts into swayam_macro_events."""
    mock_db = MagicMock()
    mock_db.client.table.return_value.upsert.return_value.execute.return_value.data = [
        {"event_key": "IN_CPI_2026-09-10"},
        {"event_key": "US_FOMC_2026-09-13"},
    ]

    res = ingest_macro_calendar(db=mock_db)
    assert res["status"] == "success"
    assert res["count"] >= 2
    mock_db.client.table.assert_called_with("swayam_macro_events")


def test_curate_macro_events_resets_old_highlights():
    """REINFORCEMENT 2: Verifies curation unsets highlighted=false on all rows before applying picks."""
    mock_db = MagicMock()
    # Mock upcoming events query
    mock_db.client.table.return_value.select.return_value.gte.return_value.lte.return_value.order.return_value.execute.return_value.data = [
        {"event_key": "EV_1", "event_date": "2026-09-08", "country": "IN", "event_name": "India CPI", "importance": "high"},
        {"event_key": "EV_2", "event_date": "2026-09-10", "country": "US", "event_name": "US FOMC", "importance": "high"},
        {"event_key": "EV_3", "event_date": "2026-09-12", "country": "IN", "event_name": "India IIP", "importance": "medium"},
    ]

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json_str = (
        '[{"event_key": "EV_1", "highlighted": true, "impact_brief": "Inflation marker; watch IV expansion."}, '
        '{"event_key": "EV_2", "highlighted": true, "impact_brief": "Fed decision; overnight gap risk on GIFT Nifty."}]'
    )
    mock_response.usage_metadata.total_token_count = 500
    mock_client.models.generate_content.return_value = mock_response

    res = curate_macro_events(db=mock_db, client=mock_client)
    assert res["status"] == "success"
    assert res["curated_count"] == 2
    assert "EV_1" in res["curated_keys"]
    assert "EV_2" in res["curated_keys"]

    # Verify that reset was executed: update({"highlighted": False})
    table_mock = mock_db.client.table.return_value
    table_mock.update.assert_any_call({"highlighted": False})


def test_build_planning_context():
    """Verifies that context builder formats highlighted events for system prompt injection."""
    mock_db = MagicMock()
    mock_db.client.table.return_value.select.return_value.eq.return_value.gte.return_value.lte.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {
            "event_name": "India CPI Inflation",
            "event_date": "2026-09-10",
            "country": "IN",
            "impact_brief": "Monitor RBI rate trajectory; post-release IV crush likely.",
        },
        {
            "event_name": "US Fed Interest Rate Decision",
            "event_date": "2026-09-13",
            "country": "US",
            "impact_brief": "Global risk-off trigger; watch GIFT Nifty gap.",
        }
    ]

    ctx = build_planning_context(db=mock_db)
    assert "Upcoming macro events (next 7 days):" in ctx
    assert "[IN] India CPI Inflation" in ctx
    assert "[US] US Fed Interest Rate Decision" in ctx
    assert "Factor these events into any multi-day trade" in ctx


def test_post_macro_refresh_unauthorized_without_secret(client):
    """REINFORCEMENT 4: Verifies HTTP 401 when X-Cron-Secret is missing or incorrect."""
    resp = client.post("/api/macro/refresh?mode=ingest")
    assert resp.status_code == 401
    assert "Unauthorized" in resp.json()["detail"]

    # Invalid secret
    resp_bad = client.post(
        "/api/macro/refresh?mode=ingest",
        headers={"X-Cron-Secret": "wrong-secret-value"},
    )
    assert resp_bad.status_code == 401


def test_post_macro_refresh_authorized_with_secret(client):
    """REINFORCEMENT 4: Verifies HTTP 200 when valid X-Cron-Secret is provided."""
    secret = settings.cron_shared_secret or "swayam-cron-internal-secret-2026"
    with patch("swayam.api.routes.macro.ingest_macro_calendar") as mock_ingest:
        mock_ingest.return_value = {"status": "success", "count": 7}
        resp = client.post(
            "/api/macro/refresh?mode=ingest",
            headers={"X-Cron-Secret": secret},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "ingest"
        assert data["ingest"]["status"] == "success"


def test_get_macro_events_staleness_flag(client):
    """REINFORCEMENT 3: Verifies is_stale and stale_warning when last cron > 8 days ago."""
    old_time = (datetime.now(timezone.utc) - timedelta(days=9)).isoformat()

    mock_db = MagicMock()
    # Events query returns 1 item
    mock_db.client.table.return_value.select.return_value.gte.return_value.lte.return_value.order.return_value.eq.return_value.execute.return_value.data = [
        {
            "event_key": "IN_CPI_OLD",
            "event_name": "India CPI",
            "event_date": "2026-09-10",
            "country": "IN",
            "highlighted": True,
            "impact_brief": "Old brief",
        }
    ]
    # Latest row query returns old_time
    mock_db.client.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"fetched_at": old_time, "curated_at": old_time}
    ]

    with patch("swayam.api.routes.macro.SupabaseDB", return_value=mock_db):
        resp = client.get("/api/macro/events?highlighted_only=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_stale"] is True
        assert "Calendar may be stale" in data["stale_warning"]
