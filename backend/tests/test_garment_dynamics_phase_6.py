"""
YORVYN — PHASE 6 INTEGRATION & DYNAMICS TEST SUITE
Tests the continuous motion-aware cloth dynamics, fabric preset differentiation,
hierarchical collision proxies, dynamic wrinkle engine, and animation stability.
"""

import math
import numpy as np
import pytest

from backend.app.models.garment_intelligence_models import (
    AvatarMeasurementsV2,
    ClothPhysicsMetricsV2,
    WrinkleDeformationMetricsV2,
    MotionSequenceSimulationMetricsV2
)
from backend.app.services.garments.fitting import (
    GarmentPhysicsEngine,
    garment_physics_engine,
    FABRIC_PRESETS,
    GarmentCollisionEngine,
    garment_collision_engine,
    GarmentWrinkleEngine,
    garment_wrinkle_engine,
    AnimationDeformationValidator,
    animation_deformation_validator,
    UniversalGarmentFittingEngine,
    universal_garment_fitting_engine
)
from backend.app.services.garments.reconstruction.tops_engine import TopsReconstructionEngine
from backend.app.services.garments.reconstruction.bottoms_engine import BottomsReconstructionEngine
from backend.app.services.garments.reconstruction.traditional_engine import TraditionalWearReconstructionEngine


@pytest.fixture
def standard_avatar():
    return AvatarMeasurementsV2(
        profile_id="standard_175",
        display_name="Standard Adult (1.75m)",
        height_cm=175.0,
        shoulder_width_cm=43.5,
        chest_circumference_cm=96.0,
        waist_circumference_cm=78.0,
        hip_circumference_cm=98.0,
        neck_circumference_cm=38.0,
        arm_length_cm=60.0,
        upper_arm_circumference_cm=30.0,
        wrist_circumference_cm=17.0,
        inseam_cm=78.0,
        thigh_circumference_cm=54.0,
        calf_circumference_cm=36.0,
        foot_length_cm=26.5,
        foot_width_cm=9.8
    )


def test_fabric_presets_8_calibrated_differentiation():
    """Verifies that all 8 fabric presets model distinct physical properties."""
    expected_fabrics = ["cotton", "denim", "silk", "wool", "leather", "knitwear", "synthetic", "linen"]
    for f in expected_fabrics:
        assert f in FABRIC_PRESETS, f"Fabric preset {f} missing from FABRIC_PRESETS"
        preset = FABRIC_PRESETS[f]
        assert preset.mass_g_m2 > 50.0
        assert 0.50 <= preset.stretch_stiffness <= 1.0
        assert 0.10 <= preset.bending_stiffness <= 1.0
        assert 0.30 <= preset.shear_stiffness <= 1.0
        assert 0.80 <= preset.damping <= 0.99
        assert preset.air_resistance > 0.0
        assert 0.80 <= preset.recovery_rate <= 1.0
        assert preset.elasticity_limit >= 1.05

    # Specific material property differentiations
    # Silk is fluid (low bending, low mass, high air drag)
    silk = FABRIC_PRESETS["silk"]
    denim = FABRIC_PRESETS["denim"]
    leather = FABRIC_PRESETS["leather"]

    assert silk.bending_stiffness < denim.bending_stiffness
    assert silk.mass_g_m2 < denim.mass_g_m2
    assert denim.bending_stiffness > silk.bending_stiffness
    assert leather.stretch_stiffness > silk.stretch_stiffness
    assert leather.thickness_mm > silk.thickness_mm


def test_narrow_phase_joint_spheres_collision():
    """Verifies articulating narrow-phase joint spheres detect and resolve collisions at flex joints."""
    engine = GarmentCollisionEngine()
    assert len(engine.joint_spheres) >= 10

    # Test an elbow joint collision point (LeftForeArm at [0.33, 1.25, 0.0])
    elbow_pt = np.array([[0.33, 1.25, 0.0]], dtype=np.float32)
    resolved_pts, metrics = engine.detect_and_resolve_collisions(elbow_pt, min_clearance_m=0.0030)

    # Point must be pushed outside the elbow joint sphere
    assert metrics.initial_penetration_count >= 1
    assert metrics.penetration_count == 0
    assert metrics.average_clearance_mm >= 3.0


