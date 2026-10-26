"""
Response Generator — Transform ML recommendations into human-like advisor responses.

This module takes raw ML recommendations and generates natural, engaging,
human-like responses that feel like talking to a stylish fragrance expert.
"""
from __future__ import annotations
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class VibeStyle(str, Enum):
    """Fragrance vibe styles detected from user input."""
    LUXURY = "luxury"
    FRESH = "fresh"
    ROMANTIC = "romantic"
    BOLD = "bold"
    SOFT = "soft"
    MYSTERIOUS = "mysterious"
    PLAYFUL = "playful"
    PROFESSIONAL = "professional"


@dataclass
class VibeProfile:
    """User's fragrance vibe profile."""
    primary_vibe: VibeStyle
    confidence: float
    keywords: List[str]
    notes_preference: List[str]
    intensity: str  # "light", "medium", "strong"


# ── VIBE DETECTION PATTERNS ──────────────────────────────────────────

VIBE_PATTERNS = {
    VibeStyle.LUXURY: {
        "keywords": ["luxury", "rich", "expensive", "premium", "niche", "aura", "high end", "designer", "exclusive"],
        "notes": ["oud", "amber", "iris", "leather", "saffron", "rose", "incense"],
        "intensity": "strong",
    },
    VibeStyle.FRESH: {
        "keywords": ["fresh", "clean", "light", "crisp", "airy", "aquatic", "marine", "sport", "gym", "daily"],
        "notes": ["citrus", "bergamot", "lemon", "aquatic", "green", "mint", "ozonic"],
        "intensity": "light",
    },
    VibeStyle.ROMANTIC: {
        "keywords": ["romantic", "date", "sensual", "sexy", "intimate", "seductive", "love", "valentine"],
        "notes": ["rose", "vanilla", "musk", "jasmine", "amber", "tonka", "sweet"],
        "intensity": "medium",
    },
    VibeStyle.BOLD: {
        "keywords": ["bold", "strong", "powerful", "intense", "statement", "projection", "beast mode", "loud"],
        "notes": ["oud", "spicy", "pepper", "tobacco", "leather", "patchouli", "woody"],
        "intensity": "strong",
    },
    VibeStyle.SOFT: {
        "keywords": ["soft", "subtle", "gentle", "delicate", "powdery", "light", "office", "work"],
        "notes": ["musk", "powdery", "iris", "cotton", "clean", "soft floral", "lavender"],
        "intensity": "light",
    },
    VibeStyle.MYSTERIOUS: {
        "keywords": ["mysterious", "dark", "night", "smoky", "deep", "enigmatic", "complex"],
        "notes": ["oud", "incense", "smoky", "amber", "dark woods", "vetiver", "patchouli"],
        "intensity": "strong",
    },
    VibeStyle.PLAYFUL: {
        "keywords": ["playful", "fun", "sweet", "fruity", "young", "energetic", "vibrant", "party"],
        "notes": ["fruity", "sweet", "vanilla", "caramel", "gourmand", "citrus", "berry"],
        "intensity": "medium",
    },
    VibeStyle.PROFESSIONAL: {
        "keywords": ["professional", "office", "work", "meeting", "corporate", "business", "formal"],
        "notes": ["clean", "fresh", "woody", "aromatic", "green", "citrus", "musk"],
        "intensity": "light",
    },
}


def detect_vibe(user_input: str, context: Optional[Dict[str, Any]] = None) -> VibeProfile:
    """
    Detect user's fragrance vibe from input.
    
    Args:
        user_input: User's message
        context: Additional context (occasion, mood, etc.)
        
    Returns:
        VibeProfile with detected vibe and preferences
    """
    text_lower = user_input.lower()
    context = context or {}
    
    # Score each vibe
    vibe_scores: Dict[VibeStyle, float] = {}
    
    for vibe, patterns in VIBE_PATTERNS.items():
        score = 0.0
        matched_keywords = []
        
        # Check keywords
        for keyword in patterns["keywords"]:
            if keyword in text_lower:
                score += 1.0
                matched_keywords.append(keyword)
        
        # Check notes
        for note in patterns["notes"]:
            if note in text_lower:
                score += 0.5
        
        # Check context
        if context.get("occasion"):
            occasion = context["occasion"].lower()
            if vibe == VibeStyle.ROMANTIC and occasion in ["date", "romantic"]:
                score += 2.0
            elif vibe == VibeStyle.PROFESSIONAL and occasion in ["office", "work"]:
                score += 2.0
            elif vibe == VibeStyle.BOLD and occasion in ["party", "night"]:
                score += 2.0
        
        if score > 0:
            vibe_scores[vibe] = score
    
    # Default to FRESH if no clear vibe
    if not vibe_scores:
        return VibeProfile(
            primary_vibe=VibeStyle.FRESH,
            confidence=0.3,
            keywords=[],
            notes_preference=VIBE_PATTERNS[VibeStyle.FRESH]["notes"],
            intensity="light",
        )
    
    # Get top vibe
    top_vibe = max(vibe_scores, key=vibe_scores.get)
    confidence = min(1.0, vibe_scores[top_vibe] / 3.0)
    
    return VibeProfile(
        primary_vibe=top_vibe,
        confidence=confidence,
        keywords=list(set(k for k in VIBE_PATTERNS[top_vibe]["keywords"] if k in text_lower)),
        notes_preference=VIBE_PATTERNS[top_vibe]["notes"],
        intensity=VIBE_PATTERNS[top_vibe]["intensity"],
    )


