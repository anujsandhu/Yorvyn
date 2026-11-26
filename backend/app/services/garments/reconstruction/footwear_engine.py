"""
YORVYN — Footwear 3D Garment Reconstruction Engine
Reconstructs sneakers, running shoes, boots, and formal shoes:
- Outsole Platform & Tread Base Slab
- Midsole Layer & Cushioning Profile
- Lofted Upper Shell (Toe Box, Vamp, Lateral/Medial Quarters, Heel Counter)
- Padded Collar / Ankle Entry Opening Loop
- Dual Footwear Units: Left Foot and Right Foot
- Skinned to Ara 3D Gen Feet (Bones 16 & 19) and Lower Legs (Bones 15 & 18)
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
    compute_footwear_skinning,
    identify_observed_surface
)
from .mesh_validator import GarmentMeshValidator
from .proportions import GarmentProportionsEstimator


class FootwearReconstructionEngine(IGarmentReconstructionEngine):
    """Engine for sneakers, athletic shoes, boots, and footwear."""

    @property
    def engine_id(self) -> str:
        return "footwear_pattern_engine_v1"

    @property
    def supported_categories(self) -> List[str]:
        return ["footwear", "shoes", "sneakers"]

    @property
    def supported_subcategories(self) -> List[str]:
        return ["sneakers", "running_shoes", "boots", "formal_shoes", "sandals", "slippers"]

    def reconstruct(
        self,
        intelligence: Optional[GarmentIntelligenceV2Result] = None,
        category: str = "footwear",
        subcategory: str = "sneakers",
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

        is_boot = "boot" in subcategory.lower()
        collar_top_y = 0.18 if is_boot else 0.085
        sole_h = 0.032

        # Canonical Ara 3D Gen Foot Centers: LeftFoot (X = +0.098), RightFoot (X = -0.098)
        foot_configs = [
            ("left_footwear", 1.0, 0.098),
            ("right_footwear", -1.0, -0.098)
        ]

        # Foot length parameters (meters)
        # Z: Heel at -0.065, Ball of foot at +0.08, Toe at +0.165
        z_toe = 0.165
        z_heel = -0.065

        shoe_seg = 16

        for panel_name, side, center_x in foot_configs:
            shoe_start_v = len(verts)
            shoe_start_t = len(tris)

            # Lofted Rings from Ground Sole up to Ankle Opening
            # Format: (y, half_width, z_front, z_back)
            rings_spec = [
                (0.002, 0.052, z_toe, z_heel),                     # 0: Sole bottom / tread
                (sole_h, 0.050, z_toe - 0.005, z_heel + 0.005),   # 1: Midsole top / welt seam
                (sole_h + 0.025, 0.046, z_toe - 0.015, z_heel + 0.010), # 2: Lower upper / toe box
                (collar_top_y, 0.038, 0.075, 0.005),              # 3: Padded ankle collar opening
            ]

            ring_starts: List[int] = []
            for r_idx, (y, hw, zf, zb) in enumerate(rings_spec):
                ring_starts.append(len(verts))
                frac_y = r_idx / (len(rings_spec) - 1)
                zc = (zf + zb) * 0.5
                zl = (zf - zb) * 0.5

                for i in range(shoe_seg):
                    th = 2.0 * math.pi * i / shoe_seg
                    # Elliptical ring centered at (center_x, y, zc)
                    px = center_x + hw * math.cos(th)
                    pz = zc + zl * math.sin(th)

                    nx = math.cos(th)
                    nz = math.sin(th)
                    ny = -0.2 if r_idx == 0 else (0.4 if r_idx == len(rings_spec) - 1 else 0.0)
                    norm_len = math.hypot(nx, ny, nz) or 1.0

                    verts.append([px, y, pz])
                    norms.append([nx / norm_len, ny / norm_len, nz / norm_len])

                    u = (0.75 if side > 0 else 0.25) + 0.22 * math.cos(th)
                    v = 0.10 + frac_y * 0.80
                    uvs.append([u, v])

            # Connect rings
            for r in range(len(rings_spec) - 1):
                add_quad_strip(tris, ring_starts[r], ring_starts[r + 1], shoe_seg, closed=True)

            shoe_v_cnt = len(verts) - shoe_start_v
            shoe_t_cnt = len(tris) - shoe_start_t
            panels.append(PanelGeometry(panel_name, shoe_start_v, shoe_v_cnt, shoe_start_t, shoe_t_cnt, True))

        # Finalize Geometry & Normals
        pos_np = np.array(verts, dtype=np.float32)
        idx_np = np.array(tris, dtype=np.uint32)
        norm_np = calculate_smooth_normals(pos_np, idx_np)
        uv_np = np.array(uvs, dtype=np.float32)

        # Skeletal Rigging
        joint_indices, joint_weights = compute_footwear_skinning(pos_np)
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

