# BUILD 03 — RESTING ORDERS. A limit the book has not reached waits for it.

> Written 2026-09-10 evening by the main chat, from his decision of 10
> September (`docs/PLAN.md` §2.12.5 item 1). Branch
> `feature/swayam-build03-resting-orders-044`. One pull request. **This is
> BUILD B, the one piece kept apart because it is the trickiest to prove.
> Builds after Build A (BUILD_01, 02 and 04 together) is merged.**
>
> **The prompt he pastes into the builder chat is in the fence below.**

---

```
Swayam Capital, my NIFTY options terminal. THIS CHAT IS A BUILDER CHAT. It
builds exactly ONE thing: Build 03, resting orders. A limit order away from
the market sits as an open order until the bid or ask reaches it, for entry
and for exit, with Modify and Cancel in the position area, and expiry at the
bell. The main chat planned it and will review it; you do not re-plan it,
widen it, or start anything else.

READ THESE, ALL THE WAY THROUGH, IN THIS ORDER. Do not ask me where anything is.
1. docs/builds/README.md                 how a build works and the rules
2. docs/builds/BUILD_03_RESTING_ORDERS.md   THIS BUILD, the whole spec
3. docs/builds/BUILD_01_DESK_POSITION_AREA.md, BUILD_02 and BUILD_04, which
   Build A built before you: what they left you
4. docs/PLAN.md sections 1a (the chain feed), 2.12.1, 2.12.3, 2.12.5, 2.12.6
5. CLAUDE.md, then docs/SWAYAM_START_HERE.md section 1
6. The mockup: https://claude.ai/code/artifact/ef242a22-59a7-4752-8aa4-91d59393c5d5
   Screen 4, and the amber "your price, not a rule" note on screen 3, are
   yours. The build must look like them.

WHO I AM. Abhishek. Not a developer. Plain English, never code to approve, a
recommendation rather than a menu. I speak my prompts, so an odd word is
transcription; ask. Night shift: awake around 1 pm IST, at the screen by 2 pm,
I trade 1 to 2:30 pm. Never plan anything for 09:15.

MY TWO RULES. No fake data, ever, or unavailable with the reason. Never say
done, live or passing unless you checked it on the running system that day
and can show me the proof.

MY SCREEN RULES. Numbers I read are big and bold; informative text small and
muted. Cards 70 to 80 percent filled. Every kind of order clearly labelled
and coloured by its nature. Identical to the mockup.

HOW WE WORK. Plan first in plain English, six parts; I approve before any
code. Branch feature/swayam-build03-resting-orders-044 off main, never main,
never a worktree. git fetch before every push. Hand off in five parts, files
as clickable links, manual steps in bold up front, one bold line saying what
exists and what does not.

DO NOT TOUCH: the fill RULE in services/fills.py (you add resting beside it),
the charge engine, docs/ROADMAP.md, the recorder, src/swayam/research/, the
AI, the Trade Journal page, the vault cage, the database guard, any migration
but 024. Every trade in the record is a terminal test until I say otherwise.

BEFORE YOU DO ANYTHING, ANSWER THESE IN YOUR OWN WORDS.
1. What did the ticket do wrong on 10 September, and what did I say it must
   do instead?
2. Where does the watcher get its prices, how often, and what happens to a
   resting order at 15:30?
3. What does a resting entry order become when it fills, and when is its
   note written?
4. How does the exchange's price band reach this build, and what does the
   ticket say when it cannot be read?
5. Which three groups does the position area show for orders, and where?
```

---

## 1. What this build is for

His words, 10 September: "I can place 111, 112, or 113 because it's a limit
order... It should not execute if the price is not available, but must be
sitting in the system till the time the bid and ask reach the price I want."
The ticket refused a limit away from the book. That refusal was the previous
chat's design and it is wrong. It cost him his strangle on 10 September and
gave his condor the wrong name.

## 2. What exists today, verified 2026-09-10, plus what BUILD_01 and 02 leave

- The fill rule in `src/swayam/services/fills.py`: a market buy pays the ask,
  a market sell gets the bid, a limit fills at his price or better, nothing
  fills after 15:30. **Unchanged by this build.** Today a limit away from the
  book refuses the leg (HTTP 422, "your price, not a rule" since BUILD_01).
- The chain feed, `src/swayam/api/chain_feed.py`: one refresh per expiry on
  its own cadence, however many browsers watch, backs off when FYERS refuses,
  keeps the last chain, slows to one read every five minutes after the close.
  **The watcher hangs off it; it never adds a FYERS call of its own.**
- The clock: `/api/market/data-health` and `services/expiry.py`
  (`session_is_over`). The bell is 15:30 IST.
- The execution key: `services/execution_safety.py`.
- After BUILD_01: exit one leg, reverse, exit all with per-leg order type;
  the position area with its groups; the exit ticket. After BUILD_02: the
  phase mark, the Home band.
- Migrations up to 023. This build adds **024**.

## 3. What to build, in this order

### 3.1 The order book (migration 024)

`swayam_orders`: `id uuid`, `position_id uuid NULL` (null for an entry that
will open a new trade), `kind` (`entry` | `add_leg` | `exit_leg` |
`reverse` | `exit_all_leg`), `leg jsonb` (the leg exactly as the ticket
sends it: direction, strike, type, expiry, lots, and for exits the sequence),
`limit_price numeric`, `status` (`resting` | `filled` | `cancelled` |
`expired` | `failed`), `placed_at`, `expires_at` (15:30 IST of the day
placed), `filled_at`, `fill jsonb` (the fill exactly as `fills.py` reports
it), `result jsonb` (what filling it produced: position id, leg sequence),
`band_lower`, `band_upper` (nullable), `band_source text`, `idempotency_key`,
`failure_reason text`, `provenance text` (the phase mark). Index on
`(status, expires_at)`. `tests/test_written_columns_exist.py` covers it.

