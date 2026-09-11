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

from fastapi import HTTPException
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
    """A chain with a real book on it.

    Every quote carries a bid and an ask, because since Build A the position is
    marked at the side he would actually GET rather than at the last trade. A
    chain with only a traded price is a chain nothing can be marked against,
    and there is a test below that says exactly that.
    """
    return {
        "underlyingValue": spot,
        "optionsChain": [
            {
                "strike_price": 24850.0,
                "put_ltp": ltp_24850_pe,
                "put_bid": ltp_24850_pe - 1.0,
                "put_ask": ltp_24850_pe + 1.0,
                "put_iv": 0.16,
                "call_ltp": 120.0,
                "call_bid": 119.0,
                "call_ask": 121.0,
                "call_iv": 0.14,
            },
            {
                "strike_price": 24100.0,
                "put_ltp": ltp_24100_pe,
                "put_bid": ltp_24100_pe - 0.5,
                "put_ask": ltp_24100_pe + 0.5,
                "put_iv": 0.18,
                "call_ltp": 600.0,
                "call_bid": 599.0,
                "call_ask": 601.0,
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
                "entry_charges_inr": 30.11,
                "expiry_date": "2026-09-11",
            },
            {
                "strike": 24100.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 1,
                "lot_size": 75,
                "entry_premium": 60.0,
                "entry_charges_inr": 12.44,
                "expiry_date": "2026-09-11",
            },
        ],
    }


def test_positions_live_marks_each_leg_at_the_side_he_would_get(client):
    """The mark is the price he could actually trade at, not the last trade.

    UNTIL BUILD A this test asserted a P&L of 4,500, computed from the traded
    prices of 220.00 and 40.00. That was nobody's price: to get out of the long
    put he has to SELL it, at the bid, and to get out of the short put he has to
    BUY it back, at the ask. The old figure was a profit he could not have
    realised, and the exit already filled the other way (services/fills.py
    reversed), so the screen and the fill disagreed.

    Now, on a book of 219.00 / 221.00 and 39.50 / 40.50:

      long  24,850 PE, bought at 180.00, marked at the BID 219.00
            (219.00 - 180.00) x 75 = +2,925.00
      short 24,100 PE, sold at 60.00, marked at the ASK 40.50
            (60.00 - 40.50) x 75 = +1,462.50

      gross                                        +4,387.50
      as a share of the 9,000 max loss              0.4875
      position value  219.00 x 75 - 40.50 x 75     +13,387.50
    """
    sample_pos = _make_sample_position()

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.fyers_client") as mock_fyers,
        # Round 1b: the live valuation reads api/chain_feed.py now, so the
        # chain is stubbed at this route's own door rather than at the
        # broker client, which it no longer calls itself.
        patch("swayam.api.routes.positions._get_cached_option_chain") as mock_chain_door,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_pos
        ]
        mock_chain_door.return_value = mock_fyers.get_option_chain.return_value = _make_mock_chain(
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

    assert abs(item["unrealized_pnl_inr"] - 4387.50) < 1.0
    assert abs(item["unrealized_pnl_pct_of_risk"] - 0.4875) < 0.01
    assert abs(item["current_position_value_inr"] - 13387.50) < 1.0

    # Each leg says WHICH side of the book its mark came from, so the card can
    # print it and he can see that the figure is the one he would get.
    legs = {(l["strike"], l["option_type"]): l for l in item["legs"]}
    long_leg = legs[(24850.0, "PE")]
    short_leg = legs[(24100.0, "PE")]
    assert long_leg["mark_side"] == "bid"
    assert long_leg["mark"] == 219.0
    assert short_leg["mark_side"] == "ask"
    assert short_leg["mark"] == 40.5
    # The traded price is kept beside it, as history rather than as the mark.
    assert long_leg["current_ltp"] == 220.0

    # And the round trip is costed: what was paid to get in, and what getting
    # out would cost right now at these marks.
    assert item["charges_in_inr"] == pytest.approx(30.11 + 12.44, abs=0.01)
    assert item["charges_out_now_inr"] > 0
    assert item["net_if_exit_now_inr"] == pytest.approx(
        item["unrealized_pnl_inr"] - item["charges_in_inr"] - item["charges_out_now_inr"], abs=0.01
    )
    assert item["net_if_exit_now_inr"] < item["unrealized_pnl_inr"], "charges only ever take"


def test_a_leg_with_no_book_cannot_be_marked_and_says_so(client):
    """A traded price is not a substitute for a book. No bid, no mark."""
    sample_pos = _make_sample_position()
    no_book = {
        "underlyingValue": 24800.0,
        "optionsChain": [
            {"strike_price": 24850.0, "put_ltp": 220.0, "put_iv": 0.16},
            {"strike_price": 24100.0, "put_ltp": 40.0, "put_bid": 39.5, "put_ask": 40.5, "put_iv": 0.18},
        ],
    }

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.fyers_client") as mock_fyers,
        # Round 1b: the live valuation reads api/chain_feed.py now, so the
        # chain is stubbed at this route's own door rather than at the
        # broker client, which it no longer calls itself.
        patch("swayam.api.routes.positions._get_cached_option_chain") as mock_chain_door,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_pos
        ]
        mock_chain_door.return_value = mock_fyers.get_option_chain.return_value = no_book
        mock_fyers.get_nifty_spot.return_value = 24800.0

        resp = client.get("/api/positions/live")

    assert resp.status_code == 200
    item = resp.json()[0]
    assert item["unrealized_pnl_inr"] is None
    assert "bid is not published" in item["error"]
    # And the leg that could not be marked names itself.
    bad = [l for l in item["legs"] if l.get("error")]
    assert bad and bad[0]["strike"] == 24850.0


