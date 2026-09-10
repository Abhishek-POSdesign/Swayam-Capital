"""Reading, re-pricing and cancelling his open orders. Build B, BUILD_03 §3.4.

An order that waits has to be visible and changeable, or it is worse than a
refusal: he would not know what the terminal was holding on his behalf.

What these hold:

  * the three groups the position area draws, each order saying exactly what
    it is waiting for and how far the book is from it
  * the sentence he must never be without: an order fills only while this
    terminal is awake and reading prices
  * a re-price keeps the order's id and its place in his book
  * modify and cancel refuse on anything that has stopped resting
  * a resting exit killed by the bell on a trade that is STILL OPEN is named,
    because he may otherwise believe he is flat

Offline throughout. The database is the in-memory stand-in, the market is a
dictionary, and the exchange's band is handed in rather than read.
"""

from datetime import datetime, timedelta
from unittest.mock import patch
import uuid

import pytest
from fastapi.testclient import TestClient

from swayam.api import app
from swayam.services import order_watcher
from swayam.services import orders as book
from swayam.services.price_band import FYERS_DEPTH, UNAVAILABLE, PriceBand

client = TestClient(app)

EXPIRY = "2026-09-29"
POSITION = "7cd4d017-2c92-445a-a348-28f395c03db8"


def _band(lower=0.05, upper=1000.0, tick=0.05):
    return PriceBand(lower=lower, upper=upper, tick=tick, source=FYERS_DEPTH, symbol="NSE:TEST")


def _leg(direction="buy", strike=23800.0, opt="CE", **extra):
    out = {
        "direction": direction, "strike": float(strike), "option_type": opt,
        "expiry_date": EXPIRY, "quantity_lots": 1, "underlying": "NIFTY",
    }
    out.update(extra)
    return out


def _place(fake_db, *, kind=book.ENTRY, limit=95.0, leg=None, position_id=None, band=None):
    return book.place([book.NewOrder(
        kind=kind, leg=leg or _leg(), limit_price=limit, position_id=position_id,
        group_id=str(uuid.uuid4()),
        band=_band() if band is None else band,
        provenance="terminal_test",
    )])[0]


BOOK = {(23800.0, "CE"): {"bid": 98.60, "ask": 98.75, "ltp": 109.40}}


def _reading(state="live"):
    """The chain the feed would hand the route, without any FYERS call."""
    return patch.object(order_watcher, "_chain_for", return_value=(23389.25, BOOK, state))


@pytest.fixture(autouse=True)
def _clean_watcher():
    order_watcher.reset()
    yield
    order_watcher.reset()


# ------------------------------------------------------------------- reading


@pytest.mark.fake_db
def test_the_three_groups_come_back_with_what_each_order_waits_for(fake_db):
    resting = _place(fake_db, limit=95.0, kind=book.EXIT_LEG, position_id=POSITION,
                     leg=_leg(direction="buy", sequence=3))
    filled = _place(fake_db, limit=90.0)
    cancelled = _place(fake_db, limit=80.0)
    fake_db.rows["swayam_orders"][1]["status"] = book.FILLED
    fake_db.rows["swayam_orders"][2]["status"] = book.CANCELLED

    with _reading(), patch.object(book, "expire_due", return_value=[]):
        res = client.get("/api/orders?date=today")

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["counts"] == {"resting": 1, "filled": 1, "closed": 1}
    assert [o["id"] for o in body["resting"]] == [resting["id"]]
    assert [o["id"] for o in body["filled"]] == [filled["id"]]
    assert [o["id"] for o in body["closed"]] == [cancelled["id"]]

    waiting = body["resting"][0]
    assert waiting["state"]["waiting_for"] == "waiting for the ask to reach 95.00"
    assert waiting["state"]["book"] == 98.75
    assert waiting["state"]["distance"] == 3.75
    assert waiting["state"]["needs"] == "fall"
    assert "inside today's band" in waiting["state"]["band"]
    assert waiting["can_modify"] is True and waiting["can_cancel"] is True


