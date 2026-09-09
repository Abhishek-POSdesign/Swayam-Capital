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

**`docs/ROADMAP.md` sits above this file.** It is the direction, in his words;
this is the work. Every item here belongs to one of its four horizons.

One list, in priority order. When something is finished, move it to section 4
with the date and the proof. When something new is decided, add it here rather
than starting a new document. That is the whole system.

**Nothing in this file overrides `MY TRADING RULES - ONE PAGE.md` in his vault.**

---

## 0. THE THING MOST LIKELY TO BE GOT WRONG

**He is not at his desk in the morning.** He works a night shift, wakes around
1 pm IST, and is at the screen by about 2 pm. He trades between 1 and 2:30 pm,
mostly swing and positional, rarely intraday.

So a plan that says "tomorrow morning, with the market open" is a plan he cannot
run. **His live window is roughly 14:00 to 15:30 IST, which is 60 to 90 minutes,
once a day.** Anything needing his hands must fit inside it, in priority order.
Anything readable from the logs afterwards must not consume any of it.

Every dated plan in this file assumes that. Earlier versions did not, and he has
had to correct it more than once.

---

## 1. IN FLIGHT RIGHT NOW

### Where this stands, end of the 2026-09-08 LATE EVENING session

**All merged, all deployed, verified by image digest rather than by hope.**

| | |
|---|---|
| Live revision | `swayam-dashboard-00045-lg2`, running the image built from `main` at `573cd6b` |
| Round 2 | PRs #32 to #37. The desk and Home rebuilt to his approved prototypes |
| The FYERS request budget | **Fixed**, PR #38 |
| Round 3, Home's dead space | **Fixed**, PR #39 |
| The recorder | **Deployed** 19:05 IST, revision `swayam-recorder-00002-lez`. Its first real chance to write is 09:15 on the next trading day |
| Tests | Python **413 pass, 1 fail**. JavaScript **216 pass, 0 fail**. The one failure is `test_notifications` dispatch, confirmed identical on a clean tree, so it pre-dates all of this |

**His deadline is Friday 2026-09-11.** Paper trading starts when the live
verification passes, not on a fixed date. His words: "I'm not keeping a minimum
fixed date, but a deadline is fixed."

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

### 1b. Round 3, the UI brief. MERGED AND LIVE 2026-09-08 night, PR #39.

`docs/UI_BUILD_BRIEF_ROUND_3.md`, written from his own sweep of the live pages.
Branch `feature/swayam-round3-home-and-chat-019`. **Note the brief itself was
stranded** on `feature/swayam-desk-live-ticks-018` after PR #38 merged; this
branch carries it, so merging this puts the brief on `main` too.

What landed, all of it verified in a real browser against a backend started
from this branch, in both themes:

- **The dead background is gone.** Open positions left the half-width cell and
  became a full-width collapsible line directly under the health strip. Your
  record took that cell instead and now draws six real rows, so the cell fills
  its own height and there is nothing for Events ahead to stretch around.
- **Open positions colours from the money and nothing else** — grey flat, sage
  in profit, coral in loss. Shut it still carries the count, the combined
  profit or loss and the running-loss headroom. Open/shut is remembered in
  `localStorage` under `swayam-home-positions-expanded`.
- **Profit and loss comes from `/api/positions/live`**, valued against the
  chain. `/api/positions` carries a stored figure that defaults to zero and it
  is no longer trusted for money. A partial valuation is never summed into a
  total that looks whole.
- **Today's limits is no longer a card.** The four figures are a band inside
  Your money, on their own ground with their own heading. **The margin ceiling
  now appears exactly once** — it is rule 4, and it had been printed both as a
  money tile and as a limit, which he counted. The intraday-entry paragraph
  moved to the desk.
- **Your record shows six figures, with a dash where nothing is known.** The
  journal returns `0.0` for expectancy and `100.0` for discipline on an empty
  book; neither is ever printed. `/api/journal/trades` gained a `mode` filter
  so "Paper" means paper rather than every book summed.
- **Events ahead shows `impact_brief`** — already written by the curator,
  already in the response, previously discarded. It floats on hover, focus or
  tap so the card keeps its size, which he asked for explicitly. Rows without
  a brief get no marker.
- **Both chats** lost the saturated bubble. Sage tint on his, no background at
  all on the AI's.
- **The lot multiplier is a stepper.** Floor of one, enforced on every path.
- **`.why` rose from `--fg-3` to `--fg-2`.** Measured: 6.18:1 light, 7.84:1
  dark, from roughly 3.0 and 4.3.

**One thing beyond the brief, and it is rule 2.** The Sectors card was caught
saying "LIVE · read 20:51 IST" beside a strip saying CLOSED — the third and
fourth places this has happened. `nifty_snapshot.py` is untouched, as §8 of the
brief requires, but no label on Home now says LIVE unless
`/api/market/data-health` says the market is open.

**The backend half is now also FIXED**, in the close-out change. The rule for
when an expiry stops existing moved to `services/expiry.py`, so every caller
inherits it instead of each one deciding for itself. The `spot_live` flag that
made four screens claim LIVE is fixed at source in the same change.

**Nothing here has been seen with a real open position**, because he has never
had one. He has agreed to take a dummy paper position with the market open.
Until that happens, the strip's profit, loss, colour and headroom are verified
only against injected data, not against his own trade.

### THE LIVE VERIFICATION — RUN 2026-09-09. Read this before re-running it.

**He ran it. Most of it passed. The gate is no longer the blocker; the desk is.**

| Reading | Result |
|---|---|
| Token refreshed and reached the live site | **PASSED.** No redeploy, no restart. First time ever proven in production |
| The recorder wrote to its bucket | **PASSED.** `2026-09-09/nifty_chain.parquet`, its first object ever |
| The desk held live prices for a whole session | **PASSED.** Data-health read LIVE with the age in single-digit seconds |
| The rules answered every time | **PASSED.** Twenty of twenty on a scripted run, and on all three real trades |
| A real open position, seen with real data | **PASSED, and it exposed most of section 2.12** |
| Closing a trade | **PASSED on the third attempt.** It was impossible until migration 020 that morning, and there was no button until he did it from a terminal |
| The AI answered his running-loss cap | **PASSED.** ₹9,705, named FYERS as the source |

**What it cost to learn:** four separate faults in the exit path, a dead live
profit-and-loss call, an execution key that only ever allowed one trade per
browser, and a ghost position. All fixed on the day. Section 2.12.0 has the full
audit of what his three trades did.

### The original script, kept for the next time it is run.

**Nothing below has ever been run against a live market since rounds 2 and 3
landed.** Until it has, nothing here may be described as working. Read section 0
first: he has 60 to 90 minutes, from about 14:00 IST, and not a minute at 09:15.

#### What he does. Four actions, about 30 minutes of his 90.

Ordered so that if he runs out of time, the things that block later work are
already done.

1. **Refresh the FYERS token** with `.\Refresh-Token.ps1` as soon as he sits
   down, not before. A token generated pre-dawn has been rejected by 13:30.
   **No redeploy or restart should be needed.** That is the fourth reading below
   and it has never been proven in production.
2. **Open the Strategy Desk, load a four-leg structure, leave it open** for the
   session. That is the chain-feed load test and it runs in the background at no
   cost to him.
3. **Take one dummy paper position, then close it.** He has never had one.
   *Nothing* about an open position has been seen with real data: not the Home
   strip's colour, not its combined profit and loss, not the desk's margin-used
   figure feeding rule 4, not the Trade Journal row. Closing it also gives the
   record its first complete trade.
4. **Ask the AI exactly one question:** "what is my running-loss cap today?" It
   must answer with 1% of the live balance and name FYERS as the source. It
   costs money, so once.

#### What he reads back. One command.

```
gcloud storage ls -r gs://swayam-capital-options-data/
```

One object proves the recorder finally writes. **Then look inside it.** In a
local probe on 2026-09-08 the price, volume and open-interest columns were real
but `underlying_spot` and every Greek came back as `0.0`. See section 2.10.

Beyond that he only glances at the desk: does the data-health strip read **LIVE**
in green, and does the age beside it stay small.

#### What is read from the logs afterwards, using none of his time

- **FYERS refusals stayed at zero** under a real four-leg load. `fyers_refusals`
  on `/api/market/data-health`, and `"request limit reached"` in the Cloud Run
  logs. The live site has already gone from 46 refusals in ten minutes to zero
  across two hours and 124 requests, but that was after the close.
