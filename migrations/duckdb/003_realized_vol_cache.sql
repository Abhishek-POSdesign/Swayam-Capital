-- Migration 003: Create realized_vol_cache table in DuckDB
CREATE TABLE IF NOT EXISTS realized_vol_cache (
    symbol TEXT NOT NULL,
    as_of_date DATE NOT NULL,
    window_days INTEGER NOT NULL,
    annualized_vol DOUBLE NOT NULL,
    computed_at TIMESTAMP NOT NULL,
    bar_count INTEGER NOT NULL,
    PRIMARY KEY (symbol, as_of_date, window_days)
);
