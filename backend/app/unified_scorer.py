"""
Unified Scorer — Single consistent scoring pipeline for perfume recommendations.

This module provides a unified scoring system with clear, documented weights:
- Note match: 40% (from ML TF-IDF similarity)
- Occasion match: 20% (how well perfume fits the occasion)
- Rating: 20% (normalized user ratings)
- Price fit: 10% (how well price fits budget)
- Popularity: 10% (rating count + sold)

This replaces scattered scoring logic across the codebase.
"""
from __future__ import annotations
import numpy as np
from typing import Dict, Any, Optional, List


# ── Scoring Weights ───────────────────────────────────────────────────

WEIGHTS = {
    "note_match": 0.40,      # ML-based note similarity
    "occasion_match": 0.20,  # Occasion appropriateness
    "rating": 0.20,          # User ratings (quality signal)
    "price_fit": 0.10,       # Budget compatibility
    "popularity": 0.10,      # Social proof (rating_count + sold)
}


# ── Occasion Requirements ─────────────────────────────────────────────

OCCASION_NOTES = {
    "office": {
        "required": ["fresh", "clean", "citrus", "green", "light"],
        "avoid": ["oud", "heavy", "intense", "smoky"],
        "intensity": "light",
    },
    "work": {
        "required": ["fresh", "clean", "citrus", "green", "light"],
        "avoid": ["oud", "heavy", "intense", "smoky"],
        "intensity": "light",
    },
    "date": {
        "required": ["vanilla", "amber", "musk", "rose", "warm"],
        "avoid": ["sport", "gym", "aquatic"],
        "intensity": "medium",
    },
    "romantic": {
        "required": ["vanilla", "amber", "musk", "rose", "warm"],
        "avoid": ["sport", "gym", "aquatic"],
        "intensity": "medium",
    },
    "party": {
        "required": ["oud", "spicy", "bold", "intense", "amber"],
        "avoid": ["light", "subtle", "soft"],
        "intensity": "strong",
    },
    "night": {
        "required": ["oud", "spicy", "bold", "intense", "amber"],
        "avoid": ["light", "subtle", "soft"],
        "intensity": "strong",
    },
    "wedding": {
        "required": ["rose", "elegant", "floral", "amber", "woody"],
        "avoid": ["sport", "gym", "casual"],
        "intensity": "medium",
    },
    "daily": {
        "required": ["fresh", "clean", "light", "versatile"],
        "avoid": ["heavy", "intense", "overpowering"],
        "intensity": "light",
    },
    "gym": {
        "required": ["fresh", "aquatic", "clean", "citrus", "sport"],
        "avoid": ["heavy", "sweet", "gourmand"],
        "intensity": "light",
    },
    "outdoor": {
        "required": ["green", "woody", "fresh", "earthy", "citrus"],
        "avoid": ["heavy", "sweet", "powdery"],
        "intensity": "medium",
    },
    "formal": {
        "required": ["woody", "amber", "spicy", "elegant", "musk"],
        "avoid": ["casual", "sport", "playful"],
        "intensity": "medium",
    },
    "casual": {
        "required": ["fresh", "clean", "light", "citrus", "soft"],
        "avoid": ["intense", "heavy", "formal"],
        "intensity": "light",
    },
}


def compute_unified_score(
    perfume: Dict[str, Any],
    context: Dict[str, Any],
    ml_score: float,
) -> float:
    """
    Compute unified score with clear weights.
    
    Score = (note_match * 0.4) +
            (occasion_match * 0.2) +
            (rating_normalized * 0.2) +
            (price_fit * 0.1) +
            (popularity * 0.1)
    
    Args:
        perfume: Perfume dictionary with fields (name, brand, accords, rating, price, etc.)
        context: User context (occasion, budget, mood, etc.)
        ml_score: ML-based note similarity score (0.0 - 1.0)
        
    Returns:
        Final unified score (0.0 - 1.0)
    """
    # Note match (from ML)
    note_score = ml_score * WEIGHTS["note_match"]
    
    # Occasion match
    occasion_score = compute_occasion_match(perfume, context) * WEIGHTS["occasion_match"]
    
    # Rating normalized
    rating = perfume.get("rating", 4.0)
    rating_score = (rating / 5.0) * WEIGHTS["rating"]
    
    # Price fit
    price_score = compute_price_fit(perfume, context) * WEIGHTS["price_fit"]
    
    # Popularity
    popularity_score = compute_popularity(perfume) * WEIGHTS["popularity"]
    
    # Combine scores
    final_score = note_score + occasion_score + rating_score + price_score + popularity_score
    
    return min(1.0, max(0.0, final_score))


