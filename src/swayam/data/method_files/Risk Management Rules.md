# 🛡️ Risk Management Rules

**Purpose:** The arithmetic that keeps you in the game. Every rule below is either **fixed** (won't change after paper trading) or **tentative** (gets refined once you have real data). Both are labelled explicitly.

*Part of [[Method Overview]]. Grounded in the evidence in [[00 - Reference/Historical Trade Journal/Historical Trade Journal Overview|Historical Trade Journal]] and [[00 - Reference/Historical Swing Trades/_Swing Trades Overview|Historical Swing Trades]].*

---

## The single rule that governs everything below

> **Position size derives from the risk cap, not from the chart.**
>
> You decide first what you're willing to lose on this trade (in ₹ and %). Then you place the stop where the setup would be invalidated. Then position size is what remains: the number of lots/contracts such that `(entry price − stop price) × size × lot size = your rupee risk cap`. Never the other way around.

Everything else is enforcement of this one rule.

---

## 1. Per-trade risk cap — FIXED

- **1% of margin base per trade. Hard CEILING.**
- Margin base = cash margin + pledged-share margin combined (~₹8–9 lakh as of 2026-09-03).
- **Rupee cap: roughly ₹8,000–₹9,000 per trade.**
- **You may cut a loss EARLIER** (e.g., exit at 0.5% loss if the setup invalidates fast). Below-ceiling exits are always fine.
- **You may NOT exceed the ceiling.** Not "1% for normal, 2% for A+ setups." **1% max. Every trade. Every time.**
- If the setup feels so good that 2% is warranted, that is a *feeling*, not a rule.

**The framing that governs this and all Phase 1 risk rules — added 2026-09-03:**

> **Downside is CAPPED. Upside is OPEN.**
>
> Loss ceilings are fixed (1% per trade, 2% per day, 4% per week). You can always exit earlier if the setup breaks.
> Profit targets are minimums (1:2 R:R min, aiming 1:2.5). You can always wait for more if the market cooperates.
> **Every rule below applies this asymmetry.**

**Why fixed:** This is not a strategy variable. It's a survivability floor. At 1% per trade you can absorb 100 losing trades before ruin. Anything above 2% starts compressing the survival window fast.

## 2. R:R minimum — TENTATIVE (refined by paper-trade data)

- **Phase 1 minimum: 1:2 R:R** (mathematical breakeven at 33.3% win rate).
- **Phase 1 target: 1:2.5 R:R** (chosen to stay net-positive AFTER round-trip charges even at breakeven win rate).
- **Upside acceptable: 1:3 to 1:5.**
- **Below 1:2 → no trade.** No exceptions.

**Why tentative:** you'll explore 1:1, 2:1, 3:1 ratios during paper trading (Oct 2026 → Diwali) to see which frequency-vs-yield mix actually works for *you*. Final rule gets locked from your own data, not from theoretical math.

**The math your own history requires** *(from [[Personal Trading Brief]]):*

- Historical intraday win rate: **30–32%**.
- At 1:2 R:R, breakeven win rate = **33.3%** → you're at or slightly below breakeven.
- At 1:3 R:R, breakeven win rate = **25%** → comfortable profit at 30%.
- Every 100 trades at 30% win rate + 1:3 R:R → net **+20% of risk-per-trade** (roughly ₹1,700 × 100 = +₹1.7L per 100 trades, at 1% risk).

## 3. Transaction-cost floor — FIXED (new, from FY25-26 evidence)

**The rule:** Expected gross P&L on this trade must exceed **~2× expected round-trip charges** before the trade is worth taking.

**Why fixed:** FY 2025–26 evidence, verified against raw FYERS CSV — you generated a **gross +₹6,109 that was fully consumed by ₹92,408 in charges, ending in NET −₹86,299.** Activity level ate the edge. Cost-blindness is what killed the year, not strategy.

**Rough per-trade charge estimates (verify with FYERS actuals during paper trading):**

- Single-leg NIFTY option round-trip: ~₹100–200 (brokerage + STT + exchange + GST)
- 2-leg spread round-trip: ~₹200–400
- 4-leg iron-condor-style round-trip: ~₹400–800
- Adds another ~₹50–100 if you hedge with a far-OTM leg

**What this eliminates:**

- Any scalp expecting <₹1,000 gross gain on a single leg
- Any tight-range spread expecting <₹1,500 gross gain on a 2-leg
- Any small-lot iron condor expecting <₹2,500 gross gain
- Rapid re-entries after a stop-out ("revenge scalps") — costs compound

**What it protects:**

- Multi-leg swing spreads held 2–14 days where premium moves are meaningful (this is your historical edge — see [[00 - Reference/Historical Swing Trades/_Swing Trades Overview]])
- Directional plays on strong regime signals

## 4. Order type — FIXED

- **99% limit orders.** Every entry, every exit for a directional trade.
- **Market orders permitted ONLY for cheap hedges** (₹5–₹10 premium options) where NIFTY's high liquidity makes slippage negligible.
- **Never** market-order into or out of a real directional position.

**Why fixed:** slippage compounds silently. On a 1% risk cap, even ₹200 of slippage per side eats into R:R meaningfully. Limit orders are free of this problem; market orders aren't.

## 5. Stop-loss discipline — FIXED (Trade-07 lesson)

**Rule:** the stop-loss is a **contractual line**, not a suggestion.

- Stop level is decided **at entry**, based on setup invalidation and worked backward to satisfy the 1% risk cap.
- Stop is **entered as a live order** at entry, or coded into the platform's rule engine — not held in your head.
- **If the stop is breached, you're out.** No "let me see if it comes back." No "widening the stop." No "closing half and holding half through it."

**The evidence — Trade-07 (Dec 27 2022, Balanced Calendar Spread):**

- Planned stop: **−₹7,000**
- Actual loss when finally exited: **−₹21,000 (3× the planned stop)**
- Impact: this single trade **dragged the entire Balanced Calendar Spread strategy (5 total trades, 4 winners) from a would-be +₹15,595 to −₹5,405 net.**

**One violated stop erased four disciplined trades.** This is the pattern. It's not new — it's what your own 2022 trade journal already proved. See [[00 - Reference/Historical Swing Trades/Trade-06 - 2022-12-15 - Bear Condor]] — Abhishek's own comment in that same era: *"Don't trade intraday and swing in same account."* You already know this from experience.

**Enforcement in Phase 1** (manual): stop entered as live order at trade entry, no discretionary override permitted.
**Enforcement in Phase 2** (platform): rule engine refuses stop-widening after entry. Locked.

## 6. Single-trade blast-radius rule — FIXED

- **Any single trade whose realized loss exceeds 3% of margin base = system failure.**
- 3% of ₹8.5L = **~₹25,500 max any single trade can lose, even if the standard rules break.**
- Above that → **mandatory pause** (no trading for the next 3 trading days) and full process audit before restart. Root-cause the rule-breaking, not the trade.

**Why:** the 1% rule assumes stops are honored. This rule is the hard fuse behind it. If a stop gets missed and the loss balloons past 3%, that's not just a bad trade — it's a signal the system failed and needs fixing before the next trade.

## 7. Daily loss cap — TENTATIVE

- **Daily loss cap: 2% of margin base (~₹17,000).**
- If hit, **stop trading for the day.** No revenge scalps. Log the day-close honestly.
- Applies whether it's one trade or three that combined to reach the cap.

**Why tentative:** the exact percentage should be refined by paper-trade data — you may find 1.5% is a better fit for your temperament, or 2.5% is fine because your setups take longer. Data over 3–4 months tells us.

## 8. Weekly loss cap — TENTATIVE

- **Weekly loss cap: 4% of margin base (~₹34,000).**
- If hit, **stop trading for the rest of the week.** Resume Monday.
- Also triggers a mandatory weekend review of what went wrong before restart.

**Why tentative:** same reason — refined by paper-trade data.

## 9. Position-sizing worked example

Assumptions: margin base ₹8.5L → 1% = ₹8,500 max risk. NIFTY lot size = 75.

**Example 1 — Single-leg long put (directional bearish):**
- Buy NIFTY 24500 PE at ₹150
- Setup invalidates above 24700 spot → PE would drop to ~₹110 (worst-case exit)
- Risk per lot = (150 − 110) × 75 = ₹3,000
- Max lots = ₹8,500 / ₹3,000 = **2 lots** (round down; never round up)
- Position: 2 lots × ₹150 × 75 = ₹22,500 premium paid
- **Risk: ₹6,000** (within cap)
- Target for 1:3 R:R: PE hits ~₹270 (₹120 gain × 75 × 2 = ₹18,000 gross gain)

**Example 2 — 4-leg Iron Condor (theta play):**
- Sell 25000 CE, Buy 25200 CE, Sell 24500 PE, Buy 24300 PE (200-point wings each side)
- Net credit received (say): ₹40 × 75 = ₹3,000 per lot
- Max loss = (200-point wing − ₹40 net credit) × 75 = ₹12,000 per lot **at expiry, no adjustment**
- **1 lot risk = ₹12,000 exceeds ₹8,500 cap.** ❌ **Cannot take this size at ₹8,500 cap.**
- **Options:**
  - Narrow wings to 100 points → max loss = ₹4,500/lot → 1 lot risk within cap (single lot)
  - Or use tighter strike selection to increase net credit
  - Or don't take this trade — its risk profile doesn't fit the cap

**Example 3 — Bear Put Spread (your historical best strategy):**
- Buy 24500 PE at ₹150, Sell 24000 PE at ₹60 → Net debit ₹90
- Risk per lot = ₹90 × 75 = ₹6,750 (max loss = full net debit, if both expire OOTM to the long)
- Max lots = ₹8,500 / ₹6,750 = **1 lot**
- Target: full width capture minus debit = (500 − 90) × 75 = ₹30,750 gross per lot
- **R:R = 30,750 / 6,750 = ~4.55:1** ✓ Well above 1:2.5 minimum

## 10. Trade-structure gates — FIXED (added 2026-09-03)

Two hard constraints on WHAT you can trade in Phase 1, not just HOW MUCH:

- **One new-trade entry per trading day, maximum.** Positional/swing pace means one deliberate entry per day is plenty. Multiple new entries in a day = intraday behavior in disguise = exactly the pattern that ate FY25-26.
  - "New entry" means opening a fresh position. Managing (adjusting stops, taking profits on) existing open positions doesn't count against the daily limit.
  - If you already opened one today and see a better setup an hour later — **skip it.** Log it as "second setup considered, skipped per daily-cap rule." That log becomes evidence for whether the rule should be relaxed later.
- **No single-leg trades.** Every position is a spread or a hedged structure — Bear Put Spread, Bull Call Spread, Iron Condor, Calendar Spread, or a directional long option with a far-OTM protective leg. **Never a bare long call or bare long put.**
  - Reason 1: matches your historical edge — the profitable 2022-23 swing period was 100% multi-leg structures (see [[00 - Reference/Historical Swing Trades/_Swing Trades Overview|Swing Trades Overview]]).
  - Reason 2: defined risk. A spread has a mathematically-fixed max loss regardless of what price does. Single legs can suffer unexpected volatility crush (see [[Setup Rules]] event regime).
  - Reason 3: it's how you already think about setups when you're at your best — hedges + directional bias, not naked bets.

### 10a. Overnight-hedge sizing rule — FIXED (added 2026-09-03 late night)

Because positional/swing trades are held overnight (and sometimes over weekends), the hedge structure must be sized so that **a gap-open against the position on the NEXT trading day cannot lose more than 2% of margin base (~₹17,000).**

This is a **specific, additional constraint** on top of the 1% per-trade cap:

- **1% cap = today's max realized loss if the stop is hit during the session.**
- **2% overnight cap = maximum loss possible from an adverse gap open the next morning, assuming no in-session management is possible before the gap plays out.**

**In Abhishek's own words (2026-09-03):** *"If anything happens in the market, I will not lose more than 2% tomorrow. That will be two days, so we plan accordingly so that our loss is always capped with hedging. We will have hedging provide more margin as well."*

**How this constrains structure selection:**

- **Naked long puts / long calls held overnight → ❌** — no floor to overnight losses beyond premium paid, and volatility crush after events can wipe out even in-the-money positions.
- **Defined-risk spreads (Bear Put Spread, Iron Condor, Bull Call Spread) → ✅** — max loss is mathematically fixed at entry, regardless of overnight gap direction or magnitude.
- **Directional long option + far-OTM protective leg → ✅ if the protective leg genuinely caps the tail.** For example: long 24500 PE + short 24000 PE (Bear Put Spread) caps overnight loss at (500 − net debit) per lot. A protective wing that's too far OTM to activate under a realistic gap is theoretical protection only.
- **Calendar spreads → ✅ but with vol-crush awareness.** IV skew between front and back month can shift overnight; size accordingly.

**Bonus effect:** hedging with defined-risk spreads also **reduces margin required** vs naked positions (broker margin rules for spreads are ~50-70% of the equivalent naked position). More margin available for the next opportunity, without increasing tail risk.

**Rule enforcement:** the platform's setup validator checks max-possible-loss-per-lot for the structure and rejects submissions where max loss > 2% of margin base. See [[../06 - Platform Plan/Platform Overview|Platform Overview]] Setup Queue component.

## Two-tier risk model — realistic vs absolute (added 2026-09-07)

Every trade is validated against TWO risk caps, both must pass.

### 1. Realistic Risk Cap — 1.0% of margin base
The primary decision variable. Compares to how much the spread would lose if NIFTY moves **2× its usual daily move** (specifically: 2σ of the last 20 trading days' realized volatility). That is a bad day, not the apocalypse.

- If this cap fails → the trade is too big for a normal bad day, don't take it.
- If this cap passes → the trade is sized correctly for realistic day-to-day risk.

### 2. Blast Radius Fuse — 3.0% of margin base
The last-resort ceiling. Compares to the absolute mathematical worst case — spot going to zero for a bearish spread, or to infinity for a bullish one. This is a black swan event (2008, COVID-March-2020 scale).

- If this cap fails → even the apocalypse would take out more than 3% of the account. Don't take the trade regardless of realistic risk.
- If this cap passes → survival is assured even in the worst case.

### Why two caps
The mathematical max loss on a Bear Put Spread with tight strikes can be ₹15,000+ per lot — that's the "spot goes to zero" number. But NIFTY realistically moves 0.7–1.5% in a day; 2σ is ~2–3%. The realistic worst-case loss on that same spread might be ₹4,000. If we only validated against max loss, we'd never take any spread. If we only validated against realistic loss, we'd have no safety against black swans. Both together = correct.

### Parameters
- `realistic_risk_cap_pct: 1.0` — the realistic cap as a percentage of margin base
- `blast_radius_pct: 3.0` — the absolute cap as a percentage of margin base
- `realistic_stress_sigma: 2.0` — how many standard deviations the stress test uses
- `realized_vol_window_days: 20` — trailing window for volatility computation

## 11. What refuses to be a rule (yet)

- **Add-to-winners** — Hougaard's principle, philosophically agreed but you've never trained your mind to execute it. Parked as **aspirational for Phase 2** ([[00 - Reference/Influences/Tom Hougaard - Best Loser Wins|see Hougaard note]]).
- **Averaging into positions** — deliberately NO. You have zero tolerance for adding to losers.
- **Scaling out of winners** (partial profits) — plausible but too many parameters to pin without data. Revisit after paper trading.
- **Correlation-based hedging** (BankNifty vs Nifty spreads) — you deprioritized correlation regime. Not a Phase 1 rule.

## Rule status summary

| Rule | Status | Refinable by paper trading? |
|:---|:---:|:---:|
| 1% risk cap | 🔒 Fixed | No |
| No trade below 1:2 R:R | 🔒 Fixed floor | Above the floor: yes |
| 1:2.5 target for charge coverage | 🟡 Tentative | Yes |
| Transaction-cost floor | 🔒 Fixed principle | Rupee thresholds refined |
| Limit orders 99% | 🔒 Fixed | No |
| Stop honored, no widening | 🔒 Fixed | No |
| 3% single-trade blast fuse | 🔒 Fixed | No |
| Daily loss cap 2% | 🟡 Tentative | Yes |
| Weekly loss cap 4% | 🟡 Tentative | Yes |

---
[[Method Overview|⬅️ Back to Method Overview]]
