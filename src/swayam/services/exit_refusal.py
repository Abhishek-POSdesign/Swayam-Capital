"""The words a refused exit price uses. His decision of 2026-09-10.

WHY THIS EXISTS
---------------
On 2026-09-10 his strangle was stopped by his own limit price, and beside the
greyed buttons sat red "Unlimited" rule tiles. It read like the hedge rule had
blocked the trade. It had not. His entry is NEVER blocked by a rule; only
carrying overnight is gated.

So a price that has not been reached says one thing, a rule says another, and
they never share a colour. Amber for a price, never red, never beside a rule
tile.

WHAT THIS BUILD DOES AND DOES NOT DO. In Build A a limit the book has not
reached refuses that send. Build B makes it REST as an open order until the
book comes to it, which is what he actually asked for: "It should not execute
if the price is not available, but must be sitting in the system till the time
the bid and ask reach the price I want." The wording says so plainly, so the
refusal reads as a limitation of the terminal today rather than as a rule he
has broken.

The fill rule itself is untouched. `services/fills.py` decides whether a leg
fills. This only decides how the refusal is worded when it does not, and it
decides that from the OUTCOME rather than by repeating the rule.
"""

from __future__ import annotations

from typing import Optional


def side_needed(direction: str) -> str:
    """Which side of the book this order has to take. A buy pays the ask."""
    return "ask" if str(direction).lower() in ("buy", "long") else "bid"


def price_not_reached(*, side_hit: str, market: Optional[float]) -> str:
    """The sentence a limit away from the book must use, everywhere."""
    where = (
        f"the {side_hit} is {market:,.2f}"
        if market is not None
        else f"the {side_hit} is not published"
    )
    return (
        f"Your price, not a rule: {where}. "
        "Resting orders arrive in the next build; for now move the price or switch to market."
    )


def is_his_price(
    *,
    order_type: str,
    book_is_tradeable: bool,
    side_price: Optional[float],
    limit_price: Optional[float],
) -> bool:
    """Whether a refusal was about HIS PRICE rather than about the market.

    Read as an outcome, not as a rule. When there IS a tradeable book, the
    side he needs IS published, and he sent a LIMIT with a real price, the
    only thing left for `resolve_fill` to have objected to is that the market
    has not come to his price. Anything else, after the bell or with no book
    at all, is a fact about the market and keeps its own words.
    """
    return (
        str(order_type).upper() == "LIMIT"
        and book_is_tradeable
        and side_price is not None
        and limit_price is not None
        and limit_price > 0
    )


def reword_if_his_price(
    reason: str,
    *,
    direction: str,
    order_type: str,
    book_is_tradeable: bool,
    side_price: Optional[float],
    limit_price: Optional[float],
) -> str:
    """The refusal, reworded only when it is about his price."""
    if not is_his_price(
        order_type=order_type,
        book_is_tradeable=book_is_tradeable,
        side_price=side_price,
        limit_price=limit_price,
    ):
        return reason
    return price_not_reached(side_hit=side_needed(direction), market=side_price)
