"""
YORVYN — Phase 5: Universal Avatar-Aware Garment Fitting, Cloth Physics & Dynamic Deformation Test Suite
Tests:
1. AvatarBodyMeasurementEngine: 14 anthropometric measurements, archetypes, dynamic modifiers, validation.
2. GarmentEaseEngine: ease allowances across segments, fit classification, non-uniform scaling curves.
3. GarmentCollisionEngine: body hull intersection detection, outward normal projection, 3.0mm clearance.
4. GarmentPhysicsEngine: PBD draping, fabric presets (cotton, denim, silk, wool, leather, knitwear), convergence.
5. AnimationDeformationValidator: 20-bone forward kinematics, 6 canonical animation poses, stability score.
6. UniversalGarmentFittingEngine: category-specific fitting across 10 categories, dynamic refitting.
7. REST API: GET /api/fashion/garment-gen/avatar-profiles endpoints.
"""

import math
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.garment_intelligence_models import (
    AvatarMeasurementsV2,
    GarmentFittingResultV2,
    GarmentEaseAnalysisV2
)
from backend.app.services.garments.garment_mesh_builder import GarmentMesh, ARA_SKELETON_SPECS
from backend.app.services.garments.reconstruction import (
    reconstruction_registry,
    TopsReconstructionEngine,
    BottomsReconstructionEngine,
    DressReconstructionEngine,
    FootwearReconstructionEngine
)
from backend.app.services.garments.fitting import (
    avatar_body_measurement_engine,
    garment_ease_engine,
    garment_collision_engine,
    garment_physics_engine,
    animation_deformation_validator,
    universal_garment_fitting_engine,
    FABRIC_PRESETS
)

client = TestClient(app)


def test_avatar_body_measurement_archetypes():
    """Verifies that all 4 canonical avatar archetypes contain 14 valid human measurements."""
    for profile_id in ["standard_175", "athletic_broad", "slim_lean", "plus_curvy"]:
        profile = avatar_body_measurement_engine.get_profile(profile_id)
        assert isinstance(profile, AvatarMeasurementsV2)
        assert profile.height_cm > 150.0
        assert profile.chest_circumference_cm > 70.0
        assert profile.waist_circumference_cm > 55.0
        assert profile.hip_circumference_cm > 75.0
        assert profile.shoulder_width_cm > 35.0
        assert profile.arm_length_cm > 50.0
        assert profile.inseam_cm > 65.0
        assert profile.foot_length_cm > 20.0

        is_valid, issues = avatar_body_measurement_engine.validate_measurements(profile)
        assert is_valid, f"Profile {profile_id} failed validation: {issues}"


def test_avatar_body_measurement_custom_modifiers():
    """Verifies scaling laws when applying user customization sliders (height, muscle, weight)."""
    base = avatar_body_measurement_engine.get_profile("standard_175")
    
    # Scale up height +10%, muscle +15%, weight +20%
    scaled = avatar_body_measurement_engine.apply_custom_modifiers(
        base_profile=base,
        height_scale=1.10,
        muscle_scale=1.15,
        weight_scale=1.20,
        shoulder_scale=1.08
    )

    assert scaled.height_cm > base.height_cm
    assert scaled.shoulder_width_cm > base.shoulder_width_cm
    assert scaled.chest_circumference_cm > base.chest_circumference_cm
    assert scaled.waist_circumference_cm > base.waist_circumference_cm
    assert scaled.inseam_cm > base.inseam_cm

    is_valid, _ = avatar_body_measurement_engine.validate_measurements(scaled)
    assert is_valid


def test_avatar_measurement_extraction_from_mesh():
    """Verifies slice-based circumference and height measurement from 3D vertex positions."""
    # Create synthetic cylindrical torso mesh
    angles = np.linspace(0, 2 * math.pi, 32, endpoint=False)
    y_levels = np.linspace(0.0, 1.75, 40)
    
    verts = []
    for y in y_levels:
        rx = 0.16 if (0.9 < y < 1.35) else 0.12
        rz = 0.12 if (0.9 < y < 1.35) else 0.10
        for a in angles:
            verts.append([rx * math.cos(a), y, rz * math.sin(a)])

    mesh_pos = np.array(verts, dtype=np.float32)
    profile = avatar_body_measurement_engine.extract_from_mesh(mesh_pos, profile_id="test_mesh")

    assert 170.0 <= profile.height_cm <= 180.0
    assert 75.0 <= profile.chest_circumference_cm <= 105.0
    assert 65.0 <= profile.waist_circumference_cm <= 95.0
    assert profile.inseam_cm > 60.0


