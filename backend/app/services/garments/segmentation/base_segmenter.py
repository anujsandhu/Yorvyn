"""
Base Interfaces and Output Types for Garment Segmentation.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from PIL import Image
from pydantic import BaseModel, Field, ConfigDict
import io
import base64


class GarmentSegmentationOutput(BaseModel):
    """
    Standardized result contract for all neural and geometric garment segmenters.
    Zero background bleed; preserves internal holes, sleeve gaps, and thin straps.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())

    segmented_image: Image.Image
    alpha_mask: np.ndarray
    outer_contour: List[List[int]]  # [[x, y], ...]
    holes: List[List[List[int]]]    # [[[x, y], ...], ...]
    bbox: Tuple[int, int, int, int] # (min_x, min_y, max_x, max_y)
    silhouette_quality: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    edge_sharpness: float
    compactness: float
    model_id: str
    model_version: str
    processing_time_ms: float
    warnings: List[str] = Field(default_factory=list)

    # Phase 11B: On-Body & Human Parsing Telemetry
    image_type: Optional[str] = None  # "isolated_product", "flat_lay", "on_body", "lifestyle_fashion", "ambiguous_unsupported"
    target_garment_class: Optional[str] = None
    occlusion_mask: Optional[np.ndarray] = None
    occlusion_ratio: float = 0.0
    visible_surface_ratio: float = 1.0
    inferred_surface_ratio: float = 0.0
    detected_body_parts: Dict[str, float] = Field(default_factory=dict)
    human_parsing_map: Optional[Image.Image] = None

    def to_alpha_mask_png_bytes(self) -> bytes:
        mask_pil = Image.fromarray(self.alpha_mask.astype(np.uint8), mode="L")
        buf = io.BytesIO()
        mask_pil.save(buf, format="PNG")
        return buf.getvalue()

    def to_alpha_mask_data_url(self) -> str:
        png_bytes = self.to_alpha_mask_png_bytes()
        b64 = base64.b64encode(png_bytes).decode("ascii")
        return f"data:image/png;base64,{b64}"

    def to_segmented_preview_data_url(self) -> str:
        buf = io.BytesIO()
        self.segmented_image.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"

    def to_human_parsing_data_url(self) -> Optional[str]:
        if self.human_parsing_map is None:
            return None
        buf = io.BytesIO()
        self.human_parsing_map.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"

    def to_occlusion_mask_data_url(self) -> Optional[str]:
        if self.occlusion_mask is None:
            return None
        mask_pil = Image.fromarray((self.occlusion_mask * 255).astype(np.uint8), mode="L")
        buf = io.BytesIO()
        mask_pil.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"


class IGarmentSegmenter(ABC):
    """Abstract interface for all garment segmentation model adapters."""

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Unique identifier for this segmenter adapter."""
        pass

    @property
    @abstractmethod
    def model_version(self) -> str:
        """Version string of the underlying model/algorithm."""
        pass

    @abstractmethod
    def segment(self, image: Image.Image) -> GarmentSegmentationOutput:
        """
        Executes foreground garment segmentation on the given PIL image.
        Returns GarmentSegmentationOutput containing alpha mask, transparent image,
        outer boundary contour, internal opening holes, and quality metrics.
        """
        pass