### 3.2 The ticket rests instead of refusing

- **Entry ticket** (`execution-ticket.js`, `/api/execute/multi-leg`): a limit
  leg the book has not reached no longer refuses the ticket. The legs that
  fill, fill; each leg that cannot becomes a resting order. If NO leg fills,
  the trade is not opened yet: every leg rests as `entry`, and the first fill
  opens the trade (through the same path a sent leg opens it) with the rest
  becoming `add_leg` orders on that trade. The button reads "Send the fills
  and rest the rest" when any leg will rest. The response lists fills and
  resting orders separately.
- **Exit ticket** and the per-leg exit and reverse (BUILD_01's routes): the
  same. A leg that cannot fill rests as `exit_leg`, `exit_all_leg` or
  `reverse`; the trade stays open; the result row is written only when the
  last open leg actually closes.
- **Execute one by one** and resting: a resting leg is "sent"; the next leg
  can still be sent.
- The amber note on both tickets: "your price, not a rule. {Legs} will rest
  as open orders until the book reaches your price, inside today's price
  band, and expire at the bell. The other legs fill now."
- **The price band. Settled by a read-only test on 2026-09-10 evening.**
  The FYERS **quote** call carries no band at all (its fields: ask, atp,
  bid, ch, chp, high_price, low_price, lp, open_price, prev_close_price,
  spread, volume and names). The FYERS **market depth** call does:
  `fyers_client.model.depth(data={"symbol": sym, "ohlcv_flag": "1"})`
  returns, keyed by the symbol, `lower_ckt`, `upper_ckt` and `tick_Size`,
  beside `bids`, `ask`, `ltp`, `oi`, `pdoi`, `totalbuyqty`, `totalsellqty`.
  For `NSE:NIFTY26SEP23800CE` at the close: lower 0.05, upper 263.85, tick
  0.05. So: **one depth call when the order is placed**, store the band on
  the order with `band_source = 'FYERS depth'`, refuse a limit outside it
  with the band named, and refuse a limit that is not on the tick. **If the
  depth call fails, the order rests anyway, `band_source = 'unavailable'`,
  and the ticket says "band not readable from FYERS; the order rests without
  a band check".** Never an invented band. The depth call is one more FYERS
  request per placement, not per refresh; it does not touch the chain feed's
  budget.

### 3.3 The watcher

- In the backend process, registered on the chain feed: after every refresh
  of an expiry while `/api/market/data-health` says live, evaluate every
  resting order on that expiry against the fresh book: a buy fills when the
  ask is at or below the limit, a sell when the bid is at or above it, **at
  his price or better**, through `fills.py`, then through exactly the path a
  sent leg takes (open the trade, add the leg, exit the leg, reverse), with
  its charges, its note line, its key. One order fills at most once; a
  failure marks it `failed` with the reason and leaves the position as it
  was.
- The chain feed refreshes only expiries in demand. **A resting order keeps
  its expiry in demand** while it rests, so the watcher sees the book.
- At the bell every resting order becomes `expired`, nothing charged, its
  line kept for the day.
- When the process restarts (Cloud Run does), resting orders are read back
  from the table; nothing is lost, nothing is filled twice.
- Never a FYERS call of the watcher's own. Never a fill after 15:30. Never a
  fill from a closing price.

### 3.4 Modify, cancel, read

`GET /api/orders?date=today`, `PATCH /api/orders/{id}` (`limit_price` only,
inside the band, refuses on anything not resting), `DELETE /api/orders/{id}`
(cancel, refuses on anything not resting). A modify keeps the order's id and
its place in his book.

### 3.5 The position area's groups (screen 4 of the mockup)

Inside the position area, after Open now: **Open orders** with three visible
groups, each with its own labelled and coloured chip: **Resting** (amber,
pulsing dot; the state line says what it waits for: "waiting for the ask to
reach 95.00", the book now and the distance, "inside today's band" or "band
unavailable", "expires 15:30"; Modify with the price editable in place, Save
price, Cancel with the dustbin), **Filled from the book today** (sage; time,
price, "better" when it was, charges, which trade it joined), **Expired or
cancelled today** (muted; the price the book never reached). Each order says
which trade it belongs to, or "new trade · opens when it fills". Empty
groups show one quiet line saying so, not nothing. The same groups appear in
the Home band's third figure as a count ("2 resting") when any rest.

## 4. What is NOT in this build

A resting order that outlives the day. Stop orders or triggers of any kind. A
watcher that calls FYERS itself. Any change to the fill rule or the charge
engine. Anything on the option chain (BUILD_04).

## 5. How it is verified

- Python: 024 applied and the columns test green; the watcher fills a buy
  when the ask reaches the limit and not before, at his price or better;
  a sell likewise; an entry order opens a trade with the right provenance and
  key; a second refresh cannot fill it twice; the bell expires everything;
  a restart reads the book back; the band refusal and the band-unavailable
  path; modify and cancel refuse on a filled order.
- JavaScript: the tickets' resting note; the three groups from captured
  replies.
- Browser: both themes, real backend, market shut: a limit away from the book
  rests and appears in Open orders with its state line; Modify and Cancel
  work; at the close the ticket says nothing fills. No console errors.
- **Only his window can prove:** a fill from the book by the watcher. Say so
  in bold, and tell him which leg to rest and where to look.

## 6. The handoff

**Manual step in bold up front:** migration 024. One bold line: what exists
and what does not. Then the main chat reviews.
