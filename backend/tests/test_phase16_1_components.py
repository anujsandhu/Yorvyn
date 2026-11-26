"""Deterministic Phase 16.1 verification suite for component taxonomy, localization, fusion, graph, and Stylist routing."""
from __future__ import annotations

import asyncio
import hashlib
import io
import os
from pathlib import Path
import threading
from types import SimpleNamespace
import uuid

import cv2
import numpy as np
from PIL import Image, ImageDraw
import pytest

from backend.app.api.conversational_garments import garment_router
from backend.app.services.ai.base import EvidenceStatus, ModelMetadata
from backend.app.services.ai.contracts import (
    AppearanceDetail,
    CanonicalGarmentSpecification,
    CanonicalGarmentSpecificationV2,
    ComponentAnalysisBundle,
    ComponentObservation,
    GarmentItemEvidence,
    GeometricEstimate,
    HandoffToReconstruction,
    ImageEvidenceRecord,
    ImageQualityAssessment,
    UncertaintyBreakdown,
)
from backend.app.services.ai.evaluation.component_evaluator import ComponentEvaluator
from backend.app.services.ai.multiview.fusion_engine import multi_view_fusion_engine
from backend.app.services.ai.multiview.view_classifier import GarmentViewType, view_classifier
from backend.app.services.intelligence.capability_registry import State, garment_capabilities
from backend.app.services.intelligence.component_evidence import (
    _COMPONENT_CACHE,
    analyze_garment_components,
    fuse_component_observations,
)
from backend.app.services.intelligence.component_taxonomy import (
    COMPONENT_TAXONOMY,
    TAXONOMY_VERSION,
    ComponentEvidenceStatus,
    DetectionState,
    GarmentFamily,
    ReconstructionDecision,
    VisibilityState,
    resolve_category_profile,
)
from backend.app.services.intelligence.garment_execution import ExecutionContext
from backend.app.services.intelligence.garment_structure_graph import build_garment_structure_graph


@pytest.fixture(autouse=True)
def fast_deterministic_vision(monkeypatch):
    """Force lightweight SegFormer-off/CLIP-off mode unless test explicitly exercises live cached models."""
    if os.getenv("YORVYN_TEST_LIVE_LOCAL_MODELS") != "1":
        monkeypatch.setenv("YORVYN_DISABLE_SEGFORMER", "1")
        monkeypatch.setenv("YORVYN_DISABLE_COMPONENT_CLIP", "1")
    yield


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _draw_upper_garment(
    *,
    size=(240, 240),
    zipper: bool = False,
    pocket: bool = False,
    hood: bool = False,
    sleeves: bool = True,
    cropped_top: bool = False,
) -> Image.Image:
    w, h = size
    img = Image.new("RGB", (w, h), (242, 242, 242))
    draw = ImageDraw.Draw(img)
    top_y = 0 if cropped_top else 38
    # Torso
    draw.rectangle([72, top_y, 168, 205], fill=(45, 70, 120), outline=(25, 40, 75), width=2)
    if sleeves:
        draw.polygon([(72, top_y + 6), (26, 115), (46, 130), (72, 72)], fill=(45, 70, 120), outline=(25, 40, 75))
        draw.polygon([(168, top_y + 6), (214, 115), (194, 130), (168, 72)], fill=(45, 70, 120), outline=(25, 40, 75))
    if hood and not cropped_top:
        draw.ellipse([90, 12, 150, 52], fill=(45, 70, 120), outline=(25, 40, 75), width=2)
    if zipper:
        draw.line([(120, top_y + 12), (120, 198)], fill=(215, 215, 215), width=3)
    if pocket:
        draw.rectangle([90, 145, 150, 185], fill=(38, 60, 105), outline=(220, 220, 220), width=2)
    return img


def _draw_trousers(size=(240, 240), pockets: bool = False) -> Image.Image:
    w, h = size
    img = Image.new("RGB", (w, h), (242, 242, 242))
    draw = ImageDraw.Draw(img)
    # Waistband + pelvis
    draw.rectangle([70, 28, 170, 92], fill=(55, 65, 85), outline=(25, 30, 40), width=2)
    # Bifurcated legs
    draw.rectangle([70, 92, 112, 215], fill=(55, 65, 85), outline=(25, 30, 40), width=2)
    draw.rectangle([128, 92, 170, 215], fill=(55, 65, 85), outline=(25, 30, 40), width=2)
    # Fly seam
    draw.line([(120, 32), (120, 82)], fill=(210, 210, 210), width=2)
    if pockets:
        draw.rectangle([78, 56, 108, 86], outline=(210, 210, 210), width=2)
        draw.rectangle([132, 56, 162, 86], outline=(210, 210, 210), width=2)
    return img


