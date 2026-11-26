"""
YORVYN — Universal 3D Garment Reconstruction Base Interfaces
Defines abstract contracts for category-specific 3D garment reconstruction,
panel-based geometry representation, quality validation, and provenance tracking.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import numpy as np

from backend.app.services.garments.garment_mesh_builder import GarmentMesh, ARA_SKELETON_SPECS
from backend.app.models.garment_intelligence_models import GarmentIntelligenceV2Result


@dataclass
class MeshQualityReport:
    """Rigorous mesh quality telemetry."""
    is_valid: bool
    is_manifold: bool
    has_degenerate_triangles: bool
    degenerate_triangle_count: int
    vertex_count: int
    triangle_count: int
    boundary_loops: int
    non_finite_vertex_count: int
    issues: List[str] = field(default_factory=list)
    quality_score: float = 1.0  # 0.0 to 1.0


@dataclass
class PanelGeometry:
    """Named garment pattern panel with distinct topology and spatial role."""
    name: str
    vertex_start_idx: int
    vertex_count: int
    triangle_start_idx: int
    triangle_count: int
    is_observed: bool  # True if directly visible in input photographs, False if inferred/posterior


@dataclass
class GarmentProportions:
    """Estimated physical ease and anatomical proportions."""
    category: str
    subcategory: str
    fit: str
    shoulder_width_m: float
    chest_width_m: float
    waist_width_m: float
    hem_width_m: float
    torso_length_m: float
    sleeve_length_m: float
    inseam_length_m: float
    ease_margin_m: float
    scale_calibration: str  # "Ara3D_humanoid_canonical_1.75m" or "uncalibrated_2d_relative"
    confidence: float


@dataclass
class GarmentComponentNode:
    """Explicit structural component in the 3D garment hierarchy."""
    component_id: str
    category: str
    semantic_type: str  # "torso", "sleeve", "hood", "pocket", "collar", "placket", "cuff", "waistband", "drawstring", "leg", "skirt_drape", "bodice", "hardware"
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    dimensions_m: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # (width_x, height_y, depth_z)
    bounding_box_3d: Tuple[Tuple[float, float, float], Tuple[float, float, float]] = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    source_image_region: Optional[Dict[str, float]] = None
    attachment_location: str = "torso_root"
    material_assignment: str = "main_shell"
    confidence: float = 1.0
    provenance: str = "pattern_constructed"
    vertex_range: Tuple[int, int] = (0, 0)  # (start_idx, count)
    triangle_range: Tuple[int, int] = (0, 0)  # (start_idx, count)
    depth_confidence: float = 0.65  # Single-view default vs multi-view calibrated
    uncertainty_status: str = "estimated_single_view"
    representation_type: str = "GEOMETRIC_MESH"  # "GEOMETRIC_MESH", "SURFACE_RELIEF", "TEXTURE_ONLY", "NOT_APPLICABLE", "NOT_RECONSTRUCTED"


@dataclass
class GarmentComponentGraph:
    """Directed acyclic graph representing semantic and spatial composition of a garment."""
    nodes: Dict[str, GarmentComponentNode] = field(default_factory=dict)
    root_ids: List[str] = field(default_factory=list)

    def add_node(self, node: GarmentComponentNode) -> None:
        self.nodes[node.component_id] = node
        if not node.parent_id:
            if node.component_id not in self.root_ids:
                self.root_ids.append(node.component_id)
        else:
            if node.parent_id in self.nodes:
                if node.component_id not in self.nodes[node.parent_id].children_ids:
                    self.nodes[node.parent_id].children_ids.append(node.component_id)

    def get_node(self, component_id: str) -> Optional[GarmentComponentNode]:
        return self.nodes.get(component_id)

    def get_children(self, component_id: str) -> List[GarmentComponentNode]:
        node = self.nodes.get(component_id)
        if not node:
            return []
        return [self.nodes[cid] for cid in node.children_ids if cid in self.nodes]

    def get_topological_order(self) -> List[GarmentComponentNode]:
        ordered: List[GarmentComponentNode] = []
        visited = set()

        def _traverse(node_id: str):
            if node_id in visited:
                return
            visited.add(node_id)
            if node_id in self.nodes:
                node = self.nodes[node_id]
                ordered.append(node)
                for child_id in node.children_ids:
                    _traverse(child_id)

        for root_id in self.root_ids:
            _traverse(root_id)
        for node_id, node in self.nodes.items():
            if node_id not in visited:
                visited.add(node_id)
                ordered.append(node)
        return ordered

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_ids": self.root_ids,
            "node_count": len(self.nodes),
            "nodes": {
                nid: {
                    "component_id": n.component_id,
                    "category": n.category,
                    "semantic_type": n.semantic_type,
                    "parent_id": n.parent_id,
                    "children_ids": n.children_ids,
                    "dimensions_m": list(n.dimensions_m),
                    "bounding_box_3d": [list(n.bounding_box_3d[0]), list(n.bounding_box_3d[1])],
                    "source_image_region": n.source_image_region,
                    "attachment_location": n.attachment_location,
                    "material_assignment": n.material_assignment,
                    "confidence": n.confidence,
                    "provenance": n.provenance,
                    "vertex_range": list(n.vertex_range),
                    "triangle_range": list(n.triangle_range),
                    "depth_confidence": n.depth_confidence,
                    "uncertainty_status": n.uncertainty_status,
                }
                for nid, n in self.nodes.items()
            }
        }


def compute_component_bounds(
    verts: np.ndarray,
    v_start: int,
    v_count: int
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]:
    """Calculates min_xyz, max_xyz, and (width, height, depth) dimensions in meters."""
    if v_count <= 0 or v_start >= len(verts):
        return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    sub = verts[v_start:v_start + v_count]
    min_pt = sub.min(axis=0)
    max_pt = sub.max(axis=0)
    dims = max_pt - min_pt
    return (
        (float(min_pt[0]), float(min_pt[1]), float(min_pt[2])),
        (float(max_pt[0]), float(max_pt[1]), float(max_pt[2])),
        (round(float(dims[0]), 4), round(float(dims[1]), 4), round(float(dims[2]), 4))
    )


@dataclass
class ReconstructionOutput:
    """Comprehensive output from a category-specific reconstruction engine."""
    mesh: GarmentMesh
    panels: List[PanelGeometry]
    quality_report: MeshQualityReport
    proportions: GarmentProportions
    observed_vertex_count: int
    inferred_vertex_count: int
    observed_surface_ratio: float  # observed / total
    provenance: str  # "pattern_constructed", "learned_neural", "procedural", "hybrid_refined"
    engine_id: str
    reconstruction_time_ms: float
    warnings: List[str] = field(default_factory=list)
    component_graph: Optional[GarmentComponentGraph] = None
    engine_identity: str = "yorvyn_hybrid_reconstruction_engine"
    engine_mode: str = "hybrid_reconstruction"  # "neural_reconstruction", "parametric_reconstruction", "hybrid_reconstruction"
    engine_version: str = "14.10.0"
    model_id: Optional[str] = "mattmdjaga/segformer_b2_clothes"
    model_version: Optional[str] = "14.10.0"
    checkpoint_sha256: Optional[str] = None  # Genuine neural 3D checkpoint hash, or None for procedural
    segmentation_checkpoint_sha256: Optional[str] = "8f86fd90c567afd4370b3cc3a7e81ed767a632b2832a738331af660acc0c4c68"
    source_code_revision: str = "7139fc7eea4e1f890e28da9140db2e8550081267"
    configuration_sha256: Optional[str] = None
    input_image_sha256: Optional[str] = None
    input_image_hash: Optional[str] = None  # Alias for backward compatibility
    output_glb_sha256: Optional[str] = None
    inference_device: str = "mps"
    inference_endpoint: str = "local_mps_in_process"
    reconstruction_timestamp: Optional[str] = None
    raw_model_output_location: Optional[str] = None
    post_processing_operations: List[str] = field(default_factory=list)
    fallback_reason: Optional[str] = None
    provenance_signature: Optional[str] = None


class IGarmentReconstructionEngine(ABC):
    """
    Abstract interface for all category-specific 3D garment reconstruction engines.
    Every engine must consume structured Phase 2 Garment Intelligence and generate
    anatomically accurate, panel-constructed, skinned 3D geometry.
    """

    @property
    @abstractmethod
    def engine_id(self) -> str:
        """Unique identifier of the reconstruction engine."""
        pass

    @property
    @abstractmethod
    def supported_categories(self) -> List[str]:
        """List of taxonomy categories supported by this engine."""
        pass

    @property
    @abstractmethod
    def supported_subcategories(self) -> List[str]:
        """List of taxonomy subcategories supported by this engine."""
        pass

    @abstractmethod
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
        """
        Executes panel-based 3D reconstruction for the target garment category.
        Returns rigged, quality-validated geometry with transparent provenance.
        """
        pass