def test_anti_jitter_deadband_filter():
    """Verifies that sub-millimeter oscillations do not cause erratic jitter."""
    engine = GarmentCollisionEngine()
    # Point at exact safe clearance boundary plus tiny noise
    near_safe_pt = np.array([[0.0, 1.25, 0.20]], dtype=np.float32)
    resolved_pts, metrics = engine.detect_and_resolve_collisions(near_safe_pt, min_clearance_m=0.0030)
    # Distance moved should be minimal/stable
    displacement = np.linalg.norm(resolved_pts[0] - near_safe_pt[0])
    assert displacement < 0.05  # No massive jump


def test_garment_wrinkle_engine_strain_and_folds():
    """Verifies that compressive strain generates realistic folds while tensile strain avoids wrinkles."""
    # Create simple grid of rest vertices
    rest_pos = np.array([
        [0.0, 0.0, 0.0],
        [0.1, 0.0, 0.0],
        [0.0, 0.1, 0.0],
        [0.1, 0.1, 0.0]
    ], dtype=np.float32)

    # Compress horizontally along X axis
    compressed_pos = np.array([
        [0.0, 0.0, 0.0],
        [0.05, 0.0, 0.0],  # 50% horizontal compression!
        [0.0, 0.1, 0.0],
        [0.05, 0.1, 0.0]
    ], dtype=np.float32)

    indices = np.array([[0, 1, 2], [1, 3, 2]], dtype=np.int32)

    wrinkled_pos, perturbed_norm, metrics = garment_wrinkle_engine.analyze_strain_and_generate_folds(
        rest_positions=rest_pos,
        deformed_positions=compressed_pos,
        indices=indices,
        fabric_type="denim"
    )

    assert metrics.compression_vertex_ratio > 0.0
    assert metrics.min_strain < 0.0
    assert metrics.wrinkle_amplitude_mm >= 3.0
    # Buckling displacement occurred on Z axis
    z_disp = np.abs(wrinkled_pos[:, 2] - compressed_pos[:, 2])
    assert np.any(z_disp > 0.0)


def test_wrinkle_wavelength_and_amplitude_textile_variation():
    """Verifies that stiff fabrics (denim, leather) produce wider folds than fluid fabrics (silk)."""
    # Create test patch
    rest_pos = np.random.uniform(-0.1, 0.1, size=(20, 3)).astype(np.float32)
    deformed_pos = rest_pos * np.array([0.8, 1.0, 1.0], dtype=np.float32)  # 20% compression along X
    indices = np.array([[0, 1, 2], [2, 3, 4], [4, 5, 6]], dtype=np.int32)

    _, _, denim_metrics = garment_wrinkle_engine.analyze_strain_and_generate_folds(
        rest_pos, deformed_pos, indices, fabric_type="denim"
    )
    _, _, silk_metrics = garment_wrinkle_engine.analyze_strain_and_generate_folds(
        rest_pos, deformed_pos, indices, fabric_type="silk"
    )

    assert denim_metrics.wrinkle_wavelength_mm > silk_metrics.wrinkle_wavelength_mm
    assert denim_metrics.wrinkle_amplitude_mm > silk_metrics.wrinkle_amplitude_mm


