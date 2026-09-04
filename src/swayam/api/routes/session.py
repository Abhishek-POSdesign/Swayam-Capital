"""
FastAPI route for AI Trading Session Management & Continuity.
Supports session IDs, message history loading, and cron compaction triggers.
"""

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from swayam.ai.memory import compact_session
from swayam.db import db

router = APIRouter(prefix="/api/ai/session", tags=["AI Session Continuity"])


class NewSessionResponse(BaseModel):
    session_id: str
    started_at: str


class SessionMessage(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    provider: Optional[str] = None
    position_id: Optional[str] = None


@router.post("/new", response_model=NewSessionResponse)
def create_session() -> NewSessionResponse:
    """Creates a new trading session conversation."""
    try:
        res = (
            db.client.table("swayam_ai_conversations")
            .insert({
                "title": f"Trading Session {datetime.now(timezone.utc).strftime('%d %b %H:%M')}",
            })
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to initialize session.")
        row = res.data[0]
        return NewSessionResponse(
            session_id=row["id"],
            started_at=row["started_at"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not create session: {exc}")


@router.get("/{session_id}/messages", response_model=List[SessionMessage])
def get_session_messages(session_id: str) -> List[SessionMessage]:
    """Retrieves all dialogue messages for an active trading session."""
    try:
        res = (
            db.client.table("swayam_ai_messages")
            .select("id, role, content, created_at, provider, position_id")
            .eq("conversation_id", session_id)
            .in_("role", ["user", "assistant"])
            .order("created_at", desc=False)
            .execute()
        )
        return [
            SessionMessage(
                id=row["id"],
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"],
                provider=row.get("provider"),
                position_id=row.get("position_id"),
            )
            for row in (res.data or [])
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not retrieve session messages: {exc}")


@router.post("/compact-yesterday")
def compact_yesterday_cron() -> dict:
    """Cron endpoint for 4 PM IST daily compaction of yesterday's session."""
    yesterday = date.today() - timedelta(days=1)
    try:
        summary = compact_session(yesterday)
        return {
            "status": "success",
            "session_date": yesterday.isoformat(),
            "summary": summary,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Compaction failed: {exc}")
