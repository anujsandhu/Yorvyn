"""
Strict Filter — Enforce strict filtering rules for perfume recommendations.

This module applies hard filters to ensure recommendations meet user requirements:
1. Budget: price <= user_budget * 1.2 (20% tolerance)
2. Notes: at least 2 matching notes (for note-based queries)
3. Occasion: must match occasion requirements (no oud for office, etc.)
4. Strength: match intensity preference
5. Gender: match gender preference (with unisex flexibility)

These filters run AFTER ML scoring to ensure quality and relevance.
"""
from __future__ import annotations
import re
from typing import List, Dict, Any, Optional, Tuple


# ── Opposite Note Pairs ───────────────────────────────────────────────
# Notes that conflict with each other (shouldn't appear together for specific queries)

OPPOSITE_NOTES = {
    "fresh": ["oud", "heavy", "intense", "smoky", "dark"],
    "light": ["oud", "heavy", "intense", "bold", "strong"],
    "clean": ["oud", "smoky", "dark", "animalic"],
    "citrus": ["oud", "heavy", "dark", "smoky"],
    "aquatic": ["oud", "heavy", "gourmand", "sweet"],
    "oud": ["fresh", "light", "clean", "citrus", "aquatic"],
    "heavy": ["fresh", "light", "clean", "citrus"],
    "sweet": ["fresh", "clean", "aquatic", "marine"],
}


# ── Occasion Hard Filters ─────────────────────────────────────────────
# Perfumes that should be EXCLUDED for specific occasions

OCCASION_EXCLUSIONS = {
    "office": ["oud", "heavy", "intense", "smoky", "bold"],
    "work": ["oud", "heavy", "intense", "smoky", "bold"],
    "gym": ["heavy", "sweet", "gourmand", "oud", "intense"],
    "daily": ["heavy", "intense", "overpowering", "bold"],
}


