"""
User routes: Authenticated endpoints for user data, preferences, history, and feedback.

Protected endpoints requiring Firebase authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List
from auth import get_current_user, UserContext
from user_service import (
    create_user,
    get_user,
    get_user_preferences,
    update_preferences,
    get_user_history,
    save_feedback,
    get_perfume_feedback,
)
from usage_service import get_user_stats
from personalization_service import get_user_profile_summary
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["user"])


# ============================================================================
# Pydantic Models
# ============================================================================


class PreferencesUpdate(BaseModel):
    """Request model for updating user preferences."""
    
    gender: Optional[str] = Field(None, description="male/female/unisex")
    occasion: Optional[str] = Field(None, description="e.g., casual, formal, evening")
    season: Optional[str] = Field(None, description="spring/summer/fall/winter")
    mood: Optional[str] = Field(None, description="e.g., fresh, warm, spicy")
    notes: Optional[List[str]] = Field(None, description="Favorite fragrance notes")
    budget_min: Optional[int] = Field(None, ge=0, description="Budget minimum in INR")
    budget_max: Optional[int] = Field(None, ge=0, description="Budget maximum in INR")


class FeedbackRequest(BaseModel):
    """Request model for submitting perfume feedback."""
    
    perfume_id: str = Field(..., description="ID of perfume being reviewed")
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5")
    comment: Optional[str] = Field(None, max_length=500, description="Optional comment")


class UserProfile(BaseModel):
    """Response model for user profile."""
    
    user_id: str
    email: str
    display_name: str
    created_at: str


class UserPreferencesResponse(BaseModel):
    """Response model for user preferences."""
    
    gender_counts: dict
    occasion_counts: dict
    season_counts: dict
    mood_counts: dict
    note_frequency: dict
    budget_range: dict
    last_updated: str


class HistoryEntry(BaseModel):
    """Response model for history entry."""
    
    query: str
    results_count: int
    selected_perfume_id: Optional[str]
    timestamp: str


class UsageStats(BaseModel):
    """Response model for usage statistics."""
    
    period_days: int
    total_tokens_used: int
    total_requests: int
    ai_requests: int
    average_tokens_per_request: int
    today_tokens_used: int
    today_requests: int
    today_ai_requests: int


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/me", response_model=UserProfile, summary="Get current user profile")
async def get_my_profile(user: UserContext = Depends(get_current_user)):
    """
    Get current authenticated user's profile.
    
    **Authentication:** Required (Bearer token)
    
    Returns:
        User profile data
    """
    user_data = get_user(user.user_id)
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return user_data


@router.post("/preferences", summary="Update user preferences")
async def update_user_preferences(
    update: PreferencesUpdate,
    user: UserContext = Depends(get_current_user),
):
    """
    Update user's preference profile.
    
    Used to personalize future recommendations. Can be called after each
    interaction to accumulate preference data.
    
    **Authentication:** Required (Bearer token)
    
    Args:
        gender: Male, female, or unisex preference
        occasion: Preferred occasion (casual, formal, evening, etc.)
        season: Preferred season (spring, summer, fall, winter)
        mood: Preferred vibe (fresh, warm, spicy, etc.)
        notes: List of favorite fragrance notes
        budget_min/max: Price range in INR
        
    Returns:
        Success message
    """
    success = update_preferences(
        user_id=user.user_id,
        gender=update.gender,
        occasion=update.occasion,
        season=update.season,
        mood=update.mood,
        notes=update.notes,
        budget_min=update.budget_min,
        budget_max=update.budget_max,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences",
        )
    
    return {"status": "preferences updated"}


@router.get("/preferences", response_model=UserPreferencesResponse, summary="Get user preferences")
async def get_my_preferences(user: UserContext = Depends(get_current_user)):
    """
    Get current user's preference profile.
    
    Shows aggregated preferences from past interactions.
    
    **Authentication:** Required (Bearer token)
    
    Returns:
        User preferences data
    """
    prefs = get_user_preferences(user.user_id)
    
    if not prefs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preferences not found",
        )
    
    return prefs


@router.get("/profile-summary", summary="Get personalized profile summary")
async def get_profile_summary(user: UserContext = Depends(get_current_user)):
    """
    Get a human-readable summary of user's preference profile.
    
    Shows: top notes, preferred occasion, gender, season, mood, budget.
    
    **Authentication:** Required (Bearer token)
    
    Returns:
        Profile summary
    """
    summary = get_user_profile_summary(user.user_id)
    return summary


@router.get("/history", response_model=List[HistoryEntry], summary="Get user query history")
async def get_my_history(
    limit: int = 20,
    user: UserContext = Depends(get_current_user),
):
    """
    Get user's recent query history.
    
    Shows up to `limit` recent searches/recommendations.
    
    **Authentication:** Required (Bearer token)
    
    Args:
        limit: Max number of history entries (default: 20)
        
    Returns:
        List of recent queries
    """
    if limit > 100:
        limit = 100  # Cap at 100
    
    history = get_user_history(user.user_id, limit=limit)
    return history


@router.post("/feedback", summary="Submit perfume feedback")
async def submit_feedback(
    feedback: FeedbackRequest,
    user: UserContext = Depends(get_current_user),
):
    """
    Submit feedback (rating + comment) for a perfume.
    
    Helps improve personalization and provides social proof.
    
    **Authentication:** Required (Bearer token)
    
    Args:
        perfume_id: ID of perfume being reviewed
        rating: Rating 1-5 stars
        comment: Optional text comment (max 500 chars)
        
    Returns:
        Success message
    """
    success = save_feedback(
        user_id=user.user_id,
        perfume_id=feedback.perfume_id,
        rating=feedback.rating,
        comment=feedback.comment,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save feedback",
        )
    
    return {"status": "feedback saved"}


@router.get("/feedback/{perfume_id}", summary="Get perfume feedback")
async def get_perfume_feedback_endpoint(perfume_id: str):
    """
    Get aggregated feedback for a perfume.
    
    Shows average rating, review count, and sample comments.
    
    **Authentication:** Not required
    
    Args:
        perfume_id: ID of perfume
        
    Returns:
        Aggregated feedback data
    """
    feedback = get_perfume_feedback(perfume_id)
    return feedback


@router.get("/usage", response_model=UsageStats, summary="Get API usage statistics")
async def get_usage(
    days: int = 7,
    user: UserContext = Depends(get_current_user),
):
    """
    Get user's API usage statistics.
    
    Shows token usage, request counts, AI provider usage over N days.
    
    **Authentication:** Required (Bearer token)
    
    Args:
        days: Number of days to aggregate (default: 7)
        
    Returns:
        Usage statistics
    """
    if days > 90:
        days = 90  # Cap at 90 days
    
    stats = get_user_stats(user.user_id, days=days)
    
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage stats",
        )
    
    return stats


# ============================================================================
# Initialization Helper (call from main.py startup)
# ============================================================================


async def ensure_user_exists(user_id: str, email: str, display_name: str = ""):
    """
    Create user if not exists (called on first login).
    
    Args:
        user_id: Firebase UID
        email: User email
        display_name: Optional display name
    """
    existing_user = get_user(user_id)
    
    if not existing_user:
        logger.info(f"Creating new user: {user_id}")
        create_user(user_id, email, display_name)
    else:
        logger.debug(f"User exists: {user_id}")
