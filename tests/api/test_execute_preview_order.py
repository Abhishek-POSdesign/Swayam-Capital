"""
Order preview: leg ordering, contract size, and honest margin.

This file used to assert `margin_saved_inr > 0` against two invented constants,
Rs 32,000 hedged and Rs 1,15,000 naked. Measured against the live account on
2026-09-07, one lot of NIFTY actually costs about Rs 66,836 hedged and
Rs 2,00,441 naked, so both understated the real requirement by roughly half.
The endpoint now asks FYERS, and reports "unavailable" with a reason when it
cannot. These tests assert that contract, not a number.
"""

from fastapi.testclient import TestClient
from swayam.api import app

client = TestClient(app)


def _payload() -> dict:
    return {
        "underlying": "NIFTY",
        "current_spot": 24850.0,
        "legs": [
            # SELL listed first on purpose, to prove the endpoint reorders.
            {
                "strike": 24700.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 1,
                "entry_premium": 65.0,
                "expiry_date": "2026-09-10",
                # Deliberately wrong. The server must ignore it.
                "lot_size": 75,
            },
            {
                "strike": 24900.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 120.0,
                "expiry_date": "2026-09-10",
                "lot_size": 75,
            },
        ],
    }


def test_preview_order_sequence_buys_first():
    response = client.post("/api/execute/preview-order", json=_payload())
    assert response.status_code == 200
    data = response.json()

    ordered = data["ordered_legs"]
    assert len(ordered) == 2

    # Buys first. This is not cosmetic: FYERS returns the un-hedged margin when
    # a short leg is listed before the long leg that covers it.
    assert ordered[0]["direction"] == "BUY"
    assert ordered[0]["strike"] == 24900.0
    assert ordered[0]["sequence"] == 1
    assert ordered[1]["direction"] == "SELL"
    assert ordered[1]["strike"] == 24700.0
    assert ordered[1]["sequence"] == 2

    assert data["buy_count"] == 1
    assert data["sell_count"] == 1


def test_contract_size_comes_from_the_contract_master_not_the_request():
    """The browser sends 75. The server must use the real 65."""
    response = client.post("/api/execute/preview-order", json=_payload())
    assert response.status_code == 200
    for leg in response.json()["ordered_legs"]:
        assert leg["lot_size"] == 65, "contract size must come from the FYERS master"


def test_margin_is_real_or_explicitly_unavailable_never_invented():
    response = client.post("/api/execute/preview-order", json=_payload())
    assert response.status_code == 200
    data = response.json()

    # A per-leg margin is not a real quantity: the broker prices the basket.
    for leg in data["ordered_legs"]:
        assert leg["estimated_margin_inr"] is None

    margin = data["margin_required_inr"]
    if margin is None:
        # Unavailable must always say why.
        assert data["margin_unavailable_reason"]
    else:
        assert margin > 0
        assert data["margin_source"]
        assert data["margin_fetched_at"]
        # The old invented constants must never reappear.
        assert margin not in (32000.0, 115000.0)
