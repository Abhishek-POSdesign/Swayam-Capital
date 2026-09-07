# 🛠️ SWAYAM — MASTER FIX PLAN v4 (Honest → Safe → Live) — FOR APPROVAL

> **STATUS: PROPOSED — NOT APPROVED, NOTHING BUILT.** v4 written 2026-09-07 by Claude Code (Opus 4.8) after checking the live Cloud networking (FYERS static-IP question) + the Codex path-assessment review. No app code changed by this planning work.
> **History:** v1 → v2 (Codex review) → v3 (my deep self-audit + real test runs) → **v4 (Cloud networking + FYERS static IP + Codex path assessment).** Each version found real things the last missed. I keep verifying; I do not call anything "ready".
> **Canonical:** this file (vault). Mirror: repo `docs/SWAYAM_PHASE_A_PLAN_2026-09-07.md`.
> **Phase 1 detailed; Phases 2–4 + Method track in brief.** **No unresolved "TBD" safety decisions** (login method now resolved — §4.A1.6).

---

## 0. Abhishek's priority (his words)
1. **No fake data. Anywhere. Ever.** Real from FYERS, or honest "unavailable / —". Never a placeholder shown as real.
2. **What is already built comes first** — finish + clean it.
3. **Real, live data** — all FYERS can give; real alternate source or honest blank for the rest.
4. **Paper stays paper** — real-money permanently code-blocked. Paper is the trust gate.
5. Data honesty > UI polish.

---

## 1. What I verified MYSELF (evidence, not claims)

