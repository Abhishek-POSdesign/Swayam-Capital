"""Reading his twenty-one historical swing trades out of the vault.

`ROADMAP.md` §3 milestone 2: the backtester is not trusted until it reproduces
what these trades actually did. That makes these notes the acceptance test, and
an acceptance test has to be machine-readable before it can be run.

They are his own records of October 2022 to April 2023: 13 wins, 8 losses,
net +₹73,676, every one a multi-leg structure. Ten are calendars.

READ ONLY. Nothing in this module writes to the vault, and the test suite is
given a copy rather than the real folder, for the same reason
`conftest.cage_the_vault` exists: twenty-six fabricated notes once reached his
real journal because something wrote where it should only have read.

What the notes do not carry
---------------------------
**No expiry dates.** Not on the initial legs, not on the adjustments, not on the
exits. For a vertical spread that is recoverable, since both legs share the next
weekly expiry. For a CALENDAR it is the whole trade: Trade-07 sells the 18700
call and buys the 18700 call, the same strike, and the only thing separating
them is an expiry that is not written down. Ten of the twenty-one are calendars.
`missing_expiries` reports this rather than letting a backtest invent one.

**No lot size**, though it is recoverable: every quantity in these notes divides
by 50, which was the NIFTY lot in that era.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
import re
from typing import Iterator, Optional

# The NIFTY lot in his 2022-23 era. Used only to check that quantities divide by
# it, never to fill one in.
LOT_SIZE_2022 = 50

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_LEG_ROW = re.compile(
    r"^\|\s*(Buy|Sell)\s+(CE|PE)\s*(\(HEDGE\))?\s*\|"
    r"\s*([\d.]+)\s*\|\s*(-?[\d.]+)\s*\|\s*(-?[\d.]+)\s*\|\s*(-?[\d.eE+]+)\s*\|",
    re.IGNORECASE,
)
_ADJUSTMENT_HEADER = re.compile(r"\*\*(\d+)(?:st|nd|rd|th)\s+Adjustment", re.IGNORECASE)
_ADJUSTMENT_LEG = re.compile(
    r"^\s*-\s*(Buy|Sell)\s+(CE|PE)\s*(\(HEDGE\))?\s*Strike:\s*([\d.]+)\s*\|"
    r"\s*Premium:\s*(-?[\d.]+)\s*\|\s*Qty:\s*(-?[\d.]+)",
    re.IGNORECASE,
)
_EXIT_ROW = re.compile(
    r"^\s*-\s*(\d{4}-\d{2}-\d{2}):\s*(Buy|Sell)\s+(CE|PE)\s+Strike\s+([\d.]+)\s*@\s*₹?\s*(-?[\d.]+)",
    re.IGNORECASE,
)
_SECTION = re.compile(r"^##\s+(.*)$", re.MULTILINE)


@dataclass
class Leg:
    """One leg as he recorded it. `premium` is his sign: negative means paid."""

    action: str          # BUY or SELL
    option_type: str     # CE or PE
    strike: float
    premium: float
    quantity: int
    is_hedge: bool = False

    @property
    def lots(self) -> Optional[float]:
        if self.quantity % LOT_SIZE_2022:
            return None
        return self.quantity / LOT_SIZE_2022


@dataclass
class Exit:
    """One squared-off leg, on the day he squared it."""

    on: date
    action: str
    option_type: str
    strike: float
    price: float


@dataclass
class HistoricalTrade:
    """One campaign, as his own note records it."""

    trade_id: int
    path: Path
    strategy: str
    entry_date: Optional[date]
    exit_date: Optional[date]
    result: Optional[str]
    pnl_rupees: Optional[float]
    capital_used: Optional[float]
    planned_stop: Optional[float]
    planned_target: Optional[float]
    legs: list[Leg] = field(default_factory=list)
    adjustments: list[list[Leg]] = field(default_factory=list)
    exits: list[Exit] = field(default_factory=list)

    @property
    def is_calendar(self) -> bool:
        """Two legs at the same strike and side can only be a calendar."""
        if "calendar" in self.strategy.lower() or "calender" in self.strategy.lower():
            return True
        seen: set[tuple[float, str]] = set()
        for leg in self.legs:
            key = (leg.strike, leg.option_type)
            if key in seen:
                return True
            seen.add(key)
        return False

    @property
    def last_exit_date(self) -> Optional[date]:
        return max((e.on for e in self.exits), default=None)

    @property
    def strikes(self) -> list[float]:
        every = {leg.strike for leg in self.legs}
        for block in self.adjustments:
            every.update(leg.strike for leg in block)
        every.update(exit_.strike for exit_ in self.exits)
        return sorted(every)

    def problems(self) -> list[str]:
        """Everything about this note that would mislead a backtester.

        Reported, never corrected. These are his records and a silent repair
        would be exactly the kind of invisible edit this project refuses.
        """
        found: list[str] = []
        if self.entry_date is None:
            found.append("no entry date")
        if self.exit_date is None:
            found.append("no exit date")
        if self.entry_date and self.exit_date and self.exit_date < self.entry_date:
            found.append(
                f"the note's exit date {self.exit_date} is before its entry date "
                f"{self.entry_date}"
            )
        last = self.last_exit_date
        if last and self.exit_date and last != self.exit_date:
            found.append(
                f"the note's exit date {self.exit_date} disagrees with the last "
                f"booked order, {last}"
            )
        if not self.legs:
            found.append("no opening legs")
        if not self.exits:
            found.append("no booked exits, so what it closed at is unknown")
        for leg in self.legs:
            if leg.lots is None:
                found.append(
                    f"quantity {leg.quantity} does not divide by the lot of "
                    f"{LOT_SIZE_2022}"
                )
        return found


def _parse_date(value: str) -> Optional[date]:
    text = (value or "").strip().strip('"').strip("'")
    for pattern in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _parse_number(value: str) -> Optional[float]:
    cleaned = re.sub(r"[₹,\s]", "", value or "")
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    return float(match.group()) if match else None


def _frontmatter(text: str) -> dict[str, str]:
    match = _FRONTMATTER.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip('"')
    return fields


def _section(text: str, title: str) -> str:
    """The body of one `## ` section, or an empty string."""
    positions = [(m.start(), m.group(1).strip()) for m in _SECTION.finditer(text)]
    for index, (start, heading) in enumerate(positions):
        if heading.lower().startswith(title.lower()):
            end = positions[index + 1][0] if index + 1 < len(positions) else len(text)
            return text[start:end]
    return ""


def _bullet_value(block: str, label: str) -> Optional[str]:
    match = re.search(rf"\*\*{re.escape(label)}:?\*\*[:\s]*(.+)", block)
    return match.group(1).strip() if match else None


def parse_note(path: Path) -> HistoricalTrade:
    """One trade note as a record. Never writes; never edits."""
    text = path.read_text(encoding="utf-8", errors="replace")
    meta = _frontmatter(text)

    overview = _section(text, "Campaign Overview")
    trade_id = int(_parse_number(meta.get("trade_id", "")) or 0)

    legs = [
        Leg(
            action=m.group(1).upper(), option_type=m.group(2).upper(),
            is_hedge=bool(m.group(3)), strike=float(m.group(4)),
            premium=float(m.group(5)), quantity=int(float(m.group(6))),
        )
        for m in (_LEG_ROW.match(line) for line in _section(text, "Initial Position Legs").splitlines())
        if m
    ]

    adjustments: list[list[Leg]] = []
    current: list[Leg] = []
    started = False
    for line in _section(text, "Trade Adjustments").splitlines():
        if _ADJUSTMENT_HEADER.search(line):
            if started:
                adjustments.append(current)
            current, started = [], True
            continue
        match = _ADJUSTMENT_LEG.match(line)
        if match:
            current.append(Leg(
                action=match.group(1).upper(), option_type=match.group(2).upper(),
                is_hedge=bool(match.group(3)), strike=float(match.group(4)),
                premium=float(match.group(5)), quantity=int(float(match.group(6))),
            ))
    if started:
        adjustments.append(current)
    adjustments = [block for block in adjustments if block]

    exits = [
        Exit(
            on=_parse_date(m.group(1)), action=m.group(2).upper(),
            option_type=m.group(3).upper(), strike=float(m.group(4)),
            price=float(m.group(5)),
        )
        for m in (_EXIT_ROW.match(line) for line in _section(text, "Booked Orders").splitlines())
        if m and _parse_date(m.group(1))
    ]

    return HistoricalTrade(
        trade_id=trade_id,
        path=path,
        strategy=meta.get("strategy", "").strip('"') or "unknown",
        entry_date=_parse_date(meta.get("entry_date", "")),
        exit_date=_parse_date(meta.get("exit_date", "")),
        result=meta.get("result"),
        pnl_rupees=_parse_number(meta.get("pnl_rupees", "")),
        capital_used=_parse_number(_bullet_value(overview, "Capital Reserved / Used") or ""),
        planned_stop=_parse_number(_bullet_value(overview, "Planned Stop Loss") or ""),
        planned_target=_parse_number(_bullet_value(overview, "Planned Target") or ""),
        legs=legs,
        adjustments=adjustments,
        exits=exits,
    )


def load_all(folder: Path) -> list[HistoricalTrade]:
    """Every `Trade-NN` note in a folder, in order. Overview files are skipped."""
    notes = sorted(
        path for path in folder.glob("*.md") if re.match(r"^Trade-\d+", path.name)
    )
    return sorted(
        (parse_note(path) for path in notes), key=lambda trade: trade.trade_id
    )


def missing_expiries(trades: list[HistoricalTrade]) -> list[HistoricalTrade]:
    """The trades that cannot be priced without an expiry being established.

    Every note is missing its expiries. For a vertical spread both legs share the
    next weekly expiry and the gap is recoverable. For a calendar the two legs
    differ ONLY by expiry, so there is nothing to recover it from and it has to
    come from him or from matching his recorded premiums against the chain.
    """
    return [trade for trade in trades if trade.is_calendar]
