import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from swayam.api import app

client = TestClient(app)


def test_execute_multi_leg_real_mode_blocked():
    payload = {
        "strategy_name": "Bear Put Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24900.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 120.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
        ],
        "current_spot": 24850.0,
        "mode": "real",
    }
    response = client.post("/api/execute/multi-leg", json=payload)
    assert response.status_code == 403


@patch("swayam.api.routes.execution.write_new_trade_journal", return_value="Trade-Journal/2026-09/test.md")
def test_execute_multi_leg_success(mock_journal):
    payload = {
        "strategy_name": "Bear Put Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24700.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 1,
                "entry_premium": 65.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
            {
                "strike": 24900.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 120.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
        ],
        "current_spot": 24850.0,
        "mode": "paper",
        "session_id": "sess-test-999",
        "order_type": "LIMIT",
    }

    with patch("swayam.api.routes.execution.db") as mock_exec_db, \
         patch("swayam.api.routes.validation.db") as mock_val_db:
        mock_val_db.get_margin_base_inr.return_value = 1000000.0
        mock_val_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        mock_exec_db.get_margin_base_inr.return_value = 1000000.0
        mock_exec_db.client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "test-uuid"}])

        response = client.post("/api/execute/multi-leg", json=payload)
        assert response.status_code == 200, f"Error: {response.json()}"
        data = response.json()
        assert data["status"] == "opened"
        assert "position_id" in data
        assert data["journal_path"] == "Trade-Journal/2026-09/test.md"
