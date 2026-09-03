"""
Tests for VertexAIProvider.

Mocks the google-genai Client so no real API calls are made.
Verifies: chat(), stream_chat(), structured_query(),
error mapping (ResourceExhausted → AIRateLimitError, etc.)
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# Helpers to build mock response objects
# ---------------------------------------------------------------------------

def _mock_generate_response(text: str):
    """Creates a mock GenerateContentResponse with .text attribute."""
    resp = MagicMock()
    resp.text = text
    resp.usage_metadata = MagicMock()
    resp.usage_metadata.prompt_token_count = 100
    resp.usage_metadata.candidates_token_count = 50
    return resp


def _mock_stream_chunks(texts: list[str]):
    """Creates mock streaming chunk objects."""
    chunks = []
    for t in texts:
        c = MagicMock()
        c.text = t
        chunks.append(c)
    return chunks


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVertexAIProviderChat:
    def test_chat_returns_response_text(self):
        """chat() should return the text from the Vertex API response."""
        with patch("swayam.ai.providers.vertex.VertexAIProvider._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = _mock_generate_response("Test response")
            mock_get_client.return_value = mock_client

            from swayam.ai.providers.vertex import VertexAIProvider
            provider = VertexAIProvider(project_id="swayam-capital", location="asia-south1")
            result = provider.chat([{"role": "user", "content": "Hello"}])

        assert result == "Test response"

    def test_chat_extracts_system_instruction(self):
        """chat() should pass system messages as system_instruction, not in contents."""
        with patch("swayam.ai.providers.vertex.VertexAIProvider._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = _mock_generate_response("ok")
            mock_get_client.return_value = mock_client

            from swayam.ai.providers.vertex import VertexAIProvider
            provider = VertexAIProvider(project_id="p", location="l")
            provider.chat([
                {"role": "system", "content": "You are a trading partner."},
                {"role": "user", "content": "Should I trade?"},
            ])

            call_kwargs = mock_client.models.generate_content.call_args[1]
            config = call_kwargs["config"]
            # System instruction should be set on config
            assert config.system_instruction == "You are a trading partner."
            # Only the user message should be in contents
            contents = call_kwargs["contents"]
            assert len(contents) == 1
            assert contents[0].role == "user"

    def test_chat_maps_resource_exhausted_to_rate_limit_error(self):
        """ResourceExhausted from Vertex should raise AIRateLimitError."""
        with patch("swayam.ai.providers.vertex.VertexAIProvider._get_client") as mock_get_client:
            try:
                from google.api_core.exceptions import ResourceExhausted
            except ImportError:
                pytest.skip("google-api-core not installed")

            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = ResourceExhausted("quota exceeded")
            mock_get_client.return_value = mock_client

            from swayam.ai.providers.vertex import VertexAIProvider
            from swayam.ai.adapter import AIRateLimitError

            provider = VertexAIProvider(project_id="p", location="l")
            with pytest.raises(AIRateLimitError):
                provider.chat([{"role": "user", "content": "test"}])

    def test_chat_maps_permission_denied_to_ai_permission_error(self):
        """PermissionDenied from Vertex should raise AIPermissionError."""
        with patch("swayam.ai.providers.vertex.VertexAIProvider._get_client") as mock_get_client:
            try:
                from google.api_core.exceptions import PermissionDenied
            except ImportError:
                pytest.skip("google-api-core not installed")

            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = PermissionDenied("forbidden")
            mock_get_client.return_value = mock_client

            from swayam.ai.providers.vertex import VertexAIProvider
            from swayam.ai.adapter import AIPermissionError

            provider = VertexAIProvider(project_id="p", location="l")
            with pytest.raises(AIPermissionError):
                provider.chat([{"role": "user", "content": "test"}])

    def test_chat_maps_not_found_to_model_not_found_error(self):
        """NotFound from Vertex should raise ModelNotFoundError."""
        with patch("swayam.ai.providers.vertex.VertexAIProvider._get_client") as mock_get_client:
            try:
                from google.api_core.exceptions import NotFound
            except ImportError:
                pytest.skip("google-api-core not installed")

            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = NotFound("model gone")
            mock_get_client.return_value = mock_client

            from swayam.ai.providers.vertex import VertexAIProvider
            from swayam.ai.adapter import ModelNotFoundError

            provider = VertexAIProvider(project_id="p", location="l")
            with pytest.raises(ModelNotFoundError):
                provider.chat([{"role": "user", "content": "test"}])


class TestVertexAIProviderStreamChat:
    def test_stream_chat_yields_deltas(self):
        """stream_chat() should yield each text chunk from the streaming API."""
        with patch("swayam.ai.providers.vertex.VertexAIProvider._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.models.generate_content_stream.return_value = iter(
                _mock_stream_chunks(["Hello", " world", "!"])
            )
            mock_get_client.return_value = mock_client

            from swayam.ai.providers.vertex import VertexAIProvider
            provider = VertexAIProvider(project_id="p", location="l")
            result = list(provider.stream_chat([{"role": "user", "content": "hi"}]))

        assert result == ["Hello", " world", "!"]

    def test_stream_chat_skips_empty_chunks(self):
        """stream_chat() should not yield empty text chunks."""
        with patch("swayam.ai.providers.vertex.VertexAIProvider._get_client") as mock_get_client:
            mock_client = MagicMock()
            chunks = _mock_stream_chunks(["chunk1", "", "chunk3"])
            chunks[1].text = ""  # Explicitly empty
            mock_client.models.generate_content_stream.return_value = iter(chunks)
            mock_get_client.return_value = mock_client

            from swayam.ai.providers.vertex import VertexAIProvider
            provider = VertexAIProvider(project_id="p", location="l")
            result = list(provider.stream_chat([{"role": "user", "content": "hi"}]))

        assert result == ["chunk1", "chunk3"]

    def test_stream_chat_propagates_rate_limit_error(self):
        """stream_chat() should raise AIRateLimitError on quota exceeded."""
        with patch("swayam.ai.providers.vertex.VertexAIProvider._get_client") as mock_get_client:
            try:
                from google.api_core.exceptions import ResourceExhausted
            except ImportError:
                pytest.skip("google-api-core not installed")

            mock_client = MagicMock()
            mock_client.models.generate_content_stream.side_effect = ResourceExhausted("quota")
            mock_get_client.return_value = mock_client

            from swayam.ai.providers.vertex import VertexAIProvider
            from swayam.ai.adapter import AIRateLimitError

            provider = VertexAIProvider(project_id="p", location="l")
            with pytest.raises(AIRateLimitError):
                list(provider.stream_chat([{"role": "user", "content": "test"}]))


class TestVertexAIProviderStructuredQuery:
    def test_structured_query_returns_parsed_json(self):
        """structured_query() should parse the JSON text response."""
        with patch("swayam.ai.providers.vertex.VertexAIProvider._get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = _mock_generate_response(
                '{"verdict": "proceed", "reason": "R:R meets target"}'
            )
            mock_get_client.return_value = mock_client

            from swayam.ai.providers.vertex import VertexAIProvider
            provider = VertexAIProvider(project_id="p", location="l")
            schema = {"type": "object", "properties": {"verdict": {"type": "string"}}}
            result = provider.structured_query("Analyse this trade.", schema)

        assert result == {"verdict": "proceed", "reason": "R:R meets target"}
