# SWAYAM CAPITAL — PHASE 1 IMPLEMENTATION PLAN (v7, APPROVED SHAPE)

> **Written 2026-09-07, 22:30 IST by Claude Code (Opus 5).** v7 = v6 plus the adjudicated amendments from Hermes's gatekeeper audit of v6. **Read v6 for the full body**; this document carries the amendments, the corrected release order, and the market-test plan. v6 and v7 together are the complete plan.
>
> **Status: PROPOSED. No application code written.**
>
> Review chain to date: v4 (Claude) → Codex path assessment → v5 (Claude) → Codex loophole review, 14 items → v6 (Claude, 12 accepted, 1 refuted, 2 scoped) → Hermes gatekeeper audit, 5 items → **v7 (this document, 3 accepted, 1 accepted and promoted, 1 split)**.

---

## 1. ADJUDICATION OF HERMES'S FIVE LOOPHOLES

| # | Item | Verdict | Where it lands |
|---|---|---|---|
| A | Paper must enforce the broker's cash-equivalent margin rule | **ACCEPTED IN FULL. My error.** | Release 2 |
| B | Baseline the live schema before building a migration runner | **ACCEPTED IN FULL** | New Release 0 |
| C | Idempotency on execution | **ACCEPTED AND PROMOTED. This is a live bug today.** | Release 1A |
| D | Two-tier kill switch with automatic flatten | **SPLIT. Tier 1 accepted now. Automatic liquidation refused for Phase 1, with reasons.** | Release 1A, and the real-money gate |
| E | Fallback source for the volatility data | **SPLIT. Third-party source refused. Bounded previous-session cache accepted. The durable fix already exists in the plan.** | Release 1B and Release 2 |

---

### A — Paper must enforce the cash-equivalent margin rule. Accepted, and it was my mistake.

v6 said the exchange cash rule "constrains nothing in paper trading and is recorded for the real-money gate only." That directly contradicts Abhishek's own decision D8, that a paper trade must mimic a real trade exactly. Hermes is right: if the paper engine lets him deploy Rs 8.71 lakh of margin when the broker would only permit roughly Rs 3.55 lakh, then every paper result is built on capital he does not actually have access to, and the strategies he learns to trust would be rejected on day one of real money.

**Amendment.** The paper engine enforces the same constraint the broker would:

- Usable margin ceiling = **2 × cash-equivalent collateral**, because at least half of blocked margin must be cash or cash-equivalent.
- Today: cash-equivalent Rs 1,77,480.46 gives a ceiling of about **Rs 3,54,960**, against total collateral of Rs 8,71,002.38.
- A paper execution whose required margin exceeds that ceiling is **rejected with the same wording the broker would use**, not silently allowed.
- Both numbers are shown on screen at all times: total collateral, and the margin ceiling the cash component actually supports.
- The cash-equivalent figure has no dedicated field in the FYERS funds response, verified 2026-09-07. It is derived by classifying each pledged instrument from `holdings()` as cash-equivalent or non-cash, with the classification list stored in configuration and shown to Abhishek. If an instrument cannot be classified, it counts as **non-cash**, the conservative direction.
- When he makes his planned one-time cash deposit, the ceiling rises automatically because it is derived, not typed in.

---

### B — Release 0, baseline the live schema. Accepted in full.

Pointing a newly written migration runner at a database whose true state nobody knows is how ledger data gets destroyed. Verified on 2026-09-07: no `swayam_schema_migrations` table exists, three candidate names return HTTP 404, and the migrations folder holds 001, 002, 004, 005, 006, 007, 013, 014, 015 and 016, with 003 and 008 to 012 absent.

**Amendment. A new Release 0 that changes nothing and only establishes truth:**

1. Export the live schema of all 19 `swayam_*` tables: columns, types, defaults, constraints, indexes.
2. Diff it against every migration file on disk. Record which files are applied, which are partly applied, which were never applied, and which live objects exist that no file explains.
3. Write the result as `migrations/000_baseline.sql`, the authoritative statement of what the database is today.
4. Take a full backup, verified by row count, **before** anything else in Phase 1 runs.
5. Only then build the runner and the version table, with the version table seeded to the baseline.

