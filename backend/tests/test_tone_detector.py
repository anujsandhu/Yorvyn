"""Property-based and unit tests for tone_detector.detect_tone."""
from __future__ import annotations
import pytest
from hypothesis import given, assume, settings as h_settings
from hypothesis import strategies as st

from backend.app.tone_detector import Tone, ToneResult, detect_tone


# ── Property tests ────────────────────────────────────────────────────

@given(text=st.text())
def test_detect_tone_always_valid_tone(text):
    """Property 1: output tone is always a valid Tone enum member.

    Validates: Requirements 1.1
    """
    result = detect_tone(text)
    assert result.tone in Tone


@given(text=st.text())
def test_detect_tone_confidence_bounded(text):
    """Property 2: confidence is always in [0.0, 1.0].

    Validates: Requirements 1.2
    """
    result = detect_tone(text)
    assert 0.0 <= result.confidence <= 1.0


@given(base=st.text(alphabet=st.characters(whitelist_categories=("Ll",))))
def test_gen_z_keywords_monotonic(base):
    """Property 3: appending Gen Z keywords never decreases gen_z_hits.

    Validates: Requirements 1.9, 5.1
    """
    result_base = detect_tone(base)
    result_aug = detect_tone(base + " bro vibe lit")
    assert result_aug.signals.get("gen_z_hits", 0) >= result_base.signals.get("gen_z_hits", 0)


@given(text=st.one_of(st.text(), st.just("")))
def test_detect_tone_never_raises(text):
    """Property 4: detect_tone never raises for any input.

    Validates: Requirements 1.4, 1.5
    """
    try:
        result = detect_tone(text)
        assert result is not None
    except Exception as exc:
        pytest.fail(f"detect_tone raised: {exc}")


# ── Unit tests ────────────────────────────────────────────────────────

def test_empty_string_returns_friendly():
    result = detect_tone("")
    assert result.tone == Tone.FRIENDLY
    assert result.confidence == 0.5
    assert result.signals == {}


def test_gen_z_message():
    result = detect_tone("bro what fragrance hits different for a wedding vibe")
    assert result.tone == Tone.GEN_Z


def test_professional_message():
    result = detect_tone("Kindly suggest a suitable fragrance for a formal wedding.")
    assert result.tone == Tone.PROFESSIONAL


def test_friendly_default():
    result = detect_tone("I want a fresh scent")
    assert result.tone == Tone.FRIENDLY


def test_signals_keys_present():
    result = detect_tone("ngl this is lowkey hard, need something fr")
    assert result.tone == Tone.GEN_Z
    for key in ("gen_z_hits", "formal_hits", "contraction_hits", "avg_word_len", "has_punctuation"):
        assert key in result.signals