- **The tick feed pushed frames.** `frames_sent` climbing on
  `/api/market/spot-feed/status`. A socket that opened is not a socket that ticks.
- **The rules answered every time.** Twenty calls to `/api/strategy/validate`,
  twenty 200s. Before round 2 the same test gave roughly half server errors.
- **The token was re-read without a restart.** `services/fyers_token.py` reads
  Secret Manager at request time with a 60-second cache, and the dashboard's
  service account holds `secretmanager.secretAccessor` on the secret. Code and
  permission are both in place. **Never proven in production.**
- **Put-call ratio and max pain against a live chain**, not a dead one.

### After the live test, in order

1. ~~The Trade Journal's four faults.~~ **DONE 2026-09-08 night.** Section 2.2,
   and section 4 carries the proof.
2. **THE TRADING DESK: execute, manage, exit. Section 2.12.** PRs 1, 2 and 4
   MERGED 2026-09-09. **PR 3, the position area with the exit ticket, is the
   next build**, then PR 5, the option chain tested live. Then §2.13, the
   vault bridge, then **§2.14's read-only broker bridge**, which is his
   decision of 2026-09-09 night on real-money orders. He took three paper trades on 2026-09-09 and
   could not execute cleanly, could not see what he held, and could not exit
   without a terminal. His decisions on how it should work are recorded there
   verbatim. Section 2.11's campaign model is folded into it.
3. ~~Charges at execution.~~ **DONE 2026-09-09, per leg.** Section 2.3.
4. **Scheduled backups.** Section 2.6.
5. **The kill switch.** Section 2.5.
6. **The calendar backend.** Section 3, and `docs/CALENDAR_BUILD_BRIEF.md` PR 1.
   Independent of everything above and can start any time.
7. **The AI chapter.** Section 3, after the above. He named it himself as
   something that must be in the plan.

### On calendars, his position as of 2026-09-08

Undecided, and deliberately so. Whether he needs them for Monday depends on the
market: if volatility is already high with no event ahead, he will not put on a
calendar, because the premium can collapse. If an event is coming and volatility
is rising, a calendar is the trade. **He will decide when he has looked at the
market. Do not push him and do not assume either way.**

## 2. NEXT, IN ORDER

### 2.1 Notes into Obsidian from the cloud — SUPERSEDED BY 2.13

> **Read 2.13 instead.** It carries the current Drive status, checked 2026-09-09,
> and the bridge he chose that does not wait on Google. What follows is the
> older write-up, kept only for the Drive detail it records.
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

### 2.2 The Trade Journal — DONE 2026-09-08 night

All four faults fixed in one pass, plus two more found while fixing them, plus
the rule he gave that night. Verified in a real browser against the real backend
and his live database, in both themes, with no console errors.

| Fault | What it was | What it is now |
|---|---|---|
| The ninth invented constant | A hardcoded five-lakh "margin base" divided his cumulative result and his drawdown, in two places | Live capital from `services/capital.py`. Read live at 23:26 IST: ₹9,71,111 from FYERS. Nothing printed when it cannot be read |
| A write fired by opening the page | `journal.js` posted to `archive-test-trades` on first load, nothing clicked | Gone. The endpoint answers 410 so a stale bundle cannot write either |
| Analytics ignored `provenance` | It had **no filter of any kind** beyond dates, so all 81 build-test rows fed the curve, drawdown, expectancy and every per-strategy figure | Filters `provenance` and `status`. Live check: 0 series points, 0 strategies |
| Two marks for one idea | `provenance` and a date-cutoff `status = 'archived'` that could disagree | One mark. The page says "81 rows excluded as build tests, not trades you took" |
| **The silent zero**, found while fixing the above | Both endpoints read `realized_pnl_inr` and `unrealized_pnl_inr` off `swayam_positions`. **Neither column exists.** Every trade without a `swayam_trade_history` row scored a flat ₹0, and that table is empty today | A result nobody can read is unknown and counted separately, never zero |
| **Zeros on an empty book** | 0.0% win rate, 100.0% discipline rate, ₹0 profit, 0.00% of margin | Every one a dash. The strip refuses those figures even if a stale server sends them |

**His rule, given that night and now enforced:** "I only want the trade that is
squared off to go in as a trade journal." A trade scores only when it is closed
**and** its result can be read.

**What this did NOT do.** It did not change how a trade is modelled. That is
section 2.11, and it is now the next job.

### 2.3 Charges — DONE 2026-09-09, and per LEG, which is his correction

**His instruction, 2026-09-09, correcting the plan:** "The charges should not be
recorded as per the trade. Charges are recorded as per the leg. The buy leg has
its own charges, and the sell leg has its own charges. Why would squaring one
leg charge for the whole trade?... Whenever we buy or sell, the charges will be
calculated then and there."

He was right, and the real system was worse than the plan said. **Nothing was
charged at entry at all.** The only charge ever booked was a flat ₹150 times the
number of legs, once, at the close.

| | Was | Is |
|---|---|---|
| Entry | Nothing charged, ever | Each leg costed as it is bought or sold, at its own price, on its own side |
| Exit | Flat ₹150 × legs | Each leg costed at its real exit price, on the reversed side |
| One-lot condor round trip | ₹600 | About ₹223 |
| A trade held across 1 April 2026 | One rate | Entry on the old schedule, exit on the new one |
| Per leg | Nothing | Gross, entry charges, exit charges, total charges, net |
| Per trade | One net figure | Cumulative gross, cumulative charges, net after them |

**Costing leg by leg is exact, not an approximation.** Brokerage is per order and
every other line is a percentage of that leg's own turnover, so the parts sum to
the whole to the paisa. `tests/test_charges_per_leg.py` asserts it.

`ESTIMATED_CHARGE_PER_LEG_INR` is deleted from `config.py`, and a source-level
guard fails if it returns.

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

### 2.7 The ONE long-standing test failure
`tests/test_notifications.py::test_execute_endpoint_best_effort_dispatch_on_success`
fails with `ValueError: not enough values to unpack (expected 3, got 2)` at
`execution.py:244`. Confirmed identical on a clean tree by stashing every change,
so it pre-dates all of this. **Do not "fix" it by weakening the assertion.**

Its former sibling, the `test_market` option-chain failure, was genuinely fixed
in round 2. **There is one now, not two.** Any document still saying two is
stale.

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

**Fixed AT SOURCE in the close-out change, and this matters.** The first fix
lived in `api/routes/market.py`, so `services/nifty_snapshot.py` bypassed it and
Home's Options card still counted down to a dead contract. The rule now lives in
`services/expiry.py` as `session_is_over()` and `expiry_is_alive()`, and
`get_expiry_metadata()` applies it, so **every caller inherits it**. The metadata
also returns `expired_today`, so a screen can say why a selection vanished
instead of switching under him. The countdown stays relative to today, not to
tomorrow, which was the subtle trap: rolling the weekly forward must not roll the
clock or every figure on screen would be short by a day.

There was a **second cause of the same symptom**, not diagnosed here at the time:
the FYERS budget exhaustion in §1a. Both are fixed. `tests/test_expiry_lifecycle.py`
holds all of it, 19 tests, including the bell at exactly 15:30 and a naive
datetime being read as IST rather than UTC.

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

### 2.10 The recorder recorded zeros — FIXED 2026-09-09 night. One gap remains.

**What was measured, on the file itself, not inferred.**
`gs://swayam-capital-options-data/2026-09-09/nifty_chain.parquet`, **10,332 rows,
24 columns.** Real: `close` in all 10,332 rows, `volume` and `open_interest` in
9,801. Twelve columns were entirely zero in every row: `open`, `high`, `low`,
`settle_price`, `turnover_inr`, `change_in_oi`, `underlying_spot`, `iv`,
`delta`, `gamma`, `theta`, `vega`.

**A THIRTEENTH column was wrong, and worse than zero.** `expiry_date` said
`2026-09-09` on all 10,332 rows, while the contracts' own names
(`NSE:NIFTY2691523300PE`) say 15 September. A zero announces itself as missing.
A wrong date does not, and it makes every valuation and every Greek computed
from that file wrong without saying so.

**The cause, one for both.** `fyers_recorder.py` was written against a response
shape FYERS does not return — `call_ltp`, `put_oi`, `call_iv`, `call_pdoi` —
with a fallback to the flat keys that do exist. The fallback carried price,
volume and open interest; everything without a fallback became `0.0`. And
`parse_expiry_from_symbol` was an empty shell that returned today's date for
whatever it was given. **The unit test passed the whole time, because it
asserted the imagined shape.** That test has been replaced by one driven from a
reply captured off the live API.

