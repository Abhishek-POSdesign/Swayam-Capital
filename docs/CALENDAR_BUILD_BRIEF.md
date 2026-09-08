# CALENDAR BUILD BRIEF — multi-expiry valuation

> Written 2026-09-08. **The next job after round 2.**
>
> Read `docs/SWAYAM_START_HERE.md` for where things live and `docs/PLAN.md` for
> the order of work. `docs/UI_BUILD_BRIEF_ROUND_2.md` is the job running now.
> **This file is the job after it.**
>
> Ten of Abhishek's twenty-one historical trades are calendars. On 2026-09-08 he
> said he uses them more than half the time and that they were profitable for
> him. This is the largest gap between what he actually trades and what the
> terminal supports.

---

## 0. THE RULES YOU ARE JUDGED ON

1. **NO FABRICATED VALUES.** Every number is real from FYERS or the database, or
   it says `unavailable` with a reason. **This brief is the one place in the
   repository where a modelled number is unavoidable**, because a calendar's
   result depends on what the far leg is worth on a future date. The rule is
   therefore not "never model" but **"never model silently"**: every modelled
   figure carries the assumption that produced it, in words, on screen.
2. **NEVER CLAIM SOMETHING WORKS THAT YOU HAVE NOT RUN.** Say plainly in the
   pull request what you ran and what you could not.
3. **DO NOT BREAK ANYTHING THAT WORKS TODAY.** Single-expiry positions must
   produce byte-identical numbers before and after this work. That is a test,
   not a hope. See §7.
4. **Do not merge.** Open the pull requests and stop. He clicks Merge.

---

## 0b. HOW HE ACTUALLY TRADES A CALENDAR. His own words, 2026-09-08.

He said this himself when asked, and it should never be asked again.

**Why he puts one on.** "The calendar with far expiry is for the hedge and for
the margin benefit, and the current expiry is to gain theta, so the near expiry.
It is always for near expiry." The far leg is not a trade of its own. It is
there to cap the short and to reduce the margin the broker demands.

**When he gets out.** "My target is to square off the calendar before near
expiry." He is not a morning trader. With a Tuesday expiry he closes **Monday
before the close**, or **the Friday before** if he is already well in profit and
can see it turning, or if he is already in a loss.

**Two consequences for anyone building this.**

1. Every figure that gates money is measured to the **near** expiry, which is
   decision 1 below. His exit behaviour is the reason it is correct, not a
   simplification.
2. **A calendar spread gets NO margin benefit on the day its near leg expires.**
   SEBI removed it for index derivatives from February 2025; the circular of
   February 2026 extended the same rule to single stocks. The requirement can
   roughly double on that last day. **His practice of closing the day before
   already avoids this**, which is worth telling him rather than assuming he
   knows. The terminal does not model it today. If a margin projection is ever
   shown for a calendar held into its near expiry day, it must not show the
   hedged figure.

---

## 1. HIS DECISIONS. DO NOT RELITIGATE ANY OF THESE.

Recorded verbatim in intent from the session of 2026-09-08.

1. **Risk is measured at the NEAR expiry date. Never the far expiry.**
   He exits the whole trade at or before the near expiry and never rides the far
   leg to its own expiry. Measuring the worst case at the far expiry would be
   measuring a risk he does not take. His words: "we should carry the risk we
   assume for the near expiry, not the far expiry, because we are not taking it
   for the far expiry."
2. **No early-exit percentage.** He was asked whether the terminal should model
   his habit of closing once most of the sold premium has decayed. He declined:
   "We cannot decide 70%, 80%, or 50%. Those market dynamics we cannot predict.
   We only know what is fixed: the expiry date." **Do not build a decay-based
   exit trigger. Everything is calculated to the near expiry date.**
3. **A calendar is a swing trade and may be carried overnight.** "Calendar is a
   swing trade. It's not an intraday trade, so it will be allowed to carry
   overnight." Today the system forces every calendar to be treated as unhedged
   and refuses the carry. That must change.
4. **The payoff graph holds the far leg's volatility at today's measured level**,
   matching Sensibull, because that is the picture he is used to reading. The
   graph says what it assumed.
5. **How calendars fit his method** — entering ahead of the budget, RBI or Fed
   announcements — is **explicitly deferred**. "That is a discussion for some
   other day." Do not build method or signal logic here.

---

## 2. THE PROBLEM, PRECISELY

A calendar sells a near-expiry option and buys the same strike in a later
expiry. On the day the near leg dies it settles to intrinsic value. **The far
leg does not.** It is still alive and still carries time value, and what it is
worth depends on a pricing model plus an assumption about implied volatility.

### What is already correct — do not rebuild it