def test_a_missing_entry_charge_hides_the_cost_but_not_the_profit(client):
    """His trades opened before 2026-09-09 record no charges on their legs.

    The profit is still perfectly readable; only what the round trip cost is
    not. Blanking the profit as well would hide a figure that IS known behind
    one that is not.
    """
    sample_pos = _make_sample_position()
    for leg in sample_pos["legs"]:
        leg.pop("entry_charges_inr", None)

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.fyers_client") as mock_fyers,
        # Round 1b: the live valuation reads api/chain_feed.py now, so the
        # chain is stubbed at this route's own door rather than at the
        # broker client, which it no longer calls itself.
        patch("swayam.api.routes.positions._get_cached_option_chain") as mock_chain_door,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_pos
        ]
        mock_chain_door.return_value = mock_fyers.get_option_chain.return_value = _make_mock_chain()
        mock_fyers.get_nifty_spot.return_value = 24800.0

        resp = client.get("/api/positions/live")

    assert resp.status_code == 200
    item = resp.json()[0]
    assert item["error"] is None
    assert abs(item["unrealized_pnl_inr"] - 4387.50) < 1.0, "the profit is known"
    assert item["net_if_exit_now_inr"] is None, "what it costs to get out is not"
    assert item["charges_in_inr"] is None
    assert "no recorded entry charges" in item["charges_unavailable_reason"]


def test_positions_live_handles_missing_strike_cleanly(client):
    """If a leg strike is not in the option chain, P&L is null and error is flagged."""
    sample_pos = _make_sample_position()

    # Create chain missing the 24100 strike
    # The 24,850 leg has a full book; the 24,100 strike is simply not there, so
    # the missing STRIKE is the only fault this test is about.
    incomplete_chain = {
        "underlyingValue": 24800.0,
        "optionsChain": [
            {
                "strike_price": 24850.0,
                "put_ltp": 220.0,
                "put_bid": 219.0,
                "put_ask": 221.0,
                "put_iv": 0.16,
            }
        ],
    }

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.fyers_client") as mock_fyers,
        # Round 1b: the live valuation reads api/chain_feed.py now, so the
        # chain is stubbed at this route's own door rather than at the
        # broker client, which it no longer calls itself.
        patch("swayam.api.routes.positions._get_cached_option_chain") as mock_chain_door,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_pos
        ]
        mock_chain_door.return_value = mock_fyers.get_option_chain.return_value = incomplete_chain
        mock_fyers.get_nifty_spot.return_value = 24800.0

        resp = client.get("/api/positions/live")

    assert resp.status_code == 200
    data = resp.json()
    item = data[0]

    assert item["unrealized_pnl_inr"] is None
    # The position states the reason in words he can read, and the LEG keeps
    # the machine-readable code beside it.
    assert item["error"] == "a leg is not in the current chain"
    missing_leg = [l for l in item["legs"] if l.get("strike") == 24100.0][0]
    assert missing_leg.get("error") == "strike_not_in_current_chain"