**What FYERS actually returns**, verified against the live chain on 2026-09-09
at 23:15 IST: `ltp`, `ltpch`, `ltpchp`, `bid`, `ask`, `volume`, `oi`, `oich`,
`oichp`, `prev_oi`, `strike_price`, `option_type`, `symbol`, plus one row per
chain with an empty `option_type` and a strike of `-1` whose `ltp` is the NIFTY
level. There is no `underlyingValue` field anywhere, which is why spot was zero.
There is no open, high, low, previous close, turnover, implied volatility or any
Greek.

#### What was built, 2026-09-09 night

| | |
|---|---|
| `underlying_spot` | **Real.** From the chain's underlying row |
| `change_in_oi`, `prev_oi` | **Real.** FYERS sends `oich` and `prev_oi`; the old code read `pdoi`, which does not exist. `prev_oi` is new, so the change can be re-derived and checked rather than trusted |
| `expiry_date` | **Real.** From FYERS' `expiryData` for the chain requested, cross-checked against the contract's own symbol. A row whose symbol disagrees is dropped rather than filed under the wrong expiry |
| `tte_years` | **New.** Snapshot to 15:30 IST on the expiry day, in years, not whole days. On expiry afternoon the difference between "one day" and "ninety minutes" is the difference between a theta figure that is roughly right and one that is nonsense |
| `iv`, `delta`, `gamma`, `theta`, `vega` | **Computed** from the traded price in `cloud/recorder/bs_math.py`, a dependency-free Black-Scholes written for the Cloud Function. `tests/cloud/test_recorder_bs_math.py` proves it agrees with `swayam.options_math.engine` (vollib) to better than 1e-9 across 1,080 cases |
| `open`, `high`, `low`, `settle_price`, `turnover_inr` | **NULL, never zero.** FYERS does not send them. They are exactly the columns the free NSE end-of-day file carries, and §2.15 is how they get filled |
| **Two expiries** | **New.** Every snapshot now records the near expiry AND the nearest monthly after it. One expiry cannot value a calendar, and ten of his twenty-one historical trades are calendars. Fail-safe: if the far fetch fails, the near expiry is still written |
| **NSE holidays** | **New.** The recorder used to run every minute of a closed exchange, get the previous session's frozen prices back, and write a full day indistinguishable from a real one. It now refuses on a holiday. Fails open on an unknown year, loudly |
| The date the file is filed under | **India's**, not the container's |

**Proved on the running system, 2026-09-09 23:45 IST**, against live FYERS with
the market shut: 164 rows across two expiries (2026-09-15 and 2026-09-29), spot
`23431.5` real, 151 of 164 rows with a solved implied volatility between 6.6%
and 142%, at-the-money delta `0.510` on the call and `-0.489` on the put, and
the far expiry carrying more vega and slower decay than the near one — which is
the calendar structure he trades, visible in the archive for the first time. The
thirteen rows without a volatility are all deep in-the-money puts trading at
intrinsic value, where a single tick of price would move the answer by tens of
volatility points; those are refused, not guessed.

#### THE GAP THAT REMAINS, and it is his decision

**The recorder captures the afternoon only, and cannot capture the morning.**
The 2026-09-09 file starts at 13:25 IST, not 09:15, and holds 126 minutes of a
375-minute session. The Cloud logs say why, once a minute for four hours:
`Snapshot recording failed: FYERS option chain query failed: Please provide
valid token`. It began working the minute he refreshed his token by hand on
sitting down.

He is asleep at 09:15. So **two thirds of every trading day is lost, including
the open, which is the most volatile part of the session** and the part a
backtest most wants.

**The fix is the FYERS refresh-token flow**: the login response carries a
refresh token valid for fifteen days, which can mint a new access token given
his PIN. A small scheduled job before 09:15 could do it. **That needs his PIN
stored in Secret Manager, which is his call and nobody else's.** Not built.
Raise it with him; do not implement it unasked.

Until then the recorder's own forward history is an afternoon-only archive, and
§2.15's purchased history is what covers the morning.

### 2.12 THE TRADING DESK. Execute, manage, exit. — THE NEXT JOB, AND THE BIG ONE

**Written 2026-09-09 after he took his first three paper trades and could not
execute, could not see, and could not exit without a terminal. His verdict, in
his own words: "immature execution, immature exit, immature monitoring... From
the trade point of view, everything is immature. Taking a position is more
immature than buying a soda bottle."**

This section replaces 2.11, which is folded into it: the campaign model is how a
trade is stored, and this is how he works with it. Neither is any use alone.

---

#### 2.12.0 WHAT HIS THREE TRADES ACTUALLY DID. Audited on the backend, 2026-09-09.

**The headline, and he should be shown it before anything else.**

| Trade | Gross | Charges | Net |
|---|---:|---:|---:|
| Bull Call Spread | +₹74.75 | ₹174.65 | **−₹99.90** |
| Iron Condor | +₹78.00 | ₹264.77 | **−₹186.77** |
| Bull Put Spread | +₹42.25 | ₹146.02 | **−₹103.77** |
| **All three** | **+₹195.00** | **₹585.44** | **−₹390.44** |

**Every one of the three made a gross profit and every one lost money. Charges
were 300% of gross.** That is his FY 2025-26 in miniature: a gross of +₹6,109
turned into a net of −₹86,299 by ₹92,408 of costs. The terminal now measures it
correctly, which is the single most valuable thing it did today.

**What worked, verified against the database.**

- Three executions, three positions, no double booking. The idempotency key held.
- Contract size 65 on every leg of all three, resolved server-side.
- Charges recorded per leg at entry and at exit on all three.
- Three closes, three history rows, no duplicates.
- The options maths is right. The condor's credit of ₹10,546.25 and its max loss
  of ₹8,953.75 both reconcile exactly at 65 a lot.
- **The vault cage did exactly its job.** Trades 2 and 3 refused to write a note
  into the container and queued to the outbox with the correct reason.
- The four rules evaluated and answered on every trade.

**What was wrong, and he could not see any of it.**

1. **`spot_at_entry` is never stored.** `execution.py` never puts it on the row,
   so `points_in_trade` is always null and the vault note prints a spot of 0.
2. **A close with a pending note queues NOTHING for the exit.** The exit block is
   inside `if journal_path:`, so when the note has not landed yet the exit is
   never written and never queued. **Two of his three trades are in that state
   and their exits are lost from the vault** unless they are rebuilt.
3. **Two entry notes are still pending in the outbox** and need the drainer.
4. **`/api/readiness/today` returns 500 on the live site, every time.** His daily
   check-in is broken there. It reads his Atlas daily log from the vault, and the
   live site cannot see the vault. Same root cause as the note.
5. **`/api/nifty/spot` 503'd repeatedly** early in his session.
6. **Margin used is never stored on a position.** So rule 4, the deployable
   margin ceiling, CAN NEVER BE TESTED against what he is actually using. The
   desk says so honestly: "margin already used is unknown, so the ceiling cannot
   be tested". That is a rule that does not work.
7. **Home never refreshes positions.** Its timer reloads the snapshot and the
   daily strip only, so a trade taken on the desk does not appear until a full
   page reload. He reported exactly this.
8. **Fills use the last traded price.** He has decided this changes: buy at the
   ask, sell at the bid.

**The systemic finding underneath several of these: THE LIVE SITE CANNOT SEE HIS
VAULT, AND FEATURES THAT NEED IT EITHER 500 OR DEGRADE SILENTLY.** The trade note
was one. Readiness is another. The AI persona reading his Method files is a
third. This gets its own decision in section 2.13.

---

#### 2.12.1 HIS DECISIONS. Given 2026-09-09. Do not relitigate.

**Where management lives.** The Strategy Desk, in a dedicated area BELOW the
payoff graph and the execution block. Not Home. His words:

> "at the strategy desk itself, the bottom area below the payoff graph and
> execution should be dedicated to open position, close position for the day,
> and everything for the positions... After the payoff graph area, open
> position. If anything is closed, it must be visible there. The leg is closed.
> Majorly, whatever happens today and what is open, either today or the past
> position, should be in that area."

And how it must feel, which is not decoration to him:

> "Full width. Big numbers. Bold. Clearly visible with required colors. Easily
> manageable. No cheap cross button or rather dustbin button. No cheap round
> circle for reset, a proper reset button. I must feel good while managing it."

