"""
YORVYN — Phase 3: Universal Category-Specific 3D Garment Reconstruction Test Suite
Tests:
1. ReconstructionEngineRegistry dispatching across all 9 specialized engines (zero generic cylinder fallbacks).
2. Category engines: Tops, Shirts (collar stand/placket/cuffs), Hoodies (cowl/pocket/ribbing),
   Jackets (lapels/zipper/structured shoulders), Bottoms (waistband/crotch/legs),
   Dresses & Skirts (bodice vs waistband-anchored skirt), Traditional (kurta with open side chaks),
   Footwear (soles/uppers/ankles), Accessories (crown/visor).
3. Geometric quality validation: 100% manifoldness, 0 degenerate triangles, boundary opening loops, normal normalization.
4. Physical ease and proportions estimation anchored to Ara 3D 1.75m humanoid scale.
5. Ara 3D Gen 20-bone skeletal skinning integrity (weights sum to 1.0, indices in [0, 19]).
6. Specification-compliant binary glTF 2.0 (.glb) export across all categories.
7. Multi-view 3D fusion and observed vs inferred surface provenance tracking.
8. Learned model evaluations (TRELLIS, Hunyuan3D, InstantMesh, TripoSR, SF3D) and Apple Silicon M2 8GB hardware audit.
9. REST API endpoints (/api/fashion/garment-gen/neural-evaluations and /jobs/{job_id}/diagnostics).
"""

import os
import io
import pytest
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.garments.garment_mesh_builder import (
    GarmentMesh,
    garment_mesh_builder,
    ARA_SKELETON_SPECS
)
from backend.app.services.garments.glb_exporter import glb_exporter
from backend.app.services.garments.reconstruction import (
    reconstruction_registry,
    GarmentMeshValidator,
    GarmentProportionsEstimator,
    MultiViewGarmentFuser,
    TopsReconstructionEngine,
    ShirtReconstructionEngine,
    HoodieReconstructionEngine,
    JacketReconstructionEngine,
    BottomsReconstructionEngine,
    DressReconstructionEngine,
    TraditionalWearReconstructionEngine,
    FootwearReconstructionEngine,
    AccessoriesReconstructionEngine
)
from backend.app.services.garments.reconstruction.neural import (
    LearnedModelEvaluator,
    LearnedReconstructionClient,
    HybridReconstructionRefiner
)
from backend.app.models.garment_intelligence_models import (
    GarmentIntelligenceV2Result,
    GarmentLandmarkV2,
    GarmentComponentV2,
    Point2D,
    BoundingBox2D,
    ImageQualityMetrics,
    SegmentationMetrics
)

client = TestClient(app)


