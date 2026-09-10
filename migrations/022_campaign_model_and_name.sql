-- =====================================================================
-- 022_campaign_model_and_name.sql
--
-- Build A, part one. docs/builds/BUILD_01_DESK_POSITION_AREA.md section 3.1.
--
-- A trade is a CAMPAIGN, not a leg. His rule, 2026-09-08: "Every leg that I
-- square off will have its own profit/loss added, and every new leg I add
-- will be considered in the same trade. Once I close all the legs or I say
-- 'the trade is closed', then only the trade is closed."
--
-- Almost none of that needs a column. The per-leg state lives in the `legs`
-- JSON the row already carries, so a leg gains `status`, `closed_at`,
-- `exit_premium`, `exit_side_hit`, `exit_ltp`, `exit_order_type`,
-- `exit_limit_price`, `exit_spread_cost_inr`, `exit_charges_inr`,
-- `gross_pnl_inr` and `net_pnl_inr` as it is closed. A leg with no `status`
-- is open, which is every leg on every existing row, so nothing has to be
-- backfilled and no existing row is touched.
--
-- Two things DO need the schema: where the strategy's name came from, and a
-- new kind of note in the outbox.
--
-- All additive. No existing row is touched. Trade 7cd4d017 is not edited by
-- this migration or by any script in this build.
-- =====================================================================


-- ---------------------------------------------------------------------
-- Where the name came from.
--
-- His correction, 2026-09-10: "Short Strangle was not the name chosen by me.
-- It was the system error that gave it the name." He loaded the strangle
-- preset, the ticket refused his limit price because the book had not
-- reached it, he went to a condor at market, and the stored name stayed with
-- the preset that had been loaded first. "I had no role to play in naming
-- any order I made today."
--
-- From this migration the name is derived from the OPEN legs by
-- services/structure_name.py and recomputed whenever the legs change, unless
-- he has named the trade himself. `name_source` is what says which:
--
--   'structure' - the terminal derives it, and keeps it right as legs change
--   'his'       - he typed it, and nothing overwrites it, ever
--
-- Existing rows default to 'structure', so his open condor corrects its own
-- name the first time a leg of it is touched or he presses Edit name. It is
-- NOT renamed by this migration, because a script does not touch that trade.
-- ---------------------------------------------------------------------
ALTER TABLE public.swayam_positions
  ADD COLUMN IF NOT EXISTS name_source text NOT NULL DEFAULT 'structure';

COMMENT ON COLUMN public.swayam_positions.name_source IS
  'structure: strategy_name is derived from the open legs and recomputed when they change. his: he named it and nothing overwrites it.';

ALTER TABLE public.swayam_positions
  DROP CONSTRAINT IF EXISTS swayam_positions_name_source_check;

ALTER TABLE public.swayam_positions
  ADD CONSTRAINT swayam_positions_name_source_check
  CHECK (name_source IN ('structure', 'his'));


-- ---------------------------------------------------------------------
-- A leg exited on its own needs a note, and the outbox refused the kind.
--
-- Exiting one leg of four is an adjustment, not a close: the trade stays
-- open and its note gets a line under Adjustments saying which leg went, at
-- what price, on which side of the book and for what result. When the vault
-- cannot be reached from the container that block queues here, like every
-- other kind, and the drainer writes it from his PC.
--
-- 'close' still means the whole trade squared off and still appends the Exit
-- block. Nothing about that changes.
-- ---------------------------------------------------------------------
ALTER TABLE public.swayam_journal_outbox
  DROP CONSTRAINT IF EXISTS swayam_journal_outbox_kind_check;

ALTER TABLE public.swayam_journal_outbox
  ADD CONSTRAINT swayam_journal_outbox_kind_check
  CHECK (kind IN ('new_trade', 'close', 'add_leg', 'leg_exit'));
