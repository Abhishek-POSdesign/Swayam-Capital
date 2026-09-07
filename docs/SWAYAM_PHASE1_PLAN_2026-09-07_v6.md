# SWAYAM CAPITAL — PHASE 1 IMPLEMENTATION PLAN (v6, FOR EXECUTION)

> **Written 2026-09-07, 21:30 IST by Claude Code (Opus 5).** Supersedes v5 of the same date. v6 exists because Codex reviewed v5 and found fourteen loopholes. Twelve were real. One was wrong and is refuted below with evidence. One is partly right and is scoped down. v5's own overstatement is corrected in Section 0.
>
> **Status: PROPOSED, awaiting Abhishek's approval. No application code written.**
>
> **Written to be executed cold by another agent and to be attacked by Codex and Hermes.** Every current-state claim carries the command or query that proved it, run on 2026-09-07.

---

## 0. CORRECTIONS TO v5 (own them before anything else)

**0.1 v5 overstated the lot-size impact. Codex is right.**

v5 said every rupee figure the platform ever displayed was wrong. That is not accurate. The lot-size error corrupts every figure that is **scaled by number of contracts**: total premium, net debit and credit, payoff curves, max profit, max loss, the stressed 2-sigma loss, position P&L, margin and charges. It does **not** corrupt per-unit market quotes: NIFTY spot, option last-traded price, bid, ask, strike, implied volatility and open interest were and are correct. The corrected statement is: **every contract-scaled rupee figure is 15.4% too large; per-unit quotes are unaffected.**

**0.2 The invented margin error is separate from the lot-size error.** The Rs 32,000 and Rs 1,15,000 constants were never contract-scaled; they were made up. Their error is not 15.4%, it is arbitrary and much larger. Do not merge the two findings.

**0.3 A target-date payoff figure is a model output, never "real".** Any what-if number must display its assumptions: target timestamp, price source, IV source and shift, and valuation rule. It must never sit next to broker P&L without that label.

---

## 1. CODEX REVIEW ADJUDICATION

Fourteen loopholes, judged by the lead developer, with evidence.

| # | Codex item | Verdict | Action |
|---|---|---|---|
| L1 | Risk release depends on history that Release 5 fixes | **REAL MISS** | Data health moves before the risk work. New Release 1B. |
| L2 | No authoritative "intended holding days" input | **REAL MISS** | Add a planned-exit date to the request, UI, journal and database. Blocks if absent or past expiry. |
| L3 | 2-sigma scenario under-specified (time, IV, direction, bid/ask) | **REAL MISS, the most serious** | One versioned, published risk scenario. See Section 3. |
| L4 | 20 sessions weak without stability rules | **PART REAL** | Accept the data-age, completeness, gap and outlier checks and the block-never-substitute rule. Reject the implied window change: 20-session realized volatility is Abhishek's chosen Method parameter and a standard one. Changing it is a Method decision, not a Phase 1 defect. |
| L5 | Broker balance is not automatically risk capital | **REAL MISS** | Define the denominator precisely, snapshot once per session, show broker funds and approved risk capital separately. Abhishek's collateral answer of 2026-09-07 is folded in at Section 4. |
| L6 | Hedge geometry stated as a phrase, not a rule | **REAL MISS on geometry, REJECTED on hiding calendars** | Implement exact geometry. Do **not** hide calendar and diagonal structures: ten of Abhishek's twenty-one recorded historical swing trades are calendar spreads. Fix multi-expiry valuation instead. See Section 5. |
| L7 | Kill switch contradicts itself | **REAL MISS, mine** | Halt blocks risk-increasing actions only. Close, reduce, journal, notebook and audit stay permitted. |
| L8 | Editable limit prices conflict with the fill policy | **REAL MISS** | Two labelled modes. Limit simulation is the default because Abhishek's Method says limit orders 99% of the time. |
| L9 | Charge model incomplete | **REAL MISS** | Add clearing charges, IPFT, exercise and expiry handling, and version every rate by effective date. One qualifier: Codex asks for reconciliation against a live contract note, which paper trading cannot produce. Reconcile against the FYERS brokerage calculator and, if he still holds them, his 2022-23 contract notes. |
| L10 | IAP enablement can lock the owner out | **REAL MISS** | Full runbook with pre-change export, exact bindings, owner verification, rollback and a post-change deploy test. |
| L11 | Migrations are not a deployment mechanism | **REAL MISS, and worse than stated** | Verified: `scripts/apply_migration.py` reads the file, prints a line count and tells you to paste it into the Supabase editor. It executes no SQL. There is no `swayam_schema_migrations` table; three candidate names return HTTP 404. The folder holds 001, 002, 004, 005, 006, 007, 013, 014, 015, 016, with 003 and 008 to 012 missing. **Nobody can currently state which migrations are applied to the live database.** Build a real runner and a version table before adding any table. |
| L12 | Backup identity model wrong | **REAL MISS** | Map every workload identity first, grant each the minimum, version objects, checksum, prove restore. |
| L13 | Release 4 creates rate-limit and honesty failures | **PART REAL, one claim refuted** | Accept debouncing, throttled and manual margin refresh, cached last-verified margin with timestamp. **Refuted:** Codex says open-interest change is not available from one chain snapshot. It is. The FYERS option chain returns `oi`, `oich`, `oichp` and `prev_oi` in the same response, verified 2026-09-07. The Sensibull OI-change view is therefore buildable from one call. |
| L14 | No staging or isolated test data | **REAL MISS** | A second free Supabase project with sanitised seed data, plus a test configuration that cannot reach the live project. Scoped to that, not a parallel cloud stack. |

