# SWAYAM CAPITAL — THE ROADMAP. PLAN STARTS HERE.

> **Mandatory reading for every agent, before `SWAYAM_START_HERE.md` and before
> `PLAN.md`.** A new chat, a chat after compaction, a chat after clearing: read
> this first. It is the direction. Everything else is the work.
>
> **Editing this file requires Abhishek's explicit approval, every time.** An
> agent may propose a change in the chat and wait. It may not edit and tell.
>
> Written 2026-09-09 night from his own words, after a week in which one session
> said "everything is ready" and a week later paper trading was still not fully
> proven. That week is why every milestone below is a condition proven on the
> running system, never a session's report, and never a date.
>
> Edited with his explicit approval on 2026-09-11: §1 horizon 1 gate 7 and §3,
> where the backtesting history lives. It is DuckDB on his PC with the bucket as
> the copy, not Postgres. He authorised the edit in the main chat in those words
> and added that he stays open to a better option if one is shown to him.
>
> Edited with his explicit approval on 2026-09-10 night: §3 milestones 1 and 2
> and the two §2 rows for the recorder and backtesting, after the backtesting
> chat's findings and his correction that his past trades are experience, not
> test material.
>
> Mirrored in his vault at `02 - Projects/Trading/06 - Platform Plan/Roadmap.md`.
> The vault is the Second Brain this whole thing serves; a future dedicated
> session will make the vault itself the single entry point for agents. Until
> then this file and its mirror are the same text and this one is edited first.

---

## 0. THE END GOAL, IN HIS WORDS

> "Autonomy is my ultimate goal, not 100% autonomy, but I want to create a
> system which can run with my overview. I'm creating a second brain, like
> Obsidian, which can take info from my second brain, create everything for me
> for my overview, and can run autonomously. Whenever there is a decision about
> changing anything related to money, I'll stay in the loop. That means 90%
> automation. That is my goal.
>
> I don't know how the technology will evolve. In the next one year, seeing AI
> evolving very fast, it might go to 95%, 98% autonomy, but can never be 100%
> till the time I am alive. I also need to be in the loop always and forever.
> Maximum autonomy is the target, the end goal."

**What that settles.** Maximum autonomy is the destination. He is in the loop
for every decision about money, always. The system may plan, research,
document, monitor, and eventually execute inside rules he set; it never changes
a rule, a size, a cap or a risk limit without him. Two documents in the vault
used to say "fully autonomous execution is explicitly not on the roadmap". On
2026-09-09 he replaced that with the paragraph above, and those documents now
point here.

**The safeguard that survives the ambition.** A kill switch, a daily cap, a
per-trade approval that is a switch he can turn off only when a horizon's gate
says trust has been earned, and a terminal that can always be overridden from
the broker's terminal in parallel.

---

## 1. THE FOUR HORIZONS

No dates. Each horizon opens when the previous one's gate is met, and a gate
is met when it is proven on the running system, with the proof written down.
His own vault said this first: "you do NOT advance to the next phase until the
previous phase's exit criteria are met, regardless of calendar."

His rough feel for time, recorded because he gave it, never used as a deadline:
horizon 1 about a week, horizon 2 about four to six weeks, horizon 3 within
about six months, horizon 4 after that.

### Horizon 1 — PAPER, PERFECT. The terminal does everything except carry real money.

**Inside this terminal, all of it:** market overview, brainstorming with the AI,
strategy building and brainstorming with the AI, understanding the discipline,
risk, executing the paper trade as close to a real order as possible,
journaling, analytics, and the beginning of backtesting.

**What "as close to a real order as possible" means, decided 2026-09-09:** a
market buy pays the ask, a market sell gets the bid, a limit fills at his price
or better, nothing fills when the market is shut, every leg carries its own
charges and its own spread cost, and a trade is a campaign whose legs are
added and squared off inside one identity.

**Gate out of horizon 1, all of these:**

1. A run of paper trades opened, managed and closed **entirely on the desk**,
   with no terminal and no database edit: the execution ticket, the position
   area, the exit ticket, one by one, a leg exited alone, a leg reversed.
2. The journal and analytics read those trades correctly, squared-off trades
   only, charges per leg, fills marked bid/ask, and the vault note complete
   for each: entry, adjustments, exit, lesson.
3. His four rules evaluated on every trade against the live balance, with
   rule 4 tested against a real margin-used figure.
4. The daily check-in works on the live site (the vault bridge, PLAN §2.13).
5. The option chain used against a live market to build a structure.
6. The recorder records real spot and implied volatility, not zeros, so data
   for backtesting accumulates from now (PLAN §2.10).
