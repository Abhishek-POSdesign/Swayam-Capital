-- Migration 006: BUILD-11 Trade Journal + Analytics + Lesson Ledger
-- Creates swayam_lessons table and adds trade context columns to swayam_positions

-- 1. Create swayam_lessons table
CREATE TABLE IF NOT EXISTS swayam_lessons (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id       UUID NOT NULL REFERENCES swayam_positions(id) ON DELETE CASCADE,
    trade_closed_at   TIMESTAMPTZ NOT NULL,
    strategy_name     TEXT NOT NULL,
    outcome           TEXT NOT NULL CHECK (outcome IN ('WIN', 'LOSS', 'BREAKEVEN')),
    realised_pnl_inr  NUMERIC(12,2) NOT NULL,
    rr_planned        NUMERIC(6,2),
    rr_actual         NUMERIC(6,2),
    lesson_text       TEXT NOT NULL,
    lesson_source     TEXT NOT NULL DEFAULT 'ai_generated',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_swayam_lessons_position ON swayam_lessons(position_id);
CREATE INDEX IF NOT EXISTS idx_swayam_lessons_outcome ON swayam_lessons(outcome);
CREATE INDEX IF NOT EXISTS idx_swayam_lessons_closed_at ON swayam_lessons(trade_closed_at DESC);

-- 2. Add historical trade context fields to swayam_positions
ALTER TABLE swayam_positions ADD COLUMN IF NOT EXISTS time_in_trade_minutes INT;
ALTER TABLE swayam_positions ADD COLUMN IF NOT EXISTS spot_at_entry NUMERIC(12,2);
ALTER TABLE swayam_positions ADD COLUMN IF NOT EXISTS spot_at_exit NUMERIC(12,2);
ALTER TABLE swayam_positions ADD COLUMN IF NOT EXISTS points_in_trade NUMERIC(8,2);
ALTER TABLE swayam_positions ADD COLUMN IF NOT EXISTS directional_view TEXT;
ALTER TABLE swayam_positions ADD COLUMN IF NOT EXISTS setup_technical TEXT;
ALTER TABLE swayam_positions ADD COLUMN IF NOT EXISTS setup_location TEXT;
ALTER TABLE swayam_positions ADD COLUMN IF NOT EXISTS moneyness_summary TEXT;
ALTER TABLE swayam_positions ADD COLUMN IF NOT EXISTS with_or_against_trend TEXT;
ALTER TABLE swayam_positions ADD COLUMN IF NOT EXISTS charges_inr NUMERIC(10,2) NOT NULL DEFAULT 0;
ALTER TABLE swayam_positions ADD COLUMN IF NOT EXISTS rules_followed BOOLEAN DEFAULT true;
ALTER TABLE swayam_positions ADD COLUMN IF NOT EXISTS rules_broken_reason TEXT;
ALTER TABLE swayam_positions ADD COLUMN IF NOT EXISTS exit_reason TEXT;
ALTER TABLE swayam_positions ADD COLUMN IF NOT EXISTS entry_rationale TEXT;
ALTER TABLE swayam_positions ADD COLUMN IF NOT EXISTS exit_rationale TEXT;
