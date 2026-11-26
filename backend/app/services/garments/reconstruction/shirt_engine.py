"""
YORVYN — Shirt 3D Garment Reconstruction Engine
Reconstructs formal button-downs, casual shirts, and polo shirts with authentic
architectural garment features:
- Upright Collar Stand
- Folded Collar Points (Spread or Button-Down)
- Vertical Raised Front Placket Band
- Barrel Sleeve Cuffs (Left & Right)
- Upper Back Shoulder Yoke
- Full-length Articulated Sleeves
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


class ShirtReconstructionEngine(IGarmentReconstructionEngine):
    """Engine for formal and casual button-down shirts, oxford shirts, and polo shirts."""

    @property
    def engine_id(self) -> str:
        return "shirt_pattern_engine_v1"

    @property
    def supported_categories(self) -> List[str]:
        return ["tops", "shirts", "formal_wear"]

    @property
    def supported_subcategories(self) -> List[str]:
        return ["formal_shirt", "casual_shirt", "oversized_shirt", "oxford_shirt", "shirt", "button_down", "polo_shirt"]

    def reconstruct(
        self,
        intelligence: Optional[GarmentIntelligenceV2Result] = None,
        category: str = "tops",
        subcategory: str = "formal_shirt",
        sleeve_length: str = "long",
        neckline_type: str = "collared",
        fit: str = "slim",
        front_image: Optional[Any] = None,
        back_image: Optional[Any] = None,
        **kwargs
    ) -> ReconstructionOutput:
        start_t = time.perf_counter()

        proportions = GarmentProportionsEstimator.estimate(
            category=category,
            subcategory=subcategory,
            fit=fit,
            intelligence=intelligence
        )
        margin = proportions.ease_margin_m

        top_y = 1.42
        hem_y = 0.88
        if intelligence and hasattr(intelligence, "landmarks") and intelligence.landmarks:
            lm = intelligence.landmarks
            if "collar_center" in lm:
                top_y = float(np.clip(1.42 + (0.05 - lm["collar_center"].position.y) * 0.10, 1.38, 1.45))
            if "hem_center" in lm:
                hem_y = float(np.clip(0.88 + (0.95 - lm["hem_center"].position.y) * 0.15, 0.82, 0.95))

        verts: List[List[float]] = []
        norms: List[List[float]] = []
        uvs: List[List[float]] = []
        tris: List[List[int]] = []
        panels: List[PanelGeometry] = []

        # 1. Torso Panels (Chest down to Hem) with Anatomical Curvature
        n_torso_rings = 24
        n_seg = 28
        torso_start_v = len(verts)
        torso_start_t = len(tris)
        ring_starts: List[int] = []

        sil_scales, sil_offsets = extract_silhouette_profile(front_image, n_torso_rings)

        for ring_idx in range(n_torso_rings):
            t = ring_idx / (n_torso_rings - 1)
            ring_starts.append(len(verts))

            y = top_y - t * (top_y - hem_y)
            if t < 0.20:
                frac_c = t / 0.20
                rx = (0.170 + 0.015 * frac_c) + margin
                rz = (0.110 + 0.012 * frac_c) + margin
            elif t < 0.55:
                frac_w = (t - 0.20) / 0.35
                rx = (0.185 - 0.025 * math.sin(frac_w * math.pi * 0.5)) + margin
                rz = (0.122 - 0.014 * math.sin(frac_w * math.pi * 0.5)) + margin
            elif t < 0.85:
                frac_h = (t - 0.55) / 0.30
                rx = (0.160 + 0.018 * math.sin(frac_h * math.pi * 0.5)) + margin
                rz = (0.108 + 0.012 * math.sin(frac_h * math.pi * 0.5)) + margin
            else:
                frac_b = (t - 0.85) / 0.15
                rx = (0.178 + 0.010 * frac_b) + margin
                rz = (0.120 + 0.006 * frac_b) + margin

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

                px = rx * cos_t + c_offset_x
                pz = rz * sin_t
                py = y

                nx, nz = cos_t, sin_t
                ny = 0.0
                norm_len = math.hypot(nx, ny, nz) or 1.0

                verts.append([px, py, pz])
                norms.append([nx / norm_len, ny / norm_len, nz / norm_len])

                if pz >= 0:
                    theta_front = theta if theta <= math.pi else (2.0 * math.pi - theta)
                    u = 0.04 + (0.42 * (1.0 - theta_front / math.pi))
                else:
                    theta_back = (theta - math.pi) if theta >= math.pi else (math.pi - theta)
                    u = 0.54 + (0.42 * (theta_back / math.pi))
                v = 0.48 + t * 0.48
                uvs.append([u, v])

        for r in range(n_torso_rings - 1):
            add_quad_strip(tris, ring_starts[r], ring_starts[r + 1], n_seg, closed=True)

        torso_v_cnt = len(verts) - torso_start_v
        torso_t_cnt = len(tris) - torso_start_t
        panels.append(PanelGeometry("front_torso_panel", torso_start_v, torso_v_cnt // 2, torso_start_t, torso_t_cnt // 2, True))
        panels.append(PanelGeometry("back_torso_panel", torso_start_v + torso_v_cnt // 2, torso_v_cnt // 2, torso_start_t + torso_t_cnt // 2, torso_t_cnt // 2, back_image is not None))

        # 2. Upright Collar Stand & Folded Collar Points
        collar_start_v = len(verts)
        collar_start_t = len(tris)
        collar_stand_rings = 4
        collar_seg = 20
        stand_h = 0.032
        base_rx, base_rz = 0.085 + margin * 0.5, 0.088 + margin * 0.5

        for cr in range(collar_stand_rings):
            frac = cr / (collar_stand_rings - 1)
            cy = top_y + frac * stand_h
            # Collar flares outward slightly at points
            crx = base_rx * (1.0 + frac * 0.12)
            crz = base_rz * (1.0 + frac * 0.12)

            for i in range(collar_seg):
                th = -0.45 * math.pi + (i / (collar_seg - 1)) * (1.90 * math.pi)
                cx = crx * math.sin(th)
                cz = crz * math.cos(th)

                # Collar point fold-down on front tips
                if math.cos(th) > 0.4:
                    cy_mod = cy - frac * 0.018 * math.cos(th)
                else:
                    cy_mod = cy

                verts.append([cx, cy_mod, cz])
                norms.append([cx / crx, 0.2, cz / crz])
                # Canonical island: [0.20, 0.80] x [0.04, 0.16]
                uvs.append([0.20 + (i / (collar_seg - 1)) * 0.60, 0.04 + frac * 0.12])

        for cr in range(collar_stand_rings - 1):
            r_c = collar_start_v + cr * collar_seg
            r_n = collar_start_v + (cr + 1) * collar_seg
            add_quad_strip(tris, r_c, r_n, collar_seg, closed=False)

        collar_v_cnt = len(verts) - collar_start_v
        collar_t_cnt = len(tris) - collar_start_t
        panels.append(PanelGeometry("collar_stand_and_points", collar_start_v, collar_v_cnt, collar_start_t, collar_t_cnt, True))

        # 3. Vertical Raised Front Placket Band
        placket_start_v = len(verts)
        placket_start_t = len(tris)
        placket_slices = 12
        placket_w = 0.022
        p_z = 0.122 + margin + 0.005  # Raised 5mm relief

        for s in range(placket_slices + 1):
            frac_s = s / placket_slices
            py = hem_y + frac_s * (top_y - hem_y)
            # Left and right edge of placket strip
            verts.append([-placket_w, py, p_z])
            norms.append([0.0, 0.0, 1.0])
            # Placket island: [0.48, 0.52] x [0.48, 0.96]
            uvs.append([0.48, 0.96 - frac_s * 0.48])

            verts.append([placket_w, py, p_z])
            norms.append([0.0, 0.0, 1.0])
            uvs.append([0.52, 0.96 - frac_s * 0.48])

        for s in range(placket_slices):
            v0 = placket_start_v + s * 2
            v1 = v0 + 1
            v2 = v0 + 3
            v3 = v0 + 2
            add_quad(tris, v0, v1, v2, v3)

        placket_v_cnt = len(verts) - placket_start_v
        placket_t_cnt = len(tris) - placket_start_t
        panels.append(PanelGeometry("front_placket_band", placket_start_v, placket_v_cnt, placket_start_t, placket_t_cnt, True))

        # 4. Long Sleeves with Barrel Cuffs
        arm_reach = 0.50
        n_arm_rings = 10
        arm_r_shoulder = 0.065 + margin * 0.7
        arm_r_cuff = 0.046 + margin * 0.6
        arm_seg = 20

        arm_configs = [
            ("left_sleeve_and_cuff", 1.0, CANONICAL_SHOULDER_ORIGIN_LEFT, CANONICAL_ARM_DIR_LEFT),
            ("right_sleeve_and_cuff", -1.0, CANONICAL_SHOULDER_ORIGIN_RIGHT, CANONICAL_ARM_DIR_RIGHT)
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
                # Raised cuff band on last ring
                is_cuff = frac > 0.88
                radius = (arm_r_cuff + 0.004) if is_cuff else (arm_r_shoulder + (arm_r_cuff - arm_r_shoulder) * frac)

                for i in range(arm_seg):
                    phi = 2.0 * math.pi * i / arm_seg
                    p = center + (arm_right * math.cos(phi) + arm_up * math.sin(phi)) * radius
                    n = arm_right * math.cos(phi) + arm_up * math.sin(phi)

                    verts.append(p.tolist())
                    norms.append(n.tolist())

                    # Sleeve islands: Left [0.04, 0.46] x [0.24, 0.44], Right [0.54, 0.96] x [0.24, 0.44]
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

        # 5. Finalize Geometry & Normals
        pos_np = np.array(verts, dtype=np.float32)
        idx_np = np.array(tris, dtype=np.uint32)
        norm_np = calculate_smooth_normals(pos_np, idx_np)
        uv_np = np.array(uvs, dtype=np.float32)

        # 6. Skeletal Rigging
        v_labels = assign_vertex_labels(
            len(pos_np),
            [
                ("left_sleeve", arm_configs_tracking[0][0], n_arm_rings * arm_seg),
                ("right_sleeve", arm_configs_tracking[1][0], n_arm_rings * arm_seg),
            ],
            default="torso"
        )
        joint_indices, joint_weights = compute_torso_skinning(
            pos_np, hem_y=hem_y, top_y=top_y, has_hood=False, component_labels=v_labels
        )
        mesh = GarmentMesh(pos_np, norm_np, uv_np, idx_np, joint_indices, joint_weights)

        # 7. Quality & Provenance
        quality_report = GarmentMeshValidator.validate(mesh)
        observed_mask = identify_observed_surface(pos_np, has_back_view=(back_image is not None))
        obs_count = int(np.sum(observed_mask))
        inf_count = len(pos_np) - obs_count
        obs_ratio = round(obs_count / max(1, len(pos_np)), 3)

        # 8. Multi-Component Graph Construction
        graph = GarmentComponentGraph()

        # 1. Main Torso
        b_min, b_max, dims = compute_component_bounds(pos_np, torso_start_v, torso_v_cnt)
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
            vertex_range=(torso_start_v, torso_v_cnt),
            triangle_range=(torso_start_t, torso_t_cnt)
        ))

        # 2. Upright Collar Stand & Points
        b_min, b_max, dims = compute_component_bounds(pos_np, collar_start_v, collar_v_cnt)
        graph.add_node(GarmentComponentNode(
            component_id="collar_stand",
            category=category,
            semantic_type="collar",
            parent_id="main_torso",
            dimensions_m=dims,
            bounding_box_3d=(b_min, b_max),
            attachment_location="neckline_seam",
            material_assignment="main_shell",
            confidence=1.0,
            provenance="pattern_constructed",
            vertex_range=(collar_start_v, collar_v_cnt),
            triangle_range=(collar_start_t, collar_t_cnt)
        ))

        # 3. Front Placket Band
        b_min, b_max, dims = compute_component_bounds(pos_np, placket_start_v, placket_v_cnt)
        graph.add_node(GarmentComponentNode(
            component_id="front_placket_band",
            category=category,
            semantic_type="placket",
            parent_id="main_torso",
            dimensions_m=dims,
            bounding_box_3d=(b_min, b_max),
            attachment_location="front_centerline",
            material_assignment="main_shell",
            confidence=1.0,
            provenance="pattern_constructed",
            vertex_range=(placket_start_v, placket_v_cnt),
            triangle_range=(placket_start_t, placket_t_cnt)
        ))

        # 4. Sleeves & Barrel Cuffs
        for side_name, (side_v_start, side_t_start) in [
            ("left", arm_configs_tracking[0]),
            ("right", arm_configs_tracking[1])
        ]:
            slv_v_start = side_v_start
            slv_v_cnt = 8 * arm_seg
            slv_t_start = side_t_start
            slv_t_cnt = 7 * arm_seg * 2
            b_min, b_max, dims = compute_component_bounds(pos_np, slv_v_start, slv_v_cnt)
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
                vertex_range=(slv_v_start, slv_v_cnt),
                triangle_range=(slv_t_start, slv_t_cnt)
            ))

            cuff_v_start = side_v_start + 8 * arm_seg
            cuff_v_cnt = 2 * arm_seg
            cuff_t_start = side_t_start + 7 * arm_seg * 2
            cuff_t_cnt = 2 * arm_seg * 2
            b_min, b_max, dims = compute_component_bounds(pos_np, cuff_v_start, cuff_v_cnt)
            graph.add_node(GarmentComponentNode(
                component_id=f"{side_name}_cuff",
                category=category,
                semantic_type="cuff",
                parent_id=f"{side_name}_sleeve",
                dimensions_m=dims,
                bounding_box_3d=(b_min, b_max),
                attachment_location=f"wrist_{side_name}",
                material_assignment="main_shell",
                confidence=1.0,
                provenance="pattern_constructed",
                vertex_range=(cuff_v_start, cuff_v_cnt),
                triangle_range=(cuff_t_start, cuff_t_cnt)
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

