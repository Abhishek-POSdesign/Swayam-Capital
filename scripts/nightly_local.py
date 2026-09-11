r"""The LOCAL half of the nightly backup. Runs on his PC at 03:00 IST.

WHY THERE ARE TWO HALVES, AND WHY THIS ONE RUNS AT 03:00
--------------------------------------------------------
The cloud half (Cloud Run job `swayam-nightly-backup`, Cloud Scheduler
`swayam-nightly-backup-schedule`) backs the database up to the bucket at
**02:00 IST**. It runs in Google's data centre so his record is protected
whether his PC is awake or not.

This half cannot run there. The vault is a local filesystem path
(`G:\My Drive\Second Brain`) and `data/history` is 631 MB sitting on his PC.
A data-centre job can reach neither.

**THE ONE-HOUR GAP IS DELIBERATE AND MUST NOT BE CLOSED.** This script copies
the NEWEST backup out of the bucket. If both halves started at 02:00 it would
race the cloud half and copy LAST night's file while reporting success. An hour
is ordering, not padding.

WHAT IT DOES
------------
1. Copies the newest database backup from the bucket into his vault, keeping
   the newest THIRTY and pruning the rest.
2. Syncs `data/history` to the bucket. **Only what changed** — compared by size
   and MD5. The first run uploads about 631 MB and should be started by hand;
   after that most nights upload nothing.
3. Rewrites section 7 of the Data Map, in the repo and in the vault, between
   the LIVE FIGURES markers and nowhere else.

Any figure it cannot read says `unavailable` with the reason. **No stale number
is ever left standing**, because that note is how he answers a future chat
about where his data lives.

Usage:
    .\.venv\Scripts\python.exe scripts/nightly_local.py
    .\.venv\Scripts\python.exe scripts/nightly_local.py --first-history-push
    .\.venv\Scripts\python.exe scripts/nightly_local.py --skip-history
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

logger = logging.getLogger("nightly_local")

BUCKET = "swayam-backups"
BACKUP_PREFIX = "supabase"
HISTORY_PREFIX = "history"
KEEP_IN_VAULT = 30
VAULT_SUBDIR = Path("02 - Projects") / "Trading" / "07 - Backups"
DATA_MAP_VAULT = Path("02 - Projects") / "Trading" / "06 - Platform Plan" / "Data Map.md"
DATA_MAP_REPO = Path("docs") / "DATA_MAP.md"
START_MARKER = "<!-- LIVE FIGURES:"
END_MARKER = "<!-- END LIVE FIGURES -->"

UNAVAILABLE = "unavailable"


def _cage() -> None:
    """The vault cage. Twenty-six fabricated notes reached his real journal on
    2026-09-08 because nothing stopped a test writing there. Nothing in this
    script writes to the vault while a test is running."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        raise RuntimeError(
            "BLOCKED: a test tried to run the nightly local task, which writes "
            "into his live vault. Tests must call the individual functions with "
            "an explicit temporary path."
        )


def _vault_root() -> Path:
    from swayam.config import settings
    return Path(settings.vault_path)


def _storage():
    from google.cloud import storage
    return storage.Client()


