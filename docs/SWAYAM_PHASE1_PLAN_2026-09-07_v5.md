# SWAYAM CAPITAL — PHASE 1 IMPLEMENTATION PLAN (v5, FOR EXECUTION)

> **Written 2026-09-07, 20:00 IST by Claude Code (Opus 5).** Supersedes `SWAYAM_PHASE_A_PLAN_2026-09-07.md` (v4). v4 was written before Abhishek's risk-rule decisions, before the Sensibull reference screenshots, and before two defects were found that invalidate every rupee figure the platform has ever shown him.
>
> **Status: PROPOSED, awaiting Abhishek's approval. No application code written.**
>
> **This document is written to be executed cold by another agent, and to be cross-checked by Codex and Hermes.** Every claim of current state carries the command or query that proved it, run on 2026-09-07.

---

## 0. CONTEXT — why this plan exists

Abhishek built an Obsidian Second Brain, linked it to his Atlas daily-log app, loaded three years of his own trading history and psychology into it, and had this platform built on top. He was told across several sessions that it was ready. On Monday he found it was not. Three independent audits (Claude, Codex, Hermes) then found fail-open safety controls, a public deployment, fabricated numbers, a dead WebSocket, backups that report success while saving nothing, and a restore script that restores nothing.

This session verified all of that first-hand and found more. The two findings below were missed by every prior audit and by every agent, and they matter more than everything else on the list, because they mean **no rupee figure the platform has ever displayed to him was correct.**

### FINDING A — the NIFTY lot size is 65. The platform hardcodes 75.

Proven twice, independently, on 2026-09-07:

1. The FYERS margin API rejected a 75-quantity order with `{"code":-50,"message":"75 not a multiple of minimum lot size 65"}`.
2. The official FYERS contract master at `https://public.fyers.in/sym_details/NSE_FO.csv`, **which this app already downloads for expiry dates**, carries lot size in column index 3. The row for `NSE:NIFTY2690818850CE` reads `['101126090835404','NIFTY 08 Sep 26 18850 CE','14','65','0.05', ... ,'NIFTY','26000','18850.0']`. Column 3 is `65`.

The app hardcodes 75 in at least twelve places: `src/swayam/api/models_api.py:21,81`; `src/swayam/api/routes/execution.py:49`; `src/swayam/api/routes/positions.py:305,497`; `src/swayam/options_math/models.py:45`; `src/swayam/options_math/strategies.py:32,85,138`; and in the frontend leg handling in `web/src/pages/strategy-builder.js`.

**Consequence:** every premium, every max profit and max loss, every 2-sigma stressed loss, every margin figure, every charge and every position P&L in Swayam is **15.4% too large**. The risk gate has been sizing him against a contract that does not exist. A 100-point-wide bear put spread shows a max loss of Rs 7,500 when the real figure is Rs 6,500.

### FINDING B — the order-preview margin figures are invented and badly wrong.

`src/swayam/api/routes/execution.py:59-61,86-90` hardcodes Rs 32,000 per lot hedged and Rs 1,15,000 per lot naked. Verified against the real FYERS margin calculator on 2026-09-07:

| Position | App shows | FYERS says |
|---|---|---|
| Single short NIFTY 23650 PE, 1 lot | Rs 1,15,000 | **Rs 1,94,741** |
| Bear put spread 23850 / 23650, 1 lot | Rs 32,000 | **Rs 2,01,447** |

The endpoint `POST https://api-t1.fyers.in/api/v3/multiorder/margin` returns HTTP 200 with `margin_avail`, `margin_total` and `margin_new_order` tied to his real account. It is not in the Python SDK's method list and must be called over HTTP with the header `Authorization: {client_id}:{access_token}`.

**Note, stated honestly:** in the test above the endpoint did not net the hedge benefit for the spread. The correct call shape to obtain that benefit must be pinned down during the build, and checked against the FYERS web margin calculator, before any margin number is displayed. Until it is proven, show "unavailable" rather than a figure.

