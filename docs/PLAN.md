# THE PLAN

> **The one plan file.** Everything before this — Phase A, Phase 1 v5, v6, v7,
> v8 and v9, and the Strategy Builder v2 plan — was folded into this on
> 2026-09-08 and deleted. Git still has them if anyone ever needs them.
>
> **Update this file as work lands. Do not write a new plan document.**
>
> Read `SWAYAM_START_HERE.md` first for where everything lives and what is
> verified true. This file is only what happens next.

---

## HOW TO USE THIS FILE

One list, in priority order. When something is finished, move it to section 4
with the date and the proof. When something new is decided, add it here rather
than starting a new document. That is the whole system.

**Nothing in this file overrides `MY TRADING RULES - ONE PAGE.md` in his vault.**

---

## 1. IN FLIGHT RIGHT NOW

### Where this stands, end of the 2026-09-08 EVENING session

Round 2 is **built, reviewed and merged**, and **the mis-merge is fixed**. PR #37
put the desk work on `main`; Cloud Run is on `swayam-dashboard-00043-8xq`, whose
image digest was checked against the build for `main` at `1699157`. **Every
visual change is live.**

**A new fault was found and fixed the same evening: the desk was exhausting the
FYERS request budget.** See §1a. Branch `feature/swayam-desk-live-ticks-018`.

**His deadline: Home and the Strategy Desk right by Friday 2026-09-11, so paper
trading starts Monday 2026-09-14.** Wednesday, Thursday and Friday are the
working days. There is room; do not rush and do not skip verification.

### The mis-merge. RESOLVED 2026-09-08 by PR #37. Kept for the lesson.

**PR #35 was merged into PR #34's branch, not into `main`.** It was opened with
PR 1's branch as its base, and GitHub did not retarget it when PR 1 merged
first. GitHub reports it as merged, and it is, into a branch that was already a
dead end.

So `main` and the live site carry **PR 1 only**: real numbers, the live-price
plumbing, the working rules, breadth and futures volume. **Everything visual is
missing** — the Devanagari mark, the auto-theme fix, the depth and the larger
type, the ritual tile, So Far Today's play button and collapse, chat thumbnails,
one leg per row, the greeks in the left rail, the payoff axis and the resets, the
seventeen presets, and the whole option chain panel.

Branch `feature/swayam-desk-onto-main-017` merged that work onto `main` as
PR #37 at 18:18 IST. Verified: the desk commit `f7bd1ec` is an ancestor of
`main`, the build for `1699157` produced image digest `e440efae…`, and live
revision `swayam-dashboard-00043-8xq` runs exactly that digest at 100% of
traffic. `feature/swayam-round2-pr2-the-desk-016` is now safe to delete.

**The lesson, and it is new:** opening a pull request against another pull
request's branch is not safe here. GitHub only retargets to `main` when the base
branch is deleted on merge. Stack the work in one branch, or open the second
pull request against `main` after the first has landed.

### 1a. The FYERS request budget. FOUND AND FIXED 2026-09-08 evening.

**Not in any earlier plan. Found by reading the live logs, not by being told.**

Between 18:29 and 18:31 IST the live site logged **46 refusals from FYERS**
("request limit reached") in ten minutes, **164 leg-price requests** in the same
ten minutes, and **three 503s on `/api/nifty/spot`**. Leg prices went blank on
the desk with nothing on screen explaining why.

**The cause, in three parts.** The desk re-quotes every leg every 5 seconds. The
shared chain cache lived 3 seconds, which is less than the poll, so it never
survived from one round to the next and every leg on every round became a FYERS
call. A far expiry cost two calls rather than one. And nothing anywhere backed
off when FYERS refused, so it asked again 5 seconds later, indefinitely.

**The fix.** `src/swayam/api/chain_feed.py`, built on the same leader/follower
shape as the spot feed. A browser request now registers interest in an expiry
and reads what the feed last fetched, with the age attached. The feed refreshes
what is in demand on its own cadence, one call per expiry however many legs or
browsers are watching, stands back when FYERS refuses, keeps the last real chain
rather than blanking it, and slows to one read every five minutes after the
close. A cold four-leg page load is single-flighted into one call.

