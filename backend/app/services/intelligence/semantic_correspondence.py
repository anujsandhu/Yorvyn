"""Phase 16.3.1 Semantic Pattern-to-Mesh Correspondence, Category Operation Specs, & Dimensional Integrity."""
from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

from backend.app.services.garments.reconstruction.pattern_geometry import (
    ConstructionVerificationState,
    PatternPiece2D,
    SeamConnection,
    UnifiedConstructionGraphContract,
)


CORRESPONDENCE_VERSION = "16.3.1"


class SyncStatus(str, Enum):
    SYNCHRONIZED = "SYNCHRONIZED"
    SYNCHRONIZED_WITH_UNCERTAINTY = "SYNCHRONIZED_WITH_UNCERTAINTY"
    REQUIRES_REBUILD = "REQUIRES_REBUILD"
    MAPPING_INVALID = "MAPPING_INVALID"
    CONSTRUCTION_CONFLICT = "CONSTRUCTION_CONFLICT"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class MeasurementScope(str, Enum):
    BODY_BASELINE = "BODY_BASELINE"
    PATTERN_PANEL_HALF = "PATTERN_PANEL_HALF"
    PATTERN_PANEL_FULL = "PATTERN_PANEL_FULL"
    HALF_GARMENT_FLAT = "HALF_GARMENT_FLAT"
    FULL_CIRCUMFERENCE = "FULL_CIRCUMFERENCE"
    EASE_ALLOWANCE = "EASE_ALLOWANCE"
    SEAM_ALLOWANCE = "SEAM_ALLOWANCE"
    FINISHED_GARMENT = "FINISHED_GARMENT"


class ConstructionRelationType(str, Enum):
    ATTACHED_TO = "ATTACHED_TO"
    PART_OF = "PART_OF"
    CONNECTED_TO = "CONNECTED_TO"
    OVERLAPS = "OVERLAPS"
    SYMMETRIC_WITH = "SYMMETRIC_WITH"
    SEWN_TO = "SEWN_TO"
    FOLDED_FROM = "FOLDED_FROM"
    SUPPORTED_BY_VIEW = "SUPPORTED_BY_VIEW"


class ScopedMeasurement(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    value_m: float
    unit: str = "m"
    scope: MeasurementScope
    panel_id: Optional[str] = None
    seam_allowance_included: bool = False
    ease_m: float = 0.0
    notes: str = ""

    @property
    def value_cm(self) -> float:
        return round(self.value_m * 100.0, 3)


def panel_width_to_half_chest_m(panel_width_m: float, scope: MeasurementScope, *, symmetry_multiplier: int = 2) -> float:
    """Convert a cut/finished front panel width into half-garment flat chest width."""
    if panel_width_m <= 0:
        raise ValueError("Panel width must be positive.")
    if scope == MeasurementScope.PATTERN_PANEL_HALF:
        return round(panel_width_m * max(1, symmetry_multiplier), 5)
    if scope == MeasurementScope.PATTERN_PANEL_FULL:
        return round(panel_width_m, 5)
    if scope == MeasurementScope.HALF_GARMENT_FLAT:
        return round(panel_width_m, 5)
    if scope == MeasurementScope.FULL_CIRCUMFERENCE:
        return round(panel_width_m * 0.5, 5)
    raise ValueError(f"Unsupported scope '{scope.value}' for half-chest conversion.")


def half_chest_to_circumference_m(half_chest_m: float) -> float:
    if half_chest_m <= 0:
        raise ValueError("Half-chest measurement must be positive.")
    return round(half_chest_m * 2.0, 5)


def net_dimension_excluding_seam_allowance_m(cut_dimension_m: float, seam_allowance_per_side_m: float, sides: int = 2) -> float:
    net = cut_dimension_m - seam_allowance_per_side_m * sides
    if net <= 0:
        raise ValueError("Seam allowances exceed total cut dimension.")
    return round(net, 5)


def apply_panel_ease_to_chest(
    *,
    panel_width_m: float,
    panel_scope: MeasurementScope,
    ease_delta_m: float,
    apply_symmetrically: bool = True,
) -> Dict[str, ScopedMeasurement]:
    """Deterministically apply pattern ease (+cm) on one panel and derive exact flat & circumference totals."""
    if panel_width_m + ease_delta_m <= 0.04:
        raise ValueError("Resulting panel width cannot collapse below 4 cm.")
    new_panel_w = round(panel_width_m + ease_delta_m, 5)
    if panel_scope == MeasurementScope.PATTERN_PANEL_HALF:
        half_flat = round(new_panel_w * 2.0 if apply_symmetrically else (panel_width_m * 2.0 + ease_delta_m), 5)
        full_circ = round(half_flat * 2.0, 5) if apply_symmetrically else round(panel_width_m * 4.0 + ease_delta_m, 5)
    elif panel_scope == MeasurementScope.PATTERN_PANEL_FULL:
        half_flat = new_panel_w
        full_circ = round(new_panel_w * 2.0 if apply_symmetrically else (panel_width_m * 2.0 + ease_delta_m), 5)
    else:
        raise ValueError(f"Panel ease requires PATTERN_PANEL_HALF or PATTERN_PANEL_FULL scope, got {panel_scope.value}.")

    return {
        "panel_width": ScopedMeasurement(
            name="panel_width", value_m=new_panel_w, scope=panel_scope,
            notes="Single pattern piece net width",
        ),
        "half_garment_flat": ScopedMeasurement(
            name="half_garment_chest", value_m=half_flat, scope=MeasurementScope.HALF_GARMENT_FLAT,
            notes="Flat front width across body center",
        ),
        "finished_garment_circumference": ScopedMeasurement(
            name="chest_circumference", value_m=full_circ, scope=MeasurementScope.FULL_CIRCUMFERENCE,
            notes="Full finished garment circumference (front + back)",
        ),
        "applied_ease_delta": ScopedMeasurement(
            name="panel_ease_delta", value_m=round(ease_delta_m, 5), scope=MeasurementScope.EASE_ALLOWANCE,
            notes="Requested per-panel ease delta",
        ),
    }


class TopologySignature(BaseModel):
    vertex_count: int = 0
    triangle_count: int = 0
    component_ids_hash: str = ""
    is_valid: bool = True


class PatternRegionMapping(BaseModel):
    mapping_id: str
    piece_id: str
    pattern_vertex_ids: List[str] = Field(default_factory=list)
    pattern_edge_ids: List[str] = Field(default_factory=list)
    curve_ids: List[str] = Field(default_factory=list)
    seam_ids: List[str] = Field(default_factory=list)
    dart_ids: List[str] = Field(default_factory=list)
    notch_ids: List[str] = Field(default_factory=list)
    grainline_id: str = ""
    local_coordinate_system: str = "2D_METRIC_Z_UP_CCW"
    unit: str = "m"
    panel_scope: MeasurementScope = MeasurementScope.PATTERN_PANEL_FULL

    # Target 3D correspondence
    mesh_id: str
    mesh_region_ids: List[str] = Field(default_factory=list)
    garment_component_id: str
    surface_correspondence: str = "parametric_zone"  # direct_component | parametric_zone | unmapped
    uv_region_id: str = "main_uv_atlas"
    material_region_ref: str = "main_shell"
    vertex_index_ranges: List[Tuple[int, int]] = Field(default_factory=list)

    # Provenance & Epistemic state (preserved strictly across edits)
    source_image_ids: List[str] = Field(default_factory=list)
    source_image_hashes: List[str] = Field(default_factory=list)
    source_views: List[str] = Field(default_factory=list)
    evidence_source: str = "pattern_construction_engine"
    algorithm_id: str = "semantic_correspondence_v16.3.1"
    verification_state: ConstructionVerificationState = ConstructionVerificationState.INFERRED
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)
    valid: bool = True
    invalidation_reason: Optional[str] = None


