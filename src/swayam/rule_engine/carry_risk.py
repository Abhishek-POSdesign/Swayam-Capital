"""
Overnight carry risk: what a gap would cost, and whether it may be held.

Abhishek's rule, stated 2026-09-08, and this module exists to implement it
literally rather than approximately:

  * Entry is NEVER blocked. He builds and adjusts whatever he likes, whenever
    he likes. While he is converting a straddle into a condor he must exit legs
    and add legs, and for a minute or two in between the position looks
    appalling. A system that refused him at that moment would be useless.
  * A RUNNING loss above 1% of live capital turns the app red and alerts him.
    That is a monitor, not a gate.
  * Carrying a position OVERNIGHT requires two things: it must be hedged, and a
    gap of twice the average daily move must not cost more than 2% of live
    capital.
  * The absolute worst case at expiry is informational. Rs 25,000 or Rs 30,000
    is fine, because reaching it needs a 3 to 5 percent move or expiry day.

Why the gap test rather than the worst case
-------------------------------------------
His words: "the maximum risk could be 30,000, but that is the maximum risk
after maybe a 3%, 4%, 5% move, or on the expiry day, not today." Tomorrow's
real exposure is the gap, not the tail. Measuring tomorrow against a number
that can only occur weeks away would refuse sound trades and teach him to
ignore the warning, which is worse than having none.

The move size
-------------
Twice the average absolute close-to-close move over the trailing window, from
his own stored history. On the 26 sessions available on 2026-09-08 the average
was 73.7 points, so the test gaps NIFTY by 147.4 points in both directions and
takes the worse. Two standard deviations of the same series is 157.6, close
enough that the two framings agree; the statistical figure is reported beside
his so he can see both.

Everything is a percentage of the LIVE broker balance, never a stored figure.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional, Sequence

from swayam.options_math.models import Leg
from swayam.options_math.payoff import loss_is_unbounded, pnl_at_spot

# Trailing sessions used for the average move. Matches the Method's
# realized-volatility window so the two figures describe the same period.
DEFAULT_WINDOW = 20

# The history must be current. A gap test computed from last week's typical
# move is not a gap test, it is a memory.
MAX_HISTORY_AGE_DAYS = 4


class CarryDataUnavailable(RuntimeError):
    """The move size cannot be established, so the carry test cannot run."""


@dataclass(frozen=True)
class MoveProfile:
    """How much this index typically moves, from its own recent history."""

    average_daily_move_points: float
    two_x_average_points: float
    two_sigma_points: float
    sessions_used: int
    newest_session: date
    oldest_session: date

    def as_dict(self) -> dict:
        return {
            "average_daily_move_points": round(self.average_daily_move_points, 1),
            "gap_tested_points": round(self.two_x_average_points, 1),
            "two_sigma_points": round(self.two_sigma_points, 1),
            "sessions_used": self.sessions_used,
            "newest_session": self.newest_session.isoformat(),
            "oldest_session": self.oldest_session.isoformat(),
            "definition": "twice the average absolute close-to-close move",
        }


@dataclass(frozen=True)
class CarryAssessment:
    """Whether this position may be carried overnight, and the arithmetic."""

    may_carry: bool
    hedged: bool
    gap_loss_inr: Optional[float]
    cap_inr: float
    move: Optional[MoveProfile]
    reasons: tuple[str, ...]
    arithmetic: Optional[str]

    def as_dict(self) -> dict:
        return {
            "may_carry_overnight": self.may_carry,
            "hedged": self.hedged,
            "gap_loss_inr": round(self.gap_loss_inr, 2) if self.gap_loss_inr is not None else None,
            "cap_inr": round(self.cap_inr, 2),
            "move": self.move.as_dict() if self.move else None,
            "reasons": list(self.reasons),
            "arithmetic": self.arithmetic,
        }


def load_move_profile(
    *,
    window: int = DEFAULT_WINDOW,
    today: Optional[date] = None,
) -> MoveProfile:
    """Reads the recent daily bars and measures the typical move.

    Raises CarryDataUnavailable rather than substituting a number. A gap test
    with an invented move size would be worse than no gap test at all.
    """
    from swayam.db import db

    today = today or date.today()
    try:
        rows = (
            db.client.table("swayam_nifty_daily_bars")
            .select("trade_date,close")
            .order("trade_date", desc=True)
            .limit(window + 1)
            .execute()
            .data
        )
    except Exception as exc:
        raise CarryDataUnavailable(f"Could not read daily price history: {exc}") from exc

    if not rows or len(rows) < window + 1:
        raise CarryDataUnavailable(
            f"Only {len(rows or [])} sessions of history are stored; "
            f"{window + 1} are needed to measure the average daily move."
        )

    rows = sorted(rows, key=lambda r: r["trade_date"])
    newest = date.fromisoformat(rows[-1]["trade_date"])
    if today - newest > timedelta(days=MAX_HISTORY_AGE_DAYS):
        raise CarryDataUnavailable(
            f"The newest stored session is {newest:%d %b %Y}, which is stale. "
            f"The nightly price ingest needs to run before an overnight carry "
            f"can be assessed."
        )

    closes = [float(r["close"]) for r in rows]
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    if not changes:
        raise CarryDataUnavailable("Not enough sessions to compute a move.")

    average = statistics.mean(abs(c) for c in changes)
    sigma = statistics.pstdev(changes)

    return MoveProfile(
        average_daily_move_points=average,
        two_x_average_points=2.0 * average,
        two_sigma_points=2.0 * sigma,
        sessions_used=len(changes),
        newest_session=newest,
        oldest_session=date.fromisoformat(rows[0]["trade_date"]),
    )


def assess_overnight_carry(
    legs: Sequence[Leg],
    *,
    current_spot: float,
    risk_capital_inr: float,
    hedged: bool,
    carry_cap_pct: float = 0.02,
    iv_per_leg: Optional[dict[Leg, float]] = None,
    as_of_date: Optional[date] = None,
    today: Optional[date] = None,
) -> CarryAssessment:
    """Decides whether this position may be held overnight.

    Two conditions, both required:
      1. the structure is hedged, meaning its loss has a ceiling
      2. a gap of twice the average daily move, in the worse direction, costs
         no more than `carry_cap_pct` of live capital

    Nothing here blocks entry. It answers only "may this be carried".
    """
    cap = risk_capital_inr * carry_cap_pct
    reasons: list[str] = []

    if not hedged:
        reasons.append(
            "The position is not hedged, so its loss has no ceiling and there is "
            "nothing for the 2% test to measure. Add the protective leg before the close."
        )

    try:
        move = load_move_profile(today=today)
    except CarryDataUnavailable as exc:
        return CarryAssessment(
            may_carry=False,
            hedged=hedged,
            gap_loss_inr=None,
            cap_inr=cap,
            move=None,
            reasons=tuple(reasons + [str(exc)]),
            arithmetic=None,
        )

    gap = move.two_x_average_points
    pnl_up = pnl_at_spot(
        list(legs), current_spot + gap, current_iv_per_leg=iv_per_leg, as_of_date=as_of_date
    )
    pnl_down = pnl_at_spot(
        list(legs), current_spot - gap, current_iv_per_leg=iv_per_leg, as_of_date=as_of_date
    )
    gap_loss = max(0.0, -min(pnl_up, pnl_down))
    direction = "up" if pnl_up <= pnl_down else "down"

    within_cap = gap_loss <= cap
    if not within_cap:
        reasons.append(
            f"A {gap:.0f} point gap {direction} would cost ₹{gap_loss:,.0f}, "
            f"which is more than the ₹{cap:,.0f} you allow yourself to carry."
        )

    arithmetic = (
        f"NIFTY gaps {gap:.0f} points {direction} (2 × the {move.average_daily_move_points:.0f} "
        f"point average daily move over {move.sessions_used} sessions) → loss ₹{gap_loss:,.0f}, "
        f"against a carry cap of ₹{cap:,.0f} ({carry_cap_pct * 100:.0f}% of ₹{risk_capital_inr:,.0f})"
    )

    return CarryAssessment(
        may_carry=hedged and within_cap,
        hedged=hedged,
        gap_loss_inr=gap_loss,
        cap_inr=cap,
        move=move,
        reasons=tuple(reasons),
        arithmetic=arithmetic,
    )


def running_loss_status(
    unrealised_pnl_inr: Optional[float],
    *,
    risk_capital_inr: float,
    alert_pct: float = 0.01,
) -> dict:
    """Where a live position's running loss sits against the 1% line.

    Abhishek's rule: above 1% of live capital, the app goes red and alerts him.
    This is a monitor. It never blocks anything, and it never closes anything.
    """
    threshold = risk_capital_inr * alert_pct

    if unrealised_pnl_inr is None:
        return {
            "state": "unknown",
            "threshold_inr": round(threshold, 2),
            "loss_inr": None,
            "pct_of_capital": None,
            "message": "Running profit and loss is unavailable, so the 1% line cannot be checked.",
        }

    loss = max(0.0, -unrealised_pnl_inr)
    pct = loss / risk_capital_inr * 100.0 if risk_capital_inr else 0.0

    if loss >= threshold:
        state = "breached"
        message = (
            f"Running loss ₹{loss:,.0f} is past your 1% line of ₹{threshold:,.0f}. "
            f"Your rule says exit."
        )
    elif loss >= threshold * 0.75:
        state = "approaching"
        message = (
            f"Running loss ₹{loss:,.0f} is {pct:.2f}% of capital, nearing the 1% "
            f"line of ₹{threshold:,.0f}."
        )
    else:
        state = "ok"
        message = f"Running loss ₹{loss:,.0f}, {pct:.2f}% of capital."

    return {
        "state": state,
        "threshold_inr": round(threshold, 2),
        "loss_inr": round(loss, 2),
        "pct_of_capital": round(pct, 3),
        "message": message,
    }
