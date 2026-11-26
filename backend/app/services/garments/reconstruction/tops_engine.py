"""
YORVYN — Tops 3D Garment Reconstruction Engine
Reconstructs wearable upper body garments (T-shirts, sweaters, sweatshirts, tank tops)
with authentic pattern-based panel topology:
- Front Torso Panel (with anatomical chest curvature)
- Back Torso Panel (with spinal contour)
- Left and Right Sleeves (stitched along canonical Ara 3D A-pose armscyes)
- Neck Opening & Collar Rim
- Sleeve Openings & Lower Hem Loop
"""

import time
import math
from typing import List, Tuple, Dict, Any, Optional
import numpy as np

from backend.app.services.garments.garment_mesh_builder import (
    GarmentMesh,
    CANONICAL_ARM_DIR_LEFT,
    CANONICAL_ARM_DIR_RIGHT,
    CANONICAL_SHOULDER_ORIGIN_LEFT,
    CANONICAL_SHOULDER_ORIGIN_RIGHT
)
from backend.app.models.garment_intelligence_models import GarmentIntelligenceV2Result
from .base_reconstruction_engine import (
    IGarmentReconstructionEngine,
    ReconstructionOutput,
    PanelGeometry,
    GarmentComponentNode,
    GarmentComponentGraph,
    compute_component_bounds
)
from .geometry_utils import (
    calculate_smooth_normals,
    add_quad,
    add_quad_strip,
    assign_vertex_labels,
    compute_torso_skinning,
    identify_observed_surface,
    extract_silhouette_profile
)
from .mesh_validator import GarmentMeshValidator
from .proportions import GarmentProportionsEstimator


