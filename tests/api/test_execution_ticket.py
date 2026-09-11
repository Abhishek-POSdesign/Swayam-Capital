"""
The execution ticket, docs/PLAN.md 2.12 PR 1, proved rather than described.

  * A leg is filled against the SERVER'S quote: market at the quote, limit only
    if the market is at or through it, no quote no fill.
  * His order is his when he says so; buys first otherwise.
  * The spot at entry and the broker margin are stored on the row.
  * A leg can be added to an open trade, and the trade keeps its identity.
  * The note records when the TRADE opened, not when the note was written.

Everything runs against the in-memory database and a temporary vault.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from swayam.api import app
from swayam.services.fills import FillRefused, LegQuote, resolve_fill
from swayam.services.margin import MarginQuote

client = TestClient(app)

EXPIRY = "2026-09-24"


def _leg(direction, strike, opt, premium, **extra):
    body = {
        "strike": float(strike), "option_type": opt, "direction": direction,
        "quantity_lots": 1, "entry_premium": float(premium), "expiry_date": EXPIRY,
    }
    body.update(extra)
    return body


def _condor(**overrides):
    body = {
        "strategy_name": "Iron Condor",
        "underlying": "NIFTY",
        "current_spot": 23635.10,
        "mode": "paper",
        "legs": [
            _leg("sell", 23700, "CE", 185.00),
            _leg("sell", 23300, "PE", 122.25),
            _leg("buy", 24000, "CE", 82.20),
            _leg("buy", 23000, "PE", 62.80),
        ],
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------- the fill rule

def _quote(ltp=100.0, bid=99.5, ask=100.5, state="live", open_=True):
    return LegQuote(ltp=ltp, bid=bid, ask=ask, spot=23635.1, state=state, market_open=open_, as_of=None)


def _band(lower=0.05, upper=1000.0, tick=0.05):
    """A band the way the FYERS depth call reports one. Build B."""
    from swayam.services.price_band import FYERS_DEPTH, PriceBand

    return PriceBand(lower=lower, upper=upper, tick=tick, source=FYERS_DEPTH, symbol="NSE:TEST")


def test_a_market_buy_pays_the_ask_and_a_market_sell_gets_the_bid():
    buy = resolve_fill(direction="buy", order_type="MARKET", limit_price=None, quote=_quote(), leg_label="BUY 24,000 CE")
    assert buy.price == 100.5 and buy.side_hit == "ask"
    assert buy.basis == "bid_ask"
    assert buy.ltp_at_fill == 100.0, "the traded price is kept so the record can show the spread cost"
    sell = resolve_fill(direction="sell", order_type="MARKET", limit_price=None, quote=_quote(), leg_label="SELL 23,700 CE")
    assert sell.price == 99.5 and sell.side_hit == "bid"


def test_the_spread_cost_is_what_crossing_the_book_cost_against_the_trade():
    from swayam.services.fills import spread_cost_inr
    assert spread_cost_inr("buy", 100.5, 100.0, 65) == -32.5
    assert spread_cost_inr("sell", 99.5, 100.0, 65) == -32.5
    assert spread_cost_inr("buy", 100.5, None, 65) is None


def test_a_limit_away_from_the_market_does_not_fill_and_says_where_the_market_is():
    with pytest.raises(FillRefused) as exc:
        resolve_fill(direction="buy", order_type="LIMIT", limit_price=95.0, quote=_quote(), leg_label="BUY 24,000 CE")
    assert "would not fill now" in str(exc.value)
    assert "ask is 100.50" in str(exc.value)
    assert "Nothing was sent" in str(exc.value)


def test_a_limit_through_the_market_fills_at_his_price_or_better_as_the_exchange_does():
    """His correction, 2026-09-09 evening: a limit executes at my limit or better."""
    sell = resolve_fill(direction="sell", order_type="LIMIT", limit_price=98.0, quote=_quote(), leg_label="SELL 23,700 CE")
    assert sell.price == 99.5, "a sell limit below the bid receives the bid"
    assert sell.limit_price == 98.0
    assert "better" in sell.how
    buy = resolve_fill(direction="buy", order_type="LIMIT", limit_price=100.5, quote=_quote(), leg_label="BUY 24,000 CE")
    assert buy.price == 100.5 and "better" not in buy.how


def test_a_missing_side_of_the_book_refuses_that_side_only():
    with pytest.raises(FillRefused) as exc:
        resolve_fill(direction="buy", order_type="MARKET", limit_price=None,
                     quote=_quote(ask=None), leg_label="BUY 24,000 CE")
    assert "the ask is not published" in str(exc.value)
    sell = resolve_fill(direction="sell", order_type="MARKET", limit_price=None, quote=_quote(ask=None), leg_label="SELL 24,000 CE")
    assert sell.price == 99.5


def test_a_closing_price_is_not_a_fill():
    with pytest.raises(FillRefused) as exc:
        resolve_fill(direction="buy", order_type="MARKET", limit_price=None,
                     quote=_quote(state="closing", open_=False), leg_label="BUY 24,000 CE")
    assert "market is closed" in str(exc.value)


def test_no_quote_means_no_fill():
    with pytest.raises(FillRefused) as exc:
        resolve_fill(direction="buy", order_type="MARKET", limit_price=None,
                     quote=LegQuote(None, None, None, None, "unavailable", True, None, note="chain unreadable"),
                     leg_label="BUY 24,000 CE")
    assert "no live bid or ask" in str(exc.value)


def test_a_limit_order_with_no_price_is_refused_with_what_to_do():
    with pytest.raises(FillRefused) as exc:
        resolve_fill(direction="buy", order_type="LIMIT", limit_price=None, quote=_quote(), leg_label="BUY 24,000 CE")
    assert "Reset" in str(exc.value)


# ---------------------------------------------------------------- the route

@pytest.mark.fake_db
def test_his_order_is_kept_when_he_chooses_it(fake_db):
    res = client.post("/api/execute/multi-leg", json=_condor(leg_order="as_sent"))
    assert res.status_code == 200, res.text
    stored = fake_db.inserted_into("swayam_positions")[0]["legs"]
    assert [l["direction"] for l in stored] == ["sell", "sell", "buy", "buy"]
    assert [l["sequence"] for l in stored] == [1, 2, 3, 4]
    fills = res.json()["fills"]
    assert [f["sequence"] for f in fills] == [1, 2, 3, 4]
    assert fills[0]["direction"] == "SELL"


@pytest.mark.fake_db
def test_buys_go_first_by_default(fake_db):
    res = client.post("/api/execute/multi-leg", json=_condor())
    assert res.status_code == 200, res.text
    stored = fake_db.inserted_into("swayam_positions")[0]["legs"]
    assert [l["direction"] for l in stored] == ["buy", "buy", "sell", "sell"]


@pytest.mark.fake_db
def test_the_row_records_the_spot_and_how_each_leg_was_filled(fake_db):
    res = client.post("/api/execute/multi-leg", json=_condor(leg_order="as_sent"))
    assert res.status_code == 200, res.text
    row = fake_db.inserted_into("swayam_positions")[0]
    # Never stored before this. The note printed a spot of 0 on every trade.
    assert row["spot_at_entry"] == 23635.10
    assert row["fill_basis"] == "bid_ask"
    for leg in row["legs"]:
        assert leg["order_type"] == "MARKET"
        assert leg["fill_basis"] == "bid_ask"
        assert leg["spread_cost_inr"] == 0.0, "the test market has no spread"
        assert leg["ltp_at_fill"] == leg["entry_premium"]
        assert leg["filled_at"]
        assert leg["entry_charges_inr"] > 0
    assert res.json()["spot_at_entry"] == 23635.10


@pytest.mark.fake_db
def test_the_brokers_margin_is_stored_so_rule_4_can_be_tested(fake_db):
    quote = MarginQuote(total_inr=71204.0, new_order_inr=71204.0, available_inr=500000.0,
                        fetched_at=datetime(2026, 9, 9, 8, 36, tzinfo=timezone.utc))
    with patch("swayam.api.routes.execution.try_get_margin", return_value=(quote, None)):
        res = client.post("/api/execute/multi-leg", json=_condor())
    assert res.status_code == 200, res.text
    row = fake_db.inserted_into("swayam_positions")[0]
    assert row["margin_required_inr"] == 71204.0
    assert row["margin_source"] == "FYERS multiorder/margin"
    assert row["margin_quoted_at"].startswith("2026-09-09T08:36")
    assert res.json()["margin_required_inr"] == 71204.0


@pytest.mark.fake_db
def test_an_unavailable_margin_is_stored_as_unavailable_and_the_trade_still_happens(fake_db):
    with patch("swayam.api.routes.execution.try_get_margin", return_value=(None, "FYERS refused: request limit reached")):
        res = client.post("/api/execute/multi-leg", json=_condor())
    assert res.status_code == 200, res.text
    row = fake_db.inserted_into("swayam_positions")[0]
    assert row["margin_required_inr"] is None
    assert "unavailable" in row["margin_source"]


@pytest.mark.fake_db
@pytest.mark.real_fills
def test_a_market_leg_is_filled_at_the_servers_price_even_if_the_browser_sent_another(fake_db):
    def quote_leg(**kw):
        return _quote(ltp=100.0)
    with patch("swayam.api.routes.execution.quote_leg", side_effect=quote_leg):
        body = _condor(legs=[_leg("buy", 23800, "PE", 120.0), _leg("sell", 23600, "PE", 60.0)])
        res = client.post("/api/execute/multi-leg", json=body)
    assert res.status_code == 200, res.text
    legs = fake_db.inserted_into("swayam_positions")[0]["legs"]
    by_dir = {l["direction"]: l for l in legs}
    assert by_dir["buy"]["entry_premium"] == 100.5, "a buy pays the ask, whatever the browser remembered"
    assert by_dir["sell"]["entry_premium"] == 99.5, "a sell gets the bid"
    assert by_dir["buy"]["spread_cost_inr"] == -32.5 and by_dir["sell"]["spread_cost_inr"] == -32.5
    assert res.json()["spread_cost_inr"] == -65.0


@pytest.mark.fake_db
@pytest.mark.real_fills
def test_a_limit_away_from_the_book_rests_and_the_rest_of_the_ticket_fills(fake_db):
    """BUILD B replaced this test's original meaning, on purpose.

    It used to assert that one limit the book had not reached refused the
    WHOLE ticket. That refusal cost him his strangle on 10 September and is
    the fault Build B exists to remove. What must be true now is: the legs
    that can fill DO, the ones that cannot become open orders on the trade
    those fills opened, and one press is still one trade.
    """
    with patch("swayam.api.routes.execution.quote_leg", side_effect=lambda **kw: _quote(ltp=100.0)), \
         patch("swayam.api.routes.execution.band_for_leg", side_effect=lambda **kw: _band()), \
         patch("swayam.services.orders.session_is_over", return_value=False):
        body = _condor(legs=[
            _leg("buy", 23800, "PE", 120.0, order_type="LIMIT", limit_price=95.0),   # away from the market
            _leg("sell", 23600, "PE", 60.0, order_type="LIMIT", limit_price=110.0),  # away the other way
            _leg("buy", 23900, "PE", 100.0),                                          # fills now
        ], leg_order="as_sent")
        res = client.post("/api/execute/multi-leg", json=body)

    assert res.status_code == 200, res.text
    body = res.json()

    # One trade, opened by the one leg that could fill.
    positions = fake_db.inserted_into("swayam_positions")
    assert len(positions) == 1
    assert len(positions[0]["legs"]) == 1, "only the leg that filled is on the trade"
    assert len(body["fills"]) == 1

    # And two orders waiting, on that same trade.
    orders = fake_db.inserted_into("swayam_orders")
    assert len(orders) == 2
    assert {o["kind"] for o in orders} == {"add_leg"}
    assert {o["position_id"] for o in orders} == {positions[0]["id"]}
    assert {float(o["limit_price"]) for o in orders} == {95.0, 110.0}
    assert all(o["status"] == "resting" for o in orders)
    assert body["resting_count"] == 2
    assert {r["leg"] for r in body["resting"]} == {"BUY 23,800 PE", "SELL 23,600 PE"}
    assert "rest" in body["message"].lower()


@pytest.mark.fake_db
@pytest.mark.real_fills
def test_when_no_leg_can_fill_every_leg_rests_and_no_trade_is_opened(fake_db):
    """His words: it must sit in the system until the bid and ask reach it.

    Nothing is opened, nothing is charged, and the first order to fill is what
    opens the trade. The siblings share a group so they can find it.
    """
    with patch("swayam.api.routes.execution.quote_leg", side_effect=lambda **kw: _quote(ltp=100.0)), \
         patch("swayam.api.routes.execution.band_for_leg", side_effect=lambda **kw: _band()), \
         patch("swayam.services.orders.session_is_over", return_value=False):
        body = _condor(legs=[
            _leg("buy", 23800, "PE", 120.0, order_type="LIMIT", limit_price=95.0),
            _leg("sell", 23600, "PE", 60.0, order_type="LIMIT", limit_price=110.0),
        ], leg_order="as_sent")
        res = client.post("/api/execute/multi-leg", json=body)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["position_id"] is None
    assert body["status"] == "resting"
    assert body["fills"] == []
    assert fake_db.inserted_into("swayam_positions") == [], "no trade until something fills"

    orders = fake_db.inserted_into("swayam_orders")
    assert len(orders) == 2
    assert {o["kind"] for o in orders} == {"entry"}
    assert all(o["position_id"] is None for o in orders)
    assert len({o["group_id"] for o in orders}) == 1, "one press, one group"


@pytest.mark.fake_db
@pytest.mark.real_fills
def test_after_the_bell_nothing_rests_and_he_is_told_to_use_his_window(fake_db):
    """His instruction of 2026-09-10: refuse after 15:30, exactly as the close does.

    An order placed after the bell would expire the same second, so accepting
    it would be a lie of omission.
    """
    with patch("swayam.api.routes.execution.quote_leg", side_effect=lambda **kw: _quote(ltp=100.0)), \
         patch("swayam.api.routes.execution.band_for_leg", side_effect=lambda **kw: _band()), \
         patch("swayam.services.orders.session_is_over", return_value=True):
        body = _condor(legs=[
            _leg("buy", 23800, "PE", 120.0, order_type="LIMIT", limit_price=95.0),
        ])
        res = client.post("/api/execute/multi-leg", json=body)

    assert res.status_code == 422, res.text
    detail = res.json()["detail"]
    assert "nothing is resting" in detail["error"].lower()
    assert "window" in detail["refused_legs"][0]["reason"].lower()
    assert fake_db.inserted_into("swayam_positions") == []
    assert fake_db.inserted_into("swayam_orders") == []


@pytest.mark.fake_db
@pytest.mark.real_fills
def test_a_price_outside_the_exchange_band_rests_nothing_and_names_the_band(fake_db):
    """The band is the exchange's, read from the FYERS depth call at placement."""
    with patch("swayam.api.routes.execution.quote_leg", side_effect=lambda **kw: _quote(ltp=100.0)), \
         patch("swayam.api.routes.execution.band_for_leg",
               side_effect=lambda **kw: _band(lower=0.05, upper=200.0)), \
         patch("swayam.services.orders.session_is_over", return_value=False):
        body = _condor(legs=[
            _leg("buy", 23800, "PE", 120.0, order_type="LIMIT", limit_price=0.02),
        ])
        res = client.post("/api/execute/multi-leg", json=body)

    assert res.status_code == 422, res.text
    detail = res.json()["detail"]
    assert "outside" in detail["refused_legs"][0]["reason"]
    assert "200.00" in detail["refused_legs"][0]["reason"], "the band is named"
    assert fake_db.inserted_into("swayam_orders") == []


