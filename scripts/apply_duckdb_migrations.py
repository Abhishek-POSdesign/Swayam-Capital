"""
DuckDB Migration Runner for Swayam Capital.

Finds and executes SQL migration scripts against the local DuckDB database.
"""

from pathlib import Path
import sys
from typing import Optional
import duckdb

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from swayam.config import settings


def apply_duckdb_migrations(
    conn: Optional[duckdb.DuckDBPyConnection] = None,
    db_path: Optional[Path] = None,
) -> list[str]:
    """Applies all pending DuckDB migration SQL files idempotently.

    Args:
        conn: Optional active DuckDB connection.
        db_path: Optional path to DuckDB database file.

    Returns:
        list[str]: Names of newly applied migration files.
    """
    migrations_dir = ROOT_DIR / "migrations" / "duckdb"
    if not migrations_dir.exists():
        return []

    target_conn = conn if conn is not None else duckdb.connect(str(db_path or settings.duckdb_path))

    # Migration tracking table
    target_conn.execute("""
        CREATE TABLE IF NOT EXISTS _duckdb_migrations (
            migration_name TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    applied_rows = target_conn.execute("SELECT migration_name FROM _duckdb_migrations;").fetchall()
    applied_set = {r[0] for r in applied_rows}

    sql_files = sorted(migrations_dir.glob("*.sql"))
    executed = []

    for sql_file in sql_files:
        if sql_file.name not in applied_set:
            sql_content = sql_file.read_text(encoding="utf-8")
            target_conn.execute(sql_content)
            target_conn.execute("INSERT INTO _duckdb_migrations (migration_name) VALUES (?);", [sql_file.name])
            executed.append(sql_file.name)

    return executed


if __name__ == "__main__":
    executed = apply_duckdb_migrations()
    print(f"[OK] Applied {len(executed)} DuckDB migrations: {executed}")
