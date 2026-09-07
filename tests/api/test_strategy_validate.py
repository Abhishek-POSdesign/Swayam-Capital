"""
Tests for Method rule validation endpoint in Swayam Capital.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from swayam.api import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_readiness_allowed():
    """Ensures strategy validation tests run with clear readiness status."""
    from swayam.db import db
    try:
        orig_table = db.client.table

        def table_router(name):
            if name == "swayam_readiness_log":
                mock_t = MagicMock()
                mock_t.select.return_value.eq.return_value.execute.return_value.data = []
                return mock_t
            return orig_table(name)

        with patch.object(db.client, "table", side_effect=table_router):
            yield
    except Exception:
        yield



def test_validate_compliant_spread_passes() -> None:

    payload = {
        "strategy_name": "Valid Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24850.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 150.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
            {
                "strike": 24100.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 1,
                "entry_premium": 50.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
        ],
        "current_spot": 24867.5,
        "iv_per_leg": {"default": 0.15},
    }

    response = client.post("/api/strategy/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is True
    assert len(data["checks"]) >= 4


def test_validate_single_leg_fails_no_single_leg_rule() -> None:
    payload = {
        "strategy_name": "Naked Call",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 25000.0,
                "option_type": "CE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 150.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            }
        ],
        "current_spot": 24867.5,
        "iv_per_leg": {"default": 0.15},
    }

    response = client.post("/api/strategy/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is False

    rule_checks = {c["rule"]: c["verdict"] for c in data["checks"]}
    assert rule_checks["no_single_leg"] == "FAIL"


def test_validate_excessive_loss_fails_blast_radius() -> None:
    # 20 lots with ₹200 risk = ₹3,00,000 max loss, which blows past 3% blast cap (~₹25,500)
    payload = {
        "strategy_name": "Excessive Risk Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 25000.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 20,
                "entry_premium": 300.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
            {
                "strike": 24000.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 20,
                "entry_premium": 100.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
        ],
        "current_spot": 24867.5,
        "iv_per_leg": {"default": 0.15},
    }

    response = client.post("/api/strategy/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["passed"] is False

    rule_checks = {c["rule"]: c["verdict"] for c in data["checks"]}
    assert rule_checks["blast_radius"] == "FAIL"


def test_validate_blocks_when_live_capital_is_unavailable(mocker) -> None:
    """Capital is a hard dependency: no live balance, no trade.

    This test used to check a stale `margin_base_inr` row in the config table.
    That figure is gone. Risk caps are now a percentage of the live broker
    balance, and if the broker cannot be reached the gate refuses rather than
    falling back to a remembered number.
    """
    from swayam.services.capital import CapitalUnavailable

    mocker.patch(
        "swayam.api.routes.validation.get_capital",
        side_effect=CapitalUnavailable("Could not reach the broker for funds"),
    )

    payload = {
        "strategy_name": "Valid Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24850.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 150.0,
                "expiry_date": "2026-09-24",
            },
            {
                "strike": 24100.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 1,
                "entry_premium": 50.0,
                "expiry_date": "2026-09-24",
            },
        ],
        "current_spot": 24867.5,
        "iv_per_leg": {"default": 0.15},
    }
    response = client.post("/api/strategy/validate", json=payload)
    assert response.status_code == 503
    assert "capital is unavailable" in response.json()["detail"].lower()


def test_validate_uses_settings_tolerance_not_hardcoded_002() -> None:
    """Verify TolerantComparator receives settings.default_tolerance_pct, not 0.02 literal."""
    from swayam.config import settings

    orig_tolerance = settings.default_tolerance_pct
    object.__setattr__(settings, "default_tolerance_pct", 0.05)  # override to 5%
    try:
        payload = {
            "strategy_name": "Boundary Spread",
            "underlying": "NIFTY",
            "legs": [
                {
                    "strike": 24850.0,
                    "option_type": "PE",
                    "direction": "buy",
                    "quantity_lots": 1,
                    "entry_premium": 167.33333333333334,
                    "expiry_date": "2026-09-24",
                    "lot_size": 75,
                },
                {
                    "strike": 24100.0,
                    "option_type": "PE",
                    "direction": "sell",
                    "quantity_lots": 1,
                    "entry_premium": 50.0,
                    "expiry_date": "2026-09-24",
                    "lot_size": 75,
                },
            ],
            "current_spot": 24867.5,
            "iv_per_leg": {"default": 0.15},
        }
        response = client.post("/api/strategy/validate", json=payload)
        assert response.status_code == 200
        data = response.json()
        cap_check = next(c for c in data["checks"] if c["rule"] == "blast_radius")
        assert cap_check["verdict"] == "PASS"
        assert cap_check["tolerance_pct"] == 0.05
    finally:
        object.__setattr__(settings, "default_tolerance_pct", orig_tolerance)


def test_validate_spread_passes_realistic_fails_blast() -> None:
    """A far-OTM credit spread: tiny loss at 2 sigma, catastrophic worst case.

    Sizes changed 2026-09-08. The old fixture no longer separated the two caps
    once the contract size became 65 and the fuse rose from 3% to 5%. This
    shape separates them cleanly: the short strike is far enough away that a 2
    sigma move barely touches it, while the 1000-point wing makes the absolute
    worst case enormous.
    """
    payload = {
        "strategy_name": "Far OTM Credit Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 23000.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 2,
                "entry_premium": 8.0,
                "expiry_date": "2026-09-24",
            },
            {
                "strike": 22000.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 2,
                "entry_premium": 3.0,
                "expiry_date": "2026-09-24",
            },
        ],
        "current_spot": 24867.5,
        "iv_per_leg": {"default": 0.15},
    }
    response = client.post("/api/strategy/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["overall_passed"] is False
    assert data["realistic_risk"]["passed"] is True
    assert data["blast_radius"]["passed"] is False
    # 5% of the live 9,71,002.38.
    assert data["blast_radius"]["cap_inr"] == 48550.12


def test_validate_spread_passes_blast_fails_realistic() -> None:
    """A debit spread sized so the 2 sigma loss breaches 1% but the worst case does not breach 5%."""
    payload = {
        "strategy_name": "Oversized Debit Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24850.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 7,
                "entry_premium": 120.0,
                "expiry_date": "2026-09-24",
            },
            {
                "strike": 24400.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 7,
                "entry_premium": 20.0,
                "expiry_date": "2026-09-24",
            },
        ],
        "current_spot": 24867.5,
        "iv_per_leg": {"default": 0.15},
    }
    response = client.post("/api/strategy/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["overall_passed"] is False
    assert data["realistic_risk"]["passed"] is False
    assert data["blast_radius"]["passed"] is True
    # 7 lots x 65 x Rs 100 net debit = 45,500, inside the 48,550 fuse.
    assert data["blast_radius"]["loss_inr"] == 45500.0
    # The primary gate now includes the round-trip cost reserve, and says so.
    assert data["realistic_risk"]["cost_reserve_inr"] > 0
    assert "round-trip costs" in data["realistic_risk"]["arithmetic"]

def test_validate_spread_passes_both() -> None:
    """Compliant spread that passes both realistic and blast radius caps."""
    payload = {
        "strategy_name": "Pass Both Caps",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24850.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 120.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
            {
                "strike": 24400.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 1,
                "entry_premium": 20.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
        ],
        "current_spot": 24867.5,
        "iv_per_leg": {"default": 0.15},
    }
    response = client.post("/api/strategy/validate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["overall_passed"] is True
    assert data["passed"] is True
    assert data["realistic_risk"]["passed"] is True
    assert data["blast_radius"]["passed"] is True
    assert data["realistic_risk"]["loss_inr"] <= data["realistic_risk"]["cap_inr"]


def test_validate_historical_vol_unavailable_raises_503(mocker) -> None:
    """Historical data missing raises 503 with loud error."""
    from swayam.options_math.realized_vol import HistoricalDataUnavailableError
    mocker.patch(
        "swayam.api.routes.validation.compute_realized_vol",
        side_effect=HistoricalDataUnavailableError("Table 'nifty_daily_bars' does not exist in DuckDB."),
    )
    payload = {
        "strategy_name": "Test 503 Vol",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24850.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 120.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
            {
                "strike": 24400.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 1,
                "entry_premium": 20.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
        ],
        "current_spot": 24867.5,
        "iv_per_leg": {"default": 0.15},
    }
    response = client.post("/api/strategy/validate", json=payload)
    assert response.status_code == 503
    assert "historical market data unavailable" in response.json()["detail"].lower()


def test_validate_insufficient_history_raises_503(mocker) -> None:
    """Insufficient history raises 503 with actionable backfill command."""
    from swayam.options_math.realized_vol import InsufficientHistoryError
    mocker.patch(
        "swayam.api.routes.validation.compute_realized_vol",
        side_effect=InsufficientHistoryError(
            needed=20,
            available=10,
            backfill_command="python scripts/backfill_bhavcopy.py --days 30",
        ),
    )
    payload = {
        "strategy_name": "Test Insufficient History",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24850.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 120.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
            {
                "strike": 24400.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 1,
                "entry_premium": 20.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
        ],
        "current_spot": 24867.5,
        "iv_per_leg": {"default": 0.15},
    }
    response = client.post("/api/strategy/validate", json=payload)
    assert response.status_code == 503
    assert "insufficient nifty history (10/20 sessions)" in response.json()["detail"].lower()
    assert "backfill_bhavcopy.py" in response.json()["detail"]

