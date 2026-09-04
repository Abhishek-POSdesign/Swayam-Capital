"""
Tests for POST /api/positions/{position_id}/close endpoint (BUILD-7).

Verifies:
- 200 OK on successful close with correct realized P&L and charges
- 404 Not Found when position ID does not exist
- 400 Bad Request when attempting to close an already-closed position
- 503 Service Unavailable when Supabase database fails
- 500 Internal Server Error when journal write fails after DB update
- Database-before-journal ordering verification
"""

from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from swayam.api.main import app
from swayam.api.routes.positions import _local_paper_positions


@pytest.fixture(autouse=True)
def clean_local_state():
    _local_paper_positions.clear()
    yield
    _local_paper_positions.clear()


@pytest.fixture()
def client():
    return TestClient(app)


def _make_open_position(pos_id="pos-close-123"):
    return {
        "id": pos_id,
        "strategy_name": "Bear Put Spread",
        "underlying": "NIFTY",
        "opened_at": "2026-09-08T10:15:00Z",
        "expiry_date": "2026-09-11",
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


def test_close_position_success(client):
    """Verifies complete close flow with explicit exit legs:

    Entry net debit = -9,000
    Exit: Long leg sold @ 250 (proceeds +18,750), Short leg bought @ 30 (cost -2,250)
    Gross exit value = 18,750 - 2,250 = 16,500
    Gross P&L = 16,500 - (-9,000) = 7,500
    Charges = 2 legs * 150 = 300
    Net realized P&L = 7,500 - 300 = 7,200
    """
    open_pos = _make_open_position()

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.append_exit_block") as mock_journal,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            open_pos
        ]
        mock_db.client.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_db.client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_db.get_margin_base_inr.return_value = 850000.0

        resp = client.post(
            "/api/positions/pos-close-123/close",
            json={
                "close_reason": "target_hit",
                "notes": "Target hit per plan",
                "exit_legs": [
                    {"strike": 24850.0, "option_type": "PE", "exit_premium": 250.0},
                    {"strike": 24100.0, "option_type": "PE", "exit_premium": 30.0},
                ],
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["position_id"] == "pos-close-123"
    assert data["status"] == "closed"
    assert data["realized_pnl_inr"] == 7200.0
    assert data["total_charges_inr"] == 300.0
    assert data["journal_path"] == open_pos["journal_path"]

    # Verify journal writer was invoked with correct parameters
    mock_journal.assert_called_once()
    kwargs = mock_journal.call_args.kwargs
    assert kwargs["net_pnl_inr"] == 7200.0
    assert kwargs["close_reason"] == "target_hit"
    assert kwargs["charges_inr"] == 300.0


def test_close_position_404_when_not_found(client):
    with patch("swayam.api.routes.positions.db") as mock_db:
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        resp = client.post(
            "/api/positions/non-existent-pos/close",
            json={"close_reason": "manual"},
        )

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_close_position_400_when_already_closed(client):
    closed_pos = _make_open_position()
    closed_pos["status"] = "closed"

    with patch("swayam.api.routes.positions.db") as mock_db:
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            closed_pos
        ]

        resp = client.post(
            "/api/positions/pos-close-123/close",
            json={"close_reason": "manual"},
        )

    assert resp.status_code == 400
    assert "already closed" in resp.json()["detail"].lower()


def test_close_position_503_when_database_insert_fails(client):
    open_pos = _make_open_position()

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.append_exit_block") as mock_journal,
    ):
        mock_db.url = "https://supabase.test"
        mock_db.key = "fake-key"
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            open_pos
        ]
        # Simulate trade_history insert failure
        mock_db.client.table.return_value.insert.return_value.execute.side_effect = RuntimeError(
            "Database connection lost"
        )

        resp = client.post(
            "/api/positions/pos-close-123/close",
            json={
                "close_reason": "manual",
                "exit_legs": [
                    {"strike": 24850.0, "option_type": "PE", "exit_premium": 250.0},
                    {"strike": 24100.0, "option_type": "PE", "exit_premium": 30.0},
                ],
            },
        )

    assert resp.status_code == 503
    assert "Database error writing trade history" in resp.json()["detail"]
    # Verify journal write was NOT attempted (DB-before-journal guarantee)
    mock_journal.assert_not_called()


