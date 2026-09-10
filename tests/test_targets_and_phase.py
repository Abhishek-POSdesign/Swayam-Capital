"""Targets, the phase, and the two scripts he runs himself.

WHAT THESE PROVE
----------------
1. A leg's target is judged on the side he would actually GET: a bought leg on
   the bid, a sold leg on the ask. Getting that backwards would tell him a
   short call had hit its profit target while it was running against him.
2. A blank box is silence. The one exception is a blank trade loss, which falls
   back to rule 1 read live, and says that it did.
3. Rule 1 unavailable means no loss signal at all, never a guessed cap.
4. The phase answers "not started" when it cannot read the table, which is true
   today and is the safe direction.
5. A note written while the phase is testing lands in the Terminal tests
   subfolder OF THE CAGED VAULT, never in his real journal folder.
6. The marking script skips an open trade. His condor 7cd4d017 is open on
   purpose, and no script may touch it.

None of these needs the database, the network or his vault.
"""

from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest

from swayam.api.journal_writer import journal_rel_dir, write_new_trade_journal
from swayam.config import settings
from swayam.services.phase import Phase, _parse_stamp
from swayam.services.targets import (
    STATE_ALERT,
    STATE_QUIET,
    STATE_RUNNING,
    evaluate_leg,
    evaluate_position,
    evaluate_trade,
)

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def bought(**over):
    """A leg he BOUGHT. Its mark is the bid, because selling is what closes it."""
    leg = {
        "sequence": 1,
        "direction": "buy",
        "strike": 24200,
        "option_type": "CE",
        "status": "open",
        "entry_premium": 34.5,
        "quantity_units": 65,
        "mark": 30.6,
        "mark_side": "bid",
    }
    leg.update(over)
    return leg


def sold(**over):
    """A leg he SOLD. Its mark is the ask, because buying back is what closes it."""
    leg = {
        "sequence": 3,
        "direction": "sell",
        "strike": 23800,
        "option_type": "CE",
        "status": "open",
        "entry_premium": 109.15,
        "quantity_units": 65,
        "mark": 98.75,
        "mark_side": "ask",
    }
    leg.update(over)
    return leg


# ---------------------------------------------------------------- one leg


def test_a_bought_leg_takes_profit_when_the_bid_rises_to_his_price():
    got = evaluate_leg(bought(target_price=38.0, mark=38.0))
    assert got is not None
    assert got["kind"] == "profit"
    assert got["leg_label"] == "24,200 CE"
    assert got["level"] == 38.0


def test_a_bought_leg_cuts_loss_when_the_bid_falls_to_his_price():
    got = evaluate_leg(bought(stop_price=20.0, mark=19.5))
    assert got is not None and got["kind"] == "loss"


def test_a_sold_leg_takes_profit_when_the_ask_FALLS_to_his_price():
    """The direction that is easiest to get backwards, and the costliest.

    A short call is winning when its price comes DOWN. If profit were tested as
    "mark at or above the target", his condor's short call would announce a
    profit target exactly when it was running against him.
    """
    got = evaluate_leg(sold(target_price=50.0, mark=49.0))
    assert got is not None and got["kind"] == "profit"

    # And the same price, going the other way, is a LOSS, not a profit.
    got = evaluate_leg(sold(target_price=50.0, stop_price=160.0, mark=161.0))
    assert got is not None and got["kind"] == "loss"


def test_a_leg_between_its_two_prices_says_nothing():
    assert evaluate_leg(bought(target_price=38.0, stop_price=20.0, mark=30.6)) is None
    assert evaluate_leg(sold(target_price=50.0, stop_price=160.0, mark=98.75)) is None


def test_a_blank_box_is_silence_not_zero():
    """An empty box must never behave like a target of zero."""
    assert evaluate_leg(bought(target_price=None, stop_price=None, mark=0.05)) is None
    assert evaluate_leg(sold(target_price=None, stop_price=None, mark=0.05)) is None


def test_a_leg_that_could_not_be_marked_says_nothing():
    """No mark, no verdict. Never a target judged against a stale last trade."""
    assert evaluate_leg(bought(target_price=38.0, mark=None)) is None


def test_a_squared_off_leg_is_not_re_judged():
    """It was closed at a real price on a real day; it cannot reach a target now."""
    assert evaluate_leg(bought(target_price=1.0, status="closed", mark=30.6)) is None


# -------------------------------------------------------------- the trade


def test_the_trade_takes_profit_on_the_net_after_charges_both_ways():
    alert, _, _ = evaluate_trade(
        net_if_exit_now_inr=7200.0,
        target_profit_inr=7000.0,
        target_loss_inr=None,
        rule1_cap_inr=9711.0,
    )
    assert alert is not None and alert["kind"] == "profit" and alert["scope"] == "trade"


