"""The order book: a limit that the market has not reached, waiting for it.

WHY THIS EXISTS
---------------
His words, 2026-09-10, after the first live send: "I can place 111, 112, or
113 because it's a limit order... It should not execute if the price is not
available, but must be sitting in the system till the time the bid and ask
reach the price I want."

Before this, a limit away from the book refused the whole ticket. He lost a
strangle to that on 10 September and his condor took the name of the preset
he had loaded first, because he had to rebuild the trade at market.

WHAT THIS MODULE IS, AND IS NOT
-------------------------------
It is the BOOK: it writes orders down, reads them back, claims one for filling
so that only one process can, and records what happened. It is not the fill
rule and it is not the watcher. `services/fills.py` decides whether anything
fills; that file is untouched by this build. `services/order_watcher.py` is
what looks at the market.

THREE RULES THIS MODULE KEEPS
-----------------------------
1. **Nothing here is money until it fills.** A resting order holds no margin,
   books no charge and writes no note. When it fills it goes down exactly the
   path a leg he pressed Send on takes.
2. **One order fills at most once.** The move from `resting` to `filling` is
   ONE conditional update, and the database decides the winner. Two copies of
   the backend can never fill the same order twice. `claim` is that update and
   `tests/test_resting_orders.py` proves it.
3. **Nothing outlives the day.** Every order expires at 15:30 IST of the day
   it was placed, nothing is charged for expiring, and the line stays on his
   screen until the day turns so he can see what the book never reached.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta, timezone
import logging
from typing import Any, Optional
import uuid
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

# The table name is written out in full at every call rather than through this
# constant, because tests/test_written_columns_exist.py reads the SOURCE to
# check that every column written actually exists, and it can only see a
# literal. Keeping the constant for anything that needs to name the table.
TABLE = "swayam_orders"

# The bell. Shared with services/expiry.py, which owns the same time for the
# same reason: a fill after it is a fill nobody could have got.
BELL = dtime(15, 30)

RESTING = "resting"
FILLING = "filling"
FILLED = "filled"
CANCELLED = "cancelled"
EXPIRED = "expired"
FAILED = "failed"

OPEN_STATES = (RESTING, FILLING)

ENTRY = "entry"
ADD_LEG = "add_leg"
EXIT_LEG = "exit_leg"
REVERSE = "reverse"
EXIT_ALL_LEG = "exit_all_leg"

EXIT_KINDS = (EXIT_LEG, REVERSE, EXIT_ALL_LEG)


class OrderBookUnavailable(RuntimeError):
    """The book could not be read or written. Never silently swallowed."""


# ---------------------------------------------------------------- the clock

def bell_on(day: date) -> datetime:
    """15:30 IST of that day, as an instant."""
    return datetime.combine(day, BELL, tzinfo=IST)


def ist_now(now: Optional[datetime] = None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(IST)


def ist_day(value: Any) -> Optional[str]:
    """The trading day an instant belongs to, in IST, as YYYY-MM-DD.

    Everything is stored in UTC and his day is an IST day, five and a half
    hours apart. A timestamp sliced at the T gives the wrong date for anything
    after 18:30 IST, which is most of when he reads his record.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(IST).date().isoformat()
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(IST).date().isoformat()


def expiry_for(now: Optional[datetime] = None) -> datetime:
    """When an order placed now would expire: the bell of today, in IST."""
    return bell_on(ist_now(now).date())


def session_is_over(now: Optional[datetime] = None) -> bool:
    """Past the bell. A resting order cannot be placed after it, and he is told why."""
    from swayam.services.expiry import session_is_over as _session_is_over

    return _session_is_over(now)


# ------------------------------------------------------------- reading them

def _client():
    from swayam.db import db

    return db.client


def _rows(res: Any) -> list[dict[str, Any]]:
    data = getattr(res, "data", None)
    return list(data) if isinstance(data, list) else []


def get_order(order_id: str) -> Optional[dict[str, Any]]:
    try:
        res = _client().table("swayam_orders").select("*").eq("id", str(order_id)).execute()
    except Exception as exc:  # noqa: BLE001
        raise OrderBookUnavailable(f"Could not read order {order_id}: {exc}") from exc
    rows = _rows(res)
    return rows[0] if rows else None


def orders_for_day(day: Optional[str] = None) -> list[dict[str, Any]]:
    """Every order of one IST trading day, newest first, plus anything still open.

    Anything still resting is ALWAYS included whatever day it was placed, so a
    row that somehow survived a day cannot hide from him behind a date filter.
    """
    want = day or ist_now().date().isoformat()
    try:
        res = _client().table("swayam_orders").select("*").order("placed_at", desc=True).limit(400).execute()
    except Exception as exc:  # noqa: BLE001
        raise OrderBookUnavailable(f"Could not read the order book: {exc}") from exc
    out = []
    for row in _rows(res):
        if row.get("status") in OPEN_STATES or ist_day(row.get("placed_at")) == want:
            out.append(row)
    return out