def apply_strict_filters(
    recommendations: List[Dict[str, Any]],
    context: Dict[str, Any],
    min_score: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    Apply strict filtering rules to recommendations.
    
    Args:
        recommendations: List of perfume recommendations
        context: User context (occasion, budget, notes, etc.)
        min_score: Minimum score threshold (default: 0.3)
        
    Returns:
        Filtered list of recommendations
    """
    if not recommendations:
        return []
    
    filtered = []
    
    for rec in recommendations:
        # Filter 1: Minimum score threshold
        score = rec.get("final_score", rec.get("score", rec.get("match_score", 0)))
        if score < min_score:
            continue
        
        # Filter 2: Budget filter (STRICT)
        if not passes_budget_filter(rec, context):
            continue
        
        # Filter 3: Note matching filter
        if not passes_note_filter(rec, context):
            continue
        
        # Filter 4: Occasion filter (HARD)
        if not passes_occasion_filter(rec, context):
            continue
        
        # Filter 5: Strength/intensity filter
        if not passes_intensity_filter(rec, context):
            continue
        
        # Filter 6: Gender filter
        if not passes_gender_filter(rec, context):
            continue
        
        # Filter 7: Opposite notes penalty
        penalty = compute_opposite_notes_penalty(rec, context)
        if penalty > 0.5:  # Too many opposite notes
            continue
        
        # Apply penalty to score
        if penalty > 0:
            rec["final_score"] = max(0, score - penalty)
        
        filtered.append(rec)
    
    return filtered


def passes_budget_filter(perfume: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """
    Check if perfume passes budget filter.
    
    Args:
        perfume: Perfume dictionary
        context: User context with budget_max
        
    Returns:
        True if passes, False otherwise
    """
    if not context.get("budget_max"):
        return True  # No budget constraint
    
    price = perfume.get("price", 0)
    budget = context["budget_max"]
    
    if price <= 0:
        return True  # Unknown price, allow
    
    # Allow 20% over budget
    return price <= budget * 1.2


def passes_note_filter(perfume: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """
    Check if perfume has at least 2 matching notes (for note-based queries).
    
    Args:
        perfume: Perfume dictionary
        context: User context with liked_notes
        
    Returns:
        True if passes, False otherwise
    """
    liked_notes = context.get("liked_notes", [])
    
    if not liked_notes:
        return True  # No note requirement
    
    # If user specified notes, require at least 2 matches
    if len(liked_notes) >= 2:
        accords = perfume.get("accords", "").lower()
        matches = sum(1 for note in liked_notes if note.lower() in accords)
        return matches >= 2
    
    # If only 1 note specified, require at least 1 match
    else:
        accords = perfume.get("accords", "").lower()
        return any(note.lower() in accords for note in liked_notes)


def passes_occasion_filter(perfume: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """
    Check if perfume passes occasion filter (HARD filter).
    
    Args:
        perfume: Perfume dictionary
        context: User context with occasion
        
    Returns:
        True if passes, False otherwise
    """
    occasion = context.get("occasion")
    
    if not occasion:
        return True  # No occasion constraint
    
    occasion = occasion.lower()
    
    if occasion not in OCCASION_EXCLUSIONS:
        return True  # No exclusions for this occasion
    
    accords = perfume.get("accords", "").lower()
    excluded_notes = OCCASION_EXCLUSIONS[occasion]
    
    # Check if perfume contains any excluded notes
    for note in excluded_notes:
        if note in accords:
            return False  # Hard filter: exclude
    
    return True


def passes_intensity_filter(perfume: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """
    Check if perfume matches intensity preference.
    
    Args:
        perfume: Perfume dictionary
        context: User context with intensity or occasion
        
    Returns:
        True if passes, False otherwise
    """
    # Determine desired intensity
    desired_intensity = context.get("intensity")
    
    if not desired_intensity:
        # Infer from occasion
        occasion = context.get("occasion", "").lower()
        intensity_map = {
            "office": "light",
            "work": "light",
            "gym": "light",
            "daily": "light",
            "date": "medium",
            "wedding": "medium",
            "party": "strong",
            "night": "strong",
        }
        desired_intensity = intensity_map.get(occasion)
    
    if not desired_intensity:
        return True  # No intensity constraint
    
    # Detect perfume intensity
    accords = perfume.get("accords", "").lower()
    
    light_notes = ["fresh", "citrus", "aquatic", "green", "light", "clean"]
    strong_notes = ["oud", "amber", "intense", "bold", "heavy", "spicy", "leather"]
    
    light_count = sum(1 for note in light_notes if note in accords)
    strong_count = sum(1 for note in strong_notes if note in accords)
    
    if light_count > strong_count:
        perfume_intensity = "light"
    elif strong_count > light_count:
        perfume_intensity = "strong"
    else:
        perfume_intensity = "medium"
    
    # Allow medium perfumes for any intensity (flexible)
    if perfume_intensity == "medium":
        return True
    
    # Strict match for light/strong
    if desired_intensity == "light" and perfume_intensity == "strong":
        return False
    if desired_intensity == "strong" and perfume_intensity == "light":
        return False
    
    return True


def passes_gender_filter(perfume: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """
    Check if perfume matches gender preference.
    
    Args:
        perfume: Perfume dictionary
        context: User context with gender
        
    Returns:
        True if passes, False otherwise
    """
    requested_gender = context.get("gender", "").lower()
    
    if not requested_gender or requested_gender == "unisex":
        return True  # No gender constraint
    
    perfume_gender = perfume.get("gender", "unisex").lower()
    
    # Exact match
    if perfume_gender == requested_gender:
        return True
    
    # Unisex perfumes work for everyone
    if perfume_gender == "unisex":
        return True
    
    # Wrong gender
    return False


def compute_opposite_notes_penalty(perfume: Dict[str, Any], context: Dict[str, Any]) -> float:
    """
    Compute penalty for opposite notes.
    
    If user wants "fresh citrus" but perfume has "oud heavy", apply penalty.
    
    Args:
        perfume: Perfume dictionary
        context: User context with liked_notes
        
    Returns:
        Penalty score (0.0 - 1.0)
    """
    liked_notes = context.get("liked_notes", [])
    
    if not liked_notes:
        return 0.0  # No penalty if no notes specified
    
    accords = perfume.get("accords", "").lower()
    
    penalty = 0.0
    
    for note in liked_notes:
        note_lower = note.lower()
        
        # Check if this note has opposites
        if note_lower in OPPOSITE_NOTES:
            opposite_notes = OPPOSITE_NOTES[note_lower]
            
            # Count how many opposite notes are present
            opposite_count = sum(1 for opp in opposite_notes if opp in accords)
            
            if opposite_count > 0:
                # Penalty: 0.15 per opposite note
                penalty += opposite_count * 0.15
    
    return min(1.0, penalty)


def filter_by_quality(
    recommendations: List[Dict[str, Any]],
    min_rating: float = 3.5,
    min_rating_count: int = 10,
) -> List[Dict[str, Any]]:
    """
    Filter recommendations by quality metrics.
    
    Args:
        recommendations: List of perfume recommendations
        min_rating: Minimum rating threshold
        min_rating_count: Minimum rating count threshold
        
    Returns:
        Filtered list
    """
    filtered = []
    
    for rec in recommendations:
        rating = rec.get("rating", 0)
        rating_count = rec.get("rating_count", 0)
        
        # Quality filter
        if rating >= min_rating and rating_count >= min_rating_count:
            filtered.append(rec)
    
    return filtered


def remove_duplicates(recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate perfumes (same name + brand).
    
    Args:
        recommendations: List of perfume recommendations
        
    Returns:
        Deduplicated list
    """
    seen = set()
    unique = []
    
    for rec in recommendations:
        name = rec.get("name", "").lower().strip()
        brand = rec.get("brand", "").lower().strip()
        key = f"{name}|{brand}"
        
        if key not in seen:
            seen.add(key)
            unique.append(rec)
    
    return unique


def apply_all_filters(
    recommendations: List[Dict[str, Any]],
    context: Dict[str, Any],
    min_score: float = 0.3,
    min_rating: float = 3.5,
    min_rating_count: int = 10,
) -> List[Dict[str, Any]]:
    """
    Apply all filters in sequence.
    
    Args:
        recommendations: List of perfume recommendations
        context: User context
        min_score: Minimum score threshold
        min_rating: Minimum rating threshold
        min_rating_count: Minimum rating count threshold
        
    Returns:
        Fully filtered list
    """
    # Step 1: Remove duplicates
    filtered = remove_duplicates(recommendations)
    
    # Step 2: Apply strict filters
    filtered = apply_strict_filters(filtered, context, min_score)
    
    # Step 3: Apply quality filter
    filtered = filter_by_quality(filtered, min_rating, min_rating_count)
    
    return filtered


# ── Example Usage ─────────────────────────────────────────────────────

if __name__ == "__main__":
    # Example: Filter recommendations
    recommendations = [
        {
            "name": "Dior Sauvage",
            "brand": "Dior",
            "accords": "fresh citrus woody spicy",
            "rating": 4.5,
            "price": 85.0,
            "rating_count": 5000,
            "gender": "men",
            "final_score": 0.85,
        },
        {
            "name": "Oud Wood",
            "brand": "Tom Ford",
            "accords": "oud woody smoky intense",
            "rating": 4.3,
            "price": 150.0,
            "rating_count": 2000,
            "gender": "unisex",
            "final_score": 0.75,
        },
        {
            "name": "Light Blue",
            "brand": "Dolce & Gabbana",
            "accords": "fresh citrus aquatic light",
            "rating": 4.2,
            "price": 70.0,
            "rating_count": 3000,
            "gender": "women",
            "final_score": 0.80,
        },
    ]
    
    context = {
        "occasion": "office",
        "budget_max": 100.0,
        "liked_notes": ["fresh", "citrus"],
        "gender": "men",
    }
    
    # Apply filters
    filtered = apply_all_filters(recommendations, context)
    
    print(f"Original: {len(recommendations)} recommendations")
    print(f"Filtered: {len(filtered)} recommendations\n")
    
    for rec in filtered:
        print(f"✓ {rec['name']} by {rec['brand']}")
        print(f"  Score: {rec['final_score']:.2f}, Price: ${rec['price']:.0f}")
        print(f"  Accords: {rec['accords']}\n")
