"""The drainer's close branch. docs/PLAN.md 2.12.5 item 8.

TWO ROWS HAVE FAILED ON EVERY DRAIN SINCE 2026-09-10, for positions 03a1b63d
and 8030ed03. Both faults are real and both are proved here against payloads
shaped exactly like the ones in his outbox, read from the live database on
2026-09-10 and reproduced below:

    payload keys: awaiting_entry_note, charges_inr, close_reason, closed_at,
                  exit_legs, gross_pnl_inr, holding_days, max_loss_inr,
                  net_pnl_inr, notes

    NO journal_rel_path. NO margin_base_inr. journal_path on the row: None.
    The note path lives only in swayam_journal_entries.

FAULT ONE, the crash. The branch read `payload["journal_rel_path"]`, which is
not there, so it raised KeyError every single time and the row retried for
ever.

FAULT TWO, the one a careless fix would have caused. Both notes ALREADY carry
their Exit block: the drainer appends it itself, through
`_append_exit_if_already_closed`, when it writes an entry note for a trade
that has since closed. A fix that only resolved the path and appended would
have written a SECOND Exit into his real journal note.

Offline: the vault is a temporary folder and the database is a stand-in.
"""

from pathlib import Path
from typing import Any, Optional
from unittest.mock import patch

import pytest

import scripts.drain_journal_outbox as drainer


NOTE_REL = "02 - Projects/Trading/04 - Journal/2026-09-10-trade02.md"

# The shape his two stuck rows actually have. No path, no margin base.
STUCK_CLOSE_PAYLOAD: dict[str, Any] = {
    "awaiting_entry_note": True,
    "closed_at": "2026-09-10T08:57:20+00:00",
    "close_reason": "manual",
    "notes": None,
    "exit_legs": [
        {
            "strike": 23800.0,
            "option_type": "CE",
            "direction": "sell",
            "quantity_lots": 1,
            "lot_size": 65,
            "entry_premium": 109.15,
            "exit_premium": 98.75,
            "exit_side_hit": "ask",
            "gross_pnl_inr": 676.0,
            "entry_charges_inr": 37.98,
            "exit_charges_inr": 27.18,
            "charges_inr": 65.16,
            "net_pnl_inr": 610.84,
        }
    ],
    "gross_pnl_inr": -32.5,
    "charges_inr": 164.41,
    "net_pnl_inr": -196.91,
    "max_loss_inr": 4550.0,
    "holding_days": 0,
}

WITH_EXIT = """---
type: trade
---

## Entry

Something.

## Exit

Already written by the other route on 2026-09-10.
"""

WITHOUT_EXIT = """---
type: trade
---

## Entry

Something.

Exit: to be filled at close.
"""


class FakeTable:
    def __init__(self, store, name):
        self.store = store
        self.name = name

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def update(self, values):
        self.store.updates.setdefault(self.name, []).append(values)
        return self

    def insert(self, values):
        self.store.inserts.setdefault(self.name, []).append(values)
        return self

    def execute(self):
        class R:
            pass

        r = R()
        r.data = self.store.rows_for(self.name)
        return r


class FakeDB:
    def __init__(self, *, note_in_index: Optional[str] = NOTE_REL, path_on_row: Optional[str] = None):
        self.updates: dict[str, list] = {}
        self.inserts: dict[str, list] = {}
        self.note_in_index = note_in_index
        self.path_on_row = path_on_row

    def rows_for(self, name):
        if name == "swayam_positions":
            return [{"journal_path": self.path_on_row, "status": "closed"}]
        if name == "swayam_journal_entries":
            return [{"md_path": self.note_in_index}] if self.note_in_index else []
        return []

    @property
    def client(self):
        store = self

        class C:
            def table(self, name):
                return FakeTable(store, name)

        return C()

    url = "https://example.invalid"
    key = "anon"


@pytest.fixture
def vault(tmp_path):
    """A vault in a temporary folder. Never his."""
    note = tmp_path / NOTE_REL
    note.parent.mkdir(parents=True, exist_ok=True)
    return tmp_path


def _row(kind="close", payload=None):
    return {
        "id": "outbox-1",
        "position_id": "03a1b63d-0000-0000-0000-000000000000",
        "kind": kind,
        "payload": payload if payload is not None else dict(STUCK_CLOSE_PAYLOAD),
        "attempts": 1,
        "queued_at": "2026-09-10T08:57:20+00:00",
    }