class ConstructionRelationshipLink(BaseModel):
    relation_id: str
    relation: ConstructionRelationType
    source_id: str
    target_id: str
    evidence_refs: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    verification_state: ConstructionVerificationState = ConstructionVerificationState.INFERRED


class SemanticOperationSpec(BaseModel):
    operation_name: str
    supported_categories: List[str]
    target_component: str
    affected_pieces: List[str]
    affected_boundaries: List[str]
    related_seams: List[str]
    corresponding_3d_regions: List[str]
    preserved_regions: List[str]
    param_name: str
    min_scale: float
    max_scale: float
    geometric_transform: str
    construction_constraints: List[str]
    validation_criteria: List[str]
    rollback_behavior: str = "Restore exact prior revision snapshot (geometry, pattern, correspondence, measurements)"


class SemanticCorrespondenceMap(BaseModel):
    mapping_version: str = CORRESPONDENCE_VERSION
    garment_id: str
    candidate_id: Optional[str] = None
    category: str
    subcategory: str = ""
    pattern_version: int = 1
    geometry_version: int = 1
    topology_signature: TopologySignature = Field(default_factory=TopologySignature)
    piece_mappings: Dict[str, PatternRegionMapping] = Field(default_factory=dict)
    relationships: List[ConstructionRelationshipLink] = Field(default_factory=list)
    valid: bool = True
    invalidated_reasons: List[str] = Field(default_factory=list)


