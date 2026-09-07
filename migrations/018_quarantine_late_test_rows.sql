-- =====================================================================
-- 018_quarantine_late_test_rows.sql
--
-- Migration 017 quarantined 79 rows at 19:03 on 2026-09-07 and the session
-- that ran it reported that Abhishek's paper record now started clean.
--
-- It did not. Two further rows were created four minutes later, at
-- 19:07:06.927909+00 and 19:07:07.848962+00, one second apart:
--
--     "Violating Spread"   opened 2026-09-07 19:07:06.927909+00
--     "Paper Bear Put"     opened 2026-09-07 19:07:07.848962+00
--
-- Both names are fixtures in tests/api/test_execute_paper.py. One second
-- apart is a machine, not a person. They were created by a test run that
-- happened after 017 had already set the provenance default to 'live', so
-- unlike the first 79 they carry provenance = 'live' and status = 'open',
-- which makes them indistinguishable from a real trade and puts them into
-- his open book and his risk picture.
--
-- The hole they came through is closed in code as of the commit that adds
-- tests/db_guard.py: the suite now runs against an in-memory database and a
-- write to the live project raises. This migration cleans up what it let in.
--
-- Scoped by id, deliberately. Matching on strategy_name would also catch a
-- genuine future trade Abhishek happens to name "Paper Bear Put", which is a
-- plausible name for a real bear put spread.
--
-- Quarantine, never delete. The audit trail is the point.
-- =====================================================================

-- The two rows, by primary key.
UPDATE public.swayam_positions
SET
    provenance = 'build_test',
    status     = 'archived',
    notes      = COALESCE(notes || ' | ', '')
                 || 'Quarantined by migration 018. Created by a test run at '
                 || to_char(opened_at, 'YYYY-MM-DD HH24:MI:SS')
                 || ' UTC, four minutes after migration 017. Not a trading decision.'
WHERE id IN (
    SELECT id
    FROM public.swayam_positions
    WHERE provenance = 'live'
      AND opened_at >= TIMESTAMPTZ '2026-09-07 19:07:00+00'
      AND opened_at <  TIMESTAMPTZ '2026-09-07 19:08:00+00'
);

-- The journal index has no provenance column of its own, so a statistic built
-- from it cannot currently exclude test rows. Give it the same column the
-- positions table got in 017, then mark every entry whose position is
-- build_test. All 81 of them are, because all 81 positions are.
ALTER TABLE public.swayam_journal_entries
  ADD COLUMN IF NOT EXISTS provenance text NOT NULL DEFAULT 'live';

COMMENT ON COLUMN public.swayam_journal_entries.provenance IS
  'Where the row came from. build_test rows are excluded from every statistic and from the AI. Real entries are ''live''.';

UPDATE public.swayam_journal_entries AS j
SET provenance = 'build_test'
FROM public.swayam_positions AS p
WHERE p.id = j.position_id
  AND p.provenance = 'build_test'
  AND j.provenance <> 'build_test';

-- After this migration the expected state of swayam_positions is:
--     81 rows, all provenance = 'build_test', all status = 'archived',
--     zero rows with status = 'open'.
-- Abhishek's real paper record starts at the next row inserted.
