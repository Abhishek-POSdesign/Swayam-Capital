# SWAYAM CAPITAL — THE DATA MAP

> **Written 11 September 2026. This is the one page that says where every piece
> of my data lives, what protects it, and what deletes it.**
>
> It lives in my vault and not inside the terminal on purpose: **the day I most
> need to know where my backups are is the day the app is broken.** This note
> works on my phone, offline, when nothing else does.
>
> **Send a new chat this file's path and it should not have to ask me anything
> about storage.**
>
> The top half is hand-written and no script may overwrite it. The block at the
> bottom, between the two markers, is rewritten by the nightly local task with
> figures read fresh. Anything it cannot read says unavailable and why.

---

## 1. THE SEVEN PLACES MY DATA LIVES

| # | What it is | Where it really is | Who writes it | What deletes it |
|---|---|---|---|---|
| 1 | **My trade record.** Trades, legs, results, journal rows, targets, AI conversations | Supabase project `wxijlrwoiaeaupaaqecc`, ap-south-1. Shared with two other apps, so everything of mine is prefixed `swayam_` | The terminal | **Nothing** |
| 2 | **My trade notes**, one per trade | This vault, `02 - Projects/Trading/04 - Journal/` and its `Terminal tests/` subfolder | The drainer, from the terminal | **Nothing** |
| 3 | **Recorder data.** Spot, open interest, implied volatility, Greeks, minute snapshots of the chain | Google bucket `gs://swayam-capital-options-data`, Mumbai. **Not Supabase, not this vault, not my PC** | The recorder, a Cloud Run job, every minute the market is open | **Nothing. It has no deletion rule** |
| 4 | **Backtest history**, the years of option data sourced from FYERS and NSE | My PC, `D:\Claude\POS\Trading-Platform\Swayam Capital\data\history` (git ignores it) **and, since 11 September 2026, a copy in `gs://swayam-backups/history/`** — 160 objects, 630.5 MiB | The loader scripts, run by hand. The copy is kept current by `scripts/nightly_local.py`, which uploads only what changed | **Kept one year, then deleted**, by the same bucket rule as row 6 |
| 5 | **Backtest query store** | My PC, `data\options_cache.duckdb` | DuckDB, from the files above | Nothing |
| 6 | **Backups of my record** | **TWO places.** The full history in Google bucket `gs://swayam-backups`, Singapore, under `supabase/<timestamp>/`. **And the newest THIRTY nights in this vault, at `02 - Projects/Trading/07 - Backups/<timestamp>/`**, each folder holding all 19 tables, `schema.sql` and `MANIFEST.json` | The bucket copy by the nightly Cloud Run job `swayam-nightly-backup` at 02:00, or `scripts/backup_supabase.py --gcs` by hand. The vault copy by `scripts/nightly_local.py` at 03:00, which also prunes to thirty | **Bucket: kept one year, then deleted.** One rule, applied 11 September 2026. **Vault: newest thirty nights, older ones pruned** |
| 7 | **My code** | GitHub, `Abhishek-POSdesign/Swayam-Capital` | Every merged pull request | Nothing. This is my real history |

---

## 2. WHAT IS AND IS NOT PROTECTED

**Protected.** My code, by GitHub, completely. My record, by the backup in row 6,
as far back as the newest backup.

**Not protected today.**

- **Rows 3 and 5 have no copy anywhere.** The recorder's bucket is its only
  home, and the DuckDB query store is rebuilt from row 4 rather than backed up.
- ~~Row 4 has no copy~~ **Row 4 is now copied**, since 11 September 2026:
  630.5 MiB across 160 objects in `gs://swayam-backups/history/`. Before that it
  existed on one disk in my house, and the minute bars alone took 90 minutes and
  8,576 requests to FYERS to source.
- **⚠️ Row 1 is only as safe as the newest backup, and as of 12 September 2026
  the NIGHTLY CLOUD BACKUP IS FAILING.** The job runs, reads all 19 tables, and
  is then refused when it tries to write: its service account
  `swayam-dashboard-sa` has no permission on `gs://swayam-backups`. **It fails
  loudly rather than reporting success**, which is the behaviour I want, but it
  means the newest backup is still the one taken by hand on 11 September at
  16:46 UTC. The local 03:00 half is registered and working. **Until the
  permission is granted, a backup only exists when it is taken by hand.**

---

## 3. WHAT DELETES ANYTHING, ANYWHERE

Only three things delete automatically in my whole setup. Nothing else, ever.

| What | Rule |
|---|---|
| Build images, Google's store of my app | Newest 20 kept, the rest deleted after 2 days |
| Live site versions, Cloud Run revisions | Newest 20 kept, pruned by a step inside every deploy. Whatever is serving traffic is never touched |
| Backups | Everything kept one year, then deleted |

**Nothing deletes my trades, my notes, my recorder data or my backtest files.**

