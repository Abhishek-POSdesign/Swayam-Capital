-- 001: Initial schema for Swayam Capital
-- Created: 2026-09-04
-- Multi-year sustainability: Additive-only schema. Never modify this file once applied.

-- Positions: one row per open trade (live or paper)
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    mode TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
    strategy_name TEXT NOT NULL,         -- e.g., "Bear Put Spread"
    underlying TEXT NOT NULL,            -- e.g., "NIFTY"
    expiry_date DATE NOT NULL,
    legs JSONB NOT NULL,                 -- array of {strike, ce_pe, buy_sell, qty_lots, entry_premium}
    net_debit_credit_inr NUMERIC(12, 2) NOT NULL,
    max_loss_inr NUMERIC(12, 2) NOT NULL,
    max_profit_inr NUMERIC(12, 2) NOT NULL,
    breakeven_points JSONB NOT NULL,     -- array of numbers
    stop_level NUMERIC(12, 2),           -- underlying price at which stop triggers
    target_level NUMERIC(12, 2),
    risk_at_entry_inr NUMERIC(12, 2) NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed', 'stopped')),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_opened_at ON positions(opened_at DESC);

-- Trade history: one row per closed trade (immutable log)
CREATE TABLE IF NOT EXISTS trade_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID REFERENCES positions(id),
    closed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    close_reason TEXT NOT NULL CHECK (close_reason IN ('target_hit', 'stop_hit', 'time_exit', 'manual')),
    realized_pnl_inr NUMERIC(12, 2) NOT NULL,
    total_charges_inr NUMERIC(12, 2),
    holding_days INTEGER NOT NULL,
    exit_legs JSONB NOT NULL,            -- actual exit fills
    journal_md_path TEXT                 -- path to the Obsidian journal file
);

CREATE INDEX IF NOT EXISTS idx_trade_history_closed_at ON trade_history(closed_at DESC);

-- Backtest runs: one row per backtest execution
CREATE TABLE IF NOT EXISTS backtest_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rule_snapshot JSONB NOT NULL,        -- snapshot of MethodRules at time of run
    strategy_name TEXT NOT NULL,
    date_range_start DATE NOT NULL,
    date_range_end DATE NOT NULL,
    n_trades INTEGER NOT NULL,
    win_rate NUMERIC(5, 4),
    avg_rr NUMERIC(6, 3),
    expectancy_inr NUMERIC(12, 2),
    max_drawdown_pct NUMERIC(5, 4),
    trades JSONB NOT NULL,               -- array of individual trade records
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_run_at ON backtest_runs(run_at DESC);

-- Config: overrides for values not derivable from vault (e.g., current margin base)
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by TEXT
);

-- Seed initial config
INSERT INTO config (key, value, updated_by) VALUES
    ('margin_base_inr', '850000', 'BUILD-1'),
    ('current_alcohol_streak_days', '0', 'BUILD-1'),
    ('current_reentry_ramp_tier', 'null', 'BUILD-1')
ON CONFLICT (key) DO NOTHING;

-- Readiness log: one row per trading day, records the daily verdict
CREATE TABLE IF NOT EXISTS readiness_log (
    log_date DATE PRIMARY KEY,
    verdict TEXT NOT NULL CHECK (verdict IN ('green', 'yellow', 'red')),
    factors JSONB NOT NULL,              -- {sleep: {status, hours}, alcohol: {status, streak_days}, ...}
    trading_allowed BOOLEAN NOT NULL,
    size_cap_pct NUMERIC(4, 3),          -- e.g., 0.0100 = 1%, 0.0025 = 0.25% (during re-entry ramp)
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Journal entries: one row per trade journal entry (mirrors vault markdown files)
CREATE TABLE IF NOT EXISTS journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID REFERENCES positions(id),
    entry_date DATE NOT NULL,
    entry_type TEXT NOT NULL CHECK (entry_type IN ('entry', 'daily_update', 'exit', 'no_trade_day')),
    md_path TEXT,                        -- path to vault MD file
    chart_image_path TEXT,               -- path to annotated chart PNG
    body_summary TEXT,                   -- first 500 chars of the journal
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_journal_entries_position_id ON journal_entries(position_id);
