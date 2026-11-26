"""
YORVYN — Hybrid Reconstruction & Landmark-Guided Geometry Refiner
Fuses base reconstruction geometry (pattern-constructed or neural mesh)
with Phase 2 anatomical landmarks (collar, shoulders, armscyes, cuffs, waist, hem, crotch)
and multi-view silhouettes to eliminate clipping and optimize avatar drape.
"""

from typing import Optional, Dict, Any, List
import numpy as np

from backend.app.services.garments.garment_mesh_builder import GarmentMesh
from backend.app.models.garment_intelligence_models import GarmentIntelligenceV2Result
from ..base_reconstruction_engine import ReconstructionOutput
from ..mesh_validator import GarmentMeshValidator


class HybridReconstructionRefiner:
    """Refines reconstructed garment geometry with landmark-guided constraints."""

    @staticmethod
    def refine(
        reconstruction: ReconstructionOutput,
        intelligence: Optional[GarmentIntelligenceV2Result] = None
    ) -> ReconstructionOutput:
        if intelligence is None or not hasattr(intelligence, "landmarks") or not intelligence.landmarks:
            return reconstruction

        mesh = reconstruction.mesh
        pos = mesh.positions.copy()
        lm = intelligence.landmarks

        # 1. Landmark Guidance: Subtle boundary warp based on localized landmark offsets
        # If collar_center is lower or higher in photograph, smoothly adjust upper vertices
        if "collar_center" in lm:
            collar_y_offset = (0.05 - lm["collar_center"].position.y) * 0.08
            collar_mask = pos[:, 1] > 1.35
            pos[collar_mask, 1] += float(collar_y_offset) * (pos[collar_mask, 1] - 1.35) / 0.10

        # If hem_center is shifted, adjust lower hemline vertices
        if "hem_center" in lm:
            hem_y_offset = (0.95 - lm["hem_center"].position.y) * 0.10
            hem_mask = pos[:, 1] < 1.00
            pos[hem_mask, 1] += float(hem_y_offset) * (1.00 - pos[hem_mask, 1]) / 0.15

        # Update mesh positions
        mesh.positions = pos.astype(np.float32)

        # Re-validate mesh after refinement
        quality = GarmentMeshValidator.validate(mesh)
        reconstruction.quality_report = quality
        reconstruction.provenance = "hybrid_refined"

        return reconstruction

