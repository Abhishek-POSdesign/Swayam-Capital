# Operational Readiness Workflow 🌅

## 1. Design Philosophy: Manual-First, Data-Verified

In automated algorithmic platforms, health checks often assume automated sync from smartwatches and rings happens before trading. **For Abhishek Sikka, that assumption fails:**

- **Night Shift Reality:** Abhishek wakes between 1:00 PM and 2:00 PM IST.
- **Decision Window:** He sits at the workstation around 2:30 PM. Markets close at 3:30 PM. He has a tight 30–45 minute window to evaluate setups and execute.
- **Delayed Sync:** Health Connect and smartwatch sleep/activity data frequently does not finish syncing to the Obsidian Second Brain daily log until ~3:00 PM.
- **Core Principle:** *"Manual entries has to be primary source. How I am feeling is bigger than any data. Data can be used for later verification."*

---

## 2. Pre-Market Workflow (2:30 PM IST)

When opening `http://localhost:5173`, the top section displays the **60-Second Readiness Check**:

```
[🌅 60-Second Readiness Check]
Sleep Duration:    [ Dropdown: 7+ hours (Well Rested) ▼ ] (Autofilled from Atlas if synced)
Alcohol Yesterday: [ No (Clean) ▼ ]
Workout in 48h:    [ Yes (Active) ▼ ]
Life Stressor:     [ None ▼ ] [ Optional Note: ____________ ]
How do I feel?:    [ 🎯 Focused ]  [ ⚖️ Neutral ]  [ 🥱 Tired ]  [ ⚡ Off ]  [ 🛑 Angry/Grief ]
                   ↳ * Required: No default! Abhishek must choose.
[ ✓ Submit Readiness ]
```

1. **Autofill Defaults:** If any data (like sleep duration or workout) is *already* present in today's `{YYYY-MM-DD}.md` daily log, it is pre-selected as a suggestion. If not synced yet, fields remain blank for rapid selection.
2. **Subjective Feeling is Mandatory:** Mood is never defaulted. Abhishek must choose how he feels.
3. **Execution Gating:**
   - **🟢 GREEN (1.0% Risk):** Full trading authorized. Strategy Builder is enabled with standard 1% capital ceiling.
   - **🟡 YELLOW (0.75% Risk or Caution):** Sizing reduced to 75% if sleep was 5–6h; positional discipline warned if workout missing. Strategy validation strictly enforces the reduced risk ceiling.
   - **🔴 RED (Trading Blocked):** If sleep was < 5h, alcohol was consumed, mood was Angry/Grief, or active 90-day lockout is running, trading is blocked. Strategy Builder is disabled, and backend `/api/strategy/validate` refuses execution.

---

## 3. Re-Logging State

If Abhishek takes a 30-minute nap, has coffee, or resolves a personal stressor before market close, he can click **✎ Re-log State**.  
- Re-logging allows updating today's assessment.
- Supabase updates the row with the latest timestamp.
- The reconciler records any changes between attempts.

---

## 4. Evening Pattern Reconciler (10:00 PM IST)

At 22:00 IST daily, a scheduled background job (`scripts/run_reconciler.py`) executes:

1. Re-reads today's now-finalized daily log in `01 - Daily Logs/{YYYY-MM-DD}.md`.
2. Compares the synced smartwatch data with Abhishek's 2:30 PM manual assessment.
3. Stores discrepancies in `swayam_readiness_log.factors.reconciliation`.
4. **Non-Corrective:** Discrepancies are **data for learning**, not punishments or retroactive changes:
   - *"You logged 6h sleep at 2:30 PM, but your watch recorded 4.5h. You may be underestimating your physical fatigue."*
   - This history feeds directly into the AI Trading Partner (BUILD-6) to identify blind spots over months of trading.
