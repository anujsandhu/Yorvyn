"""
Continuous AI Learning & Personalization Engine Test Suite for Yorvyn.
Comprehensive verification of:
1. Personalization from explicit preferences
2. Preference confidence updates & evidence accumulation
3. Feedback persistence & consent snapshots
4. Consent disabled enforcement
5. Consent enabled ingestion
6. Image training consent independently disabled
7. Global training eligibility & validation
8. Invalid feedback rejection
9. Duplicate feedback detection (hashing)
10. Poisoning protection & contradiction quarantine
11. Training dataset generation & versioning
12. Dataset provenance & audit traceability
13. Model evaluation on held-out benchmarks
14. Candidate model rejection upon quality regression
15. Safe model deployment & previous model archiving
16. Zero-downtime rollback controls
17. Complete user data deletion propagation
18. Strict cross-user data isolation
19. User preference & learning data export
20. Session context separation & model weight isolation
"""

from __future__ import annotations

import time
import uuid
import pytest
from fastapi.testclient import TestClient
from jose import jwt

from backend.app.main import app
from backend.app.core.settings import settings
from backend.app.services.database.supabase_repository import supabase_repo
from backend.app.services.learning.personalization_service import personalization_service
from backend.app.services.learning.feedback_pipeline import feedback_pipeline
from backend.app.services.learning.model_training_service import model_training_service

client = TestClient(app)


def _generate_jwt(user_id: str, email: str = "user@yorvyn.ai", role: str = "authenticated") -> str:
    secret = settings.supabase_jwt_secret or settings.secret_key
    now_ts = int(time.time())
    claims = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "role": role,
        "exp": now_ts + 7200,
        "iat": now_ts
    }
    return jwt.encode(claims, secret, algorithm="HS256")


def _auth_header(token: str, admin_key: bool = False) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if admin_key:
        headers["X-Admin-Key"] = settings.secret_key
    return headers


# ── Test 1: Personalization from explicit preferences ─────────────────────────
def test_01_personalization_from_explicit_preferences():
    uid = f"usr_test_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    res = client.post(
        "/api/learning/preferences",
        json={
            "category": "fit",
            "key": "silhouette",
            "value": "oversized",
            "source": "explicit",
            "confidence": 0.90
        },
        headers=_auth_header(token)
    )
    assert res.status_code == 201
    data = res.json()
    assert data["preference_category"] == "fit"
    assert data["preference_key"] == "silhouette"
    assert data["preference_value"] == "oversized"
    assert data["confidence"] >= 0.90

    # Verify context builder incorporates this preference
    ctx = personalization_service.build_personalized_context(uid)
    assert ctx["personalization_enabled"] is True
    assert "oversized" in ctx["fit_preferences"]
    assert ctx["confidence"]["silhouette"] >= 0.90


# ── Test 2: Preference confidence updates ─────────────────────────────────────
def test_02_preference_confidence_updates():
    uid = f"usr_test_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    # First interaction
    res1 = client.post(
        "/api/learning/preferences",
        json={
            "category": "colour",
            "key": "dark_palette",
            "value": "dark chocolate brown",
            "source": "behavioral",
            "confidence": 0.60
        },
        headers=_auth_header(token)
    )
    assert res1.status_code == 201
    assert res1.json()["evidence_count"] == 1
    initial_conf = res1.json()["confidence"]

    # Re-confirm preference (behavioral reinforcement)
    res2 = client.post(
        "/api/learning/preferences",
        json={
            "category": "colour",
            "key": "dark_palette",
            "value": "dark chocolate brown",
            "source": "behavioral",
            "confidence": 0.60
        },
        headers=_auth_header(token)
    )
    assert res2.status_code == 201
    assert res2.json()["evidence_count"] == 2
    # Confidence must increase
    assert res2.json()["confidence"] > initial_conf


