# BUILD 02 — HOME'S RUNNING TRADE, TARGETS, THE CROSSHAIR, THE TERMINAL-TEST PHASE

> Written 2026-09-10 evening by the main chat, from his feedback on the mockup.
>
> **STATE, 2026-09-11. THIS IS THE LAST PART OF BUILD A AND IT IS THE ONLY
> PART LEFT.** Parts one and three are built, verified on the running system
> and pushed. It gets its own chat because the previous one filled up, and it
> continues on the SAME BRANCH so Build A stays one pull request.
>
> **His correction of the states, 2026-09-10 late evening, which overrides any
> other wording in this file:** "Blinking means the trade is running. When it
> becomes a solid color, then the trade has reached its target, either profit
> or loss. Green and red colors define it." Muted means nothing open or
> squared off.

---

## 0. WHERE BUILD A HAS GOT TO. Read this before anything else.

**The branch is `feature/swayam-build-a-desk-home-chain-042`**, cut from `main`
at the merge of pull request #63. It is pushed. **There is no pull request yet
and nothing is merged, so nothing is live.** Four commits:

| Commit | What it is |
|---|---|
| `b3b4ec9` | Part one: the position area, the exit ticket, the campaign model |
| `d1533ca` | Part one verified in the browser: three tests rewritten, the charge fix, four faults found |
| `f016360` | This build's sibling `BUILD_04` filled to `BUILD_01`'s shape |
| `c803ef6` | Part three: the option chain |

**Check before you push:** `git fetch`, then confirm the branch's pull request
has not been opened and merged while you were away. He merges mid-session.

### What part one already gave you, and part two builds ON it

Do not rebuild any of this. It is done, and the tests hold it.

- **`GET /api/positions/live`** now answers with everything a card needs, per
  position: `legs[]` each carrying `mark`, `mark_side`, `leg_pnl_inr`,
  `exit_charges_now_inr` and `status`; and at the top `charges_in_inr`,
  `charges_out_now_inr`, `net_if_exit_now_inr`, `rule1_cap_inr`,
  `rule1_headroom_inr`, `rule4_ceiling_inr`, `margin_required_inr`,
  `breakevens`, `spot_at_entry`, `legs_open`, `legs_closed`, `name_source`,
  `market_state` and `read_at`. **Targets and `alerts[]` are what part two
  adds to it**, in `_value_one_position` in `src/swayam/api/routes/positions.py`.
- **The mark is the side he would GET**, a bought leg at the bid and a sold leg
  at the ask. Every figure part two shows must keep that.
- **Each position is valued on its own**, so one the feed cannot price says
  `error` with the reason and the rest still show.
- **`GET /api/positions?status=closed`** now carries the RESULT of each trade,
  joined from `swayam_trade_history`: `closed_at`, `close_reason`,
  `gross_pnl_inr`, `total_charges_inr`, `realized_pnl_inr`, `holding_days`.
- **`web/src/components/exit-ticket.js`**, `ExitTicket`. **This is what Manage
  on Home opens.** `open(position, sequenceOrNull)` where the position is a row
  from `/api/positions/live`. Its callbacks are `onExitAll(payload)`,
  `onExitLeg(sequence, payload)` and `onDone(result)`. Home mounts its own
  instance; do not move the desk's.
- **`web/src/components/position-area.js`**, `PositionArea`. Its header is
  where **the Targets button goes**, beside Edit name. Its `act(action, args)`
  is the single place a button's work lives, and the click listener is a thin
  adapter onto it, because the test DOM cannot deliver a delegated click.
- **`src/swayam/services/structure_name.py`** names a structure from its OPEN
  legs. **`src/swayam/services/exit_refusal.py`** owns the "your price, not a
  rule" wording.
- **`POST /api/positions/{id}/legs/{sequence}/exit`** and `.../reverse` square
  off or flip one leg. **`PATCH /api/positions/{id}/name`** sets his own name.
