# BUILD 04 — THE OPTION CHAIN, TESTED LIVE AND MADE USABLE

> Written 2026-09-10 evening by the main chat. **This is PART THREE OF BUILD
> A**, built by the same chat, on the same branch and in the same pull request
> as BUILD_01 and BUILD_02, after both. **It waits for its own mockup from the
> main chat, because he will judge it by eye.** The main chat supplies that
> mockup into Build A's chat while the builder is on parts one and two, and
> fills this file to the shape of the others at the same time. The builder
> starts the chain only when the mockup is in hand; if it is not there when
> parts one and two are done, the builder says so and waits rather than
> guessing at the look.

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
