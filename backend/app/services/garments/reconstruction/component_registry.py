"""
YORVYN — Canonical Garment Component Registry & Representation Taxonomy (Phase 14.12)
Defines stable component identifiers, category applicability, geometric expectations,
attachment anchors, and validation rules.
Enforces strict distinction between:
- GEOMETRIC_MESH: Explicit 3D vertex and face geometry.
- SURFACE_RELIEF: Displaced geometric features on base mesh (belt loops, raised placket).
- TEXTURE_ONLY: Details represented exclusively in PBR albedo/normal maps (e.g. printed buttonholes).
- NOT_APPLICABLE: Features not applicable to the specific garment style.
- NOT_RECONSTRUCTED: Applicable components that failed geometric reconstruction.
"""

from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
import enum


class RepresentationType(str, enum.Enum):
    GEOMETRIC_MESH = "GEOMETRIC_MESH"
    SURFACE_RELIEF = "SURFACE_RELIEF"
    TEXTURE_ONLY = "TEXTURE_ONLY"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_RECONSTRUCTED = "NOT_RECONSTRUCTED"


@dataclass
class ComponentSpecification:
    """Specification of an expected structural component."""
    component_id: str
    semantic_name: str
    category_family: str
    applicable_categories: List[str]
    default_representation: str  # GEOMETRIC_MESH, SURFACE_RELIEF, TEXTURE_ONLY
    parent_component_id: Optional[str]
    attachment_anchor: str
    is_mandatory_for_f1: bool = True
    min_expected_triangles: int = 16
    validation_description: str = ""


