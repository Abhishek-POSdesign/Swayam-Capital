# Independent Codex Audit — Home and Strategy Builder

**Date:** 2026-09-07  
**Scope:** Home page, Strategy Builder page, and only the services those pages rely on.  
**Method:** Source-code trace, configuration-presence check (no secrets read), local data inventory, repository/log inspection, production frontend build, and automated tests. No real trade, database write, cloud deployment, or broker order was triggered.

## Bottom line

**Do not use this application for real-money trading.** It is a **paper-trading prototype with useful rule and calculation components**, not a professional live-trading terminal. Its visual product is comparatively mature; its operational controls, data guarantees, deployment evidence, and audit controls are not.

Paper trading may continue only after the priority-0 issues below are fixed and independently retested. Real-money trading must remain disabled until the whole release gate is complete.

## What was verified to work

| Area | Verified finding | Confidence |
|---|---|---|
| Frontend | Production Vite build completes successfully. The output is one very large 5.2 MB JavaScript bundle. | High |
| Frontend tests | 109 Vitest tests passed across 28 files. A navigation test nevertheless logs a real `rule-panel.js` rendering error. | High |
| Strategy maths | Backend contains payoff, Greeks, probability-of-profit and two-tier risk calculation code, with 322 tests collected in the repository. | Medium — mostly mocked/unit tested |
| Paper execution | The UI can create a paper position in Supabase and write a journal note after validation. Real mode returns HTTP 403 by design. | High from source/tests |
| Market access | FYERS credentials are configured locally; recent FYERS logs include successful quote, history and option-chain responses. | Medium — no live market-hours acceptance test |
| Historical local data | DuckDB contains 36,998 option-history rows, 22 NIFTY daily bars and 5 realised-volatility cache rows. | High for local file presence; not independently source-validated |
| No-fake-data clean-up | Old fake VIX, fake payoff and fake snapshot fallbacks were removed in current code. Most unavailable values now render as `—` or return 503. | High |

## What is not working, unsafe, or unproven

### Priority 0 — block paper-trading release until fixed

1. **The “live WebSocket” is not live.** The browser opens `/ws/spot`, but no code calls `broadcast_spot` or `broadcast_position`. The browser therefore reconnects forever to an idle socket while a separate REST poll runs every 10 seconds. This is misleading and cannot provide professional-grade live ticks.

2. **Readiness validation fails open.** In `validation.py`, failure while reading today’s readiness record is swallowed with `except Exception: pass`. A database outage therefore removes a safety gate instead of blocking a trade. Financial controls must fail closed.

3. **Backup success is false-positive.** All three backup jobs call `upload_to_gcs(...)` and then return `True` regardless of whether the upload failed. The code only logs the failure. Cloud Scheduler can therefore report a successful backup when no off-machine backup exists.

4. **The restore command does not restore.** `restore_from_backup.py` merely parses the SQL and checks database connectivity; it explicitly does not execute any restoration statements. The current recovery plan is therefore untested and not automated.

5. **Hard-coded rollover data remains.** The Home snapshot returns `rollover_pct: 68.5` whenever it is in the rollover window. It has a `PREVIOUS SESSION` label, but the number is still fabricated and contradicts the project’s stated “no fake numbers” rule.

6. **Broker instability is visible in the application logs.** FYERS logs contain repeated 429 rate-limit responses and later 401/403 responses. The app has caching, but no verified quota monitor, circuit breaker, stale-data banner at the terminal level, or operational alert path demonstrated by the audit.

### Priority 1 — necessary before any real-money design work

7. **No authoritative live-data chain of custody.** Home mixes FYERS REST quotes, FYERS contract-master/cache data, local DuckDB data and Supabase rows. Not every field carries source, timestamp, session state, market status and error state. A professional terminal needs this for every displayed trading datum.

8. **Expiry logic can invent dates.** When both the FYERS contract master and its disk cache fail, the code computes Tuesdays as expiry dates. It labels the result as normal calculated data rather than a blocked/unavailable trading input. For order-capable software, contract metadata must never be guessed.

9. **Risk/hedge validation is too coarse.** “Hedged” means merely that at least one sell leg exists; it does not verify matching expiry, strike relationship, contract identity, quantities, or worst-case exposure per leg. The later naked-short checker also totals calls and puts across all legs rather than validating an exact hedge relationship.

