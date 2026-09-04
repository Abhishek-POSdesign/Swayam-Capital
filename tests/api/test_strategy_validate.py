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


def test_validate_raises_503_when_supabase_unreachable_for_margin_base(mocker) -> None:
    """If db.get_margin_base_inr raises, validate returns 503, not silent fallback."""
    from swayam.db import DatabaseError
    mocker.patch("swayam.db.db.get_margin_base_inr", side_effect=DatabaseError("Config row missing"))
    valid_payload = {
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
    response = client.post("/api/strategy/validate", json=valid_payload)
    assert response.status_code == 503
    assert "margin base unavailable" in response.json()["detail"].lower()


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
    """Spread passing realistic risk but failing 3% blast radius ceiling."""
    # 4 lots of 450-pt wide Bear Put: max loss = 4 * 7500 = ₹30,000 > ₹25,500 blast cap
    # Overnight 2-sigma move loss: ~₹8,000 <= ₹8,500 realistic cap
    payload = {
        "strategy_name": "Pass Realistic Fail Blast",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24850.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 4,
                "entry_premium": 120.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
            {
                "strike": 24400.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 4,
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
    assert data["overall_passed"] is False
    assert data["passed"] is False
    assert data["realistic_risk"]["passed"] is True
    assert data["blast_radius"]["passed"] is False
    assert data["blast_radius"]["loss_inr"] == 30000.0


def test_validate_spread_passes_blast_fails_realistic() -> None:
    """Spread passing blast radius fuse but failing 1% realistic risk cap."""
    # 5 lots of 150-pt wide Bear Put: max loss = 5 * 63 * 75 = ₹23,625 <= ₹25,500 blast cap
    # Overnight 2-sigma move loss: ~₹10,225 > ₹8,500 realistic cap
    payload = {
        "strategy_name": "Pass Blast Fail Realistic",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 24850.0,
                "option_type": "PE",
                "direction": "buy",
                "quantity_lots": 5,
                "entry_premium": 150.0,
                "expiry_date": "2026-09-24",
                "lot_size": 75,
            },
            {
                "strike": 24700.0,
                "option_type": "PE",
                "direction": "sell",
                "quantity_lots": 5,
                "entry_premium": 87.0,
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
    assert data["overall_passed"] is False
    assert data["passed"] is False
    assert data["realistic_risk"]["passed"] is False
    assert data["blast_radius"]["passed"] is True
    assert data["blast_radius"]["loss_inr"] == 23625.0


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
    assert "insufficient nifty history (10/20 bars)" in response.json()["detail"].lower()
    assert "backfill_bhavcopy.py" in response.json()["detail"]

