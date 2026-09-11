# BUILD 06, ROUND TWO — HANDOFF TO THE MAIN CHAT

> Written 2026-09-11 night by the polish chat, the same chat that built round
> one (#72) and round 1b (#74). **He pastes the PATH of this file into the main
> chat rather than copying its contents.** That is the habit from now on: every
> message between a builder chat and the main chat is a file in
> `docs/handoffs/`, named after its build.

**Branch** `feature/swayam-look-round2-053` · **Pull request** #76 · cut off
`main` at `ad06dcb`, which already contained the main chat's own #75.

**No manual step. No migration, no script, no config.**

---

## 1. What was built

Everything in `BUILD_06_THE_LOOK.md`, plus one correction to that document and
one rule he gave while it was being built. Four files, all presentation:

| File | What changed |
|---|---|
| `web/src/styles/swayam-desk.css` | Atlas's grounds in all three theme blocks; tiles filled and rounded; the chain's Buy and Sell as pastel fills; four near-black buttons to sage |
| `web/src/styles/swayam-tokens.css` | Atlas's grounds and light accents; the `--accent-lilac` alias deleted entirely |
| `web/index.html` | the last literal violet, and the three references to the lilac token |
| `web/src/components/position-area.js` | two tiles tagged as facts, so the money tiles stay neutral |
| `docs/builds/BUILD_06_THE_LOOK.md` | section 5, the amendment, appended to the main chat's own copy |

**No Python. No route, no service, no model, no migration.** Nothing that can
move a number was opened.

## 2. The correction the main chat needs to carry forward

**BUILD_06 section 1.1 named one token file and there are two.** He checked and
agreed: *"you are right and my document was wrong."*

- `swayam-tokens.css` dresses the header, the AI drawer and the Trade Journal.
- `swayam-desk.css` dresses **Home, the Strategy Desk, both tickets, the option
  chain and the targets modal**, which all render inside `.sw-desk`.

Changing only the first would have restyled the journal and left the two pages
he looks at every day untouched. Both were changed, every token NAME kept. The
full detail, with the before-and-after values, is section 5 of
`docs/builds/BUILD_06_THE_LOOK.md` on this branch.

## 3. The tile rule, which is now settled and belongs in the standing rules

His words, after seeing the first build: *"colour comes from the money only. So
on the position card, tint the tiles that hold a FACT and leave neutral the
tiles that hold MONEY."*

- **Money tile, neutral ground**, so the green or the red of the figure is the
  only colour in it. On the position card: open profit and loss, net if you
  exit now, rule 1 headroom, max loss.
- **Fact tile, pastel ground**, because there is no result for the colour to
  fight. On the position card: the broker's margin, and the NIFTY level.
- **Home's Your money is tinted throughout** for the same reason: balance, free
  cash, collateral and margin used are facts about the account.

Implemented as a `.met.fact.<colour>` class rather than a position in the grid,
so a tile that changes meaning changes its own class.

## 4. His warning about the money, and how it was held

*"`--up` and `--down` are not accents. They are the colours he reads his MONEY
in, and they are the only colours on the screen that are allowed to shout.
Atlas has no equivalent, so there is nothing to copy and you will be tempted to
mute them to match everything else. Do not."*

They are not muted. The grounds went calm, the accents went calm, the money
stayed loud. Their backgrounds moved from solid cool tints to `rgba`, so green
and red tint the warm paper rather than sitting on it as a cold mint or pink
patch. That was the adjustment for contrast he authorised instead of softening.

## 5. Proof, taken on the running system on 2026-09-11

| | |
|---|---|
| The open condor `7cd4d017` | Read before the build and again after. **Byte-identical**: profit, net, both charge figures, margin, both breakevens, all four legs with their marks and per-leg results |
| Python | 705 passing, 1 failing: the stale `test_notifications` mock that fails identically on `main` |
| JavaScript | 348 passing in 36 files |
| Violet | `lilac`, `purple`, `violet`, `#ac9fd2` return **zero** across `web/src` and `web/index.html` |
| Hardcoded hexes outside the token file | 158 before, 143 after; 48 of those are token definitions in `swayam-desk.css`, 20 are in dead code |
| His journal folder | One note and seven terminal tests, before and after every run |
| Screenshots | Home, the desk, the option chain and the Trade Journal, both themes, every one showing a profit and a loss figure together |

## 6. What the main chat should know is NOT done

- **The AI chat panel is untouched**, as instructed. It still carries its old
  colours and will look out of place until BUILD_07. Its attachment thumbnail
  also has a hardcoded dark, left alone for the same reason.
- **The Trade Journal was not redesigned.** It inherits the tokens and was
  photographed only to prove the palette did not break it.
- **Home's last-backup age was not touched.** That is BUILD_05's one line.
- **`src/modules/payoff-chart.js` is dead code**, twenty hardcoded colours,
  imported by nothing. Left in place deliberately: deleting a file is not a look
  change. **It should be removed in a later pass.**
- **The desk's metric row above the payoff is still neutral throughout.** The
  fact-and-money rule was applied to the position card. If the main chat wants
  it on the metric row too, that is a small follow-up.
