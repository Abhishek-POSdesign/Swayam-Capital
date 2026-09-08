# UI BUILD BRIEF — ROUND 3

> Written 2026-09-08 evening, from Abhishek's own sweep of the live pages.
>
> Read `docs/SWAYAM_START_HERE.md` for where everything lives and `docs/PLAN.md`
> for the order of work. **This brief is the frontend job.** A separate backend
> job is listed in §8 and is NOT yours; do not touch those files.

---

## 0. THE RULES YOU ARE JUDGED ON

1. **NO FABRICATED VALUES.** Every number is real from FYERS or the database, or
   it says `unavailable` with a reason. Never a placeholder, never a fallback
   constant, never `|| 0` on a rendered figure.
2. **NEVER SAY "LIVE" ABOUT SOMETHING THAT IS NOT.** Three separate places were
   caught claiming LIVE over a closing price on 2026-09-08. Two are fixed. Do
   not add a fourth. If you need the market clock in a component, read
   `market_open` from `/api/market/data-health`, which is the one clock.
3. **NO PURPLE, LILAC OR VIOLET.** He has complained many times. `--accent-lilac`
   aliases blue. The brand accent is **sage** (`--accent-sage`).
4. **DO NOT BREAK WHAT WORKS.** The payoff graph, its drag behaviour and its two
   sliders are praised and settled. The AI chat's behaviour is settled. The
   four-rule block is settled. You are changing layout and colour, not logic.
5. **NEVER CLAIM SOMETHING WORKS THAT YOU HAVE NOT RUN.** Load the real page in
   a real browser. `node --check` is not verification.
6. **Do not merge.** Open the pull request and stop. He clicks Merge.

Run both suites before you open anything: `npm test` in `web/` (206 pass today)
and `python -m pytest -q` from the root (394 pass, 1 known failure in
`test_notifications`).

---

## 1. THE PROBLEM HE REPORTED, IN HIS WORDS

> "On the dashboard there is one issue, and this is something I don't like: a
> dead background. When you see the open position, it is showing a dead
> background behind it because there is no open position. That's why it is kind
> of squeezed and showing a dead background."

Home's third row is a two-column grid. **Open positions** sits on the left and
**Events ahead** on the right. Events ahead holds five rows; Open positions
holds one sentence. The left cell stretches to match the right and leaves a
large empty panel. That is the dead space.

---

## 2. THE HOME LAYOUT. His design, with two additions of mine.

### 2.1 Open positions becomes a full-width collapsible strip — HIS DECISION

- One full-width row, **not** a half-width card.
- **Collapsed by default when nothing is open**, and it stays a single muted
  line: "Nothing open. Your paper record starts clean from 8 September."
- **Expandable and collapsible** by click, with the state remembered in
  `localStorage` per viewer.
- **Colour follows the money, and only the money:**

| State | Treatment |
|---|---|
| Nothing open | grey, muted, one line |
| Open and in profit | sage left border, profit in sage |
| Open and in loss | coral left border, loss in coral |

  Use `--accent-sage` and `--accent-coral`. Never red-on-green traffic lights,
  and never a colour when there is no position to colour.

**My addition, and I recommend it:** put this strip **directly under the data
health strip, above "Your money"**. When he has a live position at one o'clock
it is the most important thing on the page and should be first. When he is flat
it costs one muted line. Today it sits below the fold, which is backwards.

**My second addition:** when collapsed with a position open, the single line
must still be useful. Show the count, the combined profit or loss, and the
closest rule headroom. For example: "2 open · −₹1,240 · running loss 13% used".
A collapsed strip that says nothing is just a smaller dead space.

### 2.2 Your record moves into the two-column row — HIS DECISION

- **Your record** takes the left cell, beside **Events ahead**, and the two are
  made equal height with `align-items: stretch` on the grid.
- It lists his performance figures as rows, in the same shape as Events ahead:
  **win rate, cumulative profit, expectancy**, and whatever else the analytics
  endpoint returns.
- The Paper / Real money toggle stays exactly as it is.

**My addition, and this is the part that actually kills the dead space:**
**render the real rows as a skeleton, not a sentence.** With no trades yet, draw
each row with its label and a muted em dash for the value. Do not print "No
paper trades yet" and leave the rest empty.

