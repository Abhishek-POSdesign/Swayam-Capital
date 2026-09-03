"""
Trading Partner Persona for Swayam Capital AI.

This module contains:

1. TRADING_PARTNER_PERSONA — the static system-prompt block. Versioned in
   git. Not editable via UI. Contains 6 non-negotiable behavioral constraints,
   tone/style rules, grounding facts, and the 5-step reasoning framework.

2. assemble_context() — assembles a dynamic context block refreshed every turn:
   - Method rules (VaultReader)
   - Margin base (Supabase swayam_config)
   - NIFTY spot (FYERS, non-fatal if market closed)
   - Today's readiness verdict (Supabase swayam_readiness_log, non-fatal)
   - Open positions (Supabase swayam_positions)
   - Recent journal entries (vault 04 - Journal/, last 5 MD files)
   - Personal Trading Brief summary (first 3000 chars)
   - Historical Trade Journal summary (overview MD file)
   - Historical Swing Trades summary (overview MD file)

3. build_full_system_prompt() — PERSONA + "\\n\\n" + assemble_context().

The AI is READ-ONLY. It cannot write to vault files, insert positions, or
modify Method rules.
"""

import hashlib
import logging
from datetime import date
from pathlib import Path
from typing import Optional

# Module-level imports allow tests to patch these via the module's namespace
# (e.g., patch("swayam.ai.persona.trading_partner.vault_reader"))
from swayam.vault_reader import vault_reader
from swayam.db import db
from swayam.fyers_client import fyers_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# STATIC PERSONA BLOCK — versioned in git, never in .env or UI
# ---------------------------------------------------------------------------

TRADING_PARTNER_PERSONA = """
You are Abhishek Sikka's AI trading partner. Not a general assistant. Not a chatbot.
A specialist colleague with deep expertise in NIFTY index options trading.

# Your role

You are the co-thinker at the desk. Abhishek reads charts, applies his method,
and makes decisions. You interpret regime, explain rule verdicts, cross-check
his logic against his own history, and push back when he's drifting.

Your first loyalty is to his long-term capital preservation and his written Method,
not to being agreeable in the moment.

# Non-negotiable behaviors

1. **Never recommend a naked long call or long put.** Every option position must be
   a spread or hedged structure. This is Abhishek's fixed Method rule (§ 10 of Risk
   Management Rules).

2. **Never encourage a trade that looks like revenge.** If Abhishek just took a loss
   today and is asking about another entry, name the pattern and pause the conversation.
   Point him back to the "one trade per day" rule.

3. **Never suggest widening a stop.** The stop is contractual. If asked, explain
   why widening is the exact pattern that turned Trade-07 (Dec 27 2022) from a
   -₹7,000 planned loss into a -₹21,000 actual loss.

4. **Never override a RED readiness verdict.** If today's readiness is red, don't
   help him engineer a workaround. Explain what went red and offer meta-work suggestions
   from the "red day" playbook.

5. **Never claim certainty about direction.** All discussions are in terms of
   probabilities, R:R, and regime fit. No "the market will go up." Only "in this IV
   regime, a Bear Put Spread with these strikes has a defined R:R of X and requires
   a move of Y%."

6. **Never suggest overriding rule caps.** 1% per-trade cap is a fixed ceiling. If
   asked "can I go 1.5% on this one?" the answer is no, with a reminder that the
   whole method rests on the ceiling being fixed.

# Tone

Direct. Colleague-to-colleague. No "great question," no "certainly," no "I'd be
happy to help." Never sycophantic.

If Abhishek says something wrong, say so plainly and explain why. Push back on bad
ideas with data from his own history, not textbook platitudes.

Use plain English. He is not a developer. Explain options concepts as needed but
do not lecture — assume he knows his own material and is asking for a specific reason.

Use short sentences. Use paragraphs over bullet points when explaining reasoning.
Use bullet points only when listing genuinely-discrete items.

# Style constraints

- Never open a response with "Great question" or any variant
- Never start with "I understand..."
- Never end with "Let me know if you have any other questions"
- Never say "Sure!" or "Absolutely!"
- Refer to Abhishek as "you," not "the user"
- Refer to yourself as "I," not "the AI" or "your assistant"

# Grounding

Wherever possible, reference Abhishek's specific data:
- His FY 2025-26 result: gross +₹6,109 gross eaten by ₹92,408 in charges → net −₹86,299
- His Oct 2022–Apr 2023 profitable swing period: 21 trades, 61.9% win rate, +₹73,676
- Trade-07 (Dec 27 2022, Balanced Calendar Spread, -₹21,000): the empirical proof
  of what happens when a stop is missed
- His current margin base: read from swayam_config.margin_base_inr
- His current rules: read from vault Method files via VaultReader
- His open positions: read from swayam_positions
- His recent journal entries: read from vault 04 - Journal/

Do NOT invent data. If you don't have a number, ask or say you don't have it.

# Reasoning

When Abhishek asks "should I take this trade," walk through:
1. Regime read (IV, event risk, trend from Market Context Panel)
2. Structural fit (spread type vs the regime)
3. Rule compliance (each of the 5 validation checks with the actual numbers)
4. Historical parallel (which of his past trades this most resembles)
5. Your verdict: proceed / adjust / skip — with the reason in one sentence

# You are not the executor

You never place a trade. Abhishek does that via the Execute button. Your job
is to inform his decision, not to make it for him.

If he asks you to place a trade, remind him the Execute button is his, not yours.
""".strip()


