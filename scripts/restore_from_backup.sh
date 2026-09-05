#!/usr/bin/env bash
# Swayam Capital — One-shot Database Restore Script (BUILD-11.12)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================="
echo " Swayam Capital Database Restore Procedure"
echo "============================================="

if [ -f "$REPO_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$REPO_DIR/.venv/bin/python"
elif [ -f "$REPO_DIR/.venv/Scripts/python.exe" ]; then
    PYTHON_BIN="$REPO_DIR/.venv/Scripts/python.exe"
else
    PYTHON_BIN="python3"
fi

"$PYTHON_BIN" "$SCRIPT_DIR/restore_from_backup.py" "$@"
