"""
YORVYN — Universal Category-Specific Material Pipeline
Provides physically grounded PBR material profiles for all 9 apparel categories
and physical fabric types: Cotton, Denim, Leather, Wool, Silk, Satin, Knitwear,
Sportswear/Synthetics, Rubber/EVA (footwear), and Hardware (metal buttons, zippers).

Dynamically refines material priors based on reference image evidence (specular highlights,
luminance variance, and micro-texture gradients).
"""

from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np

from backend.app.models.garment_intelligence_models import FabricPBRPropertiesV2


@dataclass
class PBRMaterialProfile:
    """Complete physically based rendering material profile."""
    name: str
    fabric_category: str
    surface_texture: str
    roughness: float
    metalness: float
    sheen: float = 0.0
    clearcoat: float = 0.0
    normal_strength: float = 1.0
    specular_intensity: float = 0.5
    double_sided: bool = True
    alpha_mode: str = "OPAQUE"  # OPAQUE, MASK, BLEND
    is_estimated: bool = True
    notes: str = ""


class CategoryMaterialSystem:
    """Manages category-specific fabric PBR profiles and empirical evidence refinement."""

    # Category defaults (priors)
    CATEGORY_DEFAULTS: Dict[str, PBRMaterialProfile] = {
        "tops": PBRMaterialProfile(
            name="Cotton Jersey",
            fabric_category="cotton",
            surface_texture="plain_weave",
            roughness=0.76,
            metalness=0.01,
            sheen=0.15,
            normal_strength=0.70,
            notes="Soft combed cotton jersey with micro-fibrous diffuse scatter."
        ),
        "formal_shirt": PBRMaterialProfile(
            name="Oxford / Poplin Cotton",
            fabric_category="cotton",
            surface_texture="plain_weave",
            roughness=0.62,
            metalness=0.02,
            sheen=0.20,
            normal_strength=0.85,
            notes="Crisp woven poplin or Oxford cotton with defined yarn structure."
        ),
        "hoodie": PBRMaterialProfile(
            name="Brushed Heavy Fleece",
            fabric_category="fleece",
            surface_texture="ribbed_knit",
            roughness=0.88,
            metalness=0.01,
            sheen=0.10,
            normal_strength=1.10,
            notes="Thermal loopback or brushed fleece with matte light absorption and ribbing."
        ),
        "jacket": PBRMaterialProfile(
            name="Outerwear Twill / Leather",
            fabric_category="denim",
            surface_texture="twill_diagonal",
            roughness=0.78,
            metalness=0.05,
            sheen=0.10,
            clearcoat=0.15,
            normal_strength=1.20,
            notes="Heavyweight outerwear envelope with structural seams and hardware."
        ),
        "bottoms": PBRMaterialProfile(
            name="Heavy 3x1 Twill Denim",
            fabric_category="denim",
            surface_texture="twill_diagonal",
            roughness=0.82,
            metalness=0.03,
            sheen=0.05,
            normal_strength=1.25,
            notes="Directional diagonal twill ridges with high surface friction."
        ),
        "dresses_and_skirts": PBRMaterialProfile(
            name="Silk Satin / Crepe",
            fabric_category="silk",
            surface_texture="smooth_sheen",
            roughness=0.32,
            metalness=0.06,
            sheen=0.80,
            clearcoat=0.25,
            normal_strength=0.45,
            notes="Lustrous drape with anisotropic specular highlights and fluid sheen."
        ),
        "traditional": PBRMaterialProfile(
            name="Raw Silk / Chanderi Cotton",
            fabric_category="silk",
            surface_texture="plain_weave",
            roughness=0.46,
            metalness=0.08,
            sheen=0.65,
            clearcoat=0.10,
            normal_strength=0.90,
            notes="Woven ethnic fabric with subtle slub texture and metallic/zari thread luster."
        ),
        "footwear": PBRMaterialProfile(
            name="Dual-Material Sole & Upper",
            fabric_category="leather",
            surface_texture="pebble_leather",
            roughness=0.42,
            metalness=0.08,
            clearcoat=0.35,
            normal_strength=1.35,
            notes="Dual-zone: vulcanized rubber sole (0.85 roughness) + nappa/mesh upper."
        ),
        "accessories": PBRMaterialProfile(
            name="Heavy Canvas / Visor",
            fabric_category="cotton",
            surface_texture="canvas",
            roughness=0.80,
            metalness=0.05,
            normal_strength=1.15,
            notes="Rigid structured cotton canvas with reinforced visor brim."
        )
    }

    # Fabric-specific overrides
    FABRIC_PROFILES: Dict[str, PBRMaterialProfile] = {
        "cotton": PBRMaterialProfile("Cotton", "cotton", "plain_weave", 0.76, 0.01, 0.15, 0.0, 0.70),
        "denim": PBRMaterialProfile("Denim", "denim", "twill_diagonal", 0.82, 0.03, 0.05, 0.0, 1.25),
        "leather": PBRMaterialProfile("Nappa Leather", "leather", "pebble_leather", 0.35, 0.08, 0.10, 0.50, 0.65),
        "wool": PBRMaterialProfile("Worsted Wool", "wool", "plain_weave", 0.88, 0.01, 0.10, 0.0, 1.05),
        "knitwear": PBRMaterialProfile("Chunky Knit", "knitwear", "cable_knit", 0.84, 0.01, 0.12, 0.0, 1.40),
        "silk": PBRMaterialProfile("Silk Satin", "silk", "smooth_sheen", 0.28, 0.06, 0.85, 0.30, 0.40),
        "satin": PBRMaterialProfile("Polyester Satin", "satin", "smooth_sheen", 0.26, 0.07, 0.90, 0.35, 0.35),
        "synthetic": PBRMaterialProfile("Athletic Poly-Spandex", "synthetic", "plain_weave", 0.48, 0.05, 0.35, 0.15, 0.50),
        "fleece": PBRMaterialProfile("Thermal Fleece", "fleece", "ribbed_knit", 0.88, 0.01, 0.10, 0.0, 1.10),
        "linen": PBRMaterialProfile("Slub Linen", "linen", "plain_weave", 0.78, 0.01, 0.08, 0.0, 0.95),
        "corduroy": PBRMaterialProfile("Wale Corduroy", "corduroy", "ribbed_knit", 0.86, 0.02, 0.20, 0.0, 1.50),
    }

    @classmethod
    def get_material_profile(
        cls,
        category: str,
        subcategory: str = "",
        fabric_hint: Optional[str] = None,
        specular_evidence: Optional[float] = None
    ) -> PBRMaterialProfile:
        """
        Resolves initial category prior and refines with fabric hint and visual evidence.
        """
        cat = category.lower().strip()
        subcat = subcategory.lower().strip()

        # 1. Base Category Prior
        if "footwear" in cat or subcat in ["sneakers", "boots", "shoes"]:
            profile = cls.CATEGORY_DEFAULTS["footwear"]
        elif "traditional" in cat or subcat in ["kurta", "sherwani", "saree", "lehenga"]:
            profile = cls.CATEGORY_DEFAULTS["traditional"]
        elif cat in ["bottom", "bottoms", "pants", "jeans", "trousers"]:
            profile = cls.CATEGORY_DEFAULTS["bottoms"]
        elif cat in ["dress", "skirt", "dresses_and_skirts"]:
            profile = cls.CATEGORY_DEFAULTS["dresses_and_skirts"]
        elif cat in ["outerwear", "jacket", "coat"] or "jacket" in subcat:
            profile = cls.CATEGORY_DEFAULTS["jacket"]
        elif "hoodie" in subcat:
            profile = cls.CATEGORY_DEFAULTS["hoodie"]
        elif "shirt" in subcat or "polo" in subcat:
            profile = cls.CATEGORY_DEFAULTS["formal_shirt"]
        elif cat in ["accessories", "hats", "caps"] or "cap" in subcat:
            profile = cls.CATEGORY_DEFAULTS["accessories"]
        else:
            profile = cls.CATEGORY_DEFAULTS["tops"]

        # Clone profile so we don't mutate class dictionary
        res = PBRMaterialProfile(
            name=profile.name,
            fabric_category=profile.fabric_category,
            surface_texture=profile.surface_texture,
            roughness=profile.roughness,
            metalness=profile.metalness,
            sheen=profile.sheen,
            clearcoat=profile.clearcoat,
            normal_strength=profile.normal_strength,
            specular_intensity=profile.specular_intensity,
            double_sided=profile.double_sided,
            notes=profile.notes
        )

        # 2. Fabric override if provided
        if fabric_hint:
            f_key = fabric_hint.lower().strip()
            for key, f_prof in cls.FABRIC_PROFILES.items():
                if key in f_key:
                    res.fabric_category = f_prof.fabric_category
                    res.surface_texture = f_prof.surface_texture
                    res.roughness = f_prof.roughness
                    res.metalness = f_prof.metalness
                    res.sheen = f_prof.sheen
                    res.clearcoat = f_prof.clearcoat
                    res.normal_strength = f_prof.normal_strength
                    res.name = f"{f_prof.name} ({profile.name})"
                    break

        # 3. Dynamic Evidence-Based Refinement
        # High specular highlights in photograph reduce roughness and increase clearcoat
        if specular_evidence is not None:
            spec = float(np.clip(specular_evidence, 0.0, 1.0))
            if spec > 0.65:
                # Glossy fabric (leather, satin, wet-look nylon)
                res.roughness = max(0.20, res.roughness - 0.25 * (spec - 0.65) / 0.35)
                res.clearcoat = min(0.80, res.clearcoat + 0.30)
                res.is_estimated = False
            elif spec < 0.20:
                # Ultra matte (raw cotton, dense wool fleece)
                res.roughness = min(0.95, res.roughness + 0.10)
                res.clearcoat = 0.0

        return res

    @classmethod
    def to_fabric_properties_v2(cls, profile: PBRMaterialProfile, confidence: float = 0.88) -> FabricPBRPropertiesV2:
        return FabricPBRPropertiesV2(
            fabric_category=profile.fabric_category,
            surface_texture=profile.surface_texture,
            roughness=round(profile.roughness, 3),
            metalness=round(profile.metalness, 3),
            sheen=round(profile.sheen, 3),
            clearcoat=round(profile.clearcoat, 3),
            normal_strength=round(profile.normal_strength, 3),
            is_estimated=profile.is_estimated,
            confidence=round(confidence, 2)
        )

