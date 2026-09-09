"""
How a paper leg gets its fill price.

WHY THIS EXISTS
---------------
Until the execution ticket, a paper trade was filled at whatever price the
browser sent. A limit of ₹1 on a ₹100 option would have "filled". That is a
fabricated fill, and it falls under his first rule: every number is real from
FYERS or it says unavailable.

A fill now needs a market to fill against, and it fills the way an exchange
fills. His words, 2026-09-09 evening: "bid and ask matter more because sellers
need buyers and buyers need sellers... I want to keep it as close as I can to
reality."

  * MARKET: a buy pays the best ASK, a sell receives the best BID, read from
    the SERVER'S live chain at the moment of sending. The last traded price is
    history and is kept on the leg only so the record can show what the
    spread cost.
  * LIMIT: fills at his price OR BETTER, which is what the exchange does. A
    buy limit at or above the ask fills at the ask; a sell limit at or below
    the bid fills at the bid. A limit away from the market does not fill, and
    the answer says where the market is. There are no resting orders in this
    app, so none are pretended.
  * No quote, no fill. After the close the chain carries a closing book, and a
    fill against it is a fill nobody could have got.

The same rule runs in reverse for an exit: a leg he bought is sold back at the
bid, a leg he sold is bought back at the ask. `exit_side_of` says which.

PR 1 (docs/PLAN.md 2.12.2) filled at the traded price. PR 2 is this file.
Positions opened under PR 1 carry `fill_basis = "traded_price"` and are not
comparable with anything filled here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

FILL_BASIS: Literal["traded_price", "bid_ask"] = "bid_ask"


class FillRefused(Exception):
    """The leg cannot be filled honestly. Carries what he can DO about it."""

    def __init__(self, message: str, *, leg: str, market: Optional[float] = None) -> None:
        super().__init__(message)
        self.leg = leg
        self.market = market


@dataclass(frozen=True)
class LegQuote:
    """What the market says about one contract right now."""

    ltp: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    spot: Optional[float]
    state: str  # live | delayed | closing | unavailable
    market_open: bool
    as_of: Optional[str]
    note: Optional[str] = None

    @property
    def tradeable(self) -> bool:
        """A book a fill may be measured against. A closing book is not one."""
        return self.state in ("live", "delayed") and (
            (self.bid is not None and self.bid > 0) or (self.ask is not None and self.ask > 0)
        )


@dataclass(frozen=True)
class Fill:
    price: float
    basis: str
    order_type: str
    limit_price: Optional[float]
    ltp_at_fill: Optional[float]
    bid_at_fill: Optional[float]
    ask_at_fill: Optional[float]
    filled_at: str
    how: str
    side_hit: str = ""  # "ask" or "bid": which side of the book this fill took


def exit_side_of(entry_direction: str) -> str:
    """The direction that closes a leg: a bought leg is sold, a sold leg is bought."""
    return "sell" if entry_direction.lower() in ("buy", "long") else "buy"


def spread_cost_inr(direction: str, fill_price: float, ltp: Optional[float], units: int) -> Optional[float]:
    """What crossing the spread cost against the last traded price. Negative is a cost.

    A buy at the ask above the traded price costs; a sell at the bid below the
    traded price costs. None when no traded price was published.
    """
    if ltp is None:
        return None
    diff = (ltp - fill_price) if direction.lower() == "buy" else (fill_price - ltp)
    return round(diff * units, 2)


def quote_leg(*, strike: float, expiry: str, option_type: str, underlying: str = "NIFTY") -> LegQuote:
    """The live quote for one contract, from the shared chain feed.

    Goes through the same route the desk uses for its leg prices, so a fill is
    measured against exactly the book he was looking at, read again at the
    moment of sending.
    """
    from swayam.api.routes.market import get_option_quote

    symbols = {
        "NIFTY": "NSE:NIFTY50-INDEX",
        "NIFTY50": "NSE:NIFTY50-INDEX",
        "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
        "FINNIFTY": "NSE:FINNIFTY-INDEX",
    }
    symbol = symbols.get(underlying.upper(), "NSE:NIFTY50-INDEX")
    try:
        q: dict[str, Any] = get_option_quote(strike=strike, expiry=expiry, type=option_type, symbol=symbol)
    except Exception as exc:  # the route raises HTTPException on a bad type only
        logger.warning("quote_leg failed for %s %s %s: %s", strike, option_type, expiry, exc)
        return LegQuote(None, None, None, None, "unavailable", False, None, note=str(exc))
    return quote_from_dict(q)


def quote_from_dict(q: dict[str, Any]) -> LegQuote:
    """A LegQuote from the quote route's answer, or from a chain row shaped like one."""

    def _f(v: Any) -> Optional[float]:
        try:
            return float(v) if v is not None and float(v) > 0 else None
        except (TypeError, ValueError):
            return None

    return LegQuote(
        ltp=_f(q.get("ltp")),
        bid=_f(q.get("bid")),
        ask=_f(q.get("ask")),
        spot=_f(q.get("spot")),
        state=str(q.get("freshness") or q.get("state") or "unavailable"),
        market_open=bool(q.get("market_open")),
        as_of=q.get("as_of"),
        note=q.get("note"),
    )


