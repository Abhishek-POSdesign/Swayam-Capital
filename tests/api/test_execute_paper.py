"""
Tests for trade execution endpoint in Swayam Capital.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from swayam.api import app


client = TestClient(app)


def test_execute_blocks_real_mode_with_403() -> None:
    payload = {
        "strategy_name": "Test Real Mode",
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
        "mode": "real",
    }

    response = client.post("/api/execute", json=payload)
    assert response.status_code == 403
    assert "Real execution disabled" in response.json()["detail"]


# These two tests drive the real execution path, which inserts a position and a
# journal row. They previously patched `swayam.db.db`, but `execution.py` does
# `from swayam.db import db` at import time, so the patch never reached the name
# the route actually uses and every run wrote into the LIVE record. The marker
# swaps in an in-memory database instead. See tests/db_guard.py.
@pytest.mark.fake_db
def test_execute_allows_a_non_compliant_intraday_strategy() -> None:
    payload = {
        "strategy_name": "Violating Spread",
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
        "mode": "paper",
    }

    response = client.post("/api/execute", json=payload)
    # Abhishek's rule of 2026-09-08: nothing blocks an entry. He builds and
    # adjusts freely, including structures that breach the advisory caps,
    # because mid-adjustment a position always looks terrible for a minute.
    # Only carrying a position overnight is gated.
    assert response.status_code == 200


# These two tests drive the real execution path, which inserts a position and a
# journal row. They previously patched `swayam.db.db`, but `execution.py` does
# `from swayam.db import db` at import time, so the patch never reached the name
# the route actually uses and every run wrote into the LIVE record. The marker
# swaps in an in-memory database instead. See tests/db_guard.py.
@pytest.mark.fake_db
def test_execute_paper_mode_creates_journal_and_position(tmp_path: Path) -> None:
    from swayam.config import settings
    original_vault = settings.vault_path
    object.__setattr__(settings, "vault_path", tmp_path)

    # Prepare mock method rules in tmp_path
    method_dir = tmp_path / "02 - Projects" / "Trading" / "01 - Method"
    method_dir.mkdir(parents=True, exist_ok=True)
    (method_dir / "Risk Management Rules.md").write_text(
        "1. Risk per trade: 1.0%\n2. R:R minimum: 1:2.0\n3. Daily loss cap: 2.0%\n4. Weekly loss cap: 4.0%\n5. Blast radius: 3.0%\n6. Overnight hedge cap: 2.0%\n",
        encoding="utf-8",
    )
    (method_dir / "Operational Readiness Rules.md").write_text(
        "Sleep < 5 hours = No trade\nSleep 5–6 hours = 75% sizing\nAlcohol: 90-day lockout\nRe-entry Ramp:\n- Week 1: 25% size\n- Week 2: 50% size\n- Week 3: 75% size\n- Week 4: 100% size\n",
        encoding="utf-8",
    )
    (method_dir / "Personal Trading Brief.md").write_text(
        "Base margin: ₹8–9 lakh (midpoint ₹8.5 lakh)\n",
        encoding="utf-8",
    )

    payload = {
        "strategy_name": "Paper Bear Put",
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
        "mode": "paper",
    }

    try:
        with patch("swayam.db.db") as mock_val_db:
            mock_val_db.get_margin_base_inr.return_value = 850000.0
            mock_val_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
            response = client.post("/api/execute", json=payload)
        assert response.status_code == 200
        data = response.json()


        assert data["status"] == "opened"
        assert "journal_path" in data

        # Verify journal file was physically written to tmp_path
        created_file = tmp_path / data["journal_path"]
        assert created_file.exists()
        content = created_file.read_text(encoding="utf-8")
        assert "Paper Bear Put" in content
        assert "status: open" in content
    finally:
        object.__setattr__(settings, "vault_path", original_vault)


def test_execute_raises_503_when_live_capital_unavailable(mocker) -> None:
    """If the live FYERS balance cannot be read, execute returns 503, not a stored figure.

    The journal states risk as a percentage of capital. That denominator used
    to be `swayam_config.margin_base_inr`; it is the live balance now, and
    without it the trade must not happen.
    """
    from swayam.services.capital import CapitalUnavailable

    mocker.patch(
        "swayam.services.capital.get_capital",
        side_effect=CapitalUnavailable("Could not reach the broker for funds"),
    )
    payload = {
        "strategy_name": "Paper Bear Put",
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
        "mode": "paper",
    }
    response = client.post("/api/execute", json=payload)
    assert response.status_code == 503
    detail = response.json()["detail"].lower()
    assert "live account balance is unavailable" in detail
    assert "could not reach the broker" in detail


def test_execute_raises_503_when_supabase_insert_fails(mocker, tmp_path: Path) -> None:
    """If Supabase INSERT to swayam_positions fails, execute returns 503, no orphan file."""
    from swayam.config import settings
    from swayam.db import db

    original_vault = settings.vault_path
    object.__setattr__(settings, "vault_path", tmp_path)

    method_dir = tmp_path / "02 - Projects" / "Trading" / "01 - Method"
    method_dir.mkdir(parents=True, exist_ok=True)
    (method_dir / "Risk Management Rules.md").write_text(
        "1. Risk per trade: 1.0%\n2. R:R minimum: 1:2.0\n3. Daily loss cap: 2.0%\n4. Weekly loss cap: 4.0%\n5. Blast radius: 3.0%\n6. Overnight hedge cap: 2.0%\n",
        encoding="utf-8",
    )
    (method_dir / "Operational Readiness Rules.md").write_text(
        "Sleep < 5 hours = No trade\nSleep 5–6 hours = 75% sizing\nAlcohol: 90-day lockout\nRe-entry Ramp:\n- Week 1: 25% size\n- Week 2: 50% size\n- Week 3: 75% size\n- Week 4: 100% size\n",
        encoding="utf-8",
    )
    (method_dir / "Personal Trading Brief.md").write_text(
        "Base margin: ₹8–9 lakh (midpoint ₹8.5 lakh)\n",
        encoding="utf-8",
    )

    mock_table = mocker.MagicMock()
    mock_table.insert.return_value.execute.side_effect = Exception("Supabase connection timeout")
    mocker.patch.object(db.client, "table", return_value=mock_table)

    payload = {
        "strategy_name": "Paper Bear Put",
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
        "mode": "paper",
    }

    try:
        response = client.post("/api/execute", json=payload)
        assert response.status_code == 503
        assert "trade execution blocked: supabase insert to swayam_positions failed" in response.json()["detail"].lower()
        orphan_files = list(tmp_path.rglob("*-trade*.md"))
        assert len(orphan_files) == 0, f"Expected 0 orphan files, but found: {orphan_files}"
    finally:
        object.__setattr__(settings, "vault_path", original_vault)


def test_execute_creates_no_orphan_journal_file_on_db_failure(mocker, tmp_path: Path) -> None:
    """Verify DB failure means no journal file on disk (order-of-operations correctness)."""
    from swayam.config import settings
    from swayam.db import db

    original_vault = settings.vault_path
    object.__setattr__(settings, "vault_path", tmp_path)

    method_dir = tmp_path / "02 - Projects" / "Trading" / "01 - Method"
    method_dir.mkdir(parents=True, exist_ok=True)
    (method_dir / "Risk Management Rules.md").write_text(
        "1. Risk per trade: 1.0%\n2. R:R minimum: 1:2.0\n3. Daily loss cap: 2.0%\n4. Weekly loss cap: 4.0%\n5. Blast radius: 3.0%\n6. Overnight hedge cap: 2.0%\n",
        encoding="utf-8",
    )
    (method_dir / "Operational Readiness Rules.md").write_text(
        "Sleep < 5 hours = No trade\nSleep 5–6 hours = 75% sizing\nAlcohol: 90-day lockout\nRe-entry Ramp:\n- Week 1: 25% size\n- Week 2: 50% size\n- Week 3: 75% size\n- Week 4: 100% size\n",
        encoding="utf-8",
    )
    (method_dir / "Personal Trading Brief.md").write_text(
        "Base margin: ₹8–9 lakh (midpoint ₹8.5 lakh)\n",
        encoding="utf-8",
    )

    mock_table = mocker.MagicMock()
    mock_table.insert.return_value.execute.side_effect = Exception("Disk full / DB connection lost")
    mocker.patch.object(db.client, "table", return_value=mock_table)

    payload = {
        "strategy_name": "Paper Bear Put",
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
        "mode": "paper",
    }

    try:
        response = client.post("/api/execute", json=payload)
        assert response.status_code == 503
        orphan_files = list(tmp_path.rglob("*-trade*.md"))
        assert len(orphan_files) == 0, f"Expected 0 orphan files, but found: {orphan_files}"
    finally:
        object.__setattr__(settings, "vault_path", original_vault)




@pytest.mark.fake_db
def test_the_stored_leg_carries_the_servers_contract_size_and_its_entry_cost(fake_db) -> None:
    """Two money bugs in one line, both proven against the desk's real payload.

    ONE. `web/src/pages/strategy-builder.js` sends no `lot_size` at all. The
    stored leg used to be a dump of the request, so it was stored as null, and
    `close_position` REFUSES to value a leg with no contract size rather than
    guess. His first paper trade would have opened and then never closed.

    TWO. Nothing was charged at entry. A leg is now costed as it is bought or
    sold, on its own side, at its own price.

    The payload below is copied from `legsPayload()` in that file. If the desk
    ever starts sending a contract size, the server still wins: a browser that
    hardcodes 75 is how every contract-scaled figure came to be 15.4% too big.
    """
    payload = {
        "strategy_name": "Bull Call Spread",
        "underlying": "NIFTY",
        "current_spot": 24800.0,
        "order_type": "LIMIT",
        "mode": "paper",
        "legs": [
            {
                "strike": 25000.0,
                "option_type": "CE",
                "direction": "buy",
                "quantity_lots": 1,
                "entry_premium": 150.0,
                "expiry_date": "2026-09-24",
                "order_type": "LIMIT",
            },
            {
                "strike": 25200.0,
                "option_type": "CE",
                "direction": "sell",
                "quantity_lots": 1,
                "entry_premium": 80.0,
                "expiry_date": "2026-09-24",
                "order_type": "LIMIT",
            },
        ],
        "iv_per_leg": {"default": 0.15},
    }

    response = client.post("/api/execute/multi-leg", json=payload)
    assert response.status_code == 200, response.text

    written = fake_db.inserted_into("swayam_positions")
    assert len(written) == 1
    legs = written[0]["legs"]
    assert len(legs) == 2

    for leg in legs:
        assert isinstance(leg["lot_size"], int) and leg["lot_size"] > 0, (
            "a leg stored without a contract size can never be closed"
        )
        assert leg["lot_size"] != 75, "75 is the old contract size; the server resolves 65"
        assert leg["entry_charges_inr"] > 0, "getting in was never charged before this"
        assert leg["charges_schedule_version"]

    # The bought leg and the sold leg cost different amounts to open.
    assert legs[0]["entry_charges_inr"] != legs[1]["entry_charges_inr"]

    # The position's running cost is the sum of its legs'.
    assert written[0]["charges_inr"] == pytest.approx(
        round(sum(l["entry_charges_inr"] for l in legs), 2)
    )