def _draw_dress(size=(240, 240)) -> Image.Image:
    w, h = size
    img = Image.new("RGB", (w, h), (242, 242, 242))
    draw = ImageDraw.Draw(img)
    # Bodice
    draw.rectangle([86, 30, 154, 100], fill=(150, 45, 65), outline=(90, 20, 35), width=2)
    # Flared skirt
    draw.polygon([(86, 100), (154, 100), (186, 212), (54, 212)], fill=(150, 45, 65), outline=(90, 20, 35))
    return img


def test_taxonomy_version_families_and_profiles():
    assert TAXONOMY_VERSION == "16.1.0"
    families = {entry.family for entry in COMPONENT_TAXONOMY.values()}
    assert {GarmentFamily.UPPER_BODY, GarmentFamily.LOWER_BODY, GarmentFamily.DRESS_ONE_PIECE} <= families
    for required in ("front_body", "back_body", "left_sleeve", "right_sleeve", "cuff", "collar", "lapel", "zipper",
                     "button_placket", "chest_pocket", "hem", "lower_waistband", "belt_loops", "fly", "left_leg",
                     "right_leg", "inseam", "outseam", "crotch_seam", "leg_opening", "bodice", "waistline", "skirt"):
        assert required in COMPONENT_TAXONOMY

    jacket_prof = resolve_category_profile("jacket", "denim_jacket")
    hoodie_prof = resolve_category_profile("hoodie", "pullover_hoodie")
    pants_prof = resolve_category_profile("bottoms", "chinos")
    dress_prof = resolve_category_profile("dress", "a_line_dress")
    assert "hood" in hoodie_prof.required_components
    assert "fly" in pants_prof.expected_components and "hood" not in pants_prof.expected_components
    assert "bodice" in dress_prof.required_components and "skirt" in dress_prof.required_components
    assert jacket_prof.category == "jacket"


def test_component_provenance_visibility_unknown_vs_absent_and_uncertainty():
    front_bytes = _png_bytes(_draw_upper_garment(zipper=True, hood=True, sleeves=True))
    expected_hash = hashlib.sha256(front_bytes).hexdigest()
    bundle = analyze_garment_components(
        images_input=[("front_img", front_bytes, "front")],
        garment_id="g_jacket_01",
        category="jacket",
        subcategory="zip_jacket",
    )
    assert isinstance(bundle, ComponentAnalysisBundle)
    assert bundle.fused_components["front_body"].detection_state == DetectionState.DETECTED
    assert bundle.fused_components["front_body"].evidence_status == ComponentEvidenceStatus.OBSERVED
    assert bundle.fused_components["front_body"].source_image_ids == ["front_img"]
    assert bundle.fused_components["front_body"].source_image_hashes == [expected_hash]
    assert bundle.fused_components["front_body"].localized_bbox is not None
    # Front photo MUST NOT mark back_body as absent; it must remain NOT_OBSERVED.
    back = bundle.fused_components["back_body"]
    assert back.evidence_status == ComponentEvidenceStatus.NOT_OBSERVED
    assert back.detection_state == DetectionState.NOT_DETECTED
    assert back.confidence is None
    assert back.downstream_decision == ReconstructionDecision.DO_NOT_INFER
    # Separate confidence, calibrated probability, and uncertainty completeness
    fb = bundle.fused_components["front_body"]
    assert fb.confidence is not None and fb.calibrated_probability is not None
    assert 0.0 < fb.uncertainty.total_uncertainty < 1.0
    assert "back" in " ".join(bundle.handoff.clarification_prompts).lower()