# 11-part Category-Aware Semantic Operation Registry
SEMANTIC_OPERATION_SPECS: Dict[str, SemanticOperationSpec] = {
    "torso_width": SemanticOperationSpec(
        operation_name="torso_width",
        supported_categories=["jacket", "outerwear", "hoodie", "shirt", "tops", "traditional", "dress"],
        target_component="torso",
        affected_pieces=["front_body", "front_left_body", "front_right_body", "back_body", "bodice_front", "bodice_back"],
        affected_boundaries=["hem", "side_left", "side_right", "side_seam", "shoulder_left", "shoulder_right"],
        related_seams=["seam_side_left", "seam_side_right", "seam_shoulder_left", "seam_shoulder_right", "seam_waistband_hem"],
        corresponding_3d_regions=["main_torso", "torso", "torso_shell", "bodice"],
        preserved_regions=["left_sleeve", "right_sleeve", "left_cuff", "right_cuff", "collar", "collar_stand"],
        param_name="torso_width_scale",
        min_scale=0.75,
        max_scale=1.40,
        geometric_transform="Symmetric XZ radial expansion around chest centerline keeping armhole attachment tangent",
        construction_constraints=["Side seam lengths must match across front and back", "Neckline aperture preserved"],
        validation_criteria=["CCW polygon", "non-self-intersecting", "seam length delta <= tolerance"],
    ),
    "torso_length": SemanticOperationSpec(
        operation_name="torso_length",
        supported_categories=["jacket", "outerwear", "hoodie", "shirt", "tops", "traditional", "dress"],
        target_component="torso",
        affected_pieces=["front_body", "front_left_body", "front_right_body", "back_body", "placket"],
        affected_boundaries=["side_left", "side_right", "side_seam", "center_closure"],
        related_seams=["seam_side_left", "seam_side_right", "seam_front_placket_l", "seam_front_placket_r"],
        corresponding_3d_regions=["main_torso", "torso", "front_zipper_track", "front_placket"],
        preserved_regions=["lapels_and_collar", "collar_and_stand", "hood_cowl", "left_sleeve", "right_sleeve"],
        param_name="torso_length_scale",
        min_scale=0.70,
        max_scale=1.35,
        geometric_transform="Vertical Y-stretch anchored at shoulder-neckline plane downward toward hem",
        construction_constraints=["Shoulder and neckline geometry unchanged", "Placket scales proportionally with front closure"],
        validation_criteria=["Positive height", "finite vertex normals", "hem waistband alignment"],
    ),
    "shoulder_width": SemanticOperationSpec(
        operation_name="shoulder_width",
        supported_categories=["jacket", "outerwear", "hoodie", "shirt", "tops", "traditional"],
        target_component="shoulder",
        affected_pieces=["front_body", "front_left_body", "front_right_body", "back_body"],
        affected_boundaries=["shoulder", "shoulder_left", "shoulder_right", "armscye", "armscye_left", "armscye_right"],
        related_seams=["seam_shoulder_left", "seam_shoulder_right", "seam_armscye_left", "seam_armscye_right"],
        corresponding_3d_regions=["main_torso", "left_sleeve", "right_sleeve"],
        preserved_regions=["waistband", "left_cuff", "right_cuff"],
        param_name="shoulder_width_scale",
        min_scale=0.82,
        max_scale=1.28,
        geometric_transform="Upper-shoulder lateral X displacement shifting sleeve origins cleanly without tearing armscye seams",
        construction_constraints=["Front & back shoulder seam lengths remain equal", "Sleeves translate laterally with shoulder apex"],
        validation_criteria=["No armhole pinch", "sleeve cap length within ease budget"],
    ),
    "sleeve_length": SemanticOperationSpec(
        operation_name="sleeve_length",
        supported_categories=["jacket", "outerwear", "hoodie", "shirt", "tops", "traditional"],
        target_component="sleeve",
        affected_pieces=["left_sleeve", "right_sleeve"],
        affected_boundaries=["underarm_a", "underarm_b", "cuff_edge"],
        related_seams=["seam_cuff_left", "seam_cuff_right"],
        corresponding_3d_regions=["left_sleeve", "right_sleeve", "left_cuff", "right_cuff"],
        preserved_regions=["main_torso", "lapels_and_collar", "hood_cowl", "waistband"],
        param_name="sleeve_length_scale",
        min_scale=0.55,
        max_scale=1.30,
        geometric_transform="Longitudinal sleeve-axis stretch anchored at armscye sleeve cap; cuffs translate cleanly along sleeve axis",
        construction_constraints=["Sleeve cap perimeter invariant", "Left/right symmetry unless asymmetric mode specified"],
        validation_criteria=["Non-collapsed sleeve cylinder", "cuff edge attached cleanly"],
    ),
    "sleeve_width": SemanticOperationSpec(
        operation_name="sleeve_width",
        supported_categories=["jacket", "outerwear", "hoodie", "shirt", "tops", "traditional"],
        target_component="sleeve",
        affected_pieces=["left_sleeve", "right_sleeve", "left_cuff", "right_cuff"],
        affected_boundaries=["sleeve_cap", "cuff_edge"],
        related_seams=["seam_armscye_left", "seam_armscye_right", "seam_cuff_left", "seam_cuff_right"],
        corresponding_3d_regions=["left_sleeve", "right_sleeve", "left_cuff", "right_cuff"],
        preserved_regions=["main_torso", "lapels_and_collar", "hood_cowl"],
        param_name="sleeve_width_scale",
        min_scale=0.75,
        max_scale=1.40,
        geometric_transform="Radial cross-section expansion orthogonal to each sleeve's longitudinal PCA/bone axis",
        construction_constraints=["Sleeve cap stays compatible with armscye ease budget", "Cuff circumference scales consistently"],
        validation_criteria=["No inverted sleeve normals", "positive sleeve polygon area"],
    ),
    "collar_width": SemanticOperationSpec(
        operation_name="collar_width",
        supported_categories=["jacket", "outerwear", "shirt", "tops", "hoodie", "traditional"],
        target_component="collar",
        affected_pieces=["collar", "collar_stand", "neckband", "mandarin_collar", "hood_left_panel", "hood_right_panel"],
        affected_boundaries=["neckline", "attach_front_l", "attach_front_r", "attach_back", "bottom"],
        related_seams=["seam_collar_to_stand", "seam_stand_to_front_l", "seam_stand_to_back", "seam_neckband", "seam_hood_neck"],
        corresponding_3d_regions=["lapels_and_collar", "collar_and_stand", "hood_cowl"],
        preserved_regions=["left_sleeve", "right_sleeve", "kangaroo_pocket"],
        param_name="collar_width_scale",
        min_scale=0.75,
        max_scale=1.30,
        geometric_transform="Circumferential X/Z scaling of collar/stand ring anchored at nape",
        construction_constraints=["Collar stand attachment total must match front + back neckline arcs within ease"],
        validation_criteria=["Non-self-intersecting neckline curve"],
    ),
    "cuff_width": SemanticOperationSpec(
        operation_name="cuff_width",
        supported_categories=["jacket", "outerwear", "hoodie", "shirt"],
        target_component="cuff",
        affected_pieces=["left_cuff", "right_cuff"],
        affected_boundaries=["top", "bottom"],
        related_seams=["seam_cuff_left", "seam_cuff_right"],
        corresponding_3d_regions=["left_cuff", "right_cuff"],
        preserved_regions=["main_torso", "lapels_and_collar", "hood_cowl"],
        param_name="cuff_width_scale",
        min_scale=0.78,
        max_scale=1.32,
        geometric_transform="Radial scaling of wrist cuff bands while tapering lower sleeve transition",
        construction_constraints=["Wrist opening must stay >= minimum hand passage clearance (16 cm)"],
        validation_criteria=["Positive cuff opening perimeter", "cuff seam Delta <= tolerance"],
    ),
    "hem_width": SemanticOperationSpec(
        operation_name="hem_width",
        supported_categories=["jacket", "outerwear", "hoodie", "shirt", "tops", "skirt", "dress"],
        target_component="hem",
        affected_pieces=["waistband", "hem_facing", "front_body", "front_left_body", "front_right_body", "back_body", "skirt_front", "skirt_back"],
        affected_boundaries=["hem", "bottom", "top"],
        related_seams=["seam_waistband_hem", "seam_waistband_hem_l", "seam_waistband_hem_r", "seam_hem_facing"],
        corresponding_3d_regions=["main_torso", "torso", "skirt_shell", "waistband"],
        preserved_regions=["lapels_and_collar", "left_sleeve", "right_sleeve"],
        param_name="hem_width_scale",
        min_scale=0.80,
        max_scale=1.35,
        geometric_transform="Smooth lower-hem X/Z flare taper weighted toward bottom 25% of torso/skirt height",
        construction_constraints=["Hem facing/waistband length must stay locked to body hem length"],
        validation_criteria=["Continuous side seam slope", "seam length match on waistband"],
    ),
    "waistband_width": SemanticOperationSpec(
        operation_name="waistband_width",
        supported_categories=["bottoms", "pants", "trousers", "jeans", "shorts", "skirt"],
        target_component="waistband",
        affected_pieces=["waistband", "left_front_leg", "right_front_leg", "left_back_leg", "right_back_leg", "skirt_front", "skirt_back"],
        affected_boundaries=["waist_top", "attach_front_left", "attach_front_right", "attach_back_left", "attach_back_right"],
        related_seams=["seam_waist_left_front", "seam_waist_right_front", "seam_waist_left_back", "seam_waist_right_back"],
        corresponding_3d_regions=["waistband_and_pelvis"],
        preserved_regions=["left_cuff", "right_cuff"],
        param_name="waistband_width_scale",
        min_scale=0.78,
        max_scale=1.35,
        geometric_transform="Pelvis top ring & waistband XZ radial scaling while blending smoothly to mid-hip",
        construction_constraints=["Total waistband attach span equals sum of 4 top leg waist edges"],
        validation_criteria=["Positive waist area", "no fly zipper distortion"],
    ),
    "leg_width": SemanticOperationSpec(
        operation_name="leg_width",
        supported_categories=["bottoms", "pants", "trousers", "jeans", "shorts"],
        target_component="leg",
        affected_pieces=["left_front_leg", "right_front_leg", "left_back_leg", "right_back_leg"],
        affected_boundaries=["inseam", "outseam", "hem"],
        related_seams=["seam_left_inseam", "seam_left_outseam", "seam_right_inseam", "seam_right_outseam"],
        corresponding_3d_regions=["left_leg", "right_leg", "left_cuff", "right_cuff"],
        preserved_regions=["waistband_and_pelvis"],
        param_name="leg_width_scale",
        min_scale=0.75,
        max_scale=1.45,
        geometric_transform="Bifurcated radial leg cylinder expansion centered on each leg tube axis",
        construction_constraints=["Front & back leg inseam/outseam lengths remain synchronized", "Crotch rise bridge kept intact"],
        validation_criteria=["Zero inter-leg inner collision overlap", "finite normals"],
    ),
    "leg_length": SemanticOperationSpec(
        operation_name="leg_length",
        supported_categories=["bottoms", "pants", "trousers", "jeans", "shorts"],
        target_component="leg",
        affected_pieces=["left_front_leg", "right_front_leg", "left_back_leg", "right_back_leg"],
        affected_boundaries=["inseam", "outseam"],
        related_seams=["seam_left_inseam", "seam_left_outseam", "seam_right_inseam", "seam_right_outseam"],
        corresponding_3d_regions=["left_leg", "right_leg", "left_cuff", "right_cuff"],
        preserved_regions=["waistband_and_pelvis"],
        param_name="leg_length_scale",
        min_scale=0.60,
        max_scale=1.30,
        geometric_transform="Vertical Y leg elongation downward from crotch apex",
        construction_constraints=["Crotch apex and pelvis rise fixed", "Leg hems stay horizontally aligned"],
        validation_criteria=["Positive inseam length", "valid ankle bounds"],
    ),
    "pocket_placement": SemanticOperationSpec(
        operation_name="pocket_placement",
        supported_categories=["hoodie", "jacket", "outerwear"],
        target_component="pocket",
        affected_pieces=["kangaroo_pocket", "chest_pocket_left"],
        affected_boundaries=["bottom"],
        related_seams=["seam_kangaroo_pocket", "seam_chest_pocket_l"],
        corresponding_3d_regions=["kangaroo_pocket", "chest_pocket_left"],
        preserved_regions=["main_torso", "left_sleeve", "right_sleeve", "lapels_and_collar", "hood_cowl"],
        param_name="pocket_offset_y_m",
        min_scale=-0.06,
        max_scale=0.06,
        geometric_transform="Bounded Y translation along front torso surface only when pocket mesh node exists in correspondence",
        construction_constraints=["Requires verified pocket node in both pattern graph and 3D component graph"],
        validation_criteria=["Pocket stays strictly inside front torso boundary polygon"],
    ),
}


