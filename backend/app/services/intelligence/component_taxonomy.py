"""Versioned garment component taxonomy and category-specific evidence profiles (Phase 16.1)."""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field


TAXONOMY_VERSION = "16.1.0"


class VisibilityState(str, Enum):
    FULLY_VISIBLE = "FULLY_VISIBLE"
    PARTIALLY_VISIBLE = "PARTIALLY_VISIBLE"
    OCCLUDED = "OCCLUDED"
    OUT_OF_FRAME = "OUT_OF_FRAME"
    LOW_IMAGE_QUALITY = "LOW_IMAGE_QUALITY"
    UNKNOWN = "UNKNOWN"


class ComponentEvidenceStatus(str, Enum):
    OBSERVED = "OBSERVED"
    NOT_OBSERVED = "NOT_OBSERVED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNVERIFIED = "UNVERIFIED"


class DetectionState(str, Enum):
    DETECTED = "DETECTED"
    ABSENT_VERIFIED = "ABSENT_VERIFIED"
    NOT_DETECTED = "NOT_DETECTED"
    UNCERTAIN = "UNCERTAIN"
    UNAVAILABLE = "UNAVAILABLE"


class ReconstructionDecision(str, Enum):
    SAFE_TO_USE = "SAFE_TO_USE"
    USE_WITH_UNCERTAINTY = "USE_WITH_UNCERTAINTY"
    REQUIRE_MORE_EVIDENCE = "REQUIRE_MORE_EVIDENCE"
    DO_NOT_INFER = "DO_NOT_INFER"


class GarmentFamily(str, Enum):
    UPPER_BODY = "upper_body"
    LOWER_BODY = "lower_body"
    DRESS_ONE_PIECE = "dress_one_piece"
    FOOTWEAR = "footwear"
    ACCESSORY = "accessory"


class ComponentTaxonomyEntry(BaseModel):
    model_config = ConfigDict(frozen=True)
    component_id: str
    component_type: str
    display_name: str
    family: GarmentFamily
    parent_component: Optional[str] = None
    side_applicable: bool = False
    default_side: Optional[str] = None
    expected_views: Tuple[str, ...] = ("front",)
    absence_requires_full_view: bool = True
    supports_spatial_localization: bool = True
    description: str = ""


class CategoryComponentProfile(BaseModel):
    model_config = ConfigDict(frozen=True)
    category: str
    family: GarmentFamily
    required_components: Tuple[str, ...]
    expected_components: Tuple[str, ...]
    optional_components: Tuple[str, ...] = ()
    landmark_targets: Tuple[str, ...] = ()
    absence_rules: Dict[str, str] = Field(default_factory=dict)


def _entry(
    cid: str,
    ctype: str,
    name: str,
    family: GarmentFamily,
    parent: Optional[str] = None,
    side_applicable: bool = False,
    default_side: Optional[str] = None,
    views: Tuple[str, ...] = ("front",),
    desc: str = "",
) -> ComponentTaxonomyEntry:
    return ComponentTaxonomyEntry(
        component_id=cid,
        component_type=ctype,
        display_name=name,
        family=family,
        parent_component=parent,
        side_applicable=side_applicable,
        default_side=default_side,
        expected_views=views,
        description=desc or name,
    )


UB = GarmentFamily.UPPER_BODY
LB = GarmentFamily.LOWER_BODY
DR = GarmentFamily.DRESS_ONE_PIECE


