"""Closing a trade twice must not record it twice.

Found 2026-09-09 by probing the live schema rather than by reading code. The
close path wrote `closed_at` and `journal_path` to `swayam_positions`, and
NEITHER COLUMN EXISTED. So his first close would have gone:

    1. the result is INSERTED into swayam_trade_history  (recorded)
    2. the UPDATE marking the position closed FAILS      (missing column)
    3. he sees HTTP 503
    4. the position still reads `open`
    5. he presses close again, and step 1 runs a second time

Migration 020 adds the columns and a unique index. These tests hold the code
half of the same rule, so a retry completes the half-finished close instead of
duplicating the trade.
"""

from typing import Any, Optional
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from swayam.api import app

client = TestClient(app)


OPEN_POSITION = {
    "id": "pos-retry-1",
    "strategy_name": "Bull Call Spread",
    "underlying": "NIFTY",
    "opened_at": "2026-09-09T09:30:00Z",
    "expiry_date": "2026-09-15",
    "net_debit_credit_inr": -4550.0,
    "max_loss_inr": 4550.0,
    "max_profit_inr": 8450.0,
    "status": "open",
    "mode": "paper",
    "provenance": "live",
    "legs": [
        {
            "strike": 25000.0,
            "option_type": "CE",
            "direction": "buy",
            "quantity_lots": 1,
            "lot_size": 65,
            "entry_premium": 150.0,
            "entry_charges_inr": 25.22,
            "expiry_date": "2026-09-15",
        },
        {
            "strike": 25200.0,
            "option_type": "CE",
            "direction": "sell",
            "quantity_lots": 1,
            "lot_size": 65,
            "entry_premium": 80.0,
            "entry_charges_inr": 32.02,
            "expiry_date": "2026-09-15",
        },
    ],
}

EXIT_LEGS = [
    {"strike": 25000.0, "option_type": "CE", "exit_premium": 210.0},
    {"strike": 25200.0, "option_type": "CE", "exit_premium": 95.0},
]


class FakeTable:
    def __init__(self, store, name):
        self._store = store
        self._name = name
        self._filters: list[tuple[str, Any]] = []

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def limit(self, *_a, **_k):
        return self

    def insert(self, record):
        self._store.inserts.setdefault(self._name, []).append(record)
        return self

    def update(self, values):
        self._store.updates.setdefault(self._name, []).append(values)
        self._pending_update = values
        return self

    def execute(self):
        class R:
            pass

        r = R()
        r.data = self._store.rows_for(self._name, self._filters)
        return r


class FakeStore:
    """A database that knows which table it is answering for."""

    def __init__(self, *, prior_result=False, note_row: Optional[str] = None,
                 position_has_path: bool = False, update_fails: bool = False):
        self.inserts: dict[str, list] = {}
        self.updates: dict[str, list] = {}
        self.prior_result = prior_result
        self.note_row = note_row
        self.update_fails = update_fails
        self.position = dict(OPEN_POSITION)
        if position_has_path:
            self.position["journal_path"] = "02 - Projects/Trading/04 - Journal/on-the-row.md"

    def rows_for(self, table, _filters):
        if table == "swayam_positions":
            return [self.position]
        if table == "swayam_trade_history":
            return [{"id": "hist-1"}] if self.prior_result else []
        if table == "swayam_journal_entries":
            return [{"md_path": self.note_row}] if self.note_row else []
        return []

    @property
    def client(self):
        store = self

        class C:
            def table(self, name):
                return FakeTable(store, name)

        return C()

    # the close path also reads these off `db`
    url = "https://example.invalid"
    key = "anon"


def _close(store, reason="target_hit"):
    with (
        patch("swayam.api.routes.positions.db", store),
        patch("swayam.api.routes.positions.append_exit_block") as journal,
    ):
        resp = client.post(
            "/api/positions/pos-retry-1/close",
            json={"close_reason": reason, "notes": "", "exit_legs": EXIT_LEGS},
        )
    return resp, journal


