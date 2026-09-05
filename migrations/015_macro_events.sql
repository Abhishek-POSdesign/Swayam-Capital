-- 015_macro_events.sql
CREATE TABLE IF NOT EXISTS swayam_macro_events (
  event_key TEXT PRIMARY KEY,          -- from Trading Economics / source id
  event_name TEXT NOT NULL,
  event_date DATE NOT NULL,
  event_time_ist TIME,
  country TEXT NOT NULL,               -- 'IN' | 'US'
  category TEXT,                       -- 'monetary', 'inflation', 'employment', 'corporate', etc.
  importance TEXT,                     -- 'high' | 'medium' | 'low'
  highlighted BOOLEAN NOT NULL DEFAULT FALSE,
  impact_brief TEXT,                   -- Gemini-generated impact brief
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  curated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_macro_events_date ON swayam_macro_events (event_date);
CREATE INDEX IF NOT EXISTS idx_macro_events_highlighted ON swayam_macro_events (highlighted, event_date);