def test_garment_ease_engine_classifications():
    """Verifies garment ease evaluation across slim, regular, relaxed, oversized, and compression fits."""
    standard_avatar = avatar_body_measurement_engine.get_profile("standard_175")

    # Regular fit
    reg_ease = garment_ease_engine.calculate_ease("tops", "tshirt", standard_avatar, target_fit="regular")
    assert reg_ease.fit_classification in ["regular", "slim"]
    assert reg_ease.chest_ease_cm >= 4.0
    assert not reg_ease.is_negative_ease

    # Relaxed / Oversized fit (Hoodie)
    hoodie_ease = garment_ease_engine.calculate_ease("tops", "hoodie", standard_avatar)
    assert hoodie_ease.fit_classification in ["relaxed", "oversized"]
    assert hoodie_ease.chest_ease_cm >= 10.0

    # Compression fit
    comp_ease = garment_ease_engine.calculate_ease("tops", "tshirt", standard_avatar, target_fit="compression")
    assert comp_ease.fit_classification == "compression" or comp_ease.chest_ease_cm < 4.0

    # Verify segment scale factors exist
    assert "chest" in reg_ease.segment_scale_factors
    assert "waist" in reg_ease.segment_scale_factors
    assert "shoulder" in reg_ease.segment_scale_factors
    assert "height" in reg_ease.segment_scale_factors


def test_garment_collision_engine_resolution():
    """Verifies that penetrating garment vertices are pushed outside the body hull with guaranteed clearance."""
    # Create vertices that intentionally penetrate inside the torso (X=0, Y=1.20, Z=0)
    penetrating_pts = np.array([
        [0.0, 1.20, 0.0],       # Dead center inside torso
        [0.02, 1.25, 0.01],     # Inside chest core
        [0.21, 1.40, 0.0],      # Inside shoulder core
        [0.0, 0.80, 0.0],       # Inside pelvis
    ], dtype=np.float32)

    resolved, metrics = garment_collision_engine.detect_and_resolve_collisions(
        penetrating_pts,
        min_clearance_m=0.0030
    )

    assert metrics.initial_penetration_count > 0
    assert metrics.resolved_penetration_count == metrics.initial_penetration_count
    assert metrics.penetration_count == 0
    assert metrics.max_penetration_mm > 10.0
    assert metrics.min_clearance_guaranteed_mm == 3.0

    # Re-evaluating resolved vertices against the collision engine should yield 0 penetrations
    re_resolved, re_metrics = garment_collision_engine.detect_and_resolve_collisions(
        resolved,
        min_clearance_m=0.0030
    )
    assert re_metrics.penetration_count == 0
    assert re_metrics.initial_penetration_count == 0
    assert re_metrics.max_penetration_mm == 0.0


def test_garment_physics_engine_fabric_presets():
    """Verifies physical behavior differences across fabric presets (silk vs denim vs leather)."""
    # Create simple grid cloth mesh
    positions = []
    indices = []
    w, h = 5, 5
    for y in range(h):
        for x in range(w):
            positions.append([(x - 2) * 0.05, 1.30 - y * 0.05, 0.18])
    for y in range(h - 1):
        for x in range(w - 1):
            i0 = y * w + x
            i1 = i0 + 1
            i2 = (y + 1) * w + x
            i3 = i2 + 1
            indices.append([i0, i1, i2])
            indices.append([i1, i3, i2])

    pos_np = np.array(positions, dtype=np.float32)
    idx_np = np.array(indices, dtype=np.int32)

    # 1. Silk (low bending stiffness, high fluid drape)
    silk_draped, silk_metrics = garment_physics_engine.simulate_draping(
        pos_np, idx_np, fabric_type="silk", iterations=10
    )
    assert silk_metrics.bending_stiffness < 0.25
    assert silk_metrics.convergence_score > 0.80

    # 2. Denim (heavy twill, high bending stiffness, structured)
    denim_draped, denim_metrics = garment_physics_engine.simulate_draping(
        pos_np, idx_np, fabric_type="denim", iterations=10
    )
    assert denim_metrics.bending_stiffness > 0.70
    assert denim_metrics.mass_g_m2 > silk_metrics.mass_g_m2

    # 3. Leather (stiffest profile, thickest)
    leather_draped, leather_metrics = garment_physics_engine.simulate_draping(
        pos_np, idx_np, fabric_type="leather", iterations=10
    )
    assert leather_metrics.bending_stiffness >= 0.85
    assert leather_metrics.thickness_mm == 5.0


def test_animation_deformation_validator_6_poses():
    """Verifies garment mesh deformation under all 6 canonical avatar animation poses."""
    rec = TopsReconstructionEngine().reconstruct(category="tops", subcategory="tshirt")
    mesh = rec.mesh

    def_metrics = animation_deformation_validator.validate_garment_deformation(mesh, category="tops")

    assert len(def_metrics.tested_poses) == 6
    assert "idle" in def_metrics.tested_poses
    assert "walking" in def_metrics.tested_poses
    assert "arm_raising" in def_metrics.tested_poses
    assert "arm_bending" in def_metrics.tested_poses
    assert "sitting" in def_metrics.tested_poses
    assert "squatting" in def_metrics.tested_poses

    assert def_metrics.skinning_compliance_20_bones
    assert def_metrics.deformation_stability_score > 0.85
    assert def_metrics.normal_inversion_count == 0


