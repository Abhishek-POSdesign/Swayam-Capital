"""
Unit and API integration tests for Google Cloud Text-to-Speech (TTS) integration.
"""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest

from swayam.ai.tts import (
    DEFAULT_SPEAKING_RATE,
    DEFAULT_VOICE,
    MAX_CHAR_CAP,
    TTSAuthError,
    TTSServiceError,
    synthesize,
    truncate_text_at_sentence_boundary,
)
from swayam.api.main import app

client = TestClient(app)


def test_truncate_text_below_cap():
    text = "This is a short test sentence."
    res, is_trunc = truncate_text_at_sentence_boundary(text, max_chars=100)
    assert res == text
    assert not is_trunc


def test_truncate_text_at_sentence_boundary():
    s1 = "First sentence here. "
    s2 = "Second sentence continues."
    full = s1 + s2
    res, is_trunc = truncate_text_at_sentence_boundary(full, max_chars=len(s1) + 5)
    assert res == s1.strip()
    assert is_trunc is True


def test_synthesize_invalid_voice():
    with pytest.raises(ValueError, match="Unknown voice profile"):
        synthesize("Test", voice_profile="non_existent_voice")


def test_synthesize_empty_text():
    with pytest.raises(ValueError, match="Text content cannot be empty"):
        synthesize("   ")


@patch("swayam.ai.tts.texttospeech.TextToSpeechClient")
def test_tts_speak_post_success(mock_client_cls):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.audio_content = b"\xff\xfb\x90\x44fake_mp3_data"
    mock_client.synthesize_speech.return_value = mock_resp
    mock_client_cls.return_value = mock_client

    resp = client.post(
        "/api/tts/speak",
        json={
            "text": "NIFTY 50 trading partner briefing.",
            "voice_profile": "swayam_calm",
            "speaking_rate": 0.90,
        },
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.headers["x-voice-truncated"] == "false"
    assert resp.content == b"\xff\xfb\x90\x44fake_mp3_data"


@patch("swayam.ai.tts.texttospeech.TextToSpeechClient")
def test_tts_speak_get_success(mock_client_cls):
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.audio_content = b"\xff\xfb\x90\x44get_mp3_data"
    mock_client.synthesize_speech.return_value = mock_resp
    mock_client_cls.return_value = mock_client

    resp = client.get("/api/tts/speak?text=Hello+Trader&voice=swayam_warm&rate=1.0")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.content == b"\xff\xfb\x90\x44get_mp3_data"


@patch("swayam.ai.tts.texttospeech.TextToSpeechClient")
def test_tts_auth_failure_surfaces_503(mock_client_cls):
    mock_client_cls.side_effect = Exception("ADC credentials not found")

    resp = client.post(
        "/api/tts/speak",
        json={"text": "Test speech"},
    )

    assert resp.status_code == 503
    assert "roles/texttospeech.editor" in resp.json()["detail"]


@patch("swayam.ai.tts.texttospeech.TextToSpeechClient")
def test_tts_service_error_surfaces_502(mock_client_cls):
    mock_client = MagicMock()
    mock_client.synthesize_speech.side_effect = Exception("Google Cloud TTS quota exceeded")
    mock_client_cls.return_value = mock_client

    resp = client.post(
        "/api/tts/speak",
        json={"text": "Test speech"},
    )

    assert resp.status_code == 502
    assert "Google Cloud TTS synthesis failed" in resp.json()["detail"]