def test_lower_body_and_dress_profiles_do_not_invent_hidden_parts():
    trousers_bytes = _png_bytes(_draw_trousers())
    t_bundle = analyze_garment_components([("pants_f", trousers_bytes, "front")], "g_pants", "bottoms", "chinos")
    assert t_bundle.fused_components["left_leg"].detection_state == DetectionState.DETECTED
    assert t_bundle.fused_components["right_leg"].detection_state == DetectionState.DETECTED
    assert t_bundle.fused_components["lower_waistband"].detection_state == DetectionState.DETECTED
    assert t_bundle.fused_components["crotch_seam"].detection_state == DetectionState.DETECTED
    # Back pocket CANNOT be declared absent from front view!
    bp = t_bundle.fused_components["back_pocket"]
    assert bp.detection_state != DetectionState.ABSENT_VERIFIED
    assert bp.evidence_status == ComponentEvidenceStatus.NOT_OBSERVED

    dress_bytes = _png_bytes(_draw_dress())
    d_bundle = analyze_garment_components([("dress_f", dress_bytes, "front")], "g_dress", "dress", "a_line_dress")
    assert d_bundle.fused_components["bodice"].detection_state == DetectionState.DETECTED
    assert d_bundle.fused_components["skirt"].detection_state == DetectionState.DETECTED
    assert d_bundle.fused_components["dress_closures"].evidence_status == ComponentEvidenceStatus.NOT_OBSERVED


def test_occlusion_out_of_frame_and_low_image_quality_visibility():
    # Out-of-frame cropped top
    cropped = _png_bytes(_draw_upper_garment(cropped_top=True))
    crop_bundle = analyze_garment_components([("top_crop", cropped, "front")], "g_crop", "jacket", "denim_jacket")
    assert any(
        obs.visibility_state == VisibilityState.OUT_OF_FRAME
        for obs in crop_bundle.observations
    )

    # Very blurry dark low-quality image
    dark_blur = Image.new("RGB", (140, 140), (14, 14, 14))
    arr = np.array(dark_blur)
    arr[20:120, 30:110] = 28
    blur_bytes = _png_bytes(Image.fromarray(cv2.GaussianBlur(arr, (15, 15), 5)))
    blur_bundle = analyze_garment_components([("low_q", blur_bytes, "front")], "g_blur", "tops", "tshirt")
    # Unusable / low-quality image never returns high-confidence SAFE_TO_USE
    assert not blur_bundle.handoff.safe_components


def test_occlusion_via_segformer_occluder_mask_monkeypatched(monkeypatch):
    from backend.app.services.intelligence import component_evidence as ce
    front_bytes = _png_bytes(_draw_upper_garment(hood=True, sleeves=True))
    h, w = 240, 240
    fg = np.zeros((h, w), dtype=np.uint8)
    fg[38:205, 72:168] = 255
    occ = np.zeros((h, w), dtype=np.uint8)
    occ[30:110, 60:180] = 255  # Cover neck/upper chest completely
    monkeypatch.setattr(ce, "_run_segformer_parsing", lambda img, cat: (fg, occ, {"backend": "test_occluder", "weights_loaded": True}))
    bundle = analyze_garment_components([("occ_front", front_bytes, "front")], "g_occ", "hoodie", "pullover_hoodie")
    hood_obs = [o for o in bundle.observations if o.component_id == "hood" or o.component_id == "neck_opening"]
    assert hood_obs and hood_obs[0].visibility_state in (VisibilityState.OCCLUDED, VisibilityState.PARTIALLY_VISIBLE)
    assert hood_obs[0].uncertainty.aleatoric_uncertainty >= 0.35