# ── RESPONSE HOOKS ────────────────────────────────────────────────────

HOOKS = {
    VibeStyle.LUXURY: [
        "Alright, going premium — you want something that screams quality.",
        "Got you — luxury vibes, something with presence and depth.",
        "Okay, high-end territory — let's find something with real character.",
    ],
    VibeStyle.FRESH: [
        "Fresh and clean — got it, something light and easy to wear.",
        "Alright, keeping it crisp — you want something that feels effortless.",
        "Got you — fresh vibes, something that won't overpower.",
    ],
    VibeStyle.ROMANTIC: [
        "For a date — you want something memorable but not too heavy.",
        "Romantic vibes — got it, something warm and inviting.",
        "Alright, date night energy — let's find something smooth and sensual.",
    ],
    VibeStyle.BOLD: [
        "Bold and strong — you want something with serious projection.",
        "Got you — statement fragrance, something that turns heads.",
        "Alright, going intense — you want something that lasts all day.",
    ],
    VibeStyle.SOFT: [
        "Soft and subtle — you want something that stays close to skin.",
        "Got you — gentle vibes, something office-friendly.",
        "Alright, keeping it light — you want something that won't announce itself.",
    ],
    VibeStyle.MYSTERIOUS: [
        "Dark and mysterious — you want something with depth and complexity.",
        "Got you — enigmatic vibes, something that unfolds over time.",
        "Alright, going deep — you want something that keeps people guessing.",
    ],
    VibeStyle.PLAYFUL: [
        "Fun and playful — you want something sweet and energetic.",
        "Got you — vibrant vibes, something that feels young and fresh.",
        "Alright, keeping it fun — you want something that lifts the mood.",
    ],
    VibeStyle.PROFESSIONAL: [
        "For work — you want something clean and professional.",
        "Got you — office vibes, something that's polished but not boring.",
        "Alright, business mode — you want something subtle and refined.",
    ],
}


def get_hook(vibe: VibeStyle, occasion: Optional[str] = None) -> str:
    """Get opening hook based on vibe."""
    import random
    hooks = HOOKS.get(vibe, HOOKS[VibeStyle.FRESH])
    
    # Add occasion-specific context
    if occasion:
        if occasion == "wedding":
            return "Alright, for a wedding — you want something classy, smooth, and noticeable but not overpowering."
        elif occasion == "date":
            return "For a date — you want something memorable, warm, and inviting without being too heavy."
        elif occasion == "office":
            return "For the office — you want something clean, professional, and subtle enough for close quarters."
        elif occasion == "party":
            return "For a party — you want something bold, fun, and with enough projection to stand out."
    
    return random.choice(hooks)


# ── TOP PICK EXPLANATIONS ─────────────────────────────────────────────

