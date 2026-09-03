"""
Tests for Method rules retrieval endpoint in Swayam Capital.
"""

from fastapi.testclient import TestClient
from swayam.api import app

client = TestClient(app)


def test_get_rules_returns_parsed_method_percentages() -> None:
    response = client.get("/api/rules")
    assert response.status_code == 200
    rules = response.json()

    assert rules["per_trade_risk_pct"] == 0.01
    assert rules["rr_minimum"] == 2.0
    assert rules["daily_loss_cap_pct"] == 0.02
    assert rules["weekly_loss_cap_pct"] == 0.04
    assert rules["blast_radius_pct"] == 0.03
    assert rules["overnight_hedge_cap_pct"] == 0.02
    assert rules["alcohol_lockout_days"] == 90
    assert rules["sleep_no_trade_threshold_hours"] == 5.0
    assert "per_trade_risk_cap_inr" in rules
    assert "reentry_ramp" in rules


def test_get_rules_force_reload_param_succeeds() -> None:
    response = client.get("/api/rules?force_reload=true")
    assert response.status_code == 200
    data = response.json()
    assert data["per_trade_risk_pct"] == 0.01
