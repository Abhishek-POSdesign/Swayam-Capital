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
| 4 | **Backtest history**, the years of option data sourced from FYERS and NSE | **My PC only**, `D:\Claude\POS\Trading-Platform\Swayam Capital\data\history`. Git ignores it | The loader scripts, run by hand | **Nothing, and nothing copies it either** |
| 5 | **Backtest query store** | My PC, `data\options_cache.duckdb` | DuckDB, from the files above | Nothing |
| 6 | **Backups of my record** | Google bucket `gs://swayam-backups`, Singapore, under `supabase/<timestamp>/` | `scripts/backup_supabase.py --gcs` | **Kept one year, then deleted.** One rule, applied 11 September 2026 |
| 7 | **My code** | GitHub, `Abhishek-POSdesign/Swayam-Capital` | Every merged pull request | Nothing. This is my real history |

---

## 2. WHAT IS AND IS NOT PROTECTED

**Protected.** My code, by GitHub, completely. My record, by the backup in row 6,
as far back as the newest backup.

**Not protected today.**

- **Rows 3, 4 and 5 have no copy anywhere.** The recorder's bucket is its only
  home, and my 631 MB of backtest history exists on one disk in my house. If
  that disk dies I have to source it again: the minute bars alone took 90
  minutes and 8,576 requests to FYERS.
- **Row 1 is only as safe as the newest backup**, and **no nightly backup runs
  yet.** That is the outstanding half of Build C.

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
