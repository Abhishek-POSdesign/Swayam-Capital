# BUILD 01 — THE POSITION AREA ON THE DESK, THE EXIT TICKET, THE CAMPAIGN MODEL

> Written 2026-09-10 evening by the main chat, from his decisions of 9 and 10
> September and his feedback on the mockup.
>
> **Corrected the same night: this is PART ONE OF BUILD A.** Build A is this
> document, then `BUILD_02_HOME_TARGETS_AND_READING.md`, then
> `BUILD_04_OPTION_CHAIN.md`, in one chat, one branch
> `feature/swayam-build-a-desk-home-chain-042`, one pull request, migrations
> 022 and 023. Only resting orders (`BUILD_03`) are a separate build. The
> prompt in the fence below is Build A's prompt; the builder that pasted the
> earlier four-build version follows the correction message he gave it.

---

```
Swayam Capital, my NIFTY options terminal. THIS CHAT IS A BUILDER CHAT. It
builds exactly ONE build: BUILD A, which is three documents in order: the
position area on the Strategy Desk with the exit ticket and the campaign
model (BUILD_01), then Home's running-trade band, targets, Manage from Home,
the payoff crosshair, the terminal-test phase and the big-number pass
(BUILD_02), then the option chain (BUILD_04). One branch, one pull request,
migrations 022 and 023. Resting orders (BUILD_03) are NOT yours. The main
chat planned it and will review it; you do not re-plan it, widen it, or start
anything else. If I ask for something outside it, say so.

READ THESE, ALL THE WAY THROUGH, IN THIS ORDER. Do not ask me where anything is.
1. docs/builds/README.md                 how a build works and the rules
2. docs/builds/BUILD_01_DESK_POSITION_AREA.md   part one, the whole spec
3. docs/builds/BUILD_02_HOME_TARGETS_AND_READING.md   part two
4. docs/builds/BUILD_04_OPTION_CHAIN.md   part three; its mockup arrives from
                                         the main chat while you are on parts
                                         one and two
5. docs/PLAN.md sections 2.12.1, 2.12.2, 2.12.3, 2.12.5, 2.12.6
6. CLAUDE.md                             how to work here, what I trade
7. docs/SWAYAM_START_HERE.md section 1   where everything lives
8. The mockup: https://claude.ai/code/artifact/ef242a22-59a7-4752-8aa4-91d59393c5d5
   Every screen is yours. The build must look like them.

HOME'S BAND, IN MY WORDS, SO NOBODY GETS IT BACKWARDS. Blinking means the
trade is running. Solid green or solid red means a target I set was reached,
profit or loss, on a leg or on the trade, and it needs my attention. Muted
means nothing open or squared off.

WHO I AM. Abhishek. Not a developer. Plain English, never code to approve, a
recommendation rather than a menu. I speak my prompts, so an odd word is
transcription; ask. Night shift: I wake around 1 pm IST, at the screen by 2 pm,
I trade 1 to 2:30 pm. Never plan anything for 09:15.

MY TWO RULES. No fake data: every figure real from FYERS or the database, or
unavailable with the reason. Never say done, live or passing unless you checked
it on the running system that day and can show me the proof.

MY SCREEN RULES. Numbers I read are big and bold; informative text is small and
muted. Cards are 70 to 80 percent filled. Colour only from the money. The
build must be identical to the mockup, not picture-perfect there and cramped
in reality.

HOW WE WORK. Plan first in plain English, six parts, in the chat, for the
whole of Build A; I approve once, before any code. Then build part one, part
two, part three in order, with a short note in the chat after each part. One
feature branch feature/swayam-build-a-desk-home-chain-042 off main, never
main, never a git worktree, in the primary folder. git fetch and check the PR
state before every push. Hand off once, at the end, in five parts with files
as clickable links, the manual steps (migrations 022 and 023, the drainer,
the marking script) in bold up front, and one bold line saying what exists
and what does not. Then I test, and the main chat reviews before I merge.

DO NOT TOUCH: trade 7cd4d017 by script (open on purpose), docs/ROADMAP.md,
the recorder, src/swayam/research/, the AI, the fill rule in
services/fills.py, the Trade Journal page, the vault cage, the database
guard, any migration but 022 and 023. Every trade in the record is a terminal
test; none is a paper trade.

BEFORE YOU DO ANYTHING, ANSWER THESE IN YOUR OWN WORDS. I read your answers,
then we start.
1. What is a trade in my record, and what happens to it when I exit one of
   its four legs?
2. Where does the structure's name come from after this build, and why was
   my open condor called "Short Strangle"?
3. What does the exit ticket do with a limit price the book has not reached,
   in THIS build, and what wording must it use?
4. Which endpoint closes the whole trade today, which adds a leg, and which
   two are new in this build?
5. What is wrong with the drainer's close branch and how does this build fix it?
6. Name every number on the position card, and where each one comes from.
7. What may you never say LIVE without?
8. What do blinking, solid and muted mean on Home's band, and what is a
   target on a leg?
9. What marks a trade as a terminal test, and which script must NOT be run
   until I say paper trading starts?
```

