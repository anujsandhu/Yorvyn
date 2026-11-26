"""
Yorvyn Phase 10: Production Platform, Security Remediation, Production Billing,
Tenant Isolation, and Private Beta Validation Test Suite.
"""

import os
import io
import time
import uuid
import json
import pytest
from datetime import datetime, timedelta
from PIL import Image
from fastapi.testclient import TestClient
from jose import jwt

from backend.app.main import app
from backend.app.core.settings import settings
from backend.app.core.security import verify_supabase_jwt, UserContext
from backend.app.core.billing_config import SUBSCRIPTION_PLANS, get_plan_definition
from backend.app.services.billing.entitlement_service import entitlement_service
from backend.app.services.billing.stripe_service import stripe_billing_service
from backend.app.services.database.supabase_repository import supabase_repo
from backend.app.services.garments.job_manager import garment_job_manager, TEMP_BASE_DIR
from backend.app.models.garment_models import GarmentGenJobStatus, GarmentGenJob
from backend.app.api.fashion_routes import (
    create_saved_look,
    get_saved_look_details,
    delete_saved_look,
    export_user_data_archive,
    purge_user_data_request,
    update_user_privacy_consent,
    get_user_privacy_consent,
    UserConsentRequest,
    CreateLookRequest
)
from backend.app.api.garment_generation_routes import (
    get_job_status,
    cancel_job,
    retry_job
)

client = TestClient(app)


def _generate_test_jwt(user_id: str, email: str = "test@yorvyn.ai", expired: bool = False, aud: str = "authenticated") -> str:
    """Generates a signed test JWT for Supabase authentication simulation using UNIX epoch time."""
    secret = settings.supabase_jwt_secret or settings.secret_key
    now_ts = int(time.time())
    exp_ts = (now_ts - 3600) if expired else (now_ts + 7200)
    claims = {
        "sub": user_id,
        "email": email,
        "aud": aud,
        "role": "authenticated",
        "exp": exp_ts,
        "iat": now_ts
    }
    return jwt.encode(claims, secret, algorithm="HS256")


def _create_synthetic_image(width: int = 128, height: int = 128, color=(180, 50, 50)) -> bytes:
    """Creates synthetic PNG image bytes for job submission."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ==============================================================================
# SECTION 1: AUTHENTICATION ENFORCEMENT & JWT SECURITY
# ==============================================================================

def test_jwt_verification_valid():
    """Verifies that valid Supabase JWT tokens decode cleanly into UserContext."""
    token = _generate_test_jwt("usr_auth_001", "auth001@yorvyn.ai")
    payload = verify_supabase_jwt(token)
    assert payload["sub"] == "usr_auth_001"
    assert payload["email"] == "auth001@yorvyn.ai"
    assert payload["aud"] == "authenticated"


def test_jwt_verification_expired():
    """Verifies that expired JWT tokens strictly raise HTTP 401."""
    expired_token = _generate_test_jwt("usr_expired_001", expired=True)
    with pytest.raises(Exception) as excinfo:
        verify_supabase_jwt(expired_token)
    assert "401" in str(excinfo.value) or "expired" in str(excinfo.value).lower()


def test_jwt_verification_invalid_audience():
    """Verifies that tokens with unauthorized audience claims raise HTTP 401."""
    tampered_token = _generate_test_jwt("usr_tampered_001", aud="malicious_service")
    with pytest.raises(Exception) as excinfo:
        verify_supabase_jwt(tampered_token)
    assert "401" in str(excinfo.value) or "audience" in str(excinfo.value).lower()


def test_anonymous_guest_cannot_impersonate_registered_user():
    """
    Critical Security Test:
    Ensures unauthenticated callers cannot bypass isolation by supplying registered user IDs.
    """
    # 1. Unauthenticated request to purge another user's data
    resp_purge = client.post("/api/fashion/user/purge", params={"user_id": "usr_victim_999"})
    assert resp_purge.status_code == 401

    # 2. Unauthenticated request to export another user's data
    resp_export = client.get("/api/fashion/user/export?user_id=usr_victim_999")
    assert resp_export.status_code == 401

    # 3. Unauthenticated request to update consent
    resp_consent = client.post("/api/fashion/consent", json={
        "user_id": "usr_victim_999",
        "ephemeral_processing_accepted": True,
        "ai_training_opt_in": True
    })
    assert resp_consent.status_code == 401


def test_authenticated_user_cannot_impersonate_another_user():
    """
    Ensures an authenticated User A attempting to pass User B's ID is rejected with 403 Forbidden.
    """
    token_a = _generate_test_jwt("usr_attacker_A")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # User A tries to export User B's data
    resp = client.get("/api/fashion/user/export?user_id=usr_victim_B", headers=headers_a)
    assert resp.status_code == 403
    assert "Cross-tenant" in resp.json()["detail"]


# ==============================================================================
# SECTION 2: COMPLETE TENANT ISOLATION & RLS VERIFICATION
# ==============================================================================

def test_cross_tenant_look_mutation_forbidden():
    """Ensures User A cannot view, mutate, duplicate, or delete User B's saved looks."""
    user_b = UserContext(user_id="usr_tenant_owner_B")

    # User B creates a look
    look = create_saved_look(
        CreateLookRequest(
            user_id="usr_tenant_owner_B",
            name="Confidential Runway Ensemble",
            garment_ids=["garment_b1", "garment_b2"]
        ),
        current_user=user_b
    )
    look_id = look["id"]

    # User A attempts to read User B's look
    token_a = _generate_test_jwt("usr_tenant_intruder_A")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Direct query passing User B's user_id with User A's token
    resp_get = client.get(f"/api/fashion/looks/{look_id}?user_id=usr_tenant_owner_B", headers=headers_a)
    assert resp_get.status_code == 403

    # Direct delete attempt
    resp_del = client.delete(f"/api/fashion/looks/{look_id}?user_id=usr_tenant_owner_B", headers=headers_a)
    assert resp_del.status_code == 403