def test_a_blank_trade_loss_falls_back_to_rule_one_read_live():
    alert, effective, source = evaluate_trade(
        net_if_exit_now_inr=-9800.0,
        target_profit_inr=None,
        target_loss_inr=None,
        rule1_cap_inr=9711.0,
    )
    assert alert is not None and alert["kind"] == "loss"
    assert alert["from_rule1"] is True
    assert effective == 9711.0
    assert source == "rule1"


def test_his_own_loss_figure_beats_rule_one():
    alert, effective, source = evaluate_trade(
        net_if_exit_now_inr=-5100.0,
        target_profit_inr=None,
        target_loss_inr=5000.0,
        rule1_cap_inr=9711.0,
    )
    assert alert is not None and alert["from_rule1"] is False
    assert effective == 5000.0 and source == "his"


def test_a_minus_sign_he_typed_is_emphasis_not_a_direction():
    """-5000 in the loss box means a loss of five thousand, not a profit."""
    alert, effective, _ = evaluate_trade(
        net_if_exit_now_inr=-5100.0,
        target_profit_inr=None,
        target_loss_inr=-5000.0,
        rule1_cap_inr=None,
    )
    assert alert is not None and alert["kind"] == "loss"
    assert effective == 5000.0


def test_no_rule_one_means_no_loss_signal_never_a_guessed_cap():
    alert, effective, source = evaluate_trade(
        net_if_exit_now_inr=-999999.0,
        target_profit_inr=None,
        target_loss_inr=None,
        rule1_cap_inr=None,
    )
    assert alert is None
    assert effective is None
    assert source == "none"


def test_a_trade_that_could_not_be_valued_says_nothing():
    alert, _, _ = evaluate_trade(
        net_if_exit_now_inr=None,
        target_profit_inr=7000.0,
        target_loss_inr=9711.0,
        rule1_cap_inr=9711.0,
    )
    assert alert is None


# ------------------------------------------------------- the whole position


def _evaluate(legs, **over):
    args = dict(
        legs=legs,
        net_if_exit_now_inr=-1480.0,
        target_profit_inr=None,
        target_loss_inr=None,
        targets_set_at=None,
        rule1_cap_inr=9711.0,
        legs_open=len([l for l in legs if l.get("status", "open") == "open"]),
        market_state="live",
    )
    args.update(over)
    return evaluate_position(**args)


def test_a_running_trade_with_nothing_reached_is_running():
    out = _evaluate([bought(target_price=38.0), sold(stop_price=160.0)])
    assert out["state"] == STATE_RUNNING
    assert out["alerts"] == []
    assert out["targets"]["legs_with_targets"] == 2
    assert out["targets"]["loss_source"] == "rule1"


def test_one_reached_leg_makes_the_whole_trade_an_alert():
    out = _evaluate([bought(target_price=30.0), sold(stop_price=160.0)])
    assert out["state"] == STATE_ALERT
    assert [a["leg_label"] for a in out["alerts"]] == ["24,200 CE"]


def test_nothing_open_is_quiet_whatever_the_targets_say():
    out = _evaluate([bought(target_price=1.0, status="closed")], legs_open=0)
    assert out["state"] == STATE_QUIET


def test_the_reply_carries_the_market_state_it_was_judged_in():
    """So the band can say "at the close" and stop blinking over a frozen number."""
    out = _evaluate([bought()], market_state="closing")
    assert out["evaluated_at_market_state"] == "closing"


# ------------------------------------------------------------- the phase


def test_an_unreadable_phase_table_reads_as_not_started():
    p = Phase(None, None, None, source="unreadable", unavailable_reason="no such table")
    assert p.paper_trading_started is False
    assert p.testing is True
    assert p.provenance_for_new_position == "terminal_test"


def test_a_null_timestamp_is_not_started():
    p = Phase(None, None, None, source="table")
    assert p.provenance_for_new_position == "terminal_test"


def test_a_timestamp_means_paper_trading_has_begun():
    p = Phase(datetime(2026, 10, 1, tzinfo=timezone.utc), "Abhishek", None, source="table")
    assert p.paper_trading_started is True
    assert p.provenance_for_new_position == "live"
    assert p.to_dict()["paper_trading_started_at"].startswith("2026-10-01")


def test_a_stamp_that_cannot_be_parsed_is_none_never_today():
    assert _parse_stamp("not a date") is None
    assert _parse_stamp("") is None
    assert _parse_stamp(None) is None
    assert _parse_stamp("2026-10-01T04:00:00Z") is not None


# ------------------------------------------- the note, in the caged vault