---

## 1. What this build is for

On 10 September he took a four-leg condor and could not see it, manage it or
exit it from the desk. He approved a clickable journey on 9 September and read
all of it as built; only the ticket half was. This build is the other half:
**the position area below the payoff, the exit ticket for one leg or all legs,
and a record that can hold a trade whose legs change while it is open.**

His words, 9 September: "at the strategy desk itself, the bottom area below
the payoff graph and execution should be dedicated to open position, close
position for the day, and everything for the positions." And: "Full width. Big
numbers. Bold. Clearly visible with required colors. Easily manageable. No
cheap cross button or rather dustbin button. No cheap round circle for reset, a
proper reset button. I must feel good while managing it."

## 2. What exists today, verified 2026-09-10

- The execution ticket: `web/src/components/execution-ticket.js`
  (`ExecutionTicket`, `bookPrice`, `previewFill`), sending through
  `POST /api/execute/multi-leg` in `src/swayam/api/routes/execution.py`.
- Add a leg to an open trade: `POST /api/positions/{id}/legs`, same file,
  `add_leg_to_position`. Fills through `_fill_all`, charges per leg, structure
  recomputed, an Adjustments block queued for the note.
- Close the whole trade: `POST /api/positions/{id}/close` in
  `src/swayam/api/routes/positions.py`, `close_position`. Fills every leg
  against the book reversed, one result row in `swayam_trade_history`,
  refuses after the bell. `exit_legs` may carry explicit prices, which are
  recorded as supplied, never dressed as fills.
- Live valuation: `GET /api/positions/live` (`LivePositionResponse`), marks
  every leg against the chain feed; `GET /api/positions?status=open|closed`.
- Fills: `src/swayam/services/fills.py`. A market buy pays the ask, a market
  sell gets the bid, a limit fills at his price or better, nothing fills after
  15:30. **Do not change this rule.**
- Charges: `src/swayam/services/charges.py`, `charge_for_leg(side, price,
  units, on)`. The only correct money maths in the repository.
- The execution key: `src/swayam/services/execution_safety.py`,
  `claim_execution`, `canonical_payload_hash`. The hash ignores the spot and a
  market leg's price, keeps a limit price.
- The desk page: `web/src/pages/strategy-builder.js` (`StrategyBuilderPage`,
  `refreshPositions`, `renderMetrics`, `payoffChart` from
  `web/src/components/payoff-svg.js`). **There is no position area on it.**
- Home's strip: `web/src/pages/home.js`. Untouched by this build.
- The note: `src/swayam/services/journal_writer.py` (`append_leg_block`,
  `append_exit_block`); the outbox `swayam_journal_outbox`; the drainer
  `scripts/drain_journal_outbox.py`.
- The record's one mark: `provenance` on `swayam_positions`;
  `api/routes/journal.py` filters `LIVE_PROVENANCE`.
- Migrations up to `021_execution_ticket.sql`. This build adds **022**.
- The open condor: `7cd4d017-2c92-445a-a348-28f395c03db8`, four legs on the
  29 September expiry, `strategy_name` "Short Strangle", `margin_required_inr`
  84,929.20, `spot_at_entry` 23,435.05. **Its legs are stored as JSON on the
  row** with `direction`, `strike`, `option_type`, `expiry_date`, `sequence`,
  `entry_premium`, `side_hit`, `ltp_at_fill`, `bid_at_fill`, `ask_at_fill`,
  `spread_cost_inr`, `entry_charges_inr`, `lot_size`, `quantity_lots`.

