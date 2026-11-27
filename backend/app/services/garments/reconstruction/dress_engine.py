"""
YORVYN — Dresses and Skirts 3D Garment Reconstruction Engine
Reconstructs dresses, gowns, and skirts with category-accurate architecture:
- Standalone Skirts: Starts at Waistband (1.02m) and drapes outward, NOT collarbone
- Dresses: Fitted Upper Bodice + Waist Seam Transition + Flared Skirt Volume
- Realistic Fabric Draping Waves and Bell Silhouettes
- Ara 3D 20-bone Dual Leg & Pelvis Skinning Blends
"""

import time
import math
from typing import List, Tuple, Dict, Any, Optional
import numpy as np

from backend.app.services.garments.garment_mesh_builder import GarmentMesh
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
    add_quad_strip,
    identify_observed_surface,
    extract_silhouette_profile
)
from .mesh_validator import GarmentMeshValidator
from .proportions import GarmentProportionsEstimator


class DressReconstructionEngine(IGarmentReconstructionEngine):
    """Engine for dresses, gowns, maxi dresses, mini dresses, and skirts."""

    @property
    def engine_id(self) -> str:
        return "dress_pattern_engine_v1"

    @property
    def supported_categories(self) -> List[str]:
        return ["dresses_and_skirts", "dresses", "dress", "skirts", "skirt"]

    @property
    def supported_subcategories(self) -> List[str]:
        return ["dress", "casual_dress", "formal_dress", "gown", "maxi_dress", "mini_dress", "skirt", "a_line_skirt", "pleated_skirt", "pencil_skirt"]

    def reconstruct(
        self,
        intelligence: Optional[GarmentIntelligenceV2Result] = None,
        category: str = "dresses_and_skirts",
        subcategory: str = "dress",
        sleeve_length: str = "sleeveless",
        neckline_type: str = "crewneck",
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

        is_skirt = "skirt" in subcategory.lower() or (category.lower() in ["skirt", "skirts"] and "dress" not in subcategory.lower())
        is_maxi = "maxi" in subcategory.lower() or "gown" in subcategory.lower()
        hem_y = 0.18 if is_maxi else (0.50 if is_skirt else 0.45)
        top_y = 1.02 if is_skirt else 1.42

        if intelligence and hasattr(intelligence, "landmarks") and intelligence.landmarks:
            lm = intelligence.landmarks
            if not is_skirt and ("neckline_center" in lm or "collar_center" in lm):
                p = (lm.get("neckline_center") or lm.get("collar_center")).position
                top_y = float(np.clip(1.42 + (0.05 - p.y) * 0.10, 1.38, 1.45))
            elif is_skirt and ("waist_left" in lm or "waist_right" in lm):
                key = "waist_left" if "waist_left" in lm else "waist_right"
                top_y = float(np.clip(1.02 + (0.15 - lm[key].position.y) * 0.10, 0.98, 1.06))

            if "hem_center" in lm:
                hem_y = float(np.clip(0.48 + (0.95 - lm["hem_center"].position.y) * 0.25, 0.10, 0.65))

        verts: List[List[float]] = []
        norms: List[List[float]] = []
        uvs: List[List[float]] = []
        tris: List[List[int]] = []
        panels: List[PanelGeometry] = []
        n_seg = 28

        if is_skirt:
            # Standalone skirt: rings from waist down to hem
            skirt_rings_spec = [
                (top_y, 0.178 + margin, 0.124 + margin),        # 0: Waistband opening
                (top_y - 0.08, 0.190 + margin, 0.134 + margin), # 1: Upper hips
                (0.85, 0.215 + margin, 0.150 + margin),         # 2: Flare start
                (0.68, 0.245 + margin, 0.175 + margin),         # 3: Mid flare
                (hem_y, 0.275 + margin, 0.195 + margin),        # 4: Lower hem
            ]
        else:
            # Complete Multi-Zone One-Piece Dress: Upper Bodice + Waist Transition + Flared Skirt Drape
            skirt_rings_spec = [
                (top_y, 0.168 + margin, 0.108 + margin),           # 0: Upper neckline / clavicle
                (top_y - 0.04, 0.174 + margin, 0.114 + margin),    # 1: Upper chest
                (top_y - 0.08, 0.182 + margin, 0.122 + margin),    # 2: Bust apex
                (top_y - 0.13, 0.176 + margin, 0.118 + margin),    # 3: Underbust
                (top_y - 0.18, 0.170 + margin, 0.114 + margin),    # 4: Ribcage
                (top_y - 0.23, 0.164 + margin, 0.110 + margin),    # 5: High waist
                (top_y - 0.28, 0.158 + margin, 0.105 + margin),    # 6: Natural waist seam
                (top_y - 0.34, 0.172 + margin, 0.115 + margin),    # 7: Upper hip flare
                (1.02, 0.185 + margin, 0.125 + margin),            # 8: Mid hips
                (0.93, 0.200 + margin, 0.136 + margin),            # 9: Low hip
                (0.85, 0.215 + margin, 0.148 + margin),            # 10: Flare initiation
                (0.75, 0.230 + margin, 0.159 + margin),            # 11: Thigh drape
                (0.65, 0.245 + margin, 0.170 + margin),            # 12: Mid flare
                (0.55, 0.260 + margin, 0.182 + margin),            # 13: Lower flare
                (hem_y + 0.04, 0.272 + margin, 0.192 + margin),     # 14: Above hem
                (hem_y, 0.280 + margin, 0.198 + margin),           # 15: Flared hem wave
            ]

        sil_scales, sil_offsets = extract_silhouette_profile(front_image, len(skirt_rings_spec))

        ring_starts: List[int] = []
        for ring_idx, (y, rx, rz) in enumerate(skirt_rings_spec):
            ring_starts.append(len(verts))
            v_coord = ring_idx / (len(skirt_rings_spec) - 1)

            if sil_scales is not None:
                s_factor = float(sil_scales[ring_idx])
                rx = rx * s_factor
                rz = rz * (0.6 + 0.4 * s_factor)
                c_offset_x = float(sil_offsets[ring_idx])
            else:
                c_offset_x = 0.0

            for i in range(n_seg):
                th = 2.0 * math.pi * i / n_seg
                # Fabric ripple waves near hem
                wave = 0.006 * math.sin(6.0 * th) if ring_idx >= len(skirt_rings_spec) - 2 else 0.0
                px = (rx + wave) * math.cos(th) + c_offset_x
                pz = (rz + wave) * math.sin(th)

                verts.append([px, y, pz])
                norms.append([math.cos(th), 0.05, math.sin(th)])
                u = (math.atan2(pz, px) / (2.0 * math.pi)) + 0.5
                uvs.append([u, 0.95 - v_coord * 0.90])

        for r in range(len(skirt_rings_spec) - 1):
            add_quad_strip(tris, ring_starts[r], ring_starts[r + 1], n_seg, closed=True)

        if is_skirt:
            panels.append(PanelGeometry("waistband_panel", 0, n_seg * 2, 0, (n_seg - 1) * 2, True))
            panels.append(PanelGeometry("flared_skirt_drape", n_seg * 2, len(verts) - n_seg * 2, (n_seg - 1) * 2, len(tris) - (n_seg - 1) * 2, True))
        else:
            bodice_v = n_seg * 7
            bodice_t = n_seg * 6 * 2
            waist_v = n_seg * 3
            waist_t = n_seg * 3 * 2
            skirt_v = len(verts) - (bodice_v + waist_v)
            skirt_t = len(tris) - (bodice_t + waist_t)
            panels.append(PanelGeometry("upper_bodice_panel", 0, bodice_v, 0, bodice_t, True))
            panels.append(PanelGeometry("upper_bodice", 0, bodice_v, 0, bodice_t, True))
            panels.append(PanelGeometry("waist_connection", bodice_v, waist_v, bodice_t, waist_t, True))
            panels.append(PanelGeometry("flared_skirt_drape", bodice_v + waist_v, skirt_v, bodice_t + waist_t, skirt_t, True))

        # Arrays & Normals
        pos_np = np.array(verts, dtype=np.float32)
        idx_np = np.array(tris, dtype=np.uint32)
        norm_np = calculate_smooth_normals(pos_np, idx_np)
        uv_np = np.array(uvs, dtype=np.float32)

        # Rigging (Ara 3D Gen 20 Bones)
        joint_indices, joint_weights = self._compute_skinning(pos_np, is_skirt=is_skirt)
        mesh = GarmentMesh(pos_np, norm_np, uv_np, idx_np, joint_indices, joint_weights)

        # Quality & Provenance
        quality_report = GarmentMeshValidator.validate(mesh)
        observed_mask = identify_observed_surface(pos_np, has_back_view=(back_image is not None))
        obs_count = int(np.sum(observed_mask))
        inf_count = len(pos_np) - obs_count
        obs_ratio = round(obs_count / max(1, len(pos_np)), 3)

        # Multi-Component Graph Construction
        graph = GarmentComponentGraph()

        if is_skirt:
            # 1. Waistband
            wb_v_cnt = n_seg * 2
            wb_t_cnt = 1 * n_seg * 2
            b_min, b_max, dims = compute_component_bounds(pos_np, 0, wb_v_cnt)
            graph.add_node(GarmentComponentNode(
                component_id="waistband",
                category=category,
                semantic_type="waistband",
                parent_id=None,
                dimensions_m=dims,
                bounding_box_3d=(b_min, b_max),
                attachment_location="waist_root",
                material_assignment="main_shell",
                confidence=1.0,
                provenance="pattern_constructed",
                vertex_range=(0, wb_v_cnt),
                triangle_range=(0, wb_t_cnt)
            ))

            # 2. Flared Skirt Drape
            skirt_v_cnt = len(verts) - wb_v_cnt
            skirt_t_cnt = len(tris) - wb_t_cnt
            b_min, b_max, dims = compute_component_bounds(pos_np, wb_v_cnt, skirt_v_cnt)
            graph.add_node(GarmentComponentNode(
                component_id="flared_skirt_drape",
                category=category,
                semantic_type="skirt_drape",
                parent_id="waistband",
                dimensions_m=dims,
                bounding_box_3d=(b_min, b_max),
                attachment_location="waistband_seam",
                material_assignment="main_shell",
                confidence=1.0,
                provenance="pattern_constructed",
                vertex_range=(wb_v_cnt, skirt_v_cnt),
                triangle_range=(wb_t_cnt, skirt_t_cnt)
            ))
        else:
            # 1. Upper Bodice
            bodice_v_cnt = n_seg * 7
            bodice_t_cnt = 6 * n_seg * 2
            b_min, b_max, dims = compute_component_bounds(pos_np, 0, bodice_v_cnt)
            graph.add_node(GarmentComponentNode(
                component_id="upper_bodice",
                category=category,
                semantic_type="bodice",
                parent_id=None,
                dimensions_m=dims,
                bounding_box_3d=(b_min, b_max),
                attachment_location="torso_root",
                material_assignment="main_shell",
                confidence=1.0,
                provenance="pattern_constructed",
                vertex_range=(0, bodice_v_cnt),
                triangle_range=(0, bodice_t_cnt)
            ))

            # 2. Waist Connection Seam
            waist_v_cnt = n_seg * 3
            waist_t_cnt = 3 * n_seg * 2
            b_min, b_max, dims = compute_component_bounds(pos_np, bodice_v_cnt, waist_v_cnt)
            graph.add_node(GarmentComponentNode(
                component_id="waist_connection",
                category=category,
                semantic_type="waist_seam",
                parent_id="upper_bodice",
                dimensions_m=dims,
                bounding_box_3d=(b_min, b_max),
                attachment_location="natural_waist",
                material_assignment="main_shell",
                confidence=1.0,
                provenance="pattern_constructed",
                vertex_range=(bodice_v_cnt, waist_v_cnt),
                triangle_range=(bodice_t_cnt, waist_t_cnt)
            ))

            # 3. Flared Skirt Drape
            skirt_v_cnt = len(verts) - (bodice_v_cnt + waist_v_cnt)
            skirt_t_cnt = len(tris) - (bodice_t_cnt + waist_t_cnt)
            b_min, b_max, dims = compute_component_bounds(pos_np, bodice_v_cnt + waist_v_cnt, skirt_v_cnt)
            graph.add_node(GarmentComponentNode(
                component_id="flared_skirt_drape",
                category=category,
                semantic_type="skirt_drape",
                parent_id="waist_connection",
                dimensions_m=dims,
                bounding_box_3d=(b_min, b_max),
                attachment_location="waist_seam",
                material_assignment="main_shell",
                confidence=1.0,
                provenance="pattern_constructed",
                vertex_range=(bodice_v_cnt + waist_v_cnt, skirt_v_cnt),
                triangle_range=(bodice_t_cnt + waist_t_cnt, skirt_t_cnt)
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

    def _compute_skinning(self, positions: np.ndarray, is_skirt: bool = False) -> Tuple[np.ndarray, np.ndarray]:
        num_verts = len(positions)
        joint_indices = np.zeros((num_verts, 4), dtype=np.uint16)
        joint_weights = np.zeros((num_verts, 4), dtype=np.float32)

        for i in range(num_verts):
            px, py, pz = float(positions[i, 0]), float(positions[i, 1]), float(positions[i, 2])

            if not is_skirt and py > 1.25:
                # Bodice: Spine1 (2) -> Spine2 (3) -> Neck (4)
                s = float(np.clip((py - 1.25) / 0.17, 0.0, 1.0))
                joint_indices[i] = [3, 4, 2, 0]
                joint_weights[i] = [1.0 - s * 0.40, s * 0.40, 0.0, 0.0]
            elif not is_skirt and py > 1.00:
                # Waist: Spine (1) -> Spine1 (2) -> Spine2 (3)
                s = float(np.clip((py - 1.00) / 0.25, 0.0, 1.0))
                joint_indices[i] = [1, 2, 3, 0]
                joint_weights[i] = [(1.0 - s) * 0.50, 0.40, s * 0.50, 0.0]
            elif py > 0.88:
                # Pelvis / Waistband: smooth transition Hips (0) -> Spine (1)
                s = float(np.clip((py - 0.88) / 0.12, 0.0, 1.0))
                joint_indices[i] = [0, 1, 14 if px >= 0 else 17, 0]
                joint_weights[i] = [0.85 - s * 0.35, 0.15 + s * 0.35, 0.0, 0.0]
            else:
                # Continuous flared skirt drape: gradually introduce hip-leg influence without sharp fold at y=0.70
                leg_s = float(np.clip((0.88 - py) / 0.70, 0.0, 1.0))
                side_w = float(np.clip((px + 0.06) / 0.12, 0.0, 1.0))
                w_hip = 0.85 - leg_s * 0.10
                w_spine = 0.15 * (1.0 - leg_s)
                w_leg = 1.0 - w_hip - w_spine
                joint_indices[i] = [0, 1, 14, 17]
                joint_weights[i] = [w_hip, w_spine, w_leg * side_w, w_leg * (1.0 - side_w)]

            w_sum = float(np.sum(joint_weights[i]))
            if w_sum > 1e-6:
                joint_weights[i] /= w_sum
            else:
                joint_weights[i] = [1.0, 0.0, 0.0, 0.0]

        return joint_indices, joint_weights

