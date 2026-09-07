# UI BUILD BRIEF — Home and Strategy Builder

> Written 2026-09-08 for a **cloud session that runs unattended overnight**.
> Everything you need is in this file. Do not wait for a human; there is none.
> Read `docs/SWAYAM_START_HERE.md` for background you may want, but this file
> is the job.

---

## 0. READ THIS FIRST, IT DECIDES WHETHER YOUR WORK IS ACCEPTED

**You are rebuilding two page files to a design the owner has already approved.
You are not designing anything. You are not re-planning. Build what is written.**

### The three rules you will be judged on

1. **NO FABRICATED VALUES.** Every number rendered must come from an API
   response or say `unavailable` with a reason. Never a fallback constant,
   never a plausible-looking placeholder, never `|| 0`, never `|| 75`. This is
   the single most important rule in this repository. The last version of the
   rule panel invented a reward ratio of 1:2.63 and a risk of ₹4,125 and showed
   them as his own; that is exactly what you must not do.
2. **NEVER CLAIM SOMETHING WORKS THAT YOU HAVE NOT RUN.** You have no FYERS
   token, no Supabase credentials and no live data. You therefore **cannot**
   verify against his account, and you must not say you have. State plainly in
   the pull request what you ran and what you could not.
3. **DO NOT BREAK THE PAYOFF MATHS.** He said the payoff graph impressed him.
   The Black-Scholes and payoff logic in the reference prototype is correct.
   Port it faithfully.

### What you must NOT do

- Do not run anything that writes to the database. `tests/db_guard.py` blocks
  test writes; do not weaken, bypass or remove it.
- Do not run `gcloud`, deploy, or touch cloud infrastructure.
- Do not merge anything. Open a pull request and stop.
- Do not modify `src/swayam/rule_engine/`, `src/swayam/options_math/`, or
  `src/swayam/api/routes/validation.py`. The backend risk model is settled and
  correct. This is a **frontend** job.
- Do not delete the AI chat. See section 3.

---

## 1. WHO THIS IS FOR

Abhishek Sikka. Not a developer. NIFTY options, paper trading, restarting after
a break, intends to trade real money through this terminal. He sits at his desk
between 1 and 2 pm IST.

**His four rules, which the UI exists to serve.** Every one is a percentage of
his live FYERS balance, read fresh each session, never stored.

| # | Rule | Threshold |
|---|---|---|
| 1 | Running loss | 1% of live balance |
| 2 | Overnight gap, tested at 2x the average daily move | 2% |
| 3 | Black swan, worst case at expiry | 5% |
| 4 | Deployable margin ceiling | 2x cash equivalent |

**Entry is NEVER blocked**, including naked and half-built structures, because
converting a straddle into a condor requires passing through states no gate
would allow. **Only carrying overnight is gated**, on two conditions: hedged,
and inside the gap test. The UI must say this plainly. A red badge that stops
nothing teaches him to ignore red badges.

**The NIFTY lot is 65**, resolved server-side. If the browser sends 75 the
server ignores it. Never hardcode 75 anywhere.

**The readiness form is a journal with zero power.** It cannot block a trade or
shrink size.

---

## 2. THE REFERENCE PROTOTYPES — YOUR SPECIFICATION

Two working, interactive prototypes were approved by him on 2026-09-08:

**Both prototypes are in this repository. They are your specification.**

```
docs/reference/strategy-desk-prototype.html
docs/reference/home-prototype.html
```

They are complete, self-contained, working pages. Open them, read the CSS and
the JavaScript, and port them into the app's page classes. The maths, the
layout, the wording, the colours and the interactions are all decided there.
**Where this brief and the prototypes disagree, the prototypes win**, except on
the three rules in section 0, which always win.

The prototypes carry his real figures from 2026-09-08 hardcoded as constants,
because they had to run standalone. **In the real pages every one of those must
come from the API instead.** Search them for `SPOT`, `BAL`, `CAP1`, `LOT`,
`AVG_MOVE`, `MARGIN_USED`, `MARGIN_CEILING` and the `TICK` array: each is a
placeholder for a live value, and leaving any of them hardcoded is exactly the
fabricated-data failure this project exists to prevent.

They are also published, if you can reach the network:
https://claude.ai/code/artifact/7adbe205-616c-4e7a-8f6e-ef003d1c98ff and
https://claude.ai/code/artifact/967d09bf-d826-45b4-b8fa-6df6d580a1fe