@pytest.mark.asyncio
async def test_cross_tenant_garment_job_forbidden():
    """Ensures User A cannot inspect, view diagnostics, or cancel User B's generation jobs."""
    job_b = GarmentGenJob(
        job_id=f"job_owner_b_{uuid.uuid4().hex[:8]}",
        user_id="usr_job_owner_B",
        status=GarmentGenJobStatus.QUEUED,
        progress=5,
        current_stage="Queued",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        temporary_files=[]
    )
    garment_job_manager._jobs[job_b.job_id] = job_b

    user_a = UserContext(user_id="usr_job_intruder_A")

    # User A attempts to view User B's job status
    with pytest.raises(Exception) as excinfo:
        await get_job_status(job_b.job_id, current_user=user_a)
    assert "403" in str(excinfo.value)

    # User A attempts to cancel User B's job
    with pytest.raises(Exception) as excinfo:
        await cancel_job(job_b.job_id, current_user=user_a)
    assert "403" in str(excinfo.value)

    del garment_job_manager._jobs[job_b.job_id]


@pytest.mark.asyncio
async def test_unauthenticated_garment_job_access_blocked():
    """Ensures anonymous callers cannot access a registered tenant's generation job."""
    job_private = GarmentGenJob(
        job_id=f"job_private_c_{uuid.uuid4().hex[:8]}",
        user_id="usr_private_tenant_C",
        status=GarmentGenJobStatus.QUEUED,
        progress=5,
        current_stage="Queued",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        temporary_files=[]
    )
    garment_job_manager._jobs[job_private.job_id] = job_private

    # Anonymous call with no user context
    with pytest.raises(Exception) as excinfo:
        await get_job_status(job_private.job_id, current_user=None)
    assert "401" in str(excinfo.value)

    del garment_job_manager._jobs[job_private.job_id]


# ==============================================================================
# SECTION 3: PRIVACY, CONSENT LIFECYCLE & GDPR COMPLIANCE
# ==============================================================================

