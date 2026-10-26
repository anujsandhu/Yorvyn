"""
Firebase Authentication utilities.

Provides token verification and FastAPI dependency for protected routes.
"""

from typing import Optional
from fastapi import HTTPException, Request, status
from firebase_admin import auth
import logging


logger = logging.getLogger(__name__)


class UserContext:
    """Context object attached to requests with user info."""
    
    def __init__(self, user_id: str, email: Optional[str] = None):
        self.user_id = user_id
        self.email = email


async def get_current_user(request: Request) -> UserContext:
    """
    FastAPI dependency: Extract and verify Firebase ID token from Authorization header.
    
    Expected header format: Authorization: Bearer <firebase_id_token>
    
    Args:
        request: FastAPI request object
        
    Returns:
        UserContext with verified user_id and email
        
    Raises:
        HTTPException: If token missing, invalid, or expired (401)
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Expected format: "Bearer <token>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise ValueError("Invalid authorization header format")
        
        token = parts[1]
    except (IndexError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Verify Firebase ID token
        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token.get("uid")
        email = decoded_token.get("email", "")
        
        if not user_id:
            raise ValueError("Token missing uid")
        
        logger.info(f"✓ Verified user: {user_id}")
        return UserContext(user_id=user_id, email=email)
    
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except auth.InvalidIdTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_optional(request: Request) -> Optional[UserContext]:
    """
    Optional authentication: Returns user if valid token present, None otherwise.
    
    Useful for endpoints that support both authenticated and guest users.
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        return None
    
    try:
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        
        token = parts[1]
        decoded_token = auth.verify_id_token(token)
        user_id = decoded_token.get("uid")
        email = decoded_token.get("email", "")
        
        if user_id:
            return UserContext(user_id=user_id, email=email)
    except Exception:
        pass
    
    return None
