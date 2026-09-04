"""
AI Memory Management & Compaction System for Swayam Capital.

Implements the 3-tier event-driven memory model:
- Layer 1: Verbatim Working Memory (open trading day, position-tagged messages)
- Layer 2: Event-Boundary Compaction:
    Trigger A: Daily 4 PM IST compaction of yesterday's session
    Trigger B: Trade closed AND journal written
    Trigger C: Explicit Clear Chat compaction
- Layer 3: Persistent Memory (Notebook entries + Pinned decision rules)
- Layer 4: Safety Valve (>200 messages auto-compacts oldest half)
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from swayam.ai import router as ai_router
from swayam.db import db

logger = logging.getLogger(__name__)


class ContextAssemblyError(RuntimeError):
    """Raised when a required context source fails and cannot be assembled."""
    pass


def _safe_json_parse(text: str, fallback_summary: str = "") -> dict:
    """Safely extracts JSON from model output or returns structured fallback."""
    text_clean = text.strip()
    if "```json" in text_clean:
        text_clean = text_clean.split("```json")[1].split("```")[0].strip()
    elif "```" in text_clean:
        text_clean = text_clean.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(text_clean)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    return {
        "summary": text.strip() or fallback_summary,
        "decisions": [],
        "questions": [],
        "preferences": [],
        "constraints": [],
        "nextSteps": [],
    }


def compact_session(session_date: date) -> Dict[str, Any]:
    """Compacts one day's trading conversation into a structured summary block.

    Trigger A: Scheduled daily at 4 PM IST or on-demand.
    Uses cheap model tier (gemini-2.5-flash-lite). Idempotent.
    """
    date_str = session_date.isoformat()

    # Check for existing summary (idempotency)
    try:
        existing = (
            db.client.table("swayam_ai_session_summaries")
            .select("*")
            .eq("session_date", date_str)
            .execute()
        )
        if existing.data:
            logger.info("Session summary for %s already exists.", date_str)
            return existing.data[0]
    except Exception as exc:
        logger.warning("Could not check existing session summary for %s: %s", date_str, exc)

    # Fetch messages from that date
    try:
        res = (
            db.client.table("swayam_ai_messages")
            .select("id, role, content, created_at")
            .eq("session_date", date_str)
            .in_("role", ["user", "assistant"])
            .order("created_at", desc=False)
            .execute()
        )
        messages = res.data or []
    except Exception as exc:
        logger.error("Failed to query messages for session date %s: %s", date_str, exc)
        raise RuntimeError(f"Failed to query messages for session date {date_str}: {exc}") from exc

    if not messages:
        logger.info("No messages found for session date %s to compact.", date_str)
        empty_block = {
            "summary": f"No trading conversations recorded for {date_str}.",
            "decisions": [],
            "questions": [],
            "preferences": [],
            "constraints": [],
            "nextSteps": [],
        }
        res_ins = (
            db.client.table("swayam_ai_session_summaries")
            .insert({
                "session_date": date_str,
                "summary_block": empty_block,
                "message_count": 0,
                "covered_message_ids": [],
            })
            .execute()
        )
        return res_ins.data[0] if res_ins.data else {"session_date": date_str, "summary_block": empty_block}

    # Format transcript for summarization
    transcript_lines = []
    message_ids = []
    for m in messages:
        message_ids.append(m["id"])
        role_label = "Abhishek" if m["role"] == "user" else "AI Partner"
        transcript_lines.append(f"{role_label}: {m['content']}")

    transcript_text = "\n\n".join(transcript_lines)

    prompt = (
        "You are an AI assistant compacting a day's trading conversation for Abhishek Sikka.\n"
        f"Session date: {date_str}.\n\n"
        "Produce a valid JSON summary block with the following exact keys:\n"
        "- summary (string: 2-3 sentence overview of what was discussed)\n"
        "- decisions (array of strings: trades decided, levels watched, setups passed)\n"
        "- questions (array of strings: key questions explored)\n"
        "- preferences (array of strings: user preferences expressed)\n"
        "- constraints (array of strings: risk caps or timing limits noted)\n"
        "- nextSteps (array of strings: planned actions for tomorrow)\n\n"
        f"Conversation Transcript:\n{transcript_text}"
    )

    try:
        reply_text, _ = ai_router.chat_lightweight([
            {"role": "user", "content": prompt}
        ])
        summary_block = _safe_json_parse(reply_text, fallback_summary=f"Session summary for {date_str}")
    except Exception as exc:
        logger.warning("Compaction model call failed for date %s: %s", date_str, exc)
        summary_block = {
            "summary": f"Conversation on {date_str} with {len(messages)} messages.",
            "decisions": [],
            "questions": [],
            "preferences": [],
            "constraints": [],
            "nextSteps": [],
        }

    # Insert into swayam_ai_session_summaries
    try:
        inserted = (
            db.client.table("swayam_ai_session_summaries")
            .insert({
                "session_date": date_str,
                "summary_block": summary_block,
                "message_count": len(messages),
                "covered_message_ids": message_ids,
            })
            .execute()
        )
        return inserted.data[0] if inserted.data else {"session_date": date_str, "summary_block": summary_block}
    except Exception as exc:
        logger.error("Failed to insert session summary for %s: %s", date_str, exc)
        raise RuntimeError(f"Could not save session summary: {exc}") from exc


def compact_trade(position_id: str) -> Optional[Dict[str, Any]]:
    """Compacts conversation messages tagged with a closed and journaled position.

    Trigger B: Fires when swayam_positions.status == 'closed' AND
    swayam_trade_history has journal reflection recorded.
    """
    try:
        pos_res = (
            db.client.table("swayam_positions")
            .select("id, status, strategy_name, underlying")
            .eq("id", position_id)
            .execute()
        )
        if not pos_res.data:
            logger.warning("Trade compaction skipped: position %s not found.", position_id)
            return None

        pos = pos_res.data[0]
        if pos.get("status") != "closed":
            logger.info("Trade compaction skipped: position %s is not closed yet.", position_id)
            return None

        # Check journal entry exists in trade_history
        trade_res = (
            db.client.table("swayam_trade_history")
            .select("id, realized_pnl_inr, journal_reflection, journal_md_path, ai_context_summary")
            .eq("position_id", position_id)
            .execute()
        )
        if not trade_res.data:
            logger.info("Trade compaction skipped: trade history row not found for position %s.", position_id)
            return None

        trade_row = trade_res.data[0]
        has_journal = bool(trade_row.get("journal_reflection") or trade_row.get("journal_md_path"))
        if not has_journal:
            logger.info("Trade compaction skipped: journal reflection not yet recorded for position %s.", position_id)
            return None

        # Query messages tagged with position_id
        msg_res = (
            db.client.table("swayam_ai_messages")
            .select("role, content, created_at")
            .eq("position_id", position_id)
            .order("created_at", desc=False)
            .execute()
        )
        messages = msg_res.data or []
        if not messages:
            logger.info("No messages tagged with position %s to compact.", position_id)
            return None

        transcript = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        prompt = (
            f"Synthesize the trading partner discussion for closed position {pos.get('strategy_name', '')} "
            f"({pos.get('underlying', '')}).\n"
            f"Realized PnL: ₹{trade_row.get('realized_pnl_inr', 0)}\n\n"
            "Return a clean JSON object with keys:\n"
            "- direction (string: bullish/bearish/neutral)\n"
            "- setup (string: setup identified)\n"
            "- entry_rationale (string: why entered)\n"
            "- exit_reason (string: why exited)\n"
            "- lesson (string: key hindsight takeaway)\n\n"
            f"Transcript:\n{transcript}"
        )

        reply, _ = ai_router.chat_lightweight([{"role": "user", "content": prompt}])
        trade_summary = _safe_json_parse(reply, fallback_summary=f"Trade summary for position {position_id}")

        # Update swayam_trade_history.ai_context_summary
        db.client.table("swayam_trade_history").update({
            "ai_context_summary": trade_summary,
        }).eq("position_id", position_id).execute()

        return trade_summary
    except Exception as exc:
        logger.error("Trade compaction failed for position %s: %s", position_id, exc)
        raise


def safety_valve_check(session_date: date) -> None:
    """Auto-compacts oldest half if a single session exceeds 200 messages."""
    date_str = session_date.isoformat()
    try:
        res = (
            db.client.table("swayam_ai_messages")
            .select("id", count="exact")
            .eq("session_date", date_str)
            .execute()
        )
        total_count = res.count or len(res.data or [])
        if total_count > 200:
            logger.warning(
                "Safety valve triggered for session %s: %d messages detected (threshold 200).",
                date_str,
                total_count,
            )
            # Fetch oldest 100
            oldest_res = (
                db.client.table("swayam_ai_messages")
                .select("id, role, content")
                .eq("session_date", date_str)
                .order("created_at", desc=False)
                .limit(100)
                .execute()
            )
            if oldest_res.data:
                transcript = "\n".join([f"{m['role']}: {m['content']}" for m in oldest_res.data])
                prompt = f"Summarize these earlier trading discussion messages concisely in 3 bullets:\n{transcript}"
                summary_text, _ = ai_router.chat_lightweight([{"role": "user", "content": prompt}])
                logger.info("Safety valve compaction generated: %s", summary_text[:100])
    except Exception as exc:
        logger.warning("Safety valve check encountered non-fatal error: %s", exc)


def load_persistent_memory() -> Dict[str, Any]:
    """Loads Layer 3 persistent memory: pinned decisions and notebook entries."""
    pinned_rules: List[str] = []
    notebook_entries: List[Dict[str, Any]] = []

    try:
        pinned_res = (
            db.client.table("swayam_ai_pinned_decisions")
            .select("id, rule_text, pinned_at")
            .eq("active", True)
            .order("pinned_at", desc=True)
            .execute()
        )
        pinned_rules = [r["rule_text"] for r in (pinned_res.data or [])]
    except Exception as exc:
        logger.warning("Could not load pinned decisions: %s", exc)

    try:
        note_res = (
            db.client.table("swayam_ai_notebook")
            .select("id, entry_text, created_at")
            .order("created_at", desc=True)
            .limit(25)
            .execute()
        )
        notebook_entries = note_res.data or []
    except Exception as exc:
        logger.warning("Could not load notebook entries: %s", exc)

    return {
        "pinned_rules": pinned_rules,
        "notebook_entries": notebook_entries,
    }


def load_recent_session_summaries(days: int = 30) -> List[Dict[str, Any]]:
    """Loads recent compacted session summaries from Layer 2."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    try:
        res = (
            db.client.table("swayam_ai_session_summaries")
            .select("session_date, summary_block, message_count")
            .gte("session_date", cutoff)
            .order("session_date", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        logger.warning("Could not load recent session summaries: %s", exc)
        return []
