"""
AI Integration Module for Swayam Capital.

Implements the multi-provider adapter architecture supporting Vertex AI, OpenRouter,
and direct LLM APIs (Anthropic, OpenAI, Google). Built on the core principle from
Abhishek's POS design-bible: AI is an advisory partner and explanation collaborator,
not an unsupervised execution authority.
"""

from swayam.ai.adapter import AIProvider
from swayam.ai.factory import get_ai_provider

__all__ = ["AIProvider", "get_ai_provider"]
