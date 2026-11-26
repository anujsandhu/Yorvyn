"""
Garment Segmentation Package.
Provides pluggable neural and geometric boundary isolation adapters.
"""

from .base_segmenter import IGarmentSegmenter, GarmentSegmentationOutput
from .opencv_contour_segmenter import OpenCVContourSegmenter
from .neural_birefnet_segmenter import NeuralBiRefNetSegmenter
from .human_parsing_segmenter import HumanParsingSegmenter, human_parsing_segmenter
from .segmenter_registry import SegmenterRegistry, segmenter_registry

__all__ = [
    "IGarmentSegmenter",
    "GarmentSegmentationOutput",
    "OpenCVContourSegmenter",
    "NeuralBiRefNetSegmenter",
    "HumanParsingSegmenter",
    "human_parsing_segmenter",
    "SegmenterRegistry",
    "segmenter_registry"
]

