# BUILD BRIEF ROUND 2 — his feedback on the rebuilt pages

> Written 2026-09-08 for a **cloud session that runs unattended**. Everything you
> need is in this file. There is no human to ask.
>
> Read `docs/SWAYAM_START_HERE.md` for where things live and `docs/PLAN.md` for
> what happens after this. **This file is the job.**
>
> Supersedes nothing. `docs/UI_BUILD_BRIEF.md` was round 1 and is finished and
> live. This is round 2: what he said after using round 1 with the market open.
>
> Plain-English plan he approved:
> https://claude.ai/code/artifact/b99c1be3-8a29-4f54-af7c-a9917a449321

---

## 0. READ THIS FIRST. IT DECIDES WHETHER YOUR WORK IS ACCEPTED.

### The three rules you are judged on

1. **NO FABRICATED VALUES.** Every number rendered must come from an API
   response or say `unavailable` with a reason. Never a fallback constant,
   never a plausible placeholder, never `|| 0`, never `|| 75`. This is the
   single most important rule in this repository. **This round exists partly
   because eight such constants are still in the backend and one of them
   reached him through the AI.** Do not add a ninth.
2. **NEVER CLAIM SOMETHING WORKS THAT YOU HAVE NOT RUN.** State plainly in the
   pull request what you ran and what you could not. An honest gap is welcome.
   An overstatement is not. He has burned days and real money on false status
   reports.
3. **DO NOT BREAK THE PAYOFF GRAPH.** He said unprompted that dragging it is
   "really smooth and properly readable" and that it is "a very good job".
   Step 17 changes only the x-axis ticks and the slider direction. The drag
   handler, the Black-Scholes maths and the two curves stay exactly as they are.

### What you must NOT do

- Do not merge anything. Open the pull requests and stop. **He clicks Merge.**
- Do not run anything that writes to the database. `tests/db_guard.py` cages the
  test suite because there is no staging project. Do not weaken, bypass or
  remove that guard.
- Do not use a git worktree. The virtual environment is an editable install
  pointing at the primary folder, so a worktree silently tests the wrong tree.
- Do not modify `src/swayam/rule_engine/`, `src/swayam/options_math/payoff.py`,
  `engine.py` or `models.py`, or the arithmetic inside
  `src/swayam/api/routes/validation.py`. The backend risk model is settled and
  correct. Step 7 fixes a *reachability* bug in `realized_vol.py` and step 8
  changes only what the frontend sends. Nothing else in the risk path moves.
- Do not redesign the AI chat. Step 1 corrects facts in its persona; step 14
  changes the size of an attached image. Its layout and behaviour stay.
- Do not introduce purple, lilac or violet. Standing rule, litigated, closed.
- Do not make So Far Today fire on page load. Manual button, 60-minute cache,
  daily cap of 8. Breaking that costs him real money.
- `node --check` is not verification. It has passed files the browser rejected.

---

## 1. WHO THIS IS FOR

Abhishek Sikka. **Not a developer.** He trades NIFTY options, paper for now,
restarting after a break of several months, and intends to trade real money
through this terminal.

**He arrives at his desk between 1 and 2:30 pm IST and he is mostly taking
swing and positional trades, not intraday.** He said this explicitly on
2026-09-08: "If I am coming on to trade at 2:30 pm, I will not be coming for
1 day or an intraday. I'll be coming for a swing or a positional trade, so I'll
be taking it for the next day." Step 8 exists because of that sentence.

**His four rules.** Every one is a percentage of his live FYERS balance, read
fresh each session, never a stored figure. Authority is
`docs/MY_TRADING_RULES_ONE_PAGE.md`, mirrored from his vault.

| # | Rule | Threshold |
|---|---|---|
| 1 | Running loss | 1% of live balance |
| 2 | Overnight gap, tested at 2x the average daily move | 2% |
| 3 | Black swan, worst case at expiry | 5% |
| 4 | Deployable margin ceiling | 2x cash equivalent |

**Entry is NEVER blocked**, including naked and half-built structures. Only
**carrying overnight** is gated, on two conditions: hedged, and inside the gap
test. **The readiness form is a journal with zero power.**