def _spread():
    return {
        "strategy_name": "Iron Condor",
        "underlying": "NIFTY",
        "expiry_date": "2026-09-29",
        "legs": [
            {
                "strike": 23800,
                "option_type": "CE",
                "direction": "sell",
                "quantity_lots": 1,
                "lot_size": 65,
                "entry_premium": 109.15,
            }
        ],
        "greeks": {},
        "payoff_curve": {"max_loss_inr": 16783.0, "max_profit_inr": 9217.0},
    }


def test_a_terminal_test_note_lands_in_its_own_subfolder_of_the_cage(cage_the_vault):
    rel = write_new_trade_journal(
        position_id="phase-check",
        spread_data=_spread(),
        validation_data={"checks": [], "verdict": "pass"},
        current_spot=23389.25,
        margin_base_inr=971002.38,
        terminal_test=True,
    )

    assert rel.startswith(journal_rel_dir(True))
    assert "Terminal tests" in rel

    written = Path(cage_the_vault) / rel
    assert written.exists()
    # THE CAGE STILL HOLDS. A new folder must not become a new way into his vault.
    assert str(settings.vault_path) not in str(written)
    assert "provenance: terminal_test" in written.read_text(encoding="utf-8")


def test_a_live_note_stays_in_the_journal_folder(cage_the_vault):
    rel = write_new_trade_journal(
        position_id="phase-check-live",
        spread_data=_spread(),
        validation_data={"checks": [], "verdict": "pass"},
        current_spot=23389.25,
        margin_base_inr=971002.38,
        terminal_test=False,
    )
    assert "Terminal tests" not in rel
    assert (Path(cage_the_vault) / rel).read_text(encoding="utf-8").count("provenance: live") == 1


# ------------------------------------------------ the marking script, dry


def test_the_marking_script_skips_the_open_condor():
    """7cd4d017 is open on purpose. No script marks, closes or edits it."""
    from mark_terminal_tests import _new_rel_path, candidates

    rows = [
        {
            "id": "7cd4d017-2c92-445a-a348-28f395c03db8",
            "strategy_name": "Iron Condor",
            "status": "open",
            "provenance": "live",
            "opened_at": "2026-09-10T08:15:49+00:00",
            "journal_path": "02 - Projects/Trading/04 - Journal/2026-09-10-trade01.md",
        },
        {
            "id": "03a1b63d-1111-2222-3333-444444444444",
            "strategy_name": "Bear Call Spread",
            "status": "closed",
            "provenance": "live",
            "opened_at": "2026-09-10T08:02:29+00:00",
            "journal_path": "02 - Projects/Trading/04 - Journal/2026-09-10-trade02.md",
        },
        {
            "id": "quarantined",
            "strategy_name": "a build made this",
            "status": "archived",
            "provenance": "build_test",
            "opened_at": "2026-09-01T00:00:00+00:00",
            "journal_path": None,
        },
    ]

    to_mark, skipped = candidates(rows, None)

    assert [r["id"] for r in to_mark] == ["03a1b63d-1111-2222-3333-444444444444"]
    reasons = {r["id"]: why for r, why in skipped}
    assert "only once it is closed" in reasons["7cd4d017-2c92-445a-a348-28f395c03db8"]
    assert "already marked build_test" in reasons["quarantined"]

    assert _new_rel_path(rows[1]["journal_path"]) == (
        "02 - Projects/Trading/04 - Journal/Terminal tests/2026-09-10-trade02.md"
    )


def test_the_marking_script_leaves_a_trade_taken_after_the_line_alone():
    from mark_terminal_tests import candidates

    started = datetime(2026, 10, 1, tzinfo=timezone.utc)
    rows = [
        {
            "id": "after",
            "status": "closed",
            "provenance": "live",
            "opened_at": "2026-10-02T04:00:00+00:00",
            "journal_path": None,
        },
        {
            "id": "before",
            "status": "closed",
            "provenance": "live",
            "opened_at": "2026-09-10T08:00:00+00:00",
            "journal_path": None,
        },
    ]
    to_mark, skipped = candidates(rows, started)
    assert [r["id"] for r in to_mark] == ["before"]
    assert "after paper trading started" in dict((r["id"], w) for r, w in skipped)["after"]


def test_a_note_already_in_the_subfolder_is_not_moved_twice():
    from mark_terminal_tests import _new_rel_path

    already = "02 - Projects/Trading/04 - Journal/Terminal tests/2026-09-10-trade02.md"
    assert _new_rel_path(already) == already
    # A path this script does not understand is left alone rather than guessed at.
    assert _new_rel_path("somewhere/else/note.md") is None
    assert _new_rel_path(None) is None


# ------------------------------------- the note the script is about to move