COMPONENT_TAXONOMY: Dict[str, ComponentTaxonomyEntry] = {
    entry.component_id: entry
    for entry in (
        # ── A. Upper-body: Body construction ──
        _entry("front_body", "front_body", "Front body panel", UB, "body", True, "front", ("front", "three_quarter")),
        _entry("back_body", "back_body", "Back body panel", UB, "body", True, "back", ("back",)),
        _entry("left_body_panel", "left_body_panel", "Left body panel", UB, "front_body", True, "left", ("front", "left_side", "three_quarter")),
        _entry("right_body_panel", "right_body_panel", "Right body panel", UB, "front_body", True, "right", ("front", "right_side", "three_quarter")),
        _entry("shoulder_panel", "shoulder_panel", "Shoulder panel / yoke", UB, "body", True, "bilateral", ("front", "back")),
        _entry("side_panel", "side_panel", "Side torso panel", UB, "body", True, "bilateral", ("left_side", "right_side")),
        # ── A. Upper-body: Sleeves ──
        _entry("left_sleeve", "left_sleeve", "Left sleeve", UB, "front_body", True, "left", ("front", "back", "left_side", "three_quarter")),
        _entry("right_sleeve", "right_sleeve", "Right sleeve", UB, "front_body", True, "right", ("front", "back", "right_side", "three_quarter")),
        _entry("sleeve_opening", "sleeve_opening", "Sleeve opening", UB, "sleeve", True, "bilateral", ("front", "left_side", "right_side", "close_up", "detail")),
        _entry("cuff", "cuff", "Sleeve cuff", UB, "sleeve", True, "bilateral", ("front", "left_side", "right_side", "close_up", "detail")),
        _entry("sleeve_seam", "sleeve_seam", "Sleeve underarm seam", UB, "sleeve", True, "bilateral", ("front", "back", "left_side", "right_side", "detail")),
        _entry("sleeve_attachment", "sleeve_attachment", "Armscye sleeve attachment", UB, "front_body", True, "bilateral", ("front", "back", "left_side", "right_side")),
        # ── A. Upper-body: Neck and collar ──
        _entry("collar", "collar", "Folded or stand collar", UB, "neck_opening", False, "center", ("front", "back", "three_quarter", "close_up")),
        _entry("collar_stand", "collar_stand", "Collar stand", UB, "collar", False, "center", ("front", "three_quarter", "close_up", "detail")),
        _entry("lapel", "lapel", "Jacket lapel", UB, "front_body", True, "bilateral", ("front", "three_quarter", "close_up")),
        _entry("neck_opening", "neck_opening", "Neck opening", UB, "front_body", False, "center", ("front", "back", "three_quarter")),
        _entry("hood", "hood", "Attached hood", UB, "neck_opening", False, "center", ("front", "back", "left_side", "right_side", "three_quarter")),
        _entry("hood_opening", "hood_opening", "Hood face opening", UB, "hood", False, "front", ("front", "three_quarter")),
        _entry("neckband", "neckband", "Ribbed neckband", UB, "neck_opening", False, "center", ("front", "close_up", "detail")),
        # ── A. Upper-body: Closures ──
        _entry("zipper", "zipper", "Front or pocket zipper", UB, "front_body", False, "center", ("front", "three_quarter", "close_up", "detail")),
        _entry("button", "button", "Button fastener", UB, "button_placket", False, "center", ("front", "close_up", "detail")),
        _entry("button_placket", "button_placket", "Center front button placket", UB, "front_body", False, "center", ("front", "three_quarter", "close_up")),
        _entry("snap", "snap", "Snap fastener", UB, "front_body", False, "center", ("front", "close_up", "detail")),
        _entry("hook", "hook", "Hook fastener", UB, "front_body", False, "center", ("front", "close_up", "detail")),
        _entry("drawstring", "drawstring", "Hood or waist drawstring", UB, "hood", False, "front", ("front", "close_up", "detail")),
        _entry("velcro_closure", "velcro_closure", "Hook-and-loop velcro closure", UB, "front_body", False, "front", ("front", "close_up", "detail")),
        # ── A. Upper-body: Pockets ──
        _entry("chest_pocket", "chest_pocket", "Chest pocket", UB, "front_body", True, "bilateral", ("front", "three_quarter", "close_up")),
        _entry("side_pocket", "side_pocket", "Side seam pocket", UB, "front_body", True, "bilateral", ("front", "left_side", "right_side", "close_up")),
        _entry("patch_pocket", "patch_pocket", "Exterior patch pocket", UB, "front_body", True, "bilateral", ("front", "back", "close_up")),
        _entry("welt_pocket", "welt_pocket", "Welt slit pocket", UB, "front_body", True, "bilateral", ("front", "back", "close_up", "detail")),
        _entry("flap_pocket", "flap_pocket", "Flap pocket", UB, "front_body", True, "bilateral", ("front", "back", "close_up")),
        _entry("pocket_opening", "pocket_opening", "Pocket entry opening", UB, "patch_pocket", True, "bilateral", ("front", "close_up", "detail")),
        _entry("kangaroo_pocket", "kangaroo_pocket", "Front kangaroo pouch pocket", UB, "front_body", False, "front", ("front", "three_quarter")),
        # ── A. Upper-body: Construction details ──
        _entry("shoulder_seam", "shoulder_seam", "Shoulder seam", UB, "front_body", True, "bilateral", ("front", "back", "detail")),
        _entry("side_seam", "side_seam", "Lateral side seam", UB, "front_body", True, "bilateral", ("left_side", "right_side", "detail")),
        _entry("hem", "hem", "Lower garment hem", UB, "front_body", False, "center", ("front", "back", "left_side", "right_side")),
        _entry("waistband", "waistband", "Lower ribbed or contoured waistband", UB, "front_body", False, "center", ("front", "back")),
        _entry("ribbing", "ribbing", "Rib-knit trim band", UB, "waistband", False, "center", ("front", "close_up", "detail")),
        _entry("stitching", "stitching", "Visible topstitching seam detail", UB, "front_body", False, "center", ("close_up", "detail")),
        # ── B. Lower-body garments ──
        _entry("lower_waistband", "waistband", "Trouser or skirt waistband", LB, None, False, "center", ("front", "back", "left_side", "right_side")),
        _entry("belt_loops", "belt_loops", "Waistband belt loops", LB, "lower_waistband", False, "center", ("front", "back", "close_up", "detail")),
        _entry("fly", "fly", "Center front fly closure", LB, "lower_waistband", False, "front", ("front", "close_up")),
        _entry("front_rise", "front_rise", "Front rise panel", LB, "lower_waistband", False, "front", ("front",)),
        _entry("back_rise", "back_rise", "Back rise panel", LB, "lower_waistband", False, "back", ("back",)),
        _entry("left_leg", "left_leg", "Left trouser leg", LB, "lower_waistband", True, "left", ("front", "back", "left_side")),
        _entry("right_leg", "right_leg", "Right trouser leg", LB, "lower_waistband", True, "right", ("front", "back", "right_side")),
        _entry("inseam", "inseam", "Inner leg inseam", LB, "left_leg", True, "bilateral", ("front", "back", "detail")),
        _entry("outseam", "outseam", "Outer leg outseam", LB, "left_leg", True, "bilateral", ("left_side", "right_side", "detail")),
        _entry("crotch_seam", "crotch_seam", "Crotch bifurcation seam", LB, "front_rise", False, "center", ("front", "back")),
        _entry("leg_opening", "leg_opening", "Leg cuff opening", LB, "left_leg", True, "bilateral", ("front", "back", "close_up")),
        _entry("front_pocket", "pocket", "Lower-body front pocket", LB, "front_rise", True, "bilateral", ("front", "left_side", "right_side", "close_up")),
        _entry("back_pocket", "pocket", "Lower-body rear pocket", LB, "back_rise", True, "bilateral", ("back", "close_up")),
        # ── C. Dresses and one-piece garments ──
        _entry("bodice", "bodice", "Upper dress bodice", DR, None, False, "center", ("front", "back", "three_quarter")),
        _entry("waistline", "waistline", "Dress waistline transition", DR, "bodice", False, "center", ("front", "back", "left_side", "right_side")),
        _entry("skirt", "skirt", "Lower dress or standalone skirt body", DR, "waistline", False, "center", ("front", "back", "left_side", "right_side")),
        _entry("neckline", "neckline", "Dress neckline contour", DR, "bodice", False, "front", ("front", "three_quarter")),
        _entry("straps", "straps", "Shoulder straps", DR, "bodice", True, "bilateral", ("front", "back")),
        _entry("dress_panels", "panels", "Vertical dress panels / gores", DR, "skirt", True, "bilateral", ("front", "back", "left_side", "right_side")),
        _entry("dress_closures", "closures", "Dress back or side closure", DR, "bodice", False, "back", ("back", "left_side", "right_side", "close_up")),
    )
}


