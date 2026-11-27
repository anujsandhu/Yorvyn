"""
Yorvyn Fashion DNA Service (ML Phase 2).
Handles persistence, evolution, avatar profile synchronization, provenance tracking,
and privacy-compliant lifecycle management for user Fashion Intelligence profiles.
Strictly distinguishes user-confirmed data from avatar-derived and CV estimates.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.app.models.fashion_dna import (
    AdditionalPreferences,
    BodyProfile,
    ColourProfile,
    FashionDNA,
    PreferenceConfidence,
    PreferenceSignal,
    StyleProfile,
)
from backend.app.services.database.supabase_repository import supabase_repo
from backend.app.services.ml.body_intelligence import (
    body_intelligence_service,
    cm_to_inches,
    inches_to_cm,
)
from backend.app.services.ml.skin_colour_intelligence import (
    skin_colour_intelligence_service,
)

logger = logging.getLogger(__name__)


class FashionDNAService:
    """Manages persistent Fashion DNA for users."""

    def __init__(self):
        self.repo = supabase_repo
        self.body_intel = body_intelligence_service
        self.colour_intel = skin_colour_intelligence_service

    def get_fashion_dna(self, user_id: str) -> FashionDNA:
        """Retrieves user Fashion DNA, creating a baseline profile if none exists."""
        raw = self.repo.get_fashion_dna(user_id)
        if raw:
            try:
                return FashionDNA(**raw)
            except Exception as e:
                logger.warning(f"Error parsing Fashion DNA for user {user_id}: {e}. Initializing default.")

        # Create curated baseline
        dna = FashionDNA(user_id=str(user_id))
        self.repo.upsert_fashion_dna(user_id, dna.model_dump())
        return dna

    def update_fashion_dna(self, user_id: str, updates: Dict[str, Any]) -> FashionDNA:
        """Updates specific components of the user Fashion DNA."""
        current = self.get_fashion_dna(user_id)
        current_dict = current.model_dump()

        for key, value in updates.items():
            if key in current_dict and isinstance(value, dict) and isinstance(current_dict[key], dict):
                current_dict[key].update(value)
            elif key in current_dict:
                current_dict[key] = value

        current_dict["updated_at"] = datetime.utcnow().isoformat()
        validated = FashionDNA(**current_dict)
        self.repo.upsert_fashion_dna(user_id, validated.model_dump())
        return validated

    def update_body_measurements(
        self,
        user_id: str,
        measurements: Dict[str, Any],
        unit: str = "cm",
        source: str = "user_confirmed"
    ) -> FashionDNA:
        """
        Updates continuous physical body measurements with provenance and confidence tracking.
        Converts from inches to centimeters if unit == 'in'.
        Recalculates continuous proportion ratios automatically.
        Never overwrites user-confirmed measurements with uncertain estimates.
        """
        dna = self.get_fashion_dna(user_id)
        bp = dna.body_profile
        now_iso = datetime.utcnow().isoformat()

        # Update preferred unit if specified
        if unit.lower() in ["in", "inch", "inches"]:
            bp.unit_preference = "in"
            is_inches = True
        else:
            bp.unit_preference = "cm"
            is_inches = False

        # Measurement keys recognized
        keys_mapping = {
            "height": "height_cm",
            "height_cm": "height_cm",
            "weight": "weight_kg",
            "weight_kg": "weight_kg",
            "shoulder": "shoulder_cm",
            "shoulder_cm": "shoulder_cm",
            "shoulder_width": "shoulder_width_cm",
            "shoulder_width_cm": "shoulder_width_cm",
            "chest": "chest_cm",
            "chest_cm": "chest_cm",
            "waist": "waist_cm",
            "waist_cm": "waist_cm",
            "hip": "hip_cm",
            "hip_cm": "hip_cm",
            "torso_length": "torso_length_cm",
            "torso_length_cm": "torso_length_cm",
            "arm_length": "arm_length_cm",
            "arm_length_cm": "arm_length_cm",
            "inseam": "inseam_cm",
            "inseam_cm": "inseam_cm",
            "thigh": "thigh_cm",
            "thigh_cm": "thigh_cm",
            "neck": "neck_cm",
            "neck_cm": "neck_cm",
        }

        confidence_map = {
            "user_confirmed": 1.0,
            "manual": 0.95,
            "avatar_derived": 0.75,
            "cv_estimated": 0.65,
            "inferred": 0.50
        }
        conf_val = confidence_map.get(source, 0.80)

        for input_key, val in measurements.items():
            if val is None or input_key not in keys_mapping:
                continue
            target_field = keys_mapping[input_key]

            # Protect confirmed data: do not overwrite user_confirmed with cv_estimated or inferred
            existing_source = bp.measurement_sources.get(target_field, bp.measurement_source)
            if existing_source == "user_confirmed" and source not in ["user_confirmed", "manual"]:
                logger.info(f"Skipping overwrite of user_confirmed {target_field} by {source}")
                continue

            try:
                numeric_val = float(val)
                # Convert if value provided in inches and target is cm
                if is_inches and target_field.endswith("_cm"):
                    numeric_val = inches_to_cm(numeric_val)
                elif is_inches and target_field == "weight_kg":
                    numeric_val = round(numeric_val * 0.45359237, 2)  # lbs to kg

                setattr(bp, target_field, numeric_val)
                # If updating shoulder, keep both shoulder_cm and shoulder_width_cm in sync
                if "shoulder" in target_field:
                    bp.shoulder_cm = numeric_val
                    bp.shoulder_width_cm = numeric_val

                bp.measurement_sources[target_field] = source
                bp.measurement_confidences[target_field] = conf_val
                bp.measurement_updated_at[target_field] = now_iso
            except (ValueError, TypeError) as err:
                logger.warning(f"Invalid measurement value {val} for {target_field}: {err}")

        # Overall source state
        if source == "user_confirmed":
            bp.measurement_source = "user_confirmed"

        # Recalculate continuous proportions
        analysis = self.body_intel.analyze_body_proportions(
            height_cm=bp.height_cm,
            shoulder_width_cm=bp.shoulder_width_cm or bp.shoulder_cm,
            chest_cm=bp.chest_cm,
            waist_cm=bp.waist_cm,
            hip_cm=bp.hip_cm,
            torso_length_cm=bp.torso_length_cm,
            arm_length_cm=bp.arm_length_cm,
            inseam_cm=bp.inseam_cm,
            thigh_cm=bp.thigh_cm,
            silhouette=bp.silhouette,
            fit_preference=bp.fit_preference
        )

        bp.proportions = analysis.proportions
        bp.torso_proportion = "long" if analysis.torso_leg_balance == "longer_torso" else ("short" if analysis.torso_leg_balance == "longer_legs" else "balanced")
        bp.silhouette = analysis.silhouette

        dna.confidence_scores.body_fit_confidence = min(1.0, dna.confidence_scores.body_fit_confidence + 0.05)
        dna.updated_at = now_iso

        self.repo.upsert_fashion_dna(user_id, dna.model_dump())
        return dna

    def update_colour_profile_colorimetric(
        self,
        user_id: str,
        skin_r: Optional[int] = None,
        skin_g: Optional[int] = None,
        skin_b: Optional[int] = None,
        user_undertone: Optional[str] = None,
        preferred_palette: Optional[str] = None,
        contrast_preference: Optional[str] = None,
        source: str = "user_confirmed"
    ) -> FashionDNA:
        """
        Updates color profile using lighting-aware colorimetric CIELAB analysis.
        """
        dna = self.get_fashion_dna(user_id)
        cp = dna.colour_profile
        now_iso = datetime.utcnow().isoformat()

        if skin_r is not None and skin_g is not None and skin_b is not None:
            analysis = self.colour_intel.analyze_skin_tone_lighting_aware(skin_r, skin_g, skin_b)
            cp.skin_tone_range = analysis.skin_tone_range
            cp.cielab_l = analysis.cielab["L"]
            cp.cielab_a = analysis.cielab["a"]
            cp.cielab_b = analysis.cielab["b"]
            cp.lighting_compensation_applied = analysis.lighting_compensation_applied
            cp.lighting_condition = analysis.lighting_condition
            cp.skin_hex = f"#{skin_r:02x}{skin_g:02x}{skin_b:02x}"
            if not user_undertone:
                cp.skin_undertone = analysis.skin_undertone
                cp.confidence = analysis.confidence

        if user_undertone in ["warm", "cool", "neutral", "uncertain"]:
            cp.skin_undertone = user_undertone
            cp.confidence = 0.95 if source == "user_confirmed" else cp.confidence

        # Re-derive personal palette
        palette_details = self.colour_intel.get_personal_colour_palette(
            undertone=cp.skin_undertone,
            skin_tone_range=cp.skin_tone_range,
            user_preferred_palette=preferred_palette or cp.personal_palette
        )

        cp.personal_palette = palette_details.palette_id
        cp.seasonal_palette_name = palette_details.palette_name
        cp.complementary_colours = palette_details.complementary_colours
        cp.analogous_colours = palette_details.analogous_colours
        cp.neutral_anchors = palette_details.neutral_anchors
        cp.accent_colours = palette_details.accent_colours
        if contrast_preference:
            cp.contrast_preference = contrast_preference
        cp.source = source

        dna.confidence_scores.colour_harmony_confidence = min(1.0, dna.confidence_scores.colour_harmony_confidence + 0.05)
        dna.updated_at = now_iso

        self.repo.upsert_fashion_dna(user_id, dna.model_dump())
        return dna

    def compare_with_avatar_dna(
        self,
        user_id: str,
        avatar_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compares 3D avatar proportions with user Fashion DNA continuous measurements.
        Detects structural mismatches without modifying facial features, hair, or skin styling.
        Clearly labels avatar parameters as visual approximations.
        """
        dna = self.get_fashion_dna(user_id)
        bp = dna.body_profile
        raw_props = avatar_profile.get("proportions")
        props = raw_props if isinstance(raw_props, dict) else {}

        mismatches: List[Dict[str, Any]] = []
        validated_parameter_updates: Dict[str, Any] = {}

        # 1. Stature / Height Check
        avatar_height_raw = (
            props.get("heightCm")
            or avatar_profile.get("heightCm")
            or avatar_profile.get("height_cm")
            or avatar_profile.get("height")
        )
        if isinstance(avatar_height_raw, (int, float)):
            if avatar_height_raw <= 2.5:
                avatar_height = 160.0 + avatar_height_raw * 30.0  # Normalized 0..1 to cm scale
            else:
                avatar_height = float(avatar_height_raw)
        else:
            avatar_height = 180.0

        height_diff = bp.height_cm - float(avatar_height)
        if abs(height_diff) >= 3.0:
            mismatches.append({
                "attribute": "height",
                "fashion_dna_value": f"{bp.height_cm} cm",
                "avatar_value": f"{round(avatar_height, 1)} cm",
                "difference": f"{round(height_diff, 1)} cm",
                "severity": "medium",
                "recommendation": f"Calibrate avatar heightCm from {round(avatar_height, 1)} to {bp.height_cm}."
            })
            validated_parameter_updates["heightCm"] = bp.height_cm

        # 2. Shoulder to Waist Proportion Check
        avatar_shoulder_mod = float(props.get("shoulderWidth", 0.0))  # -1.0 to 1.0
        sw_ratio = bp.proportions.get("shoulder_to_waist_ratio")
        if sw_ratio and sw_ratio >= 1.30 and avatar_shoulder_mod < 0.10:
            mismatches.append({
                "attribute": "shoulder_breadth",
                "fashion_dna_value": f"Shoulder-to-waist ratio {sw_ratio} (athletic / broad)",
                "avatar_value": f"shoulderWidth mod {avatar_shoulder_mod}",
                "difference": "Avatar appears narrower across shoulder frame than measured profile",
                "severity": "low",
                "recommendation": "Adjust avatar shoulderWidth to +0.20 to reflect athletic frame."
            })
            validated_parameter_updates["shoulderWidth"] = 0.20

        # 3. Torso to Leg Proportion Check
        tl_ratio = bp.proportions.get("torso_to_leg_ratio")
        avatar_torso_mod = float(props.get("torsoLength", 0.0))
        if tl_ratio and tl_ratio > 0.72 and avatar_torso_mod < 0.0:
            mismatches.append({
                "attribute": "torso_length",
                "fashion_dna_value": f"Torso-to-leg ratio {tl_ratio} (longer torso)",
                "avatar_value": f"torsoLength mod {avatar_torso_mod}",
                "difference": "Avatar torso visually shorter than measured proportion",
                "severity": "low",
                "recommendation": "Adjust avatar torsoLength parameter to +0.10."
            })
            validated_parameter_updates["torsoLength"] = 0.10

        return {
            "user_id": user_id,
            "has_mismatches": len(mismatches) > 0,
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
            "validated_parameter_updates": validated_parameter_updates,
            "disclaimer": "Avatar DNA morphs represent interactive 3D visual approximations. They do not constitute laser-scanned body scans."
        }

    def sync_from_avatar_dna(self, user_id: str, avatar_profile: Dict[str, Any]) -> FashionDNA:
        """
        Derives baseline physical stature, silhouette, and colour undertone from Avatar DNA.
        Preserves existing manual/user_confirmed measurements.
        """
        dna = self.get_fashion_dna(user_id)
        bp = dna.body_profile
        raw_props = avatar_profile.get("proportions")
        props = raw_props if isinstance(raw_props, dict) else {}

        # Only sync height if not explicitly confirmed by user
        if bp.measurement_sources.get("height_cm") != "user_confirmed":
            height_val = (
                props.get("heightCm")
                or avatar_profile.get("height_cm")
                or avatar_profile.get("height")
            )
            if height_val and isinstance(height_val, (int, float)):
                if height_val <= 2.5:
                    bp.height_cm = 160.0 + height_val * 30.0
                else:
                    bp.height_cm = float(height_val)
                bp.measurement_sources["height_cm"] = "avatar_derived"
                bp.measurement_confidences["height_cm"] = 0.80

            # Derive body silhouette from avatar body shape
            body_shape = (
                props.get("silhouette")
                or avatar_profile.get("body_shape")
                or avatar_profile.get("bodyType")
            )
            if body_shape:
                bp.silhouette = str(body_shape).lower()

            bp.measurement_source = "avatar_derived"

            bp.measurement_source = "avatar_derived"

        # Derive skin tone/undertone from avatar skin hex or undertone if present
        app = avatar_profile.get("appearance", {})
        skin_undertone = app.get("skinUndertone") or avatar_profile.get("skin_undertone") or avatar_profile.get("undertone")
        if skin_undertone in ["warm", "cool", "neutral", "uncertain"]:
            dna.colour_profile.skin_undertone = skin_undertone
            dna.colour_profile.source = "avatar_derived"

        skin_hex = app.get("skinToneHex") or avatar_profile.get("skin_hex")
        if skin_hex:
            dna.colour_profile.skin_hex = skin_hex

        color_season = avatar_profile.get("color_season")
        if color_season:
            dna.colour_profile.personal_palette = str(color_season).lower()

        # Record synchronization signal
        dna.preference_evolution.append(PreferenceSignal(
            signal_id=str(uuid.uuid4())[:8],
            signal_type="inferred",
            category="avatar_sync",
            value={"body_shape": bp.silhouette, "height_cm": bp.height_cm},
            weight=0.5,
            source="avatar_dna_sync"
        ))

        dna.updated_at = datetime.utcnow().isoformat()
        self.repo.upsert_fashion_dna(user_id, dna.model_dump())
        return dna

    def evolve_fashion_dna(
        self,
        user_id: str,
        signal_type: str,
        category: str,
        value: Any,
        weight: float = 1.0,
        source: str = "interaction"
    ) -> FashionDNA:
        """
        Evolves user Fashion DNA in response to explicit, inferred, or rejected preference signals.
        Strictly distinguishes permanent profile mutations from temporary styling signals.
        """
        dna = self.get_fashion_dna(user_id)
        signal = PreferenceSignal(
            signal_id=str(uuid.uuid4())[:8],
            signal_type=signal_type,
            category=category,
            value=value,
            weight=weight,
            created_at=datetime.utcnow().isoformat(),
            source=source
        )

        dna.preference_evolution.append(signal)

        # Mutate persistent state only if signal is explicit or permanent rejection
        if signal_type == "explicit":
            if category == "fit" and isinstance(value, str):
                dna.body_profile.fit_preference = value
                dna.confidence_scores.body_fit_confidence = min(1.0, dna.confidence_scores.body_fit_confidence + 0.05)
            elif category == "style" and isinstance(value, str):
                if value not in dna.style_profile.primary_styles:
                    dna.style_profile.primary_styles.append(value)
                dna.confidence_scores.style_affinity_confidence = min(1.0, dna.confidence_scores.style_affinity_confidence + 0.05)
            elif category == "colour" and isinstance(value, str):
                if value not in dna.colour_profile.preferred_colours:
                    dna.colour_profile.preferred_colours.append(value)
                if value in dna.colour_profile.disliked_colours:
                    dna.colour_profile.disliked_colours.remove(value)
            elif category == "brand" and isinstance(value, str):
                if value not in dna.additional_preferences.preferred_brands:
                    dna.additional_preferences.preferred_brands.append(value)

        elif signal_type == "rejected":
            if category == "colour" and isinstance(value, str):
                if value not in dna.colour_profile.disliked_colours:
                    dna.colour_profile.disliked_colours.append(value)
                if value in dna.colour_profile.preferred_colours:
                    dna.colour_profile.preferred_colours.remove(value)
            elif category == "material" and isinstance(value, str):
                if value not in dna.additional_preferences.disliked_materials:
                    dna.additional_preferences.disliked_materials.append(value)
                if value in dna.additional_preferences.preferred_materials:
                    dna.additional_preferences.preferred_materials.remove(value)

        elif signal_type == "temporary":
            # Temporary styling signals (e.g. "for tonight only") do not mutate permanent profile
            pass

        dna.updated_at = datetime.utcnow().isoformat()
        self.repo.upsert_fashion_dna(user_id, dna.model_dump())
        return dna

    def reset_fashion_dna(self, user_id: str) -> FashionDNA:
        """Resets user Fashion DNA to pristine default baseline."""
        default_dna = FashionDNA(user_id=str(user_id))
        self.repo.upsert_fashion_dna(user_id, default_dna.model_dump())
        return default_dna

    def delete_fashion_dna(self, user_id: str) -> bool:
        """Permanently purges user Fashion DNA for GDPR / CCPA compliance."""
        return self.repo.delete_fashion_dna(user_id)


# Global singleton
fashion_dna_service = FashionDNAService()