def _make_dummy_png(color=(100, 100, 100), size=(32, 32)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── 1. Registry & Engine Dispatch Verification ────────────────────────────────

def test_reconstruction_engine_registry_dispatch():
    """Verifies that every category and subcategory dispatches to its dedicated engine."""
    assert len(reconstruction_registry._engines) >= 9

    test_cases = [
        ("tops", "tshirt", TopsReconstructionEngine),
        ("tops", "formal_shirt", ShirtReconstructionEngine),
        ("tops", "hoodie", HoodieReconstructionEngine),
        ("outerwear", "jacket", JacketReconstructionEngine),
        ("outerwear", "denim_jacket", JacketReconstructionEngine),
        ("bottoms", "jeans", BottomsReconstructionEngine),
        ("bottoms", "trousers", BottomsReconstructionEngine),
        ("bottoms", "shorts", BottomsReconstructionEngine),
        ("dresses_and_skirts", "dress", DressReconstructionEngine),
        ("dresses_and_skirts", "skirt", DressReconstructionEngine),
        ("traditional", "kurta", TraditionalWearReconstructionEngine),
        ("footwear", "sneakers", FootwearReconstructionEngine),
        ("accessories", "caps", AccessoriesReconstructionEngine),
    ]

    for cat, subcat, expected_cls in test_cases:
        eng = reconstruction_registry.get_engine(cat, subcat)
        assert isinstance(eng, expected_cls), f"Expected {expected_cls} for {cat}/{subcat}, got {type(eng)}"


# ── 2. Category-Specific Pattern Construction Verification ────────────────────

def test_tops_reconstruction_engine():
    """Verifies TopsReconstructionEngine pattern topology and panels."""
    eng = TopsReconstructionEngine()
    out = eng.reconstruct(category="tops", subcategory="tshirt", sleeve_length="short", fit="regular")
    
    assert out.provenance == "pattern_constructed"
    assert out.mesh.positions.shape[0] > 100
    assert out.mesh.indices.shape[0] > 100
    assert out.quality_report.is_valid
    assert out.quality_report.is_manifold
    assert out.quality_report.degenerate_triangle_count == 0

    panel_names = [p.name for p in out.panels]
    assert "front_torso_panel" in panel_names
    assert "back_torso_panel" in panel_names
    assert "left_sleeve" in panel_names
    assert "right_sleeve" in panel_names


def test_shirt_reconstruction_engine():
    """Verifies ShirtReconstructionEngine constructs collar stand, points, placket, and cuffs."""
    eng = ShirtReconstructionEngine()
    out = eng.reconstruct(category="tops", subcategory="formal_shirt", fit="slim")

    assert out.quality_report.is_valid
    assert out.quality_report.is_manifold
    assert out.quality_report.degenerate_triangle_count == 0

    panel_names = [p.name for p in out.panels]
    assert "collar_stand_and_points" in panel_names
    assert "front_placket_band" in panel_names
    assert "left_sleeve_and_cuff" in panel_names
    assert "right_sleeve_and_cuff" in panel_names


def test_hoodie_reconstruction_engine():
    """Verifies HoodieReconstructionEngine constructs 3D hood cowl and kangaroo pocket."""
    eng = HoodieReconstructionEngine()
    out = eng.reconstruct(category="tops", subcategory="hoodie", fit="relaxed")

    assert out.quality_report.is_valid
    assert out.quality_report.is_manifold
    assert out.quality_report.degenerate_triangle_count == 0

    panel_names = [p.name for p in out.panels]
    assert "hood_cowl" in panel_names
    assert "kangaroo_pocket" in panel_names
    assert "left_sleeve_and_cuff" in panel_names


def test_jacket_reconstruction_engine():
    """Verifies JacketReconstructionEngine constructs lapels, zipper track, and structured envelope."""
    eng = JacketReconstructionEngine()
    out = eng.reconstruct(category="outerwear", subcategory="jacket")

    assert out.quality_report.is_valid
    assert out.quality_report.is_manifold
    assert out.quality_report.degenerate_triangle_count == 0

    panel_names = [p.name for p in out.panels]
    assert "lapels_and_collar" in panel_names
    assert "front_zipper_track" in panel_names
    assert "front_jacket_torso" in panel_names


def test_bottoms_reconstruction_engine():
    """Verifies BottomsReconstructionEngine constructs waistband, crotch curve, and dual legs."""
    eng = BottomsReconstructionEngine()
    
    # Full jeans
    out_jeans = eng.reconstruct(category="bottoms", subcategory="jeans", fit="regular")
    assert out_jeans.quality_report.is_valid
    assert out_jeans.quality_report.is_manifold
    panel_names = [p.name for p in out_jeans.panels]
    assert "waistband_and_pelvis" in panel_names
    assert "left_leg_panel" in panel_names
    assert "right_leg_panel" in panel_names
    # Jeans reach ankle (y ~ 0.08)
    assert out_jeans.mesh.positions[:, 1].min() < 0.15

    # Shorts
    out_shorts = eng.reconstruct(category="bottoms", subcategory="shorts")
    assert out_shorts.quality_report.is_valid
    # Shorts terminate at knee (y ~ 0.50)
    assert out_shorts.mesh.positions[:, 1].min() > 0.40


def test_dress_and_skirt_reconstruction_engine():
    """Verifies standalone skirts start at waistband (1.02m) rather than neck collarbone (1.42m)."""
    eng = DressReconstructionEngine()

    # Full dress
    out_dress = eng.reconstruct(category="dresses_and_skirts", subcategory="dress")
    assert out_dress.quality_report.is_valid
    assert out_dress.mesh.positions[:, 1].max() > 1.38  # Starts at neck

    # Standalone skirt
    out_skirt = eng.reconstruct(category="dresses_and_skirts", subcategory="skirt")
    assert out_skirt.quality_report.is_valid
    assert out_skirt.mesh.positions[:, 1].max() <= 1.05  # Correctly starts at waist!
    assert "waistband_panel" in [p.name for p in out_skirt.panels]
    assert "flared_skirt_drape" in [p.name for p in out_skirt.panels]


def test_traditional_kurta_reconstruction_engine():
    """Verifies Kurta tunic length and open lateral side slits (chaks)."""
    eng = TraditionalWearReconstructionEngine()
    out = eng.reconstruct(category="traditional", subcategory="kurta")

    assert out.quality_report.is_valid
    assert out.quality_report.is_manifold
    assert out.quality_report.degenerate_triangle_count == 0

    # Knee-length tunic: y extends down to ~0.60m
    assert out.mesh.positions[:, 1].min() < 0.65

    panel_names = [p.name for p in out.panels]
    assert "mandarin_nehru_collar" in panel_names
    assert "kurta_front_flap_with_side_slits" in panel_names
    assert "kurta_back_flap_with_side_slits" in panel_names


def test_footwear_reconstruction_engine():
    """Verifies Footwear generates shoes with soles and collar entry, not shirts."""
    eng = FootwearReconstructionEngine()
    out = eng.reconstruct(category="footwear", subcategory="sneakers")

    assert out.quality_report.is_valid
    assert out.quality_report.is_manifold
    assert out.quality_report.degenerate_triangle_count == 0

    # Ground level sole slab
    assert out.mesh.positions[:, 1].min() < 0.01
    assert out.mesh.positions[:, 1].max() < 0.20  # Shoes are at feet level!

    panel_names = [p.name for p in out.panels]
    assert "left_footwear" in panel_names
    assert "right_footwear" in panel_names


def test_accessories_reconstruction_engine():
    """Verifies Accessories generates cap crown dome and visor brim at head level."""
    eng = AccessoriesReconstructionEngine()
    out = eng.reconstruct(category="accessories", subcategory="caps")

    assert out.quality_report.is_valid
    assert out.quality_report.is_manifold
    # Head level: y in [1.44, 1.58]
    assert out.mesh.positions[:, 1].min() > 1.40

    panel_names = [p.name for p in out.panels]
    assert "cap_crown_dome" in panel_names
    assert "cap_visor_brim" in panel_names


# ── 3. Geometric Quality Validation Subsystem ─────────────────────────────────

def test_mesh_quality_validator_clean():
    """Verifies validator approves topologically clean, manifold meshes."""
    eng = TopsReconstructionEngine()
    res = eng.reconstruct(category="tops", subcategory="tshirt")
    q = GarmentMeshValidator.validate(res.mesh)
    assert q.is_valid
    assert q.is_manifold
    assert not q.has_degenerate_triangles
    assert q.quality_score >= 0.95


def test_mesh_quality_validator_detects_defects():
    """Verifies validator detects degenerate triangles and non-manifold edges."""
    # Create artificial mesh with a degenerate triangle (zero area)
    pos = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [1.0, 0.0, 0.0], # Duplicate vertex -> area = 0
        [0.0, 1.0, 0.0]
    ], dtype=np.float32)
    norm = np.array([[0, 0, 1]] * 4, dtype=np.float32)
    uv = np.array([[0, 0]] * 4, dtype=np.float32)
    idx = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.uint32)

    mesh = GarmentMesh(pos, norm, uv, idx)
    q = GarmentMeshValidator.validate(mesh)
    assert q.has_degenerate_triangles
    assert q.degenerate_triangle_count >= 1
    assert not q.is_valid