**Measured against the real backend and live FYERS, 2026-09-08 19:15 IST:**

| | |
|---|---|
| 60 leg quotes from a cold start | **2 FYERS calls, 0 refusals** |
| A full desk session: page load, preset, pricing, several minutes open | **2 FYERS calls, 0 refusals** |

**And the half he actually asked for: he must be able to see it.**
`GET /api/market/data-health` returns one honest state, `live`, `delayed`,
`closing` or `unavailable`, taking the **worst** of the chain and the tick feed
so nothing hides behind a healthy sibling. `web/src/components/data-health-strip.js`
draws it at the top of Home and the desk **in every state, including the healthy
one**, because a warning he has never seen before is one he will not trust the
first time it matters. When something is wrong it also says what to do, and it
names the token case specifically, because that one needs a person.

**Two related lies were found and fixed while verifying this.** Home's NIFTY
card and the desk's spot chip both said **LIVE** at 19:18 IST with the market
shut, on the same screen as a strip saying CLOSED. Both now follow the market
clock. The timestamp still names when the price was read, which was always the
honest half.

### Tomorrow morning, and only with the market open

None of these can be claimed before 09:15 IST. Do not describe any of them as
working until they have been run and the answer read.

1. **Do prices actually tick.** Watch `frames_sent` climb on
   `/api/market/spot-feed/status`. A socket that merely opened is not a tick.
2. **Do leg prices move on their own** within a minute of a real market move,
   on the desk, without touching anything.
3. **Do the rules answer every time.** Call `/api/strategy/validate` twenty
   times against the live site and expect twenty 200s. Before round 2 the same
   test gave roughly half 500s.
4. **Does the recorder write its first file** into
   `gs://swayam-capital-options-data`. The bucket is empty; one object proves it.
5. **Is the token re-read without a restart.** Refresh it, wait, and confirm the
   live site still prices without a redeploy.
6. **Put-call ratio and max pain against a live chain**, not the dead one.
7. **One question to the AI**, "what is my running-loss cap today?" It must
   answer with 1% of the live balance and name FYERS. Costs money; ask once.

### After market, any time. In this order.

1. ~~**Deploy the recorder.**~~ **DONE 2026-09-08 19:05 IST**, on his explicit
   go. Revision `swayam-recorder-00002-lez` is ACTIVE and answers HTTP 200.
   **Proven:** it starts, runs the new code, refuses correctly outside market
   hours, reads the token, and FYERS returns 82 real option rows to its own
   fetch path. **NOT yet proven:** that it writes to `gs://swayam-capital-options-data`
   under its own identity. Only 09:15 IST tomorrow can show that. All three
   permissions were verified present at resource level first: `run.invoker` on
   the service, `storage.objectAdmin` on the bucket, `secretmanager.secretAccessor`
   on the token. **Open question for the first file: spot and every Greek came
   back as 0.0 in the local probe.** See §2.10.
2. ~~**The after-hours blackout.**~~ **FIXED**, and verified against real data at
   19:08 IST on a weekly expiry day. See §2.8.
3. **The Trade Journal, all three faults in one pass.** See §2.2. From Monday
   that page holds his paper record, so it is on the critical path. **This is
   the next job.**
4. ~~**Remove the deleted reward-to-risk check.**~~ **DONE.** See §2.9.
5. **Close-out.** Delete merged branches, remove the leftover worktree
   `.claude/worktrees/swayam-capital-ui-build-f2a909`, record what is live.
6. **The calendar backend.** `docs/CALENDAR_BUILD_BRIEF.md` PR 1. Independent of
   everything above and can start any time.

### On calendars, his position as of 2026-09-08

Undecided, and deliberately so. Whether he needs them for Monday depends on the
market: if volatility is already high with no event ahead, he will not put on a
calendar, because the premium can collapse. If an event is coming and volatility
is rising, a calendar is the trade. **He will decide when he has looked at the
market. Do not push him and do not assume either way.**

## 2. NEXT, IN ORDER

### 2.1 Notes into Obsidian from the cloud
Blocked on a Google policy, not on code. `scripts/link_google_drive.py` is
written and works.

