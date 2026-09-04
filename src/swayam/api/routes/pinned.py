"""
FastAPI route for Layer 3 Pinned Trading Rules and Decisions.
Persists permanent trading constraints and user directives across all conversations.
"""

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from swayam.db import db

router = APIRouter(prefix="/api/ai/pinned", tags=["AI Pinned Rules"])


class PinnedRuleCreate(BaseModel):
    rule_text: str = Field(..., min_length=1, description="Rule or constraint description")
    source_message_id: Optional[str] = Field(None, description="Optional source message UUID")


class PinnedRuleRecord(BaseModel):
    id: int
    rule_text: str
    active: bool
    pinned_at: str
    source_message_id: Optional[str] = None


@router.post("", response_model=PinnedRuleRecord)
def pin_rule(body: PinnedRuleCreate) -> PinnedRuleRecord:
    """Pins a new permanent trading rule or decision."""
    try:
        now_str = datetime.now(timezone.utc).isoformat()
        res = (
            db.client.table("swayam_ai_pinned_decisions")
            .insert({
                "rule_text": body.rule_text.strip(),
                "source_message_id": body.source_message_id,
                "pinned_at": now_str,
                "active": True,
            })
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to pin rule.")
        row = res.data[0]
        return PinnedRuleRecord(
            id=row["id"],
            rule_text=row["rule_text"],
            active=row["active"],
            pinned_at=row["pinned_at"],
            source_message_id=row.get("source_message_id"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not pin rule: {exc}")


@router.get("", response_model=List[PinnedRuleRecord])
def list_pinned_rules() -> List[PinnedRuleRecord]:
    """Lists all active pinned trading rules."""
    try:
        res = (
            db.client.table("swayam_ai_pinned_decisions")
            .select("id, rule_text, active, pinned_at, source_message_id")
            .eq("active", True)
            .order("pinned_at", desc=True)
            .execute()
        )
        return [
            PinnedRuleRecord(
                id=row["id"],
                rule_text=row["rule_text"],
                active=row["active"],
                pinned_at=row["pinned_at"],
                source_message_id=row.get("source_message_id"),
            )
            for row in (res.data or [])
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not list pinned rules: {exc}")


@router.delete("/{rule_id}")
def unpin_rule(rule_id: int) -> dict:
    """Deactivates/unpins a rule."""
    try:
        db.client.table("swayam_ai_pinned_decisions").update({
            "active": False
        }).eq("id", rule_id).execute()
        return {"status": "unpinned", "id": rule_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not unpin rule: {exc}")
