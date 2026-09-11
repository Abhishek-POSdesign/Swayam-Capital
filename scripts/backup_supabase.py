r"""Full logical backup of every swayam_* table in Supabase.

This is a thin wrapper. **The logic lives in `swayam.services.record_backup`**,
so that exactly one implementation exists and the same code runs whether the
backup is taken from his PC or from the nightly Cloud Run job. Before
2026-09-11 the logic lived here and could only run on his PC, because it shelled
out to the `gcloud` command line, which is not in the Cloud Run image.

Nothing about the behaviour changed: the same 19 tables, the same stable sort,
the same MANIFEST.json with per-table row counts and SHA-256, the same refusal
to write a schema-less backup, and the same proof that every object landed in
the bucket before reporting success.

Writes, under data/backups/<UTC timestamp>/:
  - <table>.json         one file per table, rows sorted for a stable checksum
  - schema.sql           the DDL captured at baseline
  - MANIFEST.json        row count + SHA-256 for every file, plus totals

A failed upload fails the job. A table that cannot be read fails the job.
There is no "best effort" here on purpose: a backup that reports success
without writing bytes is worse than no backup.

Usage:
    .\.venv\Scripts\python.exe scripts/backup_supabase.py
    .\.venv\Scripts\python.exe scripts/backup_supabase.py --gcs
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from swayam.services.record_backup import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
