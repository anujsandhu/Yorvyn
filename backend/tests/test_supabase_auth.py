"""
Automated Unit Tests for Supabase Auth JWT Verification and Security Dependencies.
Validates:
1. Valid Supabase JWT token generation & payload verification
2. Expired token rejection with HTTP 401
3. Malformed/invalid token rejection
4. UserContext object attributes and representation
5. Authorization header extraction (missing, invalid format, valid Bearer token)
"""

import time
import pytest
from fastapi import HTTPException
from jose import jwt

from backend.app.core.security import verify_supabase_jwt, UserContext, get_current_user
from backend.app.core.settings import settings


class DummyRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}


def test_user_context():
    user = UserContext(user_id="usr_12345", email="test@yorvyn.ai", role="authenticated")
    assert user.user_id == "usr_12345"
    assert user.email == "test@yorvyn.ai"
    assert user.role == "authenticated"
    assert "usr_12345" in repr(user)


def test_verify_valid_supabase_jwt():
    secret = settings.supabase_jwt_secret or settings.secret_key
    now = int(time.time())
    payload = {
        "sub": "b8f683a4-8451-419b-a7e8-e1679092d64f",
        "email": "fashionista@yorvyn.com",
        "role": "authenticated",
        "iat": now,
        "exp": now + 3600
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    
    decoded = verify_supabase_jwt(token)
    assert decoded["sub"] == "b8f683a4-8451-419b-a7e8-e1679092d64f"
    assert decoded["email"] == "fashionista@yorvyn.com"
    assert decoded["role"] == "authenticated"


def test_verify_expired_supabase_jwt():
    secret = settings.supabase_jwt_secret or settings.secret_key
    now = int(time.time())
    payload = {
        "sub": "b8f683a4-8451-419b-a7e8-e1679092d64f",
        "email": "fashionista@yorvyn.com",
        "role": "authenticated",
        "iat": now - 7200,
        "exp": now - 3600
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    
    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_jwt(token)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


def test_verify_invalid_token():
    with pytest.raises(HTTPException) as exc_info:
        verify_supabase_jwt("this.is.notavalidtoken")
    assert exc_info.value.status_code == 401


def test_get_current_user_valid_header():
    import asyncio
    secret = settings.supabase_jwt_secret or settings.secret_key
    now = int(time.time())
    payload = {
        "sub": "user_supabase_abc999",
        "email": "atelier@yorvyn.ai",
        "role": "authenticated",
        "iat": now,
        "exp": now + 1800
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    req = DummyRequest(headers={"Authorization": f"Bearer {token}"})
    
    user = asyncio.run(get_current_user(req))
    assert user.user_id == "user_supabase_abc999"
    assert user.email == "atelier@yorvyn.ai"


def test_get_current_user_missing_header():
    import asyncio
    req = DummyRequest(headers={})
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_current_user(req))
    assert exc_info.value.status_code == 401
    assert "missing authorization header" in exc_info.value.detail.lower()


def test_get_current_user_malformed_header():
    import asyncio
    req = DummyRequest(headers={"Authorization": "TokenWithoutBearerPrefix"})
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_current_user(req))
    assert exc_info.value.status_code == 401
    assert "invalid authorization header format" in exc_info.value.detail.lower()
