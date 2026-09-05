-- 007: Allow 'archived' status in swayam_positions for archiving pre-launch test trades
-- Created: 2026-09-05

ALTER TABLE swayam_positions DROP CONSTRAINT IF EXISTS swayam_positions_status_check;
ALTER TABLE swayam_positions ADD CONSTRAINT swayam_positions_status_check CHECK (status IN ('open', 'closed', 'stopped', 'archived'));
