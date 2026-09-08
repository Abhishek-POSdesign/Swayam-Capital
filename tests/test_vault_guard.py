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

    real_journal_dir = settings.vault_path / "02 - Projects" / "Trading" / "04 - Journal"
    assert not (real_journal_dir / Path(rel).name).exists(), (
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