**Exit gate:** a table of all 19 tables with their column counts and row counts, and a written list of every discrepancy found between disk and database. No schema change is permitted in Release 0.

---

### C — Idempotency. Accepted, promoted, and it is a live bug right now.

Verified in the code on 2026-09-07: the execution route carries no idempotency key, no request id and no duplicate check, and the execute control has no in-flight guard and does not disable itself on submit. A double-click, a slow response, or an impatient second press **creates the position twice**. On a four-leg structure that is eight legs, double the intended risk, and it would sail past the 5% black-swan fuse because each request passes validation on its own.

This is not a future risk. It can happen during tomorrow's market test.

**Amendment, moved into Release 1A:**

- The frontend generates a UUID per execution attempt and sends it with the payload.
- The execution table gains a unique constraint on that key. A repeat within 60 seconds returns the original result instead of creating a second position.
- The execute control disables itself on submit and shows a submitting state until the server answers.
- A test proves that two identical submissions produce exactly one position.

---

### D — Kill switch. Tier 1 now. Automatic liquidation refused for Phase 1.

**Accepted:** Tier 1, the soft halt, blocking every risk-increasing action at the backend, while close, reduce, journal, notebook and audit stay permitted.

**Accepted as a middle path:** a **one-click Close All** for paper positions. It prepares every closing leg, shows the prices and the charges, and executes on one confirmation. Abhishek gets the speed without the system acting alone.

**Refused for Phase 1: automatic liquidation at market.** The reasons, stated plainly so this is not revisited casually:

1. **There is nothing to liquidate.** Real-money execution returns HTTP 403 by design. There are no live orders to cancel and no real positions to close. An automatic flatten in paper mode would only stamp a closing price on simulated rows. It protects no money.
2. **Building it requires giving the platform order-placement power.** An unattended path that fires market orders is the single most dangerous component in any trading system. Building it now, before order-state handling, fill reconciliation, rate limiting and reconciliation against the broker exist, and while the codebase still contains fabricated values, would manufacture the exact catastrophe this whole audit chain has been trying to prevent. A bug in that path liquidates a healthy book during a panic.
3. **It contradicts Abhishek's own standing rule.** His Method and his AI plan both state that the system never acts on its own and that he approves every trade. Automatic liquidation is autonomous execution.
4. **Market orders in a black swan are the wrong instrument.** Options books go thin exactly when it matters. An automatic market exit in an illiquid strike converts a bad day into a permanent loss.

**Where it does belong:** the real-money design phase, alongside order-state handling and broker reconciliation, and even then the default should be assisted one-click closure with confirmation rather than an unattended trigger. Recorded as a real-money gate item, not dropped.

---

### E — Volatility fallback. Third-party source refused. Bounded cache accepted.

**Refused: a secondary market-data source such as `yfinance` for the risk calculation.** Introducing a second, unofficial, terms-of-service-grey source whose numbers may silently differ from the broker's is the exact substitute-number pattern that produced three days of false confidence. A risk gate fed by an unverifiable source is worse than a risk gate that stops.

**Accepted: a bounded previous-session cache.** Yesterday's successfully computed 20-session volatility is a real number that was verified when it was computed. It is not a substitute. Rules:

- Use the last successfully computed figure only if it is at most **one trading day old**.
- Display it prominently as previous session, with the exact timestamp of computation, beside the verdict.
- Beyond one trading day, **block**. No exceptions, no third source.

**And the durable fix, which already sits in the plan:** Hermes's lockout scenario assumes the twenty sessions come from a live API call each time. They should not. The local history store already holds daily bars; Release 1B repairs the nightly ingest that stopped on 2026-09-03. Once history is stored locally and topped up each night, a single broker API glitch cannot lock him out, because the twenty sessions are already on disk. The cache is the seatbelt; the repaired local store is the road.

---

## 2. CORRECTED RELEASE ORDER