def test_close_position_500_when_journal_write_fails_after_db(client):
    open_pos = _make_open_position()

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.append_exit_block") as mock_journal,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            open_pos
        ]
        mock_db.client.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_db.client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_db.get_margin_base_inr.return_value = 850000.0

        # Simulate journal append failure (e.g. disk permission or file lock)
        mock_journal.side_effect = RuntimeError("Disk full / permission denied")

        resp = client.post(
            "/api/positions/pos-close-123/close",
            json={
                "close_reason": "manual",
                "exit_legs": [
                    {"strike": 24850.0, "option_type": "PE", "exit_premium": 250.0},
                    {"strike": 24100.0, "option_type": "PE", "exit_premium": 30.0},
                ],
            },
        )

    assert resp.status_code == 500
    assert "Trade closed in DB, but writing to journal note failed" in resp.json()["detail"]


def test_close_position_fetches_ltp_when_exit_legs_omitted(client):
    """When exit_legs is omitted, close_position fetches LTPs from FYERS option chain."""
    open_pos = _make_open_position()
    mock_chain = {
        "underlyingValue": 24800.0,
        "optionsChain": [
            {"strike_price": 24850.0, "put_ltp": 250.0, "put_iv": 0.16},
            {"strike_price": 24100.0, "put_ltp": 30.0, "put_iv": 0.18},
        ],
    }

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.fyers_client") as mock_fyers,
        patch("swayam.api.routes.positions.append_exit_block") as mock_journal,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            open_pos
        ]
        mock_db.client.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_db.client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_db.get_margin_base_inr.return_value = 850000.0
        mock_fyers.get_option_chain.return_value = mock_chain

        resp = client.post(
            "/api/positions/pos-close-123/close",
            json={"close_reason": "time_exit"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "closed"
    assert data["realized_pnl_inr"] == 7200.0
    mock_fyers.get_option_chain.assert_called_once()


def test_close_position_margin_fallback_to_method_rules(client):
    open_pos = _make_open_position()

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.append_exit_block") as mock_journal,
        patch("swayam.vault_reader.vault_reader.load_rules") as mock_load,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            open_pos
        ]
        mock_db.client.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_db.client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_db.get_margin_base_inr.side_effect = RuntimeError("DB down")

        mock_rules = MagicMock()
        mock_rules.margin_base_default_inr = 900000.0
        mock_load.return_value = mock_rules

        resp = client.post(
            "/api/positions/pos-close-123/close",
            json={
                "close_reason": "target_hit",
                "exit_legs": [
                    {"strike": 24850.0, "option_type": "PE", "exit_premium": 250.0},
                    {"strike": 24100.0, "option_type": "PE", "exit_premium": 30.0},
                ],
            },
        )

    assert resp.status_code == 200
    mock_journal.assert_called_once()
    assert mock_journal.call_args.kwargs["margin_base_inr"] == 900000.0


def test_close_position_margin_fails_503_when_both_unreachable(client):
    open_pos = _make_open_position()

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.append_exit_block") as mock_journal,
        patch("swayam.vault_reader.vault_reader.load_rules", side_effect=RuntimeError("Vault missing")),
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            open_pos
        ]
        mock_db.client.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_db.client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_db.get_margin_base_inr.side_effect = RuntimeError("DB down")

        resp = client.post(
            "/api/positions/pos-close-123/close",
            json={
                "close_reason": "target_hit",
                "exit_legs": [
                    {"strike": 24850.0, "option_type": "PE", "exit_premium": 250.0},
                    {"strike": 24100.0, "option_type": "PE", "exit_premium": 30.0},
                ],
            },
        )

    assert resp.status_code == 503
    assert "margin base" in resp.json()["detail"].lower()

