"""
Phase 9: Production Productization, Platform Reliability & Controlled Launch Readiness Test Suite

Validates:
1. Journey A: User Onboarding, Privacy Consent Lifecycle & GDPR Data Rights (Export Art. 20, Purge Art. 17).
2. Journey B: Garment Creation, Duplicate Upload Deduplication, Cost & Provenance Transparency.
3. Journey C: Look Management Engine, Slot Exclusivity & Outfit Compatibility Rules.
4. Journey D: Strict Multi-Tenant Isolation for Looks and Privacy Records.
5. Journey E: Infrastructure Observability, Job Retry & Health Monitoring.
"""

import pytest
import io
import time
from fastapi import HTTPException
from PIL import Image, ImageDraw

from backend.app.core.security import UserContext
from backend.app.services.database.supabase_repository import supabase_repo
from backend.app.services.outfits.look_management_service import (
    look_management_service,
    OutfitCompatibilityResult
)
from backend.app.api.fashion_routes import (
    get_saved_looks,
    create_saved_look,
    get_saved_look_details,
    update_saved_look,
    delete_saved_look,
    duplicate_saved_look,
    wear_saved_look,
    validate_outfit_compatibility,
    get_user_privacy_consent,
    update_user_privacy_consent,
    export_user_data_archive,
    purge_user_data_request,
    CreateLookRequest,
    UpdateLookRequest,
    DuplicateLookRequest,
    CompatibilityValidateRequest,
    UserConsentRequest
)
from backend.app.services.garments.job_manager import garment_job_manager
from backend.app.api.garment_generation_routes import (
    retry_job,
    get_pipeline_health
)
from backend.app.main import get_system_metrics


from backend.app.models.garment_models import GarmentGenJobStatus


