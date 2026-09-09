"""Reading his 21 trade notes, and refusing to tidy them up.

These notes are the acceptance test for the backtester: `ROADMAP.md` §3
milestone 2 says it is not trusted until it reproduces what these trades
actually did. So the parser has to read them faithfully AND report their flaws
rather than smooth them over.

The notes were extracted from a spreadsheet by Antigravity, and the extraction
made real mistakes. Trade-08's booked orders are dated October when the trade
ran in January. Trade-16 has the literal word `None` where its prices should be.
Trade-21 has no opening legs at all. Thirteen of the twenty-one carry something
that would mislead a backtester.

Every test here uses a fixture written into a temporary folder. **None of them
reads his real vault**, for the same reason `conftest.cage_the_vault` exists.
"""

from datetime import date
from pathlib import Path

import pytest

from swayam.research.historical_trades import (
    LOT_SIZE_2022,
    load_all,
    missing_expiries,
    parse_note,
)

GOOD_NOTE = """---
trade_id: 1
tid: 10
entry_date: 2022-10-14
exit_date: 2022-10-21
strategy: "Balanced Calender Spread"
result: Win
pnl_rupees: 4548
---

# Trade 01

## Campaign Overview

- **Entry Date:** 2022-10-14
- **Capital Reserved / Used:** ₹500,000
- **Planned Stop Loss:** ₹-7,500
- **Planned Target:** ₹10,000

## Initial Position Legs

| Leg | Strike Price | Entry Premium | Quantity | Total Premium |
| :--- | :--- | :--- | :--- | :--- |
| Sell CE | 17800 | 28.9 | 200 | 5780 |
| Sell PE | 16700 | 72.15 | 200 | 14430 |
| Buy CE (HEDGE) | 18000 | -34.1 | 200 | -6820 |
| Buy PE (HEDGE) | 16500 | -74.72 | 200 | -14944 |

## Trade Adjustments

- **1st Adjustment:**
  - Legs Strike: Final SP | Premium: Premium | Qty: Quantity | Total: Total Premium
  - Sell PE Strike: 17100 | Premium: 63.05 | Qty: 200 | Total: 12610
  - Buy PE (HEDGE) Strike: 16900 | Premium: -72.86 | Qty: 200 | Total: -14572
- **2nd Adjustment:**

## Booked Orders / Exits

- 2022-10-18: Buy PE Strike 16700 @ ₹23.05
- 2022-10-21: Buy CE Strike 17800 @ ₹26.15
"""

# Trade-07's real flaw: the frontmatter says the trade ended in January 2022,
# eleven months before it started, while the booked orders say January 2023.
BACKWARDS_DATE_NOTE = """---
trade_id: 7
entry_date: 2022-12-27
exit_date: 2022-01-10
strategy: "Balanced Calender Spread"
result: Loss
pnl_rupees: -21000
---

# Trade 07

## Campaign Overview

- **Entry Date:** 2022-12-27

## Initial Position Legs

| Leg | Strike Price | Entry Premium | Quantity | Total Premium |
| :--- | :--- | :--- | :--- | :--- |
| Sell CE | 18700 | 35.1 | 250 | 8775 |
| Buy CE (HEDGE) | 18700 | -96.99 | 250 | -24247.5 |

## Booked Orders / Exits

- 2023-01-10: Buy CE Strike 18300 @ ₹10.55
"""

# Trade-16's real flaw: the extraction lost the numbers entirely.
NONE_PRICES_NOTE = """---
trade_id: 16
entry_date: 2023-03-10
strategy: "Iron Condor"
result: Loss
pnl_rupees: -2460
---

# Trade 16

## Initial Position Legs

| Leg | Strike Price | Entry Premium | Quantity | Total Premium |
| :--- | :--- | :--- | :--- | :--- |
| Sell CE | 17650 | 21.65 | 250 | 5412.5 |

## Booked Orders / Exits

- 2023-03-08: Buy CE Strike None @ ₹None
"""

# Trade-21's real flaw: no legs section at all.
NO_LEGS_NOTE = """---
trade_id: 21
entry_date: 2023-04-18
strategy: "Bull call spread"
result: Loss
pnl_rupees: -5800
---

# Trade 21

## Initial Position Legs

## Booked Orders / Exits
"""


@pytest.fixture
def folder(tmp_path):
    (tmp_path / "Trade-01 - 2022-10-14 - Balanced Calender Spread.md").write_text(
        GOOD_NOTE, encoding="utf-8"
    )
    (tmp_path / "Trade-07 - 2022-12-27 - Balanced Calender Spread.md").write_text(
        BACKWARDS_DATE_NOTE, encoding="utf-8"
    )
    (tmp_path / "Trade-16 - 2023-03-10 - Iron Condor.md").write_text(
        NONE_PRICES_NOTE, encoding="utf-8"
    )
    (tmp_path / "Trade-21 - 2023-04-18 - Bull call spread.md").write_text(
        NO_LEGS_NOTE, encoding="utf-8"
    )
    (tmp_path / "_Swing Trades Overview.md").write_text("not a trade", encoding="utf-8")
    return tmp_path


