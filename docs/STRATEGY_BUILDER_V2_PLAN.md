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
*Branch: `feature/swayam-strategy-builder-v2-001`. Mirror this into the vault `06 - Platform Plan/` when G: access is available.*
