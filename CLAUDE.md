# Swayam Capital — orientation for any agent

**Read `docs/SWAYAM_START_HERE.md` before anything else.** It has every
location, what is verified true right now, and what is not done. Then read
`docs/PLAN.md`, the only plan file. There is no third document to hunt for.

This file used to be 120 lines, most of it historical correction notices and a
list of trading rules Abhishek has since replaced. It is all in git history.
What is left is only what changes how you work today.

---

## Who this is for

Abhishek Sikka. **Not a developer.** Plain English, never code to approve, a
recommendation rather than a menu. **English, not Hinglish**, unless he asks.
He speaks his prompts, so an odd word is transcription, not intent.

He built a Second Brain in Obsidian, fed his daily life into it through his
Atlas app, then added four years of his own trading history. He stopped trading
for months. **This terminal is how he restarts.** He intends to trade real
money through it. That is why a fabricated number is not a cosmetic bug: it
damages the thing the Second Brain was built to be.

He trades **1 to 2 pm IST** and works the night shift.

---

## The two rules he will not repeat

1. **No fake data.** Every number is real from FYERS or the database, or it
   says `unavailable`. Never a placeholder shown as real, never a fallback
   constant. This has been violated repeatedly and it is what he cares about
   most.
2. **Never say something is done, live or passing** unless you checked it on
   the running system that day and can show the proof. He has burned days and
   real money on false status reports. **An honest gap is welcome; an
   overstatement is not.**

---

## His trading rules, settled 2026-09-08

Authority is `02 - Projects/Trading/MY TRADING RULES - ONE PAGE.md` in his
vault, mirrored at `docs/MY_TRADING_RULES_ONE_PAGE.md`. It overrides every plan
and this file.

| # | Rule | Threshold |
|---|---|---|
| 1 | Running loss | 1% of live balance |
| 2 | Overnight gap, at 2x the average daily move | 2% |
| 3 | Black swan, worst case at expiry | 5% |
| 4 | Deployable margin ceiling | 2x cash equivalent |

Every figure is a percentage of the **live FYERS balance read fresh each
session**, never a stored number.

**Entry is NEVER blocked**, including naked and half-built structures, because
converting a straddle into a condor requires passing through states no gate
would allow. **Only carrying overnight is gated:** hedged, and inside the gap
test.

**These replaced an older set. If you find a document mentioning a 3%
blast-radius fuse, a 1:2 reward-to-risk floor, "no single-leg trades ever", or
"one entry per trading day", that document is stale.** Those rules are gone.

**The NIFTY lot is 65**, resolved server-side from the FYERS contract master.
A browser that sends 75 is ignored. Never hardcode 75.

**The readiness form is a journal with zero power.** It cannot block a trade or
shrink size. He removed that on 2026-09-07, because a form he fills in himself
can be lied to.

---

## Settled decisions, do not reopen

- **The Sanskrit branding is decided.** The mark is `स्व` in sage green beside
  the word Swayam. Never raise Western or Nazi associations about it; he has
  litigated this and it is closed.
- **No purple, lilac or violet anywhere.** He has complained many times.
- **AI cost rule:** AI-heavy features are always a manual button, a 60-minute
  cache and a daily cap. Never fire on page load. Left unguarded this was
  estimated at ₹4,000 a month.
- **AI tuning:** one variable at a time, written hypothesis, human approved.
  Method files are constitution and hand-edited only. No auto-apply and no
  autonomous execution, ever.
- **The vault is authoritative; the repo mirrors it.** Not bidirectional sync.

---

## How to work here

- **Never work on `main`.** Feature branch, pull request, **he** clicks Merge.
  The PR is his only revert button.
- **Check whether the branch's PR is already merged before pushing more work.**
  He merges mid-session to review. Commits pushed onto a merged branch strand
  with no PR and no revert button. This happened twice on 2026-09-08.
- **Work in the primary folder, never a git worktree.** The venv is an editable
  install pointing at it, so a worktree silently tests the wrong source tree.
- **Plan first, plain English, six parts.** Then build. Then hand off, five
  parts. His `/layman-plan` and `/handoff` skills carry the shape.
- **Ask when unsure.** He has said so explicitly, and mid-build is fine.
- **`node --check` is not verification.** It has passed files the browser then
  rejected. Load the real page in a real browser.
- **The dev environment points at the LIVE database.** The test suite is caged
  (`tests/db_guard.py`) because there is no staging project. Do not weaken or
  remove that guard.
- **Update `docs/PLAN.md` as work lands. Do not write a new plan document.**
  Every superseded plan was deleted on 2026-09-08 for exactly this reason.
- When he pastes an Antigravity "done" report, **inspect the real repo,
  database and vault** rather than trusting the summary. Grep for silent
  fallbacks and verify doc claims against real paths.

---

## Where to look

| File | What it is |
|---|---|
| `docs/SWAYAM_START_HERE.md` | Where everything lives, what is verified, what is not done |
| `docs/PLAN.md` | The one plan. What happens next, in order |
| `docs/UI_BUILD_BRIEF_ROUND_2.md` | **The active job**: his feedback on the rebuilt pages, 21 steps, two PRs |
| `docs/CALENDAR_BUILD_BRIEF.md` | **The job after that**: multi-expiry valuation. Backend can start now |
| `docs/UI_BUILD_BRIEF.md` | Round 1, finished and live on 2026-09-08. History |
| `docs/reference/` | The two approved page prototypes, as working code |

Deeper reference only when needed: `WHERE_EVERYTHING_LIVES.md`,
`docs/RUNBOOK.md`, `docs/API.md`, `docs/architecture.md`.

*Real-money trading is code-blocked by absence: there is no order-placement
code anywhere in this repository.*
