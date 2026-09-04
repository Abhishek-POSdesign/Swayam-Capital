import pytest
from fastapi.testclient import TestClient
from swayam.api import app
from swayam.api.routes.positions import record_local_paper_position, _local_paper_positions

client = TestClient(app)


def test_detect_naked_shorts_with_hedged_spread():
    # Clear local test positions
    _local_paper_positions.clear()

    # Add fully hedged spread: 1 buy put, 1 sell put
    record_local_paper_position({
        "id": "test-hedged-1",
        "strategy_name": "Bear Put Spread",
        "underlying": "NIFTY",
        "status": "open",
        "legs": [
            {"strike": 24900, "option_type": "PE", "direction": "buy", "quantity_lots": 1},
            {"strike": 24700, "option_type": "PE", "direction": "sell", "quantity_lots": 1},
        ],
    })

    res = client.get("/api/positions/naked-shorts?at_time=15:20")
    assert res.status_code == 200
    data = res.json()
    assert data["has_naked_shorts"] is False
    assert len(data["violations"]) == 0


def test_detect_naked_shorts_with_unhedged_short():
    _local_paper_positions.clear()

    # Add unhedged short put
    record_local_paper_position({
        "id": "test-naked-1",
        "strategy_name": "Naked Put",
        "underlying": "NIFTY",
        "status": "open",
        "legs": [
            {"strike": 24500, "option_type": "PE", "direction": "sell", "quantity_lots": 1},
        ],
    })

    res = client.get("/api/positions/naked-shorts?at_time=15:20")
    assert res.status_code == 200
    data = res.json()
    assert data["has_naked_shorts"] is True
    assert len(data["violations"]) == 1
    v = data["violations"][0]
    assert v["position_id"] == "test-naked-1"
    assert len(v["suggested_hedges"]) > 0
    assert v["suggested_hedges"][0]["action"] == "BUY"
    assert v["suggested_hedges"][0]["option_type"] == "PE"
    assert "Risk Management Rules § 10a" in v["rule_citation"]


def test_detect_naked_shorts_supabase_failure_raises_503(monkeypatch):
    _local_paper_positions.clear()

    class MockTable:
        def select(self, *args, **kwargs):
            raise Exception("Database connection lost")

    class MockClient:
        def table(self, *args, **kwargs):
            return MockTable()

    from swayam.db import db
    monkeypatch.setattr(db, "_client", MockClient())

    res = client.get("/api/positions/naked-shorts?at_time=15:20")
    assert res.status_code == 503
    data = res.json()
    assert "Naked-shorts safety check unavailable" in data["detail"]
    assert "safety-critical endpoint" in data["detail"]

