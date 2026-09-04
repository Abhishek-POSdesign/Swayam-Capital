import pytest
from fastapi.testclient import TestClient
from swayam.api import app

client = TestClient(app)


def test_preview_order_sequence_buys_first():
    # Pass legs with SELL before BUY to verify sorting
    payload = {
        "underlying": "NIFTY",
        "current_spot": 24850.0,
        "legs": [
            {
                "strike": 24700.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 1,
                "entry_premium": 65.0,
                "expiry_date": "2026-09-10",
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

    response = client.post("/api/execute/preview-order", json=payload)
    assert response.status_code == 200
    data = response.json()

    ordered = data["ordered_legs"]
    assert len(ordered) == 2
    # First leg MUST be BUY for margin safety
    assert ordered[0]["direction"] == "BUY"
    assert ordered[0]["strike"] == 24900.0
    assert ordered[0]["sequence"] == 1

    # Second leg MUST be SELL
    assert ordered[1]["direction"] == "SELL"
    assert ordered[1]["strike"] == 24700.0
    assert ordered[1]["sequence"] == 2

    assert data["buy_count"] == 1
    assert data["sell_count"] == 1
    assert data["margin_saved_inr"] > 0