def compute_topology_signature(mesh_components: Optional[Dict[str, Any]] = None, vertex_count: int = 0, triangle_count: int = 0) -> TopologySignature:
    comp_ids = sorted(mesh_components.keys()) if mesh_components else []
    sig_hash = hashlib.sha256(json.dumps(comp_ids).encode("utf-8")).hexdigest()[:16]
    return TopologySignature(
        vertex_count=vertex_count,
        triangle_count=triangle_count,
        component_ids_hash=sig_hash,
        is_valid=True,
    )


def _match_mesh_regions(piece_id: str, piece: PatternPiece2D, available_3d_regions: List[str]) -> Tuple[List[str], str, str]:
    """Map pattern piece semantically onto known 3D component regions without relying on raw vertex indices."""
    avail_set = set(available_3d_regions)
    pid = piece_id.lower()
    comp = piece.parent_component.lower()

    if "left_sleeve" in pid:
        targets = [r for r in ("left_sleeve",) if r in avail_set] or ["left_sleeve"]
        return targets, "direct_component" if "left_sleeve" in avail_set else "parametric_zone", "sleeve_left_uv"
    if "right_sleeve" in pid:
        targets = [r for r in ("right_sleeve",) if r in avail_set] or ["right_sleeve"]
        return targets, "direct_component" if "right_sleeve" in avail_set else "parametric_zone", "sleeve_right_uv"
    if "left_cuff" in pid:
        return ["left_cuff"], "direct_component" if "left_cuff" in avail_set else "parametric_zone", "cuff_uv"
    if "right_cuff" in pid:
        return ["right_cuff"], "direct_component" if "right_cuff" in avail_set else "parametric_zone", "cuff_uv"
    if "hood" in pid:
        return ["hood_cowl"], "direct_component" if "hood_cowl" in avail_set else "parametric_zone", "hood_uv"
    if "kangaroo" in pid:
        if "kangaroo_pocket" in avail_set or not avail_set:
            return ["kangaroo_pocket"], "direct_component" if "kangaroo_pocket" in avail_set else "parametric_zone", "pocket_uv"
        return [], "unmapped", "pocket_uv"
    if "chest_pocket" in pid:
        if "chest_pocket_left" in avail_set:
            return ["chest_pocket_left"], "direct_component", "pocket_uv"
        return ["main_torso"], "parametric_zone", "pocket_uv"
    if "back_pocket" in pid:
        return [], "unmapped", "pocket_uv"
    if "collar" in pid or "neckband" in pid:
        cands = [r for r in ("lapels_and_collar", "collar_and_stand", "main_torso") if r in avail_set]
        return cands or ["lapels_and_collar"], "direct_component" if any(c in avail_set for c in ("lapels_and_collar", "collar_and_stand")) else "parametric_zone", "collar_uv"
    if "placket" in pid:
        cands = [r for r in ("front_placket", "front_zipper_track", "main_torso") if r in avail_set]
        return cands or ["front_placket"], "direct_component" if any(c in avail_set for c in ("front_placket", "front_zipper_track")) else "parametric_zone", "placket_uv"
    if "left_front_leg" in pid or "left_back_leg" in pid:
        return ["left_leg"], "direct_component" if "left_leg" in avail_set else "parametric_zone", "left_leg_uv"
    if "right_front_leg" in pid or "right_back_leg" in pid:
        return ["right_leg"], "direct_component" if "right_leg" in avail_set else "parametric_zone", "right_leg_uv"
    if "waistband" in pid or "fly_shield" in pid:
        if "waistband_and_pelvis" in avail_set:
            return ["waistband_and_pelvis"], "direct_component", "waistband_uv"
        return ["main_torso"], "parametric_zone", "hem_uv"
    if any(k in pid for k in ("front", "back", "bodice", "skirt", "hem", "lehenga")):
        return ["main_torso"], "direct_component" if "main_torso" in avail_set else "parametric_zone", f"{comp}_uv"
    return [], "unmapped", "main_uv_atlas"