def test_universal_fitting_engine_tshirt():
    """Verifies end-to-end universal fitting on a graphic T-shirt."""
    rec = TopsReconstructionEngine().reconstruct(category="tops", subcategory="tshirt")
    mesh = rec.mesh

    fitted_mesh, res = universal_garment_fitting_engine.fit_garment(
        mesh=mesh,
        category="tops",
        subcategory="tshirt",
        avatar_profile_id="standard_175",
        fabric_type="cotton"
    )

    assert isinstance(res, GarmentFittingResultV2)
    assert len(fitted_mesh.positions) == len(mesh.positions)
    assert res.collision.min_clearance_guaranteed_mm == 3.0
    assert res.physics.simulation_status == "converged"
    assert res.animation_deformation.deformation_stability_score > 0.85
    assert "neckline" in res.anchor_points
    assert "shoulder_left" in res.anchor_points
    assert res.fitting_time_ms > 0.0


def test_universal_fitting_engine_bottoms_jeans():
    """Verifies category-specific fitting on jeans (pelvic waistband and leg contours)."""
    rec = BottomsReconstructionEngine().reconstruct(category="bottoms", subcategory="jeans")
    mesh = rec.mesh

    fitted_mesh, res = universal_garment_fitting_engine.fit_garment(
        mesh=mesh,
        category="bottoms",
        subcategory="jeans",
        avatar_profile_id="athletic_broad",
        fabric_type="denim"
    )

    assert isinstance(res, GarmentFittingResultV2)
    assert "waistband" in res.anchor_points
    assert "crotch" in res.anchor_points
    assert res.physics.fabric_preset == "denim"
    assert res.collision.min_clearance_guaranteed_mm == 3.0


def test_universal_fitting_engine_traditional_kurta():
    """Verifies traditional kurta fitting (mandarin collar and lateral side slits / chaks)."""
    engine = reconstruction_registry.get_engine("traditional", "kurta")
    rec = engine.reconstruct(category="traditional", subcategory="kurta")
    mesh = rec.mesh

    fitted_mesh, res = universal_garment_fitting_engine.fit_garment(
        mesh=mesh,
        category="traditional",
        subcategory="kurta",
        avatar_profile_id="standard_175",
        fabric_type="linen"
    )

    assert isinstance(res, GarmentFittingResultV2)
    assert "mandarin_collar" in res.anchor_points
    assert "side_slit_left" in res.anchor_points
    assert "side_slit_right" in res.anchor_points
    assert res.physics.fabric_preset == "linen"


def test_dynamic_refitting_on_avatar_customization():
    """Verifies dynamic in-place refitting without reconstructing 3D mesh from scratch."""
    rec = TopsReconstructionEngine().reconstruct(category="tops", subcategory="tshirt")
    mesh = rec.mesh

    # Initial fit on standard avatar
    fitted_1, res_1 = universal_garment_fitting_engine.fit_garment(mesh, "tops", "tshirt", "standard_175")

    # Dynamic customization: user increases chest (+15%) and height (+5%)
    custom_avatar = avatar_body_measurement_engine.apply_custom_modifiers(
        base_profile=res_1.avatar_measurements,
        height_scale=1.05,
        muscle_scale=1.15,
        weight_scale=1.10
    )

    fitted_2, res_2 = universal_garment_fitting_engine.refit_garment(
        mesh=fitted_1,
        category="tops",
        subcategory="tshirt",
        updated_avatar_measurements=custom_avatar
    )

    assert res_2.avatar_measurements.height_cm > res_1.avatar_measurements.height_cm
    assert res_2.avatar_measurements.chest_circumference_cm > res_1.avatar_measurements.chest_circumference_cm
    assert res_2.collision.is_collision_free or res_2.collision.penetration_count == 0
    # Original mesh topology (vertex count and triangles) is strictly preserved
    assert len(fitted_2.positions) == len(mesh.positions)
    assert len(fitted_2.indices) == len(mesh.indices)


def test_api_avatar_profiles_endpoints():
    """Verifies GET /api/fashion/garment-gen/avatar-profiles endpoints."""
    res = client.get("/api/fashion/garment-gen/avatar-profiles")
    assert res.status_code == 200
    data = res.json()
    assert "profiles" in data
    assert "standard_175" in data["profiles"]
    assert "athletic_broad" in data["profiles"]
    assert "slim_lean" in data["profiles"]
    assert "plus_curvy" in data["profiles"]
    assert len(data["supported_measurements"]) == 14

    # Test single profile lookup
    p_res = client.get("/api/fashion/garment-gen/avatar-profiles/standard_175")
    assert p_res.status_code == 200
    p_data = p_res.json()
    assert p_data["profile_id"] == "standard_175"
    assert p_data["height_cm"] == 175.0
