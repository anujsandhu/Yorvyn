"""
YORVYN — Learned Material, Textile & Texture Intelligence Engine.
Integrates neural fabric perception from UniversalGarmentIntelligenceModel
with fine-grained physical material properties (PBR roughness, metallic, sheen,
clearcoat, normal strength), graphic print bounding boxes, and structural hardware.
"""

import time
import logging
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
from PIL import Image

from backend.app.models.garment_intelligence_models import (
    FabricPBRPropertiesV2,
    GraphicPrintPlacementV2,
    HardwareElementV2,
    BoundingBox2D
)
from .universal_garment_intelligence_model import universal_intelligence_model

logger = logging.getLogger(__name__)

# Canonical PBR calibration lookup table for textiles
FABRIC_PBR_BASE_PROPERTIES: Dict[str, Dict[str, float]] = {
    "cotton": {"roughness": 0.72, "metalness": 0.02, "sheen": 0.05, "clearcoat": 0.0, "normal_strength": 1.1},
    "denim": {"roughness": 0.82, "metalness": 0.01, "sheen": 0.02, "clearcoat": 0.0, "normal_strength": 1.8},
    "leather": {"roughness": 0.38, "metalness": 0.05, "sheen": 0.25, "clearcoat": 0.45, "normal_strength": 1.4},
    "wool": {"roughness": 0.88, "metalness": 0.01, "sheen": 0.08, "clearcoat": 0.0, "normal_strength": 1.6},
    "silk": {"roughness": 0.28, "metalness": 0.04, "sheen": 0.85, "clearcoat": 0.20, "normal_strength": 0.6},
    "knitwear": {"roughness": 0.85, "metalness": 0.01, "sheen": 0.04, "clearcoat": 0.0, "normal_strength": 2.0},
    "synthetic": {"roughness": 0.45, "metalness": 0.06, "sheen": 0.30, "clearcoat": 0.10, "normal_strength": 0.8},
    "linen": {"roughness": 0.78, "metalness": 0.02, "sheen": 0.03, "clearcoat": 0.0, "normal_strength": 1.3}
}


