# Swayam Capital — orientation for any agent

**Read `docs/ROADMAP.md` first. Plan starts there.** It is the direction, in
his words, four horizons with gates and no dates, and it may only be edited
with his explicit approval. **Then `docs/SWAYAM_START_HERE.md`.** It has every
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

**He is NOT at his desk in the morning.** He works a night shift, wakes around
1 pm IST, and is at the screen by about 2 pm. He trades **1 to 2:30 pm**, mostly
swing and positional, rarely intraday. **His live window is 60 to 90 minutes a
day.**

Never plan anything for 09:15 and never write "tomorrow morning" in a plan for
him. Anything needing his hands has to fit in that window, in priority order,
and anything readable from logs afterwards must not consume any of it. He has
corrected this more than once.

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

## What he actually trades. Read this before designing anything he will use.

Learned from his vault on 2026-09-08, by reading it rather than by asking him.
He should not have to explain any of it again.

**His profitable era is the model.** Oct 2022 to Apr 2023, 21 swing trades:
**13 wins, 8 losses, 61.9%, net +₹73,676.** Every one of them a multi-leg
structure named by its shape — iron condor, bull call spread, balanced calendar.
Never a single leg. Held days to weeks; one ran a month. That is the era this
terminal exists to restart. `00 - Reference/Historical Swing Trades/` in the vault.

**Calendars are more than half of it.** Ten of the twenty-one. His own framing,
given 2026-09-08: **the far expiry is the hedge and the margin benefit, the near
expiry is where the theta is earned.** Everything is for the near expiry. He
squares off before it: with a Tuesday expiry he closes Monday before the close,
or the Friday before if he is already well in profit or already in a loss.

**A trade is a CAMPAIGN, not a leg, and it changes while it is open.** His own
sheet has "Initial Position Legs", then "Trade Adjustments" (1st, 2nd), then
"Booked Orders / Exits" — often on different days. Trade-01 rolled a short put
from 16,700 to 17,100 mid-life and was closed in two pieces three days apart.
**His words, 2026-09-08:** "In options, you have to manage the trade... if you
don't manage, you won't survive." Any journal or position model that assumes
open-then-close-unchanged is wrong about him.

**His rule for the record, given 2026-09-08.** One trade has one identity. Legs
may be added, removed and squared off inside it, each squared-off leg adding its
own profit or loss to that trade. The trade closes when every leg is closed or
when he says it is closed. A genuinely new position is a new trade. Trades are
classified intraday or swing/positional and still counted together.
**Only a squared-off trade enters the record.**

**Beware one conflict in his own documents.** `01 - Method/Exit Rules.md` §5 says
he does not add to positions in Phase 1 and that every add is a new trade. His
`MY TRADING RULES - ONE PAGE.md`, which is newer and overrides everything, says he
must be free to exit and add legs to convert a straddle into a condor. Both are
right about different things: **pyramiding size onto a bet he already holds is a
new trade; reshaping a structure he already holds is the same trade continuing.**

**Charges are what killed his last year, not strategy.** FY 2025-26, verified
against the raw broker file: gross **+₹6,109**, charges **−₹92,408**, net
**−₹86,299**, across 246 intraday contracts. His transaction-cost rule follows
from that: expected gross must exceed about twice the round-trip charges. Treat
anything that misstates costs as a first-order bug, not cosmetics.

**The failure pattern to design against.** Not missing stops. One badly managed
session every month or two that erased weeks of discipline. Trade-07, a calendar,
planned stop −₹7,000, actual loss **−₹21,000**, three times the stop, after too
many adjustments. Its own lesson line: taking a trade without a proper hedge
leads to big losses.

**Why he stopped and why he is back.** Four years, a losing first two, a
break-even 2023-24 that he credits to Tom Hougaard's *Best Loser Wins*, then
2025-26 back to losses on night shift and alcohol. Sober since April/May 2026,
and this time without forcing it. He stopped trading in March 2026 by choice and
set three conditions in order: sobriety, discipline, then trading. **He has taken
no trade of his own since 31 March 2026.** Any trade row or note dated after that
which he did not create himself is test data.
`00 - Reference/Trading Journey - The Story So Far.md`.

## The market he trades, as at September 2026. Verified, not remembered.

- **NIFTY weekly options expire on TUESDAY**, moved from Thursday in September
  2025. Monthly is the last Tuesday.
- **The lot is 65**, cut from 75 in January 2026. Resolved server-side from the
  FYERS contract master. Never hardcode either number.
- **Securities transaction tax on options is 0.15% of premium on the sell side**
  from 1 April 2026, up from 0.10%. `services/charges.py` already carries this,
  versioned by effective date and computed in `Decimal`. It is the only correct
  charge model in the repository.
- **A calendar spread gets NO margin benefit on the day its near leg expires.**
  This has applied to index derivatives since February 2025; the February 2026
  circular extended it to single stocks. The requirement can roughly double on
  that final day. His practice of closing the day before already avoids it, and
  the terminal does not model it. Tell him before he puts on his first calendar.

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
- **`git fetch` and check whether the branch's PR is already merged before
  pushing more work.** He merges mid-session to review. Commits pushed onto a
  merged branch strand with no PR and no revert button. **This happened three
  times on 2026-09-08**, the last time 38 minutes after the merge, and the next
  branch had to rescue the file.
- **Never open a pull request against another pull request's branch.** GitHub
  only retargets to `main` when the base branch is deleted on merge. PR #35
  merged into a dead end and the live site silently kept the old interface.
- **Merge one pull request, wait for the green tick, then merge the next.** Two
  at once races two deploys and the wrong one can win. A failed build is silent.
- **Only one session may write to the working tree at a time.** Two sessions
  sharing it will fight over the index and the checked-out branch. If two are
  needed at once, one takes a separate clone.