### His fourteen decisions. Do not relitigate any of them.

1. **Legs at the TOP of the left column.** Not the bottom. He said this twice.
2. **One expiry dropdown and one lot multiplier for ALL legs**, in a toolbar
   directly above the legs table.
3. **An expiry selector above the ready-made grid**, which drives what the
   presets load and keeps the legs expiry in sync.
4. **A dustbin icon for delete.** Never a cross. He called the cross ugly.
5. **His four rules sit at the BOTTOM, with the execute button**, in one block.
   Not scattered, not at the top.
6. **The top metric row starts with margin**: margin needed for this structure,
   and margin already used. Green when it fits, red with the shortfall in
   rupees when it does not. Then max profit, max loss, breakeven, reward to
   risk, and the value at his chosen target.
7. **The payoff graph must keep working.** Drag it to move the target. The date
   slider pulls the "on target date" curve away from the "at expiry" curve.
8. **A running ticker** across the top of both pages.
9. **Home has a dedicated NIFTY sidebar** down the left.
10. **The morning ritual is ONE THIN STRIP**, filled from a modal. Never cards.
11. **The record toggles** between the paper book and the real-money book.
12. **So Far Today moves INSIDE the AI chat panel.** See section 3.
13. **Theme: simple black and white**, one accent, light and dark. He cites his
    Atlas app as the standard. No purple, ever: it is a hard standing rule.
14. **Replace the existing pages directly.** Do not build v2 pages alongside.

---

## 3. THE AI PANEL — HANDLE WITH CARE

He wants the AI chat **kept exactly as it is**. Do not redesign it, do not
rewrite `components/chat-surface.js`, do not change its behaviour. Mount the
existing component in the new layout and leave it alone.

**So Far Today moves into the AI chat panel.** Today it is a card on home
(`components/so-far-today-card.js`). Move that component so it renders inside
the AI chat surface, at the top, above the conversation. Keep its manual
Generate button, its 60-minute cache and its daily cap. It must never fire on
page load: that is a standing cost rule and breaking it costs him real money.

The backend half is already done: the AI now receives the So Far Today summary
as section 15 of its context. You do not need to touch that.

---

## 4. CONTRACTS YOU MUST PRESERVE, OR THE APP CRASHES

`web/src/main.js` constructs and calls these. Breaking any of them breaks the
whole app, not just one page.

```
HomePage
  constructor(container, options)   options: { onOpenAIDrawer, onOpenSettings, onNavigateStrategy }
  async init()
  destroy()
  .niftyChart                       MUST exist as an object with retheme().
                                    main.js calls homePage.niftyChart.retheme?.()
                                    UNGUARDED, so undefined throws a TypeError.

StrategyBuilderPage
  constructor(container, options)
  async init()
  destroy()
  async refreshPositions()
  .payoffChart                      MUST exist with retheme()
```

Home currently mounts these components. Keep the AI chat and the PWA prompt.
The others are superseded by the new layout and may be dropped from home:

| Component | Fate |
|---|---|
| `pwa-install-prompt.js` | **Keep**, mount as today |
| `chat-surface.js` (the AI) | **Keep, unchanged.** Now also hosts So Far Today |
| `so-far-today-card.js` | **Move** into the chat surface |
| `readiness-ritual.js` | Superseded by the thin ritual strip |
| `verdict-card.js` | Drop. Readiness has no power; a verdict card implies it does |
| `kpi-history-card.js` | Drop from home |
| `nifty-snapshot-card.js` | Superseded by the NIFTY sidebar |
| `macro-events-card.js` | Superseded by the events panel |

---

## 5. HOME — `web/src/pages/home.js`

Top to bottom:

1. **Running ticker.** One horizontal marquee, pausing on hover, respecting
   `prefers-reduced-motion`. Duplicate the item list so the loop is seamless.
   Items: NIFTY spot, today's change, 20-day low and high, India VIX, ATR 20,
   20 DMA, realised vol, put-call ratio, max pain, each sector, balance, and
   market breadth which must read `unavailable`.
