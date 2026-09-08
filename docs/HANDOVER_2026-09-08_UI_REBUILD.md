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

## Second pass, after the first push

A sweep over the finished work found four things and fixed all four:

1. **An unpriced leg was sent to the server as a zero premium.** The server then priced all
   four rules off a premium nobody paid, and the desk showed those figures as real. Nothing is
   sent now until every leg has a price, and any answer from an earlier priced state is
   dropped rather than left on screen.
2. **An implied volatility survived an expiry change.** Repricing a leg onto a new expiry that
   has no traded price left the old expiry's volatility in place, and the greeks and the
   on-date curve quietly used it. It is cleared now. A volatility typed by hand is his and
   still survives.
3. **The 15:20 overnight-naked watch had been dropped** with the old page and not mentioned.
   It is back: it polls open positions, raises the block modal, and says so in the execute row
   when the check itself cannot run. The suggested hedge loads at the server's strike with NO
   price — the old page pushed it in at an invented premium of 35.00 and a contract size of 75.
4. **Margin used said "positions not read yet" when something was open.** Checked against
   /api/positions: a stored position carries no margin field at all, so it now says which of
   the two situations it is in.

## Left for a human

1. Load both pages against the real backend during market hours and confirm every figure.
2. Decide whether the 20-session average daily move should move from a browser calculation
   onto the snapshot endpoint, so home and the gap test read the same number from one place.
3. `rollover_pct` is hardcoded to `68.5` in `src/swayam/services/nifty_snapshot.py`. Backend,
   out of this brief's scope, but it is a fabricated value behind a real-looking badge.