def compute_occasion_match(perfume: Dict[str, Any], context: Dict[str, Any]) -> float:
    """
    Compute how well perfume matches occasion.
    
    Args:
        perfume: Perfume dictionary
        context: User context with occasion
        
    Returns:
        Occasion match score (0.0 - 1.0)
    """
    if not context.get("occasion"):
        return 0.5  # Neutral if no occasion specified
    
    occasion = context["occasion"].lower()
    accords = perfume.get("accords", "").lower()
    
    if occasion not in OCCASION_NOTES:
        return 0.5  # Unknown occasion, neutral score
    
    requirements = OCCASION_NOTES[occasion]
    
    # Check required notes
    required_notes = requirements["required"]
    required_matches = sum(1 for note in required_notes if note in accords)
    required_score = required_matches / len(required_notes) if required_notes else 0.5
    
    # Check avoided notes (penalty)
    avoid_notes = requirements.get("avoid", [])
    avoid_matches = sum(1 for note in avoid_notes if note in accords)
    avoid_penalty = avoid_matches / len(avoid_notes) if avoid_notes else 0.0
    
    # Combine: reward required, penalize avoided
    match_score = required_score - (avoid_penalty * 0.5)
    
    return min(1.0, max(0.0, match_score))


def compute_price_fit(perfume: Dict[str, Any], context: Dict[str, Any]) -> float:
    """
    Compute how well price fits budget.
    
    Args:
        perfume: Perfume dictionary with price
        context: User context with budget_max
        
    Returns:
        Price fit score (0.0 - 1.0)
    """
    if not context.get("budget_max"):
        return 0.5  # Neutral if no budget specified
    
    price = perfume.get("price", 0)
    budget = context["budget_max"]
    
    if price <= 0:
        return 0.5  # Unknown price, neutral
    
    if price <= budget:
        # Perfect fit: within budget
        # Reward being closer to budget (not too cheap)
        ratio = price / budget
        if ratio >= 0.7:
            return 1.0  # Sweet spot: 70-100% of budget
        elif ratio >= 0.5:
            return 0.9  # Good: 50-70% of budget
        else:
            return 0.7  # Okay: under 50% of budget
    
    elif price <= budget * 1.2:
        # Slightly over budget (20% tolerance)
        return 0.6
    
    elif price <= budget * 1.5:
        # Moderately over budget
        return 0.3
    
    else:
        # Way over budget
        return 0.0


def compute_popularity(perfume: Dict[str, Any]) -> float:
    """
    Compute popularity score from rating_count and sold.
    
    Args:
        perfume: Perfume dictionary with rating_count and sold
        
    Returns:
        Popularity score (0.0 - 1.0)
    """
    rating_count = perfume.get("rating_count", 0)
    sold = perfume.get("sold", 0)
    
    # Log scale for better distribution
    rating_count_log = np.log1p(rating_count)
    sold_log = np.log1p(sold)
    
    # Normalize (assuming max values from dataset analysis)
    # Max rating_count ~10,000 → log ~9.2
    # Max sold ~5,000 → log ~8.5
    rating_count_norm = min(1.0, rating_count_log / 9.2)
    sold_norm = min(1.0, sold_log / 8.5)
    
    # Combine: rating_count is more reliable than sold
    popularity = (rating_count_norm * 0.7 + sold_norm * 0.3)
    
    return popularity


