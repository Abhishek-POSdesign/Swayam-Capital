"""
BUILD_07. THE SAVED DAILY SUMMARY, AND DELETING A CONVERSATION.

The two rules these tests exist to hold:

1. ONE ROW A TRADING DAY. He is paying for each summary and wants the record.
   Regenerating REPLACES that day's row rather than adding another copy, and
   the daily cap is counted from that row rather than from a row count, which
   would otherwise have silently become a cap of one.

2. DELETING A CONVERSATION TAKES ITS IMAGES WITH IT, and takes nothing else.
   The notebook and the pinned decisions survive by foreign key. Only the one
   conversation goes; there is no delete-everything anywhere.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from swayam.api.routes.ai import ATTACHMENT_BUCKET, delete_conversation
from swayam.services.so_far_today import (
    GROUNDED_MODEL,
    SUMMARY_TABLE,
    generate_so_far_today,
)

MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "026_daily_summary.sql"


# --------------------------------------------------------------- the migration

def test_the_day_is_the_key_so_a_day_can_only_have_one_summary():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS public.swayam_daily_summary" in sql
    assert "day              date        PRIMARY KEY" in sql
    # The column the cap reads. Without it the cap becomes one a day.
    assert "generation_count integer     NOT NULL DEFAULT 1" in sql


def test_the_backfill_takes_the_newest_of_each_day_and_deletes_nothing():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "ROW_NUMBER() OVER (" in sql
    assert "ORDER BY generated_at DESC" in sql
    assert "WHERE newest_first = 1" in sql
    assert "ON CONFLICT (day) DO NOTHING" in sql
    # Nothing may be removed from the table it reads.
    assert "DELETE FROM" not in sql.upper()
    assert "DROP TABLE" not in sql.upper()


def test_backfilled_rows_do_not_borrow_a_model_they_never_recorded():
    """His first rule. A figure is real or it says so; it is never inferred."""
    sql = MIGRATION.read_text(encoding="utf-8")
    insert = sql[sql.index("INSERT INTO public.swayam_daily_summary"):]
    select = insert[insert.index("SELECT"):insert.index("FROM src")]
    # The model column's value in the backfill SELECT is a literal NULL.
    assert "\n    NULL,\n" in select


# ------------------------------------------------------- one row a trading day

def _fake_db_with_day_row(row):
    db = MagicMock()
    chain = db.client.table.return_value.select.return_value.eq.return_value.limit.return_value
    chain.execute.return_value.data = [row] if row else []
    return db


def _grounded(text="NIFTY did a thing."):
    return {
        "text": text,
        "sources": [{"title": "A source", "url": "https://example.test"}],
        "search_queries": ["nifty today"],
        "tokens_used": 1234,
    }


def test_regenerating_replaces_the_day_rather_than_adding_a_copy():
    db = _fake_db_with_day_row({
        "day": date.today().isoformat(),
        "text": "the earlier one",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_count": 1,
    })

    with patch("swayam.services.so_far_today.generate_grounded_content", return_value=_grounded()):
        out = generate_so_far_today(force=True, db=db)

    summary_writes = [
        c for c in db.client.table.call_args_list if c.args and c.args[0] == SUMMARY_TABLE
    ]
    assert summary_writes, "the summary table was never written to"

    # An upsert keyed on the day, never a plain insert.
    assert db.client.table.return_value.upsert.called
    row, = db.client.table.return_value.upsert.call_args.args
    assert db.client.table.return_value.upsert.call_args.kwargs["on_conflict"] == "day"
    assert row["day"] == date.today().isoformat()
    assert row["generation_count"] == 2, "the second press of the day must count as two"
    assert row["model"] == GROUNDED_MODEL, "a row written today records the model that wrote it"
    assert out["call_count_today"] == 2
    assert out["stored"] is True


def test_a_failed_save_is_reported_rather_than_hidden():
    """He was charged. If the row did not save, the screen has to say so."""
    db = _fake_db_with_day_row(None)
    db.client.table.return_value.upsert.return_value.execute.side_effect = RuntimeError("no table")

    with patch("swayam.services.so_far_today.generate_grounded_content", return_value=_grounded()):
        out = generate_so_far_today(force=True, db=db)

    assert out["stored"] is False
    assert out["text"] == "NIFTY did a thing."


def test_the_sixty_minute_cache_returns_the_stored_row_without_calling_the_model():
    db = _fake_db_with_day_row({
        "day": date.today().isoformat(),
        "text": "already written a moment ago",
        "sources": [],
        "model": GROUNDED_MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_count": 1,
    })

    with patch("swayam.services.so_far_today.generate_grounded_content") as called:
        out = generate_so_far_today(force=False, db=db)

    called.assert_not_called()
    assert out["text"] == "already written a moment ago"
    assert out["is_cached"] is True


# ------------------------------------------------------------ deleting one chat

def test_deleting_a_conversation_removes_its_images_too():
    with patch("swayam.api.routes.ai.db") as db:
        bucket = db.client.storage.from_.return_value
        bucket.list.return_value = [{"name": "a.png"}, {"name": "b.png"}]

        out = delete_conversation("conv-1")

    db.client.table.assert_called_with("swayam_ai_conversations")
    db.client.storage.from_.assert_called_with(ATTACHMENT_BUCKET)
    bucket.list.assert_called_with("conv-1")
    bucket.remove.assert_called_once_with(["conv-1/a.png", "conv-1/b.png"])
    assert out["images_removed"] == 2
    assert out["images_error"] is None


def test_only_the_conversation_named_is_deleted():
    with patch("swayam.api.routes.ai.db") as db:
        db.client.storage.from_.return_value.list.return_value = []
        delete_conversation("conv-1")

    tables = [c.args[0] for c in db.client.table.call_args_list if c.args]
    # The notebook and the pinned decisions are never opened here: they survive
    # by foreign key, with their source_message_id set to NULL.
    assert "swayam_ai_notebook" not in tables
    assert "swayam_ai_pinned_decisions" not in tables
    assert "swayam_ai_usage_daily" not in tables
    db.client.table.return_value.delete.return_value.eq.assert_called_with("id", "conv-1")


def test_images_are_left_alone_when_the_rows_could_not_be_deleted():
    """Deleting the pictures of a conversation that still exists is worse."""
    from fastapi import HTTPException

    with patch("swayam.api.routes.ai.db") as db:
        db.client.table.return_value.delete.return_value.eq.return_value.execute.side_effect = (
            RuntimeError("connection lost")
        )
        with pytest.raises(HTTPException):
            delete_conversation("conv-1")

    db.client.storage.from_.assert_not_called()


def test_a_failure_to_remove_the_images_is_said_out_loud():
    with patch("swayam.api.routes.ai.db") as db:
        db.client.storage.from_.return_value.list.side_effect = RuntimeError("bucket unreachable")
        out = delete_conversation("conv-1")

    assert out["status"] == "deleted"
    assert out["images_removed"] == 0
    assert "bucket unreachable" in out["images_error"]
