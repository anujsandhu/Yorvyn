"""
Improved recommendation ranking with strict vibe matching.

This module adds strict filtering and stronger penalties to ensure
recommendations match user intent (vibe, strength, occasion, budget).
"""

from typing import Dict, List, Set, Tuple, Any
import numpy as np


# ── OPPOSITE NOTES (STRONG PENALTIES) ────────────────────────────────

OPPOSITE_NOTES = {
    # Fresh/Light opposites
    "fresh": {"oud", "leather", "smoky", "tobacco", "heavy", "intense", "dark"},
    "clean": {"oud", "leather", "smoky", "tobacco", "animalic", "dark"},
    "light": {"oud", "leather", "heavy", "intense", "bold", "strong", "smoky"},
    "citrus": {"oud", "leather", "smoky", "tobacco", "heavy", "dark"},
    "aquatic": {"oud", "leather", "smoky", "tobacco", "heavy", "gourmand"},
    
    # Heavy/Dark opposites
    "oud": {"fresh", "clean", "light", "citrus", "aquatic", "airy", "subtle"},
    "leather": {"fresh", "clean", "light", "citrus", "aquatic", "floral", "sweet"},
    "smoky": {"fresh", "clean", "light", "citrus", "aquatic", "floral"},
    "tobacco": {"fresh", "clean", "light", "citrus", "aquatic", "floral"},
    "heavy": {"light", "fresh", "clean", "subtle", "airy", "delicate"},
    "intense": {"light", "subtle", "soft", "delicate", "gentle"},
    
    # Sweet opposites
    "sweet": {"leather", "smoky", "tobacco", "green", "ozonic"},
    "vanilla": {"leather", "smoky", "tobacco", "green", "ozonic"},
    "gourmand": {"leather", "smoky", "tobacco", "green", "ozonic", "aquatic"},
    
    # Woody opposites
    "woody": {"aquatic", "marine", "ozonic"},
    
    # Floral opposites
    "floral": {"leather", "tobacco", "smoky"},
}


# ── STRENGTH INDICATORS ──────────────────────────────────────────────

STRENGTH_INDICATORS = {
    "light": {"fresh", "citrus", "aquatic", "clean", "green", "soft", "subtle", "delicate", "airy"},
    "medium": {"floral", "woody", "aromatic", "musk", "powdery"},
    "strong": {"oud", "leather", "tobacco", "smoky", "amber", "spicy", "patchouli", "intense", "bold"},
}


# ── OCCASION REQUIREMENTS ────────────────────────────────────────────

OCCASION_REQUIREMENTS = {
    "office": {
        "required": {"fresh", "clean", "light", "subtle", "professional"},
        "avoid": {"oud", "heavy", "intense", "bold", "smoky", "sweet"},
        "strength": "light",
    },
    "work": {
        "required": {"fresh", "clean", "light", "subtle", "professional"},
        "avoid": {"oud", "heavy", "intense", "bold", "smoky", "sweet"},
        "strength": "light",
    },
    "daily": {
        "required": {"fresh", "clean", "light", "versatile"},
        "avoid": {"heavy", "intense", "bold"},
        "strength": "light",
    },
    "college": {
        "required": {"fresh", "clean", "light", "youthful"},
        "avoid": {"oud", "heavy", "intense", "mature", "smoky"},
        "strength": "light",
    },
    "gym": {
        "required": {"fresh", "clean", "aquatic", "sport"},
        "avoid": {"oud", "heavy", "sweet", "gourmand", "smoky"},
        "strength": "light",
    },
    "date": {
        "required": {"warm", "sensual", "romantic"},
        "avoid": {"heavy", "overpowering"},
        "strength": "medium",
    },
    "party": {
        "required": {"bold", "vibrant", "memorable"},
        "avoid": {"subtle", "weak"},
        "strength": "strong",
    },
    "wedding": {
        "required": {"elegant", "sophisticated", "memorable"},
        "avoid": {"casual", "sport"},
        "strength": "medium",
    },
}


