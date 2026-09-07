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

from fastapi import APIRouter, HTTPException, Request
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
    provider: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    created_at: str
    attachment_url: str | None = None
    attachment_mime: str | None = None


class ChatResponse(BaseModel):
    response: str
    attachment_url: str | None = None
    conversation_id: str
    model_used: str


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


ALLOWED_IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


async def _process_image_upload(image_file: Any, conversation_id: str) -> tuple[bytes, str, str]:
    """Validates and uploads an image attachment to Supabase Storage.

    Returns:
        (image_bytes, image_mime, attachment_url)
    """
    raw_bytes = await image_file.read()
    if len(raw_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Image size ({len(raw_bytes) / 1024 / 1024:.2f} MB) exceeds maximum allowed size of 5 MB."
        )

    mime = getattr(image_file, "content_type", None) or "image/png"
    if mime not in ALLOWED_IMAGE_MIMES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image format '{mime}'. Allowed formats: PNG, JPEG, WEBP, GIF."
        )

    ext = mime.split("/")[-1].replace("jpeg", "jpg")
    msg_id = str(uuid4())
    storage_path = f"{conversation_id}/{msg_id}.{ext}"

    try:
        bucket = db.client.storage.from_("swayam-ai-chat-attachments")
        bucket.upload(storage_path, raw_bytes, file_options={"content-type": mime})
        attachment_url = bucket.get_public_url(storage_path)
        return raw_bytes, mime, attachment_url
    except Exception as exc:
        logger.error("Failed to upload image to Supabase Storage: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to upload image attachment: {exc}")


def _persist_message(
    conversation_id: str,
    role: str,
    content: str,
    context_snapshot: dict | None = None,
    provider: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    latency_ms: int | None = None,
    attachment_url: str | None = None,
    attachment_mime: str | None = None,
) -> None:
    """Saves a message row to swayam_ai_messages."""
    try:
        payload = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "context_snapshot": context_snapshot,
            "provider": provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
        }
        if attachment_url:
            payload["attachment_url"] = attachment_url
        if attachment_mime:
            payload["attachment_mime"] = attachment_mime
        db.client.table("swayam_ai_messages").insert(payload).execute()
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
            .select("id, role, content, provider, input_tokens, output_tokens, created_at, attachment_url, attachment_mime")
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
                attachment_url=row.get("attachment_url"),
                attachment_mime=row.get("attachment_mime"),
            )
            for row in (res.data or [])
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch messages: {exc}")


