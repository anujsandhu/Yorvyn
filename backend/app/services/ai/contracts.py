"""
YORVYN — Canonical Garment Specification Contract (Phase 14.26)
Defines the authoritative canonical garment specification consumed by
UniversalConstructionGraph and ImageConditionedReconstructionEngine.
Strictly distinguishes between OBSERVED, INFERRED, UNKNOWN, and NOT_APPLICABLE evidence.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field
from backend.app.services.ai.base import EvidenceStatus, ModelMetadata
from backend.app.services.intelligence.component_taxonomy import (
    TAXONOMY_VERSION,
    VisibilityState,
    ComponentEvidenceStatus,
    DetectionState,
    ReconstructionDecision,
)


class GarmentItemEvidence(BaseModel):
    category: str = Field(..., description="Canonical category: hoodie, shirt, jacket, tshirt, etc.")
    subcategory: str = Field(..., description="Specific subcategory: pullover_hoodie, denim_jacket, etc.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Heuristic or model confidence score")
    evidence_status: EvidenceStatus = Field(default=EvidenceStatus.OBSERVED)
    direct_evidence_text: str = Field(default="", description="Visual features directly seen")


class ComponentDetail(BaseModel):
    name: str
    present: bool
    component_type: str = Field(default="standard", description="e.g. kangaroo, welt, long, crew, spread")
    confidence: float = Field(default=0.90, ge=0.0, le=1.0)
    evidence_status: EvidenceStatus = Field(default=EvidenceStatus.OBSERVED)
    bbox: Optional[Tuple[float, float, float, float]] = Field(default=None, description="(ymin, xmin, ymax, xmax) normalized")
    notes: str = Field(default="")


class AppearanceDetail(BaseModel):
    primary_color: str = "unknown"
    secondary_color: Optional[str] = None
    palette_hex: List[str] = Field(default_factory=list)
    pattern: str = "solid"
    fabric_appearance: str = "cotton"
    evidence_status: EvidenceStatus = Field(default=EvidenceStatus.OBSERVED)


class ImageQualityAssessment(BaseModel):
    image_usable: bool = True
    occlusion_detected: bool = False
    contrast_acceptable: bool = True
    ambiguity_notes: List[str] = Field(default_factory=list)


class GeometricEstimate(BaseModel):
    measurement_method: str = "aspect_ratio_contour_carving"
    scale_assumptions: str = "normalized_bounding_box"
    estimated_torso_aspect_ratio: float = 1.2
    sleeve_length_ratio: float = 1.0
    uncertainty_cm: float = 2.0
    evidence_status: EvidenceStatus = Field(default=EvidenceStatus.INFERRED)


class HandoffToReconstruction(BaseModel):
    target_dag_template: str = "hoodie_construction"
    enable_hood_mesh: bool = False
    enable_pocket_mesh: bool = False
    pocket_type: Optional[str] = None
    closure_geometry: str = "none"
    curved_hem: bool = False
    torso_fit_offset_cm: float = 2.0
    material_preset: str = "cotton_fleece_pbr"


class CanonicalGarmentSpecification(BaseModel):
    """
    Authoritative canonical contract uniting Gemini, Groq, Hugging Face,
    and Local CV models before handoff to 3D reconstruction.
    """
    garment_id: str
    garment: GarmentItemEvidence
    components: Dict[str, ComponentDetail] = Field(default_factory=dict)
    appearance: AppearanceDetail = Field(default_factory=AppearanceDetail)
    orientation: str = Field(default="front", description="front, back, side, angled")
    orientation_status: EvidenceStatus = Field(default=EvidenceStatus.OBSERVED)
    quality: ImageQualityAssessment = Field(default_factory=ImageQualityAssessment)
    geometry: GeometricEstimate = Field(default_factory=GeometricEstimate)
    reconstruction_handoff: HandoffToReconstruction = Field(default_factory=HandoffToReconstruction)
    provenance_chain: List[ModelMetadata] = Field(default_factory=list)
    model_execution_provenance: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    directly_visible_evidence: List[str] = Field(default_factory=list)
    inferred_properties: List[str] = Field(default_factory=list)
    unknown_unobservable_properties: List[str] = Field(default_factory=list)
    natural_language_explanation: str = Field(default="")
    total_pipeline_latency_ms: float = 0.0
    estimated_cost_usd: float = 0.0


# -----------------------------------------------------------------------------
# PHASE 14.27: Multi-View Evidence & Canonical Specification V2 Extensions
# -----------------------------------------------------------------------------

class PropertyEvidence(BaseModel):
    """Fine-grained evidence backing a specific garment property."""
    value: Any
    status: EvidenceStatus = Field(default=EvidenceStatus.OBSERVED)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source_image_ids: List[str] = Field(default_factory=list)
    source_provider: str = Field(default="local_cv")
    evidence_type: str = Field(default="direct_visual_detection")  # direct_visual_detection, heuristic_prior, rule_engine
    validation_status: str = Field(default="validated")  # validated, unvalidated, conflicted
    justification: str = Field(default="")


class MultiViewComponentDetail(BaseModel):
    """Component representation tracking presence, construction, and evidence across views."""
    name: str
    presence: PropertyEvidence
    component_type: PropertyEvidence
    bbox: Optional[Tuple[float, float, float, float]] = Field(default=None, description="(ymin, xmin, ymax, xmax) normalized")
    source_views: List[str] = Field(default_factory=list, description="front, back, left_side, right_side, detail, label")
    notes: str = Field(default="")


class ImageEvidenceRecord(BaseModel):
    """Metadata and classification for an uploaded viewpoint image."""
    image_id: str
    image_hash: str = Field(..., description="SHA-256 hash of image payload")
    perceptual_hash: Optional[str] = Field(default=None, description="64-bit difference hash used for near-duplicate screening")
    duplicate_of_image_id: Optional[str] = None
    duplicate_type: Optional[str] = None  # exact_bytes, perceptual_near_duplicate, crop_of_existing_view
    crop_of_image_id: Optional[str] = None
    counts_as_independent_view: bool = True
    view_type: str = Field(..., description="front, back, left_side, right_side, three_quarter, close_up, detail, label, unknown")
    view_assignment_source: str = "heuristic"  # heuristic, provided_hint
    user_view_hint: Optional[str] = None
    view_confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    quality_score: float = Field(default=0.90, ge=0.0, le=1.0)
    resolution: Tuple[int, int] = Field(default=(512, 512), description="(width, height)")
    usable: bool = True
    detected_features: List[str] = Field(default_factory=list)
    associated_garment_id: Optional[str] = None


class ConflictingObservation(BaseModel):
    """Preserves competing or contradictory visual observations across viewpoints."""
    attribute_name: str
    conflicting_views: List[str] = Field(default_factory=list)
    competing_values: List[Dict[str, Any]] = Field(default_factory=list)
    resolution_status: str = Field(default="UNRESOLVED_CONFLICT")  # RESOLVED, UNRESOLVED_CONFLICT
    winning_value: Optional[Any] = None
    resolution_rationale: str = Field(default="")


class ReconstructionReadiness(BaseModel):
    """Readiness assessment and geometric breakdown for 3D reconstruction handoff."""
    status: str = Field(default="PARTIAL", description="READY | PARTIAL | INSUFFICIENT_EVIDENCE | CONFLICTED")
    missing_evidence: List[str] = Field(default_factory=list)
    observed_geometry: List[str] = Field(default_factory=list)
    inferred_geometry: List[str] = Field(default_factory=list)
    unknown_geometry: List[str] = Field(default_factory=list)
    recommended_additional_views: List[str] = Field(default_factory=list)


class UncertaintyBreakdown(BaseModel):
    """First-class uncertainty representation distinct from raw confidence and completeness."""
    total_uncertainty: float = Field(..., ge=0.0, le=1.0)
    epistemic_uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    aleatoric_uncertainty: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    reasons: List[str] = Field(default_factory=list)


class ComponentObservation(BaseModel):
    """Single source-cited component observation from a specific view and image."""
    observation_id: str
    component_id: str
    component_type: str
    parent_component: Optional[str] = None
    garment_id: str
    garment_category: str
    garment_subcategory: str = ""
    side_or_orientation: Optional[str] = None
    source_image_id: str
    source_image_hash: str
    source_view: str
    bbox: Optional[Tuple[float, float, float, float]] = None
    segmentation_mask_ref: Optional[str] = None
    landmark_refs: List[str] = Field(default_factory=list)
    visibility_state: VisibilityState = VisibilityState.UNKNOWN
    detection_state: DetectionState = DetectionState.NOT_DETECTED
    evidence_status: ComponentEvidenceStatus = ComponentEvidenceStatus.NOT_OBSERVED
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    calibrated_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    uncertainty: UncertaintyBreakdown = Field(
        default_factory=lambda: UncertaintyBreakdown(total_uncertainty=1.0, epistemic_uncertainty=1.0)
    )
    model_id: str = "deterministic_cv_component_localizer"
    checkpoint_identity: str = "opencv-contour-sobel-v16.1"
    capability_id: str = "components.identify"
    execution_provenance: Dict[str, Any] = Field(default_factory=dict)
    processing_ms: float = 0.0


class FusedComponentAssessment(BaseModel):
    """Multi-view fused evidence for one garment component preserving contradictions and source links."""
    component_id: str
    component_type: str
    parent_component: Optional[str] = None
    side_or_orientation: Optional[str] = None
    garment_category: str
    garment_subcategory: str = ""
    detection_state: DetectionState
    evidence_status: ComponentEvidenceStatus
    visibility_by_view: Dict[str, VisibilityState] = Field(default_factory=dict)
    best_visibility: VisibilityState = VisibilityState.UNKNOWN
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    calibrated_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    uncertainty: UncertaintyBreakdown
    evidence_completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    agreement_score: float = Field(default=1.0, ge=0.0, le=1.0)
    contradicted: bool = False
    contradiction_notes: List[str] = Field(default_factory=list)
    source_image_ids: List[str] = Field(default_factory=list)
    source_image_hashes: List[str] = Field(default_factory=list)
    source_views: List[str] = Field(default_factory=list)
    observation_ids: List[str] = Field(default_factory=list)
    observations: List[ComponentObservation] = Field(default_factory=list)
    localized_bbox: Optional[Tuple[float, float, float, float]] = None
    segmentation_mask_ref: Optional[str] = None
    landmark_refs: List[str] = Field(default_factory=list)
    downstream_decision: ReconstructionDecision = ReconstructionDecision.DO_NOT_INFER
    decision_rationale: str = ""


class StructureGraphNode(BaseModel):
    node_id: str
    component_id: str
    component_type: str
    side_or_orientation: Optional[str] = None
    visibility_state: VisibilityState
    detection_state: DetectionState
    evidence_status: ComponentEvidenceStatus
    confidence: Optional[float] = None
    uncertainty: float = 1.0
    contradicted: bool = False
    downstream_decision: ReconstructionDecision = ReconstructionDecision.DO_NOT_INFER
    source_image_ids: List[str] = Field(default_factory=list)
    source_views: List[str] = Field(default_factory=list)
    observation_ids: List[str] = Field(default_factory=list)


class StructureGraphEdge(BaseModel):
    edge_id: str
    source_node: str
    target_node: str
    relation: str  # ATTACHED_TO | PART_OF | CONNECTED_TO | OVERLAPS | SYMMETRIC_WITH | ADJACENT_TO | SUPPORTED_BY_VIEW
    evidence_status: ComponentEvidenceStatus = ComponentEvidenceStatus.NOT_OBSERVED
    confidence: Optional[float] = None
    uncertainty: float = 1.0
    source_image_ids: List[str] = Field(default_factory=list)
    contradicted: bool = False
    notes: str = ""


class GarmentStructureGraphContract(BaseModel):
    taxonomy_version: str = TAXONOMY_VERSION
    garment_id: str
    category: str
    subcategory: str = ""
    nodes: List[StructureGraphNode] = Field(default_factory=list)
    edges: List[StructureGraphEdge] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)


class ComponentHandoffDecisionItem(BaseModel):
    component_id: str
    component_type: str
    decision: ReconstructionDecision
    evidence_status: ComponentEvidenceStatus
    visibility_state: VisibilityState
    detection_state: DetectionState
    confidence: Optional[float] = None
    uncertainty: float = 1.0
    evidence_completeness: float = 0.0
    source_image_ids: List[str] = Field(default_factory=list)
    bbox: Optional[Tuple[float, float, float, float]] = None
    notes: str = ""


class ComponentHandoffContract(BaseModel):
    schema_version: str = "16.1"
    taxonomy_version: str = TAXONOMY_VERSION
    garment_id: str
    category: str
    subcategory: str = ""
    components: Dict[str, ComponentHandoffDecisionItem] = Field(default_factory=dict)
    safe_components: List[str] = Field(default_factory=list)
    uncertain_components: List[str] = Field(default_factory=list)
    more_evidence_components: List[str] = Field(default_factory=list)
    blocked_components: List[str] = Field(default_factory=list)
    clarification_prompts: List[str] = Field(default_factory=list)


class ComponentAnalysisBundle(BaseModel):
    """Unified return object for analyze_garment_components()."""
    taxonomy_version: str = TAXONOMY_VERSION
    garment_id: str
    category: str
    subcategory: str = ""
    views_analyzed: List[ImageEvidenceRecord] = Field(default_factory=list)
    observations: List[ComponentObservation] = Field(default_factory=list)
    fused_components: Dict[str, FusedComponentAssessment] = Field(default_factory=dict)
    structure_graph: GarmentStructureGraphContract
    handoff: ComponentHandoffContract
    landmarks: Dict[str, Tuple[float, float]] = Field(default_factory=dict)
    per_image_timing_ms: Dict[str, float] = Field(default_factory=dict)
    total_latency_ms: float = 0.0
    cache_hits: int = 0
    warnings: List[str] = Field(default_factory=list)


class CanonicalGarmentSpecificationV2(CanonicalGarmentSpecification):
    """
    Phase 14.27 / Phase 16.1 Multi-View Canonical Specification.
    Strictly preserves backward-compatibility with Phase 14.26 & Phase 16.0 consumers
    while adding multi-view component evidence, visibility, uncertainty, and structure graph.
    """
    specification_version: str = "2.0"
    taxonomy_version: str = TAXONOMY_VERSION
    views: List[ImageEvidenceRecord] = Field(default_factory=list)
    conflicts: List[ConflictingObservation] = Field(default_factory=list)
    reconstruction_readiness: ReconstructionReadiness = Field(default_factory=ReconstructionReadiness)
    v2_components: Dict[str, MultiViewComponentDetail] = Field(default_factory=dict)
    property_evidence: Dict[str, PropertyEvidence] = Field(default_factory=dict)
    component_observations: List[ComponentObservation] = Field(default_factory=list)
    fused_components: Dict[str, FusedComponentAssessment] = Field(default_factory=dict)
    structure_graph: Optional[GarmentStructureGraphContract] = None
    component_handoff: Optional[ComponentHandoffContract] = None
    clarification_prompts: List[str] = Field(default_factory=list)

    def validate_evidence_integrity(self) -> List[str]:
        """
        Validates forensic evidence integrity:
        1. OBSERVED properties must cite at least one valid source image.
        2. INFERRED properties must document an inference source.
        3. UNKNOWN properties must not carry fabricated confidence scores.
        4. CONFLICTED properties must record competing observation details.
        5. Component observations must reference valid view hashes and valid normalized boxes.
        Returns a list of validation failure descriptions (empty if valid).
        """
        errors = []
        image_by_id = {view.image_id: view for view in self.views}
        if len(image_by_id) != len(self.views):
            errors.append("Image evidence contains duplicate image_id values.")
        hashes = [view.image_hash for view in self.views if view.usable]
        if len(set(hashes)) != len(hashes):
            errors.append("Image evidence contains duplicate image hashes; duplicate images must be deduplicated before fusion.")

        def validate_property(prop_name: str, prop: PropertyEvidence) -> None:
            unknown_sources = [source_id for source_id in prop.source_image_ids if source_id not in image_by_id]
            if unknown_sources:
                errors.append(f"Property '{prop_name}' references unknown image IDs: {unknown_sources}.")
            unusable_sources = [
                source_id for source_id in prop.source_image_ids
                if source_id in image_by_id and not image_by_id[source_id].usable
                and image_by_id[source_id].duplicate_type != "crop_of_existing_view"
            ]
            if unusable_sources:
                errors.append(f"Property '{prop_name}' cites unusable source images: {unusable_sources}.")
            if prop.status == EvidenceStatus.OBSERVED and not prop.source_image_ids:
                errors.append(f"Property '{prop_name}' is OBSERVED but has no source_image_ids.")
            if prop.status == EvidenceStatus.INFERRED and not prop.justification.strip():
                errors.append(f"Property '{prop_name}' is INFERRED but has no inference justification.")
            if prop.status == EvidenceStatus.UNKNOWN and prop.confidence not in (None, 0.0):
                errors.append(f"Property '{prop_name}' is UNKNOWN but carries fabricated confidence {prop.confidence}.")
            if prop.status == EvidenceStatus.CONFLICTED:
                matching = [c for c in self.conflicts if c.attribute_name == prop_name]
                if not matching:
                    errors.append(f"Property '{prop_name}' marked CONFLICTED without corresponding conflict record.")
                elif not any(len(c.competing_values) >= 2 for c in matching):
                    errors.append(f"Property '{prop_name}' is CONFLICTED without at least two recorded competing values.")
            if prop.validation_status == "validated" and prop.status in (EvidenceStatus.OBSERVED, EvidenceStatus.INFERRED) and not prop.source_provider.strip():
                errors.append(f"Property '{prop_name}' is marked validated but has no source_provider.")

        for prop_name, prop in self.property_evidence.items():
            validate_property(prop_name, prop)
        for component_name, component in self.v2_components.items():
            validate_property(f"{component_name}.presence", component.presence)
            validate_property(f"{component_name}.component_type", component.component_type)
            if component.bbox is not None:
                ymin, xmin, ymax, xmax = component.bbox
                if not (0.0 <= ymin < ymax <= 1.0 and 0.0 <= xmin < xmax <= 1.0):
                    errors.append(f"Component '{component_name}' has an invalid normalized bounding box.")
        for obs in self.component_observations:
            if obs.source_image_id not in image_by_id:
                errors.append(f"Component observation '{obs.observation_id}' references unknown image ID '{obs.source_image_id}'.")
            elif image_by_id[obs.source_image_id].image_hash != obs.source_image_hash:
                errors.append(f"Component observation '{obs.observation_id}' image_hash mismatch with view '{obs.source_image_id}'.")
            if obs.bbox is not None:
                ymin, xmin, ymax, xmax = obs.bbox
                if not (0.0 <= ymin < ymax <= 1.0 and 0.0 <= xmin < xmax <= 1.0):
                    errors.append(f"Component observation '{obs.observation_id}' has invalid normalized bbox {obs.bbox}.")
        return errors

