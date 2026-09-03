"""
Vertex AI Provider Adapter for Swayam Capital.

Implements the AIProvider interface using the google-genai SDK with Vertex AI
(Agent Platform / enterprise mode). Uses Application Default Credentials (ADC)
via the enterprise=True flag — no JSON key files required.

Supports:
- chat()          — single-turn completion
- stream_chat()   — synchronous streaming token generator
- structured_query() — JSON-mode output via response_schema

Error mapping:
- google.api_core.exceptions.ResourceExhausted  → AIRateLimitError
- google.api_core.exceptions.PermissionDenied   → AIPermissionError
- google.api_core.exceptions.NotFound           → ModelNotFoundError
"""

import logging
import time
from typing import Any, Generator, Optional

from swayam.ai.adapter import AIProvider, AIRateLimitError, AIPermissionError, ModelNotFoundError

logger = logging.getLogger(__name__)


class VertexAIProvider(AIProvider):
    """Google Cloud Vertex AI provider using the google-genai SDK (enterprise mode).

    Uses ADC (Application Default Credentials) — no API key required.
    Ensure `gcloud auth application-default login` is active and
    GCP_PROJECT_ID is set to 'swayam-capital'.
    """

    def __init__(
        self,
        project_id: str,
        location: str,
        model: str = "gemini-2.5-pro",
        max_output_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> None:
        """Initialise the Vertex AI provider.

        Args:
            project_id: GCP project ID (e.g. 'swayam-capital').
            location: GCP region (e.g. 'asia-south1').
            model: Gemini model ID (e.g. 'gemini-3.1-pro-preview').
            max_output_tokens: Maximum tokens in the generated response.
            temperature: Sampling temperature (0.0–1.0).
        """
        self.project_id = project_id
        self.location = location
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature

        # Lazy-initialise the client (avoids import cost at module load)
        self._client: Any = None

    def _get_client(self) -> Any:
        """Returns the google-genai Client, creating it on first use."""
        if self._client is None:
            try:
                from google import genai  # type: ignore
                self._client = genai.Client(
                    enterprise=True,
                    project=self.project_id,
                    location=self.location,
                )
            except ImportError as exc:
                raise RuntimeError(
                    "google-genai package is not installed. "
                    "Run: .venv\\Scripts\\pip.exe install google-genai>=1.0.0"
                ) from exc
        return self._client

    def _build_config(self, system_instruction: Optional[str] = None) -> Any:
        """Builds a GenerateContentConfig with standard generation parameters."""
        from google.genai import types  # type: ignore
        kwargs: dict[str, Any] = {
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
        }
        if system_instruction:
            kwargs["system_instruction"] = system_instruction
        return types.GenerateContentConfig(**kwargs)

    def _extract_system_and_turns(
        self, messages: list[dict[str, str]]
    ) -> tuple[Optional[str], list[Any]]:
        """Splits messages into a system instruction and user/assistant turns.

        The google-genai SDK accepts system_instruction separately from
        the conversation turns. The first 'system' role message is extracted;
        all subsequent messages become the conversation content list.

        Returns:
            (system_instruction_text, [Content, ...])
        """
        from google.genai import types  # type: ignore
        system_text: Optional[str] = None
        contents: list[Any] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                # Only the first system message is used as system_instruction
                if system_text is None:
                    system_text = content
                # Additional system messages are silently skipped (shouldn't occur)
            elif role == "user":
                contents.append(
                    types.Content(role="user", parts=[types.Part.from_text(text=content)])
                )
            elif role == "assistant":
                contents.append(
                    types.Content(role="model", parts=[types.Part.from_text(text=content)])
                )

        return system_text, contents

    def _map_api_error(self, exc: Exception) -> Exception:
        """Maps google.api_core exceptions to Swayam AI exceptions."""
        try:
            from google.api_core import exceptions as gex  # type: ignore
            if isinstance(exc, gex.ResourceExhausted):
                return AIRateLimitError(
                    f"Vertex AI quota exceeded for model '{self.model}'. "
                    f"Retry in ~60 seconds. Detail: {exc}"
                )
            if isinstance(exc, gex.PermissionDenied):
                return AIPermissionError(
                    f"Vertex AI permission denied for model '{self.model}'. "
                    "Check: (1) ADC active (`gcloud auth application-default login`), "
                    "(2) roles/aiplatform.user granted, (3) Vertex AI API enabled. "
                    f"See docs/gcp_setup.md. Detail: {exc}"
                )
            if isinstance(exc, gex.NotFound):
                return ModelNotFoundError(
                    f"Vertex AI model '{self.model}' not found or deprecated. "
                    f"Detail: {exc}"
                )
        except ImportError:
            pass
        return exc

    # -------------------------------------------------------------------------
    # Public AIProvider interface
    # -------------------------------------------------------------------------

    def chat(
        self,
        messages: list[dict[str, str]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> str:
        """Sends messages and returns the full response text.

        Args:
            messages: List of {'role': ..., 'content': ...} dicts.
            tools: Unused (reserved for future function-calling support).

        Returns:
            str: Complete assistant response text.

        Raises:
            AIRateLimitError: Vertex quota exceeded.
            AIPermissionError: ADC or IAM issue.
            ModelNotFoundError: Model ID not recognised.
        """
        client = self._get_client()
        system_text, contents = self._extract_system_and_turns(messages)
        config = self._build_config(system_instruction=system_text)

        try:
            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            return response.text or ""
        except Exception as exc:
            raise self._map_api_error(exc) from exc

    def stream_chat(self, messages: list[dict[str, str]]) -> Generator[str, None, None]:
        """Streams conversation tokens as they are generated.

        Args:
            messages: List of {'role': ..., 'content': ...} dicts.

        Yields:
            str: Token delta chunks as they arrive from Vertex AI.

        Raises:
            AIRateLimitError: Vertex quota exceeded.
            AIPermissionError: ADC or IAM issue.
            ModelNotFoundError: Model ID not recognised.
        """
        client = self._get_client()
        system_text, contents = self._extract_system_and_turns(messages)
        config = self._build_config(system_instruction=system_text)

        try:
            for chunk in client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config,
            ):
                delta = chunk.text
                if delta:
                    yield delta
        except Exception as exc:
            raise self._map_api_error(exc) from exc

    def structured_query(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Queries the model and returns structured JSON output.

        Uses Vertex AI's response_schema capability to enforce JSON mode.

        Args:
            prompt: Instruction text.
            schema: JSON schema dict describing the required output structure.

        Returns:
            dict: Parsed JSON payload matching the schema.

        Raises:
            AIRateLimitError, AIPermissionError, ModelNotFoundError: as above.
            ValueError: If the response cannot be parsed as JSON.
        """
        import json
        from google.genai import types  # type: ignore

        client = self._get_client()
        config = types.GenerateContentConfig(
            max_output_tokens=self.max_output_tokens,
            temperature=0.0,  # deterministic for structured output
            response_mime_type="application/json",
            response_schema=schema,
        )
        contents = [
            types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
        ]

        try:
            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            raw = response.text or "{}"
            return json.loads(raw)
        except Exception as exc:
            mapped = self._map_api_error(exc)
            if mapped is not exc:
                raise mapped from exc
            raise ValueError(
                f"VertexAI structured_query failed for model '{self.model}': {exc}"
            ) from exc

    def get_usage_metadata(self, response: Any) -> dict[str, int]:
        """Extracts token usage from a Vertex AI response object.

        Args:
            response: The GenerateContentResponse object.

        Returns:
            dict with 'input_tokens' and 'output_tokens'.
        """
        try:
            meta = response.usage_metadata
            return {
                "input_tokens": meta.prompt_token_count or 0,
                "output_tokens": meta.candidates_token_count or 0,
            }
        except Exception:
            return {"input_tokens": 0, "output_tokens": 0}