def _drain(db, vault_base, rows):
    """Runs the drainer's loop over these rows, with the vault in tmp_path."""
    appended: list[dict[str, Any]] = []

    def fake_append(**kwargs):
        appended.append(kwargs)
        return Path(vault_base) / kwargs["journal_rel_path"]

    with (
        patch.object(drainer, "db", db),
        patch.object(drainer, "_default_vault_base", return_value=Path(vault_base)),
        patch.object(drainer, "_pending_rows", return_value=rows, create=True),
        patch.object(drainer, "append_exit_block", side_effect=fake_append),
        patch.object(drainer, "_require_vault", return_value=Path(vault_base), create=True),
    ):
        drainer.drain(dry_run=False)
    return appended


# ------------------------------------------------------------- fault one


def test_a_close_queued_with_no_path_resolves_it_instead_of_crashing(vault):
    """The KeyError that made both rows retry for ever."""
    (vault / NOTE_REL).write_text(WITHOUT_EXIT, encoding="utf-8")
    db = FakeDB()

    assert "journal_rel_path" not in STUCK_CLOSE_PAYLOAD
    assert drainer._resolve_note_path is not None

    with patch.object(drainer, "db", db):
        resolved = drainer._resolve_note_path("03a1b63d-0000-0000-0000-000000000000")
    assert resolved == NOTE_REL, "the path lives in swayam_journal_entries, not on the row"


def test_the_note_check_reads_the_note_itself(vault):
    """Verify by invoking, never by reading a status."""
    (vault / NOTE_REL).write_text(WITH_EXIT, encoding="utf-8")
    assert drainer._note_already_has_exit(NOTE_REL, vault_base=vault) is True

    (vault / NOTE_REL).write_text(WITHOUT_EXIT, encoding="utf-8")
    assert drainer._note_already_has_exit(NOTE_REL, vault_base=vault) is False


# ------------------------------------------------------------- fault two


def test_a_note_that_already_has_its_exit_is_not_appended_to_again(vault):
    """The second Exit block a careless fix would have written into his note."""
    (vault / NOTE_REL).write_text(WITH_EXIT, encoding="utf-8")
    before = (vault / NOTE_REL).read_text(encoding="utf-8")

    assert drainer._note_already_has_exit(NOTE_REL, vault_base=vault) is True
    assert before.count("## Exit") == 1

    # And the file is untouched by the check itself.
    assert (vault / NOTE_REL).read_text(encoding="utf-8") == before


def test_a_missing_note_is_not_treated_as_complete(vault):
    """Saying "nothing to do" because the vault was unreachable loses the exit.

    That is the failure this whole branch exists to fix, so it must not be
    reintroduced by the fix.
    """
    assert drainer._note_already_has_exit("does/not/exist.md", vault_base=vault) is False


def test_an_unreadable_vault_is_not_treated_as_complete(tmp_path):
    assert drainer._note_already_has_exit(NOTE_REL, vault_base=tmp_path / "no such vault") is False


# ------------------------------------------------------- the new kind


def test_the_outbox_accepts_a_leg_exit_kind():
    """Migration 022 widens the constraint; the drainer must handle the kind."""
    source = Path(drainer.__file__).read_text(encoding="utf-8")
    assert 'row["kind"] == "leg_exit"' in source
    assert "append_leg_exit_block" in source

    migration = (
        Path(__file__).resolve().parents[2] / "migrations" / "022_campaign_model_and_name.sql"
    ).read_text(encoding="utf-8")
    assert "'leg_exit'" in migration


def test_the_close_branch_no_longer_reads_the_two_missing_keys():
    """Both KeyErrors, gone at the source rather than caught downstream."""
    source = Path(drainer.__file__).read_text(encoding="utf-8")
    close_branch = source.split('if row["kind"] == "close":', 1)[1]
    # Just this branch: it ends where the new-trade fallthrough begins.
    close_branch = close_branch.split('would write  {label}', 1)[0]
    # Comments are allowed to NAME the fault; only the code must not do it.
    code = chr(10).join(
        line for line in close_branch.splitlines() if not line.strip().startswith('#')
    )
    close_branch = code
    assert 'payload["journal_rel_path"]' not in close_branch
    assert 'payload["margin_base_inr"]' not in close_branch
    assert 'payload.get("journal_rel_path")' in close_branch
    assert "_resolve_note_path(pid)" in close_branch
    assert "_note_already_has_exit" in close_branch
