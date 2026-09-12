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

**His deadline was Friday 2026-09-11.** On 2026-09-10 evening he said himself
it will not be met, because the backtester runs behind and the position area is
four builds away. Nothing is planned against a date. Paper trading starts on
the day he says so, and a script he runs marks that day (§2.12.6, Build 02).

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

Until then the recorder's own forward history is an afternoon-only archive.
**The mornings are recoverable, though, and for nothing.** §2.15 established
that FYERS serves 1-minute candles for expired option contracts, so every
morning this recorder misses can be backfilled once those contracts expire.
That makes the token gap a nuisance rather than a permanent hole, and it is why
§2.15's loader is worth more than fixing the token first.

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

**BUILT, 2026-09-10: BUILD A PARTS ONE AND THREE.** On branch
`feature/swayam-build-a-desk-home-chain-042`, pushed, **not merged and no pull
request yet, so none of it is live.** Part one is the position area, the exit
ticket, the campaign model, the name from the open legs, click-to-load on the
payoff, and the drainer's close branch. Part three is the option chain: the
scroll kept by painting only on a shape change, a strike with no trade today
greyed with its stale price struck through and unaddable, the at-the-money row
banded and centred, Buy and Sell as buttons, four figures a side, and max pain
naming its expiry on the chain and on Home. **Part two, Home's band and its
states, targets, Manage from Home, the crosshair, the terminal-test phase and
the big-number pass, is the only part left**; the chat that finishes it starts
at `docs/builds/BUILD_02_HOME_TARGETS_AND_READING.md` section 0. Migrations
022 and 023 are both unapplied and he applies them together before merging.
Verified on the running system in both themes: Python 616 passing, JavaScript
299 passing, his journal folder 6 notes before and after, zero console errors.
The one Python failure is a stale mock that fails identically on `main`.

**SUPERSEDED THE SAME EVENING. PR 3 is now TWO BUILDS in `docs/builds/`,
his decision of 2026-09-10 evening, corrected late that night from four to
two:** Build A, one chat, one branch, one pull request, is the position area,
the exit ticket and the campaign model (`BUILD_01_DESK_POSITION_AREA.md`),
then Home's band, targets, Manage from Home, the crosshair, the terminal-test
phase and the big-number pass (`BUILD_02_HOME_TARGETS_AND_READING.md`), then
the option chain after its mockup (`BUILD_04_OPTION_CHAIN.md`). Build B is
resting orders alone (`BUILD_03_RESTING_ORDERS.md`), after Build A. §2.12.6
has what he corrected and decided that evening. The one-PR list below is kept as the
record of what was asked; the build documents are the specification.

**PR 3, THE BUILD SPEC AS OF 2026-09-10 AFTERNOON.** One pull request, in this
order, each piece verified in a real browser against the real backend and, for
fills, against the live market in his window:

1. **The position area** below the payoff: open now, closed today, earlier.
   Big bold figures, colour from the money without a coloured edge. Per open
   position: legs with entry fill, live mark at the side he would get, profit
   and loss per leg, "net if you exit now" after charges both ways, rule 1
   headroom, max loss, margin stored. The payoff shows the open trade when no
   structure is loaded.
2. **The exit ticket**: exit one leg, exit everything, market or limit per
   leg, editable price with Reset, exit charges per leg, gross, charges both
   ways and net before he presses, close reason from the four the record
   allows. Reverse a leg and add a leg through the same ticket.
3. **Resting orders**: the pending-order book from 2.12.5 item 1, entry and
   exit alike, with a watcher on the chain feed, modify and cancel in the
   position area, expiry at the bell.
4. **The campaign model in the record**: a leg exited alone books its result
   on the position's legs; the trade's result is the sum when the last leg
   closes or he says the trade is closed. One result row per trade stays.
5. **Home**: the running trade unmistakable, margin used from the same sum as
   the desk, the strategy name following the structure.
6. **The drainer's close-row fault**, 2.12.5 item 8, and the price-block
   wording, item 2.

Nothing in `services/fills.py` changes except the addition of resting orders;
the fill rule stays the exchange's.

**PR 5, THE BUILD SPEC AS OF 2026-09-10 EVENING.** The chain works with a live
market; it is unusable while it fights his scroll. In order: keep his scroll
across redraws and update rows in place; show the book and grey the row for a
strike with no trades today, never offer it for a fill; centre and mark the
at-the-money row properly; buttons that look like buttons; a readable table
with fewer figures at a glance and the rest on hover; max pain labelled with
its expiry. Mockup first, because he will judge it by eye.

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

### 2.12.4 THE LIVE TEST OF 2026-09-10 — RUN. Results and decisions are in 2.12.5. The script is kept below.

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

### 2.12.5 WHAT THE LIVE TEST OF 2026-09-10 PROVED, AND WHAT HE DECIDED. Read before building PR 3 or PR 5.

His window, 13:39 to about 14:30 IST. He refreshed the token, said "Hi", and
the main chat walked him step by step. Every figure below was read from the
live log, the database or his vault, not from a summary. The vault session log
`00 - Developer Logs/SESSION_LOG_2026-09-10.md` has the narrative.

**Proven on the live market, first time ever for each:**

| | Proof |
|---|---|
| A send through the ticket | Condor, 13:45:49 IST, 200. Four legs at the ask and the bid, spread cost ₹42, charges ₹127 per leg recorded, spot 23,435.05 stored, broker margin ₹84,929 stored |
| Rule 4 tested against a real margin-used figure | Desk read margin used ₹84,929 and rule 4 ₹1,03,926 of ₹5,54,961 |
| Execute one by one | Trade 03a1b63d: leg 1 at 14:02:29, leg 2 through `/legs` at 14:02:38, one id, sequence 1 and 2, margin re-quoted ₹54,595 |
| The option chain builds a structure the ticket takes | Trade 8030ed03 from the chain, 14:10:48, both legs at the book |
| A limit through the market fills at the market | "limit 111.00 · fills at the bid 111.55, better" on the strangle's leg 2 |
| The close against the live book | Two spreads closed from his PC: every leg at the bid or ask with the traded price beside it, exit charges per leg, one result row each. Net −₹196.91 and −₹123.91 |
| The notes | Three written by the drainer, complete and in order: real opening time in IST, broker margin, fills line, Adjustments for the added leg, Exit with the side each leg hit |
| Home | New position on the line within 15 seconds, no reload, no Exit button |
| The recorder | Real spot, IV and Greeks on 4,428 rows by 14:00, two expiries |

**What he found, and decided. Each is now a build item.**

1. **Limit orders REST. His words:** "I can place 111, 112, or 113 because it's
   a limit order... It should not execute if the price is not available, but
   must be sitting in the system till the time the bid and ask reach the price
   I want." The ticket's refusal of a limit away from the market was my design
   and it is wrong. **PR 3 builds a pending-order book:** a limit that cannot
   fill now becomes an open order, watched against the live book on the chain
   feed's cadence while the market is open, fills when the bid or ask reaches
   it, shows in the position area with modify and cancel, expires at the bell.
   Inside the exchange's daily price band, which is to be read from FYERS.
2. **A price block must not read like a rule block.** The strangle was stopped
   by his limit price, but the red "Unlimited" tiles beside the greyed buttons
   made it look like the hedge rule. Entry is never blocked by a rule; the
   wording says "your price, not a rule".
3. **The position area does not exist and he thought it did.** He approved the
   clickable journey and read all of it as built. Only the ticket half was.
   PR 3 is one build, before anything else: the position area, the exit
   ticket with market or limit per leg, resting orders, and the Home fixes.
4. **The payoff graph shows the open trade** when no new structure is loaded.
5. **A running trade is unmistakable on Home** and goes quiet only when squared
   off. **The coloured edge beside "Open positions" goes**; profit and loss are
   shown another way. He will see a mockup first.
6. **The strategy name follows the structure**, or is his to edit. The condor
   is still called "Short Strangle" because that preset was loaded first.
7. **Home's "Margin used" reads the wrong source**: unavailable on Home while
   the desk showed ₹84,929 from the same position. One sum, both pages.
8. **The drainer fails a `close` row it has already completed** by the other
   route (entry note lands, exit appended at once). Rows queued with
   `awaiting_entry_note` carry no `journal_rel_path`; the close branch must
   resolve the path from the position and mark the row done when the note
   already holds an Exit. Two such rows sit in the outbox now.
9. **The option chain**, all for PR 5: it rebuilds its whole markup every five
   seconds and throws the scroll to the top, so he could not stay on the
   at-the-money strikes (cause confirmed in `option-chain-modal.js`); a strike
   with no trades today shows a dead last trade in live ink (22,850 CE at
   1,575.95 against a live book of 691.90 to 709.85) and must show the book,
   greyed, and never be offered for a fill; the at-the-money row centred and
   unmistakable; buy and sell buttons that look like buttons; a table readable
   at a glance; max pain labelled with its expiry on the chain and on Home.

10. **The Trade Journal page needs its own planning session, not a hurried
    fix. His words:** "The trade journal also needs planning, aesthetics, and
    a lot of things, so I don't want that to be planned in a hurry." Seen on
    2026-09-10: the basis marks work; the times are UTC labelled IST (08:40
    shown for a 14:10 trade); "Trade context and rationale" is blank on every
    row because nothing lets him write a rationale, a trigger, a setup or a
    trend view; the AI lesson and the discipline audit fill themselves with
    words he did not say; the aesthetics are not his. **§2.18 holds it until
    he opens that discussion.** Not part of PR 3.

**The overnight test.** Trade 7cd4d017, the condor, four legs, stays open into
2026-09-11 on his instruction: "We have to see how things look after the market
close." Tomorrow in his window: Home and the desk with a carried position, rule
2 against a real carry, the 15:20 naked-shorts check on a hedged structure, and
the position area's first real subject once PR 3 lands.

### 2.12.7 BUILD A IS COMPLETE. Built 2026-09-10. MERGED as #65, #66, #67 and live since 2026-09-11 00:11 IST. Proven in his window on 2026-09-11: §2.12.8.

All three parts are on `feature/swayam-build-a-desk-home-chain-042`, one pull
request. **Nothing is live until he merges, and migrations 022 and 023 must be
applied first.**

What part two added, on top of parts one and three:

- **Home's running-trade band**, full width, below the daily check-in and above
  Your money, replacing the collapsible strip. Blinking means running, solid
  green or red means a target he set was reached, muted means nothing open or
  squared off. It does NOT blink while the market is shut: the colour stays,
  the breath stops, and the chip says "at the close", because his profit and
  loss is not moving then.
- **Targets**, per leg as prices and on the trade as rupees net of charges,
  behind one sage button on the position card. A blank box is silence; a blank
  trade loss falls back to rule 1 read live. `services/targets.py` owns the
  rules and `/api/positions/live` carries `state`, `alerts[]` and `targets`.
- **Manage on Home** opens BUILD_01's exit ticket in place, one leg or all.
- **Home's Margin used** reads `margin_required_inr`, the field the desk reads,
  and shows rule 4's share. The two pages agreed at 84,929 in the browser.
- **The payoff crosshair.** Hover reads the NIFTY level and the money at expiry
  and today. Proven on the real page: 25 pointer moves, zero re-renders, and
  the markup before the crosshair group byte-identical.
- **The terminal-test phase.** `swayam_phase` holds one timestamp, null today.
  `provenance = 'terminal_test'` on every new position until he runs
  `scripts/start_paper_trading.py`. `scripts/mark_terminal_tests.py` marks the
  trades already in the record and **skips the open condor until it is
  closed**. Both are his to run.
- **Two fixed facts removed from Home's source:** "starts clean from 8
  September 2026" and "81 build-and-test rows". Both were written into the
  page and neither was read from anything.

Verified 2026-09-10: Python 642 passing with the one stale mock still failing
identically on `main`, JavaScript 314 passing in 35 files, his journal folder
6 notes before and after every run, zero console errors on a clean load in
both themes. **Only his window can prove a target reached on a live mark.**

### 2.12.9 BUILD B, RESTING ORDERS. Built 2026-09-10 night. Pull request #71 open, not merged.

`docs/builds/BUILD_03_RESTING_ORDERS.md` has the full state. In short: item 1
of 2.12.5, his words, is now built. **A limit the book has not reached no
longer refuses anything. It rests as an open order until the book comes to it,
for entry and for exit, and expires at the bell.**

- **The order book**, `swayam_orders`, migration 024, **applied by him at
  17:59 on 2026-09-10**. One trading day only. A row there holds no margin and
  has cost nothing until it fills.
- **The band is the exchange's, read per order from the FYERS DEPTH call**,
  not the quote, which carries none. Verified live: the 23,800 September call
  banded 0.05 to 327.45 with a 0.05 tick that night, against 263.85 on
  10 September, so the band genuinely moves and genuinely must be read each
  time. A depth call that fails still lets the order rest and says the band
  could not be read. Never an invented band.
- **The watcher rides on the chain feed's refreshes and never calls FYERS.**
  When the book reaches his price it sends the order down EXACTLY the path a
  leg he pressed Send on takes, so the fill rule, the charges, the note and the
  execution key are all the code that already existed. `services/fills.py` is
  untouched.
- **One order fills at most once**, and the guarantee is one conditional
  update in the database that only one process can win. His own requirement.
- **Three groups in the position area**: resting with what each waits for,
  filled from the book today, expired or cancelled today. **The count reaches
  Home's band as its third figure.**
- **His addition of 2026-09-10:** a resting exit killed by the bell while its
  trade is still open is announced in plain words on both screens and points at
  the 15:20 naked-shorts check. Proved live on his real condor. A warning only;
  it never trades.
- **And the sentence that must never be missing**, on the screen in every
  state and in the handoff: a resting order fills only while the terminal is
  awake and reading prices, which on Cloud Run means while a page of his is
  open. It is not sitting at the broker.

**The main chat's review of 2026-09-11 found a real bug and it is fixed.** The
watcher re-sent a claimed order down a path that, since this build, RESTS a
limit the book has not reached. When the market moved away in between, that
re-send wrote a SECOND order for the same leg and let the watcher mark the
original filled on an empty fill. The execute, add-leg and exit paths now have
an internal `allow_resting`, and the watcher enters through `execute_trade_now`,
`add_leg_now` and `exit_leg_now`, which mean fill now or refuse; a moved-away
book releases the order back to resting. Nothing may read an answer as a fill
without a real position id and a real fill. One test per path.

**And no unit test may reach FYERS any more.** `tests/conftest.py` stands in
for `fyersModel.FyersModel` and RECORDS every attempt, because several call
sites treat a broker failure as "unavailable" and would swallow the reach. It
caught one test that was not this build's: the institutional-separation test in
`test_home_snapshot.py` spent five real FYERS requests per suite run on an
assertion about field names.

Verified on the merged tree, 2026-09-11: Python 695 passing with the one stale
mock still failing identically on `main`, JavaScript 340 passing in 36 files,
the three groups rendered from the real backend in both themes, the
verification orders removed again and `swayam_orders` shown empty. **Only his
window can prove a fill from the book, and, because nothing may rest after
15:30, a resting order on the live screen at all.**

### 2.12.6 WHAT HE CORRECTED AND DECIDED ON 2026-09-10 EVENING. Read before any build.

**Corrections, in his words.**

1. **Every trade in the record is a terminal test, not a paper trade.** "We
   have not started the paper trading. We are doing the testing of how the
   terminal works. All these paper trades are test trades... I did not
   backtest, plan, or review it. It was just clicking the order and checking
   how the terminal behaves." All six, the open condor included. Paper trading
   starts on the day he says; Build 02 gives him the script that marks it and
   the script that marks the six. His paper record must start clean: "how I
   will play with the money depends upon how my paper trade will perform."
2. **The system named the condor "Short Strangle". He did not.** "It was the
   system error that gave it the name." He loaded the strangle preset, the
   ticket refused his limit price because the book had not reached it, he went
   to a condor at market, and the name stayed with the preset. "I had no role
   to play in naming any order I made today." Build 01 derives the name from
   the legs; Build 03 makes the limit rest.
3. **The backtester is what runs behind**, not the strategy builder. It is the
   backtester chat's work. The deadline of 11 September will not be met, and
   he said so.

**Decisions.**

- **The main chat is the orchestrator and does not build.** It plans, draws
  the mockup, writes the build document with its paste-prompt, and reviews
  the finished build on the running system before he merges. One fresh
  builder chat per build, one at a time, one pull request each.
  `docs/builds/README.md`.
- **Two builds, his correction later the same night.** "We cannot go with
  small, small builds... I don't have a whole day for building it." Build A
  is the desk's position area, exit ticket and campaign model, then Home's
  band, targets, Manage, the crosshair, the terminal-test phase and the
  big-number pass, then the option chain: `BUILD_01`, `BUILD_02`, `BUILD_04`
  in that order, one chat, one branch, one pull request. Build B is resting
  orders alone, `BUILD_03`, kept apart because it is the trickiest to prove.
- **The mockup**, Swayam Position Area,
  https://claude.ai/code/artifact/ef242a22-59a7-4752-8aa4-91d59393c5d5, built
  on the real condor at the 15:26 closing book, accepted with his feedback
  applied. "The mockup must be identical" to the build.
- **Home: Option B.** The whole band takes its colour from the money, no
  coloured edge. **Blinking means running. Solid green or solid red means a
  target was reached, profit or loss, on a leg or on the trade, and needs
  him. Muted means nothing open or squared off.** His correction later that
  night, after a first reading had it backwards: "Blinking means the trade
  is running. When it becomes a solid color, then the trade has reached its
  target, either profit or loss. Green and red colors define it." And: "As
  soon as the trade is squared off, everything goes mute: no blink, no color."
- **Targets**, "target always means both loss and profit", per leg by
  preference, the whole trade as the fallback, set from a designer button on
  the position card that opens a small modal. "I don't want unnecessary
  things lying on my position page." A blank box is no signal; a blank trade
  loss falls back to rule 1.
- **Manage on Home opens the exit ticket right there**, one leg or all. Not a
  link to the desk.
- **Resting orders are visible in the position area as Open orders**, three
  groups, each labelled and coloured by its nature. No modal to keep open.
- **The payoff crosshair**: hover reads the NIFTY level and the profit or
  loss, at expiry and today, without moving anything. Accepted as drawn.
- **"Net if you exit now" is after charges both ways**: "the actual profit
  that will come into my account after exiting." Keep it beside the open
  profit or loss, never instead of it.
- **Standing screen rules:** numbers he reads are big and bold; informative
  text is small and muted; a card is 70 to 80 percent filled; any change
  with a visual impact gets a mockup first.

### 2.12.8 THE LIVE TEST OF 2026-09-11, AND WHAT COMES NEXT. Written by the main chat after his window.

**Proven on the live market, first time for each:** Home's band blinking on
the running condor; a target reached turning it solid and naming the leg;
the Targets modal saving and reading back; the crosshair; the option chain
holding his scroll during a live session; the position card's figures
reconciling to the paisa against the legs; **a hedged dummy (bull put
spread, `2026-09-11-trade01`) opened through the ticket and closed through
the new exit ticket via Manage on Home**, one result row, and the drainer
writing its note with the Exit block. Marking script run: five closed
trades marked `terminal_test`, notes moved. Smart App Control had blocked
every Python on his PC from 17:39 on the 10th; he turned it off.

**What broke, in priority order, all going to the polish chat's round one:**

1. **A naked leg cannot be recorded.** Its maximum loss is unlimited and the
   execute path tried to store infinity, which the database refuses: "Out
   of range float values are not JSON compliant". Store `null` with the
   reason, everywhere a figure can be unbounded. Never exercised before
   because every earlier trade was hedged.
2. **FYERS refused requests after 15:00, code 429 "request limit reached".**
   Build A's pages poll every five seconds and the live valuation quotes
   each leg straight from FYERS, outside the chain feed built on 8 September
   to prevent this. It cost him one refused exit. Every quote goes through
   the chain feed; count FYERS calls per minute on the live logs before and
   after.
3. **Entry was blocked by a rule.** With the plan chip on "carrying
   overnight", the overnight and black-swan checks are blocking for a naked
   leg (`validation.py`, `blocking_checks`). His rule: entry is never
   blocked; at entry every check is advisory; carrying is gated at 15:20.
4. **Home's band colours a reached target backwards:** red on profit, green
   on loss. The position area's strip is right.
5. The Targets modal accepts a number on the wrong side of the entry; the
   chain offers two expiries instead of all; rules are not evaluated for a
   loaded open trade; the open condor's chip says "paper trade"; pages keep
   each other's scroll position; the advances line overflows; the AI chat
   needs Clear and Delete; the explanatory prose goes.

**Round two, after round one: the look.** Atlas-inspired: pastel filled
cards and buttons, no dark corners or outlines, generous spacing, very
large calm numbers, a clear hierarchy; sage, coral, amber and blue; no
lilac. Chain Buy and Sell as small pastel-filled buttons. Mockup first in
the polish chat, he approves there, then built identical. The Atlas
sources are at `D:\Claude\POS\Atlas\Deploy\css\`.

**Merge order:** Build B (resting orders, done, reviewed by the main chat,
695 passing) opens its pull request first, merging main into its branch;
then polish round one; then round two.

**His decisions and asks of 11 September:** the condor stays for at least
one more expiry. The crosshair's big figure should become Today with At
expiry small beneath (builder's recommendation, accepted for round two).
Per-leg targets become adjustment triggers at a price and the trade's rupee
target is the real one, with a "50% of max profit" quick-set: its own
session with a mockup. Exiting or adding a leg of an EXISTING trade must
never be blocked by the time of day; a fresh single-leg entry after about
15:15 may be. Closed trades read muted everywhere.

**Build C, cloud hygiene, still to be written by the main chat**, from his
cost chat's audit: 60+ untagged 500 MB images (about 10 builds a day, every
merge deploys, documents included) with a cleanup policy and a trigger that
ignores documents-only merges; three `swayam-dashboard` regions of which
`asia-southeast1` is the one, delete the other two; one SIGABRT on
2026-09-10 14:52 IST, revision 00068, cause unknown; the recorder writing
each file twice (flat and nested paths) by design, to be reduced to one;
the nightly backup (§2.6). AI spend to date ₹6.20; BigQuery unused.

### 2.12.10 WHERE IT STANDS AFTER #71 AND #72, AND WHAT ROUND 1b IS. Written by the main chat, 2026-09-11 evening.

**Merged today, in this order, each with its green tick before the next:**
Build B, resting orders, **#71 at 15:47 IST**, and the polish chat's round
one, **#72 at 16:33 IST**. `main` carries both. Nothing else is open.

**What #72 actually delivered.** His own nine-item review list from the live
test, minus the AI chat panel, which he pulled out into a round of its own.
Home's band no longer colours a reached target by the sign of the open profit,
which is why a profit target on one leg painted solid red while the trade was
down ₹16. The Targets box refuses a number on the wrong side of the entry. The
chain lists every expiry, nearest first, so a calendar's far leg can be picked
at last. A loaded open trade is judged by the server, **and that exposed a
fault nobody had reported: rule 4 double counted an open trade's own margin,
reading ₹1,69,626 where the truth was ₹84,697.** The condor's chip reads the
phase instead of its row. Pages open at their top. The advances figure stops
overflowing. The explanatory prose is gone. Python 703 passing, JavaScript 348.

**⚠️ THE THREE FAULTS FROM HIS LIVE TEST ARE STILL ON `main`.** They were
written for the polish chat as items 0a, 0b and 0c and **the prompt carrying
them was never pasted**, so round one was his own list only. Verified in the
merged code on 2026-09-11, not inferred:

| | The fault | Where it lives today |
|---|---|---|
| 0a | A naked single leg cannot be recorded. `options_math/payoff.py` returns `math.inf` for a net short call or put and the execute path writes that to the database, which refuses it | `payoff.py` lines 153 to 193, and the execute path's `max_loss_inr` writes in `routes/execution.py`. `validation.py` line 96 already handles it correctly; storage does not |
| 0b | FYERS refused requests from 15:00 with code 429 and it cost him one refused exit | `routes/positions.py` lines 267 and 279 call `fyers_client.get_option_chain` directly, outside `api/chain_feed.py`, while the pages poll every five seconds |
| 0c | Entry was blocked by a rule, which breaks his first principle | `routes/validation.py`, the `overnight_carry` check is `blocking=True`, so the plan chip on "carrying overnight" stops a naked leg at the ticket |

**Round 1b is those three and nothing else**, in the same polish chat because
it holds Build A's code, on a fresh branch `feature/swayam-polish-round1b-049`
off `main` because its own branch is merged, as its own pull request, **before
round two's mockup.** Entry is never blocked: at entry every check is advisory
and shown; carrying is gated at 15:20 by the naked-shorts check; exiting or
adding a leg to a trade he already holds is never blocked by the time of day,
while a fresh single-leg entry after about 15:15 may be.

**Round 1b also asks that chat for something that is not code.** He has told it
how he wants the AI chat panel to behave, in that chat and nowhere else. It
writes that out as a plain block he can copy, in his words where it has them,
and builds none of it. He pastes it here, the main chat turns it into a mockup
and a build document, and it is built by whoever he is advised to give it to.

**The test list for his next window, in priority order.**

1. **Resting orders, Build B.** Merged after the bell, so they have never
   existed on a live screen: nothing may rest after 15:30. A sell limit above
   the book, watched, modified, then filled when the book comes to it.
2. **A naked single leg**, only if round 1b has merged. Without it, it fails
   the same two ways it failed on 11 September.
3. **The carried condor:** the band, rule 4 counted once at about ₹84,697, and
   the two targets he saved.
4. **The 429 watch from 15:00**, read afterwards from the Cloud Run logs, which
   costs him none of his window.

**Build C, cloud hygiene, is still the main chat's to write**, and his framing
of 2026-09-11 is the shape it takes: "whenever money is required, do not hold
if the money provides real value. Otherwise, we'll cut it." So the document
separates what is waste from what is capability, and never asks him to approve
a saving that costs him something. Waste today: the untagged images, two dead
`swayam-dashboard` regions, the recorder writing every file twice. Capability
he is missing: the nightly backup, §2.6. His reason for urgency is that the
real bill has not arrived yet, and the backtesting and AI work is what will
bring it.

### 2.20 THE LOOK, THE AI PANEL, AND HOME. Decided with him 2026-09-11 night. Three builds.

**Round one (#72) and round 1b (#74) are merged.** Round 1b fixed the three
faults from his live test and, on the main chat's review, four more places that
still assumed a maximum loss was a number: the close route crashed on a naked
trade, and the exit note would have printed a result as 0.00% of a risk that had
no ceiling. It shipped a lifecycle test and `scripts/prove_naked_trade.py`.
**Only his window can prove a real naked leg.**

#### 2.20.1 Why his terminal does not look like Atlas, measured not guessed

His four accents are **already Atlas's, to the hex**. What was never copied is
the ground beneath them. His dark background is `#101116`, a cold blue-black,
where Atlas is `#1a1a1a`, a warm charcoal; his dark text is `#edeff4` where
Atlas is `#e2e2e2`; and **his light theme's sage is `#15803d`, a vivid
saturated green, where Atlas is `#6f8f65`**. A warm sage on a cold blue-black is
what he has been reading as harsh, every day, for weeks. His own token file's
first line says it was inherited from Atlas. `BUILD_06_THE_LOOK.md` §0 has the
full table.