def open_orders() -> list[dict[str, Any]]:
    """Everything the watcher has to look at: resting, and in flight."""
    try:
        res = (
            _client().table("swayam_orders").select("*")
            .in_("status", list(OPEN_STATES))
            .order("placed_at", desc=False)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise OrderBookUnavailable(f"Could not read the resting orders: {exc}") from exc
    return _rows(res)


def siblings_of(group_id: Optional[str], *, exclude: Optional[str] = None) -> list[dict[str, Any]]:
    """The other orders placed by the same press of the ticket."""
    if not group_id:
        return []
    try:
        res = (
            _client().table("swayam_orders").select("*")
            .eq("group_id", str(group_id))
            .order("placed_at", desc=False)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise OrderBookUnavailable(f"Could not read the order's siblings: {exc}") from exc
    return [r for r in _rows(res) if str(r.get("id")) != str(exclude or "")]


# ------------------------------------------------------------- writing them

@dataclass(frozen=True)
class NewOrder:
    """One order to place. Everything about it is his, except the band."""

    kind: str
    leg: dict[str, Any]
    limit_price: float
    position_id: Optional[str] = None
    group_id: Optional[str] = None
    band: Any = None                       # services.price_band.PriceBand or None
    provenance: Optional[str] = None
    idempotency_key: Optional[str] = None


def place(orders: list[NewOrder], *, now: Optional[datetime] = None) -> list[dict[str, Any]]:
    """Writes orders into the book, all at once, and answers with the rows.

    Every order of one press shares a group, because when the first entry of a
    group fills and opens the trade, the rest have to join THAT trade rather
    than open more of their own.
    """
    if not orders:
        return []
    # Written in UTC even though the bell is an IST time. Postgres normalises a
    # timestamptz either way, but every other timestamp in this record is UTC
    # and a column that mixes offsets is one that gets compared as text
    # somewhere and quietly gives the wrong answer.
    expires = expiry_for(now).astimezone(timezone.utc).isoformat()
    placed = ist_now(now).astimezone(timezone.utc).isoformat()
    payload = []
    for order in orders:
        band = order.band
        payload.append({
            "id": str(uuid.uuid4()),
            "position_id": str(order.position_id) if order.position_id else None,
            "group_id": str(order.group_id) if order.group_id else None,
            "kind": order.kind,
            "leg": order.leg,
            "limit_price": round(float(order.limit_price), 2),
            "status": RESTING,
            "placed_at": placed,
            "expires_at": expires,
            "band_lower": (float(band.lower) if band is not None and band.known else None),
            "band_upper": (float(band.upper) if band is not None and band.known else None),
            "band_source": (band.source if band is not None else None),
            "idempotency_key": order.idempotency_key,
            "provenance": order.provenance,
        })
    try:
        res = _client().table("swayam_orders").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        raise OrderBookUnavailable(
            f"Nothing rests: the order book could not be written, so no order is waiting. {exc}"
        ) from exc
    rows = _rows(res)
    return rows if rows else payload


def claim(order_id: str) -> bool:
    """Takes this order out of `resting` so exactly one process can fill it.

    ONE CONDITIONAL UPDATE, and the database picks the winner. His
    requirement of 2026-09-10: "The move from resting to filled is one
    conditional update in the database that only one process can win, so two
    copies of the backend can never fill the same order twice."

    The `.eq("status", "resting")` is the whole safety property. A second
    caller updates nothing, gets no rows back, and is told it lost.
    """
    try:
        res = (
            _client().table("swayam_orders")
            .update({"status": FILLING})
            .eq("id", str(order_id))
            .eq("status", RESTING)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not claim order %s: %s", order_id, exc)
        return False
    return len(_rows(res)) == 1


def release(order_id: str, reason: str) -> None:
    """Puts a claimed order back to resting after a failure it can retry.

    Used when the market moved away between the watcher seeing the price and
    the fill path re-reading it. Nothing happened, so the order goes on
    waiting.
    """
    try:
        (
            _client().table("swayam_orders")
            .update({"status": RESTING, "failure_reason": reason})
            .eq("id", str(order_id))
            .eq("status", FILLING)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not release order %s: %s", order_id, exc)


def mark_filled(
    order_id: str,
    *,
    fill: dict[str, Any],
    result: dict[str, Any],
    position_id: Optional[str],
    now: Optional[datetime] = None,
) -> None:
    """It filled. What it filled at and what it produced go on the row."""
    update = {
        "status": FILLED,
        "filled_at": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
        "fill": fill,
        "result": result,
        "failure_reason": None,
    }
    if position_id:
        update["position_id"] = str(position_id)
    try:
        _client().table("swayam_orders").update(update).eq("id", str(order_id)).execute()
    except Exception as exc:  # noqa: BLE001
        # The leg IS on the trade. Losing the bookkeeping row is bad but it is
        # not the money, and it must be loud rather than silent.
        logger.error(
            "Order %s filled but the book could not be updated: %s", order_id, exc
        )


def mark_failed(order_id: str, reason: str) -> None:
    """It could not fill, and the position is exactly as it was."""
    try:
        (
            _client().table("swayam_orders")
            .update({"status": FAILED, "failure_reason": reason})
            .eq("id", str(order_id))
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not mark order %s failed: %s", order_id, exc)


def join_position(order_id: str, position_id: str) -> None:
    """An entry order whose sibling opened the trade first now joins that trade."""
    try:
        (
            _client().table("swayam_orders")
            .update({"kind": ADD_LEG, "position_id": str(position_id)})
            .eq("id", str(order_id))
            .eq("status", RESTING)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not point order %s at trade %s: %s", order_id, position_id, exc)


def cancel(order_id: str) -> dict[str, Any]:
    """He cancelled it. Only something still resting can be cancelled."""
    try:
        res = (
            _client().table("swayam_orders")
            .update({"status": CANCELLED})
            .eq("id", str(order_id))
            .eq("status", RESTING)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise OrderBookUnavailable(f"Could not cancel order {order_id}: {exc}") from exc
    rows = _rows(res)
    if not rows:
        raise LookupError(order_id)
    return rows[0]


def modify(order_id: str, *, limit_price: float, band: Any = None) -> dict[str, Any]:
    """A new price on the SAME order, so it keeps its id and its place in his book."""
    update: dict[str, Any] = {"limit_price": round(float(limit_price), 2)}
    if band is not None:
        update["band_lower"] = float(band.lower) if band.known else None
        update["band_upper"] = float(band.upper) if band.known else None
        update["band_source"] = band.source
    try:
        res = (
            _client().table("swayam_orders")
            .update(update)
            .eq("id", str(order_id))
            .eq("status", RESTING)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise OrderBookUnavailable(f"Could not change the price on order {order_id}: {exc}") from exc
    rows = _rows(res)
    if not rows:
        raise LookupError(order_id)
    return rows[0]


def expire_due(now: Optional[datetime] = None) -> list[dict[str, Any]]:
    """The bell. Everything still resting expires, and nothing is charged for it.

    Answers with the rows that expired, because one of them may be the last
    leg of an Exit everything, and he asked to be told about that in words.
    """
    at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    try:
        res = (
            _client().table("swayam_orders")
            .update({"status": EXPIRED})
            .eq("status", RESTING)
            .lte("expires_at", at.isoformat())
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not expire the resting orders: %s", exc)
        return []
    expired = _rows(res)
    if expired:
        logger.info("The bell expired %s resting order(s).", len(expired))
    return expired


# ------------------------------------------------------- reading one of them

def leg_label(leg: dict[str, Any]) -> str:
    """`23,800 CE`, the way every other screen names a leg."""
    try:
        return f"{float(leg.get('strike', 0)):,.0f} {str(leg.get('option_type', '')).upper()}"
    except (TypeError, ValueError):
        return str(leg.get("strike", "?"))


def side_needed(order: dict[str, Any]) -> str:
    """Which side of the book this order has to take. A buy pays the ask."""
    direction = str((order.get("leg") or {}).get("direction", "buy")).lower()
    return "ask" if direction in ("buy", "long") else "bid"


def would_fill(order: dict[str, Any], *, bid: Optional[float], ask: Optional[float]) -> bool:
    """Has the book reached his price.

    A buy fills when the ask is at or BELOW his limit, a sell when the bid is
    at or ABOVE it: his price or better, which is what an exchange does. This
    only decides whether to TRY. The fill itself is `services/fills.py`, which
    re-reads the book and can still refuse.
    """
    try:
        limit = float(order.get("limit_price"))
    except (TypeError, ValueError):
        return False
    if side_needed(order) == "ask":
        return ask is not None and ask > 0 and ask <= limit
    return bid is not None and bid > 0 and bid >= limit


def band_note(order: dict[str, Any]) -> str:
    """What the screen says about this order's band. Never an invented one."""
    source = order.get("band_source")
    lower, upper = order.get("band_lower"), order.get("band_upper")
    if source == "FYERS depth" and lower is not None and upper is not None:
        return f"inside today's band, {float(lower):,.2f} to {float(upper):,.2f}"
    if source:
        return "band not readable from FYERS; resting without a band check"
    return "no band recorded for this order"


def state_line(order: dict[str, Any], *, bid: Optional[float], ask: Optional[float]) -> dict[str, Any]:
    """What it is waiting for, the book now, and how far away it is.

    Every figure here is the real book or nothing at all. When the feed has no
    price for the contract the distance is None and the screen says the book
    could not be read, rather than showing a distance from a price that does
    not exist.
    """
    side = side_needed(order)
    market = ask if side == "ask" else bid
    limit = float(order.get("limit_price") or 0.0)
    distance: Optional[float] = None
    direction_word: Optional[str] = None
    if market is not None and market > 0:
        distance = round(abs(market - limit), 2)
        if side == "ask":
            direction_word = "fall" if market > limit else "already there"
        else:
            direction_word = "rise" if market < limit else "already there"
    return {
        "side": side,
        "waiting_for": f"waiting for the {side} to reach {limit:,.2f}",
        "book": market,
        "distance": distance,
        "needs": direction_word,
        "band": band_note(order),
        "expires": "expires 15:30",
    }
