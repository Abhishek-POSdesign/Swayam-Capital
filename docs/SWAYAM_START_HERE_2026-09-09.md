# SWAYAM CAPITAL — START HERE

> **Written 2026-09-08 at the end of the Release 1 build session by Claude Code (Opus 5).**
> This is the one file to read first. It replaces the 2026-09-08 bridge.
> Mirrored to the vault at `00 - Developer Logs/SWAYAM_START_HERE_2026-09-09.md`.

---

## 0. THE PROMPT ABHISHEK PASTES INTO A NEW CHAT

```
You are picking up Swayam Capital, my NIFTY options paper-trading terminal.
I am not a developer. Write to me in plain English, never hand me code to
approve, and give me a recommendation rather than a menu.

Read these first, in order, before touching anything:
1. G:\My Drive\Second Brain\00 - Developer Logs\SWAYAM_START_HERE_2026-09-09.md
2. G:\My Drive\Second Brain\02 - Projects\Trading\MY TRADING RULES - ONE PAGE.md
3. G:\My Drive\Second Brain\00 - Developer Logs\SWAYAM_RELEASE1_BUILD_LOG_2026-09-08.md

Code: D:\Claude\POS\Trading-Platform\Swayam Capital  (GitHub Abhishek-POSdesign/Swayam-Capital)
Python: .\.venv\Scripts\python.exe          Vault: G:\My Drive\Second Brain  (never D:\)

Do not re-audit and do not re-plan. Eight independent audits were run on
2026-09-07 and the plan went through five review rounds. Everything is written
down in docs/Independent reports/.

Two rules I will not repeat again:
- No fake data. Every number is real from FYERS or the database, or it says
  unavailable. Never a placeholder shown as real.
- Never tell me something is done, live or passing unless you checked it on the
  running system that day and can show me the proof.
```

---

## 1. THE RULES. These override every other document.

The authority is **`02 - Projects/Trading/MY TRADING RULES - ONE PAGE.md`** in the vault.
Settled by Abhishek on 2026-09-08. Do not reinterpret them.

| Rule | Threshold | Live figure on 2026-09-08 |
|---|---|---|
| Running loss on a live trade | 1% of live balance | ₹9,710 |
| Overnight gap test, 2x average daily move | 2% of live balance | ₹19,420 |
| Black swan, absolute worst case at expiry | 5% of live balance | ₹48,550 |
| Deployable margin ceiling | 2x cash-equivalent | ₹5,54,961 |

**Entry is NEVER blocked.** Any structure, any time, including naked and
half-built ones. He adjusts positions in pieces and mid-adjustment a position
always looks appalling. Only **carrying overnight** is gated, and only on two
conditions: hedged, and the gap test passes.

Everything derives from the **live FYERS balance every session**. Nothing is a
stored figure.

---

## 2. HOW THE PIECES ARE WIRED, verified 2026-09-08

### Supabase — the database
| | |
|---|---|
| Project | `wxijlrwoiaeaupaaqecc` "Sikka Business Apps", region ap-south-1 |
| **Shared with** | **Biz Research Hub (`biz_*`) and B.tech Learning Hub (`hub_*`) and the blog automation (`blog_*`), 17 tables.** Scope everything to `swayam_*`. |
| Staging | **None.** The free tier allows two projects and he has two. All work is against live. |
| App access | Supabase REST, service-role key from Secret Manager |
| Tooling access | **NEW**: direct Postgres via `SUPABASE_DB_URL` in `.env`, used only by scripts |
| Connection | **Session pooler `aws-1-ap-south-1.pooler.supabase.com:5432`, user `postgres.wxijlrwoiaeaupaaqecc`.** The direct host is IPv6-only and drops here. Note **aws-1**, not aws-0. |
| Migrations | `swayam_schema_migrations`, 12 applied, 0 pending |
| RLS | **Off on all tables.** Recorded, not fixed. |

### Google Cloud — project `swayam-capital`
| | |
|---|---|
| Live site | Cloud Run `swayam-dashboard`, asia-southeast1, mapped to swayam.abhisheksikka.com |
| Access | **PUBLIC. `allUsers` has invoker.** IAP is NOT applied. |
| Secrets | Secret Manager: fyers-access-token, fyers-client-id, fyers-app-id, fyers-secret-key, supabase url/anon/service-role |
| Token delivery | Injected as env vars at **container start**, so a refreshed token does not reach a running instance |
| Backups | `gs://swayam-backups/supabase/<timestamp>/` — first real one taken 2026-09-08 |
| Recorder | `swayam-recorder` function + scheduler. **Has never once succeeded.** PERMISSION_DENIED, empty bucket. |
| Drive API | **NOT enabled.** |
| Static egress IP | None. compute and vpcaccess APIs disabled. |

