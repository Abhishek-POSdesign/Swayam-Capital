# AI Memory System — Swayam Capital (BUILD-9-FIXES-B)

## Overview

Swayam Capital features a **3-tier, event-driven memory architecture** designed specifically for real-world options trading workflows. Unlike arbitrary message-count truncations, Swayam structures memory around trading sessions and trade lifecycles.

---

## 1. The 3-Tier Memory Model

### Layer 1: Verbatim Working Memory
- **Behavior:** Never compacts while a trading day or position is active.
- **Scope:** Every message exchanged during an active session and all messages tagged with an active `position_id` are preserved verbatim.
- **Context Injection:** Active messages are passed in full to Gemini to ensure zero loss of intraday nuance or decision logic.

### Layer 2: Event-Boundary Auto-Compaction
Compaction runs via `gemini-2.5-flash-lite` at specific lifecycle moments:
1. **End-of-Day Compaction (Daily at 4:00 PM IST):**
   - Compacts the day’s conversation into a structured summary block:
     - `summary`: High-level narrative of the trading day.
     - `decisions`: Executed trades, skipped setups, risk allocations.
     - `questions`: Open questions or hypotheses explored.
     - `preferences`: User trading inclinations noted.
     - `constraints`: Rules or limitations tested.
     - `nextSteps`: Preparation items for tomorrow.
   - Stored in `swayam_ai_session_summaries` table.
2. **Trade Closed & Journaled Compaction:**
   - When a position is marked `closed` in `swayam_positions` AND a reflection is entered in `swayam_trade_history.journal_reflection`, all position-specific discussion is compacted into `ai_context_summary`.
3. **Explicit Clear:**
   - User-initiated clear chat force-compacts recent messages before resetting screen state.

### Layer 3: Persistent Long-Term Memory (Permanent Context)
1. **Memory Notebook (`swayam_ai_notebook`):**
   - Click the 📓 icon on any AI message or save manual notes via the settings drawer.
   - Stored permanently with timestamps; included in every system prompt.
2. **Pinned Rules & Constraints (`swayam_ai_pinned_decisions`):**
   - Click the ⭐ icon on any directive or add rules via the settings drawer.
   - Pinned rules remain in permanent prompt context forever until explicitly unpinned.

### Layer 4: Safety Valve
- If an active session exceeds **200 messages**, the oldest half is auto-compacted using cheap tier to protect token limits.

---

## 2. Supabase Tables

- `swayam_ai_session_summaries`: Daily structured summaries.
- `swayam_ai_notebook`: User-saved key insights and lessons.
- `swayam_ai_pinned_decisions`: Permanent operating constraints and trading rules.
- `swayam_ai_messages`: Extended with `position_id` and `session_date`.
- `swayam_trade_history`: Extended with `ai_context_summary` and `journal_reflection`.