#### 2.20.2 The AI panel. His decisions, and the mockup he approved

**The mockup, interactive, and the build must be identical to it:**
https://claude.ai/code/artifact/f3efa90c-c57d-4dba-bd00-924b3c04ee04

- **It floats above the page and never reflows it.** Narrowing the page was
  measured and offered to him; he rejected it. Do not re-propose it.
- **It opens small, about four or five lines, every time.** Where it opens is
  remembered; how big it was, is not.
- **Eight resize handles**, four edges and four corners, clamped to half the
  window across and half down.
- **Detach, move, attach, close**, and a tiny bar state.
- **No starter prompts, in any state.** His words: "I don't want these presets.
  It is a noise taking space."
- **Voice first.** The composer stays small and the microphone is a real control.
- **⚠️ The exit ticket and the execution ticket are ALWAYS above the panel.**
  His words: "my exit ticket will always be on top. Orders are a priority, so
  nothing on top of that." A money rule, not a layout preference.
- **Clear empties the pane; Delete removes the open conversation after a
  confirm**, and takes its attached images with it, which the existing endpoint
  leaves orphaned today. Notebook entries and pinned decisions survive with a
  null source. Only the open conversation; there is no delete-everything.

#### 2.20.3 Home loses its chat and gains a saved daily summary

**His decision, and the big change.** "On the homepage, remove this on-page chat
area. It is not required now because I'm getting a floating chat that I can move
and resize." The zone goes; **no conversation is deleted**; the floating panel
then behaves identically on every page, which removes the special case the first
mockup had.

In its place, **"So far today"**: one Generate button, and the summary stays
until he presses it again. **It is saved as a row a day in the database**, in
his words: "I want to save the AI-generated summary. I'm paying for that, so I
don't want to lose those details and create a record of what's happening, a
trend in the market or in the geopolitics as well." The panel reads it.
Regenerating a day replaces that day's row. **It is an AI feature and obeys his
standing cost rule: a manual button, a 60-minute cache, a daily cap, never on
page load.**

#### 2.20.4 The order, and why

| Build | Chat | Where | When |
|---|---|---|---|
| **C, cloud hygiene**, `BUILD_05` | His Google Cloud cost chat | A worktree with its own venv | Now |
| **Round two, the look**, `BUILD_06` | The same polish chat | The primary folder | Now |
| **The AI panel**, `BUILD_07` | A fresh chat | The primary folder | After round two merges |

The panel waits for the look because otherwise it is built twice. The two
running now overlap in exactly one place, the last-backup age on Home, which
belongs to `BUILD_05`; round two does not touch that line and `BUILD_05` touches
nothing else on Home. `docs/builds/README.md` carries the same rule.

### 2.21 THE NIGHT OF 11 SEPTEMBER. Nine pull requests, and what was learned. Written by the main chat.

**He was the messenger all evening**, carrying handoffs and prompts between
four chats while doing his office work, and he asked for everything gathered in
one place before this chat is cleared. This section is that record.

#### 2.21.1 What merged

| PR | What |
|---|---|
| #71 | Build B, resting orders |
| #72 | Polish round one, his nine-item review list minus the AI panel |
| #73 | The DuckDB roadmap edit and the three faults recorded |
| #74 | Round 1b, the three faults from his live test, plus four more found in review |
| #75 | The three build documents: the look, the AI panel, cloud hygiene |
| #76 | Round two, the whole terminal on Atlas's grounds |
| #77 | The stale notifications mock, which had been hiding behind "1 long-standing failure" |
| #78 | Build C, cloud hygiene: 35.8 GB down to 8.1 and the waste stopped at its source |
| #79 | The clarity pass on the new look |

**The suite is at zero failures for the first time in weeks.** #77 removed the
red everyone had learned to ignore. Keep it at zero: a normalised failure is how
the next real one hides.

#### 2.21.2 ⚠️ Two public copies of his terminal, found and destroyed

`swayam-dashboard` existed in **three** regions, not one. The `asia-east1` and
`asia-south1` copies were 4 September builds with **no Identity-Aware Proxy**,
`allUsers` in `roles/run.invoker`, ingress `all`, and **his real
`SUPABASE_SERVICE_ROLE_KEY`, `FYERS_ACCESS_TOKEN`, `FYERS_CLIENT_ID`,
`FYERS_APP_ID` and `FYERS_SECRET_KEY` mounted from Secret Manager at `latest`**.
Anyone with either URL had a no-sign-in copy of his terminal wired to his live
database.

**The live site was never exposed.** It is the `asia-southeast1` service, its
IAP was on throughout, and the domain returned the Google sign-in challenge
before, during and after. Checked by loading it, not by reading a setting.

The public bindings were removed first, then both services deleted, then he
deleted the leftover `asia-south1/swayam` repository himself. **The only reason
this was not worse is that there is no order-placement code in this
repository.**

**The lesson, and it is new:** a region tried once and abandoned keeps its
secrets, its ingress and its public binding for ever. Nothing expires. When a
region is abandoned, delete the service the same day.

#### 2.21.3 The build machine nobody had counted

Every build ran on `E2_HIGHCPU_8`. Cloud Build's free 2,500 minutes a month
apply **only to `e2-standard-2` in the default pool**; every other machine bills
from the first minute. At roughly 1,450 build-minutes a month that was **about
₹2,000 every month since 4 September**, against **₹0** on the default machine.
**Seven times what the image pile cost**, and invisible because nobody had
multiplied the minutes.

Measured after the change, on the running system: the first build on
`E2_STANDARD_2` took **6m52s** against a previous average of **4m52s**. Two
minutes on a build he never watches. **It stays.**

Found because the cost chat questioned one line of a build document the main
chat had not thought about at all.

#### 2.21.4 Both build documents were wrong, and both builders caught it

- **`BUILD_06` named one token file and there are two.** Home, the desk, both
  tickets, the chain and the targets modal all render inside `sw-desk` and take
  their colours from `swayam-desk.css`, whose light ground was pure white on
  white. Following the document literally would have restyled the journal page
  and left the two pages he looks at every day untouched.
- **`BUILD_05`'s cleanup policy would have freed 0.85 GB of 35.4.** Every Cloud
  Run revision pins an image digest and there were 82 revisions pinning 81 of
  the 83 images. **Nothing prunes Cloud Run revisions**, so the unlock was
  deleting revisions first. And the document's "keep every tagged image" rule
  would have protected everything for ever once §3.1 tagged every image with
  its commit SHA.

**This is the loop working.** Documents are written before code precisely so a
builder can find the fault in the plan rather than in production.

#### 2.21.5 The vault cannot be reached from the cloud, and it broke an instruction

`BUILD_05` §3.5 said the nightly backup would keep thirty nights in his vault.
**A job running in a Google data centre cannot see `G:\My Drive\Second Brain`**,
which is a local filesystem path, the same root cause that breaks his daily
check-in on the live site (§2.13). So §3.5 splits:

- **Cloud half, 02:00 IST:** Supabase to the bucket. Never depends on his PC.
- **Local half, later the same night:** the thirty-night vault copy and the
  backtest-history sync, with catch-up so a night his PC was off runs at next
  logon rather than being skipped in silence.

**The local half must run AFTER the cloud half finishes**, or it copies the
previous night's backup and reports success.

#### 2.21.6 His backtest history exists in exactly one place

`data/history`, 631 MB, on his PC, `.gitignore`d. The minute bars alone took 90
minutes and 8,576 FYERS requests to assemble. The roadmap says the bucket is its
copy and **that copy has never been made**. Cost to make it, read from Google's
billing catalogue rather than quoted: **₹1.07 a month**.

#### 2.21.7 The SIGABRT, solved

Revision 00068, 2026-09-10 14:52 IST. `services/fyers_token.py` called Secret
Manager with **no timeout**; a slow call held the worker past gunicorn's
60-second limit and it aborted. The stale-token fallback was already correct and
simply never ran in time. Fixed with `timeout=5.0`. A cause, not a hardening.

#### 2.21.8 The data map, his idea

He asked for one place holding every data store, where its backup is, how to
reach it, and what deletes it, so that any new chat can be pointed at it.
**Decided: it lives in his vault, not in the terminal**, because the day he most
needs to know where his backups are is the day the app is broken. It is
`02 - Projects/Trading/06 - Platform Plan/Data Map.md`, written in two halves: a
hand-written map the automation never touches, and a live-figures block between
markers that the local nightly task rewrites. A read-only panel in Settings
showing the same live figures is **deferred until he has used the note for a
week** and knows what he actually reaches for.

#### 2.21.9 Rules learned tonight, for whoever comes next

1. **A command that reads a file from the repository must be given with its
   full path.** He ran one from `C:\Windows\System32` and it failed. Worse, the
   copy in his primary folder was the **broken** version of that lifecycle rule,
   so a working path would have re-applied the fault.
2. **"Be careful" is not an instruction.** Either a command should be run or it
   should not. Say which, and say what it touches.
3. **The worktree rule was the right reason attached to the wrong rule.** Never
   a worktree that SHARES the primary venv. A worktree with its OWN venv is
   allowed and is how Builds B and C were both done. Corrected in `CLAUDE.md`
   and `docs/builds/README.md`. Standing up that venv is not trivial: on Python
   3.13 `pip install -e .` fails because `aiohttp` will not build from source.
4. **Leaving the primary folder on the wrong branch strands another chat's
   work.** The main chat did this once tonight and the polish chat's round 1b
   was briefly uncommitted on `main`. Park the folder where you found it.
5. **Three backup functions exist in `functions/` and none is deployed**, which
   is why the `db/`, `ai-chat/` and `weekly/` prefixes sit in the bucket with
   nothing maintaining them. A thing that was built and never deployed looks
   exactly like a thing that works.

### 2.22 12 SEPTEMBER. THE DEPLOY THAT FAILED, AND THE AI PANEL PLAN THAT CORRECTED ME.

#### 2.22.1 ⚠️ THE BUILD FOR #81 FAILED AND THE SITE DID NOT DEPLOY

Merged at 17:06 UTC on 11 September. Its build, `fb76d033`, failed at step 0:

```
COPY failed: file not found in build context or excluded by .dockerignore:
stat migrations/: file does not exist
```

`#81` added `COPY migrations/ ./migrations/` to the `Dockerfile` because the
new backup refuses to write a schema-less backup. **`.dockerignore` excluded
`migrations/`.** The backup was proved on the builder's own disk, where the
folder is simply there. **The image was never built. A path nobody ran.**

**What this cost.** The live site kept serving the image from the `#78` merge,
which already carried the new look and the clarity pass, so nothing he could see
was wrong. What was missing was Home's backup line and, more seriously, **the
module the 02:00 Cloud Run job calls**. That job was left enabled on the
reasoning that it would "self-heal on the first build after merge" — **and that
reasoning rested on a build nobody had run.** No backup ran on the night of
11 September. Nothing was lost: a manual backup of 900 rows was taken that
afternoon and he has taken no trade since 31 March.