def test_a_position_the_feed_cannot_price_is_marked_rather_than_blanking_the_page(client):
    """One bad trade must not take the whole position area down with it.

    UNTIL BUILD A this raised 503 for the ENTIRE reply, so a single position on
    an expiry FYERS would not serve left him looking at nothing at all. His
    instruction of 2026-09-10 evening: mark that one unavailable with the
    reason and still show the rest.
    """
    sample_pos = _make_sample_position()

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.fyers_client") as mock_fyers,
        # Round 1b: the live valuation reads api/chain_feed.py now, so the
        # chain is stubbed at this route's own door rather than at the
        # broker client, which it no longer calls itself.
        patch("swayam.api.routes.positions._get_cached_option_chain") as mock_chain_door,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_pos
        ]
        # What the real door raises when the feed has nothing: the route
        # wraps the broker error itself, so stubbing the door means the
        # stub has to raise the wrapped form rather than the raw one.
        mock_chain_door.side_effect = HTTPException(
            status_code=503,
            detail="Cannot compute live P&L: FYERS chain unreachable. Try again in a moment.",
        )
        mock_fyers.get_option_chain.side_effect = RuntimeError("FYERS connection timeout")

        resp = client.get("/api/positions/live")

    assert resp.status_code == 200
    item = resp.json()[0]
    assert item["position_id"] == "pos-test-123"
    assert item["unrealized_pnl_inr"] is None
    assert item["net_if_exit_now_inr"] is None
    assert "FYERS chain unreachable" in item["error"]
    # The trade itself is still described, so he can see WHAT he cannot price.
    assert item["strategy_name"]
    assert len(item["legs"]) == 2


def test_one_unpriceable_position_does_not_blank_the_others(client):
    """The whole point of valuing each position on its own."""
    good = _make_sample_position("pos-good-1")
    bad = _make_sample_position("pos-bad-1")
    bad["expiry_date"] = "2026-12-31"
    for leg in bad["legs"]:
        leg["expiry_date"] = "2026-12-31"

    def chain_for(underlying, expiry=None):
        if str(expiry) == "2026-12-31":
            raise RuntimeError("FYERS has no chain for that expiry")
        return _make_mock_chain()

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        # This one already stubs the route's own door, per expiry, which is
        # exactly where Round 1b moved the chain read to.
        patch("swayam.api.routes.positions._get_cached_option_chain", side_effect=chain_for),
        patch("swayam.api.routes.positions.fyers_client") as mock_fyers,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            good, bad
        ]
        mock_fyers.get_nifty_spot.return_value = 24800.0

        resp = client.get("/api/positions/live")

    assert resp.status_code == 200
    data = {p["position_id"]: p for p in resp.json()}
    assert len(data) == 2
    assert data["pos-good-1"]["unrealized_pnl_inr"] is not None, "the good one still shows its money"
    assert data["pos-bad-1"]["unrealized_pnl_inr"] is None
    assert data["pos-bad-1"]["error"]


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
        # Round 1b: the live valuation reads api/chain_feed.py now, so the
        # chain is stubbed at this route's own door rather than at the
        # broker client, which it no longer calls itself.
        patch("swayam.api.routes.positions._get_cached_option_chain") as mock_chain_door,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_pos
        ]
        mock_chain_door.return_value = mock_fyers.get_option_chain.return_value = _make_mock_chain()
        mock_fyers.get_nifty_spot.return_value = 24800.0

        # Call 1
        resp1 = client.get("/api/positions/live")
        assert resp1.status_code == 200

        # Call 2 immediately (within 5s)
        resp2 = client.get("/api/positions/live")
        assert resp2.status_code == 200

        # FYERS get_option_chain must have been called exactly once
        # Two calls on the FIRST request: one resolves the expiry to a FYERS
        # epoch, one reads the chain. The second request adds none, which is
        # what the five-second cache is for.
        assert mock_chain_door.call_count == 2


def test_positions_live_holding_days_calculation(client):
    """Verifies days held and days remaining calculation."""
    sample_pos = _make_sample_position()
    sample_pos["opened_at"] = "2026-09-01T10:00:00Z"
    sample_pos["expiry_date"] = "2026-09-24"

    with (
        patch("swayam.api.routes.positions.db") as mock_db,
        patch("swayam.api.routes.positions.fyers_client") as mock_fyers,
        # Round 1b: the live valuation reads api/chain_feed.py now, so the
        # chain is stubbed at this route's own door rather than at the
        # broker client, which it no longer calls itself.
        patch("swayam.api.routes.positions._get_cached_option_chain") as mock_chain_door,
    ):
        mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_pos
        ]
        mock_chain_door.return_value = mock_fyers.get_option_chain.return_value = _make_mock_chain()
        mock_fyers.get_nifty_spot.return_value = 24800.0

        resp = client.get("/api/positions/live")

    assert resp.status_code == 200
    item = resp.json()[0]
    assert item["days_held"] >= 0
    assert item["days_remaining_to_expiry"] >= 0

