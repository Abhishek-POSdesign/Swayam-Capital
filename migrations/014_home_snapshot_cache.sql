-- 014_home_snapshot_cache.sql
CREATE TABLE IF NOT EXISTS swayam_home_snapshot (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  snapshot_type TEXT NOT NULL, -- 'so_far_today' | 'nifty_snapshot' | 'macro_events' etc.
  generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  payload JSONB NOT NULL,
  ai_tokens_used INT
);
CREATE INDEX IF NOT EXISTS idx_home_snapshot_type_time ON swayam_home_snapshot (snapshot_type, generated_at DESC);
