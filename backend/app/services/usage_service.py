"""
API usage tracking and rate limiting.

Tracks daily AI token usage per user and enforces limits.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from firestore_client import get_db
import logging


logger = logging.getLogger(__name__)

# Configuration (can be overridden via environment)
DEFAULT_DAILY_LIMIT = 10000  # Tokens per day
DEFAULT_RESET_HOUR = 0  # UTC hour to reset (midnight)


def get_usage_doc_id(user_id: str, date: Optional[str] = None) -> str:
    """
    Generate usage document ID.
    
    Format: user_id_YYYY-MM-DD
    
    Args:
        user_id: Firebase UID
        date: Date string (defaults to today)
        
    Returns:
        Document ID
    """
    if not date:
        date = datetime.utcnow().strftime("%Y-%m-%d")
    
    return f"{user_id}_{date}"


def get_user_usage(user_id: str, date: Optional[str] = None) -> Dict[str, Any]:
    """
    Get current day's usage for a user.
    
    Args:
        user_id: Firebase UID
        date: Optional date (defaults to today)
        
    Returns:
        Usage document data
    """
    db = get_db()
    doc_id = get_usage_doc_id(user_id, date)
    
    try:
        doc = db.collection("api_usage").document(doc_id).get()
        
        if doc.exists:
            return doc.to_dict()
        
        # Initialize new usage document
        date_str = date or datetime.utcnow().strftime("%Y-%m-%d")
        return {
            "user_id": user_id,
            "date": date_str,
            "daily_tokens_used": 0,
            "requests_count": 0,
            "ai_requests_count": 0,
            "created_at": datetime.now().isoformat(),
            "last_reset": datetime.now().isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Error getting usage for {user_id}: {e}")
        return {}


def check_user_limit(
    user_id: str,
    tokens_to_use: int = 0,
    daily_limit: int = DEFAULT_DAILY_LIMIT,
) -> tuple[bool, str, int]:
    """
    Check if user is within daily token limit.
    
    Args:
        user_id: Firebase UID
        tokens_to_use: Tokens that would be used in this request
        daily_limit: Daily token limit (default: 10000)
        
    Returns:
        Tuple of (is_allowed, message, remaining_tokens)
    """
    usage = get_user_usage(user_id)
    current_usage = usage.get("daily_tokens_used", 0)
    
    if current_usage + tokens_to_use > daily_limit:
        remaining = max(0, daily_limit - current_usage)
        message = (
            f"Daily token limit exceeded. "
            f"Used: {current_usage}/{daily_limit}, "
            f"Remaining: {remaining}"
        )
        logger.warning(f"Rate limit hit for {user_id}: {message}")
        return False, message, remaining
    
    remaining = daily_limit - (current_usage + tokens_to_use)
    return True, "Within limit", remaining


def increment_usage(
    user_id: str,
    tokens_used: int,
    is_ai_request: bool = False,
    date: Optional[str] = None,
) -> bool:
    """
    Increment usage counters for a user.
    
    Args:
        user_id: Firebase UID
        tokens_used: Number of tokens used
        is_ai_request: Whether this was an AI API call
        date: Optional date (defaults to today)
        
    Returns:
        True if successful
    """
    db = get_db()
    doc_id = get_usage_doc_id(user_id, date)
    
    try:
        usage_doc = db.collection("api_usage").document(doc_id)
        
        # Get current data
        current = usage_doc.get()
        
        if current.exists:
            data = current.to_dict()
            update_data = {
                "daily_tokens_used": data.get("daily_tokens_used", 0) + tokens_used,
                "requests_count": data.get("requests_count", 0) + 1,
            }
        else:
            # First request this day
            date_str = date or datetime.utcnow().strftime("%Y-%m-%d")
            update_data = {
                "user_id": user_id,
                "date": date_str,
                "daily_tokens_used": tokens_used,
                "requests_count": 1,
                "created_at": datetime.now().isoformat(),
                "last_reset": datetime.now().isoformat(),
            }
        
        if is_ai_request:
            ai_count = update_data.get("ai_requests_count", 0) + 1
            update_data["ai_requests_count"] = ai_count
        
        usage_doc.set(update_data, merge=True)
        logger.debug(f"✓ Incremented usage for {user_id}: +{tokens_used} tokens")
        return True
    
    except Exception as e:
        logger.error(f"Error incrementing usage for {user_id}: {e}")
        return False


def get_user_stats(user_id: str, days: int = 7) -> Dict[str, Any]:
    """
    Get usage statistics for a user over N days.
    
    Args:
        user_id: Firebase UID
        days: Number of days to aggregate
        
    Returns:
        Usage statistics
    """
    db = get_db()
    
    try:
        # Query usage documents for the past N days
        start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        docs = (
            db.collection("api_usage")
            .where("user_id", "==", user_id)
            .where("date", ">=", start_date)
            .stream()
        )
        
        total_tokens = 0
        total_requests = 0
        ai_requests = 0
        
        for doc in docs:
            data = doc.to_dict()
            total_tokens += data.get("daily_tokens_used", 0)
            total_requests += data.get("requests_count", 0)
            ai_requests += data.get("ai_requests_count", 0)
        
        avg_tokens_per_request = (
            total_tokens // total_requests if total_requests > 0 else 0
        )
        
        today_usage = get_user_usage(user_id)
        
        return {
            "period_days": days,
            "total_tokens_used": total_tokens,
            "total_requests": total_requests,
            "ai_requests": ai_requests,
            "average_tokens_per_request": avg_tokens_per_request,
            "today_tokens_used": today_usage.get("daily_tokens_used", 0),
            "today_requests": today_usage.get("requests_count", 0),
            "today_ai_requests": today_usage.get("ai_requests_count", 0),
        }
    
    except Exception as e:
        logger.error(f"Error getting stats for {user_id}: {e}")
        return {}


def get_all_users_usage(date: Optional[str] = None, limit: int = 100) -> list:
    """
    Get usage records for all users on a specific date.
    
    Useful for analytics and monitoring.
    
    Args:
        date: Date to query (defaults to today)
        limit: Max records to return
        
    Returns:
        List of usage documents
    """
    db = get_db()
    date_str = date or datetime.utcnow().strftime("%Y-%m-%d")
    
    try:
        docs = (
            db.collection("api_usage")
            .where("date", "==", date_str)
            .order_by("daily_tokens_used", direction="DESCENDING")
            .limit(limit)
            .stream()
        )
        
        return [doc.to_dict() for doc in docs]
    
    except Exception as e:
        logger.error(f"Error getting all users usage: {e}")
        return []