def generate_top_pick_reason(perfume: Dict[str, Any], vibe: VibeProfile, context: Dict[str, Any]) -> str:
    """
    Generate human-like explanation for top pick.
    
    Args:
        perfume: Top recommendation
        vibe: User's vibe profile
        context: Additional context
        
    Returns:
        Natural explanation string
    """
    name = perfume.get("name", "Unknown")
    brand = perfume.get("brand", "")
    accords = perfume.get("accords", "").lower()
    
    # Extract key notes
    notes = []
    if "oud" in accords:
        notes.append("oud")
    if "vanilla" in accords:
        notes.append("vanilla")
    if "rose" in accords:
        notes.append("rose")
    if "citrus" in accords or "bergamot" in accords:
        notes.append("citrus")
    if "woody" in accords or "cedar" in accords:
        notes.append("woody")
    if "spicy" in accords or "pepper" in accords:
        notes.append("spicy")
    if "fresh" in accords or "aquatic" in accords:
        notes.append("fresh")
    if "amber" in accords:
        notes.append("amber")
    
    # Build reason based on vibe
    if vibe.primary_vibe == VibeStyle.LUXURY:
        if "oud" in notes:
            return f"🔥 Top pick: **{name}** — rich oud with a classy edge, the kind of scent that makes a statement without trying."
        elif "amber" in notes:
            return f"🔥 Top pick: **{name}** — warm amber with depth, feels expensive and refined."
        else:
            return f"🔥 Top pick: **{name}** — premium quality, the kind of fragrance that gets noticed."
    
    elif vibe.primary_vibe == VibeStyle.FRESH:
        if "citrus" in notes:
            return f"🔥 Top pick: **{name}** — crisp citrus with a clean finish, perfect for daily wear."
        elif "fresh" in notes:
            return f"🔥 Top pick: **{name}** — fresh and airy, the kind of scent that feels effortless."
        else:
            return f"🔥 Top pick: **{name}** — light and clean, won't overpower."
    
    elif vibe.primary_vibe == VibeStyle.ROMANTIC:
        if "rose" in notes and "vanilla" in notes:
            return f"🔥 Top pick: **{name}** — rose and vanilla blend, warm and inviting without being too sweet."
        elif "vanilla" in notes:
            return f"🔥 Top pick: **{name}** — smooth vanilla with warmth, perfect date night energy."
        else:
            return f"🔥 Top pick: **{name}** — warm and sensual, the kind of scent that draws people in."
    
    elif vibe.primary_vibe == VibeStyle.BOLD:
        if "oud" in notes:
            return f"🔥 Top pick: **{name}** — bold oud with serious projection, this one lasts all day."
        elif "spicy" in notes:
            return f"🔥 Top pick: **{name}** — spicy and intense, the kind of scent that turns heads."
        else:
            return f"🔥 Top pick: **{name}** — strong and confident, makes a statement."
    
    elif vibe.primary_vibe == VibeStyle.SOFT:
        if "powdery" in accords or "musk" in accords:
            return f"🔥 Top pick: **{name}** — soft musk with a powdery finish, stays close to skin."
        else:
            return f"🔥 Top pick: **{name}** — gentle and subtle, perfect for the office."
    
    elif vibe.primary_vibe == VibeStyle.MYSTERIOUS:
        if "oud" in notes:
            return f"🔥 Top pick: **{name}** — dark oud with complexity, the kind of scent that unfolds over time."
        else:
            return f"🔥 Top pick: **{name}** — deep and enigmatic, keeps people guessing."
    
    elif vibe.primary_vibe == VibeStyle.PLAYFUL:
        if "fruity" in accords or "sweet" in accords:
            return f"🔥 Top pick: **{name}** — sweet and fruity, fun and energetic vibes."
        else:
            return f"🔥 Top pick: **{name}** — playful and vibrant, lifts the mood."
    
    else:  # PROFESSIONAL
        return f"🔥 Top pick: **{name}** — clean and professional, polished without being boring."


def generate_other_options(perfumes: List[Dict[str, Any]], vibe: VibeProfile) -> List[str]:
    """
    Generate short descriptions for other options.
    
    Args:
        perfumes: List of recommendations (excluding top pick)
        vibe: User's vibe profile
        
    Returns:
        List of formatted option strings
    """
    options = []
    
    for perfume in perfumes[:4]:  # Max 4 other options
        name = perfume.get("name", "Unknown")
        accords = perfume.get("accords", "").lower()
        
        # Generate short description
        descriptors = []
        
        if "woody" in accords:
            descriptors.append("woody")
        if "fresh" in accords or "citrus" in accords:
            descriptors.append("fresh")
        if "spicy" in accords:
            descriptors.append("spicy")
        if "sweet" in accords or "vanilla" in accords:
            descriptors.append("sweet")
        if "floral" in accords:
            descriptors.append("floral")
        if "oud" in accords:
            descriptors.append("oud-forward")
        if "amber" in accords:
            descriptors.append("warm")
        
        # Add intensity hint
        if vibe.intensity == "strong":
            descriptors.append("good projection")
        elif vibe.intensity == "light":
            descriptors.append("subtle")
        
        desc = ", ".join(descriptors[:3]) if descriptors else "balanced"
        options.append(f"- **{name}** → {desc}")
    
    return options


