"""Targets on a trade and on its legs, and whether one has been reached.

WHY THIS EXISTS
---------------
His words, 2026-09-10: "My preference is to add a target for each leg. Target
always means both loss and profit... In case I cannot add profit and loss for
each leg, I have to add it for the whole trade."

So a target is always a PAIR. Take profit at, and cut loss at. Per leg by
preference, on the whole trade as the fallback, and both may be set at once.

WHAT A TARGET IS MEASURED AGAINST
---------------------------------
A LEG's targets are PRICES of that option, and they are judged against the
mark, which is the side he would actually get:

    a BOUGHT leg is marked at the BID, because selling is what closes it
        profit when the bid is AT OR ABOVE take-profit
        loss   when the bid is AT OR BELOW cut-loss

    a SOLD leg is marked at the ASK, because buying back is what closes it
        profit when the ask is AT OR BELOW take-profit
        loss   when the ask is AT OR ABOVE cut-loss

That is the same side services/fills.py would hit on the exit, so the signal
and the fill agree. A leg already squared off is not evaluated: it has no live
mark, and re-marking it would rewrite history.

The TRADE's targets are RUPEES, net of charges both ways. His words: "the
actual profit that will come into my account after exiting."

BLANK MEANS NO SIGNAL. One exception.
-------------------------------------
A blank box is silence, never a number the terminal picked, because a number
the terminal picked is a plan he did not make. The single exception is a blank
LOSS target on the whole trade, which falls back to rule 1: one percent of the
live FYERS balance, read fresh. That is his own standing rule, not an invention
of this module, and it is read live rather than stored because a stored
percentage of a balance goes stale the moment the balance moves.

If rule 1's cap cannot be read there is no fallback and no loss signal, and
loss_source says so. It is never guessed.

WHAT THIS MODULE DOES NOT DO
----------------------------
It never exits anything. A reached target lights up and waits for him. There is
no order-placement code anywhere in this repository, and nothing here changes
that.

This module is pure: dictionaries in, dictionaries out. No database, no clock,
no network.
"""

from __future__ import annotations

from typing import Any, Optional

# The state of one position, for Home's band. His correction of 2026-09-10:
#   running - the trade is live and no target is reached. The band blinks.
#   alert   - a target he set was reached. The band goes solid and stops.
#   quiet   - nothing open, or squared off. No colour, no blink.
STATE_RUNNING = "running"
STATE_ALERT = "alert"
STATE_QUIET = "quiet"