| Release | Name | Contains | Changes anything? |
|---|---|---|---|
| **0** | State baseline | Live schema export, diff against disk, `000_baseline.sql`, verified full backup | **No. Read-only.** |
| **1A** | Foundation, access, truth | Real migration runner and version table; Google sign-in with lockout-proof runbook; CORS narrowed; real lot size from the contract master; legacy lot-75 positions quarantined; **idempotency on execute**; Tier-1 kill switch plus one-click Close All; every remaining fabricated value removed; fail-closed on all trade dependencies; readiness demoted to ceremonial; test hygiene; staging database created | Yes |
| **1B** | The data the risk rule needs | Recorder permission repair with a real file proved; nightly ingest restored; data-quality contract; stale-data guard; backups with correct identities, versioning, checksums and a real restore drill; monitoring on feed age, token validity, recorder arrival, backup age and alert delivery | Yes |
| **2** | Risk policy | Risk capital as defined; **paper enforces the cash-equivalent margin ceiling**; the versioned risk scenario; planned-exit-date field; exact hedge geometry; real broker margin, cached and throttled; percentage display bug; **bounded previous-session volatility cache**; Method files updated in both copies | Yes |
| **3** | Real cost of trading | Versioned charge schedule with clearing charges, IPFT and expiry handling; Decimal money maths; limit simulation as the default fill mode; full quote snapshot stored per fill | Yes |
| **4** | Strategy Builder to the Sensibull standard | What-if engine, correct multi-expiry valuation so calendars work, metrics strip, payoff chart with open-interest and OI change, standard-deviation table, greeks toggles, Shift/Width/Multiplier, ready-made grid, 30-second refresh, execution on the page, all to the v6 Section 2 size standard | Yes |

Nothing after Release 4 is in Phase 1. The Trade Journal redesign, charts, backtesting, book ingestion and the four AI learning loops resume once this foundation holds.

---

## 3. TOMORROW'S MARKET TEST (2026-09-08, 13:00–14:00 IST)

Abhishek asked for a live run tomorrow and for a stable week afterwards. Tomorrow is a **measurement session, not a build session.** No code ships into the live site during market hours.

**Before he arrives:** the FYERS token is refreshed close to trading time, never before 08:00 IST, per the lesson recorded on 2026-09-07.

**He does:** whatever he would normally do. Open both pages, build a strategy, look at the numbers, press what he would press. He reports what he sees as a user.

**Claude does, in parallel, and records with evidence:** live spot against the broker; every displayed number recomputed at lot size 65 and compared with what the screen shows; the real broker margin against the invented constants; the risk verdict against the real capital; whether any value is stale, frozen or unavailable without saying so; a duplicate-execute attempt on paper to confirm the idempotency bug is real before it is fixed; and the age of every data source.

**Output:** one dated findings list, his observations and mine merged, each with proof. That list is the input to Release 1A, which is built in the evening and over the following days off-market.

---

## 4. WHAT PEACE OF MIND ACTUALLY REQUIRES

Abhishek's stated need: that problems he finds this week are new problems, not the same ones again.

That is only achievable if a fix cannot silently regress. Therefore, from Release 1A onward, each of these is a permanent, automated check that fails the build, not a promise:

1. No fabricated fallback may enter a data or trade path. Enforced by a check that fails on the pattern, in addition to the data-quality contract.
2. No hardcoded contract size, margin figure or charge rate. Contract data comes from the contract master; margin from the broker; rates from a dated schedule.
3. Every safety control fails closed. A test proves each one blocks when its dependency is removed.
4. A browser console error fails the frontend suite.
5. Every displayed market value carries source and timestamp, and a test proves an unavailable source renders as unavailable rather than a number.
6. Execution is idempotent, proven by test.
7. Real-money execution stays blocked, proven by test.

If a problem he reports next week is one of these seven, the check was wrong and the check gets fixed, not just the symptom.

---

*Nothing here is a claim of readiness. Real-money trading remains code-blocked. Written 2026-09-07 by Claude Code (Opus 5). v6 carries the full body; this document carries the amendments, the order and the market-test plan.*
