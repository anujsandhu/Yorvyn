"""
User personalization: Apply user history and preferences to recommendation scoring.
"""

from typing import List, Dict, Any, Optional
from user_service import get_user_preferences
import logging


logger = logging.getLogger(__name__)


def apply_personalization(
    results: List[Dict[str, Any]],
    user_id: str,
    personalization_weight: float = 0.2,
) -> List[Dict[str, Any]]:
    """
    Adjust recommendation scores based on user preferences.
    
    Algorithm:
    final_score = base_score + (personalization_weight * user_preference_match)
    
    User preference match considers:
    - Fragrance notes matching user's history
    - Gender category preference
    - Occasion/season bias
    
    Args:
        results: List of recommendation results (each with 'score' field)
        user_id: Firebase UID
        personalization_weight: Weight factor (0.0-1.0, default 0.2)
        
    Returns:
        Results list with adjusted scores
    """
    if not results or personalization_weight == 0:
        return results
    
    try:
        # Get user preferences
        prefs = get_user_preferences(user_id)
        
        if not prefs:
            logger.warning(f"No preferences found for {user_id}, returning base results")
            return results
        
        # Extract preference data
        top_notes = _get_top_preferences(prefs.get("note_frequency", {}), n=5)
        top_occasion = _get_top_preference(prefs.get("occasion_counts", {}))
        top_gender = _get_top_preference(prefs.get("gender_counts", {}))
        
        logger.info(
            f"Personalizing for {user_id}: "
            f"notes={top_notes[:2]}, occasion={top_occasion}, gender={top_gender}"
        )
        
        # Apply personalization to each result
        personalized_results = []
        
        for result in results:
            personalized_result = result.copy()
            base_score = result.get("score", 0)
            
            # Calculate preference match score (0.0-1.0)
            match_score = _calculate_preference_match(
                result,
                top_notes,
                top_occasion,
                top_gender,
            )
            
            # Apply personalization
            adjusted_score = base_score + (personalization_weight * match_score)
            personalized_result["score"] = adjusted_score
            personalized_result["personalization_boost"] = (
                personalization_weight * match_score
            )
            
            personalized_results.append(personalized_result)
        
        # Re-sort by adjusted score
        personalized_results.sort(key=lambda x: x["score"], reverse=True)
        
        logger.info(
            f"✓ Personalized {len(personalized_results)} results for {user_id}"
        )
        return personalized_results
    
    except Exception as e:
        logger.error(f"Error applying personalization: {e}")
        # Return original results if personalization fails
        return results


def _get_top_preference(counts: Dict[str, int]) -> Optional[str]:
    """Get the most frequently occurring preference."""
    if not counts:
        return None
    
    return max(counts.items(), key=lambda x: x[1])[0]


def _get_top_preferences(counts: Dict[str, int], n: int = 5) -> List[str]:
    """Get top N preferences by frequency."""
    if not counts:
        return []
    
    sorted_prefs = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [pref[0] for pref in sorted_prefs[:n]]


def _calculate_preference_match(
    perfume: Dict[str, Any],
    preferred_notes: List[str],
    preferred_occasion: Optional[str],
    preferred_gender: Optional[str],
) -> float:
    """
    Calculate how well a perfume matches user preferences (0.0-1.0).
    
    Factors:
    - Note matching (0-0.6): Does perfume contain user's favorite notes?
    - Occasion matching (0-0.2): Is occasion aligned?
    - Gender matching (0-0.2): Is gender/style aligned?
    """
    match_score = 0.0
    
    # Extract perfume data
    perfume_notes = set()
    if "notes" in perfume:
        perfume_notes = set(str(n).lower() for n in perfume["notes"])
    if "accords" in perfume:
        perfume_notes.update(str(a).lower() for a in perfume["accords"])
    
    perfume_gender = perfume.get("gender", "").lower()
    perfume_occasion = perfume.get("occasion", "").lower()
    
    # Note matching (0-0.6)
    if preferred_notes and perfume_notes:
        preferred_notes_lower = set(n.lower() for n in preferred_notes)
        note_overlap = len(perfume_notes & preferred_notes_lower)
        note_match = min(note_overlap / len(preferred_notes), 1.0)
        match_score += note_match * 0.6
    
    # Occasion matching (0-0.2)
    if preferred_occasion and perfume_occasion:
        if preferred_occasion.lower() in perfume_occasion:
            match_score += 0.2
    
    # Gender matching (0-0.2)
    if preferred_gender and perfume_gender:
        preferred_gender_lower = preferred_gender.lower()
        if (
            preferred_gender_lower in perfume_gender
            or perfume_gender == "unisex"
        ):
            match_score += 0.2
    
    return min(match_score, 1.0)


def get_user_profile_summary(user_id: str) -> Dict[str, Any]:
    """
    Get a human-readable summary of a user's preference profile.
    
    Useful for debugging and analytics.
    
    Args:
        user_id: Firebase UID
        
    Returns:
        User profile summary
    """
    try:
        prefs = get_user_preferences(user_id)
        
        if not prefs:
            return {"status": "No preferences found"}
        
        top_notes = _get_top_preferences(prefs.get("note_frequency", {}), n=3)
        top_occasion = _get_top_preference(prefs.get("occasion_counts", {}))
        top_gender = _get_top_preference(prefs.get("gender_counts", {}))
        top_season = _get_top_preference(prefs.get("season_counts", {}))
        top_mood = _get_top_preference(prefs.get("mood_counts", {}))
        budget = prefs.get("budget_range", {})
        
        return {
            "preferred_notes": top_notes,
            "preferred_occasion": top_occasion,
            "preferred_gender": top_gender,
            "preferred_season": top_season,
            "preferred_mood": top_mood,
            "budget_range": budget,
            "last_updated": prefs.get("last_updated"),
        }
    
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return {"status": "Error retrieving profile"}