def _num(value: Any) -> Optional[float]:
    """A finite number, or None. An empty box is None, never zero."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def _is_buy(leg: dict[str, Any]) -> bool:
    """True for a bought leg. Matches how the rest of the file reads a leg."""
    direction = str(leg.get("direction") or leg.get("side") or "").strip().upper()
    return direction in ("BUY", "B", "LONG")


def _leg_label(leg: dict[str, Any]) -> str:
    """23,800 CE, the way he names a leg out loud."""
    strike = _num(leg.get("strike"))
    kind = str(leg.get("option_type") or leg.get("type") or "").strip().upper()
    if strike is None:
        return kind or "leg"
    return f"{strike:,.0f} {kind}".strip()


def leg_targets_from(leg: dict[str, Any]) -> dict[str, Optional[float]]:
    """The two prices stored on a leg, if he set them. Both may be None."""
    return {
        "target_price": _num(leg.get("target_price")),
        "stop_price": _num(leg.get("stop_price")),
    }


def wrong_side_of_entry(
    leg: dict[str, Any],
    *,
    target_price: Optional[float],
    stop_price: Optional[float],
) -> Optional[str]:
    """A target that can never fire, said in plain words, or None if both are fine.

    HIS REPORT, 2026-09-11: the Targets box accepted a number on the wrong side
    of the entry. It saved, it sat on the trade looking like a plan, and it
    could never be reached, because the only way a bought leg loses money is by
    falling and the only way it makes money is by rising.

        a BOUGHT leg   take profit ABOVE the entry, cut loss BELOW it
        a SOLD leg     take profit BELOW the entry, cut loss ABOVE it

    EQUAL TO THE ENTRY IS ALLOWED. A target at the entry price is a break-even
    exit, which is a real thing to want; it is not on the wrong side of
    anything. Only a strictly wrong side is refused.

    A leg with no stored entry price is not judged. There is nothing to be on
    the wrong side OF, and inventing a reference price to check against would
    be exactly the kind of made-up number this terminal must never produce.

    The message says what he can DO, per his standing rule that a refusal on
    his screen is useless unless it names the way out.
    """
    entry = _num(leg.get("entry_premium"))
    if entry is None:
        return None

    buy = _is_buy(leg)
    label = _leg_label(leg)
    side = "bought" if buy else "sold"
    entry_text = f"{entry:,.2f}"

    if target_price is not None:
        if buy and target_price < entry:
            return (
                f"On {label}, which you BOUGHT at {entry_text}, a take-profit of "
                f"{target_price:,.2f} is below your entry, so it could only be reached "
                f"at a loss. Put the take-profit ABOVE {entry_text}, or move that number "
                f"to the cut-loss box."
            )
        if not buy and target_price > entry:
            return (
                f"On {label}, which you SOLD at {entry_text}, a take-profit of "
                f"{target_price:,.2f} is above your entry, so it could only be reached "
                f"at a loss. A sold leg profits as it falls: put the take-profit BELOW "
                f"{entry_text}, or move that number to the cut-loss box."
            )

    if stop_price is not None:
        if buy and stop_price > entry:
            return (
                f"On {label}, which you BOUGHT at {entry_text}, a cut-loss of "
                f"{stop_price:,.2f} is above your entry, so it would fire while you are "
                f"in PROFIT. Put the cut-loss BELOW {entry_text}, or move that number to "
                f"the take-profit box."
            )
        if not buy and stop_price < entry:
            return (
                f"On {label}, which you SOLD at {entry_text}, a cut-loss of "
                f"{stop_price:,.2f} is below your entry, so it would fire while you are "
                f"in PROFIT. A sold leg loses as it rises: put the cut-loss ABOVE "
                f"{entry_text}, or move that number to the take-profit box."
            )

    return None


def evaluate_leg(leg: dict[str, Any]) -> Optional[dict[str, Any]]:
    """One alert for one open leg, or None if nothing of his was reached.

    Profit is checked before loss. They cannot both be true unless he set a
    cut-loss above his take-profit on a bought leg, which is a contradiction,
    and in that case the profit is what he is told about.
    """
    if str(leg.get("status") or "open").lower() != "open":
        return None

    mark = _num(leg.get("mark"))
    if mark is None:
        return None  # the leg could not be marked; say nothing rather than guess

    t = leg_targets_from(leg)
    take, cut = t["target_price"], t["stop_price"]
    buy = _is_buy(leg)
    sequence = leg.get("sequence")

    if take is not None:
        reached = mark >= take if buy else mark <= take
        if reached:
            return {
                "scope": "leg",
                "sequence": sequence,
                "leg_label": _leg_label(leg),
                "kind": "profit",
                "level": take,
                "mark": mark,
                "mark_side": leg.get("mark_side"),
            }

    if cut is not None:
        reached = mark <= cut if buy else mark >= cut
        if reached:
            return {
                "scope": "leg",
                "sequence": sequence,
                "leg_label": _leg_label(leg),
                "kind": "loss",
                "level": cut,
                "mark": mark,
                "mark_side": leg.get("mark_side"),
            }

    return None


def evaluate_trade(
    *,
    net_if_exit_now_inr: Optional[float],
    target_profit_inr: Optional[float],
    target_loss_inr: Optional[float],
    rule1_cap_inr: Optional[float],
) -> tuple[Optional[dict[str, Any]], Optional[float], str]:
    """The whole trade's alert, the loss level in force, and where it came from.

    Returns (alert or None, effective_loss_inr or None, loss_source), where
    loss_source is one of:

        his    - he typed a loss figure on this trade
        rule1  - he left it blank, so rule 1's cap stands in, read live
        none   - blank, and rule 1 could not be read, so there is no signal
    """
    profit = _num(target_profit_inr)
    his_loss = _num(target_loss_inr)
    cap = _num(rule1_cap_inr)

    if his_loss is not None:
        effective_loss, loss_source = abs(his_loss), "his"
    elif cap is not None and cap > 0:
        effective_loss, loss_source = abs(cap), "rule1"
    else:
        effective_loss, loss_source = None, "none"

    net = _num(net_if_exit_now_inr)
    if net is None:
        return None, effective_loss, loss_source

    if profit is not None and net >= profit:
        return (
            {
                "scope": "trade",
                "sequence": None,
                "leg_label": None,
                "kind": "profit",
                "level": profit,
                "mark": net,
                "mark_side": None,
                "from_rule1": False,
            },
            effective_loss,
            loss_source,
        )

    if effective_loss is not None and net <= -effective_loss:
        return (
            {
                "scope": "trade",
                "sequence": None,
                "leg_label": None,
                "kind": "loss",
                "level": effective_loss,
                "mark": net,
                "mark_side": None,
                "from_rule1": loss_source == "rule1",
            },
            effective_loss,
            loss_source,
        )

    return None, effective_loss, loss_source


def evaluate_position(
    *,
    legs: list[dict[str, Any]],
    net_if_exit_now_inr: Optional[float],
    target_profit_inr: Optional[float],
    target_loss_inr: Optional[float],
    targets_set_at: Optional[str],
    rule1_cap_inr: Optional[float],
    legs_open: int,
    market_state: str,
) -> dict[str, Any]:
    """Everything Home's band needs for one trade: its state and its alerts.

    THE STATE IS COMPUTED HERE, ON THE SERVER, and the browser only paints it.
    Home must never decide from raw numbers what colour it is, or the two
    screens can disagree about the same trade.

    ON THE MARKET BEING SHUT. The marks a shut market gives are the closing
    book, so an alert computed from them is the alert as it stood at the close,
    which is what it last was. evaluated_at_market_state carries that word
    through to the screen, so the band can say "at the close" and stop blinking
    over a figure that is no longer moving.
    """
    alerts: list[dict[str, Any]] = []
    for leg in legs:
        got = evaluate_leg(leg)
        if got is not None:
            alerts.append(got)

    trade_alert, effective_loss, loss_source = evaluate_trade(
        net_if_exit_now_inr=net_if_exit_now_inr,
        target_profit_inr=target_profit_inr,
        target_loss_inr=target_loss_inr,
        rule1_cap_inr=rule1_cap_inr,
    )
    if trade_alert is not None:
        alerts.append(trade_alert)

    leg_targets = []
    legs_with_targets = 0
    for leg in legs:
        t = leg_targets_from(leg)
        if t["target_price"] is not None or t["stop_price"] is not None:
            legs_with_targets += 1
        leg_targets.append(
            {
                "sequence": leg.get("sequence"),
                "leg_label": _leg_label(leg),
                "status": str(leg.get("status") or "open").lower(),
                "target_price": t["target_price"],
                "stop_price": t["stop_price"],
            }
        )

    if legs_open <= 0:
        state = STATE_QUIET
    elif alerts:
        state = STATE_ALERT
    else:
        state = STATE_RUNNING

    return {
        "state": state,
        "alerts": alerts,
        "targets": {
            "legs": leg_targets,
            "legs_with_targets": legs_with_targets,
            "legs_total": len(leg_targets),
            "target_profit_inr": _num(target_profit_inr),
            "target_loss_inr": _num(target_loss_inr),
            "effective_loss_inr": effective_loss,
            "loss_source": loss_source,
            "targets_set_at": targets_set_at,
        },
        "evaluated_at_market_state": market_state,
    }
