"""
Garment Intelligence Package.
Provides universal taxonomy classification, component/landmark detection,
confidence validation, multi-view reasoning, and developer diagnostics.
"""

from .universal_garment_classifier import UniversalGarmentClassifier, universal_garment_classifier
from .component_detector import ComponentDetector, component_detector
from .confidence_engine import ConfidenceEngine, confidence_engine
from .multiview_engine import MultiViewEngine, multiview_engine
from .garment_intelligence_service import GarmentIntelligenceService, garment_intelligence_service
from .universal_garment_intelligence_model import (
    UniversalGarmentIntelligenceModel,
    universal_intelligence_model,
    UniversalGarmentIntelligenceOutput,
    MultiTaskGarmentNeuralNetwork
)
from .learned_multiview_engine import LearnedMultiViewEngine, learned_multiview_engine
from .learned_material_engine import LearnedMaterialEngine, learned_material_engine

__all__ = [
    "UniversalGarmentClassifier",
    "universal_garment_classifier",
    "ComponentDetector",
    "component_detector",
    "ConfidenceEngine",
    "confidence_engine",
    "MultiViewEngine",
    "multiview_engine",
    "GarmentIntelligenceService",
    "garment_intelligence_service",
    "UniversalGarmentIntelligenceModel",
    "universal_intelligence_model",
    "UniversalGarmentIntelligenceOutput",
    "MultiTaskGarmentNeuralNetwork",
    "LearnedMultiViewEngine",
    "learned_multiview_engine",
    "LearnedMaterialEngine",
    "learned_material_engine"
]

