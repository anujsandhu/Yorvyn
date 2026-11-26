"""
YORVYN — Garment Size and Ease Intelligence Engine (Phase 5)
Calculates physical garment ease, categorizes fit styles (slim, regular, relaxed, oversized, compression),
and computes segment-specific, non-uniform anatomical scaling factors.
Strictly preserves structural proportions without applying arbitrary uniform whole-mesh scaling.
"""

from typing import Dict, Any, Optional, Tuple, List
import math
import numpy as np

from backend.app.models.garment_intelligence_models import (
    AvatarMeasurementsV2,
    GarmentEaseAnalysisV2
)


class GarmentEaseEngine:
    """
    Evaluates garment ease relative to avatar measurements and computes
    anatomically tailored scaling curves for proportional fitting.
    """

    # Category base circumferences for standard Ara 3D 1.75m humanoid (in cm)
    CANONICAL_GARMENT_DIMENSIONS = {
        "tops": {
            "chest_cm": 102.0,       # +6cm ease over 96cm chest (regular fit)
            "waist_cm": 84.0,        # +6cm ease over 78cm waist
            "shoulder_width_cm": 45.0, # +1.5cm ease
            "length_cm": 68.0
        },
        "formal_shirt": {
            "chest_cm": 100.0,       # +4cm ease (tailored/regular)
            "waist_cm": 82.0,        # +4cm ease
            "shoulder_width_cm": 44.5,
            "length_cm": 72.0
        },
        "hoodie": {
            "chest_cm": 110.0,       # +14cm ease (relaxed/oversized)
            "waist_cm": 90.0,
            "shoulder_width_cm": 48.0,
            "length_cm": 70.0
        },
        "jacket": {
            "chest_cm": 108.0,       # +12cm ease (outerwear layer)
            "waist_cm": 90.0,
            "shoulder_width_cm": 47.0,
            "length_cm": 68.0
        },
        "bottoms": {
            "waist_cm": 82.0,        # +4cm ease over 78cm waist
            "hip_cm": 104.0,         # +6cm ease over 98cm hips
            "thigh_cm": 58.0,        # +4cm ease over 54cm thigh
            "inseam_cm": 78.0
        },
        "jeans": {
            "waist_cm": 80.0,        # +2cm ease (fitted denim waistband)
            "hip_cm": 102.0,         # +4cm ease
            "thigh_cm": 57.0,
            "inseam_cm": 78.0
        },
        "trousers": {
            "waist_cm": 81.0,
            "hip_cm": 103.0,
            "thigh_cm": 58.0,
            "inseam_cm": 78.5
        },
        "dress": {
            "chest_cm": 98.0,        # +2cm ease (fitted bodice)
            "waist_cm": 80.0,        # +2cm ease
            "hip_cm": 108.0,         # +10cm ease (skirt drape flare)
            "length_cm": 96.0
        },
        "skirt": {
            "waist_cm": 80.0,        # +2cm ease
            "hip_cm": 112.0,         # +14cm ease (flared drape)
            "length_cm": 50.0
        },
        "traditional": {
            "chest_cm": 104.0,       # +8cm ease (straight tunic kurta)
            "waist_cm": 92.0,        # +14cm ease (straight cut)
            "hip_cm": 108.0,         # side slits provide infinite movement ease
            "shoulder_width_cm": 45.0,
            "length_cm": 98.0
        },
        "footwear": {
            "foot_length_cm": 27.3,  # +0.8cm toe clearance over 26.5cm foot
            "foot_width_cm": 10.4
        }
    }

    # Standard ease thresholds for fit classification (in cm)
    EASE_THRESHOLDS = {
        "compression": (-10.0, 0.0),
        "slim": (0.0, 4.0),
        "regular": (4.0, 9.0),
        "relaxed": (9.0, 15.0),
        "oversized": (15.0, 50.0)
    }

    @classmethod
    def calculate_ease(
        cls,
        category: str,
        subcategory: str,
        avatar_measurements: AvatarMeasurementsV2,
        target_fit: Optional[str] = None,
        custom_garment_dimensions: Optional[Dict[str, float]] = None
    ) -> GarmentEaseAnalysisV2:
        """
        Calculates ease across chest, waist, hips, shoulders, and inseam.
        Determines whether garment has positive or negative ease and assigns fit classification.
        """
        cat_key = subcategory if subcategory in cls.CANONICAL_GARMENT_DIMENSIONS else category
        dims = custom_garment_dimensions or cls.CANONICAL_GARMENT_DIMENSIONS.get(cat_key, cls.CANONICAL_GARMENT_DIMENSIONS["tops"])

        # Target ease offsets if user requested a specific fit style
        fit_offsets = {
            "compression": -3.0,
            "slim": -2.0,
            "regular": 0.0,
            "relaxed": +5.0,
            "oversized": +10.0
        }
        offset = fit_offsets.get(target_fit.lower(), 0.0) if target_fit else 0.0

        # Primary ease calculations (Garment Dimension - Body Measurement)
        chest_g = dims.get("chest_cm", avatar_measurements.chest_circumference_cm + 6.0) + offset
        waist_g = dims.get("waist_cm", avatar_measurements.waist_circumference_cm + 6.0) + offset
        hip_g = dims.get("hip_cm", avatar_measurements.hip_circumference_cm + 6.0) + offset
        sh_g = dims.get("shoulder_width_cm", avatar_measurements.shoulder_width_cm + 2.0) + (offset * 0.25)
        ins_g = dims.get("inseam_cm", avatar_measurements.inseam_cm)

        chest_ease = round(chest_g - avatar_measurements.chest_circumference_cm, 1)
        waist_ease = round(waist_g - avatar_measurements.waist_circumference_cm, 1)
        hip_ease = round(hip_g - avatar_measurements.hip_circumference_cm, 1)
        shoulder_ease = round(sh_g - avatar_measurements.shoulder_width_cm, 1)
        inseam_ease = round(ins_g - avatar_measurements.inseam_cm, 1)

        # Fit classification based on primary ease
        ref_ease = chest_ease if "bottom" not in category else hip_ease
        classification = "regular"
        for fit_name, (min_e, max_e) in cls.EASE_THRESHOLDS.items():
            if min_e <= ref_ease < max_e:
                classification = fit_name
                break
        if ref_ease >= 15.0:
            classification = "oversized"
        elif ref_ease < 0.0:
            classification = "compression"

        is_neg = (ref_ease < 0.0)

        # Segment-specific scaling multipliers relative to canonical Ara 3D 1.75m body
        # Standard Ara 3D measurements: height=175cm, chest=96cm, waist=78cm, hip=98cm
        canonical = cls.CANONICAL_GARMENT_DIMENSIONS["tops"]
        scale_x_chest = float(np.clip((avatar_measurements.chest_circumference_cm + chest_ease) / 102.0, 0.70, 1.45))
        scale_x_waist = float(np.clip((avatar_measurements.waist_circumference_cm + waist_ease) / 84.0, 0.70, 1.45))
        scale_x_hip = float(np.clip((avatar_measurements.hip_circumference_cm + hip_ease) / 104.0, 0.70, 1.45))
        scale_x_shoulder = float(np.clip((avatar_measurements.shoulder_width_cm + shoulder_ease) / 45.0, 0.75, 1.40))
        scale_y_height = float(np.clip(avatar_measurements.height_cm / 175.0, 0.75, 1.35))

        segment_scales = {
            "shoulder": round(scale_x_shoulder, 3),
            "chest": round(scale_x_chest, 3),
            "waist": round(scale_x_waist, 3),
            "hip": round(scale_x_hip, 3),
            "height": round(scale_y_height, 3)
        }

        return GarmentEaseAnalysisV2(
            fit_classification=classification,
            chest_ease_cm=chest_ease,
            waist_ease_cm=waist_ease,
            hip_ease_cm=hip_ease,
            shoulder_ease_cm=shoulder_ease,
            inseam_ease_cm=inseam_ease,
            is_negative_ease=is_neg,
            segment_scale_factors=segment_scales
        )


garment_ease_engine = GarmentEaseEngine()