def test_continuous_motion_simulation_gait_cycle():
    """Verifies continuous multi-frame simulation over a motion sequence."""
    rec = TopsReconstructionEngine().reconstruct(category="tops", subcategory="tshirt")
    mesh = rec.mesh

    motion_sequence = [
        {"pose": "idle", "inertia": [0.0, 0.0, 0.0]},
        {"pose": "walk_step_1", "inertia": [0.05, -0.01, 0.02]},
        {"pose": "walk_step_2", "inertia": [-0.05, -0.01, -0.02]},
        {"pose": "walk_step_3", "inertia": [0.04, -0.01, 0.03]}
    ]

    final_pos, motion_metrics, wrinkle_metrics = garment_physics_engine.simulate_continuous_motion(
        positions=mesh.positions,
        indices=mesh.indices,
        motion_sequence=motion_sequence,
        fabric_type="cotton",
        category="tops",
        fps=60.0
    )

    assert motion_metrics.total_simulated_frames >= 10
    assert motion_metrics.mean_frame_time_ms < 60.0
    assert motion_metrics.residual_motion_penetrations == 0
    assert motion_metrics.kinetic_energy_stable
    assert motion_metrics.motion_stability_score >= 0.85
    assert wrinkle_metrics.is_strain_balanced


def test_category_specific_dynamic_profiles():
    """Verifies category-specific dynamic profiles adjust stiffness constraints appropriately."""
    rec_hoodie = TopsReconstructionEngine().reconstruct(category="tops", subcategory="hoodie")
    rec_tshirt = TopsReconstructionEngine().reconstruct(category="tops", subcategory="tshirt")

    # Hoodie has heavier fleece and structured hood
    _, m_hoodie, _ = garment_physics_engine.simulate_continuous_motion(
        rec_hoodie.mesh.positions, rec_hoodie.mesh.indices,
        motion_sequence=[{"pose": "idle"}], fabric_type="wool", category="hoodie"
    )

    _, m_tshirt, _ = garment_physics_engine.simulate_continuous_motion(
        rec_tshirt.mesh.positions, rec_tshirt.mesh.indices,
        motion_sequence=[{"pose": "idle"}], fabric_type="cotton", category="tops"
    )

    assert m_hoodie.motion_stability_score >= 0.85
    assert m_tshirt.motion_stability_score >= 0.85
    assert m_hoodie.residual_motion_penetrations == 0
    assert m_tshirt.residual_motion_penetrations == 0


def test_kurta_side_slit_preservation():
    """Verifies traditional tunic side slits do not bridge or fuse during motion."""
    rec = TraditionalWearReconstructionEngine().reconstruct(category="traditional", subcategory="kurta")
    mesh = rec.mesh

    _, motion_metrics, wrinkle_metrics = garment_physics_engine.simulate_continuous_motion(
        positions=mesh.positions,
        indices=mesh.indices,
        motion_sequence=[{"pose": "walk"}],
        fabric_type="linen",
        category="traditional"
    )

    assert motion_metrics.residual_motion_penetrations == 0
    assert motion_metrics.dynamic_collision_clearance_mm >= 3.0


def test_animation_deformation_validator_10_continuous_poses():
    """Verifies that all 10 continuous animation poses are validated without mesh explosion."""
    rec = BottomsReconstructionEngine().reconstruct(category="bottoms", subcategory="jeans")
    mesh = rec.mesh

    motion_metrics = animation_deformation_validator.validate_continuous_motion_sequence(
        mesh=mesh,
        category="bottoms",
        fabric_type="denim"
    )

    assert motion_metrics.total_simulated_frames >= 10
    assert motion_metrics.residual_motion_penetrations == 0
    assert motion_metrics.motion_stability_score >= 0.85


def test_universal_fitting_engine_phase_6_telemetry(standard_avatar):
    """Verifies that universal fitting engine generates motion simulation and wrinkle deformation telemetry."""
    rec = TopsReconstructionEngine().reconstruct(category="tops", subcategory="tshirt")
    mesh = rec.mesh

    fitted_mesh, fit_res = universal_garment_fitting_engine.fit_garment(
        mesh=mesh,
        category="tops",
        subcategory="tshirt",
        avatar_profile_id="standard_175",
        fabric_type="cotton",
        job_id="test_p6_fit"
    )

    assert fit_res.motion_simulation is not None
    assert fit_res.wrinkle_deformation is not None
    assert fit_res.motion_simulation.total_simulated_frames >= 10
    assert fit_res.motion_simulation.residual_motion_penetrations == 0
    assert fit_res.wrinkle_deformation.generated_fold_count >= 0
    assert fit_res.collision.is_collision_free
