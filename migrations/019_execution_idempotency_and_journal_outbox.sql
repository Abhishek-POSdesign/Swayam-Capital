-- =====================================================================
-- 019_execution_idempotency_and_journal_outbox.sql
--
-- Plan v9 Step 5, which Release 1 did not ship. Two problems, one migration,
-- because they are the same failure seen from two ends.
--
-- PROBLEM 1: a double click creates two positions.
--   There is no idempotency key, no unique constraint and no in-flight guard
--   anywhere in the execution path. This matters most precisely when something
--   else has gone wrong, because that is when he clicks again.
--
-- PROBLEM 2: a failed journal write returns HTTP 500 after the position has
--   already been inserted.
--   The live site cannot reach the vault at all: VAULT_PATH is unset on Cloud
--   Run, so config.py falls back to the Windows path G:\My Drive\Second Brain,
--   which a Linux container has no way to reach. So today EVERY trade on the
--   live site inserts the position, fails the journal write, and reports an
--   error. He then clicks again, and problem 1 gives him two positions for one
--   trade.
--
-- The journal note must never fail the trade. It becomes an outbox row that a
-- drainer completes later, and the position carries its own journal_status so
-- nothing is silently lost.
-- =====================================================================


-- ---------------------------------------------------------------------
-- Idempotency. The unique constraint is the control; a disabled button is
-- only a convenience.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.swayam_execution_attempts (
    idempotency_key text PRIMARY KEY,
    payload_hash    text        NOT NULL,
    position_id     uuid        NULL,
    outcome         text        NOT NULL DEFAULT 'in_flight',
    response        jsonb       NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    completed_at    timestamptz NULL,
    CONSTRAINT swayam_execution_attempts_outcome_check
        CHECK (outcome IN ('in_flight', 'succeeded', 'failed'))
);

COMMENT ON TABLE public.swayam_execution_attempts IS
  'One row per execution attempt, keyed by the idempotency key the browser generates and reuses on every retry. Same key and same payload replays the stored response. Same key and a different payload is rejected.';

COMMENT ON COLUMN public.swayam_execution_attempts.payload_hash IS
  'SHA-256 of the canonical request. Guards against a key being reused for a different trade.';

CREATE INDEX IF NOT EXISTS swayam_execution_attempts_position_idx
    ON public.swayam_execution_attempts (position_id);


-- ---------------------------------------------------------------------
-- The journal outbox. A queued note, not a lost one.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.swayam_journal_outbox (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id  uuid        NOT NULL,
    kind         text        NOT NULL DEFAULT 'new_trade',
    payload      jsonb       NOT NULL,
    status       text        NOT NULL DEFAULT 'pending',
    attempts     integer     NOT NULL DEFAULT 0,
    last_error   text        NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    drained_at   timestamptz NULL,
    md_path      text        NULL,
    CONSTRAINT swayam_journal_outbox_status_check
        CHECK (status IN ('pending', 'done', 'failed')),
    CONSTRAINT swayam_journal_outbox_kind_check
        CHECK (kind IN ('new_trade', 'close'))
);

COMMENT ON TABLE public.swayam_journal_outbox IS
  'Journal notes that could not be written to the vault at the time of the trade, usually because the writer was a Linux container with no route to his Google Drive folder. A drainer completes them. A trade is never failed because of a note.';

CREATE INDEX IF NOT EXISTS swayam_journal_outbox_pending_idx
    ON public.swayam_journal_outbox (status, created_at)
    WHERE status = 'pending';


-- ---------------------------------------------------------------------
-- The position says, on its own row, whether its note was written.
-- ---------------------------------------------------------------------
ALTER TABLE public.swayam_positions
  ADD COLUMN IF NOT EXISTS journal_status text NOT NULL DEFAULT 'written';

COMMENT ON COLUMN public.swayam_positions.journal_status IS
  'written when the markdown note is in the vault, pending while it sits in swayam_journal_outbox, failed when the drainer gave up. Never blocks the trade.';

-- Every row that exists today was written from his own PC, where the vault is
-- reachable, so 'written' is the correct state for all of them.
UPDATE public.swayam_positions
SET journal_status = 'written'
WHERE journal_status IS NULL;

ALTER TABLE public.swayam_positions
  DROP CONSTRAINT IF EXISTS swayam_positions_journal_status_check;

ALTER TABLE public.swayam_positions
  ADD CONSTRAINT swayam_positions_journal_status_check
      CHECK (journal_status IN ('written', 'pending', 'failed'));