def _md5_b64(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return base64.b64encode(h.digest()).decode()


# --------------------------------------------------------------------------
# 1. The vault copy
# --------------------------------------------------------------------------

def copy_newest_backup_to_vault(vault_root: Optional[Path] = None) -> dict:
    """Copies the newest bucket backup into the vault, keeping the newest 30."""
    _cage()
    vault_root = vault_root or _vault_root()
    dest_root = vault_root / VAULT_SUBDIR
    dest_root.mkdir(parents=True, exist_ok=True)

    client = _storage()
    stamps = sorted({
        b.name.split("/")[1]
        for b in client.list_blobs(BUCKET, prefix=f"{BACKUP_PREFIX}/")
        if len(b.name.split("/")) > 2
    })
    if not stamps:
        raise RuntimeError(f"no backups found under gs://{BUCKET}/{BACKUP_PREFIX}/")

    newest = stamps[-1]
    target = dest_root / newest
    copied = 0
    if not target.exists():
        target.mkdir(parents=True, exist_ok=True)
        for blob in client.list_blobs(BUCKET, prefix=f"{BACKUP_PREFIX}/{newest}/"):
            name = blob.name.split("/")[-1]
            if name:
                blob.download_to_filename(str(target / name))
                copied += 1

    present = sorted(p for p in dest_root.iterdir() if p.is_dir())
    pruned = []
    for old in present[:-KEEP_IN_VAULT] if len(present) > KEEP_IN_VAULT else []:
        for f in old.iterdir():
            f.unlink()
        old.rmdir()
        pruned.append(old.name)

    logger.info("vault: newest=%s copied=%d files, kept=%d, pruned=%d",
                newest, copied, min(len(present), KEEP_IN_VAULT), len(pruned))
    return {"newest": newest, "copied": copied,
            "kept": min(len(present), KEEP_IN_VAULT), "pruned": pruned}


# --------------------------------------------------------------------------
# 2. The history sync
# --------------------------------------------------------------------------

def sync_history(root: Optional[Path] = None, dry_run: bool = False) -> dict:
    """Uploads only the files of data/history that changed. Compared by size
    then MD5, so an unchanged 631 MB history uploads nothing."""
    root = root or ROOT_DIR
    src = root / "data" / "history"
    if not src.exists():
        return {"skipped": f"nothing to sync: no folder at {src}",
                "uploaded": 0, "bytes": 0}

    client = _storage()
    bucket = client.bucket(BUCKET)
    remote = {
        b.name[len(HISTORY_PREFIX) + 1:]: b
        for b in client.list_blobs(BUCKET, prefix=f"{HISTORY_PREFIX}/")
    }

    uploaded = skipped = 0
    sent_bytes = 0
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = path.relative_to(src).as_posix()
        blob = remote.get(rel)
        if blob is not None and blob.size == path.stat().st_size:
            if blob.md5_hash and blob.md5_hash == _md5_b64(path):
                skipped += 1
                continue
        if not dry_run:
            bucket.blob(f"{HISTORY_PREFIX}/{rel}").upload_from_filename(str(path))
        uploaded += 1
        sent_bytes += path.stat().st_size

    logger.info("history: %d uploaded (%.1f MB), %d unchanged%s",
                uploaded, sent_bytes / 1048576, skipped, " [DRY RUN]" if dry_run else "")
    return {"uploaded": uploaded, "unchanged": skipped, "bytes": sent_bytes}


# --------------------------------------------------------------------------
# 3. The live figures in the Data Map
# --------------------------------------------------------------------------

def _gcloud_json(args: list[str]):
    """Runs gcloud and returns JSON. A failure names the command it ran, so the
    message says what was attempted rather than only that something failed."""
    p = subprocess.run(["gcloud"] + args, capture_output=True, text=True, shell=True)
    if p.returncode != 0:
        tail = (p.stderr or "no stderr").strip().splitlines()
        raise RuntimeError(
            f"`gcloud {' '.join(args[:4])}…` exited {p.returncode}: "
            f"{tail[-1][:110] if tail else 'no stderr'}"
        )
    return json.loads(p.stdout or "[]")


def gather_figures() -> dict[str, str]:
    """Every figure read live. A failure becomes `unavailable` WITH ITS REASON,
    never a stale number carried over from last night."""
    figures: dict[str, str] = {}

    # EVERY FAILURE NAMES WHAT IT READ AND WHERE IT LOOKED. `where` is required,
    # so this cannot be forgotten.
    #
    # WHY IT IS BUILT THIS WAY RATHER THAN LEFT TO CARE. On 2026-09-11 this
    # function reported "data/history not present on this machine". That is a
    # conclusion about his MACHINE drawn from looking in exactly ONE place, and
    # it was FALSE: the folder held 631 MB in his primary folder, and the task
    # had merely been run from a worktree. The wrong answer then reached the
    # Data Map in his vault, the note he hands to future chats, and said his
    # most vulnerable data was missing.
    #
    # A message that names the path it looked in cannot mislead like that, and
    # it would have shown the fault immediately. So no message here states
    # anything about the machine, the account or the world: only what was
    # sought, where, and what came back.
    def attempt(key: str, where: str, fn):
        try:
            figures[key] = fn()
        except Exception as exc:
            figures[key] = f"{UNAVAILABLE} — could not read {where}: {str(exc)[:120]}"

    def newest_backup() -> str:
        client = _storage()
        stamps = sorted({
            b.name.split("/")[1]
            for b in client.list_blobs(BUCKET, prefix=f"{BACKUP_PREFIX}/")
            if len(b.name.split("/")) > 2
        })
        if not stamps:
            raise RuntimeError(f"no backup folders found under gs://{BUCKET}/{BACKUP_PREFIX}/")
        newest = stamps[-1]
        man = client.bucket(BUCKET).blob(f"{BACKUP_PREFIX}/{newest}/MANIFEST.json")
        if not man.exists():
            return f"{newest} (MANIFEST.json missing)"
        m = json.loads(man.download_as_text())
        return (f"{newest}, {len(m.get('tables', {}))} tables, "
                f"{m.get('total_rows', '?')} rows")

    def older_backups() -> str:
        client = _storage()
        stamps = sorted({
            b.name.split("/")[1]
            for b in client.list_blobs(BUCKET, prefix=f"{BACKUP_PREFIX}/")
            if len(b.name.split("/")) > 2
        })
        return f"{max(0, len(stamps) - 1)}, oldest {stamps[0]}" if stamps else "none"

    def recorder_data() -> str:
        client = _storage()
        try:
            blobs = list(client.list_blobs("swayam-capital-options-data"))
        except Exception as exc:
            raise RuntimeError(
                f"gs://swayam-capital-options-data/ could not be listed: {exc}") from exc
        total = sum(b.size or 0 for b in blobs)
        days = {"/".join(b.name.split("/")[:3]) for b in blobs if b.name.count("/") >= 3}
        return f"{len(days)} trading days, {total / 1048576:.1f} MB total"

    def history_local() -> str:
        src = ROOT_DIR / "data" / "history"
        if not src.exists():
            # Names the path, never a claim about the machine. Run from a
            # worktree this folder is legitimately absent while 631 MB sits in
            # the primary folder, and saying otherwise put a falsehood in his
            # vault on 2026-09-11.
            raise RuntimeError(f"data/history not found at {src}")
        size = sum(p.stat().st_size for p in src.rglob("*") if p.is_file())
        return f"{size / 1048576:.0f} MB at {src}"

    def history_in_bucket() -> str:
        client = _storage()
        blobs = list(client.list_blobs(BUCKET, prefix=f"{HISTORY_PREFIX}/"))
        if not blobs:
            return f"nothing under gs://{BUCKET}/{HISTORY_PREFIX}/ yet"
        total = sum(b.size or 0 for b in blobs)
        return f"{len(blobs)} files, {total / 1048576:.0f} MB in gs://{BUCKET}/{HISTORY_PREFIX}/"

    def build_images() -> str:
        rows = _gcloud_json([
            "artifacts", "docker", "images", "list",
            "asia-southeast1-docker.pkg.dev/swayam-capital/swayam/dashboard",
            "--format=json(version)", "--limit=500", "--project=swayam-capital"])
        return str(len(rows))

    def live_versions() -> str:
        rows = _gcloud_json([
            "run", "revisions", "list", "--service=swayam-dashboard",
            "--region=asia-southeast1", "--project=swayam-capital",
            "--format=json(metadata.name)"])
        return str(len(rows))

    def open_trades() -> str:
        from swayam.db import SupabaseDB
        res = (SupabaseDB().client.table("swayam_positions")
               .select("id,status").eq("status", "open").execute())
        rows = res.data or []
        if not rows:
            return "none"
        ids = ", ".join(f"`{r['id'].split('-')[0]}`" for r in rows[:5])
        return f"{len(rows)}, {ids}"

    # `where` is a short label saying WHAT was being read. Each function's own
    # error carries WHERE it looked, so between them a failure always answers
    # both, once each, without repeating a long path twice in his Data Map.
    attempt("newest_backup", "the newest backup", newest_backup)
    attempt("older_backups", "the backup history", older_backups)
    attempt("recorder", "the recorder's bucket", recorder_data)
    attempt("history_local", "the local backtest history", history_local)
    attempt("history_bucket", "the history copy in the bucket", history_in_bucket)
    attempt("images", "the build images", build_images)
    attempt("versions", "the live site versions", live_versions)
    attempt("open_trades", "the open trades", open_trades)
    return figures


def render_block(figures: dict[str, str]) -> str:
    stamp = datetime.now(timezone.utc).astimezone().strftime("%d %B %Y, %H:%M %Z")
    return "\n".join([
        "",
        "## 7. LIVE FIGURES",
        "",
        f"Refreshed automatically by `scripts/nightly_local.py` on **{stamp}**.",
        "Anything it could not read says so, with the reason. No stale number is",
        "left standing here.",
        "",
        "| | |",
        "|---|---|",
        f"| Newest backup of my record | {figures.get('newest_backup', UNAVAILABLE)} |",
        f"| Older backups kept | {figures.get('older_backups', UNAVAILABLE)} |",
        f"| Recorder data | {figures.get('recorder', UNAVAILABLE)} |",
        f"| Backtest history on my PC | {figures.get('history_local', UNAVAILABLE)} |",
        f"| Backtest history copied to the bucket | {figures.get('history_bucket', UNAVAILABLE)} |",
        f"| Build images | {figures.get('images', UNAVAILABLE)} |",
        f"| Live site versions | {figures.get('versions', UNAVAILABLE)} |",
        f"| Open trades | {figures.get('open_trades', UNAVAILABLE)} |",
        "",
    ])


def rewrite_data_map(path: Path, block: str) -> bool:
    """Replaces ONLY what sits between the markers. Never touches a line above
    the opening marker. Returns False and changes nothing if either marker is
    missing, because a half-recognised file is not one to rewrite."""
    if not path.exists():
        logger.warning("data map not found: %s", path)
        return False
    text = path.read_text(encoding="utf-8")
    start = text.find(START_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        logger.warning("markers missing or out of order in %s; left untouched", path)
        return False
    open_close = text.find("-->", start)
    if open_close == -1 or open_close > end:
        logger.warning("opening marker unterminated in %s; left untouched", path)
        return False
    new = text[: open_close + 3] + "\n" + block + "\n" + text[end:]
    path.write_text(new, encoding="utf-8")
    logger.info("data map refreshed: %s", path)
    return True


# --------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-history", action="store_true",
                    help="skip the history sync (it is the slow part)")
    ap.add_argument("--first-history-push", action="store_true",
                    help="acknowledge the first ~631 MB upload and do it")
    ap.add_argument("--dry-run-history", action="store_true")
    args = ap.parse_args(argv)

    _cage()
    failures = []

    try:
        copy_newest_backup_to_vault()
    except Exception as exc:
        failures.append(f"vault copy: {exc}")
        logger.error("vault copy FAILED: %s", exc)

    if not args.skip_history:
        try:
            client = _storage()
            already = any(client.list_blobs(BUCKET, prefix=f"{HISTORY_PREFIX}/",
                                            max_results=1))
            if not already and not args.first_history_push and not args.dry_run_history:
                logger.warning(
                    "history: NOT copied. The first upload is about 631 MB and is "
                    "deliberately a one-off you start yourself, so it never competes "
                    "with your connection while you are working. Run:\n"
                    "    .\\.venv\\Scripts\\python.exe scripts/nightly_local.py --first-history-push")
            else:
                sync_history(dry_run=args.dry_run_history)
        except Exception as exc:
            failures.append(f"history sync: {exc}")
            logger.error("history sync FAILED: %s", exc)

    figures = gather_figures()
    block = render_block(figures)
    rewrite_data_map(ROOT_DIR / DATA_MAP_REPO, block)
    try:
        rewrite_data_map(_vault_root() / DATA_MAP_VAULT, block)
    except Exception as exc:
        failures.append(f"vault data map: {exc}")
        logger.error("vault data map FAILED: %s", exc)

    unread = [k for k, v in figures.items() if str(v).startswith(UNAVAILABLE)]
    if unread:
        logger.warning("figures that could not be read: %s", ", ".join(unread))
    if failures:
        logger.error("FINISHED WITH %d FAILURE(S): %s", len(failures), "; ".join(failures))
        return 1
    logger.info("nightly local task finished cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