def generate_mini_explanation(vibe: VibeProfile, perfumes: List[Dict[str, Any]]) -> str:
    """
    Generate mini explanation of why these perfumes fit.
    
    Args:
        vibe: User's vibe profile
        perfumes: List of recommendations
        
    Returns:
        Natural explanation string
    """
    # Extract common notes
    all_accords = " ".join([p.get("accords", "").lower() for p in perfumes])
    
    common_notes = []
    if "woody" in all_accords:
        common_notes.append("woody")
    if "fresh" in all_accords or "citrus" in all_accords:
        common_notes.append("fresh")
    if "oud" in all_accords:
        common_notes.append("oud")
    if "amber" in all_accords:
        common_notes.append("amber")
    if "floral" in all_accords:
        common_notes.append("floral")
    
    notes_str = " + ".join(common_notes[:3]) if common_notes else "balanced"
    
    # Build explanation based on vibe
    if vibe.primary_vibe == VibeStyle.LUXURY:
        return f"These lean into {notes_str} tones — premium quality with depth and character."
    elif vibe.primary_vibe == VibeStyle.FRESH:
        return f"These are all {notes_str} profiles — light, clean, and easy to wear daily."
    elif vibe.primary_vibe == VibeStyle.ROMANTIC:
        return f"These have {notes_str} bases — warm and inviting without being too heavy."
    elif vibe.primary_vibe == VibeStyle.BOLD:
        return f"These are {notes_str} forward — strong projection and all-day longevity."
    elif vibe.primary_vibe == VibeStyle.SOFT:
        return f"These stay in the {notes_str} range — subtle and office-friendly."
    elif vibe.primary_vibe == VibeStyle.MYSTERIOUS:
        return f"These have {notes_str} complexity — deep and enigmatic."
    elif vibe.primary_vibe == VibeStyle.PLAYFUL:
        return f"These are {notes_str} leaning — fun, sweet, and energetic."
    else:  # PROFESSIONAL
        return f"These are {notes_str} based — clean, professional, and versatile."


def generate_follow_up(vibe: VibeProfile, context: Dict[str, Any]) -> str:
    """
    Generate contextual follow-up question.
    
    Args:
        vibe: User's vibe profile
        context: Additional context
        
    Returns:
        Natural follow-up question
    """
    # Context-aware follow-ups
    if context.get("occasion") == "wedding":
        return "Want something fresher or more bold?"
    elif context.get("occasion") == "date":
        return "Need it sweeter or more woody?"
    elif context.get("occasion") == "office":
        return "Want something even lighter or a bit more noticeable?"
    
    # Vibe-based follow-ups
    if vibe.primary_vibe == VibeStyle.LUXURY:
        return "Want something even more niche or a bit more wearable?"
    elif vibe.primary_vibe == VibeStyle.FRESH:
        return "Need it lighter or with more depth?"
    elif vibe.primary_vibe == VibeStyle.ROMANTIC:
        return "Want it sweeter or more musky?"
    elif vibe.primary_vibe == VibeStyle.BOLD:
        return "Need it stronger or a bit more balanced?"
    elif vibe.primary_vibe == VibeStyle.SOFT:
        return "Want something even softer or with a bit more presence?"
    elif vibe.primary_vibe == VibeStyle.MYSTERIOUS:
        return "Want it darker or a bit more approachable?"
    elif vibe.primary_vibe == VibeStyle.PLAYFUL:
        return "Need it sweeter or more fresh?"
    else:  # PROFESSIONAL
        return "Want something more formal or a bit more casual?"


# ── MAIN RESPONSE GENERATOR ──────────────────────────────────────────

