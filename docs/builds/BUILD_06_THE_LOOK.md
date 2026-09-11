# BUILD 06 — THE LOOK. Swayam goes home to Atlas. "ROUND TWO"

> Written 2026-09-11 night by the main chat, after he saw the AI panel mockup
> and asked the question this build exists to answer: **"Why doesn't my website
> have these colours? Why do they have these colours that I don't like at all,
> to be honest?"**
>
> This is **round two** of the polish chat's work, promised in `docs/PLAN.md`
> §2.12.8 and held back until round one and round 1b were merged. They are:
> #72 and #74. **This build goes to the SAME polish chat**, because it already
> holds every page it will touch.
>
> **The prompt he pastes is in the fence below.**

---

## 0. THE ANSWER TO HIS QUESTION, MEASURED

His accents are **already Atlas's**, to the hex. What was never copied is the
ground they sit on, and that is the whole problem.

| | Swayam today, `web/src/styles/swayam-tokens.css` | Atlas, `D:\Claude\POS\Atlas\Deploy\css\tokens.css` |
|---|---|---|
| Dark background | `#101116` cold blue-black | `#1a1a1a` warm charcoal |
| Dark card | `#191b21` | `#202020` |
| Dark card, raised | `#20232b` | `#2a2a2a` |
| Dark text | `#edeff4` cold white | `#e2e2e2` warm grey |
| Dark sage | `#86ab92` | `#86ab92` **identical** |
| Dark blue | `#759ad0` | `#759ad0` **identical** |
| Dark coral | `#dd8170` | `#dd8170` **identical** |
| Dark amber | `#c9a04a` | `#c9a04a` **identical** |
| **Light sage** | **`#15803d` a vivid saturated green** | **`#6f8f65` muted** |

**So a warm sage is being laid on a cold blue-black.** That mismatch is what he
reads as harsh, and the light theme is worse still, because its green is a
different colour altogether rather than a lighter version of the same one.

His own token file already says, in its first line, that it was **inherited
from Atlas** and names Atlas's two files as its canonical reference. **This
build is going home, not starting over.**

---

```
Swayam Capital, my NIFTY options terminal. THIS IS ROUND TWO, and you are the
same chat that built round one and round 1b. You now change how the whole
terminal LOOKS. You are not adding a feature and you are not fixing a bug.

READ THESE, IN THIS ORDER.
1. docs/builds/BUILD_06_THE_LOOK.md      THIS BUILD, the whole spec
2. docs/builds/README.md                 the rules every builder follows
3. docs/PLAN.md 2.12.8 and 2.12.10
4. CLAUDE.md
5. The palette, live and interactive, in both themes:
   https://claude.ai/code/artifact/f3efa90c-c57d-4dba-bd00-924b3c04ee04
   The desk cards, the tiles, the table and Home's tiles in that mockup are
   what my pages must look like when you are done. The floating panel in it
   is NOT yours: that is BUILD_07, a different chat, after you.

WHAT I SAID, AND IT IS THE WHOLE BRIEF. "I do not like how Swayam looks and I
see it every day. My Atlas app is the reference." Soft pastel FILLED cards and
buttons, no dark corners, no dark outlines, no muddy fills, no shiny colours,
generous spacing, very large calm numbers my eye reads instantly, a clear text
hierarchy. Sage, coral, amber and blue. NO lilac, purple or violet, anywhere,
including as a fallback value in a var() that renders blue today.

WHO I AM. Abhishek. Not a developer. Plain English, never code to approve, a
recommendation rather than a menu. Night shift: awake around 1 pm IST, at the
screen by 2 pm, I trade 1 to 2:30 pm. Never plan anything for 09:15.

MY TWO RULES. No fake data, ever, or unavailable with the reason. Never say
done, live or passing unless you checked it on the running system that day and
can show me the proof. For this build the proof is screenshots of every page in
BOTH themes, not a passing test.

HOW WE WORK. Branch feature/swayam-look-round2-0NN off main, never main, never
a worktree. Plan first in plain English, six parts, and wait for my yes. Hand
off in five parts with one bold line saying what exists and what does not.

DO NOT TOUCH: any behaviour. No route, no calculation, no rule, no fill, no
charge, no migration. If a change makes a number move, you have gone outside
this build. The AI chat panel is BUILD_07's and you leave it alone. The Trade
Journal page waits for its own discussion. docs/ROADMAP.md needs my yes.

BEFORE YOU DO ANYTHING, ANSWER THESE IN YOUR OWN WORDS.
1. Which of my colours are already Atlas's, and which three are not?
2. What is wrong with my LIGHT theme specifically?
3. Where is the last literal violet in my codebase, and why has nobody seen it?
4. What proves this build worked, and what would NOT prove it?
```

