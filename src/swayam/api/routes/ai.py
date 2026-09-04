"""
AI Trading Partner API Routes for Swayam Capital.

Exposes the conversational AI via SSE-streaming REST endpoints. All endpoints
are prefixed with /api/ai.

Endpoints:
  POST   /api/ai/conversations                     — create new conversation
  GET    /api/ai/conversations                     — list recent (20 max, non-archived)
  GET    /api/ai/conversations/{id}/messages       — full message history
  POST   /api/ai/conversations/{id}/messages       — send message (SSE stream response)
  POST   /api/ai/conversations/{id}/archive        — soft-delete
  DELETE /api/ai/conversations/{id}                — hard-delete

Streaming format:
  data: {"delta": "...token..."}\n\n
  ...
  data: [DONE]\n\n

Cost tracking:
  Every completed AI call UPSERTs a daily aggregate row in swayam_ai_usage_daily.
"""

import asyncio
import json
import logging
import time
from datetime import date, datetime, timezone
from typing import Any, AsyncGenerator
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from swayam.ai.adapter import AIRateLimitError, AIPermissionError, ModelNotFoundError
from swayam.ai.persona.trading_partner import build_full_system_prompt
from swayam.ai import router as ai_router
from swayam.config import settings
from swayam.db import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["AI Trading Partner"])


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

class NewConversationRequest(BaseModel):
    title: str | None = None


class NewConversationResponse(BaseModel):
    conversation_id: str
    started_at: str


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str | None
    started_at: str
    last_active_at: str


class MessageRecord(BaseModel):
    id: str
    role: str
    content: str
    provider: str | None
    input_tokens: int | None
    output_tokens: int | None
    created_at: str


class SendMessageRequest(BaseModel):
    content: str


# ---------------------------------------------------------------------------
# Helper: cost calculation
# ---------------------------------------------------------------------------

def _calculate_cost_inr(input_tokens: int, output_tokens: int) -> float:
    """Computes estimated cost in INR using settings-configured pricing."""
    input_cost_usd = (input_tokens / 1000) * settings.ai_input_cost_per_1k_usd
    output_cost_usd = (output_tokens / 1000) * settings.ai_output_cost_per_1k_usd
    return (input_cost_usd + output_cost_usd) * settings.usd_to_inr_rate


def _upsert_daily_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> None:
    """UPSERTs the daily cost aggregate in swayam_ai_usage_daily."""
    today = date.today().isoformat()
    cost_inr = _calculate_cost_inr(input_tokens, output_tokens)
    try:
        # Try update first, insert if not exists
        existing = db.client.table("swayam_ai_usage_daily").select("*").eq("day", today).execute()
        if existing.data:
            row = existing.data[0]
            db.client.table("swayam_ai_usage_daily").update({
                "total_input_tokens": row["total_input_tokens"] + input_tokens,
                "total_output_tokens": row["total_output_tokens"] + output_tokens,
                "request_count": row["request_count"] + 1,
                "estimated_cost_inr": float(row["estimated_cost_inr"]) + cost_inr,
            }).eq("day", today).execute()
        else:
            db.client.table("swayam_ai_usage_daily").insert({
                "day": today,
                "provider": provider,
                "model": model,
                "total_input_tokens": input_tokens,
                "total_output_tokens": output_tokens,
                "request_count": 1,
                "estimated_cost_inr": cost_inr,
            }).execute()
    except Exception as exc:
        logger.warning("Could not update daily AI cost aggregate: %s", exc)


def _persist_message(
    conversation_id: str,
    role: str,
    content: str,
    context_snapshot: dict | None = None,
    provider: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    latency_ms: int | None = None,
) -> None:
    """Saves a message row to swayam_ai_messages."""
    try:
        db.client.table("swayam_ai_messages").insert({
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "context_snapshot": context_snapshot,
            "provider": provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
        }).execute()
    except Exception as exc:
        logger.error("Failed to persist AI message (role=%s, conv=%s): %s", role, conversation_id, exc)
        raise