def test_multiview_fusion_contradiction_preservation_and_graph():
    front_zip = _png_bytes(_draw_upper_garment(zipper=True, hood=True))
    back_clean = _png_bytes(_draw_upper_garment(zipper=False, hood=True))
    bundle = analyze_garment_components(
        images_input=[("view_front", front_zip, "front"), ("view_back", back_clean, "back")],
        garment_id="g_mv_01",
        category="hoodie",
        subcategory="zip_hoodie",
    )
    assert bundle.fused_components["front_body"].detection_state == DetectionState.DETECTED
    assert bundle.fused_components["back_body"].detection_state == DetectionState.DETECTED
    assert bundle.fused_components["zipper"].detection_state == DetectionState.DETECTED
    assert bundle.fused_components["zipper"].downstream_decision in (
        ReconstructionDecision.SAFE_TO_USE,
        ReconstructionDecision.USE_WITH_UNCERTAINTY,
    )

    # Synthetic contradiction across views (zipper detected vs verified absent on same garment)
    h1 = hashlib.sha256(front_zip).hexdigest()
    h2 = hashlib.sha256(back_clean).hexdigest()
    views = [
        ImageEvidenceRecord(image_id="v1", image_hash=h1, view_type="front", usable=True),
        ImageEvidenceRecord(image_id="v2", image_hash=h2, view_type="three_quarter", usable=True),
    ]
    obs_pos = ComponentObservation(
        observation_id="o1", component_id="zipper", component_type="zipper", garment_id="g_conf",
        garment_category="jacket", source_image_id="v1", source_image_hash=h1, source_view="front",
        visibility_state=VisibilityState.FULLY_VISIBLE, detection_state=DetectionState.DETECTED,
        evidence_status=ComponentEvidenceStatus.OBSERVED, confidence=0.88, calibrated_probability=0.84,
        uncertainty=UncertaintyBreakdown(total_uncertainty=0.2),
    )
    obs_neg = ComponentObservation(
        observation_id="o2", component_id="zipper", component_type="zipper", garment_id="g_conf",
        garment_category="jacket", source_image_id="v2", source_image_hash=h2, source_view="three_quarter",
        visibility_state=VisibilityState.FULLY_VISIBLE, detection_state=DetectionState.ABSENT_VERIFIED,
        evidence_status=ComponentEvidenceStatus.OBSERVED, confidence=0.82, calibrated_probability=0.79,
        uncertainty=UncertaintyBreakdown(total_uncertainty=0.22),
    )
    fused = fuse_component_observations("g_conf", "jacket", "denim_jacket", [obs_pos, obs_neg], views)
    assert fused["zipper"].contradicted is True
    assert fused["zipper"].evidence_status == ComponentEvidenceStatus.CONTRADICTED
    assert len(fused["zipper"].observations) == 2
    assert fused["zipper"].downstream_decision == ReconstructionDecision.REQUIRE_MORE_EVIDENCE

    graph = build_garment_structure_graph("g_conf", "jacket", "denim_jacket", fused)
    assert graph.contradictions
    relations = {e.relation for e in graph.edges}
    assert {"SUPPORTED_BY_VIEW", "ATTACHED_TO", "SYMMETRIC_WITH"} <= relations


def test_duplicate_and_repeated_crop_do_not_count_as_independent_views(monkeypatch):
    base_img = _draw_upper_garment(size=(360, 360), zipper=True, pocket=True, hood=True)
    # Create an exact spatial crop of the lower pocket area from base_img
    crop_img = base_img.crop((100, 180, 260, 320))
    sim = view_classifier.detect_subcrop_similarity(crop_img, base_img)
    assert sim is not None and sim >= 0.88

    # Fusion engine marks crop_of_existing_view and counts_as_independent_view=False
    monkeypatch.setattr(multi_view_fusion_engine, "fuse_garment_views", multi_view_fusion_engine.fuse_garment_views)
    from backend.app.services.ai.orchestration import orchestrator
    fake_spec = CanonicalGarmentSpecification(
        garment_id="stub_crop",
        garment=GarmentItemEvidence(category="hoodie", subcategory="zip_hoodie", confidence=0.89, evidence_status=EvidenceStatus.INFERRED),
        components={},
        appearance=AppearanceDetail(primary_color="blue", palette_hex=["#2d4678"], pattern="solid", fabric_appearance="cotton", evidence_status=EvidenceStatus.INFERRED),
        orientation="front",
        quality=ImageQualityAssessment(image_usable=True, occlusion_detected=False, contrast_acceptable=True, ambiguity_notes=[]),
        geometry=GeometricEstimate(measurement_method="c", scale_assumptions="b", estimated_torso_aspect_ratio=1.1, sleeve_length_ratio=1.0, uncertainty_cm=2.0, evidence_status=EvidenceStatus.INFERRED),
        reconstruction_handoff=HandoffToReconstruction(target_dag_template="hoodie_construction", enable_hood_mesh=True, enable_pocket_mesh=True, pocket_type="kangaroo_pocket", closure_geometry="zipper", curved_hem=False, torso_fit_offset_cm=2.0, material_preset="cotton_pbr"),
        provenance_chain=[ModelMetadata(provider_name="local_cv", model_name="local_cv", is_local=True)],
        model_execution_provenance={},
    )
    monkeypatch.setattr(orchestrator.ai_orchestrator, "process_garment_image", lambda **kw: fake_spec)
    spec = multi_view_fusion_engine.fuse_garment_views(
        [("full.png", _png_bytes(base_img), "front"), ("crop.png", _png_bytes(crop_img), "back")],
        garment_id="g_crop_check",
    )
    assert len(spec.views) == 2
    assert spec.views[1].crop_of_image_id == "full.png"
    assert spec.views[1].duplicate_type == "crop_of_existing_view"
    assert spec.views[1].counts_as_independent_view is False
    # Even though user passed "back" hint on crop, it is NOT an independent rear view!
    assert spec.reconstruction_readiness.status == "PARTIAL"
    assert spec.validate_evidence_integrity() == []


