-- =====================================================================
-- 021_execution_ticket.sql
--
-- The execution ticket, docs/PLAN.md section 2.12, PR 1.
--
-- Three things a trade has never recorded, and one kind of note that could
-- not be queued. All additive. No existing row is touched.
-- =====================================================================


-- ---------------------------------------------------------------------
-- The margin the broker needed for this position when it was opened.
--
-- Rule 4, the deployable margin ceiling, compares margin NEEDED plus margin
-- already USED against twice the cash-equivalent holding. Margin used was
-- never stored on a position, so the desk has said "margin already used is
-- unknown, so the ceiling cannot be tested" on every trade he has taken.
-- A rule that can never be tested is a rule that does not work.
--
-- From this migration the execute path stores the broker's basket margin on
-- the row, and the desk sums it across open positions. A position opened
-- before this keeps NULL, and a NULL in the sum makes the whole figure
-- "unavailable" rather than a smaller number that looks whole.
-- ---------------------------------------------------------------------
ALTER TABLE public.swayam_positions
  ADD COLUMN IF NOT EXISTS margin_required_inr numeric(12,2) NULL;

COMMENT ON COLUMN public.swayam_positions.margin_required_inr IS
  'The broker margin for the whole basket when it was opened, from the FYERS margin endpoint. NULL means the broker could not be asked at the time; never a guess.';

ALTER TABLE public.swayam_positions
  ADD COLUMN IF NOT EXISTS margin_quoted_at timestamptz NULL;

COMMENT ON COLUMN public.swayam_positions.margin_quoted_at IS
  'When the broker quoted margin_required_inr.';

ALTER TABLE public.swayam_positions
  ADD COLUMN IF NOT EXISTS margin_source text NULL;

COMMENT ON COLUMN public.swayam_positions.margin_source IS
  'Where margin_required_inr came from, or why it is NULL.';


-- ---------------------------------------------------------------------
-- How the legs were filled.
--
-- PR 1 fills at the traded price and records that fact. PR 2 fills a buy at
-- the ask and a sell at the bid, and the two are NOT comparable. His three
-- trades of 2026-09-09 were filled at the traded price and must say so in
-- the record, which is PR 2's migration, not this one.
-- ---------------------------------------------------------------------
ALTER TABLE public.swayam_positions
  ADD COLUMN IF NOT EXISTS fill_basis text NULL;

COMMENT ON COLUMN public.swayam_positions.fill_basis IS
  'traded_price: every leg filled at the last traded price. bid_ask: buys at the ask, sells at the bid. NULL: opened before this was recorded.';

ALTER TABLE public.swayam_positions
  DROP CONSTRAINT IF EXISTS swayam_positions_fill_basis_check;

ALTER TABLE public.swayam_positions
  ADD CONSTRAINT swayam_positions_fill_basis_check
  CHECK (fill_basis IS NULL OR fill_basis IN ('traded_price', 'bid_ask'));


-- ---------------------------------------------------------------------
-- A leg added to an open trade needs a note, and the outbox refused the
-- kind. "Execute one by one" opens the trade on the first leg and adds each
-- later leg to the same trade, which is the campaign model from section
-- 2.11. Each added leg appends an adjustment block to the trade's note, and
-- when the vault is unreachable that block queues here like any other.
-- ---------------------------------------------------------------------
ALTER TABLE public.swayam_journal_outbox
  DROP CONSTRAINT IF EXISTS swayam_journal_outbox_kind_check;

ALTER TABLE public.swayam_journal_outbox
  ADD CONSTRAINT swayam_journal_outbox_kind_check
  CHECK (kind IN ('new_trade', 'close', 'add_leg'));