@pytest.mark.fake_db
def test_every_reply_carries_the_sentence_about_being_awake(fake_db):
    """He must never believe an order is watched while he is away."""
    _place(fake_db)
    with _reading(), patch.object(book, "expire_due", return_value=[]):
        body = client.get("/api/orders").json()
    assert "while one of your pages is open" in body["awake_note"]
    assert "not sitting at the broker" in body["awake_note"]


@pytest.mark.fake_db
def test_an_entry_order_says_it_will_open_a_new_trade(fake_db):
    _place(fake_db, kind=book.ENTRY)
    with _reading(), patch.object(book, "expire_due", return_value=[]):
        body = client.get("/api/orders").json()
    order = body["resting"][0]
    assert order["trade_label"] == "New trade"
    assert order["trade_note"] == "entry · opens when it fills"
    assert order["position_id"] is None


@pytest.mark.fake_db
def test_reading_the_book_runs_the_bell_first_so_nothing_shows_resting_past_1530(fake_db):
    """The sweep happens on the read as well as on the watcher's pass.

    If the watcher has not had a look since 15:30 (no page open, no refresh),
    the screen must still never print "resting" for something the bell killed.
    """
    _place(fake_db)
    swept = {"ran": False}

    def _sweep(*_a, **_k):
        swept["ran"] = True
        for row in fake_db.rows["swayam_orders"]:
            row["status"] = book.EXPIRED
        return []

    with _reading(), patch.object(book, "expire_due", side_effect=_sweep):
        body = client.get("/api/orders").json()

    assert swept["ran"] is True
    assert body["counts"]["resting"] == 0
    assert body["counts"]["closed"] == 1


# ------------------------------------------------------------------- modify


@pytest.mark.fake_db
def test_a_new_price_keeps_the_same_order(fake_db):
    order = _place(fake_db, limit=95.0)
    with patch("swayam.api.routes.orders.band_for_leg", return_value=_band()):
        res = client.patch(f"/api/orders/{order['id']}", json={"limit_price": 97.50})

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"] == order["id"], "a re-price is not a new order"
    assert body["limit_price"] == 97.50
    assert "waits for the ask to reach 97.50" in body["message"]
    assert len(fake_db.rows["swayam_orders"]) == 1


@pytest.mark.fake_db
def test_a_new_price_outside_the_band_is_refused_with_the_band_named(fake_db):
    order = _place(fake_db, limit=95.0)
    with patch("swayam.api.routes.orders.band_for_leg", return_value=_band(0.05, 200.0)):
        res = client.patch(f"/api/orders/{order['id']}", json={"limit_price": 500.0})

    assert res.status_code == 422, res.text
    assert "200.00" in res.json()["detail"]["error"]
    assert float(fake_db.rows["swayam_orders"][0]["limit_price"]) == 95.0, "unchanged"


@pytest.mark.fake_db
def test_a_new_price_is_allowed_when_the_band_could_not_be_read(fake_db):
    """A band nobody could read must not block him. It is not a rule of his."""
    order = _place(fake_db, limit=95.0)
    unknown = PriceBand(None, None, None, UNAVAILABLE, reason="depth timed out")
    with patch("swayam.api.routes.orders.band_for_leg", return_value=unknown):
        res = client.patch(f"/api/orders/{order['id']}", json={"limit_price": 97.50})

    assert res.status_code == 200, res.text
    assert "without a band check" in res.json()["band_note"]


@pytest.mark.fake_db
def test_modify_refuses_on_an_order_that_has_stopped_resting(fake_db):
    for status, said in (
        (book.FILLED, "already filled"),
        (book.EXPIRED, "expired at the bell"),
        (book.CANCELLED, "already cancelled"),
    ):
        order = _place(fake_db, limit=95.0)
        fake_db.rows["swayam_orders"][-1]["status"] = status
        res = client.patch(f"/api/orders/{order['id']}", json={"limit_price": 99.0})
        assert res.status_code == 409, res.text
        assert said in res.json()["detail"]


