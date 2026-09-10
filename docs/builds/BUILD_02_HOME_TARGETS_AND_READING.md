# BUILD 02 — HOME'S RUNNING TRADE, TARGETS, THE CROSSHAIR, THE TERMINAL-TEST PHASE

> Written 2026-09-10 evening by the main chat, from his feedback on the
> mockup. Branch `feature/swayam-build02-home-targets-043`. One pull request.
> **Builds after BUILD_01 is merged**, because it opens BUILD_01's exit ticket
> from Home and reads BUILD_01's live valuation.
>
> **The prompt he pastes into the builder chat is in the fence below.**

---

```
Swayam Capital, my NIFTY options terminal. THIS CHAT IS A BUILDER CHAT. It
builds exactly ONE thing: Build 02, Home's running-trade band with its
states, targets per leg and per trade, Manage from Home, the payoff
crosshair, the terminal-test phase, and the big-number pass. The main chat
planned it and will review it; you do not re-plan it, widen it, or start
anything else. If I ask for something outside it, say so.

READ THESE, ALL THE WAY THROUGH, IN THIS ORDER. Do not ask me where anything is.
1. docs/builds/README.md                 how a build works and the rules
2. docs/builds/BUILD_02_HOME_TARGETS_AND_READING.md   THIS BUILD, the whole spec
3. docs/builds/BUILD_01_DESK_POSITION_AREA.md  what the previous build left you
4. docs/PLAN.md sections 2.12.1, 2.12.3, 2.12.5, 2.12.6
5. CLAUDE.md, then docs/SWAYAM_START_HERE.md section 1
6. The mockup: https://claude.ai/code/artifact/ef242a22-59a7-4752-8aa4-91d59393c5d5
   Screen 1 (the crosshair), the Targets modal on screen 2, and screen 5 are
   yours. The build must look like them.

WHO I AM. Abhishek. Not a developer. Plain English, never code to approve, a
recommendation rather than a menu. I speak my prompts, so an odd word is
transcription; ask. Night shift: awake around 1 pm IST, at the screen by 2 pm,
I trade 1 to 2:30 pm. Never plan anything for 09:15.

MY TWO RULES. No fake data: every figure real from FYERS or the database, or
unavailable with the reason. Never say done, live or passing unless you
checked it on the running system that day and can show me the proof.

MY SCREEN RULES. Numbers I read are big and bold; informative text small and
muted. Cards 70 to 80 percent filled. Colour only from the money. Identical
to the mockup.

HOW WE WORK. Plan first in plain English, six parts; I approve before any
code. Branch feature/swayam-build02-home-targets-043 off main, never main,
never a worktree. git fetch before every push. Hand off in five parts, files
as clickable links, manual steps in bold up front (the migration, the two
scripts), one bold line saying what exists and what does not.

DO NOT TOUCH: trade 7cd4d017 by script, docs/ROADMAP.md, the recorder,
src/swayam/research/, the AI, the fill rule, the Trade Journal page, the
vault cage, the database guard, any migration but 023, the payoff's drag and
sliders. Every trade in the record is a terminal test until I run the script
that says paper trading has started.

BEFORE YOU DO ANYTHING, ANSWER THESE IN YOUR OWN WORDS.
1. What do solid, blinking and muted mean on Home's band, in my words?
2. What is a target on a leg, what is a target on the trade, and what happens
   when I leave a box blank?
3. What does the Manage button on Home open, and why is it not a link to
   the desk?
4. Which figure does Home's "Margin used" read today, which does the desk
   read, and which one is right?
5. What marks a trade as a terminal test, when does that stop, and where do
   the six existing notes go?
6. What must the crosshair never do to the payoff graph?
```

---

## 1. What this build is for

His decisions of 10 September, in his words. **Home:** "A running trade is
unmistakable on Home and goes quiet only when squared off. The coloured edge
goes." He chose **Option B**, the whole band coloured from the money. **The
states:** "Whenever it reaches my target area, either profit or loss, it
starts blinking green or red, and I'll open it. When it is not blinking, it
becomes solid... As soon as the trade is squared off, everything goes mute:
no blink, no color." So: **solid colour means running; blinking means a
target was reached and needs him; muted means nothing open or squared off.**
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
  match, solid, no animation. Chip "running" with a still dot.
- **Alert**, a target reached: the same colours, and the band breathes:
  saturation and a soft ring, about two seconds a cycle, gentle, never a
  strobe. Chip "profit target reached" or "loss target reached" with a
  pulsing dot; the third figure names the leg, e.g. "23,800 CE · profit".
  Manage becomes the primary button. Under `prefers-reduced-motion` no
  animation and a solid outline instead. The blink stops the moment no target
  is reached or the leg is exited.
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
  blinking. Say so in bold.

## 6. The handoff

**Manual steps in bold up front:** migration 023; `scripts\mark_terminal_tests.py`
dry run then `--apply` (he decides when; the open condor is skipped until
closed); `scripts\start_paper_trading.py` is NOT to be run until he says
paper trading starts. One bold line: what exists and what does not.