def build_semantic_correspondence(
    *,
    garment_id: str,
    candidate_id: Optional[str],
    graph: UnifiedConstructionGraphContract,
    mesh_id: str = "candidate_mesh_v1",
    available_3d_regions: Optional[List[str]] = None,
    topology_signature: Optional[TopologySignature] = None,
    pattern_version: int = 1,
    geometry_version: int = 1,
    source_image_hashes: Optional[Dict[str, str]] = None,
) -> SemanticCorrespondenceMap:
    """Build explicit versioned 2D Pattern -> 3D Mesh Region correspondence preserving evidence provenance."""
    regions_3d = list(available_3d_regions or [])
    hash_lookup = source_image_hashes or {}
    mappings: Dict[str, PatternRegionMapping] = {}
    rels: List[ConstructionRelationshipLink] = []

    for pid, piece in graph.pieces.items():
        mesh_regions, surf_kind, uv_reg = _match_mesh_regions(pid, piece, regions_3d)
        piece_seams = [s.seam_id for s in graph.seams if s.piece_a == pid or s.piece_b == pid]
        v_ids = [f"{pid}:v{i}" for i in range(len(piece.boundary_polygon))]
        e_ids = [f"{pid}:{e.edge_id}" for e in piece.edges]
        c_ids = [f"{pid}:{e.edge_id}:bezier" for e in piece.edges if e.bezier is not None]
        d_ids = [d.dart_id for d in piece.darts]
        n_ids = [n.notch_id for n in piece.notches]
        img_hashes = [hash_lookup[img_id] for img_id in piece.evidence_refs if img_id in hash_lookup]

        scope = MeasurementScope.PATTERN_PANEL_HALF if ("front_left" in pid or "front_right" in pid) else MeasurementScope.PATTERN_PANEL_FULL
        mappings[pid] = PatternRegionMapping(
            mapping_id=f"map_{pid}_v{pattern_version}_{geometry_version}",
            piece_id=pid,
            pattern_vertex_ids=v_ids,
            pattern_edge_ids=e_ids,
            curve_ids=c_ids,
            seam_ids=piece_seams,
            dart_ids=d_ids,
            notch_ids=n_ids,
            grainline_id=f"{pid}:grainline",
            panel_scope=scope,
            mesh_id=mesh_id,
            mesh_region_ids=mesh_regions,
            garment_component_id=piece.parent_component,
            surface_correspondence=surf_kind,
            uv_region_id=uv_reg,
            material_region_ref=piece.material_ref,
            source_image_ids=list(piece.evidence_refs),
            source_image_hashes=img_hashes,
            source_views=list(piece.source_views),
            verification_state=piece.verification_state,
            confidence=piece.confidence,
            uncertainty=piece.uncertainty,
            valid=(surf_kind != "unmapped"),
            invalidation_reason=None if surf_kind != "unmapped" else f"No 3D semantic target mapped for piece '{pid}'.",
        )

        # Preserve component attachment & view support relations
        for img_id in piece.evidence_refs:
            rels.append(ConstructionRelationshipLink(
                relation_id=f"rel_view_{pid}_{img_id}",
                relation=ConstructionRelationType.SUPPORTED_BY_VIEW,
                source_id=pid,
                target_id=img_id,
                evidence_refs=[img_id],
                confidence=piece.confidence,
                verification_state=piece.verification_state,
            ))

    for s in graph.seams:
        rel_kind = ConstructionRelationType.SEWN_TO
        if s.seam_type.value in ("COLLAR_ATTACHMENT", "SLEEVE_ATTACHMENT", "POCKET_ATTACHMENT", "LINING_ATTACHMENT"):
            rel_kind = ConstructionRelationType.ATTACHED_TO
        rels.append(ConstructionRelationshipLink(
            relation_id=f"rel_{s.seam_id}",
            relation=rel_kind,
            source_id=s.piece_a,
            target_id=s.piece_b,
            evidence_refs=list(s.source_evidence),
            confidence=s.confidence,
            verification_state=s.verification_state,
        ))

    if "front_left_body" in graph.pieces and "front_right_body" in graph.pieces:
        rels.append(ConstructionRelationshipLink(
            relation_id="rel_sym_front_panels",
            relation=ConstructionRelationType.SYMMETRIC_WITH,
            source_id="front_left_body",
            target_id="front_right_body",
            confidence=min(graph.pieces["front_left_body"].confidence, graph.pieces["front_right_body"].confidence),
            verification_state=graph.pieces["front_left_body"].verification_state,
        ))
    if "left_sleeve" in graph.pieces and "right_sleeve" in graph.pieces:
        rels.append(ConstructionRelationshipLink(
            relation_id="rel_sym_sleeves",
            relation=ConstructionRelationType.SYMMETRIC_WITH,
            source_id="left_sleeve",
            target_id="right_sleeve",
            confidence=min(graph.pieces["left_sleeve"].confidence, graph.pieces["right_sleeve"].confidence),
            verification_state=graph.pieces["left_sleeve"].verification_state,
        ))

    sig = topology_signature or TopologySignature()
    return SemanticCorrespondenceMap(
        garment_id=garment_id,
        candidate_id=candidate_id,
        category=graph.category,
        subcategory=graph.subcategory,
        pattern_version=pattern_version,
        geometry_version=geometry_version,
        topology_signature=sig,
        piece_mappings=mappings,
        relationships=rels,
        valid=True,
    )


