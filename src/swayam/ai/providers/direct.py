"""
Direct API Provider Adapter for Swayam Capital.

Integrates with direct provider endpoints (Anthropic Claude, OpenAI, or Gemini).
Placeholder stub for BUILD-1; raises NotImplementedError on live invocations.
"""

from typing import Any, Generator, Optional
from swayam.ai.adapter import AIProvider


class DirectAPIProvider(AIProvider):
    """Direct API provider implementation."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022") -> None:
        self.api_key = api_key
        self.model = model

    def chat(self, messages: list[dict[str, str]], tools: Optional[list[dict[str, Any]]] = None) -> str:
        raise NotImplementedError("DirectAPIProvider chat is an architectural stub for BUILD-1.")

    def structured_query(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("DirectAPIProvider structured_query is an architectural stub for BUILD-1.")

    def stream_chat(self, messages: list[dict[str, str]]) -> Generator[str, None, None]:
        raise NotImplementedError("DirectAPIProvider stream_chat is an architectural stub for BUILD-1.")
        yield ""