A service account can never do this: zero Drive storage quota since June 2023,
and both standard escapes need Workspace, which he does not have on a personal
Gmail account. So the app must act as him, with the `drive.file` scope, which
is non-sensitive and needs no Google verification.

**The open question is not technical.** Publishing the consent screen gives a
sign-in that never expires, but Google asks for a privacy policy and a terms of
service URL on a domain he owns, and his domain now sits behind sign-in.
Staying in Testing works immediately but the token dies every seven days.

**Decide where those two pages live.** A plain static page on a separate
address is probably enough. Ask him; do not guess.

**Never upload a logo on the branding page.** The console states that forces
the app into verification.

Nothing is lost meanwhile. The outbox holds the note and the local drainer
completes it, and his PC is on whenever he trades.

### 2.2 The Trade Journal, three faults in one pass

Found in review on 2026-09-08. All three live on the same page, so fix them
together, and before any performance figure appears on a screen.

1. **A ninth invented constant.** `api/routes/journal.py` lines 297 and 542
   hardcode a margin base of `500000.0`, used for
   `cumulative_pnl_pct_of_margin` and `max_drawdown_pct_of_margin`. Rendered by
   `web/src/components/kpi-strip.js`. It is a different made-up number from the
   Rs 8,50,000 the AI was using, with the same disease. Take live capital from
   `services/capital.py`, as execution and positions now do.
2. **The page writes to the database when you open it.**
   `web/src/pages/journal.js:58` fires `POST /api/journal/archive-test-trades`
   on the first load of each browser session, gated only by `sessionStorage`.
   Nothing is clicked. Pre-existing and wrong; make it explicit or remove it.
3. **Analytics does not filter `provenance`**, so any win rate or cumulative
   profit would be computed from the 81 quarantined build-and-test rows.

### 2.2b Journal analytics must exclude test rows
`swayam_positions` and `swayam_journal_entries` both carry `provenance`. The
analytics endpoint does not filter on it, so any win rate or cumulative profit
today would be computed from 81 rows of build-and-test data. **Fix this before
any performance figure appears on a screen.**

### 2.3 Charges applied at execution
The versioned charge engine is real and the risk gate uses it. The execution
path still closes with a flat `ESTIMATED_CHARGE_PER_LEG_INR` of ₹150. Wrong,
but it changes a recorded result rather than a decision he makes at the screen.

### 2.4 Live ticks — MOVED INTO ROUND 2, PR 1 (steps 4 to 6)
`/ws/spot` accepts a connection and answers ping with pong. Nothing is ever
pushed, so the header polls every ten seconds and the snapshot card never
updates at all. The FYERS websocket library now imports (it needed
`setuptools<81`), so this is buildable. Feed the ticker and the header from it.

Also unread and available today: **volume** from the FYERS quote. Market
breadth has no free source and must keep saying `unavailable`.

### 2.5 Kill switch
A database-backed global halt blocking every risk-increasing action at the
backend. Close, reduce, journal, notebook and audit stay permitted. Worth
having, worth much less while no code path can place a real order.

### 2.6 Scheduled backups
`scripts/backup_supabase.py --gcs` works, verifies its own upload, and the
restore drill passed on 19 tables and 600 rows. It has run **once, by hand**.
Run it nightly and show the last-backup age on screen. Say plainly that it
protects against damage inside the project, not loss of the project itself,
which needs a second project he cannot currently create.

### 2.7 The two long-standing test failures
`tests/api/test_market.py::test_get_option_chain_returns_strikes` and
`tests/test_notifications.py::test_execute_endpoint_best_effort_dispatch_on_success`.
Both pre-date all of this. Do not "fix" them by weakening assertions.

---

### 2.8 The after-hours blackout, which he reported himself — FIXED 2026-09-08

**His words, 2026-09-08:** "when the market closes, I notice that I lose all the
prices and everything. It should not happen. I should have the last traded price
of the day... I should also do my homework, strategy building, etc., after the
market closes."

**Root-caused live at 17:44 IST with the market shut. FYERS is not the problem.**
The spot came back at the close (23,635.1) and all 26 option rows carried a real
last traded price, open interest, change in open interest and volume.

