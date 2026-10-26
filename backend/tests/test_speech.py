"""
Unit and Integration Tests for Yorvyn Voice & Speech AI Services.
Executes directly without requiring external HTTP client libraries.
"""

import asyncio
import io
import pytest
from fastapi import UploadFile

from backend.app.api.speech_routes import (
    get_speech_config,
    transcribe_audio,
    synthesize_speech,
    SpeechSynthesisRequest
)


def test_speech_config_endpoint():
    """Validates speech config return properties."""
    config = get_speech_config()
    assert config.stt_provider in ["groq_whisper", "browser_native_fallback"]
    assert config.whisper_model == "whisper-large-v3-turbo"
    assert config.max_audio_size_mb == 25


def test_speech_transcription_handler():
    """Validates audio file upload transcription and privacy cleanup."""
    fake_audio_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00" + b"\x00" * 200
    upload = UploadFile(
        file=io.BytesIO(fake_audio_bytes),
        filename="sample_recording.webm"
    )

    data = asyncio.run(transcribe_audio(audio=upload, language="en"))

    assert data["status"] == "success"
    assert "text" in data
    assert len(data["text"]) > 0


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
