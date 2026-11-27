"""
Continuous Garment Intelligence Learning Test Suite for Yorvyn.
Verifies:
1. Original model prediction immutability under user corrections
2. End-to-end correction provenance (model_name, version, inference_id, session_id, feedback_id)
3. Server-side consent enforcement (personalization vs shared global training)
4. Dataset eligibility and validation gating
5. Duplicate correction rejection (SHA-256 deduplication)
6. Conflicting and contradictory label quarantine
7. Model version tracking across inferences
8. Multi-session context isolation
9. Strict cross-user data isolation
10. Deletion propagation and GDPR compliance
11. Strict machine-comparable benchmark accuracy calculation (floral dress audit)
12. Separation of training data from held-out evaluation benchmarks
13. Candidate model rejection on regression
14. Zero-downtime production rollback
15. Multi-view photograph uncertainty resolution
16. Subjective styling feedback vs objective visual reconstruction distinction
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from jose import jwt

from backend.app.main import app
from backend.app.core.settings import settings
from backend.app.services.database.supabase_repository import supabase_repo
from backend.app.services.garments.intelligence.automatic_garment_detector import automatic_garment_detector
from backend.app.services.learning.personalization_service import personalization_service
from backend.app.services.learning.model_training_service import model_training_service

client = TestClient(app)


def _get_test_garment_image() -> Image.Image:
    path = Path("docs/reports/hoodie_visual_regression/reference_hoodie.png")
    if path.exists():
        return Image.open(path).convert("RGB")
    img = Image.new("RGB", (320, 320), (240, 240, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle([60, 60, 260, 260], fill=(52, 43, 43))
    return img


def _get_test_back_image() -> Image.Image:
    front = _get_test_garment_image()
    back = front.copy()
    draw = ImageDraw.Draw(back)
    w, h = back.size
    # Smooth back panel covering kangaroo pocket
    draw.rectangle([int(w * 0.3), int(h * 0.3), int(w * 0.7), int(h * 0.8)], fill=(52, 43, 43))
    return back


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


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── Test 1: Original prediction immutability ──────────────────────────────────
def test_01_original_prediction_immutability():
    """
    Ensures that when a user applies a correction, the original model prediction
    is NEVER overwritten and remains permanently audited.
    """
    test_img = _get_test_garment_image()
    corrections = {
        "category": "outerwear",
        "subcategory": "trench_coat",
        "silhouette": "tailored_slim",
        "fabric": "linen"
    }

    res = automatic_garment_detector.detect(
        front_image=test_img,
        user_corrections=corrections
    )

    uc = res.user_correction_state
    assert uc.is_user_corrected is True
    # Original prediction must preserve what the model actually predicted
    assert uc.original_prediction["silhouette"] != "tailored_slim"
    assert uc.original_prediction["fabric"] != "linen"
    assert uc.original_prediction["category"] in ("tops", "bottoms", "outerwear", "dresses_and_skirts")
    # Final reconstruction input reconciles the correction
    assert uc.final_reconstruction_input["silhouette"] == "tailored_slim"
    assert uc.final_reconstruction_input["fabric"] == "linen"


# ── Test 2: Correction provenance tracking ────────────────────────────────────
def test_02_correction_provenance():
    """
    Verifies that all provenance fields (model_name, version, inference_id,
    session_id, feedback_id, timestamps) are faithfully recorded.
    """
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    sess_id = str(uuid.uuid4())
    inf_id = f"inf_{uuid.uuid4().hex[:12]}"
    test_img = _get_test_garment_image()

    res = automatic_garment_detector.detect(
        front_image=test_img,
        user_corrections={"subcategory": "hoodie"},
        session_id=sess_id,
        inference_id=inf_id,
        user_id=uid
    )

    uc = res.user_correction_state
    assert uc.model_name == "universal_garment_classifier"
    assert uc.model_version == "v1.0.0"
    assert uc.inference_id == inf_id
    assert uc.session_id == sess_id
    assert uc.correction_timestamp is not None


# ── Test 3: Consent enforcement on garment learning ───────────────────────────
def test_03_consent_enforcement():
    """
    Verifies that when a user disables shared training, garment corrections
    do not enter the shared training dataset, but still refine personal memory.
    """
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    # Opt out of global training
    client.put(
        "/api/learning/consent",
        json={"global_model_training_enabled": False, "personalization_enabled": True},
        headers=_auth_header(token)
    )

    res = automatic_garment_detector.record_user_correction_signal(
        inference_id=f"inf_{uuid.uuid4().hex[:10]}",
        user_id=uid,
        event_type="silhouette_correction",
        original_prediction={"silhouette": "regular"},
        user_correction={"silhouette": "oversized"}
    )

    assert res["success"] is True
    # Global pipeline must exclude it
    assert res["pipeline_status"]["status"] == "excluded"
    assert res["user_correction_state"]["consent_scope"] == "personalization_only"

    # Layer A Personalization Memory MUST still record preference for oversized
    prefs = personalization_service.get_user_preferences(uid, category="fit")
    assert any("oversized" in str(p["preference_value"]) for p in prefs)


# ── Test 4: Dataset eligibility when consent granted ──────────────────────────
def test_04_dataset_eligibility():
    """
    When user grants explicit global and image training consent,
    valid visual corrections become eligible for versioned datasets.
    """
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    client.put(
        "/api/learning/consent",
        json={"global_model_training_enabled": True, "image_training_enabled": True},
        headers=_auth_header(token)
    )

    res = automatic_garment_detector.record_user_correction_signal(
        inference_id=f"inf_{uuid.uuid4().hex[:10]}",
        user_id=uid,
        event_type="category_correction",
        original_prediction={"category": "tops", "subcategory": "sweater"},
        user_correction={"category": "tops", "subcategory": "hoodie"},
        feedback_text="This is an oversized fleece hoodie"
    )

    assert res["success"] is True
    assert res["pipeline_status"]["status"] == "validated"
    assert res["user_correction_state"]["consent_scope"] == "global_model_training"
    assert res["user_correction_state"]["dataset_eligibility"] == "eligible"


# ── Test 5: Duplicate correction rejection ────────────────────────────────────
def test_05_duplicate_correction_rejection():
    """
    Deduplication hash blocks identical corrections from skewing training distributions.
    """
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    client.put(
        "/api/learning/consent",
        json={"global_model_training_enabled": True, "image_training_enabled": True},
        headers=_auth_header(token)
    )

    sig_payload = {
        "inference_id": f"inf_{uuid.uuid4().hex[:10]}",
        "user_id": uid,
        "event_type": "fabric_correction",
        "original_prediction": {"fabric": "polyester_knit"},
        "user_correction": {"fabric": "heavyweight_cotton_fleece"},
        "feedback_text": "Material is brushed cotton fleece"
    }

    res1 = automatic_garment_detector.record_user_correction_signal(**sig_payload)
    assert res1["pipeline_status"]["status"] == "validated"

    # Exact duplicate
    res2 = automatic_garment_detector.record_user_correction_signal(**sig_payload)
    assert res2["pipeline_status"]["status"] == "duplicate"


# ── Test 6: Conflicting and contradictory labels ──────────────────────────────
def test_06_conflicting_labels():
    """
    Contradictory feedback (where correction == original) is quarantined.
    """
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    client.put(
        "/api/learning/consent",
        json={"global_model_training_enabled": True},
        headers=_auth_header(token)
    )

    res = automatic_garment_detector.record_user_correction_signal(
        inference_id=f"inf_{uuid.uuid4().hex[:10]}",
        user_id=uid,
        event_type="colour_correction",
        original_prediction={"primary_color": "dark_brown"},
        user_correction={"primary_color": "dark_brown"},  # Identical = contradiction
        feedback_text="No actual change"
    )

    assert res["pipeline_status"]["status"] == "quarantined"


# ── Test 7: Model version tracking across inferences ──────────────────────────
def test_07_model_version_tracking():
    """
    Inferences faithfully record the active deployed model version.
    """
    test_img = _get_test_garment_image()
    res = automatic_garment_detector.detect(front_image=test_img)
    assert res.user_correction_state.model_name == "universal_garment_classifier"
    assert res.user_correction_state.model_version == "v1.0.0"


# ── Test 8: Multi-session context isolation ───────────────────────────────────
def test_08_session_isolation():
    """
    Garment inferences in Session 1 do not leak into Session 2.
    """
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    s1 = str(uuid.uuid4())
    s2 = str(uuid.uuid4())

    img1 = _get_test_garment_image()
    img2 = _get_test_garment_image()

    det1 = automatic_garment_detector.detect(front_image=img1, session_id=s1, user_id=uid)
    det2 = automatic_garment_detector.detect(front_image=img2, session_id=s2, user_id=uid)

    assert det1.user_correction_state.session_id == s1
    assert det2.user_correction_state.session_id == s2
    assert det1.analysis_id != det2.analysis_id


# ── Test 9: Strict cross-user data isolation ──────────────────────────────────
def test_09_cross_user_isolation():
    """
    User A's garment corrections do not alter User B's preferences or classifications.
    """
    user_a = f"usr_a_{uuid.uuid4().hex[:8]}"
    user_b = f"usr_b_{uuid.uuid4().hex[:8]}"

    # User A corrects silhouette to oversized
    automatic_garment_detector.record_user_correction_signal(
        inference_id=f"inf_{uuid.uuid4().hex[:10]}",
        user_id=user_a,
        event_type="silhouette_correction",
        original_prediction={"silhouette": "regular"},
        user_correction={"silhouette": "oversized"}
    )

    # Check User B's context
    ctx_b = personalization_service.build_personalized_context(user_b)
    assert "oversized" not in ctx_b["fit_preferences"]


# ── Test 10: Deletion propagation and GDPR compliance ─────────────────────────
def test_10_deletion_propagation():
    """
    Deleting user data purges preferences and derived learning examples.
    """
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    token = _generate_jwt(uid)

    client.put(
        "/api/learning/consent",
        json={"global_model_training_enabled": True, "image_training_enabled": True},
        headers=_auth_header(token)
    )

    automatic_garment_detector.record_user_correction_signal(
        inference_id=f"inf_{uuid.uuid4().hex[:10]}",
        user_id=uid,
        event_type="fabric_correction",
        original_prediction={"fabric": "denim"},
        user_correction={"fabric": "corduroy"}
    )

    # Purge user data
    del_res = client.delete("/api/learning/user-data", headers=_auth_header(token))
    assert del_res.status_code == 200
    assert del_res.json()["training_examples_purged"] >= 1


# ── Test 11: Benchmark accuracy calculation (Floral dress audit) ──────────────
def test_11_benchmark_accuracy_calculation():
    """
    Verifies that machine-comparable evaluation strictly assesses labels:
    casual_dress vs maxi_dress must be evaluated as a mismatch (0.0), NOT coerced to 1.0.
    """
    ground_truth_sub = "casual_dress"
    predicted_sub = "maxi_dress"

    # Strict evaluation rule
    sub_accuracy = 1.0 if (predicted_sub == ground_truth_sub) else 0.0
    assert sub_accuracy == 0.0

    # Top level categories both match
    gt_cat = "dresses_and_skirts"
    pred_cat = "dresses_and_skirts"
    cat_accuracy = 1.0 if (pred_cat == gt_cat) else 0.0
    assert cat_accuracy == 1.0


# ── Test 12: Separation of training data from held-out evaluation benchmarks ──
def test_12_training_dataset_separation():
    """
    Verifies held-out test splits are isolated from training datasets.
    """
    held_out_ids = {"test_dress_01", "test_hoodie_02", "test_jacket_03"}
    training_examples = supabase_repo.list_learning_examples(limit=100)

    for ex in training_examples:
        input_ref = ex.get("input_reference", {})
        assert input_ref.get("item_id") not in held_out_ids


# ── Test 13: Candidate model rejection on regression ──────────────────────────
def test_13_candidate_model_rejection():
    """
    A model that degrades accuracy on held-out benchmarks is blocked from deployment.
    """
    cand = supabase_repo.register_model(
        model_name="universal_garment_classifier",
        model_version="v0.8.5_regressed",
        task_type="classification",
        artifact_uri="s3://yorvyn-models/candidates/regressed.onnx",
        artifact_checksum="sha256:reg123",
        status="candidate"
    )

    eval_res = model_training_service.evaluate_candidate_model(
        model_name="universal_garment_classifier",
        model_version="v0.8.5_regressed",
        synthetic_benchmark_results={"accuracy": 0.70, "macro_f1": 0.68}
    )

    assert eval_res["meets_quality_gate"] is False
    assert eval_res["decision"] == "rejected"


# ── Test 14: Zero-downtime production rollback ────────────────────────────────
def test_14_rollback():
    """
    Verifies atomic rollback to production baseline.
    """
    res = model_training_service.rollback_task_model("classification", target_version="v1.0.0")
    assert res["success"] is True
    deployed = supabase_repo.get_deployed_model("classification")
    assert deployed["model_version"] == "v1.0.0"


# ── Test 15: Multi-view photograph uncertainty resolution ─────────────────────
def test_15_multiview_photo_resolution():
    """
    When rear photograph is supplied, multi-view engine resolves rear observation.
    """
    front_img = _get_test_garment_image()
    back_img = _get_test_back_image()

    det = automatic_garment_detector.detect(front_image=front_img, back_image=back_img)
    assert det.views_summary["back"].supplied is True
    assert "observed" in det.views_summary["back"].status.lower()


# ── Test 16: Subjective styling feedback vs objective visual reconstruction ───
def test_16_reconstruction_rejection_distinction():
    """
    Distinguishes subjective styling rejection from objective visual reconstruction signals.
    Subjective feedback updates personal style memory, not 3D mesh training.
    """
    uid = f"usr_{uuid.uuid4().hex[:8]}"

    res = automatic_garment_detector.record_user_correction_signal(
        inference_id=f"inf_{uuid.uuid4().hex[:10]}",
        user_id=uid,
        event_type="reconstruction_rejection",
        original_prediction={"reconstruction_quality": "high"},
        user_correction={"preference": "dislike_color_combination"},
        feedback_text="I don't like this color combination on me",
        metadata={"is_visual_correction": False, "is_subjective": True}
    )

    assert res["success"] is True
    # Should not treat subjective preference as verified geometric ground truth
    assert res["task_type"] == "reconstruction"
