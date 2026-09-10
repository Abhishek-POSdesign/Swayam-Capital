"""Exiting ONE leg of a trade that stays open. Build A part one, section 3.3.

A TRADE IS A CAMPAIGN, NOT A LEG. His rule, 2026-09-08: "Every leg that I
square off will have its own profit/loss added, and every new leg I add will be
considered in the same trade. Once I close all the legs or I say 'the trade is
closed', then only the trade is closed."

Until this build the only way out of a four-leg condor was to close all four at
once. These tests hold the four things that must be true instead:

    * one leg out leaves three open and writes NO result row
    * the last leg out writes EXACTLY ONE result row, summing every leg,
      including the ones squared off days earlier
    * a reverse closes one leg and opens its opposite, in one request, leaving
      the same number of legs open
    * a limit the book has not reached refuses, in HIS words, and nothing is
      written

Offline: the database, the quote feed, the broker margin and the vault are all
stood in for. `tests/db_guard.py` and the vault cage stay in force regardless.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from swayam.api import app
from swayam.services.fills import LegQuote

client = TestClient(app)

# conftest stubs `execution._fill_for` so older tests get a fill at the price
# they asked for. This file is ABOUT the fill: a sold leg bought back at the
# ask, and a limit the book has not reached. So it opts out and stands a real
# book in instead, exactly as conftest says to.
pytestmark = pytest.mark.real_fills

EXPIRY = "2026-09-29"

# Shaped like his real open condor 7cd4d017: two wings bought, two bodies sold.
def _leg(seq, direction, strike, opt_type, premium, charges):
    return {
        "sequence": seq,
        "direction": direction,
        "strike": float(strike),
        "option_type": opt_type,
        "quantity_lots": 1,
        "lot_size": 65,
        "entry_premium": float(premium),
        "entry_charges_inr": float(charges),
        "expiry_date": EXPIRY,
        "side_hit": "ask" if direction == "buy" else "bid",
    }


CONDOR_LEGS = [
    _leg(1, "buy", 24200, "CE", 34.50, 24.85),
    _leg(2, "buy", 22800, "PE", 46.40, 25.27),
    _leg(3, "sell", 23800, "CE", 109.15, 37.98),
    _leg(4, "sell", 23200, "PE", 113.55, 38.55),
]

OPEN_CONDOR = {
    "id": "pos-condor-1",
    "strategy_name": "Short Strangle",  # the preset name that stuck. It should not survive.
    "name_source": "structure",
    "underlying": "NIFTY",
    "opened_at": "2026-09-10T08:15:00Z",
    "expiry_date": EXPIRY,
    "net_debit_credit_inr": 9217.0,
    "max_loss_inr": 16783.0,
    "max_profit_inr": 9217.0,
    "breakeven_points": [23058.2, 23941.8],
    "charges_inr": 126.65,
    "spot_at_entry": 23435.05,
    "margin_required_inr": 84929.20,
    "status": "open",
    "mode": "paper",
    "provenance": "live",
    "journal_path": "02 - Projects/Trading/04 - Journal/2026-09-10-trade01.md",
    "legs": CONDOR_LEGS,
}

# The book at the 15:26 close of 10 September, from the recorder.
BOOK = {
    (24200.0, "CE"): {"bid": 30.60, "ask": 30.75, "ltp": 34.45},
    (22800.0, "PE"): {"bid": 47.30, "ask": 47.40, "ltp": 46.10},
    (23800.0, "CE"): {"bid": 98.60, "ask": 98.75, "ltp": 109.40},
    (23200.0, "PE"): {"bid": 118.20, "ask": 118.55, "ltp": 113.60},
}


class FakeTable:
    def __init__(self, store, name):
        self._store = store
        self._name = name
        self._filters: list[tuple[str, Any]] = []

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def in_(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def insert(self, record):
        self._store.inserts.setdefault(self._name, []).append(record)
        return self

    def update(self, values):
        self._store.updates.setdefault(self._name, []).append(values)
        if self._name == "swayam_positions":
            self._store.position.update(values)
        return self

    def execute(self):
        class R:
            pass

        r = R()
        r.data = self._store.rows_for(self._name)
        return r


class FakeStore:
    def __init__(self, position: Optional[dict[str, Any]] = None, prior_result: bool = False):
        self.inserts: dict[str, list] = {}
        self.updates: dict[str, list] = {}
        self.position = dict(position or OPEN_CONDOR)
        self.position["legs"] = [dict(l) for l in self.position["legs"]]
        self.prior_result = prior_result

    def rows_for(self, table):
        if table == "swayam_positions":
            return [self.position]
        if table == "swayam_trade_history":
            return [{"id": "hist-1"}] if self.prior_result else []
        return []

    @property
    def client(self):
        store = self

        class C:
            def table(self, name):
                return FakeTable(store, name)

        return C()

    url = "https://example.invalid"
    key = "anon"

    # ------------------------------------------------------------- readers
    @property
    def legs(self):
        return self.position["legs"]

    def open_legs(self):
        return [l for l in self.legs if str(l.get("status") or "open") != "closed"]

    def closed_legs(self):
        return [l for l in self.legs if l.get("status") == "closed"]

    @property
    def results(self):
        return self.inserts.get("swayam_trade_history", [])


def fake_quote(*, strike, expiry, option_type, underlying="NIFTY", market_open=True):
    q = BOOK[(float(strike), option_type.upper())]
    return LegQuote(
        ltp=q["ltp"],
        bid=q["bid"],
        ask=q["ask"],
        spot=23389.25,
        state="live" if market_open else "closing",
        market_open=market_open,
        as_of="2026-09-10T09:56:00Z",
    )


def shut_quote(**kwargs):
    return fake_quote(**kwargs, market_open=False)


class _Margin:
    total_inr = 54595.0
    fetched_at = datetime(2026, 9, 10, 9, 56, tzinfo=timezone.utc)
    source = "FYERS span margin"


def _post(store, path, body, *, quote=fake_quote):
    """One request, with the market, the broker and the vault stood in for."""
    with (
        patch("swayam.api.routes.execution.db", store),
        patch("swayam.api.routes.positions.db", store),
        patch("swayam.api.routes.execution.quote_leg", side_effect=quote),
        patch("swayam.services.fills.quote_leg", side_effect=quote),
        patch("swayam.api.routes.execution.try_get_margin", return_value=(_Margin(), None)),
        # Exit everything reads the whole chain rather than quoting leg by leg.
        # The same book, so the two paths are comparable.
        patch("swayam.api.routes.positions._get_cached_option_chain", return_value={}),
        patch("swayam.api.routes.positions._build_chain_lookup", return_value=(23389.25, BOOK)),
        patch("swayam.api.routes.positions._market_is_open_now", return_value=(quote is fake_quote)),
        patch("swayam.api.routes.execution.append_leg_exit_block") as note,
        patch("swayam.api.routes.positions.append_exit_block") as exit_note,
        # The outbox and journal_status are the LIVE database. Nothing in this
        # file may reach them, whatever else it does.
        patch("swayam.api.routes.execution.queue_journal_note", return_value=True),
        patch("swayam.api.routes.execution.mark_journal_status"),
        patch("swayam.api.routes.positions.queue_journal_note", return_value=True),
        patch("swayam.api.routes.positions.mark_journal_status"),
    ):
        resp = client.post(path, json=body)
    return resp, note, exit_note


# --------------------------------------------------------------- one leg out


def test_exiting_one_leg_of_four_leaves_three_open_and_no_result_row():
    """The trade is NOT closed. Only a squared-off TRADE enters the record."""
    store = FakeStore()
    resp, note, _ = _post(store, "/api/positions/pos-condor-1/legs/3/exit", {"order_type": "MARKET"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["last_leg"] is False
    assert body["legs_open"] == 3
    assert body["legs_closed"] == 1

    assert len(store.open_legs()) == 3
    assert len(store.closed_legs()) == 1
    assert store.results == [], "a trade with three legs still open must not enter the record"

    # A sold leg is bought back at the ASK. 109.15 in, 98.75 out, on 65 units.
    gone = store.closed_legs()[0]
    assert gone["exit_side_hit"] == "ask"
    assert gone["exit_premium"] == pytest.approx(98.75)
    assert gone["gross_pnl_inr"] == pytest.approx((109.15 - 98.75) * 65, abs=0.01)
    assert gone["exit_charges_inr"] > 0
    assert gone["net_pnl_inr"] == pytest.approx(
        gone["gross_pnl_inr"] - gone["entry_charges_inr"] - gone["exit_charges_inr"], abs=0.01
    )
    # The note is an ADJUSTMENT, never an Exit block: the trade is still open.
    note.assert_called_once()


def test_the_name_follows_the_legs_that_are_left():
    """His condor was stored as "Short Strangle" because a preset named it.

    Take the two bought wings off and what remains genuinely IS a short
    strangle. Take one leg off a condor and it is a custom three-leg trade,
    which is what the card must say.
    """
    store = FakeStore()
    resp, _, _ = _post(store, "/api/positions/pos-condor-1/legs/1/exit", {"order_type": "MARKET"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["strategy_name"] == "Custom, 3 legs"
    assert store.position["strategy_name"] == "Custom, 3 legs"


def test_a_name_he_typed_is_never_overwritten_by_an_exit():
    store = FakeStore({**OPEN_CONDOR, "name_source": "his", "strategy_name": "September income"})
    resp, _, _ = _post(store, "/api/positions/pos-condor-1/legs/1/exit", {"order_type": "MARKET"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["strategy_name"] == "September income"


def test_a_leg_already_closed_cannot_be_closed_again():
    """One click, one exit. A stale browser must not double-book a leg."""
    store = FakeStore()
    first, _, _ = _post(store, "/api/positions/pos-condor-1/legs/3/exit", {"order_type": "MARKET"})
    assert first.status_code == 200

    second, _, _ = _post(store, "/api/positions/pos-condor-1/legs/3/exit", {"order_type": "MARKET"})
    assert second.status_code == 409
    assert "already closed" in second.text
    assert len(store.closed_legs()) == 1


def test_a_leg_that_does_not_exist_says_so():
    store = FakeStore()
    resp, _, _ = _post(store, "/api/positions/pos-condor-1/legs/9/exit", {"order_type": "MARKET"})
    assert resp.status_code == 404


# --------------------------------------------------------------- the last leg


def test_the_last_leg_out_writes_exactly_one_result_equal_to_the_sum():
    """His rule: the trade closes when the last leg closes, and only then."""
    store = FakeStore()
    for sequence in (1, 2, 3):
        resp, _, _ = _post(store, f"/api/positions/pos-condor-1/legs/{sequence}/exit", {"order_type": "MARKET"})
        assert resp.status_code == 200, resp.text
        assert store.results == [], f"the record must stay empty while leg {sequence} was not the last"

    final, _, _ = _post(store, "/api/positions/pos-condor-1/legs/4/exit", {"order_type": "MARKET"})
    assert final.status_code == 200, final.text
    assert final.json()["last_leg"] is True

    assert len(store.results) == 1, "one trade, one result row"
    result = store.results[0]

    legs = store.closed_legs()
    assert len(legs) == 4
    expected_net = sum(l["net_pnl_inr"] for l in legs)
    assert result["realized_pnl_inr"] == pytest.approx(expected_net, abs=0.05)
    assert result["total_charges_inr"] == pytest.approx(
        sum(l["entry_charges_inr"] + l["exit_charges_inr"] for l in legs), abs=0.05
    )
    assert store.position["status"] == "closed"


def test_closing_the_whole_trade_after_a_leg_went_counts_that_leg_once():
    """Exit one leg, then Exit everything. The leg that already went keeps its
    own figures and is not re-marked against today's book."""
    store = FakeStore()
    first, _, _ = _post(store, "/api/positions/pos-condor-1/legs/3/exit", {"order_type": "MARKET"})
    assert first.status_code == 200
    booked = store.closed_legs()[0]["net_pnl_inr"]

    rest, _, _ = _post(store, "/api/positions/pos-condor-1/close", {"close_reason": "manual"})
    assert rest.status_code == 200, rest.text

    assert len(store.results) == 1
    result = store.results[0]
    assert len(result["exit_legs"]) == 4
    matching = [
        l for l in result["exit_legs"]
        if l["strike"] == 23800.0 and l["option_type"] == "CE"
    ]
    assert len(matching) == 1
    assert matching[0]["net_pnl_inr"] == pytest.approx(booked, abs=0.01)
    assert result["realized_pnl_inr"] == pytest.approx(
        sum(l["net_pnl_inr"] for l in result["exit_legs"]), abs=0.05
    )