def test_bbox_and_provenance_validation_rejects_fabricated_evidence():
    img = _png_bytes(_draw_upper_garment())
    h = hashlib.sha256(img).hexdigest()
    bad_spec = CanonicalGarmentSpecificationV2(
        garment_id="g_bad",
        garment=GarmentItemEvidence(category="jacket", subcategory="denim_jacket", confidence=0.9),
        views=[ImageEvidenceRecord(image_id="img1", image_hash=h, view_type="front", usable=True)],
        component_observations=[
            ComponentObservation(
                observation_id="bad_obs",
                component_id="collar",
                component_type="collar",
                garment_id="g_bad",
                garment_category="jacket",
                source_image_id="missing_img",
                source_image_hash="deadbeef",
                source_view="front",
                bbox=(0.9, 0.2, 0.4, 1.5),
            )
        ],
    )
    errs = bad_spec.validate_evidence_integrity()
    assert len(errs) >= 2


def test_evaluator_reports_empty_blocked_and_per_component_metrics():
    ev = ComponentEvaluator()
    empty = ev.evaluate_component_detections([], [])
    assert empty["evaluation_status"] == "NOT_EVALUATED_EMPTY_DATASET"

    gt = [
        {"collar": {"present": True, "bbox": (0.1, 0.3, 0.3, 0.7), "visibility": "FULLY_VISIBLE"},
         "back_pocket": {"present": True, "bbox": (0.5, 0.4, 0.7, 0.6), "visibility": "OCCLUDED"}},
    ]
    pred = [
        {"collar": {"present": True, "bbox": (0.12, 0.31, 0.29, 0.68), "visibility": "FULLY_VISIBLE", "confidence": 0.85},
         "back_pocket": {"present": False, "absent_verified": True, "visibility": "FULLY_VISIBLE", "confidence": 0.75}},
    ]
    res = ev.evaluate_component_detections(gt, pred, require_boxes=True, dataset_kind="synthetic")
    assert res["evaluation_status"] == "SYNTHETIC_SMOKE_ONLY"
    assert res["components"]["collar"]["f1"] == 1.0
    assert res["components"]["back_pocket"]["false_absence_rate"] == 1.0
    assert res["visibility_accuracy"] == 0.5


@pytest.mark.asyncio
async def test_router_capability_cache_concurrency_and_cancellation():
    assert garment_capabilities.get("components.identify").availability == State.VERIFIED
    _COMPONENT_CACHE.clear()
    img = _png_bytes(_draw_upper_garment(zipper=True, hood=True))
    h = hashlib.sha256(img).hexdigest()

    # Warm once, then verify concurrent cache hit + router execution
    first = analyze_garment_components([("f1", img, "front")], "g_c1", "hoodie", "zip_hoodie")
    assert first.cache_hits == 0

    ctx = ExecutionContext("owner_1", "sess_1", "turn_1")
    res_a, res_b = await asyncio.gather(
        garment_router.execute(ctx, "components.identify", [("f1", img, "front")], "g_c2", "hoodie", "zip_hoodie", refs=[h]),
        garment_router.execute(ctx, "components.identify", [("f2", img, "front")], "g_c3", "hoodie", "zip_hoodie", refs=[h]),
    )
    assert isinstance(res_a, ComponentAnalysisBundle) and isinstance(res_b, ComponentAnalysisBundle)
    assert res_a.cache_hits == 1 and res_b.cache_hits == 1
    assert all(op["status"] == "COMPLETED" and op["capability_id"] == "components.identify" for op in ctx.operations)

    # Cancellation check
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(TimeoutError):
        analyze_garment_components([("f1", img, "front")], "g_cancel", "hoodie", "zip_hoodie", cancel_event=cancel)


