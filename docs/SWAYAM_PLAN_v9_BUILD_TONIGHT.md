# SWAYAM CAPITAL — PLAN v9, THE BUILD PLAN

> **Written 2026-09-08, 00:30 IST by Claude Code (Opus 5). This supersedes v8 as the execution plan.**
>
> v9 exists because two of v8's decisions were wrong, and Abhishek corrected both:
>
> 1. **v8 said a cloud service can never write to his Obsidian vault. That was wrong.** The vault is Google Drive. It has an API. The correct fix is the Drive API, not a sync task on his PC. Corrected in Section 5.
> 2. **v8 locked paper execution until Release 3, days away. That followed a reviewer instead of the owner.** Abhishek trades paper from 2026-09-08 and builds tonight. Everything that makes a paper trade dishonest is mechanical and fits in one night. Corrected in Section 2.
>
> Read `SWAYAM_PHASE1_PLAN_2026-09-07_v6.md` for the full detail body and the UI size standard, `v7` for the Hermes amendments, and `v8_FINAL` for the Codex-v7 amendments and the capital model. **v9 is what gets built and in what order.** Everything in v6, v7 and v8 that v9 does not contradict still stands.

---

## 1. THE ONE SENTENCE

Tonight's build makes a paper trade numerically true and safely recorded, so Abhishek can paper trade from 2026-09-08 afternoon on numbers he can trust. Everything else waits.

---

## 2. RELEASE 1 — HONEST PAPER TRADE (tonight, 2026-09-07 into 2026-09-08)

A paper trade today is a lie in seven separate ways. All seven are mechanical. This release fixes exactly those and nothing else.

### 2.1 Order of work, with reasons

**Step 0 — baseline, before any schema change. Read-only.**

Already half done: `migrations/_live_schema_inventory_2026-09-07.json` holds all 19 live tables with columns and types, captured 2026-09-07. Remaining: diff it against the ten migration files on disk, write `migrations/000_baseline.sql`, take a full backup with checksums, and prove one restore into a scratch database before the first production migration runs. **No schema change is permitted until that restore has been proved.**

**Step 1 — a migration runner that actually runs.** `scripts/apply_migration.py` currently reads the file, prints a line count and tells you to paste it into the Supabase editor. It executes nothing, and there is no version table, which is why nobody can say what the live schema is. Build a real runner plus `swayam_schema_migrations`, seeded to the baseline. Everything after this needs it.

**Step 2 — the money becomes true.**

| Fix | Detail | Proof required |
|---|---|---|
| Lot size | Read column index 3 of the FYERS contract master, the same `NSE_FO.csv` the app already downloads for expiries. **65, not 75.** Delete every hardcode: `models_api.py:21,81`, `execution.py:49`, `positions.py:305,497`, `options_math/models.py:45`, `options_math/strategies.py:32,85,138`, and the frontend leg builder. Missing lot size blocks the trade. | Before-and-after table of every rupee figure at 65 against 75 |
| Capital | `funds()` id 1 Total Balance, today **₹9,71,002.38**. Snapshotted once per session. Unavailable blocks. | The live number on screen with its timestamp |
| Risk caps | 1% = **₹9,710**. Black-swan fuse 5% = **₹48,550**. | Shown with the arithmetic |
| Deployable margin ceiling | 2 × cash-equivalent. Cash-equivalent = `funds()` id 3 Clear Balance (₹1,00,000) + cash-type pledged collateral (liquid ETF ₹54,279.46 + sovereign gold bond ₹1,23,201.00). Ceiling today **₹5,54,961**. A trade needing more is refused, as the broker would refuse it. | Both numbers on screen |
| Real margin | `POST https://api-t1.fyers.in/api/v3/multiorder/margin`, header `Authorization: {client_id}:{access_token}`. Delete the invented ₹32,000 and ₹1,15,000. Failure shows **unavailable**, never an estimate. Cached, throttled, schema-validated, never called on a slider drag. | Real margin beside the deleted constants |

**Step 3 — the risk gate Abhishek actually trades by.**

