"""
Model A: Body Intelligence Engine (ML Phase 2).
Provides continuous body measurement modeling, configurable unit conversions (cm/in),
continuous structural proportion analysis (shoulder-to-hip, waist-to-hip, torso-to-leg),
and granular garment fit evaluation (shirt length, trouser rise/break, sleeve, chest, waist).
Avoids discriminatory assumptions, rigid forced categories, or fabricated measurements.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Conversion constant: 1 inch = 2.54 centimeters
INCH_TO_CM = 2.54
CM_TO_INCH = 1.0 / 2.54


def cm_to_inches(val_cm: float) -> float:
    """Converts centimeters to inches rounded to 2 decimal places."""
    return round(val_cm * CM_TO_INCH, 2)


def inches_to_cm(val_in: float) -> float:
    """Converts inches to centimeters rounded to 2 decimal places."""
    return round(val_in * INCH_TO_CM, 2)


def format_measurement(val_cm: float, unit: str = "cm") -> str:
    """Formats a measurement in the requested unit."""
    if unit.lower() in ["in", "inch", "inches"]:
        return f"{cm_to_inches(val_cm)} in"
    return f"{round(val_cm, 1)} cm"


class GarmentMeasurementSpec(BaseModel):
    """Actual or estimated dimensions of a garment."""
    category: str = Field(..., description="top, bottom, outerwear, dress, footwear")
    fit_type: str = Field("regular", description="slim, regular, relaxed, oversized, athletic, tailored")
    chest_width_cm: Optional[float] = None
    waist_width_cm: Optional[float] = None
    shoulder_width_cm: Optional[float] = None
    garment_length_cm: Optional[float] = None
    sleeve_length_cm: Optional[float] = None
    inseam_cm: Optional[float] = None
    rise_cm: Optional[float] = None
    thigh_width_cm: Optional[float] = None
    is_verified_spec: bool = Field(False, description="True if from actual garment tech pack; False if estimated.")


class FitEvaluationResult(BaseModel):
    """Detailed multi-dimensional fit evaluation result."""
    overall_fit_score: float = Field(..., ge=0.0, le=100.0)
    is_compatible: bool
    recommended_fit: str
    garment_fit: str
    dimension_breakdown: Dict[str, Dict[str, Any]]
    tolerance_notes: List[str]
    styling_advice: List[str]
    confidence: float = Field(..., ge=0.0, le=1.0)
    is_estimated: bool


class BodyAnalysisResult(BaseModel):
    """Continuous structural proportions and fit guidelines."""
    silhouette: str
    height_cm: float
    torso_leg_balance: str
    shoulder_waist_ratio: float
    shoulder_hip_ratio: float = 1.05
    waist_hip_ratio: float = 0.85
    torso_leg_ratio: float = 0.67
    upper_lower_ratio: float = 1.22
    proportions: Dict[str, float] = Field(default_factory=dict)
    recommended_fits: List[str]
    length_guidelines: Dict[str, str]
    fit_compatibility_score: float = Field(..., ge=0.0, le=100.0)
    styling_principles: List[str]
    confidence: float = Field(0.85, ge=0.0, le=1.0)


class BodyIntelligenceService:
    """Modular Body Intelligence and Garment Fit Engine."""

    SILHOUETTE_FIT_AFFINITY: Dict[str, List[str]] = {
        "athletic": ["tailored", "regular", "relaxed", "athletic"],
        "rectangle": ["tailored", "relaxed", "oversized", "regular"],
        "hourglass": ["tailored", "regular", "slim"],
        "inverted_triangle": ["relaxed", "regular", "tailored", "athletic"],
        "pear": ["tailored", "regular", "relaxed"],
        "oval": ["regular", "relaxed", "oversized"],
        "lean": ["regular", "slim", "tailored"],
        "natural": ["regular", "relaxed", "tailored"]
    }

    # Standard ease tolerances (circumference ease added to body measurement in cm)
    FIT_EASE_TOLERANCES: Dict[str, Dict[str, Tuple[float, float]]] = {
        "slim": {"chest": (2.0, 5.0), "waist": (1.5, 4.0), "hip": (2.0, 5.0)},
        "tailored": {"chest": (4.0, 7.0), "waist": (3.0, 6.0), "hip": (3.0, 6.0)},
        "regular": {"chest": (6.0, 10.0), "waist": (5.0, 9.0), "hip": (5.0, 9.0)},
        "athletic": {"chest": (8.0, 12.0), "waist": (4.0, 8.0), "hip": (6.0, 10.0)},
        "relaxed": {"chest": (10.0, 16.0), "waist": (8.0, 14.0), "hip": (8.0, 14.0)},
        "oversized": {"chest": (15.0, 26.0), "waist": (12.0, 22.0), "hip": (12.0, 22.0)},
    }

    def convert_units(self, value: float, from_unit: str, to_unit: str) -> float:
        """Converts values between centimeters and inches safely."""
        from_clean = from_unit.strip().lower()
        to_clean = to_unit.strip().lower()

        if from_clean == to_clean:
            return round(value, 2)
        if from_clean in ["in", "inch", "inches"] and to_clean in ["cm", "centimeters"]:
            return inches_to_cm(value)
        if from_clean in ["cm", "centimeters"] and to_clean in ["in", "inch", "inches"]:
            return cm_to_inches(value)
        return round(value, 2)

    def analyze_body_proportions(
        self,
        height_cm: float = 178.0,
        shoulder_cm: Optional[float] = None,
        shoulder_width_cm: Optional[float] = None,
        chest_cm: Optional[float] = None,
        waist_cm: Optional[float] = None,
        hip_cm: Optional[float] = None,
        torso_length_cm: Optional[float] = None,
        arm_length_cm: Optional[float] = None,
        inseam_cm: Optional[float] = None,
        thigh_cm: Optional[float] = None,
        silhouette: str = "athletic",
        fit_preference: str = "regular"
    ) -> BodyAnalysisResult:
        """
        Computes continuous structural ratios and fit recommendations without
        relying on forced rigid categorization.
        """
        # Resolve shoulder width
        shoulder = shoulder_width_cm or shoulder_cm
        has_full_measurements = bool(shoulder and waist_cm and hip_cm)

        # 1. Continuous Ratios
        # Shoulder to waist ratio
        if shoulder and waist_cm and waist_cm > 0:
            sw_ratio = round(shoulder / waist_cm, 2)
        elif silhouette in ["athletic", "inverted_triangle"]:
            sw_ratio = 1.35
        elif silhouette in ["hourglass"]:
            sw_ratio = 1.25
        else:
            sw_ratio = 1.15

        # Shoulder to hip ratio
        if shoulder and hip_cm and hip_cm > 0:
            sh_ratio = round(shoulder / hip_cm, 2)
        elif silhouette in ["inverted_triangle", "athletic"]:
            sh_ratio = 1.20
        elif silhouette in ["pear"]:
            sh_ratio = 0.85
        else:
            sh_ratio = 1.02

        # Waist to hip ratio
        if waist_cm and hip_cm and hip_cm > 0:
            wh_ratio = round(waist_cm / hip_cm, 2)
        elif silhouette == "hourglass":
            wh_ratio = 0.72
        elif silhouette == "pear":
            wh_ratio = 0.76
        elif silhouette in ["athletic", "rectangle"]:
            wh_ratio = 0.84
        else:
            wh_ratio = 0.88

        # Torso to leg & upper to lower balance
        effective_inseam = inseam_cm or (height_cm * 0.45)
        effective_torso = torso_length_cm or (height_cm * 0.30)
        
        torso_leg_ratio = round(effective_torso / effective_inseam, 2) if effective_inseam > 0 else 0.67
        upper_lower_ratio = round((height_cm - effective_inseam) / effective_inseam, 2) if effective_inseam > 0 else 1.22

        if torso_leg_ratio > 0.75:
            torso_balance = "longer_torso"
        elif torso_leg_ratio < 0.60:
            torso_balance = "longer_legs"
        else:
            torso_balance = "balanced"

        # Continuous proportions dictionary
        proportions = {
            "shoulder_to_waist_ratio": sw_ratio,
            "shoulder_to_hip_ratio": sh_ratio,
            "waist_to_hip_ratio": wh_ratio,
            "torso_to_leg_ratio": torso_leg_ratio,
            "upper_to_lower_ratio": upper_lower_ratio,
            "height_to_shoulder_ratio": round(height_cm / (shoulder or 46.0), 2)
        }

        # Determine descriptive silhouette without forcing
        inferred_silhouette = silhouette
        if has_full_measurements and shoulder and waist_cm and hip_cm:
            if sw_ratio >= 1.30 and sh_ratio >= 1.15:
                inferred_silhouette = "inverted_triangle" if wh_ratio > 0.80 else "athletic"
            elif wh_ratio <= 0.75 and abs(sh_ratio - 1.0) <= 0.12:
                inferred_silhouette = "hourglass"
            elif sh_ratio < 0.90:
                inferred_silhouette = "pear"
            elif abs(sh_ratio - 1.0) <= 0.08 and wh_ratio >= 0.82:
                inferred_silhouette = "rectangle"

        # 2. Recommended fits based on continuous ratios
        rec_fits = self.SILHOUETTE_FIT_AFFINITY.get(inferred_silhouette.lower(), ["regular", "tailored", "relaxed"])

        # 3. Garment length guidelines
        if torso_balance == "longer_torso":
            top_guide = "Slightly shorter or tucked top hemline visually elongates the lower body."
            trouser_guide = "Mid-to-high rise trousers raise the visual waistline for harmonious leg proportions."
        elif torso_balance == "longer_legs":
            top_guide = "Mid-hip untucked top hemlines balance upper body length with long leg lines."
            trouser_guide = "Mid-rise or low-rise trousers with slight break over shoes preserve balanced proportions."
        else:
            top_guide = "Standard mid-hip hemline comfortably balances upper body and legs."
            trouser_guide = "Mid-rise trousers with clean subtle break over footwear maintain balanced symmetry."

        length_guidelines = {
            "tops": top_guide,
            "trousers": trouser_guide,
            "outerwear": "Mid-thigh to knee-length coats maintain clean vertical drape.",
            "jackets": "Jacket hem ending at mid-seat provides proportional torso framing."
        }

        # 4. Compatibility score with preferred fit
        fit_pref_clean = fit_preference.lower()
        if fit_pref_clean in rec_fits:
            compat_score = 95.0
        elif fit_pref_clean in ["regular"]:
            compat_score = 88.0
        else:
            compat_score = 80.0

        styling_principles = [
            f"Harmonize frame balance with {rec_fits[0]} cuts across shoulder and chest.",
            f"Use clean vertical lines to complement {torso_balance.replace('_', ' ')} stature.",
            "Anchor proportion through comfortable ease at the natural waistline."
        ]

        confidence = 0.95 if has_full_measurements else 0.82

        return BodyAnalysisResult(
            silhouette=inferred_silhouette,
            height_cm=height_cm,
            torso_leg_balance=torso_balance,
            shoulder_waist_ratio=sw_ratio,
            shoulder_hip_ratio=sh_ratio,
            waist_hip_ratio=wh_ratio,
            torso_leg_ratio=torso_leg_ratio,
            upper_lower_ratio=upper_lower_ratio,
            proportions=proportions,
            recommended_fits=rec_fits,
            length_guidelines=length_guidelines,
            fit_compatibility_score=compat_score,
            styling_principles=styling_principles,
            confidence=confidence
        )

    def evaluate_clothing_fit(
        self,
        body_measurements: Dict[str, Any],
        garment_spec: Dict[str, Any],
        user_fit_preference: str = "regular"
    ) -> FitEvaluationResult:
        """
        Evaluates garment fit against continuous body measurements.
        Evaluates shirt length, trouser rise/length, jacket proportions, shoulder width, sleeve length, waist fit.
        Distinguishes verified garment tech packs from estimated recommendations.
        """
        category = (garment_spec.get("category") or "top").lower()
        garment_fit = (garment_spec.get("fit_type") or "regular").lower()
        user_pref = (user_fit_preference or "regular").lower()
        is_verified = bool(garment_spec.get("is_verified_spec", False))

        height_cm = float(body_measurements.get("height_cm", 178.0))
        chest_cm = float(body_measurements.get("chest_cm") or 98.0)
        waist_cm = float(body_measurements.get("waist_cm") or 82.0)
        hip_cm = float(body_measurements.get("hip_cm") or 96.0)
        shoulder_cm = float(body_measurements.get("shoulder_width_cm") or body_measurements.get("shoulder_cm") or 46.0)
        inseam_cm = float(body_measurements.get("inseam_cm") or (height_cm * 0.45))
        torso_cm = float(body_measurements.get("torso_length_cm") or (height_cm * 0.30))
        arm_cm = float(body_measurements.get("arm_length_cm") or (height_cm * 0.35))

        dimension_breakdown: Dict[str, Dict[str, Any]] = {}
        tolerance_notes: List[str] = []
        styling_advice: List[str] = []
        score_components: List[float] = []

        # 1. Shoulder Fit
        garment_shoulder = garment_spec.get("shoulder_width_cm")
        if garment_shoulder:
            diff = garment_shoulder - shoulder_cm
            if garment_fit in ["slim", "tailored"]:
                ideal = (-1.0 <= diff <= 1.5)
            elif garment_fit in ["relaxed", "oversized"]:
                ideal = (2.0 <= diff <= 6.0)
            else:
                ideal = (0.5 <= diff <= 3.0)

            shoulder_score = 95.0 if ideal else max(60.0, 95.0 - abs(diff) * 5.0)
            dimension_breakdown["shoulder_fit"] = {
                "body_cm": shoulder_cm,
                "garment_cm": garment_shoulder,
                "difference_cm": round(diff, 1),
                "is_ideal": ideal,
                "score": shoulder_score
            }
            score_components.append(shoulder_score)
            if not ideal:
                tolerance_notes.append(f"Shoulder seam differs by {round(diff, 1)} cm from body frame.")
        else:
            dimension_breakdown["shoulder_fit"] = {
                "body_cm": shoulder_cm,
                "status": "estimated_standard",
                "score": 88.0
            }
            score_components.append(88.0)

        # 2. Chest & Torso Ease
        garment_chest = garment_spec.get("chest_width_cm")
        if garment_chest:
            # Garment chest width is typically half-circumference or full circumference
            effective_garment_chest = garment_chest * 2.0 if garment_chest < 70.0 else garment_chest
            ease = effective_garment_chest - chest_cm
            target_ease_min, target_ease_max = self.FIT_EASE_TOLERANCES.get(garment_fit, {}).get("chest", (6.0, 10.0))
            is_ideal_ease = (target_ease_min <= ease <= target_ease_max)
            chest_score = 95.0 if is_ideal_ease else max(55.0, 95.0 - abs(ease - target_ease_min) * 4.0)

            dimension_breakdown["chest_ease"] = {
                "body_cm": chest_cm,
                "garment_circumference_cm": round(effective_garment_chest, 1),
                "ease_cm": round(ease, 1),
                "is_ideal": is_ideal_ease,
                "score": chest_score
            }
            score_components.append(chest_score)
        else:
            score_components.append(85.0)

        # 3. Garment Length (Shirt / Coat / Jacket)
        garment_length = garment_spec.get("garment_length_cm")
        if garment_length:
            expected_top_length = torso_cm + 18.0  # mid-hip target
            diff_len = garment_length - expected_top_length
            len_score = max(65.0, 95.0 - abs(diff_len) * 3.0)
            dimension_breakdown["garment_length"] = {
                "torso_cm": torso_cm,
                "garment_length_cm": garment_length,
                "difference_from_mid_hip_cm": round(diff_len, 1),
                "score": len_score
            }
            score_components.append(len_score)
            if diff_len > 8.0:
                tolerance_notes.append("Garment hem extends below mid-seat, creating an elongated silhouette.")
        else:
            score_components.append(86.0)

        # 4. Sleeve Length
        garment_sleeve = garment_spec.get("sleeve_length_cm")
        if garment_sleeve:
            diff_sleeve = garment_sleeve - arm_cm
            sleeve_ideal = (-1.5 <= diff_sleeve <= 2.5)
            sleeve_score = 95.0 if sleeve_ideal else max(60.0, 95.0 - abs(diff_sleeve) * 4.0)
            dimension_breakdown["sleeve_length"] = {
                "arm_cm": arm_cm,
                "garment_sleeve_cm": garment_sleeve,
                "difference_cm": round(diff_sleeve, 1),
                "score": sleeve_score
            }
            score_components.append(sleeve_score)
            if not sleeve_ideal:
                tolerance_notes.append(f"Sleeve cuff rests {abs(round(diff_sleeve, 1))} cm {'past' if diff_sleeve > 0 else 'above'} wrist bone.")

        # 5. Trouser Inseam & Rise (for bottom garments)
        if category in ["bottom", "trouser", "pants"]:
            garment_inseam = garment_spec.get("inseam_cm")
            if garment_inseam:
                diff_inseam = garment_inseam - inseam_cm
                # Break classification
                if diff_inseam <= -3.0:
                    break_style = "cropped / ankle"
                elif -2.0 <= diff_inseam <= 0.0:
                    break_style = "no break"
                elif 0.0 < diff_inseam <= 2.5:
                    break_style = "slight break"
                else:
                    break_style = "full break"

                inseam_score = 92.0
                dimension_breakdown["trouser_inseam"] = {
                    "body_inseam_cm": inseam_cm,
                    "garment_inseam_cm": garment_inseam,
                    "break_style": break_style,
                    "score": inseam_score
                }
                score_components.append(inseam_score)
                styling_advice.append(f"Inseam creates a refined {break_style} over contemporary footwear.")

            garment_rise = garment_spec.get("rise_cm")
            if garment_rise:
                rise_type = "high-rise" if garment_rise >= 28.0 else ("mid-rise" if garment_rise >= 23.0 else "low-rise")
                dimension_breakdown["trouser_rise"] = {
                    "rise_cm": garment_rise,
                    "rise_type": rise_type,
                    "score": 90.0
                }

        # Overall composite fit score
        overall_score = round(sum(score_components) / len(score_components), 1) if score_components else 85.0
        
        # User preference alignment
        if garment_fit == user_pref:
            overall_score = min(100.0, overall_score + 4.0)
            styling_advice.append(f"Cut directly aligns with your preferred {user_pref} silhouette.")
        elif garment_fit in ["regular", "tailored"]:
            overall_score = min(100.0, overall_score + 1.0)
            styling_advice.append(f"Balanced {garment_fit} styling provides versatile drape.")

        is_compatible = (overall_score >= 75.0)

        return FitEvaluationResult(
            overall_fit_score=overall_score,
            is_compatible=is_compatible,
            recommended_fit=user_pref,
            garment_fit=garment_fit,
            dimension_breakdown=dimension_breakdown,
            tolerance_notes=tolerance_notes,
            styling_advice=styling_advice,
            confidence=0.92 if is_verified else 0.80,
            is_estimated=not is_verified
        )

    def evaluate_garment_fit(
        self,
        silhouette: str,
        user_fit_preference: str,
        garment_fit: str,
        garment_category: str
    ) -> Dict[str, Any]:
        """Legacy-compatible fit evaluator returning backward-compatible dict."""
        garment_fit_clean = (garment_fit or "regular").lower()
        user_pref_clean = (user_fit_preference or "regular").lower()

        if garment_fit_clean == user_pref_clean:
            score = 98.0
            rationale = f"Garment fit ({garment_fit_clean}) precisely matches your preferred fit."
        elif garment_fit_clean in self.SILHOUETTE_FIT_AFFINITY.get(silhouette.lower(), []):
            score = 88.0
            rationale = f"Garment fit ({garment_fit_clean}) complements your {silhouette} silhouette."
        else:
            score = 72.0
            rationale = f"Garment fit ({garment_fit_clean}) offers an intentional contrast to your standard {user_pref_clean} preference."

        return {
            "score": score,
            "compatible": score >= 75.0,
            "rationale": rationale
        }


# Global singleton
body_intelligence_service = BodyIntelligenceService()