**Smaller gaps: all accepted.** Legacy position quarantine; margin-endpoint schema validation, timeout, no broad retries, cache keyed on the full leg set; an explicit statement that the recorder cannot recreate lost history; monitoring beyond uptime covering feed age, token validity, recorder arrival, backup age and alert-delivery health; a data-quality response contract rather than UI wording alone; app-side authorization using verified identity rather than a browser-supplied email.

**One smaller gap promoted to release-blocking:** Codex lists the AI summary as untrusted content near the end. It belongs higher. The "So Far Today" summary is produced by a grounded web search, so injecting it into the AI's prompt turns arbitrary web text into instruction text inside a system that discusses trades. It must be wrapped as quoted data with its source links, never as instructions, and must be unable to alter a rule or a verdict.

---

## 2. UI STANDARD — a hard rule, not an aspiration (Abhishek, stated repeatedly)

The reference is the FYERS and Sensibull interface. Clean, calm, generously spaced, and **every number he must act on is large enough to read without leaning in**. This is now a review gate: a pull request that breaches it is rejected regardless of correctness.

| Element | Minimum size | Notes |
|---|---|---|
| Hero metrics: Max Profit, Max Loss, spot, capital, net P&L | 28 px, tabular figures | The largest things on the screen |
| Secondary metrics: breakeven, reward-to-risk, probability of profit, time value, intrinsic value, margin | 18 px | Never smaller |
| Leg row values: strike, lots, price, bid, ask, IV, delta | 16 px | These are edited, so they must be comfortable |
| Table and card labels | 14 px | Never below |
| Chart axis ticks | 13 px | |
| Chart data labels, standard-deviation markers, projected P&L tag | 12 px minimum, 14 px preferred | |
| Any number Abhishek acts on | **never below 14 px** | Hard floor |

Also fixed: tabular figures so digits align in columns; a minimum 4.5-to-1 contrast on every number; generous row height rather than dense packing; no purple anywhere, per the standing rule.

---

## 3. THE RISK SCENARIO, FULLY SPECIFIED (answers L3)

Version this as `risk_scenario_v1` and display the assumptions beside every verdict.

