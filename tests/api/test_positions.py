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


def test_close_position_triggers_lesson_generation(monkeypatch) -> None:
    from unittest.mock import MagicMock, patch
    from swayam.db import db

    pos_data = {
        "id": "pos-close-test",
        "strategy_name": "Bear Put Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 25000,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 1,
                "lot_size": 75,
                "entry_premium": 100.0,
            }
        ],
        "net_debit_credit_inr": -7500.0,
        "max_loss_inr": 7500.0,
        "max_profit_inr": 15000.0,
        "status": "open",
        "opened_at": "2026-09-04T09:30:00+00:00",
        "spot_at_entry": 25100.0,
        "journal_path": None,
    }

    class MockCloseDB:
        def __init__(self):
            self.positions_updated = []
            self.lessons_inserted = []

        def table(self, name):
            m = MagicMock()
            if name == "swayam_positions":
                m.select.return_value.eq.return_value.execute.return_value.data = [pos_data]
                def mock_update(payload):
                    self.positions_updated.append(payload)
                    return MagicMock()
                m.update = mock_update
            elif name == "swayam_trade_history":
                m.insert.return_value.execute.return_value.data = [{"id": "hist-1"}]
            elif name == "swayam_lessons":
                m.select.return_value.eq.return_value.execute.return_value.data = []
                def mock_insert(payload):
                    self.lessons_inserted.append(payload)
                    ret = MagicMock()
                    ret.execute.return_value.data = [{**payload, "id": "les-auto-1"}]
                    return ret
                m.insert = mock_insert
            return m

    mock_db = MockCloseDB()
    monkeypatch.setattr(db, "_client", mock_db)

    with patch("swayam.ai.router.chat_main_turn") as mock_ai:
        mock_ai.return_value = ("Bear Put Spread captured target profit on schedule.", "gemini-3.1-pro-preview")
        req_body = {
            "close_reason": "target_hit",
            "notes": "Target hit at 1:2 R:R",
            "exit_legs": [
                {
                    "strike": 25000,
                    "option_type": "PE",
                    "exit_premium": 150.0,
                }
            ]
        }
        res = client.post("/api/positions/pos-close-test/close", json=req_body)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "closed"
        assert data["realized_pnl_inr"] > 0
        assert data["lesson"] is not None
        assert data["lesson"]["lesson_text"] == "Bear Put Spread captured target profit on schedule."
        assert len(mock_db.positions_updated) >= 1
        # Verify time_in_trade_minutes was populated
        last_update = mock_db.positions_updated[-1]
        assert "time_in_trade_minutes" in last_update
        assert "exit_reason" in last_update