---

## 1. DECISIONS LOCKED BY ABHISHEK (2026-09-07) — do not relitigate

| # | Decision | Detail |
|---|---|---|
| D1 | **Login is Google sign-in** | He chose the safer option. Cloud Run supports it natively through the `--iap` flag: no load balancer, no Compute API, no extra cost. Only his Google account is permitted. |
| D2 | **Static egress IP deferred** | Not needed for market data. Becomes mandatory when real orders start, under the SEBI April-2026 retail-algo rules. Estimated Rs 450 to Rs 650 a month. Revisit at the real-money gate. |
| D3 | **Capital floats with the real broker balance** | The risk cap is a percentage of the FYERS balance including cash and pledged collateral, read live. Today: **Rs 8,71,002.38**, verified through `fyers.funds()`. |
| D4 | **Primary risk gate is 2 standard deviations against 1% of capital** | Not the strategy's absolute max loss. Today 1% is Rs 8,710 and 2 SD is 164 NIFTY points. |
| D5 | **The stress must be overnight-aware: the gap plus the following session's move** | He holds overnight. Close-to-close returns already contain the gap; scale by the square root of the intended holding days. |
| D6 | **Black-swan fuse is 5% of capital on absolute max loss** | Raised from the 3% currently in the Method file. His reasoning, recorded: a black swan is a once-in-two-or-three-years event and is as likely to fall in his favour as against him. Today 5% is Rs 43,550. **This is a constitutional change to a Method file and is made only on his written instruction, which is this document.** |
| D7 | **Readiness becomes ceremonial only** | Keep the ritual, the verdict card, the five-minute meditation, the alcohol streak and the seven-day dots as a personal journal. **It must have zero power over trading.** His reason: a self-reported form can be lied to, so it must never size or block a position. Revisit when real money starts, and record that revisit obligation. |
| D8 | **Paper trades carry real costs** | Brokerage, STT, exchange transaction charges, SEBI fee, stamp duty and GST, all applied. FYERS **Standard** plan at Rs 20 per executed order. He expects 20 to 30 orders a month, so Prime is not worth it yet. |
| D9 | **Execution stays on the Strategy Builder page** | So he can change a strike, ask what happens if NIFTY moves, if IV changes, or if a day passes, and then execute without leaving the screen. |
| D10 | **Sensibull is the reference for the Strategy Builder** | Screenshots supplied 2026-09-07. Section 3, Release 4 itemises the parity list taken from those screenshots. |
| D11 | **Fix the options recorder** | It has never worked. In scope. |
| D12 | **AI chapter deferred** | The four learning loops wait until the basics are trustworthy. Fixing the AI's blindness to its own "So Far Today" summary and the read-aloud pause bug are small defect fixes and stay in scope; the learning loops do not. |
| D13 | **Build off-hours, prove live** | Abhishek runs his own user test tomorrow between 1 and 2 PM IST and reports what he sees. Claude then runs the live checks he cannot see. |
| D14 | **Wake-alert job for his wife is parked** | Big gap, loss beyond expectation, or profit beyond expectation. Good to have, deliberately deferred by his own decision. |

---

## 2. VERIFIED CURRENT STATE (2026-09-07, with proof)

