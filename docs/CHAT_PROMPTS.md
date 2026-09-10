# WHICH PROMPT TO PASTE INTO WHICH CHAT

> Written 2026-09-10 night, at his request. **He keeps one chat per purpose,
> deliberately**, so a long conversation about one thing cannot contaminate
> another. Every chat starts by pasting one of these and nothing else.
>
> The point of these files is that he never spends tokens, energy or context
> explaining himself again. **If a session has to ask him something that is
> already settled, the prompt is at fault and should be fixed.**

---

## The chats, and their prompts

| Chat | Paste this | Its specification | What it is for |
|---|---|---|---|
| **Main** | `docs/SUCCESSOR_PROMPT.md` | `docs/PLAN.md` §1, §2 | The terminal itself: the desk, the ticket, positions, the journal, the recorder, live testing, everything that runs |
| **Backtester** | `docs/SUCCESSOR_BACKTESTER.md` | `docs/PLAN.md` §2.16, data in §2.15 | Market vocabulary, new strategies, the replay engine, the measurement |
| **AI partner** | `docs/SUCCESSOR_AI_PARTNER.md` | `docs/PLAN.md` §2.17 | **The mentor chat.** Designs, monitors, corrects and feeds the trading partner that lives in the terminal, whichever model that is. Never claims to be the partner. §2.17.7 |
| **Builder, one per build** | The fence at the top of `docs/builds/BUILD_0N_*.md` | That build document, `docs/builds/README.md` | **Builds exactly one build and nothing else.** Since 2026-09-10 evening the main chat is the orchestrator: it plans, draws the mockup, writes the build document, and reviews the finished build before he merges. A builder chat is opened fresh for each build and closed after it. |

**How the builder loop runs**, his decision of 2026-09-10 evening: the main
chat says "the plan is ready" and gives him the prompt; he opens a new chat
and pastes it; that chat builds one build and hands off; he tests it and
iterates with the builder; then the main chat reviews it against the build
document and the mockup and says "all good"; then he merges. One build at a
time. `docs/builds/README.md` has the rules every builder follows.

More chats will be added. When one is, add a row here, write its prompt beside
the others, and give it a numbered section in `docs/PLAN.md` so the prompt has
something to point at.

---

## The rules that apply to every chat, whichever prompt was pasted

These are in each prompt too, so a session that reads only the prompt is not
missing them. They are repeated here so a session reading the repository sees
them once, together.

**Who he is.** Abhishek. **Not a developer.** He speaks his prompts rather than
typing them, so an odd word is transcription and not intent: ask rather than
guess. Plain English, never code for him to approve, a recommendation rather
than a menu. English, not Hinglish.

**His hours, and this one is not negotiable.** Night shift. He wakes around 1 pm
IST and is at the screen by about 2 pm. He trades roughly 1 to 2:30 pm. His live
window is 60 to 90 minutes a day. **Never plan anything for 09:15 and never
write "tomorrow morning" to him.** He has corrected this more than once.

**His two rules.**
1. **No fake data.** Every number is real, from FYERS or the database, or it
   says `unavailable` with the reason. Never a placeholder shown as real.
2. **Never say something is done, live or passing** unless it was checked on the
   running system that day, with proof to show. An honest gap is welcome; an
   overstatement is not.

**How work moves.** Plan first in plain English, six parts, before any code. He
approves, then it is built. Hand off in five parts. Feature branch off `main`,
pull request, **he** clicks Merge, because the PR is his only revert button.
`git fetch` and check whether the branch's PR is already merged before pushing
more; he merges mid-session. Never work on `main`, never in a git worktree.

**`docs/ROADMAP.md` may not be edited without his explicit yes, every time.**
Propose in the chat and wait. Never edit and tell.

---

## Where his own history lives, and what it is for

**Usable whenever it helps. Never the thing a strategy is copied from, and
never the test that decides the engine is correct.** He settled this on
2026-09-10: the backtest is a fresh test of new strategies he designs, but his
history may be read, compared against and reasoned from whenever it is genuinely
useful. **Every such use states that the data is flawed.** `docs/PLAN.md`
§2.16.0 has his own words and the table of what it may and may not be.

> "I'm not going to copy anything, not even from my past. My past is my
> experience, and we should learn from it and use it whenever required. My
> future, I will be writing by my own hand, with your help."

**Use every source there is:** his history, the broker, the market, the REST
API, the WebSocket, the recorder, the NSE files.

| What | Where |
|---|---|
| The vault, authoritative | `G:\My Drive\Second Brain` |
| 21 swing trades, 2022-23, as notes | vault `02 - Projects/Trading/00 - Reference/Historical Swing Trades/` |
| The intraday year, 2025-26 | vault `02 - Projects/Trading/00 - Reference/Historical Trade Journal/` |
| **His raw archive, everything he ever saved** | `E:\Project E\Trading\Bazaar` |
| `Swing Trades Journal.xlsx`, the source of the 21 notes | `E:\Project E\Trading\Bazaar\Trading Journal\` |
| Four strategies he wrote with rules | `E:\Project E\Trading\Bazaar\60 Day Challange\Strategies\` |
| **His Zerodha history** | **Gone.** He had the account; he has no record of it any more |

**The archive is his own description: broken.** Some of it is current, some
years old, some spreadsheets were lost or deleted. He has not traded since
March 2026. Treat anything in it as evidence of how he worked, not as a record
that has been reconciled.
