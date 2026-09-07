-- =====================================================================
-- 017_quarantine_build_test_positions.sql
--
-- All 67 rows in swayam_positions were created by build and test runs
-- between 3 and 7 September 2026. Sixty-six are "Paper Bear Put", one is an
-- "Iron Fly". None is a trading decision Abhishek made. All were sized at a
-- contract size of 75, which was never the real NIFTY lot; the real lot is 65.
-- Three of them are still marked open and appear on his screen as live
-- positions.
--
-- What this does:
--   * adds a `provenance` column, so a row can say where it came from
--   * marks every existing row as build_test
--   * closes the three that are still open, with a system note
--
-- What this deliberately does NOT do: rewrite any number. Their premiums,
-- their max loss, their contract sizes all stay exactly as recorded. They
-- were computed at lot 75 and re-scaling them would invent a trade that never
-- happened. They are excluded from statistics instead.
--
-- Abhishek's real paper record starts after this migration.
-- =====================================================================

ALTER TABLE public.swayam_positions
  ADD COLUMN IF NOT EXISTS provenance text NOT NULL DEFAULT 'live';

COMMENT ON COLUMN public.swayam_positions.provenance IS
  'Where the row came from. build_test rows are excluded from every statistic and from the AI. Real trades are ''live''.';

-- Everything that exists as of this migration is build and test data.
UPDATE public.swayam_positions
   SET provenance = 'build_test'
 WHERE provenance = 'live';

-- Close the three that are still showing as open.
UPDATE public.swayam_positions
   SET status = 'archived',
       exit_reason = 'system_quarantine',
       notes = COALESCE(notes || E'\n\n', '') ||
               'Closed 2026-09-08 by the Release 1 quarantine. This was a build-test row, ' ||
               'not a trading decision, and it was sized at a contract size of 75 when the ' ||
               'real NIFTY lot is 65. Its numbers are left exactly as recorded.'
 WHERE status = 'open';

CREATE INDEX IF NOT EXISTS idx_swayam_positions_provenance
  ON public.swayam_positions USING btree (provenance);