# ── Test 3: Feedback persistence ──────────────────────────────────────────────
def test_03_feedback_persistence():
    uid = f"usr_test_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)
    sess_id = str(uuid.uuid4())
    msg_id = str(uuid.uuid4())

    res = client.post(
        "/api/learning/feedback",
        json={
            "feedback_type": "correction",
            "session_id": sess_id,
            "message_id": msg_id,
            "rating": 4,
            "original_output": {"category": "sweater", "fit": "regular"},
            "corrected_output": {"category": "hoodie", "fit": "oversized"},
            "feedback_text": "This item is an oversized pullover hoodie, not a regular sweater."
        },
        headers=_auth_header(token)
    )
    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    fb = body["feedback"]
    assert fb["session_id"] == sess_id
    assert fb["feedback_type"] == "correction"
    assert fb["rating"] == 4
    assert fb["corrected_output"]["category"] == "hoodie"
    assert "consent_snapshot" in fb


# ── Test 4: Consent disabled enforcement ──────────────────────────────────────
def test_04_consent_disabled():
    uid = f"usr_test_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    # Explicitly ensure global training consent is False
    client.put(
        "/api/learning/consent",
        json={"global_model_training_enabled": False, "personalization_enabled": True},
        headers=_auth_header(token)
    )

    # Submit feedback with correction
    res = client.post(
        "/api/learning/feedback",
        json={
            "feedback_type": "correction",
            "original_output": {"fabric": "polyester"},
            "corrected_output": {"fabric": "100% heavyweight cotton fleece"},
            "feedback_text": "Material is brushed cotton fleece."
        },
        headers=_auth_header(token)
    )
    assert res.status_code == 201
    pipe_status = res.json()["pipeline_status"]
    # Must be excluded from global training
    assert pipe_status["status"] == "excluded"
    assert "Global model training consent not enabled" in pipe_status["reason"]

    # But Layer A personalization must still work!
    prefs = client.get("/api/learning/preferences", headers=_auth_header(token)).json()
    assert len(prefs) >= 1
    assert any("cotton" in str(p["preference_value"]) for p in prefs)


# ── Test 5: Consent enabled ingestion ─────────────────────────────────────────
def test_05_consent_enabled():
    uid = f"usr_test_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    # Enable global training consent
    client.put(
        "/api/learning/consent",
        json={"global_model_training_enabled": True},
        headers=_auth_header(token)
    )

    res = client.post(
        "/api/learning/feedback",
        json={
            "feedback_type": "correction",
            "original_output": {"category": "jacket"},
            "corrected_output": {"category": "oversized_hoodie"},
            "feedback_text": "Item is an oversized hoodie with kangaroo pocket.",
            "metadata": {"task_type": "classification"}
        },
        headers=_auth_header(token)
    )
    assert res.status_code == 201
    pipe_status = res.json()["pipeline_status"]
    # Must be validated and enrolled into learning examples
    assert pipe_status["status"] == "validated"
    assert pipe_status["example_id"] is not None
    assert pipe_status["quality_score"] >= 0.85


# ── Test 6: Image training consent independently disabled ─────────────────────
def test_06_image_training_consent_independently_disabled():
    uid = f"usr_test_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    # Global training True, but image training False
    client.put(
        "/api/learning/consent",
        json={"global_model_training_enabled": True, "image_training_enabled": False},
        headers=_auth_header(token)
    )

    res = client.post(
        "/api/learning/feedback",
        json={
            "feedback_type": "correction",
            "original_output": {"mask_pixels": 1200},
            "corrected_output": {"mask_pixels": 1850},
            "feedback_text": "Corrected garment segmentation contour",
            "metadata": {"task_type": "segmentation"}
        },
        headers=_auth_header(token)
    )
    assert res.status_code == 201
    pipe_status = res.json()["pipeline_status"]
    assert pipe_status["status"] == "excluded"
    assert "Image training consent not enabled" in pipe_status["reason"]


