"""Tests for Phase 17.5 Universal Garment & Accessory Fitting YIP registry & API routes."""

from __future__ import annotations

import time
from fastapi.testclient import TestClient
from jose import jwt

from backend.app.core.settings import settings
from backend.app.main import app
from backend.app.services.intelligence.capability_registry import garment_capabilities


client = TestClient(app)


def _auth_header(user_id: str = "usr_fit_175") -> dict[str, str]:
    now = int(time.time())
    tok = jwt.encode(
        {"sub": user_id, "role": "authenticated", "aud": "authenticated", "iat": now, "exp": now + 3600},
        settings.supabase_jwt_secret or settings.secret_key,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {tok}"}


def test_phase17_5_fitting_capabilities_registered_with_honest_states() -> None:
    expected = {
        "garment.asset.inspect": "EXECUTABLE",
        "garment.fit.plan": "EXECUTABLE",
        "garment.fit.upper_body": "VERIFIED",
        "garment.fit.lower_body": "VERIFIED",
        "garment.fit.full_body": "EXECUTABLE",
        "garment.fit.footwear": "EXECUTABLE",
        "garment.fit.accessory": "EXECUTABLE",
        "garment.layer.compose": "EXECUTABLE",
        "fitting.evaluate": "EXECUTABLE",
    }
    for name, state in expected.items():
        cap = garment_capabilities.get(name)
        assert cap is not None, f"Missing capability {name}"
        assert cap.availability.value == state


def test_fitting_taxonomy_and_plan_endpoints_require_auth_and_route_categories() -> None:
    assert client.get("/api/intelligence/fitting/taxonomy").status_code == 401

    headers = _auth_header()
    tax = client.get("/api/intelligence/fitting/taxonomy", headers=headers)
    assert tax.status_code == 200
    body = tax.json()
    assert body["taxonomy_version"] == "17.5.0"
    assert "footwear" in body["supported_domains"]

    shoe_plan = client.post(
        "/api/intelligence/fitting/plan",
        json={"category": "sneakers", "avatar_profile_id": "standard_175"},
        headers=headers,
    )
    assert shoe_plan.status_code == 200
    assert shoe_plan.json()["capability"]["id"] == "garment.fit.footwear"

    acc_plan = client.post(
        "/api/intelligence/fitting/plan",
        json={"category": "sunglasses", "avatar_profile_id": "standard_175"},
        headers=headers,
    )
    assert acc_plan.status_code == 200
    assert acc_plan.json()["capability"]["id"] == "garment.fit.accessory"
