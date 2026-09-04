# 🧘 Operational Readiness Rules

**Purpose:** The check *before* the pre-trade check. Reads life data from the Atlas-synced daily log, decides whether you're in a state to trade today at all.

*Part of [[Method Overview]]. This is the operationalization of the "trading is a mirror of real life" principle from [[Trading Philosophy]] § 5 and the entire "Different man now" thesis in [[Trading Journey - The Story So Far]].*

---

## Where the data comes from

Every morning, before any setup evaluation, the system reads that day's daily log from `01 - Daily Logs/YYYY-MM-DD.md`. That file is auto-synced from Atlas at 4 PM and 10 PM daily and contains:

- **Sleep** — hours slept, wake time, sleep quality (if logged)
- **Recovery streaks** — alcohol-free days, smoke-free days
- **Workout** — session logged today or not
- **Journal / Brain Dumps** — honest reflections, mood signals
- **Checklist** — daily-routine completion
- **Tasks / commitments** — what's on your plate today

**None of this data lives in the trading vault** — it lives in Atlas and syncs into `01 - Daily Logs/`. The trading system just *reads* it. This is by design (see [[Personal Trading Brief]] → "Vault reads Atlas, never overwrites it").

---

## The three-tier readiness check

Every trading day starts with a color-coded readiness verdict computed from the daily log:

- 🟢 **GREEN — normal trading day.** All rules apply as-is.
- 🟡 **YELLOW — cautious day.** Position sizes capped; specific setups disallowed.
- 🔴 **RED — no trading.** Off day. Log the reason, don't override.

**Verdict is the strictest of any factor below.** If sleep is green but alcohol is red → the day is red.

---

## Factor 1 — Sleep

*(Grounded in your own history: night-shift + inconsistent trading hours were a major driver of the FY25-26 losses. See [[Trading Journey - The Story So Far]] and [[Personal Reference Brief]] § 9.)*

| Sleep last night | Verdict | Rule |
|:---|:---:|:---|
| ≥ 6 hours, quality good | 🟢 | Normal size, normal setups |
| 5–6 hours, quality decent | 🟡 | Position size capped at 75% of normal (0.75% risk instead of 1%) |
| < 5 hours | 🔴 | **No trading.** Sleep debt = decision debt |
| No sleep log at all today | 🟡 | Cannot verify → treat as cautious. Log honestly before trading. |

**Rationale:** below 5 hours you are demonstrably worse at pattern recognition, worse at impulse control, and worse at closing losers cleanly. This is not conservative — it's protective.

## Factor 2 — Alcohol / substance status

*(**Non-negotiable. Tightened by Abhishek 2026-09-03 late night.** From [[Personal Trading Brief]] and the entire March 2026 → present sobriety arc in [[Trading Journey - The Story So Far]].)*