| Thing | Where | State |
|---|---|---|
| Per-leg expiry on the data model | `options_math/models.py:49` `Leg.expiry_date` | **Correct.** The shape is ready |
| A calendar spread constructor | `options_math/strategies.py:183` `calendar_spread()` | **Exists** |
| A preset endpoint accepting a far expiry | `api/routes/strategy.py:127-163` | **Exists**, takes `far_expiry` |
| Per-leg time in the payoff curve | `options_math/payoff.py:235` | **Correct.** Values each leg by its own remaining days |
| Per-leg time in point valuation | `options_math/payoff.py:315-318` `pnl_at_spot()` | **Correct** |
| Rule 2's arithmetic | `rule_engine/carry_risk.py:210-213` | **Correct.** It calls `pnl_at_spot`, which is per-leg aware |
| Hedge geometry's reasoning | `rule_engine/hedge_geometry.py:42-48` | **Correct and honest.** It says a far leg does not cap a short leg *at the short leg's own expiry as a pure payoff*. That was true before valuation existed |

### What is wrong

| Thing | Where | Why it is wrong |
|---|---|---|
| At-expiry P&L | `payoff.py:25-39` `_leg_expiry_pnl` / `_spread_expiry_pnl` | Uses **intrinsic value for every leg**, i.e. assumes all legs die on the same day. False for a calendar |
| Max profit and max loss | `payoff.py:147` `compute_max_profit_loss` | Built on the above, so wrong for a calendar |
| Breakevens | `payoff.py:58` `compute_breakevens` | Built on the above |
| Rule 3, black swan | `api/routes/validation.py`, via `compute_max_profit_loss` | Inherits all of it |
| Rule 2, overnight carry | `validation.py:340` `hedged=geometry.hedged and not geometry.is_multi_expiry` | **Forces every calendar to be unhedged**, so `carry_risk.py:190` returns "no ceiling" and the carry is refused. Contradicts his decision 3 |
| Execution | `validation.py:360-365` | Blocks every multi-expiry structure outright |
| The browser's maths | `web/src/modules/options-math.js:122` `pnlAt(legs, S, T, opts)` | **One `T` for the whole position.** The browser has no concept of per-leg expiry at all |
| The browser's leg table | `web/src/pages/strategy-builder.js` `renderLegs()` | The expiry cell is `readonly`, driven by one global dropdown |

---

## 3. THE VOLATILITY ASSUMPTION, AND WHY IT IS NOT INVENTED

He was asked how to handle this and answered: "I cannot answer. You need to do
research for this." The research was done on 2026-09-08. Findings:

- **Every retail platform, Sensibull included, assumes the far leg holds today's
  implied volatility until the near expiry.** Sources are consistent that this
  single assumption decides more of the projected profit than strike selection
  does, and that the maximum gain on a calendar therefore cannot be known in
  advance.
- **The same sources flag it as the weak point, specifically around events**,
  where the projection is optimistic because volatility collapse is not
  modelled. That is exactly when he trades calendars.
- **A volatility shock does not hit both expiries equally.** The accepted
  trader's heuristic is that a term-structure move decays with the square root
  of time, so a shock of `x` at the near expiry moves the far expiry by roughly
  `x × sqrt(T_near / T_far)`. This is a documented empirical heuristic, not an
  invention.

### The three numbers to produce

**1. The payoff graph — today's measured volatility, held.**
Real, read from the live chain, per strike. Matches Sensibull. It must print
the assumption: "assumes the far leg's volatility stays at 13.2%".

**2. The two rules that gate money — a stressed volatility, measured.**
Do **not** pick a stress figure. Measure it:

- Take the horizon: calendar days from today to the **near** expiry.
- Read **India VIX history** over that horizon from the existing real source.
  `/api/market/vix/history` already serves it from the NSE bhavcopy, and
  `services/nifty_snapshot.py` already consumes VIX.
- Compute the distribution of VIX changes over a rolling window of that length,
  and take a **conservative percentile at both tails** (the 5th and the 95th are
  a sensible default; state whichever you use).
- Apply that proportional change to the **near** leg's volatility, and propagate
  it to the far leg by the square-root-of-time rule above.
- **Value the position at the near expiry under both the down-shock and the
  up-shock, and use the worse answer.** Two-sided, so a reverse calendar
  (selling the far leg) is covered by the same machinery.
- India VIX is a 30-day implied volatility on NIFTY, so it is a **proxy for the
  level of the surface, not for one strike's volatility**. Say so in the note
  that accompanies the number. Do not present it as the strike's own measured
  volatility.