**The NIFTY lot is 65**, resolved server-side from the FYERS contract master.
Never hardcode 75.

---

## 2. WHAT IS BROKEN, AND HOW IT WAS PROVEN

All five were confirmed against the running system on 2026-09-08. You do not
need to re-prove them. They are here so you understand what you are fixing.

### 2.1 The rules crash about half the time — DuckDB, two workers

`Dockerfile` runs `gunicorn --workers 2`. `compute_realized_vol()` opens an
embedded DuckDB file at `/app/data/options_cache.duckdb`. DuckDB takes an
exclusive file lock. Worker one wins it; worker two raises on every rule check.

Live evidence, `/api/strategy/validate` on 2026-09-08:
`09:05:08 → 200`, `09:05:25 → 500`, `09:15:49 → 200`, `09:16:32 → 500`.

```
File "/app/src/swayam/api/routes/validation.py", line 122, in audit_strategy_rules
    ann_vol = compute_realized_vol(
File "/app/src/swayam/options_math/realized_vol.py", line 71
    conn = target_db.get_connection()
_duckdb.IOException: Could not set lock on file "/app/data/options_cache.duckdb":
Conflicting lock is held in /usr/local/bin/python3.11 (PID 2)
```

`data/` is gitignored (`*.duckdb`) and the Dockerfile never copies it, so the
file the container fights over is one it created empty at runtime. The Supabase
fallback at `realized_vol.py:113-131` is correct and **unreachable**, because it
sits after the line that fails.

### 2.2 Two of the four rules can never light up

- **Rule 2.** `validation.py:333` computes `carry` only when
  `planned_exit_date` is later than today. `strategy-builder.js`
  `refreshFromServer()` never sends that field, so `intraday` is always true and
  the panel always reads "not tested — this is an intraday position".
- **Rule 4.** `strategy-builder.js` `renderRules()` builds rule 4 with a
  hardcoded `'idle'` state. It never turns green or red.
- Neither rule is reached at all unless `fullyPriced()` is true, so one illiquid
  strike leaves all four blank with no explanation.

### 2.3 Nothing on either page refreshes

- `ws_manager.broadcast_spot()` exists and **is never called from anywhere**.
  `grep -rn "broadcast_spot" src/ --include=*.py` returns only its definition.
  The socket accepts a connection and answers ping with pong. No tick has ever
  been pushed.
- `home.js` has no timer of any kind. Ticker and NIFTY sidebar are frozen at
  page load.
- `strategy-builder.js` has one timer, `cronTimer`, and it only polls
  `detectNakedShorts` every 30 s. Spot and every leg price are fetched once.
- `main.js:429 pollSpot()` polls every 10 s but updates only the header pill and
  `this.builder`, a component the new pages do not use. That is why exactly one
  number on screen moves.

### 2.4 The AI is running the rule set deleted on 2026-09-07

He was told his risk cap was ₹8,500 while sizing a trade. `8,50,000 × 1%` is
that number; his live balance is about ₹9,71,000 and the real cap is ₹9,710.
In `src/swayam/ai/persona/trading_partner.py`:

| Line | What it says | What is true |
|---|---|---|
| 126, 357-362 | caps are a percentage of `swayam_config.margin_base_inr` | every cap is a percentage of the live FYERS balance |
| 94, 170 | blast radius is a 3% ceiling | 5% |
| 172-173 | there is an R:R minimum and target | deleted; no R:R floor exists |
| 73 | "Never override a RED readiness verdict" | readiness has zero power |

Note `trading_partner.py:415-421` already carries the corrected readiness
wording. Line 73 contradicts it. Both must agree.

### 2.5 The recorder is failing every minute, and the option chain endpoint lies about expiry

- **Recorder.** Invoked successfully every 60 s since this morning's IAM fix,
  and FYERS rejects every call with `Please provide valid token`. Because it
  runs each minute its container never goes cold, so it never re-reads the
  secret. Today's option chain data is being lost and is not recoverable. Same
  root cause as the dashboard's morning no-prices trap: `secretKeyRef` with key
  `latest` is resolved **once, at container start**.
