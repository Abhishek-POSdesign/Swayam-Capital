# Strategy Builder v2 — Final Spec (locked 2026-09-06)

> Locked with Abhishek after a full brainstorm + FYERS API research + a Comet-driven Sensibull interaction study. This is the finished order — built in one pass, not iterated.
>
> **Governing law (non-negotiable):** every number on the page is real-from-FYERS or shows an explicit "—/unavailable." IV is *implied from the real traded price*; Greeks are *computed* (labelled as such). No fudges, no hardcoded placeholders. A fake number has no place on this terminal.

---

## Why this rebuild

The prior build wired the *look* but not the *plumbing*:
- **Option-chain calls always throw** — `fyers_client.get_option_chain()` takes `underlying/strike_count/timestamp`, but `market.py` calls it with `symbol=`/`expiry=`. The `TypeError` is swallowed, so every leg silently falls back to a Black-Scholes model price + 0.14 IV. **Real prices never flow.**
- **Sliders are dead** — `handleSliderChange` calls `this.recomputeAndValidate()`, a method that does not exist. Dragging does nothing.
- **Mismatched risk numbers** — the graph draws "realistic risk" as `max_loss × 0.8` (invented) while the rule panel shows the real 2σ figure.
- Hardcoded cosmetics (spot 24842.65, "TRADING OPEN"), dead AI buttons, three overlapping rule components (only one used).

The risk *engine* (`validation.py`) is genuinely real (live margin, real 20-day realized vol, real 2σ, vault-loaded caps, readiness gate) — we keep it and feed it real inputs.

## FYERS reality (research 2026-09-06)

- **Data:** chain returns real LTP/OI/bid-ask/volume. **No IV, no Greeks in the API** → we back-solve IV from LTP and compute Greeks via Black-Scholes.
- **Execution:** FYERS v3 supports `place_multileg_order()` / `place_basket_orders()` with **per-leg type + limitPrice** — our execution ticket is shaped to match, so Phase 2 real execution drops in with no redesign. (Execution stays paper until Phase 2.)
- **No strategy-builder API** — the analytics UI is ours (correct per R2).

## Sensibull patterns adopted (Comet study)

- One unified live-recalc engine: every edit (price, IV, lots, strike, sliders) instantly updates Max P/L, POP, margin, graph.
- Basket-order dialog with **per-leg Market/Limit toggle + editable price + live depth + margin needed/available**.
- **Per-leg expiry dropdown** (weekly + monthly) → enables calendars from the same control.
- Two independent sliders (NIFTY Target spot, Date) each with −/+ fine-step and Reset.
- **Divergence from Sensibull, per Abhishek:** show **IV + Delta inline on each leg row** (Sensibull hides them in side panels; we have the space).

---

## Build set

### A. Make the data real (backend first)
1. Fix `get_option_chain` signature/callers so real chain data flows.
2. Back-solve **implied IV** from real LTP (add IV solver to `options_math`); missing price → IV "unavailable."
3. Remove silent fallbacks in `market.py` quote endpoint (0.5 delta, ₹25k spot, ₹50 LTP, 0.14 IV) → explicit unavailable flags.
4. Feed real per-leg IV into `/api/strategy/compute` (kills the fixed 0.135).
5. Add `target_spot` to compute so the NIFTY-target slider gets a precise projected-P&L readout.
6. One source of truth for risk: chart risk line = validation's real 2σ number (remove `max_loss × 0.8`).
7. Real market status (IST clock + trading calendar).

### B. Leg table (points 1, 2, 3, 7)
- Per row: B/S · **per-leg expiry dropdown** · Strike · CE/PE · **Lots (free, never restricted)** · **editable Price (LTP-prefilled)** · **IV** · **Delta**.
- Any edit → live recompute.
- **Informational** risk-appetite readout ("2σ risk = Y% of cap, within/above appetite") — never blocks sizing.

### C. Payoff graph + working sliders (points 4, 5)
- Real dual curves (Expiry + Target-date), breakevens, spot marker, SD bands, live projected-P&L tag.
- **NIFTY Target** and **Date** sliders actually wired; −/+ fine-step + Reset each.

### D. Execution ticket (point 3)
- Lists every leg with its **own Market/Limit toggle + editable price**, lots, live bid/ask depth; **Margin Needed vs Available**.
- Paper now; shaped to FYERS `place_multileg_order` for Phase 2.
- Replaces all `alert()`.

