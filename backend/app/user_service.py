"""
User service: CRUD operations for user data, preferences, and history.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from firestore_client import get_db
import logging


logger = logging.getLogger(__name__)


class UserPreferences:
    """User preference model."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.gender_counts = {"male": 0, "female": 0, "unisex": 0}
        self.occasion_counts = {}
        self.season_counts = {}
        self.mood_counts = {}
        self.note_frequency = {}
        self.budget_range = {"min": 0, "max": 10000}
        self.last_updated = datetime.now().isoformat()


def create_user(user_id: str, email: str, display_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new user in Firestore.
    
    Args:
        user_id: Firebase UID
        email: User email
        display_name: Optional display name
        
    Returns:
        User document data
    """
    db = get_db()
    
    user_data = {
        "user_id": user_id,
        "email": email,
        "display_name": display_name or "",
        "created_at": datetime.now().isoformat(),
        "last_login": datetime.now().isoformat(),
        "is_active": True,
    }
    
    try:
        db.collection("users").document(user_id).set(user_data)
        logger.info(f"✓ Created user: {user_id}")
        return user_data
    except Exception as e:
        logger.error(f"Error creating user {user_id}: {e}")
        raise


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve user document.
    
    Args:
        user_id: Firebase UID
        
    Returns:
        User data or None if not found
    """
    db = get_db()
    
    try:
        doc = db.collection("users").document(user_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return None


def update_user_login(user_id: str) -> bool:
    """Update user's last_login timestamp."""
    db = get_db()
    
    try:
        db.collection("users").document(user_id).update({
            "last_login": datetime.now().isoformat()
        })
        return True
    except Exception as e:
        logger.error(f"Error updating login for {user_id}: {e}")
        return False


def get_user_preferences(user_id: str) -> Dict[str, Any]:
    """
    Get user preferences document.
    
    Creates empty preferences if not found.
    
    Args:
        user_id: Firebase UID
        
    Returns:
        User preferences data
    """
    db = get_db()
    
    try:
        doc = db.collection("user_preferences").document(user_id).get()
        if doc.exists:
            return doc.to_dict()
        
        # Initialize preferences
        prefs = UserPreferences(user_id)
        init_data = {
            "user_id": user_id,
            "gender_counts": prefs.gender_counts,
            "occasion_counts": prefs.occasion_counts,
            "season_counts": prefs.season_counts,
            "mood_counts": prefs.mood_counts,
            "note_frequency": prefs.note_frequency,
            "budget_range": prefs.budget_range,
            "last_updated": datetime.now().isoformat(),
        }
        db.collection("user_preferences").document(user_id).set(init_data)
        return init_data
    
    except Exception as e:
        logger.error(f"Error getting preferences for {user_id}: {e}")
        return {}


def update_preferences(
    user_id: str,
    gender: Optional[str] = None,
    occasion: Optional[str] = None,
    season: Optional[str] = None,
    mood: Optional[str] = None,
    notes: Optional[List[str]] = None,
    budget_min: Optional[int] = None,
    budget_max: Optional[int] = None,
) -> bool:
    """
    Update user preferences based on interaction.
    
    Args:
        user_id: Firebase UID
        gender: Gender preference (male/female/unisex)
        occasion: Occasion (e.g., casual, formal, evening)
        season: Season (spring, summer, fall, winter)
        mood: Mood/vibe (e.g., fresh, warm, spicy)
        notes: List of preferred fragrance notes
        budget_min/budget_max: Budget range in INR
        
    Returns:
        True if successful
    """
    db = get_db()
    
    try:
        prefs_doc = db.collection("user_preferences").document(user_id)
        prefs = prefs_doc.get()
        
        update_data = {"last_updated": datetime.now().isoformat()}
        
        if prefs.exists:
            data = prefs.to_dict()
        else:
            # Initialize if not exists
            data = UserPreferences(user_id).__dict__
        
        # Update gender counts
        if gender and gender.lower() in ["male", "female", "unisex"]:
            counts = data.get("gender_counts", {})
            counts[gender.lower()] = counts.get(gender.lower(), 0) + 1
            update_data["gender_counts"] = counts
        
        # Update occasion counts
        if occasion:
            counts = data.get("occasion_counts", {})
            counts[occasion] = counts.get(occasion, 0) + 1
            update_data["occasion_counts"] = counts
        
        # Update season counts
        if season:
            counts = data.get("season_counts", {})
            counts[season] = counts.get(season, 0) + 1
            update_data["season_counts"] = counts
        
        # Update mood counts
        if mood:
            counts = data.get("mood_counts", {})
            counts[mood] = counts.get(mood, 0) + 1
            update_data["mood_counts"] = counts
        
        # Update note frequency
        if notes:
            note_freq = data.get("note_frequency", {})
            for note in notes:
                note_freq[note] = note_freq.get(note, 0) + 1
            update_data["note_frequency"] = note_freq
        
        # Update budget range
        if budget_min is not None or budget_max is not None:
            budget = data.get("budget_range", {"min": 0, "max": 10000})
            if budget_min is not None:
                budget["min"] = budget_min
            if budget_max is not None:
                budget["max"] = budget_max
            update_data["budget_range"] = budget
        
        prefs_doc.set(update_data, merge=True)
        logger.info(f"✓ Updated preferences for {user_id}")
        return True
    
    except Exception as e:
        logger.error(f"Error updating preferences for {user_id}: {e}")
        return False


def log_query(
    user_id: str,
    query: str,
    results_count: int,
    selected_perfume_id: Optional[str] = None,
    filters: Optional[Dict] = None,
) -> bool:
    """
    Log a user query to user_history collection.
    
    Args:
        user_id: Firebase UID
        query: User's search/recommendation query
        results_count: Number of results returned
        selected_perfume_id: If user selected a result
        filters: Any applied filters
        
    Returns:
        True if successful
    """
    db = get_db()
    
    try:
        history_entry = {
            "user_id": user_id,
            "query": query,
            "results_count": results_count,
            "selected_perfume_id": selected_perfume_id,
            "filters": filters or {},
            "timestamp": datetime.now().isoformat(),
        }
        
        db.collection("user_history").add(history_entry)
        logger.info(f"✓ Logged query for {user_id}: {query[:50]}...")
        return True
    
    except Exception as e:
        logger.error(f"Error logging query for {user_id}: {e}")
        return False


def get_user_history(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Retrieve user's recent query history.
    
    Args:
        user_id: Firebase UID
        limit: Max number of records to return
        
    Returns:
        List of history entries
    """
    db = get_db()
    
    try:
        docs = (
            db.collection("user_history")
            .where("user_id", "==", user_id)
            .order_by("timestamp", direction="DESCENDING")
            .limit(limit)
            .stream()
        )
        
        history = [doc.to_dict() for doc in docs]
        return history
    
    except Exception as e:
        logger.error(f"Error retrieving history for {user_id}: {e}")
        return []


def save_feedback(
    user_id: str,
    perfume_id: str,
    rating: int,
    comment: Optional[str] = None,
) -> bool:
    """
    Save user feedback on a perfume.
    
    Args:
        user_id: Firebase UID
        perfume_id: Perfume ID being reviewed
        rating: Rating 1-5
        comment: Optional user comment
        
    Returns:
        True if successful
    """
    db = get_db()
    
    if not 1 <= rating <= 5:
        logger.warning(f"Invalid rating {rating} for {perfume_id}")
        return False
    
    try:
        feedback_data = {
            "user_id": user_id,
            "perfume_id": perfume_id,
            "rating": rating,
            "comment": comment or "",
            "timestamp": datetime.now().isoformat(),
        }
        
        db.collection("feedback").add(feedback_data)
        logger.info(f"✓ Saved feedback from {user_id} for {perfume_id}: {rating}/5")
        return True
    
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        return False


def get_perfume_feedback(perfume_id: str) -> Dict[str, Any]:
    """
    Get aggregated feedback for a perfume.
    
    Args:
        perfume_id: Perfume ID
        
    Returns:
        Average rating, count, and comments
    """
    db = get_db()
    
    try:
        docs = db.collection("feedback").where("perfume_id", "==", perfume_id).stream()
        
        ratings = []
        comments = []
        
        for doc in docs:
            data = doc.to_dict()
            ratings.append(data.get("rating", 0))
            if data.get("comment"):
                comments.append(data["comment"])
        
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        
        return {
            "average_rating": round(avg_rating, 2),
            "total_reviews": len(ratings),
            "comments": comments[:5],  # Latest 5 comments
        }
    
    except Exception as e:
        logger.error(f"Error getting feedback for {perfume_id}: {e}")
        return {"average_rating": 0, "total_reviews": 0, "comments": []}
