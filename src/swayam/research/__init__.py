"""The research data layer: history downloaded for backtesting.

Deliberately separate from everything the live terminal reads. Nothing in here
touches `swayam_positions`, the journal, or any table the trading desk uses. It
downloads and stores history, and that is all it does.

Why files rather than the database
----------------------------------
His Supabase project is on the free tier and shared with two other apps. The
minute-level history runs to gigabytes, so it lives as Parquet files that DuckDB
reads directly, in `data/history/`. Only small, summarised tables would ever go
to Postgres, and none exist yet.
"""

from swayam.research.store import (
    HistoryStore,
    ParquetWriteResult,
)

__all__ = ["HistoryStore", "ParquetWriteResult"]