7. The backtesting foundation exists: a data source chosen, and the history
   loaded on his PC in DuckDB from the Parquet files it already is, with the
   Google bucket as the copy. **His decision of 2026-09-11**, replacing
   "loading into Postgres". See §3 and PLAN §2.19.

**Not in horizon 1:** calendars (his decision when), real money, any order
code. The AI chapter's learning loops run manually, as his vault says for
Phase 1: weekly review by him and Claude, no automation.

### Horizon 2 — REAL MONEY, ORDERS AT THE BROKER. Swayam plans and records; FYERS places and exits.

**His decision, 2026-09-09:** "I will use the broker terminal for real money in
the beginning. I'll be using the broker terminal only for charting and placing
orders. The rest will be managed on Swayam." The research behind it is in
`PLAN.md` §2.14: since 1 April 2026 FYERS accepts API orders only from one
whitelisted static IP; FYERS has no all-or-none multi-leg order; its order
rate limit is undisclosed; this app has no order code, no kill switch, no
reconciliation, and three paper trades behind it.

**What Swayam does in horizon 2:** everything from horizon 1, plus the
**read-only broker bridge**: it reads his real positions, order book and trade
book from FYERS, which needs no static IP, and mirrors them into a **real
book** beside the paper book. Real positions appear in the position area with
the same big numbers, real fills are journaled with real charges, the four
rules run every day against what he actually holds, and the record toggles
paper and real as the approved design already says.

**Everything else stays exactly as the vault requires, because he sleeps while
positions run:** the **Wake Alerts** system with escalation to his wife's phone
is a **mandatory prerequisite** for carrying a real position overnight, as his
vault has said since 2026-09-05. The readiness journal stays a journal with
zero power. Entry is never blocked; only carrying overnight is gated.

**Size, in his words:** start at **one lot**. Grow to **three to five lots**,
the size he traded before and is confident with, on capital under ten lakh.
Hedged and properly managed, **seven to eight lots, ten at most**. Never the
full margin: "I will always have some extra room for my margin." Size grows
only as the record earns it, never on a date.

**Gate into horizon 2:** the horizon 1 gate, plus the Wake Alerts system built
and proven with a real phone, plus the read-only bridge showing his real book
correctly for a run of sessions with a paper position open beside it.

**Gate out of horizon 2:** a run of real trades placed at the broker whose
mirror in Swayam matched the broker **to the paisa** on entry, on exit and on
charges, with zero reconciliation differences he had to fix by hand, and the
rules evaluated against his real positions every trading day of that run.

### Horizon 3 — EXECUTION FROM SWAYAM. The order leaves this terminal.

**Only after horizon 2's gate.** The order path is a separate build with its
own plan and its own weeks of testing, and it is built in this order:

1. **The kill switch first** (PLAN §2.5): one database-backed halt that blocks
   every risk-increasing action at the backend, with close and reduce always
   allowed.
2. **The static IP**, because FYERS will reject an order from anywhere else.
   See §4 for the cost-benefit he asked for.
3. **The order-status WebSocket** feeding the position area, so what the
   broker did is what the screen shows, within a second.
4. **Guardrails the broker has and this app does not:** the NIFTY freeze
   quantity (1,800 units, 27 lots at lot 65), a lot cap he sets, a market-order
   refusal on an illiquid strike, a per-day order cap.
5. **One leg at a time with a confirmation each**, then, once proven, the
   basket with every leg's rejection or partial fill handled and shown.
6. **Reconciliation on every send**: the app's book against the broker's, a
   difference stops the next send until he looks.
7. **Every exit still possible from the broker's terminal in parallel**, always.

**Gate out of horizon 3:** a run of real trades sent from Swayam with zero
reconciliation differences and zero orders the broker refused for a reason the
app should have caught first.

### Horizon 4 — ALGO. The system executes inside his rules; he oversees.

**In his words:** "algo trading from the Swayam terminal using my past history,
planning, and backtesting strategies using the Obsidian second brain
connections... everything runs through the algos, so that I will have the
freedom to plan, document, and the system will execute for me."

**What this needs, none of it started:** the backtester proven on years of data
(§3); strategies written as rules the backtester and the executor both read;
the learning loops from his vault's Self-Improving Agent note running as
scheduled jobs writing to a review queue he approves; the order path from
horizon 3 with months of proof; the cloud, not his PC, as the home of the
order path, because the algo runs while he sleeps.

**What never changes here:** he is in the loop for every decision about money.
Sizes, caps, rule thresholds and strategy changes are proposed by the system
and approved by him. The kill switch is his. Per-trade approval is a switch he
turns off, and can turn back on, at his own pace. His vault's Self-Improving
note keeps its rule: one variable at a time, written hypothesis, human
approved, never auto-applied.