2. **Morning ritual strip.** One row of small label-and-value pairs: sleep,
   workout, alcohol, meditation, mood, one-line note, and an edit link. Before
   it is filled it shows "not filled in yet" and a link that opens a modal.
   **Bind saving to the SAVE BUTTON'S CLICK, not to the dialog's `close`
   event.** Some browsers do not dispatch `close` on a programmatic close, and
   a check-in that silently fails to save is worse than no check-in. This was
   found the hard way; do not undo it.
3. **Two columns.** Left is a fixed-width NIFTY sidebar of about 290px. Right
   is everything else. Single column below about 1080px.

### Left: the NIFTY sidebar

- Big spot price, freshness badge, today's change.
- Three range bars showing where price sits inside the day range, the 20-day
  range and the 50-day range. A track with a dot; if any bound is missing, the
  bar says `unavailable` rather than drawing a dot at a guessed position.
- Then rows: average daily move over 20 sessions, ATR 20, realised vol 20d,
  the 20-day moving average, the distance of spot from it, volume, advances
  and declines, sentiment.
- **Volume and breadth will come back null. They must render `unavailable`.**
- Sector list with small diverging bars, red left of centre, green right.
- Options card: India VIX, put-call ratio, max pain, weekly and monthly days
  to expiry.

### Right column

- **Your money**: balance, free cash, collateral, margin used, margin ceiling.
  Header carries the source and the timestamp it was read.
- **Today's limits**: the four rules as big rupee figures with a coloured top
  border each. Footnote states that entry is never blocked.
- **Open positions** and **Events ahead**, side by side.
- **Your record**, with the paper and real-money toggle. Both books are empty
  today. The real book must explain that real execution is code-blocked because
  no order-placement code exists. The paper book must explain that 81
  build-and-test rows are quarantined and excluded.

### Data sources — all of these already exist

```js
api.getNiftySnapshot()   // { cash_pane: {...}, fno_pane: {...} }
api.getRiskCapital()     // balance and the derived caps
api.getPositions('open')
api.getMacroEvents(false)
```

`cash_pane` gives: `spot`, `day_change_pct`, `spot_freshness`, `atr_20`,
`dma_20`, `realized_vol_20`, `range_20d {low,high}`, `range_50d {low,high}`,
`sentiment`, `sector_rotation [{name, change_pct, direction}]`, `advances`,
`declines` (both null today).

`fno_pane` gives: `india_vix`, `weekly_pcr`, `max_pain`, `weekly_dte
{formatted, calendar_days, trading_sessions}`, `monthly_dte`.

`getRiskCapital()` gives: `risk_capital_inr`, `free_cash_inr`,
`collateral_inr`, `deployable_margin_ceiling_inr`, `ceiling_unavailable_reason`,
`primary_risk_cap_inr`, `black_swan_fuse_inr`, `source`, `taken_at`,
`reconciliation_note`.

**Load every panel independently with `Promise.all` over individually
try-caught calls, so one dead feed cannot blank the page.**

---

## 6. STRATEGY BUILDER — `web/src/pages/strategy-builder.js`

### Left column, in this order

1. **Legs card.** A toolbar first: expiry for all legs, and lot multiplier
   (1x, 2x, 3x, 5x, 10x). Changing the expiry reprices every leg. Changing the
   multiplier scales every leg from its base lot count, so switching 3x to 1x
   returns to the original, not to 1.
2. **The legs table.** Columns: enable checkbox, buy/sell toggle button,
   expiry (read-only, driven by the toolbar), strike with minus and plus
   steppers of 50, type CE or PE, lots, price, and a **dustbin delete button**.
   Below it: add leg, clear, and the net debit or credit.
3. **Ready-made card.** An expiry selector above the grid, then a grid of
   preset tiles each with a small payoff sparkline. Presets: bull call spread,
   bear put spread, short straddle, iron butterfly, iron condor, naked short
   call. Selecting one loads it at the chosen expiry.
4. **Strikewise IV card.** One row per distinct strike, editable with steppers,
   so he can test a volatility change.

### Right column, in this order

1. **Metric row.** Margin needed, margin used, max profit, max loss, breakeven,
   reward to risk, value at target. Margin needed is green when it fits inside
   free margin and red with the shortfall when it does not.
   - Max loss must render the word **Unlimited**, never a number, when the
     position has a net short call or net short put.
   - Reward to risk must render `n/a` when the loss is unlimited.
