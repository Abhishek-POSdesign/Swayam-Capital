-- =====================================================================
-- 026_daily_summary.sql
--
-- BUILD_07. "SO FAR TODAY" BECOMES ONE ROW A TRADING DAY, KEPT FOR EVER.
--
-- HIS WORDS, 11 September 2026: "I want to save the AI-generated summary.
-- I'm paying for that, so I don't want to lose those details and create a
-- record of what's happening, a trend in the market or in the geopolitics
-- as well."
--
-- WHAT WAS WRONG. The summary was already being saved, into
-- swayam_home_snapshot (migration 014) as one row per PRESS of Generate.
-- Press it four times in a day and four copies of that day exist, with no
-- key saying which is the day's summary. That is a cache, not a record.
--
-- WHAT THIS CREATES. One row per IST trading day, keyed on the day, so a
-- regeneration REPLACES that day's row and keeps the newest stamp. Past
-- days are never touched again.
--
-- THE TRAP THIS COLUMN EXISTS FOR. His standing AI cost rule is a manual
-- button, a 60-minute cache and a daily cap of eight. The cap used to be
-- enforced by COUNTING ROWS in swayam_home_snapshot since IST midnight.
-- Collapse to one row a day and that count silently becomes one, so the
-- second press of the day would be refused as "cap reached". The cap
-- therefore reads generation_count on the day's own row instead. Checked
-- by the main chat on 12 September: count_grounded_calls_today is used
-- only inside services/so_far_today.py, so nothing else can be affected.
--
-- THE BACKFILL, on his instruction of 12 September. The NEWEST summary of
-- each past day is copied in as this table is created, so the record he
-- has already paid for starts with what he already owns rather than
-- starting empty. NOTHING IS DELETED FROM swayam_home_snapshot. That table
-- keeps every row it has, and keeps serving the nifty_snapshot type, which
-- this migration does not touch.
--
-- WHY model IS NULL ON THE BACKFILLED ROWS. The old payload never recorded
-- which model wrote it. The code of the day always called gemini-2.5-flash,
-- but that is an inference from source control, not a fact on the row, and
-- his first rule is that a figure is real or it says unavailable. Rows
-- written from today forward carry the model they were actually generated
-- with. Rows before today say nothing, because nothing was recorded.
--
-- Additive only. No existing table is altered, no existing row is
-- rewritten, and no trade is touched.
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.swayam_daily_summary (
    day              date        PRIMARY KEY,
    text             text        NOT NULL,
    sources          jsonb       NOT NULL DEFAULT '[]'::jsonb,
    search_queries   jsonb       NOT NULL DEFAULT '[]'::jsonb,
    model            text,
    generated_at     timestamptz NOT NULL DEFAULT NOW(),
    generation_count integer     NOT NULL DEFAULT 1,
    ai_tokens_used   integer
);

CREATE INDEX IF NOT EXISTS idx_daily_summary_day
    ON public.swayam_daily_summary (day DESC);

COMMENT ON TABLE public.swayam_daily_summary IS
  'One grounded market summary per IST trading day. Regenerating a day replaces its row; past days are kept for ever. BUILD_07.';

COMMENT ON COLUMN public.swayam_daily_summary.day IS
  'The IST trading day this summary describes. The key: one row a day, never two.';

COMMENT ON COLUMN public.swayam_daily_summary.generated_at IS
  'When the summary now stored was written. A regeneration moves this forward.';

COMMENT ON COLUMN public.swayam_daily_summary.generation_count IS
  'How many times Generate was pressed on this day. His daily cap of eight is enforced against this, not against a row count.';

COMMENT ON COLUMN public.swayam_daily_summary.model IS
  'Which model wrote the stored text. NULL on rows backfilled from swayam_home_snapshot, where it was never recorded. NULL means not recorded, never unknown-so-guess.';

-- ---------------------------------------------------------------------
-- The backfill. Newest summary of each past IST day, counted honestly.
-- Re-runnable: ON CONFLICT DO NOTHING leaves a day that already exists.
-- ---------------------------------------------------------------------
WITH src AS (
    SELECT
        (generated_at AT TIME ZONE 'Asia/Kolkata')::date AS ist_day,
        payload,
        generated_at,
        ai_tokens_used,
        ROW_NUMBER() OVER (
            PARTITION BY (generated_at AT TIME ZONE 'Asia/Kolkata')::date
            ORDER BY generated_at DESC
        ) AS newest_first,
        COUNT(*) OVER (
            PARTITION BY (generated_at AT TIME ZONE 'Asia/Kolkata')::date
        ) AS presses_that_day
    FROM public.swayam_home_snapshot
    WHERE snapshot_type = 'so_far_today'
      AND COALESCE(payload ->> 'text', '') <> ''
)
INSERT INTO public.swayam_daily_summary
    (day, text, sources, search_queries, model, generated_at, generation_count, ai_tokens_used)
SELECT
    ist_day,
    payload ->> 'text',
    COALESCE(payload -> 'sources', '[]'::jsonb),
    COALESCE(payload -> 'search_queries', '[]'::jsonb),
    NULL,
    generated_at,
    presses_that_day::integer,
    ai_tokens_used
FROM src
WHERE newest_first = 1
ON CONFLICT (day) DO NOTHING;