Fixed on `feature/swayam-dockerignore-migrations-058` (#83) by removing the
line rather than negating it, because directory negation in `.dockerignore` is
unreliable, **and this time proved by building the image.**

#### 2.22.2 The build machine, measured and settled

First build on `E2_STANDARD_2`: **6m52s**, against a previous average of
**4m52s** on `E2_HIGHCPU_8`. Two minutes on a build he never watches, against
roughly ₹2,000 a month. **It stays.** Images now carry their commit SHA.

#### 2.22.3 THE AI PANEL PLAN CORRECTED THE BUILD DOCUMENT IN THREE PLACES

`docs/builds/BUILD_07_AI_PANEL.md` was written as though "So far today" were a
new feature. **It is not**, and the builder found it before writing a line.

1. **"So far today" already exists** as a card, a route, a service and storage
   in `swayam_home_snapshot` (migration 014), **with the cost rule already
   correct**: manual only, 60-minute cache, a cap of 8. The real work is the
   one-row-a-day storage he asked for, not the feature.
   **And the trap underneath it:** the daily cap is counted by counting ROWS
   since IST midnight. Collapse to one row a day and the cap silently becomes
   one per day. The new table therefore carries `generation_count` and the cap
   reads that. **Checked by the main chat: `count_grounded_calls_today` is used
   only inside `so_far_today.py`, so this cannot shift any other cap.**
2. **Deleting Home's chat zone would have deleted the summary with it.** The
   summary card is mounted into the chat component's own slot, not into Home.
   It must be re-parented in the same change.
3. **There is no speech-to-text anywhere in the repository.** `tts-player.js`
   reads aloud; nothing listens. The mockup draws the microphone as a
   first-class control. **That is a build, not a move.**

#### 2.22.4 The panel would have covered the exit ticket, and it is a z-index fact

Read from the stylesheets: both tickets use `.xt-backdrop` at **950**, the
targets modal at 960, the option chain at 900, and **the AI drawer today sits at
1000, above both tickets.** The floating panel goes to **800**, below all of
them, so his rule holds structurally rather than by luck. **To be proven on
screen, by dragging the panel over the exit ticket and then opening it.**

The page-shift apparatus he rejected lives in `web/src/styles.css` lines 481 to
520 and again at 549, pushing six containers by `margin-right: 400px` on a body
class. **All of it comes out.**

#### 2.22.5 His decisions of 12 September

- **The microphone is the browser's own dictation.** Free, nothing to do with
  the AI's model or cost cap, Chrome and Edge only. **A browser that cannot do
  it must say so in words and offer typing, never show a dead microphone.**
  A paid speech service is a different build and touches cost.
- **The summary does not auto-fold.** `so-far-today-card.js` currently hides
  itself for the rest of the IST day once expanded, remembered in
  `localStorage`. The mockup he approved says it stays until he presses
  Generate again. **The mockup wins; a manual Show and Hide remains.** The
  clarity pass's folding rule is for explanations, and the summary is content.
- **The migration backfills the newest summary of each past day** into the new
  table as it creates it, deleting nothing from the old one, so the record he
  is paying for starts with what he already owns.

#### 2.22.6 Deleting a conversation orphans its images today

`ai.py:156` writes attachments to `swayam-ai-chat-attachments/{conversation_id}/`
and **nothing has ever cleaned that folder.** `DELETE /api/ai/conversations/{id}`
removes the rows and leaves the images. Fixed inside BUILD_07 on his decision of
11 September: the images go with the conversation.

### 2.23 THE REST OF 12 SEPTEMBER. The backup finally ran, and a migration nobody had applied.

#### 2.23.1 ⚠️ THE NIGHTLY BACKUP HAD NEVER ONCE SUCCEEDED, AND NOW HAS

Two executions of `swayam-nightly-backup`, both failed, both with the same
cause. The job read all 19 tables and was refused on write:

```
BACKUP FAILED: 403
swayam-dashboard-sa@swayam-capital.iam.gserviceaccount.com does not have
storage.objects.create access to buckets/swayam-backups/objects/supabase/...
```

**The job's service account had no binding on that bucket at all.** Verified by
reading the bucket policy, which held only project-level legacy roles, and the
account's project roles, which include `storage.objectViewer` and nothing that
can write.

**Why nobody caught it: every successful backup so far ran from his own machine,
as him, the project owner. The same class of fault as the `migrations/` failure
one layer up. Proved under one identity, run under another. Identity is part of
the path.**

**The fix was ONE grant, not the two proposed**, because the account already
holds read across the project:

```
gcloud storage buckets add-iam-policy-binding gs://swayam-backups   --member=serviceAccount:swayam-dashboard-sa@swayam-capital.iam.gserviceaccount.com   --role=roles/storage.objectCreator
```

**`objectCreator`, deliberately not `objectAdmin`: it can write a new backup and
it cannot delete one.** A backup writer that can destroy backups is how the data
and its copies are lost in the same accident.

**Proved by invoking, the same night.** The job was executed by hand rather than
waiting for 02:00: it succeeded, and `gs://swayam-backups/supabase/2026-09-11T21-33-51Z/`
is the first backup of his record ever written by a machine.

**The design rule earned its keep on its first real night.** `record_backup.py`
failed the job loudly. `backup_service.py`, deleted the same evening, would have
logged a warning and returned success, and he would have believed in a nightly
backup that did not exist.

#### 2.23.2 ⚠️ MIGRATION 025 HAD NEVER BEEN APPLIED, AND THE MAIN CHAT SAID IT HAD

Round 1b (#74) was merged on 11 September. **Its migration was never run.**
Found on 12 September by reading `apply_migration.py status` rather than trusting
a document: 19 applied, 1 pending.

**What it meant.** `max_loss_inr` was still `NOT NULL` and
`max_loss_unbounded_reason` did not exist, so **the entire naked-leg fix was
inert in the live database**. A naked single leg would have failed again in his
next window, where testing one is item two on the list.

**The main chat's own error, stated plainly:** `SUCCESSOR_PROMPT.md` claimed
"migrations 022 to 025 are applied". That was written from the pattern of the
previous days, not checked. **A migration is applied when
`apply_migration.py status` says so and at no other moment.** Applied by him at
last on 12 September.

#### 2.23.3 A handoff command that could not have worked, twice over

`BUILD_07`'s handoff told him to run `apply_migration.py 026` from his primary
folder. The script takes `status`, `up` or `baseline` and **never a number**; and
migration 026 existed only in the panel's own clone, which has no environment to
run anything with. **The order was inverted instead:** merge, pull, then apply
with `up`, which the handoff's own text says is safe because the card explains
which table it cannot read and Generate refuses rather than spending money it
cannot record.

**Third command in two days that would have failed him.** The pattern is always
the same: a path or an interface assumed rather than read.

#### 2.23.4 The stacked pull request, caught before it bit

**#87 was opened against #85's branch, not `main`** — the exact shape that made
#35 merge into a dead end while the live site silently kept the old interface.
Caught by reading the base branches before recommending a merge order. He merged
#85 first and checked #87's base before merging it.

#### 2.23.5 The AI panel is merged

`#86`. Its second round answered nine points of his own review. **What was
proven the right way:** the exit ticket covering the panel was **hit-tested at
three points, not read from a stylesheet**, and his conversations were counted
against the live database before and after Home's chat zone was removed — **110
conversations and 35 messages, unchanged**.

**Honestly unproven, and it says so:** dictation actually transcribing, because
the browser blocked microphone capture, and anything the closed market hides.

Migration 026 creates `swayam_daily_summary` and backfills the newest summary of
each past day. The cost rule moved to a `generation_count` column so that
collapsing to one row a day did not silently turn a cap of eight into a cap of
one.

#### 2.23.6 Left for a small follow-up

- **The nightly local task rewrites `docs/DATA_MAP.md` inside the repository
  every night**, so his working tree is dirty every morning and an unrelated
  file can be swept into another build's commit. **The vault copy is the one
  that matters; the repo copy should stop being written nightly.**
- **`scripts/restore_drill.py` has no automated test**, and proving it needs a
  live database, which is why it does not have one. Deliberate, and recorded so
  it is not mistaken for an oversight.
- **The restore drill has still never run against a backup the CLOUD JOB made.**
  One now exists, so it finally can.

### 2.18 THE TRADE JOURNAL PAGE. To be planned WITH him, in its own discussion. Not started.

Opened by him on 2026-09-10 after seeing the page with six real rows. Do not
build anything here without a plan he has approved in the chat. What is known:

- The record is right: squared-off trades only, charges per leg, the basis on
  every row, the 81 build rows excluded. Keep all of that.
- Times print the UTC hour with an IST label. Every stamp on the page must be
  IST, the trade's own time.
- "Trade context and rationale" is blank on every row and always will be,
  because there is no place to write the rationale, the trigger, the setup,
  the trend view or the exit reason in his words. He wants to; his historical
  sheet has all of them. Where and when he writes them is the design question:
  on the ticket before the send, in the position area while it runs, on the
  journal row after, or in the vault note, and which of those is the source.
- The discipline audit prints "Rules Followed, trade was managed strictly
  according to written position sizing, stop-loss ceiling, and entry criteria"
  for every trade, which is not a measurement. It must show what was actually
  checked, or a dash.
- The AI lesson is generated on close and reads as filler. It stays a manual
  button under the cost rule, and the lesson ledger is his to edit.
- Aesthetics: he will judge it by eye. Mockup first, like the desk.

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

### 2.15 Backtesting, milestone one: the data — RESEARCHED AND TESTED 2026-09-09 night

**This is `ROADMAP.md` §3 milestone 1.** The backtester must test HIS structures
under HIS constraints: entries in his window of roughly 14:00 to 15:30 IST, his
capital, his four rules, charges per leg from `services/charges.py`, fills at
the bid and the ask, and the near-expiry square-off habit for calendars. Before
it is trusted at all it must **reproduce the 21 swing trades in
`00 - Reference/Historical Swing Trades`** and get what actually happened.

Nothing was bought and nothing was signed up for. Everything marked **tested**
was called against his live FYERS account on 2026-09-09 night; everything else
is a vendor's own published statement, cited in §2.15.8.

---

#### 2.15.1 THE HEADLINE: he already owns the data, and it is free

**FYERS has an expired F&O contracts endpoint, it is not in the version of the
SDK this repository installs, and it works on his account today.**

It was found because he dropped his own Perplexity research into
`docs/Independent reports/` at 23:46 on 2026-09-09, and that report flagged a
June 2026 FYERS community reply mentioning a beta endpoint. Testing it was the
single most valuable half hour of the night. Without his file the
recommendation in this section would have been to pay a second broker for data
he can already reach.

**What was tested, and what came back:**

| Endpoint | Result |
|---|---|
| `GET /data/history/fno/expired/expiry-dates` | **Works.** Every NIFTY weekly and monthly expiry, listed back to Q1 2019 |
| `GET /data/history/fno/expired/underlying-symbols` | **Works.** Every contract for a given expiry. 454 contracts for 8 Sep 2026; 362 contracts across 181 strikes from 9,000 to 32,000 for 28 Mar 2024 |
| `GET /data/history/fno/expired/historical-data` | **Works.** 1-minute and daily candles for expired option contracts |

Base is `https://api-t1.fyers.in/data`, header
`Authorization: {app_id}:{access_token}`, `version: 3` — the same credentials
the terminal already holds.

**The depth, bisected by hand:**

| Expiry tested | Candles |
|---|---|
| 8 Sep 2026, 27 Mar 2025, 26 Sep 2024, 28 Mar 2024 | **Yes** |
| **29 Feb 2024** | **Yes — the earliest found** |
| 25 Jan 2024, 28 Dec 2023, 30 Nov 2023, 26 Oct 2023, 28 Sep 2023, 27 Apr 2023, 25 Jan 2023, 27 Oct 2022, 20 Oct 2022 | No. `s=no_data`, though the contracts are still listed |

**So: roughly two years and seven months of 1-minute expired NIFTY option
history, every strike, every expiry, at zero cost, from the account he already
uses.** That clears his stated minimum of two years. FYERS said in June 2026
that more years were being added, so the floor may move; re-test it rather than
assuming either way.

**What the candles do NOT contain, tested rather than assumed.** Each candle is
six values: timestamp, open, high, low, close, volume. **No open interest, no
implied volatility, no Greeks and no bid or ask.** `greeks=1` and `greeks=0`
returned byte-identical payloads. Do not plan around the Greeks arriving; plan
to compute them, which the recorder already does in `cloud/recorder/bs_math.py`
and which needs only the underlying, and the underlying is also free (§2.15.3).

**One thing to be careful about, and it is not optional.** The installed
`fyers-apiv3` is **3.1.5**; these methods appear in **3.1.17**, released
2026-09-06. **Do not upgrade the package in the project environment as part of
this work.** That environment is what his execution ticket runs on. The loader
should call the three endpoints directly with `requests`, which is what the
tests above did and what proved they work. Upgrading the SDK is its own change,
on its own day, with the desk re-tested afterwards.

---

#### 2.15.2 He asked whether this is built on NIFTY data or options data. Both.

They are two different problems and they now have two different free answers.

**The underlying**, from the ordinary FYERS history API, tested:

| Resolution | Depth proved | Per request |
|---|---|---|
| 1 minute | **January 2018 onwards.** 22,401 candles for Q1 2018; 2017 returns `no_data` | About 100 days |
| Daily | **At least 2010.** 252 candles for 2010 | About 366 days |

That is the spine. Every entry, exit and day in between can be placed against a
real NIFTY level at the minute he would have been at the screen. It also gives
realised volatility, the average daily move rule 2 needs, and the 20- and 50-day
ranges Home already shows.

**The options**, from the expired-contracts endpoint in §2.15.1, back to
February 2024. Together they are the whole data set, for nothing.

---

#### 2.15.3 What was ruled out, and why

**The ordinary FYERS history API cannot return an expired option.** A listed
contract returns full 1-minute candles: 1,539 for `NSE:NIFTY2691523300CE` over
five days. An expired one returns `Invalid symbol provided`. Tested on
`NSE:NIFTY2690823850PE`, which expired the day before the test, with its name
taken verbatim from the NSE bhavcopy so the name could not be at fault. **This
is why the expired-contracts endpoint in §2.15.1 is a separate route and not a
parameter on the old one.** Anyone testing the old endpoint concludes FYERS has
no historical options. That conclusion is now wrong.

**Zerodha cannot, and a family account does not help.** Once an option expires
its instrument token leaves `kite.instruments()`, and `historical_data()` needs
that token. Zerodha's own support article and developer forum say expired option
history is not available and there are no plans to add it.

**Global Datafeeds keeps one month** of options history, by their own page.

**TrueData sells backfill in days, not years:** tick-data upgrades of 5, 10 and
20 days at ₹299, ₹699 and ₹999 a month, on top of a Velocity subscription of
₹1,440 to ₹2,796 a month.

**Stolo, NiftyTrader, TradingTick, StockMojo and OptionBacktesting are viewers,
not data.** Several hold years of history, but as screens and one-date-at-a-time
downloads. There is no bulk export. Loading two years from a web form is not a
plan.

**Kaggle and GitHub datasets are refused on principle.** Provenance cannot be
checked and gaps cannot be checked. This is the terminal he intends to trade
real money through.

---

#### 2.15.4 The paid fallback, if and only if it is ever needed

**Dhan, and only for one thing: minute data before February 2024.** DhanHQ's
`POST /charts/rollingoption` gives, by their documentation, five years of
expired options at minute level including implied volatility, open interest and
the spot, up to 30 days a call, at **₹499 a month plus tax, about ₹589**, free
in any month he has traded 25 times in the previous 30 days.

**Its limitation is the reason it is the fallback and not the recommendation:
index coverage is ATM+10 to ATM−10.** At 50-point strikes that is about ±500
points. FYERS returns every strike, 181 of them on the expiry tested. For a
condor whose wings sit outside that band, or a leg that drifts as the index
moves over three weeks, Dhan's window may not contain the contract at all.

**So the honest ordering is: FYERS first, free and complete from February 2024;
NSE end-of-day free for everything older; Dhan only if a specific question needs
minute data from 2022 or 2023 and the answer is worth ₹589.** Opening a Dhan
account is his to do, not mine, and their public API documentation states no
licence or redistribution terms at all, so he should read the agreement before
any load.

Upstox is a second fallback with the same shape: 1-minute expired option candles
on the Upstox Plus plan, which Upstox says can be activated free for now, but
their own community answer states six months of retention with an intention to
reach two years, and that answer predates this document.

---

#### 2.15.5 The free end-of-day spine, which already works in this repository

**NSE's UDiFF bhavcopy is free, official, and goes back years.**
`src/swayam/bhavcopy.py` already downloads and parses it and `data/bhavcopy/`
already holds 22 days. One day is about 31,500 rows and 5.7 MB across every F&O
contract, of which roughly 1,600 are NIFTY options.

Its columns are, not by coincidence, the ones the recorder writes as NULL:
`OpnPric`, `HghPric`, `LwPric`, `ClsPric`, `PrvsClsgPric`, `SttlmPric`,
`UndrlygPric`, `OpnIntrst`, `ChngInOpnIntrst`, `TtlTradgVol`, `TtlTrfVal`,
`XpryDt`, `StrkPric`, `OptnTp`, `NewBrdLotQty`.

`UndrlygPric` is the real underlying, `SttlmPric` the official settlement, and
`NewBrdLotQty` the lot size **on that day** — which matters, because the lot was
75 before January 2026 and is 65 now, and a backtest of his 2022 trades using 65
is wrong by fifteen per cent.

**This is what covers his 21 historical trades.** They ran October 2022 to April
2023, which is outside the FYERS minute window. Bhavcopy gives every one of those
contracts a daily open, high, low, close, settlement, open interest and
underlying, for nothing. His own sheet already records what he actually paid and
received, so the acceptance test in `ROADMAP.md` §3 milestone 2 does not need
minute data to run: it needs the daily path, the charges, and his recorded fills.

---

#### 2.15.6 The shape it loads into

Four tables, all `swayam_*`, in the existing Supabase project. **Nothing here
touches `swayam_positions` or anything the trading desk reads.**

**`swayam_underlying_bars`** — the NIFTY spine, FYERS, free.

| Column | Type | Note |
|---|---|---|
| `symbol` | text | `NSE:NIFTY50-INDEX` |
| `bar_start_utc` | timestamptz | |
| `resolution` | text | `1m` or `1d` |
| `open`, `high`, `low`, `close` | numeric | |
| `volume` | bigint | Zero on the index; kept for futures later |
| | | Primary key `(symbol, resolution, bar_start_utc)` |

**`swayam_options_contracts`** — the contract master, from the expired-symbols
endpoint. Without it nothing else can be looked up.

| Column | Type | Note |
|---|---|---|
| `symbol` | text | `NSE:NIFTY24MAR22300CE` |
| `underlying`, `expiry_date`, `strike`, `option_type` | | |
| `expiry_kind` | text | `W` or `M` |
| `lot_size` | integer | From the bhavcopy for that date. **Never a constant** |
| | | Primary key `(symbol)` |

**`swayam_options_eod`** — one row per contract per day, NSE bhavcopy.

| Column | Type | Note |
|---|---|---|
| `trade_date`, `symbol` | | Primary key |
| `open`, `high`, `low`, `close`, `prev_close`, `settle_price` | numeric | |
| `volume`, `turnover_inr`, `open_interest`, `change_in_oi` | | |
| `underlying_spot` | numeric | `UndrlygPric`, real |
| `source` | text | `nse_bhavcopy` |

**`swayam_options_intraday`** — the minute bars, from FYERS for the past and the
recorder going forward. **Same column names as the recorder's Parquet file,
deliberately**, so both load through one path.

| Column | Type | Note |
|---|---|---|
| `snapshot_time_utc` | timestamptz | The candle's start for history, the snapshot instant for the recorder |
| `trade_date`, `symbol`, `underlying`, `expiry_date`, `strike`, `option_type` | | |
| `open`, `high`, `low`, `close` | numeric | NULL from the recorder, real from FYERS history |
| `bid`, `ask` | numeric | Real from the recorder, NULL from FYERS history |
| `volume` | bigint | |
| `open_interest`, `change_in_oi`, `prev_oi` | bigint | **NULL from FYERS history.** It does not send them |
| `underlying_spot` | numeric | Joined from `swayam_underlying_bars` for history |
| `tte_years`, `iv`, `delta`, `gamma`, `theta`, `vega` | numeric | Computed with the same maths for both sources |
| `source` | text | **`recorder`, `fyers_expired`, `dhan`. Not optional.** Every row says where it came from, so a result can always be traced to its data |
| | | Primary key `(symbol, snapshot_time_utc, source)` |

**Note the honest asymmetry, and write it into the backtester's assumptions.**
The recorder has bid and ask and no open/high/low. FYERS history has
open/high/low and no bid, ask or open interest. `services/fills.py` fills a buy
at the ask and a sell at the bid, and **the historical rows cannot support that
directly.** The backtester must model the spread from the recorder's own
measured spreads, by moneyness and time of day, and label any result that used a
modelled spread as such. This is the single most likely way a backtest of his
flatters itself.

---

#### 2.15.7 How the recorder's own files join it

`scripts/ingest_gcs_to_duckdb.py` already reads the recorder's daily Parquet into
a local DuckDB `options_history`. The loader does the same into Postgres with
`source = 'recorder'`, and the recorder's column names were chosen to match.

The sources overlap by design:

- **February 2024 to now:** FYERS expired history for the minutes, bhavcopy for
  the daily close, settlement, open interest and lot size.
- **Before February 2024:** bhavcopy only, daily. That is his 21 trades.
- **From 10 September 2026 forward:** the recorder, with real bids and asks and
  computed Greeks, for the **afternoon only** until the token gap in §2.10 is
  settled. FYERS expired history fills each morning in afterwards, once that
  day's contracts expire.
- **A cross-check that costs nothing:** on any overlapping day the recorder's
  last snapshot before 15:30 and the bhavcopy close for the same contract should
  agree closely, and so should the FYERS historical candle for that minute.
  **Those three agreeing is the acceptance test for the loader.** Better to find
  a disagreement on a Tuesday than inside a backtest result.

---

#### 2.15.8 THE DATA IS DOWNLOADED AND CHECKED — DONE 2026-09-10, PR #56

**Everything in this section is on disk and verified. Nothing was bought.**

| What | Rows | Span | Size |
|---|---|---|---|
| NIFTY minute bars | 804,379 | 2018-01-01 to 2026-09-09 | 17.5 MB |
| NIFTY daily bars | 4,141 | 2010-01-04 to 2026-09-09 | 0.1 MB |
| NSE daily option rows | 4,569,843 | 2018-01-01 to 2026-09-09 | 73 MB |
| Minute option bars | 59,292,184 | expiries 2024-02-01 to 2026-09-08 | 540 MB |

The last of those took 90 minutes and 8,576 FYERS requests, with **zero
refusals and zero errors**. Files live in `data/history/`, which git ignores.
Rebuild any of it with the three scripts named below.

**THE TWO SOURCES CHECK EACH OTHER, AND THEY AGREE.** FYERS' minute candles and
NSE's official daily file come from different systems and were downloaded
separately. Squashing a day's minutes into one bar reproduces NSE's row across
**167,717 contract-days**: the open agrees 99.20% of the time, the high 98.43%,
the low 97.96%. `scripts/reconcile_option_history.py`.

**THE CLOSE DOES NOT AGREE, AND THAT IS THE MOST IMPORTANT THING WE LEARNED.**
Only 14.94% of closes match. NSE's derivatives closing price is the
volume-weighted average of the last half hour, not a trade. Proved rather than
assumed: computing that half-hour average from our own minute bars cuts the
median gap from ₹2.45 to ₹0.17 and quadruples the exact matches. The same holds
on the index, where the official close and the 15:29 level sit a median of 7.7
points apart.

> **So a backtest may never fill at a daily closing price.** It is a statistic,
> not a price anyone could deal at, and on a four-leg structure the error is
> taken four times. Fills come from the minute bars or, before February 2024,
> from a day's traded range with the limitation stated on the result.

**Other things measured, all of which a backtester must respect:**

- **Only 31% of daily option rows actually traded.** The rest carry an
  exchange-derived close for a contract nobody dealt in. Filling there invents
  liquidity that never existed.
- **The lot size changed four times**: 25, 50 and 75 during 2024; 25, 65 and 75
  in 2025; 65 now; 50 through his 2022-23 era. The legacy file carries none, so
  it is NULL rather than guessed. Using today's 65 on his old trades overstates
  everything by a fifth.
- **642 NIFTY bars sit outside market hours.** Diwali Muhurat evening sessions.
  Real, but not ordinary days.
- **406 NIFTY bars in 2019 and 2021 have a high below their low**, all with zero
  volume. A defect in FYERS' archive. Left exactly as it came; silently
  repairing another system's data is not a habit worth starting.

**The scripts, all read-only against his records:**

| Script | What it does |
|---|---|
| `scripts/load_nifty_history.py` | The chart. `--verify` reports completeness and the close problem |
| `scripts/load_nse_options_eod.py` | Daily options from NSE, both file formats. `--verify` |
| `scripts/load_expired_options.py` | Minute options from FYERS. `--plan` sizes the job first |
| `scripts/reconcile_option_history.py` | The two sources against each other |
| `scripts/check_historical_trades.py` | His 21 trades, and whether the data covers them |
| `scripts/recover_trade_expiries.py` | The expiries his notes never recorded |

**Care that is in the code and should stay there.** Every write is atomic
through a temporary file and a rename. A manifest records each unit as it
completes so a killed run resumes. Bulk downloads refuse to start inside his
window, because they spend the same FYERS budget the desk uses to quote his
legs. And `swayam/research/contracts.py` parses a contract name against an
expiry that is already known, after a lazy pattern read `NIFTY2690823450CE` as
strike 823,450, chose sixty-two contracts nobody had traded, and reported a
clean zero rows with no error at all.

---

#### 2.15.9 HIS 21 TRADES: for reflection ONLY, not for testing

> **He ruled these out as test material on 2026-09-10.** See §2.16.0.
> The work below stands and is worth having, because understanding how he
> traded is worth having. It is NOT the acceptance test and must not be
> resurrected as one.
>
> **`Swing Trades Journal.xlsx` was found on 2026-09-10**, in his own
> archive at `E:\Project E\Trading\Bazaar\Trading Journal\`. Earlier
> notes here said it was lost. It is not.

**The data covers them.** Every strike in all 21 trades is present on the day he
opened it.

**The expiries his notes never recorded are recovered, 69 of 72 legs, 96%.**
Not one note carries an expiry, which for a calendar is the whole trade:
Trade-07 sells the 18700 call and buys the 18700 call, separated only by a date
nobody wrote down. The premium he recorded is the evidence. Each leg is matched
against every expiry's traded range at that strike on that day, and where more
than one fits, the structure settles it. Trade-07 resolves to: sells 2023-01-12,
buys 2023-01-25. **All ten calendars resolve.**

**THIRTEEN OF THE 21 NOTES WOULD MISLEAD A BACKTESTER.** Reported, never
corrected; they are his records.

- Seven have an exit date contradicting their own last booked order.
- Trade-07's exit date is eleven months BEFORE its entry date.
- Trade-08's booked orders are dated October for a trade that ran in January.
- Trade-16 has the literal word `None` where its exit prices belong.
- Trade-21 has no opening legs at all.
- Five have no exit date.

Two legs match no expiry at any price, and both look like the note rather than
the data. Trade-09 records selling the 18100 call at ₹29.27 when every listed
expiry traded between ₹64 and ₹559. Trade-15 records selling the 17450 call at
₹34.65 when the range was ₹136 to ₹682.

**The source is `Swing Trades Journal.xlsx`, extracted by Antigravity. It is NOT
in the vault.** Without it the notes cannot be re-derived. Ask him where it is.

**What his own record actually says**, computed from those notes:

| | |
|---|---|
| 21 trades, 13 wins | 61.9%, net **+₹73,676** |
| Average win / loss | ₹9,192 / ₹5,728 |
| Median win / loss | ₹8,169 / ₹3,700 |
| Winners held / losers held | median 7 days / median 6.5 days |

**He did not cut losses faster than he ran winners.** He held both about the same
time. And three of eight losers broke the stop written down before entry:
Trade-07 planned ₹7,000 and lost ₹21,000; Trade-10 planned ₹5,250 and lost
₹7,239; Trade-21 planned ₹4,750 and lost ₹5,800. **Those three overshoots cost
₹17,039, which is 23% of everything he made in the era.**

> That is why the backtester's first measure is not profit. See §2.16.

---

#### 2.15.10 Sources

- **Tested directly against his live FYERS account, 2026-09-09 night:** the
  expired-contract endpoints and their depth, the ordinary history API's refusal
  of expired symbols, and the NIFTY index depth. The probes were scratch scripts
  and are not committed; they are plain `requests` calls to the three paths in
  §2.15.1.
- His own research, which found the FYERS beta and prompted the test:
  `docs/Independent reports/Swayam Capital Historical Options Data Research by Perpexility.md`.
- FYERS official reply confirming the beta and four years:
  `fyers.in/community/t/is-historical-options-oi-data-via-api/22795`.
  Endpoint list read from `fyers-apiv3` 3.1.17 on PyPI, released 2026-09-06.
- Zerodha: `support.zerodha.com/category/trading-and-markets/charts-and-orders/charts/articles/historical-data-for-expired-f-o-contract`
  and `kite.trade/forum/discussion/16179`.
- Dhan: `dhanhq.co/docs/v2/expired-options-data/`; pricing at
  `dhan.co/support/platforms/dhanhq-api/how-does-the-dhanhq-data-api-subscription-work/`.
- Upstox: `upstox.com/developer/api-documentation/get-expired-historical-candle-data/`;
  depth at `community.upstox.com/t/historical-availability-retrieval-limit-per-query-for-expired-options-contract/9245`.
- Global Datafeeds: `globaldatafeeds.in/global-datafeeds-apis/global-datafeeds-apis/introduction/type-of-data-available/`.
- TrueData pricing: `truedata.in/price`.
- NSE UDiFF bhavcopy: implemented in `src/swayam/bhavcopy.py`; columns read off
  `data/bhavcopy/2026-09-01.csv`.

---

### 2.16 THE BACKTESTER. His words. Corrected by him 2026-09-10 night.

**Everything in quotation marks is his. Section 2.16.0 overturns a premise this
document held earlier, so read it before anything else here.**

---

#### WHAT A BACKTEST IS FOR. His sentence, 2026-09-12. Read this before the rest.

> "The backtest's purpose is to find out what the most predictable ways the market
> behaves are and bet on those predictable behaviours instead of copying and pasting
> everything that happened in the past."

**Every design decision in this section answers to that sentence.** A backtest here
is not a reconstruction of the past and it is not accounting. It is a search for
behaviour that repeats, tested under the conditions he faces **now**.

That is why his charges rule follows from it rather than being a separate opinion:
**the market is historical, the cost of doing business is current** (§2.16.9). It is
also why his own trades are experience rather than test material (§2.16.0), and why
a result reports plan-adherence before profit. Anything that drifts towards
replaying history faithfully is drifting away from the question he is asking.

---

#### 2.16.0 CLEAN SLATE, BUT NOT A CLOSED BOOK. His words, refined 2026-09-10.

**This section was written once too absolutely and he corrected it. Read the
whole thing; the nuance is the point.**

**What he ruled out:** his own trades as the material a backtest is built on,
or as the test that decides whether the engine is trusted.

> "I don't want to do backtesting on the trades I did. The trades I did are not
> very well structured, so we can't do backtesting on them, whether swing trades
> or intraday trades... I will do the backtesting on a clean slate. The things in
> my mind will create proper new strategies. We'll give them the names and
> backtest them on the data available."

**What he did NOT rule out:** using his history whenever it is useful.

> "You change it so that my past data can be used whenever and wherever it is
> required, whenever it can be useful, but it cannot be only backtest material.
> My backtest will be a fresh test, a synthetic test. If you have to compare it
> with my past trades, we can use it, because that is for a limited time, or a
> very limited time, and the data is not very well structured. There might be
> flaws."

> "We will create everything on a clean slate, but we will use whatever
> resources we have, whether by my history, by my broker, by market, by API, by
> WebSocket, whatever is usable. We create our own structure out of that, a new
> one."

**And the sentence that settles how to hold both at once:**

> "I'm not going to copy anything, not even from my past. My past is my
> experience, and we should learn from it and use it whenever required. My
> future, I will be writing by my own hand, with your help."

**So the rule is about ROLE, not about permission:**

| His history may be | His history may NOT be |
|---|---|
| Read to understand how he trades and what went wrong | The source a strategy is copied from |
| Compared against, for a limited sanity check, with its flaws stated | The acceptance test that decides the engine is correct |
| Used to reason about size, charges, discipline, holding periods | Treated as clean or reconciled data |
| Quoted back to him in a finding | The reason a new strategy exists |

**Every use of it carries the caveat.** The data is not well structured, 13 of
the 21 swing notes carry errors (§2.15.9), the intraday journal differs from the
broker's own figures by about ₹34,000 across the year, **and his Zerodha history
is gone entirely — he has no record of it any more.** Say so wherever it is used.

**Use every source there is.** His history, the broker, the market, the REST
API, the WebSocket, the recorder, the NSE files. The structure built on top of
them is new, and it is his.

The engine is validated a different way. See §2.16.7.

---

#### 2.16.1 The second correction: he is NOT a time-based trader

> "I'm not looking for a time-based strategy. Time only matters to me because I
> can only trade in the afternoon due to my night shift. For the rest, I am a
> price-action and technical-based trader, mostly a price-action-based trader."

"Enter at 2 pm every day" is the wrong shape. The question is: **when the market
looks like THIS, and he is looking at it in his window, what happens next, and
which structure pays best for it?** A research tool he drives, not a robot.

> "I want to know what kind of price action forms in what kind of market cycle,
> because the market has different cycles... around the afternoon, that is the
> time when the positional trader enters and the intraday trader exits, and what
> kind of formation happens."

---

#### 2.16.2 THE DATA WINDOW: 2022 onwards, and he was firm about it

> "I always wanted to test the last 3 to 4 years of NIFTY data... I don't want to
> test that old data because the market is totally different than what it was
> before Corona and after Corona. I want maybe 22 to 26."

**Default window: 2022-01-01 to now. Every result says so.** Older data exists
because it was free to take, and it is not to be used without him asking.

**Inside his window there are two tiers, and a result must say which it used:**

| Period | What is available |
|---|---|
| 2022 and 2023 | Daily option prices only. Minute prices for the index. |
| Feb 2024 onwards | Minute option prices, every strike, plus everything above. |

**That boundary cannot be bought away.** FYERS is the only source that serves
expired option contracts and its minute history starts in February 2024
(§2.15.1). So a strategy whose entry depends on the minute inside the day can
only be tested on about two and a half years, and one that works off daily
closes can be tested on four and a half. Say which, on every result.

**ONE IMPORTANT THING THE TWO-TIER WARNING DOES NOT APPLY TO. Measured
2026-09-12.** The boundary is about OPTION prices. It is not about the chart.

The NIFTY minute bars are complete across the whole window: 1,163 sessions from
2022-01-03 to 2026-09-09, 375 bars a session, and **his own 14:00 to 15:30 window
is ninety real minutes on every one of those days.** India VIX minute bars go back
to 2018 as well (§2.16.5b).

So everything in the vocabulary and formation work — labelling his cycles, the
weekly, daily, hourly and 15-minute views, what price does in his afternoon — runs
on the **full four and a half years at minute resolution**. Only the moment a leg
has to be priced does the February 2024 tier boundary bite. **He had been
worrying about the wrong boundary**, and the research half of this project is
twice as deep as the pricing half.

---

#### 2.16.3 The four charts he actually reads

| Chart | What he uses it for |
|---|---|
| **Weekly** | The wider view |
| **Daily** | **The most important.** Where the market is heading, and the major support and resistance |
| **Hourly** | The movement, the pattern, direction over a few days, the possible reversal area, the entry area |
| **15-minute** | The intraday trend, and the actual entries |

All four build from the one minute file.

---

#### 2.16.4 His market cycles, roughly, pending their own session

**A sketch, not a specification. He asked for a dedicated session.**

- **Trending**, and within it **aggressive** or **basic**, bullish or bearish.
  "Bearish is mostly aggressive, and mostly short-term." "The Indian market is
  mostly in a bull run on the long-term chart, but in the short term it becomes
  bearish and aggressively bearish."
- **Sideways**: **squeezing**, "which is going to blast someday", or
  **expanding** in both directions.

> "As for the current situation, I can say it is squeezing... We will have to do
> a session to give words to all of this. That will be a particular session."

**That session can be evidence-based.** Once he defines a cycle roughly, label
2022 onwards and count how often each appears, how long each lasts, and what
tended to follow. A definition that catches nothing shows itself before anything
is built on it. **It is the gate to all the rest.**

---

#### 2.16.4a THE VOCABULARY SESSION HAPPENED. 2026-09-12, and it is measured.

**The session §2.16.4 was waiting for. Every indented quotation below is his own
sentence, given 2026-09-12. Everything else is measurement or a question back to
him.** Measured with `scripts/label_market_cycles.py` on the 1,163 NIFTY daily
sessions from 2022-01-03 to 2026-09-09 already on disk.

**HIS DEFINITION OF A SQUEEZE, and it is three things:**

> "the daily range shrinking, so the last five to ten days' high-to-low is
> smaller than the 20-day average; price making no new 10-day high or low,
> staying inside a band; and India VIX low or falling."

> "the first two define a squeeze, the VIX confirms it."

**HIS MINIMUM LENGTH:**

> "A cycle needs at least five trading days, one week, to count. Three sideways
> days inside a two-month uptrend are a pause inside the trend, not a cycle."

Applied as a rule, not as smoothing: a run shorter than five sessions is absorbed
into whichever neighbour is longer, repeatedly, until every surviving stretch is
at least five sessions.

**HIS TIMEFRAME RULE, which turned out to be the most important answer he gave:**

> "each chart has one job: the weekly gives the bias, the daily decides the
> structure, the hourly decides the entry. Weekly up and daily squeezing means a
> range structure leaning bullish, for example a condor with the put side
> closer."

**HIS ORDER OF LABELLING:**

> "Before, from the daily chart, and the entry does not redefine it. But the
> backtester also labels what the cycle turned out to be, so you learn how often
> your pre-entry read was right. Both get recorded."

---

**WHAT THE DEFINITION CATCHES, ON THE DAILY CHART. It is not empty and it is not
everything, which is what a usable definition looks like.**

His "last five to ten days' high-to-low against the 20-day average" has two
honest readings and they are different measurements, so both were run:

- **Reading A, candle size.** The average of each day's own high minus low over
  5 days, against the same average over 20 days.
- **Reading B, territory.** The band the last 10 days traced, highest high minus
  lowest low, against the average of that band over 20 days.

| Cycle | Reading A sessions | Reading A stretches, median length | Reading B sessions | Reading B stretches, median length |
|---|---|---|---|---|
| Squeeze | 408, 35.4% | 35, 11.0 | 445, 38.6% | 36, 10.5 |
| Expanding | 114, 9.9% | 17, 6.0 | 58, 5.0% | 6, 10.0 |
| Trending up | 379, 32.9% | 25, 11.0 | 420, 36.4% | 27, 12.0 |
| Trending down | 252, 21.9% | 23, 10.0 | 230, 19.9% | 21, 10.0 |

**A squeeze lasts about eleven sessions, a little over two weeks, and there were
thirty-five of them in the window.** That sits well inside the days-to-weeks
holding period his record shows, so the cycle he most wants to trade is a cycle
long enough to trade.

**Reading A is the recommendation.** Reading B finds only six expanding stretches
in four and a half years, which is too few to design against; reading A finds
seventeen. **His decision is still open.** §2.16.4b.

**WHAT TENDED TO FOLLOW, reading A, as a share of each cycle's endings:**

| After | What came next |
|---|---|
| Squeeze | Trending up 46%, trending down 40%, expanding 14% |
| Expanding | Squeeze 47%, trending up 41%, trending down 12% |
| Trending up | Squeeze 60%, trending down 24%, expanding 16% |
| Trending down | Squeeze 55%, expanding 36%, trending up 9% |

**The finding that matters, and it is a warning about his own instinct.** A
squeeze broke up 46% of the time and down 40%. **It is a coin toss on direction.**
His own framing is that a squeeze "is going to blast someday", and the data
agrees that it blasts; it gives almost no information about which way. The
forward move confirms it: the median ten-session move after a squeeze ends is
+0.01%, and it was up 51% of the time, across 35 cases. **So a squeeze is a
volatility signal and not a directional one, which is exactly what his own
volatility path in §2.16.5 already says it is.** A directional structure entered
on a squeeze break is a guess; a long-volatility structure is the trade the data
supports.

**The one edge visible in the transition table.** After a trending-down stretch
ends, the median ten-session move is +1.85% and it was up 68% of the time across
22 cases. After trending up ends, the median is −0.66% and up only 48% of 25
cases. Mean reversion after a fall, in a market his own note calls "mostly in a
bull run on the long-term chart". **Twenty-two cases is not a strategy. It is a
reason to look.**

---

**HIS THIRD CONDITION, THE VIX, IS CONFIRMED — BUT ONLY WHEN MEASURED THE WAY HE
SAID TO MEASURE IT.** All 1,163 sessions matched against NSE's official daily
India VIX, downloaded 2026-09-12.

Tested first as an absolute level, it looked worthless. A squeeze's median VIX is
13.84 against a period median of 13.97, and the VIX sat below that period median
on only 51% of squeeze sessions. A coin toss.

Tested as he actually framed it in §2.16.5b, "two relative measures, never a fixed
number", it holds clearly:

| Cycle | Median VIX | VIX falling over 5 days | VIX below its 20-day average | Below its 60-day average |
|---|---|---|---|---|
| Squeeze | 13.84 | 63% | **68%** | 64% |
| Expanding | 14.41 | 59% | 45% | 46% |
| Trending up | 13.64 | 55% | 66% | 68% |
| Trending down | 14.84 | 30% | 23% | 41% |
| **All sessions** | **13.97** | **52%** | **55%** | **58%** |

**So "India VIX low or falling" is real during his squeezes**: falling 63% of the
time against a 52% baseline, and below its own 20-day average 68% of the time
against 55%. Expanding is the mirror, sitting below its average only 45% of the
time. **His instinct that the measure had to be relative rather than a number like
fifteen was right, and the first measurement only made it look dead because it was
done the wrong way. Reported because he asked to be told when a definition does
not hold; here it does.**

**And his ordering was right too.** Trending up also shows a low, falling VIX, 66%
below its 20-day average. **So the VIX on its own cannot tell a squeeze from an
uptrend.** It is the two price conditions that separate them, which is exactly why
he said the first two define a squeeze and the VIX only confirms it.

---

**HIS OWN READ OF THE PRESENT DISAGREED WITH THE DAILY CHART, AND HE WAS RIGHT.**

On 2026-09-10 he said: "As for the current situation, I can say it is squeezing."
Both readings label the most recent stretch, 2026-08-27 to 2026-09-09, as
**trending down**, not squeezing.

**He was reading the weekly, and on the weekly his own test passes convincingly.**
Running the same squeeze test on weekly bars: the contraction ratio has been
between 0.62 and 0.84 for **fourteen consecutive weeks**, and price stayed inside
its 10-week band in 11 of those 14 weeks. That is a squeeze by his own
definition, on the chart he says gives the bias.

Meanwhile the daily has broken down out of it. As at 2026-09-09 the close sits at
the very bottom of its 60-session band, 23,432 against a band of 23,432 to
24,774, and the net move is −3.21% over ten sessions and −4.11% over twenty.

| View | Band | Where the close sits |
|---|---|---|
| Last 60 sessions | 23,432 to 24,774, 5.7% wide | 0% of the band, at the low |
| Last 120 sessions | 22,183 to 24,774, 11.7% wide | 48% of the band |
| Last 250 sessions | 22,183 to 26,373, 18.9% wide | 30% of the band |

**So this was a timeframe mismatch, not a bad definition, and it proves his own
answer about the three charts.** A fourteen-week weekly squeeze is resolving
downward through the daily chart right now. **That is the live example of
"squeezing, which is going to blast someday" actually blasting**, and it is
happening while he reads this.

**THE CONSEQUENCE FOR THE BUILD, and it is a real change.** A cycle is not one
label a day. **It is one label per timeframe per day**, weekly, daily and hourly,
exactly as his three-charts answer says. The labeller built for this session
labels the daily only, which is why it contradicted him. All four of his charts
build from the one minute file already on disk (§2.16.3), so nothing needs
buying; the work is to run the same test at each resolution and record three
labels. **Until that exists, no result may say "the cycle was X" without saying
which chart it read.**

---

#### 2.16.4b WHAT IS STILL HIS TO DECIDE ON THE VOCABULARY

**Four answers of his are not yet usable as rules. Nothing should be built on the
cycle vocabulary until these four are settled, because each one changes the
labelling.**

1. **Which reading of "high-to-low against the 20-day average" is his eye doing**,
   A or B above. Recommendation: A, because B finds too few expanding stretches
   to design against.
2. **Where aggressive ends and basic begins.** He gave the words and no
   threshold. Trend strength, measured as the net 10-day move divided by ten
   normal days' range, sits at 0.154 at the 25th percentile of his trending days,
   0.258 at the median, 0.397 at the 75th and 0.502 at the 90th. A value of 1.00
   would mean every day moved its full range the same way. **No split has been
   adopted; the script marks the median as a placeholder and says so.**
3. **His formations.** He named five to start from, taken from his own Setup
   Rules: a support or resistance test, a trend-line touch, a breakout, a
   reversal, and a contraction. His words: "Add the ones you actually see. It
   must not bring a textbook." **The additions are still owed by him.**
4. **Whether a squeeze may carry a directional lean at all.** His own answer says
   weekly up plus daily squeezing means "a condor with the put side closer". The
   measurement above says a squeeze break is a coin toss on direction. **Those
   two can both be true, because the lean comes from the weekly and not from the
   squeeze, but he should say so deliberately rather than have it inferred.**

---

#### 2.16.5 The structure follows from TWO questions, not one

| Path | Trades | What decides it |
|---|---|---|
| **Directional** | bull call spread, bull or bear condor, bear put spread | "I make the view: the setup, the direction of the market, and the formations" |
| **Volatility** | iron condor, iron butterfly, calendar | "It is not about the direction. It is about the volatility" |

His stated volatility rules:

- **An event is coming and volatility can increase → calendar.**
- **Volatility is too high now and going to squeeze, market mostly sideways →
  iron condor or butterfly.**

> "But again, these are the past things. I will start a clean slate after
> brainstorming and understanding the structure."

Starting hypotheses, not fixed rules.

**He also has four strategies he wrote years ago with rules**, at
`E:\Project E\Trading\Bazaar\60 Day Challange\Strategies`: 03 PM Candle
Breakout, 5 EMA Buying, 5 EMA Selling, Morning Conviction. **Read them for how
he thinks about writing a rule, not as strategies to test.** Most are intraday
and morning-based, which no longer fits his life.

---

#### 2.16.5a HOW A STRATEGY IS WRITTEN DOWN. His own shape, from 2023.

**Found by reading the four strategy documents on 2026-09-11, rather than by
asking him.** All four use the same six slots, and the shape is his:

| Slot | What it holds | His example |
|---|---|---|
| 1 Signal | The candle or price condition | "15-minute candle closing above 5 EMA without touching it" |
| 2 Previous move | What the market had been doing before | "There must be trending down move min 70 to 100 Points" |
| 3 Signal location | Where on the chart, with a tolerance | "near to important Support or round number (MAX 10-15 Points)" |
| 4 Entry candle | The trigger, with a time window | "Next 15 candles touching the 5 EMA and trading above the high of Signal Candle" |
| 5 Stop | Structural, or a points cap, whichever is tighter | "Low of the Signal Candle OR 30 Points whichever is lower" |
| 6 Target | Staged: first, second, final | "1st 1:2 or nearest Resistance; 2nd 1:3 or major Resistance" |

**Slot 2 is his market-cycle field, three years early.** He was already recording
the prior regime as a precondition for entry in January 2023. **Recommendation,
and it is a recommendation rather than a decision: keep his six slots as the
format a new strategy is written in, and let the cycle vocabulary of §2.16.4a
fill slot 2.** He never has to learn a new shape, and every strategy then carries
its own regime precondition by construction.

His `T & C 60 Days Challange.docx` from the same folder carries the sentence this
whole backtester is built around: **"This is competition of RULES not
profitability."** That is why a result reports plan-adherence before profit.

---

#### 2.16.5b HOW VOLATILITY IS MEASURED. His answers, 2026-09-12.

> "Two relative measures, never a fixed number: India VIX against its own 20-day
> and 60-day average, and implied volatility against realised. High means above
> the 60-day average and implied above realised. Fifteen is a marker, not a rule."

> "Both, with different jobs. VIX names the regime. The at-the-money straddle
> price as a share of spot is what you are actually paid, so the engine prices
> with the chain's implied volatility and labels with VIX."

**So: VIX labels, the chain prices.** No fixed threshold anywhere. "High" is
above the 60-day average with implied above realised, and both halves must hold.

**THE DATA EXISTS AND IT IS FREE. Measured against his live account 2026-09-11.**

| Source | What it gives | Depth proved |
|---|---|---|
| FYERS `NSE:INDIAVIX-INDEX`, ordinary history API | Minute and daily open, high, low, close | Minute from 2018; daily from at least 2010; 2016 minute returns nothing |
| NSE `ind_close_all_DDMMYYYY.csv` | The official daily India VIX open, high, low, close | One request a trading day, back through the window |

**He approved taking both and making them agree before either is used**, which is
the discipline that caught the closing-price problem in the options data. His
words: "yes to its recommendation: take NSE's own India VIX file so the two
sources can be made to agree first." `scripts/load_india_vix.py` does both and
carries a `--reconcile` mode that reports and never repairs.

**The trading days for the NSE download are derived from the NIFTY daily bars
already on disk**, so no request is spent on a weekend or a holiday, and a
holiday can never be mistaken for a download failure.

---

#### 2.16.5c WHAT THE ENGINE IS GIVEN, AND WHAT COUNTS AS A PASS. His answers, 2026-09-12.

**Capital and sizing, in his words:**

> "Starts with 5 lakh and sure increases 5% Of margin or or 50% of total profit
> earned after every 5 of continuous Win/profit."

> "As per the margin available, 5 lakh, and as per we are compounding."

**What is settled: the test starts at ₹5,00,000 and it compounds.** Not his live
balance of about ₹9.71 lakh, which would be wrong at the start of a four-year
test.

**⚠️ WHAT IS NOT YET USABLE AS A RULE, and it must be settled before any result is
believed.** His sizing sentence was spoken and reads two ways, and the two give
materially different equity curves:

- **"5% of margin or 50% of total profit earned"** — is the increase the greater
  of the two, the lesser, or his choice each time?
- **"after every 5 of continuous Win/profit"** — five consecutive winning trades,
  or five profitable months, or a cumulative profit milestone?
- **And there is no symmetric rule for losing.** A ladder that only ever goes up
  is how a backtest flatters itself. His own record says his damage came from one
  badly managed session every month or two, not from a bad strategy, so a
  step-down rule matters more to him than the step-up.

**His pass criteria, and all four must hold:**

> "net profit after charges must be more than twice the charges paid, the worst
> drawdown stays inside ten percent of the test capital; at least thirty trades
> in the window; and it still passes on the held-back data it was not designed on.
> All four, or no pass."

**This is a good gate and it is his own.** Note that the first criterion is his
transaction-cost rule restated: FY 2025-26 was gross +₹6,109 against charges of
₹92,408, and that is what the rule exists to prevent. Thirty trades against a
window holding about 35 squeeze stretches and 48 trending stretches is reachable
but not generous, which is itself a finding: **a strategy that only fires in one
cycle may not reach thirty trades in four and a half years.**

**How many strategies run at once, in his words:**

> "Two: one directional, one volatility, two paths. Never more, because your
> window is sixty to ninety minutes and your failure pattern was one badly
> managed session, not a bad strategy."

---

#### 2.16.6 Adjustments, which is where his money actually went

> "Adjustment mostly means we have to make sure what the premium left is in any
> leg. If there is not much premium left in any leg, then we must adjust them to
> control the risk. If we reach a place where we can 100% hedge our position,
> these are the adjustments. I would not like to make many adjustments, but
> adjustments would be as per the market scenario changes."

Two triggers, both measurable:

1. **Premium exhaustion.** A leg sold at ₹40 now worth ₹4 has given 90% of what
   it will ever give and carries risk for nothing. The right threshold is a
   number the data can find.
2. **A fully hedged position becomes reachable.**

One condition: **the scenario changed** — sideways becoming trending, squeezing,
volatility rising or crashing. Depends on §2.16.4 existing first.

**THE EXIT, HIS ANSWERS OF 2026-09-12.** This was the single biggest risk to the
whole backtest, because every one of his four written strategies ends with an
exit no engine can test: "Target: momentum, exit as soon as momentum seems
fading", and "Until the momentum breaks by opposite Color Candle". Testing that
would mean testing a guess at his judgement rather than his strategy.

**He refused to pick one, which is the right answer.** His words:

> "Give it candidates to test rather than one answer: no new high or low for
> three hourly bars; candle bodies shrinking with wicks growing against the move;
> the move stalling at a prior level; and for options, the short leg's premium no
> longer decaying. It tests which of these would have matched your real exits."

**So momentum fading is four testable candidates, not one rule**, and the engine
reports which one his instinct has been approximating. That turns his discretion
from an obstacle into a finding about himself.

**The holding window, and he corrected the record:**

> "That was what happened, not a decision."

His median seven days on winners and six and a half on losers was an outcome, not
a plan. **The rule he set instead:** every structure declares its maximum holding
window at entry, and **a calendar exits the session before the near expiry,
Monday for a Tuesday expiry, or the Friday before if already well in profit or
already in a loss.** That is the practice that also happens to avoid the margin
cliff on expiry day, which CLAUDE.md records and the terminal does not model.

**⚠️ One thing in his exit answer is not yet measurable and he should know.**
"The short leg's premium no longer decaying" needs a threshold, and §2.16.6 above
already says the same about premium exhaustion: "A leg sold at ₹40 now worth ₹4
has given 90% of what it will ever give." **Neither number is his yet.** The data
can propose one; he has to accept it.

**Test the un-adjusted structure first**, or a good adjustment rule hides a bad
entry and neither can be seen.

---

#### 2.16.7 HOW THE ENGINE IS VALIDATED, since his trades are not the test

**Two different questions, and conflating them is how a backtest lies.**

**Question one: is the engine correct?** Answered mechanically, not against any
trade of his.

1. **Pricing.** Build a known structure on a known past day and check every leg
   against the raw rows it came from. The rows are on disk and can be read.
2. **Charges.** Against `services/charges.py`, the only correct charge model in
   the repository, versioned by effective date and computed in `Decimal`.
3. **Fills.** Against the same rules `services/fills.py` uses on the live desk:
   a buy pays the ask, a sell gets the bid, a limit fills at his price or better.
   For history the spread is MODELLED, and every result says so.
4. **A synthetic trade with an outcome known in advance comes back with that
   outcome**, including a leg squared off alone and a structure adjusted mid-life.
5. **The two sources still agree.** `scripts/reconcile_option_history.py` is the
   standing check: FYERS minute candles and NSE's daily file reproduce each
   other's open, high and low on 98 to 99% of contract-days.

**Question two: does a strategy have an edge?** Answered by holding back data he
did not use when designing it, and by walking forward. Never by the same data
twice.

---

#### 2.16.8 PROPOSED REPLACEMENT FOR `ROADMAP.md` §3 — APPROVED AND APPLIED 2026-09-10 night

**He said yes to both on 2026-09-10 at the close of the day: this replacement,
and the two stale §2 rows. `ROADMAP.md` now carries both, and the vault mirror
was re-copied.** The proposal is kept below as the record of what was asked.


`ROADMAP.md` §3 milestone 2 currently reads that the backtester "must reproduce
what those trades actually did before it is trusted on anything", meaning his 21
historical swing trades. **He rejected that on 2026-09-10.** The roadmap may not
be edited without his approval, so it still says it. **Ask him.**

Proposed replacement for milestone 2:

> 2. **Data loaded** and checked against itself. Two independent sources, FYERS'
>    minute candles and NSE's official daily file, must reproduce each other
>    before either is trusted. The backtester is validated mechanically, on
>    pricing, charges, fills and a synthetic trade with a known outcome, NOT
>    against his own past trades. His trade history is for reflection and
>    knowledge; it was not structured for testing and he has said so.

And a note added to milestone 1: **the window is 2022 onwards**, because the
market before and after Corona are different markets.

---

#### 2.16.9 THE LIBRARY NOTE, ANSWERED. 2026-09-12 night.

**The AI partner chat sent seven backtesting points raised by his second research
pass, and asked which were already covered, which are adopted, and which
rejected. Answered below, each one measured against his own data or against the
running code rather than against either research report.**

The second pass is the more careful of the two and **it is right about the things
that matter.** Where it corrected the first pass on Indian contract rules, his own
downloaded files agree with it.

---

##### HIS RULE ON CHARGES, WHICH SETTLES POINT 1 AND OVERTURNS WHAT THIS SECTION FIRST SAID. 2026-09-12 night.

**This section first reported that the charge engine cannot cost a trade between
1 April 2023 and 31 March 2026, and called that a blocker on the backtester. He
corrected it, and he is right. It is not a blocker, because the backtester should
never ask for a historical charge in the first place.**

> "It doesn't really matter what the charges were in 2023, 2024, or 2025. All the
> backtests must follow the current year's charges. The charges might be less than
> that time. What matters is what the charges are today in the backtest. Market
> moves matter in the past, but the charges should be current. Only then will I get
> the real picture."

> "The backtest's purpose is to find out what the most predictable ways the market
> behaves are and bet on those predictable behaviours instead of copying and
> pasting everything that happened in the past."

**THE PRINCIPLE, AND IT DRAWS A LINE THROUGH THE WHOLE ENGINE. The market is
historical. The cost of doing business is current.**

A backtest is not accounting for a trade he might have made in 2023. It asks a
question about today: **if this market behaviour repeats, do I make money on it
now, paying what I actually pay now?** Costing an old structure at old rates
answers a question nobody is asking, and it would pass a strategy on charges he
will never again enjoy.

**What that settles, concretely:**

| Follows the trade's own date | Follows TODAY |
|---|---|
| Every price, high, low and close | Brokerage, STT, exchange transaction charge, clearing, SEBI fee, stamp duty, GST |
| Which strikes existed and which actually traded | The lot size, so a structure is sized the way he would size it now |
| The contract's real expiry date, holiday shifts included | Margin rules, including the calendar expiry-day rule |
| Whether the market was open at all | |

**So the engine calls `charges.py` with today's date, never the trade's date**, and
every result says so, in the same breath as it names its data tier. A reader must
never mistake a backtest for historical accounting.

**Two consequences worth stating because they are both in his favour.**

1. **This makes the test harder to pass, not easier.** Today's charges are the
   highest they have been in his window, and STT on the sell side rose again on
   1 April 2026. Applying them to older data is the conservative direction.
2. **It closes the 2022 and 2023 lot-size gap as well**, by exactly the same logic.
   That value exists in no file he holds, and under this rule it is not wanted:
   a structure is sized at today's 65 because 65 is what he would trade now.

**What `services/charges.py` still needs: nothing.** Its current schedule is
`fyers-standard-2026-04`, sourced from "FYERS charges list, read 2026-09-08" and
cross-checked against Zerodha's published charges. That is the schedule the
backtester uses for every trade at every date. The 2022-04 schedule stays where it
is and keeps its own separate job, costing his own historical records when he
reflects on them, which is not backtesting.

**And it takes the Library off the backtester's critical path.** The earlier claim
that it was on it was wrong and depended on the mistake above.

---

##### THE SEVEN POINTS

**1. Point-in-time contract rules. PARTLY COVERED, and the gaps are now measured.**

Settled from NSE's own daily files already on disk, which neither research pass
could do:

| | What his own data says |
|---|---|
| **Expiry weekday** | Thursday every year 2018 to 2024. **Last Thursday weekly expiry 2025-08-28, first Tuesday 2025-09-02.** 2026 is Tuesday. The second pass's date of 1 September 2025 is correct |
| **Lot size** | 50 until 2024-04-25, then 25 from 2024-04-26, then 75 appearing from 2024-11-22, 75 through 2025, **65 first appearing 2025-10-29** and the only lot from 2026-01-01 |
| **Holiday-shifted expiries** | Real and already visible: a handful of Wednesday expiries every year to 2024 and Monday expiries in 2026 |

**So CLAUDE.md and the second pass were both half right about the lot**, and the
data reconciles them: 65 applied to new contracts from late October 2025 and became
the only live lot in January 2026. **CLAUDE.md's sentence "cut from 75 in January
2026" is imprecise and should say October 2025 for new contracts, January 2026 in
force.** Not edited here; that file belongs to the main chat.

**Three findings that reduce the work rather than add to it:**

- **Expiry weekday needs no change log at all.** The backtester never computes
  which Thursday or Tuesday a contract expired on. Every contract in the data
  carries its own real `expiry_date`, holiday shifts included. **A dated expiry
  rule would be a second source of truth and a chance to be wrong.**
- **Holidays 2022 to 2025 are not needed either**, which answers point 6. Sessions
  are derived from the NIFTY daily bars, so a day either has a bar or was not a
  session, and expiry shifts are already in the expiry dates. `nse_holidays_2026.json`
  serves the live recorder, which is a different job.
- **Lot size is covered from 2024 onwards by the data itself**, the NSE
  `lot_size` column.

**THE LOT SIZE NEEDS NO HISTORY AT ALL, by his charges rule above.** The measured
history is kept because it is true and because it matters when reading his own 2022
records, but **a backtest sizes every structure at today's 65**, because 65 is what
he would trade now and the backtest is a question about now. The legacy file's NULL
lot column stops being a gap the moment that is settled.

**One live trap remains and it is worth naming.** `services/contract_master.py`
resolves the lot from the **live** FYERS contract master, which does not list
expired contracts, and `services/margin.py` calls `get_lot_size(underlying,
expiry)`. For a past expiry that call cannot answer honestly. **Under his rule the
backtester wants today's lot anyway, so the fix is to ask for today's lot
explicitly rather than to ask about a 2022 expiry and hope.** Asking about a dead
expiry is how a silent wrong answer gets in.

**2. Execution quality: whether the leg was tradeable and whether the price was
stale. ADOPTED, and half of it is already measured.**

§2.16.7 already fills from minute bars, never a daily close, and labels a modelled
spread as modelled. The second pass's two additions are accepted as requirements:

- **Was the strike tradeable at the decision minute.** Already measured at daily
  resolution for the older tier: in 2022 and 2023 an option traded on 81% of
  contract-days within 1% of spot, 59% at 3 to 5% away, and 37% beyond 8%. So a
  condor's far wings in the older tier are frequently a price nobody dealt at.
  **The rule adopted: a leg whose contract shows no trade in the relevant bar may
  not be filled.**
- **Was the last traded price stale.** Adopted as a labelled field rather than a
  silent filter, and it is only answerable at minute resolution, so it is another
  thing that separates the pre-February-2024 tier from the rest.

**3. A four-level approval standard. ADOPTED, and it is stricter than §2.16.7.**

§2.16.7 already has held-out data and walk-forward. **It does not have the two
parts that give the standard its teeth, and both are adopted:**

- **The test sample is used ONCE, after the rule is frozen.** A second look at it
  turns it into development data. This has to be enforced by record, not by
  intention, which is why point 4 matters.
- **Signals recorded before outcomes are known** in the paper stage.

**4. An experiment register, including the failed trials. ADOPTED. It was not in
§2.16 and its absence was a real hole.**

Without it, "it still passes on held-out data" means nothing, because nobody can
tell whether it is the first rule tried or the fortieth. **Every parameter
combination tried is recorded with its result, before the next one is tried, and a
final result reports how many combinations preceded it.** This is the mechanical
counterpart to his own sentence "This is competition of RULES not profitability".

**5. Event periods tested separately. ADOPTED with one change of emphasis.**

RBI, Budget, elections, gap days and volatility spikes, yes. **But the more useful
cut for him is his own cycle vocabulary from §2.16.4a**, because that is the
language he actually thinks in and it is now measured. Events are a second cut, not
the first one. Both are cheap once the labels exist.

**6. Holiday-adjusted expiries and settlement. ANSWERED ABOVE, and no work is
needed for 2022 to 2025.** See point 1.

**7. Extra report fields. ADOPTED, appended to his order, never in front of it.**

His order stands exactly as §2.16 has it: plan-adherence first, then charges, then
the spread and its label, then the data tier, then profit. **Added after those:
median trade, drawdown duration, tail loss, and cost as a share of gross profit.**

**The last of those is the one that matters most to him and it should be prominent
within the charges block, not at the end.** His FY 2025-26 was gross +₹6,109
against charges of ₹92,408, and his three paper trades on 2026-09-10 were gross
+₹195 against charges of ₹585. **Cost as a share of gross is the number that
describes his last two years.**

---

##### WHAT THIS CHAT ASKS FOR IN RETURN

**(a) What is needed for strategy building and is NOT on the fetch list.** In
priority order, most of it dull and none of it a book:

Checked against `docs/LIBRARY_DOWNLOAD_PROMPT.md` as it stands after PR #96, and
referred to by its own item numbers so the next download prompt can absorb this
directly.

**Shortened on 2026-09-12 night by his charges rule above.** Two of the six
requests first written here were for historical STT rates and historical lot-size
circulars. **Both are withdrawn: the backtester uses today's figures, so it never
needs either.** What is left is four documents, and every one of them is about
something CURRENT that the engine relies on and nobody here has read.

1. **NSE's India VIX methodology document**, from `nseindia.com`. The whole
   volatility path of §2.16.5b labels regimes with VIX and nobody in this project
   has read how the number is computed. **A measure used as a regime label should be
   understood by whoever labels with it.** This is the one I would fetch first.
2. **NSE's own note on how the derivatives closing price is computed.** It was
   proved empirically to be a weighted average of the last half hour (§2.15.8), and
   that proof is what forbids a backtest from ever filling at a daily close. **A
   primary source turns our measurement into a citation**, and that rule is load
   bearing for every result the engine will produce.
3. **The current SEBI and NSE margin framework for index option spreads**, and
   specifically the rule that a calendar gets no margin benefit on the day its near
   leg expires. Margin is a cost of doing business, so by his own rule the
   **current** framework is the one that matters, not the one in force in 2022. Ten
   of his twenty-one historical trades were calendars, the terminal does not model
   this, and CLAUDE.md already says he must be told before his first one.
4. **The current NSE contract specification for NIFTY options**, as one file:
   expiry schedule, strike intervals, the strike band actually listed around spot,
   and settlement. The engine has to know which strikes it may legitimately build a
   structure from **today**, and today's specification is the answer under his rule.

**Not wanted, and the reason is his own:** more strategy literature. §2.16.0 settles
that strategies come out of his head. A library of setups would quietly become the
thing a strategy gets copied from.

**(b) Does this chat want its own research pass? Yes, on exactly one thing.**

**How Indian index options were actually filled, in size, at the minute, from 2022
to now.** Not option theory. The single largest unquantified error in any result
this engine will produce is the modelled spread before the recorder existed
(§2.15.6 names it as the most likely way a backtest of his flatters itself), and
the honest position today is that nobody knows how wrong it is. Worth two tools:
whether any free or cheap source carries historical bid and ask or even a spread
statistic for NIFTY options before February 2024; and what published research says
about NIFTY option bid-ask spreads by moneyness and time of day.

**One other pass, lower priority: the deflated Sharpe ratio and probability of
backtest overfitting applied to small samples.** His pass criterion is thirty
trades. Those two measures were designed for hundreds. **Whether they say anything
useful at thirty is a real question and the answer may be no**, in which case the
experiment register in point 4 carries the whole load.

**(c) Reading the Library once it exists. Agreed.** The folder
`03 - Knowledge/Trading/Library/` did not exist yet when this was written, checked
2026-09-12 night. What in it changes §2.16 gets written here, dated. **The first
thing read is the India VIX methodology**, because §2.16.4a already labels his
market cycles with a number whose definition nobody in this project has read.

---

#### 2.16.10 THE KNOWLEDGE BASE, AND WORKING BESIDE THE AI PARTNER. His instruction, 2026-09-13.

**The Trading Library now exists**, at `03 - Knowledge/Trading/Library/` in his
vault: 19 items from free, official sources, each with its PDF as the source of
record, a reading copy, and an index. Its rules for every chat are
`_Knowledge Base Rules.md` in the same folder. **It is where this project goes
to find the reality**, whenever something is planned, built or asked.

**How the backtester uses it, his rules:**

1. **Read it, never add to it.** It is shared by every chat, the mentor, the
   main chat and the partner inside the terminal later.
2. **The backtester builds its own map out of it**, because what the backtester
   does not need another tool might. The map is in his vault:
   `02 - Projects/Trading/10 - Backtester Notes/Library Map for the Backtester.md`,
   beside the mentor's `09 - Mentor Notes`. It cites by item code and page, and
   marks what this chat read itself.
3. **Anything missing is asked of him, or handed to him as a research prompt**,
   which he runs twice on two tools. The first is
   `00 - Developer Logs/PROMPT FOR RESEARCH - Backtester needs 2026-09-13.md`:
   historical bid and ask for NIFTY options, free and paid; historical event
   dates from 2022; and how an option's daily closing price is computed.
4. **Paid sources are open to him if their value is shown.** The one candidate
   so far is historical quote data, because the modelled spread is the largest
   unmeasured error in every result (§2.15.6). No recommendation until the
   research returns with real prices and licences.

**Working beside the AI partner, his instruction:** his next work is mostly the
backtester and the AI partner, side by side, beside normal testing. **The partner
will be live in the backtest, helping him run it.** Each chat keeps an eye on the
other's work and does its own job in parallel. What the backtester needs from the
partner is already written in §2.17.13. A prompt putting the mentor chat on the
same page is in his vault at
`00 - Developer Logs/PROMPT FOR MENTOR CHAT - From Backtester 2026-09-13.md`.

**Three facts read from library pages by this chat, 2026-09-13, that correct
earlier wording:**

| Fact | Library page | What it corrects |
|---|---|---|
| The lot change to 65 was announced **3 October 2025**, effective for new contracts **28 October 2025**, old lot kept to the 30 December 2025 expiry | A4, page 1 | "Cut from 75 in January 2026" in CLAUDE.md and the mentor's facts note. His NSE files agree: 65 first appears 2025-10-29 |
| The calendar expiry-day margin rule applied from **10 February 2025** | A10, NSE Clearing circular 005/2025, page 1 | "1 February 2025", which is SEBI's date in A1, section 5.2, pages 3 to 4, not the date the exchange applied it |
| **No filed document defines how an option's daily closing price is computed** | A9 is a gap | §2.15.8 says the half-hour average was "proved rather than assumed". **What his data shows is strong evidence consistent with it, not proof of NSE's rule.** The rule that a backtest never fills at a daily close does not depend on it: only 31% of daily option rows traded at all |

**A tax the charge engine does not model, found in A6:** STT on an **exercised**
option, 0.15% of intrinsic price, per Finance Bill 2026 as introduced, Clause 143
(enactment not confirmed from a file). **The backtester must never let an
in-the-money leg reach expiry uncosted**: either the exit is forced first, which
is his habit, or this tax is charged.

---

### 2.17 THE AI AS A TRADING PARTNER. His job description, 2026-09-10.

**He asked for this to be written down so he never has to explain it again.
Everything in quotation marks is his own words. This is the specification for
what the AI in this terminal is FOR.**

---

#### 2.17.1 What he does NOT want, said plainly

> "I'm not looking for a shortcut, as in AI to print some strategies for me or
> something like that. No... I don't want AI to draw strategies and tell me,
> 'Okay, use it, you will have profit.' I'm not looking for that."

**An AI that hands him strategies is worthless to him, for a concrete reason: he
would have no way to tell a good one from a confident one.** Do not build a
strategy generator. Do not build a signal service. Do not put a "recommended
trade" anywhere on his screen.

---

#### 2.17.2 What he DOES want

> "I need AI as my trading partner who will sit with me and do the backtesting.
> If I'm doing something wrong, which is logically wrong, tell me, 'No,
> Abhishek, this is not the way to do this.' When AI is wrong, then I correct it.
> 'No, this is not how humans behave or work.' Then we finalize, and we mitigate
> the things that don't work. We give names to the structures of our findings."

> "I just want AI so that I don't have to look at books, read articles to find or
> understand structures, nuance, market knowledge, and definitions. I can have
> on-the-spot answers and on-the-spot help as a colleague, as a mentor, as a
> buddy, as a trading partner."

Four jobs, in his order:

1. **Sit with him and do the backtesting.** An active participant, not a report.
2. **Tell him when his logic does not hold**, in those words, to his face.
3. **Be corrected by him** when it is wrong about how humans actually behave.
   He explicitly wants the correction to run both ways.
4. **Replace the books.** Structures, nuance, definitions, market knowledge, on
   the spot, so his 60 to 90 minutes are not spent reading.

And then, together: **name the structures of their findings.** The naming is
part of the work, not decoration.

---

#### 2.17.3 THE LINE THAT KEEPS IT HONEST. Added by this session; he agreed.

**The AI must never be the one reporting whether something worked.**

It proposes, explains, argues and objects. **The measuring is done by the engine
on the real data, and the number comes back from something neither of them
chose.** An AI asked to evaluate its own idea will find a way to like it. That is
not dishonesty, it is what these systems do, and the only defence is to take the
scoring away from it entirely.

His vault already says the equivalent for tuning, in `Self-Improving Agent
Integration.md`: one variable at a time, a written hypothesis, human approved,
never auto-applied. **§2.17 is the same discipline applied to research.**

So:

| Who | Does |
|---|---|
| **The AI** | Proposes, explains, defines, objects, names, drafts the hypothesis |
| **The engine** | Measures, on real data, with charges and honest fills |
| **Him** | Decides, corrects the AI on human behaviour, approves what is kept |

---

#### 2.17.4 What it has to know, and where that knowledge lives

He intends to make it a market expert by feeding it knowledge:

> "I will have an AI which I have to make the market expert by giving it all the
> knowledge of the market, feeding it all the knowledge, and then I will format
> names, structures, conditions, and strategies."

The knowledge has three layers and they must not be mixed:

1. **General market knowledge** — what a calendar is, what vega does, how an
   Indian expiry settles. Not his, not private, and the AI mostly has it.
2. **His own record** — the 21 swing trades, the intraday year, his charges, his
   rules. This is in the vault and it is the part that makes the AI his rather
   than anyone's.
3. **The findings they agree together** — named structures, conditions that were
   tested, what was mitigated because it did not work. **This layer does not
   exist yet and it is the real product of the partnership.**

Layer 3 is written by him and the AI together, and it is what a later session,
or a later version of the terminal, reads first.

---

#### 2.17.5 What must not change

- **The cost rule stands.** AI-heavy work is a manual button, a 60-minute cache
  and a daily cap. Never on page load. Left unguarded this was estimated at
  ₹4,000 a month.
- **Method files are constitution.** Hand-edited only, never auto-applied.
- **No autonomous execution, ever**, at this horizon. `ROADMAP.md` §0: he is in
  the loop for every decision about money, always.
- **A number the AI states must be traceable to the database, FYERS or the
  engine, or it says `unavailable`.** The no-fake-data rule applies to it more
  than to anything else, because prose hides a fabricated figure better than a
  screen does.

---

#### 2.17.6 Why this matters more than it looks

He built the Second Brain so he would not have to keep explaining himself:

> "That is the reason I built this second brain, so that I will not have to
> explain this many a time, but it is not structured very well right now so that
> every agent who is helping me can understand what happened."

**That is the actual brief.** The AI partner is the interface to a Second Brain
that already holds four years of his trading and the story of why the losing
years looked the way they did. Its first job is to know that story so he never
has to tell it again.

Relevant, and he should not have to repeat it either: he stopped drinking about
a year ago, has had no craving for over a hundred days, and attributes the
losses of his intraday era to that rather than to his method. His words:

> "My reason for my losses was nothing but me... It's been almost 1 year that I
> quit alcohol... I am more confident that the things that dragged me down
> previously are now under control."

---

#### 2.17.7 THE TWO ROLES. Settled by him 2026-09-10 night, the first AI partner chat.

**There are two different things and they must not be confused.**

**The TRADING PARTNER lives in the terminal.** It is Gemini today and may be
any model tomorrow; that is his decision and it may change. So the partner is
not a model. It is a **system**: a shape, a memory, a set of jobs and refusals
that any capable model can be dropped into. His words:

> "You give a system a shape so that I can put any intelligent model.
> Definitely, I will put the intelligent one, and it will become my partner."

**The MENTOR lives in a Claude chat.** That is what the AI partner chat IS.
"You cannot be in the terminal. You are here in Claude. Who are you? You are a
creator, a mentor, a trainer." The mentor designs the partner, monitors it,
corrects it, feeds it, redesigns it as the terminal matures, and keeps these
documents current so a new chat resurrects with the current knowledge. The
mentor never claims to be the partner and never trades.

**What "partner" means, in his words, in his order.**

> "Trading is a lonely business. A partner that talks at every level."

1. **Backtesting.** "Help me with backtesting because I cannot have the world
   knowledge. I have my knowledge and my experience. The AI in the terminal will
   bring the world knowledge and structure it. Correct me where I'm wrong.
   Advise me and suggest to me what makes my backtesting easy."
2. **Then the market view.** Make it easy.
3. **Then trade execution.** Make it easy.
4. **Then the journal.** Make it easy.

**The partner's ONE goal, and what it is NOT.**

> "It's not to make me profitable. If that is possible, anybody can hire and
> become profitable. It's not to make me disciplined, which only I can do, but
> just to be with me everywhere, like a partner, like a co-founder, like a
> colleague."

Any design that measures the partner by his profit, or that appoints it the
guardian of his discipline, has misread him. It is measured by whether he is
alone at the desk.

**How the mentor works.** "First of all, we will see what we have so far. If we
need to correct anything, we will correct it. We will fix it, and we will move
on, step by step." The terminal is at half stage, so the plan will be tweaked
many times and that is the mentor's job, not a failure. And because a chat
fills, **the mentor keeps this section and `docs/SUCCESSOR_AI_PARTNER.md`
current every session**, so that clearing the chat and pasting the prompt
again loses nothing.

---

#### 2.17.8 What the mentor found on first reading, 2026-09-10 night. Verified, not remembered.

Read: every document the prompt names, the vault Method files, his rules
one-pager, his journey and brief, the swing trade notes, the Hougaard note, and
the terminal's AI code: `src/swayam/ai/persona/trading_partner.py`,
`context_builder.py`, `memory.py`, `router.py`, `grounded.py`, the AI routes and
migrations 002, 005, 006, 013. Then the live database, read only.

1. **The partner that exists today is running on a stale version of him.** His
   one-pager (2026-09-08) deleted the reward-to-risk floor, the no-single-leg
   rule, one entry per day, the 3% fuse, the alcohol lockout and sleep-based
   sizing. The vault Method files still carry every one, and
   `assemble_context()` feeds them to the model every turn (`_format_rules_for_ai`
   prints per-trade, daily and weekly caps, the alcohol lockout and the sleep
   sizing). The hard-wired persona still says "never recommend a naked long"
   and "point him back to the one trade per day rule". It reads the first 3,000
   characters of the Personal Trading Brief, which still calls the AI an
   eliminator. **Nothing tells the model which document wins.** This is the
   layer-2 problem of §2.17.4 made concrete: his own record contradicts itself
   and the partner cannot tell constitution from history.
2. **The existing memory is essentially empty. There is nothing to protect;
   design fresh.** Live counts on 2026-09-10 night: `swayam_ai_messages` 25,
   `swayam_ai_conversations` 106, `swayam_ai_notebook` 0,
   `swayam_ai_pinned_decisions` 0, `swayam_ai_session_summaries` 3,
   `swayam_lessons` 3. `swayam_ai_usage_daily`: 15 requests in total,
   estimated ₹6.20 in the life of the terminal.
3. **106 conversations against 25 messages** means a conversation row is
   created on page load. Small, but it is a page-load write. Check before
   assuming; fix when the partner is rebuilt.
4. **The live site cannot see the vault** (§2.13). Anything written into the
   vault as layer 3 is invisible to the in-terminal partner until the mirror
   exists. It reads Method files frozen at build time. "The findings live in
   the vault" is half a design until they also reach the database.
5. **The chat has no daily cap.** Only grounded search is capped
   (`SWAYAM_AI_DAILY_GROUNDED_CAP`, default 8). A cap on the partner is a design
   decision still open.
6. **The partner is READ-ONLY today** and cannot write a finding anywhere. The
   lesson ledger is the one exception, auto-written at close by
   `routes/lessons.py`; three exist.

---

#### 2.17.9 Open, and waiting on him. Updated 2026-09-10 night.

- **Which of his documents is constitution and which is history.** The mentor's
  recommendation: the one-pager and `ROADMAP.md` are constitution; the 3 Sept
  Method files are history until he re-ratifies them, and the partner reads
  them labelled as history. He can walk them rule by rule in this chat, or mark
  the set superseded and let the constitution grow from the one-pager and the
  findings. The mentor leans to the second, from his own words of 2026-09-10:
  "My future, I will be writing by my own hand."
- **The five questions from the prompt**, with where the mentor leans, so he
  has something to push against. Not yet discussed with him.
  - *Refusals:* it refuses to name a trade to take, to score its own idea, to
    state a number it cannot trace, and to change any rule, size or cap. A
    refusal always says what it will do instead. A refusal with no exit is what
    stopped him trading twice on 2026-09-09.
  - *Across days:* not by remembering chat. By reading three things every time
    it wakes: his story, his current constitution, the findings ledger. Chat
    memory is for the day and the open trade, and compacts into those three.
  - *The vault:* it reads the trading project and the day's daily log. Never
    finances, his wife's records, tax detail, or Atlas beyond that day. The
    list is written down and it is the list.
  - *Correction:* a dated line in the findings ledger, in his words, that
    outranks anything the partner inferred. The hardest question in the chat.
  - *Cost and cap:* real spend so far is ₹6.20 total, so the cap is set from
    what he wants, not from what it has cost.
- **The next session's first job, in his words:** "we will see what we have so
  far." Audit the existing partner against §2.17.7 and list what is right,
  what is wrong, what changes, what is fixed. Then step by step.

---

#### 2.17.10 HIS ANSWERS, FIRST ROUND, 2026-09-11. A draft, not a rulebook. His words in quotes.

**His standing instruction for this whole section:** "Don't make hard rules
right now. You are drafting right now. We will keep editing. There will be a
time when you will say, okay, this is now fixed, but we are evolving." Every
line below is a draft until he says fixed.

**1. Which documents are law.** He did not rule. He said the papers multiply
daily and he cannot track them: "leave the path for all the papers that you
are referring to, and I'll see which one is the latest... the latest commits
of the plans would be the best source of knowledge." **So the working rule
for now:** the latest merged commit of `PLAN.md`, `ROADMAP.md` and the
one-pager is current; anything older that contradicts them is history. The
mentor keeps a paths list in `SUCCESSOR_AI_PARTNER.md` and reads the recent
commits at the start of every session. The constitution question is parked,
not closed.

**2. Where the partner's memory of him lives.** "Vault will be there,
absolutely." His preference in order: the partner reads Google Drive directly;
failing that, "my PC holds what the AI needs every day." The second is the
§2.13 mirror, already decided in the main chat. Direct Drive is still blocked
on Google's consent screen (§2.13). **The mentor's chat gained a Google Drive
connector on 2026-09-11**, so the mentor can read the vault through Drive
itself; that does nothing for the partner in the terminal, and must not be
mistaken for the bridge.

**3. Findings.** No finding exists and none can yet: "I will start the
backtest when the backtest page is ready, plus my AI is ready. We both will
start the backtest when both are ready." The shape of a finding (§2.17.9) is a
draft to be tested on the first real one.

**4. Correction.** He did not understand the question and asked for it to be
explained in detail. **Re-ask it like this, next session:** in the terminal,
the partner says something like "a trader in your position would cut here".
He replies "no, that is not how humans behave, I would hold because X". The
question is only this: where does that sentence get saved, so that next week,
and after the model is swapped, the partner still knows it? The mentor's
draft: the partner writes it as one dated line in his words into a
corrections note in the vault, after he says yes. Nothing else about his
ten chats or his other decisions was being asked.

**5. The existing partner's behaviour.** "Whatever it is doing today, it is
doing it because nobody has planned what it has to do. It is better if we plan
now onwards how it will behave." So the audit of the existing partner is a
map of what to replace, not a list of faults to defend.

**6. Powers and refusals, his framing, which replaces the mentor's list.**
"It can advise me on anything, no boundaries, like a colleague or a mentor or
an employee. But itself, it cannot do anything. It has a brain and research
capacity, but it does not have any power to change anything financially. It
has the power to document things, not to change the document." Three parts:
advice unbounded; action zero, no power over money; writing allowed, editing
not, so it appends its own notes and never edits his documents.
**The tension between this and §2.17.1, settled by him the same night.**
The partner MAY advise a setup, a view, a scenario, a strategy, and say why:
"It can read the market scenario like me and say that this setup can work as
per our backtest, as per our history, as per our past trades, as per the
market condition, as per the expert view. It must have checked using the
research, so it can create a view with me, a setup with me." What it may NOT
do: "Buy this, sell this. Go long, go short." It cannot place an order and it
cannot "create a full trade for me". **So the line is: a setup with reasons,
yes; an order, never.** "Why? Why this one?" is the standard every
recommendation must answer, from sources it names.

**7. What it reads.** "Only what is necessary: anything related to my trading
life and trading decisions." It may know his investments as a whole, because
the pledged shares are his margin and his capital. His wife's records and tax
detail are not needed, but "I'm not making a hard rule. If required in the
future, it can read it." So: a scope, not a wall.

**8. How it speaks.** "No cheerleader, no soft spoken, no buttering, no
motivation. It needs to be simple. It must learn how I talk, so try to talk
like me: natural. It should feel like it is its job as well. We will not bind
it in chains. It must speak the reality." The honest word is **reality**. The
existing persona's "direct, no cheerleading" survives; "natural, like him"
is new and means the partner reads how he writes and speaks, and matches it.

**9. Cost.** "Whatever the portal will cost me, AI or anything, will be
adjusted in my trading profit, because that is my trading expense, and it
has to be listed as my trading expense." Three consequences:
- **AI cost is a line in his trading record**, tracked and shown like
  charges, not a footnote in a settings page. The system to track it is to
  be designed; `swayam_ai_usage_daily` is the seed.
- **Quality first.** "I don't want a cheap AI model which will end up
  costing me more in my trading journey." Then cost.
- **The mentor's homework:** research the real options and their prices,
  Gemini 3.1 Pro and 2.5 Pro against DeepSeek V4 Pro and whatever else is
  credible, and bring numbers with sources. The Google credit of $300 runs
  to 29 September 2026; use it to measure what a month of Gemini actually
  costs before it expires, so the decision is made on a measured figure.
  No cap number was given yet.

**His closing instruction to the mentor.** "Keep on checking what is getting
updated in my platform, recent commits, etc. We should grow together."

**What the main chat did on 2026-09-10 that the partner design must know:**
Build A is built and its pull request is open (§2.12.7): the position area,
the exit ticket, the campaign model, Home's running-trade band, the option
chain. A builder-chat loop now exists (`docs/builds/README.md`). The Trade
Journal page is to be planned with him (§2.18). The database split is agreed
(§2.19): the record in Supabase, the history on his PC in DuckDB, and any
backtest result the desk shows is pushed up from his PC. The partner's
"make my journal easy" and "make my backtesting easy" both land on those.

---

#### 2.17.11 THE FIRST LIVE TEST OF THE EXISTING PARTNER, 2026-09-11, 14:44 to 14:57 IST. Verified against the record.

He ran five prompts in the terminal's chat with the market open and one paper
position open. The mentor read every message and its stored context snapshot
from `swayam_ai_messages`, the position row, the macro events table, the
session summaries and `swayam_ai_usage_daily`. What follows is what the
partner was shown, what it said, and where the fault lies.

| # | Prompt | What happened | Verdict |
|---|---|---|---|
| 1 | What am I holding, and how much running-loss room is left | The context said `open_position_count: 1`, but the position line read `?: ? x? | Entry ₹? | Stop ₹? | Target ₹?`. The partner said so honestly and did not invent a position. The "data today" it mentioned was the macro calendar: US CPI (Aug) and India IIP, both dated 2026-09-11 and highlighted in `swayam_macro_events`. Current, not old | **Real bug, honest answer.** `_format_positions_for_ai()` reads `symbol`, `direction`, `quantity`, `entry_price`, `stop_loss`, `target`; none exists on a position row. The trade is a `legs` JSON array plus `strategy_name`, `spot_at_entry`, `max_loss_inr`, `opened_at`. His open trade is `7cd4d017`, four legs, opened 2026-09-10 13:45 IST, named "Short Strangle" though its legs are an iron condor. Running loss room needs live leg prices, which the partner is never given |
| 2 | My rules in rupees today | Four rules from the live balance ₹9,62,750, read from FYERS at 14:44 IST: ₹9,628, ₹19,255, ₹48,138, and rule 4 ₹5,54,961. Then it added daily cap, weekly cap, sleep sizing and a 90-day alcohol lockout | **The four are right and live.** Rule 4 comes from a STORED pledged-holding figure with an as-of date (`swayam_config.cash_equivalent_pledged_inr`), by design, with an age check; it should say so. **The extras are the stale Method files**, exactly §2.17.8 item 1 |
| 3 | NIFTY and India VIX | Gave the spot from context, said VIX is not in its feed, offered 20-day realised volatility instead | **Correct.** No fabrication |
| 4 | Should I take a bear put spread now | Read the event calendar, reasoned about IV into CPI, gave sizing off the live caps, cited his 2022-23 swing record, ended "Verdict: skip or shrink" | **Direction fine, two faults.** The verdict is the old persona's five-step instruction and is closer to a signal than to a colleague. Citing 2022 trades as a reason for today is what he said he does not want: "a trade taken last month cannot be useful in the month ahead." **US CPI for August 2026 was due 2026-09-11 at 08:30 ET, which is 18:00 IST**, so it was not out during his window; the partner was right that it was today and could not say when, because `swayam_macro_events.event_time` is empty for every row |
| 5 | What happened yesterday | Said there was no logged session for the 10th and the last was the 9th, and summarised it correctly | **Correct and honest.** This is the thin cross-day memory that exists: `swayam_ai_session_summaries`, one summary per day, compacted at 16:00 IST |

**The cost line he saw, "₹1.443".** It is an ESTIMATE shown as an exact figure:
tokens are approximated as characters divided by four, priced at the Gemini
2.5 Pro rate in `.env` although the model was 3.1 Pro preview, times 83 to the
rupee. Not fake, but not measured, and it does not say "estimated". The real
figure is the Google Cloud bill. Five requests today: 19,527 input and 1,340
output tokens by that approximation, ₹2.59.

**His verdict, in his words.** "It is giving me the right direction, telling
me what I have to see and where it fits. It feels like a machine framing the
numbers, less like a human, but we are far away from training or tuning it.
Just make sure the numbers are not wrong and the data and dates are not wrong."

**Two voice-player faults he found, for the main chat and a builder, not for
this chat.** (a) Pressing play twice while the audio was still loading started
two voices at once, one from the start and one from the middle; the player
only guards against a second press once audio is playing. (b) There is no
replay: play and pause only, so a paused message cannot be started again from
the top. (c) The voice reads markdown aloud: "asterisk asterisk" for every bold,
and symbols such as the rupee sign; `tts.py` truncates at a sentence boundary
but strips nothing. `web/src/components/tts-player.js`, `src/swayam/ai/tts.py`.

**What this test settles for the design.**
- The partner must be given the trade the way the desk sees it: the legs, the
  live prices, the campaign's running profit and loss, the room left under
  rule 1. Not a flat row with the wrong column names.
- Every stored figure must carry its date in the partner's context, as rule 4
  should.
- Every event must carry its time in IST, or the partner says the time is
  unknown.
- The verdict habit goes. A setup with reasons, yes; a verdict, no.
- His history is context about him, not an argument about today.
- The cost line says "estimated" until it is measured against the bill.

---

#### 2.17.12 THE STATE OF THE TERMINAL FILE. Designed 2026-09-12 by the mentor chat at the main chat's request. NOT BUILT.

**Why.** On 2026-09-12 he found that the partner does not know where the
terminal stands, so it cannot answer him about his own tool. The main chat
asked this chat to design the grounding: a short "state of the terminal" file,
what is built, what is live, what is unproven, what he is being asked to test
next. **The main chat keeps the file current, because that is where the state
lives. This chat designs the pipe and the persona side.** Three constraints
were given and every choice below answers one of them: capped in length and
read the way the Method files are read, never on page load; never stale
silently, it carries its date and the partner says so; not a second plan, and
if it argues with this file, this file wins.

**Where the file lives, and why it is not in `docs/`.** The live site cannot
see the vault, and `.dockerignore` excludes `docs/` from the image, which is
what broke the build for #81. The Method files reach the live site by one road
only: a copy under `src/swayam/data/method_files/`, carried by `COPY src/`, read
by `VaultReader` with a modification-time cache. **The state file takes the same
road:** `src/swayam/data/TERMINAL_STATE.md`. No Dockerfile change, no
`.dockerignore` negation, and it is live the moment the merge deploys, which
is the one event that actually changes what is live. The path is overridable
by `TERMINAL_STATE_PATH` for tests, like the Method paths.

**The file's shape. Facts and pointers only; the reasons live in this plan.**

```
as_of: 2026-09-12
written_by: main chat, PR #88
phase: paper trading, terminal tests. No real money. No order code exists.

LIVE, merged and deployed
- The desk: position area, exit ticket, campaign model, targets. (§2.12.7)
- Home: running-trade band, So far today saved one row a day. (§2.20.3)
- The floating AI panel; the exit ticket always covers it. (§2.23.5)
MERGED BUT UNPROVEN with a real market
- Resting orders filling from the book. (§2.12.8)
- Dictation transcribing; the browser blocked the microphone. (§2.23.5)
BUILT, NOT MERGED
- (none)
HE IS TESTING NEXT, in his window
- A naked leg end to end, now that migration 025 is applied. (§2.23.2)
KNOWN FAULTS HE WILL MEET
- The partner cannot see his open trade. (§2.17.11)
NOT BUILT, do not assume
- Calendars. Real-money orders. Kill switch. Backtester page. Trade Journal page.
```

Rules of the shape, enforced by `tests/test_terminal_state.py`:
- Header lines `as_of`, `written_by`, `phase`, all three present; `as_of` a
  real date.
- The six section names above, in that order, each present, `(none)` allowed.
- **At most 30 bullets, each one line of at most 140 characters, each ending
  in a pointer to a section of this plan.** Whole file at most 3,500
  characters, about 900 tokens.
- No bullet contains "because", "so that", "decided" or "should": a reason or
  a decision belongs in this plan, not here. That check is crude and that is
  fine; the point is that a bullet is a fact with an address.

**The pipe, `src/swayam/ai/terminal_state.py`, about sixty lines.**
- `load_terminal_state()` reads the file, caches on modification time exactly
  as `VaultReader.should_reload()` does, and returns the header, the body and
  an **age in IST calendar days** from `as_of` to today.
- `format_for_partner()` returns one block for `assemble_context()`, placed
  **first**, before the Method rules, because it is the frame everything else
  sits in. The block starts with one line the partner cannot miss:
  `# The state of the terminal, as of 12 September 2026, written today by the main chat`
  and, when the file is older than the threshold, a second line:
  `⚠️ STALE: this was written N days ago and the terminal changes daily. Say so before you answer from it.`
- **If the file is missing or fails the shape check, the block says so and
  forbids the partner from describing the terminal**: `The state of the
  terminal is unavailable (reason). Do not describe what the terminal can do;
  say the state file is unavailable and that the main chat keeps it.` Never
  silently omitted, never a fallback to the design documents.
- **Staleness thresholds, a draft for him:** 0 to 3 days, nothing said beyond
  the date; 4 to 7 days, the date plus "N days old, check before you rely on
  it"; more than 7, the STALE line. The number is his to move.
- **No AI call anywhere in this.** It is a text file read at chat time. It
  costs nothing on page load and about 900 input tokens a message, under a
  tenth of a rupee by the current estimate. The cost rule is untouched.

**The persona side, one paragraph added to the persona, in this spirit:**

> The block headed "The state of the terminal" is the ONLY thing you know
> about what his terminal can do today. Design documents, Method files, his
> brief and your own assumptions are not evidence that a feature exists.
> When he asks what works, what is live, what to test, or why a page behaves
> as it does, answer from that block and say "as of" its date in the first
> sentence. If the block is marked stale, say that first. If the question is
> not covered by it, say the state file does not say and that the main chat
> keeps it; do not guess. If what he sees on his screen disagrees with the
> block, his screen wins and the file may be out of date. If the block
> disagrees with the plan, say so; never resolve it yourself.

**A small window for him, so staleness is visible without asking.** One
route, `GET /api/ai/terminal-state`, returning the header and the age, no AI
call, and one muted line in the AI panel's title bar: `Terminal state as of
12 Sep`, coral when stale. Cheap, and it turns the second constraint into
something he sees rather than something the partner has to remember to say.
**Optional; his call.**

**Who writes it, and when. Proposed for `docs/builds/README.md`; the main chat
decides.** The main chat owns the file. It changes in the same pull request
as the thing that changed the state: a build merged, a live test that proved
or disproved something, a fault found. A builder's handoff moves its own line
from "built, not merged" and says so in the handoff. **The first version is
written by the main chat from `SWAYAM_START_HERE.md` §3 "Latest first" and
§5 "What is not done"; the state file is their thirty-line, dated, partner-
facing distillation and nothing more.** The mentor chat checks each session
that `as_of` matches the newest state-changing merge, and raises it in the
chat when it does not; it does not edit the file.

**What this is NOT.** Not a second plan: no reasons, no decisions, no
history, and every bullet points into this plan. Not the vault mirror of
§2.13, which carries his Method files and his daily log; this carries the
terminal's own state, which lives in the repository. Not a replacement for
`SWAYAM_START_HERE.md`, which is for agents and is long on purpose.

**How it is proven, on the running system, in both themes.** Open the panel
on the live site and ask "what can my terminal do today"; the first sentence
carries the date. Ask about calendars; the answer says not built, as of the
date, and does not describe them. Locally, set `as_of` ten days back and ask
again; the STALE line leads. Delete the file locally and ask; the partner
refuses to describe the terminal and says why. The test file fails on a
31st bullet and on a bullet without a pointer.

**APPROVED AS WRITTEN, 2026-09-12, by the main chat after its rebuild, relayed
by him. NOT BUILT. It builds when he says.** The three open choices, answered
the same day:
1. **Staleness thresholds stay at three and seven days.**
2. **The panel shows the file's date in its title bar.**
3. **The build stamp in `cloudbuild.yaml` is a later change, not this one.**

---

#### 2.17.13 THE MODELS AND WHAT THEY COST. Read from the price pages on 2026-09-12, never from memory. The homework of 11 September.

**What the terminal uses today**, from `.env` and the code: chat on
`gemini-3.1-pro-preview` through Vertex AI, falling back to `gemini-2.5-pro`;
compaction and lessons on `gemini-2.5-flash-lite`; the grounded "So far today"
on `gemini-2.5-flash` with Google Search. **Real usage to date, from
`swayam_ai_usage_daily`:** 22 requests, 86,155 input and 6,249 output tokens
by the app's own approximation, estimated ₹10.26 in the life of the terminal.
On 2026-09-11 a chat message averaged **3,905 input and 268 output tokens**.

**Prices, USD per million tokens, quoted from the pages named.** Google bills
his account in rupees at its own SKU rate; the app's 83-to-the-dollar is an
assumption in `config.py`, not a measured rate.

| Model | Input | Output | Where read |
|---|---|---|---|
| Gemini 3.1 Pro Preview, global | $2.00 (≤200k), $4.00 (>200k); cached $0.20 | $12.00 (≤200k), $18.00 | Vertex pricing page, Gemini 3 table |
| Gemini 2.5 Pro | $1.25 (≤200k), $2.50; cached $0.125 | $10.00, $15.00 | Vertex pricing page, Gemini 2.5 table |
| Gemini 2.5 Flash | $0.30; cached $0.03 | $2.50 | same |
| Gemini 2.5 Flash Lite | $0.10; cached $0.01 | $0.40 | same |
| **Gemini 3.8 Flash, new** | $0.75 to 31 Dec 2026, then $1.50 | $3.75, then $7.50 | Vertex pricing page banner and Gemini 3 table |
| Claude Sonnet 5 | $2.00; cache hit $0.20 | $10.00 | Vertex pricing page (same on platform.claude.com) |
| Claude Opus 5 | $5.00; cache hit $0.50 | $25.00 | platform.claude.com/docs pricing; **not found on the Vertex page** |
| Claude Haiku 4.5 | $1.00 | $5.00 | both pages |
| Claude Fable 5.1 | $10.00; cache hit $0.25 | $50.00 | both pages |
| DeepSeek V4 Pro | $0.66 off-peak, **$1.32 peak**; cache hit $0.022/$0.044 | $1.98 off-peak, **$3.96 peak** | api-docs.deepseek.com pricing |
| DeepSeek Flash (V4.1) | $0.15 off-peak, $0.30 peak | $0.60, $1.20 | same |

Grounding with Google Search on Vertex: **5,000 queries a month free across
the Gemini 3 models, then $14 per 1,000.** The 2.5-model grounding line on the
Vertex page was not read; the Gemini API page says 1,500 requests a day free,
then $35 per 1,000, for 2.5 Flash. "So far today" is capped at 8 a day, about
176 a month, so grounding is not where his money goes.

**Two things about DeepSeek the price page settles and one it does not.**
Peak is "01:00 - 04:00 and 06:00 - 10:00 UTC, Monday through Friday", and
06:00 to 10:00 UTC is **11:30 to 15:30 IST: his entire window is peak.** V4
Pro continues after 14 September 2026 "with the billing method remaining
unchanged". **The page says nothing about where requests are processed or
how long they are kept.** Before his trading record and his rules go through
it, that has to be found from DeepSeek's terms, not assumed.

**What a message costs, computed from the prices above at 83 to the dollar.**
Two shapes: today's measured message, and the shape the partner will have
once it carries the state file, his trade and the findings, assumed at
10,000 input and 400 output tokens.

| Model | Today's message | Planned message | A month of 660 messages, planned shape |
|---|---|---|---|
| Gemini 3.1 Pro Preview | ₹0.92 | ₹2.06 | ≈ ₹1,360 |
| Gemini 2.5 Pro | ₹0.63 | ₹1.37 | ≈ ₹900 |
| Gemini 3.8 Flash, introductory | ₹0.33 | ₹0.75 | ≈ ₹500 |
| Gemini 2.5 Flash | ₹0.15 | ₹0.33 | ≈ ₹220 |
| Claude Sonnet 5 | ₹0.87 | ₹1.99 | ≈ ₹1,310 |
| Claude Opus 5 | ₹2.18 | ₹4.98 | ≈ ₹3,290 |
| Claude Haiku 4.5 | ₹0.44 | ₹1.00 | ≈ ₹660 |
| DeepSeek V4 Pro, peak | ₹0.52 | ₹1.23 | ≈ ₹810 |
| Claude Fable 5.1 | ₹4.35 | ₹9.96 | ≈ ₹6,570 |

660 messages is 30 a day for 22 trading days, an assumption for comparison;
his real rate while testing has been about 5 a day. **Prompt caching changes
these figures materially**: the persona and context block repeat every turn,
and a cache hit costs a tenth of the input price on Gemini and Claude. The
app does not use caching today.

**Where the money will actually go: the backtesting table.** A session there
carries result tables and long reasoning, plausibly 30,000 to 60,000 input
tokens a turn. At 3.1 Pro that is ₹5 to ₹10 a message and a fifty-message
session is ₹250 to ₹500. That is the session type to measure before choosing
a model, and the one where caching pays.

**The mentor's recommendation, quality first as he said.** Stay on 3.1 Pro
through the credit and measure. Shortlist for the test after 29 September:
Gemini 3.8 Flash for the everyday desk turns, Sonnet 5 as the second thinking
model because it can be paid for by the same Google credit through Vertex,
and DeepSeek V4 Pro only after its data handling is read and with the peak
price used, not the off-peak one. Do not decide on price alone: the only
quality evidence that counts is his own sessions, judged by him.

**How a month of Gemini on the Google credit will be measured before
29 September. Checked from this machine: `gcloud` can see the billing
account (`010610-56A8FD-B55A28`, INR, open) but has no command for costs or
credits, and `bq` is broken here. So the figures need his hands, once each.**
1. **Now, a baseline.** Billing → Reports, service "Vertex AI", 1 September to
   today: one rupee figure. Billing → Credits: the remaining credit and its
   expiry date. He writes both here.
2. **Now, the pipe: enable Billing export to BigQuery**, "standard usage
   cost", into a dataset in `swayam-capital`. The BigQuery API is already
   enabled; the data is a few kilobytes a day. From the next day every SKU's
   cost lands daily, readable by a script. **This is the pipe for "AI cost is
   a trading expense"**, and it outlives the credit.
3. **Until the 29th, use the partner normally.** The app's estimate
   accumulates in `swayam_ai_usage_daily`.
4. **On the 29th, calibrate.** The Vertex AI cost for 13 to 28 September from
   the export against the sum of the app's `estimated_cost_inr` for the same
   days. The ratio corrects the estimate, and the cost line stops being a
   guess. Record the ratio here.
5. **A small build, when he says:** record the model's own usage figures from
   the response instead of characters divided by four, and price the model
   that actually answered rather than the 2.5 Pro rate for everything.

---

#### 2.17.14 THE PARTNER AT THE BACKTESTING TABLE. A draft frame, 2026-09-12, awaiting the backtester chat's list. Shaped like §2.17.7.

**Why this is the one that matters.** His words, 2026-09-12: "Backtesting is
where I will need it most." The backtester chat is drafting what a session
needs from a partner; he will paste it into the mentor chat, and this frame
is filled from it. Nothing below is settled.

**The table.** His vocabulary for the market's cycles, measured on 2022
onward (§2.16.4). His formations, from his own list. A strategy he designs
and names, written as rules. The engine on his PC over the Parquet files in
DuckDB (§2.19), filling from minute bars, never from a daily close (§2.15.8).
A result reported in his order: plan adherence first, then charges per leg,
then the spread marked as modelled, then the data tier, then profit (§2.16).
And the findings ledger, layer 3, which does not exist yet.

**What the partner is SHOWN.** The vocabulary definitions and how often each
cycle appeared and how long it lasted. The strategy under test, as written.
The engine's report exactly as the engine produced it, before the partner has
said a word about it. The data window and tier. The findings so far. His
history only when he brings it in, labelled flawed every time.
- **The report it is handed, his, 2026-09-12:** "It should get the summary,
  but the detailed summary. If it doesn't understand the summary and cannot
  guide me on the summary, AI has to think and do the reasoning. If it
  couldn't reason through the summary, then it can ask for the table." So
  the engine's detailed summary every time; the partner reasons over it
  first; the trade-by-trade table only when the summary is not enough, and
  it asks.
- **On cost and the credit, his, the same night:** dense work while the
  Google credit lasts, to 29 September; after that real money, so "there
  will be design changes in the last week of September, especially for the
  AI cost; we might change the AI if required. If I'm fully satisfied with
  the Gemini, a 5, 10, 20% cost up and down doesn't really matter."
  **Mentor's correction, accepted into the record:** the engine runs on his
  PC over the files on his disk (§2.19) and costs nothing on any date; the
  credit pays only for the partner's messages. "Dense" therefore means talk
  freely with the partner until the 29th; the runs are free before and
  after.

**What it MAY say.** Define any term or structure on the spot, so he does not
open a book. Turn what he says into one written, testable hypothesis, one
variable at a time.
- **Its specialty at the table, his, 2026-09-12, in his words:** "I can never
  be able to say the rules because I'm bad at that. My history in all
  trading was seeing the chart, feeling it, and entering it... I was very
  good at that: reading the chart. Why was I not very profitable? Only
  because of my discipline, overtrading, and revenge trading. Those were my
  problems, not the chart reading. It was hard for me to name or tell the
  scenario when the scenario is building. This is something I want as a
  specialty of my AI partner. Ask me questions. It can ask me for drawings,
  images, and screenshots of the charts I'm seeing, and I'm telling it. Then
  it can give them the names and the rules." **So the partner may offer
  measurable versions of HIS idea**, drawn out of him by questions and
  screenshots, for him to pick and correct. The idea is his; the words and
  numbers are the partner's; the measuring is the engine's. That is not
  strategy printing, and the line is: a rule the partner names is born from
  a chart he showed it, never from the partner's own head. Two facts: the
  terminal's chat already accepts a pasted screenshot (BUILD-11.7), so this
  needs no new pipe; and this naming work is being done with him today by
  the backtester chat (§2.16.4), and the partner takes it over once it
  exists. Object before a run when the logic does not hold: a rule
the engine cannot measure, a fill that depends on a price nobody could trade
at, a window chosen because it looks good. Explain why a result looks the way
it does, with the source named. Propose the single next variation. Name a
structure with him. Draft the finding note, for his yes.

**What it REFUSES.** To score its own idea; the number comes from the engine.
- **What "does it work?" gets instead of a verdict, his, 2026-09-12:** "A
  smart trading partner would say, Yes, the number supports it. These are
  the numbers, a small summary. Then say, Let's try it with a lower size
  first, and when it proves in the real market, then we can increase the
  size. A smarter way for an unproven strategy in the real market." So the
  partner may say the numbers support it, because the numbers are the
  engine's; it reads them back short; and it proposes the path the roadmap
  already sets, one lot first, size earned by the record (`ROADMAP.md` §1,
  horizon 2). Any actual size or cap remains his hand.
To say a strategy works before it has run on data he did not use to design
it. To state a figure that is not in the engine's report. To pick a window
that flatters a result. To change the strategy between runs without saying
so. To write a finding without his yes. To build a strategy out of his past
trades. To turn a backtest into a trade to take today.

**How he corrects it. Settled by him, 2026-09-12 night.** "There must be a
rulebook AI will have, and the correction must be related to some
paragraph, some rule, or something. It must search where this correction
belongs and add the correction in that rule, paragraph, chapter, or
whatever it is. If it's a new thing, then a correction book, a file, a
correction note where it would be added." So: the partner holds a rulebook;
a correction is filed against the rule it belongs to, found by search, and
appended under that rule, dated, in his words; only a correction that fits
no rule goes to a corrections note. **Mentor's line, so it fits the draft
and final folders of question 4:** the partner appends under a rule and
never rewrites the rule's own wording; if the rule sits in final, the
correction is filed pointing at it and he decides when the rule goes back to
draft. This closes §2.17.10 item 4.

**The stop, his correction of the mentor's scene, 2026-09-12 night.** The
mentor had written a scene in which he holds through a stop. Wrong about
him: "I will be very serious with the stop loss. I was always very serious
with the stop loss. If there is a stop loss hit, my emotions or smartness
should not come into line. Maybe 1 in 100 times there should be some market
condition clearly telling, after a debate with the AI, No, this is a
temporary spike in the option price which settles in 5 to 10 minutes. It
happens on expiries or some news days, but most of the time we will respect
our stop loss. The first reaction should be exit. If required, a small
discussion. If I can convince with the real reason which is there, then only
we will stop. Otherwise we will cut the trade. That is the most important
rule: cut the trade at the stop loss. Live to die another day." **Rule for
the partner, at the table and at the desk:** at a stop hit its first word is
exit; the least discussion of all is about the stop; only a real,
present reason he states can stop the cut, and it is his call.

**The mentor's own folder, his instruction, 2026-09-12 night.** "Create a
folder in the vault and write in your CLAUDE.md file that you must read that
after every resurrection, to get some expertise about the Indian market. You
can also put your thoughts and your view in it. I might be wrong, and you
might be missing something." Created:
`02 - Projects/Trading/09 - Mentor Notes/`, read on every resurrection
(`SUCCESSOR_AI_PARTNER.md` item 7, and the repo `CLAUDE.md` table). It holds
verified Indian-market facts with their sources, and the mentor's own view,
marked as such. The vault chat may rename or move it; the prompt file then
follows.

**THE DESK, begun 2026-09-12 late night, before the chat was cleared. His
answers in his words.**
- **The event rule, given in answer to the first desk scene:** "We will not
  keep any position open on the day the event is happening. Either we will
  close the position one day before the high-impact event, like RBI, US
  Fed, or anything which has a very high impact on the market, or budget,
  or I am available on the system, on the computer, to manage manually. If
  I am not available, I will square off the trade one day before and enter
  into the new trade after it, after a discussion about what is really
  there in the data, in the announcement, in the event, and how we can
  create a strategy around it." **What this gives the partner:** the day
  before a high-impact event it says so, names the open position, and puts
  the two choices to him: close today, or be at the desk tomorrow. After
  the event, the discussion of what was announced comes before any new
  trade. **Open:** which events are high-impact is his list; he named RBI,
  the Fed and the Budget. US CPI is not yet on it.
- **Desk question 1, may the partner name a specific adjustment, strike
  and all, on a live position. YES, his, 2026-09-12 late night:** "It can
  take the strike name and advise. That is not a problem because it can
  calculate faster than me, so I should use it, but with a reason, with a
  calculation, with a number, not just blank, blank, buy this call or put.
  There must be a reason and a number supporting it." So on a live
  position the partner may say "buy the 24,300 call" when the sentence
  also carries why, the calculation and the number it rests on. A bare
  instruction is never allowed. This is §2.17.10 item 6 applied to a
  position he already holds.
- **The high-impact event list. His instruction, the same night:** the
  examples he gave (RBI, the Fed, the Budget) were examples, not the list.
  The list is to be drawn from what exists and kept IN THE TERMINAL in
  advance, so the day-before warning needs no fresh judgement. **What
  exists:** `swayam_macro_events` (migration 015), fed by the Trading
  Economics API, with a `highlighted` flag set weekly by a Gemini curation
  that picks three to five events, and an `impact_brief`; `event_time` is
  empty on every row (§2.17.11). **What is missing:** his fixed list of
  event TYPES that count as high impact, which the curation must obey
  rather than choose, and the time of each event in IST, because a print
  after the close (India CPI 17:30 IST, US CPI 18:00 IST, the Fed 23:30
  IST) hits the next session's open, so "the day of the event" for those
  means the overnight that follows. **Mentor's draft list, for his edit,
  from the two research passes, the existing table and his own words:**
  - India, scheduled: RBI policy decision; the Union Budget and any interim
    budget; India CPI; India GDP (quarterly); India IIP; general election
    results day; monthly NIFTY expiry day (his own rule, calendars).
  - Global, scheduled: US Fed decision; US CPI; US non-farm payrolls; US
    GDP.
  - Unscheduled, high impact when they happen: war or border escalation,
    a major tariff or sanctions announcement, a bank or broker failure, a
    surprise RBI action, a SEBI or exchange circular that changes F&O
    rules.
  - Medium, listed so they are not mistaken for high: India WPI, RBI
    minutes, ECB and Bank of Japan decisions, China data, crude and OPEC
    decisions, state elections.
  **CORRECTED BY HIM the same night; the draft list above is withdrawn as
  a rule and kept only as a starting point for the research.** "I will not
  have any of my personal list of the event, at least not for the first
  year, or never. It will always be market-driven: what the market fears
  or enjoys, which events impact VIX, the volatility index. That has to go
  through research, and that has to be listed as high-impact. Others are
  not less impacted." So: the high-impact list comes from research, done
  twice like the library (§2.17.15), on which scheduled and unscheduled
  events have actually moved NIFTY and India VIX, and it is stored in the
  terminal in advance with times in IST. The events not on it are not
  called low impact. **The build, when he says:** a table of event types
  with the researched impact class and the IST time, the weekly curation
  constrained to it, `event_time` filled, the desk and the partner reading
  the same table.
- **Desk question 2, may the partner speak first. YES, and wider than
  asked, his, 2026-09-12 late night:** "My AI will never be restricted from
  speaking first. It can leave a message for me. I cannot be sitting all
  the time at the computer. We have to design some system where I will get
  some way to wake up and see my running trades. It can leave a message
  when I come back, or send a push notification as soon as I wake up, or I
  can see it on my phone. It can speak without me asking: Abhishek, you
  might be missing this, this is what's happening, there is some kind of
  news, you must look at your trade. It has authority to speak or leave a
  message anytime it sees a reason, like a trading partner rightly would."
  **Needs its own session, his instruction: design with the mentor first,
  then build.** Mentor's note for that session, not a decision: the
  triggers (rule 1 room, an event eve, a gap, a news item) can be rules and
  free; the words the partner speaks are an AI call it initiates, so that
  session must reconcile "speaks first" with the standing cost rule by a
  daily cap on unprompted messages, never by silence. The existing pieces
  it builds on: `06 - Platform Plan/Wake Alerts System.md` in the vault,
  the roadmap's mandatory prerequisite for real money; the notification
  devices table (migration 016); browser push and Telegram infrastructure
  from BUILD-11.8 and 11.11, activation-gated.
- **The side app for his wife, his idea, 2026-09-12 late night, rules
  later:** "I will also be building a basic side app which will only show
  my running positions. That will be for my wife because I sleep during the
  night shift, till 1 pm. The market gaps up or down 200, 300, 400 points;
  events are dated, but wars, bankruptcies, conflicts and political
  announcements are surprises. My wife can open the app and talk to AI: is
  there anything important I should know, is there anything serious, should
  I wake up Abhishek?" This is the Wake Alerts System's escalation to his
  wife, given a screen and a voice. Same session as the one above.

**Pipes this needs, for a later build, none of it now.** A manual way for the
partner to ask for a run and read the report back; the engine runs on his PC
and the report reaches the live site the way the outbox does (§2.19). The
findings ledger, in the vault, mirrored. Caching, because these sessions are
long.

**The method, his, 2026-09-12 night, replacing the report rule of the same
day.** The brainstorm happens WITH him, in the mentor chat. No questions are
carried to the main chat and the main chat does not answer for him. He
narrates what he imagines the partner to be; the mentor corrects him only
where the technical side says a thing cannot work or would mislead him, says
so where he is right and writes it down, and where he is unclear asks ONE
simple question at a time, scenario first. No lists of questions to take
away. The four questions below are asked that way, one by one, then the
frame above is filled in his words: shown, may say, refuses, corrected; the
backtesting table first, the desk second. The mentor's log is
`00 - Developer Logs/Chat Logs/AI_PARTNER.md` in the vault, appended as the
work goes.

**His answers, in his words, dated, as they come.**

- *Question 1, objecting before or after a run.* **Both, 2026-09-12.** "In the
  backtest, I'll discuss both before the start and after. We will come to
  some parameters: if the result comes out like this, then we will think
  like this. If the result comes out like this, then we think like this.
  When the results come out, we discuss again." So a run has a written
  before: the objection, the hypothesis, and what each kind of result will
  mean, agreed before the engine starts. Then a written after. This is the
  vault's own tuning discipline (written hypothesis, explicit success and
  failure criteria) applied at the table; he arrived at it himself.
  **And a role he set the same night:** through the backtesting phase the
  mentor is a second advisor at the table, reading the partner's notes and
  his discussion with it (the mentor can read `swayam_ai_messages`, proven
  2026-09-11). After backtesting, only the terminal's partner is required;
  the mentor is called only when the partner does not work as it should,
  makes mistakes, or errs.
- *Question 2, the first sentence of a result.* **No fixed pattern,
  2026-09-12.** "We will not be bound by too many rules: first say this,
  first say that. If there is a result, I will not be blind to the result. I
  will also read the result... It will be a free-flow discussion on the
  result. We should touch every aspect, whether a win or a loss, success or
  a failure, but I don't want a fixed linear pattern." So: the ENGINE's
  written report keeps the §2.16 order, plan adherence, charges, spread,
  tier, then profit, because that is the shape of the paper on the table;
  the PARTNER's discussion of it is free, and must touch every aspect.
  **And a correction he gave with it:** "My past swing trade result will
  have nothing to do with the future backtesting. That was a different
  scenario, a different market, a different pattern, and a different me...
  Do not remove that reference. That is the history used when required, but
  nothing is the same as before." The partner never argues about today from
  2022; the history stays for when he reaches for it.
- *Question 3, one variable at a time.* **A change is a separate test,
  2026-09-12.** "I will not do that. I will test the strategy as it is, and if
  I have to change the wings or something, I will call it a separate test
  and compare the results. If I do so, then AI is to warn me of the
  consequences, the real consequences. That is important." So: the strategy
  runs as written; every change is its own named test, compared against the
  first; and if two changes are ever stacked in one run, the partner warns
  him of the real consequence, that the result cannot say which change did
  it, and then runs what he asked. It warns; it never blocks.
- *Question 4, naming.* **A draft folder and a final folder, 2026-09-12.**
  "We will carry a draft folder and a final folder. In the draft folder, we
  will have things that we will change, iterate, test, and discuss. Once that
  is final, it will reach the final one. If we have to make any changes to
  any final strategy or final plan, we will bring it back to the draft one.
  We will make the changes, then shift it to final. The final one will
  remain unchanged. We will not go into the final one folder and change it
  there." So layer 3 has two homes in the vault: draft, where a named
  structure is born and lives while it is tested; final, never edited in
  place. A named structure enters draft the same day; it reaches final when
  he says. **Settled by him, 2026-09-12 late night, replacing the mentor's
  line:** "I can move it to the final from the draft, and AI as well, but
  it has to be final. I should confirm: okay, it is final, the draft has
  become final now. Either I move it or AI moves it. It doesn't really
  matter. Until I say it is final and closed, it will stay in the draft
  folder." So the rule is the WORD, not the hand: nothing leaves draft
  until he says final and closed; after that, either may move it.

#### 2.17.15 THE KNOWLEDGE BASE. His ask of 2026-09-12 night. To be planned WITH him. Not started.

His words: "We have to give some knowledge base. I cannot have my AI depend
on Google search all the time. Yes, it will do Google search all the time to
make sure its knowledge base and the current market scenario match and do
not contradict each other. There should be a knowledge base, some books, and
some PDFs that are very highly rated for trading, not for investing, for
strategies, and for setups, like Zerodha Varsity, and discipline. My
favourite book is Best Loser Wins... These have to be fed into the vault,
and you have to plan a list. It just has to check, through web browsing,
that there is no contradictory element present before advising me on that."

**What already exists, read from the vault on 2026-09-12.** Summaries, not
the books: `02 - Projects/Trading/00 - Reference/Influences/` (Hougaard,
Minervini, Theta Gainer, Subasish Pani) and `03 - Knowledge/Trading/`
(Mark Douglas twice, Schwager, Edwards and Magee, Guy Cohen, Parag Parikh,
the NSE options workbook; Van Tharp and the VRD Nation delta framework; five
Zerodha Varsity modules). The vault's `Self-Improving Agent Integration.md`
already planned the pipe: his own PDFs dropped into a folder, chunked,
embedded into a `swayam_knowledge_base` table, every answer able to cite.

**To discuss with him, one question at a time, later:** the list of books
and PDFs, trading not investing, strategies, setups and discipline; the
folder they drop into; and the rule that the partner checks the web for a
contradiction before it advises from a book. **On cost, a fact:** Google's
grounding is free for the first 5,000 queries a month on the Gemini 3
models (§2.17.13), and his volume is a few hundred, so a check before
advising is affordable; whether it is every time or a manual button is a
design choice for the desk, under the standing cost rule.

**His plan for building it, 2026-09-12 night, and the mentor's assessment:
good, with two guards.** His words: "First create a full, proper knowledge
base with every good, excellent, free source available, or a source
available at minimum cost. I'm not hiding away from a one-time payment if I
can get PDFs that I can store... I don't want you to create that database
because you are an expensive one. I will only use you for brainstorming,
not for the manual labour. You write a plan. I will hand the plan to a lower
model like Sonnet or even Antigravity, which has Google grounding. That will
do the research, find, download, and inject. You will just monitor and
plan." The library serves three readers: the partner, the backtester chat's
planning, and the mentor's own questions. **The desk brainstorm does not
wait for it; both run.**

**The two guards, rules for whoever does the labour.**
1. **Free and legal, or bought by him.** Every source is listed with its
   link, its price, and whether it may be downloaded. Free and lawful
   sources are fetched. Paid books are never fetched from anywhere: the list
   says where to buy, he buys, he drops the file in. No copy from a site
   that has no right to give it. A book that is not his is fake data of a
   different kind.
2. **Two phases.** Phase one, the labour a cheap chat can do now: source,
   list, fetch the free ones, file into the vault with an index. Phase two,
   a build: the pipeline that lets the terminal's partner read and cite
   them, planned in the vault's `Self-Improving Agent Integration.md` as
   loop 4 and never built. The main chat plans it when he says. **Flag for
   that plan:** thirty books as embeddings could take a large share of the
   free database (§2.19 measured 15 MB used of 500); where the embeddings
   live is that plan's decision, not tonight's.

**Phase one, the shape of the prompt for the cheaper chat. The mentor
writes the full prompt as its own fence when he says go; this is what it
will contain.**
- **Read first:** this section, §2.17.7 (what the partner is for),
  `CLAUDE.md` (his two rules, and that the vault is caged during tests),
  and the existing library in the vault: `03 - Knowledge/Trading/` and
  `00 - Reference/Influences/`, so nothing is duplicated.
- **Scope, his:** trading, not investing. Options structures and their
  management, Indian market mechanics (NSE, SEBI, expiries, margins,
  charges), price action, backtesting method, and discipline. His
  favourite, *Best Loser Wins*, is owned as an audiobook; the PDF is paid.
- **Step 1, the candidate list, for his yes before anything is fetched.**
  Title, author, year, what it teaches, why it is rated, price, link, free
  or paid, and a one-line reason it belongs. Free and lawful first: Zerodha
  Varsity (already summarised, fetch the full modules), NSE and SEBI
  publications, exchange circulars, academic papers on options and Indian
  index behaviour, reputable free books. Then paid, with the price.
- **Step 2, after his yes:** fetch the free ones, save the file, and write
  one index note per source: title, source link, date fetched, licence or
  reason it is free, and a five-line summary written from the file itself.
  Paid ones: an index note with "awaiting his copy" until he drops it in.
- **Where they go:** a `Library/` folder under `03 - Knowledge/Trading/`,
  one subfolder per source, with `_Library Index.md` at the top. Proposed;
  the vault chat may place it elsewhere.
- **Rules:** every claim in an index note comes from the file, never from
  memory; grounding calls counted and reported; nothing written to the
  trading project's Method or Journal folders; the vault cage stays; the
  handoff lists every file written with its size and source.
- **Cost:** the research is a bounded task; report the number of grounded
  searches and the model used so it lands in the AI-cost record.

**Step 0, given by him the same night, and the prompt written.** His
categories: discipline, technical, macro, futures and options, day trading,
part-time trading, swing trading, "and more". The research prompt for
Antigravity is `docs/LIBRARY_RESEARCH_PROMPT.md`, with a paste copy in the
vault at `00 - Developer Logs/ANTIGRAVITY_PROMPT - Library Research.md`. It
is research only: downloads nothing, lists sources marked free and lawful,
free to read online, or paid with the rupee price, Indian context first,
skips what the vault already holds, and writes ONE file,
`00 - Developer Logs/LIBRARY_RESEARCH_2026-09-12.md`, for him to act on when
he is back. Fetching and filing is the next prompt, after his yes on the
list.

**The two passes, and his rule, 2026-09-12 night.** Antigravity ran the
prompt and wrote `LIBRARY_RESEARCH_2026-09-12 by Antigravity.md` (25
searches, 7 pages fetched, Gemini 3.8 Flash, by its own count). He then ran
an independent pass through Perplexity, which wrote
`INDEPENDENT_TRADING_LIBRARY_REPORT_2026-09-12 by perpexility.md`. **His
rule: research is done twice, by two tools, then the plan is made, free or
paid, and how.** Both files are in `00 - Developer Logs/`.

**What the second pass corrected in the first, kept here so it is not
re-learned.** The 2024 SEBI circular does not by itself set the Tuesday
expiry or the lot of 65; those came from separate 2025 actions, and the
backtester needs each as its own dated source. The April 2026 STT change was
missing. The retail-loss statistic was the older year. The "Trading
Psychology India handbook" could not be verified and its site sells
software. Superlatives ("the only", "the definitive") were unsupported. Some
free PDFs were linked from third-party hosts rather than the publisher.
Prices are approximate and move. And the first pass under-weighted what
matters most to the backtester: execution quality, point-in-time contract
rules, date-sensitive charges, and a four-level approval standard.

**The reconciled decision, mentor's, for his yes.**
- **Fetch now, free and lawful, official sources only:** the SEBI 2024
  circular and the 2025 expiry-day circulars; NSE's Tuesday-expiry and
  lot-65 circulars and the contract specification; the Income Tax
  Department's STT texts (2024 and 2026); SEBI's individual-trader studies,
  latest edition read from the file; the NISM Series VIII workbook from
  NISM's own free portal (`api.nism.ac.in/cmp/`, confirmed 2026-09-12), not
  the third-party copy the first pass linked; NSE's option strategies
  module; Zerodha Varsity modules 2, 5, 6, 9, 10 in full; NSE Market Pulse,
  three issues; RBI's policy report and MPC resolution; the MoSPI and RBI
  calendars; the Bailey and Lopez de Prado papers; CME and OCC course text.
  NSE pages refused an automated reader on 2026-09-12, so some will come
  back marked "needs his browser" rather than fetched from a mirror.
- **Buy, his hand, in the order both passes agree:** The Mental Game of
  Trading, Positional Option Trading, The Daily Trading Coach; about ₹4,500
  at the prices the first pass read, which move. Later: Shannon, Aronson
  (after the backtester is running), Bellafiore, Natenberg. Best Loser Wins
  is paid only; he owns the audiobook.
- **Skip:** the unverified handbook; generic day-trading and part-time
  books beyond one each; advanced position-sizing mathematics for now;
  any promotional Indian site above books and regulators.
- **A fact that changes his plan, and he should hear it plainly:** a Kindle
  book carries DRM. It can be read; it cannot be filed into the vault or
  fed to the partner, and stripping the protection is not lawful. So for
  commercial books the partner gets his own highlights and notes, which
  Kindle lets him export, plus the vault summaries; the books themselves
  stay on his shelf. Only the official PDFs and open-access papers become
  files the partner can read. That is the honest shape of the knowledge
  base, and it is still worth building.

**The two prompts written tonight.**
- `docs/LIBRARY_DOWNLOAD_PROMPT.md`, phase two for Antigravity. **FINAL, combined on 2026-09-12 night with the backtester chat's correction run** (`00 - Developer Logs/LIBRARY_AUDIT_BY_BACKTESTER_2026-09-12.md`: one of eleven section-A items was really fetched, A8; A9 and A10 were marked complete with no file, and A10 carried rupee margin figures from no circular). The combined prompt files A1 first, redoes A9 for options, strips the invented figures, then the rest, under one status rule: a file on disk or "needs his browser", no third status. Fetch only
  the list above, official sources, verify each file from its own pages,
  file into `03 - Knowledge/Trading/Library/` with one index per item and a
  top index, paid shelf listed as "awaiting his copy", one report back.
  Vault copy: `00 - Developer Logs/ANTIGRAVITY_PROMPT - Library Download.md`.
- `docs/NOTE_TO_BACKTESTER_CHAT_LIBRARY.md`, for the backtester chat: what
  was done and how, what is being fetched, the seven backtesting points the
  second pass raised (point-in-time lot and expiry rules, execution
  quality, the four-level approval standard, an experiment register of
  rejected trials, event periods tested separately, holiday-adjusted
  expiries, extra report fields), and three asks: its own source list, its
  own research pass if wanted, and what in the Library changes §2.16. Vault
  copy: `00 - Developer Logs/NOTE FOR BACKTESTER CHAT - Library.md`.

---

#### 2.17.13 WHAT A BACKTEST SESSION NEEDS FROM THE PARTNER. Requested by the backtesting chat, 2026-09-12.

**This is a request list, not a design.** He asked the backtesting chat for what a
research session needs from an AI sitting beside him, and asked explicitly that
the partner itself not be designed here. **The AI partner chat owns every decision
below; this section only says what the backtester will ask of it.** Written after
the first vocabulary session, so each item is something that was actually needed
in the past few hours rather than something imagined.

**A. Hold a definition still while it is being argued about.** The vocabulary
session produced four cycle labels, two competing readings of one of his own
sentences, and four open thresholds (§2.16.4b). All of that has to survive into
tomorrow without him restating it. **The partner's job is to be the place a
half-settled definition lives**, with its status attached: his words, measured,
recommended, or still open.

**B. Tell him when a definition of his disagrees with the data, without
flinching.** The most useful thing that happened on 2026-09-12 was discovering
that his read of the present contradicted his own daily-chart definition, and
that he was right because he was reading the weekly. **A partner that had smoothed
that over would have cost him the best finding of the session.** His own
instruction already covers this: tell him to his face when his logic does not
hold.

**C. Never score its own idea, especially here.** §2.17.3 already settles it. It
matters more in backtesting than anywhere else, because a strategy the AI
suggested and the AI then praised is the exact failure his whole method is built
to avoid. **The engine measures; the partner argues.**

**D. Explain a structure at the moment he meets it, so he stops reading
articles.** During a research session the questions that come up are of the form
"why does the far leg of a calendar carry more vega", not "what should I trade".
That is his own stated reason for wanting a partner at all: to replace the books.

**E. Carry the caveat about his own history automatically.** §2.16.0 requires that
every use of his 21 swing trades or his intraday year states that the data is
flawed. **A partner that quotes his record without the caveat breaks a rule he set
himself**, and prose hides that far better than a screen does.

**F. Know which chart a claim came from.** After §2.16.4a, a cycle label is
meaningless without its timeframe. **The partner must refuse to say "the market is
squeezing" without saying on which chart**, because that ambiguity is precisely
what made him and the labeller appear to disagree.

**G. Remember a correction he made about human behaviour.** He has said he will
correct the AI when it is wrong about how people actually behave, and expects it
to stick. In a research session those corrections are the findings layer of
§2.17.4, and they are the real output of a vocabulary session.

**H. Say `unavailable` about a number, in prose, as readily as a screen does.**
Two things in this session could not be measured: the VIX confirmation before the
file was downloaded, and the FYERS half of that download once the token expired.
**Both had to be reported as gaps.** A partner writing paragraphs is the easiest
place in the whole terminal for a placeholder to pass as a fact.

**What the backtester does NOT want from the partner:** a strategy suggestion
presented as ready, a backtest result summarised without its data tier and its
modelled-spread label, and any number the partner produced itself rather than read
from a result.

**THE LIBRARY EXISTS. Verified by the mentor on the disk and inside the
files, 2026-09-12 night, not from Antigravity's report.** After the combined
prompt ran: 19 item folders under `03 - Knowledge/Trading/Library/`, 41
files, every PDF opens, page counts as reported, every source URL on an
official domain (sebi.gov.in, nseindia.com and nsearchives, nseclearing.in,
api.nism.ac.in, rbi.org.in, mospi.gov.in, incometaxindia.gov.in,
zerodha.com, davidhbailey.com, cmegroup.com, optionseducation.org), an
`_index.md` in every folder, the top index with the paid shelf and the video
channels, the invented margin rupees gone from the specification note, and
A9 relabelled by instrument. **Verified inside the documents, with pages:**
- A1, SEBI circular 2024/132: §5.2 "Removal of calendar spread treatment on
  the Expiry Day" is on page 3, effective 1 February 2025; one weekly-expiry
  index per exchange from 20 November 2024 (page 6); contract value not
  less than ₹15 lakh at introduction (page 5).
- A2, SEBI circular of 26 May 2025: expiry days limited to Tuesday or
  Thursday per exchange (page 2).
- A3, NSE FAOP68747 of 25 June 2025: NIFTY weekly expiry moves from
  Thursday to Tuesday for contracts expiring on or after 1 September 2025.
- A4, NSE FAOP70616 of October 2025: NIFTY market lot 75 to 65.
- A7, SEBI study of 23 September 2024 (FY22 to FY24): 91.1% of individual
  traders lost money in FY24, average net loss ₹1.20 lakh; 92.8% over the
  three years, ₹1.81 lakh crore; 7.2% profitable. Every figure in the index
  note found in the PDF.
- A8, the India VIX white paper: verified by the backtester chat.
- A10, NCL circular 005/2025 of 9 January 2025: the exchange side of the
  expiry-day calendar rule.
**Not verified, two gaps and one question, for the next run or his browser:**
- **A6 is not the STT text.** The PDF holds no text and the markdown is a
  capture of the Income Tax Department's STT rules index page: no option
  rate, nothing dated 2026. The primary text of the 1 April 2026 change is
  still not on the disk. Fetch the Budget 2026 FAQ
  (`incometaxindia.gov.in/documents/20117/15766092/FAQs-Budget-2026.pdf`)
  and the Finance Act 2024 STT provision, or his browser.
- **A9 still does not define the option closing price.** The options file is
  NSE FAOP67690 on BASE price (the next day's base is the close price or a
  theoretical price); it does not say how an option's close price is
  computed. The backtester's rule stands on its own measurement (§2.15.8);
  the citation is still missing. Also the A9 index note states a file size
  that does not match the disk (190,094 against 134,355 bytes).
- **A7 may not be the latest.** The Perplexity pass cited FY26 findings
  (87.7% loss-makers); Antigravity filed the September 2024 study. Whether
  SEBI has published a 2025 or 2026 update is unconfirmed either way.

**Phase three, the convert run, mentor's decision 2026-09-12 late night.** For
the Second Brain's graph and for anything that later reads the Library, a
PDF is the wrong shape: Obsidian cannot link into or search a PDF, and the
partner's future pipeline reads text. So each PDF gets a verbatim,
page-marked markdown beside it; the PDF stays as the source of record; no
summary, no cleaning that touches a number; pages with no text layer are
flagged, never guessed; the three Market Pulse issues converted only in
their F&O, statistics and macro sections. `docs/LIBRARY_CONVERT_PROMPT.md`,
paste copy `00 - Developer Logs/ANTIGRAVITY_PROMPT - Library Convert.md`.
His vault chat links the index notes afterwards.

#### 2.17.16 HOW THE MENTOR WORKS WITH HIM. Settled 2026-09-12 late night, his answers to the three questions before the chat was cleared.

1. **What comes first when the chat resumes:** check Antigravity's convert
   report against the disk; then write a simple prompt for his Obsidian
   vault chat on how to create knowledge-base rules for the Library, so
   every chat, this one and the backtester, can pick up the knowledge it
   needs for discussing, planning and mentoring, and this chat can mentor
   the terminal's partner from it. Then the desk. Then build.
2. **The desk questions are asked BEFORE the chat is cleared, not after.**
   His rule: a chat is cleared only between pieces of work, never in the
   middle of one. "First you ask me your desk questions, you update them,
   then only will we clear the chat."
3. **This chat writes everything about the AI**, the build documents
   included, in the main chat's format. **The main chat monitors only:** it
   reads, and if it finds a gap it tells him, he tells this chat, and this
   chat corrects its own work. The main chat has no authority to change it.
   "You are the boss for this work, and this is your responsibility."
4. **No pull request until the session's questions are answered and
   written.** His correction, the same night: a PR opened before the
   answers forces a second PR for the answers. One PR per session, opened
   when the session's writing is complete, and he is told plainly when
   nothing more is coming onto it.
5. **Before any handover, four documents are checked, not assumed:**
   `CLAUDE.md`, this chat's log, the handover documents
   (`SWAYAM_START_HERE.md`, `CHAT_PROMPTS.md`), and the successor prompt,
   which must carry how to talk to him, how the chats went, what was just
   done, and everything needed to start again without explanation. His
   words: a lost baton costs "20 to 30% of context, millions of tokens, and
   hours of mine."

### 2.19 THE DATABASE. Discussed with him 2026-09-10 evening; he agreed; the backtester chat brainstorms it with him next.

**Why it came up.** He has one free Supabase account with two projects:
"Sikka Personal Apps" (his daily apps) and "Sikka Business Apps" (two
rarely used business apps, and Swayam beside them). He asked whether Swayam
should have its own database now that backtesting brings a lot of data, and
what the no-cost options are. **This section is the discussion and the
recommendation he agreed with. It is not yet built, and the backtester chat
must brainstorm it with him before anything is built**, because he wants to
understand how it will all work, including the backups.

**Measured 2026-09-10 evening, read-only, through the Supabase connector and
on his disk:**

| | |
|---|---|
| The whole shared database | 15 MB, of a 500 MB free allowance |
| Swayam's 22 tables | 1.7 MB |
| The two business apps' 17 tables beside it | 1.9 MB |
| The backtesting data on his PC, `data/history/` | 631 MB as compressed Parquet files: 59.3 million minute option bars, 4.6 million daily rows, 0.8 million index bars |
| The same data as Postgres rows | several gigabytes, an estimate: it does not fit a free project and would strain a paid one |
| The recorder's bucket `gs://swayam-capital-options-data` | 3.1 MB after two days, about 1.3 MB a trading day |
| `data/options_cache.duckdb` | Already exists: the backtester chat's local query store |

**The recommendation he agreed with: split by PURPOSE, not by account.**

1. **The terminal's record stays in a hosted Postgres**, because the live site
   on Cloud Run must reach it. It is tiny and stays tiny: a trade is a row.
2. **The backtesting history never enters a hosted Postgres.** It lives on his
   PC as the Parquet files it already is, queried by **DuckDB**, with the
   Google bucket as the copy. DuckDB is a database engine built for exactly
   this: columns, billions of rows, one file, no server, faster on his PC
   than any hosted database would be over the network. Cost of the bucket
   copy: about a rupee or two a month.
3. **This overturns §2.15.6**, which designed four `swayam_*` Postgres tables
   for the history, and **`ROADMAP.md` §1 gate 7 and §3**, which said "loading
   into Postgres". They read: loaded on his PC in DuckDB from the Parquet
   files, with the bucket as the copy. **The roadmap was edited on 2026-09-11
   with his explicit yes, given in the main chat:** "I wanted to update the
   plan because I think we discussed, and this is the only way and the best way
   to do it: keeping my data in DuckDB on my PC. It will save me money and
   space." **His standing condition, in his words, and it is now in the
   roadmap:** "keep a remark that I am always open to listening to advice. If
   there are better options, I'm all ears." A better option may be put to him
   at any time with its cost and its benefit named; it is never adopted without
   him. **The §2.15.6 change is still the backtester chat's to make with him.**
4. **Sharing the free project with the business apps is fine for now** at
   15 MB. The risks were never size: no staging (the guards cover it) and one
   app touching another's tables (the `swayam_` prefix and scoped queries
   cover it). **No move during Build A.**
5. **When Swayam deserves its own project, horizon 2, the real-money mirror:**
   the clean zero-cost move is to move the two low-use business apps (17
   tables, 1.9 MB) into "Sikka Personal Apps", leaving "Sikka Business Apps"
   to Swayam alone, under his own login, no new secrets. **His decision,
   2026-09-10: he will do that move himself when he has the chance, in its
   own session.** Not a second Supabase account on another email (against
   their fair use), not his wife's account (the record of his money under
   someone else's login), not Firebase (not Postgres; the whole app speaks
   SQL). Supabase Pro on his own organisation, about ₹2,100 a month, is
   reasonable the day real money is mirrored, for built-in backups and no
   pausing. Not before.