## 3. What to build, in this order

### 3.1 The record: a trade whose legs change (migration 022)

His rule, 2026-09-08: "Every leg that I square off will have its own
profit/loss added, and every new leg I add will be considered in the same
trade. Once I close all the legs or I say 'the trade is closed', then only the
trade is closed."

- **A leg carries its own state.** Add to each leg in the `legs` JSON:
  `status` (`open` | `closed`), `closed_at`, `exit_premium`, `exit_side_hit`,
  `exit_ltp`, `exit_order_type`, `exit_limit_price`, `exit_spread_cost_inr`,
  `exit_charges_inr`, `gross_pnl_inr`, `net_pnl_inr`. Legs without `status`
  are open (every existing row).
- **The trade closes when its last open leg closes**, or when the whole trade
  is exited. Then, and only then, ONE row goes into `swayam_trade_history`,
  summing every leg's gross, charges and net, closed legs included.
  `tests/api/test_close_is_idempotent.py` already guards one close, one
  result; keep it green and extend it to the last-leg case.
- **Migration 022** adds to `swayam_positions`: `name_source text NOT NULL
  DEFAULT 'structure'` (`structure` | `his`). Nothing else needs a column: the
  per-leg state lives in the `legs` JSON the row already has. Run
  `tests/test_written_columns_exist.py`; it must pass with 022 applied and
  fail without it if you write any new column.
- **Provenance is not this build's job** (BUILD_02 does the terminal-test
  mark). Do not touch it here.

### 3.2 The name comes from the legs

New `src/swayam/services/structure_name.py`, `name_from_legs(legs) -> str`,
pure, tested with a table in `tests/test_structure_name.py`. It must name:
Long Call, Long Put, Short Call, Short Put, Bull Call Spread, Bear Call
Spread, Bull Put Spread, Bear Put Spread, Long Straddle, Short Straddle, Long
Strangle, Short Strangle, Iron Condor, Iron Butterfly, Call Calendar, Put
Calendar, Diagonal; anything else `Custom, N legs`. Only OPEN legs count.

Applied at execute (`execution.py`, where `strategy_name` is stored), at
add-leg, at exit-leg and at reverse: the stored name is recomputed unless
`name_source = 'his'`. New `PATCH /api/positions/{id}/name` with `{name}` sets
his name and `name_source = 'his'`. **Run the recompute once over the open
condor as part of applying the build?** No. Do not edit 7cd4d017 by script.
Its name corrects itself the first time a leg of it is touched, or when he
presses Edit name. Say so in the handoff.

Why this matters to him, in his words, 10 September: "Short Strangle was not
the name chosen by me. It was the system error that gave it the name." He
loaded the strangle preset, the ticket refused his limit price, he went to a
condor at market, and the name stayed with the preset. He had no role in it.

### 3.3 Exit one leg, reverse one leg

- `POST /api/positions/{id}/legs/{sequence}/exit` with
  `{order_type: MARKET|LIMIT, limit_price?, close_reason?, notes?,
  idempotency_key}`. Fills that one leg reversed through the same
  `services/fills.py` rule: a bought leg is sold at the bid, a sold leg is
  bought back at the ask; a limit fills at his price or better. Charges from
  `charge_for_leg` on the exit side. The leg's state is written as in 3.1; the
  structure (max loss, max profit, breakevens, name) is recomputed for the
  legs still open; the broker margin is re-quoted the way add-leg does it.
  The trade stays open while any leg is open. If this was the last open leg,
  the trade closes exactly as `close_position` closes it, one result row.
  Claims the execution key the way `add_leg_to_position` does.
- **A limit the book has not reached, in THIS build:** refuse that leg only,
  HTTP 422, with the book named and this wording: *"Your price, not a rule:
  the {bid|ask} is {x}. Resting orders arrive in the next build; for now move
  the price or switch to market."* Never a rule tile, never red rule wording.
  BUILD_03 replaces this refusal with a resting order.
- `POST /api/positions/{id}/legs/{sequence}/reverse`: the same exit, then the
  opposite leg added through the add-leg path, in one request, two fills, two
  charge lines, one key. His roadmap gate names "a leg reversed".
- After 15:30 both refuse, naming the leg and saying to do it in the window,
  exactly as the close does today.
