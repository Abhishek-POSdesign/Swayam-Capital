"""Reading a NIFTY option contract's name, without guessing.

This looks trivial and is not. `NIFTY2690823450CE` is the 23,450 call expiring
on 8 September 2026: two digits of year, one character of month, two digits of
day, then the strike. Every one of those fields runs into the next with no
separator, so a lazy pattern that grabs "the digits before CE" reads the strike
as 823,450.

That is not hypothetical. It is exactly what happened on the first run of the
expired-options download on 2026-09-10: sixty-two contracts were selected as
"nearest the money" on garbage strikes, every one of them a strike that never
traded, and the download reported a clean zero rows without erroring. Data that
is silently wrong is the failure mode this whole project is built to avoid, so
the parse is anchored to an expiry that is already known, and it refuses rather
than guesses.

Two shapes exist:
  weekly   NIFTY + YY + M + DD + strike + CE/PE, month 1-9 then O, N, D
  monthly  NIFTY + YY + MMM + strike + CE/PE
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

MONTH_ABBREVIATIONS = {
    1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
    7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC",
}
# October, November and December cannot be two digits because the day follows
# immediately, so they take a letter.
WEEKLY_MONTH_CHARACTERS = {
    1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6",
    7: "7", 8: "8", 9: "9", 10: "O", 11: "N", 12: "D",
}


@dataclass(frozen=True)
class Contract:
    """One option contract, read from its name against a known expiry."""

    symbol: str
    expiry: date
    strike: float
    option_type: str
    monthly: bool


def weekly_prefix(expiry: date) -> str:
    return (
        f"NIFTY{expiry.year % 100:02d}"
        f"{WEEKLY_MONTH_CHARACTERS[expiry.month]}{expiry.day:02d}"
    )


def monthly_prefix(expiry: date) -> str:
    return f"NIFTY{expiry.year % 100:02d}{MONTH_ABBREVIATIONS[expiry.month]}"


def build_symbol(expiry: date, strike: float, option_type: str, monthly: bool) -> str:
    """The contract's name, in the shape FYERS and the NSE files both use."""
    option_type = option_type.upper()
    if option_type not in ("CE", "PE"):
        raise ValueError(f"option_type must be CE or PE, not {option_type!r}")
    prefix = monthly_prefix(expiry) if monthly else weekly_prefix(expiry)
    return f"{prefix}{int(round(strike))}{option_type}"


def parse(
    symbol: str, expiry: date, *, expiry_is_monthly: Optional[bool] = None
) -> Optional[Contract]:
    """The strike and type out of a contract name, given the expiry it belongs to.

    Returns None rather than a guess when the name does not belong to that
    expiry, which is the check that catches a contract filed under the wrong one.

    `expiry_is_monthly` tightens that check and is worth supplying whenever the
    caller knows. A weekly name carries its day, so it can be matched exactly. A
    MONTHLY name carries only the year and the month, so on its own it matches
    every expiry in that month, weekly ones included. Telling the parser which
    kind of expiry it is looking at closes that hole. The caller knows, because
    the monthly expiry is simply the last one in its month.
    """
    if not symbol:
        return None
    name = symbol.strip().upper()
    if name.startswith("NSE:"):
        name = name[4:]

    option_type = name[-2:]
    if option_type not in ("CE", "PE"):
        return None
    body = name[:-2]

    for prefix, monthly in ((monthly_prefix(expiry), True), (weekly_prefix(expiry), False)):
        if not body.startswith(prefix):
            continue
        if expiry_is_monthly is not None and monthly != expiry_is_monthly:
            continue
        digits = body[len(prefix):]
        if not digits.isdigit():
            continue
        strike = float(digits)
        if strike <= 0:
            return None
        return Contract(
            symbol=symbol, expiry=expiry, strike=strike,
            option_type=option_type, monthly=monthly,
        )
    return None


def parse_many(
    symbols: list[str], expiry: date, *, expiry_is_monthly: Optional[bool] = None
) -> tuple[list[Contract], list[str]]:
    """Every contract that parses, and every name that did not.

    The rejects are returned rather than dropped so a caller can say how many it
    could not read. A download that quietly skips half a chain looks identical to
    one that found half a chain.
    """
    parsed: list[Contract] = []
    rejected: list[str] = []
    for symbol in symbols:
        contract = parse(symbol, expiry, expiry_is_monthly=expiry_is_monthly)
        if contract is None:
            rejected.append(symbol)
        else:
            parsed.append(contract)
    return parsed, rejected


def nearest_strikes(contracts: list[Contract], centre: float, near: int) -> list[Contract]:
    """The `near` strikes either side of `centre`, both calls and puts.

    `near` of 0 means every strike, which is what to ask for when a structure's
    wings sit a long way out.
    """
    if near <= 0:
        return sorted(contracts, key=lambda c: (c.strike, c.option_type))
    strikes = sorted({c.strike for c in contracts})
    keep = set(sorted(strikes, key=lambda s: abs(s - centre))[: near * 2 + 1])
    return sorted(
        (c for c in contracts if c.strike in keep),
        key=lambda c: (c.strike, c.option_type),
    )
