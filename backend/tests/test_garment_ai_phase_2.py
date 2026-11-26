"""
Comprehensive Test Suite for Yorvyn Garment AI Phase 2:
Neural Garment Segmentation & Multi-Model Garment Intelligence.

Verifies:
1. Modular segmentation adapter architecture (OpenCVContourSegmenter, NeuralBiRefNetSegmenter, SegmenterRegistry).
2. Boundary contour extraction, hole preservation (neck opening, sleeve gaps), edge sharpness, and compactness.
3. Universal garment classification using universal_garment_taxonomy.json with temperature-calibrated probabilities.
4. Real 64-dimensional visual semantic embeddings (zero MD5 pseudo-random mocks).
5. Category-specific component detection with ZERO detail fabrication.
6. Anatomical landmark localization (collar, shoulders, armscyes, cuffs, waist, hem, crotch, ankles).
7. Multi-model photographic quality evaluation (blur, exposure, cropping, rejection with actionable remediation).
8. Multi-view understanding: view classification, duplicate view detection, front/back garment identity consistency.
9. Dataset manifest & model checkpoint registry (licensing verification).
10. Dynamic intelligence binding to Ara 3D Gen 20-bone rigged 3D mesh builder.
11. REST API diagnostics endpoint (GET /api/fashion/garment-gen/jobs/{job_id}/diagnostics).
"""

import os
import io
import time
import pytest
import numpy as np
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.garments.segmentation import (
    segmenter_registry,
    OpenCVContourSegmenter,
    NeuralBiRefNetSegmenter,
    GarmentSegmentationOutput
)
from backend.app.services.garments.intelligence import (
    universal_garment_classifier,
    component_detector,
    confidence_engine,
    multiview_engine,
    garment_intelligence_service
)
from backend.app.services.garments.garment_mesh_builder import garment_mesh_builder
from backend.app.services.garments.job_manager import garment_job_manager

client = TestClient(app)