**Home shows, Home does not manage.** He wants the position visible on Home and
managed on the desk. The Exit button added to Home on 2026-09-09 therefore moves
to the desk. Home keeps a read-only line.

**Where the Home strip belongs.** Below the black daily check-in strip and above
"Your money". In the main column, not up by the header.

**The execution ticket, simple but complete.** His list, verbatim in intent:

- market or limit, and a swap between them
- an editable price, and an editable limit price
- a proper reset button for the price
- editable lots
- margin needed, shown
- control over which leg goes first
- **execute all legs together, or one leg at a time**
- NO bid and ask ladder. NO market depth.

**Exits get the same ticket. His addition, 2026-09-09 evening**, after walking the
clickable journey: "exiting a single leg or exiting all legs should have a
limit/market price option." So every exit, one leg or every leg, goes through an
exit ticket with market or limit per leg, an editable price and a proper Reset,
exactly as the entry does. PR 3 builds it. The journey prototype shows it:
https://claude.ai/code/artifact/20a3dadd-5456-416b-b713-620680ec7f9d

**Two decisions taken with the journey, 2026-09-09 evening.** "Execute one by
one" is built on a real add-a-leg operation, so the second leg joins the trade
the first leg opened; that is the first brick of the campaign model. And the
deleted "no single-leg trades ever" rule is removed from the backend, because
it was still being evaluated and was printing into his journal notes.

**Fills become realistic: buy at the ask, sell at the bid.** He chose this over
the traded price knowing it makes his results look worse. Charges already proved
what a hidden cost does to him; the spread is the other one.

**Order of work: execute, then manage, then exit.** "Obviously, the execution is
the first thing: to take a trade, first thing we execute, then we manage, then
we exit. Need everything, but the execution comes at number one."

---

#### 2.12.2 WHAT TO BUILD, IN ORDER

**PR 1 — The execution ticket. MERGED 2026-09-09 18:03 IST, PR #49. Hardened by PR #50 the same evening.**

What landed, verified in a real browser against the real backend and live FYERS
at 17:58 IST with the market shut:

- Execute opens the ticket; nothing is sent until a button on it is pressed.
  Per leg: order with up and down, side, contract, lots stepper, Market or
  Limit, an editable price with a proper Reset, the traded price and the bid
  and ask beside it, and what the fill would be right now.
- **Fills are honest, server-side.** `services/fills.py`: a market leg fills at
  the SERVER'S live quote at the moment of sending, a limit fills only if the
  market is at or through it, no quote means no fill, and a closing price is
  not a fill. One leg that cannot fill refuses the whole ticket with HTTP 422
  and names every leg with what to do. Proven against the real backend after
  the close: both legs refused, nothing written. Before this a limit of ₹1 on
  a ₹100 option would have "filled".
- **His order is his.** `leg_order = "as_sent"`; the server no longer re-sorts.
- **`spot_at_entry` and the broker margin are stored on the row**, migration
  021. Rule 4 can be tested from the next trade on. The desk's "margin used"
  now sums the stored figure and says "unavailable" with the reason when an
  older position has none.
- **Execute one by one** opens the trade with the first leg and adds each later
  leg to the SAME trade through `POST /api/positions/{id}/legs`, with its own
  fill, its own charges, the structure recomputed, and an Adjustments block on
  the note. Stopping between legs is allowed.
- The note records when the TRADE opened, in IST, not when the note was written.
  Trades 02 and 03 of 2026-09-09 say 16:57 because that is when the drainer ran.
- "0.00% of margin base" on an unread balance now prints unavailable.
- The deleted single-leg rule is gone from the validator.
- Eight dead components deleted, two of which still carried their own leg
  arithmetic.

**Not yet seen with a real send.** The market was shut when it was built. The
first real send through the ticket is his, in his window. What to watch is in
the PR handoff.

The original brief, kept:

A modal that opens on Execute and shows what is about to happen, before anything
is sent. Per leg: buy or sell, strike, type, lots (editable), order type (market
or limit, switchable), price (editable, with a reset that restores the live
price). Ordering he controls, so he decides which leg goes first, defaulting to
buys before sells because that is what earns the hedged margin. Below the legs:
net debit or credit, margin needed against his ceiling, the four rules, and two
buttons — **Execute all** and **Execute one by one**, the second walking the legs
in order and reporting after each.

Backend: `/api/execute/multi-leg` already takes ordered legs. It needs to accept
a per-leg order type and price, to record `spot_at_entry`, and to record the
margin the preview computed so rule 4 can finally be tested.

**PR 2 — Realistic fills. MERGED 2026-09-09 19:46 IST, PR #52. He ran the marking script at 19:50: 3 rows marked.**

**His correction, given the same evening, now the rule:** "Traded price means the
last traded price, and bid and ask mean the price that is open in the market...
If I place a limit order, the price must execute at my limit order or better
than my limit order. That's what happens in the real platform." So:

- A market buy pays the ask, a market sell receives the bid, from the server's
  live book at the moment of sending. The traded price is history and is kept
  on the leg only so the record shows what the spread cost.
- A limit fills at his price **or better**, as the exchange does: a buy limit at
  or above the ask pays the ask, a sell limit at or below the bid receives the
  bid. Away from the market, no fill, and the answer says where the book is.
- **The exit is the same rule reversed.** A bought leg is sold at the bid, a sold
  leg bought back at the ask, and the close carries the side it hit, the traded
  price beside it, and the spread cost per leg. **After the bell the close
  refuses**, names every leg, and says to close it in the window. An explicit
  exit price from a terminal is recorded as supplied, never dressed as a fill.
- Every fill records `spread_cost_inr` against the traded price; the ticket shows
  it per leg and in total, and the note prints Fill and Traded side by side.
- The ticket's price box shows the ask for a buy and the bid for a sell, and the
  net at his prices is stated even when a limit is away from the market, marked
  "if every leg fills". It used to say unavailable, which he questioned.
- `fill_basis` on every position: `bid_ask` from here on. **His trades before
  this are marked `traded_price` by `scripts/mark_traded_price_fills.py`, which
  he runs**, because a one-off change to his real rows is a script, not a
  migration. The Trade Journal shows the basis on every row.

The original brief, kept:

The chain already returns bid and ask. A buy fills at the ask, a sell at the bid,
and the leg records both the fill and the last traded price so the journal can
show what the spread cost. Where a side is missing the leg says `unavailable` and
is not filled at a guess. **His two closed trades were filled at the traded price
and must be marked in the record as not comparable with anything after this.**

**PR 3 — The position area on the desk.**

Full width, below the payoff. Three groups: open now, closed today, earlier. For
each open position: strategy, legs, entry, live price, live profit and loss in
big bold figures with colour taken from the money, its own maximum loss, and how
it sits against rule 1. Per leg: **exit this leg** and **reverse this leg**. At
the position level: **add a leg** and **exit everything**. A real dustbin for
delete and a real reset button, both proper controls rather than icons.

**Every exit goes through an exit ticket, his decision of 2026-09-09 evening:**
one leg or all legs, market or limit per leg, an editable price, a proper Reset,
the exit charges per leg, and gross, charges both ways and net before he presses.
The close reason is one of the four the record allows. The fill rule is the
entry rule reversed, from the same `services/fills.py`.

**The record for a partial exit.** `swayam_trade_history` holds one result per
trade, which is right: only a squared-off trade enters the record. A leg exited
on its own books its result on the position's legs, and the trade's result is
the sum when the last leg closes or when he says the trade is closed.

This is where 2.11's campaign model becomes necessary: exiting one leg of four
leaves a trade that is neither open nor closed, and the schema has to hold that.
**Build the campaign model as part of this pull request, not before it.**

**PR 4 — Home, corrected. DONE 2026-09-09, PR #51.** The strip moved below the daily check-in and above Your money, the Exit button left Home, positions refresh on the 15-second timer. The original brief, kept:

The open-positions strip moves below the daily check-in and above "Your money",
becomes read-only, and refreshes on the timer so a trade appears without a
reload. The Exit button leaves Home.

**PR 5 — The option chain, tested rather than built.**

It already exists: `OptionChainModalComponent` is wired to `addLegFromChain` and
the desk has an "Option chain" button beside "Add leg". Nobody has ever used it
against a live market. Test it, fix what it gets wrong, and make picking a strike
from the chain the natural way to build a structure.

---

#### 2.12.3 WHAT MUST NOT BREAK