| Area | State | Proof |
|---|---|---|
| Access | **PUBLIC.** `allUsers -> roles/run.invoker` on `swayam-dashboard`. Anonymous requests to `/api/nifty/spot`, `/api/positions` and `/api/readiness/today` all return 200. The readiness endpoint serves his sleep, mood and stress notes to the open internet. | `gcloud run services get-iam-policy swayam-dashboard --region asia-southeast1`; anonymous curl |
| CORS | `allow_origins=["*"]` together with `allow_credentials=True` | `src/swayam/api/main.py:21` |
| RLS | Off. The anon key reads `swayam_positions`, `swayam_ai_messages`, `swayam_readiness_log` and `swayam_config`. **Mitigating fact: the frontend ships no Supabase key; all database access is server-side.** | direct REST call with the anon key, HTTP 200 |
| Safety gate | Fails open three ways: `except Exception: pass`; the gate is skipped entirely when no readiness row exists for today; `trading_allowed` defaults to `True` when the field is absent | `src/swayam/api/routes/validation.py:96-113` |
| Size throttle | Today's row is verdict GREEN with trading allowed and `size_cap_pct = 0.003`. That 0.3% overrides his 1% and is why valid trades were blocked. | `GET /api/readiness/today` |
| Hedge check | Passes if **any** leg is a sell. A short strangle counts as hedged. | `validation.py:198-206` |
| Kill switch | Does not exist | grep across the repository |
| WebSocket | `broadcast_spot` and `broadcast_position` have zero callers. The FYERS websocket module additionally **cannot import** in the project environment: `No module named 'pkg_resources'`. | grep; import test |
| Dashboard freshness | The home snapshot loads once behind a fifteen-minute server cache. Only the header spot and the strategy ticker poll, every ten seconds. | `nifty_snapshot.py:33`; `web/src/main.js:429` |
| Recorder | **Never succeeded once.** Every invocation since deployment on 2026-09-03 fails PERMISSION_DENIED; there is no HTTP 200 in its logs; `gs://swayam-capital-options-data` is empty. Its service account holds only `logging.logWriter`. | Cloud Logging; `gcloud storage ls`; project IAM |
| Backups | No schedule exists. `swayam-dashboard-sa` has `storage.objectViewer` only, so it cannot write. `upload_to_gcs` returns False on failure and the caller ignores it. `restore_from_backup.py` restores nothing. | project IAM; `backup_service.py:125-157`; `restore_from_backup.py:37-69` |
| Monitoring | None. No uptime check and no alert policy exist. | `gcloud monitoring uptime list-configs` returns empty |
| Method files in production | Cloud Run reads `/app/src/swayam/data/method_files`, a build-time snapshot of three of the seven vault files. Vault edits do not reach the live app until a redeploy. Contents are currently identical. | Cloud Run environment; normalised diff |
| Local history | DuckDB `options_history` holds 36,998 rows and `nifty_daily_bars` holds 22, both ending **2026-09-03**. Realized volatility needs 20 bars and has 22, all stale. | DuckDB query |
| Tests | Backend **322 collected, 2 failing**. Frontend **109 passing**, with a real `rule-panel.js:35` `toFixed` error swallowed inside a green test. | `pytest`, `vitest run` |
| FYERS today | Token valid. Spot 23,779.15. `funds()`, `positions()`, `depth()`, multi-symbol `quotes()`, `optionchain()`, `history()` and `market_status()` all return 200. | live calls |
| Real market numbers | Average daily move 80 points; one standard deviation 82; two standard deviations 164; average overnight gap 46; largest gap 198; average day range 142 | `fyers.history()` over the last 21 sessions |

---

## 3. RELEASE PLAN — five gated releases

**Discipline.** Each release is a separate branch and a separate pull request. A release does not begin until the previous one has passed its exit gate. No release may be called complete without the evidence listed in Section 6.

### RELEASE 1 — Correct the money, lock the door, stop the lies

The most urgent release. Nothing else matters while every number is 15% wrong and the site is open to anyone.

**R1.1 Lot size becomes real, everywhere.**

- Add `get_lot_size(symbol)` to `src/swayam/services/expiry.py`, which already downloads and caches `NSE_FO.csv`, reading **column index 3** of the contract-master row. Cache it alongside the expiry cache.
- Delete every hardcoded 75 at `models_api.py:21,81`; `execution.py:49`; `positions.py:305,497`; `options_math/models.py:45`; `options_math/strategies.py:32,85,138`; and in the frontend leg builder.
- **A missing lot size must block the trade**, never fall back to a number.
- Backfill note: rows already written into `swayam_positions` with lot size 75 are wrong. Do **not** silently rewrite them. Write a separate one-off script, show Abhishek exactly what it will change, and let him run it.

