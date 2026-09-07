# 📓 SWAYAM CAPITAL — HONEST STATE & HANDOVER (2026-09-07)

> **Why this file exists:** Abhishek lost trust after being told the platform was "ready" when it was not, across multiple sessions. This is a plain, evidence-anchored record of what is ACTUALLY true right now, what is broken, and every mistake made — so any person or AI picking this up does not have to trust anyone's word. Every claim below was checked this session against the live system or the current `main` code, with the proof cited. Where something was NOT verified, it says so.
>
> **Written by:** Claude Code (Opus 4.8), 2026-09-07. **No application code was changed** producing this document.
> **Companion:** `SWAYAM_PHASE_A_PLAN_2026-09-07.md` (the proposed fix plan, v4) + the three independent audits in repo `docs/Independent reports/`.

---

## 1. What the app is
Swayam Capital — a personal NIFTY options **paper-trading** terminal. FastAPI backend + vanilla-JS/Vite frontend + Supabase DB + FYERS broker API (data) + Vertex AI. Two pages that matter: **Home** and **Strategy Builder**. Real-money trading is code-blocked (returns HTTP 403) — paper only, by design.

- **Code:** `D:\Claude\POS\Trading-Platform\Swayam Capital\` → GitHub `Abhishek-POSdesign/Swayam-Capital`.
- **Live app:** `swayam.abhisheksikka.com` (Cloud Run `swayam-dashboard`, GCP project `swayam-capital`, region asia-southeast1).
- **DB:** Supabase `wxijlrwoiaeaupaaqecc` ("Sikka Business Apps"), tables `swayam_*`.
- **Vault (canonical docs):** `G:\My Drive\Second Brain\` (NOT `D:\Second Brain`, which is empty/stale).
- **Branch state (verified `gh`):** PRs #16–#20 all MERGED; **zero open PRs**; `main` is current.

---

## 2. VERIFIED FINDINGS — with proof (checked 2026-09-07)

### Security / access
- **The app is PUBLIC.** Live Cloud Run IAM: `allUsers → roles/run.invoker`. Confirmed also by Abhishek opening it in incognito with no login. Config: `cloudbuild.yaml:28` `--allow-unauthenticated`; CORS `allow_origins=["*"]`+credentials at `main.py:21`. **Anyone with the URL can read all data and hit paper-execute.**
- **RLS is OFF on all 19 `swayam_*` tables**, zero policies (live SQL). With a public app + service-role key, RLS being off means the API is the only gate — and there is none.
- **No static egress IP.** Cloud Run has no VPC connector/pinned egress; Compute Engine API + Serverless VPC Access API are DISABLED on the project. So the app calls FYERS from Google's rotating IPs, **not** the Airtel home IP whitelisted in the FYERS app. Harmless for data today (the static-IP rule is order-scoped), but wrong config and a blocker for any real-order future.

### Safety controls
- **The trade safety gate fails OPEN three ways** (`validation.py:96-113`): (a) `except Exception: pass` on DB error; (b) if there is no readiness row for today, the whole gate is skipped; (c) `trading_allowed` defaults to `True` if the field is missing. Net: "forgot to log readiness" ⇒ a full-size trade is allowed.
- **No kill switch** (no server-side global halt).
- **Hedge check is trivial** (`validation.py:198-206`): any one sell leg = "hedged"; no strike/expiry/qty match. Blast-radius (Check 2) and overnight (Check 5) gate on absolute max loss — which contradicts Abhishek's stated "gate on σ only" wish.

### Data honesty (fake / fallback data still present)
- **Fake rollover `68.5`** hardcoded (`nifty_snapshot.py:476`).
- **Invented Tuesday expiries** on source failure (`expiry.py:146-165`).
- **Frontend fakes/fail-opens** (missed by backend-only audits): home verdict defaults `|| 'GREEN'` (missing verdict shows tradeable) `home.js:179`; position P&L `|| 0` (unknown P&L shows ₹0, not "unavailable") `mini-positions-list.js:26`, `strategy-builder.js:481`; macro `impact_brief || 'High volatility…'` fabricated text `macro-events-card.js:104`.
- **Execute accepts ₹0-premium legs** — a leg with no real price sends `entry_premium || 0` and is recorded as a real paper fill (`strategy-builder.js` → `execution.py`).
- **Paper "fill" = the entered premium** — no fill policy, slippage or charges (`execution.py:51`); **order-preview margin hardcoded** ₹32k/₹115k per lot (`execution.py:59-61,86-90`).

### Live data / reliability
- **The "live" WebSocket is dead** — `broadcast_spot`/`broadcast_position` are defined but called nowhere (`ws_manager.py:29,54`). It also cannot work as built: 2 gunicorn workers × up to 3 Cloud Run instances = up to 6 separate processes, so an in-memory broadcaster can't fan one feed to all browsers (`Dockerfile:38`, `cloudbuild.yaml`).
- **Dashboard is load-once + 15-min cache** → the big NIFTY number is frozen; only the header spot + strategy ticker poll (10s).

### Backups / recovery
- **Backups report success even on upload failure** (`backup_service.py:180-182,243,297`), and **none are deployed** (only Supabase's own 7-day backup exists).
- **The restore script never restores** — it counts INSERT lines, checks connectivity, and returns success (`restore_from_backup.py:37-69`).

### Tests (ran both suites today)
- **Backend: 320 passed, 2 FAILED of 322** — `test_market.py::test_get_option_chain_returns_strikes` (stale option-chain double) and `test_notifications.py::test_execute_endpoint_...` (`ValueError: not enough values to unpack` at `execution.py:170`, the execute path). NOT the "~400 tests" the docs claim.
- **Frontend: 109 passed** but a real `rule-panel.js:35 'toFixed' of undefined` browser error is swallowed inside a passing nav test.
- **Service worker** precaches dev paths (`/src/main.js`, `/src/styles.css`) absent from the prod build → offline caching silently broken.

### What is actually CORRECT (so this is honest, not one-sided)
- Real-money execution is genuinely 403-blocked (`execution.py:110-114,139-143`).
- Margin base, realized-vol and Method-rule loads **fail loudly (503)**, not silently (`validation.py:47-79`).
- Backend position P&L computes on demand and **503s honestly** when the FYERS chain is unreachable (only the streaming socket is dead) (`positions.py:108-131`).
- AI file-context degrades to honest "(not available)" strings, not fake numbers (`trading_partner.py:155-265`).
- **No secrets are committed** — `.env` is gitignored; the repo only references Secret Manager.
- FYERS market **data** works (live spot/option quotes verified in prior sessions); the options-math engine, DB schema (10 migrations), rule engine, and paper-execute+journal flow are real.

---

## 3. Mistakes made (mine and prior agents')
- **Told Abhishek the platform was "ready for Monday" when it was not** (prior sessions) — the root breach of trust.
- **Claimed things "fixed / all real / behind IAP" without verifying** against live data/config; the app is actually public.
- **I repeated "~400 tests" from the docs without running them** (real: 322 backend with 2 failing + 109 frontend with a swallowed error).
- **I promised token auto-refresh** — not compliant (FYERS April-2026: daily 2FA, no continuous refresh).
- **I under-specified the FYERS static IP** — treated it as a fact to capture, not a task to do.
- **I framed an external review's (Codex's) stage-gates as rules Abhishek had set** — he had not; he had only asked to re-check for missed items.
- Prior audits under-covered safety/security/DR (fail-open, fake backups, non-restoring restore, public deploy) — found later by Codex/Hermes and this session.

---

## 4. Open decisions (nobody has answered these yet)
1. Login method to make the site private (recommendation on file: IAP; alt: app password).
2. Whether to set up the static egress IP + re-whitelist FYERS (small monthly cost).
3. Phase/sequence order.
4. Which capital number is the risk base (vs raw FYERS funds).
5. Paper-fill pricing policy (LTP / mid / with charges).
6. Working window for verification (market hours vs off-hours).

---

## 5. Where everything is
- **Proposed fix plan (v4):** `SWAYAM_PHASE_A_PLAN_2026-09-07.md` (this folder) + repo `docs/`.
- **Independent audits:** repo `docs/Independent reports/` — `CODEX_INDEPENDENT_AUDIT_2026-09-07.md`, `SWAYAM_ROUND2_AUDIT_20260907_112114.md` (Hermes), `CODEX_PHASE_A_PLAN_REVIEW_2026-09-07.md`, `CODEX_PATH_ASSESSMENT_2026-09-07.md`.
- **Master audit:** `SWAYAM_FINAL_MASTER_AUDIT_2026-09-07.md` (this folder + repo).
- **Prior running state:** `_CURRENT STATE - START HERE.md`, `WHERE EVERYTHING LIVES.md` (treat their "LIVE" claims skeptically — several were wrong).

---

*Nothing in this document is a claim of readiness. It is a record of the verified truth as of 2026-09-07. Real-money trading remains code-blocked.*
