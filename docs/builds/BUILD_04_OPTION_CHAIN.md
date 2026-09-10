# BUILD 04 — THE OPTION CHAIN, TESTED LIVE AND MADE USABLE

> Written 2026-09-10 evening by the main chat as a stub, and filled on
> 2026-09-11 by the builder from screen 6 of the mockup and `docs/PLAN.md`
> §2.12.5 item 9, on his approval of that screen. **This is PART THREE OF
> BUILD A**, built by the same chat, on the same branch and in the same pull
> request as `BUILD_01` and `BUILD_02`. It adds no migration.
>
> **It is not pasted into a chat of its own**; the fence below is kept only so
> its questions can be asked and so the build reads like the other two.
>
> The mockup: screen 6 of
> https://claude.ai/code/artifact/ef242a22-59a7-4752-8aa4-91d59393c5d5
> **Approved as it stands, 2026-09-11.** Both expiries as the recorder
> captured them at the 15:26 close on 10 September, including the 22,850 call
> with its dead 1,575.95 against a live book of 670.95 to 705.40, and max pain
> computed from that open interest: 23,500 on the weekly against 24,000 on the
> monthly, which is the mismatch he saw.

---

```
Swayam Capital, my NIFTY options terminal. THIS CHAT IS A BUILDER CHAT. It
builds the option chain, part three of Build A, on the same branch and in the
same pull request as parts one and two. No migration.

READ THESE, ALL THE WAY THROUGH, IN THIS ORDER.
1. docs/builds/README.md                 how a build works and the rules
2. docs/builds/BUILD_04_OPTION_CHAIN.md  THIS PART, the whole spec
3. docs/PLAN.md section 2.12.5 item 9    what he found on the live market
4. CLAUDE.md, then docs/SWAYAM_START_HERE.md section 1
5. The mockup, screen 6. The build must look like it.

WHAT I FOUND ON 10 SEPTEMBER, IN MY OWN WORDS. The chain rebuilds itself every
five seconds and throws my scroll to the top, so I cannot stay on the strikes
I am reading. A strike that has not traded today shows a dead last price in
live ink. The at-the-money row is not obvious. The buy and sell controls do
not look like buttons. There are too many figures at once. And max pain says
one number on the chain and another on Home, with neither saying which expiry
it belongs to.

MY TWO RULES. No fake data: every figure real from FYERS or the database, or
unavailable with the reason. Never say done, live or passing unless you
checked it on the running system that day and can show me the proof.

MY SCREEN RULES. Numbers I read are big and bold; informative text is small
and muted. Cards are 70 to 80 percent filled. Colour only from the money.
Every card title claims its area. Identical to the mockup.

BEFORE YOU DO ANYTHING, ANSWER THESE IN YOUR OWN WORDS.
1. Why does my scroll jump, and what exactly changes so it stops?
2. What does a strike with no trade today show, and what can I do with it?
3. Which max pain is on Home today, which is on the chain, and what will
   each of them say after this build?
4. What may you never say LIVE without?
```

---

## 1. What this build is for

He used the option chain against a live market for the first time on
2026-09-10 and it built him a real trade: 8030ed03 came out of it at 14:10.
So the chain works. It is also, in his words, unusable while it fights his
scroll.

Four of the five faults are about reading it under time pressure. He has 60 to
90 minutes a day at the screen, from about 2 pm, and a table that throws him to
the top every five seconds costs him the part of that window he can least
spare. The fifth, max pain, is a correctness fault: two screens showed two
different numbers for what looked like the same thing.

## 2. What exists today, verified 2026-09-11

- `web/src/components/option-chain-modal.js`,
  `OptionChainModalComponent`. A floating panel on the desk, opened by the
  "Option chain" button beside "Add leg" in `web/src/pages/strategy-builder.js`,
  wired to `addLegFromChain`. Draggable, Escape closes it, refreshes on a
  5-second timer while open.
- **Its `render()` assigns `this.el.innerHTML` in full.** Every refresh
  replaces the scrolling container along with everything in it, so the scroll
  position is destroyed five seconds after he sets it. That is the whole of
  the scroll fault, and it is confirmed by reading the method.
- It follows the expiry chosen on the desk. There is no expiry switcher in
  the panel itself.
- `GET /api/option-chain?expiry=&strike_count=` in
  `src/swayam/api/routes/market.py` returns, per strike, `ce` and `pe` each
  with `ltp`, `ltp_change`, `ltp_change_pct`, `bid`, `ask`, `oi`, `oi_change`,
  `oi_change_pct`, `volume`, `iv` and `symbol`; and at the top `spot`,
  `atm_strike`, `expiry`, `expiry_epoch`, `days_to_expiry`, `total_call_oi`,
  `total_put_oi`, `pcr`, `max_pain`, `as_of`, `source`, `underlying`.
  **Everything this build needs is already there. No endpoint changes.**
- `calculate_max_pain` lives in `src/swayam/services/nifty_snapshot.py` and is
  used by both the chain route and the Home snapshot.
- **Home's max pain is the WEEKLY one.** `nifty_snapshot.py` computes it from
  the weekly chain and `home.js` prints it under "Options, weekly" as a bare
  "Max pain". The desk's chain computes it for whatever expiry is selected,
  which is usually the monthly. Verified on the running system 2026-09-11:
  Home 23,500 for the 15 Sep weekly, the chain 24,000 for the 29 Sep monthly.
  **Neither said which.** Both figures are correct; the labels were not.
- The Home snapshot already carries `weekly_expiry` and `monthly_expiry`, so
  labelling needs no backend change either.
