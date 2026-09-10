-- =====================================================================
-- 023_targets_and_phase.sql
--
-- Build A, part two. docs/builds/BUILD_02_HOME_TARGETS_AND_READING.md
-- sections 3.1 and 3.5.
--
-- Two unrelated things, in one migration because he applies migrations by
-- hand and 022 and 023 go in together.
--
--   1. TARGETS. His words, 2026-09-10: "My preference is to add a target for
--      each leg. Target always means both loss and profit... In case I cannot
--      add profit and loss for each leg, I have to add it for the whole
--      trade." A leg's targets are PRICES of that option and live in the
--      `legs` JSON the row already carries, so they need no column. The
--      whole trade's targets are RUPEES, net of charges both ways, and those
--      need three columns.
--
--   2. THE PHASE. His correction, 2026-09-10: "We have not started the paper
--      trading. We are doing the testing of how the terminal works. All these
--      paper trades are test trades." Nothing is a paper trade until he says
--      the day. That day lives in one row of one table and nowhere else.
--
-- All additive. No existing row is touched. Trade 7cd4d017 is not edited by
-- this migration or by any script in this build.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. TARGETS ON THE WHOLE TRADE.
--
-- Both in rupees, both optional, both measured against `net_if_exit_now_inr`
-- from /api/positions/live, which is after charges in AND charges to get out.
-- His words: "the actual profit that will come into my account after
-- exiting."
--
-- Reached when the net is at or above target_profit_inr, or at or below
-- minus target_loss_inr.
--
-- A BLANK PROFIT TARGET IS NO SIGNAL. A number the terminal picked is a plan
-- he did not make, so nothing is defaulted here.
--
-- A BLANK LOSS TARGET falls back to rule 1's cap, one percent of the live
-- FYERS balance read fresh by services/capital.py. That fallback is computed
-- at read time and is deliberately NOT stored: a stored percentage of a
-- balance goes stale the moment the balance moves.
--
-- Both are NULL by default, so every existing row starts with no target set,
-- which is the truth.
-- ---------------------------------------------------------------------
ALTER TABLE public.swayam_positions
  ADD COLUMN IF NOT EXISTS target_profit_inr numeric NULL;

ALTER TABLE public.swayam_positions
  ADD COLUMN IF NOT EXISTS target_loss_inr numeric NULL;

ALTER TABLE public.swayam_positions
  ADD COLUMN IF NOT EXISTS targets_set_at timestamptz NULL;

COMMENT ON COLUMN public.swayam_positions.target_profit_inr IS
  'Rupees, net of charges both ways. Reached when net_if_exit_now_inr is at or above it. NULL means no profit signal; nothing is defaulted.';

COMMENT ON COLUMN public.swayam_positions.target_loss_inr IS
  'Rupees, net of charges both ways, held as a POSITIVE number. Reached when net_if_exit_now_inr is at or below minus this. NULL falls back to rule 1 read live, never to a stored figure.';

COMMENT ON COLUMN public.swayam_positions.targets_set_at IS
  'When he last saved targets on this trade. NULL means he never has.';

-- A loss target is a size, not a direction, so it is never negative. A
-- profit target below zero would be a loss dressed as a profit.
ALTER TABLE public.swayam_positions
  DROP CONSTRAINT IF EXISTS swayam_positions_targets_sign_check;

ALTER TABLE public.swayam_positions
  ADD CONSTRAINT swayam_positions_targets_sign_check
  CHECK (
    (target_profit_inr IS NULL OR target_profit_inr > 0)
    AND (target_loss_inr IS NULL OR target_loss_inr > 0)
  );


-- ---------------------------------------------------------------------
-- 2. THE PHASE. One row, one timestamp, and it is null today.
--
-- `paper_trading_started_at` is the whole table. While it is NULL every new
-- position is written with provenance = 'terminal_test'; once it holds a
-- timestamp, new positions are 'live'. It is set by ONE script,
-- scripts/start_paper_trading.py, which HE runs on the day he decides, and
-- which refuses to run a second time.
--
-- Read through src/swayam/services/phase.py, never cached in a constant. If
-- this table cannot be read the phase service answers "not started", which
-- is the truth today and is the safe direction: a terminal test wrongly
-- called live would dirty the record his paper results are judged against.
--
-- The single-row shape is enforced by the primary key and the check, so
-- there can never be two answers to "has paper trading started".
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.swayam_phase (
  id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  paper_trading_started_at timestamptz NULL,
  set_by text NULL,
  note text NULL
);

COMMENT ON TABLE public.swayam_phase IS
  'One row. The day Abhishek said paper trading begins. NULL means it has not begun and every new position is a terminal test.';

COMMENT ON COLUMN public.swayam_phase.paper_trading_started_at IS
  'NULL until he runs scripts/start_paper_trading.py. Positions opened before it are terminal tests; positions opened after it are paper trades.';

INSERT INTO public.swayam_phase (id, paper_trading_started_at, set_by, note)
VALUES (1, NULL, NULL, 'Created by migration 023. Paper trading has not started. He says when.')
ON CONFLICT (id) DO NOTHING;


-- ---------------------------------------------------------------------
-- 3. THE THIRD PROVENANCE VALUE.
--
-- `provenance` has been a free-text column with a default of 'live' since
-- migration 017, and it carries two values today:
--
--   'live'       - a trade of his that belongs in the record
--   'build_test' - a row a build made, quarantined by 017 and 018
--
-- This adds a third:
--
--   'terminal_test' - he clicked it himself to see how the terminal behaves,
--                     before paper trading began. Real fills, real charges,
--                     real money arithmetic, but not a trade he planned.
--
-- His words: "I did not backtest, plan, or review it. It was just clicking
-- the order and checking how the terminal behaves."
--
-- No row is reclassified here. His six existing rows still say 'live' after
-- this migration, and are moved by scripts/mark_terminal_tests.py, which HE
-- runs, dry by default. The open condor is skipped until it is closed.
--
-- The journal index gets the same value for the same reason, so a statistic
-- built from it agrees with a statistic built from the positions.
-- ---------------------------------------------------------------------
COMMENT ON COLUMN public.swayam_positions.provenance IS
  'live: a trade of his, in the record. terminal_test: he clicked it to test the terminal, before paper trading began. build_test: a row a build made, quarantined.';

COMMENT ON COLUMN public.swayam_journal_entries.provenance IS
  'Mirrors swayam_positions.provenance so a statistic from the journal index agrees with one from the positions.';

CREATE INDEX IF NOT EXISTS idx_swayam_positions_opened_at
  ON public.swayam_positions USING btree (opened_at);
