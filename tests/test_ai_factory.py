"""
Unit tests for Swayam Capital AI Factory & Provider Adapters.
"""

import pytest
from swayam.ai.factory import get_ai_provider
from swayam.ai.providers.direct import DirectAPIProvider
from swayam.ai.providers.openrouter import OpenRouterProvider
from swayam.ai.providers.vertex import VertexAIProvider


def test_ai_factory_resolves_vertex_provider() -> None:
    provider = get_ai_provider("vertex")
    assert isinstance(provider, VertexAIProvider)


def test_ai_factory_resolves_openrouter_provider() -> None:
    provider = get_ai_provider("openrouter")
    assert isinstance(provider, OpenRouterProvider)


def test_ai_factory_resolves_direct_provider() -> None:
    provider = get_ai_provider("direct")
    assert isinstance(provider, DirectAPIProvider)


def test_ai_factory_raises_on_unsupported_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported AI provider"):
        get_ai_provider("non_existent_provider")
