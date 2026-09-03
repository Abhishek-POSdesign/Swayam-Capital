"""
AI Provider Factory for Swayam Capital.

Instantiates and configures the appropriate AI provider adapter based on
the `AI_PROVIDER` environment setting (e.g. 'vertex', 'openrouter', 'direct').
Enables zero-code provider switching via configuration.
"""

from typing import Optional
from swayam.ai.adapter import AIProvider
from swayam.ai.providers.direct import DirectAPIProvider
from swayam.ai.providers.openrouter import OpenRouterProvider
from swayam.ai.providers.vertex import VertexAIProvider
from swayam.config import settings


def get_ai_provider(
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
) -> AIProvider:
    """Factory function returning the configured AI provider adapter.

    Args:
        provider_name: Optional explicit provider override ('vertex', 'openrouter', 'direct').
                       If None, resolves from `settings.ai_provider`.
        model: Optional model override. If None, resolves from settings based on provider.

    Returns:
        AIProvider: Configured provider instance.

    Raises:
        ValueError: If an unrecognized provider name is specified.
    """
    resolved_name = (provider_name or settings.ai_provider).strip().lower()
    resolved_model = model or settings.ai_model_primary

    if resolved_name == "vertex":
        return VertexAIProvider(
            project_id=settings.gcp_project_id,
            location=settings.gcp_region,
            model=resolved_model,
            max_output_tokens=settings.ai_max_output_tokens,
            temperature=settings.ai_temperature,
        )
    elif resolved_name == "openrouter":
        return OpenRouterProvider(api_key=settings.ai_api_key, model=resolved_model)
    elif resolved_name in ("direct", "anthropic", "openai", "gemini"):
        return DirectAPIProvider(api_key=settings.ai_api_key, model=resolved_model)
    else:
        raise ValueError(
            f"Unsupported AI provider: '{resolved_name}'. Supported: 'vertex', 'openrouter', 'direct'."
        )