Two reasons. The card fills its height honestly, so there is nothing to stretch
around. And the layout does not jump the day his first trade lands, because the
rows are already there. Keep one muted line underneath explaining why they are
empty, and keep the existing sentence about the 81 quarantined rows.

An empty value is `—`, never `0`, never `0%`. A zero win rate and an unknown win
rate are different things and must not look the same.

### 2.3 Today's limits shrinks into Your money — MY RECOMMENDATION, he asked for one

> "I don't think this belongs here because this belongs to Strategy Builder on
> the execution page... I think it is just a repeat of a margin ceiling that I
> already have. This is a big strip, so this belongs to the strategy page."

He is right that a full-width strip of four large tiles is too much weight on a
page whose job is forming a view of the market. He is also right that it repeats:
all four caps already appear on the desk, in the ticker strip and again in the
four-rule block, at the moment he is actually deciding.

**But do not delete it from Home.** His rule 1 is one percent of a balance read
fresh every session, and seeing today's four numbers before he starts is the
discipline the terminal exists to enforce.

**Do this instead.** Remove the standalone "Today's limits" card. Add its four
figures as **one small line inside the "Your money" card**, under the five money
tiles, where they belong logically because they are derived from the balance
directly above them:

> Today's caps · running loss ₹9,711 · overnight gap ₹19,422 · black swan
> ₹48,556 · margin ceiling ₹5,54,961

Keep the existing sentence "a percentage of the balance above, never a stored
number", which is the honest part and must survive. Move the long paragraph
about nothing blocking an intraday entry to the desk, where the decision is made.

This frees a whole full-width row, which is most of the vertical budget the two
changes above need.

### 2.4 Events ahead shows the impact brief — NEW, and the data already exists

He asked what this card is and whether the AI can research it.

**The answer is in §7.** The short version for you: every event row may carry an
`impact_brief`, written by the macro curator, and **the API already returns it
and the card already ignores it.** Two of the five events on his screen have one
sitting unused in the database.

- Show the brief under the event name, muted, one or two lines.
- Rows without a brief simply do not show one. Do not invent a placeholder and
  do not write "no brief available" on every row.
- Keep the existing footer: "From your own macro events table. Nothing here is
  scraped live yet." It is true and it must stay true.

---

## 3. THE AI CHAT COLOURS — HIS DECISION

> "The AI chat box we have has this green color, which looks ugly and alien in
> the whole dashboard, where the whole dashboard is kind of muted and calm. This
> has to be changed. Something like Claude or Gemini: the AI chat stays without
> any background, and my chat should have a light-colored background just so
> that it will differ from the AI text."

| Whose message | Treatment |
|---|---|
| **His** | A light sage tint background, `--accent-sage-tint`. Normal body text colour, not white on green. Rounded, and it may stay right-aligned. |
| **The AI's** | **No background at all.** Plain text on the page, full width, same colour as body copy. |

The saturated green bubble goes entirely. Check it in **both light and dark**:
the tint is defined in both themes, so read the value, do not hardcode a hex.

The attachment thumbnail, the character counter, the send button and every
behaviour stay exactly as they are. This is colour only.

---

## 4. THE LOT MULTIPLIER BECOMES A STEPPER — HIS DECISION

> "I also want to change this lot multiplier option from the dropdown. The
> default all-lot multiplier, which is next to the expiry all legs, should have
> 1 in between and +, −, left and right."

On the Strategy Desk, the **global** "Lot multiplier" control beside "Expiry,
all legs" becomes `−  1  +`. Minus on the left, the number in the middle, plus
on the right. There is room in that toolbar.

- Minimum 1. It must never reach 0 or go negative.
- The number is typeable as well as steppable, so he can jump to 10 without
  eleven clicks.
- It drives every leg exactly as the dropdown does today. **No maths changes.**

**The per-leg LOTS dropdown in each leg row is NOT in scope** and stays a
dropdown, unless he says otherwise. See the open question in §9.

---

## 5. TEXT CONTRAST — HIS OBSERVATION, needs a judgement

> "I see a lot of muted text, like sentiment bearish. The text is very muted,
> which is important text to read actually. Is this because the market closed,
> or will it stay muted and light?"

