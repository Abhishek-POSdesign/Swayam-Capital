"""
Unit and integration tests for AI Lesson Ledger endpoints (BUILD-11).
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from swayam.api import app
from swayam.db import db

client = TestClient(app)

SAMPLE_POSITION = {
    "id": "pos-100",
    "opened_at": "2026-09-03T09:45:00Z",
    "closed_at": "2026-09-03T11:15:00Z",
    "strategy_name": "Iron Condor",
    "underlying": "NIFTY",
    "legs": [],
    "net_debit_credit_inr": 2500.0,
    "max_loss_inr": 5000.0,
    "max_profit_inr": 2500.0,
    "status": "closed",
    "realized_pnl_inr": 2400.0,
    "charges_inr": 160.0,
    "rules_followed": True,
    "rules_broken_reason": None,
    "exit_reason": "Target Hit",
    "entry_rationale": "High IV percentile contraction play",
    "exit_rationale": "Captured 90% premium decay",
    "time_in_trade_minutes": 90,
    "points_in_trade": 15.0,
    "journal_path": None,
}


class MockLessonsTable:
    def __init__(self):
        self.rows = []

    def select(self, *args, **kwargs):
        return self

    def eq(self, col, val):
        self._filter_col = col
        self._filter_val = val
        return self

    def execute(self):
        res = MagicMock()
        if hasattr(self, "_filter_col") and self._filter_col == "position_id":
            res.data = [r for r in self.rows if r.get("position_id") == self._filter_val]
        elif hasattr(self, "_filter_col") and self._filter_col == "id":
            res.data = [r for r in self.rows if r.get("id") == self._filter_val]
        else:
            res.data = list(self.rows)
        return res

    def insert(self, payload):
        res = MagicMock()
        record = {**payload, "id": "les-new-999"}
        self.rows.append(record)
        res.data = [record]
        return self

    def update(self, payload):
        res = MagicMock()
        for r in self.rows:
            if hasattr(self, "_filter_col") and r.get(self._filter_col) == self._filter_val:
                r.update(payload)
        res.data = self.rows
        return self


class MockClientWithPositionsAndLessons:
    def __init__(self):
        self.lessons_table = MockLessonsTable()

    def table(self, name):
        if name == "swayam_positions":
            m = MagicMock()
            m.select.return_value.eq.return_value.execute.return_value.data = [SAMPLE_POSITION]
            return m
        elif name == "swayam_lessons":
            return self.lessons_table
        m = MagicMock()
        m.select.return_value.execute.return_value.data = []
        return m


def test_generate_lesson_success(monkeypatch):
    mock_db = MockClientWithPositionsAndLessons()
    monkeypatch.setattr(db, "_client", mock_db)

    with patch("swayam.ai.router.chat_main_turn") as mock_ai:
        mock_ai.return_value = ("Iron Condor captured premium decay as expected with disciplined exit.", "gemini-3.1-pro-preview")
        res = client.post("/api/lessons/generate/pos-100")
        assert res.status_code == 200
        data = res.json()
        assert data["position_id"] == "pos-100"
        assert data["lesson_text"] == "Iron Condor captured premium decay as expected with disciplined exit."
        assert data["lesson_source"] == "ai_generated"
        assert data["outcome"] == "WIN"


def test_generate_lesson_ai_failure_fallback(monkeypatch):
    mock_db = MockClientWithPositionsAndLessons()
    monkeypatch.setattr(db, "_client", mock_db)

    with patch("swayam.ai.router.chat_main_turn") as mock_ai:
        mock_ai.side_effect = RuntimeError("Vertex quota exhausted")
        res = client.post("/api/lessons/generate/pos-100")
        assert res.status_code == 200
        data = res.json()
        assert data["position_id"] == "pos-100"
        assert "Lesson generation failed" in data["lesson_text"]
        assert data["lesson_source"] == "ai_failed"


def test_update_lesson(monkeypatch):
    mock_db = MockClientWithPositionsAndLessons()
    mock_db.lessons_table.rows.append({
        "id": "les-existing-1",
        "position_id": "pos-100",
        "trade_closed_at": "2026-09-03T11:15:00Z",
        "strategy_name": "Iron Condor",
        "outcome": "WIN",
        "realised_pnl_inr": 2400.0,
        "rr_planned": 0.5,
        "rr_actual": 0.48,
        "lesson_text": "Original auto lesson.",
        "lesson_source": "ai_generated",
        "created_at": "2026-09-03T11:15:00Z",
        "updated_at": "2026-09-03T11:15:00Z",
    })
    monkeypatch.setattr(db, "_client", mock_db)

    res = client.put("/api/lessons/les-existing-1", json={"lesson_text": "My manual refined lesson."})
    assert res.status_code == 200
    data = res.json()
    assert data["lesson_text"] == "My manual refined lesson."
    assert data["lesson_source"] == "user_edited"