"""
YORVYN — Analytic relative-disparity heuristic
Uses image intensity, blur residuals and a torso prior; it does not load Depth Anything V2.
"""

import time
import logging
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
import numpy as np
from PIL import Image
import cv2

import torch

logger = logging.getLogger(__name__)


@dataclass
class DepthAnythingOutput:
    relative_depth: np.ndarray      # (H, W) float32 in [0, 1]
    confidence_map: np.ndarray      # (H, W) float32 in [0, 1]
    fold_relief_map: np.ndarray     # (H, W) float32 high-pass gradient
    latency_ms: float
    device: str
    model_name: str = "Analytic relative-disparity heuristic (not Depth Anything V2)"
    metric_calibrated: bool = False


class DepthAnythingV2Adapter:
    """Heuristic relative disparity estimator; not a learned depth model."""

    def __init__(self, device: Optional[str] = None):
        if device is None:
            self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        else:
            self.device = device
        self.model_name = "Analytic relative-disparity heuristic (not Depth Anything V2)"
        logger.info(f"DepthAnythingV2Adapter initialized on {self.device}")

    def estimate_depth(
        self,
        image: Image.Image,
        silhouette_mask: Optional[np.ndarray] = None
    ) -> DepthAnythingOutput:
        """
        Estimates normalized relative depth disparity and surface fold relief.
        """
        t0 = time.perf_counter()
        img_np = np.array(image.convert("RGB"))
        h, w = img_np.shape[:2]

        if silhouette_mask is None:
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            bg_is_light = float(np.mean(gray[:10, :10])) > 180.0
            thresh_type = cv2.THRESH_BINARY_INV if bg_is_light else cv2.THRESH_BINARY
            _, silhouette_mask = cv2.threshold(gray, 0, 255, thresh_type + cv2.THRESH_OTSU)

        # Multi-scale Gaussian gradient disparity
        gray_f = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
        g_blur = cv2.GaussianBlur(gray_f, (15, 15), 0)

        # Parabolic anterior chest fullness prior
        y_coords, x_coords = np.mgrid[0:h, 0:w]
        cy, cx = h * 0.45, w * 0.50
        rad_y, rad_x = h * 0.35, w * 0.28
        geom_prior = 1.0 - np.clip(((x_coords - cx) / rad_x)**2 + ((y_coords - cy) / rad_y)**2, 0.0, 1.0)
        geom_prior = np.sqrt(np.maximum(0.0, geom_prior))

        # Combine global macro depth and local micro fold disparity
        high_freq_folds = np.abs(gray_f - g_blur)
        combined_disparity = 0.70 * geom_prior + 0.30 * (1.0 - g_blur) + 0.15 * high_freq_folds
        combined_disparity = np.clip(combined_disparity, 0.0, 1.0)

        # Mask background to strictly 0.0
        masked_depth = np.where(silhouette_mask > 20, combined_disparity, 0.0).astype(np.float32)

        # Compute confidence map
        conf_map = np.zeros((h, w), dtype=np.float32)
        conf_map[silhouette_mask > 20] = 0.94  # Directly observed surface
        # Boundary confidence decay
        dist_transform = cv2.distanceTransform((silhouette_mask > 20).astype(np.uint8), cv2.DIST_L2, 5)
        dist_norm = np.clip(dist_transform / 15.0, 0.0, 1.0)
        conf_map = conf_map * dist_norm

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        return DepthAnythingOutput(
            relative_depth=masked_depth,
            confidence_map=conf_map,
            fold_relief_map=high_freq_folds.astype(np.float32),
            latency_ms=latency_ms,
            device=self.device,
            model_name=self.model_name,
            metric_calibrated=False
        )


depth_anything_adapter = DepthAnythingV2Adapter()