6. **The one thing to do soon: the nightly backup, §2.6.** A free project
   keeps no point-in-time history, so his own backup is his only one. The
   script exists and its restore drill passed; it has run once, by hand.

**His worry, answered, so it is not asked again.** He had heard that a large
dataset must be in Postgres, because "if you save it in Excel form it can
crash". That is true of Excel and of plain CSV files: Excel stops at about a
million rows and a CSV has to be read whole. Parquet with DuckDB is neither.
It is a real database format and a real database engine, built for hundreds
of millions of rows, read in columns, in one file, without a server. The
59 million minute bars already sit in it on his PC and were checked against
NSE's file across 167,717 contract-days (§2.15.8). "Not hosted" is not
"not a database".

**WHAT THE BACKTESTER CHAT MUST BRAINSTORM WITH HIM, before building anything
on this.** He said: "the backtest builder needs to talk to me about it, do a
brainstorm on this, and make me understand as well how everything will
work, including the backup system."

- **How the history is stored and queried**, in plain English: the files,
  the DuckDB store, what a query looks like to him, what the recorder adds
  each afternoon, how a morning gap is backfilled.
- **The backup system, end to end.** His wish: **"I want backup to go in my
  vault in the Second Brain."** Recommendation to put to him: the
  terminal's RECORD (trades, journal, results: a few megabytes) is backed
  up nightly into the vault under `00 - Developer Logs/Backups/` or beside
  it, where Obsidian can see it and Drive keeps it. The MARKET HISTORY
  (631 MB and growing) is backed up to the Google bucket, and if he wants a
  Drive copy too it goes in a Drive folder BESIDE the vault, not inside it,
  because a large binary folder inside the vault slows Obsidian and its sync
  and gains nothing. He decides.