class TopsReconstructionEngine(IGarmentReconstructionEngine):
    """Engine for reconstructing standard tops, T-shirts, sweaters, and tank tops."""

    @property
    def engine_id(self) -> str:
        return "tops_pattern_engine_v1"

    @property
    def supported_categories(self) -> List[str]:
        return ["tops", "top", "upper_body"]

    @property
    def supported_subcategories(self) -> List[str]:
        return ["tshirt", "sweatshirt", "sweater", "tank_top", "crop_top", "long_sleeve", "polo_shirt"]

    def reconstruct(
        self,
        intelligence: Optional[GarmentIntelligenceV2Result] = None,
        category: str = "tops",
        subcategory: str = "tshirt",
        sleeve_length: str = "short",
        neckline_type: str = "crewneck",
        fit: str = "regular",
        front_image: Optional[Any] = None,
        back_image: Optional[Any] = None,
        **kwargs
    ) -> ReconstructionOutput:
        start_t = time.perf_counter()

        # 1. Proportions & Physical Ease
        proportions = GarmentProportionsEstimator.estimate(
            category=category,
            subcategory=subcategory,
            fit=fit,
            intelligence=intelligence
        )
        margin = proportions.ease_margin_m

        # Dynamic landmark adjustments
        top_y = 1.42
        hem_y = 0.90
        if intelligence and hasattr(intelligence, "landmarks") and intelligence.landmarks:
            lm = intelligence.landmarks
            if "collar_center" in lm:
                top_y = float(np.clip(1.42 + (0.05 - lm["collar_center"].position.y) * 0.10, 1.38, 1.45))
            if "hem_center" in lm:
                hem_y = float(np.clip(0.90 + (0.95 - lm["hem_center"].position.y) * 0.15, 0.82, 0.98))

        if subcategory == "crop_top":
            hem_y = 1.10

        verts: List[List[float]] = []
        norms: List[List[float]] = []
        uvs: List[List[float]] = []
        tris: List[List[int]] = []
        panels: List[PanelGeometry] = []

        # 2. Torso Pattern Rings (Clavicle down to Hem) with Anatomical Curvature
        n_torso_rings = 14
        n_seg = 28
        torso_start_v = len(verts)
        torso_start_t = len(tris)
        ring_starts: List[int] = []

        sil_scales, sil_offsets = extract_silhouette_profile(front_image, n_torso_rings)

        for ring_idx in range(n_torso_rings):
            t = ring_idx / (n_torso_rings - 1) # 0.0 (collar/clavicle) to 1.0 (hem)
            ring_starts.append(len(verts))

            # Anatomical vertical distribution and cross-section curves
            y = top_y - t * (top_y - hem_y)
            if t < 0.20:
                # Upper chest / Clavicle to bust
                frac_chest = t / 0.20
                rx = (0.175 + 0.015 * frac_chest) + margin
                rz = (0.115 + 0.012 * frac_chest) + margin
            elif t < 0.55:
                # Bust to natural waist taper
                frac_waist = (t - 0.20) / 0.35
                rx = (0.190 - 0.022 * math.sin(frac_waist * math.pi * 0.5)) + margin
                rz = (0.127 - 0.015 * math.sin(frac_waist * math.pi * 0.5)) + margin
            elif t < 0.85:
                # Waist to upper hip flare
                frac_hip = (t - 0.55) / 0.30
                rx = (0.168 + 0.018 * math.sin(frac_hip * math.pi * 0.5)) + margin
                rz = (0.112 + 0.014 * math.sin(frac_hip * math.pi * 0.5)) + margin
            else:
                # Lower hem flare
                frac_hem = (t - 0.85) / 0.15
                rx = (0.186 + 0.008 * frac_hem) + margin
                rz = (0.126 + 0.006 * frac_hem) + margin

            if sil_scales is not None:
                s_factor = float(sil_scales[ring_idx])
                rx = rx * s_factor
                rz = rz * (0.6 + 0.4 * s_factor)
                c_offset_x = float(sil_offsets[ring_idx])
            else:
                c_offset_x = 0.0

            for i in range(n_seg):
                theta = 2.0 * math.pi * i / n_seg
                cos_t = math.cos(theta)
                sin_t = math.sin(theta)

                y_mod = y
                # Realistic neckline scoop on top ring
                if ring_idx == 0 and sin_t > 0:
                    dip = 0.045 if neckline_type == "v_neck" else 0.025
                    y_mod -= dip * (sin_t ** 2)

                px = rx * cos_t + c_offset_x
                pz = rz * sin_t
                py = y_mod

                # Normal hint
                nx, nz = cos_t, sin_t
                ny = 0.0
                norm_len = math.hypot(nx, ny, nz) or 1.0

                verts.append([px, py, pz])
                norms.append([nx / norm_len, ny / norm_len, nz / norm_len])

                # Canonical UV layout: Front Island [0.04, 0.46] x [0.48, 0.96]
                # Back Island [0.54, 0.96] x [0.48, 0.96]
                if pz >= 0:
                    theta_front = theta if theta <= math.pi else (2.0 * math.pi - theta)
                    u = 0.04 + (0.42 * (1.0 - theta_front / math.pi))
                else:
                    theta_back = (theta - math.pi) if theta >= math.pi else (math.pi - theta)
                    u = 0.54 + (0.42 * (theta_back / math.pi))
                # Top ring (ring_idx 0) maps to v=0.48; Hem ring maps to v=0.96
                v = 0.48 + t * 0.48
                uvs.append([u, v])

        # Connect Torso rings
        for r in range(n_torso_rings - 1):
            add_quad_strip(tris, ring_starts[r], ring_starts[r + 1], n_seg, closed=True)

        torso_v_cnt = len(verts) - torso_start_v
        torso_t_cnt = len(tris) - torso_start_t
        panels.append(PanelGeometry("front_torso_panel", torso_start_v, torso_v_cnt // 2, torso_start_t, torso_t_cnt // 2, True))
        panels.append(PanelGeometry("back_torso_panel", torso_start_v + torso_v_cnt // 2, torso_v_cnt // 2, torso_start_t + torso_t_cnt // 2, torso_t_cnt // 2, back_image is not None))

        # 3. Sleeves Construction (Sleeveless / Short / Long)
        is_sleeveless = subcategory == "tank_top" or sleeve_length == "sleeveless"
        is_long = sleeve_length == "long" or subcategory in ["long_sleeve", "sweater", "sweatshirt"]

        if not is_sleeveless:
            arm_reach = 0.48 if is_long else 0.18
            n_arm_rings = 10 if is_long else 6
            arm_r_shoulder = 0.065 + margin * 0.7
            arm_r_cuff = 0.045 + margin * 0.6 if is_long else 0.058 + margin * 0.7
            arm_seg = 20

            arm_configs = [
                ("left_sleeve", 1.0, CANONICAL_SHOULDER_ORIGIN_LEFT, CANONICAL_ARM_DIR_LEFT),
                ("right_sleeve", -1.0, CANONICAL_SHOULDER_ORIGIN_RIGHT, CANONICAL_ARM_DIR_RIGHT)
            ]
            arm_configs_tracking = []

            for panel_name, side, shoulder_origin, arm_dir in arm_configs:
                arm_start_v = len(verts)
                arm_start_t = len(tris)
                arm_configs_tracking.append((arm_start_v, arm_start_t))

                up_hint = np.array([0.0, 0.0, 1.0], dtype=np.float32)
                arm_right = np.cross(arm_dir, up_hint)
                arm_right = arm_right / (np.linalg.norm(arm_right) or 1.0)
                arm_up = np.cross(arm_right, arm_dir)

                for r in range(n_arm_rings):
                    frac = r / (n_arm_rings - 1)
                    center = shoulder_origin + arm_dir * (frac * arm_reach)
                    radius = arm_r_shoulder + (arm_r_cuff - arm_r_shoulder) * frac

                    for i in range(arm_seg):
                        phi = 2.0 * math.pi * i / arm_seg
                        p = center + (arm_right * math.cos(phi) + arm_up * math.sin(phi)) * radius
                        n = arm_right * math.cos(phi) + arm_up * math.sin(phi)

                        verts.append(p.tolist())
                        norms.append(n.tolist())

                        # Left sleeve island [0.04, 0.46] x [0.24, 0.44]
                        # Right sleeve island [0.54, 0.96] x [0.24, 0.44]
                        u = (0.04 if side > 0 else 0.54) + 0.42 * (i / arm_seg)
                        v = 0.24 + 0.20 * frac
                        uvs.append([u, v])

                for r in range(n_arm_rings - 1):
                    r_curr = arm_start_v + r * arm_seg
                    r_next = arm_start_v + (r + 1) * arm_seg
                    add_quad_strip(tris, r_curr, r_next, arm_seg, closed=True)

                arm_v_cnt = len(verts) - arm_start_v
                arm_t_cnt = len(tris) - arm_start_t
                panels.append(PanelGeometry(panel_name, arm_start_v, arm_v_cnt, arm_start_t, arm_t_cnt, True))

        # 4. Finalize Arrays and Normal Calculations
        pos_np = np.array(verts, dtype=np.float32)
        idx_np = np.array(tris, dtype=np.uint32)
        norm_np = calculate_smooth_normals(pos_np, idx_np)
        uv_np = np.array(uvs, dtype=np.float32)

        # 5. Skeletal Rigging (Ara 3D Gen 20 Bones)
        label_spans = []
        if not is_sleeveless:
            label_spans.extend([
                ("left_sleeve", arm_configs_tracking[0][0], n_arm_rings * arm_seg),
                ("right_sleeve", arm_configs_tracking[1][0], n_arm_rings * arm_seg),
            ])
        v_labels = assign_vertex_labels(len(pos_np), label_spans, default="torso")
        joint_indices, joint_weights = compute_torso_skinning(
            pos_np, hem_y=hem_y, top_y=top_y, has_hood=False, component_labels=v_labels
        )

        mesh = GarmentMesh(pos_np, norm_np, uv_np, idx_np, joint_indices, joint_weights)

        # 6. Quality Validation
        quality_report = GarmentMeshValidator.validate(mesh)

        # 7. Surface Provenance
        observed_mask = identify_observed_surface(pos_np, has_back_view=(back_image is not None))
        obs_count = int(np.sum(observed_mask))
        inf_count = len(pos_np) - obs_count
        obs_ratio = round(obs_count / max(1, len(pos_np)), 3)

        # 8. Multi-Component Graph Construction
        graph = GarmentComponentGraph()

        # 1. Main Torso (rings 0..11)
        main_v_cnt = 12 * n_seg
        main_t_cnt = 11 * n_seg * 2
        b_min, b_max, dims = compute_component_bounds(pos_np, 0, main_v_cnt)
        graph.add_node(GarmentComponentNode(
            component_id="main_torso",
            category=category,
            semantic_type="torso",
            parent_id=None,
            dimensions_m=dims,
            bounding_box_3d=(b_min, b_max),
            attachment_location="torso_root",
            material_assignment="main_shell",
            confidence=1.0,
            provenance="pattern_constructed",
            vertex_range=(0, main_v_cnt),
            triangle_range=(0, main_t_cnt)
        ))

        # 2. Hem Loop (rings 11..13)
        hem_v_cnt = 2 * n_seg
        hem_t_cnt = 2 * n_seg * 2
        b_min, b_max, dims = compute_component_bounds(pos_np, main_v_cnt, hem_v_cnt)
        graph.add_node(GarmentComponentNode(
            component_id="hem_loop",
            category=category,
            semantic_type="hem",
            parent_id="main_torso",
            dimensions_m=dims,
            bounding_box_3d=(b_min, b_max),
            attachment_location="hem_seam",
            material_assignment="main_shell",
            confidence=1.0,
            provenance="pattern_constructed",
            vertex_range=(main_v_cnt, hem_v_cnt),
            triangle_range=(main_t_cnt, hem_t_cnt)
        ))

        # 3. Sleeves
        if not is_sleeveless:
            for side_name, (side_v_start, side_t_start) in [
                ("left", arm_configs_tracking[0]),
                ("right", arm_configs_tracking[1])
            ]:
                slv_v_cnt = n_arm_rings * arm_seg
                slv_t_cnt = (n_arm_rings - 1) * arm_seg * 2
                b_min, b_max, dims = compute_component_bounds(pos_np, side_v_start, slv_v_cnt)
                graph.add_node(GarmentComponentNode(
                    component_id=f"{side_name}_sleeve",
                    category=category,
                    semantic_type="sleeve",
                    parent_id="main_torso",
                    dimensions_m=dims,
                    bounding_box_3d=(b_min, b_max),
                    attachment_location=f"shoulder_{side_name}",
                    material_assignment="main_shell",
                    confidence=1.0,
                    provenance="pattern_constructed",
                    vertex_range=(side_v_start, slv_v_cnt),
                    triangle_range=(side_t_start, slv_t_cnt)
                ))

        dur_ms = round((time.perf_counter() - start_t) * 1000.0, 2)

        return ReconstructionOutput(
            mesh=mesh,
            panels=panels,
            quality_report=quality_report,
            proportions=proportions,
            observed_vertex_count=obs_count,
            inferred_vertex_count=inf_count,
            observed_surface_ratio=obs_ratio,
            provenance="pattern_constructed",
            engine_id=self.engine_id,
            reconstruction_time_ms=dur_ms,
            component_graph=graph
        )

