"""
YORVYN — Universal 3D Garment Reconstruction Module
Provides modular, category-specific reconstruction engines, quality validation,
Ara 3D Gen 20-bone skeletal rigging, proportions estimation, and multi-view fusion.
"""

from .base_reconstruction_engine import (
    IGarmentReconstructionEngine,
    ReconstructionOutput,
    PanelGeometry,
    MeshQualityReport,
    GarmentProportions
)
from .mesh_validator import GarmentMeshValidator
from .proportions import GarmentProportionsEstimator
from .geometry_utils import (
    calculate_smooth_normals,
    add_quad,
    add_quad_strip,
    compute_torso_skinning,
    compute_bottoms_skinning,
    compute_footwear_skinning,
    compute_headwear_skinning,
    identify_observed_surface
)
from .tops_engine import TopsReconstructionEngine
from .shirt_engine import ShirtReconstructionEngine
from .hoodie_engine import HoodieReconstructionEngine
from .jacket_engine import JacketReconstructionEngine
from .bottoms_engine import BottomsReconstructionEngine
from .dress_engine import DressReconstructionEngine
from .traditional_engine import TraditionalWearReconstructionEngine
from .footwear_engine import FootwearReconstructionEngine
from .accessories_engine import AccessoriesReconstructionEngine
from .neural.neural_reconstruction_engine import NeuralGarmentReconstructionEngine, neural_reconstruction_engine
from .engine_registry import ReconstructionEngineRegistry, reconstruction_registry
from .multi_view_fuser import MultiViewGarmentFuser

__all__ = [
    "IGarmentReconstructionEngine",
    "ReconstructionOutput",
    "PanelGeometry",
    "MeshQualityReport",
    "GarmentProportions",
    "GarmentMeshValidator",
    "GarmentProportionsEstimator",
    "calculate_smooth_normals",
    "add_quad",
    "add_quad_strip",
    "compute_torso_skinning",
    "compute_bottoms_skinning",
    "compute_footwear_skinning",
    "compute_headwear_skinning",
    "identify_observed_surface",
    "TopsReconstructionEngine",
    "ShirtReconstructionEngine",
    "HoodieReconstructionEngine",
    "JacketReconstructionEngine",
    "BottomsReconstructionEngine",
    "DressReconstructionEngine",
    "TraditionalWearReconstructionEngine",
    "FootwearReconstructionEngine",
    "AccessoriesReconstructionEngine",
    "NeuralGarmentReconstructionEngine",
    "neural_reconstruction_engine",
    "ReconstructionEngineRegistry",
    "reconstruction_registry",
    "MultiViewGarmentFuser"
]

