"""The name of a structure, read off its own legs.

WHY THIS EXISTS
---------------
His open condor is stored as "Short Strangle". He did not name it. On
2026-09-10 he loaded the strangle preset, the ticket refused his limit price
because the book had not reached it, he switched to a condor at market, and
the name stayed with the preset that had been loaded first. His words: "Short
Strangle was not the name chosen by me. It was the system error that gave it
the name... I had no role to play in naming any order I made today."

So the name is no longer something a preset leaves behind. It is derived from
what he actually holds, and recomputed every time the legs change: at execute,
at add-leg, at exit-leg and at reverse. The one exception is a name he typed
himself, which is recorded on the row as `name_source = 'his'` and is never
overwritten.

ONLY OPEN LEGS COUNT. A trade is a campaign whose shape changes while it runs,
so a four-leg condor with one leg squared off is no longer a condor; it is
whatever the three remaining legs make. That is the name he should see.

This module is pure. It reads dictionaries and returns a string. It touches no
database, no clock and no network, which is why it can be tested by a table.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional


class _Leg:
    """A leg once it is normalised: side B or S, kind CE or PE, strike, expiry."""

    __slots__ = ("side", "kind", "strike", "expiry")

    def __init__(self, side: str, kind: str, strike: float, expiry: Optional[str]) -> None:
        self.side = side
        self.kind = kind
        self.strike = strike
        self.expiry = expiry


def is_open(leg: dict[str, Any]) -> bool:
    """A leg with no status is open.

    Every leg on every row written before migration 022 has no status, so the
    absence of the field must mean open. Anything that is not the word
    "closed" is treated as open, because a half-written state should show him
    a position he still holds rather than hide one.
    """
    return str(leg.get("status") or "open").lower() != "closed"


def open_legs(legs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """The legs of this trade that are still running."""
    return [l for l in (legs or []) if isinstance(l, dict) and is_open(l)]


def _normalise(legs: Iterable[dict[str, Any]]) -> list[_Leg]:
    out: list[_Leg] = []
    for leg in legs:
        if not isinstance(leg, dict):
            continue
        direction = str(leg.get("direction") or leg.get("side") or "").strip().lower()
        if direction in ("buy", "long", "b"):
            side = "B"
        elif direction in ("sell", "short", "s"):
            side = "S"
        else:
            continue
        kind = str(leg.get("option_type") or leg.get("type") or "").strip().upper()
        if kind in ("C", "CALL"):
            kind = "CE"
        elif kind in ("P", "PUT"):
            kind = "PE"
        if kind not in ("CE", "PE"):
            continue
        try:
            strike = float(leg.get("strike"))
        except (TypeError, ValueError):
            continue
        expiry = leg.get("expiry_date") or leg.get("expiry")
        out.append(_Leg(side, kind, strike, str(expiry) if expiry else None))
    return out


def _expiries(legs: list[_Leg]) -> set[str]:
    return {l.expiry for l in legs if l.expiry}


def _one_expiry(legs: list[_Leg]) -> bool:
    """True when every leg that names an expiry names the same one.

    A leg with no expiry recorded does not turn a structure into a calendar.
    It leaves the expiry unknown, and an unknown expiry is treated as the same
    expiry rather than invented as a different one.
    """
    return len(_expiries(legs)) <= 1


def _single(leg: _Leg) -> str:
    if leg.side == "B":
        return "Long Call" if leg.kind == "CE" else "Long Put"
    return "Short Call" if leg.kind == "CE" else "Short Put"


def _two(legs: list[_Leg]) -> Optional[str]:
    a, b = legs
    same_kind = a.kind == b.kind
    same_strike = abs(a.strike - b.strike) < 0.005
    one_expiry = _one_expiry(legs)
    opposite_sides = a.side != b.side

    # Calendars and diagonals: two expiries, the same kind of option, one
    # bought and one sold. His own framing, 2026-09-08: the far expiry is the
    # hedge and the margin benefit, the near expiry is where the theta is
    # earned. Ten of his twenty-one profitable swing trades were calendars,
    # so this branch matters more than any other here.
    if not one_expiry and same_kind and opposite_sides:
        if same_strike:
            return "Call Calendar" if a.kind == "CE" else "Put Calendar"
        return "Diagonal"

    if not one_expiry:
        return None

    # Straddles and strangles: one call and one put, both on the same side.
    if not same_kind and a.side == b.side:
        if same_strike:
            return "Long Straddle" if a.side == "B" else "Short Straddle"
        return "Long Strangle" if a.side == "B" else "Short Strangle"

    # Vertical spreads: the same kind, one bought and one sold, two strikes.
    if same_kind and opposite_sides and not same_strike:
        bought = a if a.side == "B" else b
        sold = b if a.side == "B" else a
        if a.kind == "CE":
            # A call spread is bullish when the lower strike is the one bought.
            return "Bull Call Spread" if bought.strike < sold.strike else "Bear Call Spread"
        # A put spread is bullish when the lower strike is bought and the
        # higher one sold, which is the shape that takes in a credit.
        return "Bull Put Spread" if bought.strike < sold.strike else "Bear Put Spread"

    return None


def _four(legs: list[_Leg]) -> Optional[str]:
    """Iron condor and iron butterfly, the two four-leg shapes he trades.

    Both are two calls and two puts on one expiry with the short strikes
    inside the long ones. They differ only in whether the two short strikes
    are the same: equal is a butterfly, apart is a condor. Anything else with
    four legs is Custom, which is honest rather than flattering.
    """
    if not _one_expiry(legs):
        return None
    calls = [l for l in legs if l.kind == "CE"]
    puts = [l for l in legs if l.kind == "PE"]
    if len(calls) != 2 or len(puts) != 2:
        return None
    if {c.side for c in calls} != {"B", "S"} or {p.side for p in puts} != {"B", "S"}:
        return None

    short_call = next(c for c in calls if c.side == "S")
    long_call = next(c for c in calls if c.side == "B")
    short_put = next(p for p in puts if p.side == "S")
    long_put = next(p for p in puts if p.side == "B")

    # The wings sit outside the body: the long call above the short call and
    # the long put below the short put. That is what makes the loss finite,
    # and it is the whole reason he may carry the thing overnight at all.
    if not (long_call.strike > short_call.strike and long_put.strike < short_put.strike):
        return None
    # A short put above the short call is a different animal, not this one.
    if short_put.strike > short_call.strike:
        return None

    if abs(short_call.strike - short_put.strike) < 0.005:
        return "Iron Butterfly"
    return "Iron Condor"


def name_from_legs(legs: Iterable[dict[str, Any]]) -> str:
    """The name of the structure formed by the OPEN legs.

    Anything this cannot name confidently comes back as "Custom, N legs",
    which is a true statement about what he holds rather than a guess dressed
    up as a name.
    """
    parsed = _normalise(open_legs(legs))

    if not parsed:
        return "No open legs"

    named: Optional[str] = None
    if len(parsed) == 1:
        named = _single(parsed[0])
    elif len(parsed) == 2:
        named = _two(parsed)
    elif len(parsed) == 4:
        named = _four(parsed)

    if named:
        return named
    return f"Custom, {len(parsed)} leg{'' if len(parsed) == 1 else 's'}"


def name_from_all_legs(legs: Iterable[dict[str, Any]]) -> str:
    """The name of the structure a FINISHED trade had, from every leg it held.

    A closed trade has no open legs, so `name_from_legs` would truthfully but
    uselessly answer "No open legs". What he wants to read in his record is the
    shape the trade WAS: the bull put spread stays a bull put spread after it is
    squared off.

    Only for a trade that is closed. An open trade is named by what is still
    running, which is the whole point of naming from the open legs.
    """
    parsed = _normalise(legs or [])
    if not parsed:
        return "No legs recorded"

    named: Optional[str] = None
    if len(parsed) == 1:
        named = _single(parsed[0])
    elif len(parsed) == 2:
        named = _two(parsed)
    elif len(parsed) == 4:
        named = _four(parsed)

    if named:
        return named
    return f"Custom, {len(parsed)} leg{'' if len(parsed) == 1 else 's'}"


def resolve_name(
    legs: Iterable[dict[str, Any]],
    *,
    name_source: Optional[str],
    current_name: Optional[str],
    closed: bool = False,
) -> str:
    """The name to store: his if he set one, otherwise the structure's.

    Every writer goes through here so the rule lives in one place rather than
    being repeated at four call sites. A name he typed is never overwritten,
    however the legs change afterwards; that is the point of letting him type
    one at all.
    """
    if str(name_source or "structure").lower() == "his" and current_name:
        return str(current_name)
    return name_from_all_legs(legs) if closed else name_from_legs(legs)