### Round 1 (live infra + code)
| # | Finding | Proof |
|---|---|---|
| 1 | **App is PUBLIC** (no login/IAP). | Live Cloud Run IAM: `allUsers → roles/run.invoker`; `cloudbuild.yaml:28`; CORS `["*"]`+credentials `main.py:21`. |
| 2 | **RLS OFF on all 19 `swayam_*` tables**, 0 policies. | Live SQL on Supabase `wxijlrwoiaeaupaaqecc`. Public app + service key ⇒ anyone can read/write all data. |
| 3 | **Backups falsely report success; restore never restores.** | `backup_service.py` (180-182/243/297); `restore_from_backup.py:37-69` validates + returns True, runs no restore. |
| 4 | **Fake rollover 68.5; invented Tuesday expiries.** | `nifty_snapshot.py:476`; `expiry.py:146-165`. |
| 5 | **WebSocket dead AND unusable as built** (2 gunicorn workers × ≤3 instances = ≤6 processes; in-memory manager can't fan out). | `ws_manager.py:29,54` zero callers; `Dockerfile:38`; `cloudbuild.yaml`. |
| 6 | **Paper "fill" = entered premium** (no fill policy/slippage/charges); **order-preview margin hardcoded** ₹32k/₹115k. | `execution.py:51,59-61,86-90`. |
| 7 | **Token can't be continuously auto-refreshed** (SEBI Apr-2026: static IP + daily 2FA + no continuous refresh). | [FYERS notice](https://fyers.in/notice-board/new-sebi-framework-for-retail-algo-trading-from-april-01-2026/). |
| + | Good: real exec 403-blocked; margin/vol/rules fail LOUD (503); no secrets committed (.env gitignored). | `execution.py:110-114,207-251`; `validation.py:47-79`; `git ls-files`. |

### Round 2 (deep self-audit + REAL test runs) — new, beyond all three prior audits
| # | Finding | Proof |
|---|---|---|
| 8 | **Safety gate fails open THREE ways**, not one: (a) `except: pass`; (b) **no readiness row today** → whole gate skipped; (c) `trading_allowed` defaults **True** if field missing. "Forgot to log readiness" ⇒ full-size trade allowed. | `validation.py:96-113` (esp. `if res.data:` L99, `.get("trading_allowed", True)` L101). |
| 9 | **UI-layer fakes / fail-opens** (frontend, missed by backend-only audits): home verdict defaults **`|| 'GREEN'`** (missing verdict shows tradeable); position P&L **`|| 0`** (unknown P&L shows ₹0, not "unavailable"); macro **`impact_brief || 'High volatility…'`** (fabricated text). | `home.js:179`; `mini-positions-list.js:26`, `strategy-builder.js:481`; `macro-events-card.js:104,80`. |
| 10 | **Execute accepts ₹0-premium legs** — a leg with no real price sends `entry_premium || 0` and can be recorded as a real paper fill. | `strategy-builder.js:584,604,663,708` → `execution.py`. |
| 11 | **Hedge check is trivial** (any one sell leg = "hedged"; no strike/expiry/qty match). Blast-radius (Check 2) + overnight (Check 5) gate on **absolute max loss** — contradicts your "σ-only" wish. | `validation.py:184-206`. |
| 12 | **Test suite NOT clean** (ran both today): backend **320 pass / 2 FAIL** of 322 (not "~400") — one on the **execute path** (`execution.py:170` unpack error), one stale option-chain double; frontend **109 pass** but a real `rule-panel.js:35 toFixed` browser error is **swallowed inside a passing nav test**. | `pytest` + `vitest` output 2026-09-07. |
| 13 | **Service worker precaches dev paths** (`/src/main.js`, `/src/styles.css`) absent from the prod build ⇒ offline caching silently broken; `CACHE_NAME` never bumped. | `web/public/service-worker.js:5-11`. |
| + | Good: backend position P&L computes on-demand and **503s honestly** when the chain is unreachable (the DEAD part is only the streaming socket); AI file-context degrades to honest "(not available)" strings, not fake numbers. | `positions.py:108-131`; `trading_partner.py:155-265`. |

### Round 3 (Cloud networking + FYERS static IP)
| # | Finding | Proof |
|---|---|---|
| 14 | **No static egress IP.** Cloud Run has **no VPC connector / no pinned egress**, and **Compute Engine API + Serverless VPC Access API are DISABLED** on the project — so the app calls FYERS from Google's **rotating IPs**, not the **Airtel home IP** whitelisted in the FYERS app. Harmless for data today (static-IP rule is order-scoped) but **wrong config** and a **blocker for any real-order future**. | Live `run services describe` (no `vpc-access-*` annotations); `compute`/`vpcaccess` APIs `SERVICE_DISABLED`. |

---

## 2. What I got WRONG / MISSED in my own earlier plans (owning it)
- **v1:** promised **token auto-refresh** — not compliant (finding #7). Corrected to a **daily one-tap auth + status light**.
- **v2:** my "fail closed" only covered the `except: pass`. It **missed the missing-row and default-True fail-opens** (#8). Corrected below.
- **v2:** focused on backend fakes; **missed the UI-layer fakes/fail-opens** (#9, #10). Added to Phase 1.
- **In chat I twice repeated "~400 tests" from the docs without running them.** Ground truth is **322 backend (2 failing) + 109 frontend with a swallowed error** (#12). Corrected.
- Earlier docs called "live position P&L dead" flatly; more precisely, **streaming is dead but a REST P&L path works and 503s honestly** — the honesty gap is the **frontend `|| 0`** (#9), which I'll fix.
- **v1–v3:** I treated the **FYERS static IP** as a fact to *capture*, not a task to *do* (#14) — reasoning it only bites on real orders. Too passive: the Airtel-IP whitelist is wrong for a cloud app and it's cheap to fix now. Promoted to a concrete Phase-1 task (§4.A1.6b).

---

## 3. Delivery order & discipline
**PHASE 1** (detailed) = Freeze/Prove + Safety/Ownership/Honesty. **PHASE 2** Data-Truth Contract. **PHASE 3** Resilient Live Data (true frozen-dashboard fix). **PHASE 4** Paper maturity. **METHOD TRACK** separate. **Real-money code-blocked throughout.**
> Maps to Codex's stages: Phase 1 = **Stage 0 (establish truth) + Stage 1 (make paper safe)**; Phase 2 = **Stage 2 (every number explains itself)**; Phase 3 = **Stage 3 (live, carefully)**; Phase 4 = **Stage 4 (earn the trust gate)**.
> **Discipline (Codex path assessment):** this is **NOT a broad feature sprint**. Each release is a **small, gated change** — it does not start until the previous one clears the §6 release gate. Phase 3 is itself split into separate programmes (data transport → risk policy → paper accounting), never one big build. **The very next deliverable is the detailed Stage-0/Stage-1 plan with zero TBD safety decisions — not code.**

> **Frozen dashboard:** proper fix = Phase 3 (needs the shared-feed plumbing; rushing it on the broken socket is how Monday happened). **Phase 2 gives an honest interim** (short cache + real polling), never fabricated.

---

## 4. PHASE 1 — DETAIL (Freeze, Prove & Make Safe/Private/Honest)

### A0 — Freeze & Prove (no feature code; a factual runbook)
Capture the real live state (much already gathered above): deployed commit + Cloud Run config + IAM; secrets list; Supabase schema + RLS; cron/scheduler reality; FYERS app mode + static-IP + token lifecycle; backup status. Decide on paper the login method + the streaming architecture. **Exit gate: a signed evidence sheet (facts + proof), not a narrative.**

### A1 — Safety, Ownership & Honesty (the fixes)
1. **Kill remaining fakes in trade paths:** remove rollover `68.5`; remove Tuesday-expiry guessing (block/"unavailable" instead).
2. **Kill UI-layer fakes/fail-opens (#9, #10):** no data value may fall back to a fabricated default — remove verdict `|| 'GREEN'` (missing verdict ⇒ block, not tradeable), position P&L `|| 0` (⇒ "unavailable"), macro `impact_brief` fabricated text; **block execute when any leg lacks a real price** (no ₹0-premium fills).
3. **Fail CLOSED — all three ways (#8):** require a readiness row for today AND explicit `trading_allowed = True` AND a present size cap; any DB/read error or missing data **blocks** the trade. No `except: pass`, no default-True.
4. **Server-side kill switch** — DB-backed, audited global halt enforced in **every write endpoint** (execute, multi-leg, position close, journal, lessons, notebook, pinned, readiness, ai-messages):

   | Action | When halted |
   |---|---|
   | New paper trade / execute | **Blocked at backend** |
   | AI trade proposal | Unavailable / no action |
   | Data display | Continues, visibly stale |
   | Position close / risk reduction | **Allowed** |
   | Un-halt | Authenticated owner + reason + audit record |

5. **Keep real execution impossible** (already 403) + regression tests proving it.
6. **Lock the door (main objective) — access method RESOLVED (no TBD):**
   - **(a) Login:** put the site behind an **external HTTPS Load Balancer + Identity-Aware Proxy (IAP)**, allowing only Abhishek's Google account. This is my firm recommendation: Google-managed login, **no passwords in the app**, and the raw Cloud Run URL is fenced off. *Fallback if he prefers less setup:* a single app-level password + secure session — faster, but the Cloud Run URL stays publicly reachable, so IAP is the honest choice. **Then revoke `allUsers`**, tighten CORS to the real origin (the current `*`+credentials combo is also invalid), least-priv service account, no browser-held creds, reconcile RLS-off vs single-user model, and **prove the direct Cloud Run URL can't bypass** the login.
   - **(b) FYERS static egress IP (#14):** enable Compute + Serverless-VPC-Access APIs; reserve a static external IP (asia-southeast1); add a VPC connector + Cloud NAT so all Cloud Run egress leaves from that one IP; **whitelist that IP in the FYERS app and remove the Airtel IP**; verify outbound calls now originate from it. (~few-hundred ₹/mo — flag cost before doing. Not required for paper data today, but corrects a wrong config and is prerequisite for any real-order future. Real orders stay blocked.)
7. **Real backups + recovery:** fail the job on upload/integrity failure; encrypt + checksum + version + timestamp; implement a **real restore into an isolated test DB**; run **one restore drill** (record row counts, AI memory, elapsed); surface last-backup-age + last-restore-date; deploy the backup cron.
8. **Clean the tests (#12, #13):** fix the 2 failing backend tests (execute-path unpack + stale option-chain double); make the swallowed `rule-panel.js toFixed` browser error **fail** the test; fix the service-worker precache paths. Anti-fake **lint** as a supplementary guard; begin the data-quality contract on trade-critical fields (spot, legs, expiry) so an unavailable source can never emit a number and expiry can never be heuristic.

**Phase-1 exit gate:** clean build; **backend + frontend suites green with zero swallowed browser errors**; browser E2E; **security proof** (incognito/direct-URL can't open); **restore-drill evidence**; before/after table for every changed number.

---

## 5. PHASES 2–4 + METHOD TRACK (brief)

**PHASE 2 — Data-Truth Contract.** Common metadata on **every** Home/Strategy value: `value, source, source_timestamp, received_timestamp, market_session, quality (LIVE/DELAYED/PREVIOUS_SESSION/CALCULATED/UNAVAILABLE), reason`. Frontend rule: **never** `|| <default>` on a data value. Session-aware freshness. **Terminal health strip** (broker auth, feed age, DB, recorder, backup age, deployed commit). Define approved **trading-allocation risk base** (shown beside FYERS funds, not overwriting) + **paper-fill policy** (LTP/mid + slippage + charges). **Honest interim de-freeze** (short cache + poll). *Exit: forced outage ⇒ unavailable/stale, never a number, never a new entry on bad data.*

**PHASE 3 — Resilient Live Data.** Shared FYERS feed architecture FIRST (one feed owner + Pub/Sub or Redis across the ≤6 processes + quote store w/ timestamps/seq/session). Stream only essentials (NIFTY spot, active legs, open positions — wiring the currently-dead position stream). REST fallback + circuit breaker + quota. **Daily one-tap FYERS auth + status.** FII/DII + breadth only after named source + usage + cache + failure policy. *Exit: several market-hours sessions with latency/reconnect/outage tests; no paper entry on stale/unknown data.* **True frozen-dashboard fix.**

**PHASE 4 — Paper Maturity.** Run paper with documented fill policy + daily-auth status + reconciliation vs FYERS for a set period; review every mismatch. Only then revisit Method changes / real-money.

**METHOD TRACK (separate, your sign-off each).** 0.3%-GREEN throttle; **σ-only vs absolute-max** (Check 2/5, #11); overnight sigma; trivial hedge check (#11) → real per-leg hedge validation. The **62%↔0.62% display** is a pure frontend bug (backend returns correct percent) — fixable as a defect; the sizing-policy items need your written rule + scenarios + versioned Method file + before/after tests.

---

## 6. Acceptance criteria for EVERY build (reject unless all present)
1. Changed files + migrations. 2. Test results, exact counts, **no ignored browser console errors**. 3. Desktop + mobile screenshots. 4. **Live market-hours proof** for feed changes (or labelled off-hours). 5. **Before/after table for every displayed number changed.** 6. Rollback + deployed commit id. 7. Updated runbook + handover.

---

## 7. Open decisions I need from you
1. **Login method** — my firm recommendation is **IAP** (§4.A1.6a); confirm, or pick the app-password fallback.
2. **Static egress IP** — OK to enable the two APIs + reserve IP + Cloud NAT (~few-hundred ₹/mo) and re-whitelist FYERS with it (removing Airtel)? (§4.A1.6b)
3. **Phase order** — foundation (Phase 1) before true streaming (Phase 3), with the Phase-2 interim de-freeze. OK?
4. **Trading-allocation number** (your ₹8.5L?) shown beside real FYERS funds.
5. **Paper-fill policy** — I'll recommend (mid or LTP + modelled charges).
6. **Working window** — market hours (live proof) vs off-hours (previous-close proof).

---

*Nothing built. On your "go", next is the detailed **Phase-1** build plan (plain-English, pre-code), then a feature branch + PR you merge. I will not call anything ready without showing you the proof. Real-money stays blocked.*