**R1.2 Real broker margin replaces the invented figures.**

- Add `get_order_margin(legs)` to `src/swayam/fyers_client.py`, calling `POST https://api-t1.fyers.in/api/v3/multiorder/margin` with the header `Authorization: {client_id}:{access_token}`.
- Pin down the call shape that produces the correct hedge benefit before displaying anything, and check it against the FYERS web margin calculator for the same spread.
- Delete the Rs 32,000 and Rs 1,15,000 constants from `execution.py`. If the margin call fails, display **unavailable**, never an estimate.

**R1.3 Google sign-in.**

- `gcloud run services update swayam-dashboard --region asia-southeast1 --iap`
- Grant `roles/iap.httpsResourceAccessor` to `abhisheksikka99.99@gmail.com` and nobody else.
- Remove `allUsers` from the invoker policy and remove `--allow-unauthenticated` from `cloudbuild.yaml`.
- Narrow CORS in `main.py` from `["*"]` to `https://swayam.abhisheksikka.com`. The current wildcard combined with credentials is also invalid under the CORS specification.
- **Proof required:** an incognito browser and a raw request to both the custom domain and the `run.app` URL must be refused.

**R1.4 Readiness demoted to ceremonial (D7).**

- Delete Check 0 from `validation.py` entirely. No readiness read, no `size_cap_pct`, no `trading_allowed`, no verdict influence anywhere in the trade path.
- Keep the ritual, the meditation timer, the verdict card, the streak and the dots on Home as a journal.
- Add a visible line on the readiness card: this is your journal, it does not change your position size or block a trade.
- Record in `01 - Method/Operational Readiness Rules.md` that this is deliberate for the paper phase and must be revisited before real money.

**R1.5 Fail closed on everything a trade depends on.**

- Capital, realized volatility, live leg prices, expiry and lot size. Any one unavailable blocks validation and execution with a named reason. No bare `except: pass` anywhere in the trade path.

**R1.6 Remove the last fabricated values.**

| Location | Fabrication | Replace with |
|---|---|---|
| `nifty_snapshot.py:476` | `rollover_pct: 68.5` | remove, show unavailable |
| `expiry.py:146-165` | `_generate_fallback_tuesdays()` | remove, block and say the contract source is unreachable |
| `web/src/pages/home.js:179` | verdict defaults to GREEN | show unavailable |
| `web/src/components/mini-readiness-card.js:14` | verdict defaults to GO | show unavailable |
| `web/src/components/verdict-card.js:43` | verdict defaults to green | show unavailable |
| `mini-positions-list.js:26`, `strategy-builder.js:481` | unknown P&L defaults to zero | show unavailable |
| `macro-events-card.js:104` | invented impact text | show nothing |
| `strategy-builder.js:779` | `entry_premium: 35.0` in the add-hedge fix | fetch the real price or refuse to add the leg |
| `strategy-builder.js:584,604,663,708` | premium defaults to zero on execute | block execution when any leg has no real price |

**R1.7 Server-side kill switch.**

- New table `swayam_kill_switch` holding a single row with `halted`, `reason`, `set_by` and `set_at`, plus an audit table.
- Enforced in **every** write endpoint: execute, multi-leg, position close, journal, lessons, notebook, pinned, readiness and AI messages.
- Halted behaviour: new trades blocked at the backend; AI proposals unavailable; **closing a position stays allowed**; data keeps displaying, marked stale. Releasing the halt requires the signed-in owner, a written reason and an audit row.
- A prominent control in the header of both pages.

**R1.8 Test hygiene.**

- Fix `tests/api/test_market.py::test_get_option_chain_returns_strikes`, a stale option-chain double, and `tests/test_notifications.py::test_execute_endpoint_best_effort_dispatch_on_success`, a `ValueError: not enough values to unpack` at `execution.py:170`.
- Fix `web/src/components/rule-panel.js:35`, `toFixed of undefined`.
- Make any browser console error fail the frontend suite.
- Fix `web/public/service-worker.js:5-11`, which precaches `/src/main.js` and `/src/styles.css`, neither of which exists in the production build.