def generate_human_response(
    recommendations: List[Dict[str, Any]],
    user_input: str,
    context: Optional[Dict[str, Any]] = None,
    user_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate human-like advisor response from ML recommendations.
    
    Args:
        recommendations: List of perfume recommendations from ML
        user_input: User's original message
        context: Additional context (occasion, mood, etc.)
        user_name: User's name for personalization
        
    Returns:
        Structured response with human-like message
    """
    context = context or {}
    
    # Detect vibe
    vibe = detect_vibe(user_input, context)
    
    # Filter out low-quality results
    filtered_recs = filter_recommendations(recommendations)
    
    if not filtered_recs:
        return {
            "message": "Hmm, couldn't find a strong match for that. Could you tell me more — like a specific note (oud, vanilla, citrus) or an occasion?",
            "tone": "genz_advisor",
            "top_pick_reason": None,
            "follow_up": "What kind of vibe are you going for? Fresh, bold, sweet, or something else?",
            "vibe_detected": vibe.primary_vibe.value,
            "confidence": 0.0,
        }
    
    # Build response components
    hook = get_hook(vibe.primary_vibe, context.get("occasion"))
    
    # Add name if available
    if user_name:
        hook = f"{user_name}, {hook[0].lower()}{hook[1:]}"
    
    top_pick = filtered_recs[0]
    top_pick_reason = generate_top_pick_reason(top_pick, vibe, context)
    
    other_options = generate_other_options(filtered_recs[1:], vibe)
    
    mini_explanation = generate_mini_explanation(vibe, filtered_recs)
    
    follow_up = generate_follow_up(vibe, context)
    
    # Assemble message
    message_parts = [hook, "", top_pick_reason]
    
    if other_options:
        message_parts.append("")
        message_parts.append("**Other solid options:**")
        message_parts.extend(other_options)
    
    message_parts.append("")
    message_parts.append(mini_explanation)
    message_parts.append("")
    message_parts.append(follow_up)
    
    message = "\n".join(message_parts)
    
    # Extract IDs for frontend matching
    top_pick_id = str(top_pick.get("id", top_pick.get("perfume_id", "")))
    recommended_ids = [str(rec.get("id", rec.get("perfume_id", ""))) for rec in filtered_recs]
    
    return {
        "message": message,
        "tone": "genz_advisor",
        "top_pick_reason": top_pick_reason,
        "follow_up": follow_up,
        "vibe_detected": vibe.primary_vibe.value,
        "confidence": vibe.confidence,
        "recommendations": filtered_recs,  # Return filtered list
        "top_pick_id": top_pick_id,  # ID of the top pick for highlighting
        "recommended_ids": recommended_ids,  # Ordered list of IDs
    }


def filter_recommendations(recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter out low-quality recommendations.
    
    Removes:
    - Duplicate perfumes
    - Sample packs
    - Testers
    - Irrelevant matches
    
    Args:
        recommendations: Raw ML recommendations
        
    Returns:
        Filtered list
    """
    if not recommendations:
        return []
    
    filtered = []
    seen_names = set()
    
    # Noise patterns
    noise_patterns = [
        "sample", "tester", "vial", "decant", "mini", "set", "pack", "bundle",
        "lot", "gift set", "discovery", "variety", "empty bottle"
    ]
    
    for rec in recommendations:
        name = rec.get("name", "").lower()
        
        # Skip duplicates
        if name in seen_names:
            continue
        
        # Skip noise
        if any(pattern in name for pattern in noise_patterns):
            continue
        
        # Skip very low scores
        score = rec.get("final_score", rec.get("score", 0))
        if score < 0.3:
            continue
        
        seen_names.add(name)
        filtered.append(rec)
    
    return filtered[:6]  # Max 6 recommendations


def handle_vague_input(user_input: str) -> Dict[str, Any]:
    """
    Handle vague inputs that need clarification.
    
    Args:
        user_input: User's message
        
    Returns:
        Clarification response
    """
    return {
        "message": "Got you — what kind of vibe are you going for? Fresh and clean, bold and woody, sweet and playful, or something else?",
        "tone": "genz_advisor",
        "top_pick_reason": None,
        "follow_up": "Tell me more about the occasion or mood you're aiming for.",
        "vibe_detected": None,
        "confidence": 0.0,
        "needs_clarification": True,
    }


def handle_refinement(
    previous_recommendations: List[Dict[str, Any]],
    refinement: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Handle refinement requests (e.g., "make it stronger", "more fresh").
    
    Args:
        previous_recommendations: Previous recommendations
        refinement: Refinement request
        context: Context including previous vibe
        
    Returns:
        Refined response
    """
    refinement_lower = refinement.lower()
    
    # Detect refinement type
    if any(word in refinement_lower for word in ["stronger", "bold", "intense", "powerful"]):
        message = "Got it — going stronger this time. Pushing more bold, woody, and spicy profiles."
    elif any(word in refinement_lower for word in ["lighter", "soft", "subtle", "gentle"]):
        message = "Got it — going lighter. Focusing on fresh, clean, and subtle options."
    elif any(word in refinement_lower for word in ["sweet", "sweeter", "vanilla", "gourmand"]):
        message = "Got it — adding more sweetness. Leaning into vanilla, caramel, and fruity notes."
    elif any(word in refinement_lower for word in ["fresh", "fresher", "clean", "citrus"]):
        message = "Got it — going fresher. Focusing on citrus, aquatic, and green notes."
    elif any(word in refinement_lower for word in ["woody", "wood", "cedar", "sandalwood"]):
        message = "Got it — more woody vibes. Focusing on cedar, sandalwood, and vetiver."
    else:
        message = "Got it — adjusting the recommendations based on your feedback."
    
    return {
        "message": message,
        "tone": "genz_advisor",
        "top_pick_reason": None,
        "follow_up": "Let me know if this direction works better.",
        "vibe_detected": context.get("previous_vibe"),
        "confidence": 0.8,
        "is_refinement": True,
    }