### Google Drive — the Second Brain
| | |
|---|---|
| Vault | `G:\My Drive\Second Brain` (Google Drive). **Never `D:\Second Brain`, which is empty and stale.** |
| Folder sharing | **DONE 2026-09-08.** `swayam-dashboard-sa@swayam-capital.iam.gserviceaccount.com` has **Editor** on the Second Brain folder. |
| Cloud writes | **NOT working.** The Drive API is not enabled and no code uses it. `VAULT_PATH` is unset in Cloud Run so `config.py` falls back to a Windows path a Linux container cannot reach. A paper trade on the LIVE SITE inserts the position, fails the journal write, and returns HTTP 500. |
| Local writes | Work. All 79 journal entries were written from his PC. |
| Method files | The container carries a **build-time copy** of 3 of the 7 files. Editing a rule in Obsidian does NOT change the live app. Edit **both** copies and redeploy. |

### FYERS
Token valid 2026-09-07. `funds()`, `positions()`, `quotes()`, `optionchain()`,
`history()`, `market_status()`, `holdings()` and the margin endpoint all work.
**Refresh after 08:00 IST, never before.** An early token dies by lunchtime.

---

## 3. WHAT WAS BUILT ON 2026-09-08, all proved on the running system

| Area | State |
|---|---|
| Live schema baselined | `migrations/000_baseline.sql`, reconciled against all 10 files on disk. 003 and 008-012 never existed. |
| Backup | `scripts/backup_supabase.py`. 19 tables, checksums, verified GCS upload. Fails on a short object count. |
| Restore | `scripts/restore_drill.py`. **Drill PASSED**: 19 tables rebuilt, 600 rows, every table matching on count and content. |
| Migration runner | `scripts/apply_migration.py`. One transaction each, checksums, refuses to run if an applied file was edited. 12 applied. |
| Contract size | 65 from the FYERS contract master, per expiry. No default anywhere. |
| Broker margin | Real, from `multiorder/margin`. Invented ₹32,000 / ₹1,15,000 deleted. |
| Capital | Live from `funds()` id 1, snapshotted per trading day. |
| Charges | Versioned by effective date, Decimal, sourced from FYERS and cross-checked against Zerodha. |
| Risk gate | Rebuilt to his rules. Readiness has zero power. Entry never blocks. |
| Hedge geometry | Real. Short strangle refused, bear put spread allowed. |
| Overnight carry | `rule_engine/carry_risk.py`. Gap test at 2x average daily move. |
| Unlimited loss | Reported honestly. Was fabricating ₹3,69,200 for a short straddle. |
| Price history | Topped up to 2026-09-07, 26 sessions. |
| Positions quarantined | All 79 marked `provenance = build_test`, all archived. |

**Tests: 322 passed, 2 failed.** Both failures pre-date this work:
`test_market.py::test_get_option_chain_returns_strikes` and
`test_notifications.py::test_execute_endpoint_best_effort_dispatch_on_success`.

---

## 4. WHAT IS **NOT** DONE. Do not claim any of these.

Ordered by what matters most for his trading.

1. **The tests write to the live database.** Running the backend suite created
   about 12 real position rows on 2026-09-07. They are quarantined, but the
   hole is open. **Fix this first.** There is no staging project, so the guard
   has to live in the code.
2. **Google sign-in / IAP is NOT applied. The site is public.** He asked for it
   on 2026-09-08 and it did not get done. Anyone with the URL can use it.
3. **The live site still cannot write journal notes to the vault.** Enable the
   Drive API and write through it. The folder is already shared.
4. **A refreshed token does not reach the live site without a redeploy.** Fix by
   reading the secret at runtime with a short cache.
5. **Paper fills are still the entered premium.** No bid/ask, no charges applied
   at execution. The charge engine exists and is used by the risk gate, but the
   execution path does not call it yet. `ESTIMATED_CHARGE_PER_LEG_INR` (₹150) is
   still used on close.
6. **Execution is not idempotent.** A double click still creates two positions.
   No key, no unique constraint, no in-flight guard.