### E. Safety & clarity
- One **verdict banner** above Execute (real check, plain language).
- **Event-in-window** amber warning (RBI/CPI/FOMC inside holding window).
- **Wake Alerts** placeholder section (activates BUILD-11.13).

### F. Cleanup & layout
- Single-page/no-scroll target; purple token → emerald/slate; delete two dead rule components + broken AI buttons.

### Core vs stretch
- **Core (today):** A, B, C, D, E, cleanup.
- **Stretch (if time):** Shift/Width/Multiplier helpers, editable Strikewise-IV panel, P&L-table tab.

## Deferred (post-Monday, per Abhishek)
- What the risk section *allows/blocks* is tuned after he watches Monday's behaviour with real paper trades.

---

## FINAL BUILD PLAN — approved by Abhishek 2026-09-06 (EXECUTE AFTER COMPACTION)

> The **data layer is already done and merged-ready in PR #15** (branch `feature/swayam-strategy-builder-v2-001`): real IV/Delta-from-price, honest quote, `/api/market/expiries`, working sliders, NIFTY-target projection, execution ticket, honest spot/status, tests green (103 frontend + backend). **What remains is the visual re-skin + VIX + AI panel below.** Approved design mockups: Strategy Builder `https://claude.ai/code/artifact/f3ea243c-ee61-41b9-b20c-e8cc5cf6535c`, VIX `https://claude.ai/code/artifact/aedf8882-4f91-4280-98a0-caab82366bab`. Build to match these 1:1. Verify each in a browser, commit per chunk on the same branch.

### 1. Legs → Option B (buy-left / sell-right cards) — `leg-card.js` + `leg-builder.js`
- Two columns: **BUY legs (left), SELL legs (right)**. A leg's side is decided by its column.
- **No Buy/Sell toggle on the card.** Only a **CE/PE** toggle. Add legs via **"+ Add Buy Leg"** (buy column) and **"+ Add Sell Leg"** (sell column). Subtle green(left)/coral(right) accent so side reads at a glance.
- Per card, top row: CE/PE toggle · **strike − / + stepper** · **lots dropdown** · **price input + ↻ refresh** (refresh re-fetches live LTP via getOptionQuote; if unavailable, leave user's price, no fake).
- Per card, stats row below (small mono): **Bid / Ask / IV / Delta / OI**.
- **Global "Expiry · all legs"** dropdown at top (from `/api/market/expiries`), in addition to (or replacing) per-card expiry.
- Net Debit/Credit foot. Note: "Buys-first sequencing happens at execution, not here."
- Keep the price→real-IV/Delta wiring already built; just re-skin to cards.

### 2. Payoff graph — `payoff-chart.js` (approved as mocked)
- **Solid high-contrast lines**: expiry = solid green (thick), T+0 = solid blue (`#3a6ea5`/`#7fb0d9`), NOT faint dashes. Bigger axis + label fonts. Clear Spot line, Breakeven diamond, projected-P&L tag.
- **Fix bug #6**: the Time slider must read correct DTE (a 2-day expiry shows "2 days · Today/+1/Expiry", never "43 days"). Trace `daysToExpiry` from the real leg expiry.

### 3. Pre-trade risk panel — approved as-is (two-tier gating). No change.

### 4. VIX home card — `vix-card.js` (approved)
- Replace the tall chart + 3 stacked cards with **one compact card**: VIX + change + regime chip, a 1-year **percentile band**, and a short **60-day sparkline**. Roughly half the height.

### 5. AI side panel — mirror the Atlas side panel (no mockup; follow Atlas)
- Read Atlas's AI side-panel component + tokens (`D:\Claude\POS\Atlas`) and replicate in Swayam's side panel: **Play / Save** on messages, **Cloud (Gemini) picker**, and in settings **Voice replies** toggle, **Indian English male/female voice** dropdown, **speaking-speed** slider, clean Atlas layout. Font: match the screenshot Abhishek will provide.

### Build order (post-compaction)
1. Option B leg cards (`leg-card.js`, `leg-builder.js`) + global expiry + ↻ refresh.
2. Payoff graph high-contrast + fix DTE bug (`payoff-chart.js`).
3. Compact VIX (`vix-card.js`).
4. AI side panel from Atlas.
Each: build → browser-verify → commit on `feature/swayam-strategy-builder-v2-001`. Then update PR #15 / handoff. Abhishek merges.

---
*Branch: `feature/swayam-strategy-builder-v2-001`. Mirror this into the vault `06 - Platform Plan/` when G: access is available.*