- **Migration `022_campaign_model_and_name.sql` is written but NOT APPLIED.**
  Part two's migration is 023 and it will be applied at the same time, by him.
- **`web/src/utils/display.js` gained `inrExact`**: rupees to the paisa. Use it
  for every charge. `inr` rounds to whole rupees and is for the hero tiles.
- **`position-area.js` exports `signed`, `tone`, `heldFor`, `istDay`**. `istDay`
  is the trading day in IST; never slice a UTC timestamp to get his date.

### What part three gave you

- `web/src/components/option-chain-modal.js` is rebuilt: `_paint()` for a shape
  change, `_update()` for a refresh in place, `_paintChrome()` for the header
  and tiles. **Nothing that runs on a timer may call `_paint()`.**
- **Max pain now names its expiry on both screens.** Home's is in
  `HomePage._maxPainRow`, and `HomePage._expiryLabel` turns an ISO date into
  "15 Sep". Part two's big-number pass must not undo either.

### One rule he added mid-build, 2026-09-10 evening, which is now standing

**"Every card on any page must be bold and large enough, or, if required,
colored, so that it claims or represents that it is its boundary, its card,
like it owns this area."** The card headings were 12px, weight 600, in muted
grey, which was smaller and quieter than the body beneath them. `.sw-desk .card
> h3` is now 16px, weight 800, in the primary ink, which lifts NIFTY 50,
Sectors today, Options weekly, Your money, Your record and Events ahead on
Home, and Payoff, Legs, Ready-made, Strikewise IV, Greeks and Rules and
execution on the desk. **Part two's big-number pass carries this on**: any card
whose title still does not claim its area gets fixed.

### What this machine does, learned the hard way on 2026-09-11

- **Work in the primary folder**, `D:\Claude\POS\Trading-Platform\Swayam Capital`.
  The venv is an editable install pointing at it.
- **Python is `.\.venv\Scripts\python.exe`.** If it refuses to launch with "An
  Application Control policy has blocked this file", that is Windows Smart App
  Control, not the project. He turns it off; do not recreate the venv.
- **Bash heredocs mangle `${...}` and backslashes.** Write a file with the
  editor tool and copy it into place, or use the anchor-patch helper the last
  chat used: read the file, normalise `\r\n` to `\n`, replace an exact anchor
  that must appear EXACTLY ONCE, put the endings back. The repo is checked out
  CRLF (`core.autocrlf=true`) while everything you write is LF, so a multi-line
  anchor never matches until you normalise.
- **The servers:** `.\.venv\Scripts\python.exe -m uvicorn swayam.api.main:app
  --port 8000` and `npm run dev` in `web`. Vite proxies `/api` to 8000. Reach
  the page at `http://localhost:5173`, not `127.0.0.1`.
- **The browser pane's screenshot does not follow the page scroll.** Set a tall
  viewport with `resize_window`, or hide the sections above what you want to
  see, screenshot, and put them back.
- **The desk page instance is at `window.__swayamApp.strategyPage`**, and its
  chain panel at `.chainModal`. That is how to drive a component in the real
  page and measure what it actually did.
- **The test DOM (`web/tests/setup_test_dom.js`) builds a NEW synthetic element
  on every `querySelector`.** Element identity means nothing there, a write to
  `outerHTML` lands on a throwaway, `tr.atm` is not a supported selector, and
  `localStorage` is wiped on every setup. Test the DECISION in vitest and prove
  the DOM behaviour in a real browser.
- **`tests/conftest.py` stubs `execution._fill_for`** so old tests get a fill at
  the price they asked for. A test that is ABOUT the fill opts out with
  `pytestmark = pytest.mark.real_fills` and stands in its own quotes.
- **Anything that reaches `queue_journal_note` or `mark_journal_status` in a
  test writes to the LIVE database.** Patch them, or the cage stops you and the
  test fails for the wrong reason.