- **Chain expiry.** `market.py:62` accepts an `expiry` query parameter, uses it
  only as a cache key, and calls `fyers_client.get_option_chain()` at line 81
  **without the `timestamp` argument**. FYERS returns the nearest expiry every
  time. The single-leg quote endpoint from `market.py:178` resolves the epoch
  from FYERS' `expiryData` correctly. Lift that pattern.

### 2.6 Eight invented constants

| File | Line | Constant |
|---|---|---|
| `services/nifty_snapshot.py` | 148 | put-call ratio `1.0` |
| `services/nifty_snapshot.py` | 216 | ATR `150.0` |
| `services/nifty_snapshot.py` | 219 | distance from 20-DMA `0.0` |
| `services/nifty_snapshot.py` | 230 | realised volatility `12.0` |
| `services/nifty_snapshot.py` | 234 | position in 20-day range `50.0` |
| `services/nifty_snapshot.py` | 476 | rollover `68.5` |
| `api/routes/market.py` | 618 | India VIX `0.0` |
| `api/routes/market.py` | 637 | VIX percentile `50.0` |

The first four render on his NIFTY sidebar. All eight become `None`, and the
frontend already renders `unavailable` for a null.

---

## 3. SHIP THIS AS TWO PULL REQUESTS

**Not one.** Branch off `main`, then:

- **PR 1 — "Real numbers, live prices, working rules"**: sections 4, 5 and 6
  below (steps 1 to 9). This is the release that lets him trade.
- **PR 2 — "The desk he wants to sit at"**: sections 7, 8 and 9 below
  (steps 10 to 21). Branch PR 2 off PR 1's branch so it does not conflict.

Put the reason in both PR bodies: **he must merge PR 1, wait for the green
tick, then merge PR 2.** Merging two within seconds races two Cloud Build
deploys and Cloud Run aborts the loser with `ABORTED: Conflict for resource`.
That happened on 2026-09-08 and the winner carried a documentation change while
the loser carried the new pages, so the site came back with the old interface
and nothing said so.

---

## 4. PR 1 · BAND P0 — nothing on screen may be invented

### Step 1 — Rewrite the AI trading partner's facts

`src/swayam/ai/persona/trading_partner.py`

- Line 126 and lines 357-362: stop reading `db.get_margin_base_inr()`. Take
  capital from `get_capital()` in `src/swayam/api/routes/validation.py`, the
  same source Home and the risk gate use. If it raises `CapitalUnavailable`,
  the context must say the balance is unavailable. **It must never fall back to
  the config table.**
- Line 94 and line 170: black swan is **5%**, not 3%.
- Lines 169-173: express every cap as a percentage of the **live balance**, and
  **delete the R:R minimum and target lines entirely**. There is no reward-to-
  risk floor any more.
- Line 73: delete "Never override a RED readiness verdict." Replace with the
  wording already at lines 415-421: readiness is a journal he fills in himself,
  it has zero power over trading, and the AI must never tell him it limits him.
- Grep the whole repo for `margin_base_inr` afterwards. No read path may remain
  outside a migration file.

**Verify:** ask the live AI chat "what is my running-loss cap today?" It must
answer with 1% of the live FYERS balance and name FYERS as the source.

### Step 2 — Remove all eight invented fallbacks

Every constant in the table at §2.6 returns `None` instead. Update the response
models to allow null where they do not already.

Also **delete `web/src/components/nifty-snapshot-card.js`**. It is the only
place `rollover_pct` was ever drawn and no page mounts it any more. Check
`web/src/main.js` and both page files for imports before deleting.

**Verify:** one unit test per field asserting `None` when the input series is
too short. Load Home against the real backend and confirm no number changed on
a normal trading day.

### Step 3 — Read the FYERS token at request time

`src/swayam/fyers_client.py` and the recorder at **`cloud/recorder/`** (`main.py`, `fyers_recorder.py`, `config.py`). It is NOT under `functions/`; that directory holds the backup and digest jobs.

Fetch the `latest` version from Secret Manager on demand with a short
in-process cache (60 s is fine). Keep `FYERS_ACCESS_TOKEN` from the environment
as the local-development path, so nothing changes for local work.

