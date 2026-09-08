"""
Unit and integration tests for Trade Journal & Performance Analytics (BUILD-11).
"""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from swayam.api import app
from swayam.db import db

client = TestClient(app)

SAMPLE_POSITIONS = [
    {
        "id": "pos-001",
        "opened_at": "2026-09-01T09:30:00Z",
        "closed_at": "2026-09-01T11:45:00Z",
        "strategy_name": "Bear Put Spread",
        "underlying": "NIFTY",
        "legs": [{"strike": 25000, "option_type": "PE", "direction": "BUY", "quantity_lots": 1}],
        "net_debit_credit_inr": -3500.0,
        "max_loss_inr": 3500.0,
        "max_profit_inr": 7000.0,
        "status": "closed",
        "spot_at_entry": 25100.0,
        "spot_at_exit": 24980.0,
        "points_in_trade": -120.0,
        "time_in_trade_minutes": 135,
        "charges_inr": 80.0,
        "rules_followed": True,
        "rules_broken_reason": None,
        "exit_reason": "Target Hit",
        "directional_view": "Bearish",
        "setup_technical": "Breakdown below VWAP",
        "setup_location": "Prior Day Low",
        "with_or_against_trend": "With Trend",
        "moneyness_summary": "OTM Bear Spread",
        "entry_rationale": "Clear head-and-shoulders breakdown",
        "exit_rationale": "Hit 50% target",
        "journal_path": "02 - Projects/Trading/04 - Journal/2026-09-01-trade01.md",
        "provenance": "live",
    },
    {
        "id": "pos-002",
        "opened_at": "2026-09-02T10:00:00Z",
        "closed_at": "2026-09-02T14:00:00Z",
        "strategy_name": "Bull Call Spread",
        "underlying": "NIFTY",
        "legs": [{"strike": 25200, "option_type": "CE", "direction": "BUY", "quantity_lots": 1}],
        "net_debit_credit_inr": -4000.0,
        "max_loss_inr": 4000.0,
        "max_profit_inr": 8000.0,
        "status": "closed",
        "spot_at_entry": 25150.0,
        "spot_at_exit": 25050.0,
        "points_in_trade": -100.0,
        "time_in_trade_minutes": 240,
        "charges_inr": 80.0,
        "rules_followed": False,
        "rules_broken_reason": "Widened stop loss past planned ceiling",
        "exit_reason": "Stop Loss Hit",
        "directional_view": "Bullish",
        "setup_technical": "Ascending triangle",
        "setup_location": "VWAP Support",
        "with_or_against_trend": "Against Trend",
        "moneyness_summary": "ATM Bull Spread",
        "entry_rationale": "Anticipated breakout",
        "exit_rationale": "Stopped out",
        "journal_path": "02 - Projects/Trading/04 - Journal/2026-09-02-trade01.md",
        "provenance": "live",
    }
]


# Not his trades. Written by a build test, marked with the one column that says
# so. Nothing below may count them.
SAMPLE_POSITIONS.append({
    "id": "pos-test-001",
    "opened_at": "2026-09-03T09:30:00Z",
    "strategy_name": "Violating Spread",
    "underlying": "NIFTY",
    "legs": [{"strike": 25000, "option_type": "CE", "direction": "BUY", "quantity_lots": 1}],
    "net_debit_credit_inr": -9750.0,
    "max_loss_inr": 9750.0,
    "max_profit_inr": 143276.0,
    "status": "closed",
    "charges_inr": 150.0,
    "rules_followed": True,
    "exit_reason": "Target Hit",
    "provenance": "build_test",
})

# His trade, closed, but with no row in swayam_trade_history. Its result cannot
# be read. It must be reported as unknown, never scored as zero rupees.
SAMPLE_POSITIONS.append({
    "id": "pos-unpriced",
    "opened_at": "2026-09-04T09:30:00Z",
    "strategy_name": "Iron Condor",
    "underlying": "NIFTY",
    "legs": [{"strike": 25000, "option_type": "CE", "direction": "SELL", "quantity_lots": 1}],
    "net_debit_credit_inr": 2000.0,
    "max_loss_inr": 5000.0,
    "max_profit_inr": 2000.0,
    "status": "closed",
    "charges_inr": 200.0,
    "rules_followed": True,
    "exit_reason": "Time Exit",
    "provenance": "live",
})

