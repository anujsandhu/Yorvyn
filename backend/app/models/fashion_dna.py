"""
Pydantic Data Models for Yorvyn Fashion DNA.
Provides strongly typed schemas for user body proportions, skin tone and undertones,
personal colour palettes, style affinities, preference signals, and confidence evolution.
Separate from Avatar DNA (which defines 3D visual geometry/rig morphs).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MeasurementProvenance(BaseModel):
    """Tracks origin, reliability, and confirmation state of physical measurements."""
    source: str = Field(
        "estimated",
        description="Origin: 'user_confirmed', 'avatar_derived', 'cv_estimated', or 'inferred'."
    )
    confidence: float = Field(0.8, ge=0.0, le=1.0, description="Confidence metric for measurement.")
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class BodyProfile(BaseModel):
    """Structural body measurements, continuous proportions, and fit preferences."""
    # Stature and primary circumferences (in cm)
    height_cm: float = Field(178.0, ge=100.0, le=250.0, description="Height in centimeters.")
    weight_kg: Optional[float] = Field(None, ge=30.0, le=300.0, description="Weight in kilograms, if voluntarily provided.")
    shoulder_cm: Optional[float] = Field(None, ge=20.0, le=80.0, description="Shoulder breadth in cm.")
    shoulder_width_cm: Optional[float] = Field(None, ge=20.0, le=80.0, description="Shoulder width in cm.")
    chest_cm: Optional[float] = Field(None, ge=50.0, le=180.0, description="Chest circumference in cm.")
    waist_cm: Optional[float] = Field(None, ge=40.0, le=160.0, description="Waist circumference in cm.")
    hip_cm: Optional[float] = Field(None, ge=50.0, le=180.0, description="Hip circumference in cm.")
    
    # Extended continuous garment-fit measurements
    torso_length_cm: Optional[float] = Field(None, ge=30.0, le=90.0, description="Torso length from C7 to hip crest.")
    arm_length_cm: Optional[float] = Field(None, ge=40.0, le=110.0, description="Arm length from shoulder to wrist bone.")
    inseam_cm: Optional[float] = Field(None, ge=50.0, le=120.0, description="Leg inseam from crotch to ankle.")
    thigh_cm: Optional[float] = Field(None, ge=30.0, le=100.0, description="Thigh circumference in cm.")
    neck_cm: Optional[float] = Field(None, ge=25.0, le=60.0, description="Neck circumference in cm.")

    # Unit configuration
    unit_preference: str = Field("cm", description="Preferred display and entry unit: 'cm' or 'in'.")

    # Proportions & descriptive silhouettes (continuous ratios preserved)
    torso_proportion: str = Field("balanced", description="Torso proportion: short, balanced, or long.")
    arm_proportion: str = Field("balanced", description="Arm proportion: short, balanced, or long.")
    leg_proportion: str = Field("balanced", description="Leg proportion: short, balanced, or long.")
    silhouette: str = Field(
        "athletic",
        description="Continuous body silhouette descriptor: rectangle, hourglass, inverted_triangle, pear, athletic, oval, lean, natural."
    )
    proportions: Dict[str, float] = Field(
        default_factory=dict,
        description="Calculated continuous ratios: shoulder_to_hip, waist_to_hip, shoulder_to_waist, torso_to_leg, upper_to_lower."
    )

    # Fit preferences
    fit_preference: str = Field(
        "regular",
        description="Primary fit preference: slim, tailored, regular, relaxed, athletic, or oversized."
    )
    category_fit_preferences: Dict[str, str] = Field(
        default_factory=lambda: {"tops": "regular", "bottoms": "regular", "outerwear": "regular"},
        description="Per-category fit preferences."
    )

    # Provenance tracking per measurement
    measurement_source: str = Field(
        "estimated",
        description="Overall profile measurement origin: 'user_confirmed', 'avatar_derived', 'cv_estimated', or 'inferred'."
    )
    measurement_sources: Dict[str, str] = Field(
        default_factory=dict,
        description="Granular provenance per measurement key."
    )
    measurement_confidences: Dict[str, float] = Field(
        default_factory=dict,
        description="Confidence scores per measurement key (0.0 to 1.0)."
    )
    measurement_updated_at: Dict[str, str] = Field(
        default_factory=dict,
        description="Last updated timestamp per measurement key."
    )


class ColourProfile(BaseModel):
    """Colorimetrics, skin undertones, seasonal palettes, and palette affinities."""
    skin_tone_range: str = Field("medium", description="Skin tone category: fair, light, medium, tan, rich, deep.")
    skin_undertone: str = Field("neutral", description="Undertone classification: warm, cool, neutral, uncertain.")
    skin_hex: Optional[str] = Field(None, description="Optional hex representation of analyzed skin tone.")
    
    # CIELAB colorimetry & lighting compensation
    cielab_l: Optional[float] = Field(None, ge=0.0, le=100.0, description="CIELAB Lightness L*")
    cielab_a: Optional[float] = Field(None, ge=-128.0, le=127.0, description="CIELAB Green-Red a*")
    cielab_b: Optional[float] = Field(None, ge=-128.0, le=127.0, description="CIELAB Blue-Yellow b*")
    lighting_condition: str = Field("neutral_daylight", description="neutral_daylight, warm_indoor, cool_fluorescent, uncalibrated.")
    lighting_compensation_applied: bool = Field(False, description="Whether illuminant correction was applied.")

    # Personal seasonal and harmonious palettes
    personal_palette: str = Field("autumn_deep", description="Seasonal palette key: spring_warm, summer_cool, autumn_deep, winter_clear, neutral_versatile.")
    seasonal_palette_name: str = Field("Autumn Deep", description="Human-readable seasonal palette title.")
    complementary_colours: List[str] = Field(default_factory=list, description="Complementary color harmonies.")
    analogous_colours: List[str] = Field(default_factory=list, description="Analogous neighboring shades.")
    neutral_anchors: List[str] = Field(default_factory=lambda: ["charcoal", "navy", "cream", "white"])
    accent_colours: List[str] = Field(default_factory=lambda: ["terracotta", "forest_green", "mustard"])
    
    preferred_colours: List[str] = Field(default_factory=lambda: ["navy", "charcoal", "olive", "cream"])
    disliked_colours: List[str] = Field(default_factory=lambda: ["neon_yellow"])
    preferred_harmonies: List[str] = Field(default_factory=lambda: ["complementary", "tonal", "monochromatic"])
    contrast_preference: str = Field("medium", description="Preferred contrast level: low, medium, high.")
    
    confidence: float = Field(0.85, ge=0.0, le=1.0, description="Confidence in colour profile classification.")
    source: str = Field("estimated", description="'user_confirmed', 'avatar_derived', 'cv_estimated', or 'inferred'.")


class StyleProfile(BaseModel):
    """Personal aesthetics, style genres, and occasion frequency."""
    primary_styles: List[str] = Field(
        default_factory=lambda: ["smart_casual", "minimalist"],
        description="Curated styles: casual, smart_casual, formal, streetwear, minimalist, old_money, athleisure, ethnic, business, luxury, experimental."
    )
    aesthetic_tags: List[str] = Field(default_factory=lambda: ["tailored", "clean", "timeless"])
    occasion_frequency: Dict[str, float] = Field(
        default_factory=lambda: {"casual": 0.4, "work": 0.4, "formal": 0.2}
    )


class AdditionalPreferences(BaseModel):
    """Brand affinities, fabric preferences, budget levels, and seasonal climate."""
    gender_presentation: str = Field("androgynous", description="masculine, feminine, androgynous, unspecified.")
    age_range: Optional[str] = Field("25-34", description="Voluntarily provided age demographic bracket.")
    preferred_brands: List[str] = Field(default_factory=lambda: ["COS", "Arket", "Uniqlo"])
    preferred_materials: List[str] = Field(default_factory=lambda: ["wool", "cotton", "linen"])
    disliked_materials: List[str] = Field(default_factory=lambda: ["polyester"])
    budget_level: str = Field("mid", description="budget, mid, premium, luxury.")
    min_budget: float = Field(30.0, ge=0.0)
    max_budget: float = Field(350.0, ge=0.0)
    currency: str = Field("USD")
    climate_preference: str = Field("temperate", description="tropical, temperate, cold, variable.")


class PreferenceConfidence(BaseModel):
    """Confidence calibration across distinct Fashion DNA aspects."""
    body_fit_confidence: float = Field(0.80, ge=0.0, le=1.0)
    colour_harmony_confidence: float = Field(0.85, ge=0.0, le=1.0)
    style_affinity_confidence: float = Field(0.85, ge=0.0, le=1.0)
    overall_dna_confidence: float = Field(0.85, ge=0.0, le=1.0)


class PreferenceSignal(BaseModel):
    """An interaction signal that evolves or adjusts the user's Fashion DNA."""
    signal_id: str
    signal_type: str = Field(
        ...,
        description="explicit (user statement/form), inferred (ML vision/choice pattern), temporary (event-specific), rejected (disliked item/palette), uncertain."
    )
    category: str = Field(..., description="colour, fit, style, brand, material, occasion, silhouette.")
    value: Any
    weight: float = Field(1.0, ge=-1.0, le=1.0)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = Field("user_interaction", description="chat, feedback, avatar_sync, wardrobe_action.")


class FashionDNA(BaseModel):
    """Complete, persistent, evolving user Fashion Intelligence profile."""
    user_id: str
    body_profile: BodyProfile = Field(default_factory=BodyProfile)
    colour_profile: ColourProfile = Field(default_factory=ColourProfile)
    style_profile: StyleProfile = Field(default_factory=StyleProfile)
    additional_preferences: AdditionalPreferences = Field(default_factory=AdditionalPreferences)
    confidence_scores: PreferenceConfidence = Field(default_factory=PreferenceConfidence)
    preference_evolution: List[PreferenceSignal] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
