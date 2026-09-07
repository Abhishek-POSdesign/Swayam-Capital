"""
Whether a structure is actually hedged, rather than merely containing a sell leg.

What this replaces
------------------
`any(leg.direction == "sell")`. That is not a hedge test, it is a test for the
presence of a short leg. Under it, a naked short call passed, and so did a
short strangle, which has unlimited loss on both sides. The rule was described
in the Method as "hedged structure" and enforced as its opposite.

A correction to the plan, made because the arithmetic was actually checked
------------------------------------------------------------------------
Plan v9 specifies: "a short put needs a long put BELOW it, a short call needs a
long call ABOVE it." Implemented literally that refuses a bear put spread, which
is Abhishek's own preset and the structure in 66 of his 67 recorded positions.

Worked through at 1 lot of 65, BUY 23800 PE and SELL 23700 PE, as spot falls:

    spot 23700   long 100    short      0   net  100/unit
    spot 20000   long 3800   short  -3700   net  100/unit
    spot     0   long 23800  short -23700   net  100/unit

The loss is capped at every point, including a total collapse to zero. A long
put ABOVE a short put caps the loss just as completely as one below it. The
strike relationship changes the SIZE of the worst case, not whether there is
one.

The rule this module actually enforces, which is the correct one:

  **Every short leg must be matched, one for one, by a long leg of the same
  option type in the same expiry.**

That is precisely the condition for bounded loss. How big the bound is, is a
separate question, and the blast-radius fuse already answers it by capping
absolute max loss at 5% of capital. Both checks together are what make a
structure safe; neither is sufficient alone.

What still fails, correctly:
  * a naked short call or put, no long leg of that type
  * a short strangle, no long legs at all
  * a ratio spread, two shorts against one long
  * a calendar or diagonal, where the long leg sits in a different expiry and
    therefore does not cap the short leg's loss at the short leg's expiry

Multi-expiry structures are NOT hidden, because ten of Abhishek's twenty-one
recorded historical swing trades are calendar spreads. They stay visible and
computable, are reported as uncovered, and are blocked from EXECUTION only
until multi-expiry valuation is correct.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Iterable


@dataclass(frozen=True)
class GeometryLeg:
    option_type: str  # "CE" or "PE"
    direction: str  # "buy" or "sell"
    strike: float
    quantity_lots: int
    expiry: date


@dataclass(frozen=True)
class GeometryResult:
    hedged: bool
    reason: str
    uncovered: tuple[str, ...]
    is_multi_expiry: bool
    expiries: tuple[date, ...]


def check_hedge_geometry(legs: Iterable[GeometryLeg]) -> GeometryResult:
    """Returns whether every short leg's loss is bounded by a long leg."""
    legs = list(legs)
    if not legs:
        return GeometryResult(False, "No legs.", (), False, ())

    expiries = tuple(sorted({l.expiry for l in legs}))
    multi = len(expiries) > 1

    shorts = [l for l in legs if l.direction.lower() == "sell"]
    if not shorts:
        return GeometryResult(
            True,
            "No short legs, so the most that can be lost is the premium paid.",
            (),
            multi,
            expiries,
        )

    # Long quantity available per option type and expiry. Cover is matched
    # within an expiry: a long leg in a different expiry has already expired
    # or not yet expired when the short leg settles, so it caps nothing then.
    available: dict[tuple[str, date], int] = defaultdict(int)
    for leg in legs:
        if leg.direction.lower() == "buy":
            available[(leg.option_type.upper(), leg.expiry)] += leg.quantity_lots

    uncovered: list[str] = []
    # Largest shorts first, so a shortage is reported against the leg that
    # actually carries the exposure.
    for short in sorted(shorts, key=lambda l: -l.quantity_lots):
        key = (short.option_type.upper(), short.expiry)
        covered = min(short.quantity_lots, available[key])
        available[key] -= covered
        missing = short.quantity_lots - covered

        if missing > 0:
            opt = short.option_type.upper()
            detail = (
                f"short {opt} {short.strike:g} has {missing} lot(s) with no long {opt} "
                f"in the same expiry ({short.expiry:%d %b %Y})"
            )
            if any(
                l.direction.lower() == "buy"
                and l.option_type.upper() == opt
                and l.expiry != short.expiry
                for l in legs
            ):
                detail += (
                    "; the long leg in another expiry does not cap this leg's loss "
                    "at its own expiry"
                )
            uncovered.append(detail)

    if uncovered:
        return GeometryResult(
            False,
            "Uncovered short legs: " + "; ".join(uncovered),
            tuple(uncovered),
            multi,
            expiries,
        )

    return GeometryResult(
        True,
        "Every short leg is matched by a long leg of the same type in the same expiry, "
        "so the loss is bounded. How large that bound is, is the blast-radius fuse's job.",
        (),
        multi,
        expiries,
    )