- Primary gate: loss at a **2 standard deviation** adverse move, both directions, worse one used, scaled by the square root of the planned holding days, **plus a reserved round-trip cost**, must be at or under **1% of capital**. Close-to-close returns already contain the overnight gap, which is what makes it overnight-aware.
- Black-swan fuse: absolute max loss at or under **5%**. Hard block.
- Absolute max loss otherwise is **informational only** and never blocks.
- **Delete the readiness gate from the trade path entirely.** No `size_cap_pct`, no `trading_allowed`, no verdict influence. Today's 0.3% throttle dies with it.
- Fix `rule-validation-panel.js:97,133`, which multiplies an already-percentage value by 100 and prints 62% where the truth is 0.62%. Remove the hardcoded demo `pct_of_margin: 0.41` at lines 23 and 30.
- Real hedge geometry: a short put needs a long put below it, a short call needs a long call above it, same underlying, same expiry, quantity at least equal. A short strangle must fail. Multi-expiry structures are blocked from execution until Release 3 gives them correct valuation; they stay visible and are labelled approximate.
- Display the whole arithmetic beside the verdict: `scenario price loss + round-trip cost reserve = total risk, against the ₹9,710 cap`.
- Data preconditions: 20 complete sessions, newest no older than one trading day, no gaps. Failure **blocks**. The only permitted softener is the previous session's already-computed figure, at most one trading day old, labelled with its computation time. **No third-party volatility source, ever.**

**Step 4 — a paper fill that costs what a real fill costs.**

- Buy legs fill at the **ask**, sell legs at the **bid**, captured at execution with a source timestamp. A missing bid or ask **refuses the fill**. Never ₹0.
- Because Abhishek's Method says limit orders 99% of the time, limit simulation is available and labelled: a limit that is not marketable creates a pending paper order rather than a flattering instant fill.
- Charge schedule, versioned by effective date, applied on entry and exit:

| Charge | Rate |
|---|---|
| Brokerage | ₹20 per executed order, FYERS Standard |
| STT | 0.15% of premium, sell side |
| NSE transaction charges | 0.03503% of premium, both sides, plus the clearing component listed on the FYERS charges page |
| IPFT | ₹50 per crore |
| SEBI turnover fee | ₹10 per crore |
| Stamp duty | 0.003%, buy side |
| GST | 18% on brokerage plus transaction plus SEBI |

- Every rate carries its source and effective date in code. Pin the transaction and clearing components from the FYERS charges page before shipping; two public sources disagree by about fifty paise per lakh. Reconcile the whole schedule against the FYERS brokerage calculator, and against his 2022-23 contract notes if he still holds them. **Never compute a historical journal entry with today's rates.**
- Money arithmetic uses `Decimal` server-side. The frontend displays what the backend computed and never recomputes.
- Delete the `legs × ₹150` placeholder from the close path.

**Step 5 — the trade cannot be recorded twice or half-recorded.**

- **Idempotency.** The browser makes an execution key, persists it in local storage, and reuses it on every retry until a final answer arrives. An execution-attempt row carrying the key and a canonical payload hash is written **before** the position. Same key and same payload replays the stored result; same key and different payload is rejected. Both `/api/execute` and `/api/execute/multi-leg` are covered. A database unique constraint plus a transaction is the control; disabling the button is only convenience. Proven by a test that simulates a lost response and asserts exactly one position.
- **Atomic lifecycle.** Position state, execution attempt, trade-history intent and a journal outbox task commit together. **The journal never fails the trade.** If the vault is unreachable, the note queues and the position shows `pending_journal` rather than returning HTTP 500 after the trade already exists. Same on close. Reconciliation view for anything stuck.

**Step 6 — honesty and safety.**