- **One Python test fails and it is not yours:**
  `tests/test_notifications.py::test_execute_endpoint_best_effort_dispatch_on_success`
  mocks `build_spread_from_request` with a two-tuple where the code unpacks
  three. It fails identically on `main`; that was checked by running it there.

### The counts to compare against

| Suite | On this branch, 2026-09-11 |
|---|---|
| Python | 616 passing, 1 failing (the stale mock above) |
| JavaScript | 299 passing in 34 files |
| His journal folder, `02 - Projects/Trading/04 - Journal` | **6 notes, before and after every run** |

---

```
Swayam Capital, my NIFTY options terminal. THIS CHAT FINISHES BUILD A. Parts
one and three are built, verified and pushed on the branch
feature/swayam-build-a-desk-home-chain-042. Part two is all that is left, and
it goes on THAT SAME BRANCH so Build A is one pull request. Do not start a new
branch and do not open a pull request until the handoff.

READ THESE, ALL THE WAY THROUGH, IN THIS ORDER. Do not ask me where anything is.
1. docs/builds/README.md                              how a build works
2. docs/builds/BUILD_02_HOME_TARGETS_AND_READING.md   START AT SECTION 0. It
   says exactly where Build A has got to, what parts one and three already
   built for you, and what this machine does that will waste your time.
3. docs/PLAN.md sections 2.12.1, 2.12.3, 2.12.5, 2.12.6
4. CLAUDE.md, then docs/SWAYAM_START_HERE.md section 1
5. The mockup: https://claude.ai/code/artifact/ef242a22-59a7-4752-8aa4-91d59393c5d5
   Screen 1's crosshair, the Targets modal on screen 2, and screen 5 are
   yours. The build must look like them.

HOME'S BAND, IN MY WORDS, SO NOBODY GETS IT BACKWARDS. Blinking means the
trade is running, a gentle blink, so my running profit or loss always draws my
eye. Solid green or solid red means a target I set was reached, profit or
loss, on a leg or on the trade, and it needs my attention; it stops blinking.
Muted means nothing open or squared off.

WHO I AM. Abhishek. Not a developer. Plain English, never code to approve, a
recommendation rather than a menu. I speak my prompts, so an odd word is
transcription; ask. Night shift: I wake around 1 pm IST, at the screen by 2 pm,
I trade 1 to 2:30 pm. Never plan anything for 09:15.

MY TWO RULES. No fake data: every figure real from FYERS or the database, or
unavailable with the reason. Never say done, live or passing unless you
checked it on the running system that day and can show me the proof.

MY SCREEN RULES. Numbers I read are big and bold; informative text is small
and muted. Cards are 70 to 80 percent filled. Colour only from the money.
Every card title must claim its area: bold, large enough, coloured if it
needs to be. Identical to the mockup.

HOW WE WORK. Plan part two first, in plain English, six parts, in the chat; I
approve before any code. Then build. Then hand off ONCE FOR THE WHOLE OF
BUILD A, five parts, files as clickable links, and every manual step in bold
up front: migration 022 AND migration 023, the drainer run, the marking
script's dry run, and the line saying start_paper_trading.py is NOT to be run
until I say paper trading starts. One bold line saying what exists and what
does not. Then open the pull request and I test.

DO NOT TOUCH: trade 7cd4d017 by script, docs/ROADMAP.md, the recorder,
src/swayam/research/, the AI, the fill rule in services/fills.py, resting
orders (BUILD_03, its own chat), the Trade Journal page, the vault cage, the
database guard, the payoff's drag and its two sliders, any migration but 023,
and anything parts one and three already built.

BEFORE YOU DO ANYTHING, ANSWER THESE IN YOUR OWN WORDS.
1. What do blinking, solid and muted mean on Home's band, in my words?
2. What is a target on a leg, what is a target on the trade, and what happens
   when I leave a box blank?
3. What does the Manage button on Home open, and where does that component
   already exist?
4. Which figure does Home's "Margin used" read today, which does the desk
   read, and which one is right?
5. What marks a trade as a terminal test, when does that stop, and which
   script must NOT be run until I say so?
6. What must the crosshair never do to the payoff graph?
7. What may you never say LIVE without?
```