- **The note.** The exit of one leg appends an Adjustments line to the trade's
  note (`journal_writer`: a new `append_leg_exit_block`, shape like
  `append_leg_block`), via the outbox when the vault cannot be reached, with a
  new outbox kind `leg_exit`. A closed trade's Exit block stays exactly as it
  is today.

### 3.4 Exit everything, with market or limit per leg

Extend `CloseLegItem` in `positions.py` so each leg carries `order_type` and
`limit_price`. A MARKET leg fills at the book reversed, as today. A LIMIT leg
fills at his price or better, or is refused with the wording in 3.3. An
explicit `exit_premium` with no `order_type` keeps today's behaviour
(recorded as supplied, from a terminal). Only OPEN legs are filled; closed
legs contribute their stored figures to the one result row.

### 3.5 The drainer's close branch, 2.12.5 item 8

`scripts/drain_journal_outbox.py`: a `close` row whose payload has no
`journal_rel_path` (queued as `awaiting_entry_note`) must resolve the path
with `_resolve_note_path(pid)`; if the note already holds an `## Exit`
heading, mark the row done without appending; otherwise append. Test it with
a payload shaped like the two rows in the outbox now (positions 03a1b63d and
8030ed03). **Then he runs the drainer once and both rows complete.** Put that
in the handoff as a manual step.

### 3.6 The live valuation carries what the card needs

`GET /api/positions/live` gains, per position: `legs[]` each with `mark`,
`mark_side` (`bid`|`ask`), `leg_pnl_inr`, `exit_charges_now_inr`, `status`;
and at the top: `charges_in_inr`, `charges_out_now_inr`,
`net_if_exit_now_inr` (gross − in − out), `rule1_cap_inr`,
`rule1_headroom_inr`, `legs_open`, `legs_closed`, `market_state` from
`/api/market/data-health` (`live` | `closing` | `unavailable`) and `read_at`.
A leg that cannot be marked makes the position's total `null` with a reason,
never a partial sum shown as whole. At the close the marks are the last book
and `market_state` says so.

### 3.7 The position area on the desk (screen 2 of the mockup)

New `web/src/components/position-area.js`, mounted in
`web/src/pages/strategy-builder.js` **below the payoff and the execution
block, full width.** Three groups, headed in uppercase: **Open now**, **Closed
today**, **Earlier** (collapsible, remembered in `localStorage`). Reads
`/api/positions` and `/api/positions/live`, refreshes every 5 seconds while
`/api/market/data-health` says live; otherwise holds the last book and the
card says "at the close HH:MM".

**The position card**, exactly as the mockup:
- Header: the name at 22px bold with a sage chip "named from the structure"
  (or "your name"); meta in mono: id, opened (IST), held, expiry, swing;
  a blue chip "terminal test" while the record says so (read the provenance
  it will get in BUILD_02; until then show the chip for every row, because
  every row is one). Buttons right: **Edit name**, **Show on the payoff**,
  **Add a leg**, **Exit everything** (primary). BUILD_02 adds Targets here.