| Element | Rule |
|---|---|
| Capital denominator | Approved risk capital, snapshotted once per session. Section 4. |
| Primary cap | 1% of that capital. Rs 8,710 at today's Rs 8,71,002.38. |
| Black-swan fuse | 5% of that capital on absolute max loss. Rs 43,550 today. Hard block. |
| Move size | 2 standard deviations of close-to-close NIFTY returns over 20 sessions, scaled by the square root of the planned holding days. Close-to-close already contains the overnight gap. Today 1 SD is 82 points and 2 SD is 164. |
| Direction | Both directions are evaluated. The gate uses the worse of the two. |
| Target timestamp | The planned exit date at 15:30 IST, from the new planned-exit field (L2). |
| Time decay | Included. The position is revalued at the target timestamp, not at today's time to expiry. |
| IV assumption | Each leg's IV solved from its real market price at entry, held flat by default. A stress shift is displayed as a separate scenario and does not gate. Flat is stated on screen, never hidden. |
| Valuation | Long legs valued at the bid and short legs at the ask, so the exit is priced conservatively. |
| Risk-free rate | From configuration, displayed. |
| Data preconditions | 20 complete sessions, newest not older than one trading day, no gaps, no outlier beyond a stated threshold. Any failure **blocks**. No substitute volatility, ever. |
| Forbidden | Any default IV, any zero premium, any assumed lot size, any stale capital figure entering this path. |

---

## 4. RISK CAPITAL, DEFINED (answers L5, and folds in Abhishek's 2026-09-07 collateral answer)

**What his account actually holds, from his FYERS collateral report of 2026-09-07 20:00:**

| Line | Amount | Share |
|---|---|---|
| Total collateral | Rs 8,71,002.38 | 100% |
| Cash-equivalent, being LIQUIDBEES and SGBJUN30GB | Rs 1,77,480.46 | 20.4% |
| Non-cash equity and ETF | Rs 6,93,521.93 | 79.6% |
| Utilisation | Rs 0 | |

Cross-checked against the API on the same date: `holdings()` returns fifteen holdings with a total current value of Rs 10,34,927.31 against Rs 8,71,002.38 of collateral, which is the broker haircut Codex correctly flagged. `funds()` returns Total Balance, Collaterals and Available Balance all equal to Rs 8,71,002.38 and exposes **no cash-versus-non-cash split**. That split must therefore be derived by classifying each pledged instrument, or entered by Abhishek and stored.

**His stated plan, recorded:** before real money he will deposit a planned annual risk amount of Rs 1 to 2 lakh as cash, once, with no further deposits, bringing cash-equivalent collateral to roughly Rs 3.5 to 4 lakh.

**The rule this must respect, stated plainly for the real-money gate:** the exchange cash requirement applies to **margin used**, not to total collateral. At least half of the margin blocked for an F&O position must be cash or cash-equivalent. So today's Rs 1,77,480 of cash-equivalent supports roughly **Rs 3.55 lakh of total margin**, not Rs 8.71 lakh. After his planned deposit, roughly Rs 7 to 8 lakh of margin becomes supportable. **This constrains nothing in paper trading and is recorded here for the real-money gate only.**

**Denominator rules:**

1. Named source: `funds()` field id 10, Available Balance, falling back to id 1, Total Balance, both stated on screen with the source timestamp.
2. Snapshotted once at the start of a trading session. A mid-session balance change must never retroactively alter the allowed risk of an open trade.
3. Raw broker funds and approved risk capital are shown separately and are never conflated.
4. Utilised margin and existing open-position exposure are subtracted before the cap is applied.
5. Unavailable means blocked. Never a stale figure, never a default.
6. The cash-equivalent share is displayed alongside, for his awareness, marked as not gating during the paper phase.

---

## 5. CALENDAR SPREADS — why Codex's advice is rejected here

Codex recommends hiding calendar and diagonal structures until multi-expiry valuation is correct. That is the wrong call for this user.