SAMPLE_HISTORY = [
    {
        "position_id": "pos-001",
        "realized_pnl_inr": 5000.0,
        "total_charges_inr": 80.0,
        "close_reason": "Target Hit",
        "closed_at": "2026-09-01T11:45:00Z",
    },
    {
        "position_id": "pos-002",
        "realized_pnl_inr": -4080.0,
        "total_charges_inr": 80.0,
        "close_reason": "Stop Loss Hit",
        "closed_at": "2026-09-02T14:00:00Z",
    }
]

SAMPLE_LESSONS = [
    {
        "id": "les-001",
        "position_id": "pos-001",
        "lesson_text": "Bear Put Spread executed well, capturing profit on breakdown.",
        "lesson_source": "ai_generated",
        "created_at": "2026-09-01T11:45:00Z",
    },
    {
        "id": "les-002",
        "position_id": "pos-002",
        "lesson_text": "Bull Call Spread broke stop discipline resulting in max loss.",
        "lesson_source": "ai_generated",
        "created_at": "2026-09-02T14:00:00Z",
    }
]


class MockQuery:
    def __init__(self, data):
        self._data = list(data)
        self._filtered = list(data)

    def select(self, *args, **kwargs):
        return self

    def eq(self, col, val):
        self._filtered = [r for r in self._filtered if str(r.get(col)) == str(val)]
        return self

    def ilike(self, *args, **kwargs):
        return self

    def gte(self, *args, **kwargs):
        return self

    def neq(self, col, val):
        self._filtered = [r for r in self._filtered if str(r.get(col)) != str(val)]
        return self

    def lt(self, col, val):
        self._filtered = [r for r in self._filtered if str(r.get(col, "")) < str(val)]
        return self

    def update(self, values):
        for r in self._filtered:
            r.update(values)
        return self

    def lte(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        res = MagicMock()
        res.data = list(self._filtered)
        return res


class MockDBClient:
    def table(self, name):
        if name == "swayam_positions":
            return MockQuery(SAMPLE_POSITIONS)
        elif name == "swayam_trade_history":
            return MockQuery(SAMPLE_HISTORY)
        elif name == "swayam_lessons":
            return MockQuery(SAMPLE_LESSONS)
        return MockQuery([])


def test_get_journal_trades_returns_200_and_kpis(monkeypatch):
    monkeypatch.setattr(db, "_client", MockDBClient())

    res = client.get("/api/journal/trades?status=closed")
    assert res.status_code == 200
    data = res.json()
    assert "trades" in data
    assert "kpis" in data

    listed = {t["position_id"] for t in data["trades"]}
    # The build-test row never appears, in any list, under any filter.
    assert "pos-test-001" not in listed
    # The unpriced trade IS listed, so he can see it exists and needs fixing.
    assert listed == {"pos-001", "pos-002", "pos-unpriced"}

    unpriced = next(t for t in data["trades"] if t["position_id"] == "pos-unpriced")
    assert unpriced["net_pnl_inr"] is None, "a result nobody can read must not render as zero"
    assert unpriced["outcome"] == "UNKNOWN"

    # Only SQUARED-OFF trades reach his record. Two of the three qualify.
    kpis = data["kpis"]
    assert kpis["total_trades"] == 2
    assert kpis["wins_count"] == 1
    assert kpis["losses_count"] == 1
    assert kpis["win_rate_pct"] == 50.0
    assert kpis["discipline_rate_pct"] == 50.0
    assert kpis["charges_drag_inr"] == 160.0
    assert kpis["cumulative_net_pnl_inr"] == 920.0  # 5000 - 4080 = 920

    # What was left out, said out loud rather than silently dropped.
    assert data["excluded_test_rows"] == 1
    assert data["unpriced_closed_trades"] == 1


def test_the_percentage_is_of_his_live_balance_not_a_hardcoded_five_lakh(monkeypatch):
    """The margin base was 500000.0, a figure that was neither his nor chosen.

    `conftest.deterministic_capital` pins his real 2026-09-07 balance, so the
    expected figure below is computed from the same number the desk uses.
    """
    monkeypatch.setattr(db, "_client", MockDBClient())

    data = client.get("/api/journal/trades?status=closed").json()

    assert data["capital_base_inr"] == pytest.approx(971002.38)
    assert "FYERS" in (data["capital_base_source"] or "")

    expected = round(920.0 / 971002.38 * 100, 2)
    assert data["kpis"]["cumulative_pnl_pct_of_capital"] == pytest.approx(expected)
    # The old divisor would have given this instead.
    assert data["kpis"]["cumulative_pnl_pct_of_capital"] != pytest.approx(
        round(920.0 / 500000.0 * 100, 2)
    )


def test_an_empty_book_reports_nothing_rather_than_zero(monkeypatch):
    """No trades means no win rate and no discipline rate, not 0% and 100%."""

    class EmptyClient:
        def table(self, name):
            return MockQuery([])

    monkeypatch.setattr(db, "_client", EmptyClient())

    kpis = client.get("/api/journal/trades?status=closed").json()["kpis"]
    assert kpis["total_trades"] == 0
    assert kpis["win_rate_pct"] is None
    assert kpis["discipline_rate_pct"] is None
    assert kpis["avg_rr_actual"] is None
    assert kpis["cumulative_pnl_pct_of_capital"] is None


def test_get_journal_trade_detail_returns_single_trade(monkeypatch):
    monkeypatch.setattr(db, "_client", MockDBClient())

    res = client.get("/api/journal/trade/pos-001")
    assert res.status_code == 200
    data = res.json()
    assert data["position_id"] == "pos-001"
    assert data["strategy_name"] == "Bear Put Spread"
    assert data["net_pnl_inr"] == 5000.0
    assert data["lesson_text"] == "Bear Put Spread executed well, capturing profit on breakdown."


def test_get_journal_trade_detail_404(monkeypatch):
    monkeypatch.setattr(db, "_client", MockDBClient())

    res = client.get("/api/journal/trade/pos-unknown")
    assert res.status_code == 404


def test_get_journal_analytics(monkeypatch):
    monkeypatch.setattr(db, "_client", MockDBClient())

    res = client.get("/api/journal/analytics")
    assert res.status_code == 200
    data = res.json()
    assert "cumulative_pnl_series" in data
    assert "pnl_by_strategy" in data
    assert "pnl_by_exit_reason" in data
    assert "win_rate_by_trend" in data
    assert "recent_lessons" in data
    assert len(data["pnl_by_strategy"]) >= 1
    assert len(data["recent_lessons"]) >= 1


def test_journal_db_failure_raises_503(monkeypatch):
    class ErrorClient:
        def table(self, *args):
            raise RuntimeError("Supabase connection reset")

    monkeypatch.setattr(db, "_client", ErrorClient())
    res = client.get("/api/journal/trades")
    assert res.status_code == 503
    assert "safety-critical service" in res.json()["detail"]


def test_the_retired_archive_endpoint_refuses_and_writes_nothing(monkeypatch):
    """Opening the Trade Journal used to fire this at his live database.

    The page no longer calls it, but a browser holding an old bundle still
    will, so the endpoint must refuse rather than quietly archive rows by a
    hardcoded date. There is one mark now, `provenance`, and it is filtered in
    every query rather than applied by rewriting his rows.
    """
    written: list[tuple[str, dict]] = []

    class RecordingQuery(MockQuery):
        def update(self, values):
            written.append(("update", dict(values)))
            return super().update(values)

    class RecordingClient:
        def table(self, name):
            return RecordingQuery(SAMPLE_POSITIONS)

    monkeypatch.setattr(db, "_client", RecordingClient())

    res = client.post("/api/journal/archive-test-trades")
    assert res.status_code == 410
    assert "provenance" in res.json()["detail"]
    assert written == [], "a retired endpoint must not touch his record"
