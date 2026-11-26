"""
OpenCV Advanced Contour, Hole Preservation & Adaptive GrabCut Segmenter.
Provides high-fidelity garment boundary isolation, internal hole preservation
(neck opening, sleeve gaps, open jacket fronts), and morphological refinement.
"""

import time
import math
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import cv2
from PIL import Image

from .base_segmenter import IGarmentSegmenter, GarmentSegmentationOutput


class OpenCVContourSegmenter(IGarmentSegmenter):
    """
    Production-grade computer vision segmenter based on adaptive GrabCut,
    morphological boundary analysis, and dual-level contour hierarchy extraction.
    """

    def __init__(self, iterations: int = 4):
        self._iterations = iterations
        self._model_id = "opencv-adaptive-grabcut"
        self._model_version = "cv-5.0.0-hierarchical-v2"

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def model_version(self) -> str:
        return self._model_version

    def segment(self, image: Image.Image) -> GarmentSegmentationOutput:
        start_time = time.perf_counter()
        warnings: List[str] = []

        # 1. Image preparation
        rgb_img = image.convert("RGB")
        orig_w, orig_h = rgb_img.size

        # Working scale: max dimension 768px for balanced performance and sub-pixel edge detail
        max_dim = 768
        scale = min(max_dim / max(orig_w, 1), max_dim / max(orig_h, 1), 1.0)
        work_w = max(120, int(orig_w * scale))
        work_h = max(120, int(orig_h * scale))

        if scale < 1.0:
            work_img = rgb_img.resize((work_w, work_h), Image.Resampling.LANCZOS)
        else:
            work_img = rgb_img

        cv_img = cv2.cvtColor(np.array(work_img), cv2.COLOR_RGB2BGR)

        # 2. Border Sampling & Color Contrast Estimation
        # Sample image perimeter to determine background distribution
        border_thickness = max(4, int(min(work_w, work_h) * 0.035))
        top_border = cv_img[:border_thickness, :]
        bot_border = cv_img[-border_thickness:, :]
        left_border = cv_img[:, :border_thickness]
        right_border = cv_img[:, -border_thickness:]

        border_pixels = np.concatenate([
            top_border.reshape(-1, 3),
            bot_border.reshape(-1, 3),
            left_border.reshape(-1, 3),
            right_border.reshape(-1, 3)
        ], axis=0)

        bg_mean = np.median(border_pixels, axis=0)
        bg_std = np.std(border_pixels, axis=0)
        is_uniform_bg = np.mean(bg_std) < 28.0

        # 3. Adaptive Foreground Initialization & GrabCut
        mask = np.zeros((work_h, work_w), dtype=np.uint8)
        mask[:] = cv2.GC_BGD

        # Define initial bounding rect
        margin_x = max(2, int(work_w * 0.02))
        margin_y = max(2, int(work_h * 0.02))
        rect = (margin_x, margin_y, work_w - 2 * margin_x, work_h - 2 * margin_y)

        # Preliminary color distance mask
        diff = np.linalg.norm(cv_img.astype(np.float32) - bg_mean, axis=2)
        diff_threshold = max(25.0, np.percentile(diff, 18))

        # Likely foreground and probable background
        fg_candidate = diff > diff_threshold
        mask[rect[1]:rect[1]+rect[3], rect[0]:rect[0]+rect[2]] = cv2.GC_PR_FGD
        mask[~fg_candidate] = cv2.GC_BGD

        # Ensure borders are marked definite background
        mask[:border_thickness, :] = cv2.GC_BGD
        mask[-border_thickness:, :] = cv2.GC_BGD
        mask[:, :border_thickness] = cv2.GC_BGD
        mask[:, -border_thickness:] = cv2.GC_BGD

        # Run GrabCut optimization
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)

        try:
            cv2.grabCut(cv_img, mask, rect, bgd_model, fgd_model, self._iterations, cv2.GC_INIT_WITH_MASK)
            # Binary mask: pixels marked GC_FGD or GC_PR_FGD
            bin_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
        except Exception as e:
            warnings.append(f"GrabCut convergence exception: {str(e)}; falling back to adaptive color thresholding.")
            bin_mask = (diff > diff_threshold).astype(np.uint8) * 255

        # 4. Morphological Cleanup with Hole & Sleeve-Gap Preservation
        # Small elliptical kernel to smooth micro-roughness without obliterating straps or seams
        kernel_smooth = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        bin_mask = cv2.morphologyEx(bin_mask, cv2.MORPH_OPEN, kernel_smooth)
        bin_mask = cv2.morphologyEx(bin_mask, cv2.MORPH_CLOSE, kernel_smooth)

        # 5. Two-level Contour Hierarchy Extraction (RETR_CCOMP)
        # RETR_CCOMP retrieves all contours and organizes them into a two-level hierarchy:
        # Level 1: external boundaries of clothing panels
        # Level 2: boundaries of internal holes (neckline cutout, sleeve-to-torso gap, unbuttoned front gap)
        contours, hierarchy = cv2.findContours(bin_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

        outer_contours: List[np.ndarray] = []
        inner_holes: List[np.ndarray] = []

        if hierarchy is not None and len(contours) > 0:
            h_data = hierarchy[0]  # [Next, Previous, First_Child, Parent]
            
            # Find the largest outer contour (primary garment body)
            outer_indices = [idx for idx, h in enumerate(h_data) if h[3] == -1]
            if outer_indices:
                primary_idx = max(outer_indices, key=lambda idx: cv2.contourArea(contours[idx]))
                outer_contours.append(contours[primary_idx])

                # Retain significant internal holes belonging to the primary garment
                for idx, h in enumerate(h_data):
                    if h[3] == primary_idx:
                        hole_area = cv2.contourArea(contours[idx])
                        # Keep macroscopic holes (e.g. neck hole, sleeve gap) > 0.3% of garment area
                        primary_area = cv2.contourArea(contours[primary_idx])
                        if hole_area >= max(50.0, primary_area * 0.003):
                            inner_holes.append(contours[idx])

        # Construct clean refined mask from outer contour and holes
        refined_mask = np.zeros_like(bin_mask)
        if outer_contours:
            cv2.drawContours(refined_mask, outer_contours, -1, 255, thickness=cv2.FILLED)
            if inner_holes:
                # Carve out internal holes
                cv2.drawContours(refined_mask, inner_holes, -1, 0, thickness=cv2.FILLED)
        else:
            refined_mask = bin_mask

        # 6. Smooth boundary anti-aliasing
        refined_mask_float = cv2.GaussianBlur(refined_mask.astype(np.float32), (3, 3), 0.8)
        alpha_mask = np.clip(refined_mask_float, 0, 255).astype(np.uint8)

        # 7. Convert Contours and Holes to Normalized Polygon Coordinate Lists
        outer_poly_pts: List[List[int]] = []
        if outer_contours:
            # Polygon approximation to reduce vertex redundancy while preserving curvature
            epsilon = 0.0018 * cv2.arcLength(outer_contours[0], True)
            approx_outer = cv2.approxPolyDP(outer_contours[0], epsilon, True)
            outer_poly_pts = approx_outer.reshape(-1, 2).tolist()

        holes_poly_pts: List[List[List[int]]] = []
        for hole in inner_holes:
            eps_hole = 0.002 * cv2.arcLength(hole, True)
            approx_h = cv2.approxPolyDP(hole, eps_hole, True)
            holes_poly_pts.append(approx_h.reshape(-1, 2).tolist())

        # 8. Compute Bounding Box
        y_indices, x_indices = np.where(alpha_mask > 20)
        if len(y_indices) > 0:
            min_y, max_y = int(np.min(y_indices)), int(np.max(y_indices))
            min_x, max_x = int(np.min(x_indices)), int(np.max(x_indices))
            bbox = (min_x, min_y, max_x, max_y)
        else:
            bbox = (0, 0, work_w, work_h)
            warnings.append("Segmented mask is empty; foreground could not be reliably isolated.")

        # 9. Silhouette Quality & Boundary Sharpness Metrics
        garment_area = float(np.sum(alpha_mask > 30))
        total_area = float(work_w * work_h)
        coverage_ratio = garment_area / max(total_area, 1.0)

        if coverage_ratio < 0.04:
            warnings.append("Garment covers less than 4% of image area; framing is too distant.")
        elif coverage_ratio > 0.94:
            warnings.append("Garment occupies >94% of image area; boundary edges may be cropped.")

        # Edge sharpness along boundary
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        # Boundary band
        kernel_band = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(bin_mask, kernel_band)
        eroded = cv2.erode(bin_mask, kernel_band)
        boundary_band = (dilated > 0) & (eroded == 0)

        if np.any(boundary_band):
            boundary_sharpness = float(np.var(laplacian[boundary_band]))
        else:
            boundary_sharpness = float(np.var(laplacian))

        # Compactness metric: 4 * pi * Area / Perimeter^2
        if outer_contours:
            perimeter = float(cv2.arcLength(outer_contours[0], True))
            primary_area = float(cv2.contourArea(outer_contours[0]))
            compactness = float((4.0 * math.pi * primary_area) / max(perimeter * perimeter, 1.0))
        else:
            compactness = 0.5

        # Calibrated silhouette quality score [0.0, 1.0]
        quality_score = 0.88
        if not is_uniform_bg:
            quality_score -= 0.06
        if coverage_ratio < 0.08 or coverage_ratio > 0.90:
            quality_score -= 0.12
        if len(inner_holes) > 0:
            # Preserving genuine openings is a positive indicator of fidelity
            quality_score += 0.04
        quality_score = float(np.clip(quality_score, 0.20, 0.98))

        # 10. Generate Transparent RGBA Composite
        work_rgba = work_img.convert("RGBA")
        alpha_pil = Image.fromarray(alpha_mask, mode="L")
        work_rgba.putalpha(alpha_pil)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return GarmentSegmentationOutput(
            segmented_image=work_rgba,
            alpha_mask=alpha_mask,
            outer_contour=outer_poly_pts,
            holes=holes_poly_pts,
            bbox=bbox,
            silhouette_quality=quality_score,
            confidence=quality_score,
            edge_sharpness=boundary_sharpness,
            compactness=compactness,
            model_id=self._model_id,
            model_version=self._model_version,
            processing_time_ms=elapsed_ms,
            warnings=warnings
        )

