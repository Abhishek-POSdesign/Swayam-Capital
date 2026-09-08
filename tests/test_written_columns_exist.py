"""Every column the trade path writes must be created by a migration.

WHY THIS EXISTS
---------------
On 2026-09-09, closing a trade was found to write `closed_at` and
`journal_path` to `swayam_positions`. Neither column existed. Nobody noticed
because nobody had ever closed a trade, and the two cages this project already
has do not cover it: `db_guard` stops a test writing the wrong DATA, and the
vault cage stops it writing the wrong FILE. Neither catches writing to a column
that is not there.

The failure was not cosmetic. The result row was inserted first, so the close
recorded the trade and THEN failed, leaving the position open. A second press
wrote a second result and double counted it in his record.

This test reads the source for the column names it writes and the migrations
for the column names that exist, and compares them. It is offline and
deterministic: it needs neither the database nor the network.
"""

import ast
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"

# The modules that write to his record. Add one here when a new writer appears.
WRITERS = [
    ROOT / "src" / "swayam" / "api" / "routes" / "positions.py",
    ROOT / "src" / "swayam" / "api" / "routes" / "execution.py",
    ROOT / "src" / "swayam" / "services" / "execution_safety.py",
]

# Keys a payload may carry that are not columns: filters, and the primary key
# supplied on insert.
NOT_A_COLUMN: dict[str, set[str]] = {}


def _columns_from_migrations() -> dict[str, set[str]]:
    """Every column each swayam_* table has, according to the migration files."""
    columns: dict[str, set[str]] = {}
    create_re = re.compile(
        r"CREATE TABLE (?:IF NOT EXISTS )?(?:public\.)?(\w+)\s*\((.*?)\n\)\s*;",
        re.DOTALL | re.IGNORECASE,
    )
    add_re = re.compile(
        r"ALTER TABLE\s+(?:public\.)?(\w+)\s+ADD COLUMN (?:IF NOT EXISTS )?(\w+)",
        re.DOTALL | re.IGNORECASE,
    )

    for sql_file in sorted(MIGRATIONS.glob("*.sql")):
        text = sql_file.read_text(encoding="utf-8")

        for table, body in create_re.findall(text):
            cols = columns.setdefault(table, set())
            for line in body.splitlines():
                line = line.strip().strip(",")
                if not line or line.startswith("--"):
                    continue
                first = line.split()[0].lower()
                if first in {
                    "constraint", "primary", "unique", "foreign", "check", "exclude",
                }:
                    continue
                cols.add(line.split()[0])

        for table, col in add_re.findall(text):
            columns.setdefault(table, set()).add(col)

    return columns


def _written_columns() -> dict[str, set[tuple[str, str]]]:
    """Column names each swayam_* table is written with, and by which file.

    Handles both a dict literal passed straight to insert/update and one bound
    to a name first, which is how every payload in these modules is built.
    """
    written: dict[str, set[tuple[str, str]]] = {}

    for path in WRITERS:
        tree = ast.parse(path.read_text(encoding="utf-8"))

        literals: dict[str, list[str]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
                keys = [
                    k.value for k in node.value.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)
                ]
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        literals[target.id] = keys

        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr not in {"insert", "update"} or not node.args:
                continue

            table = _table_of(node.func.value)
            if not table or not table.startswith("swayam_"):
                continue

            arg = node.args[0]
            if isinstance(arg, ast.Dict):
                keys = [
                    k.value for k in arg.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)
                ]
            elif isinstance(arg, ast.Name):
                keys = literals.get(arg.id, [])
            else:
                keys = []

            for key in keys:
                written.setdefault(table, set()).add((key, path.name))

    return written


def _table_of(node: ast.AST) -> str | None:
    """The literal table name in a `.table("name")` anywhere up the chain."""
    while isinstance(node, (ast.Call, ast.Attribute)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "table"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            return node.args[0].value
        node = node.func.value if isinstance(node, ast.Call) else node.value
    return None


def test_the_trade_path_never_writes_a_column_that_does_not_exist():
    schema = _columns_from_migrations()
    written = _written_columns()

    assert written, "found no writes at all; the scanner is broken, not the code"

    problems = []
    for table, entries in sorted(written.items()):
        known = schema.get(table)
        if known is None:
            problems.append(f"{table}: no migration creates this table")
            continue
        for column, source in sorted(entries):
            if column in NOT_A_COLUMN.get(table, set()):
                continue
            if column not in known:
                problems.append(f"{table}.{column} written by {source}, created by no migration")

    assert not problems, (
        "These writes would be rejected by the database:\n  "
        + "\n  ".join(problems)
        + "\n\nThis is how his first close was going to fail on 2026-09-09."
    )


def test_the_scanner_actually_sees_the_close_payload():
    """A guard on the guard. If the scanner silently stops finding writes,
    the test above passes for the wrong reason."""
    written = _written_columns()

    positions = {c for c, _ in written.get("swayam_positions", set())}
    assert {"status", "closed_at", "journal_path"} <= positions

    history = {c for c, _ in written.get("swayam_trade_history", set())}
    assert {"position_id", "realized_pnl_inr", "total_charges_inr"} <= history
