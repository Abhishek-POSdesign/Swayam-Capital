
> # ⚠ READ THIS FIRST: `docs/SWAYAM_START_HERE_2026-09-09.md`
>
> That file supersedes anything below it that disagrees. It carries the verified
> state as of 2026-09-08, how Supabase, Google Cloud and Google Drive are
> actually wired, the document map, and the complete list of what is NOT done.
>
> Abhishek's trading rules are `docs/MY_TRADING_RULES_ONE_PAGE.md`. Those rules
> override every plan document, including plan v9.
> # ⛔ CORRECTION NOTICE — 2026-09-07, 18:30 IST
>
> **Everything written in this file BEFORE 2026-09-07 contained statements that were NOT TRUE.** They were written from intention, from a build report, or from another document — not from checking the running system. Abhishek trusted them, planned around them, and arrived at his desk to find the platform not working. That is the direct cost of the false lines below.
>
> On 2026-09-07 Claude Code (Opus 5) checked every infrastructure and status claim in this file against the live Google Cloud project, the live Supabase database, the live FYERS account, the deployed Cloud Run service and a real run of both test suites. The corrections are applied inline below, and the specific false statements are listed here so nobody repeats them.
>
> **What was wrong before this date:**
>
> | Claim that was written | The verified truth on 2026-09-07 |
> |---|---|
> | "Behind IAP", "private login", "IAM invoker restricted to abhisheksikka99.99@gmail.com" | **FALSE. The site is PUBLIC.** Live Cloud Run IAM on `swayam-dashboard` is `allUsers -> roles/run.invoker`. Proved by anonymous request: `/api/nifty/spot`, `/api/positions` and `/api/readiness/today` all return 200 with no credentials, and `/api/readiness/today` serves Abhishek's sleep, mood and stress notes to the open internet. `cloudbuild.yaml` deploys with `--allow-unauthenticated` and the API sets CORS `allow_origins=["*"]`. |
> | "Options recorder runs every minute during market hours / recorder is LIVE" | **FALSE. It has never succeeded once.** Since deployment on 2026-09-03 every scheduled invocation returns PERMISSION_DENIED because the Cloud Scheduler identity has no `run.invoker` on the function. Zero HTTP 200 in its entire log history. The destination bucket `gs://swayam-capital-options-data` is EMPTY. Second fault behind the first: the `swayam-recorder` service account holds only `logging.logWriter`, so it could not write to storage even if it were reached. |
> | "Backups LIVE / durable automated multi-destination backup pipeline" | **FALSE.** No backup schedule exists in any region. `gs://swayam-backups` holds one manual run from 2026-09-05 and nothing since. The backup code also cannot succeed if deployed: `swayam-dashboard-sa` has `storage.objectViewer` only, with no write permission, and `upload_to_gcs` returns `False` on failure while the calling job ignores that and still returns success. |
> | "Restore from backup: automated one-command script" | **FALSE.** `scripts/restore_from_backup.py` counts INSERT lines, pings the database and returns success. It executes no restore. The SQL dump is also data-only with no schema, so it could not rebuild an empty project. |
> | "The rule engine reads Method files from the vault at runtime — vault edits become new runtime behaviour without code changes" | **FALSE in production.** Cloud Run runs with `TRADING_METHOD_PATH=/app/src/swayam/data/method_files`, a build-time copy baked into the container, holding only 3 of the 7 Method files in the vault. Editing rules in Obsidian changes nothing on the live site until a rebuild and redeploy. It is true only on Abhishek's local machine. |
> | "Cloud Run service `swayam-web`" | **WRONG NAME.** The deployed service is `swayam-dashboard` in `asia-southeast1`. There is no `swayam-web`. |
> | "Cloud Functions `cron_notifications`, `cron_macro_refresh`, `cron_email_digest`, `cron_backup_db`, `cron_backup_weekly_zip`, `cron_backup_ai_chat`" | **NOT DEPLOYED.** The only Cloud Function that exists in the project is `swayam-recorder` (asia-south1). The only two Cloud Scheduler jobs that exist are `swayam-ai-compaction` (working) and `swayam-recorder-schedule` (failing, above). |
> | Secrets list naming `fcm-server-key`, `vapid-public-key`, `vapid-private-key`, `trading-economics-api-key`, `cron-shared-secret`, `gemini-api-key` | **DO NOT EXIST.** Secret Manager holds exactly 11 secrets: the four FYERS ones, the three Supabase ones, `telegram-bot-token`, `telegram-chat-id`, `gmail-app-password`, `gmail-sender-address`. |
> | "153 automated tests passing (51 pytest + 102 vitest, 0 failures)" / "327 backend" / "~400 tests" | **ALL WRONG.** Verified by running them on 2026-09-07: backend collects **322**, of which **2 FAIL** (`tests/api/test_market.py::test_get_option_chain_returns_strikes` returns 503 not 200, and `tests/test_notifications.py::test_execute_endpoint_best_effort_dispatch_on_success`). Frontend is **109 passing**, but a real browser error, `rule-panel.js:35 Cannot read properties of undefined (reading 'toFixed')`, is printed and swallowed inside a test that still reports green. |
> | "Ready for live paper trading on Monday Sep 8, 2026" | **NOT TRUE and must not be repeated.** The safety gate fails open three separate ways, fabricated numbers still sit in trade paths, the site is public, there is no working backup, and no kill switch exists. |
> | "GCS bucket `swayam-capital-options-data` populated nightly / DuckDB populated nightly from GCS Parquet" | **FALSE.** The bucket is empty. The local DuckDB rows (36,998 option rows, 22 daily bars) came from a one-off historical backfill and stop at **2026-09-03**. The realized-volatility risk gate needs 20 daily bars and has 22, all stale. |
>
> **Standing rule from this date forward.** Nothing in this file may be written as LIVE, done, working, deployed or passing unless the writer checked it on the running system that same day and can name the command or query that proved it. Write the date of the check next to the claim. If it was not checked, write "not verified". A build report is not evidence. Another document is not evidence.