This is one fix for two daily failures: the dashboard showing "no live price"
all afternoon after an 08:30 token refresh, and the recorder failing every
minute today.

**Proof, if you want it.** `swayam-recorder` is still on revision
`swayam-recorder-00001-baf`, created 2026-09-03 22:49 UTC and never redeployed.
Its token is a `secretKeyRef` with key `latest`. The secret has had four
versions since, the newest at 2026-09-08 08:31 UTC. The container resolved
`latest` once, on 3 September, and has served that dead token ever since.

**The recorder does not deploy from the `main` trigger.** `swayam-main-deploy`
builds `swayam-dashboard` only. Say so in the pull request body: after this
merges, `swayam-recorder` needs its own deployment from `cloud/recorder/`
before it will record anything.

**Verify:** refresh the token, wait one minute, and confirm the recorder writes
an object into `gs://swayam-capital-options-data` with **no redeploy**. The
bucket is empty today, so one object proves it.

---

## 5. PR 1 · BAND P1 — prices that actually move

### Step 4 — Push real ticks over the socket that already exists

- `src/swayam/api/main.py`: start one background task in the lifespan handler
  that polls `fyers_client.get_nifty_spot()` every 2 s during market hours
  (Mon-Fri, 09:15-15:30 IST) and calls `ws_manager.broadcast_spot()`.
- **Guard it so only one of the two Gunicorn workers runs it.** A file lock or
  an advisory lock is fine. Two workers both polling doubles the FYERS calls
  for no benefit.
- Outside market hours the task sleeps. It must not spin.
- `web/src/modules/ws-client.js` is already written and already connects.
  Add one thing: if no frame arrives within 10 s, fall back to a 3 s REST poll,
  so a socket problem degrades instead of freezing the screen.

**Verify:** open the desk during market hours and watch the spot change without
touching anything. Confirm in the browser console that **frames arrive**, not
merely that the socket opened. That distinction is the whole point of this step.

### Step 5 — Refresh everything that claims to be live

- `web/src/pages/home.js`: add an interval that re-runs `loadSnapshot()` and
  `loadDaily()` and re-renders the ticker. 15 s is right. **Clear it in
  `destroy()`** or navigating away leaks a timer.
- `web/src/pages/strategy-builder.js`: subscribe to the tick stream in `init()`
  so `this.spot` follows it, and add a re-quote loop over `activeLegs()` every
  5 s reusing the existing `repriceLeg()`.
- **A price he typed himself is never overwritten.** `leg.priceSource ===
  'your own limit price'` marks those; skip them in the re-quote loop.
- Flash each changed value green or red for about 400 ms. Respect
  `prefers-reduced-motion`.
- Every panel carries the time it was last read, in IST.

**Verify:** load a bear put spread and leave it alone. Both leg prices must
change within a minute of a real market move, and the metric row must recompute.

### Step 6 — Market breadth and volume, actually fetched

`src/swayam/services/nifty_snapshot.py:451-453` currently hardcodes `advances`
and `declines` to `None` and nothing has ever asked FYERS for them.

- Quote the 50 NIFTY constituents in one FYERS call and count how many are up
  against down. The list lives in a new `data/nifty50_constituents.json` with an
  `as_of` date, so a stale list is visible rather than silent.
- **Volume** comes from the front-month NIFTY futures contract and the row must
  be labelled **"Futures volume"**. The index itself has no volume; a row
  reading plain "Volume" beside an index price would be its own small lie.
  `home.js` currently hardcodes `this._kv('Volume today', null)`.

**Verify:** the two counts add to 50 on a normal session. If either call fails
both stay `unavailable`.

---

## 6. PR 1 · BAND P2 — the four rules answer, every time

### Step 7 — Stop the two workers fighting over a database file

`src/swayam/options_math/realized_vol.py`, `compute_realized_vol()` from line 71.

Hoist the Supabase branch (currently lines 113-131, reading
`swayam_nifty_daily_bars`) **above** the DuckDB connection, or wrap
`target_db.get_connection()` so an `IOException` is treated as "no local
database here" and falls through instead of raising. Either shape is fine. The
requirement is that a locked or absent DuckDB file can never fail the request.

