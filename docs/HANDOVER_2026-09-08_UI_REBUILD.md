# Handover — Home and Strategy Desk rebuilt to the approved prototypes

**Date:** 2026-09-08 · **Branch:** `claude/ui-build-brief-r89zss` · **By:** Claude Code, unattended cloud session
**Brief followed:** `docs/UI_BUILD_BRIEF.md` · **Specification:** `docs/reference/home-prototype.html`, `docs/reference/strategy-desk-prototype.html`

## What changed

Two pages were replaced in place, not built alongside.

**Home** (`web/src/pages/home.js`) is now a running ticker, the morning ritual as one thin
strip filled from a modal, then two columns: a fixed NIFTY sidebar on the left and, on the
right, your money, today's four limits, open positions beside events ahead, your record with
the paper / real-money toggle, and the AI panel. So Far Today now sits at the top of the AI
panel, above the conversation, with its manual button, its 60-minute cache and its daily cap
intact. It still never fires on page load.

**Strategy Desk** (`web/src/pages/strategy-builder.js`) puts the legs at the top of the left
column with one expiry and one lot multiplier above them, then the ready-made grid with its
own expiry selector, then the strikewise volatility. The right column runs metric row, payoff
graph with two sliders and drag-to-move-target, greeks, and the four rules with the execute
button last, in one block.

## What was NOT verified

No FYERS token, no Supabase credentials, no Google Cloud access in this session. Nothing was
checked against the live account, the deployed site or a real trade. See the pull request body
for the full list.

## Left for a human

1. Load both pages against the real backend during market hours and confirm every figure.
2. Decide whether the 20-session average daily move should move from a browser calculation
   onto the snapshot endpoint, so home and the gap test read the same number from one place.
3. `rollover_pct` is hardcoded to `68.5` in `src/swayam/services/nifty_snapshot.py`. Backend,
   out of this brief's scope, but it is a fabricated value behind a real-looking badge.
