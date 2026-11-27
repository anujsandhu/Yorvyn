"""
Animation Intent Data Contract for Yorvyn Conversational Human Avatar.
Defines strongly typed, validated animation intent schemas produced by the AI reasoning engine
and consumed by the 3D performance controller.
Enforces a strict allowlist to guarantee that the LLM cannot execute arbitrary bone transforms.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
try:
    from pydantic import field_validator
    def custom_validator(*fields):
        return field_validator(*fields, mode="before")
except ImportError:
    from pydantic import validator as field_validator
    def custom_validator(*fields):
        return field_validator(*fields)

ALLOWED_EMOTIONS = {
    "neutral",
    "happy",
    "thinking",
    "curious",
    "surprised",
    "confused",
    "empathetic",
    "serious",
}

ALLOWED_GESTURES = {
    "open_palm",
    "explain",
    "emphasis",
    "small_nod",
    "head_tilt",
    "thinking",
    "point",
    "greeting",
    "listening",
    "idle_breathing",
    "speaking_posture",
}

ALLOWED_GAZES = {
    "user",
    "camera",
    "thoughtful_away",
    "garment",
    "down",
}

ALLOWED_STATES = {
    "speaking",
    "listening",
    "thinking",
    "idle",
}


class VisemeTiming(BaseModel):
    """Timestamped viseme cue for lip synchronization."""
    viseme: str = Field(..., description="Oculus/ARKit viseme identifier (e.g. viseme_aa, viseme_O, viseme_PP).")
    start_time: float = Field(..., ge=0.0, description="Start offset in seconds from audio commencement.")
    duration: float = Field(..., gt=0.0, description="Duration in seconds.")
    weight: float = Field(1.0, ge=0.0, le=1.0, description="Target blendshape influence.")


class AnimationIntent(BaseModel):
    """
    Validated animation intent emitted by the LLM / stylist intelligence service.
    Contains emotional expression, gaze target, gesture commands, and timing parameters.
    """
    spoken_response: str = Field(..., description="Spoken text to be synthesized or displayed.")
    emotion: str = Field("neutral", description="Target emotional state on strict allowlist.")
    expression_intensity: float = Field(0.8, ge=0.0, le=1.0, description="Intensity of facial expression blend.")
    gaze_target: str = Field("user", description="Gaze target: user, camera, thoughtful_away, garment, down.")
    gesture_id: str = Field("open_palm", description="Identifier of arm/body gesture on strict allowlist.")
    gesture_timing: float = Field(0.0, ge=0.0, description="Offset in seconds from start of speech for gesture trigger.")
    speaking_state: str = Field("speaking", description="Overall performance state: speaking, listening, thinking, idle.")
    conversational_emphasis: List[str] = Field(default_factory=list, description="Key words requiring head nod or gesture emphasis.")
    viseme_cues: List[VisemeTiming] = Field(default_factory=list, description="Optional phoneme/viseme timestamps.")

    @custom_validator("emotion")
    def validate_emotion(cls, v: str) -> str:
        clean = v.lower().strip()
        if clean not in ALLOWED_EMOTIONS:
            return "neutral"
        return clean

    @custom_validator("gesture_id")
    def validate_gesture(cls, v: str) -> str:
        clean = v.lower().strip()
        if clean not in ALLOWED_GESTURES:
            return "open_palm"
        return clean

    @custom_validator("gaze_target")
    def validate_gaze(cls, v: str) -> str:
        clean = v.lower().strip()
        if clean not in ALLOWED_GAZES:
            return "user"
        return clean

    @custom_validator("speaking_state")
    def validate_speaking_state(cls, v: str) -> str:
        clean = v.lower().strip()
        if clean not in ALLOWED_STATES:
            return "speaking"
        return clean

    @classmethod
    def infer_from_text(cls, text: str) -> "AnimationIntent":
        """
        Derives high-fidelity animation intent and viseme cues from text response.
        Detects emotional cues, gesture triggers, and generates approximate speech timing.
        """
        lower = text.lower()
        
        # 1. Detect emotion
        emotion = "neutral"
        if any(w in lower for w in ["great", "perfect", "love", "beautiful", "chic", "wonderful", "impeccable", "delightful"]):
            emotion = "happy"
        elif any(w in lower for w in ["let's see", "consider", "ponder", "balance", "perhaps", "evaluate"]):
            emotion = "thinking"
        elif any(w in lower for w in ["what", "how", "curious", "explore", "tell me"]):
            emotion = "curious"
        elif any(w in lower for w in ["wow", "stunning", "bold", "surprise"]):
            emotion = "surprised"
        elif any(w in lower for w in ["apologize", "understand", "completely", "comfort"]):
            emotion = "empathetic"

        # 2. Detect gesture
        gesture = "open_palm"
        if any(w in lower for w in ["hello", "hi", "welcome", "greetings"]):
            gesture = "greeting"
        elif any(w in lower for w in ["recommend", "tailored", "ensemble", "outfit", "look at"]):
            gesture = "explain"
        elif any(w in lower for w in ["crucial", "essential", "must", "strictly", "important"]):
            gesture = "emphasis"
        elif any(w in lower for w in ["this jacket", "these trousers", "the shirt", "here"]):
            gesture = "point"
        elif emotion == "thinking":
            gesture = "thinking"

        # 3. Detect gaze
        gaze = "user"
        if emotion == "thinking":
            gaze = "thoughtful_away"
        elif gesture == "point":
            gaze = "garment"

        # 4. Generate timestamped viseme cues from words
        words = text.split()
        viseme_cues: List[VisemeTiming] = []
        current_time = 0.15

        # Vowel to viseme mapping
        vowel_map = {
            "a": "viseme_aa",
            "e": "viseme_E",
            "i": "viseme_I",
            "o": "viseme_O",
            "u": "viseme_U"
        }

        for word in words:
            cleaned_word = "".join(c for c in word.lower() if c.isalpha())
            if not cleaned_word:
                continue

            word_len = len(cleaned_word)
            syllable_dur = max(0.08, min(0.22, 0.05 * word_len))

            # Plosive start (p, b, m -> viseme_PP)
            if cleaned_word[0] in ["p", "b", "m"]:
                viseme_cues.append(VisemeTiming(
                    viseme="viseme_PP",
                    start_time=round(current_time, 3),
                    duration=0.06,
                    weight=0.95
                ))
                current_time += 0.06
            elif cleaned_word[0] in ["f", "v"]:
                viseme_cues.append(VisemeTiming(
                    viseme="viseme_FF",
                    start_time=round(current_time, 3),
                    duration=0.07,
                    weight=0.85
                ))
                current_time += 0.07

            # Primary vowel
            found_vowel = False
            for char in cleaned_word:
                if char in vowel_map:
                    viseme_cues.append(VisemeTiming(
                        viseme=vowel_map[char],
                        start_time=round(current_time, 3),
                        duration=syllable_dur,
                        weight=0.85
                    ))
                    current_time += syllable_dur
                    found_vowel = True
                    break

            if not found_vowel:
                viseme_cues.append(VisemeTiming(
                    viseme="viseme_aa",
                    start_time=round(current_time, 3),
                    duration=syllable_dur,
                    weight=0.75
                ))
                current_time += syllable_dur

            # Dental/consonant finish (s, z, t, d -> viseme_SS / viseme_DD)
            if cleaned_word[-1] in ["s", "z", "c"]:
                viseme_cues.append(VisemeTiming(
                    viseme="viseme_SS",
                    start_time=round(current_time, 3),
                    duration=0.06,
                    weight=0.7
                ))
                current_time += 0.06
            elif cleaned_word[-1] in ["t", "d", "n"]:
                viseme_cues.append(VisemeTiming(
                    viseme="viseme_DD",
                    start_time=round(current_time, 3),
                    duration=0.05,
                    weight=0.65
                ))
                current_time += 0.05

            # Brief inter-word pause
            current_time += 0.04

        return cls(
            spoken_response=text,
            emotion=emotion,
            expression_intensity=0.85,
            gaze_target=gaze,
            gesture_id=gesture,
            gesture_timing=0.2,
            speaking_state="speaking",
            conversational_emphasis=[w for w in words if len(w) > 6][:3],
            viseme_cues=viseme_cues
        )