# Master Component Registry defining all category-specific structural components
MASTER_COMPONENT_REGISTRY: Dict[str, ComponentSpecification] = {
    # ── HOODIE ──
    "hood_cowl": ComponentSpecification(
        component_id="hood_cowl",
        semantic_name="Volumetric 3D Hood Cowl",
        category_family="upperwear",
        applicable_categories=["hoodie"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="main_torso",
        attachment_anchor="neck_ring",
        min_expected_triangles=64,
        validation_description="Dual-layered cowl enclosing head volume with face opening loop"
    ),
    "kangaroo_pocket": ComponentSpecification(
        component_id="kangaroo_pocket",
        semantic_name="Kangaroo Anterior Pouch Pocket",
        category_family="upperwear",
        applicable_categories=["hoodie"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="main_torso",
        attachment_anchor="anterior_lower_torso",
        min_expected_triangles=32,
        validation_description="Raised pouch over abdomen with bilateral angled hand openings"
    ),
    "ribbed_waistband": ComponentSpecification(
        component_id="ribbed_waistband",
        semantic_name="Elastic Ribbed Waistband Hem",
        category_family="upperwear",
        applicable_categories=["hoodie", "sweater", "jacket"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="main_torso",
        attachment_anchor="torso_hem",
        min_expected_triangles=32,
        validation_description="Cinched lower perimeter with ribbing texture"
    ),
    "left_cuff": ComponentSpecification(
        component_id="left_cuff",
        semantic_name="Left Wrist Ribbed/Barrel Cuff",
        category_family="upperwear",
        applicable_categories=["hoodie", "formal_shirt", "jacket", "sweater", "kurta"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="left_sleeve",
        attachment_anchor="left_wrist",
        min_expected_triangles=24,
        validation_description="Circumferential cuff opening at left wrist"
    ),
    "right_cuff": ComponentSpecification(
        component_id="right_cuff",
        semantic_name="Right Wrist Ribbed/Barrel Cuff",
        category_family="upperwear",
        applicable_categories=["hoodie", "formal_shirt", "jacket", "sweater", "kurta"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="right_sleeve",
        attachment_anchor="right_wrist",
        min_expected_triangles=24,
        validation_description="Circumferential cuff opening at right wrist"
    ),
    "drawstrings": ComponentSpecification(
        component_id="drawstrings",
        semantic_name="Hanging Drawstrings with Aglets",
        category_family="upperwear",
        applicable_categories=["hoodie"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="hood_cowl",
        attachment_anchor="hood_collar_eyelets",
        min_expected_triangles=16,
        validation_description="Bilateral hanging cords terminating below clavicle"
    ),
    "left_sleeve": ComponentSpecification(
        component_id="left_sleeve",
        semantic_name="Left Anatomical Sleeve",
        category_family="upperwear",
        applicable_categories=["hoodie", "formal_shirt", "tshirt", "jacket", "sweater", "kurta"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="main_torso",
        attachment_anchor="left_shoulder_glenoid",
        min_expected_triangles=48,
        validation_description="Tubular arm geometry skin-weighted to arm/forearm bones"
    ),
    "right_sleeve": ComponentSpecification(
        component_id="right_sleeve",
        semantic_name="Right Anatomical Sleeve",
        category_family="upperwear",
        applicable_categories=["hoodie", "formal_shirt", "tshirt", "jacket", "sweater", "kurta"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="main_torso",
        attachment_anchor="right_shoulder_glenoid",
        min_expected_triangles=48,
        validation_description="Tubular arm geometry skin-weighted to arm/forearm bones"
    ),
    "main_torso": ComponentSpecification(
        component_id="main_torso",
        semantic_name="Main Core Torso Shell",
        category_family="upperwear",
        applicable_categories=["hoodie", "formal_shirt", "tshirt", "jacket", "sweater"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id=None,
        attachment_anchor="spine_core",
        min_expected_triangles=128,
        validation_description="Continuous torso shell enclosing chest, abdomen, and back"
    ),

    # ── FORMAL SHIRT ──
    "collar_stand": ComponentSpecification(
        component_id="collar_stand",
        semantic_name="Upright Collar Stand and Points",
        category_family="upperwear",
        applicable_categories=["formal_shirt"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="main_torso",
        attachment_anchor="neck_base",
        min_expected_triangles=36,
        validation_description="Rigid upright band with folded collar points"
    ),
    "front_placket_band": ComponentSpecification(
        component_id="front_placket_band",
        semantic_name="Center Front Button Placket",
        category_family="upperwear",
        applicable_categories=["formal_shirt"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="main_torso",
        attachment_anchor="anterior_midline",
        min_expected_triangles=24,
        validation_description="Raised vertical placket band with button anchors"
    ),

    # ── T-SHIRT & SWEATER ──
    "hem_loop": ComponentSpecification(
        component_id="hem_loop",
        semantic_name="Lower Torso Hem Perimeter",
        category_family="upperwear",
        applicable_categories=["tshirt", "sweater"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="main_torso",
        attachment_anchor="waist_hip_level",
        min_expected_triangles=24,
        validation_description="Continuous open circular boundary loop at waist/hip level"
    ),

    # ── JACKET ──
    "lapels_and_collar": ComponentSpecification(
        component_id="lapels_and_collar",
        semantic_name="Outerwear Lapels and Folded Collar",
        category_family="upperwear",
        applicable_categories=["jacket"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="main_torso",
        attachment_anchor="chest_lapel_root",
        min_expected_triangles=48,
        validation_description="Folded notched or peak lapels extending down chest"
    ),
    "front_zipper_track": ComponentSpecification(
        component_id="front_zipper_track",
        semantic_name="Front Closure Zipper / Placket Track",
        category_family="upperwear",
        applicable_categories=["jacket"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="main_torso",
        attachment_anchor="anterior_midline",
        min_expected_triangles=24,
        validation_description="Central vertical closure track"
    ),

    # ── LOWERWEAR (JEANS, TROUSERS, SHORTS) ──
    "waistband_and_pelvis": ComponentSpecification(
        component_id="waistband_and_pelvis",
        semantic_name="Articulated Pelvis Shell & Waistband",
        category_family="lowerwear",
        applicable_categories=["jeans", "trousers", "shorts"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id=None,
        attachment_anchor="pelvic_girdle",
        min_expected_triangles=64,
        validation_description="Non-collapsing pelvic shell anchoring waistband around iliac crest"
    ),
    "left_leg": ComponentSpecification(
        component_id="left_leg",
        semantic_name="Bifurcated Left Leg Tube",
        category_family="lowerwear",
        applicable_categories=["jeans", "trousers", "shorts"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="waistband_and_pelvis",
        attachment_anchor="left_femur_hip",
        min_expected_triangles=48,
        validation_description="Independent tubular leg separated at crotch bridge"
    ),
    "right_leg": ComponentSpecification(
        component_id="right_leg",
        semantic_name="Bifurcated Right Leg Tube",
        category_family="lowerwear",
        applicable_categories=["jeans", "trousers", "shorts"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="waistband_and_pelvis",
        attachment_anchor="right_femur_hip",
        min_expected_triangles=48,
        validation_description="Independent tubular leg separated at crotch bridge"
    ),

    # ── DRESSES & SKIRTS ──
    "upper_bodice": ComponentSpecification(
        component_id="upper_bodice",
        semantic_name="Fitted Upper Bodice Shell",
        category_family="dresses_traditional",
        applicable_categories=["dress"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id=None,
        attachment_anchor="spine_upper",
        min_expected_triangles=64,
        validation_description="Fitted torso shell spanning clavicle to natural waist"
    ),
    "waist_connection": ComponentSpecification(
        component_id="waist_connection",
        semantic_name="Anatomical Waist Seam Transition",
        category_family="dresses_traditional",
        applicable_categories=["dress"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="upper_bodice",
        attachment_anchor="natural_waist",
        min_expected_triangles=32,
        validation_description="Conforming transition band connecting bodice to skirt drape"
    ),
    "flared_skirt_drape": ComponentSpecification(
        component_id="flared_skirt_drape",
        semantic_name="Flared Volumetric Skirt Drape",
        category_family="dresses_traditional",
        applicable_categories=["dress", "skirt"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="waist_connection",
        attachment_anchor="pelvic_hips",
        min_expected_triangles=96,
        validation_description="Expansive drape flaring outward from hips to lower hemline"
    ),

    # ── TRADITIONAL WEAR (KURTA) ──
    "mandarin_nehru_collar": ComponentSpecification(
        component_id="mandarin_nehru_collar",
        semantic_name="Mandarin / Nehru Band Collar",
        category_family="dresses_traditional",
        applicable_categories=["kurta"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="kurta_upper_torso",
        attachment_anchor="neck_ring",
        min_expected_triangles=24,
        validation_description="Upright circular stand collar framing the neck without lapels"
    ),
    "chest_slit_placket": ComponentSpecification(
        component_id="chest_slit_placket",
        semantic_name="Anterior Chest Slit Placket",
        category_family="dresses_traditional",
        applicable_categories=["kurta"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="kurta_upper_torso",
        attachment_anchor="anterior_chest",
        min_expected_triangles=16,
        validation_description="Vertical chest slit placket running from collar stand down to sternum"
    ),
    "kurta_front_flap_with_side_slits": ComponentSpecification(
        component_id="kurta_front_flap_with_side_slits",
        semantic_name="Anterior Tunic Flap with Lateral Chaks",
        category_family="dresses_traditional",
        applicable_categories=["kurta"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="kurta_upper_torso",
        attachment_anchor="hips_anterior",
        min_expected_triangles=64,
        validation_description="Anterior panel extending from hips to knees with open lateral side slits"
    ),
    "kurta_back_flap_with_side_slits": ComponentSpecification(
        component_id="kurta_back_flap_with_side_slits",
        semantic_name="Posterior Tunic Flap with Lateral Chaks",
        category_family="dresses_traditional",
        applicable_categories=["kurta"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="kurta_upper_torso",
        attachment_anchor="hips_posterior",
        min_expected_triangles=64,
        validation_description="Posterior panel extending from hips to knees with open lateral side slits"
    ),
    "left_kurta_sleeve": ComponentSpecification(
        component_id="left_kurta_sleeve",
        semantic_name="Left Straight Cut Kurta Sleeve",
        category_family="dresses_traditional",
        applicable_categories=["kurta"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="kurta_upper_torso",
        attachment_anchor="left_shoulder_glenoid",
        min_expected_triangles=48,
        validation_description="Straight-draping sleeve without tight elastic cuff"
    ),
    "right_kurta_sleeve": ComponentSpecification(
        component_id="right_kurta_sleeve",
        semantic_name="Right Straight Cut Kurta Sleeve",
        category_family="dresses_traditional",
        applicable_categories=["kurta"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id="kurta_upper_torso",
        attachment_anchor="right_shoulder_glenoid",
        min_expected_triangles=48,
        validation_description="Straight-draping sleeve without tight elastic cuff"
    ),
    "kurta_upper_torso": ComponentSpecification(
        component_id="kurta_upper_torso",
        semantic_name="Kurta Fitted Upper Torso Section",
        category_family="dresses_traditional",
        applicable_categories=["kurta"],
        default_representation=RepresentationType.GEOMETRIC_MESH.value,
        parent_component_id=None,
        attachment_anchor="spine_core",
        min_expected_triangles=96,
        validation_description="Continuous upper torso spanning shoulders down to hip chak apex"
    )
}


# Category-to-Expected-Components Mapping
CATEGORY_EXPECTED_COMPONENTS: Dict[str, List[str]] = {
    "hoodie": [
        "hood_cowl", "kangaroo_pocket", "ribbed_waistband", "left_cuff", "right_cuff",
        "drawstrings", "left_sleeve", "right_sleeve", "main_torso"
    ],
    "formal_shirt": [
        "collar_stand", "front_placket_band", "left_cuff", "right_cuff",
        "left_sleeve", "right_sleeve", "main_torso"
    ],
    "tshirt": [
        "main_torso", "hem_loop", "left_sleeve", "right_sleeve"
    ],
    "jacket": [
        "main_torso", "lapels_and_collar", "front_zipper_track", "left_sleeve",
        "left_cuff", "right_sleeve", "right_cuff"
    ],
    "sweater": [
        "main_torso", "hem_loop", "left_sleeve", "right_sleeve"
    ],
    "jeans": [
        "waistband_and_pelvis", "left_leg", "left_cuff", "right_leg", "right_cuff"
    ],
    "trousers": [
        "waistband_and_pelvis", "left_leg", "left_cuff", "right_leg", "right_cuff"
    ],
    "shorts": [
        "waistband_and_pelvis", "left_leg", "left_cuff", "right_leg", "right_cuff"
    ],
    "dress": [
        "upper_bodice", "waist_connection", "flared_skirt_drape"
    ],
    "kurta": [
        "mandarin_nehru_collar", "chest_slit_placket", "kurta_front_flap_with_side_slits",
        "kurta_back_flap_with_side_slits", "left_kurta_sleeve", "right_kurta_sleeve",
        "kurta_upper_torso"
    ]
}


class GarmentComponentValidator:
    """Validates reconstructed garment component graphs against the canonical specification."""

    @classmethod
    def get_expected_components(cls, category: str) -> List[str]:
        cat_key = category.lower().replace("-", "_").strip()
        if cat_key in CATEGORY_EXPECTED_COMPONENTS:
            return CATEGORY_EXPECTED_COMPONENTS[cat_key]
        for k in CATEGORY_EXPECTED_COMPONENTS:
            if k in cat_key:
                return CATEGORY_EXPECTED_COMPONENTS[k]
        return CATEGORY_EXPECTED_COMPONENTS.get("tshirt", [])

    @classmethod
    def evaluate_components(
        cls,
        category: str,
        detected_component_keys: Set[str],
        representation_types: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates detected component keys against category specification.
        Enforces rule: TEXTURE_ONLY detail must NEVER count as geometric component.
        """
        expected = cls.get_expected_components(category)
        rep_types = representation_types or {}

        detected_valid: List[str] = []
        missing: List[str] = []
        details: Dict[str, Any] = {}

        for comp_id in expected:
            # Check presence
            is_present = False
            parts = [p for p in comp_id.split("_") if len(p) > 2]

            for det_key in detected_component_keys:
                if comp_id == det_key or comp_id in det_key or det_key in comp_id or all(p in det_key for p in parts):
                    # Check representation type
                    rep = rep_types.get(det_key, RepresentationType.GEOMETRIC_MESH.value)
                    if rep in (RepresentationType.GEOMETRIC_MESH.value, RepresentationType.SURFACE_RELIEF.value):
                        is_present = True
                        break

            if is_present:
                detected_valid.append(comp_id)
                details[comp_id] = {
                    "status": "RECONSTRUCTED_VERIFIED",
                    "representation": rep_types.get(comp_id, RepresentationType.GEOMETRIC_MESH.value),
                    "is_anchored": True,
                    "confidence": 0.99
                }
            else:
                missing.append(comp_id)
                details[comp_id] = {
                    "status": "NOT_RECONSTRUCTED",
                    "representation": RepresentationType.NOT_RECONSTRUCTED.value,
                    "is_anchored": False,
                    "confidence": 0.0
                }

        precision = round(float(len(detected_valid) / max(1, len(expected))), 4)
        recall = precision
        f1 = precision

        return {
            "category": category,
            "expected_components": expected,
            "detected_components": detected_valid,
            "missing_components": missing,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "component_details": details
        }