---

# CLAUDE.md — Swayam Capital (Claude Code's operating brief)

> This is Claude's counterpart to `GEMINI.md`. It auto-loads whenever Claude Code opens this repo. Its job: get me oriented and current in one read so I never re-derive context or relitigate settled decisions. **Keep it honest — update it at the end of any session that changes state, PR count, locked decisions, or file locations.**
>
> **Last updated:** 2026-09-07 (evening) by Claude Code (Opus 5) — every infrastructure claim re-verified against the live system. See the CORRECTION NOTICE at the top of this file for what was false before this date.

---

## 0. First actions in any Swayam session (read in this order)

The **vault** (`G:\My Drive\Second Brain\02 - Projects\Trading\` + `00 - Developer Logs\`) is the source of truth for *thinking*; this repo is the *code*. Before touching code, read:

1. `G:\My Drive\Second Brain\00 - Developer Logs\SESSION_STATE_<latest>.md` — where things stand right now.
2. `G:\My Drive\Second Brain\02 - Projects\Trading\WHERE EVERYTHING LIVES.md` — the map (locations, repos, secrets, buckets, authority).
3. `06 - Platform Plan\Platform Overview.md`, `Home Page v2 Plan.md`, `AI Trading Partner Chapter.md` — design + AI + memory.
4. The Method files in `01 - Method\` before writing any trade-entry logic.

Abhishek is **non-technical**. Write to him in plain English, never hand him code to approve, give a recommendation not a menu. **Plan first in plain English (6-part), build, then hand off structured (5-part)** — per his global `CLAUDE.md` and the `/layman-plan` + `/handoff` skills.

---

## 1. What Swayam Capital is

Abhishek's own NIFTY F&O trading platform ("my terms, my rules"). A rule-enforcing terminal + journal + (future) backtester for **positional/swing** options trades — NOT a scanner, NOT a signal service, NOT autonomous. He is an **afternoon trader** (arrives desk 1–2 PM IST), ~1–2 swing trades/week. **Paper trading has NOT safely started. Verified 2026-09-07: the safety gate fails open, the site is public, fabricated numbers remain in trade paths, there is no kill switch and no working backup.** Real capital is rules-proven, not date-driven (post-Diwali earliest).

- **Live:** https://swayam.abhisheksikka.com (Cloud Run service `swayam-dashboard`, `asia-southeast1`). **PUBLIC — no login of any kind. Verified 2026-09-07: IAM is `allUsers -> roles/run.invoker` and anonymous requests to the API succeed.** Locking this down is Priority 0.
- **Stack:** Python 3.11 FastAPI backend (`src/`), Vite vanilla-ESM + Plotly frontend (`web/`), Supabase (`swayam_*` tables), Vertex AI Gemini (3.1 Pro Preview → 2.5 Pro → 2.5 Flash-Lite), FYERS API v3 (broker, Phase 2).

## 2. ⚠️ TWO SEPARATE GitHub repos — never confuse PR numbers

- **App code (this repo):** `Abhishek-POSdesign/Swayam-Capital` — PR-based workflow. **All PR numbers ("PR #13") refer ONLY to this repo.**
- **Second Brain vault:** `Abhishek-POSdesign/Obsidian-second-brain-` — a plain nightly **encrypted backup**, **zero pull requests**.

If a "PR #N" link opens the vault repo, it's the wrong repo. This mix-up cost real confusion on 2026-09-06. **Always give the full PR URL and name the repo** in any handoff.

## 3. Current state (verified 2026-09-06 late)

- `main` = `b8b7f7f` (verified 2026-09-07). **PRs #10 through #20 all merged; zero open PRs.** Earlier note said `e6ec371` / PR #14, now superseded. #15–#16 Strategy Builder v2, #17 AI voice panel, #18 AI panel header, #19 real prices + home no-fake sweep, #20 compact leg card + live-spot strikes. #10 = Home Page v2 (BUILDs 11.6–11.12); #11 = typography/mobile/real macro; #12 = app icons/mobile polish; #13 = strategy mobile stacking, emerald chat, sector strip; #14 = docs refresh.
- **Tests (RUN, not collected, on 2026-09-07):** backend **322 collected, 2 FAILING**; frontend **109 passing but with a swallowed `rule-panel.js:35` browser error inside a green test**. Earlier figures of 51, 102, 153, 290, 327 and "~400" were all wrong. Never quote a test count you did not run today.
- **Gated on Abhishek's manual secrets** (none block Monday): Telegram token/chat-id, Firebase VAPID + FCM key, Trading Economics API key, Gmail app password + sender. Backup pipeline + macro ingest are code-shipped.
- **Next session:** **Strategy Builder page 2 redesign**, built directly by Claude Code (Antigravity's weekly budget spent ~4 days; refreshes ~2026-09-10). Then Trade Journal page 3.

## 4. Queued fixes (do on a branch → PR for his 1-click)

1. **Sector-rotation silent fallback** — `src/swayam/services/nifty_snapshot.py` shows hardcoded constants (BANK +0.42%, IT −0.65%, …) under a "PREVIOUS SESSION" badge when the market is closed. Fake data under a real-looking badge. Fetch genuine prior-session values or badge as explicit placeholder.
2. **`GEMINI.md` test scorecard** — fix the internal contradiction (says "258 backend" and "51 backend"); state the real 327. Update the vault mirror of GEMINI.md in the same pass.
3. **Add two rules to `GEMINI.md`:** (a) report the FULL test suite, never a partial as "all passing"; (b) never ship hardcoded market values behind a LIVE/CALCULATED/PREVIOUS SESSION badge.
4. **Design debts:** macro card text contrast (`web/src/components/macro-events-card.js`); purple side rail (`web/src/pages/strategy.js`, `web/src/styles.css`) — the side rail is absorbed into the Strategy Builder redesign.
5. **Park local `main`** back to origin (repo is often left on a feature branch after Antigravity sessions).

## 5. Locked decisions — do NOT relitigate

- **Afternoon-trader design:** hero is "So Far Today", not a morning brief. No 09:15 engagement assumptions.
- **Cost gate:** every AI-heavy feature is manual-button + 60-min cache + daily cap. **Never auto-fire on page load.** The only scheduled Gemini call is the *weekly* Sunday macro curation.
- **Freshness badges** (LIVE / CALCULATED / PREVIOUS SESSION / STALE) mandatory per data point. Never present static/fake data under a live-looking badge.
- **FII/DII:** cash and F&O always separate rows, never one "bias" number.
- **NIFTY weekly expiry = Tuesday** (SEBI change), read from FYERS contract master — never hardcode weekday.
- **AI persona hardcoded** (direct, evidence-first, no cheerleading); persona change only via a joint brainstorm, never unilateral.
- **Sanskrit स्वयं / स्वस्तिक branding** is decided — never raise Western/Nazi concerns.
- **Vault↔repo sync:** vault authoritative + repo mirror; weekly cron drift-alert (BUILD-11.14), NOT live bidirectional sync.
- **AI tuning:** one variable at a time, written hypothesis, human-approved. `learned_parameters` tunable; Method files are constitution (hand-edited only). No auto-apply, no autonomous execution — ever.

## 6. Rules that gate ANY trade-entry code (from `01 - Method/`)

- **1% realistic risk cap AND 3% blast-radius fuse** — both must pass (two-tier model).
- **1:2 R:R floor / 1:2.5 target.** No trade below 1:2.
- **No single-leg trades ever** — spread or hedged structure only.
- **One new entry per trading day.**
- **2% overnight-gap hedge cap** on any position held overnight.
- **Limit orders 99%; no stop-widening after entry; margin-safe (BUY legs before SELL); overnight-naked lockout after 15:20 IST.**
- Historical edge: directional-bearish + theta (Bear Put Spread specifically).
- Wake Alerts (BUILD-11.13) will attach per-trade criteria *from inside the Strategy Builder at trade open* — leave a home for it.

## 7. Verification discipline (non-negotiable)

- `node --check` is NOT sufficient — it has passed files the browser then rejected. Load real modules in a real browser before claiming something works.
- **The dev env points at the LIVE Supabase DB.** Do not run the full backend suite or click around signed-in unless you mean to write real data. Use a safe test config or collect-only when just counting.
- Never tell Abhishek something is done/pushed/live unless actually confirmed.
- **Never work directly on `main`** — feature branch + PR; he clicks Merge (that's his one-click Revert safety net). Delete only fully-merged branches you created.
- When Abhishek pastes an Antigravity "done" report: **inspect the real repo/DB/vault** (`/inspect-agy`), don't trust the summary. Grep for silent fallbacks; verify doc claims against real paths; check new tables against the vault sync scripts.

## 8. Update rule

If a session changes state, PR count, file/bucket/secret locations, locked decisions, or the queued list — update this file AND the vault `WHERE EVERYTHING LIVES.md` before closing. Keep the two honest and consistent.
