"""
Unit and integration tests for BUILD-11.9:
- Authoritative Tuesday-adjusted expiry math & trading session counts
- Option chain analytics: Max Pain, PCR, OI walls, 50-strike boundary validation
- So Far Today grounded Gemini caching & daily cap enforcement (429)
- Institutional participation separation (FII cash vs F&O)
"""

from datetime import date, datetime, timezone
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from swayam.api.main import app
from swayam.services.expiry import (
    adjust_to_previous_trading_day,
    count_trading_sessions,
    get_expiry_metadata,
    is_trading_day,
)
from swayam.services.nifty_snapshot import (
    calculate_max_pain,
    compute_pcr_and_walls,
    compute_technical_metrics,
    get_nifty_snapshot_data,
)
from swayam.services.so_far_today import (
    DailyCapExceededError,
    generate_so_far_today,
    get_cached_so_far_today,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_tuesday_expiry_and_holiday_adjustment():
    """Validates Tuesday-aligned expiries and holiday rollback logic."""
    holidays = {date(2026, 11, 24)}  # Guru Nanak Jayanti on Tuesday
    
    # Non-holiday Tuesday
    tues = date(2026, 9, 8)
    assert tues.weekday() == 1
    assert is_trading_day(tues, holidays) is True
    assert adjust_to_previous_trading_day(tues, holidays) == tues

    # Holiday Tuesday should roll back to Monday
    holiday_tues = date(2026, 11, 24)
    assert is_trading_day(holiday_tues, holidays) is False
    adjusted = adjust_to_previous_trading_day(holiday_tues, holidays)
    assert adjusted == date(2026, 11, 23)
    assert adjusted.weekday() == 0  # Monday


def test_trading_sessions_counting():
    """Asserts accurate count of trading days excluding weekends and holidays."""
    # Friday 2026-09-04 to Tuesday 2026-09-08
    # Days: Friday(trading), Saturday(weekend), Sunday(weekend), Monday(trading), Tuesday(trading)
    # Total trading sessions inclusive = 3
    start = date(2026, 9, 4)
    end = date(2026, 9, 8)
    sessions = count_trading_sessions(start, end, include_start=True)
    assert sessions == 3


def test_expiry_metadata_contract_master():
    """Verifies weekly and monthly expiries derived from FYERS contract master."""
    meta = get_expiry_metadata(ref_date=date(2026, 9, 6))
    assert "weekly_expiry" in meta
    assert "monthly_expiry" in meta
    assert "weekly_dte" in meta
    assert "monthly_dte" in meta

    # Both dates must be Tuesdays or holiday-adjusted weekdays (not Saturday or Sunday)
    w_d = date.fromisoformat(meta["weekly_expiry"])
    m_d = date.fromisoformat(meta["monthly_expiry"])
    assert w_d.weekday() < 5
    assert m_d.weekday() < 5

    # DTE formatted strings
    assert "calendar days" in meta["weekly_dte"]["formatted"]
    assert "trading sessions" in meta["weekly_dte"]["formatted"]


def test_max_pain_calculation_fixture():
    """Computes Max Pain strike from synthetic option chain."""
    # Synthetic chain around 24,800
    chain = [
        {"strike_price": 24600, "call_oi": 10000, "put_oi": 80000},
        {"strike_price": 24700, "call_oi": 25000, "put_oi": 60000},
        {"strike_price": 24800, "call_oi": 50000, "put_oi": 50000},
        {"strike_price": 24900, "call_oi": 75000, "put_oi": 20000},
        {"strike_price": 25000, "call_oi": 95000, "put_oi": 5000},
    ]
    pain = calculate_max_pain(chain)
    assert pain == 24800.0


def test_pcr_and_walls_with_boundary_detection():
    """Asserts PCR, Max Call/Put OI strikes and 50-strike boundary detection."""
    chain = [
        {"strike_price": 24500, "call_oi": 1000, "put_oi": 50000},
        {"strike_price": 24800, "call_oi": 20000, "put_oi": 25000},
        {"strike_price": 25000, "call_oi": 80000, "put_oi": 2000},
    ]
    stats = compute_pcr_and_walls(chain)
    # Total call OI = 101000, total put OI = 77000 -> PCR = 77000/101000 = 0.76
    assert stats["pcr"] == 0.76
    assert stats["max_call_oi_strike"] == 25000
    assert stats["max_put_oi_strike"] == 24500
    # Because 25000 and 24500 are the edge boundaries of this chain:
    assert stats["boundary_touch"] is True


def test_technical_metrics_calculation():
    """Computes 20-day range, 20-DMA, ATR and realized volatility."""
    # Mock daily candles: [timestamp, open, high, low, close, volume]
    candles = []
    base_price = 24000.0
    for i in range(30):
        c = base_price + i * 20
        candles.append([i * 86400, c - 10, c + 30, c - 20, c, 100000])

    metrics = compute_technical_metrics(candles, current_spot=24600.0)
    assert metrics["dma_20"] > 0
    assert metrics["atr_20"] > 0
    assert metrics["range_20d"]["high"] >= metrics["range_20d"]["low"]
    assert 0 <= metrics["spot_position_pct_20d"] <= 100
    assert metrics["sentiment"] in ("Bullish", "Neutral", "Bearish")


def test_nifty_snapshot_institutional_separation():
    """Asserts FII Cash and F&O are kept in separate fields and never blended.

    THE BROKER IS STOOD IN FOR, from 2026-09-11. This test mocked the database
    and not FYERS, so every run of the suite made five real calls to his
    broker: quotes, history and the option chain. It asserts the SHAPE of the
    institutional fields, which come from the database, so the market was
    never the subject. Spending his finite request budget on a shape assertion
    is what the broker cage in conftest exists to catch.
    """
    mock_db = MagicMock()
    mock_db.client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

    from swayam.fyers_client import FyersClientError

    broker = MagicMock()
    broker.get_nifty_spot.side_effect = FyersClientError("stood in for: no broker in tests")
    broker.get_option_chain.side_effect = FyersClientError("stood in for: no broker in tests")
    broker.get_historical_candles.side_effect = FyersClientError("stood in for: no broker in tests")
    broker.model.quotes.side_effect = FyersClientError("stood in for: no broker in tests")
    broker.model.history.side_effect = FyersClientError("stood in for: no broker in tests")
    broker.model.optionchain.side_effect = FyersClientError("stood in for: no broker in tests")

    with patch("swayam.services.nifty_snapshot.fyers_client", broker):
        snap = get_nifty_snapshot_data(is_refresh=True, db=mock_db)
    inst = snap["fno_pane"]["institutional"]

    assert "fii_cash_net_cr" in inst
    assert "fii_fno_net_contracts" in inst
    assert "dii_cash_net_cr" in inst
    assert "dii_fno_net_contracts" in inst

    # Verify no combined bias score field exists
    assert "fii_bias" not in inst
    assert "institutional_bias" not in inst


def test_so_far_today_daily_cap_enforcement():
    """Ensures generate_so_far_today raises DailyCapExceededError when cap is reached."""
    mock_db = MagicMock()
    # Mock count of calls today returning 8
    mock_db.client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value.count = 8
    mock_db.client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

    with pytest.raises(DailyCapExceededError) as exc_info:
        generate_so_far_today(force=True, db=mock_db)
    assert "Daily cap reached" in str(exc_info.value)


def test_so_far_today_api_429_on_cap_hit(client, monkeypatch):
    """Verifies that the FastAPI endpoint returns HTTP 429 when daily cap is reached."""
    with patch("swayam.api.routes.home.generate_so_far_today") as mock_gen:
        mock_gen.side_effect = DailyCapExceededError("Daily cap reached (8 calls). Resets at 09:15 IST tomorrow.")
        resp = client.post("/api/home/so-far-today?force=true")
        assert resp.status_code == 429
        assert "Daily cap reached" in resp.json()["detail"]


def test_so_far_today_cache_retrieval():
    """Tests 60-minute cache validity."""
    mock_db = MagicMock()
    recent_time = datetime.now(timezone.utc).isoformat()
    mock_db.client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {
            "generated_at": recent_time,
            "payload": {"text": "Session summary text", "sources": []},
        }
    ]
    mock_db.client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value.count = 2

    cached = get_cached_so_far_today(max_age_minutes=60, db=mock_db)
    assert cached is not None
    assert cached["is_cached"] is True
    assert cached["text"] == "Session summary text"