- Six tiles in one row, 1px gaps, each 70 to 80 percent filled: Open profit /
  loss (hero, 46px, colour from the money, sub "marked at the price you would
  get · LIVE 4 s" or "at the close 15:26"); Net if you exit now (30px, after
  charges both ways, in and out shown); Rule 1 headroom (with a bar); Max loss
  (with max profit beneath); Margin (with rule 4's share and a bar); NIFTY
  (with the move since entry and the breakevens).
- The legs table: Side pill, Leg at 17px bold with the expiry beneath, Lots,
  Entry fill with side and traded price beneath, Now with the side and the
  book beneath, Profit / loss at 19px bold coloured, Charges in, To exit, and
  the actions **Exit this leg** and **Reverse**. A closed leg stays in the
  table greyed, with its exit and its result, marked closed.
- Footer: gross, charges in, charges to exit, net now; the refresh note.
- Actions: Exit this leg and Reverse open an inline confirm row with Market /
  Limit, an editable price, a proper **Reset** (icon plus the word), the
  quote, the fill note and what it books; Send and Cancel. Add a leg opens
  the execution ticket with one leg that joins this trade (the path that
  exists). Exit everything opens the exit ticket (3.8).

**Closed today** and **Earlier** rows: name at 17px with when and how
beneath, Gross, Charges, Net at 24px, Fills (bid / ask or traded price), the
chips (terminal test; "not comparable" on traded-price rows). Earlier rows
are dimmed.

### 3.8 The exit ticket (screen 3 of the mockup)

New `web/src/components/exit-ticket.js`, the same shape as
`ExecutionTicket`, reused wherever it can be: per leg Order, Send pill
(reversed), Leg at 17px with lots and expiry beneath, Entry, Market / Limit,
Exit price with Reset and the quote, Fill note, Gross, Charges in, Charges
out, Net at 21px. Below: Gross, Charges in, Charges out, **Net before you
press at 32px**, charges as a share of gross; Close reason (Manual, Target
hit, Stop hit, Time exit), Note for the record, Held. Buttons: **Exit all N
legs**, **Exit one by one**. A limit away from the book shows the amber note
"your price, not a rule" and, in this build, that leg refuses on send with
the wording in 3.3. Opens for one leg (from its row) or all legs (from the
header) **with the same details**. BUILD_02 opens the same component from
Home.

### 3.9 Click a position, see it on the payoff (screen 1 of the mockup)

- **When the desk has no legs loaded and a trade is open, the payoff shows
  it**: `StrategyBuilderPage.loadFromPosition(pos)` builds the leg list from
  the stored open legs at their entry fills, sets the name, and the payoff,
  metrics and rules render for it. A sage band above the payoff says "open
  trade · Iron Condor #7cd4d017 · loaded from your position, not a preset",
  with **Clear and build new**. More than one open trade: the most recent,
  with a switcher.
- **Show on the payoff** on any position card does the same on demand.
- Loading a preset or the chain clears it, as today. **The payoff's drag and
  both sliders are untouched.** The crosshair is BUILD_02.

### 3.10 The price block's wording, 2.12.5 item 2

On the execution ticket, when a limit is away from the book, the note beside
the greyed buttons reads "your price, not a rule", amber, never red, never
beside a rule tile. Same wording on the exit ticket.

## 4. What is NOT in this part, and what is NOT in Build A at all

Not in this part, but in Build A's parts two and three: targets, the Home
band, the crosshair, the terminal-test phase, the big-number pass (BUILD_02);
the option chain (BUILD_04). **Not in Build A at all:** resting orders
(BUILD_03, its own chat). The Trade Journal page (`docs/PLAN.md` §2.18). Any
change to the fill rule. Any edit to trade 7cd4d017 by script.

## 5. How it is verified, and what only his window can prove

- Python: `tests/test_written_columns_exist.py` green with 022;
  `tests/test_structure_name.py` new; `tests/api/test_close_is_idempotent.py`
  extended to the last-leg close; new `tests/api/test_exit_one_leg.py`: exit
  one of four leaves three open and no result row, exiting the last writes
  exactly one result row equal to the sum of the legs, a reverse leaves the
  leg count unchanged with one closed and one new leg, a limit away from the
  book refuses with the wording, all after-the-bell paths refuse; the drainer
  test for the `awaiting_entry_note` close row. Journal folder: 6 notes
  before, 6 after.
- JavaScript: the existing suite plus tests for `position-area.js` and
  `exit-ticket.js` rendering from a captured `/api/positions/live` reply.
- Browser: both themes, against the real backend, with the market shut: the
  position area shows the open condor with every tile real or `unavailable`
  with the reason, the exit ticket opens for one leg and for all, the card
  says "at the close", no console errors. **Screenshots in the handoff, both
  themes, beside the mockup.**
- **Only his window can prove:** a real one-leg exit, a reverse, a whole-trade
  exit through the ticket, the note's Adjustments line landing. Say so in bold.

## 6. The handoff

One handoff for the whole of Build A, at the end, five parts, per
`README.md`. **Manual steps, in bold up front:** apply migrations 022 and 023
(`.\.venv\Scripts\python.exe scripts\apply_migration.py up`); run the drainer
once (`scripts\drain_journal_outbox.py`) so the two stuck close rows
complete; the marking script's dry run, and its `--apply` when he says; and
the line that `scripts\start_paper_trading.py` is NOT to be run until he says
paper trading starts. One bold line: what exists and what does not. Then the
main chat reviews.
