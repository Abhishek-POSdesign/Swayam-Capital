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

# WHERE_EVERYTHING_LIVES — Swayam Capital Master Reference (Repo Mirror)

> **This is the repo-side mirror of the master reference doc.** The canonical version lives in the Obsidian vault at `G:\My Drive\Second Brain\02 - Projects\Trading\WHERE EVERYTHING LIVES.md`. Both copies must stay in sync.
>
> **If you are a coding agent (Antigravity, Claude Code, etc.) picking up this repo — read this file first.** It tells you where everything is, what depends on what, and what NOT to change without checking.
>
> **Last updated:** 2026-09-07 by Claude Code (Opus 5). Every cloud claim in this file was re-checked against the live GCP project on that date and several were false — see the CORRECTION NOTICE at the top. Test counts previously stated here (102 vitest + 51 pytest) were wrong; the real figures are 322 backend collected with 2 failing and 109 frontend passing with one swallowed browser error.

---

## The 30-second version

- **Live app:** https://swayam.abhisheksikka.com
- **Code (you are here):** `D:\Claude\POS\Trading-Platform\Swayam Capital\`
- **Git remote:** https://github.com/Abhishek-POSdesign/Swayam-Capital
- **Vault (design + plans):** `G:\My Drive\Second Brain\02 - Projects\Trading\`
- **Database:** Supabase `wxijlrwoiaeaupaaqecc` ("Sikka Business Apps"), tables prefixed `swayam_*`
- **Cloud:** GCP `swayam-capital`, region `asia-southeast1`, Cloud Run + Cloud Build
- **AI:** Vertex AI Gemini 3.1 Pro Preview (primary), 2.5 Pro (fallback), 2.5 Flash-Lite (light)
- **Broker:** FYERS API v3, personal app `IWB0OQ1J1Y-200`, client `YA38914`

---

## Section 1 — Code and app

### Where the code lives

| Location | What's there |
|---|---|
| `D:\Claude\POS\Trading-Platform\Swayam Capital\` (this repo) | Python 3.11 backend + Vite frontend + tests + migrations |
| https://github.com/Abhishek-POSdesign/Swayam-Capital | Git remote. Feature branches → PR → merge to `main`. |
| https://swayam.abhisheksikka.com | Live app. Cloud Run service `swayam-dashboard` in `asia-southeast1`. **PUBLIC, no login — verified 2026-09-07.** |

### Deployment flow

1. Feature branch (worktree) → push to GitHub
2. Pull request → Abhishek reviews and clicks Merge (never you)
3. Cloud Build trigger `swayam-main-deploy` fires on push to `main`
4. Docker image built → Cloud Run revision deployed → ~5 min later live

**Never push to `main` directly. Never merge PRs yourself. Never force-push.**

### Repo top-level

- `web/` — frontend (Vite, vanilla ES modules, Plotly)
- `src/` — backend (Python 3.11, FastAPI, uvicorn)
- `tests/` — pytest for backend
- `web/tests/` — vitest for frontend
- `migrations/` — numbered SQL migrations for Supabase
- `GEMINI.md` — Antigravity's operating rules and disciplines
- `CHANGELOG.md` — version history
- `WHERE_EVERYTHING_LIVES.md` — this file (mirror of the vault doc)

---

## Section 2 — The vault (design and planning home)

**Location:** `G:\My Drive\Second Brain\02 - Projects\Trading\`

The vault is where all design decisions, method rules, journals, and session state live. **This is only true on Abhishek's local machine.** Verified 2026-09-07: the deployed Cloud Run service sets `TRADING_METHOD_PATH=/app/src/swayam/data/method_files`, a build-time copy baked into the container holding only 3 of the 7 vault Method files. **A rule edited in Obsidian does NOT change the live app until someone rebuilds and redeploys.**

| Vault folder | What's there |
|---|---|
| `00 - Reference/` | Personal Trading Brief, book notes, imported research |
| `01 - Method/` | Trading rules that the rule engine reads at runtime |
| `02 - Journal/` | Daily reflections, weekly reviews |
| `06 - Platform Plan/` | Design source of truth — Platform Overview, AI Trading Partner Chapter, Home Page v2 Plan |
| `WHERE EVERYTHING LIVES.md` | The canonical version of this doc |

### Which doc is authoritative for what

| Question | Answer |
|---|---|
| Where is X? | This doc. |
| Trading rules? | `01 - Method/` (Risk Management Rules, Operational Readiness Rules, Trading Philosophy) |
| Platform design? | `06 - Platform Plan/Platform Overview.md` |
| AI behavior? | `06 - Platform Plan/AI Trading Partner Chapter.md` |
| Home page spec? | `06 - Platform Plan/Home Page v2 Plan.md` |
| Current state? | `00 - Developer Logs/SESSION_STATE_<latest>.md` |

---

## Section 3 — Data

### Supabase

- **Project:** `wxijlrwoiaeaupaaqecc` ("Sikka Business Apps")
- **Tier:** Free (7-day automated backups)
- **Table prefix:** `swayam_*` (isolates from other apps in the same project)

Major tables: `swayam_positions`, `swayam_lessons`, `swayam_ai_sessions`, `swayam_ai_messages`, `swayam_ai_usage_daily`, `swayam_macro_events` (BUILD-11.10), `swayam_knowledge_base` (BUILD-13, pgvector), `swayam_learned_parameters` (BUILD-11.5).

### Market data

- **Historical:** local DuckDB at `data/options_cache.duckdb`, populated nightly from GCS Parquet dumps
- **Live:** FYERS API v3 quotes/WebSocket
- **EOD reference:** NSE Bhavcopy CSVs

### FYERS

- Client `YA38914`, API app `IWB0OQ1J1Y-200`
- API v3, rate limits 10/s · 200/min · 100k/day
- Access token in GCP Secret Manager as `fyers-access-token`. **NOT refreshed nightly — there is no refresh job.** Abhishek runs `scripts/refresh_fyers_token.py` by hand each trading day, and the live Cloud Run service keeps the old token until a new revision is deployed.

---

## Section 4 — Cloud (GCP)

- **Project:** `swayam-capital` (paid tier + $300 credit through Sept 29, 2026)
- **Region:** `asia-southeast1`
- **Auth:** ADC locally + service account identities in cloud. Zero JSON key files.

Services:
- **Cloud Run** service **`swayam-dashboard`** — the live app. (There is no service named `swayam-web`; that name was never correct.) Deployed `--allow-unauthenticated`, max 3 instances, 2 gunicorn workers.
- **Cloud Build** trigger `swayam-main-deploy` — auto-deploy on push to main
- **Cloud Functions — verified 2026-09-07, only ONE exists:**
  - `swayam-recorder` (asia-south1) — intended to take 60-second option-chain snapshots. **IT HAS NEVER RUN SUCCESSFULLY.** Every scheduled call fails PERMISSION_DENIED and its output bucket is empty.
  - The functions listed below were written in code but **never deployed**:
  - `cron_notifications` — (BUILD-11.8) Telegram + FCM push dispatcher
  - `cron_macro_refresh` — (BUILD-11.10) Trading Economics nightly ingest + Sunday Gemini curation
  - `cron_email_digest` — (BUILD-11.11) Sunday 11:00 IST weekly performance & planning digest via Gmail SMTP
- **Cloud Scheduler** — verified 2026-09-07: exactly TWO jobs exist, both in **asia-south1**, not asia-southeast1. `swayam-ai-compaction` (working) and `swayam-recorder-schedule` (failing every minute with PERMISSION_DENIED). No notification, macro or digest job exists.
- **GCS bucket** `swayam-capital-options-data` (asia-south1) — intended nightly Parquet. **Verified EMPTY on 2026-09-07.** (There is no bucket named `swayam-options-recordings`.)
- **GCS bucket** `swayam-backups` (asia-southeast1) — holds one manual run from 2026-09-05 and nothing else.

Secrets in **GCP Secret Manager**: `fyers-access-token`, `fyers-client-id`, `supabase-service-role-key`, `telegram-bot-token` (BUILD-11.8), `telegram-chat-id`, `fcm-server-key`, `vapid-public-key`, `vapid-private-key`, `trading-economics-api-key` (BUILD-11.10), `cron-shared-secret`, `gmail-app-password` (BUILD-11.11), `gmail-sender-address`, `gemini-api-key` (unused, ADC preferred).

---

## Section 5 — Backups (BUILD-11.12) — ⛔ NOT LIVE, NOT RUNNING, CANNOT SUCCEED AS BUILT

**Verified 2026-09-07.** None of the schedules below exist in Cloud Scheduler. The application's service account `swayam-dashboard-sa` has `storage.objectViewer` only and therefore cannot write a backup object at all. `upload_to_gcs` returns `False` on failure and the calling job ignores that and reports success anyway, so a deployed job would have reported healthy while saving nothing. The restore script executes no restore. **The only real protection today is Supabase's own 7-day automated backup.** The design below is the INTENT, not the state:

1. **Nightly Database Dumps (02:00 IST Daily):**
   - Cloud Function: `cron_backup_db`
   - Destination: `gs://swayam-backups/db/YYYY-MM-DD.sql.gz`
   - Local Mirror: `data/backups/db/YYYY-MM-DD.sql.gz`
   - GCS Lifecycle Retention (`gcs_lifecycle_backups.json`):
     - Daily files deleted after 30 days.
     - Monthly 1st-of-month files (`*-01.sql.gz`) kept for 12 months.
     - Yearly files (`*-01-01.sql.gz`) kept for 5 years.
   - Alerting: Immediate Telegram alert dispatched if backup fails or is skipped.