**The fault is ours.** `/api/market/expiries` keeps an expiry in the list once
its day has passed: it computes `cal = (d - today).days` and filters nothing, so
after 15:30 on an expiry day the app still offers today's expiry, labelled
"08 Sep (0d)". Those contracts no longer exist and every price reads 0.05, which
is what an expired option is worth. 2026-09-08 was a weekly expiry, which is why
he hit it that evening.

**Fixed.** An expiry is dropped once its day is over: before 15:30 on expiry
day it stays, because it is the live front month he may well be trading; after
15:30 it goes. The weekly and monthly badges move to whatever replaced it, which
was a second bug caught only by running it against real data. Prices after the
close are labelled `closing`, never `live`.

**Verified 2026-09-08 19:08 IST**, against the real contract master, on a
weekly expiry evening: the list now starts at 15 Sep (7d), `expired_today`
names 08 Sep, and the weekly badge sits on 15 Sep.

There was a **second cause of the same symptom**, not diagnosed here at the
time: the FYERS budget exhaustion in §1a. Both are fixed.

### 2.9 The deleted reward-to-risk rule is still running — FIXED 2026-09-08

`api/routes/validation.py` still evaluates the reward-to-risk check as an
advisory. That rule was deleted on 2026-09-07 and does not exist any more. Round
2 was forbidden from touching that file's arithmetic, so the desk simply drops
the line from what it prints.

**Removed.** The check, its entry in the display-name map, and the now-unused
`rr_implied` local in that function are gone. `rr_implied` itself stays
everywhere else: it is a number he reads in the metric row, not a rule with a
floor to pass, and his approved design lists it there.

**Still to decide, not done on my own initiative:** `no_single_leg` is also
evaluated in that file, and `CLAUDE.md` lists "no single-leg trades ever" among
the rules he deleted. The rebuilt desk does not render it, so nothing wrong
reaches his screen today. **Ask him before removing it.**

### 2.10 The recorder records zeros where it should record numbers

Found while proving the recorder on 2026-09-08. Its own fetch path returns 82
real option rows with real close, volume and open interest, but
`underlying_spot`, `iv`, `delta`, `gamma`, `theta`, `vega`, `change_in_oi` and
`open/high/low` all came back **0.0**. The probe ran after the close, so some of
it may be FYERS returning nothing out of hours, but `underlying_spot` is
available at any time and should not be zero.

**The README claims it calculates Greeks and tracks open-interest change.** If
those columns are zero every minute, the recorded history is far less useful
than it looks, and a calendar backtest is the thing it exists to feed.

**Check the first real file after 09:15 tomorrow before trusting the recorder.**
One object in `gs://swayam-capital-options-data` proves it writes; reading the
columns proves it is worth writing.

## 3. THE BIG ONE, AFTER THE ABOVE

### Multi-expiry valuation, so calendars work — BRIEFED. `docs/CALENDAR_BUILD_BRIEF.md`

**His decisions, settled 2026-09-08, do not relitigate.** Risk is measured at
the NEAR expiry date, never the far one, because he exits the whole trade at or
before the near expiry. No decay-based early-exit trigger: "We cannot decide
70%, 80%, or 50%. Those market dynamics we cannot predict. We only know what is
fixed: the expiry date." A calendar is a swing trade and may be carried
overnight. How calendars fit his method, around the budget and RBI and Fed
announcements, is deferred by name.

**The volatility question was researched, not guessed.** Every retail platform,
Sensibull included, holds the far leg's volatility at today's level to the near
expiry, and every source flags that as the weak point around events. The payoff
graph will match them and say so. The two rules that gate money will instead use
a shock MEASURED from real India VIX history over the horizon to the near
expiry, propagated to the far leg by the square-root-of-time rule, tested both
directions, worse answer wins. If VIX history is short the rule says
`unavailable` rather than falling back to a constant.

**Backend first, and it can start immediately** — round 2 is forbidden from
touching `options_math/` and `rule_engine/`. The screen work waits until round 2
is on `main`, because both change the leg table.
Calendars are visible and computable but **blocked from execution**, because
the payoff across two expiries is approximate. **Ten of his twenty-one
historical trades are calendars, and on 2026-09-08 he said he uses them more
than half the time and that they were profitable for him.** This is the largest single gap between what
he actually trades and what the terminal supports, and it deserves its own run.

