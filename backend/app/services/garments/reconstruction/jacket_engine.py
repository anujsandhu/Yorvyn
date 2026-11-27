"""
YORVYN — Jacket 3D Garment Reconstruction Engine
Reconstructs outerwear, denim jackets, leather jackets, blazers, and coats with:
- Structured Shoulders & Outerwear Volume Envelope
- Notched / Peak Lapels & Upright Collar
- Front Center Split Opening
- Raised Zipper / Closure Track
- Articulated Sleeves with Structural Cuffs
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


class JacketReconstructionEngine(IGarmentReconstructionEngine):
    """Engine for jackets, coats, blazers, and structured outerwear."""

    @property
    def engine_id(self) -> str:
        return "jacket_pattern_engine_v1"

    @property
    def supported_categories(self) -> List[str]:
        return ["outerwear", "jackets", "coats", "blazers"]

    @property
    def supported_subcategories(self) -> List[str]:
        return ["jacket", "denim_jacket", "leather_jacket", "bomber_jacket", "blazer", "formal_coat", "trench_coat", "parka", "windbreaker"]

    def reconstruct(
        self,
        intelligence: Optional[GarmentIntelligenceV2Result] = None,
        category: str = "outerwear",
        subcategory: str = "jacket",
        sleeve_length: str = "long",
        neckline_type: str = "collared",
        fit: str = "regular",
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
        margin = proportions.ease_margin_m + 0.012  # Generous outerwear ease

        top_y = 1.43
        hem_y = 0.86
        if intelligence and hasattr(intelligence, "landmarks") and intelligence.landmarks:
            lm = intelligence.landmarks
            if "collar_center" in lm:
                top_y = float(np.clip(1.43 + (0.05 - lm["collar_center"].position.y) * 0.10, 1.39, 1.46))
            if "hem_center" in lm:
                hem_y = float(np.clip(0.86 + (0.95 - lm["hem_center"].position.y) * 0.15, 0.78, 0.94))

        verts: List[List[float]] = []
        norms: List[List[float]] = []
        uvs: List[List[float]] = []
        tris: List[List[int]] = []
        panels: List[PanelGeometry] = []

        # 1. Torso Panels (Structured chest, waist, hem with 24 continuous contour rings)
        n_torso_rings = 24
        kf_t = [0.00, 0.14, 0.32, 0.50, 0.70, 1.00]
        kf_rx = [0.182 + margin, 0.194 + margin, 0.186 + margin, 0.178 + margin, 0.190 + margin, 0.200 + margin]
        kf_rz = [0.118 + margin, 0.130 + margin, 0.124 + margin, 0.118 + margin, 0.126 + margin, 0.134 + margin]
        torso_rings_spec = [
            (
                top_y - (r_idx / (n_torso_rings - 1)) * (top_y - hem_y),
                float(np.interp(r_idx / (n_torso_rings - 1), kf_t, kf_rx)),
                float(np.interp(r_idx / (n_torso_rings - 1), kf_t, kf_rz)),
            )
            for r_idx in range(n_torso_rings)
        ]

        n_seg = 28
        torso_start_v = len(verts)
        torso_start_t = len(tris)
        ring_starts: List[int] = []
        ring_profiles: List[Tuple[float, float, float, float]] = []

        sil_scales, sil_offsets = extract_silhouette_profile(front_image, len(torso_rings_spec))

        for ring_idx, (y, rx, rz) in enumerate(torso_rings_spec):
            ring_starts.append(len(verts))
            v_coord = ring_idx / (len(torso_rings_spec) - 1)

            if sil_scales is not None:
                s_factor = float(sil_scales[ring_idx])
                rx = rx * s_factor
                rz = rz * (0.6 + 0.4 * s_factor)
                c_offset_x = float(sil_offsets[ring_idx])
            else:
                c_offset_x = 0.0

            ring_profiles.append((y, rx, rz, c_offset_x))

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
                v = 0.48 + v_coord * 0.48
                uvs.append([u, v])

        def get_front_torso_z(x_val: float, y_val: float) -> float:
            closest = min(ring_profiles, key=lambda rp: abs(rp[0] - y_val))
            _, rx_c, rz_c, cx_c = closest
            ratio = ((x_val - cx_c) / max(0.01, rx_c)) ** 2
            return rz_c * math.sqrt(max(0.0, 1.0 - ratio))

        for r in range(len(torso_rings_spec) - 1):
            add_quad_strip(tris, ring_starts[r], ring_starts[r + 1], n_seg, closed=True)

        torso_v_cnt = len(verts) - torso_start_v
        torso_t_cnt = len(tris) - torso_start_t
        panels.append(PanelGeometry("front_jacket_torso", torso_start_v, torso_v_cnt // 2, torso_start_t, torso_t_cnt // 2, True))
        panels.append(PanelGeometry("back_jacket_torso", torso_start_v + torso_v_cnt // 2, torso_v_cnt // 2, torso_start_t + torso_t_cnt // 2, torso_t_cnt // 2, back_image is not None))

        is_denim = any(k in subcategory.lower() for k in ("denim", "trucker", "jean_jacket"))

        if is_denim:
            # 2. Denim Point Collar (Pointed turndown collar with spread points)
            collar_start_v = len(verts)
            collar_start_t = len(tris)
            c_rings = 4
            c_seg = 14
            for cr in range(c_rings):
                frac = cr / (c_rings - 1)
                cy = top_y + 0.02 - frac * 0.12
                c_spread = 0.075 + frac * 0.050
                for side in [-1.0, 1.0]:
                    for s in range(c_seg // 2):
                        u_s = s / (c_seg // 2 - 1)
                        cx = side * (0.025 + u_s * c_spread)
                        cz = get_front_torso_z(cx, min(top_y, cy)) + 0.008 * (1.0 - 0.5 * u_s)
                        verts.append([cx, cy, cz])
                        norms.append([side * 0.15, 0.2, 0.96])
                        uvs.append([0.45 + side * 0.12 * u_s, 0.72 + frac * 0.20])

            for cr in range(c_rings - 1):
                r_c = collar_start_v + cr * c_seg
                r_n = collar_start_v + (cr + 1) * c_seg
                add_quad_strip(tris, r_c, r_n, c_seg, closed=False)

            collar_v_cnt = len(verts) - collar_start_v
            collar_t_cnt = len(tris) - collar_start_t
            panels.append(PanelGeometry("denim_point_collar", collar_start_v, collar_v_cnt, collar_start_t, collar_t_cnt, True))

            # 3. Front Center Button Placket Band (Metal shank button placket)
            placket_start_v = len(verts)
            placket_start_t = len(tris)
            placket_slices = 10
            placket_w = 0.018

            for s in range(placket_slices + 1):
                py = hem_y + (s / placket_slices) * (top_y - 0.08 - hem_y)
                z_elev = get_front_torso_z(0.0, py) + 0.005
                verts.append([-placket_w, py, z_elev])
                norms.append([0.0, 0.0, 1.0])
                uvs.append([0.48, 0.05 + (s / placket_slices) * 0.45])

                verts.append([placket_w, py, z_elev])
                norms.append([0.0, 0.0, 1.0])
                uvs.append([0.52, 0.05 + (s / placket_slices) * 0.45])

            for s in range(placket_slices):
                v0 = placket_start_v + s * 2
                v1 = v0 + 1
                v2 = v0 + 3
                v3 = v0 + 2
                add_quad(tris, v0, v1, v2, v3)

            placket_v_cnt = len(verts) - placket_start_v
            placket_t_cnt = len(tris) - placket_start_t
            panels.append(PanelGeometry("button_placket", placket_start_v, placket_v_cnt, placket_start_t, placket_t_cnt, True))

            # 4. Twin Chest Flap Pockets with Shank Rivet Detailing
            pocket_start_v = len(verts)
            pocket_start_t = len(tris)
            pw = 0.038
            ph = 0.040
            py_top = top_y - 0.16

            for side in [-1.0, 1.0]:
                cx = side * 0.075
                pz_pocket = get_front_torso_z(cx, py_top) + 0.006
                # Flap quad
                v_p0 = len(verts)
                verts.append([cx - pw, py_top, pz_pocket])
                verts.append([cx + pw, py_top, pz_pocket])
                verts.append([cx + pw, py_top - ph * 0.4, pz_pocket + 0.003])
                verts.append([cx - pw, py_top - ph * 0.4, pz_pocket + 0.003])
                for _ in range(4):
                    norms.append([side * 0.1, 0.1, 0.98])
                uvs.extend([[0.30, 0.60], [0.38, 0.60], [0.38, 0.65], [0.30, 0.65]])
                add_quad(tris, v_p0, v_p0 + 1, v_p0 + 2, v_p0 + 3)

                # Lower pocket body quad
                v_b0 = len(verts)
                pz_bot = get_front_torso_z(cx, py_top - ph) + 0.006
                verts.append([cx - pw, py_top - ph * 0.4, pz_pocket + 0.002])
                verts.append([cx + pw, py_top - ph * 0.4, pz_pocket + 0.002])
                verts.append([cx + pw * 0.85, py_top - ph, pz_bot])
                verts.append([cx - pw * 0.85, py_top - ph, pz_bot])
                for _ in range(4):
                    norms.append([side * 0.1, 0.0, 0.99])
                uvs.extend([[0.30, 0.65], [0.38, 0.65], [0.38, 0.72], [0.30, 0.72]])
                add_quad(tris, v_b0, v_b0 + 1, v_b0 + 2, v_b0 + 3)

            pocket_v_cnt = len(verts) - pocket_start_v
            pocket_t_cnt = len(tris) - pocket_start_t
            panels.append(PanelGeometry("chest_flap_pockets", pocket_start_v, pocket_v_cnt, pocket_start_t, pocket_t_cnt, True))

        else:
            # 2. Notched / Folded Blazer Lapels
            lapel_start_v = len(verts)
            lapel_start_t = len(tris)
            lapel_rings = 4
            lapel_seg = 12

            for lr in range(lapel_rings):
                frac = lr / (lapel_rings - 1)
                ly = top_y - frac * 0.20
                flare = 0.080 + frac * 0.045
                for side in [-1.0, 1.0]:
                    for s in range(lapel_seg // 2):
                        u_s = s / (lapel_seg // 2 - 1)
                        lx = side * (0.02 + u_s * flare)
                        lz = get_front_torso_z(lx, ly) + 0.008 * (1.0 - 0.5 * u_s)
                        verts.append([lx, ly, lz])
                        norms.append([side * 0.2, 0.1, 0.97])
                        uvs.append([0.45 + side * 0.10 * u_s, 0.70 + frac * 0.20])

            for lr in range(lapel_rings - 1):
                r_c = lapel_start_v + lr * lapel_seg
                r_n = lapel_start_v + (lr + 1) * lapel_seg
                add_quad_strip(tris, r_c, r_n, lapel_seg, closed=False)

            lapel_v_cnt = len(verts) - lapel_start_v
            lapel_t_cnt = len(tris) - lapel_start_t
            panels.append(PanelGeometry("lapels_and_collar", lapel_start_v, lapel_v_cnt, lapel_start_t, lapel_t_cnt, True))

            # 3. Center Zipper / Closure Track
            zip_start_v = len(verts)
            zip_start_t = len(tris)
            zip_slices = 8
            zip_w = 0.016

            for s in range(zip_slices + 1):
                py = hem_y + (s / zip_slices) * (top_y - 0.20 - hem_y)
                z_elev = get_front_torso_z(0.0, py) + 0.004
                verts.append([-zip_w, py, z_elev])
                norms.append([0.0, 0.0, 1.0])
                uvs.append([0.49, 0.05 + (s / zip_slices) * 0.45])

                verts.append([zip_w, py, z_elev])
                norms.append([0.0, 0.0, 1.0])
                uvs.append([0.51, 0.05 + (s / zip_slices) * 0.45])

            for s in range(zip_slices):
                v0 = zip_start_v + s * 2
                v1 = v0 + 1
                v2 = v0 + 3
                v3 = v0 + 2
                add_quad(tris, v0, v1, v2, v3)

            zip_v_cnt = len(verts) - zip_start_v
            zip_t_cnt = len(tris) - zip_start_t
            panels.append(PanelGeometry("front_zipper_track", zip_start_v, zip_v_cnt, zip_start_t, zip_t_cnt, True))

        # 4. Structured Sleeves
        arm_reach = 0.50
        n_arm_rings = 10
        arm_r_shoulder = 0.072 + margin * 0.8
        arm_r_cuff = 0.048 + margin * 0.6
        arm_seg = 18

        arm_configs = [
            ("left_outerwear_sleeve", 1.0, CANONICAL_SHOULDER_ORIGIN_LEFT, CANONICAL_ARM_DIR_LEFT),
            ("right_outerwear_sleeve", -1.0, CANONICAL_SHOULDER_ORIGIN_RIGHT, CANONICAL_ARM_DIR_RIGHT)
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

        # 1. Main Outerwear Torso
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

        # 2. Collar / Lapels
        if is_denim:
            b_min, b_max, dims = compute_component_bounds(pos_np, collar_start_v, collar_v_cnt)
            graph.add_node(GarmentComponentNode(
                component_id="denim_point_collar",
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

            b_min, b_max, dims = compute_component_bounds(pos_np, placket_start_v, placket_v_cnt)
            graph.add_node(GarmentComponentNode(
                component_id="button_placket",
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

            b_min, b_max, dims = compute_component_bounds(pos_np, pocket_start_v, pocket_v_cnt)
            graph.add_node(GarmentComponentNode(
                component_id="chest_flap_pockets",
                category=category,
                semantic_type="pocket",
                parent_id="main_torso",
                dimensions_m=dims,
                bounding_box_3d=(b_min, b_max),
                attachment_location="chest_bilateral",
                material_assignment="main_shell",
                confidence=1.0,
                provenance="pattern_constructed",
                vertex_range=(pocket_start_v, pocket_v_cnt),
                triangle_range=(pocket_start_t, pocket_t_cnt)
            ))
        else:
            b_min, b_max, dims = compute_component_bounds(pos_np, lapel_start_v, lapel_v_cnt)
            graph.add_node(GarmentComponentNode(
                component_id="lapels_and_collar",
                category=category,
                semantic_type="lapel",
                parent_id="main_torso",
                dimensions_m=dims,
                bounding_box_3d=(b_min, b_max),
                attachment_location="neckline_seam",
                material_assignment="main_shell",
                confidence=1.0,
                provenance="pattern_constructed",
                vertex_range=(lapel_start_v, lapel_v_cnt),
                triangle_range=(lapel_start_t, lapel_t_cnt)
            ))

            b_min, b_max, dims = compute_component_bounds(pos_np, zip_start_v, zip_v_cnt)
            graph.add_node(GarmentComponentNode(
                component_id="front_zipper_track",
                category=category,
                semantic_type="zipper",
                parent_id="main_torso",
                dimensions_m=dims,
                bounding_box_3d=(b_min, b_max),
                attachment_location="front_centerline",
                material_assignment="metallic_hardware",
                confidence=1.0,
                provenance="pattern_constructed",
                vertex_range=(zip_start_v, zip_v_cnt),
                triangle_range=(zip_start_t, zip_t_cnt)
            ))

        # 3. Outerwear Sleeves & Cuffs
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

