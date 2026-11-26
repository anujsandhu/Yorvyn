"""
Segmenter Registry and Benchmarking Harness for Garment Segmentation Models.
Enables pluggable model adapters and cross-model performance comparison.
"""

import time
from typing import Dict, List, Any, Optional
from PIL import Image

from .base_segmenter import IGarmentSegmenter, GarmentSegmentationOutput
from .opencv_contour_segmenter import OpenCVContourSegmenter
from .neural_birefnet_segmenter import NeuralBiRefNetSegmenter
from .human_parsing_segmenter import HumanParsingSegmenter, human_parsing_segmenter


class SegmenterRegistry:
    """Registry maintaining active and candidate segmentation adapters."""

    def __init__(self):
        self._segmenters: Dict[str, IGarmentSegmenter] = {}
        self._default_name: str = "opencv_contour"
        self._register_defaults()

    def _register_defaults(self):
        self.register("opencv_contour", OpenCVContourSegmenter())
        self.register("neural_birefnet", NeuralBiRefNetSegmenter())
        self.register("human_parsing", human_parsing_segmenter)

        # If neural model is ready, prefer neural; otherwise default to opencv
        neural = self._segmenters.get("neural_birefnet")
        if isinstance(neural, NeuralBiRefNetSegmenter) and neural.is_neural_ready:
            self._default_name = "neural_birefnet"
        else:
            self._default_name = "opencv_contour"

    def register(self, name: str, segmenter: IGarmentSegmenter):
        self._segmenters[name] = segmenter

    def get(self, name: Optional[str] = None) -> IGarmentSegmenter:
        target = name or self._default_name
        if target not in self._segmenters:
            raise KeyError(f"Segmenter '{target}' is not registered. Available: {list(self._segmenters.keys())}")
        return self._segmenters[target]

    def list_available(self) -> List[str]:
        return list(self._segmenters.keys())

    def benchmark_all(self, image: Image.Image) -> Dict[str, Dict[str, Any]]:
        """
        Executes all registered segmenters on the identical input image to record
        comparative metrics: latency, contour complexity, compactness, and hole detection.
        """
        results: Dict[str, Dict[str, Any]] = {}
        for name, seg in self._segmenters.items():
            t0 = time.perf_counter()
            out = seg.segment(image)
            dt_ms = (time.perf_counter() - t0) * 1000.0

            results[name] = {
                "model_id": out.model_id,
                "model_version": out.model_version,
                "latency_ms": round(dt_ms, 2),
                "silhouette_quality": round(out.silhouette_quality, 3),
                "confidence": round(out.confidence, 3),
                "edge_sharpness": round(out.edge_sharpness, 2),
                "compactness": round(out.compactness, 3),
                "outer_contour_pts": len(out.outer_contour),
                "holes_count": len(out.holes),
                "warnings_count": len(out.warnings)
            }
        return results


# Global singleton registry
segmenter_registry = SegmenterRegistry()

