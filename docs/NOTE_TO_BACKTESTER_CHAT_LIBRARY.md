# A NOTE FOR THE BACKTESTER CHAT, from the AI partner chat. The library, and what the second research pass raised about backtesting.

> Written 2026-09-12 night by the mentor chat at his request, so the
> backtester chat knows what was done, how, and can say what it needs. He
> pastes the fence into the backtester chat. A copy sits in his vault at
> `00 - Developer Logs/NOTE FOR BACKTESTER CHAT - Library.md`.

---

```
From the AI partner chat, the mentor, 2026-09-12 night. Read this, then
answer him in this chat. Nothing here is a decision of yours already made;
docs/PLAN.md 2.16 is still yours.

WHAT WAS DONE. He is building a knowledge base for his AI partner and for
strategy building. His rule, set tonight: research is done TWICE, by two
tools, before anything is fetched or bought. Pass one: Antigravity, from the
prompt in docs/LIBRARY_RESEARCH_PROMPT.md, wrote
  00 - Developer Logs/LIBRARY_RESEARCH_2026-09-12 by Antigravity.md
Pass two: he ran an independent check through Perplexity, which wrote
  00 - Developer Logs/INDEPENDENT_TRADING_LIBRARY_REPORT_2026-09-12 by perpexility.md
The second pass corrected the first in several places and is the more
careful of the two. Both are in his vault; read both.

WHAT IS BEING FETCHED, free and lawful, official sources only, by Antigravity
from docs/LIBRARY_DOWNLOAD_PROMPT.md, into
  03 - Knowledge/Trading/Library/
with an index: the SEBI 2024 index-derivatives circular and the 2025
expiry-day circulars; NSE's Tuesday-expiry and lot-65 circulars and the
contract specification; the Income Tax Department's STT texts for 2024 and
2026; SEBI's studies of individual F&O traders; the NISM Series VIII
workbook; NSE's option strategies module; Zerodha Varsity modules 2, 5, 6, 9,
10; NSE Market Pulse; RBI's policy report and MPC resolution; the MoSPI and
RBI release calendars; the Bailey and Lopez de Prado papers on backtest
overfitting and the deflated Sharpe ratio; CME and OCC options course text.
Paid books are his hand, three first: The Mental Game of Trading, Positional
Option Trading, The Daily Trading Coach.

WHAT THE SECOND PASS RAISED THAT IS YOURS. Some of it is already in your 2.16
and 2.15; say which. The rest, adopt or reject with a reason, to him, in
plain English, one at a time if he wants to talk it through.
 1. Point-in-time contract rules. The lot was 75 until the October 2025
    change to 65; weekly expiry was Thursday until 1 September 2025; STT
    on options changed in October 2024 and again on 1 April 2026 (the
    second pass says both dates; verify against the Income Tax Department
    text once it is in the Library). A 2022-2026 backtest must size,
    expire and charge every trade by the rules of ITS day, never today's.
    services/charges.py is versioned by date already; are lot size and
    expiry weekday? Is there a dated change log the engine reads?
 2. Execution quality. Fill from minute bars at bid or ask, reject stale
    and illiquid legs, model each leg, price the legging. 2.16.7 already
    says minute bars and a modelled spread; the second pass asks whether a
    strike was tradeable at the decision minute and whether the last
    traded price was stale. Where does the engine stand on those two?
 3. An approval standard in four levels: development sample; an untouched
    test sample used once after the rule is frozen; walk-forward with
    parameters chosen only from earlier data; then live paper with signals
    recorded before outcomes are known. 2.16.7 has held-out data and
    walk-forward; are the "used once" and "recorded before outcomes" parts
    in it?
 4. An experiment register: every parameter combination tried, including
    the rejected ones, so a final result cannot hide its failed trials.
    This is not in 2.16 as far as the mentor can see.
 5. Event periods tested separately: RBI, Budget, elections, gap days,
    volatility spikes.
 6. Holiday-adjusted expiries and settlement. data/nse_holidays_2026.json
    exists; what about 2022 to 2025?
 7. Report fields beyond his 2.16 order: median trade, drawdown duration,
    tail loss, and cost as a share of gross profit.

WHAT HE ASKS OF YOU.
 a. Tell him what sources, documents or data YOU need for strategy building
    that are not on the fetch list above, with the official source if you
    know it, so it can be added to the next download prompt.
 b. Say whether you want your own research pass, and on what exactly. He
    will run it the same two-tool way.
 c. Read the Library folder once it exists, and say what in it changes 2.16.

Do not edit docs/ROADMAP.md. Write your decisions into docs/PLAN.md 2.16,
dated, and into your log at 00 - Developer Logs/Chat Logs/BACKTESTER.md.
```
