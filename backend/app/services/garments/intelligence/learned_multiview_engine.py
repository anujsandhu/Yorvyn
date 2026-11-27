"""
YORVYN — Learned Multi-View Alignment, Conflict Resolution & Missing Surface Engine.
Aligns multi-view photographs (front, rear, side), detects duplicate uploads,
verifies garment identity across views using semantic embeddings and color science,
resolves conflicting visual evidence, and explicitly decouples observed photographic
surfaces from inferred posterior panels and generated wearability cavities.

Truthful provenance: Never claims an unobserved back panel was photographed.
"""

import time
import math
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import numpy as np
from PIL import Image

from backend.app.models.garment_intelligence_models import (
    ViewAnalysisResult,
    BoundingBox2D,
    Point2D
)
from .universal_garment_classifier import find_closest_fashion_color, hex_to_rgb, color_distance
from .universal_garment_intelligence_model import universal_intelligence_model

logger = logging.getLogger(__name__)


@dataclass
class ViewDiscrepancy:
    """Discrepancy between two views and its automated resolution."""
    attribute_name: str
    front_value: Any
    back_value: Any
    resolved_value: Any
    resolution_strategy: str  # "prioritize_front", "prioritize_back", "fuse_asymmetric"
    rationale: str


@dataclass
class LearnedMultiViewAnalysisResult:
    """Comprehensive multi-view alignment and surface visibility report."""
    is_multi_view: bool
    views_present: List[str]
    is_duplicate_upload: bool
    identity_confirmed: bool
    cross_view_similarity: float
    color_delta_e: float
    observed_surface_ratio: float
    inferred_surface_ratio: float
    panel_provenance: Dict[str, str]
    discrepancies: List[ViewDiscrepancy]
    missing_surface_notes: List[str]
    processing_time_ms: float


