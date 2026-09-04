"""
Text-to-Speech engine using Google Cloud Text-to-Speech API.
Authenticated strictly via Application Default Credentials (ADC).
Voice profiles:
- swayam_calm: en-IN-Neural2-B (male, Indian English) — DEFAULT
- swayam_warm: en-IN-Neural2-A (female, Indian English)
"""

import re
from typing import Tuple

try:
    from google.cloud import texttospeech
    _TTS_AVAILABLE = True
except ImportError:
    _TTS_AVAILABLE = False
    texttospeech = None

VOICE_PROFILES = {
    "swayam_calm": {
        "language_code": "en-IN",
        "name": "en-IN-Neural2-B",
        "ssml_gender": "MALE",
    },
    "swayam_warm": {
        "language_code": "en-IN",
        "name": "en-IN-Neural2-A",
        "ssml_gender": "FEMALE",
    },
}

DEFAULT_VOICE = "swayam_calm"
DEFAULT_SPEAKING_RATE = 0.90
MAX_CHAR_CAP = 3000


class TTSAuthError(RuntimeError):
    """Raised when Google Cloud TTS client cannot authenticate via ADC."""
    pass


class TTSServiceError(RuntimeError):
    """Raised when TTS API request fails."""
    pass


def truncate_text_at_sentence_boundary(text: str, max_chars: int = MAX_CHAR_CAP) -> Tuple[str, bool]:
    """
    Truncate text to max_chars, breaking cleanly at sentence boundary if possible.
    Returns (processed_text, is_truncated).
    """
    if len(text) <= max_chars:
        return text, False

    truncated = text[:max_chars]
    # Look for last sentence boundary (. ! ? or newline)
    match = list(re.finditer(r"[.!?\n]\s*", truncated))
    if match:
        last_boundary = match[-1].end()
        if last_boundary > max_chars // 2:
            return truncated[:last_boundary].strip(), True

    # Fallback to word boundary
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        return truncated[:last_space].strip() + "...", True

    return truncated.strip() + "...", True


def synthesize(
    text: str,
    voice_profile: str = DEFAULT_VOICE,
    speaking_rate: float = DEFAULT_SPEAKING_RATE,
) -> Tuple[bytes, bool]:
    """
    Synthesize text into MP3 audio bytes using Google Cloud TTS.
    Returns (audio_bytes, is_truncated).
    """
    if not _TTS_AVAILABLE:
        raise TTSServiceError(
            "google-cloud-texttospeech library is not available. Please install it in dependencies."
        )

    if voice_profile not in VOICE_PROFILES:
        raise ValueError(
            f"Unknown voice profile '{voice_profile}'. Available: {list(VOICE_PROFILES.keys())}"
        )

    clamped_rate = max(0.5, min(2.0, float(speaking_rate)))
    processed_text, is_truncated = truncate_text_at_sentence_boundary(text, MAX_CHAR_CAP)

    if not processed_text.strip():
        raise ValueError("Text content cannot be empty for speech synthesis.")

    try:
        client = texttospeech.TextToSpeechClient()
    except Exception as e:
        raise TTSAuthError(
            f"Google Cloud TTS authentication failed. Check ADC credentials and verify Cloud Run service account has roles/texttospeech.editor: {e}"
        ) from e

    voice_cfg = VOICE_PROFILES[voice_profile]
    gender_enum = getattr(
        texttospeech.SsmlVoiceGender,
        voice_cfg["ssml_gender"],
        texttospeech.SsmlVoiceGender.NEUTRAL,
    )

    synthesis_input = texttospeech.SynthesisInput(text=processed_text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=voice_cfg["language_code"],
        name=voice_cfg["name"],
        ssml_gender=gender_enum,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=clamped_rate,
    )

    try:
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )
        return response.audio_content, is_truncated
    except Exception as e:
        # Check for authentication/permission issues in API call
        err_msg = str(e)
        if "403" in err_msg or "PermissionDenied" in err_msg or "Unauthenticated" in err_msg:
            raise TTSAuthError(
                f"Google Cloud TTS permission denied. Verify Cloud Run service account has roles/texttospeech.editor: {err_msg}"
            ) from e
        raise TTSServiceError(f"Google Cloud TTS synthesis failed: {err_msg}") from e