Keep DuckDB as the preferred source when it opens cleanly, because local
development uses it.

**Verify:** call `/api/strategy/validate` twenty times in a row against the live
site with a realistic two-leg spread and confirm twenty `200`s. The same test
today returns roughly half `500`s.

### Step 8 — Assume he will carry the position overnight

`web/src/pages/strategy-builder.js`, `refreshFromServer()`.

- Send `planned_exit_date` as the **next trading day** by default, so the server
  computes `carry` and rule 2 has an answer. `data/nse_holidays_2026.json`
  exists for the next-trading-day calculation.
- Add a small two-state control near the rules reading **"Carrying overnight"**
  and **"Closing today"**, defaulting to carrying. Closing today sends no
  planned exit date and the panel says rule 2 was not tested because he is
  closing before the bell.
- Word rule 2's result as **"if you carry this overnight"** so it is never
  mistaken for something that already happened.
- No backend change beyond wording. `validation.py:333` already branches
  correctly.

**Verify:** a short straddle must show rule 2 as Unlimited and refuse the carry.
An iron condor must return a rupee gap loss against 2% of the live balance.

### Step 9 — Rule 4 must pass or fail, and a missing price must explain itself

`web/src/pages/strategy-builder.js`, `renderRules()` and `refreshFromServer()`.

- Rule 4 currently hardcodes `'idle'`. Compare margin needed
  (`preview.margin_required_inr`) plus margin already used against the ceiling
  and render `pass` or `fail`, red with the shortfall in rupees when it fails.
- When `fullyPriced()` is false, do not bail silently. Render the rules that can
  be answered from what is known, and name the leg holding the rest up: "strike
  24,900 CE has no traded price, so rules 1 and 3 are not checked."

**Verify:** build a position whose margin exceeds the ceiling and confirm rule 4
turns red with the shortfall.

---

## 7. PR 2 · BAND P3 — look, feel and the two panels

### Step 10 — One logo, and a theme that follows the computer

**The logo.** He has decided. **The full Devanagari spelling `स्वयम्` in sage,
with the tagline "Discipline builds tomorrow" underneath. Nothing above the
letters. No drawn line, no arc, no ornament.** His wife is a graphic designer
and will do the letterform work later.

- Remove the old mark from `web/src/components/header.js:43-50` (the black
  circle SVG and the words `SWAYAM CAPITAL`) and put the new mark there.
- Remove the `.brandmark` block from **both** `web/src/pages/home.js` and
  `web/src/pages/strategy-builder.js`. One mark, in the header, only.
- The tagline shows where there is room and is dropped where there is not.
- Load `Tiro Devanagari Hindi` from Google Fonts with `Noto Sans Devanagari` as
  the fallback. Give it a real fallback stack.
- Leave the `<title>` as "Swayam Capital".

**The theme.** `web/src/styles/swayam-desk.css:42-43` applies the dark tokens to
`:root[data-theme='auto'] .sw-desk` unconditionally, while
`web/src/styles/swayam-tokens.css:134-135` correctly gives `auto` the light
palette under `@media (prefers-color-scheme: light)`. On a light system he gets
a light header on a dark page. Make the desk stylesheet match the token
stylesheet's pattern.

**Verify:** set the switcher to Auto and flip Windows between light and dark.
Header and page must change together, on both pages.

### Step 11 — Depth, colour and size

His words: "everything is so flat... no depth, no 3D-ness... they all look like
they are written on a 2D page." He cites his Atlas app. **Take the inspiration,
not the tokens** — Atlas has its own identity and uses lilac, which is banned
here.

Add to **both** theme blocks in `web/src/styles/swayam-desk.css`:

```css
--shadow:    0 1px 2px rgba(16,20,20,.06), 0 6px 18px rgba(16,20,20,.07);
--shadow-hi: 0 2px 4px rgba(16,20,20,.09), 0 12px 30px rgba(16,20,20,.11);
--edge:      inset 0 1px 0 rgba(255,255,255,.7);
--ease:      cubic-bezier(.16,1,.3,1);
--dur:       180ms;
```

