"""
What a trade actually costs, in Decimal, versioned by effective date.

What this replaces
------------------
A paper "fill" that cost nothing on entry, and a close path that charged
`legs x Rs 150` from a configuration value. Neither resembled a real contract
note, so every paper result was better than the same trade would have been.

Why the rates are versioned
---------------------------
Rates change. STT on options rose from 0.10% to 0.15% of premium with effect
from 1 April 2026. A journal entry for a trade taken before that date must be
costed with the rates that were in force THEN, never with today's. A schedule
keyed by effective date is the only way that stays true as the years pass.

Why Decimal and not float
-------------------------
Money is counted, not measured. Binary floating point cannot represent 0.1
exactly, and the error compounds across seven charge lines and two sides of a
round trip. Every figure here is Decimal, quantised to paise at the end. The
frontend displays what this produced and never recomputes it.

Sources, read 2026-09-08
------------------------
FYERS charges list (his broker, and therefore authoritative for his account):
brokerage Rs 20 per executed order on Standard, exchange transaction charge
0.0355299% of premium, clearing charge 0.009%, IPFT Rs 0.01 per crore, SEBI
turnover fee Rs 10 per crore, stamp duty 0.003% on the buy side, GST 18% on
brokerage plus exchange plus clearing plus SEBI plus IPFT.

Cross-checked against Zerodha's published list, which agrees on transaction
charge (0.03553%), IPFT (Rs 0.01 per crore), SEBI (Rs 10 per crore), stamp
duty (0.003% buy side) and STT (0.15% on the sell side of premium).

Two corrections to what the plan assumed, both made because the sources were
actually read rather than quoted:
  * the plan said the exchange transaction charge was 0.03503%. Both brokers
    publish 0.03553%. The plan's figure was stale.
  * the plan said IPFT was Rs 50 per crore. Both brokers publish Rs 0.01 per
    crore, which is negligible rather than material.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, Optional, Sequence

PAISE = Decimal("0.01")

Side = Literal["buy", "sell"]


def _q(value: Decimal) -> Decimal:
    """Rounds to paise, half up, the way a contract note does."""
    return value.quantize(PAISE, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ChargeSchedule:
    """One dated set of rates. Never edited in place; a new one is added."""

    version: str
    effective_from: date
    effective_to: Optional[date]

    brokerage_per_order_inr: Decimal
    stt_pct_of_premium_sell: Decimal
    exchange_txn_pct_of_premium: Decimal
    clearing_pct_of_premium: Decimal
    ipft_pct_of_premium: Decimal
    sebi_pct_of_premium: Decimal
    stamp_duty_pct_of_premium_buy: Decimal
    gst_pct: Decimal

    sources: tuple[str, ...] = ()
    notes: str = ""

    def covers(self, on: date) -> bool:
        if on < self.effective_from:
            return False
        return self.effective_to is None or on <= self.effective_to


# Rs 20 per executed order is the FYERS Standard plan, which is the plan
# Abhishek is on. Prime is Rs 15 and is NOT what he pays.
SCHEDULE_2026_04 = ChargeSchedule(
    version="fyers-standard-2026-04",
    effective_from=date(2026, 4, 1),
    effective_to=None,
    brokerage_per_order_inr=Decimal("20"),
    # STT rose from 0.10% to 0.15% of premium on the sell side, 1 April 2026.
    stt_pct_of_premium_sell=Decimal("0.0015"),
    exchange_txn_pct_of_premium=Decimal("0.000355299"),
    clearing_pct_of_premium=Decimal("0.00009"),
    # Rs 0.01 per crore. Kept as a rate rather than a rupee figure so it scales.
    ipft_pct_of_premium=Decimal("0.000000001"),
    # Rs 10 per crore.
    sebi_pct_of_premium=Decimal("0.000001"),
    stamp_duty_pct_of_premium_buy=Decimal("0.00003"),
    gst_pct=Decimal("0.18"),
    sources=(
        "FYERS charges list, read 2026-09-08",
        "Zerodha published charges, read 2026-09-08, as a cross-check",
    ),
    notes=(
        "Applies to NSE equity options on premium turnover. Exercise and "
        "assignment carry a separate STT of 0.15% on intrinsic value and are "
        "NOT covered here; expiry handling is a separate case."
    ),
)

# Retained so a trade from his 2022-23 records is costed with the rates that
# were actually in force then, not today's. STT on options was 0.05% of
# premium on the sell side before the 2023 revision.
SCHEDULE_2022_04 = ChargeSchedule(
    version="fyers-standard-2022-04",
    effective_from=date(2022, 4, 1),
    effective_to=date(2023, 3, 31),
    brokerage_per_order_inr=Decimal("20"),
    stt_pct_of_premium_sell=Decimal("0.0005"),
    exchange_txn_pct_of_premium=Decimal("0.00053"),
    clearing_pct_of_premium=Decimal("0.00009"),
    ipft_pct_of_premium=Decimal("0.000000001"),
    sebi_pct_of_premium=Decimal("0.000001"),
    stamp_duty_pct_of_premium_buy=Decimal("0.00003"),
    gst_pct=Decimal("0.18"),
    sources=("Historical rates, retained for costing old journal entries",),
    notes=(
        "NOT verified against his 2022-23 contract notes. If he still holds "
        "them, reconcile before trusting any historical figure computed with "
        "this schedule."
    ),
)

SCHEDULES: tuple[ChargeSchedule, ...] = (SCHEDULE_2022_04, SCHEDULE_2026_04)


class ChargeScheduleUnavailable(RuntimeError):
    """No published rates cover the requested date. Never guess a cost."""


def schedule_for(on: date) -> ChargeSchedule:
    for schedule in SCHEDULES:
        if schedule.covers(on):
            return schedule
    raise ChargeScheduleUnavailable(
        f"No charge schedule covers {on:%d %b %Y}. A trade cannot be costed "
        f"with rates that were not in force."
    )


@dataclass(frozen=True)
class ChargeLine:
    name: str
    amount_inr: Decimal
    basis: str


@dataclass(frozen=True)
class ChargeBreakdown:
    """Every line of a contract note, so a total can always be explained."""

    lines: tuple[ChargeLine, ...]
    total_inr: Decimal
    schedule_version: str
    computed_for: date
    orders: int
    premium_turnover_buy_inr: Decimal
    premium_turnover_sell_inr: Decimal

    def as_dict(self) -> dict:
        return {
            "total_inr": float(self.total_inr),
            "schedule_version": self.schedule_version,
            "computed_for": self.computed_for.isoformat(),
            "orders": self.orders,
            "premium_turnover_buy_inr": float(self.premium_turnover_buy_inr),
            "premium_turnover_sell_inr": float(self.premium_turnover_sell_inr),
            "lines": [
                {"name": l.name, "amount_inr": float(l.amount_inr), "basis": l.basis}
                for l in self.lines
            ],
        }


@dataclass(frozen=True)
class ChargeableLeg:
    """One executed leg, at the price it actually filled."""

    side: Side
    price_per_unit: Decimal
    quantity_units: int  # lots x contract size, already multiplied out

    @property
    def turnover(self) -> Decimal:
        return self.price_per_unit * Decimal(self.quantity_units)


def compute_charges(
    legs: Sequence[ChargeableLeg],
    *,
    on: date,
    schedule: Optional[ChargeSchedule] = None,
) -> ChargeBreakdown:
    """Costs one side of a trade: entry, or exit. Call it twice for a round trip.

    Every leg is one executed order, because brokerage is per order.
    """
    if not legs:
        raise ValueError("No legs to charge.")

    sched = schedule or schedule_for(on)

    buy_turnover = sum((l.turnover for l in legs if l.side == "buy"), Decimal("0"))
    sell_turnover = sum((l.turnover for l in legs if l.side == "sell"), Decimal("0"))
    total_turnover = buy_turnover + sell_turnover
    orders = len(legs)

    brokerage = sched.brokerage_per_order_inr * Decimal(orders)
    stt = sell_turnover * sched.stt_pct_of_premium_sell
    exchange = total_turnover * sched.exchange_txn_pct_of_premium
    clearing = total_turnover * sched.clearing_pct_of_premium
    ipft = total_turnover * sched.ipft_pct_of_premium
    sebi = total_turnover * sched.sebi_pct_of_premium
    stamp = buy_turnover * sched.stamp_duty_pct_of_premium_buy

    # GST applies to the service charges, not to the statutory taxes.
    gst = (brokerage + exchange + clearing + sebi + ipft) * sched.gst_pct

    lines = (
        ChargeLine("Brokerage", _q(brokerage), f"₹{sched.brokerage_per_order_inr} × {orders} orders"),
        ChargeLine("STT", _q(stt), f"{sched.stt_pct_of_premium_sell * 100:.4f}% of sell premium"),
        ChargeLine("Exchange transaction", _q(exchange), f"{sched.exchange_txn_pct_of_premium * 100:.6f}% of premium"),
        ChargeLine("Clearing", _q(clearing), f"{sched.clearing_pct_of_premium * 100:.4f}% of premium"),
        ChargeLine("SEBI turnover fee", _q(sebi), "₹10 per crore of premium"),
        ChargeLine("Investor protection fee", _q(ipft), "₹0.01 per crore of premium"),
        ChargeLine("Stamp duty", _q(stamp), f"{sched.stamp_duty_pct_of_premium_buy * 100:.4f}% of buy premium"),
        ChargeLine("GST", _q(gst), f"{sched.gst_pct * 100:.0f}% on brokerage, exchange, clearing, SEBI and IPFT"),
    )

    return ChargeBreakdown(
        lines=lines,
        total_inr=_q(sum((l.amount_inr for l in lines), Decimal("0"))),
        schedule_version=sched.version,
        computed_for=on,
        orders=orders,
        premium_turnover_buy_inr=_q(buy_turnover),
        premium_turnover_sell_inr=_q(sell_turnover),
    )


def round_trip_cost_reserve(
    legs: Sequence[ChargeableLeg],
    *,
    on: date,
) -> Decimal:
    """A conservative reserve for the cost of getting in AND out.

    The risk gate has to include this. A position whose price loss sits just
    under the 1% cap still breaches it once both sides of the trade are paid
    for, and a gate that ignores that is not a 1% gate.

    The exit is costed at the entry prices, with the sides reversed. That is
    an approximation, and a deliberately conservative one for the common case:
    a losing trade exits cheaper than it entered, so the real exit cost is
    usually lower than this reserve.
    """
    entry = compute_charges(legs, on=on)
    reversed_legs = [
        ChargeableLeg(
            side="sell" if l.side == "buy" else "buy",
            price_per_unit=l.price_per_unit,
            quantity_units=l.quantity_units,
        )
        for l in legs
    ]
    exit_side = compute_charges(reversed_legs, on=on)
    return _q(entry.total_inr + exit_side.total_inr)


# ---------------------------------------------------------------------------
# Per leg, which is how he thinks about it and how a contract note works.
#
# His instruction, 2026-09-09: "Charges must be calculated as per each leg, not
# as per the trade... The buy leg has its own charges, and the sell leg has its
# own charges. Why would squaring one leg charge for the whole trade?"
#
# This is safe as well as correct. Brokerage is charged per ORDER and every
# other line is a percentage of that leg's own turnover, so costing legs one at
# a time and adding them up gives EXACTLY the same total as costing them
# together. Measured on a one-lot iron condor, 2026-09-08:
#
#     35.47 + 25.22 + 34.80 + 25.22 = 120.71
#
# and 120.71 is what those four legs cost in a single call. To the paisa.
# `tests/test_charges_per_leg.py` holds that as an assertion.
# ---------------------------------------------------------------------------

_BUY_WORDS = ("buy", "long", "b")
_SELL_WORDS = ("sell", "short", "s")


def side_from_direction(direction: str) -> Side:
    """The side a stored leg was transacted on. Raises rather than guessing.

    Leg direction reaches us from several places and has been spelled `buy`,
    `BUY`, `long` and `short`. A leg whose side cannot be read cannot be
    charged, and charging it as a buy by default would understate the cost of
    a short by the whole of the securities transaction tax.
    """
    word = str(direction or "").strip().lower()
    if word in _BUY_WORDS:
        return "buy"
    if word in _SELL_WORDS:
        return "sell"
    raise ChargeScheduleUnavailable(
        f"Cannot charge a leg whose direction is {direction!r}. "
        "It must say buy or sell."
    )


def opposite(side: Side) -> Side:
    """Closing a leg transacts the other way. A bought leg is sold to exit."""
    return "sell" if side == "buy" else "buy"


def charge_for_leg(
    *,
    side: Side,
    price_per_unit: Decimal,
    quantity_units: int,
    on: date,
    schedule: Optional[ChargeSchedule] = None,
) -> ChargeBreakdown:
    """What ONE leg costs, on its own side, at its own price, on this date.

    Call it when the leg is bought or sold, and again when it is squared off.
    Every leg therefore carries an entry cost from the day it opens and an exit
    cost from the day it closes, and a trade's cost is the sum of its legs'.
    """
    return compute_charges(
        [ChargeableLeg(side=side, price_per_unit=price_per_unit, quantity_units=quantity_units)],
        on=on,
        schedule=schedule,
    )
