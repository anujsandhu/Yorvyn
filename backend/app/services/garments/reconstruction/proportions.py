"""
YORVYN — Garment Proportions and Physical Ease Estimator
Calculates physical ease margins and metric dimensions from Phase 2 landmarks,
silhouette contours, and fit classification.
Anchors geometry to Ara 3D Gen canonical humanoid scale (1.75m) without fabricating
false precision from uncalibrated 2D pixels.
"""

from typing import Optional, Dict, Any
import numpy as np

from backend.app.models.garment_intelligence_models import GarmentIntelligenceV2Result
from .base_reconstruction_engine import GarmentProportions


class GarmentProportionsEstimator:
    """Estimates physical metric ease and proportions for 3D reconstruction."""

    FIT_MARGINS = {
        "slim": 0.018,
        "athletic_slim": 0.018,
        "regular": 0.025,
        "relaxed": 0.035,
        "oversized": 0.048,
    }

    @classmethod
    def estimate(
        cls,
        category: str,
        subcategory: str,
        fit: str = "regular",
        intelligence: Optional[GarmentIntelligenceV2Result] = None
    ) -> GarmentProportions:
        ease_margin = cls.FIT_MARGINS.get(fit.lower(), 0.025)
        
        # Base canonical priors (meters in Ara 3D Gen coordinate space)
        is_short_sleeve = (
            "short" in subcategory.lower() or
            subcategory.lower() in ["tshirt", "t_shirt", "tank_top", "crop_top"] or
            (intelligence and getattr(intelligence, "sleeve_length", None) in ["short", "sleeveless", "cap"])
        )
        sleeve_length = 0.180 if is_short_sleeve else 0.520
        shoulder_width = 0.420 + ease_margin * 1.5
        chest_width = 0.360 + ease_margin * 2.0
        waist_width = 0.320 + ease_margin * 2.0
        hem_width = 0.380 + ease_margin * 2.0
        torso_length = 0.520
        inseam_length = 0.760
        calibration_mode = "Ara3D_humanoid_canonical_1.75m_prior"
        confidence = 0.75

        # Refine with Phase 2 anatomical landmarks if available
        if intelligence and hasattr(intelligence, "landmarks") and intelligence.landmarks:
            lm = intelligence.landmarks
            calibration_mode = "Ara3D_humanoid_canonical_1.75m_landmark_guided"
            confidence = 0.88

            # Shoulder span from left and right shoulders
            if "shoulder_left" in lm and "shoulder_right" in lm:
                p_left = lm["shoulder_left"].position
                p_right = lm["shoulder_right"].position
                norm_span = abs(p_right.x - p_left.x)
                # Map normalized [0, 1] span to humanoid range [0.36m, 0.54m]
                shoulder_width = float(np.clip(0.36 + norm_span * 0.25 + ease_margin, 0.36, 0.56))

            # Torso length from collar center to hem center
            if "collar_center" in lm and "hem_center" in lm:
                y_collar = lm["collar_center"].position.y
                y_hem = lm["hem_center"].position.y
                norm_len = abs(y_hem - y_collar)
                # Map normalized length to humanoid range [0.42m, 0.85m]
                torso_length = float(np.clip(0.40 + norm_len * 0.35, 0.40, 0.85))

            # Inseam from crotch apex to ankle
            if "crotch_apex" in lm and ("ankle_left" in lm or "ankle_right" in lm):
                y_crotch = lm["crotch_apex"].position.y
                ankle_key = "ankle_left" if "ankle_left" in lm else "ankle_right"
                y_ankle = lm[ankle_key].position.y
                norm_in = abs(y_ankle - y_crotch)
                inseam_length = float(np.clip(0.50 + norm_in * 0.40, 0.45, 0.88))

            # Sleeve reach from shoulder to cuff
            if "shoulder_left" in lm and "cuff_left" in lm and not is_short_sleeve:
                p_s = lm["shoulder_left"].position
                p_c = lm["cuff_left"].position
                norm_arm = np.hypot(p_c.x - p_s.x, p_c.y - p_s.y)
                sleeve_length = float(np.clip(0.15 + norm_arm * 0.60, 0.15, 0.62))

        # Component bounding box guidance fallback when landmarks are partial
        elif intelligence and hasattr(intelligence, "components") and intelligence.components:
            for c in intelligence.components:
                if c.component_type in ("torso_body", "torso") and c.bbox:
                    b_h = abs(c.bbox.ymax - c.bbox.ymin)
                    torso_length = float(np.clip(0.42 + b_h * 0.30, 0.42, 0.82))
                    confidence = 0.82
                    break

        # Adjust dimensions for specific categories
        cat = category.lower()
        subcat = subcategory.lower()

        if cat in ["outerwear", "jacket", "jackets"]:
            ease_margin += 0.012  # Extra ease to fit over base layers
            chest_width += 0.025
            shoulder_width += 0.020
            if subcat in ["formal_coat", "trench_coat", "overcoat"]:
                torso_length = max(torso_length, 0.880)
            elif subcat == "blazer":
                torso_length = max(torso_length, 0.640)
        elif subcat == "kurta":
            torso_length = max(torso_length, 0.820)  # Knee/thigh length tunic
            hem_width = 0.440 + ease_margin * 2.0
        elif cat in ["dresses_and_skirts", "dresses", "dress"]:
            if subcat in ["skirt", "pleated_skirt", "pencil_skirt", "a_line_skirt"]:
                torso_length = 0.580
            elif subcat in ["mini_dress"]:
                torso_length = max(torso_length, 0.780)
            else:
                torso_length = max(torso_length, 0.980)
            hem_width = 0.480 + ease_margin * 2.0
        elif cat in ["bottoms", "pants", "jeans"]:
            if "shorts" in subcat:
                inseam_length = 0.280
        elif subcat == "crop_top":
            torso_length = min(torso_length, 0.360)

        return GarmentProportions(
            category=category,
            subcategory=subcategory,
            fit=fit,
            shoulder_width_m=round(shoulder_width, 4),
            chest_width_m=round(chest_width, 4),
            waist_width_m=round(waist_width, 4),
            hem_width_m=round(hem_width, 4),
            torso_length_m=round(torso_length, 4),
            sleeve_length_m=round(sleeve_length, 4),
            inseam_length_m=round(inseam_length, 4),
            ease_margin_m=round(ease_margin, 4),
            scale_calibration=calibration_mode,
            confidence=round(confidence, 2)
        )

