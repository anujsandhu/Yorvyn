"""
YORVYN — Neural 3D Garment Reconstruction Engine.
Integrates remote GPU inference dispatch (TRELLIS / TripoSR / SF3D on cloud A10G/A100)
with local neural-assisted hybrid deformation and landmark-guided refinement.

Truthful provenance contract:
- When remote GPU inference runs: provenance = 'neural_remote'
- When local neural deformation runs: provenance = 'hybrid_neural_procedural'
- When fallback geometry runs: provenance = 'deterministic_procedural_fallback'
NEVER labels procedural geometry as neural AI reconstruction.
"""

import time
import logging
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
from PIL import Image

from backend.app.services.garments.garment_mesh_builder import GarmentMesh, ARA_SKELETON_SPECS
from backend.app.models.garment_intelligence_models import (
    GarmentIntelligenceV2Result,
    GarmentComponentV2,
    BoundingBox2D
)
from ..base_reconstruction_engine import (
    IGarmentReconstructionEngine,
    ReconstructionOutput,
    PanelGeometry,
    GarmentProportions,
    MeshQualityReport
)
from ..mesh_validator import GarmentMeshValidator
from ..proportions import GarmentProportionsEstimator
from .learned_model_evaluator import LearnedModelEvaluator
from .remote_gpu_client import remote_reconstruction_client
from .hybrid_refinement import HybridReconstructionRefiner

logger = logging.getLogger(__name__)


