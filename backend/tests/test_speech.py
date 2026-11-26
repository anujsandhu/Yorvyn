"""
Unit and Integration Tests for Yorvyn Voice & Speech AI Services.
Executes directly without requiring external HTTP client libraries.
"""

import asyncio
import io
import pytest
from fastapi import HTTPException, UploadFile

from backend.app.api.speech_routes import (
    get_speech_config,
    transcribe_audio,
    synthesize_speech,
    SpeechSynthesisRequest
)
from backend.app.core.settings import settings


def test_speech_config_endpoint():
    """Validates speech config return properties."""
    config = get_speech_config()
    assert config.stt_provider in ["groq_whisper", "browser_native_fallback"]
    assert config.whisper_model == "whisper-large-v3-turbo"
    assert config.max_audio_size_mb == 25


def test_speech_transcription_handler(monkeypatch):
    """Validates audio transcription fails closed when unconfigured and succeeds with Groq."""
    fake_audio_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00" + b"\x00" * 200

    # 1. Fail closed (503) when Groq key is absent
    monkeypatch.setattr(settings, "groq_api_key", "")
    upload_unconf = UploadFile(file=io.BytesIO(fake_audio_bytes), filename="sample_recording.webm")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(transcribe_audio(audio=upload_unconf, language="en"))
    assert exc_info.value.status_code == 503

    # 2. Succeed when Groq STT responds cleanly
    class _MockResp:
        status_code = 200
        def json(self):
            return {"text": "Recommend a dark minimalist jacket"}

    monkeypatch.setattr(settings, "groq_api_key", "gsk_test_mock_key")
    monkeypatch.setattr("backend.app.api.speech_routes.requests.post", lambda *a, **kw: _MockResp())
    upload_ok = UploadFile(file=io.BytesIO(fake_audio_bytes), filename="sample_recording.webm")
    data = asyncio.run(transcribe_audio(audio=upload_ok, language="en"))

    assert data["status"] == "success"
    assert data["provider"] == "groq_whisper_v3"
    assert data["text"] == "Recommend a dark minimalist jacket"


def test_speech_synthesize_handler():
    """Validates text-to-speech parameter synthesis."""
    req = SpeechSynthesisRequest(
        text="Your **Quiet Luxury** look is ready.",
        voice="en-US-Standard",
        speed=1.0
    )
    data = synthesize_speech(req)

    assert data["status"] == "ready"
    assert "**" not in data["text"]  # Verify markdown cleanup for audio clarity