# ----------------------------------------------------------------- reverse


def test_a_reverse_closes_one_leg_and_opens_its_opposite():
    """One decision, one press: two fills, two charge lines, one key.

    The number of OPEN legs does not change, because one went and one arrived.
    """
    store = FakeStore()
    resp, note, _ = _post(store, "/api/positions/pos-condor-1/legs/3/reverse", {"order_type": "MARKET"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "leg_reversed"
    assert body["legs_open"] == 4, "one closed, one opened: still four running"
    assert len(store.legs) == 5
    assert len(store.closed_legs()) == 1

    opened = [l for l in store.open_legs() if l.get("reversed_from_sequence") == 3]
    assert len(opened) == 1
    # The sold call is bought back at the ask, and the new leg is BOUGHT, so
    # it too pays the ask.
    assert opened[0]["direction"] == "buy"
    assert opened[0]["entry_premium"] == pytest.approx(98.75)
    assert opened[0]["entry_charges_inr"] > 0
    assert store.results == []
    note.assert_called_once()
    assert note.call_args.kwargs["opened_leg"] is not None


# ------------------------------------------------------- his price, not a rule


def test_a_limit_the_book_has_not_reached_refuses_in_his_words():
    """The wording is fixed, because a price and a rule must never read alike.

    On 2026-09-10 his limit price was refused beside red "Unlimited" rule
    tiles and it read like the hedge rule had blocked him. It had not.
    """
    store = FakeStore()
    # Buying back the sold 23,800 call needs the ASK, which is 98.75. Bidding
    # 95.00 for it will not fill today.
    resp, note, _ = _post(
        store,
        "/api/positions/pos-condor-1/legs/3/exit",
        {"order_type": "LIMIT", "limit_price": 95.0},
    )

    assert resp.status_code == 422, resp.text
    reason = resp.json()["detail"]["refused_legs"][0]["reason"]
    assert reason.startswith("Your price, not a rule:")
    assert "the ask is 98.75" in reason
    assert "Resting orders arrive in the next build" in reason
    assert "move the price or switch to market" in reason
    assert "rule" not in reason.replace("not a rule", ""), "a price refusal must not cite a rule"

    # NOTHING was written. The leg is still open and the note was not touched.
    assert len(store.open_legs()) == 4
    assert store.results == []
    note.assert_not_called()


def test_a_limit_through_the_book_fills_at_the_book_and_better():
    """A limit fills at his price OR BETTER, as the exchange does."""
    store = FakeStore()
    resp, _, _ = _post(
        store,
        "/api/positions/pos-condor-1/legs/3/exit",
        {"order_type": "LIMIT", "limit_price": 105.0},
    )
    assert resp.status_code == 200, resp.text
    gone = store.closed_legs()[0]
    assert gone["exit_premium"] == pytest.approx(98.75), "he paid the ask, which is better than 105"
    assert gone["exit_limit_price"] == pytest.approx(105.0)


# ------------------------------------------------------------- after the bell


def test_after_the_bell_an_exit_refuses_and_says_what_to_do():
    """A fill against the closing book is one nobody could have got."""
    store = FakeStore()
    resp, note, _ = _post(
        store, "/api/positions/pos-condor-1/legs/3/exit", {"order_type": "MARKET"}, quote=shut_quote
    )

    assert resp.status_code == 422, resp.text
    reason = resp.json()["detail"]["refused_legs"][0]["reason"]
    assert "market is closed" in reason
    assert "your price" not in reason.lower(), "a shut market is not his price"
    assert "window" in reason, "a refusal must say what he can DO"
    assert len(store.open_legs()) == 4
    note.assert_not_called()


def test_after_the_bell_a_reverse_refuses_too():
    store = FakeStore()
    resp, note, _ = _post(
        store, "/api/positions/pos-condor-1/legs/3/reverse", {"order_type": "MARKET"}, quote=shut_quote
    )
    assert resp.status_code == 422, resp.text
    assert len(store.open_legs()) == 4
    assert len(store.legs) == 4, "nothing was opened either"
    note.assert_not_called()


def test_a_closed_trade_cannot_have_a_leg_exited():
    store = FakeStore({**OPEN_CONDOR, "status": "closed"})
    resp, _, _ = _post(store, "/api/positions/pos-condor-1/legs/3/exit", {"order_type": "MARKET"})
    assert resp.status_code == 400
    assert "closed" in resp.text


# ------------------------------------------------------------------ the note


def test_a_note_that_cannot_be_written_does_not_fail_the_exit():
    """A NOTE IS NOT A TRADE, at both ends. It goes to the outbox instead."""
    store = FakeStore()
    with (
        patch("swayam.api.routes.execution.db", store),
        patch("swayam.api.routes.positions.db", store),
        patch("swayam.api.routes.execution.quote_leg", side_effect=fake_quote),
        patch("swayam.services.fills.quote_leg", side_effect=fake_quote),
        patch("swayam.api.routes.execution.try_get_margin", return_value=(_Margin(), None)),
        patch(
            "swayam.api.routes.execution.append_leg_exit_block",
            side_effect=OSError("vault unreachable from this container"),
        ),
        patch("swayam.api.routes.execution.queue_journal_note", return_value=True) as queued,
        patch("swayam.api.routes.execution.mark_journal_status"),
    ):
        resp = client.post("/api/positions/pos-condor-1/legs/3/exit", json={"order_type": "MARKET"})

    assert resp.status_code == 200, resp.text
    assert resp.json()["journal_status"] == "pending"
    assert len(store.closed_legs()) == 1, "the leg is still squared off in the database"
    queued.assert_called_once()
    assert queued.call_args.kwargs["kind"] == "leg_exit"