- **If VIX history is unavailable or too short, the rule returns `unavailable`
  with that reason. It does not fall back to a constant.** This is the whole
  no-fake-data rule and there is no exception for it here.

**3. A volatility shock he drives himself.**
The desk already has an editable implied volatility per strike
(`strategy-builder.js` `renderIvs()`, `onIvInput`, `onIvClick`). Extend that into
a single slider that shifts the whole surface up or down by a percentage, so he
can stress-test by hand. A volatility he types is his and is never overwritten,
which the existing code already respects via `ivSource`.

---

## 4. PR 1 — THE BACKEND. Can be built immediately.

**No conflict with the round 2 work**, which is explicitly forbidden from
touching `src/swayam/options_math/` and `src/swayam/rule_engine/`. Start here.

### Step 1 — Value the position at an arbitrary date

New function in `src/swayam/options_math/payoff.py`, beside the existing ones.

```
value_at_date(spread, spot, as_of, iv_for_leg) -> float
```

- A leg whose `expiry_date` is on or before `as_of` → **intrinsic value**.
- A leg expiring after `as_of` → **Black-Scholes** with `(expiry_date - as_of)`
  remaining and the volatility supplied for that leg.
- Reuse `engine.py`'s pricing. Do not write a second Black-Scholes.
- **Returns `None` if any surviving leg has no volatility.** It must never
  substitute one.

`pnl_at_spot()` at line 285 already does most of this per leg. Prefer extending
or generalising it over duplicating it.

### Step 2 — Worst case, best case and breakevens at the near expiry

- Add `near_expiry(spread)` returning the earliest `expiry_date` across legs.
- `compute_max_profit_loss` and `compute_breakevens` gain an evaluation date.
  **When every leg shares one expiry, behaviour is unchanged**, which §7 tests.
  When expiries differ, they sweep spot at the **near** expiry using step 1.
- Sweep the same spot range the existing code uses. Do not narrow it.
- `loss_is_unbounded()` at `payoff.py:135` counts net calls and puts and is
  already correct for a calendar (net zero of a type is not unbounded). Leave it.

### Step 3 — The measured volatility stress

New module, `src/swayam/options_math/vol_stress.py`.

- `measured_iv_shock(days_to_near_expiry)` → `(down_pct, up_pct, provenance)`
  from real India VIX history, per §3. `provenance` names the window, the
  percentile and the number of observations, and travels with the answer to
  the screen.
- `propagate_to_expiry(shock_pct, t_near_years, t_far_years)` → the
  square-root-of-time scaling.
- Raise a typed error when history is insufficient. **No constant fallback.**

### Step 4 — Rule 3 uses the near expiry

In `src/swayam/api/routes/validation.py`, the black-swan check takes its worst
case from `compute_max_profit_loss` evaluated at the near expiry, under the
worse of the two shocks from step 3.

The note beside the number must state the assumption in his language, for
example: "worst case on 25 September, the day your near leg expires, assuming
the far leg's volatility falls to 11.4%. Measured from 20-day India VIX moves
over the last year, 5th percentile."

**Do not change the arithmetic of the other three rules.** Rule 1 and rule 2
already value per leg correctly.

### Step 5 — A calendar may be carried overnight

- `validation.py:340` currently reads
  `hedged=geometry.hedged and not geometry.is_multi_expiry`. **Remove the
  multi-expiry clause.** Once the far leg is valued at the near expiry it does
  cap the short leg, and his decision 3 says calendars carry.
- `rule_engine/hedge_geometry.py:122-127` returns an uncovered reason for a long
  leg in a different expiry. Change it from "does not cap this leg's loss" to a
  **capped-under-assumption** result: the structure is hedged, and the reason
  names the assumption. The module docstring at lines 42-48 explains the old
  behaviour; update it in the same commit so the file does not contradict itself.
- **A diagonal is not automatically a calendar.** Different strikes as well as
  different expiries still cap, but only if the long leg's strike protects the
  short. Keep the existing strike-coverage logic and add the expiry handling
  around it; do not replace it.

### Step 6 — Lift the execution block

`validation.py:360-365` blocks every multi-expiry structure. Remove the block and
replace it with a **warning that names the assumption**, so he can execute a
calendar and still sees plainly which figure was modelled.

### Step 7 — The event warning

When the near leg's implied volatility sits materially above the far leg's,
that gap is event premium and it is the exact condition where the payoff chart
flatters the trade. Return a flag and a sentence when both are true:

- the near leg's volatility exceeds the far leg's by a stated margin, and
- a **high-importance macro event** falls before the near expiry. The events are
  already in the database and already on Home via `api.getMacroEvents`.

Wording: "Your near leg is priced for an event on 19 September. The projection
above assumes the far leg's volatility does not fall afterwards. It usually
does." **This is a warning, not a block.** Entry is never blocked.

