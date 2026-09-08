"""
Trading Partner Persona for Swayam Capital AI.

This module contains:

1. TRADING_PARTNER_PERSONA — the static system-prompt block. Versioned in
   git. Not editable via UI. Contains 6 non-negotiable behavioral constraints,
   tone/style rules, grounding facts, and the 5-step reasoning framework.

2. assemble_context() — assembles a dynamic context block refreshed every turn:
   - Method rules (VaultReader)
   - Live capital (FYERS funds(), the same source Home and the risk gate use)
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
from swayam.services import capital as capital_service
from swayam.options_math.realized_vol import compute_realized_vol, daily_sigma_from_annualized

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

4. **The readiness check is a journal with zero power.** He fills it in himself, so
   it can be lied to, and on 2026-09-07 he removed its authority over trading: a red
   readiness verdict cannot block a trade and cannot shrink his size. Never tell him a
   readiness verdict limits him. You may name what he logged (sleep, mood, a stressor)
   as context for a conversation, never as a gate.

5. **Never claim certainty about direction.** All discussions are in terms of
   probabilities, R:R, and regime fit. No "the market will go up." Only "in this IV
   regime, a Bear Put Spread with these strikes has a defined R:R of X and requires
   a move of Y%."

6. **Never suggest overriding rule caps.** The 1% running-loss cap is a fixed
   ceiling. If asked "can I go 1.5% on this one?" the answer is no, with a reminder
   that the whole method rests on the ceiling being fixed. Every cap is a percentage
   of his LIVE FYERS balance, read fresh each session and shown in the context below
   as "Live Capital". Never compute a cap from any other figure, and never quote a
   cap in rupees unless the live balance is in your context. If the balance is
   unavailable, say so and give the percentage only.

7. **Active Testing & Paper-Trading Mode.** The platform is currently operating in
   an active testing and validation phase. You must always acknowledge and treat all
   trade setups, hypothetical margin balances, and paper executions as test iterations.
   Never assume real money is being committed until Abhishek explicitly confirms
   live broker production activation.

# How I think about risk

When you critique a trade or evaluate its risk, always distinguish between REALISTIC RISK (the loss at 2σ NIFTY move — the day-to-day bad case, 1% of the live balance) and BLAST RADIUS (the absolute mathematical max loss — the black-swan ceiling, 5% of the live balance). A trade can look "risky" on the blast-radius number while being perfectly sized on realistic risk. That distinction is intentional. When you explain a spread to me, give me both numbers with that framing.

His four rules, settled 2026-09-08, every one a percentage of the live FYERS balance:
1. Running loss: 1%. Exit, no debate.
2. Overnight gap: 2%, tested at twice the average daily move. This is the ONLY rule that can stop anything, and it only stops CARRYING a position overnight.
3. Black swan: 5%, the worst case at expiry.
4. Deployable margin ceiling: twice the cash equivalent he holds.

Entry is NEVER blocked, including naked and half-built structures, because converting a straddle into a condor passes through states no gate would allow. Only carrying overnight is gated: hedged, and inside the gap test. There is no reward-to-risk minimum or target any more; that rule was deleted. Do not invent one.

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
- His live capital: the FYERS balance in the "Live Capital" section below, with the rupee caps derived from it
- His current rules: read from vault Method files via VaultReader
- His open positions: read from swayam_positions
- His recent journal entries: read from vault 04 - Journal/

Do NOT invent data. If you don't have a number, ask or say you don't have it.

# Reasoning

When Abhishek asks "should I take this trade," walk through:
1. Regime read (IV, event risk, trend from Market Context Panel)
2. Structural fit (spread type vs the regime)
3. Rule compliance (his four rules, with the actual rupee numbers from the live balance)
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
        # The four rules he settled on 2026-09-08. Every cap is a percentage of
        # the LIVE FYERS balance, never of a stored figure. The vault's method
        # files still carry an R:R minimum and target; those were deleted from
        # his rules and are deliberately not shown to the AI.
        return (
            f"- Running loss cap (rule 1): {r.realistic_risk_cap_pct * 100:.1f}% of the live balance (2σ, 20d vol)\n"
            f"- Overnight gap (rule 2): 2.0% of the live balance, tested at twice the average daily move; the only gate, and it gates carrying overnight only\n"
            f"- Black swan (rule 3): 5.0% of the live balance, the worst case at expiry\n"
            f"- Deployable margin ceiling (rule 4): twice the cash equivalent held\n"
            f"- Per-trade risk cap: {r.per_trade_risk_pct * 100:.1f}% of the live balance\n"
            f"- Daily loss cap: {r.daily_loss_cap_pct * 100:.1f}% of the live balance\n"
            f"- Weekly loss cap: {r.weekly_loss_cap_pct * 100:.1f}% of the live balance\n"
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


def _list_recent_journal_entries(n: int = 7) -> list[str]:
    """Reads the last N journal markdown files from the vault journal directory.
    Last 3 in full body; days 4-7 as concise one-line summaries.
    """
    from swayam.config import settings
    journal_dir = settings.vault_path / "02 - Projects" / "Trading" / "04 - Journal"
    try:
        if not journal_dir.exists():
            return []
        md_files = sorted(journal_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        entries = []
        for idx, f in enumerate(md_files[:n]):
            if idx < 3:
                content = _safe_read_file(f, max_chars=3000)
                if content:
                    entries.append(f"### {f.stem} (Full Entry)\n{content}")
            else:
                content = _safe_read_file(f, max_chars=140)
                if content:
                    summary_line = content.replace("\n", " ").strip()
                    entries.append(f"- **{f.stem}**: {summary_line}")
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


def _load_influences_summary() -> str:
    """Reads summaries of the 4 key trading influences from the vault."""
    from swayam.config import settings
    inf_dir = settings.vault_path / "02 - Projects" / "Trading" / "00 - Reference" / "Influences"
    if not inf_dir.exists():
        return "(Influences reference directory not found)"
    items = [
        "Tom Hougaard - Best Loser Wins.md",
        "Mark Minervini - Discipline and Mindset.md",
        "Theta Gainer - Options Selling.md",
        "Subasish Pani - Power of Stocks.md",
    ]
    parts = []
    for fname in items:
        f = inf_dir / fname
        if f.exists():
            content = _safe_read_file(f, max_chars=1200)
            if content:
                parts.append(f"### {f.stem}\n{content}")
    return "\n\n".join(parts) if parts else "(No influences notes found)"


def _load_recent_backtest_runs_summary(limit: int = 5) -> str:
    """Loads the last N backtest runs from swayam_backtest_runs table."""
    try:
        res = (
            db.client.table("swayam_backtest_runs")
            .select("run_at, strategy_name, win_rate, avg_rr, expectancy_inr, max_drawdown_pct")
            .order("run_at", desc=True)
            .limit(limit)
            .execute()
        )
        runs = res.data or []
        if not runs:
            return "(No recent backtest runs recorded)"
        lines = []
        for r in runs:
            strat = r.get("strategy_name", "?")
            wr = f"{float(r['win_rate']) * 100:.1f}%" if r.get("win_rate") is not None else "N/A"
            rr = f"1:{float(r['avg_rr']):.2f}" if r.get("avg_rr") is not None else "N/A"
            exp = f"₹{float(r['expectancy_inr']):,.0f}" if r.get("expectancy_inr") is not None else "N/A"
            lines.append(f"- {strat}: Win Rate {wr}, Avg R:R {rr}, Expectancy {exp}")
        return "\n".join(lines)
    except Exception as exc:
        return f"(Could not load backtest runs: {exc})"


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

    # 0. Operational status
    parts.append(
        "# Platform Operational Status\n"
        "Phase: Active Testing & Paper-Trading Mode. All trade setups and orders are simulated for validation. "
        "Acknowledge testing mode directly whenever discussing executions or portfolio risk."
    )
    snapshot["mode"] = "paper_testing"

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

    # 2. Live capital, from FYERS, the same source Home and the risk gate use.
    #
    # This used to read `swayam_config.margin_base_inr`, a number typed into
    # the config table reading Rs 8,50,000 and never updated. On 2026-09-08 the
    # AI told him his running-loss cap was Rs 8,500 while his real balance was
    # about Rs 9,71,000 and the real cap Rs 9,710. It must never fall back to
    # the config table: if the broker cannot be reached, the AI is told the
    # balance is unavailable and given the percentages only.
    try:
        cap = capital_service.get_capital()
        ceiling = (
            f"₹{cap.deployable_margin_ceiling_inr:,.0f}"
            if cap.deployable_margin_ceiling_inr is not None
            else f"unavailable ({cap.ceiling_unavailable_reason})"
        )
        parts.append(
            "# Live Capital (FYERS, read fresh this session)\n"
            f"Balance: ₹{cap.risk_capital_inr:,.0f} (source: {cap.source}, read {cap.taken_at:%H:%M} UTC on {cap.trading_day:%d %b %Y})\n"
            f"Rule 1, running loss cap (1%): ₹{cap.primary_risk_cap_inr:,.0f}\n"
            f"Rule 2, overnight gap cap (2%): ₹{cap.risk_capital_inr * 0.02:,.0f}\n"
            f"Rule 3, black swan fuse (5%): ₹{cap.black_swan_fuse_inr:,.0f}\n"
            f"Rule 4, deployable margin ceiling (2x cash equivalent): {ceiling}\n"
            "Every cap above is a percentage of this live balance. Quote these rupee figures, never a stored one."
        )
        snapshot["risk_capital_inr"] = round(cap.risk_capital_inr, 2)
        snapshot["capital_source"] = cap.source
    except Exception as exc:
        parts.append(
            "# Live Capital (FYERS)\n"
            f"UNAVAILABLE: the live FYERS balance could not be read ({exc}). "
            "Every cap is a percentage of that balance, so no rupee cap can be stated. "
            "Give percentages only and say the balance is unavailable. Do not use any other figure."
        )
        snapshot["risk_capital_inr"] = None
        snapshot["capital_source"] = None
        logger.warning("Could not load live capital for AI context: %s", exc)

    # 3. NIFTY spot (non-fatal — market may be closed)
    try:
        spot = fyers_client.get_nifty_spot()
        parts.append(f"# NIFTY 50 Spot (last)\n₹{spot:,.2f}")
        snapshot["nifty_spot"] = spot
    except Exception as exc:
        parts.append("# NIFTY 50 Spot\n(not available — market may be closed or token expired)")
        snapshot["nifty_spot"] = None
        logger.debug("Could not fetch NIFTY spot for AI context: %s", exc)

    # 3b. Realized Volatility (NIFTY 20-day)
    try:
        ann_vol = compute_realized_vol(symbol="NIFTY", as_of_date=date.today(), window_days=20)
        daily_sigma = daily_sigma_from_annualized(ann_vol)
        vol_pct = round(ann_vol * 100, 2)
        parts.append(
            f"# Realized Volatility (NIFTY 20-day)\n"
            f"Annualized: {vol_pct:.2f}% | 1σ daily: {daily_sigma * 100:.2f}% | 2σ daily: {daily_sigma * 200:.2f}%"
        )
        snapshot["realistic_vol_pct"] = vol_pct
    except Exception as exc:
        parts.append("# Realized Volatility (NIFTY 20-day)\n(not available)")
        snapshot["realistic_vol_pct"] = None
        logger.debug("Could not compute realized vol for AI context: %s", exc)

    # 4. Today's readiness verdict (non-fatal - may not be logged yet)
    #
    # This query used to select verdict/score/reasons/flagged_factors ordered by
    # created_at. NONE of score, reasons, flagged_factors or created_at exists on
    # swayam_readiness_log, so every call failed with Postgres 42703 and the AI
    # silently never saw his readiness at all. The real columns are log_date,
    # verdict, factors, trading_allowed, size_cap_pct and computed_at.
    try:
        today_str = date.today().isoformat()
        res = (
            db.client.table("swayam_readiness_log")
            .select("verdict, factors, trading_allowed, size_cap_pct")
            .eq("log_date", today_str)
            .order("computed_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            row = res.data[0]
            verdict = row.get("verdict", "?")
            factors = row.get("factors") or {}
            if isinstance(factors, dict):
                factor_text = ", ".join(f"{k}: {v}" for k, v in factors.items()) or "none"
            else:
                factor_text = str(factors)
            readiness_text = (
                f"Verdict: {verdict}\n"
                f"Factors: {factor_text}\n"
                "This is a journal ONLY. It has no power over his trading: it "
                "cannot block a trade and it cannot shrink his size. He removed "
                "that on 2026-09-07 because a form he fills in himself can be "
                "lied to. Never tell him a readiness verdict limits him."
            )
            parts.append(f"# Today's Readiness Check ({today_str})\n{readiness_text}")
            snapshot["readiness_verdict"] = verdict
            snapshot["readiness_score"] = None
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

    # 10. Persistent Memory (Layer 3: Pinned rules & Notebook)
    try:
        from swayam.ai.memory import load_persistent_memory
        mem = load_persistent_memory()
        pinned = mem.get("pinned_rules", [])
        notes = mem.get("notebook_entries", [])
        if pinned:
            parts.append("# Pinned Trading Rules & Directives (Permanent)\n" + "\n".join([f"- {r}" for r in pinned]))
        if notes:
            note_lines = [f"- [{n['created_at'][:10]}] {n['entry_text']}" for n in notes]
            parts.append("# Memory Notebook (Key Insights)\n" + "\n".join(note_lines))
    except Exception as exc:
        logger.warning("Could not load persistent memory for context: %s", exc)

    # 11. Recent Session Summaries (Layer 2)
    try:
        from swayam.ai.memory import load_recent_session_summaries
        summaries = load_recent_session_summaries(days=30)
        if summaries:
            sum_lines = []
            for s in summaries[:5]:
                blk = s.get("summary_block", {})
                sum_text = blk.get("summary", "") if isinstance(blk, dict) else str(blk)
                sum_lines.append(f"- **{s['session_date']}**: {sum_text}")
            parts.append("# Recent Session Summaries (Last 30 Days)\n" + "\n".join(sum_lines))
    except Exception as exc:
        logger.warning("Could not load session summaries for context: %s", exc)

    # 12. Trading Influences & Mentors
    influences = _load_influences_summary()
    parts.append(f"# Trading Influences & Mentors\n{influences}")

    # 13. Recent Backtest Runs
    backtests = _load_recent_backtest_runs_summary(limit=5)
    parts.append(f"# Recent Backtest Runs\n{backtests}")

    # 14. Upcoming Macro Events & Planning Context (BUILD-11.10)
    try:
        from swayam.ai.context_builder import build_planning_context
        macro_ctx = build_planning_context()
        if macro_ctx:
            parts.append(f"# Upcoming Macro Risk & Planning Context\n{macro_ctx}")
    except Exception as exc:
        logger.warning("Could not load macro planning context: %s", exc)

    # 15. "So Far Today" — the grounded market summary he pays for.
    #
    # He said it plainly on 2026-09-08: "I want my AI to see this info as well,
    # because I'm paying to get that info. When I brainstorm with the AI, it
    # must read this data." Until now the summary was generated, shown on the
    # home page, and never reached the model, so the same grounded search was
    # effectively paid for twice: once for him to read, once for the model to
    # guess at the same thing.
    #
    # Cache only. Generating here would fire a paid grounded search on every AI
    # turn, which breaks his standing rule that AI-heavy work is always a manual
    # button with a cache and a daily cap.
    try:
        from swayam.services.so_far_today import get_cached_so_far_today

        so_far = get_cached_so_far_today(max_age_minutes=180)
        if so_far and so_far.get("text"):
            age = so_far.get("age_minutes")
            stamp = f" (generated {age} minutes ago)" if age is not None else ""
            sources = so_far.get("sources") or []
            src_line = ""
            if sources:
                named = ", ".join(
                    str(s.get("title") or s.get("uri") or s)[:80] for s in sources[:5]
                )
                src_line = f"\nSources: {named}"
            parts.append(
                "# So Far Today, the grounded market summary he has already read"
                f"{stamp}\n{so_far['text']}{src_line}"
            )
    except Exception as exc:
        logger.warning("Could not load So Far Today for AI context: %s", exc)
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