---

## 1. What this build is for

His decisions of 10 September, in his words. **Home:** "A running trade is
unmistakable on Home and goes quiet only when squared off. The coloured edge
goes." He chose **Option B**, the whole band coloured from the money. **The
states, in his corrected words:** "Blinking means the trade is running. When
it becomes a solid color, then the trade has reached its target, either
profit or loss. Green and red colors define it... As soon as the trade is
squared off, everything goes mute: no blink, no color." So: **blinking means
running; solid green or red means a target was reached and needs him; muted
means nothing open or squared off.**
**Targets:** "My preference is to add a target for each leg. Target always
means both loss and profit... In case I cannot add profit and loss for each
leg, I have to add it for the whole trade." **Manage:** "Give a Manage button,
which will open the exit modal. Over there, I can exit all directly, or I can
exit one leg where the target is achieved." **The crosshair:** "When I hover
the mouse around the payoff graph, it must have a crosshair... the vertical
line will have the Nifty level, and the horizontal line will have my profit
and loss. Without moving any component." **The record:** "All these paper
trades are test trades... The paper trades have not yet started."

## 2. What exists today, verified 2026-09-10

- Home: `web/src/pages/home.js`. The positions strip sits below the daily
  check-in and above Your money (`#home-positions`), refreshes on the
  15-second timer, colours from `positionsTone()`, and has a coloured edge.
  **`marginUsed()` reads `p.margin_used_inr`, a field no position carries;
  the desk reads `margin_required_inr` from migration 021.** That is why Home
  said unavailable while the desk showed ₹84,929. Fix the source, not the
  symptom.
- The payoff: `web/src/components/payoff-svg.js`, `PayoffSvgComponent`, an
  SVG with a pointer drag for the target (`_bindDrag`, `pointermove` while
  `_dragging`). Two curves already: at expiry and at the chosen date.
- The record's one mark: `provenance` on `swayam_positions` (`live` |
  `build_test`), migrations 017 and 018; `api/routes/journal.py` filters
  `LIVE_PROVENANCE` everywhere; the Trade Journal page prints the excluded
  count. There is no settings or phase table.
- Notes are written by `src/swayam/services/journal_writer.py` into the
  vault's `02 - Projects/Trading/04 - Journal/`, which holds exactly six
  notes, all terminal tests: `2026-09-09-trade01..03.md`,
  `2026-09-10-trade01..03.md`.
- After BUILD_01: the exit ticket component `web/src/components/exit-ticket.js`,
  the position card with its header buttons, `/api/positions/live` with
  per-leg marks, `net_if_exit_now_inr`, `rule1_cap_inr`, `market_state`.
- Capital and rule 1: `src/swayam/services/capital.py`; the cap is 1% of the
  live balance, never stored.

## 3. What to build, in this order

### 3.1 Targets on a trade and its legs (migration 023)

- **Per leg**, in the `legs` JSON: `target_price` and `stop_price`, prices of
  that option, both optional. For a bought leg the profit target is reached
  when the bid is at or above `target_price` and the loss when the bid is at
  or below `stop_price`; for a sold leg the profit target when the ask is at
  or below `target_price` and the loss when the ask is at or above
  `stop_price`. The mark is the side he would get, as BUILD_01 defined it.
- **Per trade**, migration 023 adds to `swayam_positions`:
  `target_profit_inr numeric NULL`, `target_loss_inr numeric NULL`,
  `targets_set_at timestamptz NULL`. Reached when
  `net_if_exit_now_inr` (net of charges both ways) is at or above the profit
  target, or at or below minus the loss target. **A blank loss target falls
  back to rule 1's cap** from `capital.py`, read live. A blank profit target
  means no profit signal: a number the terminal picked is a plan he did not
  make.
