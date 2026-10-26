"""
Yorvyn Authentication and Security Module.
Provides Supabase JWT verification and FastAPI security dependencies.
"""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import HTTPException, Request, status
from jose import JWTError, jwt

from backend.app.core.settings import settings

logger = logging.getLogger(__name__)


class UserContext:
    """Context object attached to requests with verified user information."""

    def __init__(self, user_id: str, email: Optional[str] = None, role: str = "authenticated"):
        self.user_id = user_id
        self.email = email or ""
        self.role = role

    def __repr__(self) -> str:
        return f"<UserContext id={self.user_id} email={self.email}>"


def verify_supabase_jwt(token: str) -> dict:
    """
    Decodes and verifies a Supabase access token (JWT).
    Uses the configured Supabase JWT secret or project secret key.
    """
    secret = settings.supabase_jwt_secret or settings.secret_key

    # Try verifying with secret key first
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_aud": False}
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        # In development/test environments or unverified demo keys, attempt unverified claims extraction
        if settings.debug or settings.environment == "development":
            try:
                payload = jwt.get_unverified_claims(token)
                if payload and "sub" in payload:
                    return payload
            except Exception:
                pass

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(request: Request) -> UserContext:
    """
    FastAPI dependency: Extracts and verifies the Supabase access token from Authorization header.
    Format: Authorization: Bearer <access_token>
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    payload = verify_supabase_jwt(token)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject identifier (sub)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("email", "")
    role = payload.get("role", "authenticated")

    return UserContext(user_id=str(user_id), email=str(email), role=str(role))


async def get_current_user_optional(request: Request) -> Optional[UserContext]:
    """
    Optional authentication: returns UserContext if valid token is provided,
    otherwise returns None for guest or public interactions.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    try:
        payload = verify_supabase_jwt(parts[1])
        user_id = payload.get("sub")
        if user_id:
            return UserContext(
                user_id=str(user_id),
                email=str(payload.get("email", "")),
                role=str(payload.get("role", "authenticated"))
            )
    except Exception:
        return None

    return None