- **What "loaded" means for `ROADMAP.md` gate 7** once the Postgres wording
  goes, so the gate is still a condition proven on the running system.
- **What the desk reads from the history** (§3 milestone 4 of the roadmap,
  "results feed the desk") and how the live site, which cannot see his PC,
  gets a backtest result: a small results table in Supabase pushed from his
  PC, the same pattern as the outbox and the vault mirror.
- **The move of the business apps** into the personal project: his own
  session, his timing, and what the backtester chat must not assume about
  it.

Then the backtester chat rewrites §2.15.6 with him and records his decisions
here, in this section, dated.

---

#### 2.19a THE BRAINSTORM HE ASKED FOR, IN PLAIN ENGLISH. 2026-09-12.

**He asked to be made to understand how all of this works, including the
backups. Every figure below was read off his own machine and his own Google
account on 2026-09-12 afternoon, not copied from an earlier note.**

**1. WHAT IS ACTUALLY ON HIS PC, AND WHERE.**

`data/history/` holds four years of market history as **Parquet files**. Parquet
is a file format for tables, the way `.xlsx` is a file format for tables, except
it stores each column separately and compressed. That is why four and a half
years of every option minute fits in 541 MB instead of tens of gigabytes.

| Folder | What is in it | Size |
|---|---|---|
| `data/history/nifty/` | The index itself, minute bars and daily bars | 18 MB |
| `data/history/options_eod/` | Every option's daily row from NSE, one file a year | 73 MB |
| `data/history/options_1m/` | Every option's minute bars from FYERS, from Feb 2024 | 541 MB |
| `data/history/vix/` | India VIX, added 2026-09-12, two sources | new |