**Gate into horizon 4:** horizon 3's gate plus, as his vault already demands,
six months of proof from the horizon 3 order path, and a backtester whose
results on his own real trades match what actually happened.

---

## 2. THE MAP: WHERE EACH PIECE LANDS

| Piece | Horizon | Where it is planned | State on 2026-09-09 night |
|---|---|---|---|
| Execution ticket, fills at bid/ask, Home strip | 1 | PLAN §2.12.2 PRs 1, 2, 4 | **Done, merged.** Never sent with a live book; first live send 2026-09-10 |
| Position area with the exit ticket | 1 | PLAN §2.12.2 PR 3 | Next build |
| Option chain tested live | 1 | PLAN §2.12.2 PR 5 | Not started |
| Vault bridge so the check-in and the AI see his real files on the live site | 1 | PLAN §2.13 | Decided, not started |
| Recorder recording real spot and Greeks | 1 | PLAN §2.10 | **Rebuilt and deployed 2026-09-10, revision 00003.** Real spot, real change in OI, correct expiry, IV and Greeks, two expiries, NULL never zero. First real file in the new shape still to be seen. Captures the afternoon only until the token gap is closed; mornings recoverable from FYERS' expired-contract history |
| Backtesting foundation: data sourced, loaded, first replay | 1 into 2 | §3 below, PLAN §2.15 and §2.16, `docs/SUCCESSOR_BACKTESTER.md` | **Data sourced and checked 2026-09-09 night**, free, from 2022 onwards. Loaders under `scripts/` and `src/swayam/research/`. The backtester itself: specified in PLAN §2.16, its own chat, not started |
| Scheduled backups | 1 | PLAN §2.6 | Runs by hand only |
| Wake Alerts | gate into 2 | vault `06 - Platform Plan/Wake Alerts System.md` | Specified, not built |
| Read-only broker bridge, the real book | 2 | PLAN §2.14 recommendation 2 | Decided, not started |
| Calendars | 1 or 2, his call | `docs/CALENDAR_BUILD_BRIEF.md`, PLAN §3 | Briefed |
| Kill switch | opens 3 | PLAN §2.5 | Not started |
| Static IP | opens 3 | §4 below | Not started |
| Order path from Swayam | 3 | its own plan, not yet written | **Do not start** |
| AI chapter: learning loops as jobs, event research button | 2 into 4 | PLAN §3, vault Self-Improving note | Chat and grounding exist; loops manual |
| Algo execution | 4 | its own plan, not yet written | Not started |

---

## 3. BACKTESTING. Essential, and not started.

**In his words:** "When I'm saying backtesting, I'm not saying backtesting
through my data. I don't have any data for backtesting. I don't have options
data with me. We have to source the data... we will upload the data into
Postgres, and we will build a back-testing system. It will back-test these
strategies according to the time I am available to take a trade, according to
my capital and my risk appetite. I will build my custom strategies that I am
going to apply in paper testing as well as for real money."

**Where that data actually lives, his decision of 2026-09-11, which revises the
word "Postgres" in his own words above.** The market history stays on his PC as
Parquet files queried by DuckDB, with the Google bucket as the copy. The
terminal's record — trades, journal, results — stays in hosted Postgres, because
the live site must reach it. His reasons: money and disk space. His standing
condition, in his words: **"I am always open to listening to advice. If there
are better options, I'm all ears."** So a better option may be put to him at any
time, with its cost and its benefit named; it may not be adopted without him.
PLAN §2.19 has the full reasoning and what the backtester chat must still
brainstorm with him.

**What it must be, therefore:** a backtester over sourced historical NIFTY
options data, held in DuckDB on his PC, that tests **his** structures under **his**
constraints: entries only in his window (about 14:00 to 15:30 IST), his
capital, his four rules, charges per leg from the real charge engine, fills at
the bid and ask, and the near-expiry square-off habit for calendars. Not a
generic engine.

**Milestones, in order, no dates:**

1. **Data sourced.** Done on the night of 2026-09-09: FYERS' expired-contract
   history (1-minute candles for the fifteen strikes either side of NIFTY's
   close at expiry, for every expiry from December 2019; corrected with his
   explicit yes on 2026-09-13, after the backtester chat measured both facts
   on his own files), FYERS' index minute candles, and NSE's official daily
   file, all free and already downloaded. Plus our own recorder from PLAN §2.10, which now records
   real spot and implied volatility, accumulating forward. **The window is 2022
   onwards, his decision of 2026-09-10:** the market before and after Corona are
   different markets. Older data exists because it was free; it is not used
   without asking him. PLAN §2.15 and §2.16.2.
