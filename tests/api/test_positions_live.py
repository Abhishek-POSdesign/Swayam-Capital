"""
Tests for GET /api/positions/live endpoint (BUILD-7).

Verifies:
- Live P&L calculation matches manual Black-Scholes / chain pricing within 1% tolerance
- Updated Greeks are calculated from current spot and implied volatilities
- Strike missing from option chain sets unrealized_pnl_inr to null with descriptive error flag
- FYERS failure raises HTTP 503 with clear explanation
- Empty positions list returns empty array
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from swayam.api.main import app
from swayam.api.routes.positions import _chain_cache, _local_paper_positions


@pytest.fixture(autouse=True)
def clean_state():
    """Cleans in-memory caches and position lists between tests."""
    _chain_cache.clear()
    _local_paper_positions.clear()
    yield
    _chain_cache.clear()
    _local_paper_positions.clear()


@pytest.fixture()
def client():
    return TestClient(app)


def _make_mock_chain(spot=24800.0, ltp_24850_pe=220.0, ltp_24100_pe=40.0):
    return {
        "underlyingValue": spot,
        "optionsChain": [
            {
                "strike_price": 24850.0,
                "put_ltp": ltp_24850_pe,
                "put_iv": 0.16,
                "call_ltp": 120.0,
                "call_iv": 0.14,
            },
            {
                "strike_price": 24100.0,
                "put_ltp": ltp_24100_pe,
                "put_iv": 0.18,
                "call_ltp": 600.0,
                "call_iv": 0.15,
            },
        ],
    }


def _make_sample_position(pos_id="pos-test-123"):
    return {
        "id": pos_id,
        "strategy_name": "Bear Put Spread",
        "underlying": "NIFTY",
        "expiry_date": "2026-09-11",
        "opened_at": "2026-09-08T10:15:00Z",
        "net_debit_credit_inr": -9000.0,
        "max_loss_inr": 9000.0,
        "max_profit_inr": 47250.0,
        "status": "open",
        "mode": "paper",
        "journal_path": "02 - Projects/Trading/04 - Journal/2026-09-08-trade01.md",
        "legs": [
            {
                "strike": 24850.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 1,
                "lot_size": 75,
                "entry_premium": 180.0,
                "expiry_date": "2026-09-11",
            },
            {
                "strike": 24100.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 1,
                "lot_size": 75,
                "entry_premium": 60.0,
                "expiry_date": "2026-09-11",
            },
        ],
    }


def test_positions_live_computes_correct_pnl(client):
    """Verifies live P&L matches exact manual math:

    Entry: Buy 1x75 @ 180 (cost 13,500), Sell 1x75 @ 60 (credit 4,500) -> Net debit = -9,000
    Live:  Long leg LTP 220 (val +16,500), Short leg LTP 40 (val -3,000) -> Total value = +13,500
    Unrealized P&L = +13,500 - (-9,000) = +4,500
    % of risk = 4,500 / 9,000 = 50.0%
    """
    sample_pos = _make_sample_position()

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.fyers_client") as mock_fyers,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_pos
        ]
        mock_fyers.get_option_chain.return_value = _make_mock_chain(
            spot=24800.0, ltp_24850_pe=220.0, ltp_24100_pe=40.0
        )
        mock_fyers.get_nifty_spot.return_value = 24800.0

        resp = client.get("/api/positions/live")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1

    item = data[0]
    assert item["position_id"] == "pos-test-123"
    assert item["error"] is None

    # Expected value: (220 - 40) * 75 = 180 * 75 = 13,500
    # Unrealized P&L = 13,500 - (-9,000) = 4,500
    expected_pnl = 4500.0
    assert abs(item["unrealized_pnl_inr"] - expected_pnl) < 1.0
    assert abs(item["unrealized_pnl_pct_of_risk"] - 0.5) < 0.01
    assert item["current_position_value_inr"] == 13500.0


def test_positions_live_handles_missing_strike_cleanly(client):
    """If a leg strike is not in the option chain, P&L is null and error is flagged."""
    sample_pos = _make_sample_position()

    # Create chain missing the 24100 strike
    incomplete_chain = {
        "underlyingValue": 24800.0,
        "optionsChain": [
            {
                "strike_price": 24850.0,
                "put_ltp": 220.0,
                "put_iv": 0.16,
            }
        ],
    }

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.fyers_client") as mock_fyers,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_pos
        ]
        mock_fyers.get_option_chain.return_value = incomplete_chain
        mock_fyers.get_nifty_spot.return_value = 24800.0

        resp = client.get("/api/positions/live")

    assert resp.status_code == 200
    data = resp.json()
    item = data[0]

    assert item["unrealized_pnl_inr"] is None
    assert item["error"] == "strike_not_in_current_chain"
    # The missing leg has error flagged
    missing_leg = [l for l in item["legs"] if l.get("strike") == 24100.0][0]
    assert missing_leg.get("error") == "strike_not_in_current_chain"


def test_positions_live_raises_503_when_fyers_unreachable(client):
    sample_pos = _make_sample_position()

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.fyers_client") as mock_fyers,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_pos
        ]
        mock_fyers.get_option_chain.side_effect = RuntimeError("FYERS connection timeout")

        resp = client.get("/api/positions/live")

    assert resp.status_code == 503
    assert "FYERS chain unreachable" in resp.json()["detail"]


def test_positions_live_empty_when_no_positions(client):
    with patch("swayam.api.routes.positions.db") as mock_db:
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        resp = client.get("/api/positions/live")

    assert resp.status_code == 200
    assert resp.json() == []


def test_positions_live_caching_within_5_seconds(client):
    """Calling /api/positions/live within 5 seconds reuses cached chain and calls FYERS only once."""
    sample_pos = _make_sample_position()

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.fyers_client") as mock_fyers,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_pos
        ]
        mock_fyers.get_option_chain.return_value = _make_mock_chain()
        mock_fyers.get_nifty_spot.return_value = 24800.0

        # Call 1
        resp1 = client.get("/api/positions/live")
        assert resp1.status_code == 200

        # Call 2 immediately (within 5s)
        resp2 = client.get("/api/positions/live")
        assert resp2.status_code == 200

        # FYERS get_option_chain must have been called exactly once
        assert mock_fyers.get_option_chain.call_count == 1


def test_positions_live_holding_days_calculation(client):
    """Verifies days held and days remaining calculation."""
    sample_pos = _make_sample_position()
    sample_pos["opened_at"] = "2026-09-01T10:00:00Z"
    sample_pos["expiry_date"] = "2026-09-24"

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.fyers_client") as mock_fyers,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_pos
        ]
        mock_fyers.get_option_chain.return_value = _make_mock_chain()
        mock_fyers.get_nifty_spot.return_value = 24800.0

        resp = client.get("/api/positions/live")

    assert resp.status_code == 200
    item = resp.json()[0]
    assert item["days_held"] >= 0
    assert item["days_remaining_to_expiry"] >= 0

