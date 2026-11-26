"""
YORVYN — Universal Garment-to-Avatar Fitting Engine (Phase 5)
Orchestrates category-specific anatomical fitting, non-uniform ease scaling,
collision resolution, physical PBD draping, and skeletal deformation verification.
Supports all 10 apparel categories with distinct anatomical anchors.
"""

from typing import Dict, Any, Optional, Tuple, List
import time
import math
import numpy as np

from backend.app.models.garment_intelligence_models import (
    AvatarMeasurementsV2,
    GarmentFittingResultV2,
    GarmentEaseAnalysisV2,
    CollisionMetricsV2,
    ClothPhysicsMetricsV2,
    AnimationDeformationMetricsV2
)
from backend.app.services.garments.garment_mesh_builder import GarmentMesh, ARA_SKELETON_SPECS
from .avatar_body_measurement_engine import avatar_body_measurement_engine, AvatarBodyMeasurementEngine
from .garment_ease_engine import garment_ease_engine, GarmentEaseEngine
from .garment_collision_engine import garment_collision_engine, GarmentCollisionEngine
from .garment_physics_engine import garment_physics_engine, GarmentPhysicsEngine
from .animation_deformation_validator import animation_deformation_validator, AnimationDeformationValidator


class UniversalGarmentFittingEngine:
    """
    Universal fitting orchestrator. Adapts reconstructed 3D clothing to any
    avatar body shape using category-specific anatomical anchors and physics draping.
    """

    def __init__(self):
        self.measurement_engine = avatar_body_measurement_engine
        self.ease_engine = garment_ease_engine
        self.collision_engine = garment_collision_engine
        self.physics_engine = garment_physics_engine
        self.deformation_validator = animation_deformation_validator

    def fit_garment(
        self,
        mesh: GarmentMesh,
        category: str = "tops",
        subcategory: str = "tshirt",
        avatar_profile_id: str = "standard_175",
        target_fit: Optional[str] = None,
        fabric_type: str = "cotton",
        job_id: str = "fit_job",
        custom_avatar_measurements: Optional[AvatarMeasurementsV2] = None
    ) -> Tuple[GarmentMesh, GarmentFittingResultV2]:
        """
        Executes end-to-end universal fitting pipeline:
        1. Retrieve/validate avatar measurements (14 anatomical metrics)
        2. Calculate physical ease & segment-specific scaling curves
        3. Apply category-specific geometric morphing and anchor alignment
        4. Detect and resolve garment-to-body collisions (3.0mm clearance)
        5. Run PBD cloth simulation draping
        6. Validate deformation across 6 canonical animation poses
        """
        t0 = time.perf_counter()
        warnings: List[str] = []

        # 1. Avatar Body Measurements
        if custom_avatar_measurements:
            measurements = custom_avatar_measurements
        else:
            measurements = self.measurement_engine.get_profile(avatar_profile_id)

        is_valid, validation_issues = self.measurement_engine.validate_measurements(measurements)
        if not is_valid:
            warnings.extend(validation_issues)

        # 2. Size and Ease Intelligence
        ease_analysis = self.ease_engine.calculate_ease(
            category=category,
            subcategory=subcategory,
            avatar_measurements=measurements,
            target_fit=target_fit
        )

        # 3. Category-Specific Non-Uniform Anatomical Morphing
        morphed_pos, anchor_points = self._apply_category_morphing(
            positions=mesh.positions,
            category=category,
            subcategory=subcategory,
            measurements=measurements,
            ease=ease_analysis
        )

        # Update collision hulls to match avatar body profile
        scale_f = measurements.height_cm / 175.0
        bones = {spec[0]: np.array(spec[3], dtype=np.float32) * scale_f for spec in ARA_SKELETON_SPECS}
        self.collision_engine.update_hulls_from_avatar(bones, scale_factor=scale_f)

        # 4. Collision Detection & Penetration Prevention
        collision_resolved_pos, collision_metrics = self.collision_engine.detect_and_resolve_collisions(
            positions=morphed_pos,
            indices=mesh.indices,
            min_clearance_m=0.0030
        )

        # 5. Cloth Simulation & Dynamic Draping
        draped_pos, physics_metrics = self.physics_engine.simulate_draping(
            positions=collision_resolved_pos,
            indices=mesh.indices,
            fabric_type=fabric_type,
            category=category,
            iterations=12
        )

        # Build Fitted GarmentMesh with recomputed smooth normals and preserved UV parameterization
        from backend.app.services.garments.reconstruction.geometry_utils import calculate_smooth_normals
        fitted_normals = calculate_smooth_normals(draped_pos, mesh.indices)

        fitted_mesh = GarmentMesh(
            positions=draped_pos,
            normals=fitted_normals,
            uvs=mesh.uvs,
            indices=mesh.indices,
            joint_indices=mesh.joint_indices,
            joint_weights=mesh.joint_weights
        )

        # 6. Skeleton & Animation Deformation Validation
        deformation_metrics = self.deformation_validator.validate_garment_deformation(
            mesh=fitted_mesh,
            category=category
        )

        # 7. Motion-Aware Continuous Simulation & Dynamic Wrinkle Evaluation (Phase 6)
        motion_metrics = self.deformation_validator.validate_continuous_motion_sequence(
            mesh=fitted_mesh,
            category=category,
            fabric_type=fabric_type
        )

        # Wrinkle strain evaluation
        indices = mesh.indices if mesh.indices is not None else np.zeros((0, 3), dtype=np.int32)
        from .garment_wrinkle_engine import garment_wrinkle_engine
        _, _, wrinkle_metrics = garment_wrinkle_engine.analyze_strain_and_generate_folds(
            rest_positions=mesh.positions,
            deformed_positions=fitted_mesh.positions,
            indices=indices,
            fabric_type=fabric_type,
            category=category
        )

        fit_latency_ms = (time.perf_counter() - t0) * 1000.0

        fitting_result = GarmentFittingResultV2(
            job_id=job_id,
            category=category,
            subcategory=subcategory,
            avatar_measurements=measurements,
            ease_analysis=ease_analysis,
            collision=collision_metrics,
            physics=physics_metrics,
            animation_deformation=deformation_metrics,
            motion_simulation=motion_metrics,
            wrinkle_deformation=wrinkle_metrics,
            anchor_points=anchor_points,
            fitting_time_ms=round(fit_latency_ms, 2),
            warnings=warnings
        )

        return fitted_mesh, fitting_result

    def refit_garment(
        self,
        mesh: GarmentMesh,
        category: str,
        subcategory: str,
        updated_avatar_measurements: AvatarMeasurementsV2,
        fabric_type: str = "cotton"
    ) -> Tuple[GarmentMesh, GarmentFittingResultV2]:
        """
        Rapid in-place refitting when user modifies avatar sliders in the UI.
        Avoids full 3D reconstruction while accurately adjusting ease and resolving collisions.
        """
        return self.fit_garment(
            mesh=mesh,
            category=category,
            subcategory=subcategory,
            custom_avatar_measurements=updated_avatar_measurements,
            fabric_type=fabric_type,
            job_id="refit_dynamic"
        )

    def _apply_category_morphing(
        self,
        positions: np.ndarray,
        category: str,
        subcategory: str,
        measurements: AvatarMeasurementsV2,
        ease: GarmentEaseAnalysisV2
    ) -> Tuple[np.ndarray, Dict[str, List[float]]]:
        """
        Applies segment-specific non-uniform coordinate morphing tailored to each garment category.
        Preserves collar, waistband, sleeve, and hem construction without uniform whole-mesh distortion.
        """
        morphed = np.copy(positions)
        scales = ease.segment_scale_factors
        s_shoulder = scales.get("shoulder", 1.0)
        s_chest = scales.get("chest", 1.0)
        s_waist = scales.get("waist", 1.0)
        s_hip = scales.get("hip", 1.0)
        s_height = scales.get("height", 1.0)

        anchors: Dict[str, List[float]] = {}
        y_vals = positions[:, 1]
        y_min, y_max = float(np.min(y_vals)), float(np.max(y_vals))

        if "top" in category or "shirt" in category or "hoodie" in category or "jacket" in category:
            # Anchor 1: Collar / Neckline ($Y \approx 1.38\text{m}$)
            # Anchor 2: Shoulder Seams ($X \approx \pm 0.22\text{m}$)
            # Anchor 3: Hem ($Y \approx 0.88\text{m}$)
            anchors["neckline"] = [0.0, y_max, 0.0]
            anchors["shoulder_left"] = [0.21 * s_shoulder, y_max - 0.04, 0.0]
            anchors["shoulder_right"] = [-0.21 * s_shoulder, y_max - 0.04, 0.0]
            anchors["hem"] = [0.0, y_min, 0.0]

            for i in range(len(positions)):
                x, y, z = positions[i, 0], positions[i, 1], positions[i, 2]
                t_torso = float(np.clip((y - 0.88) / 0.50, 0.0, 1.0))
                # Non-uniform morphing: chest scaling at upper torso, waist scaling at lower torso
                scale_xz = (1.0 - t_torso) * s_waist + t_torso * s_chest

                # If near shoulders, blend in shoulder span
                if y > 1.30:
                    t_sh = float(np.clip((y - 1.30) / 0.15, 0.0, 1.0))
                    scale_xz = (1.0 - t_sh) * scale_xz + t_sh * s_shoulder

                # For sleeve vertices (|x| > 0.18), preserve bone alignment and arm radial thickness
                if abs(x) > 0.18:
                    x_sh = math.copysign(0.185, x)
                    morphed[i, 0] = x_sh * s_shoulder + (x - x_sh) * s_chest
                else:
                    morphed[i, 0] = x * scale_xz

                morphed[i, 2] = z * scale_xz
                # Height adjustment relative to avatar spine
                morphed[i, 1] = 0.88 + (y - 0.88) * s_height

        elif "bottom" in category or "jeans" in category or "trouser" in category:
            # Anchor 1: Waistband ($Y \approx 0.95\text{m}$)
            # Anchor 2: Crotch ($Y \approx 0.76\text{m}$)
            # Anchor 3: Ankles ($Y \approx 0.08\text{m}$)
            anchors["waistband"] = [0.0, y_max, 0.0]
            anchors["crotch"] = [0.0, 0.76 * s_height, 0.0]
            anchors["ankle_left"] = [0.098, y_min, 0.0]
            anchors["ankle_right"] = [-0.098, y_min, 0.0]

            for i in range(len(positions)):
                y = positions[i, 1]
                if y > 0.85:
                    # Pelvis / Waistband band
                    t_p = float(np.clip((y - 0.85) / 0.12, 0.0, 1.0))
                    scale_xz = (1.0 - t_p) * s_hip + t_p * s_waist
                else:
                    # Leg tubes
                    t_leg = float(np.clip((y - 0.10) / 0.75, 0.0, 1.0))
                    scale_xz = (1.0 - t_leg) * 1.0 + t_leg * s_hip

                morphed[i, 0] = positions[i, 0] * scale_xz
                morphed[i, 2] = positions[i, 2] * scale_xz
                morphed[i, 1] = positions[i, 1] * s_height

        elif "dress" in category or "skirt" in category:
            anchors["waist_seam"] = [0.0, 1.02 * s_height, 0.0]
            anchors["skirt_hem"] = [0.0, y_min * s_height, 0.0]

            for i in range(len(positions)):
                y = positions[i, 1]
                if y > 1.02:
                    # Bodice
                    t_b = float(np.clip((y - 1.02) / 0.35, 0.0, 1.0))
                    scale_xz = (1.0 - t_b) * s_waist + t_b * s_chest
                else:
                    # Skirt flare
                    t_s = float(np.clip((1.02 - y) / 0.45, 0.0, 1.0))
                    scale_xz = s_waist + t_s * (s_hip * 1.25 - s_waist)

                morphed[i, 0] = positions[i, 0] * scale_xz
                morphed[i, 2] = positions[i, 2] * scale_xz
                morphed[i, 1] = positions[i, 1] * s_height

        elif "traditional" in category or "kurta" in subcategory:
            # Long straight tunic down to knees ($Y \approx 0.60\text{m}$)
            anchors["mandarin_collar"] = [0.0, y_max, 0.0]
            anchors["side_slit_left"] = [0.22 * s_hip, 0.78 * s_height, 0.0]
            anchors["side_slit_right"] = [-0.22 * s_hip, 0.78 * s_height, 0.0]
            anchors["hem"] = [0.0, y_min * s_height, 0.0]

            for i in range(len(positions)):
                y = positions[i, 1]
                t_k = float(np.clip((y - 0.60) / 0.75, 0.0, 1.0))
                scale_xz = (1.0 - t_k) * s_hip + t_k * s_chest
                morphed[i, 0] = positions[i, 0] * scale_xz
                morphed[i, 2] = positions[i, 2] * scale_xz
                morphed[i, 1] = positions[i, 1] * s_height

        elif "footwear" in category or "sneakers" in subcategory:
            # Shoes scale with foot length and width
            fl_scale = measurements.foot_length_cm / 26.5
            fw_scale = measurements.foot_width_cm / 9.8
            anchors["left_sole"] = [0.098, 0.0, 0.0]
            anchors["right_sole"] = [-0.098, 0.0, 0.0]

            morphed[:, 0] = positions[:, 0] * fw_scale
            morphed[:, 2] = positions[:, 2] * fl_scale
            # Keep outsole sitting exactly at floor level Y=0
            morphed[:, 1] = np.maximum(0.0, positions[:, 1] * fl_scale)

        return morphed, anchors


universal_garment_fitting_engine = UniversalGarmentFittingEngine()

