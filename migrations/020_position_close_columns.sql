-- =====================================================================
-- 020_position_close_columns.sql
--
-- WITHOUT THIS, HE CANNOT CLOSE A TRADE. Found 2026-09-09 by probing the
-- live schema with the exact payload the close path writes, rather than by
-- reading code.
--
-- `POST /api/positions/{id}/close` writes two columns to swayam_positions
-- that DO NOT EXIST: `closed_at` and `journal_path`. PostgREST rejects both.
-- Nobody had noticed because nobody has ever closed a trade: the table has
-- held nothing but quarantined build-test rows since the day it was created.
--
-- What would have happened at his desk this afternoon:
--
--   1. The result is INSERTED into swayam_trade_history. Recorded correctly.
--   2. The UPDATE marking the position closed fails on the missing column.
--   3. He gets HTTP 503.
--   4. The position still reads `open`.
--   5. He presses close again, and step 1 runs a SECOND time, so his record
--      double counts that trade.
--
-- Step 5 is the reason this is a migration and not a code tidy-up. It is the
-- same shape as the double-execution fault that 019 fixed on the entry side,
-- and the exit side was never checked.
--
-- Both columns are nullable and additive. No existing row is touched, and the
-- 81 quarantined build-test rows are unaffected.
-- =====================================================================


-- ---------------------------------------------------------------------
-- When the trade was squared off.
--
-- The journal already reads this name (`api/routes/journal.py` computes time
-- in trade from `opened_at` and `closed_at`), and it has silently read None
-- for every row, so every duration fell back to the stored minutes or to a
-- dash.
-- ---------------------------------------------------------------------
ALTER TABLE public.swayam_positions
  ADD COLUMN IF NOT EXISTS closed_at timestamptz NULL;

COMMENT ON COLUMN public.swayam_positions.closed_at IS
  'When the position was squared off. NULL while it is open. Written by '
  'POST /api/positions/{id}/close.';


-- ---------------------------------------------------------------------
-- Where the trade's note lives in his Obsidian vault.
--
-- The path was computed at entry and kept only in an in-memory dict, so the
-- database row never carried it. At close, `pos.get("journal_path")` was
-- therefore always None and the exit block was never appended: his note would
-- have sat on "Exit (to be filled at close): TBD" forever, whatever he did.
--
-- The path IS recorded in swayam_journal_entries.md_path, so nothing was
-- lost; the close path simply had no way to find it. It is stored here now,
-- and the close falls back to that table for any row written before today.
-- ---------------------------------------------------------------------
ALTER TABLE public.swayam_positions
  ADD COLUMN IF NOT EXISTS journal_path text NULL;

COMMENT ON COLUMN public.swayam_positions.journal_path IS
  'Vault-relative path of the trade note, e.g. '
  '"02 - Projects/Trading/04 - Journal/2026-09-09-trade01.md". Written at '
  'entry once the note lands; NULL when the note is queued in the outbox.';


-- ---------------------------------------------------------------------
-- One close, one result.
--
-- A partial unique index, so a position can never accumulate two rows in
-- swayam_trade_history. Belt to the code's braces: the close path now checks
-- for an existing row first, but a constraint is the control and a check is a
-- convenience, exactly as 019 argued for the entry side.
-- ---------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS uq_swayam_trade_history_position
  ON public.swayam_trade_history (position_id)
  WHERE position_id IS NOT NULL;
