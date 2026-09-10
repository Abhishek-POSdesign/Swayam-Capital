# THE BUILDER CHATS. How a build leaves the main chat and comes back.

> Written 2026-09-10 evening, at his request. **The main chat is the
> orchestrator and does not build.** It plans, draws the mockup, writes the
> build document and its prompt, reviews the finished build with him, and says
> "all good" before he merges. Each build is done by a fresh chat that reads one
> build document and nothing else of its own choosing.

---

## The loop, in his words

1. The main chat says "the plan is ready" and gives him a prompt.
2. He opens a new chat and pastes that prompt. That chat builds **one build**.
3. When the builder says it is done, he runs it, iterates with the builder
   until it looks right to him, then brings it to the main chat.
4. The main chat reviews the running build against the build document and the
   mockup, and says "all good" or lists what is wrong.
5. Only then does he click Merge. Then the next build.

**One build, one chat, one pull request.** Builds run one at a time, because
only one session may write to the working folder.

## The builds. TWO, his correction of 2026-09-10 late evening.

He does not have whole days to open chats, answer questions and re-explain.
So the plumbing is ONE build in ONE chat and ONE pull request, and only the
trickiest piece, resting orders, is left aside for its own chat.

| Build | Documents, read in this order | Branch | What it is |
|---|---|---|---|
| **A** | `BUILD_01_DESK_POSITION_AREA.md`, then `BUILD_02_HOME_TARGETS_AND_READING.md`, then `BUILD_04_OPTION_CHAIN.md` | `feature/swayam-build-a-desk-home-chain-042` | The position area on the desk, the exit ticket, the campaign model, the name from the legs, click-to-load, the drainer fault; then Home's running-trade band and its states, targets, Manage from Home, the crosshair, the terminal-test phase, the big-number pass; then the option chain. **Built in that order, handed off once at the end**, with a short progress note in the chat after each of the three parts. Migrations 022 and 023 |
| **B** | `BUILD_03_RESTING_ORDERS.md` | `feature/swayam-build03-resting-orders-044` | A limit away from the book rests as an open order, entry and exit, with a watcher, Modify and Cancel, expiry at the bell. **After Build A is merged.** Migration 024 |

The option chain's look is judged by eye, so the main chat supplies its mockup
into Build A's chat while the builder is on the desk and Home; the builder
starts the chain only when that mockup is in hand.

The mockup every build is held to: https://claude.ai/code/artifact/ef242a22-59a7-4752-8aa4-91d59393c5d5
(**Swayam Position Area**, 10 September evening). It is built on his real open
condor 7cd4d017 marked at the 15:26 IST closing book. **The build must look
like it.** Not "inspired by": identical in hierarchy, sizes and placement.

## Rules every builder follows. They are in each prompt too.

**His two rules.** No fake data: every figure from FYERS or the database, or
`unavailable` with the reason, never a placeholder, never a fallback constant.
And never say done, live or passing unless it was checked on the running system
that day, with proof. An honest gap is welcome; an overstatement is not.

**His screen rules, given 2026-09-10.** Anything he reads, positions, numbers,
money, is big, bold where it matters, coloured where it matters. Informative
text is small and muted. A card is 70 to 80 percent filled with its information,
never the figures in one corner and the rest empty. Colour comes from the money
only. A dustbin for delete, a proper Reset button, never a cheap cross or a
small round icon. No purple, lilac or violet; the accent is sage.

**What must not break.** `docs/PLAN.md` §2.12.3, all seven lines. The payoff
graph, its drag and both sliders. Charges per leg from `services/charges.py`.
The vault cage and the database guard. One click, one trade; one close, one
result. Nothing says LIVE unless `/api/market/data-health` says so.

**Every trade in the record today is a terminal test.** Paper trading has not
started; he will say when. Nothing a builder takes in a browser is a paper
trade either. See BUILD_02 for the phase mark.

**Trade 7cd4d017 is open on purpose.** Do not close it, do not edit it, do not
mark it. It is the first real subject of the position area.

**How to work.** Feature branch off `main`, the name given in the table above.
Never `main`, never a git worktree, work in the primary folder. `git fetch`
and check whether the branch's pull request is already merged before pushing
more. Plan first in plain English, six parts, and wait for his yes. Hand off in
five parts, files as clickable links, any manual step in bold up front, and a
line in bold saying **what exists and what does not**.

**Verification is invoking, never reading a status.** Load the real page in a
real browser, both themes, against the real backend started from
`.claude/launch.json` (`swayam-api`, `swayam-web`), and look for console
errors. Run the Python suite (`.\.venv\Scripts\python.exe -m pytest -q`) and
the JavaScript suite; compare counts with `SWAYAM_START_HERE.md`. **His journal
folder `02 - Projects/Trading/04 - Journal` holds 6 notes; check before and
after every run.** A path that has never been run has never been tested: the
fill and exit paths only truly run in his window, so the handoff says so.

**Do not touch.** `docs/ROADMAP.md` (his approval, every time). The recorder,
`src/swayam/research/`, the AI persona and routes, migrations other than the
one your build adds. `services/fills.py`'s fill rule (Build 3 adds resting
orders beside it, it does not change the rule). The Trade Journal page
(`docs/PLAN.md` §2.18, waits for him). Anything outside your build document.

**When unsure, ask him**, mid-build is fine. Do not guess, do not smooth over.
