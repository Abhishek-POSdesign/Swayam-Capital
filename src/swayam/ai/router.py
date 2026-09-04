"""
3-Tier AI Model Router for Swayam Capital.

Routes AI requests across three model tiers with automatic fallback:

  Tier 1 (PRIMARY)   — gemini-3.1-pro-preview  — main conversation turns
  Tier 2 (FALLBACK)  — gemini-2.5-pro           — auto-fallback on rate-limit / not-found / permission
  Tier 3 (LIGHT)     — gemini-2.5-flash-lite    — widget calculations (reserved, not used in BUILD-6)

Routing rule:
  - Chat endpoints call stream_main_turn() or chat_main_turn() → tries PRIMARY first.
  - On AIRateLimitError, AIPermissionError, or ModelNotFoundError → switches to FALLBACK.
  - If FALLBACK also fails → re-raises the exception so the API layer returns a clear HTTP 503.
  - Records which model tier was actually used so callers can log it to swayam_ai_messages.provider.

No silent fallbacks. Every error that isn't handled by tier-switching is raised loudly.
"""

import logging
import time
from typing import Generator

from swayam.ai.adapter import AIRateLimitError, AIPermissionError, ModelNotFoundError
from swayam.ai.providers.vertex import VertexAIProvider
from swayam.config import settings

logger = logging.getLogger(__name__)

# Errors that trigger an automatic model-tier downgrade
_FALLBACK_ERRORS = (AIRateLimitError, AIPermissionError, ModelNotFoundError)


def _make_provider(model: str) -> VertexAIProvider:
    """Creates a VertexAIProvider wired to the given model."""
    return VertexAIProvider(
        project_id=settings.gcp_project_id,
        location=settings.gcp_ai_location,
        model=model,
        max_output_tokens=settings.ai_max_output_tokens,
        temperature=settings.ai_temperature,
    )



def chat_main_turn(messages: list[dict[str, str]]) -> tuple[str, str]:
    """Sends a conversation turn, falling back across model tiers.

    Args:
        messages: List of {'role': ..., 'content': ...} dicts including the
                  system prompt and full conversation history.

    Returns:
        (response_text, model_id_used)

    Raises:
        AIRateLimitError | AIPermissionError | ModelNotFoundError | RuntimeError:
            If both primary and fallback tiers fail.
    """
    primary_model = settings.ai_model_primary
    fallback_model = settings.ai_model_reasoning_fallback

    # --- Tier 1: PRIMARY ---
    try:
        provider = _make_provider(primary_model)
        result = provider.chat(messages)
        logger.info("AI turn completed via primary model: %s", primary_model)
        return result, f"vertex-{primary_model}"
    except _FALLBACK_ERRORS as exc:
        logger.warning(
            "Primary model '%s' failed (%s: %s). Falling back to '%s'.",
            primary_model, type(exc).__name__, exc, fallback_model,
        )

    # --- Tier 2: FALLBACK ---
    try:
        provider = _make_provider(fallback_model)
        result = provider.chat(messages)
        logger.info("AI turn completed via fallback model: %s", fallback_model)
        return result, f"vertex-{fallback_model}"
    except Exception as exc:
        logger.error(
            "Fallback model '%s' also failed: %s", fallback_model, exc
        )
        raise


def stream_main_turn(
    messages: list[dict[str, str]]
) -> Generator[tuple[str, str], None, None]:
    """Streams a conversation turn, falling back across model tiers.

    Yields (delta_chunk, model_id_used) tuples. The model_id is repeated
    on every chunk so the caller always knows which tier produced the response.

    Args:
        messages: Full conversation messages list (system + history + new user).

    Yields:
        (str_delta, model_id) — text chunk + the model that produced it.

    Raises:
        AIRateLimitError | AIPermissionError | ModelNotFoundError | RuntimeError:
            If both primary and fallback tiers fail.
    """
    primary_model = settings.ai_model_primary
    fallback_model = settings.ai_model_reasoning_fallback

    # --- Tier 1: PRIMARY (streaming) ---
    primary_failed = False
    try:
        provider = _make_provider(primary_model)
        first_chunk = True
        for delta in provider.stream_chat(messages):
            if first_chunk:
                logger.info("Streaming started via primary model: %s", primary_model)
                first_chunk = False
            yield delta, f"vertex-{primary_model}"
        return  # Primary succeeded — done
    except _FALLBACK_ERRORS as exc:
        logger.warning(
            "Primary streaming model '%s' failed (%s: %s). Falling back to '%s'.",
            primary_model, type(exc).__name__, exc, fallback_model,
        )
        primary_failed = True
    except Exception:
        # Non-fallback errors propagate immediately — no silent swallow
        raise

    # --- Tier 2: FALLBACK (streaming) ---
    if primary_failed:
        try:
            provider = _make_provider(fallback_model)
            first_chunk = True
            for delta in provider.stream_chat(messages):
                if first_chunk:
                    logger.info("Streaming started via fallback model: %s", fallback_model)
                    first_chunk = False
                yield delta, f"vertex-{fallback_model}"
        except Exception as exc:
            logger.error("Fallback streaming model '%s' also failed: %s", fallback_model, exc)
            raise


def chat_lightweight(messages: list[dict[str, str]]) -> tuple[str, str]:
    """Sends a request via the lightweight model tier (widget summaries, quick lookups).

    Reserved for future widget/inline-analysis components. Not used in BUILD-6
    conversational flow.

    Args:
        messages: Message list (typically short, single-turn).

    Returns:
        (response_text, model_id_used)
    """
    light_model = settings.ai_model_lightweight
    try:
        provider = _make_provider(light_model)
        result = provider.chat(messages)
        return result, f"vertex-{light_model}"
    except Exception as exc:
        logger.error("Lightweight model '%s' failed: %s", light_model, exc)
        raise