10. **Order preview uses fixed rupee estimates.** It assumes ₹32,000 hedged and ₹115,000 naked margin per lot. These are illustrative values, not broker margin. They must not influence a real trade decision.

11. **The AI is advisory but not sufficiently governed.** Its chat history and memory are stored in Supabase, and its source context can be incomplete. The context-building path can fall back to a generic system prompt on failure. AI costs are estimated from characters rather than provider usage in streaming mode. There is no independent citation/claim validation or immutable record of sources used for each recommendation.

12. **The production security posture is contradictory.** Cloud Build deploys `--allow-unauthenticated`; the documentation claims the app is behind IAP. The FastAPI app allows all origins. Supabase RLS is disabled for every table. A private load balancer/IAP may exist outside this repository, but it is not evidenced here. This must be reconciled and tested before exposing any terminal that stores financial and personal data.

13. **Service-worker cache is built for development paths.** It precaches `/src/main.js` and `/src/styles.css`, which do not exist in the production Vite bundle. Offline behaviour and cache upgrade safety are unproven.

14. **There is no release-quality visual verification.** The later session record explicitly says it used DOM inspection and tests, not browser screenshots. I could compile the page but could not authenticate to the live site from this environment. No desktop/mobile visual acceptance evidence is available.

### Priority 2 — quality, maintainability and trust issues

15. **Documentation is materially unreliable.** It claims 51 backend tests and 102 frontend tests while the actual current frontend suite is 109 and pytest collects 322 tests. It describes cloud resources, bucket names, service names, backup retention and database tables that conflict with source configuration.

16. **The supplied “data integrity” report is not all-real.** It says PCR and Max Pain were tested with synthetic validation matrices. It is not proof that the displayed live values were reconciled with independent sources.

17. **Tests are not clean.** The selected Home/Strategy/Paper suite produced 37 passes, 1 failure and 3 environment errors. The failure comes from a stale test double that no longer matches the FYERS option-chain method signature; the three errors were caused by a protected system temporary folder. Neither issue is a successful verification.

18. **A navigation regression is hidden by a passing test.** The frontend navigation test logs `Cannot read properties of undefined (reading 'toFixed')` from `rule-panel.js`. A passing test that permits a browser error is insufficient for a terminal.

19. **The frontend bundle is excessive.** The only production JavaScript bundle is 5.2 MB (1.55 MB gzip), mostly because Plotly is bundled. This degrades first load and makes an urgent trading screen less reliable on weak networks.

20. **The local branch is not main.** Audit started on `feature/swayam-legcard-compact-price-005` at commit `3a93d27`, with an untracked `.claude/` folder. It cannot be claimed that this exact code equals the production deployment.

## Real data, derived data, paper data, and fake/unavailable data

| Item | Classification | Notes |
|---|---|---|
| NIFTY spot, option LTP/bid/ask/OI | Potentially real FYERS REST data | Current logs show recent successful calls; live status must be displayed with timestamp and source. |
| Contract expiry from FYERS master/cache | Real when fetched/cached | Becomes unsafe when the Tuesday heuristic is used. |
| NIFTY daily history / options history | Local historical cache | Exists locally; source completeness and freshness were not independently reconciled. |
| VIX card | Derived from real bhavcopy only | Correctly reports unavailable if fewer than 20 rows are available. |
| Payoff, Greeks, PoP, 2-sigma risk | Model-derived | Depends on user-entered or broker prices, IV and assumptions. It is not live broker risk. |
| So Far Today | AI-generated, search-grounded summary | Manual trigger, cached for 60 minutes, capped at 8 calls/day; useful commentary, not a trading data feed. |
| Readiness, AI memory, journal, paper positions | User/system records in Supabase | Real records, but not broker records. |
| Execution ticket/margin | Paper simulation | Real execution is blocked. Fixed margin figures are not broker margin. |
| Rollover 68.5% | Fake | Must be removed or replaced with a sourced value. |
| WebSocket “live” feed | Non-functional | Connection exists but no publishing producer exists. |
| Reading Queue, Wake Alerts | Unbuilt | Explicit “coming soon/later build” states. |

## Home page assessment

The Home page has solid component coverage: readiness ritual and verdict, KPI history, manual So Far Today, NIFTY snapshot, VIX, macro events, AI chat, PWA prompt and an honest empty Reading Queue.

