# SWAYAM CAPITAL — START HERE

> Written 2026-09-08 by Claude Code (Opus 5). Supersedes
> `SWAYAM_START_HERE_2026-09-09.md`. Mirrored to the vault at
> `00 - Developer Logs/SWAYAM_START_HERE.md`.
>
> **He should never have to tell you where anything lives. It is all below.**

---

## 0. THE PROMPT HE PASTES INTO A NEW CHAT

```
You are picking up Swayam Capital, my NIFTY options paper-trading terminal.
I am not a developer. Plain English, never code to approve, give me a
recommendation rather than a menu. Write in English, not Hinglish.

Read docs/SWAYAM_START_HERE.md first. It has everything. Do not ask me where
my vault, database or cloud project is, and do not re-audit or re-plan.

Two rules I will not repeat:
- No fake data. Every number is real from FYERS or the database, or it says
  unavailable. Never a placeholder shown as real.
- Never tell me something is done, live or passing unless you checked it on the
  running system that day and can show me the proof.
```

---

## 1. WHERE EVERYTHING IS. Do not ask him.

| Thing | Where |
|---|---|
| Code | `D:\Claude\POS\Trading-Platform\Swayam Capital` |
| GitHub | `Abhishek-POSdesign/Swayam-Capital` |
| Python | `.\.venv\Scripts\python.exe` (editable install; work in the primary folder, NEVER a worktree) |
| **Vault** | **`G:\My Drive\Second Brain`.** `D:\Second Brain` is EMPTY and STALE. Never use it. |
| Database | Supabase `wxijlrwoiaeaupaaqecc`, ap-south-1. **Shared with two other apps.** Scope everything to `swayam_*`. |
| DB connection | Session pooler `aws-1-ap-south-1.pooler.supabase.com:5432`, user `postgres.wxijlrwoiaeaupaaqecc`, in `SUPABASE_DB_URL`. **aws-1, not aws-0.** The direct host is IPv6-only and drops here. |
| Cloud | GCP `swayam-capital`, project number 535273918813 |
| Live site | Cloud Run `swayam-dashboard`, asia-southeast1, mapped to swayam.abhisheksikka.com |
| Recorder | Cloud Run function `swayam-recorder`, asia-south1 |
| Schedulers | asia-south1: `swayam-recorder-schedule`, `swayam-ai-compaction` |
| Buckets | `gs://swayam-backups`, `gs://swayam-capital-options-data` |
| **Sign-in** | **Identity-Aware Proxy, direct on Cloud Run. FREE.** Custom OAuth client `535273918813-es1obmlci30t1eulne8l584o33rh8hf9.apps.googleusercontent.com` (his personal Gmail project has no Workspace org, so Google's managed client does not apply). `Enable-SignIn.ps1` turns it on, `Undo-SignIn.ps1` turns it off. |
| Secrets | Secret Manager: fyers-access-token, fyers-client-id, fyers-app-id, fyers-secret-key, supabase url/anon/service-role |
| **Logo** | **`स्व` in sage green (#7d9d84 light, #9dbba3 dark), wordmark "Swayam Capital".** Source art: `G:\My Drive\Second Brain\Minimalist_logo_for_Swayam_Capital_2K_202609052357.jpeg`. **Not the swastika.** |

**No staging database exists.** The Supabase free tier allows two projects and
both are used. Everything runs against live. The test suite is caged in code
(`tests/db_guard.py`); do not remove that guard.

---

## 2. HIS RULES. These override every document, including this one.

Authority: `02 - Projects/Trading/MY TRADING RULES - ONE PAGE.md` in the vault.

| # | Rule | Threshold | On ₹9,71,002 |
|---|---|---|---|
| 1 | Running loss | 1% of live balance | ₹9,710 |
| 2 | Overnight gap, at 2x average daily move | 2% | ₹19,420 |
| 3 | Black swan, worst case at expiry | 5% | ₹48,550 |
| 4 | Deployable margin ceiling | 2x cash equivalent | ₹5,54,961 |

**Entry is NEVER blocked**, including naked and half-built structures. Only
**carrying overnight** is gated: hedged, and inside the gap test. Everything is
a percentage of the balance read fresh each session, never a stored figure.

**The readiness form is a journal with zero power.** It cannot block a trade or
shrink size. Never tell him otherwise.

**The NIFTY lot is 65**, resolved server-side from the FYERS contract master.
A browser that sends 75 is ignored.

---

## 3. WHAT IS TRUE RIGHT NOW, verified 2026-09-08

| | |
|---|---|
| Test suite writing to his record | **FIXED.** 81 rows before a full run, 81 after. |
| The two late fixture rows | **QUARANTINED.** Zero open positions. |
| Risk panel showing 174% for 1.74% | **FIXED**, with a regression test. |
| One click, one trade | **DONE.** Idempotency key plus `swayam_execution_attempts`. |
| A note can never fail a trade | **DONE.** `swayam_journal_outbox` plus `scripts/drain_journal_outbox.py`. |
| Recorder | **FIXED.** Was missing `run.invoker`. Records from 09:15 IST. |
| AI reads So Far Today | **DONE.** Section 15 of the context, cache only. |
| AI reads readiness | **FIXED.** The query had never once run (Postgres 42703). |
| FYERS WebSocket library | **UNBLOCKED.** Needed `setuptools<81`. `FyersDataSocket` imports. |
| Drive API | **ENABLED** on the project. |
| Google sign-in | **ON and verified 2026-09-08.** He signed in successfully. |
| Site is public | **NO.** `allUsers` removed. Every path, on the custom domain AND the raw run.app URL, returns 302 to Google. The API answers "Invalid IAP credentials: empty token". |
| `swayam-ai-compaction` | **RUNNING again** through IAP, audience set to the IAP client id. |
| Real-money trading | **Code-blocked by absence.** No order-placement code exists anywhere. |

Migrations: 20 applied, 0 pending. Tests: 327 pass, 2 fail (both pre-date this
work: `test_market` option chain, `test_notifications` dispatch).

---

## 4. THE APPROVED DESIGNS. Build these; he has signed them off.

He reviewed and approved two interactive prototypes on 2026-09-08:

- **Strategy Desk** — https://claude.ai/code/artifact/7adbe205-616c-4e7a-8f6e-ef003d1c98ff
- **Home** — https://claude.ai/code/artifact/967d09bf-d826-45b4-b8fa-6df6d580a1fe

His decisions, do not relitigate:

1. **Legs at the TOP of the left column**, like Sensibull. Not the bottom.
2. **One expiry dropdown and one lot multiplier for ALL legs**, above the legs.
3. **Expiry selector above the ready-made grid**, and it drives what they load.
4. **Dustbin icon for delete**, never a cross.
5. **His four rules sit at the BOTTOM, with the execute button**, in one block.
6. **The top metric row starts with margin**: margin needed for this structure
   against margin used, green when it fits, red with the shortfall in rupees
   when it does not. Then max profit, max loss, breakeven, reward to risk, and
   the value at his chosen target.
7. **The payoff graph works and he likes it. Do not break it.** Drag it to move
   the target; the date slider pulls the blue curve away from the black one.
8. **A running ticker** across the top of both pages.
9. **Home has a dedicated NIFTY sidebar**: price, day and 20-day and 50-day
   range position bars, average daily move, ATR, realised vol, the 20-day
   average and the distance from it, volume, breadth, sentiment, sectors,
   options.
10. **The morning ritual is ONE THIN STRIP** filled from a modal. Never big cards.
11. **The record toggles between the paper book and the real-money book.**
12. **So Far Today moves INSIDE the AI chat panel**, and the AI must read it.
    The reading half is done. The moving half is not.
13. **Theme: simple black and white**, one accent. He cites his Atlas app.
14. He chose **replace the existing pages directly**, not build alongside.

---

## 5. WHAT IS NOT DONE. Do not claim any of these.

1. **The two page rewrites.** `web/src/pages/home.js` and
   `web/src/pages/strategy-builder.js` still carry the OLD layout. The designs
   above are approved and the plumbing is ready (`api.getRiskCapital` added, AI
   context wired) but the page files themselves are untouched. This is the next
   job and it is the big one. Preserve the class contracts: `HomePage` and
   `StrategyBuilderPage` each need `constructor(container, options)`, `init()`
   and `destroy()`; the builder also needs `refreshPositions()` and a
   `payoffChart` with `retheme()`; home needs a `niftyChart` object with
   `retheme()`, because `main.js` calls it unguarded and will throw otherwise.
   Home currently mounts these components, and he wants the AI chat kept
   exactly as it is: PWA prompt, readiness ritual, verdict card, KPI history,
   So Far Today, NIFTY snapshot, chat surface, macro events.
2. **Cloud writes to the vault.** The Drive API is enabled and the folder is
   shared, but **a service account can never do this**: zero storage quota
   since June 2023, and Shared Drives and domain-wide delegation both require
   Workspace, which he does not have on a personal Gmail account. The only
   route is **OAuth as Abhishek himself with the `drive.file` scope**, which is
   non-sensitive and needs no security assessment, so the sign-in does not
   expire. `drive.file` can only touch what the app created, so the app creates
   its own folder once and he drags it into the vault; access follows the
   folder, not the path. The outbox already means no note is lost meanwhile.
3. **Charges at execution.** `ESTIMATED_CHARGE_PER_LEG_INR` (₹150) is still
   used on close. The real versioned charge engine exists and the risk gate
   uses it.
4. **Kill switch.** None exists.
5. **Multi-expiry valuation**, so calendars are visible but blocked from
   execution. Ten of his 21 historical trades are calendars. Biggest single gap.
6. **Backups have run once, by hand.** `scripts/backup_supabase.py --gcs` works
   and the restore drill passed on 19 tables and 600 rows. Nothing is scheduled.
7. **Journal analytics does not filter `provenance`**, so any win rate would be
   computed from the 81 quarantined test rows. Fix before showing performance.
8. **Volume and market breadth.** Volume is available from FYERS and unread.
    Breadth has no free source; both pages say `unavailable`.
9. **Live ticks.** `/ws/spot` accepts a connection and answers ping with pong.
    Nothing is ever pushed. The library now imports, so this is buildable.
10. **The two long-standing test failures.**

---

## 6. HOW HE WORKS. Non-negotiable.

- **Not a developer.** Plain English, no code to approve, a recommendation
  rather than a menu. **English, not Hinglish**, unless he asks for otherwise.
- **He speaks his prompts.** An odd word is transcription, not intent.
- **Plan first, six parts, in chat.** Then build. Then hand off, five parts.
- **Never work on `main`.** Feature branch, pull request, he clicks Merge. The
  PR is his only revert button.
- **Ask when unsure.** He said so explicitly, and mid-build is fine.
- He trades **1 to 2 pm IST** and works the night shift.
- **Overstating anything is worse than saying it is not done.** He has burned
  days and real money on false status reports.

---

## 7. WHY THIS EXISTS

He built a Second Brain in Obsidian on Google Drive, fed his daily life into it
through his Atlas app, then injected four years of his own trading history. He
stopped trading for several months. **This terminal is the vehicle for
restarting.** It is the instrument he intends to trade real money through. That
is why data integrity is the whole point: a fabricated number damages the very
thing the Second Brain was built to be.

---

## 8. COMMANDS

```
.\Refresh-Token.ps1                                   # daily, after 08:00 IST
.\Undo-SignIn.ps1                                     # panic button for sign-in

.\.venv\Scripts\python.exe scripts\apply_migration.py status
.\.venv\Scripts\python.exe scripts\apply_migration.py up
.\.venv\Scripts\python.exe scripts\backup_supabase.py --gcs
.\.venv\Scripts\python.exe scripts\restore_drill.py run
.\.venv\Scripts\python.exe scripts\drain_journal_outbox.py status
.\.venv\Scripts\python.exe -m pytest -q               # safe now; writes are caged
```

*Real-money trading remains code-blocked. Nothing here is a claim of readiness.*
