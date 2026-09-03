"""
Local DuckDB Storage Manager for Swayam Capital.

Manages local high-performance analytics storage for historical options data,
Bhavcopy ingestion, and backtesting queries without cloud database overhead.
"""

from pathlib import Path
from typing import Optional
import duckdb
import pandas as pd
from swayam.config import settings


class LocalDB:
    """Manages the local DuckDB instance at `data/options_cache.duckdb`."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path or settings.duckdb_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[duckdb.DuckDBPyConnection] = None

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Returns the active DuckDB connection, initializing the schema on first connect."""
        if self._conn is None:
            self._conn = duckdb.connect(str(self.db_path))
            self.init_schema(self._conn)
        return self._conn

    def init_schema(self, conn: Optional[duckdb.DuckDBPyConnection] = None) -> None:
        """Initializes the `options_history` table and indices if they do not exist."""
        active_conn = conn or self.get_connection()
        active_conn.execute("""
            CREATE TABLE IF NOT EXISTS options_history (
                trade_date DATE NOT NULL,
                symbol TEXT NOT NULL,
                underlying TEXT NOT NULL,
                expiry_date DATE NOT NULL,
                strike NUMERIC(10, 2) NOT NULL,
                option_type TEXT NOT NULL,
                open NUMERIC(10, 2),
                high NUMERIC(10, 2),
                low NUMERIC(10, 2),
                close NUMERIC(10, 2) NOT NULL,
                settle_price NUMERIC(10, 2),
                volume BIGINT,
                turnover_inr NUMERIC(15, 2),
                open_interest BIGINT,
                change_in_oi BIGINT,
                underlying_spot NUMERIC(10, 2),
                snapshot_time_utc TIMESTAMP NOT NULL DEFAULT '1970-01-01 00:00:00',
                bid NUMERIC(10, 2),
                ask NUMERIC(10, 2),
                iv NUMERIC(6, 4),
                delta NUMERIC(6, 4),
                gamma NUMERIC(8, 6),
                theta NUMERIC(10, 2),
                vega NUMERIC(10, 2),
                PRIMARY KEY (trade_date, symbol, snapshot_time_utc)
            );
        """)

        # Migration helper: ensure all intraday columns exist if table was created previously
        table_info = active_conn.execute("PRAGMA table_info('options_history');").fetchall()
        existing_cols = {col[1] for col in table_info}
        migration_cols = [
            ("snapshot_time_utc", "TIMESTAMP DEFAULT '1970-01-01 00:00:00'"),
            ("bid", "NUMERIC(10, 2)"),
            ("ask", "NUMERIC(10, 2)"),
            ("iv", "NUMERIC(6, 4)"),
            ("delta", "NUMERIC(6, 4)"),
            ("gamma", "NUMERIC(8, 6)"),
            ("theta", "NUMERIC(10, 2)"),
            ("vega", "NUMERIC(10, 2)"),
        ]
        for col_name, col_type in migration_cols:
            if col_name not in existing_cols:
                active_conn.execute(f"ALTER TABLE options_history ADD COLUMN IF NOT EXISTS {col_name} {col_type};")

        active_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_options_history_underlying_expiry
                ON options_history(underlying, expiry_date, trade_date);
        """)

    def insert_options_df(self, df: pd.DataFrame) -> int:
        """Ingests a cleaned pandas DataFrame of options data into DuckDB.

        Args:
            df: DataFrame containing columns matching `options_history`.

        Returns:
            int: Number of rows inserted.
        """
        if df.empty:
            return 0
        conn = self.get_connection()
        insert_df = df.copy()
        if "snapshot_time_utc" not in insert_df.columns:
            insert_df["snapshot_time_utc"] = pd.Timestamp("1970-01-01 00:00:00")

        # Fetch valid target column names
        table_info = conn.execute("PRAGMA table_info('options_history');").fetchall()
        valid_cols = [c[1] for c in table_info]
        matching_cols = [c for c in insert_df.columns if c in valid_cols]

        col_str = ", ".join(matching_cols)
        conn.register("incoming_df", insert_df[matching_cols])
        conn.execute(f"""
            INSERT OR REPLACE INTO options_history ({col_str})
            SELECT {col_str} FROM incoming_df;
        """)
        conn.unregister("incoming_df")
        return len(insert_df)

    def get_table_count(self) -> int:
        """Returns the number of user tables present in the DuckDB file."""
        conn = self.get_connection()
        res = conn.execute("SHOW TABLES;").fetchall()
        return len(res)

    def get_row_count(self, table_name: str = "options_history") -> int:
        """Returns the total number of records in the specified table."""
        conn = self.get_connection()
        res = conn.execute(f"SELECT COUNT(*) FROM {table_name};").fetchone()
        return res[0] if res else 0

    def close(self) -> None:
        """Closes the active database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None


# Global local database instance
local_db = LocalDB()
