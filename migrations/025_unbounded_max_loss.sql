-- =====================================================================
-- 025_unbounded_max_loss.sql
--
-- Round 1b, fault 0a. A NAKED SINGLE LEG COULD NOT BE RECORDED.
--
-- HIS REPORT, from the live test of 11 September 2026: a sold call or a
-- sold put filled at the broker and then failed to reach the record with
-- "Out of range float values are not JSON compliant".
--
-- WHY. options_math/payoff.py answers `math.inf` for the maximum loss of a
-- net short call position, which is the honest answer: above the highest
-- strike the loss has no ceiling. That was the deliberate correction of
-- 8 September, when a short straddle used to report a confident Rs 3,69,200
-- that was an artefact of the scanning window. The figure is right. What
-- was wrong is that the execute path carried it all the way into the
-- database, and `max_loss_inr` is NOT NULL and numeric, so infinity had
-- nowhere to go and the whole trade was lost after the fills had happened.
--
-- WHAT THIS CHANGES. `max_loss_inr` and `risk_at_entry_inr` may now hold
-- NULL, meaning "this figure has no ceiling", and a new column carries the
-- REASON in words so a row read back years from now says why it is null
-- rather than leaving someone to guess between unbounded and unknown.
--
-- NULL HERE NEVER MEANS UNKNOWN. Every other figure on the row is still
-- required. If the maximum loss cannot be computed at all, that is a
-- failure and the trade is refused, exactly as before.
--
-- Additive and widening only. No existing row is touched, no value is
-- rewritten, and every row already stored keeps the figure it has. Trade
-- 7cd4d017 is not edited by this migration.
-- =====================================================================

ALTER TABLE public.swayam_positions
  ALTER COLUMN max_loss_inr DROP NOT NULL;

ALTER TABLE public.swayam_positions
  ALTER COLUMN risk_at_entry_inr DROP NOT NULL;

-- Why the figure above is null. NULL here means the loss IS bounded and the
-- figure is present; a sentence means it is not.
ALTER TABLE public.swayam_positions
  ADD COLUMN IF NOT EXISTS max_loss_unbounded_reason text;

COMMENT ON COLUMN public.swayam_positions.max_loss_inr IS
  'Worst case at expiry, a positive magnitude. NULL when the loss has no ceiling; max_loss_unbounded_reason then says why.';

COMMENT ON COLUMN public.swayam_positions.risk_at_entry_inr IS
  'The max loss as it stood at entry. NULL when the loss had no ceiling at entry.';

COMMENT ON COLUMN public.swayam_positions.max_loss_unbounded_reason IS
  'Why max_loss_inr is NULL, in words. NULL when the loss is bounded and the figure is present.';
