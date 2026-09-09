"""
The path nobody has run: one by one, then close, then the note.

"A thing that has never run has never been tested." Written 2026-09-09
evening, with the market shut, because he could walk the ticket but not send
through it. Everything here runs the REAL route code against the in-memory
database and a temporary vault: open a trade with one leg, add a second leg
to it, close it through the real close path, and read the note back.

Also the loophole found while checking: a retry after a lost response used
to carry a fresh spot and fresh market prices, hash differently under the
same key, and be refused as a different trade, which then minted a new key
and traded twice. The hash now ignores what is not his instruction.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from swayam.api import app
from swayam.config import settings
from swayam.services.execution_safety import canonical_payload_hash

client = TestClient(app)
EXPIRY = "2026-09-24"


def _leg(direction, strike, opt, premium, **extra):
    body = {"strike": float(strike), "option_type": opt, "direction": direction,
            "quantity_lots": 1, "entry_premium": float(premium), "expiry_date": EXPIRY}
    body.update(extra)
    return body


def _first(**overrides):
    body = {
        "strategy_name": "Bull Call Spread", "underlying": "NIFTY", "current_spot": 23635.10,
        "mode": "paper", "leg_order": "as_sent", "execution_mode": "one_by_one",
        "legs": [_leg("buy", 23550, "CE", 293.35)],
    }
    body.update(overrides)
    return body


def _chain_at(prices: dict[tuple[float, str], float]):
    """A chain lookup for the close path: {(strike, type): ltp}."""
    rows = [{"strike_price": k[0], "option_type": k[1], "ltp": v} for k, v in prices.items()]
    return {"underlyingValue": 23640.0, "optionsChain": rows}


# ---------------------------------------------------------------- the whole life of one trade

@pytest.mark.fake_db
def test_one_by_one_then_close_writes_one_complete_note(fake_db, tmp_path):
    original = settings.vault_path
    object.__setattr__(settings, "vault_path", tmp_path)
    try:
        # 1. The first leg opens the trade.
        first = client.post("/api/execute/multi-leg", json=_first(idempotency_key="t-leg-1"))
        assert first.status_code == 200, first.text
        pid = first.json()["position_id"]
        assert first.json()["journal_status"] == "written"
        note = tmp_path / first.json()["journal_path"]
        assert note.exists()

        # 2. The second leg joins the SAME trade.
        second = client.post(f"/api/positions/{pid}/legs", json={
            "leg": _leg("sell", 23750, "CE", 186.50), "current_spot": 23636.0, "idempotency_key": "t-leg-2",
        })
        assert second.status_code == 200, second.text
        assert second.json()["legs_count"] == 2
        assert second.json()["journal_status"] == "written"
        text = note.read_text(encoding="utf-8")
        assert "## Adjustments" in text and "### Leg added" in text
        assert "| 2 | 23,750 | CE | SELL | 1 | market | ₹186.50 |" in text

        row = next(r for r in fake_db.rows["swayam_positions"] if r["id"] == pid)
        assert len(row["legs"]) == 2 and all(l["lot_size"] > 0 for l in row["legs"])
        assert row["net_debit_credit_inr"] == pytest.approx((186.50 - 293.35) * 65, abs=0.01)

        # 3. The close, through the real close path, valued against a chain.
        with patch("swayam.api.routes.positions._get_cached_option_chain",
                   return_value=_chain_at({(23550.0, "CE"): 291.75, (23750.0, "CE"): 183.75})):
            closed = client.post(f"/api/positions/{pid}/close", json={"close_reason": "manual", "notes": "test close"})
        assert closed.status_code == 200, closed.text
        result = closed.json()
        assert result["status"] == "closed"
        assert len(result["exit_legs"]) == 2, "the added leg must be closed with the first"
        # His real trade 01 numbers: gross +74.75 at these prices.
        assert result["gross_pnl_inr"] == pytest.approx(74.75, abs=0.01)
        assert result["total_charges_inr"] > 0
        assert result["realized_pnl_inr"] == pytest.approx(74.75 - result["total_charges_inr"], abs=0.01)

        # 4. One result, the position closed, the note complete in order.
        assert len(fake_db.inserted_into("swayam_trade_history")) == 1
        row = next(r for r in fake_db.rows["swayam_positions"] if r["id"] == pid)
        assert row["status"] == "closed" and row["spot_at_exit"] == 23640.0
        assert row["points_in_trade"] == pytest.approx(23640.0 - 23635.10, abs=0.01)
        text = note.read_text(encoding="utf-8")
        assert text.index("### Legs") < text.index("## Adjustments") < text.index("## Exit")
        assert "status: closed" in text
        assert "**Time opened**: 2026-09-" in text and " IST" in text
        assert "(0 days held)" in text
    finally:
        object.__setattr__(settings, "vault_path", original)


@pytest.mark.fake_db
def test_the_second_press_after_a_tick_is_the_same_trade(fake_db, tmp_path):
    """The loophole. Same key, the spot ticked, the market leg re-quoted: ONE position."""
    original = settings.vault_path
    object.__setattr__(settings, "vault_path", tmp_path)
    try:
        body = _first(idempotency_key="t-retry")
        first = client.post("/api/execute/multi-leg", json=body)
        assert first.status_code == 200, first.text

        moved = dict(body)
        moved["current_spot"] = 23641.55
        moved["legs"] = [_leg("buy", 23550, "CE", 294.10)]  # the market moved 75 paise
        second = client.post("/api/execute/multi-leg", json=moved)
        assert second.status_code == 200, second.text
        assert second.json()["position_id"] == first.json()["position_id"]
        assert len(fake_db.inserted_into("swayam_positions")) == 1
    finally:
        object.__setattr__(settings, "vault_path", original)


def test_a_limit_price_is_his_instruction_and_stays_in_the_hash():
    a = _first(legs=[_leg("buy", 23550, "CE", 290.0, order_type="LIMIT", limit_price=290.0)])
    b = _first(legs=[_leg("buy", 23550, "CE", 291.0, order_type="LIMIT", limit_price=291.0)])
    assert canonical_payload_hash(a) != canonical_payload_hash(b)


def test_a_market_price_and_the_spot_are_not_his_instruction():
    a = _first(current_spot=23635.1, legs=[_leg("buy", 23550, "CE", 293.35)])
    b = _first(current_spot=23641.0, legs=[_leg("buy", 23550, "CE", 294.10)])
    assert canonical_payload_hash(a) == canonical_payload_hash(b)
    c = _first(current_spot=23635.1, legs=[_leg("buy", 23600, "CE", 293.35)])  # a different strike IS different
    assert canonical_payload_hash(a) != canonical_payload_hash(c)


@pytest.mark.fake_db(seed={"swayam_positions": [{
    "id": "22222222-2222-2222-2222-222222222222", "strategy_name": "X", "underlying": "NIFTY",
    "expiry_date": EXPIRY, "legs": [{"strike": 23550.0, "option_type": "CE", "direction": "buy", "quantity_lots": 1,
                                     "entry_premium": 293.35, "expiry_date": EXPIRY, "lot_size": 65, "sequence": 1}],
    "net_debit_credit_inr": -19067.75, "max_loss_inr": 19067.75, "max_profit_inr": 0.0, "breakeven_points": [],
    "risk_at_entry_inr": 19067.75, "status": "open", "mode": "paper", "opened_at": "2026-09-09T08:37:12+00:00",
    "charges_inr": 34.21, "journal_path": None,
}]})
def test_adding_the_same_leg_again_after_a_tick_adds_it_once(fake_db):
    pid = "22222222-2222-2222-2222-222222222222"
    a = {"leg": _leg("sell", 23750, "CE", 186.50), "current_spot": 23636.0, "idempotency_key": "t-add"}
    b = {"leg": _leg("sell", 23750, "CE", 186.95), "current_spot": 23639.4, "idempotency_key": "t-add"}
    assert client.post(f"/api/positions/{pid}/legs", json=a).status_code == 200
    assert client.post(f"/api/positions/{pid}/legs", json=b).status_code == 200
    row = next(r for r in fake_db.rows["swayam_positions"] if r["id"] == pid)
    assert len(row["legs"]) == 2
