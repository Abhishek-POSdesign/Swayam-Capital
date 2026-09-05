"""Weekly Email Digest Service for Swayam Capital (BUILD-11.11).

Automates the Sunday 11:00 AM IST email digest:
- Pulls last 7 days of closed & open trades from swayam_positions
- Computes weekly Net P&L and Discipline Rate
- Selects top lesson from swayam_lessons
- Formats next 7 days of highlighted macro events
- Sends multipart HTML email via Gmail SMTP using app password
"""

import email.mime.multipart
import email.mime.text
import logging
import smtplib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from swayam.config import settings
from swayam.db import db

logger = logging.getLogger(__name__)


def compose_digest_html(
    trades: list[dict[str, Any]],
    lessons: list[dict[str, Any]],
    macro_events: list[dict[str, Any]],
    date_range_str: Optional[str] = None,
) -> str:
    """Composes clean, executive HTML email digest for Abhishek."""
    if not date_range_str:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=7)
        date_range_str = f"{start.strftime('%d %b')} – {now.strftime('%d %b %Y')}"

    # Calculate summary metrics
    total_pnl = sum(float(t.get("pnl") or t.get("realized_pnl") or 0.0) for t in trades)
    discipline_count = sum(1 for t in trades if t.get("discipline_followed", True) is not False)
    trade_count = len(trades)
    discipline_rate = (discipline_count / trade_count * 100.0) if trade_count > 0 else 100.0

    pnl_color = "#86ab92" if total_pnl >= 0 else "#e06666"
    pnl_formatted = f"+₹{total_pnl:,.2f}" if total_pnl > 0 else f"-₹{abs(total_pnl):,.2f}" if total_pnl < 0 else "₹0.00"

    # Trade rows HTML
    if trades:
        trade_rows = []
        for t in trades:
            tpnl = float(t.get("pnl") or t.get("realized_pnl") or 0.0)
            tcolor = "#86ab92" if tpnl >= 0 else "#e06666"
            tformatted = f"+₹{tpnl:,.2f}" if tpnl > 0 else f"-₹{abs(tpnl):,.2f}" if tpnl < 0 else "₹0.00"
            disc = "✓" if t.get("discipline_followed", True) is not False else "✗"
            disc_color = "#86ab92" if disc == "✓" else "#e06666"
            dt_str = str(t.get("exit_time") or t.get("entry_time") or t.get("date") or "")[:10]
            strat = t.get("strategy_name") or t.get("strategy") or "Options Trade"

            row_html = f"""
            <tr style="border-bottom: 1px solid #232733;">
              <td style="padding: 8px 10px; font-size: 13px; color: #c4c7d4;">{dt_str}</td>
              <td style="padding: 8px 10px; font-size: 13px; font-weight: 500; color: #f0f2f8;">{strat}</td>
              <td style="padding: 8px 10px; font-size: 13px; font-weight: 700; color: {tcolor}; text-align: right;">{tformatted}</td>
              <td style="padding: 8px 10px; font-size: 13px; font-weight: 700; color: {disc_color}; text-align: center;">{disc}</td>
            </tr>
            """
            trade_rows.append(row_html)
        trade_table_html = "".join(trade_rows)
    else:
        trade_table_html = """
        <tr>
          <td colspan="4" style="padding: 16px; font-size: 13px; color: #8a8f9f; text-align: center;">
            No trades executed during this 7-day period. Capital preserved.
          </td>
        </tr>
        """

    # Top lesson HTML
    if lessons:
        top_lesson = lessons[0]
        lesson_text = top_lesson.get("lesson_text") or top_lesson.get("title") or "Maintain mechanical stop discipline."
        lesson_tag = top_lesson.get("category") or "Psychology & Rules"
        lesson_html = f"""
        <div style="background: #191c25; border-left: 3px solid #86ab92; border-radius: 0 6px 6px 0; padding: 12px 16px; margin-top: 8px;">
          <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #86ab92; margin-bottom: 4px;">{lesson_tag}</div>
          <div style="font-size: 14px; color: #e4e7f1; line-height: 1.45;">"{lesson_text}"</div>
        </div>
        """
    else:
        lesson_html = """
        <div style="background: #191c25; border-left: 3px solid #86ab92; border-radius: 0 6px 6px 0; padding: 12px 16px; margin-top: 8px; font-size: 13px; color: #c4c7d4;">
          "The market rewards patience and exact edge execution over trade volume."
        </div>
        """

    # Upcoming macro events HTML
    if macro_events:
        macro_items = []
        for ev in macro_events[:5]:
            ename = ev.get("event_name") or ev.get("event") or ""
            edate = str(ev.get("event_date") or "")
            ecountry = ev.get("country", "IN")
            brief = ev.get("impact_brief") or "Derivatives positioning catalyst."
            badge_bg = "rgba(234, 179, 8, 0.18)" if ecountry == "IN" else "rgba(59, 130, 246, 0.18)"
            badge_color = "#eab308" if ecountry == "IN" else "#60a5fa"

            item_html = f"""
            <div style="padding: 10px 0; border-bottom: 1px solid #232733;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                <span style="font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 4px; background: {badge_bg}; color: {badge_color};">{ecountry}</span>
                <span style="font-size: 13px; font-weight: 600; color: #f0f2f8; margin-left: 8px; flex: 1;">{ename}</span>
                <span style="font-size: 12px; font-weight: 600; color: #8a8f9f; white-space: nowrap;">{edate}</span>
              </div>
              <div style="font-size: 12px; color: #86ab92; margin-top: 2px; padding-left: 4px;">
                <strong>NIFTY Impact:</strong> {brief}
              </div>
            </div>
            """
            macro_items.append(item_html)
        macro_section_html = "".join(macro_items)
    else:
        macro_section_html = """
        <div style="padding: 12px 0; font-size: 13px; color: #8a8f9f;">
          No high-impact central bank or macro releases flagged for the next 7 days.
        </div>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Swayam Weekly Digest</title>
</head>
<body style="background-color: #101116; color: #f0f2f8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 24px;">
  <div style="max-width: 620px; margin: 0 auto; background: #151820; border: 1px solid #242835; border-radius: 12px; overflow: hidden; box-shadow: 0 8px 24px rgba(0,0,0,0.35);">
    
    <!-- Header -->
    <div style="background: #1a1e28; border-bottom: 1px solid #282d3d; padding: 20px 24px;">
      <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: #86ab92;">Swayam Capital</div>
      <div style="font-size: 20px; font-weight: 600; color: #f0f2f8; margin-top: 4px;">Weekly Performance & Planning Digest</div>
      <div style="font-size: 13px; color: #8a8f9f; margin-top: 2px;">{date_range_str}</div>
    </div>

    <div style="padding: 24px;">
      <!-- Key Stat Cards -->
      <table style="width: 100%; border-collapse: separate; border-spacing: 12px 0; margin-bottom: 24px;">
        <tr>
          <td style="width: 50%; background: #1b1f2a; border: 1px solid #272c3b; border-radius: 8px; padding: 16px; text-align: center;">
            <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: #8a8f9f; letter-spacing: 0.05em;">Weekly Net P&amp;L</div>
            <div style="font-size: 24px; font-weight: 700; color: {pnl_color}; margin-top: 6px;">{pnl_formatted}</div>
            <div style="font-size: 12px; color: #8a8f9f; margin-top: 4px;">{trade_count} trades</div>
          </td>
          <td style="width: 50%; background: #1b1f2a; border: 1px solid #272c3b; border-radius: 8px; padding: 16px; text-align: center;">
            <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: #8a8f9f; letter-spacing: 0.05em;">Discipline Rate</div>
            <div style="font-size: 24px; font-weight: 700; color: #86ab92; margin-top: 6px;">{discipline_rate:.0f}%</div>
            <div style="font-size: 12px; color: #8a8f9f; margin-top: 4px;">{discipline_count}/{trade_count} rules respected</div>
          </td>
        </tr>
      </table>

      <!-- Section: Closed Trades -->
      <div style="margin-bottom: 26px;">
        <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #8a8f9f; margin-bottom: 8px;">
          This Week's Closed Trades
        </div>
        <table style="width: 100%; border-collapse: collapse; background: #191c25; border: 1px solid #232733; border-radius: 6px; overflow: hidden;">
          <thead>
            <tr style="background: #1f2330; border-bottom: 1px solid #2b3042; text-align: left;">
              <th style="padding: 8px 10px; font-size: 11px; font-weight: 700; color: #8a8f9f; text-transform: uppercase;">Date</th>
              <th style="padding: 8px 10px; font-size: 11px; font-weight: 700; color: #8a8f9f; text-transform: uppercase;">Strategy</th>
              <th style="padding: 8px 10px; font-size: 11px; font-weight: 700; color: #8a8f9f; text-transform: uppercase; text-align: right;">P&amp;L</th>
              <th style="padding: 8px 10px; font-size: 11px; font-weight: 700; color: #8a8f9f; text-transform: uppercase; text-align: center;">Disc.</th>
            </tr>
          </thead>
          <tbody>
            {trade_table_html}
          </tbody>
        </table>
      </div>

      <!-- Section: Key Lesson -->
      <div style="margin-bottom: 26px;">
        <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #8a8f9f; margin-bottom: 6px;">
          Top Ledger Lesson
        </div>
        {lesson_html}
      </div>

      <!-- Section: Macro Events -->
      <div style="margin-bottom: 26px;">
        <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #8a8f9f; margin-bottom: 6px;">
          Upcoming Macro Events · Next 7 Days
        </div>
        <div style="background: #191c25; border: 1px solid #232733; border-radius: 6px; padding: 6px 14px;">
          {macro_section_html}
        </div>
      </div>

      <!-- CTA -->
      <div style="text-align: center; margin-top: 32px; padding-top: 18px; border-top: 1px solid #242835;">
        <a href="https://swayam.abhisheksikka.com" style="display: inline-block; background: #86ab92; color: #101116; font-weight: 700; font-size: 13px; text-decoration: none; padding: 10px 24px; border-radius: 6px;">
          Open Swayam Capital
        </a>
      </div>
    </div>

    <!-- Footer -->
    <div style="background: #111319; padding: 14px 24px; border-top: 1px solid #1f2330; text-align: center; font-size: 11px; color: #606575;">
      Automated weekly dispatch from Swayam Capital · Confidential to Abhishek Sikka
    </div>
  </div>
</body>
</html>
"""
    return html


