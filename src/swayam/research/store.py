"""Where downloaded history is kept, and how it is written safely.

One rule above all others: a download that is interrupted must never leave a
half-written file that looks complete. Every write here goes to a temporary file
in the same folder and is then moved into place, which is atomic on Windows and
on Linux. A killed process leaves the previous good file, or no file.

The second rule is that every file records where it came from. A Parquet file of
prices with no provenance is a liability in a project whose whole point is that
numbers are real or say `unavailable`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Optional

import pandas as pd

# Where the research history lives. Deliberately not `data/backups`, not the
# vault, and not the database.
DEFAULT_ROOT = Path("data") / "history"
MANIFEST_NAME = "manifest.json"


@dataclass
class ParquetWriteResult:
    """What a write actually did, so a caller can report it honestly."""

    path: Path
    rows: int
    rows_added: int
    bytes_on_disk: int


class HistoryStore:
    """Reads and writes the downloaded history as Parquet, with a manifest."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root) if root is not None else DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ paths

    def path_for(self, *parts: str) -> Path:
        path = self.root.joinpath(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    # ------------------------------------------------------------------ write

    def write_parquet(
        self,
        df: pd.DataFrame,
        *parts: str,
        dedupe_on: Optional[list[str]] = None,
        sort_on: Optional[list[str]] = None,
    ) -> ParquetWriteResult:
        """Merges `df` into the Parquet file at `parts`, atomically.

        Existing rows are kept; rows matching on `dedupe_on` are replaced by the
        incoming ones, so re-running a download repairs a partial fetch instead
        of duplicating it.
        """
        path = self.path_for(*parts)
        existing = pd.DataFrame()
        if path.exists():
            existing = pd.read_parquet(path)

        before = len(existing)
        combined = pd.concat([existing, df], ignore_index=True) if before else df.copy()
        if dedupe_on:
            combined = combined.drop_duplicates(subset=dedupe_on, keep="last")
        if sort_on:
            combined = combined.sort_values(sort_on).reset_index(drop=True)

        tmp = path.with_suffix(path.suffix + ".tmp")
        combined.to_parquet(tmp, index=False, engine="pyarrow", compression="snappy")
        os.replace(tmp, path)

        return ParquetWriteResult(
            path=path,
            rows=len(combined),
            rows_added=len(combined) - before,
            bytes_on_disk=path.stat().st_size,
        )

    # --------------------------------------------------------------- manifest

    def manifest_path(self, *parts: str) -> Path:
        return self.path_for(*parts, MANIFEST_NAME)

    def read_manifest(self, *parts: str) -> dict[str, Any]:
        path = self.manifest_path(*parts)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}

    def record(self, *parts: str, key: str, entry: dict[str, Any]) -> None:
        """Marks one unit of work done, so a resumed run can skip it.

        The manifest is what makes a multi-hour download restartable. It is
        written after the data, never before, so a crash between the two means
        the work is repeated rather than silently skipped.
        """
        manifest = self.read_manifest(*parts)
        manifest.setdefault("entries", {})[key] = {
            **entry,
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        manifest["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        path = self.manifest_path(*parts)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)

    def is_done(self, *parts: str, key: str) -> bool:
        return key in (self.read_manifest(*parts).get("entries") or {})