def _book_side_for(direction: str, quote: LegQuote) -> tuple[Optional[float], str]:
    """The price this side would actually get right now, and which side of the book it is."""
    if direction.lower() == "buy":
        return quote.ask, "ask"
    return quote.bid, "bid"


def resolve_fill(
    *,
    direction: str,
    order_type: str,
    limit_price: Optional[float],
    quote: LegQuote,
    leg_label: str,
) -> Fill:
    """Decides the fill for one leg, or refuses with a reason he can act on.

    Raises:
        FillRefused: no tradeable book, a missing side, or a limit the market is not at.
    """
    direction = direction.lower()
    order_type = (order_type or "MARKET").upper()
    if order_type not in ("MARKET", "LIMIT"):
        raise FillRefused(
            f"{leg_label}: order type must be MARKET or LIMIT, not {order_type}.",
            leg=leg_label,
        )

    if not quote.tradeable:
        if quote.state == "closing" or (quote.ltp and not quote.market_open):
            raise FillRefused(
                f"{leg_label}: the market is closed, so nothing can fill. The last book "
                f"was the closing book and a fill against it is one nobody could have got. "
                f"Keep the structure on the desk and send it in your window.",
                leg=leg_label,
                market=quote.ltp,
            )
        raise FillRefused(
            f"{leg_label}: no live bid or ask, so it cannot be filled. "
            + (quote.note or "Check the data-health strip; if it names the token, refresh it.")
            + " Nothing was sent.",
            leg=leg_label,
        )

    market, side = _book_side_for(direction, quote)
    if market is None:
        raise FillRefused(
            f"{leg_label}: the {side} is not published right now, so a {direction} cannot be "
            f"filled honestly. Try again in a few seconds.",
            leg=leg_label,
            market=quote.ltp,
        )

    now = datetime.now(timezone.utc).isoformat()
    common = dict(
        basis=FILL_BASIS,
        ltp_at_fill=quote.ltp,
        bid_at_fill=quote.bid,
        ask_at_fill=quote.ask,
        filled_at=now,
        side_hit=side,
    )

    if order_type == "MARKET":
        return Fill(
            price=round(market, 2),
            order_type="MARKET",
            limit_price=None,
            how=f"market, at the {side} {market:.2f}"
                + (f", traded {quote.ltp:.2f}" if quote.ltp is not None else ""),
            **common,
        )

    if limit_price is None or limit_price <= 0:
        raise FillRefused(
            f"{leg_label}: a limit order needs a price. Type one, press Reset for the live quote, "
            f"or switch it to market.",
            leg=leg_label,
            market=market,
        )

    marketable = limit_price >= market if direction == "buy" else limit_price <= market
    if not marketable:
        raise FillRefused(
            f"{leg_label}: a {direction} limit of {limit_price:.2f} would not fill now; the {side} "
            f"is {market:.2f}. Move the price, press Reset, or switch this leg to market. "
            f"Nothing was sent.",
            leg=leg_label,
            market=market,
        )

    # His price OR BETTER, as the exchange does it: a buy limit above the ask
    # pays the ask, a sell limit below the bid receives the bid.
    price = market
    better = abs(price - limit_price) >= 0.005
    return Fill(
        price=round(float(price), 2),
        order_type="LIMIT",
        limit_price=round(float(limit_price), 2),
        how=(
            f"limit {limit_price:.2f}, filled at the {side} {price:.2f}"
            + (" which is better" if better else "")
        ),
        **common,
    )