and the dark equivalents (deeper shadow, `rgba(255,255,255,.05)` edge). Apply
`box-shadow: var(--edge), var(--shadow)` on `.card`, `.rl`, `.mn`, `.met` and
`.preset`, with `transform: translateY(-3px)` and `--shadow-hi` on hover.
Respect `prefers-reduced-motion`.

**Size and width.** He said: "I'm going to use it on the desktop, I have more
space... Atlas uses almost the whole space of the screen... make this text more
readable to me."

| What | Today | After |
|---|---|---|
| `.sw-desk .app` max-width (line 91) | 1440px | 1840px |
| `.kv` rows | 12.5px | 14px, more row height |
| `.rangebar .lbl` | 10px | 12.5px |
| `.tk` ticker items | 12px | 13.5px |
| `.why` small print | 10.5px | 12px |
| `.cols` sidebar column (line 177) | 290px | 330px |

**Colour on the numbers that matter.** Accent only on: Balance and the four
limits on Home; Margin needed and Max loss on the desk. Everything else stays
neutral. Semantic green and red keep their existing meaning.

### Step 12 — The ritual strip becomes a tactile block

He asked for it black, then said: "in the dark theme it must change its colour...
otherwise how will I see the text? You have to take a call on this."

**The call:** it is the same *physical object* in both themes, not the same
colour. Light theme: a deep near-black block (`#141616`) with light text.
Dark theme: a raised slate (`#1f2525`) that sits clearly above the
near-black page. Both keep `--edge` and a deeper shadow so it reads as a bar
lying on the desk rather than part of it.

Two new tokens, `--tile` and `--tile-fg`, defined in **both** blocks. Applied
to `.sw-desk .ritual` and `.rr`.

### Step 13 — So Far Today gets a voice and a collapse

`web/src/components/so-far-today-card.js`

- Add a play button using `createTTSButton` from
  `web/src/components/tts-player.js`, imported exactly as
  `web/src/components/chat-surface.js:13` does it.
- Add a collapse control. Once he has generated it and expanded it once, it
  starts **collapsed** for the rest of that day. Store the flag against today's
  date in `localStorage` so a new day starts expanded again.
- Re-skin it onto the `.sw-desk` tokens. It still uses the old `--dl-*` set and
  will look like a foreign object once everything around it has depth.
- **The cost gate does not change.** Manual button, 60-minute cache, daily cap
  of 8, and it never fires on page load.

### Step 14 — Chat images become attachments, not billboards

His words: "the images are showing very big in the chat itself, that is taking a
lot of space... it stays in the chat as an attachment, showing that there is
something attached, not as a full view."

- `web/src/components/chat-surface.js:517` renders at
  `max-width:480px; max-height:280px; width:100%`. Replace with a thumbnail
  about 40px tall, inline with the file name beside it.
- `web/src/components/ai-chat.js:364` has the same problem at `max-height:200px`.
- `openImageModal()` already exists at `chat-surface.js:67` and already zooms.
  Keep it; the thumbnail opens it.

---

## 8. PR 2 · BAND P4 — the Strategy Desk, laid out properly

### Step 15 — One leg, one row, nothing falling off the card

The leg grid at `web/src/styles/swayam-desk.css:304` is
`24px 30px 56px 104px 46px 46px 66px 22px` with 7 gaps of 5px, needing **429px**.
The left rail is `minmax(340px, 430px)` (line 177) less 28px of card padding,
giving **402px**. That 27px is why the dustbin hangs outside the card.

- Widen `.cols-desk` to `minmax(430px, 520px)`.
- **He wants one row per leg. Do not wrap to two rows.**
- Replace the lots text input with a `<select>` of 1 to 20, styled like the
  existing CE/PE selector. He asked for a dropdown rather than plus and minus
  buttons precisely so no width is spent on stepper chrome.
- The dustbin stays inside the card at every width.

**Verify:** load an iron condor at 10x and confirm nothing is clipped at 1280,
1440 and 1920 pixels wide.

### Step 16 — Greeks stop taking a whole strip

His words: "the Greeks column below the payoff graph is taking an unnecessary
amount of space, scattered all around the page... the first-line Greeks-per-page
position is taking up a full strip, almost blank."

