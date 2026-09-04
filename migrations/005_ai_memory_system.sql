-- Migration 005: AI Memory System & Session Continuity
-- Created: 2026-09-07
-- Multi-year sustainability: Additive-only. Never modify this file once applied.

-- Session summaries (Trigger A: 4 PM IST daily compaction of yesterday's trading session)
CREATE TABLE IF NOT EXISTS swayam_ai_session_summaries (
    id BIGSERIAL PRIMARY KEY,
    session_date DATE NOT NULL UNIQUE,
    summary_block JSONB NOT NULL,  -- {summary, decisions, questions, preferences, constraints, nextSteps}
    message_count INTEGER NOT NULL,
    compacted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    covered_message_ids UUID[] NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_swayam_ai_session_summaries_date ON swayam_ai_session_summaries(session_date DESC);

-- Notebook entries (Layer 3: User-saved memory entries, permanent context)
CREATE TABLE IF NOT EXISTS swayam_ai_notebook (
    id BIGSERIAL PRIMARY KEY,
    entry_text TEXT NOT NULL,
    source_message_id UUID REFERENCES swayam_ai_messages(id) ON DELETE SET NULL,
    source_conversation_id UUID REFERENCES swayam_ai_conversations(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_swayam_ai_notebook_created ON swayam_ai_notebook(created_at DESC);

-- Pinned decisions (Layer 3: Permanent trading rules & constraints)
CREATE TABLE IF NOT EXISTS swayam_ai_pinned_decisions (
    id BIGSERIAL PRIMARY KEY,
    rule_text TEXT NOT NULL,
    pinned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    source_message_id UUID REFERENCES swayam_ai_messages(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_swayam_ai_pinned_active ON swayam_ai_pinned_decisions(active, pinned_at DESC);

-- Extend existing tables for trade-lifecycle memory & session tracking
ALTER TABLE swayam_ai_messages ADD COLUMN IF NOT EXISTS position_id UUID REFERENCES swayam_positions(id) ON DELETE SET NULL;
ALTER TABLE swayam_ai_messages ADD COLUMN IF NOT EXISTS session_date DATE NOT NULL DEFAULT CURRENT_DATE;
ALTER TABLE swayam_trade_history ADD COLUMN IF NOT EXISTS ai_context_summary JSONB;
ALTER TABLE swayam_trade_history ADD COLUMN IF NOT EXISTS journal_reflection TEXT;

-- Explicit RLS disable (Swayam single-user private terminal posture)
ALTER TABLE swayam_ai_session_summaries DISABLE ROW LEVEL SECURITY;
ALTER TABLE swayam_ai_notebook DISABLE ROW LEVEL SECURITY;
ALTER TABLE swayam_ai_pinned_decisions DISABLE ROW LEVEL SECURITY;
