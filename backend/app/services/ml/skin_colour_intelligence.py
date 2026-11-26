"""
Model B: Skin & Colour Intelligence Engine (ML Phase 2).
Provides colorimetric analysis in CIELAB color space, illuminant white-balance compensation,
lighting-aware skin undertone classification with honest uncertainty calibration,
personal seasonal & harmonious palette generation, and comprehensive clothing colour compatibility evaluation.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from backend.app.domain.fashion_knowledge import (
    COLOR_PALETTES,
    SEASONAL_COLOR_PALETTES,
    evaluate_color_harmony,
)

logger = logging.getLogger(__name__)

# Standard CIE D65 Illuminant reference white point
XN_D65 = 95.047
YN_D65 = 100.0
ZN_D65 = 108.883

# Representative RGB values for key fashion colors
FASHION_COLOR_RGB: Dict[str, Tuple[int, int, int]] = {
    "black": (20, 20, 20),
    "white": (245, 245, 245),
    "pure white": (255, 255, 255),
    "cream": (242, 236, 219),
    "ivory": (245, 242, 230),
    "navy": (20, 32, 60),
    "midnight navy": (12, 20, 42),
    "charcoal": (48, 50, 52),
    "grey": (128, 128, 132),
    "gray": (128, 128, 132),
    "camel": (193, 154, 107),
    "beige": (225, 214, 194),
    "tan": (180, 140, 95),
    "olive": (95, 105, 65),
    "forest green": (34, 75, 45),
    "emerald": (20, 120, 75),
    "sage": (145, 165, 140),
    "burgundy": (115, 25, 40),
    "maroon": (100, 20, 30),
    "terracotta": (190, 85, 55),
    "rust": (175, 65, 35),
    "mustard": (205, 155, 40),
    "sky blue": (135, 185, 225),
    "royal blue": (25, 65, 175),
    "lavender": (185, 175, 215),
    "pink": (230, 160, 175),
    "coral": (235, 115, 95),
    "neon_yellow": (220, 255, 0),
    "yellow": (235, 205, 45),
    "red": (200, 35, 40)
}


def rgb_to_cielab(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """
    Converts 8-bit sRGB (0-255) to CIELAB (L*, a*, b*) under D65 standard illuminant.
    """
    # 1. Linearize sRGB
    def srgb_to_linear(c_byte: int) -> float:
        c = c_byte / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r_lin = srgb_to_linear(r)
    g_lin = srgb_to_linear(g)
    b_lin = srgb_to_linear(b)

    # 2. Linear RGB to CIE XYZ
    x = (0.4124564 * r_lin + 0.3575761 * g_lin + 0.1804375 * b_lin) * 100.0
    y = (0.2126729 * r_lin + 0.7151522 * g_lin + 0.0721750 * b_lin) * 100.0
    z = (0.0193339 * r_lin + 0.1191920 * g_lin + 0.9503041 * b_lin) * 100.0

    # 3. XYZ to CIELAB
    delta = 6.0 / 29.0

    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > (delta ** 3) else (t / (3.0 * delta ** 2)) + (4.0 / 29.0)

    xr = f(x / XN_D65)
    yr = f(y / YN_D65)
    zr = f(z / ZN_D65)

    l_star = round(116.0 * yr - 16.0, 2)
    a_star = round(500.0 * (xr - yr), 2)
    b_star = round(200.0 * (yr - zr), 2)

    return l_star, a_star, b_star


def cielab_delta_e(lab1: Tuple[float, float, float], lab2: Tuple[float, float, float]) -> float:
    """Computes standard Euclidean CIELAB Delta E* color difference."""
    dl = lab1[0] - lab2[0]
    da = lab1[1] - lab2[1]
    db = lab1[2] - lab2[2]
    return round(math.sqrt(dl * dl + da * da + db * db), 2)


class SkinColorAnalysis(BaseModel):
    """Lighting-aware skin color analysis result."""
    skin_tone_range: str
    skin_undertone: str
    uncertainty_score: float = Field(..., ge=0.0, le=1.0, description="0.0 = absolute certainty, 1.0 = completely uncertain")
    confidence: float = Field(..., ge=0.0, le=1.0)
    cielab: Dict[str, float]
    lighting_condition: str
    lighting_compensation_applied: bool
    diagnostic_notes: List[str]


class PersonalPaletteDetails(BaseModel):
    """Rich personalized color palette representation."""
    palette_id: str
    palette_name: str
    description: str
    complementary_colours: List[str]
    analogous_colours: List[str]
    neutral_anchors: List[str]
    accent_colours: List[str]
    recommended_contrast: str
    avoid_strict_prohibitions: bool = True
    styling_guidelines: List[str]


class ColourCompatibilityResult(BaseModel):
    """Evaluates clothing colour compatibility with user colour profile and outfit context."""
    compatibility_score: float = Field(..., ge=0.0, le=100.0)
    is_compatible: bool
    contrast_level: str
    harmonic_relationship: str
    explanation: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    alternative_suggestions: List[str]


class SkinColourIntelligenceService:
    """Model B: Colorimetric undertone analysis, lighting calibration, and clothing harmony."""

    SEASONAL_PALETTE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
        "spring_warm": {
            "name": "Spring Warm",
            "description": "Luminous, golden-undertoned palette featuring clear, fresh warmth and moderate contrast.",
            "complementary": ["coral", "sage", "light navy", "warm yellow"],
            "analogous": ["camel", "peach", "cream"],
            "neutral_anchors": ["ivory", "camel", "light navy", "cream"],
            "accent_colours": ["coral", "warm yellow", "gold"],
            "contrast": "medium",
            "styling_guidelines": [
                "Warm golden undertones shine alongside camel and creamy neutrals.",
                "Incorporate clear coral or sage accents to illuminate complexion.",
                "Avoid overwhelming high-contrast stark jet black near the collar."
            ]
        },
        "summer_cool": {
            "name": "Summer Cool",
            "description": "Soft, muted palette with cool blue and rosy undertones that benefits from subtle tonal harmony.",
            "complementary": ["lavender", "soft grey", "rose", "sky blue"],
            "analogous": ["sage", "slate", "off-white"],
            "neutral_anchors": ["charcoal", "soft grey", "navy", "off-white"],
            "accent_colours": ["lavender", "rose", "sky blue"],
            "contrast": "low_to_medium",
            "styling_guidelines": [
                "Cool rosy undertones complement slate grey and heather textures.",
                "Subtle tonal layering produces understated elegance.",
                "Muted jewel tones and soft blues enhance natural eye and hair depth."
            ]
        },
        "autumn_deep": {
            "name": "Autumn Deep",
            "description": "Rich, earthy palette anchored in warm burnished spices, deep forest tones, and textured neutrals.",
            "complementary": ["terracotta", "forest green", "mustard", "burgundy"],
            "analogous": ["camel", "rust", "olive", "warm brown"],
            "neutral_anchors": ["charcoal", "camel", "navy", "cream", "taupe"],
            "accent_colours": ["terracotta", "forest green", "mustard"],
            "contrast": "medium_to_high",
            "styling_guidelines": [
                "Warm, deep undertones thrive with rich olive, terracotta, and deep forest hues.",
                "Pair textured cream knits with charcoal or camel outer layers.",
                "Earthy tonal harmonies create an effortless, luxurious presence."
            ]
        },
        "winter_clear": {
            "name": "Winter Clear",
            "description": "High-contrast, striking palette celebrating vivid jewel tones, deep saturations, and pure monochromes.",
            "complementary": ["royal blue", "emerald", "burgundy", "charcoal"],
            "analogous": ["stark black", "pure white", "ruby red"],
            "neutral_anchors": ["stark black", "pure white", "charcoal", "midnight navy"],
            "accent_colours": ["royal blue", "emerald", "silver", "ruby red"],
            "contrast": "high",
            "styling_guidelines": [
                "Crisp high contrast (stark black with pure white or vivid jewel tones) creates magnetic structure.",
                "Rich saturated emerald and royal blue frame cool undertones with authority.",
                "Clean, non-distressed silhouettes maximize chromatic clarity."
            ]
        },
        "neutral_versatile": {
            "name": "Neutral Versatile",
            "description": "Balanced, adaptable palette engineered for timeless versatility across neutral spectrums.",
            "complementary": ["navy", "charcoal", "forest green", "burgundy"],
            "analogous": ["camel", "cream", "grey", "white"],
            "neutral_anchors": ["navy", "charcoal", "cream", "camel", "black"],
            "accent_colours": ["olive", "burgundy", "sky blue"],
            "contrast": "medium",
            "styling_guidelines": [
                "Balanced undertones allow effortless transition across both warm and cool clothing pieces.",
                "Classic navy and charcoal foundational pieces anchor any contemporary look.",
                "Accent with seasonal pops (olive, burgundy) for intentional focal points."
            ]
        }
    }

    def analyze_skin_tone_lighting_aware(
        self,
        r: int,
        g: int,
        b: int,
        ambient_hint: str = "neutral_daylight"
    ) -> SkinColorAnalysis:
        """
        Performs lighting-aware colorimetric skin analysis in CIELAB space.
        Applies illuminant compensation and computes explicit uncertainty.
        """
        # Convert to CIELAB
        l_star, a_star, b_star = rgb_to_cielab(r, g, b)
        diagnostic_notes: List[str] = []
        uncertainty = 0.15
        compensation_applied = False

        # Lighting check 1: Exposure extremes
        if l_star > 90.0:
            diagnostic_notes.append("Image exhibits high exposure highlights or flash wash; skin tone may read artificially pale.")
            uncertainty += 0.35
        elif l_star < 24.0:
            diagnostic_notes.append("Image is heavily shadowed or underexposed; subtle undertone nuance is degraded.")
            uncertainty += 0.40

        # Lighting check 2: Ambient illuminant bias compensation
        if ambient_hint in ["warm_indoor", "tungsten"] or (b_star > 26.0 and a_star < 12.0):
            # Compensate warm light cast
            b_star = round(b_star - 4.5, 2)
            compensation_applied = True
            diagnostic_notes.append("Applied chromatic illuminant compensation for warm ambient lighting.")
        elif ambient_hint in ["cool_fluorescent", "cloudy_blue"]:
            b_star = round(b_star + 3.0, 2)
            compensation_applied = True
            diagnostic_notes.append("Applied chromatic illuminant compensation for cool ambient tint.")

        # Skin Tone Range classification based on L*
        if l_star >= 76.0:
            tone_range = "fair" if l_star >= 84.0 else "light"
        elif l_star >= 56.0:
            tone_range = "medium"
        elif l_star >= 42.0:
            tone_range = "tan"
        elif l_star >= 28.0:
            tone_range = "rich"
        else:
            tone_range = "deep"

        # Undertone classification based on CIELAB a* (green-red) and b* (blue-yellow)
        # Warm skins typically show higher yellow-golden b* relative to a*.
        # Cool skins show lower b* or elevated pink/blue-red ratio.
        b_margin = abs(b_star - 11.5)
        
        # If hovering very close to the decision boundary (b* ~ 11.0 to 12.0), raise uncertainty
        if b_margin < 1.0:
            uncertainty += 0.20
            diagnostic_notes.append("Colorimetric readings reside closely on the warm-cool boundary; profile may lean neutral.")

        if uncertainty >= 0.55:
            undertone = "uncertain"
            diagnostic_notes.append("High illuminant variance observed; user manual confirmation recommended.")
        elif b_star >= 13.5:
            undertone = "warm"
        elif b_star <= 9.5:
            undertone = "cool"
        else:
            undertone = "neutral"

        confidence = round(max(0.2, min(1.0, 1.0 - uncertainty)), 2)

        return SkinColorAnalysis(
            skin_tone_range=tone_range,
            skin_undertone=undertone,
            uncertainty_score=round(min(1.0, uncertainty), 2),
            confidence=confidence,
            cielab={"L": l_star, "a": a_star, "b": b_star},
            lighting_condition=ambient_hint,
            lighting_compensation_applied=compensation_applied,
            diagnostic_notes=diagnostic_notes
        )

    def get_personal_colour_palette(
        self,
        undertone: str = "neutral",
        skin_tone_range: str = "medium",
        user_preferred_palette: Optional[str] = None
    ) -> PersonalPaletteDetails:
        """
        Generates comprehensive seasonal, complementary, analogous, and neutral anchor palettes.
        """
        palette_key = user_preferred_palette
        if not palette_key:
            ut = undertone.lower()
            tone = skin_tone_range.lower()
            if ut == "warm":
                palette_key = "autumn_deep" if tone in ["medium", "tan", "rich", "deep"] else "spring_warm"
            elif ut == "cool":
                palette_key = "winter_clear" if tone in ["tan", "rich", "deep", "fair"] else "summer_cool"
            else:
                palette_key = "neutral_versatile"

        palette_data = self.SEASONAL_PALETTE_DEFINITIONS.get(
            palette_key,
            self.SEASONAL_PALETTE_DEFINITIONS["neutral_versatile"]
        )

        return PersonalPaletteDetails(
            palette_id=palette_key,
            palette_name=palette_data["name"],
            description=palette_data["description"],
            complementary_colours=palette_data["complementary"],
            analogous_colours=palette_data["analogous"],
            neutral_anchors=palette_data["neutral_anchors"],
            accent_colours=palette_data["accent_colours"],
            recommended_contrast=palette_data["contrast"],
            avoid_strict_prohibitions=True,
            styling_guidelines=palette_data["styling_guidelines"]
        )

    def evaluate_colour_compatibility(
        self,
        garment_colors: List[str],
        user_undertone: str = "neutral",
        personal_palette: str = "neutral_versatile",
        preferred_colors: Optional[List[str]] = None,
        disliked_colors: Optional[List[str]] = None,
        occasion: str = "casual"
    ) -> ColourCompatibilityResult:
        """
        Evaluates clothing colour compatibility for single garments or complete multi-piece outfits.
        Computes CIELAB delta E color distances, color harmony, contrast level, and alternative suggestions.
        """
        garments_clean = [c.lower().strip() for c in garment_colors if c]
        pref_clean = [p.lower().strip() for p in (preferred_colors or [])]
        disliked_clean = [d.lower().strip() for d in (disliked_colors or [])]

        if not garments_clean:
            return ColourCompatibilityResult(
                compatibility_score=75.0,
                is_compatible=True,
                contrast_level="medium",
                harmonic_relationship="neutral",
                explanation="No explicit garment colors evaluated; defaults to balanced neutral assumption.",
                confidence=0.70,
                alternative_suggestions=["navy", "charcoal", "cream"]
            )

        # 1. Hard Dislike Penalty Check
        for gc in garments_clean:
            if gc in disliked_clean:
                return ColourCompatibilityResult(
                    compatibility_score=35.0,
                    is_compatible=False,
                    contrast_level="high",
                    harmonic_relationship="discordant",
                    explanation=f"Color '{gc}' matches an item on your explicit disliked colours list.",
                    confidence=0.98,
                    alternative_suggestions=["navy", "charcoal", "olive", "camel"]
                )

        # 2. CIELAB Evaluation of Garment Hues
        palette_details = self.get_personal_colour_palette(user_undertone, user_preferred_palette=personal_palette)
        palette_harmonizing = set(palette_details.complementary_colours + palette_details.neutral_anchors + palette_details.accent_colours)

        direct_matches = [gc for gc in garments_clean if gc in palette_harmonizing]
        preferred_matches = [gc for gc in garments_clean if gc in pref_clean]

        # 3. Two-piece or Multi-piece Harmony Analysis
        if len(garments_clean) >= 2:
            base_harmony, harmony_note = evaluate_color_harmony(garments_clean)
            c1_rgb = FASHION_COLOR_RGB.get(garments_clean[0], (100, 100, 100))
            c2_rgb = FASHION_COLOR_RGB.get(garments_clean[1], (200, 200, 200))
            lab1 = rgb_to_cielab(*c1_rgb)
            lab2 = rgb_to_cielab(*c2_rgb)
            delta_e = cielab_delta_e(lab1, lab2)

            # Contrast determination
            if delta_e >= 45.0:
                contrast_level = "high"
                harmonic_rel = "complementary_contrast"
            elif delta_e >= 20.0:
                contrast_level = "medium"
                harmonic_rel = "balanced_harmony"
            else:
                contrast_level = "low"
                harmonic_rel = "tonal_monochromatic"

            composite_score = round(base_harmony * 85.0 + (10.0 if direct_matches else 0.0) + (5.0 if preferred_matches else 0.0), 1)
            explanation = f"{harmony_note}. {contrast_level.capitalize()} contrast (ΔE* {delta_e}) creates refined visual cohesion."
        else:
            # Single garment check
            gc = garments_clean[0]
            contrast_level = "medium"
            if gc in palette_harmonizing:
                composite_score = 96.0
                harmonic_rel = "palette_synergy"
                explanation = f"Garment color '{gc}' natively resonates with your {palette_details.palette_name} personal palette."
            elif any(n in gc for n in COLOR_PALETTES["neutrals"]):
                composite_score = 90.0
                harmonic_rel = "neutral_anchor"
                explanation = f"Neutral shade '{gc}' acts as a versatile canvas complementing any personal undertone."
            else:
                composite_score = 80.0
                harmonic_rel = "expressive_accent"
                explanation = f"Garment color '{gc}' provides a confident chromatic pop."

        # Preferred bonus
        if preferred_matches:
            composite_score = min(100.0, composite_score + 3.0)
            explanation += f" Highlights your personal favorite tone: '{preferred_matches[0]}'."

        return ColourCompatibilityResult(
            compatibility_score=composite_score,
            is_compatible=composite_score >= 70.0,
            contrast_level=contrast_level,
            harmonic_relationship=harmonic_rel,
            explanation=explanation,
            confidence=0.92,
            alternative_suggestions=palette_details.neutral_anchors[:3] + palette_details.accent_colours[:2]
        )

    # Legacy method compatibility
    def analyze_colour_profile(
        self,
        skin_hex: Optional[str] = None,
        skin_tone_range: str = "medium",
        user_specified_undertone: Optional[str] = None
    ) -> Any:
        """Maintains backward compatibility with Phase 1 callers."""
        from pydantic import BaseModel as BM

        class LegacyResult(BM):
            skin_tone_range: str
            skin_undertone: str
            personal_palette: str
            best_harmonizing_colors: List[str]
            palette_description: str
            contrast_recommendation: str
            confidence: float

        if user_specified_undertone and user_specified_undertone in ["warm", "cool", "neutral", "uncertain"]:
            ut = user_specified_undertone
            conf = 0.95
        elif skin_hex and len(skin_hex.lstrip("#")) == 6:
            clean = skin_hex.lstrip("#")
            r, g, b = int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)
            analysis = self.analyze_skin_tone_lighting_aware(r, g, b)
            ut = analysis.skin_undertone
            conf = analysis.confidence
        else:
            ut = "neutral"
            conf = 0.80

        palette = self.get_personal_colour_palette(ut, skin_tone_range)
        best_colors = palette.neutral_anchors + palette.accent_colours

        return LegacyResult(
            skin_tone_range=skin_tone_range,
            skin_undertone=ut,
            personal_palette=palette.palette_id,
            best_harmonizing_colors=best_colors,
            palette_description=palette.description,
            contrast_recommendation=f"{palette.recommended_contrast.capitalize()} contrast flattering this profile.",
            confidence=conf
        )

    def evaluate_clothing_colour_harmony(
        self,
        garment_colors: List[str],
        personal_palette: str,
        preferred_colors: List[str],
        disliked_colors: List[str]
    ) -> Dict[str, Any]:
        """Legacy method for outfit ranking compatibility."""
        res = self.evaluate_colour_compatibility(
            garment_colors=garment_colors,
            personal_palette=personal_palette,
            preferred_colors=preferred_colors,
            disliked_colors=disliked_colors
        )
        return {
            "harmony_score": res.compatibility_score,
            "is_harmonious": res.is_compatible,
            "rationale": res.explanation
        }


# Global singleton
skin_colour_intelligence_service = SkinColourIntelligenceService()