def test_the_note_is_found_the_way_the_drainer_finds_it():
    """Four of his five closed trades carry no journal_path on the row.

    Their notes exist all the same: they were queued in the outbox and written
    later by the drainer, which records the path in swayam_journal_entries and
    does not always put it back on the position. Reading only the row made the
    dry run say "no note recorded" for 6b4f364e, 63ce13e6, 03a1b63d and
    8030ed03, and applying it would have marked four trades while leaving four
    real notes sitting in his journal folder.
    """
    from mark_terminal_tests import resolve_note

    index = {"from-index": "02 - Projects/Trading/04 - Journal/2026-09-09-trade02.md"}

    # The row's own path wins when it has one.
    on_row = {"id": "on-row", "journal_path": "02 - Projects/Trading/04 - Journal/2026-09-09-trade01.md"}
    assert resolve_note(on_row, index).endswith("2026-09-09-trade01.md")

    # And the journal index answers when the row does not. This is the fault.
    from_index = {"id": "from-index", "journal_path": None}
    assert resolve_note(from_index, index).endswith("2026-09-09-trade02.md")

    # Neither has one: still None, so nothing is invented and nothing is moved.
    assert resolve_note({"id": "nowhere", "journal_path": None}, index) is None


def test_a_windows_path_is_read_as_a_vault_path():
    """A path stored with backslashes still finds its note."""
    from mark_terminal_tests import resolve_note

    row = {"id": "w", "journal_path": "02 - Projects\\Trading\\04 - Journal\\2026-09-10-trade02.md"}
    assert resolve_note(row, {}) == "02 - Projects/Trading/04 - Journal/2026-09-10-trade02.md"


def test_the_dry_run_names_a_note_for_every_one_of_his_five():
    """His real five, one with the path on the row and four only in the index.

    Every one must come out with a note to move. A row that reports no note is
    a row whose note would be left behind in `04 - Journal/`.
    """
    from mark_terminal_tests import _new_rel_path, candidates, resolve_note

    J = "02 - Projects/Trading/04 - Journal"
    rows = [
        {"id": "fdc785f4", "strategy_name": "Bull Call Spread", "status": "closed",
         "provenance": "live", "opened_at": "2026-09-09T08:37:12+00:00",
         "journal_path": f"{J}/2026-09-09-trade01.md"},
        {"id": "6b4f364e", "strategy_name": "Iron Condor", "status": "closed",
         "provenance": "live", "opened_at": "2026-09-09T09:10:00+00:00", "journal_path": None},
        {"id": "63ce13e6", "strategy_name": "Bull Put Spread", "status": "closed",
         "provenance": "live", "opened_at": "2026-09-09T09:40:00+00:00", "journal_path": None},
        {"id": "03a1b63d", "strategy_name": "Bear Call Spread", "status": "closed",
         "provenance": "live", "opened_at": "2026-09-10T08:02:29+00:00", "journal_path": None},
        {"id": "8030ed03", "strategy_name": "Bull Put Spread", "status": "closed",
         "provenance": "live", "opened_at": "2026-09-10T08:40:48+00:00", "journal_path": None},
        # Open on purpose, and skipped whatever its note says.
        {"id": "7cd4d017", "strategy_name": "Iron Condor", "status": "open",
         "provenance": "live", "opened_at": "2026-09-10T08:15:49+00:00",
         "journal_path": f"{J}/2026-09-10-trade01.md"},
    ]
    index = {
        "6b4f364e": f"{J}/2026-09-09-trade02.md",
        "63ce13e6": f"{J}/2026-09-09-trade03.md",
        "03a1b63d": f"{J}/2026-09-10-trade02.md",
        "8030ed03": f"{J}/2026-09-10-trade03.md",
    }

    to_mark, skipped = candidates(rows, None)
    assert len(to_mark) == 5
    assert [r["id"] for r, _ in skipped] == ["7cd4d017"]

    moves = {}
    for row in to_mark:
        old = resolve_note(row, index)
        assert old is not None, f"{row['id']} would have been marked with its note left behind"
        moves[row["id"]] = _new_rel_path(old)

    assert moves == {
        "fdc785f4": f"{J}/Terminal tests/2026-09-09-trade01.md",
        "6b4f364e": f"{J}/Terminal tests/2026-09-09-trade02.md",
        "63ce13e6": f"{J}/Terminal tests/2026-09-09-trade03.md",
        "03a1b63d": f"{J}/Terminal tests/2026-09-10-trade02.md",
        "8030ed03": f"{J}/Terminal tests/2026-09-10-trade03.md",
    }
    # All six of his notes are accounted for: five moved, and the open condor's
    # left exactly where it is.
    assert len(set(moves.values())) == 5