Everything else from the old plan's "Sensibull-grade builder" is now in the
approved prototypes and the UI brief: the target slider, the date slider,
editable per-strike volatility, one recalculation feeding every number, the
metrics strip, the ready-made grid, and execution on the page. Open interest
bars on the payoff chart and the standard-deviation table are the two pieces
the prototypes do not yet carry; add them with this work.

### Then: the AI chapter
He has said repeatedly this comes after the infrastructure is solid. The four
learning loops are described in the vault at
`06 - Platform Plan/Self-Improving Agent Integration.md`. Do not start it early.

**Standing cost rule, which is not negotiable:** AI-heavy features are always a
manual button, a 60-minute cache and a daily cap. Never fire on page load. Left
unguarded this was estimated at ₹4,000 a month.

---

## 4. DONE, WITH PROOF

Kept short. Detail is in the git history and the pull requests.

| Date | What | Proof |
|---|---|---|
| 2026-09-08 | Test suite can no longer write to his live record | 81 rows before a full run, 81 after. It used to go 67 → 79 → 81 |
| 2026-09-08 | Two fixture rows quarantined | Zero open positions; the live API returns `[]` |
| 2026-09-08 | Risk panel stopped overstating risk 100x | 1.74% rendered as 1.74%, with a regression test |
| 2026-09-08 | One click, one trade | Test simulates a lost response, asserts one position |
| 2026-09-08 | A note can never fail a trade | Outbox plus drainer; unreachable vault returns HTTP 200 |
| 2026-09-08 | Recorder works, first time ever | Was missing `run.invoker`; now answers correctly |
| 2026-09-08 | Google sign-in live | Every path 302s to Google, on the domain and the raw run.app URL |
| 2026-09-08 | AI reads So Far Today | Section appears in a real assembled context |
| 2026-09-08 | AI reads readiness | The query had never once run; Postgres 42703 is gone |
| 2026-09-08 | FYERS websocket library imports | Needed `setuptools<81` |
| 2026-09-08 | Home and Strategy Desk rebuilt to the approved prototypes, LIVE | Verified in a browser against his live account, market open |
| 2026-09-08 | The gap rule stopped blaming his data | Said "needs measured daily moves" when the backend had 20 sessions; now says "intraday" |
| 2026-09-08 | The desk work reached `main` and the live site | Image digest of revision 00043-8xq matches the build for `main` at `1699157` |
| 2026-09-08 | The desk stopped exhausting the FYERS budget | 60 leg quotes from cold: 2 FYERS calls, 0 refusals. It had been 46 refusals in 10 minutes |
| 2026-09-08 | He can see whether prices are real, at all times | The strip reads CLOSED with the age, on both pages, in a browser against the live backend |
| 2026-09-08 | The dead expiry stopped being offered after the close | Real contract master at 19:08 IST: list starts 15 Sep, `expired_today` names 08 Sep |
| 2026-09-08 | Nothing calls a closing price "live" any more | Home badge and desk chip both read "at the close · 19:22 IST" with the market shut |
| 2026-09-08 | The deleted reward-to-risk rule stopped being computed | The four-rule block renders exactly four rules from a live balance of ₹9,71,111 |
| 2026-09-08 | Recorder deployed, first time since 3 September | Revision `swayam-recorder-00002-lez` ACTIVE, answers 200, reads the token, FYERS returns 82 rows |
| 2026-09-07 | Release 1: lot 65, real margin, live capital, his risk rules | PR #23 |

---

## 4b. WHAT HAPPENED ON 2026-09-08, AND WHAT I SAW

A long session. Recorded because the pattern matters more than the list.

**What I set out to do** was work plan v9's unfinished scope. **What I found**
was that Release 1 had been handed over as complete while its own Steps 5, 6
and 7 were untouched, and that two separate things had never worked at all
despite being reported as fine.

**Three things had never once run, and nobody knew:**

- The **recorder** had failed every minute of every trading day since
  3 September. One missing grant: the service had a completely empty IAM
  policy, so nothing could invoke it. His options data bucket is still empty
  and that data is not recoverable.
