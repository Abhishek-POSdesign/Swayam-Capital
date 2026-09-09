"""
How a paper leg gets its fill price.

WHY THIS EXISTS
---------------
Until the execution ticket, a paper trade was filled at whatever price the
browser sent. A limit of ₹1 on a ₹100 option would have "filled". That is a
fabricated fill, and it falls under his first rule: every number is real from
FYERS or it says unavailable.

A fill now needs a market to fill against:

  * MARKET fills at the SERVER'S live quote at the moment of sending, never at
    a price the browser read a few seconds earlier.
  * LIMIT fills at his price only if the market is at or through it. If it is
    not, nothing fills and the answer says where the market is. There are no
    resting orders in this app, so none are pretended.
  * No quote, no fill. After the close the chain carries a closing price, and
    a fill at a closing price is a fill nobody could have got.

PR 1 (docs/PLAN.md 2.12.2) fills at the traded price and says so on the leg.
PR 2 flips `FILL_BASIS` to bid_ask: a buy at the ask, a sell at the bid. The
comparison lives in `_market_price_for`, and nowhere else, so the change is one
function.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

# What every leg is filled at in this release. PR 2 changes this to "bid_ask".
FILL_BASIS: Literal["traded_price", "bid_ask"] = "traded_price"


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
        """A price a fill may be measured against. A closing price is not one."""
        return self.ltp is not None and self.ltp > 0 and self.state in ("live", "delayed")


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


def quote_leg(*, strike: float, expiry: str, option_type: str, underlying: str = "NIFTY") -> LegQuote:
    """The live quote for one contract, from the shared chain feed.

    Goes through the same route the desk uses for its leg prices, so a fill is
    measured against exactly the number he was looking at, read again at the
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
        state=str(q.get("freshness") or "unavailable"),
        market_open=bool(q.get("market_open")),
        as_of=q.get("as_of"),
        note=q.get("note"),
    )


def _market_price_for(direction: str, quote: LegQuote) -> Optional[float]:
    """The price this side would actually get right now.

    PR 1: the traded price, both sides. PR 2 (realistic fills): a buy pays the
    ask and a sell receives the bid, and where that side is missing the leg
    is unavailable rather than filled at a guess.
    """
    if FILL_BASIS == "bid_ask":
        return quote.ask if direction == "buy" else quote.bid
    return quote.ltp


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
        FillRefused: no tradeable quote, or a limit the market is not at.
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
                f"{leg_label}: the market is closed, so nothing can fill. The last price "
                f"was a closing price and a fill at it is one nobody could have got. "
                f"Keep the structure on the desk and send it in your window.",
                leg=leg_label,
                market=quote.ltp,
            )
        raise FillRefused(
            f"{leg_label}: no live price, so it cannot be filled. "
            + (quote.note or "Check the data-health strip; if it names the token, refresh it.")
            + " Nothing was sent.",
            leg=leg_label,
        )

    market = _market_price_for(direction, quote)
    if market is None:
        side = "ask" if direction == "buy" else "bid"
        raise FillRefused(
            f"{leg_label}: the {side} is not published right now, so a {direction} cannot be "
            f"filled honestly. Try again in a few seconds, or switch this leg to a limit.",
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
    )

    if order_type == "MARKET":
        return Fill(
            price=round(market, 2),
            order_type="MARKET",
            limit_price=None,
            how=f"market, at the {'ask' if FILL_BASIS == 'bid_ask' and direction == 'buy' else 'bid' if FILL_BASIS == 'bid_ask' else 'traded price'} {market:.2f}",
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
            f"{leg_label}: a {direction} limit of {limit_price:.2f} would not fill now; the market "
            f"is {market:.2f}. Move the price, press Reset, or switch this leg to market. "
            f"Nothing was sent.",
            leg=leg_label,
            market=market,
        )

    # A limit at or through the market fills at the LIMIT, which is what a
    # broker does, and never better than he asked for.
    return Fill(
        price=round(float(limit_price), 2),
        order_type="LIMIT",
        limit_price=round(float(limit_price), 2),
        how=f"limit {limit_price:.2f}, market was {market:.2f}",
        **common,
    )
