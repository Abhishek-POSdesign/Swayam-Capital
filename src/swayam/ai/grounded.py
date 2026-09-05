"""
Google Search Grounded Gemini helper for Swayam Capital.

Uses the official google-genai SDK with Vertex AI backend to perform real-time
search-grounded reasoning over Indian market news and tape dynamics.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from google import genai
from google.genai import types

from swayam.config import settings

logger = logging.getLogger(__name__)


def generate_grounded_content(
    prompt: str,
    system_instruction: Optional[str] = None,
    model: str = "gemini-2.5-flash",
) -> dict[str, Any]:
    """Invokes Gemini with Google Search grounding enabled via Vertex AI.

    Args:
        prompt: User or session prompt requiring real-time grounding.
        system_instruction: Optional system instruction.
        model: Model name (defaults to 'gemini-2.5-flash').

    Returns:
        dict with:
            - text: str
            - sources: list of dicts with title and url
            - search_queries: list of queries executed by Google Search
            - tokens_used: int or None
    """
    client = genai.Client(
        vertexai=True,
        project=settings.gcp_project_id,
        location="us-central1",
    )

    config_args: dict[str, Any] = {
        "tools": [types.Tool(google_search=types.GoogleSearch())],
        "temperature": 0.2,
    }
    if system_instruction:
        config_args["system_instruction"] = system_instruction

    config = types.GenerateContentConfig(**config_args)

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )

        sources = []
        queries = []
        tokens_used = None

        if response.usage_metadata:
            tokens_used = response.usage_metadata.total_token_count

        if response.candidates:
            cand = response.candidates[0]
            if cand.grounding_metadata:
                gm = cand.grounding_metadata
                if gm.web_search_queries:
                    queries = list(gm.web_search_queries)
                if gm.grounding_chunks:
                    for chunk in gm.grounding_chunks:
                        if chunk.web and chunk.web.uri:
                            sources.append({
                                "title": chunk.web.title or chunk.web.uri,
                                "url": chunk.web.uri,
                            })

        # Deduplicate sources by URL
        seen_urls = set()
        deduped_sources = []
        for s in sources:
            if s["url"] not in seen_urls:
                seen_urls.add(s["url"])
                deduped_sources.append(s)

        return {
            "text": response.text or "",
            "sources": deduped_sources,
            "search_queries": queries,
            "tokens_used": tokens_used,
        }
    except Exception as e:
        logger.error("Grounded Gemini generation failed: %s", e)
        raise
