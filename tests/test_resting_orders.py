"""Resting orders, proved rather than described. Build B, BUILD_03 section 5.

A limit the book has not reached now WAITS instead of refusing. His words,
2026-09-10: "It should not execute if the price is not available, but must be
sitting in the system till the time the bid and ask reach the price I want."

These are the things that must be true, and each one is here because getting it
wrong would cost him money rather than looks:

  * a buy fills when the ASK reaches his price and not one tick before; a sell
    when the BID does
  * one order fills AT MOST ONCE, and the guarantee is one conditional update
    in the database that only one process can win. His own requirement of
    2026-09-10: "two copies of the backend can never fill the same order
    twice."
  * nothing fills while the market is shut, and nothing fills after the bell
  * the bell expires everything resting and charges nothing
  * a restart loses nothing: the watcher holds no memory, the book is the book
  * a price outside the exchange's band, or off its tick, rests nothing
  * a band that cannot be read still lets the order rest, and says so
  * modify and cancel refuse on anything that has stopped resting

Everything is offline. The database is the in-memory stand-in from
`tests/db_guard.py`, the market is a dictionary, and the vault is never
touched.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import uuid

import pytest

from tests.db_guard import FakeClient
from swayam.services import order_watcher
from swayam.services import orders as book
from swayam.services.price_band import FYERS_DEPTH, UNAVAILABLE, PriceBand, check_price

EXPIRY = "2026-09-29"


def _band(lower=0.05, upper=1000.0, tick=0.05):
    return PriceBand(lower=lower, upper=upper, tick=tick, source=FYERS_DEPTH, symbol="NSE:TEST")


def _leg(direction="buy", strike=23800.0, opt="CE", lots=1, **extra):
    out = {
        "direction": direction,
        "strike": float(strike),
        "option_type": opt,
        "expiry_date": EXPIRY,
        "quantity_lots": lots,
        "underlying": "NIFTY",
    }
    out.update(extra)
    return out


@pytest.fixture
def store():
    """An empty in-memory database wired into the order book, and a clean watcher."""
    client = FakeClient()
    order_watcher.reset()
    with patch("swayam.services.orders._client", return_value=client):
        yield client
    order_watcher.reset()


def _before_the_bell(order):
    """An instant while the market is still open on the day the order was placed.

    The suite runs at any hour, and after 15:30 IST every resting order in the
    book is correctly expired the moment the watcher looks. So a test about
    FILLING has to say when it is happening, exactly as the running system
    knows what time it is.
    """
    return datetime.fromisoformat(order["expires_at"]) - timedelta(hours=2)


def _place(kind=book.ENTRY, limit=95.0, leg=None, position_id=None, group_id=None, band=None):
    return book.place([book.NewOrder(
        kind=kind,
        leg=leg or _leg(),
        limit_price=limit,
        position_id=position_id,
        group_id=group_id or str(uuid.uuid4()),
        band=band if band is not None else _band(),
        provenance="terminal_test",
    )])[0]


# ------------------------------------------------- has the book reached him


def test_a_buy_waits_for_the_ask_and_fills_the_moment_it_arrives():
    """A buy pays the ask. It fills when the ask comes DOWN to his price."""
    order = {"limit_price": 95.0, "leg": _leg(direction="buy")}
    assert book.would_fill(order, bid=94.0, ask=98.75) is False, "the ask is still above him"
    assert book.would_fill(order, bid=94.9, ask=95.00) is True, "the ask is exactly at his price"
    assert book.would_fill(order, bid=93.0, ask=94.50) is True, "better than his price is a fill"


def test_a_sell_waits_for_the_bid_and_fills_the_moment_it_arrives():
    """A sell receives the bid. It fills when the bid comes UP to his price."""
    order = {"limit_price": 111.0, "leg": _leg(direction="sell")}
    assert book.would_fill(order, bid=108.40, ask=108.60) is False, "the bid is still below him"
    assert book.would_fill(order, bid=111.00, ask=111.20) is True, "the bid is exactly at his price"
    assert book.would_fill(order, bid=112.50, ask=112.70) is True, "better than his price is a fill"


def test_a_missing_side_of_the_book_never_fills_anything():
    """No price is not a price. Nothing fills off a side FYERS did not publish."""
    buy = {"limit_price": 95.0, "leg": _leg(direction="buy")}
    sell = {"limit_price": 111.0, "leg": _leg(direction="sell")}
    assert book.would_fill(buy, bid=94.0, ask=None) is False
    assert book.would_fill(sell, bid=None, ask=120.0) is False
    assert book.would_fill(buy, bid=94.0, ask=0) is False


# --------------------------------------------------- one order, at most once


def test_the_claim_is_one_conditional_update_that_only_one_process_can_win(store):
    """HIS REQUIREMENT, 2026-09-10, in the smallest possible form.

    Two copies of the backend claiming the same order: exactly one of them
    gets it. The `.eq("status", "resting")` on the update is the whole safety
    property, and it lives in the database rather than in any process's memory,
    which is why a second Cloud Run instance cannot double-fill.
    """
    order = _place()
    order_id = order["id"]

    first = book.claim(order_id)
    second = book.claim(order_id)

    assert first is True, "the first caller takes it"
    assert second is False, "the second caller gets nothing, because it is no longer resting"
    assert store.rows["swayam_orders"][0]["status"] == book.FILLING

    # And a third, and a fourth. There is no window in which it re-opens.
    assert book.claim(order_id) is False
    assert book.claim(order_id) is False


def test_a_claim_on_something_that_stopped_resting_is_refused(store):
    """Cancelled, expired, filled: none of them can be claimed and filled."""
    for status in (book.CANCELLED, book.EXPIRED, book.FILLED, book.FAILED):
        order = _place()
        store.rows["swayam_orders"][-1]["status"] = status
        assert book.claim(order["id"]) is False


def test_the_watcher_cannot_fill_one_order_on_two_passes(store):
    """A second reading of the same book must not fill it again."""
    order = _place(limit=95.0, leg=_leg(direction="buy"))
    during = _before_the_bell(order)
    sent = []

    def _pretend_to_fill(order):
        sent.append(order["id"])
        book.mark_filled(order["id"], fill={"fill_price": 95.0}, result={}, position_id="pos-1")
        return True

    with _market(ask=94.50), patch.object(order_watcher, "_fill_entry", side_effect=_pretend_to_fill):
        first = order_watcher.evaluate(now=during)
        order_watcher.invalidate()
        second = order_watcher.evaluate(now=during)

    assert first["filled"] == 1
    assert second["filled"] == 0, "the second pass sees nothing resting"
    assert len(sent) == 1
    assert store.rows["swayam_orders"][0]["status"] == book.FILLED


# ------------------------------------------------------------- the market


def _market(bid=None, ask=None, spot=23389.25, state="live", open_=True):
    """The book the chain feed would hand the watcher, and the clock."""
    lookup = {(23800.0, "CE"): {"bid": bid, "ask": ask, "ltp": 100.0}}
    return _patches(lookup, spot, state, open_)


class _patches:
    def __init__(self, lookup, spot, state, open_):
        self._p = [
            patch.object(order_watcher, "_chain_for", return_value=(spot, lookup, state)),
            patch("swayam.api.chain_feed.chain_feed.is_open", return_value=open_),
        ]

    def __enter__(self):
        for p in self._p:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._p:
            p.stop()
        return False


def test_nothing_fills_while_the_market_is_shut(store):
    """The feed keeps the closing book, and a fill against it is one nobody could get."""
    order = _place(limit=95.0, leg=_leg(direction="buy"))
    with _market(ask=90.0, open_=False), patch.object(order_watcher, "_fill_entry") as sent:
        result = order_watcher.evaluate(now=_before_the_bell(order))
    assert result["filled"] == 0
    assert result["why"] == "the market is shut"
    sent.assert_not_called()
    assert store.rows["swayam_orders"][0]["status"] == book.RESTING


def test_a_closing_reading_of_the_book_fills_nothing(store):
    """Even inside market hours, a reading the feed calls closing is not a book."""
    order = _place(limit=95.0, leg=_leg(direction="buy"))
    with _market(ask=90.0, state="closing"), patch.object(order_watcher, "_fill_entry") as sent:
        result = order_watcher.evaluate(now=_before_the_bell(order))
    assert result["filled"] == 0
    sent.assert_not_called()


def test_the_watcher_leaves_an_order_alone_until_the_book_arrives(store):
    """Not one tick early."""
    order = _place(limit=95.0, leg=_leg(direction="buy"))
    during = _before_the_bell(order)
    with _market(ask=95.05), patch.object(order_watcher, "_fill_entry") as sent:
        assert order_watcher.evaluate(now=during)["filled"] == 0
    sent.assert_not_called()

    order_watcher.invalidate()
    with _market(ask=95.00), patch.object(order_watcher, "_fill_entry", return_value=True) as sent:
        assert order_watcher.evaluate(now=during)["filled"] == 1
    sent.assert_called_once()


# ------------------------------------------------------------- the bell


def test_the_bell_expires_everything_resting_and_charges_nothing(store):
    """15:30, and nothing outlives it."""
    order = _place()
    after_the_bell = datetime.fromisoformat(order["expires_at"]) + timedelta(minutes=1)

    expired = book.expire_due(after_the_bell)

    assert len(expired) == 1
    assert store.rows["swayam_orders"][0]["status"] == book.EXPIRED
    row = store.rows["swayam_orders"][0]
    assert row.get("fill") is None, "nothing filled"
    assert row.get("filled_at") is None
    # No charge column exists on an order at all: an order that expires cannot
    # have cost him anything, so there is nowhere for a charge to hide.
    assert "charges_inr" not in row


def test_the_bell_does_not_touch_an_order_that_already_filled(store):
    order = _place()
    book.claim(order["id"])
    book.mark_filled(order["id"], fill={"fill_price": 95.0}, result={}, position_id="pos-1")

    after = datetime.fromisoformat(order["expires_at"]) + timedelta(minutes=1)
    assert book.expire_due(after) == []
    assert store.rows["swayam_orders"][0]["status"] == book.FILLED


def test_an_order_is_not_expired_before_the_bell(store):
    order = _place()
    before = datetime.fromisoformat(order["expires_at"]) - timedelta(minutes=1)
    assert book.expire_due(before) == []
    assert store.rows["swayam_orders"][0]["status"] == book.RESTING


# ----------------------------------------------------------- after a restart


def test_a_restart_reads_the_book_back_and_loses_nothing(store):
    """The watcher keeps NOTHING in memory. Cloud Run restarts; the table does not.

    This is the whole recovery story: forget every cached thing the process
    had, and the same orders are still there, still resting, still fillable
    exactly once.
    """
    order = _place(limit=95.0, leg=_leg(direction="buy"))

    # The process dies and comes back: every module-level cache is gone.
    order_watcher.reset()

    still_there = book.open_orders()
    assert len(still_there) == 1
    assert still_there[0]["id"] == order["id"]
    assert still_there[0]["status"] == book.RESTING

    with _market(ask=94.0), patch.object(order_watcher, "_fill_entry", return_value=True) as sent:
        assert order_watcher.evaluate(now=_before_the_bell(order))["filled"] == 1
    sent.assert_called_once()


# ------------------------------------------------------------- the band


def test_a_price_outside_the_band_is_refused_with_the_band_named():
    band = _band(lower=0.05, upper=263.85)
    refusal = check_price(band, 300.0)
    assert refusal is not None
    assert "263.85" in refusal and "0.05" in refusal
    assert "outside today's price band" in refusal


def test_a_price_off_the_tick_is_refused_with_the_two_prices_that_trade():
    band = _band(tick=0.05)
    refusal = check_price(band, 95.03)
    assert refusal is not None
    assert "95.00" in refusal and "95.05" in refusal


def test_a_price_inside_the_band_and_on_the_tick_is_accepted():
    assert check_price(_band(lower=0.05, upper=263.85), 95.00) is None
    assert check_price(_band(lower=0.05, upper=263.85), 0.05) is None, "the edge is inside"
    assert check_price(_band(lower=0.05, upper=263.85), 263.85) is None


def test_a_band_that_could_not_be_read_refuses_nothing_and_says_so():
    """His first rule. A band is never invented, so an unknown one blocks nothing.

    The order still rests; the screen carries the reason instead of a number
    nobody read.
    """
    unknown = PriceBand(None, None, None, UNAVAILABLE, reason="FYERS depth timed out")
    assert unknown.known is False
    assert check_price(unknown, 95.0) is None
    assert check_price(unknown, 9999.0) is None
    assert "band not readable from FYERS" in unknown.describe()


def test_an_order_placed_without_a_band_says_so_on_the_screen(store):
    order = _place(band=PriceBand(None, None, None, UNAVAILABLE, reason="depth failed"))
    assert order["band_lower"] is None and order["band_upper"] is None
    assert order["band_source"] == UNAVAILABLE
    assert "without a band check" in book.band_note(order)


# --------------------------------------------------------- modify and cancel


def test_modify_keeps_the_orders_id_and_its_place(store):
    order = _place(limit=95.0)
    changed = book.modify(order["id"], limit_price=97.50, band=_band())
    assert changed["id"] == order["id"], "a new price is not a new order"
    assert float(changed["limit_price"]) == 97.50
    assert changed["status"] == book.RESTING
    assert len(store.rows["swayam_orders"]) == 1


def test_modify_and_cancel_refuse_on_anything_that_stopped_resting(store):
    for status in (book.FILLED, book.EXPIRED, book.CANCELLED, book.FAILED, book.FILLING):
        order = _place()
        store.rows["swayam_orders"][-1]["status"] = status
        with pytest.raises(LookupError):
            book.modify(order["id"], limit_price=99.0)
        with pytest.raises(LookupError):
            book.cancel(order["id"])


def test_cancelling_costs_nothing_and_leaves_the_row_for_him_to_see(store):
    order = _place()
    cancelled = book.cancel(order["id"])
    assert cancelled["status"] == book.CANCELLED
    assert cancelled.get("fill") is None
    assert len(store.rows["swayam_orders"]) == 1, "the line stays on his screen for the day"


# ----------------------------------------------- what the screen is told


def test_the_state_line_says_what_it_waits_for_and_how_far_away_it_is(store):
    order = _place(limit=95.0, leg=_leg(direction="buy"))
    line = book.state_line(order, bid=98.60, ask=98.75)
    assert line["side"] == "ask"
    assert line["waiting_for"] == "waiting for the ask to reach 95.00"
    assert line["book"] == 98.75
    assert line["distance"] == 3.75
    assert line["needs"] == "fall"
    assert line["expires"] == "expires 15:30"


def test_the_state_line_never_invents_a_distance_from_a_price_nobody_published(store):
    order = _place(limit=95.0, leg=_leg(direction="buy"))
    line = book.state_line(order, bid=None, ask=None)
    assert line["book"] is None
    assert line["distance"] is None, "no book, no distance"


def test_a_resting_order_carries_the_phase_it_was_placed_in(store):
    order = _place()
    assert order["provenance"] == "terminal_test"


def test_the_ist_day_of_an_order_is_his_day_not_the_utc_one():
    """Anything after 18:30 IST is a different UTC date. His record is IST."""
    assert book.ist_day("2026-09-10T19:30:00+00:00") == "2026-09-11"
    assert book.ist_day("2026-09-10T08:15:00+00:00") == "2026-09-10"
    assert book.ist_day(None) is None


# ------------------------------- a resting entry actually opening a trade


@pytest.mark.fake_db
@pytest.mark.real_fills
def test_a_resting_entry_opens_a_trade_through_the_path_a_sent_leg_takes(fake_db):
    """The whole point, end to end and offline.

    The watcher does not invent a fill. It calls the SAME execute path the
    ticket calls, which re-reads the book and lets `services/fills.py` decide.
    So the trade that appears has a real fill, real charges from the real
    charge engine, the phase mark of the day, and the order's own execution
    key, which is what makes filling it twice impossible even if everything
    else failed.
    """
    from swayam.services.fills import LegQuote

    order = book.place([book.NewOrder(
        kind=book.ENTRY,
        leg=_leg(direction="sell", strike=23500.0, opt="CE") | {"strategy_name": "Short Call"},
        limit_price=111.0,
        band=_band(),
        provenance="terminal_test",
        group_id=str(uuid.uuid4()),
    )])[0]

    # The bid has come UP to his price, so a sell at 111.00 fills at 112.50,
    # which is better, exactly as an exchange would fill it.
    quote = LegQuote(ltp=112.0, bid=112.50, ask=112.70, spot=23389.25,
                     state="live", market_open=True, as_of=None)

    class _Margin:
        total_inr = 54595.0
        fetched_at = datetime(2026, 9, 10, 9, 56, tzinfo=timezone.utc)
        source = "FYERS span margin"

    class _Capital:
        risk_capital_inr = 971111.0

    with (
        patch("swayam.api.routes.execution.quote_leg", side_effect=lambda **kw: quote),
        patch("swayam.services.fills.quote_leg", side_effect=lambda **kw: quote),
        patch("swayam.api.routes.execution.try_get_margin", return_value=(_Margin(), None)),
        patch("swayam.api.routes.execution.capital_service.get_capital", return_value=_Capital()),
        patch("swayam.api.routes.execution.provenance_for_new_position", return_value="terminal_test"),
        patch.object(order_watcher, "_spot_for", return_value=23389.25),
    ):
        assert order_watcher.fill_now(order) is True

    # ONE trade, from the one leg, at the price the book actually gave.
    positions = fake_db.inserted_into("swayam_positions")
    assert len(positions) == 1
    position = positions[0]
    assert len(position["legs"]) == 1
    leg = position["legs"][0]
    assert leg["entry_premium"] == 112.50, "his price or better, from the book"
    assert leg["side_hit"] == "bid", "a sell receives the bid"
    assert leg["entry_charges_inr"] > 0, "charged by the real engine at the fill"

    # The phase mark of the day, not a guess.
    assert position["provenance"] == "terminal_test"

    # And the order now points at the trade it opened.
    row = [r for r in fake_db.rows["swayam_orders"] if r["id"] == order["id"]][0]
    assert row["status"] == book.FILLED
    assert row["position_id"] == position["id"]
    assert row["result"]["opened_the_trade"] is True
    assert row["fill"]["fill_price"] == 112.50
    assert row["filled_at"] is not None


@pytest.mark.fake_db
@pytest.mark.real_fills
def test_a_resting_fill_carries_the_orders_own_execution_key(fake_db):
    """One order, one key, so a replay cannot open a second trade.

    The key is the order's id, which is the only thing that is unique to this
    fill. The database claim already makes a double-fill impossible; this is
    the second lock on the same door, and it is the one that survives even if
    the row were somehow re-armed.
    """
    from swayam.services.fills import LegQuote

    order = book.place([book.NewOrder(
        kind=book.ENTRY,
        leg=_leg(direction="sell", strike=23500.0, opt="CE"),
        limit_price=111.0,
        band=_band(),
        group_id=str(uuid.uuid4()),
    )])[0]

    quote = LegQuote(ltp=112.0, bid=112.50, ask=112.70, spot=23389.25,
                     state="live", market_open=True, as_of=None)
    seen: list[str] = []

    def _remember(key, payload):
        seen.append(key)

    with (
        patch("swayam.api.routes.execution.quote_leg", side_effect=lambda **kw: quote),
        patch("swayam.services.fills.quote_leg", side_effect=lambda **kw: quote),
        patch("swayam.api.routes.execution.claim_execution", side_effect=_remember),
        patch("swayam.api.routes.execution.complete_execution"),
        patch("swayam.api.routes.execution.try_get_margin", return_value=(None, "not asked")),
        patch("swayam.api.routes.execution.capital_service.get_capital",
              return_value=type("C", (), {"risk_capital_inr": 971111.0})()),
        patch.object(order_watcher, "_spot_for", return_value=23389.25),
    ):
        order_watcher.fill_now(order)

    assert seen == [f"rest-{order['id']}"], "the key is the order's own, once"


@pytest.mark.fake_db
@pytest.mark.real_fills
def test_a_market_that_moved_away_leaves_the_order_resting_and_changes_nothing(fake_db):
    """Between the watcher looking and the fill path re-reading, prices move.

    Nothing happened, so the order goes back to waiting rather than failing.
    This is ordinary, not a fault, and it must never mark an order dead.
    """
    from swayam.services.fills import LegQuote

    order = book.place([book.NewOrder(
        kind=book.ENTRY,
        leg=_leg(direction="sell", strike=23500.0, opt="CE"),
        limit_price=111.0,
        band=_band(),
        group_id=str(uuid.uuid4()),
    )])[0]

    # The bid fell back below his price before the fill path read it.
    gone = LegQuote(ltp=108.0, bid=108.40, ask=108.60, spot=23389.25,
                    state="live", market_open=True, as_of=None)

    with (
        patch("swayam.api.routes.execution.quote_leg", side_effect=lambda **kw: gone),
        patch("swayam.services.fills.quote_leg", side_effect=lambda **kw: gone),
        patch.object(order_watcher, "_spot_for", return_value=23389.25),
    ):
        assert order_watcher.fill_now(order) is False

    assert fake_db.inserted_into("swayam_positions") == [], "nothing was opened"
    row = [r for r in fake_db.rows["swayam_orders"] if r["id"] == order["id"]][0]
    assert row["status"] == book.RESTING, "it goes on waiting"