@router.post("/conversations/{conversation_id}/messages")
async def send_message(conversation_id: str, request: Request) -> StreamingResponse:
    """Sends a user message and streams the AI response via SSE.
    Supports both JSON bodies and multipart/form-data with image attachments.

    SSE format:
        data: {"attachment_url": "..."}\n\n (optional, if image attached)
        data: {"delta": "...chunk..."}\n\n
        data: [DONE]\n\n
    """
    content_type = request.headers.get("content-type", "")
    content = ""
    image_bytes = None
    image_mime = None
    attachment_url = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        content = str(form.get("content") or "").strip()
        image_file = form.get("image")
        if image_file and hasattr(image_file, "read"):
            image_bytes, image_mime, attachment_url = await _process_image_upload(image_file, conversation_id)
    else:
        try:
            body = await request.json()
            content = str(body.get("content") or "").strip()
        except Exception:
            content = ""

    if not content and not image_bytes:
        raise HTTPException(status_code=400, detail="Message content or image attachment is required.")

    def sse_generator() -> "Generator[str, None, None]":  # type: ignore
        t_start = time.monotonic()

        # If an image was attached, echo attachment_url to client first
        if attachment_url:
            yield f"data: {json.dumps({'attachment_url': attachment_url})}\n\n"

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
        user_turn: dict[str, Any] = {"role": "user", "content": content or "Analyze this chart screenshot."}
        if image_bytes and image_mime:
            user_turn["image_bytes"] = image_bytes
            user_turn["image_mime"] = image_mime

        messages = (
            [{"role": "system", "content": system_prompt}]
            + history
            + [user_turn]
        )

        # --- 4. Persist user message ---
        try:
            _persist_message(
                conversation_id=conversation_id,
                role="user",
                content=content or "Analyze this chart screenshot.",
                context_snapshot=context_snapshot,
                attachment_url=attachment_url,
                attachment_mime=image_mime,
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
                first_words = " ".join((content or "Chart Analysis").split()[:8])
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


# NOTE: The old GET /api/ai/brief/today ("morning brief") endpoint was REMOVED on
# 2026-09-07. It returned entirely hardcoded/fake data (fake overnight globals, fake
# macro dates, fake India VIX 12.85 + sparkline) and fed fabricated reference numbers
# into the AI prompt. No fake data is served to the UI or the AI. The real, grounded
# session summary lives at POST /api/home/so-far-today (Google Search grounded).


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


@router.post("/chat", response_model=ChatResponse)
async def direct_chat_endpoint(request: Request) -> ChatResponse:
    """Non-streaming AI chat endpoint supporting both text and image attachments."""
    content_type = request.headers.get("content-type", "")
    content = ""
    conversation_id = None
    image_bytes = None
    image_mime = None
    attachment_url = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        content = str(form.get("content") or form.get("message") or "").strip()
        conversation_id = form.get("conversation_id") or form.get("session_id")
        image_file = form.get("image")
        if not conversation_id:
            res = db.client.table("swayam_ai_conversations").insert({
                "title": f"Chat {datetime.now(timezone.utc).strftime('%d %b %H:%M')}"
            }).execute()
            conversation_id = res.data[0]["id"] if res.data else str(uuid4())
        if image_file and hasattr(image_file, "read"):
            image_bytes, image_mime, attachment_url = await _process_image_upload(image_file, str(conversation_id))
    else:
        try:
            body = await request.json()
            content = str(body.get("content") or body.get("message") or "").strip()
            conversation_id = body.get("conversation_id") or body.get("session_id")
        except Exception:
            content = ""

    if not conversation_id:
        res = db.client.table("swayam_ai_conversations").insert({
            "title": f"Chat {datetime.now(timezone.utc).strftime('%d %b %H:%M')}"
        }).execute()
        conversation_id = res.data[0]["id"] if res.data else str(uuid4())

    if not content and not image_bytes:
        raise HTTPException(status_code=400, detail="Message content or image attachment is required.")

    # Load history
    try:
        hist_res = (
            db.client.table("swayam_ai_messages")
            .select("role, content")
            .eq("conversation_id", conversation_id)
            .in_("role", ["user", "assistant"])
            .order("created_at", desc=False)
            .execute()
        )
        history = [{"role": r["role"], "content": r["content"]} for r in (hist_res.data or [])]
    except Exception:
        history = []

    try:
        system_prompt, context_snapshot = build_full_system_prompt(str(conversation_id))
    except Exception:
        system_prompt = "You are Abhishek's AI trading partner."
        context_snapshot = {}

    user_turn: dict[str, Any] = {"role": "user", "content": content or "Analyze this chart screenshot."}
    if image_bytes and image_mime:
        user_turn["image_bytes"] = image_bytes
        user_turn["image_mime"] = image_mime

    messages = [{"role": "system", "content": system_prompt}] + history + [user_turn]

    _persist_message(
        conversation_id=str(conversation_id),
        role="user",
        content=content or "Analyze this chart screenshot.",
        context_snapshot=context_snapshot,
        attachment_url=attachment_url,
        attachment_mime=image_mime,
    )

    t_start = time.monotonic()
    response_text, model_used = ai_router.chat_main_turn(messages)
    latency_ms = int((time.monotonic() - t_start) * 1000)

    _persist_message(
        conversation_id=str(conversation_id),
        role="assistant",
        content=response_text,
        provider=model_used,
        latency_ms=latency_ms,
    )
    _touch_conversation(str(conversation_id))

    return ChatResponse(
        response=response_text,
        attachment_url=attachment_url,
        conversation_id=str(conversation_id),
        model_used=model_used,
    )