**Exit gate for Release 1:** both suites green with zero swallowed console errors; incognito and raw-URL access refused; a before-and-after table showing every rupee figure at lot 65 against lot 75; a real FYERS margin number shown beside the deleted constants.

### RELEASE 2 — The risk rule Abhishek actually wants

**R2.1 Capital from the broker (D3).**

- Add `get_funds()` to the FYERS client, reading `fund_limit` id 10, Available Balance, falling back to id 1, Total Balance. Today both read Rs 8,71,002.38.
- Cache with a source timestamp. Unavailable means blocked, never a stale or default number.
- Display the live broker balance on both pages with its timestamp.
- **Observation to raise with Abhishek, not to fix here:** his entire balance sits in `Collaterals` with `Clear Balance` at zero. Exchange rules generally require part of F&O margin in cash. This may block real orders later. Flagged, not actioned.

**R2.2 The new gate (D4, D5, D6).** Replace Checks 0, 1, 2 and 5 in `audit_strategy_rules` with:

| Gate | Rule | Behaviour |
|---|---|---|
| Primary | Loss at a two-standard-deviation adverse move, scaled for the holding period, at or under **1% of live capital** | hard block |
| Black-swan fuse | Absolute mathematical max loss at or under **5% of live capital** | hard block |
| Informational | Absolute max loss in rupees and as a percentage | displayed, never blocks |

- Sigma source: the standard deviation of close-to-close NIFTY returns over twenty sessions. Close-to-close already contains the overnight gap, which satisfies D5. Scale by the square root of the intended holding days.
- Show the arithmetic on screen so he can audit it, in this shape: NIFTY two standard deviations is 164 points; at 23,615 this position loses Rs 6,240; your 1% cap is Rs 8,710; pass.
- Fix the display bug at `web/src/components/rule-validation-panel.js:97,133`, which multiplies an already-percentage value by 100 and prints 62% where the truth is 0.62%.
- Remove the hardcoded demo value `pct_of_margin: 0.41` at `rule-validation-panel.js:23,30`.

**R2.3 Real hedge validation.** Replace "any sell leg counts" with a genuine per-leg check: every short leg must have a long leg of the same option type and the same expiry at a protective strike, with quantity at least equal. A short strangle must fail.

**R2.4 Method files updated, on his written instruction (D6, D7).**

- `01 - Method/Risk Management Rules.md`: the blast radius becomes **5%**, with his stated reasoning recorded and dated. The primary gate is restated as the two-standard-deviation test against 1%. Absolute max loss is demoted to informational.
- `01 - Method/Operational Readiness Rules.md`: readiness is ceremonial for the paper phase, with the revisit obligation recorded.
- **Both the vault copy and the baked copy under `src/swayam/data/method_files/` must be updated in the same pull request**, or production keeps the old rule.

**Exit gate for Release 2:** a table of at least six real strategies showing the loss at two standard deviations, the 1% cap, the 5% fuse and the verdict, computed at lot size 65 against the live broker balance; the previously blocked Rs 5,254 trade now passing; a short strangle correctly rejected.

### RELEASE 3 — The real cost of trading

**R3.1 Charges engine** at `src/swayam/services/charges.py`, applied on entry and on exit, per leg and per order:

| Charge | Rate | Applies to |
|---|---|---|
| Brokerage | Rs 20 per executed order, FYERS Standard (D8) | each order |
| STT | 0.15% of premium | sell side only |
| NSE transaction charges | 0.03503% of premium, Rs 35.03 per lakh | both sides |
| SEBI turnover fee | Rs 10 per crore | both sides |
| Stamp duty | 0.003% | buy side only |
| GST | 18% on brokerage plus transaction plus SEBI | both sides |

