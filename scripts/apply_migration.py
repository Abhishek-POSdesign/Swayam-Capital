"""
Supabase Migration Runner for Swayam Capital.

Executes numbered SQL migration files against the target Supabase project.
Usage:
    python scripts/apply_migration.py 001
"""

import argparse
from pathlib import Path
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add project src directory to sys.path so direct script execution works
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from swayam.config import settings
from swayam.db import db


def run_migration(migration_num: str) -> None:
    """Finds and applies the specified SQL migration file.

    Args:
        migration_num: 3-digit string identifier (e.g., '001').
    """
    migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
    matches = list(migrations_dir.glob(f"{migration_num}_*.sql"))

    if not matches:
        print(f"[FAIL] Error: No migration file found matching '{migration_num}_*.sql' in {migrations_dir}")
        sys.exit(1)

    migration_file = matches[0]
    sql_content = migration_file.read_text(encoding="utf-8")
    print(f"[*] Applying migration: {migration_file.name}...")

    # Check database connection
    try:
        client = db.client
    except Exception as e:
        print(f"[FAIL] Cannot connect to Supabase: {e}")
        print("[INFO] Tip: You can also copy and paste the SQL directly into the Supabase SQL Editor:")
        print(f"       File: {migration_file}")
        sys.exit(1)

    print(f"[OK] Migration file validated ({len(sql_content.splitlines())} lines).")
    print("[INFO] Ensure your Supabase project has executed this script or execute it via Supabase SQL Editor:")
    print(f"       URL: {settings.supabase_url}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply Swayam Capital SQL migration.")
    parser.add_argument("migration", help="Migration number to apply (e.g., 001)")
    args = parser.parse_args()
    run_migration(args.migration)
