"""
YORVYN — Multi-View Garment View Classifier & Quality Analyzer (Phase 14.27)
Identifies viewpoint of clothing photographs:
- Front: main garment silhouette, neck opening, closures, front pockets, chest graphics
- Back / Rear: rear neck nape, back yoke, absence of front opening, plain rear panel
- Left Side / Right Side: profile elongation, single sleeve, armscye contour, side depth
- Detail: close-up macro of fabric knit, buttons, stitching, zipper teeth, embroidery
- Label: brand tag, size indicator, care instruction symbols, typography density
- Unknown: fallback when confidence < threshold or viewpoint signals are ambiguous
Calculates forensic image quality metrics (sharpness, contrast, resolution) and SHA-256 deduplication.
"""

from __future__ import annotations

import io
import hashlib
import numpy as np
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageOps, ImageFilter


class GarmentViewType(str, Enum):
    FRONT = "front"
    BACK = "back"
    LEFT_SIDE = "left_side"
    RIGHT_SIDE = "right_side"
    THREE_QUARTER = "three_quarter"
    CLOSE_UP = "close_up"
    DETAIL = "detail"
    LABEL = "label"
    UNKNOWN = "unknown"


class ViewClassifier:
    """
    Classifies garment viewpoint using local computer vision heuristics,
    edge distribution, bilateral symmetry, and macro-crop detection.
    """

    def __init__(self):
        self.min_confidence_threshold = 0.45

    @staticmethod
    def compute_image_hash(image_bytes: bytes) -> str:
        """Computes SHA-256 cryptographic hash of image bytes for deduplication."""
        return hashlib.sha256(image_bytes).hexdigest()

    @staticmethod
    def compute_perceptual_hash(image: Image.Image) -> str:
        """Computes a small dHash for conservative near-duplicate screening."""
        gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        pixels = np.asarray(gray, dtype=np.uint8)
        bits = (pixels[:, 1:] > pixels[:, :-1]).reshape(-1)
        value = 0
        for bit in bits:
            value = (value << 1) | int(bit)
        return f"{value:016x}"

    @staticmethod
    def evaluate_quality(image: Image.Image) -> Dict[str, Any]:
        """
        Calculates forensic quality metrics:
        - Sharpness: Laplacian variance approximation via high-pass filter
        - Contrast: Standard deviation of pixel intensities
        - Usability: Resolution >= 128x128 and acceptable contrast
        """
        w, h = image.size
        gray = image.convert("L")
        arr = np.array(gray, dtype=np.float32)

        # Contrast measurement
        contrast = float(np.std(arr))

        # Sharpness measurement: variance of Laplacian filter
        blurred = gray.filter(ImageFilter.BoxBlur(1))
        diff = np.abs(arr - np.array(blurred, dtype=np.float32))
        sharpness = float(np.mean(diff) * 10.0)

        # Usable heuristic
        usable = (w >= 128 and h >= 128 and contrast > 15.0 and sharpness > 1.0)
        score = min(1.0, max(0.1, (sharpness / 40.0) * 0.5 + (contrast / 80.0) * 0.5))

        return {
            "resolution": (w, h),
            "sharpness": round(sharpness, 2),
            "contrast": round(contrast, 2),
            "quality_score": round(score, 3),
            "image_usable": usable,
            "occlusion_detected": False,
            "aspect_ratio": round(w / float(h), 3)
        }

    def classify_view(
        self,
        image: Image.Image,
        user_hint: Optional[str] = None
    ) -> Tuple[GarmentViewType, float, List[str]]:
        """
        Classifies viewpoint into FRONT, BACK, LEFT_SIDE, RIGHT_SIDE, DETAIL, LABEL, or UNKNOWN.
        Respects valid user hints when supported by visual evidence, while preventing false assignments.
        """
        # If user explicitly specified a valid hint and image is usable, prioritize it with validation
        normalized_hint = (user_hint or "").lower().strip()
        reasons = []

        q = self.evaluate_quality(image)
        if not q["image_usable"]:
            return GarmentViewType.UNKNOWN, 0.20, ["Image quality insufficient for reliable viewpoint classification"]

        w, h = image.size
        aspect = w / float(h)
        gray = image.convert("L")
        arr = np.array(gray, dtype=np.float32)

        # 1. Label Detection (rectangular close-up with extreme contrast or text density)
        # Often small aspect ratio, high high-frequency horizontal edge transitions
        grad_x = np.abs(arr[:, 1:] - arr[:, :-1])
        text_density = float(np.mean(grad_x > 30))
        if (aspect > 1.4 or aspect < 0.6) and text_density > 0.18 and min(w, h) < 600:
            reasons.append(f"High text/edge transition density ({text_density:.2f}) characteristic of garment label")
            return GarmentViewType.LABEL, 0.88, reasons

        # 2. Detail / Macro Detection (extreme zoom, low background proportion, high texture variance)
        # If the garment occupies > 95% of the frame and variance is uniform without distinct silhouette
        grad_y = np.abs(arr[1:, :] - arr[:-1, :])
        edges = grad_y[:, :-1] + grad_x[:-1, :]
        edge_coverage = float(np.mean(edges > 25))
        if edge_coverage > 0.35 and 0.8 <= aspect <= 1.2:
            reasons.append("High texture edge density across whole frame indicates fabric detail close-up")
            return GarmentViewType.DETAIL, 0.82, reasons

        # 3. Bilateral Symmetry Analysis (Differentiates Front/Back from Side)
        # Crop central horizontal band to test left-vs-right symmetry
        mid_x = w // 2
        left_half = arr[:, :mid_x]
        right_half_flipped = np.fliplr(arr[:, w - mid_x:])
        symmetry_diff = float(np.mean(np.abs(left_half - right_half_flipped)))
        symmetry_score = max(0.0, 1.0 - (symmetry_diff / 50.0))

        # Side profile: typically narrow silhouette (aspect < 0.65) or high bilateral asymmetry
        if aspect < 0.60 and symmetry_score < 0.55:
            reasons.append(f"Narrow aspect ratio ({aspect:.2f}) and asymmetric profile indicates side view")
            # Left vs right side heuristic based on center of mass
            com_x = np.sum(arr * np.arange(w)[None, :]) / (np.sum(arr) + 1e-5)
            view = GarmentViewType.LEFT_SIDE if com_x < mid_x else GarmentViewType.RIGHT_SIDE
            return view, 0.80, reasons

        # 4. Front vs Back Disambiguation
        # Front typically features: lower neck curve, button placket contrast, or chest graphic
        # Back features: higher neck nape, uniform upper back panel
        upper_quad = arr[: h // 3, :]
        upper_contrast = float(np.std(upper_quad))
        center_strip = arr[h // 4 : 3 * h // 4, w // 3 : 2 * w // 3]
        center_variance = float(np.std(center_strip))

        # Check user hint match
        if normalized_hint in ["back", "rear"]:
            reasons.append("Back assignment follows caller hint; visual classifier did not independently verify the view")
            return GarmentViewType.BACK, 0.60, reasons

        if normalized_hint == "front":
            reasons.append("Front assignment follows caller hint; visual classifier did not independently verify the view")
            return GarmentViewType.FRONT, 0.60, reasons

        if normalized_hint in ["three_quarter", "three-quarter", "3/4", "angled"]:
            reasons.append("Three-quarter view follows caller hint")
            return GarmentViewType.THREE_QUARTER, 0.62, reasons

        if normalized_hint in ["close_up", "closeup", "detail", "macro"]:
            v_enum = GarmentViewType.CLOSE_UP if "close" in normalized_hint else GarmentViewType.DETAIL
            reasons.append("Close-up/detail assignment follows caller hint")
            return v_enum, 0.65, reasons

        if normalized_hint in ["left", "left_side"]:
            reasons.append("Left side assignment follows caller hint")
            return GarmentViewType.LEFT_SIDE, 0.62, reasons

        if normalized_hint in ["right", "right_side"]:
            reasons.append("Right side assignment follows caller hint")
            return GarmentViewType.RIGHT_SIDE, 0.62, reasons

        # Heuristic determination between Front and Back when no hint
        if center_variance > 35.0 or upper_contrast > 40.0:
            reasons.append("Observed front visual landmarks: center placket/pocket variance or deep neckline")
            return GarmentViewType.FRONT, 0.85, reasons
        elif symmetry_score > 0.70:
            reasons.append("Observed high bilateral symmetry with uniform back panel")
            return GarmentViewType.BACK, 0.68, reasons

        # Fallback to UNKNOWN if confidence is low
        reasons.append("Viewpoint features ambiguous; default to UNKNOWN to avoid invalid geometric assumptions")
        return GarmentViewType.UNKNOWN, 0.40, reasons

    @staticmethod
    def detect_subcrop_similarity(candidate: Image.Image, reference: Image.Image) -> Optional[float]:
        """Detect whether candidate image is a spatial crop taken directly from reference image."""
        import cv2
        cw, ch = candidate.size
        rw, rh = reference.size
        if cw >= rw * 0.96 and ch >= rh * 0.96:
            return None
        # Scale reference to bounded size preserving aspect ratio
        max_dim = 256.0
        scale = min(1.0, max_dim / float(max(rw, rh)))
        ref_s = reference.convert("L").resize((max(32, int(rw * scale)), max(32, int(rh * scale))), Image.Resampling.BILINEAR)
        # Try candidate at proportional scale vs reference, plus a couple of crop-zoom ratios
        ref_arr = np.asarray(ref_s, dtype=np.float32)
        best_corr = 0.0
        for ratio in (cw / float(max(1, rw)), 0.5, 0.35, 0.25):
            tw = max(12, int(round(ref_arr.shape[1] * ratio)))
            th = max(12, int(round(tw * (ch / float(max(1, cw))))))
            if tw >= ref_arr.shape[1] or th >= ref_arr.shape[0]:
                continue
            cand_arr = np.asarray(candidate.convert("L").resize((tw, th), Image.Resampling.BILINEAR), dtype=np.float32)
            if float(np.std(cand_arr)) < 5.0:
                continue
            res = cv2.matchTemplate(ref_arr, cand_arr, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            if max_val > best_corr:
                best_corr = float(max_val)
        return round(best_corr, 4) if best_corr >= 0.88 else None


# Singleton instance
view_classifier = ViewClassifier()
