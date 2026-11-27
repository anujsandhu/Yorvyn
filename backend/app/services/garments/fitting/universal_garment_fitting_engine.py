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

        # 1. Avatar Body Measurements & Anatomical Envelope
        if custom_avatar_measurements:
            measurements = custom_avatar_measurements
        else:
            measurements = self.measurement_engine.get_profile(avatar_profile_id)

        is_valid, validation_issues = self.measurement_engine.validate_measurements(measurements)
        if not is_valid:
            warnings.extend(validation_issues)

        from .garment_asset_inspector import avatar_geometry_analyzer
        avatar_env = avatar_geometry_analyzer.analyze(
            avatar_profile_id=avatar_profile_id,
            custom_measurements=measurements.model_dump() if hasattr(measurements, "model_dump") else None,
        )

        # Measure actual incoming source mesh dimensions before scaling so oversized/eased inputs never double-bloat
        measured_dims = self._measure_incoming_garment_dimensions(mesh.positions, category=category, subcategory=subcategory)

        # 2. Size and Ease Intelligence (conditioned on measured source mesh vs avatar body)
        ease_analysis = self.ease_engine.calculate_ease(
            category=category,
            subcategory=subcategory,
            avatar_measurements=measurements,
            target_fit=target_fit,
            custom_garment_dimensions=measured_dims,
        )

        # 3. Category-Specific Non-Uniform Anatomical Morphing (GarmentFitPlanner + CategorySpecificFittingEngine)
        morphed_pos, anchor_points = self._apply_category_morphing(
            positions=mesh.positions,
            category=category,
            subcategory=subcategory,
            measurements=measurements,
            ease=ease_analysis,
            joint_indices=mesh.joint_indices,
            joint_weights=mesh.joint_weights,
            avatar_env=avatar_env,
        )

        # Update elliptical collision hulls & head/neck proxies to match avatar body profile
        scale_f = measurements.height_cm / 175.0
        bones = {spec[0]: np.array(spec[3], dtype=np.float32) * scale_f for spec in ARA_SKELETON_SPECS}
        self.collision_engine.update_hulls_from_avatar(bones, scale_factor=scale_f)

        cat_l = (category or "tops").lower()
        sub_l = (subcategory or "").lower()
        is_head_accessory = cat_l in {"headwear", "glasses"} or (
            cat_l == "accessories" and any(k in sub_l for k in ("hat", "cap", "beanie", "fedora", "glass", "headwear"))
        )

        # 4. Collision Detection & Penetration Prevention (with elliptical body + head/neck protection)
        collision_resolved_pos, collision_metrics = self.collision_engine.detect_and_resolve_collisions(
            positions=morphed_pos,
            indices=mesh.indices,
            min_clearance_m=0.0035,
            exclude_head=is_head_accessory,
        )

        # 5. Cloth Simulation & Dynamic Draping
        draped_pos, physics_metrics = self.physics_engine.simulate_draping(
            positions=collision_resolved_pos,
            indices=mesh.indices,
            fabric_type=fabric_type,
            category=category,
            iterations=12
        )

        # Final post-drape anatomical clearance pass so draping never pulls vertices back through chest/head
        draped_pos, final_coll_metrics = self.collision_engine.detect_and_resolve_collisions(
            positions=draped_pos,
            indices=mesh.indices,
            min_clearance_m=0.0030,
            exclude_head=is_head_accessory,
        )
        if final_coll_metrics.penetration_count <= collision_metrics.penetration_count:
            collision_metrics = final_coll_metrics

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

    @staticmethod
    def _measure_incoming_garment_dimensions(
        positions: np.ndarray,
        *,
        category: str,
        subcategory: str = "",
    ) -> Dict[str, float]:
        """Measures actual mesh circumferences so ease scaling compares target body to real mesh extents."""
        base = dict(GarmentEaseEngine.CANONICAL_GARMENT_DIMENSIONS.get(
            subcategory,
            GarmentEaseEngine.CANONICAL_GARMENT_DIMENSIONS.get(category, GarmentEaseEngine.CANONICAL_GARMENT_DIMENSIONS["tops"]),
        ))
        if positions is None or len(positions) < 8:
            return base
        pos = np.asarray(positions, dtype=np.float32)

        def _ell_circ(band: np.ndarray, default_cm: float) -> float:
            if int(np.sum(band)) < 8:
                return default_cm
            pts = pos[band]
            rx = max(0.05, 0.5 * float(np.max(pts[:, 0]) - np.min(pts[:, 0])))
            rz = max(0.05, 0.5 * float(np.max(pts[:, 2]) - np.min(pts[:, 2])))
            perim_m = math.pi * (3.0 * (rx + rz) - math.sqrt(max(1e-6, (3.0 * rx + rz) * (rx + 3.0 * rz))))
            return round(max(45.0, min(180.0, perim_m * 100.0)), 2)

        core = np.abs(pos[:, 0]) <= 0.27
        base["measured_chest_cm"] = _ell_circ(core & (pos[:, 1] >= 1.15) & (pos[:, 1] <= 1.38), 102.0)
        base["measured_waist_cm"] = _ell_circ(core & (pos[:, 1] >= 0.94) & (pos[:, 1] <= 1.12), 84.0)
        base["measured_hip_cm"] = _ell_circ((np.abs(pos[:, 0]) <= 0.34) & (pos[:, 1] >= 0.78) & (pos[:, 1] <= 0.96), 104.0)
        sh_band = (pos[:, 1] >= 1.32) & (pos[:, 1] <= 1.44) & (np.abs(pos[:, 0]) <= 0.30)
        if int(np.sum(sh_band)) >= 8:
            base["measured_shoulder_width_cm"] = round(float(np.max(pos[sh_band, 0]) - np.min(pos[sh_band, 0])) * 100.0, 2)
        return base

    def _apply_category_morphing(
        self,
        positions: np.ndarray,
        category: str,
        subcategory: str,
        measurements: AvatarMeasurementsV2,
        ease: GarmentEaseAnalysisV2,
        joint_indices: Optional[np.ndarray] = None,
        joint_weights: Optional[np.ndarray] = None,
        avatar_env: Optional[Any] = None,
    ) -> Tuple[np.ndarray, Dict[str, List[float]]]:
        """
        Applies segment-specific non-uniform anatomical coordinate morphing tailored to each garment category.
        Regulates front/back Z depth independently from circumferential X scaling and uses bone masks when available.
        """
        morphed = np.copy(positions)
        scales = ease.segment_scale_factors
        s_shoulder = min(1.16, scales.get("shoulder", 1.0))
        s_chest = min(1.14, scales.get("chest", 1.0))
        s_waist = min(1.14, scales.get("waist", 1.0))
        s_hip = min(1.16, scales.get("hip", 1.0))
        s_height = scales.get("height", 1.0)

        anchors: Dict[str, List[float]] = {}
        y_vals = positions[:, 1]
        y_min, y_max = float(np.min(y_vals)), float(np.max(y_vals))
        cat_l = (category or "tops").lower()
        sub_l = (subcategory or "").lower()

        chest_z_ctr = float(getattr(avatar_env, "chest_z_center", 0.050))
        target_chest_depth = float(getattr(avatar_env, "chest_depth_m", 0.237)) * 1.15

        arm_mask = np.zeros(len(positions), dtype=bool)
        if joint_indices is not None and joint_weights is not None and len(joint_indices) == len(positions):
            arm_bones = {6, 7, 8, 10, 11, 12}
            arm_w = np.sum(np.where(np.isin(joint_indices, list(arm_bones)), joint_weights, 0.0), axis=1)
            arm_mask = arm_w > 0.45

        if any(k in cat_l or k in sub_l for k in ("top", "shirt", "hoodie", "jacket", "outerwear", "blazer", "sweater", "coat")):
            anchors["neckline"] = [0.0, y_max, chest_z_ctr]
            anchors["shoulder_left"] = [0.20 * s_shoulder, min(y_max, 1.38 * s_height), chest_z_ctr]
            anchors["shoulder_right"] = [-0.20 * s_shoulder, min(y_max, 1.38 * s_height), chest_z_ctr]
            anchors["hem"] = [0.0, y_min, chest_z_ctr]

            core_mask = (~arm_mask) & (positions[:, 1] >= 0.90) & (positions[:, 1] <= 1.40) & (np.abs(positions[:, 0]) <= 0.28)
            cur_core_z = float(np.max(positions[core_mask, 2]) - np.min(positions[core_mask, 2])) if np.any(core_mask) else target_chest_depth
            z_src_ctr = float(0.5 * (np.max(positions[core_mask, 2]) + np.min(positions[core_mask, 2]))) if np.any(core_mask) else 0.0
            s_depth_z = min(s_chest, max(0.68, min(1.06, (target_chest_depth + 0.03) / max(cur_core_z, 0.16))))

            for i in range(len(positions)):
                x, y, z = positions[i, 0], positions[i, 1], positions[i, 2]
                t_torso = float(np.clip((y - 0.88) / 0.50, 0.0, 1.0))
                scale_x = (1.0 - t_torso) * s_waist + t_torso * s_chest
                if y > 1.30:
                    t_sh = float(np.clip((y - 1.30) / 0.15, 0.0, 1.0))
                    scale_x = (1.0 - t_sh) * scale_x + t_sh * s_shoulder

                if arm_mask[i] or (y < 1.36 and abs(x) > 0.23):
                    x_sh = math.copysign(0.20, x)
                    morphed[i, 0] = x_sh * s_shoulder + (x - x_sh) * min(1.05, s_chest)
                    morphed[i, 2] = z_src_ctr + (z - z_src_ctr) * min(1.05, s_chest)
                elif y > 1.42:
                    morphed[i, 0] = x
                    morphed[i, 2] = z
                else:
                    morphed[i, 0] = x * scale_x
                    morphed[i, 2] = (z_src_ctr + (z - z_src_ctr) * s_depth_z) * 0.65 + (chest_z_ctr + (z - z_src_ctr) * s_depth_z) * 0.35

                morphed[i, 1] = 0.88 + (y - 0.88) * s_height

        elif any(k in cat_l or k in sub_l for k in ("bottom", "jeans", "trouser", "chino", "pant", "short")):
            anchors["waistband"] = [0.0, y_max, 0.02]
            anchors["crotch"] = [0.0, 0.78 * s_height, 0.02]
            anchors["ankle_left"] = [0.098, y_min, 0.0]
            anchors["ankle_right"] = [-0.098, y_min, 0.0]

            s_z_bot = min(1.06, s_hip)
            for i in range(len(positions)):
                y = positions[i, 1]
                if y > 0.85:
                    t_p = float(np.clip((y - 0.85) / 0.14, 0.0, 1.0))
                    scale_x = (1.0 - t_p) * s_hip + t_p * s_waist
                else:
                    t_leg = float(np.clip((y - 0.10) / 0.75, 0.0, 1.0))
                    scale_x = (1.0 - t_leg) * 1.0 + t_leg * min(1.08, s_hip)

                morphed[i, 0] = positions[i, 0] * min(1.10, scale_x)
                morphed[i, 2] = positions[i, 2] * s_z_bot
                morphed[i, 1] = positions[i, 1] * s_height

        elif "dress" in cat_l or "skirt" in cat_l or "dress" in sub_l or "skirt" in sub_l:
            anchors["waist_seam"] = [0.0, 1.02 * s_height, chest_z_ctr * 0.6]
            anchors["skirt_hem"] = [0.0, y_min * s_height, 0.02]

            cur_z_span = max(0.18, float(np.max(positions[:, 2]) - np.min(positions[:, 2])))
            max_skirt_z = 0.36
            s_z_cap = max(0.68, min(1.02, max_skirt_z / cur_z_span))

            for i in range(len(positions)):
                y = positions[i, 1]
                if y > 1.02:
                    t_b = float(np.clip((y - 1.02) / 0.35, 0.0, 1.0))
                    scale_x = (1.0 - t_b) * min(1.08, s_waist) + t_b * min(1.10, s_chest)
                    scale_z = min(scale_x, s_z_cap)
                else:
                    t_s = float(np.clip((1.02 - y) / 0.45, 0.0, 1.0))
                    scale_x = min(1.12, s_waist + t_s * max(0.0, min(1.12, s_hip) - s_waist))
                    scale_z = min(1.02, s_z_cap)

                morphed[i, 0] = positions[i, 0] * scale_x
                morphed[i, 2] = positions[i, 2] * scale_z
                morphed[i, 1] = positions[i, 1] * s_height

        elif "traditional" in cat_l or "kurta" in sub_l or "sherwani" in sub_l:
            anchors["mandarin_collar"] = [0.0, y_max, chest_z_ctr]
            anchors["side_slit_left"] = [0.22 * min(1.10, s_hip), 0.78 * s_height, 0.02]
            anchors["side_slit_right"] = [-0.22 * min(1.10, s_hip), 0.78 * s_height, 0.02]
            anchors["hem"] = [0.0, y_min * s_height, 0.02]

            for i in range(len(positions)):
                y = positions[i, 1]
                t_k = float(np.clip((y - 0.60) / 0.75, 0.0, 1.0))
                scale_x = min(1.10, (1.0 - t_k) * s_hip + t_k * s_chest)
                morphed[i, 0] = positions[i, 0] * scale_x
                morphed[i, 2] = positions[i, 2] * min(1.02, scale_x)
                morphed[i, 1] = positions[i, 1] * s_height

        elif "footwear" in cat_l or any(k in sub_l for k in ("sneaker", "boot", "shoe", "sandal")):
            fl_scale = measurements.foot_length_cm / 26.5
            fw_scale = measurements.foot_width_cm / 9.8
            anchors["left_sole"] = [0.098, 0.0, 0.0]
            anchors["right_sole"] = [-0.098, 0.0, 0.0]
            morphed[:, 0] = positions[:, 0] * fw_scale
            morphed[:, 2] = positions[:, 2] * fl_scale
            morphed[:, 1] = np.maximum(0.0, positions[:, 1] * fl_scale)

        elif "headwear" in cat_l or any(k in sub_l for k in ("hat", "cap", "beanie", "fedora", "headwear")):
            head_y = float(getattr(avatar_env, "head_center", [0.0, 1.585, 0.056])[1])
            head_z = float(getattr(avatar_env, "head_center", [0.0, 1.585, 0.056])[2])
            anchors["head_crown"] = [0.0, head_y + 0.08, head_z]
            cur_y = float(0.5 * (y_min + y_max))
            dy = (head_y + 0.06) - cur_y
            if abs(dy) > 0.12:
                morphed[:, 1] = positions[:, 1] + dy
            morphed[:, 2] = (positions[:, 2] - float(np.mean(positions[:, 2]))) + head_z

        elif "glass" in cat_l or "glass" in sub_l or "eyewear" in sub_l:
            head_y = float(getattr(avatar_env, "head_center", [0.0, 1.585, 0.056])[1])
            anchors["nose_bridge"] = [0.0, head_y + 0.01, 0.155]
            morphed[:, 1] = (positions[:, 1] - float(np.mean(positions[:, 1]))) + (head_y + 0.01)
            morphed[:, 2] = (positions[:, 2] - float(np.mean(positions[:, 2]))) + 0.145

        elif "belt" in cat_l or "belt" in sub_l:
            waist_y = float(getattr(avatar_env, "waist_center_y", 1.04))
            anchors["waist_belt"] = [0.0, waist_y, 0.05]
            morphed[:, 0] = positions[:, 0] * min(1.12, s_waist)
            morphed[:, 2] = positions[:, 2] * min(1.08, s_waist)
            morphed[:, 1] = (positions[:, 1] - float(np.mean(positions[:, 1]))) + waist_y

        elif "bag" in cat_l or any(k in sub_l for k in ("bag", "backpack", "tote", "purse")):
            anchors["shoulder_strap"] = [0.18, 1.38 * s_height, 0.04]
            morphed[:, 1] = positions[:, 1] * s_height

        elif any(k in cat_l or k in sub_l for k in ("jewel", "watch", "scarf", "glove", "accessor")):
            anchors["accessory_mount"] = [0.0, 1.40 * s_height, 0.04]
            morphed[:, 1] = positions[:, 1] * s_height

        return morphed, anchors


universal_garment_fitting_engine = UniversalGarmentFittingEngine()
garment_fit_planner = universal_garment_fitting_engine
category_specific_fitting_engine = universal_garment_fitting_engine