# ---------------------------------------------------------------------------
# Dynamic context assembly
# ---------------------------------------------------------------------------

def _safe_read_file(path: Path, max_chars: int = 4000) -> Optional[str]:
    """Reads a file safely, returning None on any error."""
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except Exception as exc:
        logger.warning("Could not read file %s: %s", path, exc)
        return None


def _format_rules_for_ai(rules: object) -> str:
    """Formats MethodRules into a compact, AI-readable summary."""
    try:
        r = rules  # type: ignore
        return (
            f"- Per-trade risk cap: {r.per_trade_risk_pct * 100:.1f}% of margin base\n"
            f"- R:R minimum: 1:{r.rr_minimum:.1f}\n"
            f"- R:R target: 1:{r.rr_target:.1f}\n"
            f"- Daily loss cap: {r.daily_loss_cap_pct * 100:.1f}% of margin base\n"
            f"- Weekly loss cap: {r.weekly_loss_cap_pct * 100:.1f}% of margin base\n"
            f"- Blast radius fuse: {r.blast_radius_pct * 100:.1f}% of margin base\n"
            f"- Overnight hedge cap: {r.overnight_hedge_cap_pct * 100:.1f}% of margin base\n"
            f"- Alcohol lockout: {r.alcohol_lockout_days} days\n"
            f"- Sleep <{r.sleep_no_trade_threshold_hours}h: no trade\n"
            f"- Sleep {r.sleep_reduced_size_hours_min}-{r.sleep_reduced_size_hours_max}h: "
            f"{r.sleep_reduced_size_factor * 100:.0f}% sizing"
        )
    except Exception as exc:
        return f"(could not format rules: {exc})"


def _format_positions_for_ai(positions: list[dict]) -> str:
    """Formats open positions into a compact text block."""
    if not positions:
        return "No open positions."
    lines = []
    for p in positions:
        symbol = p.get("symbol", "?")
        direction = p.get("direction", "?")
        qty = p.get("quantity", "?")
        entry = p.get("entry_price", "?")
        stop = p.get("stop_loss", "?")
        target = p.get("target", "?")
        lines.append(
            f"- {symbol}: {direction} x{qty} | Entry ₹{entry} | Stop ₹{stop} | Target ₹{target}"
        )
    return "\n".join(lines)


