"""
YORVYN — Phase 11B: Human Parsing and Garment-Only Disentanglement Segmenter.
Employs SegFormer-B2 Clothes neural parser to semantically separate:
- Upper-clothes, Pants, Skirts, Dresses
- Head, Face, Hair, Neck, Sunglasses, Hat
- Left-arm, Right-arm, Hands
- Left-leg, Right-leg, Shoes
- Background & Accessories (Bags, Belts, Scarves)

Prevents body and background contamination on on-body and lifestyle photographs.
Provides zero fake mocks; extracts true garment RGB crop, binary mask, alpha-matted
garment, and occlusion mask.
"""

import time
import logging
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from PIL import Image, ImageOps, ImageFilter
import cv2
import torch

from .base_segmenter import IGarmentSegmenter, GarmentSegmentationOutput

logger = logging.getLogger(__name__)

# SegFormer B2 Clothes Canonical Classes (ATR / LIP Taxonomy)
PARSING_CLASSES: Dict[int, str] = {
    0: "Background",
    1: "Hat",
    2: "Hair",
    3: "Sunglasses",
    4: "Upper-clothes",
    5: "Skirt",
    6: "Pants",
    7: "Dress",
    8: "Belt",
    9: "Left-shoe",
    10: "Right-shoe",
    11: "Face",
    12: "Left-leg",
    13: "Right-leg",
    14: "Left-arm",
    15: "Right-arm",
    16: "Bag",
    17: "Scarf"
}

# Color palette for human parsing map visualization (RGB)
PARSING_PALETTE: Dict[int, Tuple[int, int, int]] = {
    0: (26, 32, 44),       # Background: Dark slate
    1: (45, 212, 191),     # Hat: Teal
    2: (168, 85, 247),     # Hair: Purple
    3: (234, 179, 8),      # Sunglasses: Yellow
    4: (59, 130, 246),     # Upper-clothes: Royal Blue
    5: (16, 185, 129),     # Skirt: Emerald
    6: (30, 64, 175),      # Pants: Deep Navy
    7: (236, 72, 153),     # Dress: Pink/Magenta
    8: (180, 83, 9),       # Belt: Amber/Brown
    9: (100, 116, 139),    # Left-shoe: Slate
    10: (71, 85, 105),     # Right-shoe: Slate dark
    11: (251, 191, 36),    # Face: Warm Gold
    12: (244, 114, 182),   # Left-leg: Rose
    13: (251, 113, 133),   # Right-leg: Rose light
    14: (249, 115, 22),    # Left-arm: Orange
    15: (234, 88, 12),     # Right-arm: Orange dark
    16: (139, 92, 246),    # Bag: Violet
    17: (20, 184, 166)     # Scarf: Cyan
}

PERSON_CLASSES = {1, 2, 3, 11, 12, 13, 14, 15}
GARMENT_CLASSES = {4, 5, 6, 7}


