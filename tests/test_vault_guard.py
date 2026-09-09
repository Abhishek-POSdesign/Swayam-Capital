"""The vault cage, proven rather than assumed.

Twenty-six fabricated trade notes were found in Abhishek's live Second Brain on
2026-09-08, written there by test runs. Twenty-two of them had no database row
at all. These tests exist so that can never happen quietly again.
"""

from pathlib import Path

import pytest

from swayam.api.journal_writer import (
    JournalWriteError,
    _default_vault_base,
    write_new_trade_journal,
)
from swayam.config import settings


def _spread():
    return {
        "strategy_name": "Bull Call Spread",
        "underlying": "NIFTY",
        "expiry_date": "2026-09-15",
        "legs": [
            {
                "strike": 25000,
                "option_type": "CE",
                "direction": "buy",
                "quantity_lots": 1,
                "lot_size": 65,
                "entry_premium": 150.0,
            }
        ],
        "greeks": {},
        "max_loss_inr": 9750.0,
        "max_profit_inr": 14000.0,
        "net_debit_credit_inr": -9750.0,
        "breakeven_points": [25150],
    }


def _validation():
    return {"checks": [], "verdict": "pass"}


def test_a_trade_note_lands_in_the_cage_not_in_his_vault(cage_the_vault):
    """The default write base is the temporary cage while a test is running."""
    rel = write_new_trade_journal(
        position_id="cage-check",
        spread_data=_spread(),
        validation_data=_validation(),
        current_spot=24867.5,
        margin_base_inr=971002.38,
    )

    written = Path(cage_the_vault) / rel
    assert written.exists(), "the note should still be written, just not to his vault"
    assert str(settings.vault_path) not in str(written)

    # Compare the FILE, not the name. He now has real trades of his own, and a
    # note written today legitimately shares the day's naming pattern.
    real_journal_dir = settings.vault_path / "02 - Projects" / "Trading" / "04 - Journal"
    real_twin = real_journal_dir / Path(rel).name
    if real_twin.exists():
        assert real_twin.read_text(encoding="utf-8") != written.read_text(encoding="utf-8"), (
            "a test just wrote a trade note into his real Second Brain"
        )


@pytest.mark.real_vault
def test_the_cage_refuses_rather_than_falling_back(request):
    """With the fixture opted out, the writer refuses instead of using his vault.

    This is the backstop. If someone deletes the autouse fixture, the source
    itself still stops a test run from reaching his record, and says why.
    """
    assert request.node.get_closest_marker("real_vault") is not None

    with pytest.raises(JournalWriteError) as excinfo:
        _default_vault_base()

    message = str(excinfo.value)
    assert "BLOCKED" in message
    assert str(settings.vault_path) in message


def test_an_unreachable_vault_is_refused_not_invented(tmp_path):
    """His first ever paper trade's note was reported written and never existed.

    VAULT_PATH is unset on Cloud Run, so config falls back to the Windows path
    for his G: drive. On Linux that is a RELATIVE folder whose name merely
    contains a colon and backslashes. `mkdir(parents=True)` created it inside
    the container, the write succeeded, the row was marked
    `journal_status = 'written'`, and the note died with the container.

    The outbox exists for exactly this case. It was never reached because
    nothing ever failed.
    """
    missing = tmp_path / "not-a-vault"
    assert not missing.exists()

    with pytest.raises(JournalWriteError) as excinfo:
        write_new_trade_journal(
            position_id="unreachable-vault",
            spread_data=_spread(),
            validation_data=_validation(),
            current_spot=23557.05,
            margin_base_inr=970538.0,
            vault_path=missing,
        )

    assert "not reachable" in str(excinfo.value)
    assert "outbox" in str(excinfo.value)
    assert not missing.exists(), "it invented a vault instead of refusing"


def test_a_real_vault_still_gets_its_journal_folder_created(tmp_path):
    """We create the journal folder inside a real vault. We never create the vault."""
    vault = tmp_path / "vault"
    vault.mkdir()

    rel = write_new_trade_journal(
        position_id="real-vault",
        spread_data=_spread(),
        validation_data=_validation(),
        current_spot=23557.05,
        margin_base_inr=970538.0,
        vault_path=vault,
    )

    assert (vault / rel).exists()
    assert (vault / "02 - Projects" / "Trading" / "04 - Journal").is_dir()