- The **AI's readiness query** had never succeeded. It asked for four columns
  that do not exist on that table, so every call failed with Postgres 42703.
  The test asserted the same non-existent columns, which is how a permanently
  broken query kept passing CI.
- The **FYERS websocket library** would not import at all, because setuptools
  81 removed a package it needs.

**The lesson, and it is the one worth carrying forward:** each of these failed
*silently* and something downstream reported success anyway. When checking
whether a thing works, invoke it and read what comes back. Do not read a status
field, a log line that says "started", or a test that passes.

**A mistake I made twice:** pushing commits onto a feature branch after its
pull request had already been merged, stranding them with no revert button.
The rule is in `CLAUDE.md`; I still did it. Check before pushing.

**A mistake in my own script:** the step that removed public access was written
so both the error and the exit code were discarded. It failed and reported
success. Nothing was exposed, because sign-in intercepts first, but the site
would have been public again the moment sign-in was switched off. The same
shape of bug as the three above, written by me, on the same day I was fixing
them.

**What he decided, that changed the work:** the pages are replaced directly
rather than built alongside; So Far Today moves inside the AI chat and the AI
must read it; the AI chat itself is not to be touched; and the design is his
four rules first, big numbers, black and white, nothing invented.

---

## 4c. TWO TRAPS LEARNED 2026-09-08, BOTH SILENT

**Merging two pull requests within seconds races two deploys, and the wrong
one can win.** Both build jobs tried to deploy `swayam-dashboard`. The first
changed the service; the second arrived holding a stale version number and
Cloud Run aborted it with `ABORTED: Conflict for resource`. The refusal was
correct. The problem was *which* one lost: the winner carried a documentation
change and the loser carried the new pages, so the site restarted with a fresh
token and the OLD interface. Re-running the trigger against `main` fixed it.

**Tell him: merge one PR, wait for the green tick, then merge the next.**
And a failed build is silent. Nothing told him; he found it by looking. Same
shape as the recorder failing every minute for five days unnoticed.

**The token still needs a restart to reach the live site.** `FYERS_ACCESS_TOKEN`
is wired as `secretKeyRef` with key `latest`, and Google resolves "latest" ONCE
at container start. His 08:31 refresh could not reach a container started at
23:27 the night before. He only escaped it because merging triggered a deploy.
On a day with no deploy his terminal shows no prices all afternoon and nothing
explains why. **This is section 2.4 and it is the highest-value hour of work
left.**

---

## 5. THE MORNING REVIEW CHECKLIST

For the cloud session's pull request. **Do not let him merge before this
passes.** Work through it in order and report honestly.

1. **Search the diff for the prototype constants.** `SPOT`, `BAL`, `CAP1`,
   `CAP2`, `CAP5`, `LOT`, `AVG_MOVE`, `MARGIN_USED`, `MARGIN_CEILING`, `23779`,
   `971002`, `9710`, `554961`, `65`, `80.1`. **Every one of these must have
   become a live API value.** A hardcoded figure here is the exact
   fabricated-data failure this project exists to prevent, and it is the most
   likely mistake an unattended session makes. This check comes first.
2. **Grep for fallbacks**: `|| 0`, `|| 75`, `?? 0`, and any literal rupee
   amount in a render path. Missing data must render `unavailable`.
3. **Confirm `pct_of_margin` is not multiplied by 100** anywhere.
4. **Confirm the class contracts survive**: `HomePage.niftyChart.retheme`
   exists (main.js calls it unguarded and will throw otherwise),
   `StrategyBuilderPage.payoffChart.retheme` and `refreshPositions` exist.
5. **Confirm the AI chat is untouched** and So Far Today moved inside it.
6. **Run it against the real backend**, which the cloud session could not do.
   Load both pages, check every figure against the API response, and look for
   console errors.
7. **Check his fourteen decisions** in `UI_BUILD_BRIEF.md` section 2, one by
   one. Legs at the top, one expiry and multiplier for all legs, expiry above
   the presets, dustbin icon, rules at the bottom with execute, margin first in
   the metric row, the payoff graph still draggable, ticker, NIFTY sidebar,
   ritual as a thin strip, record toggle, black and white theme, no purple.
8. **Read what it says it could not verify**, and verify those things.

Then tell him plainly what is right, what is wrong, and whether to merge.
