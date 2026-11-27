"""
YORVYN — Traditional Wear 3D Garment Reconstruction Engine
Reconstructs South Asian and cultural garments:
- Kurta: Long knee-length tunic silhouette with:
  * Mandarin / Nehru Band Collar
  * Center Front Chest Slit Placket
  * Open Lateral Side Slits (Chaks) below the hip line (split front and back panels)
  * Straight sleeves
- Sherwani: Structured royal outerwear tunic
- Saree & Lehenga: Flared pleated panels
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
    identify_observed_surface
)
from .mesh_validator import GarmentMeshValidator
from .proportions import GarmentProportionsEstimator


class TraditionalWearReconstructionEngine(IGarmentReconstructionEngine):
    """Engine for kurtas, sherwanis, sarees, lehengas, and ethnic wear."""

    @property
    def engine_id(self) -> str:
        return "traditional_pattern_engine_v1"

    @property
    def supported_categories(self) -> List[str]:
        return ["traditional", "ethnic_wear", "cultural_wear"]

    @property
    def supported_subcategories(self) -> List[str]:
        return ["kurta", "sherwani", "saree", "lehenga", "salwar_suit", "traditional_jacket"]

    def reconstruct(
        self,
        intelligence: Optional[GarmentIntelligenceV2Result] = None,
        category: str = "traditional",
        subcategory: str = "kurta",
        sleeve_length: str = "long",
        neckline_type: str = "mandarin_collar",
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
        margin = proportions.ease_margin_m

        top_y = 1.42
        hem_y = 0.60  # Long tunic down to mid-thigh / knee
        slit_y = 0.88  # Side slit starts at lower hip line

        if intelligence and hasattr(intelligence, "landmarks") and intelligence.landmarks:
            lm = intelligence.landmarks
            if "collar_center" in lm:
                top_y = float(np.clip(1.42 + (0.05 - lm["collar_center"].position.y) * 0.10, 1.38, 1.45))
            if "hem_center" in lm:
                hem_y = float(np.clip(0.60 + (0.95 - lm["hem_center"].position.y) * 0.20, 0.52, 0.75))

        verts: List[List[float]] = []
        norms: List[List[float]] = []
        uvs: List[List[float]] = []
        tris: List[List[int]] = []
        panels: List[PanelGeometry] = []
        n_seg = 28

        # 1. Closed Upper Torso Section (from collar down to hip slit)
        upper_torso_rings = [
            (top_y, 0.170 + margin, 0.110 + margin),        # 0: Upper chest / collar
            (top_y - 0.08, 0.185 + margin, 0.125 + margin), # 1: Bust
            (top_y - 0.18, 0.175 + margin, 0.118 + margin), # 2: Ribs
            (top_y - 0.28, 0.168 + margin, 0.112 + margin), # 3: Waist
            (top_y - 0.40, 0.182 + margin, 0.124 + margin), # 4: Upper hip
            (slit_y, 0.192 + margin, 0.130 + margin),       # 5: Slit apex (hip line)
        ]

        upper_start_v = len(verts)
        upper_start_t = len(tris)
        ring_starts: List[int] = []

        for ring_idx, (y, rx, rz) in enumerate(upper_torso_rings):
            ring_starts.append(len(verts))
            v_coord = ring_idx / (len(upper_torso_rings) - 1)

            for i in range(n_seg):
                theta = 2.0 * math.pi * i / n_seg
                px = rx * math.cos(theta)
                pz = rz * math.sin(theta)
                py = y

                nx, nz = math.cos(theta), math.sin(theta)
                verts.append([px, py, pz])
                norms.append([nx, 0.0, nz])

                if pz >= 0:
                    th_f = theta if theta <= math.pi else (2.0 * math.pi - theta)
                    u = 0.04 + (0.42 * (th_f / math.pi))
                else:
                    th_b = (theta - math.pi) if theta >= math.pi else (math.pi - theta)
                    u = 0.54 + (0.42 * (th_b / math.pi))
                v = 0.04 + (1.0 - v_coord) * 0.40
                uvs.append([u, v])

        for r in range(len(upper_torso_rings) - 1):
            add_quad_strip(tris, ring_starts[r], ring_starts[r + 1], n_seg, closed=True)

        upper_v_cnt = len(verts) - upper_start_v
        upper_t_cnt = len(tris) - upper_start_t
        panels.append(PanelGeometry("kurta_upper_torso", upper_start_v, upper_v_cnt, upper_start_t, upper_t_cnt, True))

        # 2. Open Lateral Side Slits (Chaks) below slit_y
        # The tunic splits into two separate curved flaps: Front Panel and Back Panel
        lower_rings_spec = [
            (slit_y - 0.02, 0.195 + margin, 0.132 + margin),
            ((slit_y + hem_y) * 0.5, 0.205 + margin, 0.138 + margin),
            (hem_y, 0.218 + margin, 0.145 + margin),
        ]

        flap_seg = n_seg // 2  # 14 segments each

        # Front Flap (pz >= 0)
        front_flap_start_v = len(verts)
        front_flap_start_t = len(tris)
        ff_ring_starts: List[int] = []

        for r_idx, (y, rx, rz) in enumerate(lower_rings_spec):
            ff_ring_starts.append(len(verts))
            v_val = 0.44 + (r_idx / (len(lower_rings_spec) - 1)) * 0.50
            for i in range(flap_seg):
                th = (i / (flap_seg - 1)) * math.pi  # 0 to pi (front arc)
                px = rx * math.cos(th)
                pz = rz * math.sin(th)
                verts.append([px, y, pz])
                norms.append([math.cos(th), 0.0, math.sin(th)])
                uvs.append([0.04 + (i / flap_seg) * 0.42, v_val])

        for r in range(len(lower_rings_spec) - 1):
            add_quad_strip(tris, ff_ring_starts[r], ff_ring_starts[r + 1], flap_seg, closed=False)

        ff_v_cnt = len(verts) - front_flap_start_v
        ff_t_cnt = len(tris) - front_flap_start_t
        panels.append(PanelGeometry("kurta_front_flap_with_side_slits", front_flap_start_v, ff_v_cnt, front_flap_start_t, ff_t_cnt, True))

        # Back Flap (pz < 0)
        back_flap_start_v = len(verts)
        back_flap_start_t = len(tris)
        bf_ring_starts: List[int] = []

        for r_idx, (y, rx, rz) in enumerate(lower_rings_spec):
            bf_ring_starts.append(len(verts))
            v_val = 0.44 + (r_idx / (len(lower_rings_spec) - 1)) * 0.50
            for i in range(flap_seg):
                th = math.pi + (i / (flap_seg - 1)) * math.pi  # pi to 2pi (back arc)
                px = rx * math.cos(th)
                pz = rz * math.sin(th)
                verts.append([px, y, pz])
                norms.append([math.cos(th), 0.0, math.sin(th)])
                uvs.append([0.54 + (i / flap_seg) * 0.42, v_val])

        for r in range(len(lower_rings_spec) - 1):
            add_quad_strip(tris, bf_ring_starts[r], bf_ring_starts[r + 1], flap_seg, closed=False)

        bf_v_cnt = len(verts) - back_flap_start_v
        bf_t_cnt = len(tris) - back_flap_start_t
        panels.append(PanelGeometry("kurta_back_flap_with_side_slits", back_flap_start_v, bf_v_cnt, back_flap_start_t, bf_t_cnt, back_image is not None))

        # 3. Mandarin / Nehru Standing Band Collar
        collar_start_v = len(verts)
        collar_start_t = len(tris)
        collar_h = 0.028
        collar_seg = 18
        for cr in range(2):
            cy = top_y + cr * collar_h
            for i in range(collar_seg):
                th = -0.40 * math.pi + (i / (collar_seg - 1)) * (1.80 * math.pi)
                cx = (0.082 + margin * 0.5) * math.sin(th)
                cz = (0.085 + margin * 0.5) * math.cos(th)
                verts.append([cx, cy, cz])
                norms.append([math.sin(th), 0.1, math.cos(th)])
                uvs.append([0.35 + (i / collar_seg) * 0.30, 0.88 + cr * 0.08])

        r_c = collar_start_v
        r_n = collar_start_v + collar_seg
        add_quad_strip(tris, r_c, r_n, collar_seg, closed=False)

        collar_v_cnt = len(verts) - collar_start_v
        collar_t_cnt = len(tris) - collar_start_t
        panels.append(PanelGeometry("mandarin_nehru_collar", collar_start_v, collar_v_cnt, collar_start_t, collar_t_cnt, True))

        # 3b. Center Front Chest Slit Placket
        placket_start_v = len(verts)
        placket_start_t = len(tris)
        py_top = top_y
        py_bot = top_y - 0.16
        pw = 0.012
        pz_offset = 0.115 + margin
        v_p0 = len(verts)
        verts.append([-pw, py_top, pz_offset])
        verts.append([pw, py_top, pz_offset])
        verts.append([-pw, py_bot, pz_offset])
        verts.append([pw, py_bot, pz_offset])
        norms.extend([[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]])
        uvs.extend([[0.48, 0.90], [0.52, 0.90], [0.48, 0.75], [0.52, 0.75]])
        tris.append([v_p0, v_p0 + 2, v_p0 + 1])
        tris.append([v_p0 + 1, v_p0 + 2, v_p0 + 3])
        placket_v_cnt = len(verts) - placket_start_v
        placket_t_cnt = len(tris) - placket_start_t
        panels.append(PanelGeometry("chest_slit_placket", placket_start_v, placket_v_cnt, placket_start_t, placket_t_cnt, True))

        # 4. Sleeves (Straight Kurta Sleeves)
        arm_reach = 0.50
        n_arm_rings = 10
        arm_r_shoulder = 0.065 + margin * 0.7
        arm_r_cuff = 0.052 + margin * 0.6  # Straight cut, not tightly cuffed
        arm_seg = 18

        arm_configs = [
            ("left_kurta_sleeve", 1.0, CANONICAL_SHOULDER_ORIGIN_LEFT, CANONICAL_ARM_DIR_LEFT),
            ("right_kurta_sleeve", -1.0, CANONICAL_SHOULDER_ORIGIN_RIGHT, CANONICAL_ARM_DIR_RIGHT)
        ]
        arm_configs_tracking = []

        for panel_name, side, shoulder_origin, arm_dir in arm_configs:
            arm_start_v = len(verts)
            arm_start_t = len(tris)
            arm_configs_tracking.append((arm_start_v, n_arm_rings * arm_seg))

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

                    u = (0.54 if side > 0 else 0.04) + 0.42 * (i / arm_seg)
                    v = 0.54 + 0.20 * frac
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

        # 6. Skeletal Rigging (blends down to upper legs for the long flaps)
        v_labels = assign_vertex_labels(
            len(pos_np),
            [
                ("left_sleeve", arm_configs_tracking[0][0], arm_configs_tracking[0][1]),
                ("right_sleeve", arm_configs_tracking[1][0], arm_configs_tracking[1][1]),
            ],
            default="torso"
        )
        joint_indices, joint_weights = compute_torso_skinning(
            pos_np, hem_y=hem_y, top_y=top_y, has_hood=False, is_kurta=True, component_labels=v_labels
        )
        mesh = GarmentMesh(pos_np, norm_np, uv_np, idx_np, joint_indices, joint_weights)

        # 7. Quality, Provenance & Component Graph
        quality_report = GarmentMeshValidator.validate(mesh)
        observed_mask = identify_observed_surface(pos_np, has_back_view=(back_image is not None))
        obs_count = int(np.sum(observed_mask))
        inf_count = len(pos_np) - obs_count
        obs_ratio = round(obs_count / max(1, len(pos_np)), 3)

        # Build Canonical Component Graph
        graph = GarmentComponentGraph()
        for p in panels:
            b_min, b_max, dims = compute_component_bounds(pos_np, p.vertex_start_idx, p.vertex_count)
            parent_id = "kurta_upper_torso" if p.name != "kurta_upper_torso" else None
            graph.add_node(GarmentComponentNode(
                component_id=p.name,
                category=category,
                semantic_type="torso" if p.name == "kurta_upper_torso" else ("collar" if "collar" in p.name else ("placket" if "placket" in p.name else ("sleeve" if "sleeve" in p.name else "flap_chak"))),
                parent_id=parent_id,
                dimensions_m=dims,
                bounding_box_3d=(b_min, b_max),
                attachment_location="spine_core" if p.name == "kurta_upper_torso" else "upper_torso",
                material_assignment="cotton_linen",
                confidence=1.0,
                provenance="pattern_constructed",
                vertex_range=(p.vertex_start_idx, p.vertex_count),
                triangle_range=(p.triangle_start_idx, p.triangle_count),
                representation_type="GEOMETRIC_MESH"
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