The visual and interaction layer is generally the strongest part of the app: graceful unavailable states, freshness badges, responsive layout intent and a manual AI cost gate. However, it cannot yet be trusted as a market dashboard because freshness/source metadata is inconsistent, data failures are not consolidated into one terminal-level status, VIX depends on database ingestion, the rollover value is fake, and the supposed WebSocket is idle.

## Strategy Builder assessment

The Strategy Builder has meaningful paper-trading functionality: real-or-empty option quote inputs, presets, expiry selection, payoff graph, Greeks, what-if controls, two-tier risk checks, readiness display, order sequencing and paper execution.

It is **not** a professional order-management system. It has no broker order lifecycle, exchange acknowledgement, fill reconciliation, market-data entitlement verification, actual margin, contract validation, idempotency key, trade kill-switch, immutable audit log, or reliable real-time position/risk feed. The paper execution path is appropriate for prototype learning only.

## Comparison with a professional trading terminal

| Capability | This app today | Professional minimum |
|---|---|---|
| Market data | REST polling plus an idle WebSocket | Entitled streaming feed, sequence handling, latency/freshness, stale detection, replay/recovery |
| Order management | Paper records only; real orders intentionally blocked | Broker/exchange acknowledgements, order state machine, fills, rejects, cancel/replace, idempotency and reconciliation |
| Risk controls | Useful calculations, but fail-open readiness and coarse hedge checks | Fail-closed pre-trade risk, real margin, per-leg exposure, limits, kill switch and independent reconciliation |
| Data quality | Mixed sources with partial badges | Per-field source/time/quality, cross-source checks, alerting and incident records |
| Security | Ambiguous public/IAP posture; RLS disabled | Verified access control, least privilege, secret rotation, MFA, audit logs and penetration testing |
| Backups/DR | Local files exist; upload success and restore are not real | Monitored immutable backups, restore drills, RPO/RTO and evidence |
| Testing | Good unit-test volume; incomplete/contradictory reports | Clean CI, integration tests, market-hours smoke tests, browser E2E and release gates |

## Required solution plan

### Phase A — make paper trading safe and honest

1. Remove the fake rollover figure and remove expiry heuristics from trade-capable paths.
2. Change all safety-control database/API failures to **block** validation and paper execution.
3. Either implement FYERS-to-backend-to-browser streaming with a single lifecycle owner, or remove the WebSocket UI and label REST polling accurately.
4. Replace fixed margin estimates with broker margin or show “unavailable”; strengthen hedge checks per leg, quantity, expiry and contract.
5. Make backup upload failure fatal; implement a genuine restore into an isolated database and perform a documented restore drill.
6. Fix the navigation error, stale option-chain test, test temporary-path setup, and require browser errors to fail frontend tests.

### Phase B — establish operating truth

1. Create one source-of-truth deployment/runbook document from the actual cloud state, not past agent claims.
2. Add a terminal status strip: broker token health, market-data age, database health, AI availability, recorder status, backup age and release commit.
3. Add data lineage to each Home and Strategy Builder datum: source, timestamp, market session and calculated/input flag.
4. Reconcile Cloud Run access, IAP, CORS and Supabase RLS with a security review.
5. Add CI: build, unit tests, browser E2E desktop/mobile, API contract tests, dependency/security scanning and manual release approval.

### Phase C — real-money readiness (future; do not skip)

1. Use a dedicated broker-paper environment and run market-hours acceptance tests for several weeks.
2. Implement broker OMS state handling, actual margin/positions/fills, idempotency, rate-limit management, a kill switch and broker-vs-platform reconciliation.
3. Add immutable audit trails, restore drills, monitoring/alerts, disaster recovery targets and independent security review.
4. Permit real orders only after a written release gate is signed off with objective evidence for every item above.

## Audit limitations

The path supplied for the external Claude verdict (`G:\My Drive\Second Brain\00 - Developer Logs\SWAYAM\_REALITY\_VERDICT.md`) was not available on this computer, so it was not reviewed. The live website could not be authenticated/reached from this environment, and no live cloud-console, Supabase-console or broker-account inspection was authorised. Findings about those systems are therefore code/configuration evidence, not a claim of their current cloud state.

