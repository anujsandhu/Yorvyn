"""
Phase 1 Security Hardening Regression Suite (FIND-SEC-01 .. FIND-SEC-07 + Route Auth Audit).
"""

from __future__ import annotations

import io
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from jose import jwt
from PIL import Image

from backend.app.core.security import UserContext
from backend.app.core.settings import Settings, settings
from backend.app.main import app


def _make_jwt(user_id: str = "usr_test_1", role: str = "authenticated", email: str = "user@example.com") -> str:
    secret = settings.supabase_jwt_secret or settings.secret_key
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "role": role,
            "aud": "authenticated",
            "email": email,
            "iat": now,
            "exp": now + 3600,
        },
        secret,
        algorithm="HS256",
    )


def _png_bytes(width: int = 32, height: int = 32) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (40, 80, 120)).save(buf, format="PNG")
    return buf.getvalue()


client = TestClient(app, raise_server_exceptions=False)


# ── FIND-SEC-01: CORS + Error Handler + Security Headers ──────────────────────

def test_cors_does_not_reflect_arbitrary_origin_with_credentials() -> None:
    resp = client.get("/api/billing/plans", headers={"Origin": "https://evil.attacker.example"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") != "https://evil.attacker.example"
    assert not (
        resp.headers.get("access-control-allow-origin") == "*"
        and resp.headers.get("access-control-allow-credentials") == "true"
    )


def test_security_headers_present_on_responses() -> None:
    resp = client.get("/api/billing/plans")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert "camera=(self)" in (resp.headers.get("permissions-policy") or "")


def test_non_debug_error_handler_hides_internal_details() -> None:
    from fastapi import Request

    @app.get("/_test_internal_error_probe")
    async def _probe():
        raise RuntimeError("sensitive_db_password_leak")

    with patch.object(settings, "debug", False):
        resp = client.get("/_test_internal_error_probe")
    assert resp.status_code == 500
    body = resp.json()
    assert body.get("error") == "internal_error"
    assert "request_id" in body
    assert "sensitive_db_password_leak" not in resp.text


# ── FIND-SEC-02: Beta Admin & Billing Auth ────────────────────────────────────

def test_beta_cohort_status_requires_admin_role() -> None:
    user_token = _make_jwt(user_id="usr_regular", role="authenticated", email="regular@example.com")
    resp = client.post(
        "/api/beta/cohort/status",
        json={"token_or_id": "tok_123", "status": "revoked"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403


def test_billing_rejects_unauthenticated_client_user_id_fallback() -> None:
    assert settings.stripe_test_mode is False
    resp = client.get("/api/billing/subscription", params={"user_id": "usr_victim"})
    assert resp.status_code == 401


# ── FIND-SEC-03: Auth on Identify/Analyze + Shared Upload Validator + NameError

def test_identify_and_analyze_require_authentication() -> None:
    png = _png_bytes()
    r1 = client.post("/api/garments/identify", files={"image": ("t.png", png, "image/png")})
    r2 = client.post("/api/garments/hybrid-orchestrated-identify", files={"image": ("t.png", png, "image/png")})
    r3 = client.post("/api/intelligence/fashion/analyze", files={"image": ("t.png", png, "image/png")})
    assert r1.status_code == 401
    assert r2.status_code == 401
    assert r3.status_code == 401


def test_upload_validator_rejects_non_image_magic_bytes() -> None:
    token = _make_jwt()
    resp = client.post(
        "/api/garments/identify",
        files={"image": ("fake.png", b"<html><script>alert(1)</script></html>" * 4, "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "magic bytes" in resp.json()["detail"].lower()


def test_garment_generation_permission_error_releases_slot_without_nameerror() -> None:
    token = _make_jwt(user_id="usr_quota_test")
    png = _png_bytes(64, 64)
    with patch(
        "backend.app.services.billing.entitlement_service.entitlement_service.reserve_reconstruction_slot",
        return_value=(True, "ok"),
    ), patch(
        "backend.app.services.billing.entitlement_service.entitlement_service.release_reconstruction_slot"
    ) as release_mock, patch(
        "backend.app.services.garments.job_manager.garment_job_manager.create_job",
        side_effect=PermissionError("quota exceeded"),
    ):
        resp = client.post(
            "/api/fashion/garment-gen/jobs",
            files={"front_image": ("shirt.png", png, "image/png")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "ENTITLEMENT_QUOTA_EXCEEDED"
    release_mock.assert_called_once_with("usr_quota_test")


# ── FIND-SEC-05: Production Secret Enforcement & Separate Admin Key ───────────

def test_settings_refuses_empty_secret_key_in_non_debug_production() -> None:
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(debug=False, environment="production", secret_key="")


def test_admin_key_cannot_reuse_jwt_secret_key() -> None:
    token = _make_jwt(user_id="usr_non_admin", role="authenticated", email="user@example.com")
    with patch.object(settings, "admin_api_key", "distinct-admin-key-xyz"):
        resp_jwt = client.get(
            "/api/learning/admin/dashboard",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Admin-Key": settings.secret_key,
            },
        )
        assert resp_jwt.status_code == 403

        resp_admin = client.get(
            "/api/learning/admin/dashboard",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Admin-Key": "distinct-admin-key-xyz",
            },
        )
        assert resp_admin.status_code == 200


# ── FIND-SEC-06 & Learning Service ────────────────────────────────────────────

def test_speech_transcribe_returns_503_when_provider_unavailable() -> None:
    token = _make_jwt()
    with patch.object(settings, "groq_api_key", ""):
        resp = client.post(
            "/api/fashion/speech/transcribe",
            files={"audio": ("clip.webm", b"\x1a\x45\xdf\xa3" + b"\x00" * 64, "audio/webm")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 503


def test_learning_simulated_training_gated_by_flag() -> None:
    admin_token = _make_jwt(user_id="usr_admin", role="admin", email="admin@internal.yorvyn.ai")
    with patch.object(settings, "enable_simulated_training", False):
        resp = client.post(
            "/api/learning/admin/training-jobs/job_123/execute",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 503


# ── FIND-SEC-07 / FE-01: Frontend GarmentDesignWorkspace Uses Auth Client ─────

def test_garment_design_workspace_uses_authenticated_http_client() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    src = (repo_root / "frontend" / "src" / "components" / "design" / "GarmentDesignWorkspace.tsx").read_text(
        encoding="utf-8"
    )
    assert "garmentsHttp.interceptors.request.use" in src
    assert "axios.post(" not in src
    assert "axios.get(" not in src


# ── Route Auth Allowlist Audit ────────────────────────────────────────────────

PUBLIC_MUTATION_ALLOWLIST = {
    "/api/billing/webhook",       # Stripe webhook verified via Stripe-Signature
    "/api/beta/validate-invite",  # Pre-signup invite code check
}


def test_all_mutation_routes_require_auth_or_are_explicitly_allowlisted() -> None:
    unprotected: list[str] = []
    for route in app.routes:
        if isinstance(route, APIRoute) and any(m in route.methods for m in ("POST", "PUT", "PATCH", "DELETE")):
            if route.path in PUBLIC_MUTATION_ALLOWLIST:
                continue
            deps = {d.call.__name__ for d in route.dependant.dependencies if d.call}
            if not ({"get_current_user", "get_current_user_optional", "turn_access"} & deps):
                unprotected.append(f"{sorted(route.methods)} {route.path}")
    assert not unprotected, f"Unprotected mutation routes found: {unprotected}"
