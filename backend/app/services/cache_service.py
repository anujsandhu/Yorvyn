"""
AI response caching service.

Caches AI provider responses with TTL to reduce API calls and costs.
"""

import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from firestore_client import get_db
import logging
import json


logger = logging.getLogger(__name__)

# Configuration (in hours)
DEFAULT_CACHE_TTL = 24  # Cache responses for 24 hours


def hash_prompt(prompt: str, context: Optional[Dict] = None, uid: Optional[str] = None) -> str:
    """
    Generate SHA256 hash of uid + prompt + context.

    The uid is included so cached AI responses are never shared across users.

    Args:
        prompt: The prompt/query
        context: Optional context dict (e.g., filters, user prefs)
        uid: Firebase user ID — MUST be provided for user-specific caching

    Returns:
        SHA256 hash string
    """
    # Always prefix with uid to ensure per-user isolation.
    # If uid is absent (e.g. public endpoint), prefix with "anon".
    user_prefix = uid if uid else "anon"
    cache_key = f"{user_prefix}|{prompt}"

    if context:
        sorted_context = json.dumps(context, sort_keys=True)
        cache_key = f"{cache_key}|{sorted_context}"

    return hashlib.sha256(cache_key.encode()).hexdigest()


def get_cached_response(prompt: str, context: Optional[Dict] = None, uid: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached AI response if available and not expired.

    Args:
        prompt: The prompt/query
        context: Optional context dict
        uid: Firebase user ID — required for user-scoped caching

    Returns:
        Cached response data or None if not found/expired
    """
    db = get_db()
    cache_key = hash_prompt(prompt, context, uid=uid)
    
    try:
        doc = db.collection("ai_cache").document(cache_key).get()
        
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        
        # Check if cache has expired
        expires_at = data.get("expires_at")
        if expires_at:
            expiry_time = datetime.fromisoformat(expires_at)
            if datetime.now() > expiry_time:
                logger.info(f"Cache expired for key {cache_key[:8]}...")
                # Optionally delete expired entry
                try:
                    doc.reference.delete()
                except:
                    pass
                return None
        
        logger.info(f"✓ Cache hit for {cache_key[:8]}... (saved API call)")
        # Update hit count
        doc.reference.update({"hits": data.get("hits", 0) + 1})
        
        return {
            "response": data.get("response"),
            "provider": data.get("provider"),
            "tokens_used": data.get("tokens_used", 0),
            "cached": True,
            "created_at": data.get("created_at"),
        }
    
    except Exception as e:
        logger.error(f"Error retrieving cache: {e}")
        return None


def set_cached_response(
    prompt: str,
    response: str,
    provider: str,
    tokens_used: int,
    context: Optional[Dict] = None,
    ttl_hours: int = DEFAULT_CACHE_TTL,
    uid: Optional[str] = None,
) -> bool:
    """
    Store AI response in cache, scoped by uid.

    Args:
        prompt: The prompt/query
        response: AI response text
        provider: Provider name (groq, openrouter, gemini, hf)
        tokens_used: Tokens used for this request
        context: Optional context dict
        ttl_hours: Time to live in hours
        uid: Firebase user ID — required for user-scoped caching

    Returns:
        True if successful
    """
    db = get_db()
    cache_key = hash_prompt(prompt, context, uid=uid)
    
    try:
        expires_at = (datetime.now() + timedelta(hours=ttl_hours)).isoformat()
        
        cache_data = {
            "prompt": prompt,
            "context": context or {},
            "response": response,
            "provider": provider,
            "tokens_used": tokens_used,
            "created_at": datetime.now().isoformat(),
            "expires_at": expires_at,
            "hits": 0,
        }
        
        db.collection("ai_cache").document(cache_key).set(cache_data)
        logger.info(f"✓ Cached response from {provider} (TTL: {ttl_hours}h)")
        return True
    
    except Exception as e:
        logger.error(f"Error caching response: {e}")
        return False


def clear_expired_cache() -> int:
    """
    Remove expired cache entries.
    
    Can be called periodically (e.g., via Firestore scheduled function).
    
    Returns:
        Number of entries deleted
    """
    db = get_db()
    
    try:
        now = datetime.now().isoformat()
        
        docs = (
            db.collection("ai_cache")
            .where("expires_at", "<=", now)
            .stream()
        )
        
        deleted = 0
        for doc in docs:
            doc.reference.delete()
            deleted += 1
        
        if deleted > 0:
            logger.info(f"✓ Cleared {deleted} expired cache entries")
        
        return deleted
    
    except Exception as e:
        logger.error(f"Error clearing expired cache: {e}")
        return 0


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache performance statistics.
    
    Returns:
        Cache stats
    """
    db = get_db()
    
    try:
        docs = db.collection("ai_cache").stream()
        
        total_entries = 0
        total_hits = 0
        total_tokens_saved = 0
        providers_used = {}
        
        for doc in docs:
            data = doc.to_dict()
            total_entries += 1
            hits = data.get("hits", 0)
            total_hits += hits
            total_tokens_saved += (hits * data.get("tokens_used", 0))
            
            provider = data.get("provider", "unknown")
            if provider not in providers_used:
                providers_used[provider] = 0
            providers_used[provider] += 1
        
        return {
            "total_cached_responses": total_entries,
            "total_cache_hits": total_hits,
            "estimated_tokens_saved": total_tokens_saved,
            "providers": providers_used,
        }
    
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {}


def invalidate_cache_for_prompt(prompt: str, context: Optional[Dict] = None) -> bool:
    """
    Manually invalidate (delete) a specific cache entry.
    
    Useful if you know cached data is outdated.
    
    Args:
        prompt: The prompt/query
        context: Optional context dict
        
    Returns:
        True if deleted, False if not found or error
    """
    db = get_db()
    cache_key = hash_prompt(prompt, context)
    
    try:
        db.collection("ai_cache").document(cache_key).delete()
        logger.info(f"✓ Invalidated cache for {cache_key[:8]}...")
        return True
    
    except Exception as e:
        logger.warning(f"Error invalidating cache: {e}")
        return False