@pytest.mark.fake_db
@pytest.mark.real_fills
def test_after_the_close_nothing_fills(fake_db):
    with patch("swayam.api.routes.execution.quote_leg", side_effect=lambda **kw: _quote(state="closing", open_=False)):
        res = client.post("/api/execute/multi-leg", json=_condor())
    assert res.status_code == 422
    assert "market is closed" in res.json()["detail"]["refused_legs"][0]["reason"]
    assert fake_db.inserted_into("swayam_positions") == []


# ---------------------------------------------------------------- one by one

def _open_position(position_id="11111111-1111-1111-1111-111111111111"):
    return {
        "id": position_id,
        "strategy_name": "Iron Condor",
        "underlying": "NIFTY",
        "expiry_date": EXPIRY,
        "legs": [
            {
                "strike": 24000.0, "option_type": "CE", "direction": "buy", "quantity_lots": 1,
                "entry_premium": 82.20, "expiry_date": EXPIRY, "lot_size": 65, "sequence": 1,
                "entry_charges_inr": 26.58, "order_type": "MARKET",
            }
        ],
        "net_debit_credit_inr": -5343.0,
        "max_loss_inr": 5343.0,
        "max_profit_inr": 0.0,
        "breakeven_points": [24082.2],
        "risk_at_entry_inr": 5343.0,
        "status": "open",
        "mode": "paper",
        "opened_at": "2026-09-09T08:37:12+00:00",
        "charges_inr": 26.58,
        "journal_path": None,
        "journal_status": "pending",
    }