def fetch_weekly_digest_data() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Retrieves 7-day trade positions, lessons, and next 7-day macro events from Supabase."""
    trades: list[dict[str, Any]] = []
    lessons: list[dict[str, Any]] = []
    macro_events: list[dict[str, Any]] = []

    try:
        if db.url and db.key:
            seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            # 1. Trades
            try:
                tres = db.client.table("swayam_positions").select("*").gte("created_at", seven_days_ago).execute()
                trades = tres.data or []
            except Exception as e:
                logger.warning("Could not fetch weekly trades: %s", e)

            # 2. Lessons
            try:
                lres = db.client.table("swayam_lessons").select("*").gte("created_at", seven_days_ago).order("created_at", desc=True).limit(5).execute()
                lessons = lres.data or []
            except Exception as e:
                logger.warning("Could not fetch weekly lessons: %s", e)

            # 3. Highlighted macro events (next 7 days)
            try:
                seven_days_ahead = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
                mres = db.client.table("swayam_macro_events").select("*").gte("event_date", now_date).lte("event_date", seven_days_ahead).eq("highlighted", True).order("event_date", desc=False).execute()
                macro_events = mres.data or []
            except Exception as e:
                logger.warning("Could not fetch macro events: %s", e)
    except Exception as exc:
        logger.error("Database connection failed during digest data fetch: %s", exc)

    return trades, lessons, macro_events


def send_weekly_digest(
    sender_email: Optional[str] = None,
    app_password: Optional[str] = None,
    recipient_email: Optional[str] = None,
    trades: Optional[list[dict[str, Any]]] = None,
    lessons: Optional[list[dict[str, Any]]] = None,
    macro_events: Optional[list[dict[str, Any]]] = None,
) -> bool:
    """Composes and dispatches the weekly digest via Gmail SMTP.

    REINFORCEMENT 3:
    - sender_email is configured via Secret Manager (gmail-sender-address) or env GMAIL_SENDER_ADDRESS.
    - app_password is configured via Secret Manager (gmail-app-password) or env GMAIL_APP_PASSWORD.
    - No hardcoded email addresses.
    - Best-effort: never raises exception.
    """
    sender = sender_email or settings.gmail_sender_address
    password = app_password or settings.gmail_app_password
    recipient = recipient_email or settings.gmail_recipient_address or sender

    if not sender or not password:
        logger.info("Weekly email digest skipped: GMAIL_SENDER_ADDRESS or GMAIL_APP_PASSWORD not configured.")
        return False

    try:
        if trades is None or lessons is None or macro_events is None:
            db_trades, db_lessons, db_macros = fetch_weekly_digest_data()
            trades = trades if trades is not None else db_trades
            lessons = lessons if lessons is not None else db_lessons
            macro_events = macro_events if macro_events is not None else db_macros

        html_body = compose_digest_html(trades, lessons, macro_events)

        msg = email.mime.multipart.MIMEMultipart("alternative")
        msg["Subject"] = f"Swayam Weekly · {datetime.now(timezone.utc).strftime('%d %b %Y')}"
        msg["From"] = sender
        msg["To"] = recipient

        # Fallback text
        text_content = f"Swayam Weekly Digest for {datetime.now(timezone.utc).strftime('%d %b %Y')}. Open your web app at https://swayam.abhisheksikka.com"
        msg.attach(email.mime.text.MIMEText(text_content, "plain"))
        msg.attach(email.mime.text.MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10.0) as server:
            server.login(sender, password)
            server.sendmail(sender, [recipient], msg.as_string())

        logger.info("Weekly email digest sent successfully to %s", recipient)
        return True
    except Exception as exc:
        logger.warning("Failed to send weekly email digest via Gmail SMTP: %s", exc)
        return False