- Remove the last fabricated values in trade or display paths: rollover `68.5` at `nifty_snapshot.py:476`; the Tuesday-expiry guess at `expiry.py:146-165`; verdict defaulting to GREEN at `home.js:179`, to GO at `mini-readiness-card.js:14`, to green at `verdict-card.js:43`; P&L defaulting to 0 at `mini-positions-list.js:26` and `strategy-builder.js:481`; invented macro text at `macro-events-card.js:104`; the fabricated ₹35.00 premium in the add-hedge fix at `strategy-builder.js:779`; premium defaulting to 0 on execute at `strategy-builder.js:584,604,663,708`.
- Fail closed on every trade dependency: capital, volatility, prices, expiry, lot size. No bare `except: pass` in the trade path.
- **Google sign-in**, with the full contract: `--iap` on Cloud Run, IAP service agent granted invoker, `roles/iap.httpsResourceAccessor` to his account only, `allUsers` removed, `--allow-unauthenticated` deleted from `cloudbuild.yaml`, CORS narrowed from `*` to the exact origin, the backend independently verifying the identity assertion against a one-account allow-list, `/ws/spot` authenticated, service-role key proven absent from the production bundle. **Runbook first**, with rollback, because a mistake here locks him out of his own terminal. If it cannot be done safely tonight, it ships as the first thing after, and that is stated rather than skipped quietly.
- **Kill switch**, Tier 1 only: a database-backed global halt blocking every risk-increasing action at the backend. Close, reduce, journal, notebook and audit stay permitted. One-click Close All waits for Release 3, because closing today would price at last-traded price with a ₹150 placeholder charge.
- **Quarantine the 67 existing positions.** All are `mode = paper`; 66 are `Paper Bear Put` build-test rows from 3 to 7 September, one is an `Iron Fly`, 64 are archived and **3 are still marked open and showing on his screen**. Label all 67 `provenance = build_test`, exclude them from every statistic and from the AI, close the three open ones with a system note. **Never silently rewrite their numbers.** His real paper record starts clean.

**Step 7 — test hygiene.** Fix `tests/api/test_market.py::test_get_option_chain_returns_strikes` and `tests/test_notifications.py::test_execute_endpoint_best_effort_dispatch_on_success`. Fix `rule-panel.js:35` `toFixed of undefined`. Make a browser console error fail the frontend suite. Fix `service-worker.js:5-11`, which precaches dev paths absent from the production build.

### 2.2 The gate that unlocks paper trading

Paper execution stays behind a server-side flag, default off, and turns on only when **all** of these are true and shown to Abhishek:

1. A before-and-after table of every rupee figure at lot 65 against lot 75.
2. Live capital ₹9,71,002.38 and the ₹5,54,961 ceiling on screen with timestamps.
3. A worked trade: entry and exit, every charge line, gross and net, reconciled against the FYERS brokerage calculator.
4. A boundary test proving a trade that only fails once costs are added is blocked.
5. A duplicate-submission test proving one position, run in staging, **never in production**.
6. Both suites green with zero swallowed browser errors.
7. A short strangle rejected, and a ₹0-premium leg refused.

If any one of these is not true by the time he sits down, **say so plainly and leave the flag off.** That is the whole point of this exercise.

---

## 3. RELEASE 2 — THE SECOND BRAIN CONNECTION AND THE DATA THAT KEEPS ARRIVING

- **Journal notes into the vault from the cloud, via the Google Drive API.** Enable `drive.googleapis.com` on `swayam-capital`, share the `Second Brain` folder with `swayam-dashboard-sa@swayam-capital.iam.gserviceaccount.com`, and drain the journal outbox into `02 - Projects/Trading/` in his vault. Because Drive syncs, the notes appear in Obsidian on every device even when his PC is off. **Verify before claiming**; the Drive API is currently not enabled on the project. Any note queued during Release 1 backfills automatically.
- **Fix the options recorder.** It has never succeeded once: every invocation since 2026-09-03 fails PERMISSION_DENIED because the Cloud Scheduler identity lacks `run.invoker`, and its own service account holds only `logging.logWriter` so it could not write to storage anyway. Grant both, prove a real object lands, alert if nothing arrives by 10:00 IST. State plainly that snapshots before the fix cannot be recovered.
- **Restart the nightly history ingest**, stopped since 2026-09-03, and show the age of the data on screen. This is what stops a broker glitch from locking the risk gate.
- **Real backups.** Correct per-workload identities, versioned and checksummed objects, failed upload fails the job, a restore that restores, one recorded drill, last-backup age on screen.
- **Data-quality contract and stale guard** on both pages: value, source, source timestamp, received timestamp, market session, quality, unavailable reason. Stale values grey out. New entries block on stale data; closing stays allowed.
- **Monitoring** on feed age, token validity, recorder arrival, backup age and alert delivery.
- **Method files read from the vault at runtime**, removing the manual redeploy step in Section 5.3.

---

## 4. RELEASE 3 — THE SENSIBULL-GRADE STRATEGY BUILDER

