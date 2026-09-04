-- Migration 004: Make meditation_completed_at nullable in swayam_readiness_log
-- Applied: BUILD-9-FIXES-A
-- Reason: Meditation is a voluntary ritual step. Blocking submission when it is
--         null caused a 500 on every POST to /api/readiness/log.

-- The column is already absent from the base schema as a top-level field;
-- it is stored inside the JSONB "factors" column as factors.input.meditation_completed_at.
-- Pydantic already accepts Optional[datetime] = None in ReadinessInput.
-- This migration is a safeguard: ensures no DB-level NOT NULL constraint blocks the upsert.

-- If the column exists as a standalone column and is NOT NULL, alter it:
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'swayam_readiness_log'
      AND column_name = 'meditation_completed_at'
      AND is_nullable = 'NO'
  ) THEN
    ALTER TABLE swayam_readiness_log
      ALTER COLUMN meditation_completed_at DROP NOT NULL;
    RAISE NOTICE 'meditation_completed_at column made nullable.';
  ELSE
    RAISE NOTICE 'meditation_completed_at column is already nullable or does not exist as a standalone column. No change needed.';
  END IF;
END $$;