def compute_intensity_match(perfume: Dict[str, Any], context: Dict[str, Any]) -> float:
    """
    Compute how well perfume intensity matches user preference.
    
    Args:
        perfume: Perfume dictionary with accords
        context: User context with occasion or explicit intensity preference
        
    Returns:
        Intensity match score (0.0 - 1.0)
    """
    accords = perfume.get("accords", "").lower()
    
    # Determine desired intensity
    desired_intensity = context.get("intensity")
    
    if not desired_intensity and context.get("occasion"):
        # Infer from occasion
        occasion = context["occasion"].lower()
        if occasion in OCCASION_NOTES:
            desired_intensity = OCCASION_NOTES[occasion].get("intensity", "medium")
    
    if not desired_intensity:
        return 0.5  # Neutral if unknown
    
    # Detect perfume intensity from accords
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
    
    # Match score
    if perfume_intensity == desired_intensity:
        return 1.0  # Perfect match
    elif desired_intensity == "medium":
        return 0.7  # Medium is flexible
    elif (desired_intensity == "light" and perfume_intensity == "medium") or \
         (desired_intensity == "strong" and perfume_intensity == "medium"):
        return 0.6  # Close match
    else:
        return 0.2  # Mismatch


def rank_recommendations(
    recommendations: List[Dict[str, Any]],
    context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Re-rank recommendations using unified scoring.
    
    Args:
        recommendations: List of perfume recommendations with ml_score
        context: User context
        
    Returns:
        Re-ranked list with unified scores
    """
    scored_recs = []
    
    for rec in recommendations:
        # Get ML score (note similarity)
        ml_score = rec.get("match_score", rec.get("ml_score", rec.get("score", 0.7)))
        
        # Compute unified score
        unified_score = compute_unified_score(rec, context, ml_score)
        
        # Add unified score to recommendation
        rec["unified_score"] = unified_score
        rec["final_score"] = unified_score  # Update final_score
        
        scored_recs.append(rec)
    
    # Sort by unified score
    scored_recs.sort(key=lambda x: x["unified_score"], reverse=True)
    
    return scored_recs


def explain_score(perfume: Dict[str, Any], context: Dict[str, Any], ml_score: float) -> Dict[str, Any]:
    """
    Generate detailed score breakdown for debugging/transparency.
    
    Args:
        perfume: Perfume dictionary
        context: User context
        ml_score: ML-based note similarity score
        
    Returns:
        Dictionary with score breakdown
    """
    note_score = ml_score * WEIGHTS["note_match"]
    occasion_score = compute_occasion_match(perfume, context) * WEIGHTS["occasion_match"]
    rating = perfume.get("rating", 4.0)
    rating_score = (rating / 5.0) * WEIGHTS["rating"]
    price_score = compute_price_fit(perfume, context) * WEIGHTS["price_fit"]
    popularity_score = compute_popularity(perfume) * WEIGHTS["popularity"]
    
    final_score = note_score + occasion_score + rating_score + price_score + popularity_score
    
    return {
        "final_score": min(1.0, max(0.0, final_score)),
        "breakdown": {
            "note_match": {
                "score": note_score,
                "weight": WEIGHTS["note_match"],
                "raw": ml_score,
            },
            "occasion_match": {
                "score": occasion_score,
                "weight": WEIGHTS["occasion_match"],
                "raw": compute_occasion_match(perfume, context),
            },
            "rating": {
                "score": rating_score,
                "weight": WEIGHTS["rating"],
                "raw": rating / 5.0,
            },
            "price_fit": {
                "score": price_score,
                "weight": WEIGHTS["price_fit"],
                "raw": compute_price_fit(perfume, context),
            },
            "popularity": {
                "score": popularity_score,
                "weight": WEIGHTS["popularity"],
                "raw": compute_popularity(perfume),
            },
        },
    }


# ── Example Usage ─────────────────────────────────────────────────────

if __name__ == "__main__":
    # Example: Score a perfume
    perfume = {
        "name": "Dior Sauvage",
        "brand": "Dior",
        "accords": "fresh citrus woody spicy",
        "rating": 4.5,
        "price": 85.0,
        "rating_count": 5000,
        "sold": 2000,
    }
    
    context = {
        "occasion": "office",
        "budget_max": 100.0,
    }
    
    ml_score = 0.85  # From TF-IDF similarity
    
    # Compute unified score
    score = compute_unified_score(perfume, context, ml_score)
    print(f"Unified Score: {score:.3f}")
    
    # Get detailed breakdown
    breakdown = explain_score(perfume, context, ml_score)
    print(f"\nScore Breakdown:")
    for component, details in breakdown["breakdown"].items():
        print(f"  {component}: {details['score']:.3f} (weight: {details['weight']}, raw: {details['raw']:.3f})")