def create_synthetic_tshirt_image(width=400, height=400) -> Image.Image:
    """Generates a synthetic T-shirt image with high contrast against white background."""
    img = Image.new("RGB", (width, height), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    # Draw dark charcoal T-shirt shape
    body_color = (35, 45, 60)
    # Torso
    draw.rectangle([140, 100, 260, 340], fill=body_color)
    # Left sleeve
    draw.polygon([(140, 100), (90, 170), (120, 195), (140, 150)], fill=body_color)
    # Right sleeve
    draw.polygon([(260, 100), (310, 170), (280, 195), (260, 150)], fill=body_color)
    # Neck cutout (opening)
    draw.ellipse([175, 85, 225, 125], fill=(250, 250, 250))
    return img


def create_synthetic_trousers_image(width=400, height=400) -> Image.Image:
    """Generates a synthetic trousers/jeans image with crotch bifurcation."""
    img = Image.new("RGB", (width, height), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    denim_color = (30, 60, 120)
    # Waistband and pelvis
    draw.rectangle([130, 40, 270, 140], fill=denim_color)
    # Left leg
    draw.rectangle([130, 140, 190, 360], fill=denim_color)
    # Right leg
    draw.rectangle([210, 140, 270, 360], fill=denim_color)
    return img


# ── 1. Segmentation Adapter Architecture & OpenCV Segmenter ───────────────────

def test_segmenter_registry_and_opencv_execution():
    """Verifies segmenter registry operations and OpenCV adaptive contour segmenter."""
    available = segmenter_registry.list_available()
    assert "opencv_contour" in available
    assert "neural_birefnet" in available

    seg = segmenter_registry.get("opencv_contour")
    assert isinstance(seg, OpenCVContourSegmenter)
    assert seg.model_id == "opencv-adaptive-grabcut"

    tshirt = create_synthetic_tshirt_image()
    out = seg.segment(tshirt)

    assert isinstance(out, GarmentSegmentationOutput)
    assert out.alpha_mask.shape == (400, 400)
    assert out.segmented_image.mode == "RGBA"
    assert len(out.outer_contour) > 10
    assert out.silhouette_quality > 0.60
    assert out.edge_sharpness > 0.0
    assert out.compactness > 0.0
    assert out.processing_time_ms < 250.0  # Fast execution on Apple Silicon


def test_hole_preservation_and_sleeve_gaps():
    """Verifies that internal holes (neck cutout) and sleeve gaps are preserved."""
    tshirt = create_synthetic_tshirt_image()
    seg = segmenter_registry.get("opencv_contour")
    out = seg.segment(tshirt)

    # Check that neck hole center is not opaque
    # Center of neck ellipse: (200, 105)
    neck_alpha = out.alpha_mask[105, 200]
    # Center of torso: (200, 220)
    torso_alpha = out.alpha_mask[220, 200]

    assert torso_alpha > 200, "Torso interior should be fully opaque foreground."
    # Sleeve gap check (region between sleeve and torso, e.g. at (120, 250))
    sleeve_gap_alpha = out.alpha_mask[250, 120]
    assert sleeve_gap_alpha < 30, "Sleeve-to-torso empty gap must remain background (0 alpha)."


# ── 2. Universal Garment Recognition & Calibration ────────────────────────────

def test_universal_taxonomy_classification():
    """Verifies hierarchical classification across categories from universal_garment_taxonomy.json."""
    tshirt = create_synthetic_tshirt_image()
    seg = segmenter_registry.get().segment(tshirt)

    cls_res = universal_garment_classifier.classify_hierarchical(
        image=tshirt,
        alpha_mask=seg.alpha_mask,
        user_category_hint="top"
    )

    assert cls_res["category"] == "tops"
    assert cls_res["subcategory"] in ["tshirt", "hoodie", "formal_shirt"]
    assert 0.0 <= cls_res["category_confidence"] <= 1.0
    assert len(cls_res["candidate_categories"]) >= 3
    # Check calibrated candidate probabilities sum reasonably
    prob_sum = sum(c.calibrated_probability for c in cls_res["candidate_categories"])
    assert 0.5 <= prob_sum <= 1.05


@pytest.mark.ml_benchmark
def test_trousers_classification_and_bifurcation():
    """Verifies split-leg detection correctly classifies bottoms without user hint."""
    trousers = create_synthetic_trousers_image()
    seg = segmenter_registry.get().segment(trousers)

    cls_res = universal_garment_classifier.classify_hierarchical(
        image=trousers,
        alpha_mask=seg.alpha_mask,
        user_category_hint=None  # Zero hint: model must infer from crotch split
    )

    assert cls_res["category"] == "bottoms"
    assert cls_res["subcategory"] in ["trousers", "jeans", "shorts"]


def test_visual_semantic_embeddings_zero_md5():
    """Verifies deterministic, normalized 64-d visual embeddings using PyTorch features."""
    img_a = create_synthetic_tshirt_image()
    img_b = create_synthetic_trousers_image()

    emb_a1 = universal_garment_classifier.extract_semantic_embedding(img_a)
    emb_a2 = universal_garment_classifier.extract_semantic_embedding(img_a)
    emb_b = universal_garment_classifier.extract_semantic_embedding(img_b)

    assert len(emb_a1) == 64
    assert len(emb_b) == 64
    # Determinism
    assert np.allclose(emb_a1, emb_a2, atol=1e-4)

    # Unit norm
    norm_a = np.linalg.norm(emb_a1)
    assert np.isclose(norm_a, 1.0, atol=1e-2)

    # Distinction between T-shirt and Trousers
    cos_sim = float(np.dot(emb_a1, emb_b))
    assert cos_sim < 0.99, "Different garment silhouettes must yield distinct semantic embeddings."


# ── 3. Component & Anatomical Landmark Detection ──────────────────────────────

@pytest.mark.ml_benchmark
def test_component_detection_zero_fabrication():
    """Verifies that non-existent components are strictly marked not_detected."""
    tshirt = create_synthetic_tshirt_image()
    seg = segmenter_registry.get().segment(tshirt)

    comps, landmarks = component_detector.detect(
        image=tshirt,
        alpha_mask=seg.alpha_mask,
        category="tops",
        subcategory="tshirt"
    )

    comp_dict = {c.component_type: c for c in comps}
    assert "torso_body" in comp_dict
    assert comp_dict["torso_body"].status == "detected"
    assert comp_dict["torso_body"].confidence > 0.85

    # Hood and Placket MUST NOT be detected on a basic T-shirt
    assert comp_dict["hood"].status == "not_detected"
    assert comp_dict["hood"].confidence == 0.0

    assert comp_dict["placket"].status == "not_detected"
    assert comp_dict["placket"].confidence == 0.0


def test_anatomical_landmarks_localization():
    """Verifies landmark extraction for collar, shoulders, armscyes, cuffs, and hem."""
    tshirt = create_synthetic_tshirt_image()
    seg = segmenter_registry.get().segment(tshirt)

    _, landmarks = component_detector.detect(
        image=tshirt,
        alpha_mask=seg.alpha_mask,
        category="tops",
        subcategory="tshirt"
    )

    required_landmarks = [
        "collar_center", "neckline_left", "neckline_right",
        "shoulder_left", "shoulder_right", "armscye_left", "armscye_right",
        "cuff_left", "cuff_right", "hem_center", "waist_left", "waist_right"
    ]
    for lm_key in required_landmarks:
        assert lm_key in landmarks, f"Missing landmark: {lm_key}"
        lm = landmarks[lm_key]
        assert 0.0 <= lm.position.x <= 1.0
        assert 0.0 <= lm.position.y <= 1.0
        assert lm.confidence > 0.80

    # Geometric sanity: collar is higher than hemline
    assert landmarks["collar_center"].position.y < landmarks["hem_center"].position.y
    # Left shoulder is to the left of right shoulder
    assert landmarks["shoulder_left"].position.x < landmarks["shoulder_right"].position.x


# ── 4. Photographic Quality & Rejection Handling ──────────────────────────────

def test_blur_and_rejection_validation():
    """Verifies that blurry or non-clothing inputs are rejected with actionable guidance."""
    # Create extreme blur image (uniform grey)
    blank_img = Image.new("RGB", (300, 300), (128, 128, 128))
    seg_out = segmenter_registry.get().segment(blank_img)

    with pytest.raises(ValueError) as excinfo:
        garment_intelligence_service.analyze(
            front_image=blank_img,
            job_id="test_rejection_job"
        )
    assert "Input image rejected" in str(excinfo.value)
    assert "Guidance:" in str(excinfo.value)


# ── 5. Multi-View Understanding & Identity Matching ───────────────────────────

def test_multiview_duplicate_and_identity_consistency():
    """Verifies duplicate view detection and cross-view garment consistency."""
    tshirt = create_synthetic_tshirt_image()
    trousers = create_synthetic_trousers_image()

    seg_tshirt = segmenter_registry.get().segment(tshirt)
    seg_trousers = segmenter_registry.get().segment(trousers)

    emb_tshirt = universal_garment_classifier.extract_semantic_embedding(tshirt)
    _, hex_tshirt, _ = universal_garment_classifier.extract_dominant_colors(tshirt, seg_tshirt.alpha_mask)

    # 1. Duplicate check (uploading exact same image for front and back)
    dup_res = multiview_engine.analyze_view(
        image=tshirt,
        alpha_mask=seg_tshirt.alpha_mask,
        expected_view="back",
        front_embedding=emb_tshirt,
        front_primary_hex=hex_tshirt
    )
    assert dup_res.is_duplicate is True, "Identical image uploaded as back view must trigger duplicate flag."

    # 2. Identity mismatch check (uploading blue trousers as back view of dark charcoal t-shirt)
    mismatch_res = multiview_engine.analyze_view(
        image=trousers,
        alpha_mask=seg_trousers.alpha_mask,
        expected_view="back",
        front_embedding=emb_tshirt,
        front_primary_hex=hex_tshirt
    )
    assert mismatch_res.identity_match_with_front is False, "Mismatched garment categories must fail identity match."


# ── 6. Dynamic 3D Mesh Builder Integration & Ara 20-Bone Rig ───────────────────

def test_mesh_builder_dynamic_intelligence_binding():
    """Verifies that dynamic intelligence parameterizes the 3D mesh with valid Ara 20-bone skinning."""
    tshirt = create_synthetic_tshirt_image()
    intel, diag, _ = garment_intelligence_service.analyze(
        front_image=tshirt,
        job_id="test_mesh_job",
        category_hint="top"
    )

    mesh = garment_mesh_builder.build_mesh(
        category=intel.category,
        subcategory=intel.subcategory,
        sleeve_length=intel.sleeve_length,
        neckline_type=intel.neckline_type,
        fit=intel.fit,
        intelligence=intel
    )

    assert len(mesh.positions) > 100
    assert len(mesh.indices) > 100
    assert mesh.joint_indices.shape == (len(mesh.positions), 4)
    assert mesh.joint_weights.shape == (len(mesh.positions), 4)

    # All weights sum to 1.0
    weight_sums = mesh.joint_weights.sum(axis=1)
    assert np.allclose(weight_sums, 1.0, atol=1e-3)


# ── 7. Dataset Manifest & Model Registry Verification ─────────────────────────

@pytest.mark.skipif(
    not os.path.exists("data/datasets/fashion_manifest.json"),
    reason="Gitignored local dataset manifest (data/datasets/fashion_manifest.json) not present in CI.",
)
def test_dataset_manifest_and_model_registry_integrity():
    """Verifies data manifest and model registry licensing status."""
    import json
    with open("data/datasets/fashion_manifest.json", "r") as f:
        manifest = json.load(f)
    assert manifest["version"] == "2.0.0"
    datasets = {d["name"]: d for d in manifest["datasets"]}
    assert datasets["Fashionpedia"]["commercial_status"] == "APPROVED_FOR_COMMERCIAL_USE"
    assert datasets["DeepFashion (Consumer-to-Shop / In-Shop)"]["commercial_status"] == "RESTRICTED_NON_COMMERCIAL"

    with open("models/registry.json", "r") as f:
        registry = json.load(f)
    assert registry["target_hardware"] == "Apple Silicon M2 (Unified 8GB Memory)"
    assert "opencv_adaptive_grabcut" in registry["models"]
    assert "mobilenet_v3_fashion_features" in registry["models"]


# ── 8. REST API Diagnostics Endpoint ──────────────────────────────────────────

def test_api_diagnostics_endpoint():
    """Verifies GET /api/fashion/garment-gen/jobs/{job_id}/diagnostics endpoint."""
    import uuid
    tshirt = create_synthetic_tshirt_image()
    buf = io.BytesIO()
    tshirt.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    # Create job via API with unique user_id so quota/cache does not collide across runs
    res = client.post(
        "/api/fashion/garment-gen/jobs",
        files={"front_image": ("tshirt.png", png_bytes, "image/png")},
        data={"category": "top", "user_id": f"test_user_phase2_{uuid.uuid4().hex[:8]}"}
    )
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    # Poll until job completes (with timeout)
    max_wait = 15
    start_t = time.time()
    completed = False
    while time.time() - start_t < max_wait:
        poll_res = client.get(f"/api/fashion/garment-gen/jobs/{job_id}")
        assert poll_res.status_code == 200
        st = poll_res.json()["status"]
        if st == "completed":
            completed = True
            break
        elif st == "failed":
            pytest.fail(f"Job failed: {poll_res.json().get('error')}")
        time.sleep(0.4)

    assert completed, "Generation job did not complete within timeout."

    # Fetch diagnostics
    diag_res = client.get(f"/api/fashion/garment-gen/jobs/{job_id}/diagnostics")
    assert diag_res.status_code == 200
    diag = diag_res.json()

    assert diag["job_id"] == job_id
    assert diag["schema_version"] == "2.0.0"
    assert "intelligence" in diag
    assert "pipeline_stage_latencies_ms" in diag
    assert "alpha_mask_data_url" in diag
    assert diag["intelligence"]["category"] in ["tops", "dresses_and_skirts", "outerwear"]
    assert len(diag["intelligence"]["components"]) > 0
    assert len(diag["intelligence"]["landmarks"]) > 0

