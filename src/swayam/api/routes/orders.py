"""His open orders: read them, change the price, cancel them.

WHY THIS EXISTS
---------------
Build B, `docs/builds/BUILD_03_RESTING_ORDERS.md` section 3.4. A limit the
book has not reached now waits instead of refusing, and a thing that waits has
to be visible and had to be changeable, or it is worse than a refusal: he
would not know what the terminal was holding on his behalf.

WHAT THIS FILE ANSWERS WITH
---------------------------
The three groups the position area draws, in his words rather than in states:
what is resting and exactly what each one waits for, what filled from the book
today, and what expired or was cancelled. Every price on it is the real book
from the chain feed or the word unavailable with the reason. The distance to
his price is arithmetic on two real numbers, never a guess.

TWO THINGS IT SAYS OUT LOUD
---------------------------
1. **An order only fills while this backend is awake and the chain feed is
   reading**, which on Cloud Run means while a page of his is open. It is not
   a broker. That sentence travels with every reply so no screen can forget it.
2. **A resting exit that reached the bell while its trade is still open** is
   named, with the leg, because he may believe he is flat when he is not. His
   instruction of 2026-09-10, tied to the 15:20 naked-shorts check that
   already exists. A warning only; nothing here ever trades.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from swayam.db import db
from swayam.services import order_watcher
from swayam.services import orders as book
from swayam.services.price_band import band_for_leg, check_price

logger = logging.getLogger(__name__)

router = APIRouter()


# The one sentence he must never be without. Repeated wherever an order is
# shown, because believing a resting order is watched while he is away would
# be worse than not having resting orders at all.
AWAKE_NOTE = (
    "A resting order fills only while this terminal is awake and reading prices, "
    "which means while one of your pages is open. It is not sitting at the broker "
    "and nothing is watched while you are away."
)


def _positions_named(ids: set[str]) -> dict[str, dict[str, Any]]:
    """The name and status of every trade these orders belong to."""
    real = {i for i in ids if i}
    if not real:
        return {}
    try:
        res = (
            db.client.table("swayam_positions")
            .select("id,strategy_name,status,legs")
            .in_("id", list(real))
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read the trades behind the orders: %s", exc)
        return {}
    return {str(r["id"]): r for r in (getattr(res, "data", None) or [])}


def _book_for(orders: list[dict[str, Any]]) -> tuple[dict[tuple[str, float, str], dict[str, Any]], str]:
    """The live book for every contract an order is waiting on.

    Read from the chain feed, which costs no FYERS call while the feed already
    holds the expiry, and which registers demand so the feed keeps reading the
    strike he is waiting on even when no browser is looking at it.
    """
    quotes: dict[tuple[str, float, str], dict[str, Any]] = {}
    worst = "live"
    wanted: set[tuple[str, str]] = set()
    for order in orders:
        leg = order.get("leg") or {}
        if leg.get("expiry_date"):
            wanted.add((str(leg.get("underlying") or "NIFTY"), str(leg["expiry_date"])))
    if not wanted:
        return quotes, "unavailable"

    rank = {"live": 0, "delayed": 1, "closing": 2, "unavailable": 3}
    seen: list[str] = []
    for underlying, expiry in wanted:
        try:
            _spot, lookup, state = order_watcher._chain_for(underlying, expiry)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read the book for %s: %s", expiry, exc)
            seen.append("unavailable")
            continue
        seen.append(state)
        for (strike, opt_type), quote in lookup.items():
            quotes[(expiry, float(strike), str(opt_type).upper())] = quote
    if seen:
        worst = max(seen, key=lambda s: rank.get(s, 3))
    return quotes, worst


def _quote_for(order: dict[str, Any], quotes: dict[tuple[str, float, str], dict[str, Any]]) -> dict[str, Any]:
    leg = order.get("leg") or {}
    key = (
        str(leg.get("expiry_date") or ""),
        float(leg.get("strike") or 0.0),
        str(leg.get("option_type") or "").upper(),
    )
    return quotes.get(key) or {}


def _render(
    order: dict[str, Any],
    *,
    quotes: dict[tuple[str, float, str], dict[str, Any]],
    trades: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """One order, in the shape the position area draws it."""
    leg = order.get("leg") or {}
    quote = _quote_for(order, quotes)
    position_id = str(order.get("position_id") or "") or None
    trade = trades.get(position_id or "") or {}

    out: dict[str, Any] = {
        "id": str(order.get("id")),
        "kind": order.get("kind"),
        "status": order.get("status"),
        "position_id": position_id,
        "group_id": order.get("group_id"),
        # What it belongs to, in words, which is what the mockup prints.
        "trade_label": (
            f"{trade.get('strategy_name') or 'Trade'}"
            if position_id
            else "New trade"
        ),
        "trade_note": (
            f"#{position_id[:8]} · {_kind_word(order.get('kind'))}"
            if position_id
            else "entry · opens when it fills"
        ),
        "direction": str(leg.get("direction") or "").lower(),
        "strike": leg.get("strike"),
        "option_type": leg.get("option_type"),
        "expiry_date": leg.get("expiry_date"),
        "quantity_lots": leg.get("quantity_lots"),
        "sequence": leg.get("sequence"),
        "leg_label": book.leg_label(leg),
        "limit_price": _f(order.get("limit_price")),
        "placed_at": order.get("placed_at"),
        "expires_at": order.get("expires_at"),
        "filled_at": order.get("filled_at"),
        "fill": order.get("fill"),
        "result": order.get("result"),
        "band_lower": _f(order.get("band_lower")),
        "band_upper": _f(order.get("band_upper")),
        "band_source": order.get("band_source"),
        "band_note": book.band_note(order),
        "failure_reason": order.get("failure_reason"),
        "provenance": order.get("provenance"),
        "bid": quote.get("bid"),
        "ask": quote.get("ask"),
    }

    if order.get("status") in book.OPEN_STATES:
        out["state"] = book.state_line(order, bid=quote.get("bid"), ask=quote.get("ask"))
        out["can_modify"] = order.get("status") == book.RESTING
        out["can_cancel"] = order.get("status") == book.RESTING
        out["in_flight"] = order.get("status") == book.FILLING
    else:
        out["can_modify"] = False
        out["can_cancel"] = False
        out["in_flight"] = False
    return out


def _kind_word(kind: Any) -> str:
    return {
        book.ENTRY: "entry",
        book.ADD_LEG: "joins this trade",
        book.EXIT_LEG: "exit",
        book.REVERSE: "reverse",
        book.EXIT_ALL_LEG: "exit everything",
    }.get(str(kind), str(kind))


def _f(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bell_warnings(rows: list[dict[str, Any]], trades: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """A resting exit that the bell killed while its trade is still open.

    His instruction, 2026-09-10: he presses Exit everything, three legs fill
    and the fourth rests; if the book never reaches his price that leg is
    still his at 15:30, and he may walk away believing he is flat. This is the
    line that stops him. It says what is still open and points at the 15:20
    naked-shorts check, which is the thing that already tells him whether what
    he holds is hedged.
    """
    out: list[dict[str, Any]] = []
    for row in rows:
        if row.get("status") != book.EXPIRED:
            continue
        if row.get("kind") not in (book.EXIT_ALL_LEG, book.EXIT_LEG, book.REVERSE):
            continue
        position_id = str(row.get("position_id") or "")
        trade = trades.get(position_id) or {}
        if trade.get("status") != "open":
            continue
        leg = row.get("leg") or {}
        whole = row.get("kind") == book.EXIT_ALL_LEG
        out.append({
            "position_id": position_id,
            "leg_label": book.leg_label(leg),
            "kind": row.get("kind"),
            "headline": (
                f"You are NOT out of {trade.get('strategy_name') or 'this trade'}."
                if whole
                else f"{book.leg_label(leg)} is still open."
            ),
            "detail": (
                f"Your {float(row.get('limit_price') or 0):,.2f} on {book.leg_label(leg)} "
                f"never got its price, so it expired at the bell and that leg is still yours. "
                f"Check the 15:20 naked-shorts reading before you leave it overnight."
            ),
        })
    return out


# ------------------------------------------------------------------- routes

@router.get("/api/orders")
def get_orders(date: str = Query(default="today", description="today, or an IST date as YYYY-MM-DD")) -> dict[str, Any]:
    """His order book for the day, in the three groups the position area draws."""
    day = None if date == "today" else date

    # The bell first, so nothing can be shown resting after 15:30 even if the
    # watcher has not had a pass since.
    try:
        book.expire_due()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not run the bell sweep before reading the orders: %s", exc)

    try:
        rows = book.orders_for_day(day)
    except book.OrderBookUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Your open orders could not be read, so none are shown rather than "
                f"a list that might be missing one. {exc}"
            ),
        ) from exc

    open_rows = [r for r in rows if r.get("status") in book.OPEN_STATES]
    trades = _positions_named({str(r.get("position_id") or "") for r in rows})
    quotes, market_state = _book_for(open_rows) if open_rows else ({}, "closing")

    rendered = [_render(r, quotes=quotes, trades=trades) for r in rows]
    resting = [r for r in rendered if r["status"] in book.OPEN_STATES]
    filled = [r for r in rendered if r["status"] == book.FILLED]
    done = [r for r in rendered if r["status"] in (book.EXPIRED, book.CANCELLED, book.FAILED)]

    from swayam.api.chain_feed import chain_feed

    return {
        "day": day or book.ist_now().date().isoformat(),
        "market_state": market_state if open_rows else ("live" if chain_feed.is_open() else "closing"),
        "read_at": datetime.now(timezone.utc).isoformat(),
        "session_is_over": book.session_is_over(),
        "awake_note": AWAKE_NOTE,
        "watcher": {
            "passes": order_watcher.stats.get("passes"),
            "filled": order_watcher.stats.get("filled"),
            "last_pass_at": order_watcher.stats.get("last_pass_at"),
            "last_error": order_watcher.stats.get("last_error"),
        },
        "resting": resting,
        "filled": filled,
        "closed": done,
        "counts": {"resting": len(resting), "filled": len(filled), "closed": len(done)},
        "warnings": _bell_warnings(rows, trades),
    }


class ModifyOrderRequest(BaseModel):
    """A new price on an order that is still waiting. The price and nothing else."""

    limit_price: float = Field(..., gt=0.0, description="His new price for this order")


@router.patch("/api/orders/{order_id}")
def modify_order(order_id: str, req: ModifyOrderRequest) -> dict[str, Any]:
    """Changes the price on a resting order, keeping its id and its place.

    Refuses on anything that is not resting, because an order that has filled,
    expired or been cancelled has already had its effect and re-pricing it
    would rewrite history.
    """
    existing = _resting_or_refuse(order_id, verb="re-price")
    leg = existing.get("leg") or {}

    band = band_for_leg(
        underlying=str(leg.get("underlying") or "NIFTY"),
        expiry=str(leg.get("expiry_date") or ""),
        strike=float(leg.get("strike") or 0.0),
        option_type=str(leg.get("option_type") or "CE"),
    )
    refusal = check_price(band, float(req.limit_price))
    if refusal:
        raise HTTPException(status_code=422, detail={"error": refusal, "band_source": band.source})

    try:
        row = book.modify(order_id, limit_price=float(req.limit_price), band=band)
    except LookupError as exc:
        raise HTTPException(
            status_code=409,
            detail="That order stopped resting while you were typing. Refresh your open orders.",
        ) from exc
    except book.OrderBookUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    order_watcher.invalidate()
    return {
        "id": str(row.get("id")),
        "status": row.get("status"),
        "limit_price": _f(row.get("limit_price")),
        "band_note": book.band_note(row),
        "awake_note": AWAKE_NOTE,
        "message": (
            f"{book.leg_label(leg)} now waits for the {book.side_needed(row)} to reach "
            f"{float(req.limit_price):,.2f}. {book.band_note(row)}."
        ),
    }


@router.delete("/api/orders/{order_id}")
def cancel_order(order_id: str) -> dict[str, Any]:
    """Takes a resting order out of the book. Nothing was charged and nothing is."""
    existing = _resting_or_refuse(order_id, verb="cancel")
    leg = existing.get("leg") or {}
    try:
        row = book.cancel(order_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=409,
            detail="That order stopped resting a moment ago. Refresh your open orders to see what it did.",
        ) from exc
    except book.OrderBookUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    order_watcher.invalidate()
    return {
        "id": str(row.get("id")),
        "status": row.get("status"),
        "message": (
            f"Cancelled. {book.leg_label(leg)} is no longer waiting, and it cost nothing."
        ),
    }


def _resting_or_refuse(order_id: str, *, verb: str) -> dict[str, Any]:
    """The order, if it is still resting. Otherwise a plain answer about why not."""
    try:
        existing = book.get_order(order_id)
    except book.OrderBookUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if existing is None:
        raise HTTPException(status_code=404, detail="There is no order with that id.")

    status = existing.get("status")
    if status == book.RESTING:
        return existing
    if status == book.FILLING:
        raise HTTPException(
            status_code=409,
            detail=(
                f"That order is being filled right now, so it cannot be {verb}led. "
                "Refresh your open orders in a second to see what it did."
            ) if verb == "cancel" else (
                "That order is being filled right now, so its price cannot be changed. "
                "Refresh your open orders in a second to see what it did."
            ),
        )
    said = {
        book.FILLED: "has already filled and is part of a trade",
        book.EXPIRED: "expired at the bell",
        book.CANCELLED: "was already cancelled",
        book.FAILED: "failed and did not touch your position",
    }.get(str(status), f"is {status}")
    raise HTTPException(
        status_code=409,
        detail=(
            f"That order {said}, so it cannot be {'cancelled' if verb == 'cancel' else 're-priced'}. "
            "Your open orders on the desk show what it did."
        ),
    )