def test_a_complete_note_is_read_in_full(folder):
    trade = parse_note(folder / "Trade-01 - 2022-10-14 - Balanced Calender Spread.md")
    assert trade.trade_id == 1
    assert trade.entry_date == date(2022, 10, 14)
    assert trade.exit_date == date(2022, 10, 21)
    assert trade.result == "Win"
    assert trade.pnl_rupees == 4548
    assert trade.capital_used == 500000
    assert trade.planned_stop == -7500
    assert trade.planned_target == 10000


def test_every_opening_leg_is_read_with_its_side_and_hedging(folder):
    trade = parse_note(folder / "Trade-01 - 2022-10-14 - Balanced Calender Spread.md")
    assert len(trade.legs) == 4
    sold = [leg for leg in trade.legs if leg.action == "SELL"]
    bought = [leg for leg in trade.legs if leg.action == "BUY"]
    assert len(sold) == 2 and len(bought) == 2
    assert all(leg.is_hedge for leg in bought), "the bought legs are marked HEDGE"
    assert not any(leg.is_hedge for leg in sold)

    call = next(leg for leg in sold if leg.option_type == "CE")
    assert call.strike == 17800
    assert call.premium == 28.9
    assert call.quantity == 200
    assert call.lots == 4, f"200 units is four lots of {LOT_SIZE_2022}"


def test_an_adjustment_is_kept_as_its_own_block(folder):
    """A trade is a campaign. What changed mid-life is part of the record."""
    trade = parse_note(folder / "Trade-01 - 2022-10-14 - Balanced Calender Spread.md")
    assert len(trade.adjustments) == 1
    rolled = trade.adjustments[0]
    assert len(rolled) == 2, "the spreadsheet's leaked header row is not a leg"
    assert {leg.strike for leg in rolled} == {17100, 16900}


def test_booked_exits_are_read_with_their_dates(folder):
    trade = parse_note(folder / "Trade-01 - 2022-10-14 - Balanced Calender Spread.md")
    assert len(trade.exits) == 2
    assert trade.exits[0].on == date(2022, 10, 18)
    assert trade.exits[0].action == "BUY"
    assert trade.exits[0].strike == 16700
    assert trade.exits[0].price == 23.05
    assert trade.last_exit_date == date(2022, 10, 21)


def test_every_strike_the_campaign_touched_is_collected(folder):
    """Opening legs, adjustments and exits together, because it is one trade."""
    trade = parse_note(folder / "Trade-01 - 2022-10-14 - Balanced Calender Spread.md")
    assert trade.strikes == [16500, 16700, 16900, 17100, 17800, 18000]


def test_an_exit_date_before_the_entry_date_is_reported_not_corrected(folder):
    trade = parse_note(folder / "Trade-07 - 2022-12-27 - Balanced Calender Spread.md")
    assert trade.exit_date == date(2022, 1, 10), "his note is read as written"
    problems = trade.problems()
    assert any("before its entry date" in p for p in problems)
    assert any("disagrees with the last booked order" in p for p in problems)


def test_prices_the_extraction_lost_are_reported(folder):
    """`Strike None @ ₹None` is not an exit. It is a missing exit."""
    trade = parse_note(folder / "Trade-16 - 2023-03-10 - Iron Condor.md")
    assert trade.exits == []
    assert any("no booked exits" in p for p in trade.problems())


def test_a_note_with_no_legs_is_reported(folder):
    trade = parse_note(folder / "Trade-21 - 2023-04-18 - Bull call spread.md")
    assert trade.legs == []
    assert any("no opening legs" in p for p in trade.problems())


def test_a_sound_note_reports_no_problems(folder):
    trade = parse_note(folder / "Trade-01 - 2022-10-14 - Balanced Calender Spread.md")
    assert trade.problems() == []


def test_two_legs_at_one_strike_and_side_can_only_be_a_calendar(folder):
    """Trade-07 sells the 18700 call and buys the 18700 call."""
    trade = parse_note(folder / "Trade-07 - 2022-12-27 - Balanced Calender Spread.md")
    assert trade.is_calendar is True
    assert missing_expiries([trade]) == [trade]


def test_the_folder_loads_in_order_and_skips_what_is_not_a_trade(folder):
    trades = load_all(folder)
    assert [trade.trade_id for trade in trades] == [1, 7, 16, 21]


def test_nothing_in_this_module_writes(folder):
    """It reads his records. It must never be the thing that changes them."""
    before = {path: path.read_bytes() for path in folder.glob("*.md")}
    load_all(folder)
    after = {path: path.read_bytes() for path in folder.glob("*.md")}
    assert before == after