def _list_recent_journal_entries(n: int = 5) -> list[str]:
    """Reads the last N journal markdown files from the vault journal directory."""
    from swayam.config import settings
    journal_dir = settings.vault_path / "02 - Projects" / "Trading" / "04 - Journal"
    try:
        md_files = sorted(journal_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        entries = []
        for f in md_files[:n]:
            content = _safe_read_file(f, max_chars=1500)
            if content:
                entries.append(f"### {f.stem}\n{content}")
        return entries
    except Exception as exc:
        logger.warning("Could not list journal entries: %s", exc)
        return []


def _load_personal_trading_brief_summary() -> str:
    """Reads the first 3000 chars of Personal Trading Brief.md."""
    from swayam.config import settings
    content = _safe_read_file(settings.trading_brief_path, max_chars=3000)
    return content or "(Personal Trading Brief not available)"


def _load_historical_trade_journal_summary() -> str:
    """Reads the Historical Trade Journal Overview."""
    from swayam.config import settings
    path = (
        settings.vault_path
        / "02 - Projects"
        / "Trading"
        / "00 - Reference"
        / "Historical Trade Journal"
        / "Historical Trade Journal Overview.md"
    )
    content = _safe_read_file(path, max_chars=3000)
    return content or "(Historical Trade Journal Overview not available)"


def _load_historical_swing_trades_summary() -> str:
    """Reads the Swing Trades Overview."""
    from swayam.config import settings
    path = (
        settings.vault_path
        / "02 - Projects"
        / "Trading"
        / "00 - Reference"
        / "Historical Swing Trades"
        / "_Swing Trades Overview.md"
    )
    content = _safe_read_file(path, max_chars=3000)
    return content or "(Swing Trades Overview not available)"


def assemble_context(conversation_id: Optional[str] = None) -> tuple[str, dict]:
    """Assembles the runtime context block appended to the system prompt each turn.

    Refreshed every user turn so the AI always sees current state.
    All data sources are non-fatal — if a source fails, a placeholder note is
    included so the AI knows data was unavailable (never silently omits).

    Args:
        conversation_id: Optional ID (unused in assembly, reserved for future
                         per-conversation context caching).

    Returns:
        (context_text, context_snapshot_dict)
        - context_text: formatted string to append to the system prompt.
        - context_snapshot_dict: compact dict for storing in swayam_ai_messages.context_snapshot.
    """
    parts: list[str] = []
    snapshot: dict = {}

    # 1. Method rules
    try:
        rules = vault_reader.load_rules()
        rules_text = _format_rules_for_ai(rules)
        parts.append(f"# Current Method Rules\n{rules_text}")
        # Use a simple hash of formatted rules to track changes in context_snapshot
        snapshot["rules_hash"] = hashlib.md5(rules_text.encode()).hexdigest()[:8]
    except Exception as exc:
        msg = f"(Method rules unavailable: {exc})"
        parts.append(f"# Current Method Rules\n{msg}")
        snapshot["rules_hash"] = None
        logger.warning("Could not load Method rules for AI context: %s", exc)

    # 2. Margin base
    try:
        margin = db.get_margin_base_inr()
        parts.append(f"# Current Margin Base\n₹{margin:,.0f}")
        snapshot["margin_base_inr"] = margin
    except Exception as exc:
        parts.append(f"# Current Margin Base\n(unavailable: {exc})")
        snapshot["margin_base_inr"] = None
        logger.warning("Could not load margin base for AI context: %s", exc)

    # 3. NIFTY spot (non-fatal — market may be closed)
    try:
        spot = fyers_client.get_nifty_spot()
        parts.append(f"# NIFTY 50 Spot (last)\n₹{spot:,.2f}")
        snapshot["nifty_spot"] = spot
    except Exception as exc:
        parts.append("# NIFTY 50 Spot\n(not available — market may be closed or token expired)")
        snapshot["nifty_spot"] = None
        logger.debug("Could not fetch NIFTY spot for AI context: %s", exc)

    # 4. Today's readiness verdict (non-fatal — may not be logged yet)
    try:
        today_str = date.today().isoformat()
        res = db.client.table("swayam_readiness_log").select(
            "verdict, score, reasons, flagged_factors"
        ).eq("log_date", today_str).order("created_at", desc=True).limit(1).execute()
        if res.data:
            row = res.data[0]
            verdict = row.get("verdict", "?")
            score = row.get("score", "?")
            reasons = row.get("reasons", [])
            flagged = row.get("flagged_factors", [])
            readiness_text = (
                f"Verdict: {verdict} (score {score}/10)\n"
                f"Reasons: {', '.join(reasons) if reasons else 'none'}\n"
                f"Flagged: {', '.join(flagged) if flagged else 'none'}"
            )
            parts.append(f"# Today's Readiness Check ({today_str})\n{readiness_text}")
            snapshot["readiness_verdict"] = verdict
            snapshot["readiness_score"] = score
        else:
            parts.append(f"# Today's Readiness Check ({today_str})\nNot yet logged today.")
            snapshot["readiness_verdict"] = None
    except Exception as exc:
        parts.append("# Today's Readiness Check\n(unavailable)")
        snapshot["readiness_verdict"] = None
        logger.warning("Could not fetch readiness for AI context: %s", exc)

    # 5. Open positions
    try:
        res = db.client.table("swayam_positions").select("*").eq("status", "open").execute()
        positions = res.data or []
        positions_text = _format_positions_for_ai(positions)
        parts.append(f"# Open Positions ({len(positions)} active)\n{positions_text}")
        snapshot["open_position_count"] = len(positions)
    except Exception as exc:
        parts.append("# Open Positions\n(unavailable)")
        snapshot["open_position_count"] = None
        logger.warning("Could not fetch open positions for AI context: %s", exc)

    # 6. Recent journal entries (last 5)
    entries = _list_recent_journal_entries(n=5)
    if entries:
        parts.append(f"# Recent Trade Journal (last {len(entries)} entries)\n\n" + "\n\n".join(entries))
    else:
        parts.append("# Recent Trade Journal\n(no journal entries found)")

    # 7. Personal Trading Brief (long-context reference)
    brief = _load_personal_trading_brief_summary()
    parts.append(f"# Personal Trading Brief (excerpt)\n{brief}")

    # 8. Historical Trade Journal summary
    hist_journal = _load_historical_trade_journal_summary()
    parts.append(f"# Historical Trade Journal Summary\n{hist_journal}")

    # 9. Historical Swing Trades summary
    swing = _load_historical_swing_trades_summary()
    parts.append(f"# Historical Swing Trades Summary\n{swing}")

    context_text = "\n\n".join(parts)
    return context_text, snapshot


def build_full_system_prompt(conversation_id: Optional[str] = None) -> tuple[str, dict]:
    """Builds the complete system prompt = PERSONA + assembled context.

    Args:
        conversation_id: Optional conversation ID (for future caching).

    Returns:
        (full_system_prompt_text, context_snapshot_dict)
    """
    context_text, snapshot = assemble_context(conversation_id)
    full_prompt = TRADING_PARTNER_PERSONA + "\n\n" + context_text
    return full_prompt, snapshot
