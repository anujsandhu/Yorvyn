"""
Tone Detector — classifies a user message into one of three communication styles.

Tones: PROFESSIONAL, FRIENDLY, GEN_Z

This module is stateless and performs no external I/O. It is designed to be
called synchronously on every chat turn with sub-millisecond latency.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Tone(str, Enum):
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"
    GEN_Z = "gen_z"


@dataclass(frozen=True)
class ToneResult:
    tone: Tone
    confidence: float
    signals: dict


# ---------------------------------------------------------------------------
# Keyword / phrase sets
# ---------------------------------------------------------------------------

GEN_Z_KEYWORDS: frozenset[str] = frozenset({
    "bro", "bruh", "vibe", "vibes", "aura", "lit", "lowkey", "highkey",
    "ngl", "tbh", "fr", "frfr", "slay", "bussin",
    "rizz", "based", "mid", "goated", "fire", "slaps",
    "deadass", "periodt", "bestie", "fam", "sis", "bffr",
})

GEN_Z_PHRASES: frozenset[str] = frozenset({
    "no cap", "hits different", "main character", "understood the assignment",
    "rent free", "iykyk", "W rizz", "not gonna lie",
})

FORMAL_KEYWORDS: frozenset[str] = frozenset({
    "kindly", "please", "would", "could", "shall", "regarding",
    "suitable", "appropriate", "recommend", "suggest", "prefer",
    "occasion", "formal", "professional", "require", "request",
    "assist", "provide", "inform", "advise", "seeking",
    "furthermore", "however", "therefore", "hence", "thus",
})

CASUAL_CONTRACTIONS: frozenset[str] = frozenset({
    "i'm", "i've", "i'd", "i'll", "don't", "can't", "won't",
    "it's", "that's", "what's", "gonna", "wanna", "gotta",
    "lemme", "kinda", "sorta", "yeah", "yep", "nope",
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_tone(text: str) -> ToneResult:
    """
    Classify the communication style of *text*.

    Args:
        text: The raw user message (latest turn only).

    Returns:
        ToneResult with detected tone, confidence score, and signal breakdown.

    Guarantees:
        - Always returns a valid ToneResult (never raises).
        - Defaults to FRIENDLY when signals are ambiguous.
        - Confidence >= 0.5 means the tone was clearly signalled.
    """
    # Guard: empty / None
    if not text or not text.strip():
        return ToneResult(tone=Tone.FRIENDLY, confidence=0.5, signals={})

    lowered = text.lower()
    # Tokenise: split on whitespace and punctuation
    import re
    tokens = re.findall(r"[a-z0-9']+", lowered)

    # Score Gen Z — single tokens
    gen_z_hits = sum(1 for t in tokens if t in GEN_Z_KEYWORDS)
    # Score Gen Z — multi-word phrases (weight 2 extra each)
    for phrase in GEN_Z_PHRASES:
        if phrase in lowered:
            gen_z_hits += 2

    # Score Formal
    formal_hits = sum(1 for t in tokens if t in FORMAL_KEYWORDS)

    # Linguistic signals
    avg_word_len = sum(len(t) for t in tokens) / len(tokens) if tokens else 0.0
    contraction_hits = sum(1 for t in tokens if t in CASUAL_CONTRACTIONS)
    has_punctuation = 1 if text.rstrip()[-1:] in {'.', '?', '!'} else 0

    # Composite scores
    score_gen_z = gen_z_hits * 3.0
    score_formal = (
        formal_hits * 2.5
        + (1.5 if avg_word_len > 5.5 else 0.0)
        + (1.0 if has_punctuation else 0.0)
        - contraction_hits * 0.5
    )
    score_friendly = (
        2.0
        + contraction_hits * 0.8
        - formal_hits * 0.5
        - gen_z_hits * 0.3
    )

    scores = {
        Tone.PROFESSIONAL: score_formal,
        Tone.FRIENDLY: score_friendly,
        Tone.GEN_Z: score_gen_z,
    }

    # argmax — default to FRIENDLY on ties
    winner = max(scores, key=lambda t: (scores[t], t == Tone.FRIENDLY))

    total = sum(max(0.0, s) for s in scores.values()) + 1e-6
    confidence = min(1.0, max(0.0, scores[winner] / total))

    signals = {
        "gen_z_hits": gen_z_hits,
        "formal_hits": formal_hits,
        "contraction_hits": contraction_hits,
        "avg_word_len": round(avg_word_len, 2),
        "has_punctuation": has_punctuation,
    }

    return ToneResult(tone=winner, confidence=confidence, signals=signals)