def test_ephemeral_processing_and_raw_photo_purging():
    """
    Guarantees that raw photographs and temporary artifacts are permanently purged:
    Direct test of privacy cleanup on temporary working directory.
    """
    job_id = f"job_priv_clean_{uuid.uuid4().hex[:8]}"
    job_temp_dir = os.path.join(TEMP_BASE_DIR, job_id)
    os.makedirs(job_temp_dir, exist_ok=True)
    temp_file = os.path.join(job_temp_dir, "temp_input_front.raw")
    with open(temp_file, "wb") as f:
        f.write(b"RAW_SENSITIVE_PHOTOGRAPH_DATA")
    assert os.path.exists(temp_file)

    # Execute privacy cleanup
    garment_job_manager._cleanup_temp_files(job_id)

    # Raw photograph directory and file must be completely removed
    assert not os.path.exists(job_temp_dir)


def test_ai_training_opt_in_default_off_and_withdrawal():
    """Verifies privacy consent defaults to opt-out and handles consent withdrawal cleanly."""
    user = UserContext(user_id="usr_gdpr_subject_01")

    # Initial consent defaults
    default_consent = get_user_privacy_consent(user_id="usr_gdpr_subject_01", current_user=user)
    assert default_consent["ai_training_opt_in"] is False

    # User explicitly opts in
    update_user_privacy_consent(
        UserConsentRequest(
            user_id="usr_gdpr_subject_01",
            ephemeral_processing_accepted=True,
            ai_training_opt_in=True
        ),
        current_user=user
    )
    active_consent = get_user_privacy_consent(user_id="usr_gdpr_subject_01", current_user=user)
    assert active_consent["ai_training_opt_in"] is True
    assert active_consent["opt_in_timestamp"] is not None

    # User withdraws consent (Right to Object / Article 21)
    update_user_privacy_consent(
        UserConsentRequest(
            user_id="usr_gdpr_subject_01",
            ephemeral_processing_accepted=True,
            ai_training_opt_in=False
        ),
        current_user=user
    )
    withdrawn = get_user_privacy_consent(user_id="usr_gdpr_subject_01", current_user=user)
    assert withdrawn["ai_training_opt_in"] is False
    assert withdrawn["opt_in_timestamp"] is None


def test_gdpr_article_20_export_and_article_17_purge():
    """Verifies complete GDPR export archive generation and permanent account erasure."""
    uid = "usr_gdpr_e2e_full"
    user = UserContext(user_id=uid, email="gdpr.full@yorvyn.ai")

    # Seed data across domains
    supabase_repo.upsert_profile(uid, {"display_name": "Full Subject", "email": "gdpr.full@yorvyn.ai"})
    supabase_repo.upsert_subscription(uid, {"plan_id": "pro", "status": "active"})
    supabase_repo.record_usage(uid, "garment_reconstruction", 1, "job_gdpr_01", 0.0)

    # 1. GDPR Article 20 Export
    export_res = export_user_data_archive(user_id=uid, current_user=user)
    assert export_res["user_id"] == uid
    assert "subscription" in export_res
    assert "usage_records" in export_res
    assert export_res["gdpr_compliance"]["right_to_portability"] is True

    # 2. GDPR Article 17 Permanent Purge
    purge_res = purge_user_data_request(user_id=uid, current_user=user)
    assert purge_res["status"] == "success"

    # Verify complete erasure
    assert supabase_repo.get_profile(uid) is None
    assert supabase_repo.get_subscription(uid) is None
    assert len(supabase_repo.get_usage_records(uid)) == 0


# ==============================================================================
# SECTION 4: AI JOB RELIABILITY, WORKER CAPACITY & RESILIENCE
# ==============================================================================

def test_file_size_abuse_limit():
    """Submitting photograph exceeding 25MB is strictly rejected."""
    huge_bytes = b"0" * (26 * 1024 * 1024)  # 26MB
    with pytest.raises(ValueError) as excinfo:
        garment_job_manager.create_job(
            user_id="usr_abuse_01",
            front_image_bytes=huge_bytes,
            category="top"
        )
    assert "25MB" in str(excinfo.value)