def calculate_opposite_penalty(
    requested_notes: Set[str],
    perfume_notes: Set[str],
) -> float:
    """
    Calculate penalty for opposite notes.
    
    Returns:
        Penalty value (0.0 to 1.0) where higher = worse mismatch
    """
    penalty = 0.0
    
    for requested in requested_notes:
        opposites = OPPOSITE_NOTES.get(requested, set())
        # Count how many opposite notes are in the perfume
        opposite_count = len(opposites & perfume_notes)
        if opposite_count > 0:
            # Strong penalty: -0.15 per opposite note
            penalty += 0.15 * opposite_count
    
    return min(penalty, 0.6)  # Cap at 0.6


def calculate_strength_mismatch(
    requested_strength: str,
    perfume_notes: Set[str],
) -> float:
    """
    Calculate penalty for strength mismatch.
    
    Args:
        requested_strength: "light", "medium", or "strong"
        perfume_notes: Set of perfume notes
        
    Returns:
        Penalty value (0.0 to 0.3)
    """
    if not requested_strength:
        return 0.0
    
    # Count notes in each strength category
    light_count = len(STRENGTH_INDICATORS["light"] & perfume_notes)
    medium_count = len(STRENGTH_INDICATORS["medium"] & perfume_notes)
    strong_count = len(STRENGTH_INDICATORS["strong"] & perfume_notes)
    
    total = light_count + medium_count + strong_count
    if total == 0:
        return 0.0
    
    # Calculate dominant strength
    if requested_strength == "light":
        if strong_count > light_count:
            # Strong perfume when light requested = big penalty
            return 0.25
        elif strong_count > 0:
            # Some strong notes = medium penalty
            return 0.15
    elif requested_strength == "strong":
        if light_count > strong_count:
            # Light perfume when strong requested = big penalty
            return 0.25
        elif light_count > 0:
            # Some light notes = medium penalty
            return 0.15
    
    return 0.0


def calculate_occasion_mismatch(
    occasion: str,
    perfume_notes: Set[str],
) -> Tuple[float, bool]:
    """
    Calculate penalty for occasion mismatch.
    
    Returns:
        (penalty, should_filter) where should_filter=True means hard reject
    """
    if not occasion or occasion not in OCCASION_REQUIREMENTS:
        return 0.0, False
    
    requirements = OCCASION_REQUIREMENTS[occasion]
    required = requirements.get("required", set())
    avoid = requirements.get("avoid", set())
    
    # Check if perfume has any required notes
    has_required = len(required & perfume_notes) > 0
    
    # Check if perfume has any avoided notes
    has_avoided = len(avoid & perfume_notes)
    
    # Hard filter: If has avoided notes and no required notes
    if has_avoided > 0 and not has_required:
        return 0.5, True  # Strong penalty + filter flag
    
    # Soft penalty: Has avoided notes but also has required notes
    if has_avoided > 0:
        return 0.2, False
    
    # Bonus: Has required notes
    if has_required:
        return -0.1, False  # Negative penalty = bonus
    
    return 0.0, False


def calculate_budget_penalty(
    budget_max: float,
    price: float,
) -> Tuple[float, bool]:
    """
    Calculate penalty for budget mismatch.
    
    Returns:
        (penalty, should_filter) where should_filter=True means hard reject
    """
    if not budget_max or price <= 0:
        return 0.0, False
    
    if price > budget_max:
        # Over budget
        overage_ratio = (price - budget_max) / budget_max
        
        if overage_ratio > 0.5:
            # More than 50% over budget = hard filter
            return 0.4, True
        elif overage_ratio > 0.2:
            # 20-50% over budget = strong penalty
            return 0.3, False
        else:
            # Up to 20% over budget = soft penalty
            return 0.15, False
    
    return 0.0, False