@pytest.mark.fake_db
def test_modify_refuses_while_an_order_is_being_filled(fake_db):
    """Between the claim and the fill there is a moment. It is not his to edit."""
    order = _place(fake_db, limit=95.0)
    book.claim(order["id"])
    res = client.patch(f"/api/orders/{order['id']}", json={"limit_price": 99.0})
    assert res.status_code == 409
    assert "being filled right now" in res.json()["detail"]


# ------------------------------------------------------------------- cancel


@pytest.mark.fake_db
def test_cancelling_costs_nothing_and_says_so(fake_db):
    order = _place(fake_db, limit=95.0, leg=_leg(direction="buy", strike=23800.0))
    res = client.delete(f"/api/orders/{order['id']}")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == book.CANCELLED
    assert "cost nothing" in body["message"]
    assert "23,800 CE" in body["message"]
    assert fake_db.rows["swayam_orders"][0]["status"] == book.CANCELLED


@pytest.mark.fake_db
def test_cancel_refuses_on_a_filled_order(fake_db):
    order = _place(fake_db)
    fake_db.rows["swayam_orders"][0]["status"] = book.FILLED
    res = client.delete(f"/api/orders/{order['id']}")
    assert res.status_code == 409
    assert "already filled" in res.json()["detail"]


@pytest.mark.fake_db
def test_an_order_that_does_not_exist_says_so(fake_db):
    res = client.delete(f"/api/orders/{uuid.uuid4()}")
    assert res.status_code == 404


# ------------------------------------------------------------ the bell's warning


@pytest.mark.fake_db
def test_a_resting_exit_the_bell_killed_on_an_open_trade_is_named(fake_db):
    """HIS INSTRUCTION, 2026-09-10.

    He presses Exit everything, three legs fill and the fourth rests. The book
    never reaches his price, so at 15:30 that order expires and the leg is
    STILL HIS. He must not discover that by accident, and the line points him
    at the 15:20 naked-shorts reading, which is what tells him whether what he
    is left holding is hedged.
    """
    fake_db.rows["swayam_positions"] = [{
        "id": POSITION, "strategy_name": "Iron Condor", "status": "open", "legs": [],
    }]
    _place(fake_db, kind=book.EXIT_ALL_LEG, position_id=POSITION,
           leg=_leg(direction="buy", strike=23800.0, sequence=3), limit=95.0)
    fake_db.rows["swayam_orders"][0]["status"] = book.EXPIRED

    with _reading(), patch.object(book, "expire_due", return_value=[]):
        body = client.get("/api/orders").json()

    assert len(body["warnings"]) == 1
    warning = body["warnings"][0]
    assert warning["headline"] == "You are NOT out of Iron Condor."
    assert "23,800 CE" in warning["detail"]
    assert "naked-shorts" in warning["detail"]
    assert "expired at the bell" in warning["detail"]


@pytest.mark.fake_db
def test_no_warning_when_the_trade_did_close(fake_db):
    """A trade that closed by other means is not a thing he is still holding."""
    fake_db.rows["swayam_positions"] = [{
        "id": POSITION, "strategy_name": "Iron Condor", "status": "closed", "legs": [],
    }]
    _place(fake_db, kind=book.EXIT_ALL_LEG, position_id=POSITION,
           leg=_leg(sequence=3), limit=95.0)
    fake_db.rows["swayam_orders"][0]["status"] = book.EXPIRED

    with _reading(), patch.object(book, "expire_due", return_value=[]):
        body = client.get("/api/orders").json()

    assert body["warnings"] == []


@pytest.mark.fake_db
def test_an_expired_entry_order_raises_no_warning(fake_db):
    """Nothing was ever open, so nothing is left open. Silence is correct."""
    _place(fake_db, kind=book.ENTRY, limit=95.0)
    fake_db.rows["swayam_orders"][0]["status"] = book.EXPIRED

    with _reading(), patch.object(book, "expire_due", return_value=[]):
        body = client.get("/api/orders").json()

    assert body["warnings"] == []