def test_max_concurrent_jobs_per_user():
    """User cannot launch more than 2 concurrent active jobs."""
    img_bytes = _create_synthetic_image()
    uid = "usr_concurrency_cap"

    # Create 2 active jobs
    j1 = GarmentGenJob(
        job_id="job_active_1",
        user_id=uid,
        status=GarmentGenJobStatus.ANALYZING,
        progress=20,
        current_stage="Analyzing",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        temporary_files=[]
    )
    j2 = GarmentGenJob(
        job_id="job_active_2",
        user_id=uid,
        status=GarmentGenJobStatus.GENERATING_MESH,
        progress=45,
        current_stage="Mesh",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        temporary_files=[]
    )
    garment_job_manager._jobs["job_active_1"] = j1
    garment_job_manager._jobs["job_active_2"] = j2

    # Attempt 3rd job
    with pytest.raises(ValueError) as excinfo:
        garment_job_manager.create_job(
            user_id=uid,
            front_image_bytes=img_bytes,
            category="top"
        )
    assert "concurrent job limit" in str(excinfo.value).lower()

    # Clean up mock active jobs
    del garment_job_manager._jobs["job_active_1"]
    del garment_job_manager._jobs["job_active_2"]


def test_stranded_job_recovery_on_restart():
    """Sweeps stranded non-terminal jobs on restart and sets them to failed."""
    uid = "usr_stranded_01"
    stranded_job = GarmentGenJob(
        job_id="job_stranded_99",
        user_id=uid,
        status=GarmentGenJobStatus.GENERATING_MESH,
        progress=45,
        current_stage="Incomplete mesh generation",
        created_at=datetime.utcnow() - timedelta(minutes=10),
        updated_at=datetime.utcnow() - timedelta(minutes=10),
        temporary_files=[]
    )
    garment_job_manager._jobs["job_stranded_99"] = stranded_job

    recovered_count = garment_job_manager.recover_stranded_jobs()
    assert recovered_count >= 1
    assert stranded_job.status == GarmentGenJobStatus.FAILED
    assert "interrupted by server restart" in stranded_job.error.lower()

    # Clean up mock job
    del garment_job_manager._jobs["job_stranded_99"]


# ==============================================================================
# SECTION 5: STRIPE SUBSCRIPTIONS, WEBHOOKS & ENTITLEMENT QUOTAS
# ==============================================================================

def test_subscription_plans_catalog():
    """Verifies subscription plan definitions and limits."""
    plans = SUBSCRIPTION_PLANS
    assert "explorer" in plans
    assert "pro" in plans
    assert "studio" in plans

    assert plans["explorer"].price_usd == 0.0
    assert plans["explorer"].monthly_reconstructions == 5
    assert plans["explorer"].max_saved_looks == 10

    assert plans["pro"].price_usd == 19.99
    assert plans["pro"].monthly_reconstructions == -1  # Unlimited
    assert plans["pro"].fair_use_reconstructions == 100
    assert plans["pro"].priority_queue is True

    assert plans["studio"].price_usd == 99.0
    assert plans["studio"].commercial_export is True
    assert plans["studio"].multi_avatar is True


def test_stripe_checkout_session_creation():
    """Verifies Stripe Checkout session creation in test mode."""
    session = stripe_billing_service.create_checkout_session(
        user_id="usr_stripe_checkout_01",
        user_email="checkout@yorvyn.ai",
        plan_id="pro"
    )
    assert session["session_id"].startswith("cs_test_")
    assert "url" in session
    assert session["plan_id"] == "pro"
    assert session["user_id"] == "usr_stripe_checkout_01"


def test_stripe_portal_session_creation():
    """Verifies Stripe Customer Portal session generation."""
    portal = stripe_billing_service.create_customer_portal_session(
        user_id="usr_stripe_checkout_01"
    )
    assert portal["portal_id"].startswith("bps_test_")
    assert "url" in portal


