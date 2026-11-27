"""
YORVYN — Local garment perception pipeline
Combines cached generic CLIP prompt scoring with color, contour, component-region,
and relative-disparity heuristics. Provenance identifies the stages that actually run.
"""

import time
import math
import uuid
import logging
from typing import Dict, Any, List, Tuple, Optional
from PIL import Image
import numpy as np
import cv2
import torch

from backend.app.models.structured_garment_specification import (
    GarmentCategory,
    ComponentLocation,
    GarmentVisualAttributes,
    UncertaintyAnalysis,
    IdentificationModelProvenance,
    ReconstructionHandoffSpec,
    StructuredGarmentSpecification
)
from backend.app.services.garments.intelligence.sequential_model_manager import model_manager
from backend.app.services.garments.intelligence.fashion_clip_adapter import FashionCLIPAdapter
from backend.app.services.garments.intelligence.siglip_adapter import SigLIPAdapter
from backend.app.services.garments.intelligence.grounded_sam2_adapter import GroundedSAM2Adapter
from backend.app.services.garments.reconstruction.neural.depth_anything_adapter import DepthAnythingV2Adapter
from backend.app.services.ml.dinov2_feature_extractor import Dinov2FeatureExtractor

logger = logging.getLogger(__name__)


import threading


class LocalMultimodalIdentificationEngine:
    """
    Consolidated zero-cost local multimodal engine for garment identification,
    component localization, visual attribute extraction, and 3D reconstruction handoff.
    """

    def __init__(self, device: Optional[str] = None):
        self._inference_lock = threading.Lock()
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.model_manager = model_manager
        logger.info(f"LocalMultimodalIdentificationEngine initialized on {self.device}")

    def _extract_color_palette(self, image: Image.Image, k: int = 5) -> Tuple[str, Optional[str], List[str]]:
        """Extracts dominant colors and palette hexes from garment image foreground."""
        img_np = np.array(image.convert("RGB"))
        h, w = img_np.shape[:2]

        # Basic center-weighted foreground extraction
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        bg_val = float(np.mean(gray[:10, :10]))
        thresh_type = cv2.THRESH_BINARY_INV if bg_val > 180 else cv2.THRESH_BINARY
        _, mask = cv2.threshold(gray, 0, 255, thresh_type + cv2.THRESH_OTSU)

        fg_pixels = img_np[mask > 20]
        if len(fg_pixels) < 100:
            fg_pixels = img_np.reshape(-1, 3)

        # Subsample for fast k-means
        step = max(1, len(fg_pixels) // 2000)
        samples = fg_pixels[::step].astype(np.float32)

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(samples, min(k, len(samples)), None, criteria, 5, cv2.KMEANS_PP_CENTERS)

        counts = np.bincount(labels.flatten())
        sorted_indices = np.argsort(counts)[::-1]

        palette_hex = []
        for idx in sorted_indices:
            c = centers[idx].astype(int)
            palette_hex.append(f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}")

        def hex_to_name(hex_code: str) -> str:
            r, g, b = int(hex_code[1:3], 16), int(hex_code[3:5], 16), int(hex_code[5:7], 16)
            if r < 40 and g < 40 and b < 40:
                return "black"
            if r > 215 and g > 215 and b > 215:
                return "white"
            if abs(r - g) < 20 and abs(r - b) < 20 and abs(g - b) < 20:
                return "grey" if r < 160 else "light_grey"
            if r > g + 40 and r > b + 40:
                return "red" if r > 150 else "maroon"
            if b > r + 30 and b > g + 30:
                return "navy_blue" if b < 140 else "royal_blue"
            if g > r + 20 and g > b + 20:
                return "olive_green" if g < 130 else "green"
            if r > 160 and g > 130 and b < 90:
                return "mustard_yellow"
            if r > 100 and g > 70 and b < 50:
                return "brown"
            return "indigo" if b > 100 else "charcoal"

        primary_name = hex_to_name(palette_hex[0])
        secondary_name = hex_to_name(palette_hex[1]) if len(palette_hex) > 1 else None
        return primary_name, secondary_name, palette_hex

    def _generate_explanation(
        self,
        category: GarmentCategory,
        subcategory: str,
        attributes: GarmentVisualAttributes,
        components: List[ComponentLocation],
        confidence: float
    ) -> str:
        """Generates clear, deterministic natural language explanation of garment properties."""
        comp_names = [c.name.replace("_", " ") for c in components]
        pocket_desc = f"with {', '.join(attributes.pockets).replace('_', ' ')}" if attributes.pockets else "without prominent exterior pockets"
        sleeve_desc = attributes.sleeve_type.replace('_', ' ')
        closure_desc = f"{attributes.closure.replace('_', ' ')} closure"

        explanation = (
            f"Identified as a {subcategory.replace('_', ' ')} ({category.value.capitalize()}) "
            f"with {confidence * 100:.1f}% confidence. Features a {attributes.pattern} pattern in {attributes.primary_color}, "
            f"constructed with {sleeve_desc}, {attributes.neckline.replace('_', ' ')}, and {closure_desc}. "
            f"Equipped {pocket_desc}. Localized {len(components)} distinct architectural components: {', '.join(comp_names)}."
        )
        return explanation

    def identify_garment(
        self,
        image: Image.Image,
        garment_id: Optional[str] = None
    ) -> StructuredGarmentSpecification:
        with self._inference_lock:
            return self._identify_locked(image, garment_id)

    def _identify_locked(
        self,
        image: Image.Image,
        garment_id: Optional[str] = None
    ) -> StructuredGarmentSpecification:
        """
        Executes sequential, zero-cost multimodal garment identification.
        """
        gid = garment_id or f"garment_{uuid.uuid4().hex[:8]}"
        t_start = time.perf_counter()
        img_np = np.array(image.convert("RGB"))
        gh, gw = img_np.shape[:2]

        # Step 1: Preprocessing & Color Analysis
        with self.model_manager.run_step("color_and_silhouette"):
            primary_color, secondary_color, palette_hex = self._extract_color_palette(image)

        # Step 2: FashionCLIP Category & Subcategory Identification
        with self.model_manager.run_step("fashion_clip"):
            fclip: FashionCLIPAdapter = self.model_manager.register_or_get(
                "fashion_clip",
                lambda dev: FashionCLIPAdapter(device=dev),
                device=self.device
            )
            clip_res = fclip.classify_garment(image)
            cat: GarmentCategory = clip_res["category"]
            subcat: str = clip_res["subcategory"]
            cat_conf: float = clip_res["category_confidence"]
            margin: float = clip_res["margin"]
            entropy: float = clip_res["entropy"]

        # Step 3: SigLIP Multi-Attribute Extraction
        with self.model_manager.run_step("siglip_attributes"):
            siglip: SigLIPAdapter = self.model_manager.register_or_get(
                "siglip",
                lambda dev: SigLIPAdapter(device=dev),
                device=self.device
            )
            sig_res = siglip.extract_attributes(image)

        # Step 4: DINOv2 Feature Representation
        with self.model_manager.run_step("dinov2_features"):
            dinov2: Dinov2FeatureExtractor = self.model_manager.register_or_get(
                "dinov2",
                lambda dev: Dinov2FeatureExtractor(device=dev),
                device=self.device
            )
            dinov2_res = dinov2.extract_features(image)
            dinov2_feats = dinov2_res["cls_embedding"]
            # Measure feature normality / magnitude
            feat_norm = float(np.linalg.norm(dinov2_feats))

        # Step 5: Grounded-SAM 2 Component Localization
        with self.model_manager.run_step("grounded_sam2_components"):
            gsam2: GroundedSAM2Adapter = self.model_manager.register_or_get(
                "grounded_sam2",
                lambda dev: GroundedSAM2Adapter(device=dev),
                device=self.device
            )
            det_res = gsam2.detect_and_segment(image, category=cat.value, subcategory=subcat)
            detected_components_raw = det_res.get("components", {})

            components: List[ComponentLocation] = []
            for comp_name, comp_obj in detected_components_raw.items():
                components.append(ComponentLocation(
                    name=comp_obj.label,
                    bbox=comp_obj.bbox,
                    confidence=comp_obj.confidence,
                    area_fraction=0.15,
                    source_model=comp_obj.source_model,
                    prompt_used=comp_obj.prompt_used
                ))

        # Step 6: Depth Anything V2 Disparity Analysis
        with self.model_manager.run_step("depth_anything_v2"):
            depth_adapter: DepthAnythingV2Adapter = self.model_manager.register_or_get(
                "depth_anything_v2",
                lambda dev: DepthAnythingV2Adapter(device=dev),
                device=self.device
            )
            depth_out = depth_adapter.estimate_depth(image)
            depth_map = depth_out.relative_depth
            depth_stats = {
                "mean_disparity": float(np.mean(depth_map)),
                "std_disparity": float(np.std(depth_map)),
                "min_disparity": float(np.min(depth_map)),
                "max_disparity": float(np.max(depth_map)),
                "fold_roughness": float(np.mean(depth_out.fold_relief_map))
            }

        # Step 7: Multi-Model Consensus & Uncertainty Quantification
        # Geometric analysis of silhouette
        aspect_ratio = gh / float(max(1, gw))

        has_hood_component = any("hood" in c.name for c in components)
        has_pocket_component = any("pocket" in c.name for c in components)
        has_zipper_component = any("zipper" in c.name for c in components)
        has_trouser_legs = any("leg" in c.name for c in components) or any("crotch" in c.name for c in components)

        # Cross-validation / Consensus refinement
        disagreement_flag = False

        # Consensus Rule 1: Bottoms detection
        if has_trouser_legs:
            if "denim" in sig_res["fabric_texture"] or "blue" in primary_color or "indigo" in primary_color:
                if cat not in [GarmentCategory.JEANS, GarmentCategory.TROUSERS, GarmentCategory.SHORTS]:
                    cat = GarmentCategory.JEANS
                    subcat = "classic_denim_jeans"
                    cat_conf = 0.89
            elif cat not in [GarmentCategory.TROUSERS, GarmentCategory.JEANS, GarmentCategory.SHORTS]:
                cat = GarmentCategory.TROUSERS
                subcat = "chino_trousers"
                cat_conf = 0.85

        # Consensus Rule 2: Hoodie confirmation
        elif has_hood_component:
            if cat != GarmentCategory.HOODIE:
                cat = GarmentCategory.HOODIE
                subcat = "zip_hoodie" if has_zipper_component else "pullover_hoodie"
                cat_conf = 0.91

        # Consensus Rule 3: Dress vs Skirt vs Long top
        elif cat == GarmentCategory.SKIRT and aspect_ratio > 1.3 and "bodice" in [c.name for c in components]:
            cat = GarmentCategory.DRESS
            subcat = "aline_dress"
            cat_conf = 0.82

        # Low contrast & Occlusion flags
        img_np = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        contrast = float(np.std(gray))
        low_contrast_flag = contrast < 25.0
        occlusion_flag = False  # Full bounding silhouette assumed

        verdict = "HIGH_CONFIDENCE"
        if disagreement_flag or margin < 0.10:
            verdict = "REQUIRES_REVIEW"
        elif low_contrast_flag or cat_conf < 0.70:
            verdict = "MODERATE_CONFIDENCE"

        uncertainty = UncertaintyAnalysis(
            entropy=float(entropy),
            top1_top2_margin=float(margin),
            low_contrast_flag=low_contrast_flag,
            occlusion_flag=occlusion_flag,
            model_disagreement_flag=disagreement_flag,
            confidence_score=float(cat_conf),
            verdict=verdict
        )

        # Visual attributes synthesis
        attributes = GarmentVisualAttributes(
            primary_color=primary_color,
            secondary_color=secondary_color,
            palette_hex=palette_hex,
            pattern=sig_res["pattern"],
            pattern_confidence=sig_res["pattern_confidence"],
            fit=sig_res["fit"],
            sleeve_type=sig_res["sleeve_type"],
            neckline=sig_res["neckline"],
            collar="folded_collar" if "collar" in sig_res["neckline"] else None,
            closure=sig_res["closure"],
            pockets=sig_res["detected_pockets"],
            cuffs="ribbed_cuffs" if cat in [GarmentCategory.HOODIE, GarmentCategory.SWEATSHIRT, GarmentCategory.SWEATER] else "straight_cuffs",
            hem="ribbed_waistband" if cat in [GarmentCategory.HOODIE, GarmentCategory.SWEATSHIRT] else "straight_hem",
            hood="cowl_hood" if cat == GarmentCategory.HOODIE or has_hood_component else None,
            fabric_texture=sig_res["fabric_texture"]
        )

        # Step 8: Reconstruction DAG Mapping
        dag_mapping = {
            GarmentCategory.HOODIE: "hoodie_construction",
            GarmentCategory.TSHIRT: "tshirt_construction",
            GarmentCategory.SHIRT: "shirt_construction",
            GarmentCategory.JACKET: "jacket_construction",
            GarmentCategory.SWEATSHIRT: "sweatshirt_construction",
            GarmentCategory.SWEATER: "sweater_construction",
            GarmentCategory.JEANS: "jeans_construction",
            GarmentCategory.TROUSERS: "trousers_construction",
            GarmentCategory.SHORTS: "shorts_construction",
            GarmentCategory.SKIRT: "skirt_construction",
            GarmentCategory.DRESS: "dress_construction",
            GarmentCategory.KURTA: "kurta_construction",
            GarmentCategory.TUNIC: "tunic_construction",
            GarmentCategory.COAT: "coat_construction",
            GarmentCategory.TRADITIONAL_CLOTHING: "traditional_clothing_construction"
        }

        reconstruction_handoff = ReconstructionHandoffSpec(
            target_dag_template=dag_mapping.get(cat, "hoodie_construction"),
            sleeve_length_scale=0.35 if attributes.sleeve_type == "short_sleeve" else (0.0 if attributes.sleeve_type == "sleeveless" else 1.0),
            collar_height_scale=1.4 if attributes.collar else 1.0,
            enable_hood_mesh=(cat == GarmentCategory.HOODIE or has_hood_component),
            enable_pocket_mesh=(len(attributes.pockets) > 0 or has_pocket_component),
            pocket_type="kangaroo_pocket" if (cat == GarmentCategory.HOODIE and "pullover" in subcat) else (attributes.pockets[0] if attributes.pockets else None),
            closure_geometry="zipper" if "zipper" in attributes.closure else ("buttons" if "button" in attributes.closure else "none"),
            curved_hem=(cat == GarmentCategory.SHIRT),
            torso_fit_offset_cm=2.5 if attributes.fit == "oversized" else (1.2 if attributes.fit == "slim" else 1.8),
            material_preset=f"{attributes.fabric_texture}_pbr"
        )

        total_latency_ms = (time.perf_counter() - t_start) * 1000.0

        provenance = IdentificationModelProvenance(
            fashion_clip_model=fclip.model_name,
            fashion_clip_device=str(fclip.device),
            siglip_model=siglip.model_name,
            siglip_device=str(siglip.device),
            dinov2_model=dinov2.model_name,
            dinov2_device=str(dinov2.device),
            grounded_sam2_model=det_res.get("model_name", gsam2.model_version),
            grounded_sam2_device=str(gsam2.device),
            depth_model=depth_adapter.model_name,
            depth_device=str(depth_adapter.device),
            total_latency_ms=total_latency_ms,
            peak_memory_mb=self.model_manager.peak_memory_mb,
            fallback_triggered=self.model_manager.fallback_occurred,
            # Local execution avoids paid APIs, but this field represents an
            # audited system claim and is therefore false until independently checked.
            zero_cost_local_verified=False,
            model_execution_details={
                "category_classifier": {
                    "model": clip_res.get("model"),
                    "backend": clip_res.get("execution_backend"),
                    "weights_loaded": clip_res.get("weights_loaded", False),
                    "confidence_calibrated": clip_res.get("confidence_calibrated", False)
                },
                "attribute_classifier": {
                    "model": sig_res.get("model"),
                    "backend": sig_res.get("execution_backend"),
                    "weights_loaded": sig_res.get("weights_loaded", False),
                    "scores_calibrated": sig_res.get("scores_calibrated", False)
                },
                "visual_embeddings": {
                    "model": dinov2_res.get("model"),
                    "backend": dinov2_res.get("execution_backend"),
                    "weights_loaded": dinov2_res.get("pretrained_weights_loaded", False),
                    "semantic_valid": dinov2_res.get("semantic_valid", False)
                },
                "component_regions": {
                    "model": det_res.get("model_name", gsam2.model_version),
                    "backend": det_res.get("execution_provenance"),
                    "weights_loaded": det_res.get("weights_loaded", False)
                },
                "relative_disparity": {
                    "model": depth_adapter.model_name,
                    "backend": "analytic_relative_disparity",
                    "weights_loaded": False,
                    "metric_calibrated": False
                }
            }
        )

        explanation = self._generate_explanation(cat, subcat, attributes, components, cat_conf)

        return StructuredGarmentSpecification(
            garment_id=gid,
            category=cat,
            subcategory=subcat,
            confidence=float(cat_conf),
            attributes=attributes,
            components=components,
            relative_depth_stats=depth_stats,
            uncertainty=uncertainty,
            provenance=provenance,
            reconstruction_handoff=reconstruction_handoff,
            natural_language_explanation=explanation
        )


# Singleton instance
multimodal_engine = LocalMultimodalIdentificationEngine()
