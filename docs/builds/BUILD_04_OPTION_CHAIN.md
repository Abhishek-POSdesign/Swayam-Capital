# BUILD 04 — THE OPTION CHAIN, TESTED LIVE AND MADE USABLE

> Placeholder written 2026-09-10 evening by the main chat. Branch
> `feature/swayam-build04-option-chain-045`. **Not ready to hand to a builder:
> it waits for its own mockup from the main chat, because he will judge it by
> eye.** When the mockup is approved, the main chat fills this file to the
> shape of BUILD_01 to 03 and writes the paste-prompt.

## What is known, from `docs/PLAN.md` §2.12.5 item 9 and the session log of 10 September

- `web/src/components/option-chain-modal.js` rebuilds its whole markup every
  five seconds and throws the scroll to the top, so he could not stay on the
  at-the-money strikes. Cause confirmed. Keep his scroll across redraws and
  update rows in place.
- A strike with no trades today shows a dead last trade in live ink (22,850 CE
  at 1,575.95 against a live book of 691.90 to 709.85). Show the book, grey
  the row, never offer it for a fill.
- The at-the-money row centred and unmistakable.
- Buy and sell buttons that look like buttons.
- A readable table: fewer figures at a glance, the rest on hover.
- Max pain labelled with its expiry, on the chain and on Home, because the
  two read different expiries and neither said which.
- It already builds a structure the ticket sends: trade 8030ed03 came from it
  on 10 September.

## What is NOT known yet

The look. Mockup first, in the main chat, on his approval.