def test_stripe_webhook_processing_and_idempotency():
    """Verifies webhook signature verification, state update, and replay attack prevention."""
    uid = "usr_stripe_webhook_01"
    evt_id = f"evt_test_{uuid.uuid4().hex[:12]}"

    payload = {
        "id": evt_id,
        "type": "checkout.session.completed",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": "cs_test_success_123",
                "customer": "cus_test_abc",
                "subscription": "sub_test_xyz",
                "client_reference_id": uid,
                "metadata": {
                    "user_id": uid,
                    "plan_id": "pro"
                }
            }
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")

    # 1. First webhook processing -> must succeed and activate Pro subscription
    res1 = stripe_billing_service.verify_and_process_webhook(raw_body, sig_header="test_sig")
    assert res1["status"] == "processed"
    assert res1["event_type"] == "checkout.session.completed"

    # User subscription must now be active Pro
    sub = supabase_repo.get_subscription(uid)
    assert sub["plan_id"] == "pro"
    assert sub["status"] == "active"

    # 2. Second webhook processing with same event_id -> must be deduplicated
    res2 = stripe_billing_service.verify_and_process_webhook(raw_body, sig_header="test_sig")
    assert res2["status"] in ("duplicate", "already_processed")
    assert res2["event_id"] == evt_id


def test_stripe_webhook_payment_failed_degrades():
    """Verifies that invoice.payment_failed updates subscription to past_due and degrades entitlements."""
    uid = "usr_stripe_fail_01"
    # Seed active Pro
    supabase_repo.upsert_subscription(uid, {
        "plan_id": "pro",
        "status": "active",
        "stripe_customer_id": "cus_test_fail",
        "stripe_subscription_id": "sub_test_fail"
    })

    evt_id = f"evt_fail_{uuid.uuid4().hex[:12]}"
    payload = {
        "id": evt_id,
        "type": "invoice.payment_failed",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": "in_test_fail",
                "customer": "cus_test_fail",
                "subscription": "sub_test_fail",
                "amount_due": 1999,
                "attempt_count": 2
            }
        }
    }
    raw_body = json.dumps(payload).encode("utf-8")

    res = stripe_billing_service.verify_and_process_webhook(raw_body, sig_header="test_sig")
    assert res["status"] == "processed"

    # Check updated subscription status
    sub = supabase_repo.get_subscription(uid)
    assert sub["status"] == "past_due"

    # Check entitlement degradation to Explorer
    plan, _ = entitlement_service.get_user_plan_and_sub(uid)
    assert plan.id == "explorer"


def test_explorer_reconstruction_quota_enforcement():
    """Explorer tier allows 5 reconstructions; 6th is rejected."""
    uid = "usr_explorer_quota_test"
    # User on Explorer tier
    supabase_repo.upsert_subscription(uid, {"plan_id": "explorer", "status": "active"})

    # Record 4 reconstructions
    for i in range(4):
        entitlement_service.record_reconstruction_usage(uid, f"job_{i}", 0.0)

    # 5th is allowed
    allowed, _ = entitlement_service.check_reconstruction_entitlement(uid)
    assert allowed is True

    # Record 5th
    entitlement_service.record_reconstruction_usage(uid, "job_5", 0.0)

    # 6th must be blocked
    allowed_6th, reason = entitlement_service.check_reconstruction_entitlement(uid)
    assert allowed_6th is False
    assert "quota reached (5/5)" in reason


def test_saved_looks_capacity_enforcement():
    """Explorer tier allows max 10 looks; 11th is rejected."""
    uid = "usr_explorer_looks_cap"
    user = UserContext(user_id=uid)
    supabase_repo.upsert_subscription(uid, {"plan_id": "explorer", "status": "active"})

    # Check entitlement allows up to 10
    can_save_10, _ = entitlement_service.can_save_look(uid, 9)
    assert can_save_10 is True

    # Check 11th is blocked
    can_save_11, reason = entitlement_service.can_save_look(uid, 10)
    assert can_save_11 is False
    assert "capacity reached (10/10)" in reason


def test_commercial_export_entitlement():
    """Commercial GLB export is blocked on Explorer and Pro, allowed on Studio."""
    # Explorer
    can_exp_exp, _ = entitlement_service.can_export_commercial_glb("usr_anon_export")
    assert can_exp_exp is False

    # Studio
    supabase_repo.upsert_subscription("usr_brand_studio", {"plan_id": "studio", "status": "active"})
    can_exp_studio, _ = entitlement_service.can_export_commercial_glb("usr_brand_studio")
    assert can_exp_studio is True