- **Never a worktree that SHARES the primary folder's venv.** That venv is an
  editable install pointing at the primary tree, so a builder using it would
  silently test the wrong source. **A worktree with its OWN venv is allowed**,
  and is how Build B and Build C were both done while another chat held the
  primary folder. Corrected 2026-09-11: the old wording said "never a git
  worktree", which was the right reason attached to the wrong rule.
  **A worktree builder proves the isolation before running a single test:**
  `.\.venv\Scripts\python.exe -c "import swayam; print(swayam.__file__)"`
  The path printed must contain that worktree's own folder name. If it does
  not, stop — the venv points elsewhere and nothing tested there is real.
- **Plan first, plain English, six parts.** Then build. Then hand off, five
  parts. His `/layman-plan` and `/handoff` skills carry the shape.
- **Ask when unsure.** He has said so explicitly, and mid-build is fine.
- **When he says "fix it", stop planning and start typing.** He gets
  impatient with explanation he did not ask for. Plans are for new work; a
  fault he has just shown you is not new work.
- **A refusal on his screen must say what he can DO**, not only what went
  wrong. An execution key error left him unable to trade twice in one
  afternoon with no way out from the page.
- **He judges a screen with words like immature, cheap, and I must feel good
  while managing it.** Those are requirements, not decoration. A cross where
  a dustbin belongs is a real complaint.
- **`node --check` is not verification.** It has passed files the browser then
  rejected. Load the real page in a real browser, in both themes.
- **A thing that has never run has never been tested.** On 2026-09-09 the close
  path was found to write two columns that did not exist. Three independent
  audits had missed it, every test passed, and the code read correctly. It only
  appears when a trade is actually closed, and nobody had ever closed one.
  **Before trusting any path he has not personally exercised, exercise it.**
- **Check that the columns you write actually exist.** `db_guard` stops a test
  writing the wrong DATA, the vault cage stops the wrong FILE, and neither
  catches writing to a column that is not there. `tests/test_written_columns_exist.py`
  compares every column the trade path writes against every column the
  migrations create. Keep it passing; do not weaken it.
- **A note is not a trade, at BOTH ends.** Migration 019 established this for
  entry. The exit side still returned HTTP 500 on a trade already closed in the
  database until 2026-09-09. If a vault write can fail, it goes to the outbox
  and the user's action still succeeds.
- **Verify by invoking, never by reading a status.** Three things had never once
  worked on 2026-09-08 while something downstream reported success. Do not trust
  a status field, a log line saying "started", or a passing test.
- **Fix a rule where the rule lives, not where the symptom showed.** The dead
  expiry was fixed at one route and survived in a service that read the source
  directly. "LIVE" over a closing price was fixed on two screens and survived on
  two more, because all four read one wrong backend flag.
- **`/api/market/data-health` is the ONE clock.** Nothing may say "live" unless
  it says the market is open.
- **The dev environment points at the LIVE database.** The test suite is caged
  (`tests/db_guard.py`) because there is no staging project. Do not weaken or
  remove that guard.
- **The vault is caged too, and for the same reason.** On 2026-09-08 twenty-six
  fabricated trade notes were found in his real journal folder,
  `02 - Projects/Trading/04 - Journal/`. Twenty-two had no database row at all:
  they were written by tests that mock the database, so `db_guard` never saw
  them, while every writer in `journal_writer.py` fell back to his live vault
  path. `journal_writer._default_vault_base()` now refuses during a test run and
  `conftest.cage_the_vault` redirects writes to a temporary folder. **Do not
  remove either.** `tests/test_vault_guard.py` proves both.
- **Anything that writes into his vault must be caged before you run it.** The
  vault is the thing this project exists to protect. Before running the suite,
  check the journal folder is empty; after, check it still is.
- **Update `docs/PLAN.md` as work lands. Do not write a new plan document.**
  Every superseded plan was deleted on 2026-09-08 for exactly this reason.
- When he pastes an Antigravity "done" report, **inspect the real repo,
  database and vault** rather than trusting the summary. Grep for silent
  fallbacks and verify doc claims against real paths.

---

## Where to look

| File | What it is |
|---|---|
| `docs/SUCCESSOR_PROMPT.md` | The prompt he pastes into a new chat, plus what was learned by talking to him. **Keep it accurate** |
| `docs/SWAYAM_START_HERE.md` | Where everything lives, what is verified, what is not done |
| `docs/PLAN.md` | The one plan. **Section 2.12 is the current job.** Section 2.12.0 is the audit of his first three real trades |
| `docs/Independent reports/` | Four audits from 2026-09-07, all marked SUPERSEDED. History only |
| Vault `00 - Developer Logs/SESSION_LOG_2026-09-09.md` | **What the 8/9 September session found and fixed.** A historical record, not an authority. Read it when you need to know why the code looks the way it does |
| `docs/UI_BUILD_BRIEF_ROUND_3.md` | His own sweep of the live pages. **Built and merged**, PR #39 |
| `docs/UI_BUILD_BRIEF_ROUND_2.md` | Round 2. Built and merged. History |
| `docs/CALENDAR_BUILD_BRIEF.md` | Multi-expiry valuation, so calendars work. Briefed and ready. **His decision whether he needs it.** Section 0 has how he actually trades one |
| `docs/UI_BUILD_BRIEF.md` | Round 1, finished and live on 2026-09-08. History |
| `docs/reference/` | The two approved page prototypes, as working code |

Deeper reference only when needed: `WHERE_EVERYTHING_LIVES.md`,
`docs/RUNBOOK.md`, `docs/API.md`, `docs/architecture.md`.

*Real-money trading is code-blocked by absence: there is no order-placement
code anywhere in this repository.*
