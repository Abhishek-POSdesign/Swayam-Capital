"""The watcher: it looks at the book the desk is already reading, and nothing else.

WHY THIS EXISTS
---------------
A resting order is worth nothing unless something notices when the market
comes to it. This is that something.

THE ONE RULE THAT SHAPES ALL OF IT: **it never calls FYERS.** On 2026-09-08
the desk's own re-quoting produced 46 refusals from FYERS in ten minutes and
blanked his leg prices. `api/chain_feed.py` was built so that one FYERS call
per expiry serves every browser and every leg. The watcher hangs off THAT: it
is handed the chain the feed has just fetched, and it reads it. It adds no
request of its own, at any cadence, ever.

WHAT IT DOES, EACH TIME AN EXPIRY IS REFRESHED
----------------------------------------------
1. Expires anything that has reached the bell. Nothing is charged for it.
2. Reads the orders still resting on that expiry.
3. Asks, of each: has the book reached his price. A buy fills when the ask is
   at or below his limit, a sell when the bid is at or above it. His price or
   better, which is what an exchange does.
4. For one that has: claims it with a single conditional update that only one
   process can win, then sends it down EXACTLY the path a leg he pressed Send
   on takes. The fill is decided by `services/fills.py`, unchanged, which
   re-reads the book itself. Charges, the note, the execution key and the
   record all happen there, in the code that already does them.

WHAT IT NEVER DOES
------------------
It never fills from a closing book, never fills after 15:30, never fills the
same order twice, and never leaves a position half changed: a failure marks
the order and leaves the trade exactly as it was.

AND THE THING HE MUST NOT BE ALLOWED TO BELIEVE
-----------------------------------------------
**A resting order only fills while this backend is awake and the chain feed is
reading.** On Cloud Run that means while a page of his is open. It is not a
broker; nothing of his is watched while he is away. That sentence is on the
position area and in the handoff, in those words, because believing otherwise
would be worse than not having the feature at all.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Any, Optional

from swayam.services import orders as book

logger = logging.getLogger(__name__)

# The book is re-read at most this often, however many expiries refresh in one
# pass. The feed refreshes an expiry every three seconds, so this is about one
# read of the orders table per pass and no more.
READ_EVERY_SECONDS = 2.5

_last_read_at: float = 0.0
_cached_open: list[dict[str, Any]] = []
_registered = False

# What the last pass did, for /api/orders and the handoff to report honestly.
stats: dict[str, Any] = {
    "passes": 0,
    "filled": 0,
    "failed": 0,
    "expired": 0,
    "last_pass_at": None,
    "last_error": None,
}


def invalidate() -> None:
    """Forget the cached book, so a newly placed order is seen on the next pass."""
    global _last_read_at
    _last_read_at = 0.0


def reset() -> None:
    """For the test suite, which must not inherit a pass from the test before it."""
    global _last_read_at, _cached_open, _registered
    _last_read_at = 0.0
    _cached_open = []
    _registered = False
    stats.update({"passes": 0, "filled": 0, "failed": 0, "expired": 0,
                  "last_pass_at": None, "last_error": None})


def _open_orders(force: bool = False) -> list[dict[str, Any]]:
    global _last_read_at, _cached_open
    now = time.time()
    if not force and (now - _last_read_at) < READ_EVERY_SECONDS:
        return _cached_open
    try:
        _cached_open = book.open_orders()
    except book.OrderBookUnavailable as exc:
        stats["last_error"] = str(exc)
        logger.warning("The watcher could not read the order book: %s", exc)
        return _cached_open
    _last_read_at = now
    return _cached_open


# ------------------------------------------------------------- the book read

def _chain_for(underlying: str, expiry: str) -> tuple[Optional[float], dict[tuple[float, str], dict[str, Any]], str]:
    """The chain for one expiry, FROM THE FEED. Registers demand, calls nothing.

    Reading it is also what keeps that expiry in demand while an order rests,
    so the feed does not stop refreshing a strike he is waiting on just
    because no browser is looking at it.

    Returns the spot, a (strike, type) -> quote lookup, and the feed's own
    state for that reading: live, delayed, closing or unavailable.
    """
    from swayam.api.routes.market import WIDE_CHAIN_STRIKES, epoch_for, fetch_chain_snapshot
    from swayam.api.routes.positions import _FYERS_INDEX_SYMBOLS, _build_chain_lookup

    symbol = _FYERS_INDEX_SYMBOLS.get(str(underlying).upper(), "NSE:NIFTY50-INDEX")
    # THE SAME KEY EVERYTHING ELSE READS, so the watcher costs no extra FYERS
    # call of its own, and the expiry's epoch is remembered rather than looked
    # up again on every pass. The watcher still sees exactly the 50 strikes it
    # saw before, which matters because a resting order can sit well away from
    # the money.
    epoch = epoch_for(symbol, str(expiry)) if expiry else None
    # Without an epoch the nearest expiry's wide chain is the honest fallback,
    # at full width.
    snap = fetch_chain_snapshot(symbol, WIDE_CHAIN_STRIKES, epoch) if epoch \
        else fetch_chain_snapshot(symbol, WIDE_CHAIN_STRIKES)
    if snap.data is None:
        return None, {}, "unavailable"
    spot, lookup = _build_chain_lookup(snap.data)
    return (spot or None), lookup, snap.state


# --------------------------------------------------------------- one pass

def evaluate(underlying: str = "NIFTY", expiry: Optional[str] = None, *, now: Optional[datetime] = None) -> dict[str, Any]:
    """One pass over the resting orders, for one expiry or for all of them.

    Synchronous on purpose: it is run in a worker thread by the hook below, so
    it can use the same blocking database and fill code every other path uses.
    """
    at = now or datetime.now(timezone.utc)
    stats["passes"] += 1
    stats["last_pass_at"] = at.isoformat()

    expired = book.expire_due(at)
    if expired:
        stats["expired"] += len(expired)
        invalidate()
        _announce_expiries(expired)

    resting = [o for o in _open_orders() if o.get("status") == book.RESTING]
    if expiry:
        resting = [o for o in resting if str((o.get("leg") or {}).get("expiry_date")) == str(expiry)]
    if not resting:
        return {"looked_at": 0, "filled": 0}

    # NOTHING FILLS WHEN THE MARKET IS SHUT. The feed keeps the closing book
    # and a fill against it is one nobody could have got. This is the same
    # clock everything else reads.
    from swayam.api.chain_feed import chain_feed

    if not chain_feed.is_open():
        return {"looked_at": len(resting), "filled": 0, "why": "the market is shut"}

    filled = 0
    by_expiry: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for order in resting:
        leg = order.get("leg") or {}
        key = (str(leg.get("underlying") or underlying or "NIFTY"), str(leg.get("expiry_date") or ""))
        by_expiry.setdefault(key, []).append(order)

    for (under, exp), group in by_expiry.items():
        if not exp:
            continue
        try:
            _spot, lookup, state = _chain_for(under, exp)
        except Exception as exc:  # noqa: BLE001 - one bad expiry must not stop the rest
            stats["last_error"] = str(exc)
            logger.warning("The watcher could not read the chain for %s: %s", exp, exc)
            continue
        # A closing or unavailable reading is not a book to fill against.
        if state not in ("live", "delayed"):
            continue
        for order in group:
            leg = order.get("leg") or {}
            quote = lookup.get((float(leg.get("strike", 0) or 0), str(leg.get("option_type", "")).upper())) or {}
            if not book.would_fill(order, bid=quote.get("bid"), ask=quote.get("ask")):
                continue
            if fill_now(order):
                filled += 1

    return {"looked_at": len(resting), "filled": filled}


def fill_now(order: dict[str, Any]) -> bool:
    """Claim this order and send it down the real path. True when it filled.

    THE CLAIM IS THE SAFETY PROPERTY. `book.claim` is one conditional update
    from `resting` to `filling`, and only one process can win it. Everything
    after this line runs exactly once for this order.
    """
    order_id = str(order.get("id"))
    if not book.claim(order_id):
        return False
    invalidate()

    kind = str(order.get("kind"))
    try:
        if kind == book.ENTRY:
            done = _fill_entry(order)
        elif kind == book.ADD_LEG:
            done = _fill_add_leg(order)
        elif kind in book.EXIT_KINDS:
            done = _fill_exit(order)
        else:
            book.mark_failed(order_id, f"This build does not know how to fill a {kind!r} order.")
            stats["failed"] += 1
            return False
    except _PriceMovedAway as moved:
        # Nothing happened. The book was there when the watcher looked and had
        # gone by the time the fill path re-read it, which is ordinary. It goes
        # on waiting.
        book.release(order_id, str(moved))
        return False
    except Exception as exc:  # noqa: BLE001
        logger.exception("Resting order %s could not be filled", order_id[:8])
        book.mark_failed(order_id, _plain(exc))
        stats["failed"] += 1
        return False

    if done:
        stats["filled"] += 1
    return done


class _PriceMovedAway(RuntimeError):
    """The market was at his price and was not there any more. Nothing happened."""


def _must_be_a_fill(response: dict[str, Any], *, position_id: str, fills: list[Any]) -> None:
    """Refuse to call anything a fill unless a trade and a fill actually exist.

    ADDED 2026-09-11, from the main chat's review, and it is the difference
    between a bookkeeping bug and a lie about his money.

    Before this, the watcher re-sent an order down a path that could REST it.
    When the book had moved away in the meantime, that path wrote a second
    order for the same leg and answered with no position and no fills, and the
    watcher then marked the original order FILLED, with an empty fill. A
    duplicate in his book, and an order shown as filled that never was.

    The re-send can no longer rest, so this cannot happen. It stays because an
    empty answer must never again be read as a fill: it puts the order back to
    resting, exactly where it was, and nothing is written.
    """
    resting = response.get("resting") or []
    if resting or str(response.get("status") or "") == "resting":
        raise _PriceMovedAway(
            "The book moved away before this could fill, so nothing was sent and "
            "the order is still waiting."
        )
    if not position_id or not fills:
        raise _PriceMovedAway(
            "Nothing filled: the answer carried no trade and no fill, so the order "
            "is still waiting and nothing was written."
        )


def _plain(exc: Exception) -> str:
    """A refusal in words, out of whatever shape it arrived in."""
    from fastapi import HTTPException

    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            refused = detail.get("refused_legs") or []
            if refused and isinstance(refused[0], dict):
                return str(refused[0].get("reason") or detail.get("error") or detail)
            return str(detail.get("error") or detail)
        return str(detail)
    return str(exc)


def _raise_if_price(exc: Exception) -> None:
    """A 422 is his price, not a fault. Anything else is a real failure."""
    from fastapi import HTTPException

    if isinstance(exc, HTTPException) and exc.status_code == 422:
        raise _PriceMovedAway(_plain(exc)) from exc


# ------------------------------------------------------------- the four paths

def _spot_for(order: dict[str, Any]) -> float:
    """The spot to send with the order, read from the feed, never invented."""
    leg = order.get("leg") or {}
    spot, _lookup, _state = _chain_for(
        str(leg.get("underlying") or "NIFTY"), str(leg.get("expiry_date") or "")
    )
    if not spot or spot <= 0:
        raise RuntimeError(
            "NIFTY's spot could not be read from the chain feed, so this order was "
            "not sent. Nothing changed. It will be tried again on the next reading."
        )
    return float(spot)


def _leg_request(order: dict[str, Any]):
    from swayam.api.models_api import LegRequest

    leg = order.get("leg") or {}
    return LegRequest(
        strike=float(leg["strike"]),
        option_type=str(leg["option_type"]).upper(),
        direction=str(leg["direction"]).lower(),
        quantity_lots=int(leg.get("quantity_lots", 1) or 1),
        expiry_date=str(leg["expiry_date"]),
        order_type="LIMIT",
        # His price travels with the leg, so services/fills.py fills at his
        # price OR BETTER exactly as it would have on the ticket.
        entry_premium=float(order["limit_price"]),
        limit_price=float(order["limit_price"]),
    )


def _fill_entry(order: dict[str, Any]) -> bool:
    """It opens the trade, unless a sibling of the same press already has.

    His rule: one press, one trade. When no leg of a ticket could fill, every
    leg rests, and the FIRST of them to fill opens the trade. The rest join
    that trade rather than opening more of their own.
    """
    from swayam.api.models_api import ExecuteRequest
    from swayam.api.routes.execution import execute_trade_now

    order_id = str(order.get("id"))
    leg = order.get("leg") or {}

    # Re-read the group at the last moment: a sibling may have opened the
    # trade a fraction of a second ago.
    opened = _opened_sibling(order)
    if opened:
        return _fill_add_leg({**order, "position_id": opened})

    req = ExecuteRequest(
        strategy_name=str(leg.get("strategy_name") or "Custom"),
        underlying=str(leg.get("underlying") or "NIFTY"),
        legs=[_leg_request(order)],
        current_spot=_spot_for(order),
        mode="paper",
        leg_order="as_sent",
        execution_mode="one_by_one",
        idempotency_key=f"rest-{order_id}",
    )
    try:
        response = execute_trade_now(req)
    except Exception as exc:
        _raise_if_price(exc)
        raise

    position_id = str(response.get("position_id") or "")
    fills = response.get("fills") or []
    # NO TRADE, NO FILL. `execute_trade_now` cannot rest, so this should be
    # unreachable; it is here because the alternative, if it ever were
    # reachable, is an order marked filled on an empty fill, which is a lie
    # about his money. Anything short of a real position AND a real fill puts
    # the order back to resting untouched.
    _must_be_a_fill(response, position_id=position_id, fills=fills)
    book.mark_filled(
        order_id,
        fill=(fills[0] if fills else {}),
        result={
            "position_id": position_id,
            "sequence": (fills[0].get("sequence") if fills else 1),
            "opened_the_trade": True,
            "strategy_name": response.get("strategy_name"),
        },
        position_id=position_id,
    )
    # Every sibling still resting now belongs to this trade.
    for sib in book.siblings_of(order.get("group_id"), exclude=order_id):
        if sib.get("status") == book.RESTING and sib.get("kind") == book.ENTRY:
            book.join_position(str(sib.get("id")), position_id)
    invalidate()
    return True


def _opened_sibling(order: dict[str, Any]) -> Optional[str]:
    """The trade a sibling of this press has already opened, if one has."""
    for sib in book.siblings_of(order.get("group_id"), exclude=str(order.get("id"))):
        if sib.get("position_id"):
            return str(sib["position_id"])
    return None


def _fill_add_leg(order: dict[str, Any]) -> bool:
    """It joins a trade that is already open, the way "execute one by one" does."""
    from swayam.api.models_api import AddLegRequest
    from swayam.api.routes.execution import add_leg_now

    order_id = str(order.get("id"))
    position_id = str(order.get("position_id") or "")
    if not position_id:
        raise RuntimeError("This order has no trade to join, so nothing was sent.")

    req = AddLegRequest(
        leg=_leg_request(order),
        current_spot=_spot_for(order),
        idempotency_key=f"rest-{order_id}",
    )
    try:
        response = add_leg_now(position_id, req)
    except Exception as exc:
        _raise_if_price(exc)
        raise

    fill = response.get("fill") or {}
    _must_be_a_fill(response, position_id=position_id, fills=[fill] if fill else [])
    book.mark_filled(
        order_id,
        fill=fill,
        result={
            "position_id": position_id,
            "sequence": fill.get("sequence"),
            "joined_the_trade": True,
        },
        position_id=position_id,
    )
    return True


def _fill_exit(order: dict[str, Any]) -> bool:
    """It squares off, or reverses, one leg of a trade he holds."""
    from swayam.api.routes.execution import ExitLegRequest, exit_leg_now

    order_id = str(order.get("id"))
    leg = order.get("leg") or {}
    position_id = str(order.get("position_id") or "")
    sequence = leg.get("sequence")
    if not position_id or sequence is None:
        raise RuntimeError("This exit order does not name a leg, so nothing was sent.")

    req = ExitLegRequest(
        order_type="LIMIT",
        limit_price=float(order["limit_price"]),
        close_reason=str(leg.get("close_reason") or "manual"),
        notes=leg.get("notes"),
        idempotency_key=f"rest-{order_id}",
    )
    try:
        response = exit_leg_now(
            position_id, int(sequence), req, reverse=(order.get("kind") == book.REVERSE)
        )
    except Exception as exc:
        _raise_if_price(exc)
        raise

    fill = response.get("fill") or {}
    _must_be_a_fill(response, position_id=position_id, fills=[fill] if fill else [])
    book.mark_filled(
        order_id,
        fill=fill,
        result={
            "position_id": position_id,
            "sequence": int(sequence),
            "last_leg": bool(response.get("last_leg")),
            "status": response.get("status"),
        },
        position_id=position_id,
    )
    return True


# ------------------------------------------------------- the bell's warning

def _announce_expiries(expired: list[dict[str, Any]]) -> None:
    """Say, in the log, what the bell just killed.

    The loud half of this is on his screens: `/api/orders` marks an expired
    `exit_all_leg` whose trade is STILL OPEN, and the position area and Home
    both say so in words, tied to the 15:20 naked-shorts check. He asked for
    that on 2026-09-10 because a resting exit that expires can leave him
    holding a leg he meant to be out of. It is a warning only; it never trades.
    """
    for row in expired:
        if row.get("kind") == book.EXIT_ALL_LEG:
            logger.warning(
                "The bell expired an Exit everything leg on trade %s at %s. "
                "That leg is still open.",
                str(row.get("position_id"))[:8], row.get("limit_price"),
            )


# ------------------------------------------------------ hooked to the feed

async def on_chain_refresh(key: str, data: dict[str, Any]) -> None:
    """Called by the chain feed after it refreshes an expiry. Never calls FYERS.

    The work is blocking, so it runs in a worker thread rather than on the
    feed's own loop: a slow database read must never delay the next price.
    """
    try:
        await asyncio.to_thread(evaluate)
    except Exception as exc:  # noqa: BLE001 - a bad pass must not kill the feed
        stats["last_error"] = str(exc)
        logger.warning("A watcher pass failed: %s", exc)


def register(feed=None) -> bool:
    """Attach the watcher to the chain feed. Idempotent.

    Only the feed's LEADER refreshes, so only the leader's watcher ever looks
    at the market. The claim in `services/orders.py` is what makes a second
    copy of the backend safe anyway.
    """
    global _registered
    if _registered:
        return False
    if feed is None:
        from swayam.api.chain_feed import chain_feed as feed
    feed.on_refresh(on_chain_refresh)
    _registered = True
    logger.info("The resting-order watcher is attached to the chain feed.")
    return True