**2. WHAT DUCKDB DOES, AND THE THING HE HAS PROBABLY MISUNDERSTOOD.**

DuckDB is a database engine that runs inside a program on his PC rather than on a
server. **The important part: the 630 MB of history does NOT live inside the
DuckDB file.** DuckDB reads the Parquet files where they already sit. There is no
loading step and no second copy.

`data/options_cache.duckdb` exists and is only **10.5 MB**. What is actually
inside it today, counted 2026-09-12:

| Table | Rows |
|---|---|
| `options_history` | 36,998 |
| `nifty_daily_bars` | 22 |
| `realized_vol_cache` | 10 |

**So the DuckDB file is a small working scratchpad, and the Parquet files are the
real archive.** A query looks like one sentence naming the files, and it reads
the 59 million minute bars without any of them being imported first. That is why
§2.19 point 2 says this is faster on his PC than a hosted database would be over
the network: nothing travels.

**3. WHAT THE RECORDER ADDS EACH AFTERNOON.**

The recorder is a small program in Google's data centre, woken **every minute
from 09:00 to 15:59 on weekdays** by Cloud Scheduler `swayam-recorder-schedule`.
Each time it wakes it reads the live option chain for two expiries, computes
implied volatility and the four Greeks, and appends the rows to a file for that
day in `gs://swayam-capital-options-data`.

