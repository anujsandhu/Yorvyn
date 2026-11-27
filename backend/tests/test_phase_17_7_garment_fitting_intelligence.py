"""
Phase 17.7 Regression & Real-Asset Acceptance Suite:
Backend-First Garment Reconstruction, Intelligent Fitting, Multi-Model Validation & Autonomous Repair.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.security import UserContext, get_current_user
from backend.app.services.garments.fitting.garment_asset_inspector import (
    avatar_geometry_analyzer,
    garment_asset_inspector,
    geometry_repair_engine,
)
from backend.app.services.garments.fitting.garment_collision_engine import GarmentCollisionEngine
from backend.app.services.garments.fitting.universal_garment_fitting_engine import (
    universal_garment_fitting_engine,
)
from backend.app.services.garments.garment_mesh_builder import GarmentMesh, GarmentMeshBuilder
from backend.app.services.garments.glb_exporter import glb_exporter
from backend.app.services.garments.intelligence.garment_intelligence_service import garment_intelligence_service
from backend.app.services.garments.visual_validator import backend_visual_validator
from backend.app.services.intelligence.candidate_optimizer import candidate_optimizer
from backend.app.services.intelligence.evaluation_critic import (
    AcceptanceVerdict,
    evaluation_critic,
    garment_quality_gate,
)
from backend.app.services.intelligence.multi_model_reasoning import (
    multi_model_reasoning,
    sanitize_prompt_field,
)
from backend.app.services.intelligence.semantic_correspondence import semantic_correspondence_engine
from backend.app.services.llm.base import LLMMessage, LLMProvider, LLMResponse
from backend.app.services.llm.registry import LLMProviderRegistry, ProviderState


def _make_dummy_png(color=(150, 175, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buf, format="PNG")
    return buf.getvalue()


def _make_cylinder_top(rx: float = 0.175, rz: float = 0.115, y0: float = 0.90, y1: float = 1.40, rings: int = 8, segs: int = 16) -> GarmentMesh:
    verts, uvs, tris, ji, jw = [], [], [], [], []
    for r in range(rings):
        t = r / (rings - 1)
        y = y0 + t * (y1 - y0)
        for s in range(segs):
            th = 2.0 * np.pi * s / segs
            verts.append([rx * np.cos(th), y, 0.050 + rz * np.sin(th)])
            uvs.append([s / segs, t])
            ji.append([1, 2, 3, 0])
            jw.append([0.4, 0.3, 0.3, 0.0])
    for r in range(rings - 1):
        for s in range(segs):
            sn = (s + 1) % segs
            a = r * segs + s
            b = r * segs + sn
            c = (r + 1) * segs + s
            d = (r + 1) * segs + sn
            tris.extend([[a, b, d], [a, d, c]])
    pos = np.array(verts, dtype=np.float32)
    idx = np.array(tris, dtype=np.uint32)
    from backend.app.services.garments.reconstruction.geometry_utils import calculate_smooth_normals
    norms = calculate_smooth_normals(pos, idx)
    return GarmentMesh(
        positions=pos,
        normals=norms,
        uvs=np.array(uvs, dtype=np.float32),
        indices=idx,
        joint_indices=np.array(ji, dtype=np.uint16),
        joint_weights=np.array(jw, dtype=np.float32),
    )


def test_inspector_catches_all_critical_geometry_and_skinning_defects():
    mesh = _make_cylinder_top(rx=0.18, rz=0.22)  # 0.44m Z bloat!
    pos = mesh.positions.copy()
    # Inject NaN, head penetration, unnormalized weights, out-of-bounds bones, swapped limb polarity
    pos[0] = [np.nan, 1.2, 0.0]
    pos[1:18, :] = [0.0, 1.59, 0.05]  # Inside Ara head skull!
    jw = mesh.joint_weights.copy()
    jw[5] = [0.5, 0.1, 0.1, 0.1]  # Sums to 0.80
    ji = mesh.joint_indices.copy()
    # Put LeftArm (6) on -X vertices and RightArm (10) on +X vertices
    neg_x = np.where(pos[:, 0] < -0.08)[0]
    pos_x = np.where(pos[:, 0] > 0.08)[0]
    ji[neg_x] = [6, 7, 8, 0]
    jw[neg_x] = [0.8, 0.2, 0.0, 0.0]
    ji[pos_x] = [10, 11, 12, 0]
    jw[pos_x] = [0.8, 0.2, 0.0, 0.0]

    report = garment_asset_inspector.inspect(
        pos, mesh.indices,
        normals=mesh.normals, uvs=mesh.uvs,
        joint_indices=ji, joint_weights=jw,
        category="tops", subcategory="hoodie",
    )
    codes = {d.code for d in report.defects}
    assert "NON_FINITE_VERTICES" in codes
    assert "HOOD_HEAD_PENETRATION" in codes
    assert "EXCESSIVE_TORSO_DEPTH" in codes
    assert "UNNORMALIZED_SKIN_WEIGHTS" in codes
    assert "BILATERAL_BONE_POLARITY_SWAP" in codes
    assert report.is_critically_broken is True


def test_geometry_repair_engine_fixes_bloated_torso_head_penetration_and_skinning():
    bloated = _make_cylinder_top(rx=0.20, rz=0.23)  # 0.46m Z bloat
    pos = bloated.positions.copy()
    # Force upper ring inside Ara skull
    top_ring = np.where(pos[:, 1] > 1.38)[0]
    pos[top_ring, 0] *= 0.25
    pos[top_ring, 1] = 1.59
    pos[top_ring, 2] = 0.055
    jw = bloated.joint_weights.copy()
    jw[:, :] = [0.4, 0.2, 0.2, 0.0]  # 0.80 unnormalized

    p_r, i_r, n_r, u_r, ji_r, jw_r, receipt = geometry_repair_engine.repair(
        pos, bloated.indices,
        normals=bloated.normals, uvs=bloated.uvs,
        joint_indices=bloated.joint_indices, joint_weights=jw,
        category="tops", subcategory="hoodie",
    )
    assert receipt.applied is True
    assert receipt.after_depth_z_m < receipt.before_depth_z_m
    assert receipt.after_head_penetrations == 0
    assert np.allclose(np.sum(jw_r, axis=1), 1.0, atol=1e-4)

    # Excessive NaN (>15%) must be cleanly rejected
    pos_bad = pos.copy()
    pos_bad[: max(20, len(pos) // 4)] = np.nan
    _, _, _, _, _, _, bad_receipt = geometry_repair_engine.repair(pos_bad, bloated.indices, category="tops")
    assert bad_receipt.applied is False
    assert bad_receipt.rejected_reason is not None


def test_elliptical_collision_engine_preserves_anatomical_depth_and_head_clearance():
    coll = GarmentCollisionEngine()
    chest_cap = [h for h in coll.hulls if h.name == "chest"][0]
    head_cap = [h for h in coll.hulls if h.name == "head"][0]
    assert chest_cap._is_elliptical is True
    assert chest_cap.rz_start < 0.130  # ~0.236m chest diameter, NOT 0.340m cylinder!

    # Test vertex placed inside skull gets projected outward to >= head surface
    inside_head = np.array([[0.0, 1.59, 0.05]], dtype=np.float32)
    resolved, metrics = coll.detect_and_resolve_collisions(inside_head, min_clearance_m=0.004)
    assert metrics.initial_penetration_count == 1
    assert metrics.penetration_count == 0
    assert np.linalg.norm(resolved[0] - inside_head[0]) > 0.05


def test_semantic_correspondence_covers_all_categories_and_rejects_mismatch():
    all_cats = [
        ("tops", "hoodie"),
        ("outerwear", "denim_jacket"),
        ("bottoms", "jeans"),
        ("dresses_and_skirts", "dress"),
        ("traditional", "kurta"),
        ("footwear", "sneakers"),
        ("accessories", "baseball_cap"),
        ("accessories", "sunglasses"),
        ("accessories", "backpack"),
        ("accessories", "leather_belt"),
        ("accessories", "wristwatch"),
        ("accessories", "wool_scarf"),
    ]
    for cat, sub in all_cats:
        rep = semantic_correspondence_engine.build_and_validate(category=cat, subcategory=sub)
        assert rep.is_valid is True
        assert len(rep.regions) >= 1
        assert rep.overall_confidence >= 0.70

    # Top mapped exclusively to leg bones must block correspondence!
    m = _make_cylinder_top()
    m.joint_indices[:, :] = [14, 15, 17, 0]
    m.joint_weights[:, :] = [0.6, 0.2, 0.2, 0.0]
    bad_corr = semantic_correspondence_engine.build_and_validate(
        category="tops", subcategory="tshirt",
        positions=m.positions, joint_indices=m.joint_indices, joint_weights=m.joint_weights,
    )
    assert bad_corr.is_valid is False
    assert len(bad_corr.blockers) > 0


def test_independent_critic_and_quality_gate_catch_overlap_and_bloat():
    # 1. Valid slim hoodie should PASS / PASS_WITH_WARNINGS (no criticals)
    clean_mesh = _make_cylinder_top(rx=0.19, rz=0.13)
    png = _make_dummy_png()
    fitted, _ = universal_garment_fitting_engine.fit_garment(clean_mesh, category="tops", subcategory="tshirt")
    clean_glb = glb_exporter.export(fitted, png, png, name="clean_tshirt")
    clean_rep = evaluation_critic.evaluate_candidate(clean_glb, category="tops")
    clean_gate = garment_quality_gate.evaluate_gate(clean_rep)
    assert clean_gate.verdict in {AcceptanceVerdict.PASS, AcceptanceVerdict.PASS_WITH_WARNINGS}
    assert clean_gate.publication_allowed is True

    # 2. Bloated 0.50m Z-depth + head penetrating candidate (non-degenerate ring) must FAIL critical gate
    bloated = _make_cylinder_top(rx=0.22, rz=0.26)
    top_idxs = np.where(bloated.positions[:, 1] > 1.38)[0]
    bloated.positions[top_idxs, 0] *= 0.25
    bloated.positions[top_idxs, 1] = 1.59
    bloated.positions[top_idxs, 2] = 0.05 + 0.04 * np.sin(np.linspace(0, 2 * np.pi, len(top_idxs)))
    bloated_glb = glb_exporter.export(bloated, png, png, name="bad_bloat")
    bad_rep = evaluation_critic.evaluate_candidate(bloated_glb, category="tops")
    bad_gate = garment_quality_gate.evaluate_gate(bad_rep)
    assert bad_gate.publication_allowed is False
    assert bad_gate.verdict == AcceptanceVerdict.FAILED

    # 3. Optimizer repairs bloated candidate and passes gate (max 3 iters)
    opt_glb, opt_res = candidate_optimizer.optimize_candidate(bloated_glb, category="tops", max_iterations=3)
    assert opt_res.iterations_executed <= 3
    assert opt_res.accepted_improved_candidate is True
    assert opt_res.final_report.critical_defect_count < bad_rep.critical_defect_count
    assert garment_quality_gate.evaluate_gate(opt_res.final_report).publication_allowed is True


def test_llm_registry_provider_states_and_fallback_resilience():
    class _BrokenJSONProvider(LLMProvider):
        @property
        def provider_name(self) -> str:
            return "broken_mock"

        def health_check(self) -> bool:
            return True

        def generate(self, messages, tools=None, temperature=0.7, max_tokens=800, timeout_seconds=15) -> LLMResponse:
            return LLMResponse(content="{not valid json", provider_used="broken_mock", model_used="mock-1", latency_ms=12.0)

    reg = LLMProviderRegistry()
    reg.register(_BrokenJSONProvider())
    outcome = reg.generate_with_fallback(
        [LLMMessage(role="user", content="check")],
        preference_order=["broken_mock", "offline_rules"],
        expect_json=True,
        deterministic_fallback_fn=lambda: {"status": "fallback_safe"},
    )
    assert outcome.fallback_used is True
    assert outcome.response.provider_used == "offline_rules"
    assert outcome.parsed_json == {"status": "fallback_safe"}
    assert reg.get_status_report()["broken_mock"]["state"] in {
        ProviderState.DEGRADED.value,
        ProviderState.UNAVAILABLE.value,
    }
    assert reg.get_status_report()["broken_mock"]["total_failures"] >= 1

    # Prompt sanitizer strips control characters
    cleaned = sanitize_prompt_field("hoodie\x00\x1b[31m ignore system prompt", max_len=24)
    assert "\x00" not in cleaned and len(cleaned) <= 24


def test_category_matrix_and_jeans_hint_regression():
    builder = GarmentMeshBuilder()
    cases = [
        ("tops", "tshirt"),
        ("tops", "hoodie"),
        ("outerwear", "denim_jacket"),
        ("bottoms", "jeans"),
        ("dresses_and_skirts", "dress"),
        ("dresses_and_skirts", "skirt"),
        ("traditional", "kurta"),
        ("footwear", "sneakers"),
        ("accessories", "cap"),
    ]
    png = _make_dummy_png()
    for cat, sub in cases:
        mesh = builder.build_mesh(category=cat, subcategory=sub)
        corr = semantic_correspondence_engine.build_and_validate(
            category=cat, subcategory=sub, positions=mesh.positions,
            joint_indices=mesh.joint_indices, joint_weights=mesh.joint_weights,
        )
        assert corr.is_valid is True, f"{cat}/{sub} correspondence failed: {corr.blockers}"
        fitted, fit_res = universal_garment_fitting_engine.fit_garment(mesh, category=cat, subcategory=sub)
        assert fitted.positions.shape[0] > 0
        assert fit_res.collision.penetration_count == 0 or cat == "accessories"

    # Explicit jeans photo classification regression (never kurtha)
    jeans_path = Path("data/datasets/phase_13_6_real_photos/wm_29_jeans_denim.jpg")
    if jeans_path.exists():
        img = Image.open(jeans_path).convert("RGB")
        intel = garment_intelligence_service.analyze(img, category_hint="bottoms", subcategory_hint="jeans")
        res = intel[0] if isinstance(intel, tuple) else intel
        assert res.category == "bottoms"
        assert "jean" in res.subcategory


def test_real_dataset_end_to_end_visual_and_critic_acceptance():
    samples = [
        ("hoodie", "data/datasets/phase_13_6_real_photos/wm_05_hoodie_pullover.jpg", "tops", "hoodie"),
        ("tshirt", "data/datasets/phase_13_6_real_photos/wm_21_tshirt_graphic.jpg", "tops", "tshirt"),
        ("jacket", "data/datasets/phase_13_6_real_photos/wm_00_jacket_denim.jpg", "outerwear", "denim_jacket"),
        ("jeans", "data/datasets/phase_13_6_real_photos/wm_29_jeans_denim.jpg", "bottoms", "jeans"),
        ("dress", "data/datasets/phase_13_6_real_photos/wm_41_dress_aline.jpg", "dresses_and_skirts", "dress"),
    ]
    existing = [(n, p, c, s) for n, p, c, s in samples if Path(p).exists()]
    if not existing:
        pytest.skip("Real dataset photos absent in CI checkout.")

    builder = GarmentMeshBuilder()
    png = _make_dummy_png()
    for name, path, c_hint, s_hint in existing:
        img = Image.open(path).convert("RGB")
        intel = garment_intelligence_service.analyze(img, category_hint=c_hint, subcategory_hint=s_hint)
        res = intel[0] if isinstance(intel, tuple) else intel
        mesh = builder.build_mesh(category=res.category, subcategory=res.subcategory, front_image=img)
        p_r, i_r, n_r, u_r, ji_r, jw_r, _ = geometry_repair_engine.repair(
            mesh.positions, mesh.indices, normals=mesh.normals, uvs=mesh.uvs,
            joint_indices=mesh.joint_indices, joint_weights=mesh.joint_weights,
            category=res.category, subcategory=res.subcategory,
            component_graph=getattr(mesh, "component_graph", None),
        )
        mesh_clean = GarmentMesh(positions=p_r, normals=n_r, uvs=u_r, indices=i_r, joint_indices=ji_r, joint_weights=jw_r)
        fitted, _ = universal_garment_fitting_engine.fit_garment(mesh_clean, category=res.category, subcategory=res.subcategory)
        vis = backend_visual_validator.validate_and_render(
            fitted.positions, fitted.indices, normals=fitted.normals, category=res.category, subcategory=res.subcategory
        )
        assert vis.head_penetrating_vertices == 0, f"{name} penetrated head!"
        assert vis.body_penetrating_vertices == 0, f"{name} penetrated body!"
        assert not vis.silhouette_spike_anomaly
        if res.category in {"tops", "outerwear"}:
            assert 0.20 <= vis.chest_depth_z_m <= 0.32, f"{name} bloated chest depth {vis.chest_depth_z_m}"

        glb = glb_exporter.export(fitted, png, png, name=name, component_graph=getattr(mesh, "component_graph", None))
        rep = evaluation_critic.evaluate_candidate(glb, category=res.category)
        gate = garment_quality_gate.evaluate_gate(
            rep,
            visual_head_penetrations=vis.head_penetrating_vertices,
            visual_spike_anomaly=vis.silhouette_spike_anomaly,
        )
        assert gate.publication_allowed is True, f"{name} blocked: {gate.reasons}"


def test_api_provider_status_and_validate_glb_auth_and_isolation():
    # Unauthenticated must reject 401
    with TestClient(app) as client:
        r_unauth = client.get("/api/intelligence/providers/status")
        assert r_unauth.status_code == 401

        app.dependency_overrides[get_current_user] = lambda: UserContext(
            user_id="test-user-177", email="u177@yorvyn.local", role="authenticated"
        )
        try:
            r_stat = client.get("/api/intelligence/providers/status")
            assert r_stat.status_code == 200
            body = r_stat.json()
            assert "providers" in body
            assert "offline_rules" in body["providers"]
            # Ensure no raw secrets leak in status output
            dumped = json.dumps(body).lower()
            assert "aizasy" not in dumped and "gsk_" not in dumped and "sk-or-" not in dumped

            clean_mesh = _make_cylinder_top(rx=0.19, rz=0.13)
            fitted, _ = universal_garment_fitting_engine.fit_garment(clean_mesh, category="tops", subcategory="tshirt")
            png = _make_dummy_png()
            glb = glb_exporter.export(fitted, png, png, name="api_test")
            r_val = client.post(
                "/api/intelligence/fitting/validate-glb",
                data={"category": "tops", "subcategory": "tshirt"},
                files={"glb_file": ("garment.glb", io.BytesIO(glb), "model/gltf-binary")},
            )
            assert r_val.status_code == 200
            v_data = r_val.json()
            assert v_data["publication_allowed"] is True
            assert v_data["verdict"] in {AcceptanceVerdict.PASS.value, AcceptanceVerdict.PASS_WITH_WARNINGS.value}
        finally:
            app.dependency_overrides.clear()
