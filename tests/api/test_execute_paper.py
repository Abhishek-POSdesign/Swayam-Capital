"""
Tests for trade execution endpoint in Swayam Capital.
"""

from pathlib import Path
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


def test_execute_rejects_non_compliant_strategy_with_400() -> None:
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
    assert response.status_code == 400


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


def test_execute_raises_503_when_supabase_unreachable_for_margin_base(mocker) -> None:
    """If db.get_margin_base_inr raises, execute returns 503, not silent fallback."""
    from swayam.db import DatabaseError

    mocker.patch("swayam.db.db.get_margin_base_inr", side_effect=DatabaseError("Config row missing"))
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
    assert "margin base unavailable" in response.json()["detail"].lower()


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

    mocker.patch("swayam.db.db.get_margin_base_inr", return_value=850000.0)
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

    mocker.patch("swayam.db.db.get_margin_base_inr", return_value=850000.0)
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


