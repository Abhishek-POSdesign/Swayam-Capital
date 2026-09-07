"""
The guard that stops the test suite writing into Abhishek's live record.

WHY THIS EXISTS
---------------
There is no staging Supabase project. The free tier allows two projects per
account and both are already used, so every test runs against the live project
`wxijlrwoiaeaupaaqecc`, which also carries the Biz Research Hub and the B.tech
Learning Hub.

Plan v9's unlock gate, condition 5, requires the duplicate-submission test to
run "in staging, never in production". That instruction cannot be obeyed as
written, so the guard moves from policy into code.

It has already failed twice in practice:

  * 2026-09-07, during the Release 1 build: twelve position rows created by test
    runs, three of them named "Violating Spread".
  * 2026-09-07 at 19:07, four minutes after migration 017 quarantined the first
    79 rows: two more rows, "Violating Spread" and "Paper Bear Put", this time
    carrying `provenance = 'live'` so they were indistinguishable from his own
    trades.

`conftest.py` already pins capital so tests never call the live broker. This is
the same idea for the database, and it is deliberately stricter: reads behave
exactly as they did before, and any write raises.

HOW IT BEHAVES
--------------
Default, every test:      reads pass through to the live project, writes raise.
`@pytest.mark.fake_db`:   fully in-memory. Writes are accepted and recorded, so
                          a test can exercise a real write path and then assert
                          on what would have been written.
`@pytest.mark.live_db`:   the unguarded client. Nothing in the suite should use
                          this. It exists so that a deliberate, reviewed
                          exception is visible in the diff rather than achieved
                          by quietly deleting the guard.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional


WRITE_VERBS = ("insert", "update", "upsert", "delete")


class WriteToLiveDatabaseError(AssertionError):
    """Raised when a test tries to write to the live Supabase project.

    Subclasses AssertionError so it reads as a test failure rather than an
    infrastructure error, and so a bare `except Exception` in application code
    cannot quietly swallow it into a passing test.
    """


def _blocked(table: str, verb: str) -> "WriteToLiveDatabaseError":
    return WriteToLiveDatabaseError(
        f"\n"
        f"BLOCKED: this test tried to {verb.upper()} into '{table}' on the LIVE database.\n"
        f"\n"
        f"There is no staging project, so a write here lands in Abhishek's real\n"
        f"trading record. This has already polluted it twice.\n"
        f"\n"
        f"If this test is meant to exercise a write path, mark it:\n"
        f"    @pytest.mark.fake_db\n"
        f"and it will run against an in-memory database instead.\n"
    )


# --------------------------------------------------------------------------
# Default: reads pass through, writes raise.
# --------------------------------------------------------------------------

class _GuardedTable:
    """Delegates reads to the real table handle and refuses every write."""

    def __init__(self, real_table_factory, name: str) -> None:
        self._real_table_factory = real_table_factory
        self._name = name

    def insert(self, *args: Any, **kwargs: Any):
        raise _blocked(self._name, "insert")

    def update(self, *args: Any, **kwargs: Any):
        raise _blocked(self._name, "update")

    def upsert(self, *args: Any, **kwargs: Any):
        raise _blocked(self._name, "upsert")

    def delete(self, *args: Any, **kwargs: Any):
        raise _blocked(self._name, "delete")

    def select(self, *args: Any, **kwargs: Any):
        return self._real_table_factory(self._name).select(*args, **kwargs)

    def __getattr__(self, item: str) -> Any:
        # Anything not named above is a read-shaped helper; delegate it.
        if item in WRITE_VERBS:
            raise _blocked(self._name, item)
        return getattr(self._real_table_factory(self._name), item)


class GuardedClient:
    """A Supabase client whose writes raise and whose reads are untouched.

    The real client is built lazily, so a test that never touches the database
    never needs credentials, exactly as before this guard existed.
    """

    def __init__(self, real_client_factory) -> None:
        self._real_client_factory = real_client_factory
        self._real: Any = None

    def _real_client(self) -> Any:
        if self._real is None:
            self._real = self._real_client_factory()
        return self._real

    def table(self, name: str) -> _GuardedTable:
        return _GuardedTable(lambda n: self._real_client().table(n), name)

    def rpc(self, *args: Any, **kwargs: Any) -> Any:
        # A stored procedure can write, and we cannot tell from here whether it
        # does. Refuse it rather than guess.
        raise WriteToLiveDatabaseError(
            "BLOCKED: rpc() is not permitted in tests, because a stored "
            "procedure may write. Mark the test @pytest.mark.fake_db."
        )

    def __getattr__(self, item: str) -> Any:
        return getattr(self._real_client(), item)


# --------------------------------------------------------------------------
# @pytest.mark.fake_db: an in-memory stand-in.
# --------------------------------------------------------------------------

class _Result:
    """Mimics the shape application code reads: `response.data`."""

    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data
        self.count = len(data)


class _FakeQuery:
    """A chainable query that filters an in-memory list on `.execute()`."""

    def __init__(self, store: "FakeClient", table: str, op: str,
                 payload: Any = None) -> None:
        self._store = store
        self._table = table
        self._op = op
        self._payload = payload
        self._filters: list[tuple[str, str, Any]] = []
        self._limit: Optional[int] = None
        self._single = False

    # -- filters, all chainable ------------------------------------------
    def eq(self, column: str, value: Any) -> "_FakeQuery":
        self._filters.append((column, "eq", value))
        return self

    def neq(self, column: str, value: Any) -> "_FakeQuery":
        self._filters.append((column, "neq", value))
        return self

    def in_(self, column: str, values: Iterable[Any]) -> "_FakeQuery":
        self._filters.append((column, "in", list(values)))
        return self

    def gte(self, column: str, value: Any) -> "_FakeQuery":
        self._filters.append((column, "gte", value))
        return self

    def lte(self, column: str, value: Any) -> "_FakeQuery":
        self._filters.append((column, "lte", value))
        return self

    def order(self, *args: Any, **kwargs: Any) -> "_FakeQuery":
        return self

    def limit(self, n: int) -> "_FakeQuery":
        self._limit = n
        return self

    def range(self, *args: Any, **kwargs: Any) -> "_FakeQuery":
        return self

    def single(self) -> "_FakeQuery":
        self._single = True
        return self

    def maybe_single(self) -> "_FakeQuery":
        self._single = True
        return self

    # -- terminal ---------------------------------------------------------
    def _matches(self, row: dict[str, Any]) -> bool:
        for column, op, value in self._filters:
            actual = row.get(column)
            if op == "eq" and actual != value:
                return False
            if op == "neq" and actual == value:
                return False
            if op == "in" and actual not in value:
                return False
            if op == "gte" and (actual is None or actual < value):
                return False
            if op == "lte" and (actual is None or actual > value):
                return False
        return True

    def execute(self) -> _Result:
        rows = self._store.rows.setdefault(self._table, [])

        if self._op == "select":
            hits = [r for r in rows if self._matches(r)]
            if self._limit is not None:
                hits = hits[: self._limit]
            if self._single:
                hits = hits[:1]
            return _Result([dict(r) for r in hits])

        if self._op in ("insert", "upsert"):
            written = self._payload if isinstance(self._payload, list) else [self._payload]
            for row in written:
                rows.append(dict(row))
            self._store.writes.append((self._table, self._op, written))
            return _Result([dict(r) for r in written])

        if self._op == "update":
            changed = []
            for row in rows:
                if self._matches(row):
                    row.update(self._payload or {})
                    changed.append(dict(row))
            self._store.writes.append((self._table, "update", changed))
            return _Result(changed)

        if self._op == "delete":
            keep, removed = [], []
            for row in rows:
                (removed if self._matches(row) else keep).append(row)
            self._store.rows[self._table] = keep
            self._store.writes.append((self._table, "delete", removed))
            return _Result([dict(r) for r in removed])

        return _Result([])


class _FakeTable:
    def __init__(self, store: "FakeClient", name: str) -> None:
        self._store = store
        self._name = name

    def select(self, *args: Any, **kwargs: Any) -> _FakeQuery:
        return _FakeQuery(self._store, self._name, "select")

    def insert(self, payload: Any, *args: Any, **kwargs: Any) -> _FakeQuery:
        return _FakeQuery(self._store, self._name, "insert", payload)

    def upsert(self, payload: Any, *args: Any, **kwargs: Any) -> _FakeQuery:
        return _FakeQuery(self._store, self._name, "upsert", payload)

    def update(self, payload: Any, *args: Any, **kwargs: Any) -> _FakeQuery:
        return _FakeQuery(self._store, self._name, "update", payload)

    def delete(self, *args: Any, **kwargs: Any) -> _FakeQuery:
        return _FakeQuery(self._store, self._name, "delete")


class FakeClient:
    """An in-memory Supabase stand-in.

    `rows` is the data. `writes` is an ordered log of every write attempted,
    so a test can assert that exactly one position was recorded without any
    row ever leaving the process.
    """

    def __init__(self, seed: Optional[dict[str, list[dict[str, Any]]]] = None) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = {
            k: [dict(r) for r in v] for k, v in (seed or {}).items()
        }
        self.writes: list[tuple[str, str, Any]] = []

    def table(self, name: str) -> _FakeTable:
        return _FakeTable(self, name)

    def rpc(self, *args: Any, **kwargs: Any) -> _Result:
        return _Result([])

    def inserted_into(self, table: str) -> list[dict[str, Any]]:
        """Every row inserted into `table` during this test."""
        out: list[dict[str, Any]] = []
        for name, op, payload in self.writes:
            if name == table and op in ("insert", "upsert"):
                out.extend(payload)
        return out