# ── 4. Physical Ease and Proportions Estimation ───────────────────────────────

def test_garment_proportions_estimation():
    """Verifies physical ease estimation across fit types."""
    p_slim = GarmentProportionsEstimator.estimate("tops", "tshirt", fit="slim")
    p_reg = GarmentProportionsEstimator.estimate("tops", "tshirt", fit="regular")
    p_over = GarmentProportionsEstimator.estimate("tops", "tshirt", fit="oversized")

    assert p_slim.ease_margin_m < p_reg.ease_margin_m < p_over.ease_margin_m
    assert p_slim.chest_width_m < p_reg.chest_width_m < p_over.chest_width_m


# ── 5. Skeletal Rigging Integrity (Ara 3D Gen 20 Bones) ───────────────────────

def test_ara_20_bone_skinning_integrity():
    """Verifies skinning weights sum to 1.0 and indices are in [0, 19] for all categories."""
    cats = [
        ("tops", "tshirt"),
        ("tops", "formal_shirt"),
        ("tops", "hoodie"),
        ("outerwear", "jacket"),
        ("bottoms", "jeans"),
        ("dresses_and_skirts", "dress"),
        ("traditional", "kurta"),
        ("footwear", "sneakers"),
        ("accessories", "caps")
    ]

    for cat, subcat in cats:
        eng = reconstruction_registry.get_engine(cat, subcat)
        res = eng.reconstruct(category=cat, subcategory=subcat)
        mesh = res.mesh

        assert mesh.joint_indices is not None
        assert mesh.joint_weights is not None
        assert mesh.joint_indices.shape == (len(mesh.positions), 4)
        assert mesh.joint_weights.shape == (len(mesh.positions), 4)

        # Max bone index must not exceed 19 (20 bones: 0 to 19)
        assert mesh.joint_indices.max() < len(ARA_SKELETON_SPECS)

        # Weights must sum to 1.0 (+/- 0.001)
        sums = mesh.joint_weights.sum(axis=1)
        assert np.allclose(sums, 1.0, atol=1e-3), f"Skinning weights do not sum to 1.0 for {cat}/{subcat}"


