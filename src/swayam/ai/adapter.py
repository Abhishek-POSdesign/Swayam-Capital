"""
Abstract AI Provider Interface for Swayam Capital.

Defines the contract for all AI model adapters (Vertex AI, OpenRouter, Direct API).
Enforces a consistent interface across chat generation, structured analysis, and
visual annotation extensions, adhering to Abhishek's modular POS design standards.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Generator, Optional


class AIProvider(ABC):
    """Abstract base class establishing the standard Swayam AI Provider contract."""

    @abstractmethod
    def chat(self, messages: list[dict[str, str]], tools: Optional[list[dict[str, Any]]] = None) -> str:
        """Sends a multi-turn conversation and returns the AI's response text.

        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            tools: Optional tool definitions for function calling.

        Returns:
            str: Assistant response.
        """
        pass

    @abstractmethod
    def structured_query(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Queries the model and enforces structured JSON output adhering to a schema.

        Args:
            prompt: User instructions or context.
            schema: JSON schema dict specifying required output structure.

        Returns:
            dict[str, Any]: Parsed JSON payload adhering to schema.
        """
        pass

    @abstractmethod
    def stream_chat(self, messages: list[dict[str, str]]) -> Generator[str, None, None]:
        """Streams conversation tokens as they are generated.

        Args:
            messages: List of message dictionaries.

        Yields:
            str: Token fragments.
        """
        pass

    def generate_annotated_chart(
        self,
        context: str,
        spot_history: list[dict[str, Any]],
        annotations: list[dict[str, Any]],
    ) -> Path:
        """Generates an annotated chart image on the server (reserved hook per Addendum #4).

        Args:
            context: Strategy or setup context.
            spot_history: Historical price series.
            annotations: Key levels, labels, and support/resistance zones.

        Returns:
            Path: File path to generated PNG image.
        """
        raise NotImplementedError("Server-side annotated chart generation is deferred past BUILD-1.")
