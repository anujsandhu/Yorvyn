"""
Intent Classification — Understand user input before generating recommendations.

Classifies user input into:
- GREETING: Hi, hello, hey, etc.
- PERFUME_QUERY: Actual perfume request
- VAGUE: Unclear or too short
- ABUSIVE: Inappropriate content
- CLARIFICATION: Follow-up question
"""
from __future__ import annotations
import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class Intent(str, Enum):
    GREETING = "greeting"
    PERFUME_QUERY = "perfume_query"
    VAGUE = "vague"
    ABUSIVE = "abusive"
    CLARIFICATION = "clarification"


@dataclass(frozen=True)
class IntentResult:
    intent: Intent
    confidence: float
    reason: str


# ── Pattern sets ──────────────────────────────────────────────────────

GREETING_PATTERNS = frozenset({
    "hi", "hello", "hey", "hii", "hiii", "heya", "yo", "sup", "wassup",
    "good morning", "good afternoon", "good evening", "greetings",
    "hola", "namaste", "bonjour",
})

ABUSIVE_PATTERNS = frozenset({
    "fuck", "shit", "bitch", "asshole", "bastard", "damn", "hell",
    "wtf", "stfu", "idiot", "stupid", "dumb", "moron", "retard",
    "crap", "piss", "dick", "cock", "pussy", "ass",
})

PERFUME_KEYWORDS = frozenset({
    "perfume", "fragrance", "scent", "cologne", "eau de toilette", "edt",
    "eau de parfum", "edp", "oud", "rose", "vanilla", "musk", "woody",
    "floral", "citrus", "fresh", "sweet", "spicy", "amber", "leather",
    "wedding", "date", "office", "party", "gym", "daily", "night",
    "summer", "winter", "spring", "autumn", "fall",
    "men", "women", "unisex", "him", "her", "boyfriend", "girlfriend",
    "husband", "wife", "brother", "sister", "father", "mother",
    "recommend", "suggest", "find", "looking for", "need", "want",
    "similar to", "like", "smells like",
})

CLARIFICATION_PATTERNS = frozenset({
    "more", "another", "different", "similar", "lighter", "stronger",
    "cheaper", "expensive", "under", "budget", "price", "show me",
    "what about", "how about", "can you", "tell me", "explain",
})


