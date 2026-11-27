"""
Multi-Model Confidence Calibration and Input Validation Engine.
Performs rigorous photographic quality verification, blur detection, exposure checks,
geometric silhouette consistency, and structured rejection with remediation advice.
"""

from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import cv2
from PIL import Image

from backend.app.models.garment_intelligence_models import (
    ImageQualityMetrics,
    SegmentationMetrics,
    GarmentComponentV2
)


class ValidationResult:
    def __init__(
        self,
        is_valid: bool,
        overall_confidence: float,
        quality_metrics: ImageQualityMetrics,
        rejection_reasons: List[str],
        remediation_guidance: List[str],
        warnings: List[str]
    ):
        self.is_valid = is_valid
        self.overall_confidence = overall_confidence
        self.quality_metrics = quality_metrics
        self.rejection_reasons = rejection_reasons
        self.remediation_guidance = remediation_guidance
        self.warnings = warnings


class ConfidenceEngine:
    """Evaluates multi-signal photographic quality and validates input viability."""

    def evaluate(
        self,
        image: Image.Image,
        alpha_mask: np.ndarray,
        category: str,
        subcategory: str,
        category_confidence: float,
        components: List[GarmentComponentV2],
        segmentation_metrics: SegmentationMetrics
    ) -> ValidationResult:
        """
        Runs comprehensive multi-signal quality and consistency evaluation.
        """
        rejection_reasons: List[str] = []
        remediation_guidance: List[str] = []
        warnings: List[str] = []

        w, h = image.size
        img_np = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

        # 1. Image Resolution Check
        if w < 120 or h < 120:
            rejection_reasons.append(f"Image resolution ({w}x{h}px) is below minimum threshold (120x120px required).")
            remediation_guidance.append("Please upload a higher-resolution photograph (recommended: 768px or above).")
        elif w < 300 or h < 300:
            warnings.append(f"Image resolution ({w}x{h}px) is lower than recommended (>=512px preferred). Fine fabric micro-details may be softened.")

        # 2. Blur / Sharpness Assessment via Laplacian Variance
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        blur_score = float(np.var(laplacian))
        is_blurry = blur_score < 40.0

        if blur_score < 15.0:
            rejection_reasons.append("Image is severely blurred or out of focus; boundary edges cannot be reliably traced.")
            remediation_guidance.append("Ensure the camera lens is steady and clothing is sharply focused.")
        elif is_blurry:
            warnings.append(f"Moderate image softness detected (blur score: {round(blur_score, 1)}). Seam reconstruction may rely more on canonical geometry.")

        # 3. Luminance, Exposure & Contrast
        mean_lum = float(np.mean(gray))
        lum_std = float(np.std(gray))

        if mean_lum < 25.0:
            exposure = "underexposed"
            rejection_reasons.append("Image is extremely dark / underexposed; fabric contours cannot be distinguished.")
            remediation_guidance.append("Please retake the photograph under balanced, well-lit ambient or daylight conditions.")
        elif mean_lum > 245.0:
            exposure = "overexposed"
            rejection_reasons.append("Image is completely blown out / overexposed; boundary highlights are clipped.")
            remediation_guidance.append("Reduce camera exposure or glare on the garment surface.")
        elif mean_lum < 55.0:
            exposure = "underexposed"
            warnings.append("Low ambient lighting detected. Tone mapping has boosted shadow clarity.")
        elif mean_lum > 215.0:
            exposure = "overexposed"
            warnings.append("High ambient brightness detected. Specular glare compensation enabled.")
        else:
            exposure = "balanced"

        # 4. Foreground Coverage & Cropping Analysis
        fg_pixels = int(np.sum(alpha_mask > 20))
        total_pixels = int(alpha_mask.shape[0] * alpha_mask.shape[1])
        coverage_ratio = fg_pixels / max(total_pixels, 1)

        if coverage_ratio < 0.03:
            rejection_reasons.append("Garment occupies less than 3% of the image; clothing could not be identified.")
            remediation_guidance.append("Center the garment in frame so it fills at least 40% of the photograph.")
        elif coverage_ratio > 0.98:
            rejection_reasons.append("Garment fills 98%+ of the image frame with no discernible background margins.")
            remediation_guidance.append("Step back slightly so the full outer silhouette and sleeves are visible.")

        # Check border touches for cropping
        top_touch = np.sum(alpha_mask[:3, :] > 20) / max(alpha_mask.shape[1], 1)
        bot_touch = np.sum(alpha_mask[-3:, :] > 20) / max(alpha_mask.shape[1], 1)
        left_touch = np.sum(alpha_mask[:, :3] > 20) / max(alpha_mask.shape[0], 1)
        right_touch = np.sum(alpha_mask[:, -3:] > 20) / max(alpha_mask.shape[0], 1)

        border_touches = sum([top_touch > 0.15, bot_touch > 0.15, left_touch > 0.15, right_touch > 0.15])
        cropping_score = border_touches / 4.0

        if cropping_score >= 0.75:
            rejection_reasons.append("Garment appears severely cropped at 3 or more boundaries.")
            remediation_guidance.append("Capture the complete garment within the frame without cutting off sleeves, collar, or hem.")
        elif cropping_score >= 0.50:
            warnings.append("Garment touches multiple image boundaries; partial sleeve or hem inference will be applied.")

        # 5. Component & Category Consistency Check
        detected_types = {c.component_type for c in components if c.status == "detected"}

        # E.g., hood on a formal shirt
        if "hood" in detected_types and subcategory in ["formal_shirt", "polo_shirt"]:
            warnings.append(f"Volumetric hood detected on {subcategory}; category re-classification to hoodie recommended.")

        # 6. Joint Calibrated Confidence Calculation
        # Combines category probability, silhouette quality, and photographic quality
        penalty = 0.0
        if is_blurry:
            penalty += 0.08
        if exposure != "balanced":
            penalty += 0.06
        if cropping_score > 0.25:
            penalty += 0.10

        overall_confidence = float(np.clip(
            (category_confidence * 0.45) + (segmentation_metrics.silhouette_quality * 0.45) + (0.10 - penalty),
            0.15,
            0.98
        ))

        is_valid = len(rejection_reasons) == 0

        quality_metrics = ImageQualityMetrics(
            width=w,
            height=h,
            laplacian_blur_score=round(blur_score, 2),
            is_blurry=is_blurry,
            contrast_score=round(lum_std, 2),
            exposure_level=exposure,
            cropping_score=round(cropping_score, 2)
        )

        return ValidationResult(
            is_valid=is_valid,
            overall_confidence=round(overall_confidence, 3),
            quality_metrics=quality_metrics,
            rejection_reasons=rejection_reasons,
            remediation_guidance=remediation_guidance,
            warnings=warnings
        )


# Global singleton confidence engine
confidence_engine = ConfidenceEngine()