**Open item:** one public source quotes the NSE transaction charge as 0.03553% and another as 0.03503%. The difference is about fifty paise per lakh of premium. Pin the exact figure from the FYERS charge list before shipping, and record the source and date in the code.

- Use `Decimal` for all money arithmetic. The frontend displays what the backend computed and must not recompute in floating point.

**R3.2 Paper fill policy.**

- Buy legs fill at the **ask** and sell legs fill at the **bid**, both captured at the moment of execution with a source timestamp. This is the honest realistic case; the last traded price flatters the result.
- Refuse the fill when there is no real bid or ask. Never fill at zero.
- Record the policy, both prices, the timestamp and the full charge breakdown on the position.
- Show a charges breakdown on the execution ticket, as Sensibull does.

**Exit gate for Release 3:** a worked example, entry and exit, showing gross P&L, each charge line and net P&L, reconciled by hand against the FYERS brokerage calculator.

### RELEASE 4 — Strategy Builder to the Sensibull standard (D9, D10)

Split into 4a and 4b. Do not build both at once.

**4a, the what-if engine.** One recalculation path feeds every number, so nothing on screen can go stale.

- A NIFTY Target control: a slider plus a percentage plus an editable absolute value, with Reset.
- A Date control: a slider from today to expiry with previous and next arrows and a readable label such as "Mon, 7 Sep 3:40 PM", with Reset.
- Editable strikewise IV: per-strike IV with steppers, a global Offset stepper, and Reset IVs.
- Every change instantly recomputes max profit, max loss, breakeven, reward to risk, probability of profit, time value, intrinsic value, margin, greeks and both payoff curves.
- A projected P&L tag on the chart at the chosen target and date.

**4b, the metrics, the chart and the leg row.**

- Metrics strip: Max Profit, Max Loss, Breakeven with a target-versus-expiry toggle, Reward to Risk with the inversion toggle, Probability of Profit, Time Value, Intrinsic Value, and a Funds and Margins block reading **Funds Needed, Margin Needed and Margin Available from FYERS**, per R1.2.
- Payoff chart: the expiry curve and the target-date curve together; vertical bands at one and two standard deviations on both sides; the current price line; **open-interest bars from the real option chain behind the curves** on a second axis, with an Open Interest versus OI Change selector; and Zoom Out.
- Standard-deviation table: one and two standard deviations as points, as a percentage and as the resulting price on each side. Today one standard deviation is 82 points and two is 164.
- Greeks panel with the Multiply by Lot Size and Multiply by Number of Lots toggles.
- Target-day futures price.
- Leg row parity: buy or sell badge, expiry, strike stepper, CE or PE, lots, editable price with a refresh control, a per-leg menu and delete. Plus the **Shift**, **Width** and **Multiplier** steppers, which move all strikes together, widen or narrow the spread, and scale every leg's lots at once.
- Ready-made strategies grouped Bullish, Bearish, Neutral and Others, with payoff thumbnails.
- A price freshness line reading "Prices last updated at HH:MM" with a genuine thirty-second auto-refresh, replacing the current load-once behaviour.
- Execution stays on this page, with the charges breakdown and the margin figure beside the button.
- A P&L Table tab beside the payoff graph.

**Deliberately not copied from Sensibull:** it permits a naked short sell with unlimited loss. Swayam's Method forbids single-leg and unhedged positions, and that block stays.

**Exit gate for Release 4:** side-by-side screenshots of Swayam and the Sensibull reference for the same spread on the same expiry, with every listed number matching or the difference explained.

### RELEASE 5 — Make the data keep arriving

**R5.1 Fix the recorder (D11).**

- Grant the Cloud Scheduler identity `roles/run.invoker` on the `swayam-recorder` function and set an OIDC token on the job. This is the cause of every failure since 2026-09-03.
- Grant `roles/storage.objectCreator` on `gs://swayam-capital-options-data` to `swayam-recorder@swayam-capital.iam.gserviceaccount.com`, which currently holds only `logging.logWriter`.
- **Proof required:** a real object in the bucket carrying today's date, with a row count.
- Alert if no object has landed by 10:00 IST on a trading day.

