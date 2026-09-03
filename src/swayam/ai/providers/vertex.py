"""
Vertex AI Provider Adapter for Swayam Capital.

Integrates with Google Cloud Vertex AI (Gemini 1.5 Pro / Flash).
Placeholder stub for BUILD-1; raises NotImplementedError on live invocations.
"""

from typing import Any, Generator, Optional
from swayam.ai.adapter import AIProvider


class VertexAIProvider(AIProvider):
    """Google Cloud Vertex AI provider implementation."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-pro") -> None:
        self.api_key = api_key
        self.model = model

    def chat(self, messages: list[dict[str, str]], tools: Optional[list[dict[str, Any]]] = None) -> str:
        raise NotImplementedError("VertexAIProvider chat is an architectural stub for BUILD-1.")

    def structured_query(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("VertexAIProvider structured_query is an architectural stub for BUILD-1.")

    def stream_chat(self, messages: list[dict[str, str]]) -> Generator[str, None, None]:
        raise NotImplementedError("VertexAIProvider stream_chat is an architectural stub for BUILD-1.")
        yield ""