Evidence from his own vault, `02 - Projects/Trading/00 - Reference/Historical Swing Trades/`: of twenty-one recorded historical swing trades, **ten are calendar spreads** — trades 01, 03, 04, 05, 07, 09, 10, 11, 17 and 18. Calendar structures are close to half of his recorded trading history. Removing them from the builder would remove his most-used structure to avoid fixing a maths problem.

**Decision:** implement multi-expiry valuation properly in Release 4. Until it lands, calendar and diagonal payoffs stay visible but are labelled approximate, and **execution of a multi-expiry structure is blocked** rather than the structure being hidden. That satisfies the honesty requirement without taking his primary strategy away from him.

---

## 6. RESTRUCTURED RELEASE ORDER

Codex's proposed order is adopted with one change: the UI standard applies from the first release, not the fourth.

### Release 1A — foundation, access and truth

Migration runner that actually executes SQL, plus a `swayam_schema_migrations` version table and a reconciliation of which of the ten files on disk are truly applied to the live database. Google sign-in with the full lockout-proof runbook. CORS narrowed. Real lot size read from the contract master, with a missing value blocking the trade. Legacy positions written at lot 75 quarantined and excluded from analytics, never silently rewritten. Kill switch scoped to risk-increasing actions only. Every remaining fabricated value removed. Fail-closed on every trade dependency. Readiness demoted to a ceremonial journal with no power over trading. Test hygiene, including making browser console errors fail the suite. Staging Supabase project created and the test configuration pointed away from live.

### Release 1B — the data the risk rule depends on

Recorder permission repair with a real file proved in the bucket. Nightly ingest restored and the age of the history displayed. Data-quality contract with value, source, source timestamp, received timestamp, session state, quality and unavailable reason. Stale-data guard on both pages. Backups with per-identity permissions, versioned and checksummed objects, a restore that restores, and one recorded drill. Monitoring on feed age, token validity, recorder arrival, backup age and alert delivery. An explicit written statement that historical option snapshots before this date cannot be recovered.

### Release 2 — the risk policy, only after 1B passes

Risk capital as defined in Section 4. The versioned risk scenario from Section 3. Planned-exit-date field end to end. Exact hedge geometry. Real broker margin, cached, throttled and schema-validated. The percentage display bug fixed. Method files updated in both the vault and the baked copy, on Abhishek's written instruction.

### Release 3 — paper orders that cost what real orders cost

Versioned charge schedule including clearing charges, IPFT, exercise and expiry handling. Decimal arithmetic server-side with the frontend displaying only. Limit simulation as the default fill mode with market simulation available and labelled. Full quote snapshot, spread and timestamps stored on every fill. The same rules applied at exit.

### Release 4 — the Strategy Builder, to the Sensibull standard

The what-if engine with debounced recalculation. Correct multi-expiry valuation so calendars work. The metrics strip, the payoff chart with open-interest bars and OI change from `oich` and `prev_oi`, the standard-deviation table, the greeks toggles, the leg row with Shift, Width and Multiplier, the ready-made strategy grid, the thirty-second price refresh, and execution on the same page. Built to the UI standard in Section 2.

---

## 7. EVIDENCE REQUIRED FOR EVERY RELEASE

1. Files changed and migrations listed, with proof the migration actually executed against the database.
2. Test results with exact counts and no ignored browser console errors.
3. Desktop and mobile screenshots of both pages, checked against the Section 2 UI standard.
4. Live market-hours proof for anything touching data, or an explicitly labelled off-hours limitation.
5. A before-and-after table for every displayed number that changed.
6. Rollback instructions and the deployed commit id.
7. This document and the running-state document updated.

---

*Nothing here is a claim of readiness. Real-money trading remains code-blocked. Written 2026-09-07 by Claude Code (Opus 5) for Abhishek's approval and for independent cross-check by Codex and Hermes.*