1. The payoff graph, its drag, and both sliders. He has said this twice.
2. Charges per leg, at entry and at exit, from `services/charges.py`.
3. The vault cage and the database guard.
4. One click, one trade. One close, one result.
5. Nothing may say LIVE unless `/api/market/data-health` says the market is open.
6. No purple. The accent is sage.
7. Every figure real or `unavailable`. No placeholder, ever.

---

### 2.13 The live site cannot see his vault. THE BRIDGE, and the Drive question.

Found while auditing 2026-09-09. Three features need his Obsidian vault at
request time and the Cloud Run container cannot reach it.

| Feature | What happens today | Bridged? |
|---|---|---|
| Trade notes | Refused and queued in `swayam_journal_outbox`, drained from his PC | **Yes, and it works** |
| `/api/readiness/today` | **HTTP 500 every time.** His daily check-in is broken on the live site | No |
| The AI reading his Method files | Reads a build-time snapshot baked into the image, not his live vault | No |

#### Where Google Drive actually stands, checked 2026-09-09

| | |
|---|---|
| `drive.googleapis.com` | **ENABLED.** Older documents saying it is off are stale |
| `google-api-python-client`, `google-auth-oauthlib` | **INSTALLED** |
| `scripts/link_google_drive.py` | Written and works |
| **The blocker** | The OAuth consent screen. A service account can never do this: zero Drive quota since June 2023, and both escapes need Workspace, which he does not have. So the app must act as HIM with the `drive.file` scope |
| His words, 2026-09-09 | Something is in verification and may take about a week. He also has the separate OAuth client behind the site's Google sign-in and thinks that may need to settle first |

**We cannot see Google's verification queue from here.** Do not promise a date.
**Check it by trying:** run `scripts/link_google_drive.py` and read what Google
says. That is the only honest status.

**While it is in Testing the token dies every seven days.** That is survivable
for a personal tool but it is not something to build a daily habit on, which is
why the bridge below does not depend on Drive at all.

#### THE BRIDGE. His decision, 2026-09-09: build one and do not wait for Google.

**The pattern already exists and is proven.** The outbox holds what the cloud
cannot write, and a script on his PC completes it. Extend the same idea in the
other direction for the two features that READ the vault.

**A small mirror table, `swayam_vault_mirror`,** holding only the handful of
files the app needs: his Method files, his trading rules one-pager, and today's
Atlas daily log. A script on his PC pushes them up; the live site reads them from
the database instead of the filesystem.

- **`/api/readiness/today` stops returning 500.** It reads the mirrored daily
  log. If today's log has not been pushed yet it says so plainly and offers the
  form empty, rather than erroring.
- **The AI reads his real Method files** instead of a snapshot frozen at build
  time, and the mirror records when each file was last pushed so the age is
  visible rather than assumed.
- **Nothing is duplicated by hand.** The push script runs alongside the drainer,
  so one command on his PC keeps both directions current.

**When Drive lands, the mirror stays.** It is faster, it works offline, and it
removes a dependency on a Google approval he does not control. Drive becomes the
way the app writes BACK into the vault from the cloud, which is the harder half
and the one the outbox currently covers from his PC.

**Where this sits in the order.** After section 2.12. It is not blocking a trade;
it is blocking his daily check-in and the AI knowing his current rules. Tell him
that plainly rather than letting it drift.

---

### 2.12.4 TOMORROW'S LIVE TEST, 2026-09-10, and the loopholes only the market can close

Written the night before, with the market shut. Everything in PRs #49 to #52
is proven by test and in a browser against the real backend, but **no order has
ever been sent through the ticket with a live book.** In his window, in this
order, cheapest proof first:

1. **Refresh the token, open the desk, load a two-leg spread.** Press Execute.
   The chip must read LIVE. Each buy row shows the ask in the price box and
   "market · at the ask"; each sell the bid.
2. **Execute all legs.** Watch for: every fill at the side named, the spread
   cost per leg and in total, the spot at entry, the margin stored. Then Back
   to the desk: the metric row's margin used is a real figure and rule 4 tests
   against the ceiling. Home shows the position within 15 seconds.
3. **Execute one by one** on a second small structure. Send leg 1, read its
   fill, send leg 2. Stop after two if he likes. The trade must keep ONE id.
4. **A limit away from the market**, then Reset, then a limit through the
   market: the fill must be at the market, "better".
5. **Close** from a terminal with no prices supplied (PR 3 brings the exit
   ticket): it must fill against the book and record the side each leg hit.
6. **Read back afterwards, none of his time:** the Cloud Run logs for any 422
   or 503 on `/api/execute/multi-leg` and `/api/positions/*/legs`; FYERS
   refusals on `/api/market/data-health`; the note in the vault after the
   drainer runs, with Fill and Traded side by side.

**What could still be wrong, and how it would show.**

- The live chain's bid or ask missing for a strike (thin book): the ticket
  says "no ask published", the send refuses. Not a bug; note which strikes.
- A refusal with the key already claimed: the ticket returns him to the legs
  with every refused leg named. A second press must NOT open a second trade.
- One by one with the spot moving between legs: leg 2 keys on the leg, not the
  spot. If it ever says "already been used for a different trade", that is a
  bug in the hash and must be reported with the exact legs.
- Margin used after the first real position: if it reads unavailable with a
  reason naming a position with no stored margin, that position predates 021.
- The desk's own 5-second re-quote can move a market leg's price on the ticket
  while he reads it. That is honest; the server fills at its own read anyway.

### 2.14 REAL-MONEY ORDERS FROM THIS TERMINAL. His question of 2026-09-09 night, researched.

**His question.** Can this terminal send real orders as well as the broker's
terminal does, with a minimum probability of error, or should orders stay with
the broker while everything else lives here?

**What was checked, not assumed.**

