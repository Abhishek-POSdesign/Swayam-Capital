"""
FastAPI route for Layer 3 AI Memory Notebook.
Allows Abhishek to persist key insights and lessons directly into permanent memory.
"""

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from swayam.db import db

router = APIRouter(prefix="/api/ai/notebook", tags=["AI Notebook"])


class NotebookCreateRequest(BaseModel):
    entry_text: str = Field(..., min_length=1, description="Memory text content")
    source_message_id: Optional[str] = Field(None, description="Optional UUID of source message")
    source_conversation_id: Optional[str] = Field(None, description="Optional UUID of conversation")


class NotebookUpdateRequest(BaseModel):
    entry_text: str = Field(..., min_length=1, description="Updated text content")


class NotebookEntry(BaseModel):
    id: int
    entry_text: str
    source_message_id: Optional[str] = None
    source_conversation_id: Optional[str] = None
    created_at: str
    updated_at: str


@router.post("", response_model=NotebookEntry)
def create_entry(body: NotebookCreateRequest) -> NotebookEntry:
    """Creates a new permanent notebook memory entry."""
    try:
        now_str = datetime.now(timezone.utc).isoformat()
        res = (
            db.client.table("swayam_ai_notebook")
            .insert({
                "entry_text": body.entry_text.strip(),
                "source_message_id": body.source_message_id,
                "source_conversation_id": body.source_conversation_id,
                "created_at": now_str,
                "updated_at": now_str,
            })
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to insert notebook entry.")
        row = res.data[0]
        return NotebookEntry(
            id=row["id"],
            entry_text=row["entry_text"],
            source_message_id=row.get("source_message_id"),
            source_conversation_id=row.get("source_conversation_id"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not save notebook entry: {exc}")


@router.get("", response_model=List[NotebookEntry])
def list_entries() -> List[NotebookEntry]:
    """Returns all saved memory notebook entries in reverse chronological order."""
    try:
        res = (
            db.client.table("swayam_ai_notebook")
            .select("id, entry_text, source_message_id, source_conversation_id, created_at, updated_at")
            .order("created_at", desc=True)
            .execute()
        )
        return [
            NotebookEntry(
                id=row["id"],
                entry_text=row["entry_text"],
                source_message_id=row.get("source_message_id"),
                source_conversation_id=row.get("source_conversation_id"),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in (res.data or [])
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not list notebook entries: {exc}")


@router.patch("/{entry_id}", response_model=NotebookEntry)
def update_entry(entry_id: int, body: NotebookUpdateRequest) -> NotebookEntry:
    """Updates the text content of a notebook memory entry."""
    try:
        now_str = datetime.now(timezone.utc).isoformat()
        res = (
            db.client.table("swayam_ai_notebook")
            .update({
                "entry_text": body.entry_text.strip(),
                "updated_at": now_str,
            })
            .eq("id", entry_id)
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Notebook entry not found.")
        row = res.data[0]
        return NotebookEntry(
            id=row["id"],
            entry_text=row["entry_text"],
            source_message_id=row.get("source_message_id"),
            source_conversation_id=row.get("source_conversation_id"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not update notebook entry: {exc}")


@router.delete("/{entry_id}")
def delete_entry(entry_id: int) -> dict:
    """Deletes a notebook memory entry."""
    try:
        db.client.table("swayam_ai_notebook").delete().eq("id", entry_id).execute()
        return {"status": "deleted", "id": entry_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not delete notebook entry: {exc}")