2. **Weekly Workspace & Method ZIP (Sundays 03:00 IST):**
   - Cloud Function: `cron_backup_weekly_zip`
   - Destination: `gs://swayam-backups/weekly/YYYY-WW.zip`
   - Local Vault Sync: `G:\My Drive\Second Brain\_backups\swayam\YYYY-WW.zip` (rolling 12-week retention)
   - Contents:
     - Full SQL database dump (`database_dump.sql`)
     - Complete Git repository bundle (`swayam-repo.bundle`) created via `git bundle create`
     - All markdown trading method files from vault (`02 - Projects/Trading/01 - Method`)

3. **Monthly AI Chat Journal Mirror (1st of month, 04:00 IST):**
   - Cloud Function: `cron_backup_ai_chat`
   - Destination: `gs://swayam-backups/ai-chat/YYYY-MM.json`
   - Local Vault Sync: `G:\My Drive\Second Brain\_backups\swayam\ai-chat\YYYY-MM.json`
   - Contents: Complete export of `swayam_ai_conversations` and `swayam_ai_messages`.

---

### How to Restore from Backup

#### Method A: Automated One-Command Script (Recommended)
Run the built-in restore script:
```bash
# Using Python:
python scripts/restore_from_backup.py [path/to/backup.sql.gz]

# Using Bash:
bash scripts/restore_from_backup.sh [path/to/backup.sql.gz]
```
If no file argument is provided, the script automatically selects the latest snapshot from `data/backups/db/`.