| Fact | Source | What it means here |
|---|---|---|
| Since **1 April 2026** FYERS accepts API orders only from **one whitelisted static IP per App ID**; "orders from any other source are automatically rejected". Data and read-only calls need no static IP | [FYERS, SEBI's new algo rules](https://fyers.in/community/blogs-gdppin8d/post/sebi-s-new-algo-trading-rules-kick-in-on-april-1-here-is-what-changes-Yew3vdG4CgoXk1q) | The live site runs on Cloud Run in Singapore with no fixed IP. Sending orders from it needs Cloud NAT, about ₹4,000 a month, or the order path runs on his PC with a static IP from his ISP |
| Zerodha says the same: unregistered IP, order rejected; positions, orderbook and WebSocket data stay open from any IP | [Kite Connect forum](https://kite.trade/forum/discussion/15912/preparing-to-comply-with-sebis-retail-algo-rules-static-ip-ratelimits-order-types) | Industry-wide, not a FYERS quirk |
| **10 orders per second** per client is the ceiling; above it needs exchange registration | same two sources | Not a constraint for swing trades |
| FYERS has **no all-or-none multi-leg order**. The multi-order basket sends separate orders "executed at the same time"; each leg can fill, reject or partially fill on its own | [FYERS community](https://fyers.in/community/api-algo-trading-bihtdkgq/post/how-does-one-place-spread-multileg-option-orders-via-the-api-EaxgShpc9dlRAsW) | A condor can end up half built with a naked short if one leg rejects. The broker terminal has the same risk but shows the order book instantly and lets him fix it by hand |
| FYERS's order rate limit is **undisclosed**; users report "Request limit reached" after four orders | [FYERS community](https://fyers.in/community/questions-5gz5j8db/post/apiv3---place-order---limit-reached-after-placing-4-orders-8rvYI8IfHFgKfXJ) | The desk already exhausted the data budget once, on 2026-09-08. An order refused for rate limit mid-structure is leg risk |
| FYERS API v3 offers order, position and trade WebSockets, plus orderbook, tradebook and positions endpoints; 1 lakh requests a day | [FYERS API v3](https://fyers.in/community/blogs-gdppin8d/post/unveiling-fyers-api-version-3-v3-0-0-a-comprehensive-update-to-enhance-NUuYJmm6gt9toPm), [order WebSocket](https://support.fyers.in/portal/en/kb/articles/what-functionalities-does-the-order-websocket-in-api-v3-offer) | Everything needed to READ his real book into this terminal exists today and needs no static IP |
| NIFTY freeze quantity 1,800 units, 1,755 at lot 65, so 27 lots per order | [Angel One](https://www.angelone.in/news/market-updates/nse-announces-revised-quantity-freeze-limits-for-index-derivatives-from-march-2-2026) | A guardrail the terminal does not have and the broker enforces |
| Market orders are refused for illiquid option contracts | [Zerodha](https://support.zerodha.com/category/trading-and-markets/trading-faqs/f-otrading/articles/market-orders-monthly-options) | Another broker-side guardrail this app lacks |
| His own token: generated pre-dawn, rejected by 13:30 on 2026-09-08 | this repo, START_HERE | A dead token mid-trade means he cannot exit from this terminal. The broker terminal does not have that failure |

**What this terminal has today for real money: nothing.** No order-placement
code, no order-status socket, no reconciliation against the broker's book, no
kill switch (§2.5), no freeze-quantity or lot cap, no handling of a rejected or
partially filled leg. Its paper execution has three trades behind it, all on
one afternoon, and the ticket has never sent with a live book.

**The honest answer.** It is buildable, and not as well as the broker terminal
in the next weeks. The API call is the easy part. The hard parts are the ones
around it, and each is a real-money failure mode: a leg that rejects while its
partner fills, a token that dies with a position open, a rate limit that lands
between leg two and leg three, a retry that doubles an order, a cloud container
with no fixed IP that the broker will refuse outright. A broker terminal has
years of operations behind each of those. This app has one day.

**Recommendation, and the order to do it in.**

1. **Orders through the broker terminal. Everything else here.** Exactly as he
   described: plan, build, measure and record in Swayam; place and close at
   FYERS, open in parallel. Paper trades keep going through the ticket, because
   the ticket is the training ground and it is where the discipline lives.
2. **Build the read-only bridge, next after PR 3.** Read his real positions,
   orderbook and tradebook from FYERS, which needs no static IP, and mirror
   them into a REAL book beside the paper book: real positions in the position
   area with the same big numbers, real fills journaled with real charges,
   the four rules run against what he actually holds, the record toggling
   paper and real as his design already says. When the mirror matches the
   broker to the paisa for some weeks, the terminal has earned trust.
3. **Only then consider "send to broker",** and only from his PC on a static
   IP, one leg at a time with a confirmation each, the order WebSocket feeding
   the position area, the kill switch built first, a lot cap and the freeze
   quantity enforced, and every exit still possible from the broker terminal
   in parallel. That is a separate plan with its own weeks of testing, and he
   should decide it after the mirror has run, not before.

**His decision on this is open.** He said he is ready for weeks of testing if
the answer is yes. The answer is: yes to the bridge now, not yet to sending.

---

### 2.11 The trade as a campaign: one trade, legs that change — FOLDED INTO 2.12

**He specified this himself on 2026-09-08 night, unprompted, after being told
what the terminal could and could not do. His words are the specification.**

> "For swing trading we should give every trade a trade ID or trade number. In
> that trade ID, I can add, delete, or add legs because it will happen. I cannot
> prevent it. In options, you have to manage the trade... if you don't manage,
> you won't survive."
>
> "Every leg that I square off will have its own profit/loss added, and every new
> leg I add will be considered in the same trade. Once I close all the legs or I
> say 'the trade is closed', then only the trade is closed. If I am opening a new
> trade, I shall add that as a new trade."
>
> "There should be a classification: this is an intraday trade, this is an
> options or swing trade."

**Everything else about this now lives in section 2.12**, because the way a
trade is STORED and the way he WORKS with it are the same job. His words
above are the specification; 2.12 is the build. Do not plan this section
separately.

---

### 2.15 Backtesting, milestone one: the data — RESEARCHED 2026-09-09 night

**This is `ROADMAP.md` §3 milestone 1.** The backtester must test HIS structures
under HIS constraints: entries in his window of roughly 14:00 to 15:30 IST, his
capital, his four rules, charges per leg from `services/charges.py`, fills at
the bid and the ask, and the near-expiry square-off habit for calendars. And
before it is trusted at all it must **reproduce the 21 swing trades in
`00 - Reference/Historical Swing Trades`** and get what actually happened.

Nothing here was bought and nothing was signed up for. Everything marked
"verified" was tested against the live FYERS API on 2026-09-09 night; everything
else is a vendor's own published statement, cited.

---

#### 2.15.1 He asked whether this is built on NIFTY data or options data. Both.

They are two different problems with two different answers.

**The underlying: solved, free, and already available.** The FYERS history API
returns NIFTY index candles going back years, and it costs nothing beyond the
account he already has. Verified on 2026-09-09 night:

| Resolution | Depth proved | Per request |
|---|---|---|
| 1 minute | **January 2018 onwards.** 22,401 candles for Q1 2018; 2017 returns `no_data` | About 100 days |
| Daily | **At least 2010.** 252 candles for 2010, 252 for 2020 | About 366 days |

That is the spine: every entry, every exit and every day in between can be
placed against a real NIFTY level at the minute he would have been at the
screen. It also gives realised volatility, the average daily move for rule 2,
and the 20- and 50-day ranges the Home sidebar already shows.

**The options: not solved, and not solvable from FYERS.** That is the whole of
the rest of this section.

---

#### 2.15.2 What was tested and ruled out

**FYERS history cannot return an expired option. Proved, not assumed.**
A contract that is still listed returns full one-minute candles: 1,539 of them
for `NSE:NIFTY2691523300CE` over five days. A contract that has expired returns
`Invalid symbol provided`. Tested on `NSE:NIFTY2690823850PE`, which expired on
8 September 2026 — the day before the test — with its name taken verbatim out
of the NSE bhavcopy so the name could not be at fault. Also tested on contracts
expired eight days and four years earlier. All three refused.

**Zerodha cannot either.** Once an option expires its instrument token leaves
`kite.instruments()`, and `historical_data()` needs that token. Zerodha's own
support article and developer forum say expired F&O contract history is not
available through the API and that there are no plans to add it. His family
Zerodha account does not change this.

**Global Datafeeds (GDFL) keeps one month of options history.** Their own page:
options history of any timeframe is available for one month only. Not a
candidate for two years.

**TrueData sells backfill in days, not years.** Their price page lists tick-data
upgrades of 5, 10 and 20 days at ₹299, ₹699 and ₹999 a month against a Velocity
subscription of ₹1,440 to ₹2,796 a month. That is a live-data product with a
short look-back, not a historical archive.

**Stolo, NiftyTrader, TradingTick, StockMojo and OptionBacktesting are viewers,
not data.** Several genuinely hold years of NSE option chain history — Stolo
advertises four years minute by minute, TradingTick six years — but they are
screens and one-date-at-a-time CSV downloads. There is no bulk export and no
API. Loading two years into Postgres from a web form is not a plan.

**Kaggle and GitHub datasets are refused on principle.** There are NIFTY option
chain datasets there covering 2024 to 2026. Their provenance cannot be checked,
their gaps cannot be checked, and this is the terminal he intends to trade real
money through. A backtest is only worth what its data is worth.

---

#### 2.15.3 THE RECOMMENDATION: Dhan, for one or two months, then stop

**DhanHQ's expired-options endpoint is the only source found that is deep
enough, fine enough, bulk-loadable and cheap.** From Dhan's own API
documentation:

| | |
|---|---|
| Depth | **The last 5 years**, rolling |
| Granularity | **Minute level**, resampled to 1, 5, 15, 25 and 60 minutes |
| Fields | open, high, low, close, **volume, open interest, implied volatility, and the spot** |
| Coverage | Index options **ATM+10 to ATM-10**; other contracts ATM±3 |
| Per call | Up to 30 days |
| Cost | **₹499 a month plus tax, about ₹589.** Free in any month he has executed 25 trades in the previous 30 days |

**The plan is to subscribe, pull, and cancel.** Two years of NIFTY index options
at minute granularity is a bounded download. One month of subscription is
₹589 and two is ₹1,178. After the load, the recorder from §2.10 accumulates
forward for nothing.

**The cost, all in:**

| Item | Rupees |
|---|---|
| Dhan Data API, one month | 589 |
| Dhan Data API, a second month if the load needs it | 589 |
| FYERS NIFTY index history, 2018 onwards | 0 |
| NSE end-of-day bhavcopy, all years | 0 |
| The recorder, forward from now | 0 |
| **Total, worst case** | **1,178** |

**Two things he has to do himself, and I have not done either.**

1. **Open a Dhan account.** It is free and it is a normal broker onboarding with
   KYC, but it is a signup, and signing him up for anything is not mine to do.
   He does not have to fund it or trade through it; the Data API needs the
   account, not the balance.
2. **Read Dhan's data terms before the load.** Their public API documentation
   states no redistribution or licence terms at all, so I could not verify them.
   Personal use inside his own terminal is the ordinary case and almost
   certainly fine, but it should be his eyes on the agreement, not mine.

**The one real limitation, and the first thing to test.** Coverage is ten
strikes either side of the money, which at 50-point NIFTY strikes is about ±500
points, or ±2.1% at today's level. Two questions the documentation does not
answer and a one-month subscription would: whether "at the money" is re-anchored
each day, and therefore whether a leg drifts out of coverage when the index
moves 800 points during a three-week trade; and whether the far expiry of a
calendar is covered on the same terms. **Test that against Trade-01 first**,
which rolled a short put from 16,700 to 17,100 on a roughly 17,000 index, before
paying for a second month.

**The fallback if Dhan disappoints: Upstox.** Its Expired Instruments API gives
1-minute OHLC for expired option contracts on the Upstox Plus plan, which Upstox
says can be activated free for now. The catch is depth: Upstox's own community
answer states six months of expired history with a stated intention to reach two
years, and that answer is older than this document, so the current figure must be
checked before relying on it. `marketcalls/ExpiryTrack` is an existing open
project that downloads exactly this into DuckDB and is worth reading either way.

---

#### 2.15.4 The free end-of-day spine, which already works in this repository

**NSE's UDiFF bhavcopy is free, official, and goes back years.**
`src/swayam/bhavcopy.py` already downloads and parses it, and
`data/bhavcopy/` already holds 22 days. One day is about 31,500 rows and 5.7 MB
covering every F&O contract, of which roughly 1,600 are NIFTY options.

Its columns are, not by coincidence, the ones the recorder writes as NULL:

`OpnPric`, `HghPric`, `LwPric`, `ClsPric`, `PrvsClsgPric`, `SttlmPric`,
`UndrlygPric`, `OpnIntrst`, `ChngInOpnIntrst`, `TtlTradgVol`, `TtlTrfVal`,
`XpryDt`, `StrkPric`, `OptnTp`, `NewBrdLotQty`.

`UndrlygPric` is the real underlying, `SttlmPric` is the official settlement,
and `NewBrdLotQty` is the lot size on that day — which matters, because the lot
was 75 before January 2026 and is 65 now, and a backtest of his 2022 trades that
uses 65 is wrong by 15%.

**So bhavcopy is the daily bar for every contract in every year, for nothing.**
What it cannot do is place an entry at 14:20. That is what Dhan is for.

---

#### 2.15.5 The shape it loads into

Three tables, all `swayam_*`, all in the existing Supabase project. Nothing here
touches `swayam_positions` or anything the trading desk reads.

**`swayam_underlying_bars`** — the NIFTY spine, from FYERS, free.

| Column | Type | Note |
|---|---|---|
| `symbol` | text | `NSE:NIFTY50-INDEX` |
| `bar_start_utc` | timestamptz | |
| `resolution` | text | `1m` or `1d` |
| `open`, `high`, `low`, `close` | numeric | |
| `volume` | bigint | Zero on the index; kept for futures later |
| | | Primary key `(symbol, resolution, bar_start_utc)` |

**`swayam_options_eod`** — one row per contract per day, from the NSE bhavcopy.

| Column | Type | Note |
|---|---|---|
| `trade_date` | date | |
| `symbol` | text | The FYERS-style name, `NIFTY2691523300PE`, so it joins the recorder |
| `underlying`, `expiry_date`, `strike`, `option_type` | | |
| `open`, `high`, `low`, `close`, `prev_close`, `settle_price` | numeric | |
| `volume`, `turnover_inr`, `open_interest`, `change_in_oi` | | |
| `underlying_spot` | numeric | `UndrlygPric`, real |
| `lot_size` | integer | `NewBrdLotQty` **on that day**, never a constant |
| `source` | text | `nse_bhavcopy` |
| | | Primary key `(trade_date, symbol)` |

**`swayam_options_intraday`** — the minute bars, from Dhan for the past and from
the recorder going forward. **Same column names as the recorder's Parquet file,
deliberately**, so the two load through one path.

| Column | Type | Note |
|---|---|---|
| `snapshot_time_utc` | timestamptz | |
| `trade_date`, `symbol`, `underlying`, `expiry_date`, `strike`, `option_type` | | |
| `open`, `high`, `low`, `close` | numeric | NULL from the recorder, real from Dhan |
| `bid`, `ask` | numeric | Real from the recorder, NULL from Dhan |
| `volume`, `open_interest`, `change_in_oi`, `prev_oi` | | |
| `underlying_spot` | numeric | |
| `tte_years`, `iv`, `delta`, `gamma`, `theta`, `vega` | numeric | |
| `source` | text | **`recorder`, `dhan` or `bhavcopy`. Not optional.** Every row says where it came from, so a result can always be traced to its data |
| | | Primary key `(symbol, snapshot_time_utc, source)` |

**Note the honest asymmetry.** The recorder has the bid and the ask and no
open/high/low; Dhan has open/high/low and no bid or ask. That matters for the
fill model: `services/fills.py` fills a buy at the ask and a sell at the bid,
and Dhan's history cannot support that directly. **The backtester will have to
model the spread from the recorder's own measured spreads**, by moneyness and
time of day, rather than pretend a candle close is a fill. Write that down now;
it is the single most likely way a backtest of his flatters itself.

---

#### 2.15.6 How the recorder's files join it

`scripts/ingest_gcs_to_duckdb.py` already reads the recorder's daily Parquet
into a local DuckDB `options_history` table. The loader in §2.15.7 does the same
into Postgres, with `source = 'recorder'`, and the recorder's column names were
kept identical for exactly that reason.

The three sources overlap and complement rather than conflict:

- **Before the recorder existed:** Dhan for the minutes, bhavcopy for the day.
- **From 10 September 2026:** the recorder for the afternoon minutes with real
  bids and asks, Dhan for the mornings until his token problem is solved
  (§2.10), bhavcopy for the daily close, settlement and lot size.
- **A cross-check that costs nothing:** on any overlapping day the recorder's
  last snapshot before 15:30 and the bhavcopy close for the same contract should
  agree closely. **They are the acceptance test for the loader.** If they do
  not, one of the two is being read wrong, and better to find that on a Tuesday
  than inside a backtest result.

---

#### 2.15.7 What to build, in order, when he opens this work

1. **`scripts/load_bhavcopy_to_postgres.py`** — free, no signup, can start
   immediately. Fills `swayam_options_eod` from `data/bhavcopy/` and from NSE
   for any date range. Caged tests, `db_guard` respected.
2. **`scripts/load_nifty_history.py`** — free. Fills `swayam_underlying_bars`
   from FYERS, 100 days per request at 1 minute, back to January 2018.
3. **The Dhan loader**, only once he has an account: `swayam_options_intraday`
   with `source = 'dhan'`, 30 days per call, resumable, and a manifest of what
   was fetched so a broken run does not have to start again.
4. **The recorder loader** into the same table with `source = 'recorder'`.
5. **The reconciliation check** of 2.15.6 before any backtest is run at all.
6. **Then, and only then, the backtester**, whose first job is the 21 historical
   trades. `ROADMAP.md` §3 milestone 2: it is not trusted until it reproduces
   what those trades actually did.

---

#### 2.15.8 Sources

- FYERS history behaviour on live and expired option contracts, and NIFTY index
  depth: measured directly against the live API, 2026-09-09 night. The probes are
  not committed; they are three calls to `fyersModel.history()`.
- Zerodha, expired F&O contracts:
  `support.zerodha.com/category/trading-and-markets/charts-and-orders/charts/articles/historical-data-for-expired-f-o-contract`
  and `kite.trade/forum/discussion/15660`.
- Dhan expired options: `dhanhq.co/docs/v2/expired-options-data/`. Pricing:
  `dhan.co/support/platforms/dhanhq-api/how-does-the-dhanhq-data-api-subscription-work/`.
- Upstox expired instruments: `upstox.com/developer/api-documentation/get-expired-historical-candle-data/`;
  depth statement at `community.upstox.com/t/historical-availability-retrieval-limit-per-query-for-expired-options-contract/9245`;
  `github.com/marketcalls/ExpiryTrack`.
- Global Datafeeds: `globaldatafeeds.in/global-datafeeds-apis/global-datafeeds-apis/introduction/type-of-data-available/`.
- TrueData pricing: `truedata.in/price`.
- Stolo: `stolo.in/solutions/nse-spots-futures-options-historical-data/` and `stolo.in/pricing/`.
- NSE UDiFF bhavcopy: already implemented in `src/swayam/bhavcopy.py`; column
  list read off `data/bhavcopy/2026-09-01.csv`.

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

### Then: the AI chapter. He asked for it to be in the plan.

He has said repeatedly this comes after the plumbing is solid, and he named it
again on 2026-09-08 as something that must appear here. **Not started.**

**What already works, so nobody rebuilds it.** The chat is real and grounded: it
reads his Method rules, open positions, journal, saved memory, readiness form and
"So Far Today". Macro events reach it automatically through
`ai/context_builder.build_planning_context()`, so he never needs to paste them.
The memory scaffold exists and the compaction scheduler is live. And **Google
Search grounding is already built and proven**, `src/swayam/ai/grounded.py`,
Gemini through Vertex AI, wired to exactly one feature: the So Far Today summary.

**The four learning loops** are described in his vault at
`06 - Platform Plan/Self-Improving Agent Integration.md`. That document is the
authority. Do not re-derive it and do not start early.

**Event research, which he asked for by name.** His words: "Can my AI read this
data and do its ground research, like internet search, and help me understand the
effects of each event?" Yes, and most of it exists. `swayam_macro_events` already
carries an `impact_brief` per highlighted event, written by
`services/macro_curator.py`, and round 3 put it on screen. The missing half is
pointing the grounded search at one event on demand, so he can ask what
Thursday's US CPI means for a bear put spread he is carrying and get a sourced
answer rather than a general one. **Scope it as a manual button on an event row,
under the standing cost rule below.** Never a background job, never on page load.

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
| 2026-09-09 | **He can close a trade at all** | The close wrote `closed_at` and `journal_path`, neither of which existed. Proved against the live schema; migration 020 adds them |
| 2026-09-09 | Closing twice cannot record the trade twice | A duplicate check plus a unique index. The result row was inserted before the failing update, so a retry double counted |
| 2026-09-09 | A failed exit note cannot fail a close | It goes to the outbox, and the drainer can now finish a close note. It used to return 500 on a trade already closed |
| 2026-09-09 | A column that does not exist can never ship again | `tests/test_written_columns_exist.py`, proven to fail without migration 020 |
| 2026-09-09 | The whole read flow answers, every time | 14 endpoints at 200 against a real backend; 20 of 20 rule validations |
| 2026-09-09 | Charges are computed PER LEG, at entry and at exit | A one-lot condor's real round trip is ₹223. It used to book ₹600, and nothing at all at entry |
| 2026-09-09 | A leg's costs sum to the trade's, exactly | Four legs costed separately: 35.47 + 25.22 + 34.80 + 25.22 = 120.71, the same paisa as costing them together |
| 2026-09-09 | **His first paper trade can now be closed at all** | The desk sends no contract size, so the stored leg was null and `close_position` refuses to value a leg it cannot size. Proven with the desk's exact payload |
| 2026-09-09 | His record stopped describing setups he never wrote | "Standard breakout", "Key support/resistance level", "With Trend", "Manual / Target" and a default "100% Rules Followed" all became dashes |
| 2026-09-08 | **The vault can no longer be written by a test run** | 26 fabricated notes were in his real journal folder; 22 had no database row. Folder held 0 notes before a full suite run and 0 after |
| 2026-09-08 | The 26 fabricated notes are gone from his Second Brain | Journal folder holds zero markdown files. The vault is under git, so they remain recoverable |
| 2026-09-08 | The Trade Journal stopped inventing a margin base | Live backend at 23:26 IST returns his real ₹9,71,111 from FYERS, and `null` where it cannot compute |
| 2026-09-08 | Opening the Trade Journal no longer writes to his database | The retired endpoint answers 410; position count 81 before and after |
| 2026-09-08 | Test rows no longer reach his record | The page reads "81 rows excluded as build tests, not trades you took" |
| 2026-09-08 | An empty book prints dashes, not a 0% win rate and 100% discipline | Verified in a real browser in both themes, no console errors |
| 2026-09-07 | Release 1: lot 65, real margin, live capital, his risk rules | PR #23 |
| 2026-09-09 | **The execution ticket.** He sees every leg, price, lot and the order before anything is sent | Real browser, real backend, 17:58 IST: four legs, real closing prices with bid and ask, chip reads AT THE CLOSE, no console errors. PR #49 |
| 2026-09-09 | A paper fill needs a market to fill against | Real backend after the close: 422, both legs named, nothing written. A limit away from the market is refused with the market price named |
| 2026-09-09 | The server stopped re-sorting his legs | `leg_order = "as_sent"`; sequence stored on every leg |
| 2026-09-09 | Spot at entry and broker margin are stored on the row | Migration 021; `tests/test_written_columns_exist.py` passes with it |
| 2026-09-09 | A leg can join an open trade | `POST /api/positions/{id}/legs`, same key rule, structure recomputed, Adjustments block on the note |
| 2026-09-09 | The note records when the trade opened, not when the note was written | Trades 02 and 03 said 16:57; a test pins the IST stamp to the row's `opened_at` |
| 2026-09-09 | The deleted single-leg rule stopped being evaluated | It had reached his vault as a passed check in notes 02 and 03 |
| 2026-09-09 | A retry after a lost response cannot trade twice when the market has ticked | The key and the server hash ignore the spot and a market leg's price; a limit price stays. Proven: same key, spot moved, price moved, one position. PR #50 |
| 2026-09-09 | The path nobody had run: one by one, then close, then the note | `tests/api/test_ticket_end_to_end.py`: first leg opens, second joins, real close values both, one result row, note complete in order |
| 2026-09-09 | Fills are the exchange's: a buy pays the ask, a sell gets the bid, a limit fills at his price or better | `services/fills.py`; the close is the same rule reversed and refuses after the bell. PR #52 |
| 2026-09-09 | The spread cost is visible, per leg, on the ticket and in the note | Recorded on every fill against the traded price |

---

## 4b. THE LESSONS. All learned the hard way, all silent when they happened.

**Silent failure is the house pattern.** On 2026-09-08 three separate things had
never once worked while something downstream reported success: the recorder had
failed every minute for five days with a completely empty IAM policy, the AI's
readiness query had always failed with Postgres 42703 while a test asserted the
same non-existent columns, and the FYERS websocket library would not import at
all. **When checking whether a thing works, invoke it and read what comes back.**
Never a status field, never a log line saying "started", never a test that passes.

**Pushing to a branch after its pull request merged strands the work.** It
happened **three times** on 2026-09-08. The third was the round 3 brief, pushed 38
minutes after PR #38 merged, and the next branch had to rescue it. **`git fetch`
and check the pull request state before every push.**

**Opening a pull request against another pull request's branch is not safe.**
GitHub only retargets to `main` when the base branch is deleted on merge. PR #35
merged into a dead end and the live site silently kept the old interface. Stack
the work in one branch, or open the second pull request against `main` after the
first has landed.

**Merging two pull requests within seconds races two deploys and the wrong one
can win.** Both build jobs deploy `swayam-dashboard`; the second arrives holding a
stale version number and Cloud Run aborts it. Once the winner carried a
documentation change and the loser carried the new pages, so the site restarted
with a fresh token and the OLD interface. **Merge one, wait for the green tick,
then merge the next.** A failed build is silent; nothing tells him.

**A word on a screen is a claim.** "LIVE" over a closing price was found in four
separate places, all reading one backend flag that meant "FYERS answered". A
label the API cannot honour is a claim, not a fact. The same shape of error is
why a fix applied at one route left the identical bug alive in a service that
read the source directly. **Fix the rule where the rule lives, not where the
symptom showed.**

**Two sessions in one working tree is hazardous.** It worked on 2026-09-08 only
because the second session started cleanly off `main` after a merge. If two are
needed at once, one takes a separate clone.

---

## 5. THE REVIEW CHECKLIST, for any pull request touching the pages

**Do not let him merge before this passes.** Work through it in order and
report honestly.

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
8. **Confirm nothing says LIVE** unless `/api/market/data-health` says the
   market is open. That endpoint is the one clock, and four screens have got
   this wrong.
9. **Confirm no purple, lilac or violet.** The accent is sage.
10. **Confirm the payoff graph, its drag and its two sliders are untouched.**
11. **Run both suites** and compare with the counts in section 1.
12. **Read what it says it could not verify**, and verify those things.

Then tell him plainly what is right, what is wrong, and whether to merge.
