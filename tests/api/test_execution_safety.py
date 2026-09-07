"""
The two guarantees from plan v9 Step 5, proved rather than asserted.

  1. A trade is recorded exactly once, however many times the button is pressed.
  2. A journal note that cannot be written never fails the trade.

Both run against the in-memory database from tests/db_guard.py. Plan v9's
unlock gate says the duplicate-submission test must run "in staging, never in
production"; there is no staging project, so the marker is how that condition
is met.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from swayam.api import app
from swayam.config import settings

client = TestClient(app)


def _payload(**overrides):
    body = {
        "strategy_name": "Bear Put Spread",
        "underlying": "NIFTY",
        "legs": [
            {
                "strike": 23800.0, "option_type": "PE", "direction": "buy",
                "quantity_lots": 1, "entry_premium": 120.0, "expiry_date": "2026-09-24",
            },
            {
                "strike": 23600.0, "option_type": "PE", "direction": "sell",
                "quantity_lots": 1, "entry_premium": 60.0, "expiry_date": "2026-09-24",
            },
        ],
        "current_spot": 23779.15,
        "iv_per_leg": {"default": 0.15},
        "mode": "paper",
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------- idempotency

@pytest.mark.fake_db
def test_the_same_key_twice_creates_exactly_one_position(fake_db, tmp_path):
    """A double click, or a retry after a lost response, must not trade twice."""
    original = settings.vault_path
    object.__setattr__(settings, "vault_path", tmp_path)
    try:
        body = _payload(idempotency_key="ticket-abc-123")

        first = client.post("/api/execute", json=body)
        second = client.post("/api/execute", json=body)

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text

        # The retry replays the first answer rather than opening a new position.
        assert first.json()["position_id"] == second.json()["position_id"]

        positions = fake_db.inserted_into("swayam_positions")
        assert len(positions) == 1, f"expected exactly one position, got {len(positions)}"
    finally:
        object.__setattr__(settings, "vault_path", original)


@pytest.mark.fake_db
def test_the_same_key_for_a_different_trade_is_refused(fake_db, tmp_path):
    """A key belongs to one trade. Reusing it for another is a bug, not a retry."""
    original = settings.vault_path
    object.__setattr__(settings, "vault_path", tmp_path)
    try:
        first = client.post("/api/execute", json=_payload(idempotency_key="ticket-xyz"))
        assert first.status_code == 200, first.text

        different = _payload(idempotency_key="ticket-xyz", strategy_name="Something Else")
        second = client.post("/api/execute", json=different)

        assert second.status_code == 409
        assert len(fake_db.inserted_into("swayam_positions")) == 1
    finally:
        object.__setattr__(settings, "vault_path", original)


@pytest.mark.fake_db
def test_without_a_key_there_is_no_protection_and_that_is_explicit(fake_db, tmp_path):
    """Documents the boundary: no key means no guard. The browser must send one."""
    original = settings.vault_path
    object.__setattr__(settings, "vault_path", tmp_path)
    try:
        body = _payload()
        client.post("/api/execute", json=body)
        client.post("/api/execute", json=body)
        assert len(fake_db.inserted_into("swayam_positions")) == 2
    finally:
        object.__setattr__(settings, "vault_path", original)


# -------------------------------------------------------------------- outbox

@pytest.mark.fake_db
def test_an_unreachable_vault_does_not_fail_the_trade(fake_db, tmp_path):
    """The live-site failure, reproduced.

    Cloud Run has no route to `G:\\My Drive\\Second Brain`, so the journal write
    raises. Before this change that returned HTTP 500 on a trade that had
    already been inserted, and he clicked again.
    """
    original = settings.vault_path
    object.__setattr__(settings, "vault_path", tmp_path)
    try:
        with patch(
            "swayam.api.routes.execution.write_new_trade_journal",
            side_effect=OSError("[Errno 2] No such file or directory: 'G:\\\\My Drive'"),
        ):
            response = client.post("/api/execute", json=_payload(idempotency_key="k-vault"))

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "opened"
        assert body["journal_status"] == "pending"
        assert "queued" in body["message"]

        # The trade is recorded once, and the note is parked rather than lost.
        assert len(fake_db.inserted_into("swayam_positions")) == 1
        queued = fake_db.inserted_into("swayam_journal_outbox")
        assert len(queued) == 1
        assert queued[0]["status"] == "pending"
        assert queued[0]["kind"] == "new_trade"
    finally:
        object.__setattr__(settings, "vault_path", original)


@pytest.mark.fake_db
def test_a_written_note_is_reported_as_written(fake_db, tmp_path):
    """The happy path still says so, and queues nothing."""
    original = settings.vault_path
    object.__setattr__(settings, "vault_path", tmp_path)
    try:
        response = client.post("/api/execute", json=_payload(idempotency_key="k-ok"))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["journal_status"] == "written"
        assert body["journal_path"]
        assert fake_db.inserted_into("swayam_journal_outbox") == []

        written = tmp_path / body["journal_path"]
        assert written.exists()
    finally:
        object.__setattr__(settings, "vault_path", original)
