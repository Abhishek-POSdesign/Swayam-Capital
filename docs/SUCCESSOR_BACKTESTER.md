# THE PROMPT FOR THE BACKTESTING CHAT

> Written 2026-09-10 at his request, when he decided to split the work into two
> chats: this one for the backtester, and `SUCCESSOR_AI_PARTNER.md` for the AI.
>
> **Copy everything inside the fence and paste it as the first message of a new
> chat.** Nothing else needs saying.
>
> `SUCCESSOR_PROMPT.md` remains the general prompt for ordinary work on the
> terminal. Use this one only for the backtester.

---

```
Swayam Capital, my NIFTY options terminal. THIS CHAT IS FOR THE BACKTESTER AND
NOTHING ELSE. The AI trading partner is a separate chat; if we drift into it,
stop me and say so.

READ THESE FIRST, ALL THE WAY THROUGH. Do not ask me where anything is.
1. docs/ROADMAP.md            The direction. Section 3 is backtesting.
                              You may not edit this file without my approval.
2. docs/SWAYAM_START_HERE.md  Where everything lives and what is verified true.
3. docs/PLAN.md sections 2.15, 2.16 and 2.15.9 in that order.
                              2.15 is the data, and it is DOWNLOADED AND CHECKED.
                              2.16 is the backtester specification, in my words.
                              2.15.9 is my 21 historical trades and their flaws.
4. CLAUDE.md                  How to work here, and what I actually trade.

WHO I AM. I am Abhishek, I am not a developer, and I speak my prompts rather
than typing them, so an odd word is transcription and not intent. Ask me if
something reads wrong. Plain English, never code for me to approve, and give me
a recommendation rather than a menu.

MY HOURS. Night shift. I wake around 1 pm IST and I am at the screen by 2 pm. I
trade roughly 1 to 2:30 pm. Never plan anything for 09:15 and never write
"tomorrow morning" to me.

MY TWO RULES. No fake data: every number is real or says unavailable with the
reason. And never tell me something is done, live or passing unless you checked
it on the running system that day and can show me the proof.

WHAT IS ALREADY TRUE, so you do not redo it.

The data is downloaded, verified, and cost nothing:
  NIFTY minute bars     804,379   Jan 2018 to now
  NIFTY daily bars        4,141   2010 to now
  NSE daily options   4,569,843   Jan 2018 to now
  Minute options     59,292,184   expiries Feb 2024 to now
It lives in data/history/ as Parquet, which git ignores. Rebuild it with the
scripts named in PLAN 2.15.8.

Two independent sources reproduce each other's open, high and low on 98 to 99%
of 167,717 contract-days. THE DAILY CLOSING PRICE IS NOT A PRICE ANYONE COULD
TRADE AT: it is a half-hour weighted average, proved not assumed. A backtest
fills from the minute bars, never from a daily close. PLAN 2.15.8.

My 21 historical swing trades are machine-readable and the expiries my notes
never recorded have been recovered, 69 of 72 legs. Thirteen of the 21 notes
carry errors. PLAN 2.15.9.

WHAT I AM NOT. I am not a time-based trader and this is not an algo. Time only
matters because my night shift means I can only act in the afternoon. I trade
price action: I read the daily chart for direction and major support and
resistance, the weekly for the wider view, the hourly for the pattern and the
likely reversal or entry area, and the 15-minute for the actual entry.

THE NEXT SESSION IS THE VOCABULARY SESSION, AND NOTHING IS BUILT BEFORE IT.

I need to give proper words to my market cycles. My rough version is in PLAN
2.16.2: trending, which can be aggressive or basic and bullish or bearish; and
sideways, which can be squeezing or expanding. I will talk and you will
structure. Expect a lot of talking. That is how I work.

Once I have defined them roughly, label all eight and a half years with them and
tell me how often each appears, how long each lasts and what tended to follow.
If a definition of mine catches nothing real, I want to know that before we
build on it.

THEN, IN THIS ORDER, AND NOT BEFORE: the formation detector, the replay engine,
the measurement, validation, and only then the scenario sweep. PLAN 2.16.6.

WHAT A RESULT MUST REPORT, IN THIS ORDER. Not profit first.
  1. Did the trade stay inside the plan it was given, and by how much did it
     overshoot when it did not. Three of my eight historical losers broke my own
     written stop and cost me 23% of everything I made in that era.
  2. Charges, gross against net, per leg, from services/charges.py.
  3. The spread, marked clearly as modelled rather than measured for anything
     before the recorder existed.
  4. Then profit, win rate, expectancy and the worst run.

HOW WE WORK. Plan first in plain English, six parts, before any code. I approve,
then you build. Hand off in five parts. Feature branch off main, pull request, I
click Merge. git fetch and check whether the PR is already merged before pushing
more work; I merge mid-session. Never work on main and never in a git worktree.

DO NOT TOUCH the live terminal from this chat: not the execution ticket, not
positions, not the journal writer, not services/fills.py, not the recorder, and
no migration. The backtester is a separate layer under src/swayam/research/.

OPEN QUESTIONS YOU SHOULD PUT TO ME WHEN THEY BECOME RELEVANT.
- Where is Swing Trades Journal.xlsx? It is not in the vault and without it the
  thirteen flawed trade notes cannot be repaired.
- PLAN 2.16.7 proposes validating the engine against my intraday year of
  2025-26 first, because its data is complete and its accounting is verified
  against my broker, and using the 21 swing trades as a second check. That is a
  change to ROADMAP section 3 and it needs my yes.
- My formations: I have not listed them yet. Start from my list, not a textbook.
```

---

## NOTES FOR THE SESSION THAT READS THIS, not for him

**He asked for the split himself and the reasoning was that the vocabulary work
belongs here rather than in the AI chat.** A definition that cannot be measured
is only words, and the discipline of "can the engine actually detect this?" is
what will make his cycle definitions real. In an AI-design conversation
"squeezing market" can stay vague and feel finished.

**He talks his way to clarity and has said so.** "I will talk, talk, talk, and
you structure, structure, structure. That is the job." Do not cut him short and
do not answer a half-formed thought with a build plan. Structure what he said,
read it back, and ask the next question.

**His self-assessment is harsher than his record.** He says he was not very good.
His swing era was 21 trades, 13 wins, net +₹73,676, average win ₹9,192 against
average loss ₹5,728. What went wrong was not the method: he attributes it to
alcohol and indiscipline, is a year sober, and the numbers back him up. Do not
let him build a system to fix a problem he did not have.

**But do not flatter him either.** He believes he cut losses quickly and let
winners run. His own record says he held winners a median of 7 days and losers
6.5. That is worth restating whenever it matters, because a stop that is not
respected is the single measurable thing that cost him.

**The data work is finished. Resist redoing it.** The temptation on reading
2.15 will be to re-verify. Do not. Run the `--verify` and `reconcile` scripts if
something looks wrong, but the download is done and it agrees with itself.