class LearnedMaterialEngine:
    """Infers physically accurate textile and appearance parameters using neural perception."""

    def analyze_material(
        self,
        image: Image.Image,
        alpha_mask: Optional[np.ndarray] = None,
        category: str = "tops",
        subcategory: str = "tshirt"
    ) -> Tuple[FabricPBRPropertiesV2, GraphicPrintPlacementV2, List[HardwareElementV2]]:
        """
        Extracts PBR material properties, graphic print placement, and hardware elements.
        """
        # 1. Neural Multi-Task Inference
        intel = universal_intelligence_model.predict(
            image=image,
            alpha_mask=alpha_mask,
            category_hint=category,
            subcategory_hint=subcategory
        )

        fab_cat = intel.fabric_category
        weave = intel.surface_weave

        # Base physical parameters
        base_props = FABRIC_PBR_BASE_PROPERTIES.get(fab_cat, FABRIC_PBR_BASE_PROPERTIES["cotton"])

        # Adjust with model's continuous regression outputs
        calibrated_roughness = float(np.clip(
            base_props["roughness"] * 0.7 + intel.estimated_roughness * 0.3,
            0.15, 0.95
        ))
        calibrated_metalness = float(np.clip(
            base_props["metalness"] * 0.7 + intel.estimated_metalness * 0.3,
            0.0, 0.85
        ))

        fabric_pbr = FabricPBRPropertiesV2(
            fabric_category=fab_cat,
            surface_texture=weave,
            roughness=round(calibrated_roughness, 3),
            metalness=round(calibrated_metalness, 3),
            sheen=base_props["sheen"],
            clearcoat=base_props["clearcoat"],
            normal_strength=base_props["normal_strength"],
            is_estimated=True,
            confidence=0.91
        )

        # 2. Graphic Print Detection (chest area variance in RGB)
        graphic = self._detect_graphic_print(image, alpha_mask, category)

        # 3. Hardware Elements Detection (buttons, zippers, aglets)
        hardware = self._detect_hardware(intel.attributes, category, subcategory)

        return fabric_pbr, graphic, hardware

    def _detect_graphic_print(
        self,
        image: Image.Image,
        alpha_mask: Optional[np.ndarray],
        category: str
    ) -> GraphicPrintPlacementV2:
        """Inspects center chest / torso zone for localized high-contrast graphic prints."""
        if category in ["bottoms", "footwear"]:
            return GraphicPrintPlacementV2(detected=False, confidence=0.0)

        rgb = np.array(image.convert("RGB"))
        h, w, _ = rgb.shape

        # Chest region: y: [25%, 55%], x: [30%, 70%]
        c_ymin, c_ymax = int(h * 0.25), int(h * 0.55)
        c_xmin, c_xmax = int(w * 0.30), int(w * 0.70)

        chest_patch = rgb[c_ymin:c_ymax, c_xmin:c_xmax]
        patch_std = float(np.mean(np.std(chest_patch, axis=(0, 1))))

        if patch_std > 38.0:
            return GraphicPrintPlacementV2(
                detected=True,
                bbox=BoundingBox2D(ymin=0.28, xmin=0.32, ymax=0.52, xmax=0.68),
                target_region="chest",
                contrast_ratio=round(patch_std / 20.0, 2),
                aspect_ratio=1.2,
                confidence=0.86
            )

        return GraphicPrintPlacementV2(detected=False, confidence=0.15)

    def _detect_hardware(
        self,
        attributes: Dict[str, Any],
        category: str,
        subcategory: str
    ) -> List[HardwareElementV2]:
        """Infers structural hardware elements based on category construction attributes."""
        hardware: List[HardwareElementV2] = []

        if category == "shirt" or subcategory in ["shirt", "formal_shirt", "casual_shirt"]:
            hardware.append(HardwareElementV2(
                hardware_type="button",
                count=7,
                location="front_placket",
                metalness=0.10,
                roughness=0.40,
                confidence=0.95
            ))
        elif category == "hoodie" or subcategory in ["hoodie", "zip_hoodie"]:
            if attributes.get("drawstring_present", True):
                hardware.append(HardwareElementV2(
                    hardware_type="drawstring_aglet",
                    count=2,
                    location="collar",
                    metalness=0.85,
                    roughness=0.20,
                    confidence=0.92
                ))
            if subcategory == "zip_hoodie":
                hardware.append(HardwareElementV2(
                    hardware_type="zipper",
                    count=1,
                    location="front_placket",
                    metalness=0.88,
                    roughness=0.22,
                    confidence=0.94
                ))
        elif category == "jacket":
            closure = attributes.get("closure_type", "zipper")
            if closure == "zipper":
                hardware.append(HardwareElementV2(
                    hardware_type="zipper",
                    count=1,
                    location="front_placket",
                    metalness=0.90,
                    roughness=0.20,
                    confidence=0.95
                ))
            else:
                hardware.append(HardwareElementV2(
                    hardware_type="button",
                    count=4,
                    location="front_placket",
                    metalness=0.20,
                    roughness=0.35,
                    confidence=0.90
                ))
        elif category == "bottoms":
            fly = attributes.get("fly_type", "zipper")
            hardware.append(HardwareElementV2(
                hardware_type="button",
                count=1,
                location="waistband",
                metalness=0.92,
                roughness=0.18,
                confidence=0.96
            ))
            if fly == "zipper":
                hardware.append(HardwareElementV2(
                    hardware_type="zipper",
                    count=1,
                    location="front_fly",
                    metalness=0.85,
                    roughness=0.25,
                    confidence=0.92
                ))

        return hardware


# Global instance
learned_material_engine = LearnedMaterialEngine()