Move the Greeks out of the right column and into the **vacant space at the
bottom of the left rail** (`#strategy-left-rail`), rendered as four
label-and-value pairs across two rows. Drop the near-empty card header.

**Do NOT move the four rule blocks there.** He suggested it, but his own
decision of 2026-09-08 is that the rules sit at the bottom **with the execute
button, in one block**. A verdict must not be separated from the button it
governs. The Greeks fill that space instead. This is recorded so the question is
not reopened.

### Step 17 — Payoff axis, sliders and resets

**Axis.** `web/src/components/payoff-svg.js:148` draws 7 evenly spaced labels
between `spot * 0.94` and `spot * 1.06`, producing values like 23,441. He wants
NIFTY-strike-shaped numbers. Snap `lo` and `hi` (line 105) **down and up to
whole 50s**, then label every **100 points**. He confirmed 100 is right.

**Sliders.** `web/src/pages/strategy-builder.js`, `renderSliders()`:

- The days-to-expiry slider is backwards. Today `min=0` is expiry day on the
  left and `max=dteMax` is today on the right. **He expects the left end to be
  today and the right end to be expiry day.** Invert it and swap the two end
  labels to match.
- Add a **Reset** to both sliders. Target resets to the live spot, date resets
  to today. Style them as the existing `.btn` class, small, with the word
  "Reset". His words: "make sure you don't put that ugly reset button."

**Verify:** the drag behaviour must be unchanged. Check the target still follows
the pointer smoothly after the axis change.

### Step 18 — More ready-made strategies

`web/src/pages/strategy-builder.js`, the `PRESETS` and `SPARKS` maps at
lines 37-53. Strike offsets only, **never a premium**. Add every structure that
works on a single expiry:

bull call spread · bear call spread · bull put spread · bear put spread ·
long straddle · short straddle · long strangle · short strangle ·
iron condor · iron butterfly · call butterfly · put butterfly ·
call ratio back spread · put ratio back spread · jade lizard ·
broken-wing condor bullish · broken-wing condor bearish

Each needs a payoff sparkline in `SPARKS`. Keep the existing six working.

**Calendars and diagonals are NOT in this list.** See §10.

---

## 9. PR 2 · BAND P5 — the option chain, on the desk

He asked for open interest, change in open interest, put-call ratio and the
chain itself, opening as a floating panel, with legs selectable directly from
it "like Sensibull".

**The data is already there.** FYERS' `optionchain` response carries `oi`,
`oich`, `oichp`, `volume`, `bid`, `ask`, `ltpch` and `ltpchp` per row. The
endpoint keeps only `ltp` and `oi` and discards the rest. No new data source,
no new cost, no AI involved, so the AI cost rule does not apply here.

### Step 19 — Return everything FYERS already sends

`src/swayam/api/routes/market.py`, the chain endpoint from line 62.

- Extend `StrikeQuote` with change in open interest, volume, bid, ask and the
  change in traded price. Keep every one nullable.
- **Solve implied volatility per strike** from the traded price using
  `implied_volatility` from `src/swayam/options_math/engine.py`, exactly as the
  quote endpoint does from line 178. Leave it null where there is no trade.
  Do not fabricate one.
- **Fix the expiry bug.** Pass the resolved epoch as `timestamp` to
  `fyers_client.get_option_chain()`. Copy the `expiryData` lookup from the quote
  endpoint. A chain for the wrong expiry is worse than no chain.
- Keep the existing 5-second cache and key it on the resolved expiry.

**Verify:** request the monthly expiry and confirm the strikes returned belong
to that expiry, not the current week. Confirm change in open interest is
non-zero during market hours.

### Step 20 — The chain itself, as a floating panel

New `web/src/components/option-chain-modal.js`, mounted from
`web/src/pages/strategy-builder.js` behind a button on the desk.

- Calls on the left, strikes down the middle, puts on the right. Mark the
  at-the-money row and scroll to it on open.
- Per strike: price and its change, open interest, change in open interest,
  volume, implied volatility.
- Above the table: total call and put open interest, put-call ratio and max
  pain. All three already exist in `nifty_snapshot.py`; reuse rather than
  recompute where you can.