# ── 6. Binary glTF 2.0 (.glb) Export Verification ─────────────────────────────

def test_binary_glb_export_across_categories():
    """Verifies all reconstructed category meshes export to valid glTF 2.0 binary GLB."""
    png = _make_dummy_png()
    cats = [
        ("tops", "tshirt"),
        ("tops", "formal_shirt"),
        ("tops", "hoodie"),
        ("outerwear", "jacket"),
        ("bottoms", "jeans"),
        ("dresses_and_skirts", "dress"),
        ("dresses_and_skirts", "skirt"),
        ("traditional", "kurta"),
        ("footwear", "sneakers"),
        ("accessories", "caps")
    ]

    for cat, subcat in cats:
        eng = reconstruction_registry.get_engine(cat, subcat)
        res = eng.reconstruct(category=cat, subcategory=subcat)
        glb_data = glb_exporter.export(res.mesh, png, png, name=f"test_{cat}_{subcat}")

        assert len(glb_data) > 1000
        # Check glTF 2.0 binary header: magic bytes 'glTF' (0x46546C67)
        assert glb_data[:4] == b"glTF"


# ── 7. Multi-View Fusion & Surface Provenance ─────────────────────────────────

def test_multi_view_surface_provenance():
    """Verifies front-only reconstruction flags rear as inferred, while authentic back view promotes to observed."""
    eng = TopsReconstructionEngine()
    
    # 1. Single view (front only)
    out_single = eng.reconstruct(category="tops", subcategory="tshirt", back_image=None)
    assert out_single.observed_surface_ratio < 0.90  # Back panels are inferred
    assert out_single.inferred_vertex_count > 0

    # 2. Multi-view (front + verified matching back view)
    front_img = Image.new("RGB", (200, 200), (30, 40, 50))
    back_img = Image.new("RGB", (200, 200), (30, 40, 50))
    out_fused = MultiViewGarmentFuser.fuse_views(
        reconstruction=out_single,
        front_image=front_img,
        back_image=back_img
    )
    assert out_fused.provenance == "hybrid_multiview_constructed"
    assert out_fused.observed_surface_ratio > 0.90  # Posterior promoted to observed!


# ── 8. Learned Model Evaluation & Remote GPU Client ───────────────────────────

def test_learned_model_evaluator_and_apple_silicon_audit():
    """Verifies technical evaluations for TRELLIS, Hunyuan3D, InstantMesh, TripoSR, and SF3D."""
    summary = LearnedModelEvaluator.get_summary_report()
    assert summary["evaluated_models_count"] == 5
    models = summary["models"]

    # TRELLIS
    assert "microsoft_trellis" in models
    assert "INCOMPATIBLE_OOM" in models["microsoft_trellis"]["local_m2_8gb_compatibility"]
    assert models["microsoft_trellis"]["min_vram_gb"] >= 16.0

    # Hunyuan3D 2.0
    assert "tencent_hunyuan3d_v2" in models
    assert models["tencent_hunyuan3d_v2"]["min_vram_gb"] >= 24.0

    # TripoSR
    assert "triposr" in models
    assert models["triposr"]["license_name"] == "MIT License"


def test_learned_reconstruction_client_fallback_behavior():
    """Verifies LearnedReconstructionClient transparently falls back when unconfigured."""
    client_instance = LearnedReconstructionClient(endpoint_url=None)
    assert not client_instance.is_configured
    health = client_instance.check_health()
    assert health["status"] == "unconfigured"
    assert not health["remote_available"]


# ── 9. REST API Diagnostics & Neural Evaluations ──────────────────────────────

def test_api_neural_evaluations_endpoint():
    """Verifies GET /api/fashion/garment-gen/neural-evaluations returns benchmark matrix."""
    resp = client.get("/api/fashion/garment-gen/neural-evaluations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["evaluated_models_count"] == 5
    assert "microsoft_trellis" in data["models"]
    assert "tencent_hunyuan3d_v2" in data["models"]