---

## 1. What to change

### 1.1 The token file, `web/src/styles/swayam-tokens.css`

Take Atlas's **surfaces, borders, shadows and text** in both themes, exactly as
`D:\Claude\POS\Atlas\Deploy\css\tokens.css` has them. The four accents already
match in dark; **the light theme's accents are replaced with Atlas's**, which is
where the vivid green goes.

Atlas's light ground is `#ebe8e1` with cards at `#f8f6f2` and `#fdfbf7`: a warm
paper, not a white sheet. Its dark ground is `#1a1a1a` with cards at `#202020`
and `#2a2a2a`.

Keep every token NAME Swayam already uses, so nothing downstream has to change.
This is a change of values, not of vocabulary.

### 1.2 The last violet

`web/index.html` carries

```
border-left: 2px solid var(--accent-lilac, #ac9fd2)
```

The token is aliased to blue so it renders blue, **and the literal violet is
still sitting there** waiting for the day someone removes the alias. Delete it
and use a sage or blue token outright. Then grep the whole repository for
`lilac`, `purple`, `violet`, `#ac9fd2` and `#8169c5` and report every hit.

### 1.3 Anything that hardcodes a colour

Every literal hex outside the token file is a place where the theme cannot
follow. Find them and move them to tokens. **Report the count before and after.**

### 1.4 The shapes, not only the colours

His standing screen rules, already in `docs/builds/README.md`, now applied to
every card on every page:

- **Filled pastel cards and buttons.** No dark outlines, no muddy fills.
- **Cards 70 to 80 percent filled** with their information.
- **Numbers he reads are big and bold.** Informative text small and muted.
- **Card titles claim their card**, 16px weight 800 in the primary ink.
- **A dustbin for delete, a proper Reset button.** Never a cheap cross, never a
  small round icon where a button belongs.
- **Every table of figures stays monospaced and aligned**, `tabular-nums`.
- Buy and Sell on the option chain as small pastel-filled buttons.

---

## 2. What is NOT in this build

- The AI chat panel and Home's chat zone. **BUILD_07.**
- The Trade Journal page. It waits for his own discussion, `PLAN.md` §2.18.
- Any behaviour at all. If a figure changes, something went wrong.
- The last-backup age on Home. **That belongs to BUILD_05** and is the one line
  of Home that build touches, so the two never collide.

---

## 3. How it is verified

**By looking, in a real browser, against the real backend, in both themes.**

| | Proof |
|---|---|
| Every page | A screenshot of Home, the desk, the option chain and the journal, light and dark, eight in all |
| No behaviour moved | The Python and JavaScript suites at the counts in `SWAYAM_START_HERE.md`, and the open condor's figures identical before and after |
| No violet anywhere | The grep output, in the handoff, showing zero |
| Nothing hardcoded | The count of literal hexes outside the token file, before and after |
| His journal folder | One note and a Terminal tests subfolder, before and after every run |

**The open condor `7cd4d017` is untouched, as always.** Nothing in this build
may write to the record.

---

## 4. The handoff

Five parts, files as clickable links, and the screenshots inline. One bold line
saying what exists and what does not. **Say plainly whether anything on any page
still does not match the mockup**, rather than letting him find it.
