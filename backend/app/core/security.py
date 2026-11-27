"""
Yorvyn Authentication and Security Module.
Provides Supabase JWT verification and FastAPI security dependencies.
"""

from __future__ import annotations

import logging
import time
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
    Enforces signature, expiration, and audience claims.
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
        # Verify audience if present
        aud = payload.get("aud")
        if aud and aud not in ("authenticated", "anon"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token audience claim '{aud}'.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Verify issued-at timestamp is not in the future (tampered token check)
        iat = payload.get("iat")
        if iat and isinstance(iat, (int, float)) and iat > time.time() + 300:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token issued-at timestamp is invalid or in the future.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token credentials or tampered signature.",
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

    aud = payload.get("aud")
    role = payload.get("role", "authenticated")

    # Reconciled Phase 11 policy: Anonymous guest tokens (aud == 'anon' or role == 'anon')
    # are strictly forbidden from performing protected registered user operations.
    if aud == "anon" or role == "anon":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user token required. Anonymous tokens cannot access protected user resources.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("email", "")

    return UserContext(user_id=str(user_id), email=str(email), role=str(role))


async def get_current_user_optional(request: Request) -> Optional[UserContext]:
    """
    Optional authentication: returns UserContext if valid token is provided.
    If no Authorization header is present, returns None for guest/public browsing.
    If an Authorization header is provided but invalid/expired, strictly raises HTTP 401.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_supabase_jwt(parts[1])
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject identifier (sub)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserContext(
        user_id=str(user_id),
        email=str(payload.get("email", "")),
        role=str(payload.get("role", "authenticated"))
    )
