-- Migration 002: AI conversation state + rule evolution audit + cost tracking + explicit RLS disable
-- Created: 2026-09-05
-- Multi-year sustainability: Additive-only. Never modify this file once applied.

-- AI conversation state (persistent chat history)
CREATE TABLE IF NOT EXISTS swayam_ai_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    title TEXT,                       -- auto-generated from first message
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_swayam_ai_conversations_last_active ON swayam_ai_conversations(last_active_at DESC) WHERE NOT archived;

CREATE TABLE IF NOT EXISTS swayam_ai_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES swayam_ai_conversations(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    context_snapshot JSONB,           -- what data was in context when this message was sent
    provider TEXT,                    -- 'vertex-gemini-3.1-pro-preview', etc.
    input_tokens INTEGER,
    output_tokens INTEGER,
    latency_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_swayam_ai_messages_conversation ON swayam_ai_messages(conversation_id, created_at);

-- Rule evolution log (audit trail — for the "rules evolve during paper trading" workflow)
CREATE TABLE IF NOT EXISTS swayam_rule_evolution_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rule_name TEXT NOT NULL,          -- e.g., 'per_trade_risk_pct'
    old_value JSONB,
    new_value JSONB NOT NULL,
    changed_by TEXT NOT NULL,         -- 'manual', 'ai_suggested_approved', etc.
    reason TEXT,
    reverted_at TIMESTAMPTZ           -- populated if this change was later reverted
);

CREATE INDEX IF NOT EXISTS idx_swayam_rule_evolution_log_changed_at ON swayam_rule_evolution_log(changed_at DESC);

-- Daily AI cost tracking
CREATE TABLE IF NOT EXISTS swayam_ai_usage_daily (
    day DATE PRIMARY KEY,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    total_input_tokens INTEGER NOT NULL DEFAULT 0,
    total_output_tokens INTEGER NOT NULL DEFAULT 0,
    request_count INTEGER NOT NULL DEFAULT 0,
    estimated_cost_inr NUMERIC(10, 2) NOT NULL DEFAULT 0.0
);

-- Explicit RLS disable (documenting single-user private trading terminal posture)
ALTER TABLE swayam_positions DISABLE ROW LEVEL SECURITY;
ALTER TABLE swayam_trade_history DISABLE ROW LEVEL SECURITY;
ALTER TABLE swayam_backtest_runs DISABLE ROW LEVEL SECURITY;
ALTER TABLE swayam_config DISABLE ROW LEVEL SECURITY;
ALTER TABLE swayam_readiness_log DISABLE ROW LEVEL SECURITY;
ALTER TABLE swayam_journal_entries DISABLE ROW LEVEL SECURITY;
ALTER TABLE swayam_ai_conversations DISABLE ROW LEVEL SECURITY;
ALTER TABLE swayam_ai_messages DISABLE ROW LEVEL SECURITY;
ALTER TABLE swayam_rule_evolution_log DISABLE ROW LEVEL SECURITY;
ALTER TABLE swayam_ai_usage_daily DISABLE ROW LEVEL SECURITY;