**R5.2 Keep the local history current.** The nightly ingest into DuckDB has not run since 2026-09-03. Without it the volatility figure driving the whole risk gate goes stale. Re-establish it and display the age of the data on screen.

**R5.3 Backups that are real.**

- Grant the application service account write access to `gs://swayam-backups`.
- Make a failed upload fail the job. `upload_to_gcs` currently returns False and the caller ignores it.
- Include the schema in the dump, not only the INSERT statements.
- Write a restore that actually restores, into an isolated database, and run one drill recording row counts and elapsed time.
- Deploy the schedule and show the age of the last successful backup on screen.

**R5.4 Monitoring.** An uptime check on the terminal, an alert when the recorder fails, and an alert when the last backup is older than forty-eight hours. Telegram credentials already exist in Secret Manager.

**R5.5 Stale-data guard across both pages.** Every displayed market value carries its source and its source timestamp. Beyond a session-aware threshold the value is greyed and labelled STALE. New paper entries are blocked on stale or unknown data; closing a position stays allowed.

---

## 4. SMALL DEFECTS FOLDED IN (not the AI chapter)

- The AI cannot see the "So Far Today" summary Abhishek pays to generate. `assemble_context` in `src/swayam/ai/persona/trading_partner.py` never loads it. Inject the day's summary.
- The read-aloud Pause restarts after about a second. `tts-player.js` has no user-paused flag, so auto-play or a re-render overrides the pause.
- "So Far Today" has no read-aloud button.
- The production bundle is 5.2 MB because Plotly is bundled into it. Split it out.

---

## 5. EXPLICITLY OUT OF SCOPE

| Item | Why |
|---|---|
| The four AI learning loops | D12. Basics first. |
| Static egress IP | D2. Deferred to the real-money gate. |
| Wake alerts for his wife | D14. Parked by his own decision. |
| FYERS streaming WebSocket | Cannot import today because `pkg_resources` is missing, needs a shared-feed design across up to six processes, and a thirty-second refresh plus a stale guard solves his actual complaint. Revisit after Release 4. |
| Real-money execution | Stays code-blocked at HTTP 403. |
| Backtester, book ingestion, FII and DII flows, market breadth, US indices, GIFT Nifty | Later phases, or they need a paid source. |
| Rewriting existing position rows for the lot-size error | A separate script Abhishek runs himself, after seeing exactly what it changes. |

---

## 6. EVIDENCE REQUIRED FOR EVERY RELEASE

A release is not complete without all seven:

1. Files changed and migrations listed.
2. Test results with exact counts and **no ignored browser console errors**.
3. Desktop and mobile screenshots of both pages.
4. Live market-hours proof for anything touching data, or an explicitly labelled off-hours limitation.
5. **A before-and-after table for every displayed number that changed.**
6. Rollback instructions and the deployed commit id.
7. This document and the running-state document updated.

---

## 7. ORDER, AND WHY

1. **Release 1** first, because until the lot size is 65 and the margin is real, every other number is built on sand, and until the door is locked his personal data is on the open internet.
2. **Release 2** next, because it is the rule he actually trades by and it is currently blocking valid trades.
3. **Release 3** next, because paper results that ignore Rs 20 a leg and 0.15% STT will overstate his edge and teach him the wrong lesson.
4. **Release 4** after that, because it is the largest piece of work and it must sit on numbers that are already correct.
5. **Release 5** can run alongside 3 and 4, since it is infrastructure and touches no trade path. Start R5.1 early: every day the recorder stays broken is a day of market history that cannot be recovered.

---

*Nothing in this document is a claim of readiness. Real-money trading remains code-blocked. Written 2026-09-07 by Claude Code (Opus 5), for Abhishek's approval and for independent cross-check by Codex and Hermes.*