@pytest.mark.fake_db(seed={"swayam_positions": [_open_position()]})
def test_a_leg_added_one_by_one_joins_the_same_trade(fake_db):
    pid = _open_position()["id"]
    res = client.post(f"/api/positions/{pid}/legs", json={
        "leg": _leg("sell", 23700, "CE", 185.0), "current_spot": 23635.1,
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "leg_added"
    assert data["legs_count"] == 2
    assert data["fill"]["sequence"] == 2
    assert data["fill"]["fill_price"] == 185.0

    row = next(r for r in fake_db.rows["swayam_positions"] if r["id"] == pid)
    assert len(row["legs"]) == 2
    assert row["legs"][1]["sequence"] == 2
    assert row["legs"][1]["lot_size"] == 65
    # The structure is what he now holds: a bull call spread, credit net of the debit.
    assert row["net_debit_credit_inr"] == pytest.approx((185.0 - 82.20) * 65, abs=0.01)
    assert row["max_loss_inr"] > 0
    # Charges accumulate per leg, as he asked.
    assert row["charges_inr"] == pytest.approx(26.58 + row["legs"][1]["entry_charges_inr"], abs=0.01)
    # No note yet, so the adjustment is queued, never lost.
    queued = fake_db.inserted_into("swayam_journal_outbox")
    assert len(queued) == 1 and queued[0]["kind"] == "add_leg"
    assert fake_db.inserted_into("swayam_positions") == [], "no second position was opened"


@pytest.mark.fake_db(seed={"swayam_positions": [dict(_open_position(), status="closed")]})
def test_a_leg_cannot_be_added_to_a_closed_trade(fake_db):
    pid = _open_position()["id"]
    res = client.post(f"/api/positions/{pid}/legs", json={"leg": _leg("sell", 23700, "CE", 185.0), "current_spot": 23635.1})
    assert res.status_code == 400
    assert "new trade" in res.json()["detail"]


@pytest.mark.fake_db(seed={"swayam_positions": [_open_position()]})
def test_the_same_add_leg_key_twice_adds_exactly_one_leg(fake_db):
    pid = _open_position()["id"]
    body = {"leg": _leg("sell", 23700, "CE", 185.0), "current_spot": 23635.1, "idempotency_key": "leg-2-key"}
    first = client.post(f"/api/positions/{pid}/legs", json=body)
    second = client.post(f"/api/positions/{pid}/legs", json=body)
    assert first.status_code == 200 and second.status_code == 200
    assert second.json() == first.json()
    row = next(r for r in fake_db.rows["swayam_positions"] if r["id"] == pid)
    assert len(row["legs"]) == 2


# ---------------------------------------------------------------- the note

def test_the_note_records_when_the_trade_opened_not_when_the_note_was_written(tmp_path):
    from swayam.api.journal_writer import write_new_trade_journal
    rel = write_new_trade_journal(
        position_id="abc",
        spread_data={"strategy_name": "Iron Condor", "underlying": "NIFTY", "legs": [
            {"strike": 24000, "option_type": "CE", "direction": "buy", "quantity_lots": 1,
             "entry_premium": 82.45, "entry_charges_inr": 26.58, "order_type": "MARKET", "ltp_at_fill": 82.20},
        ], "payoff_curve": {"max_loss_inr": 5343, "max_profit_inr": 0, "rr_implied": 0, "net_debit_credit_inr": -5343,
                             "breakevens": [24082]}, "greeks": {}, "margin_required_inr": 71204.0,
           "fill_basis": "traded_price"},
        validation_data={"checks": []},
        current_spot=23635.1,
        margin_base_inr=971111.0,
        vault_path=tmp_path,
        opened_at="2026-09-09T08:37:12+00:00",
    )
    text = (tmp_path / rel).read_text(encoding="utf-8")
    assert "**Time opened**: 2026-09-09 14:07:12 IST" in text
    assert "**Margin the broker needed**: ₹71,204" in text
    assert "at the traded price. Not comparable" in text
    assert "| Order | Fill | Traded | Charges |" in text
    assert "| market | ₹82.45 | ₹82.20 | ₹26.58 |" in text


def test_a_percentage_of_an_unread_balance_is_unavailable_not_zero(tmp_path):
    from swayam.api.journal_writer import write_new_trade_journal
    rel = write_new_trade_journal(
        position_id="abc",
        spread_data={"strategy_name": "X", "underlying": "NIFTY", "legs": [
            {"strike": 24000, "option_type": "CE", "direction": "buy", "quantity_lots": 1, "entry_premium": 82.45},
        ], "payoff_curve": {"max_loss_inr": 6945, "max_profit_inr": 0, "rr_implied": 0, "net_debit_credit_inr": -6945,
                             "breakevens": []}, "greeks": {}},
        validation_data={"checks": []}, current_spot=0.0, margin_base_inr=0.0, vault_path=tmp_path,
    )
    text = (tmp_path / rel).read_text(encoding="utf-8")
    assert "0.00% of margin base" not in text
    assert "unavailable" in text


def test_an_added_leg_lands_under_adjustments_before_the_exit(tmp_path):
    from swayam.api.journal_writer import append_leg_block, write_new_trade_journal
    rel = write_new_trade_journal(
        position_id="abc",
        spread_data={"strategy_name": "Iron Condor", "underlying": "NIFTY", "legs": [
            {"strike": 24000, "option_type": "CE", "direction": "buy", "quantity_lots": 1, "entry_premium": 82.45,
             "order_type": "MARKET"},
        ], "payoff_curve": {"max_loss_inr": 5343, "max_profit_inr": 0, "rr_implied": 0, "net_debit_credit_inr": -5343,
                             "breakevens": []}, "greeks": {}},
        validation_data={"checks": []}, current_spot=23635.1, margin_base_inr=971111.0, vault_path=tmp_path,
        opened_at="2026-09-09T08:37:12+00:00",
    )
    append_leg_block(
        journal_rel_path=rel, added_at="2026-09-09T08:39:01+00:00",
        leg={"sequence": 2, "strike": 23700, "option_type": "CE", "direction": "sell", "quantity_lots": 1,
             "order_type": "LIMIT", "entry_premium": 185.0, "ltp_at_fill": 184.9, "entry_charges_inr": 47.97},
        structure_after={"legs_count": 2, "net_debit_credit_inr": 6665.75, "max_loss_inr": 12834.25,
                         "max_profit_inr": 6665.75, "breakevens": [23802.55], "margin_required_inr": 66836.0},
        vault_path=tmp_path,
    )
    text = (tmp_path / rel).read_text(encoding="utf-8")
    assert "## Adjustments" in text
    assert "### Leg added — 2026-09-09 14:09:01 IST" in text
    assert "| 2 | 23,700 | CE | SELL | 1 | limit | ₹185.00 | ₹184.90 | ₹47.97 |" in text
    assert text.index("## Adjustments") < text.index("## Exit")
    assert text.index("### Legs") < text.index("## Adjustments")