def validate_correspondence_against_topology(
    corr: SemanticCorrespondenceMap,
    *,
    expected_vertex_count: int,
    expected_triangle_count: int,
    operation_name: Optional[str] = None,
) -> Tuple[bool, SyncStatus, List[str]]:
    """Verify topology invariants & check operation semantic correspondence; never silently guess."""
    reasons: List[str] = []
    if corr.topology_signature.vertex_count > 0 and corr.topology_signature.vertex_count != expected_vertex_count:
        reasons.append(f"Vertex count changed ({corr.topology_signature.vertex_count} -> {expected_vertex_count}); mapping invalidated.")
    if corr.topology_signature.triangle_count > 0 and corr.topology_signature.triangle_count != expected_triangle_count:
        reasons.append(f"Triangle count changed ({corr.topology_signature.triangle_count} -> {expected_triangle_count}); mapping invalidated.")
    if reasons or not corr.valid:
        corr.valid = False
        corr.invalidated_reasons = reasons or corr.invalidated_reasons
        return False, SyncStatus.MAPPING_INVALID, corr.invalidated_reasons

    if operation_name:
        spec = SEMANTIC_OPERATION_SPECS.get(operation_name)
        if not spec:
            return False, SyncStatus.NOT_SUPPORTED, [f"Unsupported semantic operation '{operation_name}'."]
        cat = corr.category.lower().strip()
        if not any(c in cat or cat in c for c in spec.supported_categories):
            return False, SyncStatus.NOT_SUPPORTED, [f"Operation '{operation_name}' is not supported for garment category '{corr.category}'."]
        matched_pieces = [p for p in spec.affected_pieces if p in corr.piece_mappings and corr.piece_mappings[p].valid]
        if not matched_pieces:
            return False, SyncStatus.REQUIRES_REBUILD, [f"No valid 2D-to-3D pattern correspondence exists for '{operation_name}' on garment '{corr.garment_id}'."]
        # Check if affected pieces include unverified/inferred surfaces so caller reports SYNCHRONIZED_WITH_UNCERTAINTY
        uncertain = any(
            corr.piece_mappings[p].verification_state != ConstructionVerificationState.OBSERVED
            for p in matched_pieces
        )
        if uncertain:
            return True, SyncStatus.SYNCHRONIZED_WITH_UNCERTAINTY, []

    return True, SyncStatus.SYNCHRONIZED, []