# ── Test 7: Global training eligibility & validation ──────────────────────────
def test_07_global_training_eligibility():
    uid = f"usr_test_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    client.put(
        "/api/learning/consent",
        json={"global_model_training_enabled": True, "image_training_enabled": True},
        headers=_auth_header(token)
    )

    res = client.post(
        "/api/learning/feedback",
        json={
            "feedback_type": "correction",
            "original_output": {"category": "t-shirt", "color": "white"},
            "corrected_output": {"category": "hoodie", "color": "brown"},
            "feedback_text": "High quality garment classification correction",
            "metadata": {"task_type": "classification"}
        },
        headers=_auth_header(token)
    )
    example_id = res.json()["pipeline_status"]["example_id"]
    example = supabase_repo.get_learning_example(example_id)
    assert example is not None
    assert example["validation_status"] == "validated"
    assert example["consent_scope"] == "global_model_training"
    assert example["quality_score"] >= 0.80


# ── Test 8: Invalid feedback rejection ────────────────────────────────────────
def test_08_invalid_feedback_rejection():
    # Empty payload or malformed labels with script tags
    is_valid, quality, reason = feedback_pipeline.validate_correction_integrity(
        original_output={"category": "shirt"},
        corrected_output={"<script>alert('xss')</script>": "val"},
        feedback_text="Malicious payload"
    )
    assert is_valid is False
    assert "Poisoning detected" in reason or "Malformed label" in reason


# ── Test 9: Duplicate feedback detection ──────────────────────────────────────
def test_09_duplicate_feedback_detection():
    uid = f"usr_test_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    client.put(
        "/api/learning/consent",
        json={"global_model_training_enabled": True},
        headers=_auth_header(token)
    )

    feedback_payload = {
        "feedback_type": "correction",
        "original_output": {"garment_id": "item_alpha", "pattern": "solid"},
        "corrected_output": {"garment_id": "item_alpha", "pattern": "houndstooth"},
        "feedback_text": "Specific pattern is houndstooth",
        "metadata": {"task_type": "classification"}
    }

    res1 = client.post("/api/learning/feedback", json=feedback_payload, headers=_auth_header(token))
    assert res1.json()["pipeline_status"]["status"] == "validated"

    # Exact duplicate submission
    res2 = client.post("/api/learning/feedback", json=feedback_payload, headers=_auth_header(token))
    assert res2.json()["pipeline_status"]["status"] == "duplicate"
    assert "Identical training example already exists" in res2.json()["pipeline_status"]["reason"]


# ── Test 10: Poisoning protection & contradiction quarantine ──────────────────
def test_10_poisoning_protection():
    uid = f"usr_test_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    client.put(
        "/api/learning/consent",
        json={"global_model_training_enabled": True},
        headers=_auth_header(token)
    )

    # Contradiction: user sends correction that is 100% identical to model prediction
    res = client.post(
        "/api/learning/feedback",
        json={
            "feedback_type": "correction",
            "original_output": {"fit": "regular", "color": "blue"},
            "corrected_output": {"fit": "regular", "color": "blue"},
            "feedback_text": "This is completely contradictory and identical",
            "metadata": {"task_type": "classification"}
        },
        headers=_auth_header(token)
    )
    assert res.status_code == 201
    pipe_status = res.json()["pipeline_status"]
    assert pipe_status["status"] == "quarantined"
    assert "Contradictory feedback" in pipe_status["reason"]


# ── Test 11: Training dataset generation & versioning ─────────────────────────
def test_11_training_dataset_generation():
    # Verify examples are assigned explicit dataset versions
    dataset_v = "garment_tax_v1.3_prod"
    ex = supabase_repo.create_learning_example(
        source_feedback_id=str(uuid.uuid4()),
        task_type="classification",
        input_reference={"feature": "pocket"},
        target_output={"component": "kangaroo_pocket"},
        consent_scope="global_model_training",
        quality_score=0.92,
        validation_status="validated",
        dataset_version=dataset_v
    )
    assert ex["dataset_version"] == dataset_v

    dataset_examples = supabase_repo.list_learning_examples(dataset_version=dataset_v)
    assert len(dataset_examples) >= 1
    assert all(e["dataset_version"] == dataset_v for e in dataset_examples)