7. **The trade lifecycle is not atomic.** A failed journal write can still leave
   a position recorded and return HTTP 500.
8. **The frontend still assumes lot 75** in `leg-builder.js`, `execution-ticket.js`,
   `preset-bar.js`, `strategy-builder.js`. The backend ignores what the browser
   sends, so the maths is right, but the screen can show the wrong contract count.
9. **`rule-validation-panel.js:97,133` multiplies an already-percentage value by
   100**, printing 62% where the truth is 0.62%. Hardcoded `pct_of_margin: 0.41`
   at lines 23 and 30.
10. **No alert delivery.** The 1% running-loss state is computed and exposed, but
    nothing sends him anything.
11. **No kill switch.** No global halt.
12. **The recorder has never worked.** Grant `run.invoker` to the scheduler
    identity and storage write to its own service account.
13. **Multi-expiry valuation is wrong**, so calendars are visible and computable
    but blocked from execution. Ten of his 21 historical trades are calendars.
14. **The two failing tests**, and a browser console error should fail the
    frontend suite.
15. Frontend does not yet render "Unlimited", the carry verdict, or the running-loss state.

---

## 5. DOCUMENT MAP

**Read in this order.** Everything below lives in both `docs/` in the repo and
`00 - Developer Logs/` in the vault unless stated.

| Order | File | What it is |
|---|---|---|
| 1 | `SWAYAM_START_HERE_2026-09-09.md` | This file |
| 2 | `02 - Projects/Trading/MY TRADING RULES - ONE PAGE.md` *(vault only)* | **His rules. These win over everything.** |
| 3 | `SWAYAM_RELEASE1_BUILD_LOG_2026-09-08.md` | What was built, what changed in the database, gotchas |
| 4 | `SWAYAM_TRUTH_HANDOVER_2026-09-07.md` | The verified honest state before this build |
| 5 | `SWAYAM_PLAN_v9_BUILD_TONIGHT.md` | The build plan. Release 1 is done; 2 and 3 are not. |
| 6 | `SWAYAM_PHASE1_PLAN_2026-09-07_v6.md` | Full detail body and the **UI size standard, a hard review gate** |
| 7 | `SWAYAM_PHASE1_PLAN_2026-09-07_v7.md` / `v8_FINAL.md` | Amendment chain. v9 supersedes where they conflict. |
| 8 | `docs/Independent reports/` *(repo)* | The eight audits. Do not re-run them. |
| 9 | `WHERE_EVERYTHING_LIVES.md` | File and endpoint map |

**Where the plan was WRONG and this build corrected it.** Trust these corrections:
- v9 said a short put needs a long put *below* it. That refuses a bear put
  spread, which is his own preset. See `rule_engine/hedge_geometry.py`.
- v9 said the exchange transaction charge is 0.03503% and IPFT is ₹50 per crore.
  Both FYERS and Zerodha publish 0.03553% and ₹0.01 per crore. See
  `services/charges.py`.
- v9's entry-blocking risk gate was replaced by his rules of 2026-09-08: entry
  never blocks, overnight carry does.

---

## 6. HOW TO RUN THINGS

```
.\Refresh-Token.ps1                                  # daily, after 08:00 IST

.\.venv\Scripts\python.exe scripts\apply_migration.py status
.\.venv\Scripts\python.exe scripts\apply_migration.py up --dry-run
.\.venv\Scripts\python.exe scripts\apply_migration.py up

.\.venv\Scripts\python.exe scripts\backup_supabase.py --gcs
.\.venv\Scripts\python.exe scripts\restore_drill.py run

.\.venv\Scripts\python.exe -m pytest -q      # WARNING: writes to the LIVE database
```

---

## 7. HOW HE WORKS. Non-negotiable.

- **He is not a developer.** Plain English, never code to approve, a
  recommendation rather than a menu.
- **Plan first, in plain English, six parts**, before any code. His
  `/layman-plan` skill.
- **Hand off in plain English, five parts**, after. His `/handoff` skill.
- **Never work on `main`.** Feature branch, pull request, he clicks Merge. The
  PR is his only revert button.
- **Work in the primary folder, not a git worktree.** The venv is an editable
  install pointing at it; a worktree silently tests the wrong source tree.
- He trades in the **afternoon, 1 to 2 pm IST**, and works the night shift.
- He has burned days and real money on false status reports. **Overstating
  anything is worse than saying it is not done.**

---

*Real-money trading remains code-blocked. Nothing here is a claim of readiness.*