def apply_strict_filtering(
    scored_rows: List[Tuple[int, float, List[str], Dict[str, Any]]],
    requested_notes: Set[str],
    requested_strength: str,
    occasion: str,
    budget_max: float,
    perfume_data: Any,
) -> List[Tuple[int, float, List[str]]]:
    """
    Apply strict filtering and penalties to recommendations.
    
    Args:
        scored_rows: List of (idx, score, matched_notes, row_data)
        requested_notes: Set of notes user requested
        requested_strength: "light", "medium", or "strong"
        occasion: Occasion type
        budget_max: Maximum budget (USD)
        perfume_data: DataFrame with perfume data
        
    Returns:
        Filtered and re-scored list of (idx, score, matched_notes)
    """
    filtered_rows = []
    
    for idx, score, matched_notes, row_data in scored_rows:
        # Get perfume notes
        accords = str(row_data.get("accords", "")).lower()
        perfume_notes = set(accords.split())
        price = float(row_data.get("price", 0) or 0)
        
        # Calculate penalties
        opposite_penalty = calculate_opposite_penalty(requested_notes, perfume_notes)
        strength_penalty = calculate_strength_mismatch(requested_strength, perfume_notes)
        occasion_penalty, occasion_filter = calculate_occasion_mismatch(occasion, perfume_notes)
        budget_penalty, budget_filter = calculate_budget_penalty(budget_max, price)
        
        # Hard filters
        if occasion_filter or budget_filter:
            continue  # Skip this perfume
        
        # Apply penalties to score
        adjusted_score = score - opposite_penalty - strength_penalty - occasion_penalty - budget_penalty
        
        # Only keep if score is still positive
        if adjusted_score > 0.0:
            filtered_rows.append((idx, adjusted_score, matched_notes))
    
    # Sort by adjusted score
    filtered_rows.sort(key=lambda x: x[1], reverse=True)
    
    return filtered_rows


def validate_top_recommendations(
    recommendations: List[Dict[str, Any]],
    requested_notes: Set[str],
    requested_strength: str,
    occasion: str,
) -> Tuple[bool, str]:
    """
    Validate that top 3 recommendations match intent at least 70%.
    
    Returns:
        (is_valid, reason)
    """
    if not recommendations:
        return False, "No recommendations"
    
    top_3 = recommendations[:3]
    match_count = 0
    
    for rec in top_3:
        accords = str(rec.get("accords", "")).lower()
        perfume_notes = set(accords.split())
        
        # Check for opposite notes
        has_opposites = False
        for requested in requested_notes:
            opposites = OPPOSITE_NOTES.get(requested, set())
            if opposites & perfume_notes:
                has_opposites = True
                break
        
        if not has_opposites:
            match_count += 1
    
    match_percentage = (match_count / len(top_3)) * 100
    
    if match_percentage >= 70:
        return True, f"Match: {match_percentage:.0f}%"
    else:
        return False, f"Only {match_percentage:.0f}% match (need 70%)"


# ── INTEGRATION HELPER ───────────────────────────────────────────────

def improve_recommendations(
    scored_rows: List[Tuple[int, float, List[str]]],
    profile: Any,
    perfume_data: Any,
) -> List[Tuple[int, float, List[str]]]:
    """
    Main entry point to improve recommendations with strict filtering.
    
    Args:
        scored_rows: Original scored rows from ML model
        profile: PreferenceProfile object
        perfume_data: DataFrame with perfume data
        
    Returns:
        Improved and filtered scored rows
    """
    # Extract profile details
    requested_notes = set(profile.all_positive_terms)
    
    # Infer strength from notes
    requested_strength = ""
    if any(note in requested_notes for note in STRENGTH_INDICATORS["light"]):
        requested_strength = "light"
    elif any(note in requested_notes for note in STRENGTH_INDICATORS["strong"]):
        requested_strength = "strong"
    else:
        requested_strength = "medium"
    
    # Get occasion and budget
    occasion = profile.occasion
    budget_max = profile.budget_max
    
    # Add row data to scored_rows
    scored_rows_with_data = []
    for idx, score, matched_notes in scored_rows:
        row_data = perfume_data.iloc[idx].to_dict()
        scored_rows_with_data.append((idx, score, matched_notes, row_data))
    
    # Apply strict filtering
    filtered_rows = apply_strict_filtering(
        scored_rows_with_data,
        requested_notes,
        requested_strength,
        occasion,
        budget_max,
        perfume_data,
    )
    
    return filtered_rows
