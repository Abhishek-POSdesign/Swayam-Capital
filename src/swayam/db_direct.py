"""
Direct Postgres connection to Supabase.

Until now the project had no database connection at all. That is why
scripts/apply_migration.py could only print SQL and ask a human to paste it
into the Supabase web editor, why there was no version table, and why nobody
could state which migrations were applied.

The connection string lives in SUPABASE_DB_URL in .env and never in the
repository. It is required only by the migration runner and the backup and
restore tooling. The web application does not use it and must not: the
application talks to Supabase over the REST API as it always has.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import quote, urlsplit, urlunsplit


class DatabaseUrlError(RuntimeError):
    """Raised when SUPABASE_DB_URL is absent or unusable."""


def normalise_db_url(raw: str) -> str:
    """Returns a connection URL safe to hand to libpq.

    A Supabase password is generated for the user and routinely contains
    characters that are special inside a URL, '@' above all. Pasted verbatim
    the string is ambiguous, and the failure is a confusing host-not-found
    error rather than an obvious one. Splitting the user information on the
    LAST '@' and percent-encoding it removes the ambiguity, so the string in
    .env can stay exactly as Supabase handed it over.
    """
    raw = raw.strip().strip("'\"")
    if "://" not in raw:
        raise DatabaseUrlError("SUPABASE_DB_URL is not a connection URL")

    scheme, _, rest = raw.partition("://")
    if "@" not in rest:
        raise DatabaseUrlError("SUPABASE_DB_URL has no user information")

    userinfo, _, hostpart = rest.rpartition("@")
    user, sep, password = userinfo.partition(":")
    safe_user = quote(user, safe="")
    encoded = f"{safe_user}:{quote(password, safe='')}" if sep else safe_user

    parts = urlsplit(f"{scheme}://{encoded}@{hostpart}")
    if not parts.hostname:
        raise DatabaseUrlError("SUPABASE_DB_URL has no host")
    return urlunsplit(parts)


def get_db_url() -> str:
    raw = os.getenv("SUPABASE_DB_URL", "")
    if not raw:
        raise DatabaseUrlError(
            "SUPABASE_DB_URL is not set. Add the Supabase connection string "
            "to .env. It is needed by the migration runner only."
        )
    return normalise_db_url(raw)


def describe_target() -> str:
    """Host and database only. Never the password, not even in a log line."""
    parts = urlsplit(get_db_url())
    return f"{parts.hostname}:{parts.port or 5432}{parts.path}"


@contextmanager
def connect(*, autocommit: bool = False) -> Iterator["psycopg.Connection"]:  # noqa: F821
    """Opens one connection. Rolls back on any exception."""
    import psycopg

    conn = psycopg.connect(get_db_url(), autocommit=autocommit, connect_timeout=15)
    try:
        yield conn
        if not autocommit:
            conn.commit()
    except Exception:
        if not autocommit:
            conn.rollback()
        raise
    finally:
        conn.close()
