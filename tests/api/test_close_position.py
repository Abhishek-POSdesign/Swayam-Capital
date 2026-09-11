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

    Charges are PER LEG, on the side each leg was actually transacted, at the
    price it was transacted at. His instruction, 2026-09-09: "The buy leg has
    its own charges, and the sell leg has its own charges."

        leg 1, bought at 180 and sold at 250:  31.12 + 61.61 =  92.73
        leg 2, sold at 60 and bought at 30:    32.72 + 24.85 =  57.57
        trade                                                = 150.30

    Net realized P&L = 7,500 - 150.30 = 7,349.70.

    This used to be a flat 2 legs x Rs 150 = Rs 300, with nothing charged at
    entry at all.
    """
    open_pos = _make_open_position()

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.append_exit_block") as mock_journal,
    ):
        # No prior result, and no note-path row. Both lookups are new in
        # 2026-09-09's close path and a blanket mock would otherwise answer
        # them with a truthy MagicMock, which reads as 'already closed'.
        mock_db.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
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
    assert data["realized_pnl_inr"] == 7349.70
    assert data["total_charges_inr"] == 150.30
    assert data["journal_path"] == open_pos["journal_path"]

    # Not a multiple of the old flat per-leg guess, in either direction.
    assert data["total_charges_inr"] % 150 != 0

    # Every leg carries its own three figures, and they add up to the trade's.
    legs = data["exit_legs"]
    assert len(legs) == 2
    for leg in legs:
        assert leg["entry_charges_inr"] > 0, "entry was never charged before this"
        assert leg["exit_charges_inr"] > 0
        assert leg["charges_inr"] == pytest.approx(
            leg["entry_charges_inr"] + leg["exit_charges_inr"]
        )
        assert leg["net_pnl_inr"] == pytest.approx(
            leg["gross_pnl_inr"] - leg["charges_inr"]
        )

    assert sum(l["charges_inr"] for l in legs) == pytest.approx(data["total_charges_inr"])
    assert sum(l["gross_pnl_inr"] for l in legs) == pytest.approx(data["gross_pnl_inr"])
    assert data["realized_pnl_inr"] == pytest.approx(
        data["gross_pnl_inr"] - data["total_charges_inr"]
    )

    # The bought leg and the sold leg cost different amounts, because the
    # securities transaction tax falls on the sell side only.
    assert legs[0]["entry_charges_inr"] != legs[1]["entry_charges_inr"]

    # Verify journal writer was invoked with correct parameters
    mock_journal.assert_called_once()
    kwargs = mock_journal.call_args.kwargs
    assert kwargs["net_pnl_inr"] == 7349.70
    assert kwargs["close_reason"] == "target_hit"
    assert kwargs["charges_inr"] == 150.30


def test_close_position_404_when_not_found(client):
    with patch("swayam.api.routes.positions.db") as mock_db:
        # No prior result, and no note-path row. Both lookups are new in
        # 2026-09-09's close path and a blanket mock would otherwise answer
        # them with a truthy MagicMock, which reads as 'already closed'.
        mock_db.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
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
        # No prior result, and no note-path row. Both lookups are new in
        # 2026-09-09's close path and a blanket mock would otherwise answer
        # them with a truthy MagicMock, which reads as 'already closed'.
        mock_db.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
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
        # No prior result, and no note-path row. Both lookups are new in
        # 2026-09-09's close path and a blanket mock would otherwise answer
        # them with a truthy MagicMock, which reads as 'already closed'.
        mock_db.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
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


def test_a_failed_exit_note_no_longer_fails_a_close_that_already_happened(client):
    """This test used to assert the bug. It now asserts the fix.

    A NOTE IS NOT A TRADE. Migration 019 established that on the entry side
    after the live site, which cannot reach his vault at all, returned an error
    on every recorded trade and made him press the button again. The exit side
    still raised HTTP 500 with the position already closed in the database, so
    his screen said the close had failed when it had not.

    The note goes to the outbox and the close succeeds.
    """
    open_pos = _make_open_position()

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.append_exit_block") as mock_journal,
    ):
        # No prior result, and no note-path row. Both lookups are new in
        # 2026-09-09's close path and a blanket mock would otherwise answer
        # them with a truthy MagicMock, which reads as 'already closed'.
        mock_db.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            open_pos
        ]
        mock_db.client.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_db.client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_db.get_margin_base_inr.return_value = 850000.0

        # The real case: the vault is unreachable from the container.
        mock_journal.side_effect = RuntimeError("vault unreachable from this container")

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

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "closed"
    assert data["realized_pnl_inr"] == 7349.70, "the result is still recorded in full"


def test_close_position_fills_against_the_book_when_exit_legs_omitted(client):
    """When exit_legs is omitted the close reads the FYERS chain and fills each
    leg against the BOOK: a bought leg sold at the bid, a sold leg bought back
    at the ask. It used to value every exit at the last traded price. PR 2,
    2026-09-09, his correction: keep it as close to reality as possible.

    The book here has no spread, so the result equals the traded-price result
    the older version of this test asserted; the side each leg hit is checked.
    """
    open_pos = _make_open_position()
    mock_chain = {
        "underlyingValue": 24800.0,
        "optionsChain": [
            {"strike_price": 24850.0, "put_ltp": 250.0, "put_iv": 0.16, "put_bid": 250.0, "put_ask": 250.0},
            {"strike_price": 24100.0, "put_ltp": 30.0, "put_iv": 0.18, "put_bid": 30.0, "put_ask": 30.0},
        ],
    }

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.fyers_client") as mock_fyers,
        # Round 1b: the live valuation reads api/chain_feed.py now, so the
        # chain is stubbed at this route's own door rather than at the
        # broker client, which it no longer calls itself.
        patch("swayam.api.routes.positions._get_cached_option_chain") as mock_chain_door,
        patch("swayam.api.routes.positions.append_exit_block") as mock_journal,
        patch("swayam.api.routes.positions._market_is_open_now", return_value=True),
    ):
        # No prior result, and no note-path row. Both lookups are new in
        # 2026-09-09's close path and a blanket mock would otherwise answer
        # them with a truthy MagicMock, which reads as 'already closed'.
        mock_db.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            open_pos
        ]
        mock_db.client.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_db.client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_db.get_margin_base_inr.return_value = 850000.0
        mock_chain_door.return_value = mock_fyers.get_option_chain.return_value = mock_chain

        resp = client.post(
            "/api/positions/pos-close-123/close",
            json={"close_reason": "time_exit"},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "closed"
    assert data["realized_pnl_inr"] == 7349.70
    sides = {l["direction"]: l["exit_side_hit"] for l in data["exit_legs"]}
    assert sides == {"buy": "bid", "sell": "ask"}
    # Twice: the expiry is resolved to a FYERS epoch, then the chain is
    # read. It used to send the word NIFTY as a symbol and never worked.
    # ONCE. It used to be twice: one call to map the expiry to a FYERS epoch
    # and one for the chain itself. Round 1b remembers the epoch for ten
    # minutes and reads the chain from the shared feed, so closing a trade
    # costs this route one read rather than two broker calls.
    assert mock_chain_door.call_count == 1


def test_close_position_journal_uses_the_live_balance(client):
    """The exit block's percentage is of the live FYERS balance.

    This test used to prove a fallback to a constant in the vault when the
    stored margin base was unreachable. Both the stored figure and the
    fallback are gone; conftest pins the live balance at 9,71,002.38.
    """
    open_pos = _make_open_position()

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.append_exit_block") as mock_journal,
    ):
        # No prior result, and no note-path row. Both lookups are new in
        # 2026-09-09's close path and a blanket mock would otherwise answer
        # them with a truthy MagicMock, which reads as 'already closed'.
        mock_db.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            open_pos
        ]
        mock_db.client.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_db.client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

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
    assert mock_journal.call_args.kwargs["margin_base_inr"] == 971002.38
    assert not mock_db.get_margin_base_inr.called


def test_close_position_journal_refuses_503_when_live_balance_unavailable(client):
    """No balance, no percentage: the journal write refuses rather than invent one."""
    from swayam.services.capital import CapitalUnavailable
    open_pos = _make_open_position()

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.append_exit_block") as mock_journal,
        patch("swayam.services.capital.get_capital", side_effect=CapitalUnavailable("Broker returned no fund limits.")),
    ):
        # No prior result, and no note-path row. Both lookups are new in
        # 2026-09-09's close path and a blanket mock would otherwise answer
        # them with a truthy MagicMock, which reads as 'already closed'.
        mock_db.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            open_pos
        ]
        mock_db.client.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_db.client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

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
    assert "live account balance is unavailable" in resp.json()["detail"].lower()
    mock_journal.assert_not_called()