CATEGORY_COMPONENT_PROFILES: Dict[str, CategoryComponentProfile] = {
    "jacket": CategoryComponentProfile(
        category="jacket",
        family=UB,
        required_components=("front_body", "left_sleeve", "right_sleeve", "collar", "hem"),
        expected_components=(
            "front_body", "back_body", "left_sleeve", "right_sleeve", "cuff",
            "collar", "lapel", "zipper", "button_placket", "button",
            "chest_pocket", "flap_pocket", "welt_pocket", "side_pocket", "hem", "shoulder_seam",
        ),
        optional_components=("hood", "snap", "pocket_opening", "waistband", "stitching"),
        landmark_targets=("collar_center", "shoulder_left", "shoulder_right", "armscye_left", "armscye_right", "cuff_left", "cuff_right", "hem_center"),
        absence_rules={
            "hood": "Hood can be declared absent only when the entire neckline from front or back is FULLY_VISIBLE and unobscured.",
            "chest_pocket": "Chest pocket absence requires FULLY_VISIBLE front_body at chest height with sufficient sharpness.",
        },
    ),
    "hoodie": CategoryComponentProfile(
        category="hoodie",
        family=UB,
        required_components=("front_body", "hood", "left_sleeve", "right_sleeve", "waistband"),
        expected_components=(
            "front_body", "back_body", "hood", "hood_opening", "drawstring",
            "left_sleeve", "right_sleeve", "cuff", "kangaroo_pocket", "zipper",
            "waistband", "ribbing", "hem",
        ),
        optional_components=("side_pocket", "patch_pocket", "pocket_opening"),
        landmark_targets=("hood_apex", "neckline_collar", "shoulder_left", "shoulder_right", "cuff_left", "cuff_right", "pocket_top_center", "hem_center"),
        absence_rules={
            "kangaroo_pocket": "Only absent on front view when lower torso is FULLY_VISIBLE and unobstructed.",
            "zipper": "Only absent when front center torso midline is FULLY_VISIBLE without vertical track.",
        },
    ),
    "shirt": CategoryComponentProfile(
        category="shirt",
        family=UB,
        required_components=("front_body", "collar", "button_placket", "hem"),
        expected_components=(
            "front_body", "back_body", "collar", "collar_stand", "button_placket",
            "button", "left_sleeve", "right_sleeve", "cuff", "chest_pocket", "hem", "shoulder_seam",
        ),
        optional_components=("pocket_opening", "side_seam", "sleeve_seam"),
        landmark_targets=("collar_center", "shoulder_left", "shoulder_right", "cuff_left", "cuff_right", "hem_center"),
    ),
    "tops": CategoryComponentProfile(
        category="tops",
        family=UB,
        required_components=("front_body", "neck_opening", "hem"),
        expected_components=(
            "front_body", "back_body", "neck_opening", "neckband", "collar",
            "left_sleeve", "right_sleeve", "sleeve_opening", "cuff", "hem", "waistband", "ribbing",
        ),
        optional_components=("chest_pocket", "button_placket", "zipper"),
        landmark_targets=("neck_center", "shoulder_left", "shoulder_right", "hem_center"),
    ),
    "traditional": CategoryComponentProfile(
        category="traditional",
        family=UB,
        required_components=("front_body", "collar", "hem"),
        expected_components=(
            "front_body", "back_body", "collar", "collar_stand", "button_placket",
            "button", "left_sleeve", "right_sleeve", "sleeve_opening", "side_seam", "hem",
        ),
        optional_components=("side_pocket", "stitching"),
        landmark_targets=("neck_center", "shoulder_left", "shoulder_right", "hem_center"),
    ),
    "bottoms": CategoryComponentProfile(
        category="bottoms",
        family=LB,
        required_components=("lower_waistband", "left_leg", "right_leg", "crotch_seam", "leg_opening"),
        expected_components=(
            "lower_waistband", "belt_loops", "fly", "front_rise", "back_rise",
            "left_leg", "right_leg", "inseam", "outseam", "crotch_seam", "leg_opening",
            "front_pocket", "back_pocket", "hem", "button", "zipper",
        ),
        optional_components=("patch_pocket", "flap_pocket", "drawstring"),
        landmark_targets=("waist_center", "crotch", "left_ankle", "right_ankle"),
        absence_rules={
            "back_pocket": "Never declare back_pocket absent from a front view; requires FULLY_VISIBLE back view.",
        },
    ),
    "dress": CategoryComponentProfile(
        category="dress",
        family=DR,
        required_components=("bodice", "waistline", "skirt", "neckline", "hem"),
        expected_components=(
            "bodice", "waistline", "skirt", "neckline", "left_sleeve", "right_sleeve",
            "straps", "hem", "dress_panels", "dress_closures", "zipper", "button",
        ),
        optional_components=("side_pocket", "collar", "cuff"),
        landmark_targets=("neck_center", "waist_center", "hem_center"),
        absence_rules={
            "dress_closures": "Rear zippers/buttons require back view; cannot be marked absent from front photo.",
        },
    ),
    "skirt": CategoryComponentProfile(
        category="skirt",
        family=DR,
        required_components=("lower_waistband", "skirt", "hem"),
        expected_components=("lower_waistband", "skirt", "waistline", "hem", "dress_panels", "zipper", "button", "side_pocket"),
        optional_components=("belt_loops", "flap_pocket"),
        landmark_targets=("waist_center", "hem_center"),
    ),
}