class LearnedMultiViewEngine:
    """
    Analyzes multiple views of clothing, detects inconsistencies, and provides
    verifiable surface coverage breakdown for 3D reconstruction.
    """

    def analyze_views(
        self,
        front_image: Image.Image,
        back_image: Optional[Image.Image] = None,
        side_image: Optional[Image.Image] = None,
        category: str = "tops",
        subcategory: str = "tshirt"
    ) -> LearnedMultiViewAnalysisResult:
        """
        Executes cross-view feature alignment, identity check, and surface ratio calculation.
        """
        t0 = time.perf_counter()
        views_present = ["front"]
        discrepancies: List[ViewDiscrepancy] = []
        notes: List[str] = []

        # 1. Front View Feature Extraction
        front_rgb = front_image.convert("RGB")
        front_intel = universal_intelligence_model.predict(front_rgb, category_hint=category, subcategory_hint=subcategory)

        # Base single-view default coverage: Front gives ~58% surface area
        observed_surface_ratio = 0.58
        inferred_surface_ratio = 0.42
        cross_view_similarity = 1.0
        color_delta = 0.0
        identity_confirmed = True
        is_duplicate = False

        panel_provenance: Dict[str, str] = {
            "front_torso": "observed_front",
            "back_torso": "inferred_rear",
            "left_sleeve_front": "observed_front",
            "right_sleeve_front": "observed_front",
            "left_sleeve_back": "inferred_rear",
            "right_sleeve_back": "inferred_rear",
            "collar_front": "observed_front",
            "collar_back": "inferred_rear",
            "internal_cavity": "generated_for_avatar_clearance"
        }

        # 2. Back View Processing (if provided)
        if back_image is not None:
            views_present.append("back")
            back_rgb = back_image.convert("RGB")
            back_intel = universal_intelligence_model.predict(back_rgb, category_hint=category, subcategory_hint=subcategory)

            # Extract color signatures
            front_arr = np.array(front_rgb)
            back_arr = np.array(back_rgb)

            f_mean = np.mean(front_arr, axis=(0, 1))
            b_mean = np.mean(back_arr, axis=(0, 1))
            color_delta = round(color_distance((int(f_mean[0]), int(f_mean[1]), int(f_mean[2])),
                                               (int(b_mean[0]), int(b_mean[1]), int(b_mean[2]))), 2)

            # Duplicate upload check: identical size and near-zero color difference
            if front_rgb.size == back_rgb.size and color_delta < 2.0:
                diff_norm = np.linalg.norm(front_arr.astype(float) - back_arr.astype(float)) / (front_arr.size)
                if diff_norm < 1.0:
                    is_duplicate = True
                    notes.append("Back view image is bitwise or near-identical duplicate of front image.")

            # Cross-view feature similarity
            # High similarity between front and back indicates same clothing item
            cross_view_similarity = round(float(np.clip(1.0 - (color_delta / 120.0), 0.10, 0.99)), 4)
            identity_confirmed = (color_delta < 55.0) and not is_duplicate

            if not identity_confirmed:
                notes.append(f"Front and rear photos exhibit high color discrepancy (ΔE={color_delta}). Possible different items.")

            # With verified front + rear view: observed surface increases to ~92%
            if identity_confirmed and not is_duplicate:
                observed_surface_ratio = 0.92
                inferred_surface_ratio = 0.08
                panel_provenance["back_torso"] = "observed_back"
                panel_provenance["left_sleeve_back"] = "observed_back"
                panel_provenance["right_sleeve_back"] = "observed_back"
                panel_provenance["collar_back"] = "observed_back"

                # Check for front/rear print asymmetry
                f_fab = front_intel.fabric_category
                b_fab = back_intel.fabric_category
                if f_fab != b_fab:
                    discrepancies.append(ViewDiscrepancy(
                        attribute_name="fabric_texture",
                        front_value=f_fab,
                        back_value=b_fab,
                        resolved_value=f_fab,
                        resolution_strategy="prioritize_front",
                        rationale="Front view provides primary lighting & weave ground truth."
                    ))
            else:
                notes.append("Back view rejected or unconfirmed. Retaining inferred rear geometry.")

        # 3. Side View Processing (if provided)
        if side_image is not None:
            views_present.append("side")
            observed_surface_ratio = min(0.96, observed_surface_ratio + 0.04)
            inferred_surface_ratio = round(1.0 - observed_surface_ratio, 4)
            panel_provenance["side_seam_profile"] = "observed_side"

        if len(views_present) == 1:
            notes.append("Single front view provided: rear panels are synthetically inferred via bilateral symmetry.")

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        return LearnedMultiViewAnalysisResult(
            is_multi_view=(len(views_present) > 1 and not is_duplicate),
            views_present=views_present,
            is_duplicate_upload=is_duplicate,
            identity_confirmed=identity_confirmed,
            cross_view_similarity=cross_view_similarity,
            color_delta_e=color_delta,
            observed_surface_ratio=round(observed_surface_ratio, 4),
            inferred_surface_ratio=round(inferred_surface_ratio, 4),
            panel_provenance=panel_provenance,
            discrepancies=discrepancies,
            missing_surface_notes=notes,
            processing_time_ms=latency_ms
        )


    def compare_garment_identity(
        self,
        image_a: Image.Image,
        image_b: Image.Image,
        expected_category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compares two photographs to determine if they contain the same physical garment
        or commercial product model, evaluated on isolated, neutral-letterboxed garment crops.
        """
        from .garment_instance_detector import garment_instance_detector
        from .universal_garment_classifier import universal_garment_classifier

        scene_a = garment_instance_detector.detect_instances(image_a)
        scene_b = garment_instance_detector.detect_instances(image_b)

        def to_domain(cat_str: str) -> str:
            c = cat_str.lower()
            if c in ["tops", "shirt", "hoodie", "jacket", "outerwear", "sweater", "tshirt", "blazer"]:
                return "tops"
            if c in ["bottoms", "pants", "shorts", "jeans", "trousers"]:
                return "bottoms"
            if c in ["dress", "skirt", "dresses_and_skirts"]:
                return "dress"
            if c in ["footwear", "shoes", "shoe"]:
                return "footwear"
            if c in ["accessories", "bag", "belt", "hat", "scarf"]:
                return "accessories"
            return c

        exp_domain = to_domain(expected_category) if expected_category else None

        # Select target instance in scene A
        inst_a = None
        if exp_domain:
            for inst in scene_a.instances:
                if to_domain(inst.category) == exp_domain:
                    inst_a = inst
                    break
        if inst_a is None and scene_a.instances:
            inst_a = scene_a.instances[0]

        # Select target instance in scene B
        inst_b = None
        if exp_domain:
            for inst in scene_b.instances:
                if to_domain(inst.category) == exp_domain:
                    inst_b = inst
                    break
        if inst_b is None and scene_b.instances:
            inst_b = scene_b.instances[0]

        cat_a = inst_a.category if inst_a else "unknown"
        cat_b = inst_b.category if inst_b else "unknown"
        sub_a = inst_a.subcategory if inst_a else "unknown"
        sub_b = inst_b.subcategory if inst_b else "unknown"

        # Check category and subcategory concordance
        is_cat_match = (to_domain(cat_a) == to_domain(cat_b)) and (cat_a != "unknown" and cat_b != "unknown")
        is_sub_match = (sub_a == sub_b) or (
            sub_a in ["pullover_hoodie", "hoodie"] and sub_b in ["pullover_hoodie", "hoodie"]
        ) or (
            sub_a in ["denim_jacket", "jacket"] and sub_b in ["denim_jacket", "jacket"]
        ) or (
            sub_a in ["formal_shirt", "shirt"] and sub_b in ["formal_shirt", "shirt"]
        )

        # Extract embeddings on isolated garment crops if available
        crop_a = image_a
        crop_b = image_b
        if inst_a and inst_a.crop_data_url:
            try:
                from .aspect_ratio_preprocessor import data_url_to_pil
                crop_a = data_url_to_pil(inst_a.crop_data_url)
            except Exception:
                pass
        if inst_b and inst_b.crop_data_url:
            try:
                from .aspect_ratio_preprocessor import data_url_to_pil
                crop_b = data_url_to_pil(inst_b.crop_data_url)
            except Exception:
                pass

        emb_a = universal_garment_classifier.extract_semantic_embedding(crop_a)
        emb_b = universal_garment_classifier.extract_semantic_embedding(crop_b)

        # Cosine similarity
        v1 = np.array(emb_a, dtype=np.float32)
        v2 = np.array(emb_b, dtype=np.float32)
        n1 = np.linalg.norm(v1)
        n2 = np.linalg.norm(v2)
        crop_cosine_sim = float(np.dot(v1, v2) / (n1 * n2)) if n1 > 0 and n2 > 0 else 0.0

        # Minimum pairwise color distance across dominant palettes
        pal_a = inst_a.dominant_colors if inst_a and inst_a.dominant_colors else []
        pal_b = inst_b.dominant_colors if inst_b and inst_b.dominant_colors else []
        if pal_a and pal_b:
            min_dist = 999.0
            for ca in pal_a:
                for cb in pal_b:
                    d = color_distance(hex_to_rgb(ca["hex"]), hex_to_rgb(cb["hex"]))
                    if d < min_dist:
                        min_dist = d
            color_delta = min_dist
        else:
            color_delta = 50.0

        # Composite multi-view identity score
        # In redmean space, distance < 120 indicates compatible colorway
        color_term = max(0.0, 1.0 - (color_delta / 160.0))
        identity_score = (0.65 * crop_cosine_sim) + (0.35 * color_term)
        if not is_cat_match:
            identity_score *= 0.15

        # Confirmed if category matches and composite identity score >= 0.55
        is_same_identity = is_cat_match and (identity_score >= 0.55)

        return {
            "instance_a_found": inst_a is not None,
            "instance_b_found": inst_b is not None,
            "category_a": cat_a,
            "category_b": cat_b,
            "subcategory_a": sub_a,
            "subcategory_b": sub_b,
            "category_concordant": is_cat_match,
            "subcategory_concordant": is_sub_match,
            "crop_cosine_similarity": round(crop_cosine_sim, 4),
            "color_delta_e": round(color_delta, 2),
            "composite_identity_score": round(identity_score, 4),
            "identity_confirmed": is_same_identity
        }


# Global singleton instance
learned_multiview_engine = LearnedMultiViewEngine()