def test_garment_identity_isolation_and_stylist_clarification_flow(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.api import conversational_garments as cg
    from backend.app.core.security import UserContext

    # 1. Identity isolation on duplicate/conflicting component observation hashes
    img_a = _png_bytes(_draw_upper_garment(zipper=True))
    img_b = _png_bytes(_draw_upper_garment(pocket=True))
    bundle_a = analyze_garment_components([("a", img_a, "front")], "garment_alpha", "hoodie", "zip_hoodie")
    bundle_b = analyze_garment_components([("b", img_b, "front")], "garment_beta", "hoodie", "pullover_hoodie")
    assert all(o.garment_id == "garment_alpha" for o in bundle_a.observations)
    assert all(o.garment_id == "garment_beta" for o in bundle_b.observations)

    # 2. Stylist /garment-turns integration with ownership + component clarification
    app = FastAPI()
    app.include_router(cg.router)
    app.dependency_overrides[cg.get_current_user] = lambda: UserContext(user_id="user_16_1", email="u@test.local", role="authenticated")

    class FakePipeline:
        def incr(self, *a, **kw):
            return self
        def incrby(self, *a, **kw):
            return self
        def expire(self, *a, **kw):
            return self
        def xadd(self, *a, **kw):
            return self
        def execute(self):
            return [1, True]

    class FakeRedis:
        def pipeline(self):
            return FakePipeline()
        def lock(self, *a, **kw):
            return SimpleNamespace(acquire=lambda **kw: True, owned=lambda: True, release=lambda: None)

    monkeypatch.setattr(cg.garment_job_manager, "_redis_broker", SimpleNamespace(client=FakeRedis()))
    monkeypatch.setattr(cg.garment_job_manager._postgres_adapter, "save_garment_evidence_spec", lambda *a, **kw: None)
    monkeypatch.setattr(cg.supabase_repo, "get_ai_session", lambda sid, uid: {"id": sid, "user_id": "user_16_1", "status": "active"})
    monkeypatch.setattr(cg.supabase_repo, "get_message_by_request_id", lambda uid, rid: None)
    monkeypatch.setattr(cg.supabase_repo, "create_ai_message", lambda *a, **kw: {"id": "msg_1", "content": a[3], "metadata": kw.get("metadata", {})})

    async def fake_execute(ctx, cap, *args, **kwargs):
        if cap == "intent.plan":
            from backend.app.services.llm.garment_plan import GarmentPlan
            ctx.operations.append({"capability_id": cap, "status": "COMPLETED"})
            return GarmentPlan(action="identify"), {"decision": "EXECUTE_LOCAL", "provider": "local_rules", "reason": "ok"}
        if cap == "subject.select":
            ctx.operations.append({"capability_id": cap, "status": "COMPLETED"})
            return None, []
        if cap == "views.identify":
            ctx.operations.append({"capability_id": cap, "status": "COMPLETED"})
            return CanonicalGarmentSpecificationV2(
                garment_id="g_stylist_1",
                garment=GarmentItemEvidence(category="jacket", subcategory="denim_jacket", confidence=0.91),
                views=[ImageEvidenceRecord(image_id="front.png", image_hash=hashlib.sha256(img_a).hexdigest(), view_type="front", usable=True)],
                natural_language_explanation="Identified a denim jacket.",
            )
        if cap == "components.identify":
            ctx.operations.append({"capability_id": cap, "status": "COMPLETED"})
            return bundle_a
        raise AssertionError(f"Unexpected capability {cap}")

    monkeypatch.setattr(cg.garment_router, "execute", fake_execute)
    client = TestClient(app)
    res = client.post(
        f"/api/ai/sessions/{uuid.uuid4()}/garment-turns",
        data={"instruction": "Identify the components of this jacket", "request_id": str(uuid.uuid4())},
        files=[("images", ("front.png", img_a, "image/png"))],
    )
    assert res.status_code == 200
    body = res.json()
    ops = [op["capability_id"] for op in body["metadata"]["garment"]["intelligence_execution"]["operations"]]
    assert "components.identify" in ops
    assert "back" in body["content"].lower()