def resolve_category_profile(category: str, subcategory: str = "") -> CategoryComponentProfile:
    cat = (category or "").lower().strip()
    sub = (subcategory or "").lower().strip()
    if "hoodie" in sub or cat == "hoodie":
        return CATEGORY_COMPONENT_PROFILES["hoodie"]
    if cat in {"jacket", "outerwear", "coat"} or any(k in sub for k in ("jacket", "blazer", "coat", "parka")):
        return CATEGORY_COMPONENT_PROFILES["jacket"]
    if cat == "shirt" or any(k in sub for k in ("shirt", "polo")):
        return CATEGORY_COMPONENT_PROFILES["shirt"]
    if cat in {"bottoms", "jeans", "trousers", "shorts"} or any(k in sub for k in ("jean", "trouser", "pant", "chino", "short")):
        return CATEGORY_COMPONENT_PROFILES["bottoms"]
    if cat == "skirt" or "skirt" in sub:
        return CATEGORY_COMPONENT_PROFILES["skirt"]
    if cat in {"dress", "dresses_and_skirts"} or "dress" in sub:
        return CATEGORY_COMPONENT_PROFILES["dress"]
    if cat in {"traditional", "kurta", "sherwani"} or any(k in sub for k in ("kurta", "sherwani")):
        return CATEGORY_COMPONENT_PROFILES["traditional"]
    return CATEGORY_COMPONENT_PROFILES["tops"]


def taxonomy_entry(component_id: str) -> Optional[ComponentTaxonomyEntry]:
    return COMPONENT_TAXONOMY.get(component_id)