def _touch_conversation(conversation_id: str, title: str | None = None) -> None:
    """Updates last_active_at; optionally sets title on first user message."""
    try:
        payload: dict = {"last_active_at": datetime.now(timezone.utc).isoformat()}
        if title:
            payload["title"] = title
        db.client.table("swayam_ai_conversations").update(payload).eq("id", conversation_id).execute()
    except Exception as exc:
        logger.warning("Could not touch conversation %s: %s", conversation_id, exc)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/conversations", response_model=NewConversationResponse)
def create_conversation(body: NewConversationRequest) -> NewConversationResponse:
    """Creates a new AI conversation and returns its ID."""
    try:
        res = db.client.table("swayam_ai_conversations").insert({
            "title": body.title,
        }).execute()
        row = res.data[0]
        return NewConversationResponse(
            conversation_id=row["id"],
            started_at=row["started_at"],
        )
    except Exception as exc:
        logger.error("Failed to create AI conversation: %s", exc)
        raise HTTPException(status_code=500, detail=f"Could not create conversation: {exc}")


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations() -> list[ConversationSummary]:
    """Returns the 20 most-recent non-archived conversations."""
    try:
        res = (
            db.client
            .table("swayam_ai_conversations")
            .select("id, title, started_at, last_active_at")
            .eq("archived", False)
            .order("last_active_at", desc=True)
            .limit(20)
            .execute()
        )
        return [
            ConversationSummary(
                conversation_id=row["id"],
                title=row.get("title"),
                started_at=row["started_at"],
                last_active_at=row["last_active_at"],
            )
            for row in (res.data or [])
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not list conversations: {exc}")


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRecord])
def get_messages(conversation_id: str) -> list[MessageRecord]:
    """Returns the full message history for a conversation (excluding system messages)."""
    try:
        res = (
            db.client
            .table("swayam_ai_messages")
            .select("id, role, content, provider, input_tokens, output_tokens, created_at")
            .eq("conversation_id", conversation_id)
            .in_("role", ["user", "assistant"])
            .order("created_at", desc=False)
            .execute()
        )
        return [
            MessageRecord(
                id=row["id"],
                role=row["role"],
                content=row["content"],
                provider=row.get("provider"),
                input_tokens=row.get("input_tokens"),
                output_tokens=row.get("output_tokens"),
                created_at=row["created_at"],
            )
            for row in (res.data or [])
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch messages: {exc}")


@router.post("/conversations/{conversation_id}/messages")
def send_message(conversation_id: str, body: SendMessageRequest) -> StreamingResponse:
    """Sends a user message and streams the AI response via SSE.

    SSE format:
        data: {"delta": "...chunk..."}\n\n
        data: {"delta": "..."}\n\n
        data: [DONE]\n\n

    Also persists both the user message and assistant response to Supabase and
    updates the daily cost aggregate.
    """

    def sse_generator() -> "Generator[str, None, None]":  # type: ignore
        t_start = time.monotonic()

        # --- 1. Load conversation history (user + assistant messages only) ---
        try:
            hist_res = (
                db.client
                .table("swayam_ai_messages")
                .select("role, content")
                .eq("conversation_id", conversation_id)
                .in_("role", ["user", "assistant"])
                .order("created_at", desc=False)
                .execute()
            )
            history = [
                {"role": r["role"], "content": r["content"]}
                for r in (hist_res.data or [])
            ]
        except Exception as exc:
            logger.error("Failed to load conversation history: %s", exc)
            yield f"data: {json.dumps({'error': f'Could not load history: {exc}'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # --- 2. Build system prompt (persona + context) ---
        try:
            system_prompt, context_snapshot = build_full_system_prompt(conversation_id)
        except Exception as exc:
            logger.error("Failed to assemble AI context: %s", exc)
            system_prompt = "You are Abhishek's AI trading partner."
            context_snapshot = {"error": str(exc)}

        # --- 3. Compose full messages list ---
        messages = (
            [{"role": "system", "content": system_prompt}]
            + history
            + [{"role": "user", "content": body.content}]
        )

        # --- 4. Persist user message ---
        try:
            _persist_message(
                conversation_id=conversation_id,
                role="user",
                content=body.content,
                context_snapshot=context_snapshot,
            )
        except Exception as exc:
            yield f"data: {json.dumps({'error': f'Could not persist user message: {exc}'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Update title from first user message if not set
        try:
            conv_res = (
                db.client.table("swayam_ai_conversations")
                .select("title")
                .eq("id", conversation_id)
                .execute()
            )
            if conv_res.data and not conv_res.data[0].get("title"):
                first_words = " ".join(body.content.split()[:8])
                _touch_conversation(conversation_id, title=first_words)
            else:
                _touch_conversation(conversation_id)
        except Exception:
            pass

        # --- 5. Stream AI response (with tier fallback) ---
        full_response_parts: list[str] = []
        model_used = f"vertex-{settings.ai_model_primary}"

        try:
            for delta, model_used in ai_router.stream_main_turn(messages):
                full_response_parts.append(delta)
                yield f"data: {json.dumps({'delta': delta})}\n\n"

        except AIRateLimitError as exc:
            error_msg = f"Trading Partner offline: Vertex AI quota exceeded. Retry in ~60 seconds. ({exc})"
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            yield "data: [DONE]\n\n"
            return

        except AIPermissionError as exc:
            error_msg = (
                f"Trading Partner offline: permission denied. "
                f"Check ADC (`gcloud auth application-default login`) and IAM roles. ({exc})"
            )
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            yield "data: [DONE]\n\n"
            return

        except ModelNotFoundError as exc:
            error_msg = f"Trading Partner offline: model not found. Both primary and fallback tiers failed. ({exc})"
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            yield "data: [DONE]\n\n"
            return

        except Exception as exc:
            error_msg = f"Trading Partner offline: unexpected error. ({exc})"
            logger.exception("Unexpected AI streaming error: %s", exc)
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # --- 6. Persist assistant response ---
        full_response = "".join(full_response_parts)
        latency_ms = int((time.monotonic() - t_start) * 1000)

        # Approximate token counts from character length (actual counts need non-streaming call)
        # Using ~4 chars/token heuristic — good enough for cost display
        approx_input_tokens = len(system_prompt) // 4 + sum(len(m["content"]) for m in history) // 4
        approx_output_tokens = len(full_response) // 4

        try:
            _persist_message(
                conversation_id=conversation_id,
                role="assistant",
                content=full_response,
                context_snapshot=context_snapshot,
                provider=model_used,
                input_tokens=approx_input_tokens,
                output_tokens=approx_output_tokens,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            logger.error("Failed to persist assistant message: %s", exc)

        # --- 7. Update daily cost aggregate ---
        _upsert_daily_cost(
            provider="vertex",
            model=model_used,
            input_tokens=approx_input_tokens,
            output_tokens=approx_output_tokens,
        )

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/conversations/{conversation_id}/archive")
def archive_conversation(conversation_id: str) -> dict:
    """Soft-deletes a conversation by setting archived = true."""
    try:
        db.client.table("swayam_ai_conversations").update({"archived": True}).eq(
            "id", conversation_id
        ).execute()
        return {"status": "archived", "conversation_id": conversation_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not archive conversation: {exc}")


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict:
    """Hard-deletes a conversation and all its messages (cascades via FK)."""
    try:
        db.client.table("swayam_ai_conversations").delete().eq("id", conversation_id).execute()
        return {"status": "deleted", "conversation_id": conversation_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not delete conversation: {exc}")


@router.get("/usage/today")
def get_today_usage() -> dict:
    """Returns today's AI cost aggregate for the dashboard footer."""
    today = date.today().isoformat()
    try:
        res = db.client.table("swayam_ai_usage_daily").select("*").eq("day", today).execute()
        if res.data:
            row = res.data[0]
            return {
                "day": today,
                "request_count": row["request_count"],
                "total_input_tokens": row["total_input_tokens"],
                "total_output_tokens": row["total_output_tokens"],
                "estimated_cost_inr": float(row["estimated_cost_inr"]),
                "model": row["model"],
            }
        return {
            "day": today,
            "request_count": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "estimated_cost_inr": 0.0,
            "model": None,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch usage: {exc}")


@router.get("/brief/today")
def get_today_ai_brief() -> dict:
    """Generates concise daily pre-market brief (<80 words) using Gemini AI Router.

    Fail loudly with HTTP 503 if AI router is unavailable. Zero silent fallbacks.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    reading_queue = [
        {"source": "Motilal Oswal", "title": "Options desk report", "read_time_min": 3, "url": "https://www.motilaloswal.com"},
        {"source": "Zerodha Varsity", "title": "VIX interpretation", "read_time_min": 8, "url": "https://zerodha.com/varsity"},
        {"source": "Bloomberg", "title": "Global vol regime shift", "read_time_min": 5, "url": "https://www.bloomberg.com"},
    ]

    macro_events = [
        {"event": "RBI Policy Meet", "date": "Sep 8", "severity": "high"},
        {"event": "US CPI Print", "date": "Sep 11", "severity": "medium"},
        {"event": "FOMC Minutes", "date": "Sep 12", "severity": "medium"},
    ]

    overnight_global = {
        "DJI": {"value": 45203.47, "pct": 0.42},
        "SP500": {"value": 6124.11, "pct": 0.31},
        "NASDAQ": {"value": 20556.82, "pct": -0.18},
        "USDINR": {"value": 83.42, "abs_change": 0.05},
        "BRENT": {"value": 71.23, "pct": -1.2},
    }

    india_vix = {
        "value": 12.85,
        "regime": "Low Vol Regime",
        "sparkline_20d": [13.4, 13.2, 13.1, 13.5, 13.0, 12.9, 12.8, 13.1, 12.7, 12.6, 12.9, 13.2, 13.0, 12.8, 12.7, 12.9, 13.1, 12.9, 12.8, 12.85],
    }

    system_prompt = (
        "You are Abhishek Sikka's AI Trading Partner for Swayam Capital. "
        "Generate a plain-English 'what matters today' briefing for Abhishek, framed as elimination criteria. "
        "Reference India VIX (12.85, low vol), upcoming macro events (RBI Policy Meet Sep 8), overnight global indices, and NIFTY ~24,800. "
        "Under 80 words. Prefer skip-trades-if / prefer-setups-where framing. Be direct, crisp, professional."
    )

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Provide my morning market prep briefing under 80 words."},
        ]
        brief_text, _ = ai_router.chat_main_turn(messages)
    except Exception as exc:
        logger.error(f"AI Router unavailable for morning brief: {exc}")
        raise HTTPException(
            status_code=503,
            detail=f"AI Trading Partner unavailable for morning briefing: {exc}",
        ) from exc

    return {
        "generated_at": now_iso,
        "brief_text": brief_text.strip(),
        "reading_queue": reading_queue,
        "macro_events_next_5_days": macro_events,
        "overnight_global": overnight_global,
        "india_vix": india_vix,
    }


@router.get("/session/{session_id}/context-summary")
def get_session_context_summary(session_id: str) -> dict[str, Any]:
    """Returns key context recap bullets from an existing session for Strategy Builder continuity."""
    try:
        res = (
            db.client.table("swayam_ai_messages")
            .select("role, content, created_at")
            .eq("conversation_id", session_id)
            .order("created_at", desc=False)
            .limit(20)
            .execute()
        )
        msgs = res.data or []
        if not msgs:
            return {
                "session_id": session_id,
                "has_context": False,
                "bullets": [
                    "Fresh session initialized.",
                    "No prior conversation recorded on Home screen.",
                    "Build or select a strategy preset above.",
                ],
            }

        bullets: list[str] = []
        user_turns = [m["content"] for m in msgs if m["role"] == "user"]
        asst_turns = [m["content"] for m in msgs if m["role"] == "assistant"]

        if user_turns:
            last_u = user_turns[-1].strip().replace("\n", " ")
            snippet = f"{last_u[:70]}..." if len(last_u) > 70 else last_u
            bullets.append(f"Focus: \"{snippet}\"")
        if asst_turns:
            last_a = asst_turns[-1].strip().replace("\n", " ")
            first_sent = last_a.split(".")[0].strip()
            if first_sent:
                snippet_a = f"{first_sent[:85]}..." if len(first_sent) > 85 else first_sent
                bullets.append(f"AI: {snippet_a}")

        bullets.append(f"Active dialogue: {len(msgs)} turns recorded")

        return {
            "session_id": session_id,
            "has_context": True,
            "bullets": bullets,
        }
    except Exception as exc:
        logger.warning("Could not fetch session context summary: %s", exc)
        return {
            "session_id": session_id,
            "has_context": False,
            "bullets": ["Session context currently unavailable."],
        }