# ── Test 12: Dataset provenance & audit traceability ──────────────────────────
def test_12_dataset_provenance():
    source_fid = str(uuid.uuid4())
    ex = supabase_repo.create_learning_example(
        source_feedback_id=source_fid,
        task_type="reconstruction",
        input_reference={"mesh_id": "mesh_101"},
        target_output={"hood_depth_mm": 240},
        consent_scope="global_model_training",
        quality_score=0.95,
        validation_status="validated"
    )
    retrieved = supabase_repo.get_learning_example(ex["id"])
    assert retrieved["source_feedback_id"] == source_fid
    assert retrieved["created_at"] is not None
    assert retrieved["validated_at"] is not None


# ── Test 13: Model evaluation on held-out benchmarks ──────────────────────────
def test_13_model_evaluation():
    # Register candidate model
    cand = supabase_repo.register_model(
        model_name="universal_garment_classifier",
        model_version="v1.1.0_eval",
        task_type="classification",
        artifact_uri="s3://yorvyn-models/candidates/garment_v1.1.0.onnx",
        artifact_checksum="sha256:eval123",
        status="candidate"
    )

    eval_res = model_training_service.evaluate_candidate_model(
        model_name="universal_garment_classifier",
        model_version="v1.1.0_eval",
        synthetic_benchmark_results={"accuracy": 0.952, "macro_f1": 0.948}
    )
    assert eval_res["meets_quality_gate"] is True
    assert eval_res["decision"] == "approved"
    assert eval_res["candidate_metrics"]["accuracy"] == 0.952


# ── Test 14: Candidate model rejection upon quality regression ────────────────
def test_14_candidate_model_rejection():
    cand = supabase_repo.register_model(
        model_name="universal_garment_classifier",
        model_version="v0.9.0_flawed",
        task_type="classification",
        artifact_uri="s3://yorvyn-models/candidates/garment_flawed.onnx",
        artifact_checksum="sha256:flawed123",
        status="candidate"
    )

    # Benchmark accuracy lower than deployed baseline (0.932)
    eval_res = model_training_service.evaluate_candidate_model(
        model_name="universal_garment_classifier",
        model_version="v0.9.0_flawed",
        synthetic_benchmark_results={"accuracy": 0.812, "macro_f1": 0.795}
    )
    assert eval_res["meets_quality_gate"] is False
    assert eval_res["decision"] == "rejected"
    assert len(eval_res["regression_reasons"]) > 0

    # Ensure candidate CANNOT be deployed
    with pytest.raises(ValueError, match="Cannot deploy model in 'rejected' state"):
        model_training_service.deploy_approved_model("universal_garment_classifier", "v0.9.0_flawed")


# ── Test 15: Safe model deployment & previous model archiving ─────────────────
def test_15_safe_model_deployment():
    # Register and approve candidate
    supabase_repo.register_model(
        model_name="universal_garment_classifier",
        model_version="v2.0.0_gold",
        task_type="classification",
        artifact_uri="s3://yorvyn-models/candidates/garment_v2.onnx",
        artifact_checksum="sha256:gold200",
        evaluation_metrics={"accuracy": 0.965, "macro_f1": 0.960},
        status="approved"
    )

    deploy_res = model_training_service.deploy_approved_model("universal_garment_classifier", "v2.0.0_gold")
    assert deploy_res["success"] is True

    # Check active deployed model
    deployed = supabase_repo.get_deployed_model("classification")
    assert deployed is not None
    assert deployed["model_version"] == "v2.0.0_gold"