class AvatarCorrespondenceRegion(BaseModel):
    garment_region: str
    avatar_region: str
    target_bones: List[int] = Field(default_factory=list)
    confidence: float = Field(0.85, ge=0.0, le=1.0)
    attachment_mode: str = "skinned_drape"  # skinned_drape, rigid_anchor, soft_strap
    verified_against_mesh: bool = False


class SemanticAvatarCorrespondenceReport(BaseModel):
    category: str
    subcategory: str
    overall_confidence: float
    is_valid: bool = True
    regions: List[AvatarCorrespondenceRegion] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class SemanticCorrespondenceEngine:
    """
    Phase 17.7 category-aware garment-to-avatar semantic correspondence resolver & validator
    supporting upper-body, lower-body, dresses/skirts, traditional, footwear, headwear,
    bags, belts, jewelry/watches, glasses, and scarves/gloves.
    """

    CATEGORY_REGION_SPECS: Dict[str, List[Tuple[str, str, List[int], str, float]]] = {
        "tops": [
            ("neck_collar", "Neck", [4, 3], "skinned_drape", 0.90),
            ("left_shoulder_chest", "Spine2/LeftArm", [3, 6], "skinned_drape", 0.92),
            ("right_shoulder_chest", "Spine2/RightArm", [3, 10], "skinned_drape", 0.92),
            ("torso_core", "Spine/Spine1/Spine2", [1, 2, 3], "skinned_drape", 0.94),
            ("left_sleeve", "LeftArm/LeftForeArm", [6, 7, 8], "skinned_drape", 0.88),
            ("right_sleeve", "RightArm/RightForeArm", [10, 11, 12], "skinned_drape", 0.88),
            ("hem_waist", "Hips/Spine", [0, 1], "skinned_drape", 0.90),
        ],
        "outerwear": [
            ("collar_lapel", "Neck/Spine2", [3, 4], "skinned_drape", 0.90),
            ("left_shoulder", "LeftShoulder/LeftArm", [6, 3], "skinned_drape", 0.92),
            ("right_shoulder", "RightShoulder/RightArm", [10, 3], "skinned_drape", 0.92),
            ("outer_shell_torso", "Spine1/Spine2", [1, 2, 3], "skinned_drape", 0.93),
            ("left_sleeve", "LeftArm/LeftForeArm", [6, 7, 8], "skinned_drape", 0.88),
            ("right_sleeve", "RightArm/RightForeArm", [10, 11, 12], "skinned_drape", 0.88),
            ("hem_hip", "Hips", [0, 1], "skinned_drape", 0.88),
        ],
        "bottoms": [
            ("waistband", "Hips/Spine", [0, 1], "skinned_drape", 0.94),
            ("pelvis_hip", "Hips/UpLegs", [0, 14, 17], "skinned_drape", 0.92),
            ("left_leg", "LeftUpLeg/LeftLeg/LeftFoot", [14, 15, 16], "skinned_drape", 0.91),
            ("right_leg", "RightUpLeg/RightLeg/RightFoot", [17, 18, 19], "skinned_drape", 0.91),
        ],
        "dresses_and_skirts": [
            ("upper_bodice", "Spine2/Neck", [2, 3, 4], "skinned_drape", 0.88),
            ("waist_seam", "Spine/Hips", [0, 1], "skinned_drape", 0.91),
            ("skirt_flare", "Hips/LeftUpLeg/RightUpLeg", [0, 14, 17], "skinned_drape", 0.87),
        ],
        "traditional": [
            ("mandarin_collar", "Neck/Spine2", [3, 4], "skinned_drape", 0.89),
            ("kurta_torso", "Spine1/Spine2", [1, 2, 3], "skinned_drape", 0.91),
            ("left_sleeve", "LeftArm/LeftForeArm", [6, 7], "skinned_drape", 0.86),
            ("right_sleeve", "RightArm/RightForeArm", [10, 11], "skinned_drape", 0.86),
            ("lower_panel_flare", "Hips/UpLegs", [0, 14, 17], "skinned_drape", 0.84),
        ],
        "footwear": [
            ("left_shoe", "LeftFoot", [15, 16], "rigid_anchor", 0.92),
            ("right_shoe", "RightFoot", [18, 19], "rigid_anchor", 0.92),
        ],
        "headwear": [
            ("head_crown", "Head", [5], "rigid_anchor", 0.91),
        ],
        "glasses": [
            ("nose_bridge_temples", "Head", [5], "rigid_anchor", 0.90),
        ],
        "bags": [
            ("shoulder_or_hand_strap", "LeftArm/RightArm/Spine2", [6, 10, 3], "soft_strap", 0.80),
        ],
        "belts": [
            ("waist_belt", "Hips/Spine", [0, 1], "skinned_drape", 0.91),
        ],
        "jewelry": [
            ("wrist_or_neck_mount", "LeftHand/RightHand/Neck", [4, 8, 12], "rigid_anchor", 0.82),
        ],
        "scarves_and_gloves": [
            ("neck_or_hand_wrap", "Neck/LeftHand/RightHand", [4, 8, 12], "soft_strap", 0.83),
        ],
    }

    def build_and_validate(
        self,
        *,
        category: str,
        subcategory: str = "",
        positions: Optional[np.ndarray] = None,
        joint_indices: Optional[np.ndarray] = None,
        joint_weights: Optional[np.ndarray] = None,
        component_types: Optional[List[str]] = None,
    ) -> SemanticAvatarCorrespondenceReport:
        cat_l = (category or "tops").lower().strip()
        sub_l = (subcategory or "").lower().strip()

        lookup_key = cat_l
        if cat_l == "accessories":
            if any(k in sub_l for k in ("hat", "cap", "beanie", "fedora", "headwear")):
                lookup_key = "headwear"
            elif any(k in sub_l for k in ("glass", "sunglass", "eyewear")):
                lookup_key = "glasses"
            elif any(k in sub_l for k in ("bag", "backpack", "tote", "purse", "clutch")):
                lookup_key = "bags"
            elif "belt" in sub_l:
                lookup_key = "belts"
            elif any(k in sub_l for k in ("watch", "brace", "ring", "neckl", "earr", "jewel")):
                lookup_key = "jewelry"
            elif any(k in sub_l for k in ("scarf", "glove", "shawl")):
                lookup_key = "scarves_and_gloves"
            else:
                lookup_key = "headwear"

        specs = list(self.CATEGORY_REGION_SPECS.get(lookup_key, self.CATEGORY_REGION_SPECS["tops"]))
        if "skirt" in sub_l and lookup_key == "dresses_and_skirts":
            specs = [s for s in specs if s[0] != "upper_bodice"]
        if any(k in sub_l for k in ("hoodie", "parka")) or (component_types and "hood" in component_types):
            if all(s[0] != "hood_cowl" for s in specs):
                specs.append(("hood_cowl", "Neck/Head", [4, 5], "skinned_drape", 0.86))

        regions: List[AvatarCorrespondenceRegion] = []
        blockers: List[str] = []
        warnings: List[str] = []

        present_bones = set()
        if joint_indices is not None and joint_weights is not None and len(joint_indices) > 0:
            active = joint_weights > 0.05
            present_bones = set(int(b) for b in joint_indices[active].tolist())

        confs: List[float] = []
        for g_reg, a_reg, bones, mode, base_conf in specs:
            verified = bool(present_bones.intersection(bones)) if present_bones else False
            conf = base_conf if (not present_bones or verified) else round(base_conf * 0.72, 3)
            confs.append(conf)
            regions.append(AvatarCorrespondenceRegion(
                garment_region=g_reg,
                avatar_region=a_reg,
                target_bones=bones,
                confidence=conf,
                attachment_mode=mode,
                verified_against_mesh=verified,
            ))

        # Anatomical correspondence validation against actual coordinates + skinning
        if positions is not None and len(positions) > 0 and present_bones:
            import numpy as np
            pos = np.asarray(positions, dtype=np.float32)
            # Flag tops claiming bottoms bones primarily, or vice versa
            bottoms_bones = {14, 15, 16, 17, 18, 19}
            upper_bones = {3, 4, 6, 7, 8, 10, 11, 12}
            if lookup_key == "tops" and present_bones.issubset(bottoms_bones):
                blockers.append("Tops garment mapped exclusively to leg bones.")
            if lookup_key == "bottoms" and present_bones.issubset(upper_bones):
                blockers.append("Bottoms garment mapped exclusively to upper-torso/arm bones.")
            # Verify vertical span plausibility relative to avatar height
            min_y, max_y = float(np.min(pos[:, 1])), float(np.max(pos[:, 1]))
            if lookup_key == "headwear" and max_y < 1.35:
                warnings.append(f"Headwear max Y ({max_y:.2f}m) sits below Ara neck/head crown.")
            if lookup_key == "footwear" and min_y > 0.35:
                warnings.append(f"Footwear min Y ({min_y:.2f}m) sits above ankle ground zone.")

        mean_conf = round(float(sum(confs) / max(1, len(confs))), 3)
        if mean_conf < 0.50:
            blockers.append(f"Correspondence confidence too low ({mean_conf:.2f} < 0.50).")

        return SemanticAvatarCorrespondenceReport(
            category=cat_l,
            subcategory=sub_l,
            overall_confidence=mean_conf,
            is_valid=(len(blockers) == 0),
            regions=regions,
            blockers=blockers,
            warnings=warnings,
        )


semantic_correspondence_engine = SemanticCorrespondenceEngine()