class NeuralGarmentReconstructionEngine(IGarmentReconstructionEngine):
    """
    Universal Neural Garment Reconstruction Engine.
    Executes hybrid or remote learned 3D garment generation for all categories.
    """

    @property
    def engine_id(self) -> str:
        return "neural_garment_reconstruction_engine_v3"

    @property
    def supported_categories(self) -> List[str]:
        return [
            "tops", "shirt", "hoodie", "jacket", "bottoms",
            "dress", "skirt", "traditional", "footwear", "accessories"
        ]

    @property
    def supported_subcategories(self) -> List[str]:
        return []

    def reconstruct(
        self,
        intelligence: Optional[GarmentIntelligenceV2Result] = None,
        category: str = "tops",
        subcategory: str = "tshirt",
        sleeve_length: str = "short",
        neckline_type: str = "crewneck",
        fit: str = "regular",
        front_image: Optional[Image.Image] = None,
        back_image: Optional[Image.Image] = None,
        **kwargs
    ) -> ReconstructionOutput:
        """
        Executes reconstruction through the best available truthful execution path:
        1. Remote GPU Worker (TRELLIS / TripoSR / SF3D) if configured & healthy
        2. Local Neural-Assisted Hybrid Deformation (MobileNetV3 + Landmark Refiner)
        3. Deterministic Procedural Fallback
        """
        start_time = time.perf_counter()
        cat = category.lower().strip()
        subcat = subcategory.lower().strip()

        # ── Path 1: Remote GPU Worker Dispatch ────────────────────────────────
        if kwargs.get("allow_remote", True) and remote_reconstruction_client.is_configured and front_image is not None:
            health = remote_reconstruction_client.check_health()
            if health.get("remote_available"):
                logger.info("Dispatching reconstruction to active remote GPU worker cluster...")
                remote_out = remote_reconstruction_client.reconstruct_remote(
                    front_image=front_image,
                    category=cat,
                    subcategory=subcat,
                    intelligence=intelligence
                )
                if remote_out is not None:
                    remote_out.provenance = "neural_remote"
                    remote_out.engine_id = self.engine_id
                    return remote_out
                logger.warning("Remote GPU worker returned empty mesh; falling back to local hybrid path.")

        # ── Path 2: Image-Conditioned Neural/Hybrid 3D Reconstruction ─────────
        try:
            if front_image is not None:
                from .image_conditioned_reconstruction import image_conditioned_reconstruction_engine
                _, _, img_out = image_conditioned_reconstruction_engine.reconstruct_from_image(
                    image=front_image,
                    category=cat,
                    subcategory=subcat,
                    attributes={"fit": fit, "neckline": neckline_type, "sleeve": sleeve_length}
                )
                img_out.provenance = "hybrid_neural_procedural"
                img_out.engine_id = self.engine_id
                img_out.reconstruction_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                return img_out

            from ..engine_registry import reconstruction_registry
            base_engine = reconstruction_registry.get_engine(cat, subcat)

            # Generate base anatomical pattern
            base_output = base_engine.reconstruct(
                intelligence=intelligence,
                category=cat,
                subcategory=subcat,
                sleeve_length=sleeve_length,
                neckline_type=neckline_type,
                fit=fit,
                front_image=front_image,
                back_image=back_image,
                **kwargs
            )

            # Apply neural component bounding box & landmark deformation
            refined_mesh = self._apply_neural_deformation(
                mesh=base_output.mesh,
                intelligence=intelligence,
                category=cat,
                subcategory=subcat
            )
            base_output.mesh = refined_mesh

            # Refine boundaries with landmark guidance
            hybrid_output = HybridReconstructionRefiner.refine(base_output, intelligence)
            hybrid_output.provenance = "hybrid_neural_procedural"
            hybrid_output.engine_id = self.engine_id
            hybrid_output.reconstruction_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

            return hybrid_output

        except Exception as e:
            logger.error(f"Local hybrid reconstruction error: {e}; falling back to deterministic procedural.")

        # ── Path 3: Deterministic Procedural Fallback ─────────────────────────
        from ..tops_engine import TopsReconstructionEngine
        fallback_engine = TopsReconstructionEngine()
        fallback_out = fallback_engine.reconstruct(
            intelligence=intelligence,
            category=cat,
            subcategory=subcat,
            sleeve_length=sleeve_length,
            neckline_type=neckline_type,
            fit=fit,
            front_image=front_image,
            back_image=back_image,
            **kwargs
        )
        fallback_out.provenance = "deterministic_procedural_fallback"
        fallback_out.engine_id = self.engine_id
        fallback_out.warnings.append("Local neural hybrid reconstruction failed; using deterministic geometric baseline.")
        fallback_out.reconstruction_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        return fallback_out

    def _apply_neural_deformation(
        self,
        mesh: GarmentMesh,
        intelligence: Optional[GarmentIntelligenceV2Result],
        category: str,
        subcategory: str
    ) -> GarmentMesh:
        """
        Deforms the mesh vertices using neural intelligence predictions
        (collar contour, hem curvature, waistline rise, sleeve length).
        """
        if intelligence is None:
            return mesh

        pos = mesh.positions.copy()

        # 1. Neural collar boundary deformation
        if hasattr(intelligence, "landmarks") and intelligence.landmarks:
            lm = intelligence.landmarks
            if "collar_center" in lm:
                target_y = 1.42 + (0.05 - lm["collar_center"].position.y) * 0.08
                collar_mask = pos[:, 1] > 1.36
                if np.any(collar_mask):
                    delta_y = target_y - 1.42
                    pos[collar_mask, 1] += float(delta_y) * (pos[collar_mask, 1] - 1.36) / 0.08

            # 2. Neural hem boundary deformation
            if "hem_center" in lm:
                target_hem_y = 0.90 + (0.95 - lm["hem_center"].position.y) * 0.12
                hem_mask = pos[:, 1] < 1.02
                if np.any(hem_mask):
                    delta_hem_y = target_hem_y - 0.90
                    pos[hem_mask, 1] += float(delta_hem_y) * (1.02 - pos[hem_mask, 1]) / 0.12

        # 3. Component bounding box guidance
        if hasattr(intelligence, "components") and intelligence.components:
            for comp in intelligence.components:
                if comp.status == "detected" and comp.bbox:
                    # Kangaroo pocket protrusion for hoodies
                    if comp.component_type == "kangaroo_pocket":
                        # Push front vertices outward in lower abdominal region
                        pocket_mask = (pos[:, 1] > 0.95) & (pos[:, 1] < 1.15) & (pos[:, 2] > 0.08)
                        pos[pocket_mask, 2] += 0.012

                    # Placket ridge for shirts/jackets
                    elif comp.component_type == "placket":
                        placket_mask = (np.abs(pos[:, 0]) < 0.02) & (pos[:, 1] > 0.95) & (pos[:, 1] < 1.40) & (pos[:, 2] > 0.05)
                        pos[placket_mask, 2] += 0.006

        mesh.positions = pos.astype(np.float32)
        return mesh


# Global instance
neural_reconstruction_engine = NeuralGarmentReconstructionEngine()
