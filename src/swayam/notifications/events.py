"""Unified Notification Event Dispatcher for Swayam Capital (BUILD-11.8).

Translates domain events (trade_opened, trade_closed, rule_violation, reminders)
into formatted messages and fans out to Telegram and FCM Push channels.

CRITICAL INVARIANT:
Best-effort dispatching. If one or both channels fail, warnings are logged and
the caller continues uninterrupted. Execution endpoints MUST NEVER FAIL due to
notification delivery errors.
"""

import logging
from typing import Any

from swayam.notifications.telegram import send_telegram_message
from swayam.notifications.push import send_push_notification

logger = logging.getLogger(__name__)


def format_event_message(event_type: str, payload: dict[str, Any]) -> tuple[str, str]:
    """Formats domain event into (title, plain-English message) for notification channels.

    Emoji are used sparingly and deliberately per Abhishek's preference.
    """
    if event_type == "trade_opened":
        strategy = payload.get("strategy") or "Options Strategy"
        strikes = payload.get("strikes") or ""
        net_debit = float(payload.get("net_debit_inr") or 0.0)
        mode = str(payload.get("mode") or "PAPER").upper()
        session = str(payload.get("session_id") or payload.get("position_id", "")[:8])
        strikes_str = f" · {strikes}" if strikes else ""
        title = f"📈 {mode} Trade Opened: {strategy}"
        text = f"📈 {mode} · {strategy} opened{strikes_str} · Net Debit ₹{net_debit:,.0f} · Session #{session}"
        return title, text

    if event_type == "trade_closed":
        strategy = payload.get("strategy") or "Options Strategy"
        pnl = float(payload.get("pnl_inr") or 0.0)
        pnl_str = f"+₹{pnl:,.0f}" if pnl >= 0 else f"-₹{abs(pnl):,.0f}"
        reason = payload.get("close_reason") or "manual"
        pos_id = str(payload.get("position_id", ""))[:8]
        mode = str(payload.get("mode") or "PAPER").upper()
        title = f"✅ {mode} Trade Closed: {pnl_str}"
        text = f"✅ {mode} · {strategy} closed · P&L {pnl_str} · Reason: {reason} · #{pos_id}"
        return title, text

    if event_type == "rule_violation":
        rule_name = payload.get("rule_name") or payload.get("rule_id") or "Method Rule"
        reason = payload.get("reason") or "Risk threshold exceeded"
        title = f"⚠ Rule Violation: {rule_name}"
        text = f"⚠ RULE VIOLATION · {rule_name} · Blocked · {reason}"
        return title, text

    if event_type == "readiness_reminder":
        title = "☀ Readiness Ritual Pending"
        text = "☀ 08:45 IST · Readiness ritual pending. Complete before first trade today."
        return title, text

    if event_type == "overnight_naked_warning":
        pos_id = str(payload.get("position_id", ""))[:8]
        pos_str = f"Position #{pos_id}" if pos_id else "Open positions"
        title = "⏰ 15:20 IST Risk Warning"
        text = f"⏰ 15:20 IST WARNING · {pos_str} has naked shorts. Hedge or exit before 15:30 IST."
        return title, text

    if event_type == "eod_summary":
        opened = payload.get("opened_count", 0)
        closed = payload.get("closed_count", 0)
        pnl = float(payload.get("unrealized_pnl_inr", 0.0))
        pnl_str = f"+₹{pnl:,.0f}" if pnl >= 0 else f"-₹{abs(pnl):,.0f}"
        discipline = "✓" if payload.get("discipline_passed", True) else "✕"
        title = f"📊 15:30 IST EOD Summary: {pnl_str}"
        text = f"📊 15:30 IST · Today: {opened} trade opened, {closed} closed. Unrealized P&L: {pnl_str}. Discipline: {discipline}"
        return title, text

    # Fallback generic format
    title = f"Swayam Capital: {event_type}"
    summary = ", ".join(f"{k}={v}" for k, v in payload.items())
    text = f"🔔 {event_type}: {summary}"
    return title, text


def dispatch(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatches an event to Telegram and FCM Push notification channels.

    Best-effort execution:
    - Never raises exceptions.
    - Telegram failures do NOT block push attempts.
    - Push failures do NOT block Telegram attempts.
    - Returns delivery status report dictionary.
    """
    title, message = format_event_message(event_type, payload)

    tg_delivered = False
    try:
        tg_delivered = send_telegram_message(text=message)
    except Exception as exc:
        logger.warning("Telegram dispatch handler error: %s", exc)

    push_delivered = False
    try:
        push_delivered = send_push_notification(title=title, body=message, data=payload)
    except Exception as exc:
        logger.warning("Push dispatch handler error: %s", exc)

    return {
        "event_type": event_type,
        "title": title,
        "message": message,
        "telegram": tg_delivered,
        "push": push_delivered,
    }