- `/api/market/data-health` is the one clock, as everywhere.

## 3. What to build, in this order

### 3.1 The scroll stays where he puts it

`render()` stops being the only way to paint. Split it:

- **`_paint()`**, the full build, runs once when the panel opens, when the
  expiry changes, and when the shape of the table changes (More figures on or
  off). It writes the whole panel and then centres the at-the-money row.
- **`_update()`**, the refresh, runs on every 5-second tick. It walks the rows
  already in the document and writes only the CELLS whose text has changed.
  It creates no elements, removes none, and never touches the scrolling
  container. A strike that appears or disappears between reads is the one case
  that forces a `_paint()`, and it says so in the footer when it happens.
- The scrolling container keeps a stable id so nothing else can replace it.

**Test it by invoking, not by reading:** the JavaScript test scrolls the
container, runs three refreshes with changed prices, and asserts the scroll
offset is unchanged and the prices are new.

### 3.2 A strike with no trade today

His example, 2026-09-10: the 22,850 call showed a last trade of 1,575.95 in
live ink against a real book of 670.95 to 705.40. The last trade was from a
different session. Nothing about it was current except the ink.

- **A strike with no trade today is one whose `volume` is 0.** Volume is the
  honest test: open interest survives from previous sessions, a last traded
  price survives for ever, volume is today's.
- Its price cell reads **"no trade today"**, with the live book beneath it as
  `bid / ask`, and the stale last trade **struck through** and labelled, so he
  can see it exists without mistaking it for a price. Whole cell in muted ink.
- **Buy and Sell on that side are disabled**, with the reason on hover: no
  trade today, the book is shown, it cannot be added for a fill. It cannot be
  added to the desk by any route.
- The footer says what the grey means, once, in words.

### 3.3 The at-the-money row, unmistakable

- The row whose strike is closest to spot takes a **sage band** across its full
  width, a sage strike cell with white text, and an **ATM** pill under the
  strike. Sage, not a money colour: it is a fact about the market, not about
  his money.
- **Centred when the chain opens**, and re-centred by a **Centre on ATM**
  button in the header, because spot moves and he may have scrolled away.
- In-the-money cells stay shaded as they are today, on the correct side.

### 3.4 Buy and Sell as real buttons

The hover-revealed B and S become **Buy** and **Sell**, outlined in the money
colours, filling on hover, at a size he can hit without aiming. His standing
rule: no cheap icon where a control belongs. Disabled state is visibly
disabled and carries its reason.

Clicking one adds the leg to the desk exactly as it does today, at the price
on screen, with the panel staying open so a four-leg structure is four clicks.

### 3.5 Four figures a side, and the rest on demand

At a glance, per side: **open interest** with its bar, **change in open
interest**, and the **price** with the book beneath it. That is four figures
including the book, which is what he reads to place a strike.

**IV and volume move to hover and to More.** Every money cell carries a title
with IV, volume and the book. A **More figures** button adds IV and volume as
columns and becomes **Fewer figures**; the choice is remembered in
`localStorage`. Turning it on or off is a shape change, so it repaints and
re-centres.

### 3.6 Max pain says which expiry it belongs to

- On the chain: **"Max pain · 15 Sep weekly"**, with the other expiry's max
  pain named beneath it, so the two numbers he saw are on one screen with
  their labels attached.
- The other expiry is read **once** when the panel opens and when the expiry
  changes, not on the 5-second tick.
- **An expiry switcher in the panel**: weekly and monthly, each with its own
  days to expiry, so he can compare without leaving the chain. It does not
  change the expiry on the desk; the desk's own picker still owns that.
- On Home: **"Max pain, 15 Sep weekly"**, from the expiry the snapshot already
  carries. If the snapshot has no expiry to name it with, the label says
  unavailable rather than an unlabelled number.

### 3.7 The panel reads like the rest of the desk

Header at 20px bold, the six figures as tiles in one row exactly as the
position card does them (NIFTY with the ATM strike, max pain with its expiry,
put-call ratio, call OI, put OI, and the count of in-place refreshes with
"your scroll kept every time"). Sticky table header. The footer explains the
shading, the grey and the hover in one line each.

**Nothing says LIVE unless `/api/market/data-health` says the market is open.**
The panel's chip reads the market state, not the age of the read: at the close
it says so and names when the book was read.

## 4. What is NOT in this build

Resting orders (BUILD_03, its own chat). Anything on the Trade Journal page
(`docs/PLAN.md` §2.18). Any change to the fill rule, the charge engine or the
chain endpoint. Any change to how the desk chooses its expiry. Max pain's
maths, which is correct and only needed labelling.

## 5. How it is verified

- JavaScript: the scroll is kept across three refreshes with changed prices; a
  zero-volume strike renders "no trade today" with its book and a struck
  last trade, and its buttons are disabled and cannot add a leg; the ATM row
  is marked and centred; More figures adds the two columns and is remembered;
  max pain carries its expiry and names the other one; the panel says LIVE
  only when the market state says live.
- Browser, both themes, against the real backend: open the chain on the desk,
  scroll to a strike, watch it stay through several refreshes, switch expiry,
  read the two max pains with their labels, add a leg from a live strike, and
  fail to add one from the dead strike. No console errors.
- **Only his window can prove** that the rows change while he watches, because
  with the market shut every refresh returns the same closing book. The
  handoff says so.

## 6. The handoff

Part of Build A's single handoff, at the end. **This part adds no migration
and no script.** The only thing to watch on the first live day is whether the
in-place refresh keeps his scroll when the numbers are actually moving.