---

## 5. PR 2 — THE SCREEN. Only after round 2 has merged.

**Both touch the same leg table.** `docs/UI_BUILD_BRIEF_ROUND_2.md` step 15
rebuilds the leg row grid and swaps the lots input for a dropdown. Do not start
this until that is on `main`, or you will fight it.

### Step 8 — Per-leg expiry

Today the expiry cell in each leg row is `readonly` and driven by one global
dropdown, because **his round 1 decision 2 was one expiry and one lot multiplier
for all legs.** That decision is **not reversed**. The global dropdown stays and
still sets every leg, which is what he uses for every single-expiry structure.
What changes is that the cell becomes a dropdown he *can* override per leg.

- `strategy-builder.js` `renderLegs()` — the readonly expiry input becomes a
  select of the available expiries.
- Changing the global dropdown still sets all legs, exactly as now.
- Changing one leg's expiry reprices **only that leg** and clears any implied
  volatility that came from the old expiry's price. That rule already exists in
  `repriceLeg()` and must keep working: a volatility he typed is his and
  survives; an implied one belongs to the price it came from.

### Step 9 — The browser maths learns about per-leg expiry

`web/src/modules/options-math.js` `pnlAt(legs, S, T, opts)` takes one `T` for the
whole position. Give each leg its own remaining time, computed from its own
expiry, and add a browser-side `valueAtDate` mirroring §4 step 1.

`maxLossProfit()` and `breakevens()` then evaluate at the **near** expiry.

### Step 10 — The payoff graph

- The black line stops being "at expiry" and becomes **"at your near expiry"**
  whenever the legs span more than one date, with the far leg valued rather than
  expired. Relabel the legend accordingly.
- Print the volatility assumption under the chart.
- **The drag behaviour and the two sliders must not change.** He praised them
  unprompted. Round 2 step 17 already adjusts the axis and the date slider; this
  work must not touch either again.

### Step 11 — The volatility slider

One slider that shifts the whole surface by a percentage, feeding the same
recalculation as the per-strike editor. Reset returns to measured values.

### Step 12 — Calendar and diagonal presets

Add to `PRESETS`: call calendar, put calendar, call diagonal, put diagonal, and
double calendar. Each needs a near and a far expiry, so the preset loader must
place legs in two expiries. **Strike offsets only, never a premium.**

`api.getStrategyPreset` already accepts `far_expiry` and the server already
builds `calendar_spread`; prefer the server's construction over rebuilding it.

---

## 6. WHAT IS NOT IN SCOPE

- **His calendar method.** Deferred by name. No signal logic, no event-timing
  advice, no entry suggestions.
- **An early-exit trigger based on decay.** He refused it explicitly. See §1.2.
- **Backtesting calendars.** That needs the options recorder to have actually
  recorded something. It has never once succeeded; the fix is round 2 step 3.
- **A volatility surface model.** One volatility per strike per expiry, measured
  from the traded price, is the level of sophistication this needs.

---

## 7. THE TEST THAT MATTERS MOST

**Every single-expiry position must produce identical numbers before and after
this work.** Ten of his trades are calendars; eleven are not, and the rules that
govern real money run through the same code.

- Snapshot max profit, max loss, breakevens and all four rule verdicts for a
  bull call spread, a bear put spread, an iron condor, an iron butterfly, a short
  straddle and a naked short call, **before** any change.
- Assert them unchanged **after**.
- Then add calendar cases: a call calendar priced from a real chain, a put
  calendar, and a diagonal.
- Assert that a calendar with no volatility available on the far leg returns
  `unavailable` and **never a number**.
- Assert that a short straddle is still unlimited and still refuses the carry.

Do not weaken the two long-standing failures in `tests/api/test_market.py` and
`tests/test_notifications.py`. They pre-date all of this.

---

## 8. HOW HE WORKS

- **Not a developer.** Plain English, no code to approve, a recommendation
  rather than a menu. English, not Hinglish. He speaks his prompts, so an odd
  word is transcription rather than intent.
- He trades between 1 and 2:30 pm IST, mostly swing and positional.
- **Never work on `main`.** Feature branch, pull request, he clicks Merge. The
  pull request is his only revert button.
- **Work in the primary folder**, never a git worktree. The virtual environment
  is an editable install pointing at it.
- **Merge one pull request, wait for the green tick, then merge the next.**
  Two at once races two deploys and the wrong one can win.
- **Overstating anything is worse than saying it is not done.**

---

*Real-money trading remains code-blocked by absence. There is no order-placement
code anywhere in this repository, and nothing in this brief adds any.*