2. **Data loaded** and checked against itself. Two independent sources, FYERS'
   minute candles and NSE's official daily file, must reproduce each other
   before either is trusted. The backtester is validated mechanically, on
   pricing, charges, fills and a synthetic trade with a known outcome, NOT
   against his own past trades. His trade history is for reflection and
   knowledge; it was not structured for testing and he has said so. His
   correction of 2026-09-10, approved for this file the same night: "I'm not
   going to copy anything, not even from my past. My past is my experience...
   My future, I will be writing by my own hand, with your help." His history
   stays usable whenever it genuinely helps, with its flaws stated every time.
3. **His strategies written as rules** the backtester reads, the same rules the
   desk and later the executor read.
4. **Results feed the desk:** a strategy's backtested expectancy beside its
   payoff, before he takes it on paper or for real.
5. **The learned-parameters discipline** from his vault: Method files hold
   principles and never change on tuning; thresholds that can change live
   apart, and graduate into a Method file only after they have been stable.

**Where it is planned next:** `PLAN.md` gets a §2.15 for milestone 1 when he
opens that work, in its own session, as he said.

---

## 4. THE STATIC IP. Cost-benefit, as he asked.

**Why at all.** Since 1 April 2026 FYERS accepts API orders only from one
whitelisted static IP per App ID, and rejects orders from anywhere else. Data
and read-only calls, positions, order book, trade book, are not affected.
Sources in `PLAN.md` §2.14.

**When it is needed:** the day horizon 3 starts and not before. Nothing in
horizons 1 or 2 sends an order from this app, so a static IP brings no benefit
until then. He said he is ready to take one early if it is cheap and useful;
the honest answer is that early it is only cost.

**The two ways, and when each fits:**

| | From his ISP, on his PC | From Google Cloud, on the live site |
|---|---|---|
| What it costs | Indian ISPs sell a static IP as an add-on, typically a few hundred to about a thousand rupees a month; the exact figure comes from his ISP when the time comes | A Cloud NAT gateway plus a reserved address plus the connector: roughly ₹4,000 to ₹5,000 a month at the minimum configuration, from Google's pricing |
| What it needs | His PC on and connected while an order path runs | Nothing of his; the cloud is always on |
| Fits which horizon | **Horizon 3**, where he is at the screen for every send | **Horizon 4**, where the algo runs while he sleeps |
| Risk | A power cut or a sleeping PC with an order in flight | A cloud misconfiguration sending from the wrong address, rejected by FYERS, silently |

**Recommendation:** decide at the start of horizon 3, from the ISP if the order
path starts on his PC, and move to Cloud NAT when horizon 4 needs the cloud to
send. Record the actual quotes in `PLAN.md` at that point.

---

## 5. HOW EVERY AGENT WORKS TOWARD THIS

1. **Read this file first**, then `SWAYAM_START_HERE.md`, then `PLAN.md`, then
   `CLAUDE.md`, then the vault session log named in START_HERE.
2. **Name the horizon** a piece of work belongs to before building it. Work
   that belongs to a later horizon is not started early because it is
   interesting.
3. **A gate is proven on the running system**, with the proof written into
   `PLAN.md` §4 and the vault session log, or it is not met. A session saying
   "ready" is not a gate.
4. **Never start the order path** (horizon 3) or anything that sends real
   orders, without his explicit instruction in the chat, on a day he gives it.
5. **Never widen the size ladder** in §1 horizon 2, and never store a size or a
   cap as a constant; every figure is a percentage of the live balance.
6. **The vault is authoritative and the repo mirrors it.** This file is the one
   exception until the dedicated vault session makes the vault the entry point;
   then this file follows the vault copy.
7. **Propose changes to this file in the chat and wait for his yes.**

---

## 6. WHERE THIS JOINS THE VAULT

- `02 - Projects/Trading/06 - Platform Plan/Roadmap.md` is the mirror.
- `06 - Platform Plan/Platform Overview.md` and `Self-Improving Agent
  Integration.md` carried "fully autonomous execution is explicitly not on the
  roadmap". Each now carries a dated note pointing to §0 here, and keeps its
  own text below the note so the history is visible.
- `00 - Reference/Personal Trading Brief.md`'s phase roadmap is the ancestor of
  §1 and now links here.
- `Trading Overview.md` links here from its structure table.

---

*Nothing in this file overrides `MY TRADING RULES - ONE PAGE.md`. It sits
above every plan, and below his rules.*
