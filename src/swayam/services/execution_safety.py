"""
Two guarantees for a paper trade: it is recorded exactly once, and a journal
note can never fail it.

Plan v9 Step 5. Release 1 did not ship it.

WHY IDEMPOTENCY
---------------
There was no key, no unique constraint and no in-flight guard, so a double
click created two positions. That matters most exactly when something else has
gone wrong, because that is when he clicks again. The browser makes a key,
keeps it in local storage, and reuses it on every retry until it gets a final
answer. The database primary key is the control; a disabled button is only a
convenience.

WHY AN OUTBOX
-------------
The live site cannot reach the vault at all. `VAULT_PATH` is unset on Cloud
Run, so `config.py` falls back to `G:\\My Drive\\Second Brain`, a Windows path
on his own PC that a Linux container in Singapore has no route to. Today every
live-site trade inserts the position, fails the note, and returns HTTP 500 on a
trade that actually happened.

A note is not a trade. When the vault is unreachable the note becomes a row in
`swayam_journal_outbox`, the position is marked `journal_status = 'pending'`,
and the trade succeeds. A drainer writes it later. Nothing is lost and nothing
is hidden.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from swayam.db import db

logger = logging.getLogger(__name__)

ATTEMPTS_TABLE = "swayam_execution_attempts"
OUTBOX_TABLE = "swayam_journal_outbox"


class DuplicateExecution(Exception):
    """The same idempotency key arrived again with a different trade."""


class ReplayedExecution(Exception):
    """The same key and the same trade arrived again. Carries the first answer.

    Not an error. It is the correct response to a retry, and the caller should
    return the stored result rather than opening a second position.
    """

    def __init__(self, response: dict[str, Any]) -> None:
        super().__init__("Replayed a completed execution attempt.")
        self.response = response


def canonical_payload_hash(payload: dict[str, Any]) -> str:
    """A stable fingerprint of the trade being requested.

    Sorted keys and separators with no whitespace, so the same trade always
    hashes the same regardless of how the browser happened to order the JSON.
    The idempotency key itself is excluded: the question this answers is
    "is this the same trade?", not "is this the same request envelope?".
    """
    trimmed = {k: v for k, v in payload.items() if k != "idempotency_key"}
    encoded = json.dumps(trimmed, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def claim_execution(idempotency_key: str, payload: dict[str, Any]) -> None:
    """Claims the key before any position is written.

    Raises:
        ReplayedExecution: same key, same trade, already finished. Return its
            stored response.
        DuplicateExecution: same key, different trade, or a request that is
            still in flight.
    """
    payload_hash = canonical_payload_hash(payload)
    client = db.client

    existing = (
        client.table(ATTEMPTS_TABLE)
        .select("idempotency_key,payload_hash,outcome,response,position_id")
        .eq("idempotency_key", idempotency_key)
        .execute()
    )
    rows = existing.data or []

    if rows:
        row = rows[0]
        if row.get("payload_hash") != payload_hash:
            raise DuplicateExecution(
                "This execution key has already been used for a different trade. "
                "Reload the ticket so a fresh key is generated."
            )
        if row.get("outcome") == "succeeded" and row.get("response"):
            raise ReplayedExecution(row["response"])
        if row.get("outcome") == "in_flight":
            raise DuplicateExecution(
                "This trade is already being recorded. Wait for it to finish "
                "rather than sending it again."
            )
        # A previous attempt failed. Let this one try again under the same key.
        client.table(ATTEMPTS_TABLE).update(
            {"outcome": "in_flight", "response": None, "completed_at": None}
        ).eq("idempotency_key", idempotency_key).execute()
        return

    # The insert is the claim. A concurrent duplicate loses on the primary key.
    try:
        client.table(ATTEMPTS_TABLE).insert(
            {
                "idempotency_key": idempotency_key,
                "payload_hash": payload_hash,
                "outcome": "in_flight",
            }
        ).execute()
    except Exception as exc:  # the other request got there first
        raise DuplicateExecution(
            "This trade is already being recorded. Wait for it to finish "
            "rather than sending it again."
        ) from exc


def complete_execution(
    idempotency_key: str, position_id: str, response: dict[str, Any]
) -> None:
    """Stores the answer so a retry replays it instead of trading twice."""
    try:
        db.client.table(ATTEMPTS_TABLE).update(
            {
                "outcome": "succeeded",
                "position_id": position_id,
                "response": response,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("idempotency_key", idempotency_key).execute()
    except Exception as exc:
        # The trade is real and recorded. Failing to note that here would be a
        # worse outcome than a retry creating a second row, so log and continue.
        logger.warning("Could not mark execution attempt %s complete: %s", idempotency_key, exc)


def abandon_execution(idempotency_key: str, error: str) -> None:
    """Releases the key after a failure so he can genuinely retry."""
    try:
        db.client.table(ATTEMPTS_TABLE).update(
            {
                "outcome": "failed",
                "response": {"error": error[:2000]},
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("idempotency_key", idempotency_key).execute()
    except Exception as exc:
        logger.warning("Could not mark execution attempt %s failed: %s", idempotency_key, exc)


def queue_journal_note(
    position_id: str, payload: dict[str, Any], kind: str = "new_trade",
    error: Optional[str] = None,
) -> bool:
    """Parks a journal note that could not be written, and says whether it parked.

    Returns False when even the queue write failed, which the caller should
    surface as a warning on the trade rather than as a failure of the trade.
    """
    try:
        db.client.table(OUTBOX_TABLE).insert(
            {
                "position_id": position_id,
                "kind": kind,
                "payload": payload,
                "status": "pending",
                "last_error": (error or "")[:2000] or None,
            }
        ).execute()
        return True
    except Exception as exc:
        logger.error("Could not queue journal note for position %s: %s", position_id, exc)
        return False


def mark_journal_status(position_id: str, status: str) -> None:
    """Records on the position itself whether its note reached the vault."""
    try:
        db.client.table("swayam_positions").update({"journal_status": status}).eq(
            "id", position_id
        ).execute()
    except Exception as exc:
        logger.warning("Could not set journal_status=%s on %s: %s", status, position_id, exc)