2. **Payoff card.** The SVG chart, then two sliders below it: NIFTY target and
   days to expiry. Dragging on the chart itself moves the target.
3. **Greeks card**, at the target and date chosen above.
4. **Rules and execution card, last.** The four rules, the arithmetic in words,
   a verdict chip reading either "Intraday ok, may carry overnight" or
   "Intraday ok, must close before the bell", then the execute button.

### The maths

Port the Black-Scholes, payoff, breakeven and Greeks functions from the
reference prototype exactly. Key points if you must re-derive them:

- Position value per unit at expiry: CE `max(0, S-K)`, PE `max(0, K-S)`.
  Before expiry, Black-Scholes with the strike's IV.
- Multiply by `quantity_lots * 65` and by `+1` for buy, `-1` for sell.
- P&L at spot S = position value at S minus entry cost.
- **Unlimited detection**: sum signed lots per option type. A negative net call
  count is unlimited to the upside; a negative net put count is unlimited to
  the downside. Do not infer this from a sampled minimum.
- Rule 1, running loss: the worse of a 2-sigma move up and down.
- Rule 2, overnight gap: the worse of a gap of twice the average daily move,
  each way, valued one day closer to expiry.

### Server calls to prefer over local maths

Where these succeed, **trust the server over your own arithmetic**, because the
server is the authority and resolves the real contract size and real charges:

```js
api.getExpiries()
api.getOptionQuote({ strike, expiry, type })
api.validateStrategy(payload)   // returns all four rules, carry, unlimited flag
api.previewOrder(payload)       // returns real broker margin
api.executeTrade(payload, ticketId)   // sends an idempotency key automatically
```

`validateStrategy` returns `realistic_risk`, `blast_radius`, `checks[]`,
`capital`, `carry`, `max_loss_is_unlimited`, `intraday`,
`execution_blocked_reason`, `warnings[]`.

**`pct_of_margin` is ALREADY a percentage. 1.74 means 1.74%. Do not multiply
it by 100.** A previous version did, and displayed his risk as 174%. There is a
regression test for this in `web/tests/test_rule_validation_panel.test.js`;
keep it passing.

Local Black-Scholes is for instant feedback while he drags sliders. Server
figures win when they arrive.

---

## 7. THEME

Light and dark, both designed, driven by CSS custom properties on `:root`.
Follow the existing token pattern in `web/src/styles/swayam-tokens.css`.
Simple near-white and near-black grounds, one accent. **No purple, lilac or
violet anywhere.** The brand mark is the Devanagari letter `स्व` in sage green,
`#7d9d84` on light and `#9dbba3` on dark, beside the word "Swayam". **Not a
swastika.** Numbers use a monospace face with tabular figures.

---

## 8. HOW TO VERIFY, AND WHAT YOU CANNOT VERIFY

You can and must do all of this:

```bash
cd web && npm run build          # must succeed
cd web && npm test               # 116 tests must pass, none deleted
python -m pytest -q              # 327 pass, 2 pre-existing failures
```

The two known backend failures are `tests/api/test_market.py::test_get_option_chain_returns_strikes`
and `tests/test_notifications.py::test_execute_endpoint_best_effort_dispatch_on_success`.
Both pre-date this work. Do not "fix" them by weakening assertions.

**Add frontend tests** for the new pages covering, at minimum: an unlimited
position renders the word Unlimited; a null field renders `unavailable` and
never a number; `pct_of_margin` of 1.74 renders 1.74% and never 174%; the lot
multiplier scales from the base and back; changing the expiry reprices legs.

**You cannot** run the app against live data, verify a real trade, check the
deployed site, or confirm any figure against his FYERS account. **Say so in the
pull request.** Write exactly what you ran and what remains unverified. He has
been burned by false status reports; an honest gap is welcome, an overstatement
is not.

---

## 9. DELIVERABLE

Branch `feature/swayam-ui-rebuild-012`, one pull request, do not merge.

The pull request body must contain, in plain English for a non-developer:

1. What changes on screen, page by page.
2. What you ran and what passed, with numbers.
3. **What you could not verify and why.**
4. Anything you found that was wrong but did not fix, with file and line.
5. Any decision where the brief was ambiguous, and what you chose.

Keep commits focused and their messages explanatory: say why, not what.

*Real-money trading remains code-blocked. Nothing you write may claim readiness.*