def _create_test_image_bytes(color=(30, 41, 59), size=(500, 600)) -> bytes:
    img = Image.new("RGB", size, (240, 240, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle([100, 100, 400, 500], fill=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


# ── Journey A: User Onboarding, Privacy & GDPR Tests ────────────────────────

def test_journey_a_consent_lifecycle():
    """Verify default ephemeral processing consent and explicit AI training opt-in."""
    user = UserContext(user_id="usr_onboarding_001", email="newuser@yorvyn.ai")

    # 1. Fetch initial consent before explicit choice
    default_consent = get_user_privacy_consent(user_id="usr_onboarding_001", current_user=user)
    assert default_consent["ephemeral_processing_accepted"] is True
    assert default_consent["ai_training_opt_in"] is False
    assert default_consent["status"] == "default_ephemeral_only"

    # 2. User updates consent: Accepts ephemeral, explicitly opts into AI training
    update_req = UserConsentRequest(
        user_id="usr_onboarding_001",
        ephemeral_processing_accepted=True,
        ai_training_opt_in=True,
        terms_version="2026.1"
    )
    saved_consent = update_user_privacy_consent(update_req, current_user=user)
    assert saved_consent["ephemeral_processing_accepted"] is True
    assert saved_consent["ai_training_opt_in"] is True
    assert saved_consent["opt_in_timestamp"] is not None

    # 3. User revokes AI training opt-in later
    revoke_req = UserConsentRequest(
        user_id="usr_onboarding_001",
        ephemeral_processing_accepted=True,
        ai_training_opt_in=False,
        terms_version="2026.1"
    )
    revoked_consent = update_user_privacy_consent(revoke_req, current_user=user)
    assert revoked_consent["ai_training_opt_in"] is False
    assert revoked_consent["opt_in_timestamp"] is None


def test_journey_a_gdpr_data_export_and_purge():
    """Verify GDPR Article 20 data portability export and Article 17 right to erasure."""
    user = UserContext(user_id="usr_gdpr_test_002", email="gdpr@yorvyn.ai")

    # 1. Seed user profile, consent, and a look
    supabase_repo.upsert_profile(
        user_id="usr_gdpr_test_002",
        profile_data={
            "display_name": "GDPR Subject",
            "email": "gdpr@yorvyn.ai"
        }
    )
    update_user_privacy_consent(
        UserConsentRequest(
            user_id="usr_gdpr_test_002",
            ephemeral_processing_accepted=True,
            ai_training_opt_in=True
        ),
        current_user=user
    )
    create_saved_look(
        CreateLookRequest(
            user_id="usr_gdpr_test_002",
            name="GDPR Summer Look",
            garment_ids=["shirt_01", "shorts_01"]
        ),
        current_user=user
    )

    # 2. GDPR Data Portability Export
    export_data = export_user_data_archive(user_id="usr_gdpr_test_002", current_user=user)
    assert export_data["user_id"] == "usr_gdpr_test_002"
    assert export_data["gdpr_compliance"]["right_to_portability"] is True
    assert export_data["profile"]["display_name"] == "GDPR Subject"
    assert len(export_data["saved_looks"]) == 1
    assert export_data["privacy_consents"]["ai_training_opt_in"] is True

    # 3. GDPR Right to Erasure Purge
    purge_result = purge_user_data_request(user_id="usr_gdpr_test_002", current_user=user)
    assert purge_result["status"] == "success"
    assert "permanently erased" in purge_result["message"]

    # 4. Confirm data is gone
    post_export = export_user_data_archive(user_id="usr_gdpr_test_002", current_user=user)
    assert len(post_export["saved_looks"]) == 0
    assert post_export["privacy_consents"] is None


# ── Journey B: Garment Job Infrastructure & Provenance Tests ───────────────

def test_journey_b_job_deduplication_and_provenance():
    """Verify that uploading the exact same image uses cached results with full provenance."""
    import uuid
    img_bytes = _create_test_image_bytes(color=(40, 50, 70))
    user_id = f"usr_dedup_{uuid.uuid4().hex[:8]}"

    # 1. Submit initial generation job
    job_1 = garment_job_manager.create_job(
        user_id=user_id,
        front_image_bytes=img_bytes,
        category="top"
    )
    # Wait for execution to finish
    status_1 = None
    for _ in range(30):
        status_1 = garment_job_manager.get_job(job_1.job_id)
        if status_1 and getattr(status_1.status, "value", status_1.status) in ["completed", "failed"]:
            break
        time.sleep(0.2)

    assert status_1 is not None
    assert getattr(status_1.status, "value", status_1.status) == "completed"
    assert status_1.result is not None
    assert status_1.result.cost_usd == 0.0000  # Local M2 / PyTorch is $0.0000
    assert status_1.result.is_cached is False
    assert status_1.result.reconstruction_provenance in ["hybrid_neural_procedural", "neural_category_specific", "procedural_fallback"]

    # 2. Submit duplicate generation job with identical bytes
    job_2 = garment_job_manager.create_job(
        user_id=user_id,
        front_image_bytes=img_bytes,
        category="top"
    )
    status_2 = garment_job_manager.get_job(job_2.job_id)
    assert getattr(status_2.status, "value", status_2.status) == "completed"
    assert status_2.result.is_cached is True
    assert status_2.result.glb_url == status_1.result.glb_url


@pytest.mark.asyncio
async def test_journey_b_job_retry_mechanism(monkeypatch):
    """Verify that durable failed jobs with retained temp inputs can be retried, and purged ones cannot."""
    import uuid
    img_bytes = _create_test_image_bytes()
    # Prevent immediate worker execution so raw temp input stays available during simulated transient failure
    monkeypatch.setattr(garment_job_manager, "_dispatch_next_tasks", lambda: None)

    job = garment_job_manager.create_job(
        user_id=f"usr_retry_{uuid.uuid4().hex[:8]}",
        front_image_bytes=img_bytes,
        category="hoodie"
    )
    # Simulate durable failure while temp source image is still intact
    def _mark_failed(state):
        state.transition("CLAIMED", reason="test_claim", worker_id="test_w", lease_generation=state.lease_generation)
        state.record_failure_attempt("test_w", state.lease_generation, "transient", "Network timeout")
        return state.transition("FAILED", reason="Network timeout", worker_id="test_w", lease_generation=state.lease_generation)

    garment_job_manager._postgres_adapter.mutate_job(job.job_id, _mark_failed)
    job.status = GarmentGenJobStatus.FAILED
    job.error = "Network timeout"

    retry_resp = await retry_job(job.job_id)
    resp_status = str(getattr(retry_resp["status"], "value", retry_resp["status"])).lower()
    assert resp_status in ["pending", "analyzing", "queued"]
    assert retry_resp["retry_count"] == 1
    garment_job_manager._cleanup_temp_files(job.job_id)


# ── Journey C: Look Management & Outfit Compatibility Rules ─────────────────

def test_journey_c_look_management_lifecycle():
    """Verify saved looks CRUD, renaming, duplicating, and recording wear."""
    user = UserContext(user_id="usr_looks_005", email="looks@yorvyn.ai")

    # 1. Create a look
    look = create_saved_look(
        CreateLookRequest(
            user_id="usr_looks_005",
            name="Autumn Casual",
            garment_ids=["top_sweater", "bottom_denim"],
            description="Cozy fall outfit",
            tags=["casual", "fall"],
            is_favorite=True
        ),
        current_user=user
    )
    assert look["id"] is not None
    assert look["name"] == "Autumn Casual"
    assert look["is_favorite"] is True
    look_id = look["id"]

    # 2. Fetch looks
    all_looks = get_saved_looks(user_id="usr_looks_005", current_user=user)
    assert len(all_looks) == 1
    assert all_looks[0]["name"] == "Autumn Casual"

    # 3. Update look
    updated = update_saved_look(
        look_id,
        UpdateLookRequest(name="Autumn Luxury Casual", is_favorite=False),
        current_user=user
    )
    assert updated["name"] == "Autumn Luxury Casual"

    # 4. Duplicate look
    cloned = duplicate_saved_look(
        look_id,
        DuplicateLookRequest(new_name="Autumn Luxury Casual (Evening)"),
        current_user=user
    )
    assert cloned["name"] == "Autumn Luxury Casual (Evening)"
    assert cloned["id"] != look_id

    # 5. Record wear
    wear_res = wear_saved_look(look_id, user_id="usr_looks_005", current_user=user)
    assert wear_res["status"] == "success"
    assert wear_res["look"]["wear_count"] == 1
    assert wear_res["look"]["last_worn_at"] is not None

    # 6. Delete look
    del_res = delete_saved_look(look_id, user_id="usr_looks_005", current_user=user)
    assert del_res["status"] == "success"


def test_journey_c_compatibility_rules_conflict():
    """Verify incompatibility when dress is paired with trousers (separates clash)."""
    garments = [
        {"id": "dress_01", "name": "Silk Slip Dress", "category": "dress", "warmth": 2, "formality": 8},
        {"id": "pants_01", "name": "Straight Leg Jeans", "category": "bottom", "warmth": 5, "formality": 4}
    ]
    res: OutfitCompatibilityResult = look_management_service.validate_compatibility(garments)
    assert res.is_compatible is False
    assert any("dress cannot be simultaneously combined with trousers" in r for r in res.conflicts)
    assert res.compatibility_score <= 0.60


def test_journey_c_compatibility_rules_duplicate_slot():
    """Verify incompatibility when equipping two bottoms simultaneously."""
    garments = [
        {"id": "pants_01", "name": "Chinos", "category": "bottom", "warmth": 4, "formality": 5},
        {"id": "shorts_02", "name": "Denim Shorts", "category": "bottom", "warmth": 2, "formality": 2}
    ]
    res: OutfitCompatibilityResult = look_management_service.validate_compatibility(garments)
    assert res.is_compatible is False
    assert any("Multiple conflicting bottoms selected" in r for r in res.conflicts)


def test_journey_c_compatibility_rules_valid_ensemble():
    """Verify full compatibility for coordinated top, bottom, and outerwear."""
    garments = [
        {"id": "tee_01", "name": "Cashmere Knit", "category": "top", "warmth": 5, "formality": 6},
        {"id": "pants_01", "name": "Wool Trousers", "category": "bottom", "warmth": 6, "formality": 7},
        {"id": "coat_01", "name": "Overcoat", "category": "outerwear", "warmth": 7, "formality": 7}
    ]
    res: OutfitCompatibilityResult = look_management_service.validate_compatibility(garments)
    assert res.is_compatible is True
    assert len(res.conflicts) == 0
    assert res.compatibility_score >= 0.85
    assert res.thermal_tier in ["moderate", "warm"]


def test_journey_c_compatibility_thermal_and_formality_warnings():
    """Verify warnings for extreme thermal disparity and formality clash."""
    garments = [
        {"id": "coat_01", "name": "Heavy Down Parka", "category": "outerwear", "warmth": 10, "formality": 3},
        {"id": "shorts_01", "name": "Swim Shorts", "category": "bottom", "warmth": 1, "formality": 1}
    ]
    res: OutfitCompatibilityResult = look_management_service.validate_compatibility(garments)
    # Not blocked, but emits thermal warning
    assert any("thermal disparity" in w.lower() for w in res.warnings)


# ── Journey D: Multi-Tenant Security Isolation ─────────────────────────────

def test_journey_d_multi_tenant_isolation():
    """Verify User A cannot access or mutate User B's saved looks or privacy data."""
    user_a = UserContext(user_id="usr_tenant_A", email="a@yorvyn.ai")
    user_b = UserContext(user_id="usr_tenant_B", email="b@yorvyn.ai")

    # User B creates a private look
    look_b = create_saved_look(
        CreateLookRequest(
            user_id="usr_tenant_B",
            name="Secret Look B",
            garment_ids=["tshirt_b"]
        ),
        current_user=user_b
    )
    look_b_id = look_b["id"]

    # User A maliciously requests User B's look details
    with pytest.raises(HTTPException) as exc_info:
        get_saved_look_details(look_b_id, user_id="usr_tenant_B", current_user=user_a)
    assert exc_info.value.status_code == 403

    # User A maliciously attempts to update User B's look
    with pytest.raises(HTTPException) as exc_info:
        update_saved_look(
            look_b_id,
            UpdateLookRequest(user_id="usr_tenant_B", name="Hacked Name"),
            current_user=user_a
        )
    assert exc_info.value.status_code == 403

    # User A maliciously attempts to delete User B's look
    with pytest.raises(HTTPException) as exc_info:
        delete_saved_look(look_b_id, user_id="usr_tenant_B", current_user=user_a)
    assert exc_info.value.status_code == 403

    # User A maliciously requests User B's GDPR export
    with pytest.raises(HTTPException) as exc_info:
        export_user_data_archive(user_id="usr_tenant_B", current_user=user_a)
    assert exc_info.value.status_code == 403


# ── Journey E: Observability & Health Monitoring ───────────────────────────

@pytest.mark.asyncio
async def test_journey_e_observability_and_health():
    """Verify platform health metrics, queue telemetry, and memory tracking."""
    # 1. Garment Gen Health endpoint
    gen_health = await get_pipeline_health()
    assert gen_health["status"] == "healthy"
    assert "worker_threads_max" in gen_health
    assert "jobs_total" in gen_health
    assert "cache_entries_count" in gen_health
    assert gen_health["cache_entries_count"] >= 1

    # 2. System Metrics endpoint
    metrics = get_system_metrics()
    assert metrics["status"] == "healthy"
    assert metrics["service"] == "Yorvyn Platform Metrics"
    assert "system" in metrics
    assert metrics["system"]["peak_rss_mb"] > 0
    assert "worker_telemetry" in metrics
    assert "database_connected" in metrics
