"""
Unit tests for DuckDB migrations.
"""

from pathlib import Path
import sys
import duckdb
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from apply_duckdb_migrations import apply_duckdb_migrations


def test_duckdb_migration_idempotency(tmp_path):
    db_path = tmp_path / "test_migration.duckdb"
    conn = duckdb.connect(str(db_path))

    # Run 1: Should apply 003_realized_vol_cache.sql
    applied_1 = apply_duckdb_migrations(conn=conn)
    assert "003_realized_vol_cache.sql" in applied_1

    # Verify table structure
    tables = [r[0] for r in conn.execute("SHOW TABLES;").fetchall()]
    assert "realized_vol_cache" in tables
    assert "_duckdb_migrations" in tables

    # Verify columns in realized_vol_cache
    cols = {r[1] for r in conn.execute("PRAGMA table_info('realized_vol_cache');").fetchall()}
    assert {"symbol", "as_of_date", "window_days", "annualized_vol", "computed_at", "bar_count"}.issubset(cols)

    # Run 2: Idempotent - should apply 0 migrations
    applied_2 = apply_duckdb_migrations(conn=conn)
    assert applied_2 == []

    # Verify table is still intact and valid
    tables_after = [r[0] for r in conn.execute("SHOW TABLES;").fetchall()]
    assert "realized_vol_cache" in tables_after
