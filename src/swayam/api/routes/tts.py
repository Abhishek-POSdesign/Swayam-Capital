"""
FastAPI route for Google Cloud Text-to-Speech (TTS) synthesis.
Provides Indian English voice synthesis for Swayam Capital AI trading partner.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from swayam.ai.tts import (
    DEFAULT_SPEAKING_RATE,
    DEFAULT_VOICE,
    TTSAuthError,
    TTSServiceError,
    synthesize,
)

router = APIRouter(prefix="/api/tts", tags=["tts"])


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to synthesize into speech")
    voice_profile: Optional[str] = Field(
        DEFAULT_VOICE, description="Voice profile: swayam_calm or swayam_warm"
    )
    speaking_rate: Optional[float] = Field(
        DEFAULT_SPEAKING_RATE, ge=0.5, le=2.0, description="Speech rate between 0.5 and 2.0"
    )


@router.post("/speak")
async def speak_post(req: TTSRequest) -> Response:
    """Synthesize speech from POST JSON body."""
    return _handle_synthesis(
        text=req.text,
        voice_profile=req.voice_profile or DEFAULT_VOICE,
        speaking_rate=req.speaking_rate or DEFAULT_SPEAKING_RATE,
    )


@router.get("/speak")
async def speak_get(
    text: str = Query(..., min_length=1, description="Text to synthesize"),
    voice: Optional[str] = Query(DEFAULT_VOICE, description="Voice profile"),
    rate: Optional[float] = Query(DEFAULT_SPEAKING_RATE, ge=0.5, le=2.0, description="Speech rate"),
) -> Response:
    """Synthesize speech from GET query params for direct media playback."""
    return _handle_synthesis(
        text=text,
        voice_profile=voice or DEFAULT_VOICE,
        speaking_rate=rate or DEFAULT_SPEAKING_RATE,
    )


def _handle_synthesis(text: str, voice_profile: str, speaking_rate: float) -> Response:
    try:
        audio_bytes, is_truncated = synthesize(
            text=text,
            voice_profile=voice_profile,
            speaking_rate=speaking_rate,
        )
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Type": "audio/mpeg",
                "X-Voice-Truncated": "true" if is_truncated else "false",
                "Cache-Control": "public, max-age=3600",
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TTSAuthError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except TTSServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS synthesis unexpected failure: {str(e)}")
