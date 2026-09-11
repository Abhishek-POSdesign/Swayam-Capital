# BUILD 06, THE CLARITY PASS — HANDOFF TO THE MAIN CHAT

> Written 2026-09-11 night by the polish chat. **He pastes the PATH of this file
> into the main chat**, per the habit agreed earlier tonight.

**Branch** `feature/swayam-look-clarity-055` · **Pull request** #78 · off `main`
at `02f904b`. Follows #76, which he merged. **No manual step.**

---

## 1. What he approved, from the mockup at
`https://claude.ai/code/artifact/81a58764-e291-4fc3-a373-548d61c8ff34`

| His point | Built |
|---|---|
| Caps: text and number must differ in size | Three sizes: name 11px uppercase, figure 23px, percentage 11.5px muted |
| Caps: the percentage sits by the number | Inline, small and muted, right after the figure |
| Your money: **no change at all** | Untouched. The four pastels are exactly as #76 shipped |
| Position card | Approved as mocked and built as mocked |
| Desk row: max profit and max loss bigger | 34px for those two, 23px for the other four |
| Desk row: breakeven must look like a journey | Drawn as a road, see §3 |
| The muddy look | It was the ink, not the paper, see §2 |

## 2. THE MUDDINESS WAS THE INK. Measured, not judged by eye.

Atlas's muted grey reads on Atlas's tiles. Laid on the lighter tiles Swayam
uses, the same hex falls to **3.0 : 1**, under the readable threshold. That is
what he kept calling muddy, and it was not the warm paper.

| | before | after | contrast on a tile |
|---|---|---|---|
| light `--fg-3` | `#94928e` | `#78756e` | 3.0 → 4.5 |
| light `--fg-2` | `#6c6b68` | `#56544f` | |
| dark `--fg-3` | `#8f8f8f` | `#95928b` | 4.5 → 5.5 |
| dark `--fg-2` | `#c4c4c4` | `#bdbbb6` | |

Changed in **both** token files and **all six** theme blocks.

## 3. Breakeven as a road

His words: *"it must show that the price is travelling from this place to this
place."* The tile draws the band where the structure keeps money, the two edges,
and NIFTY's own dot on the track: green when it sits between the breakevens, red
when it is outside. The two figures sit at the ends of the road.

**Nothing is computed.** The breakevens and the spot are the same figures the
tile printed before; only the drawing is new. `_breakevenTile()` in
`web/src/pages/strategy-builder.js`.

## 4. The folding rule, which is now settled

His instruction: *"when I put my mouse on the number they should appear, and
when I remove my mouse they should disappear... if you think something is really
important and should be visible, then I am okay with that, but not everything."*

**Every tile keeps ONE short line of fact and folds the explanation.** The hint
is a real element, not a `title` attribute, so it is styled for both themes; it
carries `tabindex="0"`, so the keyboard reaches what the mouse reaches. The
helper is `hint(label, said)` exported from `position-area.js`; the CSS is
`.sw-desk .hint` in `swayam-desk.css`.

Folded so far: the four caps on Home, and all six tiles of the position card.
**Anything else that still prints a sentence can use the same helper.**

## 5. TWO FAULTS FOUND, NOT FIXED, AND NOT LOOK

Both were raised by him and both are behaviour, so neither belongs in a CSS
build. **They need their own build.**

### 5.1 A held trade never gets its volatilities, so the blue curve never draws

Measured on the running desk. Landing directly on `/strategy` with the open
condor auto-loaded:

| seconds after load | volatilities held | re-quote timer |
|---|---|---|
| 5, 10, 15, 20, 25, 30 | **0** | running |

A ready-made preset fills all four within a second or two. So:

- **Strikewise IV** shows "unavailable — no traded price to imply from".
- **The blue "today" curve cannot be drawn**, and the graph says so: *on-date
  curve unavailable, no measured IV*.

**One cause, both symptoms.** `loadFromPosition` builds the legs from the stored
entry fills and never asks the chain for a quote, so `ivPctByStrike` stays empty.

**It is path-dependent**, which is worth knowing before someone "fixes" it:
arriving at the desk by clicking through from Home, the volatilities DO appear.
Landing on `/strategy` directly, they do not, for at least thirty seconds.
Whoever takes this should find why those two paths differ rather than assume.

The fix must re-quote the legs **while keeping the entry fills as the prices**,
or the at-expiry curve and every rule figure would move.

### 5.2 Two open positions

He asked what he would see. Today: the desk auto-loads the **most recently
opened** trade, and every position card's "Show on the payoff" switches to
another. There is no switcher above the graph. His own instinct was right and
nothing is broken; it is only undocumented.

## 6. Verified today

- **JavaScript 348 passing in 36 files.**
- The Python suite still shows the stale notifications mock, which belongs to
  **PR #77** and not to this branch.
- Both themes, on the running desk, against the real backend.
- **His journal folder: one note and seven terminal tests, before and after.**
- No figure moved. The condor reads the same numbers it did before the change.