def classify_intent(text: str, conversation_history: Optional[list] = None) -> IntentResult:
    """
    Classify user input intent.
    
    Args:
        text: User input text
        conversation_history: Previous messages (optional, for context)
        
    Returns:
        IntentResult with intent, confidence, and reason
    """
    if not text or not text.strip():
        return IntentResult(
            intent=Intent.VAGUE,
            confidence=1.0,
            reason="Empty input"
        )
    
    text_lower = text.lower().strip()
    tokens = set(re.findall(r'\b\w+\b', text_lower))
    
    # ── 1. Check for abusive content (highest priority) ──────────────
    if tokens & ABUSIVE_PATTERNS:
        return IntentResult(
            intent=Intent.ABUSIVE,
            confidence=1.0,
            reason="Contains inappropriate language"
        )
    
    # ── 2. Check for pure greeting ────────────────────────────────────
    # Only classify as greeting if:
    # - Very short (1-3 words)
    # - Contains greeting word
    # - No perfume keywords
    word_count = len(text_lower.split())
    is_short = word_count <= 3
    has_greeting = any(g in text_lower for g in GREETING_PATTERNS)
    has_perfume_keyword = bool(tokens & PERFUME_KEYWORDS)
    
    if is_short and has_greeting and not has_perfume_keyword:
        return IntentResult(
            intent=Intent.GREETING,
            confidence=0.95,
            reason="Pure greeting detected"
        )
    
    # ── 3. Check for perfume query ────────────────────────────────────
    # Strong signals:
    # - Contains perfume keywords
    # - Contains notes (oud, rose, vanilla, etc.)
    # - Contains occasion/season
    # - Contains gender
    # - Contains brand names
    # - Contains "for" + person/occasion
    
    perfume_score = 0.0
    
    # Direct perfume keywords
    if tokens & PERFUME_KEYWORDS:
        perfume_score += 0.4
    
    # Occasion/season patterns
    if any(p in text_lower for p in ["wedding", "date", "office", "party", "gym", "daily", "night"]):
        perfume_score += 0.2
    
    if any(p in text_lower for p in ["summer", "winter", "spring", "autumn", "fall"]):
        perfume_score += 0.15
    
    # Gender patterns
    if any(p in text_lower for p in ["men", "women", "him", "her", "male", "female", "unisex"]):
        perfume_score += 0.15
    
    # "For" patterns (for wedding, for him, for date, etc.)
    if re.search(r'\bfor\s+\w+', text_lower):
        perfume_score += 0.2
    
    # Note patterns (specific fragrance notes)
    note_keywords = {"oud", "rose", "vanilla", "musk", "woody", "floral", "citrus", "amber", "leather", "spicy"}
    if tokens & note_keywords:
        perfume_score += 0.3
    
    # Brand patterns (Dior, Chanel, YSL, etc.)
    if re.search(r'\b(dior|chanel|ysl|gucci|versace|armani|prada|tom ford|creed|jo malone)\b', text_lower):
        perfume_score += 0.25
    
    # "Similar to" / "like" patterns
    if any(p in text_lower for p in ["similar to", "like", "smells like", "reminds me of"]):
        perfume_score += 0.3
    
    if perfume_score >= 0.4:
        return IntentResult(
            intent=Intent.PERFUME_QUERY,
            confidence=min(0.95, perfume_score),
            reason="Contains perfume-related keywords and context"
        )
    
    # ── 4. Check for clarification (follow-up) ────────────────────────
    # Only if there's conversation history
    if conversation_history and len(conversation_history) > 0:
        has_clarification = bool(tokens & CLARIFICATION_PATTERNS)
        if has_clarification:
            return IntentResult(
                intent=Intent.CLARIFICATION,
                confidence=0.8,
                reason="Follow-up clarification detected"
            )
    
    # ── 5. Check for vague input ──────────────────────────────────────
    # Too short, no clear intent
    if word_count <= 2 and perfume_score < 0.3:
        return IntentResult(
            intent=Intent.VAGUE,
            confidence=0.85,
            reason="Input too short or unclear"
        )
    
    # ── 6. Default to perfume query (benefit of doubt) ───────────────
    # If we got here, assume it's a perfume query but with low confidence
    return IntentResult(
        intent=Intent.PERFUME_QUERY,
        confidence=0.5,
        reason="Assumed perfume query (low confidence)"
    )


def get_intent_response(intent_result: IntentResult, user_name: str = "") -> str:
    """
    Generate appropriate response based on intent.
    
    Args:
        intent_result: Classification result
        user_name: User's name (optional, for personalization)
        
    Returns:
        Response text
    """
    name_prefix = f"{user_name}, " if user_name else ""
    
    if intent_result.intent == Intent.GREETING:
        return (
            f"Hey{' ' + user_name if user_name else ''}! 👋 "
            f"I'm your personal fragrance advisor. "
            f"Tell me what kind of vibe you're going for — an occasion, a mood, or a note you love."
        )
    
    elif intent_result.intent == Intent.VAGUE:
        return (
            f"Got it{', ' + user_name if user_name else ''} — "
            f"but I need a bit more to work with. "
            f"Try something like: *fresh citrus for summer*, *woody oud for winter*, "
            f"*floral for a wedding*, or *something like Dior Sauvage*."
        )
    
    elif intent_result.intent == Intent.ABUSIVE:
        return (
            f"Hey 😅 I didn't quite catch that. "
            f"Let's keep it friendly — tell me your vibe: fresh, woody, sweet, or something else?"
        )
    
    # For PERFUME_QUERY and CLARIFICATION, return None (let the main flow handle it)
    return ""