**It is not the market.** It is a fixed style and it looks the same at one
o'clock. The answer to his question is: it will stay muted until changed.

The values themselves are `--text-primary` and are fine. What reads as washed
out is the explanatory paragraph under each sidebar card, `.why`, set at
`--fg-3`, which in the light theme is `#64748b` at 12px.

**Raise `.why` from `--fg-3` to `--fg-2`** (`#334155` light, `#a9afbd` dark).
Keep it smaller than body copy, because it is secondary, but it should be
readable rather than decorative. Do not touch the all-caps section labels; those
are meant to recede.

Check the result against a real screen in both themes before claiming it is
better. Contrast is the one thing that cannot be judged from the code.

---

## 6. WHERE A POSITION APPEARS, once he takes one

He asked, and it is worth writing down because he has never had one.

| Where | What shows |
|---|---|
| **Home**, the strip from §2.1 | Every open paper position, with combined profit or loss |
| **Strategy Desk**, `refreshPositions()` | Margin used, which feeds rule 4, and the close controls |
| **Trade Journal** | The full record once closed, with the lesson and the rationale |

He has agreed to take a dummy paper position with the market open to see all
three. **Nothing in this brief should be claimed as working for a live position
until that has been done.**

---

## 7. WHAT THE EVENTS CARD ACTUALLY IS — background, no work required

He asked where the data comes from. Answering it here so it is written down once.

- The rows come from **his own Supabase table, `swayam_macro_events`.** The dates
  are seeded, not scraped. The card already says so.
- A curator, `src/swayam/services/macro_curator.py`, sends the next seven days
  of events to Gemini, marks three to five as highlighted, and writes an
  **`impact_brief`** on each of those. That is why §2.4 exists.
- **The AI chat already reads these events.** `ai/context_builder.py` puts the
  highlighted ones into the context under "Upcoming Macro Risk & Planning
  Context". He does not need to paste them in.
- **Internet research is possible and already built, but not wired to events.**
  `src/swayam/ai/grounded.py` runs Gemini with Google Search grounding, and it
  is used by exactly one feature, the So Far Today summary. Pointing it at event
  research is a real option and a separate job. **Not in this brief.**

---

## 8. NOT YOURS — the backend half, being done separately

Do not edit these files. They are being fixed in a separate change and you will
get the corrected fields for free.

1. **`src/swayam/services/nifty_snapshot.py`, the LIVE flag.** `spot_live` means
   "FYERS returned a number", not "the market is open", so `spot_freshness` and
   `sector_freshness` both read LIVE after the close. That is why his Sectors
   card said "LIVE · read 20:04 IST" at eight in the evening.
2. **The same file's `weekly_expiry`.** It reads the raw expiry metadata rather
   than the corrected endpoint, so Home's Options card still shows "Days to
   weekly expiry 0d · 1 session" on the evening of an expiry day. This is the
   blackout bug he reported, surviving in a second place.

---

## 9. OPEN QUESTIONS FOR HIM. Ask, do not guess.

1. **The per-leg LOTS dropdown.** §4 changes only the global multiplier. Should
   each leg's own lots control become a stepper too, or stay a dropdown?
2. **Where the record strip sits.** §2.1 recommends moving Open positions above
   "Your money". That is a change he did not ask for and it changes the first
   thing he sees. Confirm before building.

---

## 10. VERIFICATION, before the pull request

Run it in a real browser against the real backend, on both pages, in **both
light and dark**.

- [ ] With nothing open, Home has **no empty panel** anywhere in the two-column row.
- [ ] Your record shows its three labels with muted dashes, not a bare sentence.
- [ ] Open positions is one muted line, and it expands and collapses.
- [ ] Today's limits is gone as a card and present as one line in Your money.
- [ ] The four cap figures are unchanged from what the API returns.
- [ ] Events with a brief show it; events without one show nothing extra.
- [ ] His chat messages have a light sage background; the AI's have none.
- [ ] The lot stepper cannot reach 0, and changing it moves every leg.
- [ ] `.why` text is readable in both themes.
- [ ] Nothing anywhere says LIVE while the health strip says CLOSED.
- [ ] `npm test` and `pytest -q` both at or above today's counts.

State plainly in the pull request what you ran and what you could not.
