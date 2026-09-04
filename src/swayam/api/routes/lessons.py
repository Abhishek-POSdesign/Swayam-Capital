"""
AI Lesson Ledger Endpoints for Swayam Capital (BUILD-11).

Provides:
- POST /api/lessons/generate/{position_id} — Generates 1-sentence grounded AI takeaway
- PUT  /api/lessons/{lesson_id}           — User updates/edits lesson text
- generate_lesson_for_position()          — Core helper reused by trade close flow
"""

from datetime import datetime, timezone
import logging
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from swayam.ai import router as ai_router
from swayam.api.journal_writer import append_or_update_lesson_block
from swayam.api.models_api import LessonResponse, LessonUpdateRequest
from swayam.db import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lessons", tags=["Trade Lessons"])


def generate_lesson_for_position(
    position_id: str,
    pos_record: Optional[dict[str, Any]] = None,
    realized_pnl: Optional[float] = None,
    trade_outcome: Optional[str] = None,
) -> dict[str, Any]:
    """Generates a concise, single-sentence lesson for a closed trade using AI.

    Args:
        position_id: UUID of the position.
        pos_record: Optional existing position row from swayam_positions.
        realized_pnl: Optional realized net P&L.
        trade_outcome: Optional WIN, LOSS, or BREAKEVEN outcome.

    Returns:
        Dictionary representing the created or updated swayam_lessons record.
    """
    client = db.client

    # 1. Fetch position if not provided
    if not pos_record:
        res = client.table("swayam_positions").select("*").eq("id", position_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail=f"Position {position_id} not found.")
        pos_record = res.data[0]

    strategy_name = str(pos_record.get("strategy_name") or "Options Strategy")
    closed_at_str = pos_record.get("closed_at") or datetime.now(timezone.utc).isoformat()
    pnl = realized_pnl if realized_pnl is not None else float(pos_record.get("realized_pnl_inr") or 0.0)

    if trade_outcome:
        outcome = trade_outcome
    else:
        outcome = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "BREAKEVEN"

    max_loss = float(pos_record.get("max_loss_inr") or 0.0)
    rr_planned = float(pos_record.get("rr_planned") or 0.0) if pos_record.get("rr_planned") else None
    rr_actual = round(pnl / max_loss, 2) if max_loss > 0 else None

    # Context fields for prompt grounding
    exit_reason = pos_record.get("exit_reason") or "manual"
    rules_followed = pos_record.get("rules_followed", True)
    rules_broken = pos_record.get("rules_broken_reason") or ""
    entry_rationale = pos_record.get("entry_rationale") or ""
    exit_rationale = pos_record.get("exit_rationale") or ""
    duration_mins = pos_record.get("time_in_trade_minutes")
    points_in_trade = pos_record.get("points_in_trade")

    # 2. Prompt engineering: Strict 1-sentence grounded lesson (<50 words)
    system_prompt = (
        "You are Abhishek Sikka's AI trading partner at Swayam Capital. "
        "Your task is to write a single-sentence takeaway/lesson (<40 words) for a recently closed NIFTY options trade. "
        "Name the strategy, whether it won or lost, and highlight the key execution or discipline insight. "
        "If rules were broken, call out the violation directly. If rules were followed, evaluate whether the plan worked. "
        "Write ONLY the single sentence. Do not include quotes, greetings, or bullet points."
    )

    user_prompt = (
        f"Trade details:\n"
        f"- Strategy: {strategy_name}\n"
        f"- Outcome: {outcome} (Net P&L: ₹{pnl:+,.2f}, Realised R:R: {rr_actual or 'N/A'})\n"
        f"- Planned R:R: {rr_planned or 'N/A'}\n"
        f"- Exit Reason: {exit_reason}\n"
        f"- Rules Followed: {rules_followed}"
        f"{f', Reason rules broken: {rules_broken}' if rules_broken else ''}\n"
        f"- Entry Rationale: {entry_rationale or 'Standard method setup'}\n"
        f"- Exit Rationale: {exit_rationale or 'None recorded'}\n"
        f"- Wall-clock duration: {duration_mins or 'N/A'} mins\n"
        f"- Underlying points captured: {points_in_trade or 'N/A'}\n\n"
        f"Provide the 1-sentence lesson now."
    )

    lesson_text = "[Lesson generation failed — regenerate from the Journal page]"
    lesson_source = "ai_failed"

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        ai_resp, _ = ai_router.chat_main_turn(messages)
        cleaned = ai_resp.strip().strip('"').strip("'")
        if cleaned:
            lesson_text = cleaned
            lesson_source = "ai_generated"
    except Exception as exc:
        logger.warning("AI lesson generation error for position %s: %s", position_id, exc)

    now_iso = datetime.now(timezone.utc).isoformat()

    # 3. Check for existing lesson in DB
    existing = client.table("swayam_lessons").select("*").eq("position_id", position_id).execute()
    record: dict[str, Any]

    if existing.data:
        lesson_id = existing.data[0]["id"]
        update_payload = {
            "strategy_name": strategy_name,
            "outcome": outcome,
            "realised_pnl_inr": pnl,
            "rr_planned": rr_planned,
            "rr_actual": rr_actual,
            "lesson_text": lesson_text,
            "lesson_source": lesson_source,
            "updated_at": now_iso,
        }
        client.table("swayam_lessons").update(update_payload).eq("id", lesson_id).execute()
        record = {**existing.data[0], **update_payload}
    else:
        new_payload = {
            "position_id": position_id,
            "trade_closed_at": closed_at_str,
            "strategy_name": strategy_name,
            "outcome": outcome,
            "realised_pnl_inr": pnl,
            "rr_planned": rr_planned,
            "rr_actual": rr_actual,
            "lesson_text": lesson_text,
            "lesson_source": lesson_source,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        res_ins = client.table("swayam_lessons").insert(new_payload).execute()
        record = res_ins.data[0] if res_ins.data else new_payload

    # 4. Sync lesson to Obsidian Vault markdown note
    journal_path = pos_record.get("journal_path")
    if journal_path:
        try:
            append_or_update_lesson_block(
                journal_rel_path=journal_path,
                lesson_text=lesson_text,
                lesson_source=lesson_source,
            )
        except Exception as exc:
            logger.warning("Could not sync lesson to vault note %s: %s", journal_path, exc)

    return record


@router.post("/generate/{position_id}", response_model=LessonResponse)
def api_generate_lesson(position_id: str) -> LessonResponse:
    """Generates an AI lesson for a trade position and stores it in the Lesson Ledger."""
    try:
        record = generate_lesson_for_position(position_id)
        return LessonResponse(
            id=str(record.get("id") or uuid4()),
            position_id=str(record["position_id"]),
            trade_closed_at=str(record["trade_closed_at"]),
            strategy_name=str(record["strategy_name"]),
            outcome=str(record["outcome"]),
            realised_pnl_inr=float(record["realised_pnl_inr"]),
            rr_planned=float(record["rr_planned"]) if record.get("rr_planned") is not None else None,
            rr_actual=float(record["rr_actual"]) if record.get("rr_actual") is not None else None,
            lesson_text=str(record["lesson_text"]),
            lesson_source=str(record.get("lesson_source", "ai_generated")),
            created_at=str(record.get("created_at") or datetime.now(timezone.utc).isoformat()),
            updated_at=str(record.get("updated_at") or datetime.now(timezone.utc).isoformat()),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to generate lesson: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Database or AI service unavailable while generating lesson: {exc}",
        )


@router.put("/{lesson_id}", response_model=LessonResponse)
def api_update_lesson(lesson_id: str, req: LessonUpdateRequest) -> LessonResponse:
    """Updates a lesson's text when Abhishek edits it manually from the Journal."""
    client = db.client
    try:
        existing = client.table("swayam_lessons").select("*").eq("id", lesson_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail=f"Lesson {lesson_id} not found.")

        row = existing.data[0]
        now_iso = datetime.now(timezone.utc).isoformat()
        update_data = {
            "lesson_text": req.lesson_text.strip(),
            "lesson_source": "user_edited",
            "updated_at": now_iso,
        }
        client.table("swayam_lessons").update(update_data).eq("id", lesson_id).execute()

        # Update note in vault if journal_path is available on position
        pos_res = client.table("swayam_positions").select("journal_path").eq("id", row["position_id"]).execute()
        if pos_res.data and pos_res.data[0].get("journal_path"):
            append_or_update_lesson_block(
                journal_rel_path=pos_res.data[0]["journal_path"],
                lesson_text=req.lesson_text.strip(),
                lesson_source="user_edited",
            )

        updated_row = {**row, **update_data}
        return LessonResponse(
            id=str(updated_row["id"]),
            position_id=str(updated_row["position_id"]),
            trade_closed_at=str(updated_row["trade_closed_at"]),
            strategy_name=str(updated_row["strategy_name"]),
            outcome=str(updated_row["outcome"]),
            realised_pnl_inr=float(updated_row["realised_pnl_inr"]),
            rr_planned=float(updated_row["rr_planned"]) if updated_row.get("rr_planned") is not None else None,
            rr_actual=float(updated_row["rr_actual"]) if updated_row.get("rr_actual") is not None else None,
            lesson_text=str(updated_row["lesson_text"]),
            lesson_source=str(updated_row["lesson_source"]),
            created_at=str(updated_row["created_at"]),
            updated_at=str(updated_row["updated_at"]),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to update lesson %s: %s", lesson_id, exc)
        raise HTTPException(
            status_code=503,
            detail=f"Database error while updating lesson: {exc}",
        )