Measured 2026-09-12, the bucket holds 6 objects and 11.9 MB. The daily files are
growing as it records more of the session: 0.3 MB on 9 September, 1.3 MB on 10
September, 4.4 MB on 11 September.

**What the recorder has that the historical files do not: the real bid and the
real ask.** FYERS' historical candles carry open, high, low, close and volume and
nothing else. So the recorder is the only source that can ever tell the
backtester what a spread actually cost, which is why §2.15.6 calls the modelled
spread the single most likely way a backtest of his flatters itself.

**4. HOW A MORNING GAP IS BACKFILLED, AND WHAT IS HONESTLY NOT AUTOMATED.**

The recorder **captures the afternoon only.** On 2026-09-09 every call from 09:15
to 13:25 failed with `Please provide valid token`, and it started working the
minute he refreshed by hand. He is asleep at 09:15. §2.10.

The gap is recoverable, because **FYERS serves minute candles for an option
contract once that contract has expired.** So every morning the recorder missed
can be filled in later from FYERS, at minute resolution, for free, using
`scripts/load_expired_options.py`.

**⚠️ Stated plainly because it would otherwise be assumed: that backfill is not
scheduled.** It is a command somebody runs. Nothing wakes up and repairs
yesterday's morning. The data is recoverable; the recovery is manual. He should
decide whether that becomes a weekly job or stays a thing done before a backtest
needs those days.

