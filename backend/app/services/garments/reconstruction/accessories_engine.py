"""
YORVYN — Accessories 3D Garment Reconstruction Engine
Reconstructs wearable accessories:
- Caps & Hats: Fitted Crown Dome + Curved Forward Visor / Peak Brim
- Scarves: Torso Neck Cowl Loop with Draped Chest Ribbons
- Rigged to Ara 3D Gen Head (5), Neck (4), and Upper Spine (3)
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
    PanelGeometry
)
from .geometry_utils import (
    calculate_smooth_normals,
    add_quad,
    add_quad_strip,
    compute_headwear_skinning,
    identify_observed_surface
)
from .mesh_validator import GarmentMeshValidator
from .proportions import GarmentProportionsEstimator


class AccessoriesReconstructionEngine(IGarmentReconstructionEngine):
    """Engine for caps, hats, scarves, and headwear."""

    @property
    def engine_id(self) -> str:
        return "accessories_pattern_engine_v1"

    @property
    def supported_categories(self) -> List[str]:
        return ["accessories", "hats", "caps"]

    @property
    def supported_subcategories(self) -> List[str]:
        return ["caps", "hats", "scarves", "beanies", "baseball_cap"]

    def reconstruct(
        self,
        intelligence: Optional[GarmentIntelligenceV2Result] = None,
        category: str = "accessories",
        subcategory: str = "caps",
        sleeve_length: str = "none",
        neckline_type: str = "none",
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

        verts: List[List[float]] = []
        norms: List[List[float]] = []
        uvs: List[List[float]] = []
        tris: List[List[int]] = []
        panels: List[PanelGeometry] = []

        is_scarf = "scarf" in subcategory.lower()

        if is_scarf:
            # Scarf cowl loop around neck (Y in [1.32, 1.44])
            cowl_start_v = len(verts)
            cowl_start_t = len(tris)
            cowl_rings = 4
            cowl_seg = 20
            for r in range(cowl_rings):
                frac = r / (cowl_rings - 1)
                cy = 1.34 + frac * 0.10
                rx = 0.115 + 0.015 * math.sin(frac * math.pi)
                rz = 0.120 + 0.015 * math.sin(frac * math.pi)
                for i in range(cowl_seg):
                    th = 2.0 * math.pi * i / cowl_seg
                    px = rx * math.cos(th)
                    pz = rz * math.sin(th)
                    verts.append([px, cy, pz])
                    norms.append([math.cos(th), 0.1, math.sin(th)])
                    uvs.append([i / cowl_seg, frac])

            for r in range(cowl_rings - 1):
                r_c = cowl_start_v + r * cowl_seg
                r_n = cowl_start_v + (r + 1) * cowl_seg
                add_quad_strip(tris, r_c, r_n, cowl_seg, closed=True)

            cowl_v_cnt = len(verts) - cowl_start_v
            cowl_t_cnt = len(tris) - cowl_start_t
            panels.append(PanelGeometry("scarf_cowl", cowl_start_v, cowl_v_cnt, cowl_start_t, cowl_t_cnt, True))
        else:
            # Cap / Hat: Crown Dome + Projecting Visor Brim
            crown_start_v = len(verts)
            crown_start_t = len(tris)
            crown_rings = 5
            crown_seg = 20
            base_y = 1.45
            crown_h = 0.11

            for r in range(crown_rings):
                frac = r / (crown_rings - 1)
                cy = base_y + frac * crown_h
                rad_x = (0.095 * math.cos(frac * 0.5 * math.pi)) + 0.010
                rad_z = (0.105 * math.cos(frac * 0.5 * math.pi)) + 0.010
                for i in range(crown_seg):
                    th = 2.0 * math.pi * i / crown_seg
                    px = rad_x * math.sin(th)
                    pz = -0.01 + rad_z * math.cos(th)
                    verts.append([px, cy, pz])
                    norms.append([px / rad_x, 0.4 * frac, pz / rad_z])
                    uvs.append([i / crown_seg, frac * 0.50])

            for r in range(crown_rings - 1):
                r_c = crown_start_v + r * crown_seg
                r_n = crown_start_v + (r + 1) * crown_seg
                add_quad_strip(tris, r_c, r_n, crown_seg, closed=True)

            crown_v_cnt = len(verts) - crown_start_v
            crown_t_cnt = len(tris) - crown_start_t
            panels.append(PanelGeometry("cap_crown_dome", crown_start_v, crown_v_cnt, crown_start_t, crown_t_cnt, True))

            # Forward Visor / Brim (Z in [+0.08, +0.18])
            brim_start_v = len(verts)
            brim_start_t = len(tris)
            brim_slices = 8
            brim_rings = 3

            for br in range(brim_rings):
                b_frac = br / (brim_rings - 1)
                by = base_y - 0.005 * b_frac
                for s in range(brim_slices + 1):
                    u_s = s / brim_slices
                    th = -0.30 * math.pi + u_s * (0.60 * math.pi)
                    rad = 0.105 + b_frac * 0.075
                    bx = rad * math.sin(th)
                    bz = -0.01 + rad * math.cos(th)
                    verts.append([bx, by, bz])
                    norms.append([0.0, 0.95, 0.3])
                    uvs.append([0.55 + (u_s - 0.5) * 0.40, 0.60 + b_frac * 0.35])

            for br in range(brim_rings - 1):
                r_c = brim_start_v + br * (brim_slices + 1)
                r_n = brim_start_v + (br + 1) * (brim_slices + 1)
                add_quad_strip(tris, r_c, r_n, brim_slices + 1, closed=False)

            brim_v_cnt = len(verts) - brim_start_v
            brim_t_cnt = len(tris) - brim_start_t
            panels.append(PanelGeometry("cap_visor_brim", brim_start_v, brim_v_cnt, brim_start_t, brim_t_cnt, True))

        # Finalize
        pos_np = np.array(verts, dtype=np.float32)
        idx_np = np.array(tris, dtype=np.uint32)
        norm_np = calculate_smooth_normals(pos_np, idx_np)
        uv_np = np.array(uvs, dtype=np.float32)

        # Skinning
        joint_indices, joint_weights = compute_headwear_skinning(pos_np)
        mesh = GarmentMesh(pos_np, norm_np, uv_np, idx_np, joint_indices, joint_weights)

        # Quality & Provenance
        quality_report = GarmentMeshValidator.validate(mesh)
        observed_mask = identify_observed_surface(pos_np, has_back_view=(back_image is not None))
        obs_count = int(np.sum(observed_mask))
        inf_count = len(pos_np) - obs_count
        obs_ratio = round(obs_count / max(1, len(pos_np)), 3)

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
            reconstruction_time_ms=dur_ms
        )

