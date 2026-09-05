-- 016_notification_devices.sql
CREATE TABLE IF NOT EXISTS swayam_notification_devices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_token TEXT UNIQUE NOT NULL,
  browser_ua TEXT,
  platform TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notification_devices_last_seen ON swayam_notification_devices (last_seen_at DESC);
