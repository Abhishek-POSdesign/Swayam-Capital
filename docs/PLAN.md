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

### Round 2: his feedback on the new pages. Briefed, awaiting the build.

He used the rebuilt Home and Strategy Desk with the market open on 2026-09-08
and gave twenty-two pieces of feedback. His verdict on round 1: "the data is
live, and the new website is live. I need some improvements."

**The brief is `docs/UI_BUILD_BRIEF_ROUND_2.md`.** Twenty-one steps, to be shipped
as TWO pull requests by an unattended cloud session. He approved the plain-English
plan at https://claude.ai/code/artifact/b99c1be3-8a29-4f54-af7c-a9917a449321 .

Five live faults were found while planning it, all proven against the running
system on 2026-09-08. They are the reason PR 1 exists:

1. **The rule check crashes about half the time.** Two Gunicorn workers fight
   over an exclusive DuckDB file lock. Live evidence: 200, 500, 200, 500 across
   the four `/api/strategy/validate` calls made today. The Supabase fallback in
   `realized_vol.py` is correct and unreachable, because it sits after the line
   that fails.
2. **Rules 2 and 4 can never light up.** The desk never sends a planned exit
   date, so rule 2 is always "intraday, not tested"; rule 4 is hardcoded idle in
   the page.
3. **Nothing on either page refreshes.** `broadcast_spot()` is never called from
   anywhere, Home has no timer at all, and leg prices are fetched once. He cannot
   trade from a screen whose option premiums are twenty minutes old.
4. **The AI is running the rule set deleted on 2026-09-07.** It told him his risk
   cap was Rs 8,500, which is 1% of the stale `swayam_config.margin_base_inr` of
   Rs 8,50,000. It also believes the black-swan ceiling is 3% not 5%, that an
   R:R floor exists, and that a red readiness verdict can stop him.
5. **The recorder fails every minute** with `Please provide valid token`. It runs
   each minute so its container never goes cold and never re-reads the secret.
   Same root cause as the morning no-prices trap. Today's option chain is lost.

Plus **eight invented constants** still in the market feeds, and the option chain
endpoint **ignores the expiry it is asked for** and always returns the nearest.

**Two things he decided that change later work:**

- **He uses calendar spreads more than half the time and they were profitable.**
  That raises section 3 from "the big one" to the next job after this round.
- **He mostly carries positions overnight.** He arrives at 2:30 pm for swing and
  positional trades, not intraday. The desk must default to the overnight answer.

**The logo is settled:** the full Devanagari spelling with the tagline
"Discipline builds tomorrow", nothing drawn above the letters. His wife is a
graphic designer and will do the letterform work later.

Do not start anything in section 2 until he says the pages are right.

### State as of the end of the 2026-09-08 session

- PRs #23 through #30 are all merged. `main` is at `cb2c75a`.
- Cloud Run revision `swayam-dashboard-00037-7cz`, deployed 09:04 UTC, is live
  and carries both the new pages and today's FYERS token.
- No branch is open. No commit is stranded. Nothing is uncommitted.
- Verified live with the market open: balance ₹9,71,111 from FYERS, the four
  caps derived from it, a bear put spread at the 29 Sep expiry pricing from
  the real chain, max profit ₹8,570 and max loss ₹4,430 summing to the 200
  point width times 65.

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

### 2.2 Journal analytics must exclude test rows
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
