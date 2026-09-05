"""
Gemini Multimodal Client Helper for Swayam Capital.
Constructs message payloads with inline_data for Vertex AI / Gemini API.
"""

from typing import Any, Optional


def create_image_part(image_bytes: bytes, mime_type: str) -> Any:
    """Constructs a Part with inline_data from raw bytes and MIME type."""
    from google.genai import types  # type: ignore
    return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)


def build_multimodal_turn(
    text: str,
    image_bytes: Optional[bytes] = None,
    image_mime: Optional[str] = None,
) -> dict[str, Any]:
    """Builds a user message dictionary supporting both text and optional image payload."""
    payload: dict[str, Any] = {
        "role": "user",
        "content": text,
    }
    if image_bytes and image_mime:
        payload["image_bytes"] = image_bytes
        payload["image_mime"] = image_mime
    return payload
