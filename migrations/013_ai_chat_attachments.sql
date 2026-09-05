-- 013_ai_chat_attachments.sql
-- BUILD-11.7: Add image attachment columns to swayam_ai_messages

ALTER TABLE swayam_ai_messages
  ADD COLUMN IF NOT EXISTS attachment_url TEXT,
  ADD COLUMN IF NOT EXISTS attachment_mime TEXT;