class HumanParsingSegmenter(IGarmentSegmenter):
    """Neural Human Parsing and Disentanglement Engine for Garment Isolation."""

    def __init__(self, model_name: str = "mattmdjaga/segformer_b2_clothes"):
        self._model_name = model_name
        self._device: Optional[torch.device] = None
        self._processor = None
        self._model = None
        self._is_loaded = False

    @property
    def model_id(self) -> str:
        return "human_parsing_segformer_b2"

    @property
    def model_version(self) -> str:
        return "segformer-b2-clothes-v1.0"

    def _ensure_loaded(self):
        """Loads model weights lazily with MPS/CUDA/CPU device mapping."""
        if self._is_loaded:
            return

        if torch.backends.mps.is_available():
            self._device = torch.device("mps")
        elif torch.cuda.is_available():
            self._device = torch.device("cuda")
        else:
            self._device = torch.device("cpu")

        logger.info(f"Loading HumanParsingSegmenter '{self._model_name}' on {self._device}...")
        from transformers import SegformerImageProcessor, AutoModelForSemanticSegmentation

        self._processor = SegformerImageProcessor.from_pretrained(self._model_name)
        self._model = AutoModelForSemanticSegmentation.from_pretrained(self._model_name).to(self._device)
        self._model.eval()
        self._is_loaded = True
        logger.info(f"HumanParsingSegmenter ready on {self._device}.")

    def parse_full_body(self, image: Image.Image) -> Tuple[np.ndarray, np.ndarray]:
        """
        Runs full semantic inference on image.
        Returns:
            Tuple of (pred_segmentation_map [H, W], max_class_probabilities [H, W])
        """
        self._ensure_loaded()
        rgb_img = image.convert("RGB")
        w, h = rgb_img.size

        inputs = self._processor(images=rgb_img, return_tensors="pt").to(self._device)
        with torch.no_grad():
            outputs = self._model(**inputs)
            probs = torch.softmax(outputs.logits[0], dim=0)
            conf_sm, pred_sm = torch.max(probs, dim=0)

        pred_sm_np = pred_sm.cpu().numpy().astype(np.uint8)
        conf_sm_np = conf_sm.cpu().numpy().astype(np.float32)

        pred_seg = cv2.resize(pred_sm_np, (w, h), interpolation=cv2.INTER_NEAREST)
        conf_seg = cv2.resize(conf_sm_np, (w, h), interpolation=cv2.INTER_LINEAR)
        return pred_seg, conf_seg

    def classify_image_type(
        self,
        image: Image.Image,
        pred_seg: np.ndarray
    ) -> Tuple[str, Dict[str, float]]:
        """
        Classifies input photograph into one of 5 canonical operational regimes:
        - isolated_product: Studio clean background, clothing only, person absent.
        - flat_lay: Top-down garment laid on flat surface, wrinkles/folds, person absent.
        - on_body: Studio / neutral backdrop, human wearing clothing.
        - lifestyle_fashion: Real-world / outdoor / contextual scene with human model.
        - ambiguous_unsupported: Garment absent, noise, or unparseable.
        """
        h, w = pred_seg.shape
        total_px = float(h * w)

        body_part_metrics: Dict[str, float] = {}
        for cls_id, cls_name in PARSING_CLASSES.items():
            px_count = int(np.sum(pred_seg == cls_id))
            body_part_metrics[cls_name] = round(px_count / total_px, 4)

        person_ratio = sum(body_part_metrics.get(PARSING_CLASSES[c], 0.0) for c in PERSON_CLASSES)
        garment_ratio = sum(body_part_metrics.get(PARSING_CLASSES[c], 0.0) for c in GARMENT_CLASSES)

        # Background texture & environmental analysis
        gray = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
        bg_mask = (pred_seg == 0)
        
        if np.sum(bg_mask) > 100:
            bg_pixels = gray[bg_mask]
            bg_std = float(np.std(bg_pixels))
            edges = cv2.Canny(gray, 50, 150)
            bg_edge_density = float(np.mean(edges[bg_mask]))
        else:
            bg_std = 0.0
            bg_edge_density = 0.0

        if garment_ratio < 0.015:
            img_type = "ambiguous_unsupported"
        elif (
            person_ratio >= 0.005
            or (body_part_metrics.get("Upper-clothes", 0.0) > 0.02 and body_part_metrics.get("Pants", 0.0) > 0.01)
            or (body_part_metrics.get("Face", 0.0) + body_part_metrics.get("Hair", 0.0) > 0.003)
            or (body_part_metrics.get("Left-arm", 0.0) + body_part_metrics.get("Right-arm", 0.0) > 0.003)
            or (body_part_metrics.get("Left-leg", 0.0) + body_part_metrics.get("Right-leg", 0.0) > 0.003)
        ):
            # Human model detected! Check scene context
            if bg_std > 18.0 or bg_edge_density > 1.8:
                img_type = "lifestyle_fashion"
            else:
                img_type = "on_body"
        else:
            # Person absent: distinguish isolated studio product vs flat lay
            border_mask = np.zeros((h, w), dtype=bool)
            border_mask[:15, :] = True
            border_mask[-15:, :] = True
            border_mask[:, :15] = True
            border_mask[:, -15:] = True
            border_std = float(np.std(gray[border_mask]))

            if border_std < 18.0 and bg_edge_density < 3.0:
                img_type = "isolated_product"
            else:
                img_type = "flat_lay"

        return img_type, body_part_metrics

    def resolve_target_garment_class(
        self,
        pred_seg: np.ndarray,
        category_hint: Optional[str] = None
    ) -> Tuple[int, str]:
        """Resolves target garment class based on optional category hint or dominant garment."""
        if category_hint:
            hint = category_hint.lower().replace("-", "_").strip()
            if any(k in hint for k in ["top", "tshirt", "tee", "shirt", "hoodie", "jacket", "coat", "sweater", "kurta", "tank"]):
                return 4, "Upper-clothes"
            if any(k in hint for k in ["pants", "trouser", "jean", "bottom", "short"]):
                return 6, "Pants"
            if "skirt" in hint:
                return 5, "Skirt"
            if "dress" in hint:
                return 7, "Dress"

        # Auto-selection from prediction frequency
        candidate_counts = {
            c: int(np.sum(pred_seg == c)) for c in [4, 7, 6, 5]
        }
        best_cls = max(candidate_counts, key=candidate_counts.get)
        return best_cls, PARSING_CLASSES[best_cls]

    def render_parsing_map(self, pred_seg: np.ndarray) -> Image.Image:
        """Renders color-coded human parsing segmentation map for visual inspection."""
        h, w = pred_seg.shape
        rgb = np.zeros((h, w, 3), dtype=np.uint8)
        for cls_id, color in PARSING_PALETTE.items():
            rgb[pred_seg == cls_id] = color
        return Image.fromarray(rgb, mode="RGB")

    def segment(
        self,
        image: Image.Image,
        category_hint: Optional[str] = None
    ) -> GarmentSegmentationOutput:
        """
        Executes semantic human parsing, isolates target garment, and cleanses non-garment regions.
        """
        t0 = time.perf_counter()
        rgb_img = image.convert("RGB")
        w, h = rgb_img.size
        warnings: List[str] = []

        # 1. Full Body Parsing Pass
        pred_seg, conf_seg = self.parse_full_body(rgb_img)

        # 2. Image Type Classification
        img_type, body_metrics = self.classify_image_type(rgb_img, pred_seg)

        # 3. Target Garment Resolution
        target_cls, target_name = self.resolve_target_garment_class(pred_seg, category_hint)

        # 4. Raw Garment Mask Isolation
        raw_garment_mask = (pred_seg == target_cls).astype(np.uint8)

        # If person is wearing dress and upper-clothes was requested, or vice versa, harmonise
        if target_cls == 4 and np.sum(raw_garment_mask) < (0.01 * w * h) and np.sum(pred_seg == 7) > (0.05 * w * h):
            target_cls = 7
            target_name = "Dress"
            raw_garment_mask = (pred_seg == 7).astype(np.uint8)
            warnings.append("Categorized as dress based on whole-body geometry.")

        total_garment_px = int(np.sum(raw_garment_mask))
        if total_garment_px < (0.005 * w * h):
            warnings.append(f"Garment coverage is low ({total_garment_px} px). Falling back to global foreground.")
            # Fallback to any clothing class
            for alt_c in [4, 7, 6, 5]:
                if np.sum(pred_seg == alt_c) > (0.01 * w * h):
                    target_cls = alt_c
                    target_name = PARSING_CLASSES[alt_c]
                    raw_garment_mask = (pred_seg == alt_c).astype(np.uint8)
                    break

        # 5. Non-Garment Cleanse (Zero Out Skin, Face, Hair, Arms, Legs, Background)
        exclusion_mask = np.zeros((h, w), dtype=bool)
        for c in PERSON_CLASSES | {0, 8, 9, 10, 16}:
            exclusion_mask |= (pred_seg == c)

        person_ratio = body_metrics.get("person_ratio", 0.0)
        has_real_person = (
            person_ratio >= 0.015 or
            (body_metrics.get("Face", 0.0) + body_metrics.get("Hair", 0.0) > 0.008) or
            (body_metrics.get("Left-arm", 0.0) + body_metrics.get("Right-arm", 0.0) > 0.008) or
            (body_metrics.get("Left-leg", 0.0) + body_metrics.get("Right-leg", 0.0) > 0.008)
        )

        if has_real_person:
            # Also exclude other non-target garments on real on-body models
            for alt_c in GARMENT_CLASSES:
                if alt_c != target_cls:
                    exclusion_mask |= (pred_seg == alt_c)
        else:
            # Isolated product / flat-lay packshot: combine all adjacent garment components into single garment
            for alt_c in GARMENT_CLASSES:
                if alt_c != target_cls and np.sum(pred_seg == alt_c) > 0:
                    raw_garment_mask |= (pred_seg == alt_c).astype(np.uint8)

        cleansed_mask = raw_garment_mask.copy()
        cleansed_mask[exclusion_mask] = 0

        # 6. Morphological Refinement (Preserve True Openings & Slits)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        refined_mask = cv2.morphologyEx(cleansed_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        # Keep only the primary connected garment component plus closely adjacent pieces (sleeves)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(refined_mask, connectivity=8)
        if num_labels > 1:
            areas = stats[1:, cv2.CC_STAT_AREA]
            max_area_idx = int(np.argmax(areas)) + 1
            max_area = areas[max_area_idx - 1]
            # Keep components that are at least 3% of the main component area (preserves detached sleeve tips)
            filtered_mask = np.zeros_like(refined_mask)
            for idx in range(1, num_labels):
                if stats[idx, cv2.CC_STAT_AREA] >= (0.03 * max_area):
                    filtered_mask[labels == idx] = 1
            refined_mask = filtered_mask

        # 7. Soft Anti-Aliased Alpha Matting
        refined_uint8 = (refined_mask * 255).astype(np.uint8)
        alpha_blurred = cv2.GaussianBlur(refined_uint8, (3, 3), 0.7)
        alpha_mask = np.where(refined_uint8 > 0, np.clip(alpha_blurred, 180, 255), 0).astype(np.uint8)

        # 8. Occlusion Detection (Arms, Hair, Bags Crossing the Garment Bounding Region)
        # Compute bounding box of garment
        y_indices, x_indices = np.where(refined_mask > 0)
        if len(y_indices) > 0:
            min_y, max_y = int(np.min(y_indices)), int(np.max(y_indices))
            min_x, max_x = int(np.min(x_indices)), int(np.max(x_indices))
            bbox = (min_x, min_y, max_x, max_y)
        else:
            min_y, max_y, min_x, max_x = 0, h - 1, 0, w - 1
            bbox = (0, 0, w - 1, h - 1)

        # Create garment hull envelope using 2-level contour hierarchy (RETR_CCOMP)
        contours, hierarchy = cv2.findContours(refined_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        occlusion_mask = np.zeros((h, w), dtype=np.uint8)
        if contours:
            outer_contours = [contours[i] for i in range(len(contours)) if hierarchy is None or hierarchy[0][i][3] == -1]
            if not outer_contours:
                outer_contours = contours
            hull = cv2.convexHull(np.vstack(outer_contours))
            hull_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(hull_mask, [hull], -1, 1, -1)
            # Occluders: Hair (2), Left-arm (14), Right-arm (15), Bag (16)
            occluders = ((pred_seg == 2) | (pred_seg == 14) | (pred_seg == 15) | (pred_seg == 16)).astype(np.uint8)
            occlusion_mask = (hull_mask & occluders)

        occlusion_px = int(np.sum(occlusion_mask))
        garment_px = int(np.sum(refined_mask))
        denom = max(garment_px + occlusion_px, 1)
        occlusion_ratio = round(float(occlusion_px / denom), 4)
        visible_surface_ratio = round(1.0 - occlusion_ratio, 4)
        inferred_surface_ratio = occlusion_ratio

        if occlusion_ratio > 0.05:
            warnings.append(f"Detected {round(occlusion_ratio * 100, 1)}% body occlusion (arms/hair) across garment surface.")

        # 9. Extract Outer Contour and Internal Opening Holes (Preserve Neckline, Armholes, Crotch)
        outer_contour: List[List[int]] = []
        holes: List[List[List[int]]] = []
        if contours:
            outer_contours = [contours[i] for i in range(len(contours)) if hierarchy is None or hierarchy[0][i][3] == -1]
            if not outer_contours:
                outer_contours = contours
            # Largest contour is the outer perimeter
            sorted_contours = sorted(outer_contours, key=cv2.contourArea, reverse=True)
            primary_c = sorted_contours[0]
            step = max(1, len(primary_c) // 180)
            outer_contour = [[int(pt[0][0]), int(pt[0][1])] for pt in primary_c[::step]]

            # Detect internal openings (e.g. neck opening or sleeve gaps)
            if hierarchy is not None and len(hierarchy[0]) > 1:
                for idx, h_info in enumerate(hierarchy[0]):
                    parent_idx = h_info[3]
                    if parent_idx != -1 and cv2.contourArea(contours[idx]) > 35:
                        hole_step = max(1, len(contours[idx]) // 50)
                        hole_pts = [[int(pt[0][0]), int(pt[0][1])] for pt in contours[idx][::hole_step]]
                        holes.append(hole_pts)

            # Neckline / Opening boundary heuristic: If top is hollowed out by neck/face suppression
            if not holes and target_name in ["Upper-clothes", "Dress"] and np.sum(pred_seg == 11) > 50:
                neck_mask = ((pred_seg == 11) | (pred_seg == 1)).astype(np.uint8)
                neck_dilated = cv2.dilate(neck_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)))
                neck_overlap = (neck_dilated & (refined_mask == 0) & hull_mask)
                if np.sum(neck_overlap) > 40:
                    n_contours, _ = cv2.findContours(neck_overlap.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    if n_contours:
                        n_c = max(n_contours, key=cv2.contourArea)
                        if cv2.contourArea(n_c) > 35:
                            step_n = max(1, len(n_c) // 50)
                            holes.append([[int(pt[0][0]), int(pt[0][1])] for pt in n_c[::step_n]])

        # 10. Composite Transparent RGBA Output (Zero Contamination)
        rgba_img = rgb_img.convert("RGBA")
        alpha_channel = Image.fromarray(alpha_mask, mode="L")
        rgba_img.putalpha(alpha_channel)

        # 11. Edge Sharpness and Compactness
        lap = cv2.Laplacian(alpha_mask, cv2.CV_64F)
        edge_sharpness = float(np.var(lap))
        if outer_contour and len(outer_contour) >= 3:
            pts_np = np.array(outer_contour)
            perimeter = float(cv2.arcLength(pts_np, True))
            area = float(cv2.contourArea(pts_np))
            compactness = float((4 * np.pi * area) / (perimeter * perimeter + 1e-6))
        else:
            compactness = 0.5

        # 12. Silhouette Quality & Confidence
        target_conf = float(np.mean(conf_seg[refined_mask > 0])) if garment_px > 0 else 0.5
        silhouette_quality = round(float(np.clip(0.4 * target_conf + 0.3 * (1.0 - min(1.0, occlusion_ratio * 2.0)) + 0.3 * min(1.0, compactness * 1.5), 0.1, 0.99)), 3)
        confidence = round(float(np.clip(target_conf, 0.1, 0.99)), 3)

        # 13. Render Visual Parsing Map
        parsing_map_img = self.render_parsing_map(pred_seg)

        dt_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        return GarmentSegmentationOutput(
            segmented_image=rgba_img,
            alpha_mask=alpha_mask,
            outer_contour=outer_contour,
            holes=holes,
            bbox=bbox,
            silhouette_quality=silhouette_quality,
            confidence=confidence,
            edge_sharpness=round(edge_sharpness, 2),
            compactness=round(compactness, 3),
            model_id=self.model_id,
            model_version=self.model_version,
            processing_time_ms=dt_ms,
            warnings=warnings,
            # Phase 11B Telemetry
            image_type=img_type,
            target_garment_class=target_name,
            occlusion_mask=occlusion_mask,
            occlusion_ratio=occlusion_ratio,
            visible_surface_ratio=visible_surface_ratio,
            inferred_surface_ratio=inferred_surface_ratio,
            detected_body_parts=body_metrics,
            human_parsing_map=parsing_map_img
        )


# Singleton instance
human_parsing_segmenter = HumanParsingSegmenter()