- `PUT /api/positions/{id}/targets` with `{legs: [{sequence, target_price,
  stop_price}], target_profit_inr, target_loss_inr}`; blanks clear. Refuses
  on a closed trade. Never touches an order, a fill or a charge.
- `/api/positions/live` gains `targets` (what is set) and `alerts[]`, each
  `{scope: leg|trade, sequence?, kind: profit|loss, level, mark, reached_at}`,
  and `state: running | alert | quiet` for the position. Evaluate only when
  `market_state` is live; at the close the state is what it last was, and the
  reply says so.
- **The Targets button** on the position card (BUILD_01's header), a
  designer button with the target icon in sage, opens a small modal exactly
  as the mockup: per leg Entry, Now, **Take profit at**, **Cut loss at** and
  what each means in rupees on that leg; a last row for the whole trade in
  rupees with the fallbacks stated; Save targets, Clear all. **No extra column
  on the position card.** A reached target shows on the card only as the
  state chip and a line naming the leg, nothing more.

### 3.2 Home's running-trade band (screen 5 of the mockup)

Replace the strip in `home.js` with the band. Full width, below the daily
check-in strip, above Your money. The coloured edge is gone. Contents, left
to right: the state chip; the name at 19px with legs, expiry, since, swing and
a short note beneath; **Open profit / loss at 40px**; Net if exited at 26px;
a third figure (Targets set, or Reached with the leg and kind); the
**Manage** button.

- **Running**: background `--up-bg` or `--down-bg` from the money, border to
  match, and the band **breathes gently**: saturation and a soft ring, about
  two and a half seconds a cycle, never a strobe. His words: "very light
  blinking, so that it always attracts attention that my profit and losses
  are running." Chip "running" with a pulsing dot. Under
  `prefers-reduced-motion` no animation and a soft outline instead.
- **Alert**, a target reached: the band goes **solid**, deep green
  (`--up`) or deep red (`--down-line`) with white text, and **stops
  blinking**. Chip "profit target reached" or "loss target reached" with a
  still dot; the third figure names the leg, e.g. "23,800 CE · profit".
  Manage becomes the primary button. The band returns to running the moment
  no target is reached any more, and goes quiet when the leg or trade is
  exited.
- **Quiet**: nothing open or squared off. Card colour, muted text, chip
  "squared off" or "nothing running", Manage disabled. The quiet line says
  "Your paper record starts clean on the day you say paper trading begins.
  Everything before that is a terminal test." while the phase is testing.
- **Manage opens BUILD_01's exit ticket on Home**, for that trade, one leg or
  all, with the same details. It does not navigate to the desk. Nothing on
  Home manages a position except through that ticket.
- More than one open trade: one band per trade, the alert ones first.
- Refresh on the existing timer; read `state` and `alerts` from
  `/api/positions/live`; never compute the money in the browser.

### 3.3 Home's "Margin used" reads the desk's sum

`marginUsed()` reads `margin_required_inr`, sums it across open positions,
and returns `null` with the note when any open position lacks it, exactly as
`StrategyBuilderPage.refreshPositions` does. One figure, both pages. Show
rule 4's share and a bar in the tile, as the mockup.

### 3.4 The payoff crosshair (screen 1 of the mockup)

In `payoff-svg.js`, on `pointermove` when not dragging: a dashed vertical
line at the pointer's NIFTY level with the level in a dark label on the
axis; a dashed horizontal line at the at-expiry profit or loss for that level
with the figure in a dark label on the left axis; a dot on each curve; and a
readout box top right: NIFTY, At expiry (big, coloured), Today. Hidden on
`pointerleave`. **The drag, the target marker and both sliders are
untouched, and the drag still wins while the pointer is down.** Both themes.
Levels rounded to 5 points; money to the rupee.

### 3.5 The terminal-test phase, carefully

His words: "I want to mark it as a terminal test, but make sure it has to be
done carefully without any conflicts. These are terminal tests, and they
should be read as a terminal test till the time we are testing."

- **Migration 023** also creates `swayam_phase` (`id smallint PRIMARY KEY
  DEFAULT 1 CHECK (id = 1)`, `paper_trading_started_at timestamptz NULL`,
  `set_by text`, `note text`) with its one row, null. Nothing is a paper
  trade until that timestamp exists.
- **New provenance value `terminal_test`.** `execution.py` writes
  `provenance = 'terminal_test'` on every new position while
  `paper_trading_started_at` is null, `'live'` after. Read it through a small
  `src/swayam/services/phase.py`, never a cached constant.
- **`scripts/start_paper_trading.py`**, which HE runs on the day he says so:
  sets the timestamp, prints it back. Refuses to run twice.
- **`scripts/mark_terminal_tests.py`**, which HE runs: dry run lists every
  `swayam_positions` row with `provenance = 'live'` opened before the
  timestamp (today: the six), `--apply` sets them to `terminal_test` and
  moves their six notes from `04 - Journal/` into
  `04 - Journal/Terminal tests/`, updating `journal_path` on each row and the
  outbox rows that name them. **The open condor is included only when it is
  closed**: the script skips open rows and says so. Atomic per row; a failure
  leaves the row untouched and says why.
- **The journal and analytics** already exclude everything that is not
  `live`; extend the exclusion note on the Trade Journal page to say
  "N terminal tests excluded" beside the build-test count. **The position
  area shows terminal tests** (the desk shows what he holds and did), with
  the blue chip; it hides `build_test` as today.
- **New notes** written while the phase is testing go into
  `04 - Journal/Terminal tests/` and carry `provenance: terminal_test` in
  their front matter. `journal_writer` reads the phase the same way.
- Tests: `tests/test_vault_guard.py` still proves the cage; a new test proves
  a note written in the testing phase lands in the subfolder of the CAGED
  vault; the marking script has a dry-run test against faked rows. Journal
  folder: 6 notes before, 6 after.

### 3.6 The big-number pass

Across Home and the desk, per his rule of 10 September: every figure he
reads takes the mockup's sizes (hero 40 to 46px, tile 26 to 30px, leg money
19px, names 17 to 22px); informative text stays small and muted; every card
is 70 to 80 percent filled. Home's Your money tiles, the NIFTY sidebar's
key figures and the desk's metric row are the ones to lift. Do not touch the
AI chat panel. Screenshots of before and after, both themes, in the handoff.

