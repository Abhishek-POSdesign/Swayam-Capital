"""Charges belong to the leg, not to the trade.

His instruction, 2026-09-09:

    "The charges should not be recorded as per the trade. Charges are recorded
    as per the leg. The buy leg has its own charges, and the sell leg has its
    own charges. Why would squaring one leg charge for the whole trade?...
    Whenever we buy or sell, the charges will be calculated then and there."

What this replaced: a flat Rs 150 multiplied by the number of legs, applied once
when the trade closed, with nothing charged at entry at all.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from swayam.services.charges import (
    ChargeableLeg,
    ChargeScheduleUnavailable,
    charge_for_leg,
    compute_charges,
    opposite,
    side_from_direction,
)

LOT = 65
A_TRADING_DAY = date(2026, 9, 8)


def _condor_entry():
    return [
        ChargeableLeg(side="sell", price_per_unit=Decimal("90"), quantity_units=LOT),
        ChargeableLeg(side="buy", price_per_unit=Decimal("45"), quantity_units=LOT),
        ChargeableLeg(side="sell", price_per_unit=Decimal("85"), quantity_units=LOT),
        ChargeableLeg(side="buy", price_per_unit=Decimal("45"), quantity_units=LOT),
    ]


def test_costing_leg_by_leg_is_exact_not_an_approximation():
    """The whole design rests on this. If it were lossy, per-leg would be wrong.

    Brokerage is charged per order and every other line is a percentage of that
    leg's own turnover, so the parts sum to the whole. To the paisa.
    """
    legs = _condor_entry()

    together = compute_charges(legs, on=A_TRADING_DAY).total_inr
    separately = sum(
        charge_for_leg(
            side=leg.side,
            price_per_unit=leg.price_per_unit,
            quantity_units=leg.quantity_units,
            on=A_TRADING_DAY,
        ).total_inr
        for leg in legs
    )

    assert together == separately
    assert together == Decimal("120.71")


def test_a_sold_leg_costs_more_than_a_bought_leg_at_the_same_price():
    """Securities transaction tax falls on the sell side only.

    This is why a charge cannot belong to the trade. Squaring off the bought
    leg of a spread and squaring off the sold leg cost different amounts.
    """
    price = Decimal("90")
    sold = charge_for_leg(side="sell", price_per_unit=price, quantity_units=LOT, on=A_TRADING_DAY)
    bought = charge_for_leg(side="buy", price_per_unit=price, quantity_units=LOT, on=A_TRADING_DAY)

    assert sold.total_inr > bought.total_inr


def test_entry_and_exit_are_charged_on_their_own_dates():
    """A trade carried across 1 April 2026 straddles two rate schedules.

    Securities transaction tax on options rose from 0.10% to 0.15% of premium
    that day. Charging the exit on the entry's schedule, or the other way
    round, would misstate the cost of every trade held over a rate change.
    """
    before = charge_for_leg(
        side="sell", price_per_unit=Decimal("90"), quantity_units=LOT, on=date(2022, 6, 1)
    )
    after = charge_for_leg(
        side="sell", price_per_unit=Decimal("90"), quantity_units=LOT, on=date(2026, 9, 8)
    )

    assert before.schedule_version != after.schedule_version
    assert after.total_inr > before.total_inr


def test_a_leg_whose_side_cannot_be_read_is_refused_rather_than_guessed():
    """Defaulting to a buy would drop the whole of the sell-side tax."""
    assert side_from_direction("BUY") == "buy"
    assert side_from_direction("short") == "sell"
    assert opposite("buy") == "sell"
    assert opposite("sell") == "buy"

    with pytest.raises(ChargeScheduleUnavailable):
        side_from_direction("")
    with pytest.raises(ChargeScheduleUnavailable):
        side_from_direction("hold")


def test_the_flat_one_hundred_and_fifty_is_gone():
    """The tenth invented constant. A source-level guard, like the ninth.

    ESTIMATED_CHARGE_PER_LEG_INR was Rs 150 a leg, booked once at the close. On
    a one-lot condor that is Rs 600 against a real round trip of about Rs 223,
    and the error grew with the number of legs rather than with the size of the
    trade, which is backwards.
    """
    from swayam.config import settings

    assert not hasattr(settings, "estimated_charge_per_leg_inr")

    root = Path(__file__).resolve().parents[1] / "src" / "swayam"
    for name in ("api/routes/positions.py", "api/routes/execution.py", "config.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "settings.estimated_charge_per_leg_inr" not in text, (
            f"{name} is charging a flat per-leg constant again"
        )