Everything in v6 Release 4, unchanged: the NIFTY target slider, the date slider, the editable per-strike implied volatility with offset, one debounced recalculation feeding every number, correct multi-expiry valuation so calendars work, the metrics strip with funds and margin from the broker, the payoff chart with open-interest bars and OI change (available from a single chain call via `oi`, `oich`, `oichp` and `prev_oi`, verified 2026-09-07), the standard-deviation table, the greeks multiply toggles, Shift and Width and Multiplier, the ready-made strategy grid, thirty-second price refresh, execution on the page, a P&L table tab, and functional Close All.

**Built to the UI standard in v6 Section 2, which is a review gate, not a preference:** hero metrics 28 px, secondary 18 px, leg values 16 px, labels 14 px, chart axes 13 px, chart data labels 12 px minimum, **nothing he acts on below 14 px**, tabular figures, generous rows, no purple.

---

## 5. THE SECOND BRAIN CONNECTION — CORRECTED

### 5.1 What is actually true

The deployed service sets `TRADING_METHOD_PATH` but **not** `VAULT_PATH`, so `config.py:37` falls back to the literal Windows path `G:\My Drive\Second Brain`, which no Linux container can reach. Today a paper trade on the live site inserts the position, fails to write the journal, and returns **HTTP 500**. All 67 existing journal notes were written from his own machine.

### 5.2 The correction to v8

v8 claimed a cloud service can never write to his vault, and concluded a local sync task was the answer. **That was wrong.** The vault is Google Drive, not merely a local folder. The Drive API can write into it from anywhere. Chosen approach, Release 2: enable the Drive API, share the folder with the service account, write from the cloud. A local sync remains only as a fallback if Drive access proves unreliable.

### 5.3 Manual step, recorded so it is never forgotten

Until Release 2 makes Method files read from the vault at runtime, **editing a rule in Obsidian does not change the live app.** The container carries a build-time copy of three of the seven Method files. Any Method change, including moving the black-swan fuse from 3% to 5% in Release 1, requires editing **both** the vault file and `src/swayam/data/method_files/`, then redeploying. This is in the Release 1 exit gate.

### 5.4 Deferred, with reasons

| Item | Status |
|---|---|
| Trade lessons and AI memory written back into the vault | Deferred to the AI chapter |
| Daily market notes into `08 - Daily Market Notes/` | Deferred to the AI chapter, learning loop 2 |
| Book ingestion from vault PDFs | Deferred to the AI chapter, learning loop 4 |
| Drift alert comparing vault and repository Method copies | Deferred; manual discipline until then, per 5.3 |
| Atlas daily-log prefill on the live site | Deferred to Release 2 with the Drive API; works locally today |

---

## 6. PAPER AND REAL COEXIST PERMANENTLY — binding on every release

Abhishek's requirement, 2026-09-07, in his words: paper trading never dies. After moving to real money he may return to paper for weeks, then go back, and the paper record must still be there and still accumulate.

- `mode` is a permanent first-class attribute on every position, trade-history row, journal entry and lesson. It exists on positions today and reads `paper` on all 67 rows.
- Statistics, analytics, AI context and the lesson ledger are **always** filtered by mode. A paper result may never enter a real-money statistic, in either direction.
- Each journal note states paper or real on its face.
- Switching mode is explicit and audited, never automatic, and never alters an existing record's mode.
- A finished paper season stays queryable forever: how many trades, which strategies, what result.

---

## 7. THE SEVEN PERMANENT CHECKS

Automated from Release 1, failing the build. They exist so a problem found next week is a **new** problem.

1. No fabricated fallback in any data or trade path.
2. No hardcoded contract size, margin figure or charge rate.
3. Every safety control fails closed, proven by removing its dependency.
4. A browser console error fails the frontend suite.
5. Every displayed market value carries source and timestamp; an unavailable source renders as unavailable, never as a number.
6. Execution is idempotent across retries and reloads, not just double-clicks.
7. Real-money execution stays blocked.

---

## 8. EVIDENCE REQUIRED BEFORE ANY CLAIM OF DONE

1. Files changed and migrations listed, with proof the migration actually executed.
2. Test results with exact counts, no ignored browser console errors.
3. Desktop and mobile screenshots, checked against the UI standard.
4. Live market-hours proof for data changes, or an explicitly labelled off-hours limitation.
5. A before-and-after table for every displayed number that changed.
6. Rollback instructions and the deployed commit id.
7. This document and the current-state document updated.

---

*Real-money trading remains code-blocked. Nothing here is a claim of readiness. Written 2026-09-08 by Claude Code (Opus 5).*
