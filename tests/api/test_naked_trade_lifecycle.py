"""A trade whose loss has no ceiling, from the row to the closed note.

WHY THIS FILE EXISTS
--------------------
Round 1b made `max_loss_inr` nullable, because `math.inf` in a numeric column
is what stopped him recording a naked single leg on 11 September 2026. Making
it nullable opened four places downstream that assumed the figure was a number,
and the review of that branch found two of them by reading:

  1. `close_position` read it with `float(pos.get("max_loss_inr", 0.0))`. The
     KEY is present and its value is None, so the default never fired and
     `float(None)` raised. Closing a naked trade failed outright.
  2. `close_trade_from_legs` used `or 0.0`, which did not crash but handed a
     zero to the exit note, which printed the result as "0.0% of max risk" for
     a trade whose risk had no ceiling.
  3. The entry note formatted the reward-to-risk ratio, which is now None.
  4. Found by sweeping afterwards: `/api/positions` answers with a model whose
     `max_loss_inr` was a required float, so ONE naked trade would have taken
     the whole open-positions list down, on Home and on the desk.

THE POINT OF THE FILE. This is a path nobody had run. The only reason the first
two were found at all is that someone read the code after the column changed.
These exercise it instead.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from swayam.api.main import app
from swayam.api.models_api import PositionResponse

UNBOUNDED = (
    "net short calls: above the highest strike the loss has no ceiling, "
    "so there is no worst case at expiry to record"
)


@pytest.fixture()
def client():
    return TestClient(app)


def _naked_short_call(pos_id="pos-naked-1"):
    """One sold call. No hedge above it, so no worst case at expiry."""
    return {
        "id": pos_id,
        "strategy_name": "Short Call",
        "underlying": "NIFTY",
        "opened_at": "2026-09-11T09:00:00Z",
        "expiry_date": "2026-09-15",
        "net_debit_credit_inr": 1098.5,
        # THE WHOLE POINT: no number here, and the reason beside it.
        "max_loss_inr": None,
        "max_loss_unbounded_reason": UNBOUNDED,
        "max_profit_inr": 1098.5,
        "risk_at_entry_inr": None,
        "status": "open",
        "mode": "paper",
        "provenance": "terminal_test",
        "journal_path": "02 - Projects/Trading/04 - Journal/2026-09-11-trade01.md",
        "legs": [
            {
                "strike": 23700.0,
                "option_type": "CE",
                "direction": "sell",
                "quantity_lots": 1,
                "lot_size": 65,
                "entry_premium": 16.9,
                "expiry_date": "2026-09-15",
                "entry_charges_inr": 29.21,
                "sequence": 1,
            }
        ],
    }


def test_the_open_positions_list_survives_a_trade_with_no_maximum_loss():
    """Fault 4. A required float here would have blanked the whole list."""
    built = PositionResponse(
        id="pos-naked-1",
        strategy_name="Short Call",
        underlying="NIFTY",
        legs=[],
        net_debit_credit_inr=1098.5,
        max_loss_inr=None,
        max_loss_unbounded_reason=UNBOUNDED,
        max_profit_inr=1098.5,
        breakeven_points=[],
        status="open",
        mode="paper",
        opened_at="2026-09-11T09:00:00Z",
        unrealized_pnl_inr=0.0,
    )
    assert built.max_loss_inr is None
    assert "no ceiling" in built.max_loss_unbounded_reason


def test_closing_a_naked_trade_does_not_raise_on_the_absent_maximum_loss(client):
    """Faults 1 and 2, through the real route.

    Exit prices are supplied rather than filled, so this runs with the market
    shut; the fill rule is a different gate and is not the subject here.
    """
    naked = _naked_short_call()

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.append_exit_block") as mock_exit_note,
        patch("swayam.api.routes.positions._market_is_open_now", return_value=True),
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [naked]
        mock_db.client.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_db.client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_db.get_margin_base_inr.return_value = 962750.0
        mock_exit_note.return_value = naked["journal_path"]

        resp = client.post(
            "/api/positions/pos-naked-1/close",
            json={
                "close_reason": "manual",
                "exit_legs": [
                    {"strike": 23700.0, "option_type": "CE", "exit_premium": 18.9}
                ],
            },
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "closed"

    # AND THE ABSENCE REACHED THE NOTE AS AN ABSENCE. A zero here is what made
    # the exit note print "0.0% of max risk" against a risk of nothing.
    assert mock_exit_note.called
    passed_max_loss = mock_exit_note.call_args.kwargs.get("max_loss_inr")
    assert passed_max_loss is None, (
        f"the exit note was handed {passed_max_loss!r} for a risk that had no ceiling"
    )