def test_a_first_close_records_exactly_one_result():
    store = FakeStore()
    resp, _journal = _close(store)

    assert resp.status_code == 200, resp.text
    assert len(store.inserts.get("swayam_trade_history", [])) == 1

    written = store.updates.get("swayam_positions", [])
    assert any(u.get("status") == "closed" for u in written)
    assert any("closed_at" in u for u in written), (
        "closed_at is written; migration 020 must have created the column"
    )


def test_a_second_close_does_not_record_a_second_result():
    """The retry heals the half-finished close rather than double counting."""
    store = FakeStore(prior_result=True)
    resp, _journal = _close(store)

    assert resp.status_code == 200, resp.text
    assert store.inserts.get("swayam_trade_history", []) == [], (
        "his record would have counted one trade twice"
    )
    assert any(u.get("status") == "closed" for u in store.updates.get("swayam_positions", []))


def test_the_exit_block_finds_the_note_even_when_the_row_never_carried_it():
    """Positions opened before 2026-09-09 have no journal_path on the row.

    The path was always recorded in swayam_journal_entries. Without this
    fallback the note keeps saying "Exit: to be filled at close" forever.
    """
    store = FakeStore(note_row="02 - Projects/Trading/04 - Journal/2026-09-09-trade01.md")
    resp, journal = _close(store)

    assert resp.status_code == 200, resp.text
    journal.assert_called_once()
    assert journal.call_args.kwargs["journal_rel_path"].endswith("2026-09-09-trade01.md")


def test_the_row_wins_over_the_index_when_both_exist():
    store = FakeStore(position_has_path=True, note_row="somewhere/else.md")
    resp, journal = _close(store)

    assert resp.status_code == 200
    assert journal.call_args.kwargs["journal_rel_path"].endswith("on-the-row.md")


def test_a_trade_with_no_note_at_all_still_closes():
    """The vault is unreachable from Cloud Run, so the note may be in the outbox.

    That is a real state, not an error. A note is not a trade.
    """
    store = FakeStore(note_row=None)
    resp, journal = _close(store)

    assert resp.status_code == 200, resp.text
    journal.assert_not_called()
    assert len(store.inserts.get("swayam_trade_history", [])) == 1


def test_a_note_that_cannot_be_written_does_not_fail_the_close():
    """A NOTE IS NOT A TRADE, and the exit side had never learned that.

    Migration 019 fixed this on the entry side: the vault is unreachable from
    Cloud Run, so the note write fails, and returning an error on a trade that
    is already recorded is what made him press the button again. The exit side
    still raised HTTP 500 with the position already closed in the database.
    """
    store = FakeStore(note_row="02 - Projects/Trading/04 - Journal/nowhere.md")

    with (
        patch("swayam.api.routes.positions.db", store),
        patch(
            "swayam.api.routes.positions.append_exit_block",
            side_effect=OSError("vault unreachable from this container"),
        ),
        patch("swayam.api.routes.positions.queue_journal_note", return_value=True) as queued,
        patch("swayam.api.routes.positions.mark_journal_status") as marked,
    ):
        resp = client.post(
            "/api/positions/pos-retry-1/close",
            json={"close_reason": "time_exit", "notes": "", "exit_legs": EXIT_LEGS},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "closed"

    # The result is still recorded, and the note is queued rather than lost.
    assert len(store.inserts.get("swayam_trade_history", [])) == 1
    queued.assert_called_once()
    assert queued.call_args.kwargs["kind"] == "close"
    payload = queued.call_args.kwargs["payload"]
    assert payload["journal_rel_path"].endswith("nowhere.md")
    assert payload["net_pnl_inr"] == resp.json()["realized_pnl_inr"]
    marked.assert_called_once_with("pos-retry-1", "pending")


def test_the_drainer_knows_how_to_finish_a_close_note():
    """A queued close note that nothing can drain is a note that is lost."""
    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "scripts" / "drain_journal_outbox.py"
    text = source.read_text(encoding="utf-8")

    assert 'row["kind"] == "close"' in text
    assert "append_exit_block(" in text