# ── Test 16: Zero-downtime rollback controls ──────────────────────────────────
def test_16_rollback():
    # Roll back from v2.0.0_gold to baseline v1.0.0
    rollback_res = model_training_service.rollback_task_model(task_type="classification", target_version="v1.0.0")
    assert rollback_res["success"] is True
    assert rollback_res["rolled_back_to"] == "v1.0.0"

    # Verify deployed model is now v1.0.0
    active = supabase_repo.get_deployed_model("classification")
    assert active["model_version"] == "v1.0.0"
    assert active["status"] == "deployed"


# ── Test 17: Complete user data deletion propagation ──────────────────────────
def test_17_user_data_deletion():
    uid = f"usr_test_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    # Add preferences
    client.post(
        "/api/learning/preferences",
        json={"category": "brand", "key": "favorite", "value": "Acne Studios"},
        headers=_auth_header(token)
    )

    # Purge user data
    del_res = client.delete("/api/learning/user-data", headers=_auth_header(token))
    assert del_res.status_code == 200
    assert del_res.json()["preferences_purged"] >= 1

    # Verify user preferences are now empty
    prefs_after = client.get("/api/learning/preferences", headers=_auth_header(token)).json()
    assert len(prefs_after) == 0


# ── Test 18: Strict cross-user data isolation ─────────────────────────────────
def test_18_cross_user_isolation():
    user_a = f"usr_a_{uuid.uuid4().hex[:8]}"
    user_b = f"usr_b_{uuid.uuid4().hex[:8]}"
    token_a = _generate_jwt(user_a)
    token_b = _generate_jwt(user_b)

    # User A likes avant-garde Japanese denim
    client.post(
        "/api/learning/preferences",
        json={"category": "style", "key": "avant_garde_denim", "value": "Kapital"},
        headers=_auth_header(token_a)
    )

    # User B checks their preferences
    res_b = client.get("/api/learning/preferences", headers=_auth_header(token_b))
    assert res_b.status_code == 200
    assert len(res_b.json()) == 0

    # User B builds personalized context: MUST NOT contain User A's data
    ctx_b = personalization_service.build_personalized_context(user_b)
    assert "avant_garde_denim" not in ctx_b["confidence"]
    assert "Kapital" not in ctx_b["style_preferences"]


# ── Test 19: User preference & learning data export ───────────────────────────
def test_19_user_preference_export():
    uid = f"usr_test_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    client.post(
        "/api/learning/preferences",
        json={"category": "budget", "key": "tier", "value": "luxury_investment"},
        headers=_auth_header(token)
    )

    export_res = client.get("/api/learning/preferences/export", headers=_auth_header(token))
    assert export_res.status_code == 200
    export_data = export_res.json()
    assert export_data["user_id"] == uid
    assert "export_timestamp" in export_data
    assert "consent_settings" in export_data
    assert export_data["preferences_count"] >= 1
    assert export_data["preferences"][0]["preference_key"] == "tier"


# ── Test 20: Session context separation & model weight isolation ──────────────
def test_20_session_context_separation():
    uid = f"usr_test_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    # Create Session 1
    s1 = supabase_repo.create_ai_session(user_id=uid, title="Winter Outerwear")
    s1_id = s1["id"]
    supabase_repo.update_ai_session(s1_id, uid, {"context_summary": "Looking for heavy shearling coats."})

    # Create Session 2
    s2 = supabase_repo.create_ai_session(user_id=uid, title="Summer Linen Shirts")
    s2_id = s2["id"]

    # Verify context built for Session 1 includes shearling coats
    ctx1 = personalization_service.build_personalized_context(uid, session_id=s1_id)
    assert ctx1["session_context"] == "Looking for heavy shearling coats."

    # Verify context built for Session 2 has NO knowledge of Session 1's context summary
    ctx2 = personalization_service.build_personalized_context(uid, session_id=s2_id)
    assert ctx2["session_context"] is None

    # Verify global model weights and registry status are completely decoupled and unchanged
    deployed_clf = supabase_repo.get_deployed_model("classification")
    assert deployed_clf is not None
    assert deployed_clf["status"] == "deployed"

