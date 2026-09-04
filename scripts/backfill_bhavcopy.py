"""
NSE Bhavcopy Backfill Utility for Swayam Capital.

Downloads official historical Bhavcopies from NSE and populates both
`options_history` and `nifty_daily_bars` in the local DuckDB database.

Usage:
    python scripts/backfill_bhavcopy.py --days 30
    python scripts/backfill_bhavcopy.py --from 2026-08-01 --to 2026-08-31
"""

from pathlib import Path
import sys

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.download_all_bhavcopy import main

if __name__ == "__main__":
    sys.exit(main())