#### Method B: Manual Restoration via psql or Supabase SQL Editor
1. Download or uncompress the backup file:
   ```bash
   # From GCS:
   gcloud storage cp gs://swayam-backups/db/2026-09-06.sql.gz .
   gzip -d 2026-09-06.sql.gz
   ```
2. Open Supabase Dashboard → SQL Editor (Project `wxijlrwoiaeaupaaqecc`) or connect via `psql`:
   ```bash
   psql -h aws-0-ap-south-1.pooler.supabase.com -p 5432 -d postgres -U postgres.wxijlrwoiaeaupaaqecc -f 2026-09-06.sql
   ```
3. Verify row counts across all 19 `swayam_*` tables.

#### Method C: Restoring Code from Git Bundle
To recreate or verify the entire Git repository from a weekly ZIP archive:
```bash
git clone swayam-repo.bundle restored-swayam-capital
cd restored-swayam-capital
git checkout main
```

---

## Section 6 — Cold-start for a new AI

Read in order:
1. This doc
2. Vault: `06 - Platform Plan/Platform Overview.md`
3. Vault: `06 - Platform Plan/AI Trading Partner Chapter.md`
4. Vault: `06 - Platform Plan/Home Page v2 Plan.md`
5. Vault: `00 - Developer Logs/SESSION_STATE_<latest>.md`
6. Vault: `00 - Reference/Personal Trading Brief.md`
7. THEN touch code.

Do not skip. Context first, code second.

---

## Section 7 — The update rule (mandatory)

**If your session (or your build) changes any of:**
- File locations (moved, renamed, added, removed)
- Endpoint URLs or route paths
- Supabase table/column names
- Secret Manager keys or env vars
- Backup paths or cron schedules
- Which doc is authoritative for what
- Cloud service names or regions

**Then update BOTH copies before ending the session or opening the PR:**
- Repo copy: `D:\Claude\POS\Trading-Platform\Swayam Capital\WHERE_EVERYTHING_LIVES.md`
- Vault copy: `G:\My Drive\Second Brain\02 - Projects\Trading\WHERE EVERYTHING LIVES.md`

Update the "Last updated" line at the top with today's date.

**This is enforced.** `GEMINI.md` carries this rule for Antigravity. Claude has it as an auto-loading memory. Non-compliance = the PR gets reworked.

If this doc goes stale, it becomes a lie. Keep it honest.

---

*End of repo mirror. Canonical version in vault.*
