# WHERE_EVERYTHING_LIVES — Swayam Capital Master Reference (Repo Mirror)

> **This is the repo-side mirror of the master reference doc.** The canonical version lives in the Obsidian vault at `G:\My Drive\Second Brain\02 - Projects\Trading\WHERE EVERYTHING LIVES.md`. Both copies must stay in sync.
>
> **If you are a coding agent (Antigravity, Claude Code, etc.) picking up this repo — read this file first.** It tells you where everything is, what depends on what, and what NOT to change without checking.
>
> **Last updated:** 2026-09-06 by Antigravity (post PR #10, #11, #12, #13 — 102 vitest + 51 pytest passing, UI debts documented in docs/HANDOVER_2026_09_06.md).

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
| https://swayam.abhisheksikka.com | Live app. Cloud Run in `asia-southeast1`, behind IAP. |

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

The vault is where all design decisions, method rules, journals, and session state live. **The rule engine in the backend reads Method files from the vault at runtime** — vault edits become new runtime behavior without code changes.

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
- Access token in GCP Secret Manager as `fyers-access-token`, refreshed nightly

---

## Section 4 — Cloud (GCP)

- **Project:** `swayam-capital` (paid tier + $300 credit through Sept 29, 2026)
- **Region:** `asia-southeast1`
- **Auth:** ADC locally + service account identities in cloud. Zero JSON key files.

Services:
- **Cloud Run** service `swayam-web` — the live app (PWA enabled with `manifest.webmanifest` and `service-worker.js`)
- **Cloud Build** trigger `swayam-main-deploy` — auto-deploy on push to main
- **Cloud Functions:**
  - `swayam-options-recorder` — 60-second options snapshots during market hours
  - `cron_notifications` — (BUILD-11.8) Telegram + FCM push dispatcher
  - `cron_macro_refresh` — (BUILD-11.10) Trading Economics nightly ingest + Sunday Gemini curation
  - `cron_email_digest` — (BUILD-11.11) Sunday 11:00 IST weekly performance & planning digest via Gmail SMTP
- **Cloud Scheduler** — `Asia/Kolkata` time zone, `asia-southeast1` region (triggers recorder, notifications, macro refresh, email digest)
- **GCS bucket** `swayam-options-recordings` — nightly Parquet
- **GCS bucket** `swayam-backups` — (BUILD-11.12)

Secrets in **GCP Secret Manager**: `fyers-access-token`, `fyers-client-id`, `supabase-service-role-key`, `telegram-bot-token` (BUILD-11.8), `telegram-chat-id`, `fcm-server-key`, `vapid-public-key`, `vapid-private-key`, `trading-economics-api-key` (BUILD-11.10), `cron-shared-secret`, `gmail-app-password` (BUILD-11.11), `gmail-sender-address`, `gemini-api-key` (unused, ADC preferred).

---

## Section 5 — Backups (BUILD-11.12, LIVE)

Durable, automated multi-destination backup pipeline:

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