**Keeping only twenty build images does NOT limit how far back I can go.** The
Revert button on a pull request rebuilds my app from the source code, for any
change I have ever merged. The images are a shortcut: with one, going back is
instant; without one, it costs a single build of about seven minutes.

---

## 4. HOW TO REACH EACH ONE

```
# What backups exist, newest last
gcloud storage ls gs://swayam-backups/supabase/

# Download one backup to look at it
gcloud storage cp -r gs://swayam-backups/supabase/<timestamp>/ .

# What the recorder has collected
gcloud storage ls gs://swayam-capital-options-data/**

# What the backup bucket will delete, and when
gcloud storage buckets describe gs://swayam-backups --format="json(lifecycle_config)"

# How many build images and live versions exist right now
gcloud artifacts docker images list asia-southeast1-docker.pkg.dev/swayam-capital/swayam --format="value(version)"
gcloud run revisions list --service=swayam-dashboard --region=asia-southeast1 --format="value(metadata.name)"
```

**Take a backup by hand, any time, from the project folder:**

```
.\.venv\Scripts\python.exe scripts\backup_supabase.py --gcs
```

---

---

## 4b. IF MY DATABASE IS LOST, HOW I ACTUALLY GET IT BACK

**Written 2026-09-12, after the restore drill failed against a real cloud
backup. Read this before panicking: my rows are safe. What is not proven is a
ONE-STEP restore.**

**What the drill found.** A backup ships `schema.sql`, and that file is the
schema as it stood on 8 September. Everything added since is missing from it:
`margin_required_inr`, `max_loss_unbounded_reason`, and the whole
`swayam_orders`, `swayam_phase` and `swayam_daily_summary` tables. The rows are
all there; the shape they need is not.

**So recovery today takes TWO sources, and I have both.**

1. **The shape comes from GitHub.** `migrations/` holds every change ever made.
   Apply them in order into the empty database:
   `.\.venv\Scripts\python.exe scripts\apply_migration.py up`
2. **The rows come from the backup.** One JSON file per table in
   `gs://swayam-backups/supabase/<timestamp>/`, or from the copy in this vault
   at `02 - Projects/Trading/07 - Backups/`.
3. **Check against the backup's own MANIFEST.json**, which carries a row count
   and a SHA-256 for every file.

**This has never been rehearsed end to end.** That is the honest gap, and it is
the first thing the cloud chat fixes next: a backup should carry the schema as
it is on the night it runs, not a snapshot from a past date, so that one
artifact is enough.

**What is NOT at risk:** every row exists in four places tonight — the live
database, three backups in the bucket, the copy in this vault, and GitHub for
the shape.

## 5. THE THINGS THAT HAVE BITTEN ME, SO I DO NOT REPEAT THEM

1. **A command that reads a file from the project must be run from the project
   folder**, or given its full path. One was run from `C:\Windows\System32` and
   failed. Worse, the copy of that file in my primary folder was the broken
   version, so a working path would have re-applied the fault.
2. **A region I tried once and abandoned keeps its secrets and its public
   access for ever.** Two copies of my terminal sat open to the internet with my
   live keys in them from 4 to 11 September. Nothing expires on its own.
3. **A thing built and never deployed looks exactly like a thing that works.**
   Three backup functions sit in `functions/` and none of them has ever run.
4. **The cloud cannot see this vault.** Anything that writes here must run on my
   PC. That is why the daily check-in fails on the live site.

---

## 6. WHO OWNS WHAT

| Chat | What it owns |
|---|---|
| **Main** | The terminal, the plan, the mockups, reviewing every build. `docs/SUCCESSOR_PROMPT.md` |
| **Cloud cost** | Google Cloud spend, backups, hygiene. Build C |
| **Backtester** | The history, DuckDB, the replay engine. `docs/SUCCESSOR_BACKTESTER.md` |
| **AI partner** | How the AI behaves. `docs/SUCCESSOR_AI_PARTNER.md` |
| **Builder chats** | One build each, then closed. `docs/builds/` |

---

<!-- LIVE FIGURES: everything below this marker is rewritten by the nightly
     local task. Do not hand-edit. Anything unreadable says so, with the
     reason, and no stale number is left standing. -->

## 7. LIVE FIGURES

Refreshed automatically by `scripts/nightly_local.py` on **12 September 2026, 00:47 India Standard Time**.
Anything it could not read says so, with the reason. No stale number is
left standing here.

| | |
|---|---|
| Newest backup of my record | 2026-09-11T16-46-46Z, 19 tables, 900 rows |
| Older backups kept | 2, oldest 2026-09-07T17-12-15Z |
| Recorder data | 3 trading days, 11.4 MB total |
| Backtest history on my PC | 630 MB at D:\Claude\POS\Trading-Platform\Swayam Capital\data\history |
| Backtest history copied to the bucket | nothing under gs://swayam-backups/history/ yet |
| Build images | 22 |
| Live site versions | 20 |
| Open trades | 1, `7cd4d017` |

<!-- END LIVE FIGURES -->