| Status | Verdict | Rule |
| :--- | :---: | :--- |
| **Zero alcohol, current streak intact** | 🟢 | Normal |
| **Any alcohol consumption at all** (last 24h, last 7 days, last month — doesn't matter) | 🔴 | **Trading LOCKED for a minimum of 3 months of continuous total sobriety.** The 90-day clock RESTARTS on the last day of consumption. Only after 90 unbroken days sober does trading resume — at reduced size (see re-entry ramp below). |

**In Abhishek's own words:** *"Alcohol means completely stopping trading for three months until I am a minimum of three months sober. No trading."*

### Re-entry ramp after a 90-day lockout

When the 90-day sobriety clock completes and trading can resume, position sizes ramp back gradually — not straight to 1%:

- **Days 91–120 (Month 4)**: 0.25% risk per trade cap (¼ of normal)
- **Days 121–150 (Month 5)**: 0.50% risk per trade cap (½ of normal)
- **Days 151–180 (Month 6)**: 0.75% risk per trade cap (¾ of normal)
- **Day 181+**: normal 1% cap resumes

**Rationale:** the entire "different man now" thesis rests on the sobriety being real. If alcohol enters the picture, the system that assumes sobriety is now operating on false input. This isn't punitive — it's **the integrity check the whole method depends on.** The re-entry ramp exists because immediate return to full size after a relapse invites the exact "prove I'm still OK" pattern that broke discipline in the first place.

**This is the rule most likely to feel unfair on a specific day. It won't be. Trust the rule.**

## Factor 3 — Journal / mood signal

*(Reads today's Brain Dump / journal entry from the daily log.)*

| Signal from today's journal | Verdict | Rule |
|:---|:---:|:---|
| Neutral to positive | 🟢 | Normal |
| Elevated stress, family issue, work pressure noted | 🟡 | Positional-only (no fresh entries in high-vol regimes); tighter stops on existing positions |
| Explicit anger, grief, revenge sentiment, or "I want to prove something" | 🔴 | **No trading.** Emotional state is a poor decision-maker. |
| No journal entry at all today | 🟡 | Cannot verify → cautious. Write a brief journal entry before proceeding. |

**Rationale:** your own words repeatedly across the historical journals: bad journal state → bad trades. This is empirically true for you. Trade-06's "destructive mindset forced me to push the kill switch" is the pattern in one sentence.

## Factor 4 — Workout / physical state

*(This is a leading indicator of the discipline you value. From [[Trading Journey - The Story So Far]] — your current cravings list explicitly includes "workout" as a top item.)*

| Workout status | Verdict | Rule |
|:---|:---:|:---|
| Worked out yesterday or today | 🟢 | Normal |
| Missed workout for 3+ consecutive days without a scheduled rest week | 🟡 | Positional-only, no new entries today (existing positions managed as normal) |
| Missed workout for 7+ consecutive days | 🔴 | **No trading. Root-cause the pattern.** This is the "upstream life is slipping" signal. |

**Rationale:** the workout is a proxy for whether you're honoring the life-first order (workout → sleep → business → learning → money — the honest craving list). Skipping it 7 days in a row means one of them is out of order. Fix that first.

## Factor 5 — Recovery streak (alcohol-free)

*(Uses Atlas's `atlas_targets` + `atlas_streak_relapses` data once that syncs.)*

| Streak status | Verdict | Rule |
|:---|:---:|:---|
| Alcohol-free streak growing normally | 🟢 | Normal |
| **Alcohol streak reset (any recency)** | 🔴 | **See Factor 2** — 90-day lockout applies, then re-entry ramp. |

**Smoking / vaping is NOT tracked here** (confirmed 2026-09-03 late night). Abhishek quit smoking ~2 years ago, then quit vaping a few months ago. Neither is coming back. **Only alcohol matters** because it changes brain structure and directly threatens the decision-making the whole trading system rests on. Abhishek's stated commitment: *"I'll think about alcohol not before I retire in 5–20 years."*

**Rationale:** a streak reset is a signal, not a shame. Alcohol resets trigger Factor 2's 90-day lockout at the highest severity. There is no lighter option for alcohol.

---

## The composite verdict — one number for the day

The system produces a single **DAILY READINESS SCORE** from the five factors above. Verdict is the strictest of all five.

**Example output for a hypothetical Monday:**

```
🟢 Sleep: 7h, decent quality
🔴 Alcohol: consumption last night (Sunday social)
🟢 Journal: neutral, planning-focused
🟢 Workout: 4-day streak
🟢 Recovery: alcohol-free streak reset yesterday

DAILY READINESS: 🔴 RED — NO TRADING TODAY
Reason: alcohol consumption in last 24h. See Operational Readiness Rules Factor 2.
Next re-check: tomorrow 8 AM. Meanwhile: rest, hydrate, log honestly.
```

**And a hypothetical green day:**

```
🟢 Sleep: 7.5h
🟢 Alcohol: 45-day streak
🟢 Journal: focused, "let's find something clean today"
🟢 Workout: yesterday, 30 min
🟢 Recovery: both streaks intact

DAILY READINESS: 🟢 GREEN — NORMAL DAY
Position sizing: 1% cap available
Setup evaluation: proceed to Setup Rules
```

---

## The override rule — deliberately one-directional

- **You CANNOT override a RED verdict to permit trading.** If today is red, today is red. No "just one small trade" exception.
- **You CAN choose not to trade on a green day.** Green is a permission, not a requirement.
- **You CAN downgrade a green to yellow** (e.g., you feel off despite the data — trust yourself). But you cannot upgrade yellow/red to green.

**Enforcement in Phase 1** (manual): honor the verdict as an act of discipline. Log every green day where you chose not to trade — that data is valuable.
**Enforcement in Phase 2** (platform): red verdict disables the trading UI entirely. Yellow verdict applies the size caps automatically.

---

## What happens on a red day (this is important)

Being told "no trading today" is not a punishment. Here's what to do instead:

1. **Log the readiness output** in the trading journal (short entry — "red day, reason: [X]").
2. **Do the meta-work** that would benefit your trading anyway:
   - Read a book chapter
   - Backtest a hypothesis on paper
   - Review last week's trades
   - Watch a Subasish Pani / Theta Gainer video with a specific question in mind
   - Write in your journal about what triggered the red
3. **Address the upstream cause.** If sleep is the issue, prioritize sleep. If alcohol, fix the pattern. If mood, journal or move.
4. **Come back tomorrow, honestly re-check.**

**A red day used well is more valuable than a green day traded poorly.**

---

## Rule status summary

| Rule | Status | Refinable by paper trading? |
|:---|:---:|:---:|
| Read daily log before any setup eval | 🔒 Fixed | No |
| Sleep < 5h → no trade | 🔒 Fixed | No — safety floor |
| Sleep 5-6h → size 75% | 🟡 Tentative | Threshold refined |
| **Any alcohol → 90-day lockout + re-entry ramp** | 🔒 Fixed | No — hardened 2026-09-03 |
| Anger/grief journal → no trade | 🔒 Fixed principle | Detection refined |
| No workout 7+ days → no trade | 🟡 Tentative | Threshold refined |
| Streak reset in 24h → no trade | 🔒 Fixed | No |
| RED cannot be overridden | 🔒 Fixed | No |

---

## Why this file exists

Because your own history *proved* it matters. FY 2025-26 wasn't a strategy failure — the setups you took were mostly technically valid. It was an **operational failure**: night shift + alcohol + inconsistent hours + poor sleep → indiscipline → 246 scalping contracts → ₹92k in charges → −₹86k net.

If the readiness rules above had been running (and honored) through FY 2025-26, most of those 246 contracts would not have been taken. That's the whole point.

---
[[Method Overview|⬅️ Back to Method Overview]]