## 4. What is NOT in this build

Resting orders (BUILD_03). The option chain (BUILD_04). The Trade Journal
page (§2.18) beyond the exclusion count. Any change to the fill rule or to the
charge engine. Any automatic exit: a reached target blinks, it never trades.
Any edit to 7cd4d017 by script.

## 5. How it is verified

- Python: 023 applied, `tests/test_written_columns_exist.py` green; tests
  for target evaluation on bought and sold legs, the trade-level fallback to
  rule 1, the phase service, the two scripts' dry runs, the note subfolder.
- JavaScript: the band in its three states from captured replies; the
  crosshair's maths against the same points the curves are drawn from;
  `HomePage.niftyChart.retheme` still exists.
- Browser: both themes, real backend, market shut: the band shows the open
  condor in the running state with real figures, Manage opens the exit ticket,
  the Targets modal saves and reads back, the crosshair reads, Margin used on
  Home equals the desk's. No console errors. Screenshots beside the mockup.
- **Only his window can prove:** a target reached on a live mark and the band
  going solid. Say so in bold.

## 6. The handoff

**Manual steps in bold up front:** migration 023; `scripts\mark_terminal_tests.py`
dry run then `--apply` (he decides when; the open condor is skipped until
closed); `scripts\start_paper_trading.py` is NOT to be run until he says
paper trading starts. One bold line: what exists and what does not.
