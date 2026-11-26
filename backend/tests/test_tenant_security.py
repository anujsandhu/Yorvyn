"""
Automated Security Tests for Multi-Tenant Data Isolation and Authorization.
Verifies that:
1. An authenticated user (User A) is strictly forbidden from accessing User B's wardrobe.
2. User A cannot mutate or delete User B's wardrobe items.
3. User A cannot view, cancel, or save another user's 3D garment generation jobs.
4. User A's effective UID always overrides client-supplied user_id parameters.
5. Cross-tenant tampering triggers HTTP 403 Forbidden.
"""

import pytest
from fastapi import HTTPException

from backend.app.core.security import UserContext
from backend.app.api.fashion_routes import (
    _resolve_effective_user_id,
    get_wardrobe,
    delete_wardrobe_item,
    get_avatar_config,
    save_avatar_config
)
from backend.app.api.garment_generation_routes import (
    get_job_status,
    cancel_job,
    save_to_wardrobe
)
from backend.app.services.garments.job_manager import garment_job_manager


def test_resolve_effective_user_id_matching():
    user_a = UserContext(user_id="user_aaa_111", email="a@yorvyn.ai")
    # Same user_id passed
    resolved = _resolve_effective_user_id("user_aaa_111", user_a)
    assert resolved == "user_aaa_111"

    # Default user_id passed from frontend default
    resolved_default = _resolve_effective_user_id("default_user", user_a)
    assert resolved_default == "user_aaa_111"

    # None passed
    resolved_none = _resolve_effective_user_id(None, user_a)
    assert resolved_none == "user_aaa_111"


def test_resolve_effective_user_id_cross_tenant_forbidden():
    user_a = UserContext(user_id="user_aaa_111", email="a@yorvyn.ai")
    
    # User A maliciously attempts to access User B's data
    with pytest.raises(HTTPException) as excinfo:
        _resolve_effective_user_id("user_bbb_222", user_a)

    assert excinfo.value.status_code == 403
    assert "Cross-tenant data access is not permitted" in excinfo.value.detail


def test_wardrobe_cross_tenant_access_blocked():
    user_a = UserContext(user_id="user_aaa_111", email="a@yorvyn.ai")
    
    # Trying to read User B's wardrobe
    with pytest.raises(HTTPException) as excinfo:
        get_wardrobe(user_id="user_bbb_222", current_user=user_a)
    assert excinfo.value.status_code == 403

    # Trying to delete User B's wardrobe item
    with pytest.raises(HTTPException) as excinfo:
        delete_wardrobe_item(item_id="item_999", user_id="user_bbb_222", current_user=user_a)
    assert excinfo.value.status_code == 403


def test_avatar_cross_tenant_access_blocked():
    user_a = UserContext(user_id="user_aaa_111", email="a@yorvyn.ai")
    
    # Trying to read User B's avatar config
    with pytest.raises(HTTPException) as excinfo:
        get_avatar_config(user_id="user_bbb_222", current_user=user_a)
    assert excinfo.value.status_code == 403

    # Trying to overwrite User B's avatar config
    with pytest.raises(HTTPException) as excinfo:
        save_avatar_config(config={"face": {}}, user_id="user_bbb_222", current_user=user_a)
    assert excinfo.value.status_code == 403


@pytest.mark.asyncio
async def test_garment_job_cross_tenant_isolation():
    # User B creates a 3D garment generation job
    dummy_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 2000
    job_b = garment_job_manager.create_job(
        user_id="user_bbb_222",
        front_image_bytes=dummy_bytes,
        category="top"
    )

    user_a = UserContext(user_id="user_aaa_111", email="a@yorvyn.ai")

    # User A tries to view User B's job status -> 403
    with pytest.raises(HTTPException) as excinfo:
        await get_job_status(job_id=job_b.job_id, current_user=user_a)
    assert excinfo.value.status_code == 403

    # User A tries to cancel User B's job -> 403
    with pytest.raises(HTTPException) as excinfo:
        await cancel_job(job_id=job_b.job_id, current_user=user_a)
    assert excinfo.value.status_code == 403

    # User A tries to save User B's job into their wardrobe -> 403
    with pytest.raises(HTTPException) as excinfo:
        await save_to_wardrobe(job_id=job_b.job_id, user_id="user_aaa_111", current_user=user_a)
    assert excinfo.value.status_code in [400, 403]