- Horizontal bars behind the open-interest figures, scaled to the largest value
  on screen, so the walls are visible at a glance.
- Follows the expiry chosen on the desk. Refreshes on the same 5 s timer as the
  leg prices while open, and **stops when closed**.
- Dismissed with the escape key and by clicking outside. Draggable.
- Use `api.getOptionChain`, already written in `web/src/api.js`.

**Verify:** open during market hours, confirm the put-call ratio matches Home's
figure, and confirm the numbers move while it sits open.

### Step 21 — Click a strike to build the leg

- Hovering a row reveals a small **B** and a small **S** on that side of the
  chain. Clicking one adds the leg at the price on screen.
- **Explicit buttons, never a hidden modifier key.** A wrong side on an options
  leg is not a small mistake.
- The panel stays open, so a four-leg structure is four clicks.
- Reuse `addLeg()` and `repriceLeg()`. Legs added this way are ordinary legs:
  real price, real expiry, contract size from the server.
- A strike with no traded price is not clickable and says why.

**Verify:** build an iron condor entirely by clicking, then confirm the four
rules, the payoff and the margin all agree with the same structure built by hand.

---

## 10. WHAT IS DELIBERATELY NOT IN THIS BRIEF

- **Calendars and diagonals.** He uses calendar spreads more than half the time
  and they were profitable for him, so this matters and it is the very next job.
  But the desk has ONE expiry for all legs, and a payoff across two expiries
  needs a real multi-expiry valuation rather than an approximation. Ten of his
  21 historical trades are calendars. It gets its own brief. **Do not attempt a
  partial version here.**
- **Custom strategies he defines and saves.** Agreed to arrive with the backtest
  lab, because a rule he writes is only worth saving once he can test it.
- **The backend risk model.** Settled and correct. See §0.
- **The AI chat's layout and behaviour.** Only its persona facts change.
- **The two long-standing test failures**,
  `tests/api/test_market.py::test_get_option_chain_returns_strikes` and
  `tests/test_notifications.py::test_execute_endpoint_best_effort_dispatch_on_success`.
  They pre-date all of this. **Do not weaken assertions to make them pass.**
  Note that step 19 changes the chain endpoint, so the first one may now be
  fixable honestly. If it is, fix it properly and say so.

---

## 11. CONTRACTS YOU MUST PRESERVE, OR THE APP CRASHES

`web/src/main.js` constructs and calls these unguarded.

```
HomePage
  constructor(container, options)   { onOpenAIDrawer, onOpenSettings, onNavigateStrategy }
  async init()
  destroy()
  .niftyChart                       MUST exist with retheme(); main.js calls
                                    homePage.niftyChart.retheme?.() and undefined throws

StrategyBuilderPage
  constructor(container, options)
  async init()
  destroy()
  async refreshPositions()
  .payoffChart                      MUST exist with retheme()
```

Every timer added in this brief must be cleared in `destroy()`.

---

## 12. THE REVIEW THAT HAPPENS BEFORE HE MERGES

Work through this yourself before opening each PR, and report honestly.

1. **Grep the diff for invented values.** `|| 0`, `|| 75`, `?? 0`, `else 0.0`,
   `else 50.0`, any bare rupee literal in a render path. Missing data renders
   `unavailable`.
2. **Confirm `pct_of_margin` is still not multiplied by 100** anywhere. The
   server sends 1.74 meaning 1.74%.
3. **Confirm the class contracts in §11 survive.**
4. **Confirm the AI chat is untouched** apart from image size.
5. **Confirm So Far Today still never fires on page load.**
6. **Confirm no purple, lilac or violet** entered the diff.
7. **Confirm every new timer is cleared in `destroy()`.**
8. **Run the test suite.** 327 passed and 2 failed before this work; the 2 are
   the known ones in §10.
9. **Say plainly what you could not run.** If you have no FYERS token, no
   Supabase credentials and no Google Cloud access, then steps 1, 3, 4, 5, 6, 7
   and 19 cannot be verified live by you. Say so. Do not describe them as
   working.

---

*Real-money trading remains code-blocked by absence. There is no order-placement
code anywhere in this repository, and nothing in this brief adds any.*