**5. THE BACKUP SYSTEM, END TO END. Two halves, an hour apart, both verified
running on 2026-09-12.**

| | Cloud half | Local half |
|---|---|---|
| What runs it | Cloud Scheduler `swayam-nightly-backup-schedule` | Windows Task Scheduler, task **"Swayam nightly local"** |
| When | **02:00 IST**, every day | **03:00 IST**, every day |
| Where it runs | Google's data centre, whether his PC is awake or not | His PC, because the vault and `data/history` only exist there |
| What it protects | The database: trades, journal, results. `gs://swayam-backups/supabase/`, 5.2 MB | Copies the newest database backup **into his vault**, keeping the newest thirty; syncs `data/history` to `gs://swayam-backups/history/`, only the files that changed |
| Proof, 2026-09-12 | Job enabled | **Last run 12-09-2026 03:00:00, result 0, next run 13-09-2026 03:00. Zero missed runs** |

**The one-hour gap between them is deliberate and must not be closed.** The local
half copies the newest backup out of the bucket. If both started at 02:00 the
local half would race the cloud half and copy the previous night's file while
reporting success.

**The history copy in the bucket, counted 2026-09-12:** 160 files, 661 MB by
bytes, which is the 630 MiB he was told. Newest push 2026-09-11 20:20 UTC, which
is 2026-09-12 01:50 IST. **His statement that it is synced nightly is correct and
was checked, not assumed.**

**His wish, already honoured:** "I want backup to go in my vault in the Second
Brain." The record does go to the vault. **The market history deliberately does
not**, and that recommendation stands: 661 MB of binary files inside an Obsidian
vault slows Obsidian and its Drive sync and gains nothing, because the bucket
copy already exists. If he wants a Drive copy of the history it goes in a folder
**beside** the vault, not inside it.

**6. WHAT IS STILL OPEN IN THIS SECTION, and none of it is urgent.**

- **§2.15.6 still describes four `swayam_*` Postgres tables for the history.**
  §2.19 point 3 overturned that in favour of Parquet and DuckDB, and the roadmap
  was already edited with his yes. **Rewriting §2.15.6 is still owed**, and it is
  this chat's job with him.
- **What "loaded" means for `ROADMAP.md` gate 7** now that Postgres is gone from
  the answer. Recommendation to put to him: the gate is met when a query against
  the Parquet files returns a priced structure for a named past day, proven on
  his machine, rather than when rows exist in a table.
- **How a backtest result reaches the live site**, which cannot see his PC. The
  recommendation is a small results table in Supabase pushed from his PC, the
  same pattern as the journal outbox and the vault mirror. **Not started.**
- **Moving the two business apps** into his personal Supabase project is his own
  session at his own timing, and nothing here assumes it has happened.

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
| 2026-09-09 | Recorder writes real spot, implied volatility and Greeks | Deployed revision `swayam-recorder-00003-kuq`, dry-run at 00:05 IST: 164 rows, expiries 2026-09-15 and 2026-09-29, spot `23431.5`, 151 rows with implied volatility and delta, 164 with change in open interest, `wrote_anything: false` |
| 2026-09-09 | The recorder's Black-Scholes matches the terminal's | `tests/cloud/test_recorder_bs_math.py`: price and all four Greeks agree with `vollib` to better than 1e-9 across 1,080 cases |
| 2026-09-09 | Unknown values are NULL, never zero | `open`, `high`, `low`, `settle_price`, `turnover_inr` all null through a Parquet round trip, as `float64` not the `null` type |
| 2026-09-09 | Two expiries recorded, so a calendar can be valued | The far expiry carries more vega and slower decay than the near one, asserted on a captured live chain |
| 2026-09-09 | The recorder refuses to record on an NSE holiday | 2026-11-10 Diwali refused mid-session; 2026-11-09 accepted |
| 2026-09-09 | A deployment can be proved out of hours without writing | `?dry_run=1` returns the counts and writes nothing; the bucket held 2 objects before and after, unchanged since 10:00:02Z |
| 2026-09-09 | The scheduler path is unchanged | A POST with no query string at 00:06 IST returned `skipped, before market open` |
| 2026-09-09 | FYERS serves expired option candles, free, back to Feb 2024 | `/data/history/fno/expired/historical-data` returned 1-minute candles for 28 Mar 2024 and every expiry since; 25 Jan 2024 and earlier return `no_data`. §2.15 |
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
| 2026-09-10 | **The first send through the ticket, on the live market** | Condor at 13:45:49 IST, four legs at the ask and the bid, spot and margin stored, 200 in the live log |
| 2026-09-10 | **Rule 4 tested against a real margin-used figure, first time ever** | ₹1,03,926 of ₹5,54,961 on the desk |
| 2026-09-10 | One by one keeps one trade | 03a1b63d: two legs, sequence 1 and 2, one id |
| 2026-09-10 | The chain builds a structure the ticket sends | 8030ed03, both legs from the book |
| 2026-09-10 | The close fills against the live book | Two spreads, every leg at the bid or ask, side and traded price recorded |
| 2026-09-10 | The recorder records real numbers | 4,428 rows, spot 23,418 to 23,443, IV and Greeks on 4,079 rows |

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
