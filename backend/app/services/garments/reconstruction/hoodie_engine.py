"""
YORVYN — Hoodie 3D Garment Reconstruction Engine
Reconstructs pullover and zip-up hoodies with category-defining architectural features:
- Volumetric 3D Hood Cowl with contoured face opening & inner fleece lining
- Kangaroo Front Pouch Pocket with angled lateral hand-entry openings
- Ribbed Waistband Hem
- Ribbed Elastic Sleeve Cuffs
- Dropped Shoulder Construction
- Metal Grommet Eyelets & Hanging Drawstrings with Metal Aglets
- Relaxed / Oversized Silhouette Envelope with Physical Drape Ease
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


class HoodieReconstructionEngine(IGarmentReconstructionEngine):
    """Engine for hoodies, hooded sweatshirts, and zip hoodies."""

    @property
    def engine_id(self) -> str:
        return "hoodie_pattern_engine_v1"

    @property
    def supported_categories(self) -> List[str]:
        return ["tops", "outerwear", "streetwear"]

    @property
    def supported_subcategories(self) -> List[str]:
        return ["hoodie", "zip_hoodie", "pullover_hoodie", "hooded_sweatshirt"]

    def reconstruct(
        self,
        intelligence: Optional[GarmentIntelligenceV2Result] = None,
        category: str = "tops",
        subcategory: str = "hoodie",
        sleeve_length: str = "long",
        neckline_type: str = "hooded",
        fit: str = "oversized",
        front_image: Optional[Any] = None,
        back_image: Optional[Any] = None,
        **kwargs
    ) -> ReconstructionOutput:
        start_t = time.perf_counter()

        proportions = GarmentProportionsEstimator.estimate(
            category=category,
            subcategory=subcategory,
            fit="oversized" if fit in ["regular", "oversized", "relaxed"] else fit,
            intelligence=intelligence
        )
        margin = proportions.ease_margin_m

        top_y = 1.40
        hem_y = 0.85
        has_pocket = True
        has_hood = True
        has_drawstrings = True
        has_eyelets = True

        if intelligence and hasattr(intelligence, "landmarks") and intelligence.landmarks:
            lm = intelligence.landmarks
            if "collar_center" in lm:
                top_y = float(np.clip(1.40 + (0.05 - lm["collar_center"].position.y) * 0.10, 1.36, 1.44))
            if "hem_center" in lm:
                hem_y = float(np.clip(0.85 + (0.95 - lm["hem_center"].position.y) * 0.15, 0.80, 0.90))

        if intelligence and hasattr(intelligence, "components") and intelligence.components:
            p_comp = next((c for c in intelligence.components if c.component_type == "kangaroo_pocket"), None)
            if p_comp:
                has_pocket = p_comp.status == "detected"
            h_comp = next((c for c in intelligence.components if c.component_type == "hood"), None)
            if h_comp:
                has_hood = h_comp.status == "detected"

        verts: List[List[float]] = []
        norms: List[List[float]] = []
        uvs: List[List[float]] = []
        tris: List[List[int]] = []
        panels: List[PanelGeometry] = []

        # ── 0. Surface Profiler Function ──
        def get_front_torso_z(x_val: float, y_val: float) -> float:
            t_val = float(np.clip((top_y - y_val) / max(0.05, top_y - hem_y), 0.0, 1.0))
            if t_val < 0.22:
                frac_sh = t_val / 0.22
                rx_val = (0.232 - 0.022 * frac_sh) + margin
                rz_val = (0.124 + 0.008 * frac_sh) + margin
            elif t_val < 0.55:
                frac_w = (t_val - 0.22) / 0.33
                rx_val = (0.210 - 0.008 * math.sin(frac_w * math.pi * 0.5)) + margin
                rz_val = (0.132 - 0.006 * math.sin(frac_w * math.pi * 0.5)) + margin
            elif t_val < 0.84:
                frac_h = (t_val - 0.55) / 0.29
                rx_val = (0.202 - 0.006 * math.sin(frac_h * math.pi * 0.5)) + margin
                rz_val = (0.126 - 0.004 * math.sin(frac_h * math.pi * 0.5)) + margin
            else:
                frac_rib = (t_val - 0.84) / 0.16
                rx_val = (0.196 - 0.012 * frac_rib) + margin * 0.7
                rz_val = (0.122 - 0.008 * frac_rib) + margin * 0.7

            sin_sq = max(0.0, 1.0 - (x_val / max(0.01, rx_val)) ** 2)
            return rz_val * math.sqrt(sin_sq)

        # ── 1. Main Torso Panels & Lower Ribbed Waistband (Dropped Shoulder Relaxed Envelope) ──
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

            # Oversized relaxed profile with dropped shoulder breadth at top
            if t < 0.22:
                frac_sh = t / 0.22
                rx = (0.232 - 0.022 * frac_sh) + margin
                rz = (0.124 + 0.008 * frac_sh) + margin
            elif t < 0.55:
                frac_w = (t - 0.22) / 0.33
                rx = (0.210 - 0.008 * math.sin(frac_w * math.pi * 0.5)) + margin
                rz = (0.132 - 0.006 * math.sin(frac_w * math.pi * 0.5)) + margin
            elif t < 0.84:
                frac_h = (t - 0.55) / 0.29
                rx = (0.202 - 0.006 * math.sin(frac_h * math.pi * 0.5)) + margin
                rz = (0.126 - 0.004 * math.sin(frac_h * math.pi * 0.5)) + margin
            else:
                # Tightened bottom ribbed waistband band
                frac_rib = (t - 0.84) / 0.16
                rx = (0.196 - 0.012 * frac_rib) + margin * 0.7
                rz = (0.122 - 0.008 * frac_rib) + margin * 0.7

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

                # Torso UV mapping: Front [0.04, 0.46] x [0.48, 0.96], Back [0.54, 0.96] x [0.48, 0.96]
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
        
        # Ribbed waistband panel tracking (bottom 4 rings)
        wb_start_v = ring_starts[20]
        wb_v_cnt = len(verts) - wb_start_v
        wb_start_t = torso_start_t + (20 * n_seg * 2)
        wb_t_cnt = len(tris) - wb_start_t
        panels.append(PanelGeometry("ribbed_waistband", wb_start_v, wb_v_cnt, wb_start_t, wb_t_cnt, True))

        # ── 2. Dropped Shoulder Articulated Sleeves with Ribbed Cuffs ──
        arm_reach = 0.50
        n_arm_rings = 10
        arm_r_shoulder = 0.068 + margin * 0.5
        arm_r_cuff = 0.042 + margin * 0.4
        arm_seg = 20

        arm_configs = [
            ("left_sleeve_and_cuff", 1.0, np.array([0.190 + margin * 0.4, top_y - 0.055, 0.0], dtype=np.float32), CANONICAL_ARM_DIR_LEFT),
            ("right_sleeve_and_cuff", -1.0, np.array([-0.190 - margin * 0.4, top_y - 0.055, 0.0], dtype=np.float32), CANONICAL_ARM_DIR_RIGHT)
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
                # Ribbed cuff cinch at distal end
                radius = arm_r_shoulder + (arm_r_cuff - arm_r_shoulder) * frac
                if frac > 0.85:
                    radius *= 0.94

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

        # ── 3. Volumetric 3D Hood Cowl (Outer Shell + Inner Fleece Lining + Contoured Rim) ──
        if has_hood:
            hood_start_v = len(verts)
            hood_start_t = len(tris)
            hood_rings = 10
            hood_slices = 16

            for layer, layer_offset in [('outer', 0.0), ('inner', -0.006)]:
                layer_start_v = len(verts)
                for r in range(hood_rings):
                    frac_y = r / (hood_rings - 1)
                    y_pos = top_y + frac_y * 0.27
                    rad_x = (0.132 + 0.022 * math.sin(frac_y * math.pi)) + layer_offset
                    rad_z = (0.128 + 0.024 * math.sin(frac_y * math.pi)) + layer_offset
                    center_z = 0.022 - 0.014 * frac_y

                    for s in range(hood_slices + 1):
                        u_val = s / hood_slices
                        # Wrap symmetrically around back (-Z, phi=0) and sides, leaving front (+Z) open for face
                        phi = -0.64 * math.pi + u_val * (1.28 * math.pi)
                        px = rad_x * math.sin(phi)
                        pz = center_z - rad_z * math.cos(phi)
                        py = y_pos

                        norm_len = math.hypot(px, pz) or 1.0
                        verts.append([px, py, pz])
                        if layer == 'outer':
                            norms.append([px / norm_len, 0.2, pz / norm_len])
                        else:
                            norms.append([-px / norm_len, -0.2, -pz / norm_len])
                        # Hood cowl island: [0.10, 0.90] x [0.04, 0.22]
                        uvs.append([0.10 + u_val * 0.80, 0.04 + frac_y * 0.18])

                stride = hood_slices + 1
                for r in range(hood_rings - 1):
                    for s in range(hood_slices):
                        i0 = layer_start_v + r * stride + s
                        i1 = i0 + 1
                        i2 = layer_start_v + (r + 1) * stride + s
                        i3 = i2 + 1
                        if layer == 'outer':
                            add_quad(tris, i0, i2, i3, i1)
                        else:
                            add_quad(tris, i0, i1, i3, i2)

            hood_v_cnt = len(verts) - hood_start_v
            hood_t_cnt = len(tris) - hood_start_t
            panels.append(PanelGeometry("hood_cowl", hood_start_v, hood_v_cnt, hood_start_t, hood_t_cnt, True))

        # ── 4. Kangaroo Front Pocket (Raised Pouch with Angled Side Entries) ──
        if has_pocket:
            pocket_start_v = len(verts)
            pocket_start_t = len(tris)
            pocket_rings = 6
            pocket_slices = 10
            p_ymin, p_ymax = hem_y + 0.06, hem_y + 0.28

            for r in range(pocket_rings):
                t_val = r / (pocket_rings - 1)
                p_y = p_ymin + t_val * (p_ymax - p_ymin)
                half_w = 0.160 * (1.0 - t_val * 0.25)

                for s in range(pocket_slices + 1):
                    u_p = s / pocket_slices
                    px = -half_w + u_p * (2 * half_w)
                    base_z = get_front_torso_z(px, p_y)
                    pz = base_z + 0.012 + 0.005 * math.sin(u_p * math.pi)

                    verts.append([px, p_y, pz])
                    norms.append([0.0, 0.1, 0.99])
                    # Kangaroo pocket island: [0.14, 0.36] x [0.68, 0.92]
                    uvs.append([0.14 + u_p * 0.22, 0.68 + t_val * 0.24])

            p_stride = pocket_slices + 1
            for r in range(pocket_rings - 1):
                for s in range(pocket_slices):
                    i0 = pocket_start_v + r * p_stride + s
                    i1 = i0 + 1
                    i2 = pocket_start_v + (r + 1) * p_stride + s
                    i3 = i2 + 1
                    add_quad(tris, i0, i1, i3, i2)

            pocket_v_cnt = len(verts) - pocket_start_v
            pocket_t_cnt = len(tris) - pocket_start_t
            panels.append(PanelGeometry("kangaroo_pocket", pocket_start_v, pocket_v_cnt, pocket_start_t, pocket_t_cnt, True))

        # ── 5. Metal Grommet Eyelets ──
        if has_eyelets:
            eyelet_start_v = len(verts)
            eyelet_start_t = len(tris)
            ey_pos = 1.385
            eyelet_coords = [
                (-0.038, ey_pos, get_front_torso_z(-0.038, ey_pos) + 0.004),
                (0.038, ey_pos, get_front_torso_z(0.038, ey_pos) + 0.004)
            ]
            for ex, ey, ez in eyelet_coords:
                e_start_v = len(verts)
                e_seg = 8
                for i in range(e_seg):
                    ang = 2.0 * math.pi * i / e_seg
                    dx = math.cos(ang)
                    dy = math.sin(ang)
                    # Inner ring
                    verts.append([ex + dx * 0.004, ey + dy * 0.004, ez])
                    norms.append([0.0, 0.0, 1.0])
                    uvs.append([0.85 + (i / e_seg) * 0.05, 0.022])
                    # Outer ring
                    verts.append([ex + dx * 0.007, ey + dy * 0.007, ez])
                    norms.append([0.0, 0.0, 1.0])
                    uvs.append([0.85 + (i / e_seg) * 0.05, 0.038])
                for i in range(e_seg):
                    i0 = e_start_v + i * 2
                    i1 = e_start_v + i * 2 + 1
                    i2 = e_start_v + ((i + 1) % e_seg) * 2
                    i3 = e_start_v + ((i + 1) % e_seg) * 2 + 1
                    add_quad(tris, i0, i2, i3, i1)

            eyelet_v_cnt = len(verts) - eyelet_start_v
            eyelet_t_cnt = len(tris) - eyelet_start_t
            panels.append(PanelGeometry("eyelets", eyelet_start_v, eyelet_v_cnt, eyelet_start_t, eyelet_t_cnt, True))

        # ── 6. Hanging Drawstrings with Metal Aglets ──
        if has_drawstrings:
            cord_start_all_v = len(verts)
            cord_start_all_t = len(tris)
            cords = [
                (-0.038, 1.385, 1.160),
                (0.038, 1.385, 1.135)
            ]
            for cx, cy_top, cy_bot in cords:
                cord_start_v = len(verts)
                n_cord_segs = 10
                cord_radial = 6
                for r in range(n_cord_segs):
                    fc = r / (n_cord_segs - 1)
                    cur_y = cy_top - fc * (cy_top - cy_bot)
                    base_z = get_front_torso_z(cx, cur_y)
                    cur_z = base_z + 0.009 + 0.005 * math.sin(fc * math.pi)
                    is_aglet = (fc >= 0.86)
                    r_cord = 0.0028 if not is_aglet else 0.0034  # metal aglet at tip
                    for i in range(cord_radial):
                        ang = 2.0 * math.pi * i / cord_radial
                        verts.append([cx + r_cord * math.cos(ang), cur_y, cur_z + r_cord * math.sin(ang)])
                        norms.append([math.cos(ang), 0.0, math.sin(ang)])
                        if is_aglet:
                            # Silver metallic aglet UV slot
                            u = 0.86 + 0.08 * (i / cord_radial)
                            v = 0.022 + 0.014 * ((fc - 0.86) / 0.14)
                        else:
                            # Woven drawstring cord UV slot
                            u = 0.72 + 0.09 * (i / cord_radial)
                            v = 0.022 + 0.014 * (fc / 0.86)
                        uvs.append([u, v])
                for r in range(n_cord_segs - 1):
                    add_quad_strip(tris, cord_start_v + r * cord_radial, cord_start_v + (r + 1) * cord_radial, cord_radial, closed=True)

            cord_v_cnt = len(verts) - cord_start_all_v
            cord_t_cnt = len(tris) - cord_start_all_t
            panels.append(PanelGeometry("drawstrings", cord_start_all_v, cord_v_cnt, cord_start_all_t, cord_t_cnt, True))

        # ── 7. Finalize Geometry & Normals ──
        pos_np = np.array(verts, dtype=np.float32)
        idx_np = np.array(tris, dtype=np.uint32)
        norm_np = calculate_smooth_normals(pos_np, idx_np)
        uv_np = np.array(uvs, dtype=np.float32)

        # ── 8. Skeletal Rigging (Ara 3D Gen 20 Bones) ──
        label_spans = [
            ("left_sleeve", arm_configs_tracking[0][0], n_arm_rings * arm_seg),
            ("right_sleeve", arm_configs_tracking[1][0], n_arm_rings * arm_seg),
        ]
        if has_hood:
            label_spans.append(("hood", hood_start_v, hood_v_cnt))
        v_labels = assign_vertex_labels(len(pos_np), label_spans, default="torso")
        joint_indices, joint_weights = compute_torso_skinning(
            pos_np, hem_y=hem_y, top_y=top_y, has_hood=has_hood, component_labels=v_labels
        )
        mesh = GarmentMesh(pos_np, norm_np, uv_np, idx_np, joint_indices, joint_weights)

        # ── 9. Quality & Provenance Validation ──
        quality_report = GarmentMeshValidator.validate(mesh)
        observed_mask = identify_observed_surface(pos_np, has_back_view=(back_image is not None))
        obs_count = int(np.sum(observed_mask))
        inf_count = len(pos_np) - obs_count
        obs_ratio = round(obs_count / max(1, len(pos_np)), 3)

        # ── 10. Multi-Component Graph Construction ──
        graph = GarmentComponentGraph()
        
        # 1. Main Torso (rings 0..19)
        main_torso_v_cnt = wb_start_v - torso_start_v
        main_torso_t_cnt = wb_start_t - torso_start_t
        b_min, b_max, dims = compute_component_bounds(pos_np, torso_start_v, main_torso_v_cnt)
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
            vertex_range=(torso_start_v, main_torso_v_cnt),
            triangle_range=(torso_start_t, main_torso_t_cnt)
        ))

        # 2. Ribbed Waistband (rings 20..23)
        b_min, b_max, dims = compute_component_bounds(pos_np, wb_start_v, wb_v_cnt)
        graph.add_node(GarmentComponentNode(
            component_id="ribbed_waistband",
            category=category,
            semantic_type="waistband",
            parent_id="main_torso",
            dimensions_m=dims,
            bounding_box_3d=(b_min, b_max),
            attachment_location="torso_hem",
            material_assignment="ribbed_trim",
            confidence=1.0,
            provenance="pattern_constructed",
            vertex_range=(wb_start_v, wb_v_cnt),
            triangle_range=(wb_start_t, wb_t_cnt)
        ))

        # 3. Sleeves & Cuffs
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
                material_assignment="ribbed_trim",
                confidence=1.0,
                provenance="pattern_constructed",
                vertex_range=(cuff_v_start, cuff_v_cnt),
                triangle_range=(cuff_t_start, cuff_t_cnt)
            ))

        # 4. Volumetric Hood Cowl
        if has_hood:
            b_min, b_max, dims = compute_component_bounds(pos_np, hood_start_v, hood_v_cnt)
            graph.add_node(GarmentComponentNode(
                component_id="hood_cowl",
                category=category,
                semantic_type="hood",
                parent_id="main_torso",
                dimensions_m=dims,
                bounding_box_3d=(b_min, b_max),
                attachment_location="neckline_seam",
                material_assignment="main_shell",
                confidence=1.0,
                provenance="pattern_constructed",
                vertex_range=(hood_start_v, hood_v_cnt),
                triangle_range=(hood_start_t, hood_t_cnt)
            ))

        # 5. Kangaroo Pocket
        if has_pocket:
            b_min, b_max, dims = compute_component_bounds(pos_np, pocket_start_v, pocket_v_cnt)
            graph.add_node(GarmentComponentNode(
                component_id="kangaroo_pocket",
                category=category,
                semantic_type="pocket",
                parent_id="main_torso",
                dimensions_m=dims,
                bounding_box_3d=(b_min, b_max),
                attachment_location="lower_abdomen",
                material_assignment="main_shell",
                confidence=1.0,
                provenance="pattern_constructed",
                vertex_range=(pocket_start_v, pocket_v_cnt),
                triangle_range=(pocket_start_t, pocket_t_cnt)
            ))

        # 6. Metal Eyelets
        if has_eyelets:
            b_min, b_max, dims = compute_component_bounds(pos_np, eyelet_start_v, eyelet_v_cnt)
            graph.add_node(GarmentComponentNode(
                component_id="eyelets",
                category=category,
                semantic_type="hardware",
                parent_id="main_torso",
                dimensions_m=dims,
                bounding_box_3d=(b_min, b_max),
                attachment_location="neckline_front",
                material_assignment="metallic_hardware",
                confidence=1.0,
                provenance="pattern_constructed",
                vertex_range=(eyelet_start_v, eyelet_v_cnt),
                triangle_range=(eyelet_start_t, eyelet_t_cnt)
            ))

        # 7. Hanging Drawstrings
        if has_drawstrings:
            b_min, b_max, dims = compute_component_bounds(pos_np, cord_start_all_v, cord_v_cnt)
            graph.add_node(GarmentComponentNode(
                component_id="drawstrings",
                category=category,
                semantic_type="drawstring",
                parent_id="eyelets" if has_eyelets else "main_torso",
                dimensions_m=dims,
                bounding_box_3d=(b_min, b_max),
                attachment_location="eyelet_anchor",
                material_assignment="woven_cord",
                confidence=1.0,
                provenance="pattern_constructed",
                vertex_range=(cord_start_all_v, cord_v_cnt),
                triangle_range=(cord_start_all_t, cord_t_cnt)
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
