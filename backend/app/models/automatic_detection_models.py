"""
YORVYN — Automatic AI Garment Detection Models
Pydantic schemas for AI-first automatic clothing perception without manual user configuration.
Captures garment identity, fabric intelligence, appearance, fit silhouette, structural components,
multi-view observations, confidence, uncertainty, and separate user correction tracking.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class GarmentIdentityDetection(BaseModel):
    """Detected core garment classification and construction style."""
    main_category: str = Field(..., description="Top-level clothing category (tops, bottoms, outerwear, footwear, etc.)")
    subcategory: str = Field(..., description="Fine-grained subcategory (hoodie, tshirt, jeans, formal_shirt, etc.)")
    display_name: str = Field(..., description="Human-readable title (e.g., Oversized Pullover Hoodie)")
    garment_type: str = Field("pullover", description="Garment construction type (pullover, zip-up, button-down, etc.)")
    construction_style: str = Field("cut_and_sewn", description="Manufacturing style (cut_and_sewn, fully_fashioned_knit, tailored_woven)")
    gender_neutral_classification: str = Field("unisex_casual", description="Gender-neutral garment classification")
    confidence: float = Field(..., ge=0.0, le=1.0)
    status: str = Field("detected", description="detected, estimated, inferred, not_detected, needs_another_photograph")
    uncertainty_status: str = Field("CONFIDENT", description="CONFIDENT, LOW_CONFIDENCE, AMBIGUOUS, UNSUPPORTED")
    original_prediction: Dict[str, Any] = Field(default_factory=dict)
    reasoning_signals: List[str] = Field(default_factory=list)
    rejected_alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    model_prediction: Optional[Dict[str, Any]] = None
    model_confidence: Optional[float] = None
    model_probabilities: Optional[Dict[str, float]] = None
    rule_hypothesis: Optional[Dict[str, Any]] = None
    rule_confidence: Optional[float] = None
    final_prediction: Optional[Dict[str, Any]] = None
    final_confidence: Optional[float] = None
    decision_reason: Optional[str] = None


class FabricIntelligenceDetection(BaseModel):
    """Detected fabric textile family, construction, texture, and visual drape."""
    fabric_family: str = Field(..., description="Textile family (fleece, jersey, denim, wool, silk, leather, etc.)")
    estimated_composition: str = Field(
        ...,
        description="Visual estimation of composition (e.g. 'Visually identified cotton-like fleece; exact fibre ratio unconfirmed from photo')"
    )
    construction: str = Field("knit", description="knit, woven, or non-woven")
    weight_category: str = Field("midweight", description="lightweight, midweight, heavyweight")
    surface_texture: str = Field("brushed_fleece", description="Surface texture / weave pattern")
    stretch_characteristics: str = Field("moderate_mechanical_stretch", description="Stretch behavior")
    transparency: str = Field("opaque", description="opaque, semi-sheer, sheer")
    surface_roughness: float = Field(0.80, ge=0.0, le=1.0)
    surface_metalness: float = Field(0.02, ge=0.0, le=1.0)
    fabric_drape: str = Field("relaxed_heavy_drape", description="Visual drape description")
    confidence: float = Field(..., ge=0.0, le=1.0)
    status: str = Field("estimated", description="detected, estimated, inferred, not_detected, needs_another_photograph")
    composition_disclaimer: str = Field(
        "Never claim exact fibre composition from a photograph alone. Composition is visually estimated from surface texture.",
        description="Strict physical disclaimer"
    )


class ColourAndAppearanceDetection(BaseModel):
    """Detected primary/secondary colors, palette, patterns, and visible graphics."""
    primary_colour: str = Field(..., description="Primary color name (e.g. Dark chocolate brown)")
    primary_hex: str = Field(..., description="Hex color code (e.g. #342b2b)")
    secondary_colours: List[str] = Field(default_factory=list)
    palette: List[str] = Field(default_factory=list)
    colour_distribution: Dict[str, float] = Field(default_factory=dict)
    patterns: str = Field("solid", description="Pattern type (solid, stripes, plaid, graphic_print, etc.)")
    has_graphics: bool = False
    graphic_details: Optional[str] = None
    surface_details: List[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    status: str = Field("detected", description="detected, estimated, inferred, not_detected, needs_another_photograph")


class FitAndSilhouetteDetection(BaseModel):
    """Detected garment silhouette and wearer fit disclaimer."""
    detected_silhouette: str = Field("oversized", description="Garment cut (slim, regular, relaxed, oversized, cropped, longline)")
    silhouette_confidence: float = Field(..., ge=0.0, le=1.0)
    status: str = Field("estimated", description="detected, estimated, inferred, not_detected, needs_another_photograph")
    wearer_fit_disclaimer: str = Field(
        "Garment silhouette reflects product cut. Actual wearer fit depends on individual avatar proportions.",
        description="Distinguishes garment silhouette from wearer fit"
    )


class ComponentStatusItem(BaseModel):
    """Individual structural component with presence status and confidence."""
    name: str
    component_type: str
    status: str = Field(..., description="detected, estimated, inferred, not_detected, needs_another_photograph")
    confidence: float = Field(..., ge=0.0, le=1.0)
    provenance: str = Field("observed", description="observed, inferred_symmetry, procedural")
    notes: Optional[str] = None


class ViewObservationSummary(BaseModel):
    """Multi-view observation status for a specific photograph angle."""
    view_type: str  # front, back, side, detail
    supplied: bool
    observed: bool = False
    confidence: float = 0.0
    status: str = "Not supplied"
    is_duplicate: bool = False
    identity_match: Optional[bool] = None
    similarity_score: Optional[float] = None
    warning: Optional[str] = None


class UserCorrectionRecord(BaseModel):
    """Audit record capturing original model predictions vs optional user corrections."""
    original_prediction: Dict[str, Any] = Field(default_factory=dict)
    prediction_confidence: float = 0.0
    user_correction: Optional[Dict[str, Any]] = None
    final_reconstruction_input: Dict[str, Any] = Field(default_factory=dict)
    corrected_at: Optional[str] = None
    is_user_corrected: bool = False

    # Continuous Learning & Provenance Extension
    model_name: str = "universal_garment_classifier"
    model_version: str = "v1.0.0"
    inference_id: str = Field(default_factory=lambda: "")
    session_id: Optional[str] = None
    search_id: Optional[str] = None
    feedback_id: Optional[str] = None
    dataset_eligibility: str = "pending"
    validation_status: str = "pending"
    consent_scope: str = "none"
    correction_timestamp: Optional[str] = None


class GarmentLearningEvent(str):
    CATEGORY_CORRECTION = "category_correction"
    SUBCATEGORY_CORRECTION = "subcategory_correction"
    FABRIC_CORRECTION = "fabric_correction"
    COLOUR_CORRECTION = "colour_correction"
    SILHOUETTE_CORRECTION = "silhouette_correction"
    COMPONENT_CORRECTION = "component_correction"
    SEGMENTATION_CORRECTION = "segmentation_correction"
    MULTIVIEW_RESOLUTION = "multiview_resolution"
    RECONSTRUCTION_ACCEPTANCE = "reconstruction_acceptance"
    RECONSTRUCTION_REJECTION = "reconstruction_rejection"
    RECONSTRUCTION_EDIT = "reconstruction_edit"
    RECONSTRUCTION_MISMATCH = "reconstruction_mismatch"


class GarmentFeedbackSubmissionRequest(BaseModel):
    """Structured feedback submission for AI garment detection & reconstruction."""
    inference_id: str
    analysis_id: Optional[str] = None
    job_id: Optional[str] = None
    session_id: Optional[str] = None
    search_id: Optional[str] = None
    event_type: str = Field(..., description="One of GarmentLearningEvent types")
    original_value: Optional[Any] = None
    corrected_value: Optional[Any] = None
    feedback_text: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    is_visual_correction: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AutomaticGarmentDetectionResult(BaseModel):
    """
    Unified result of automatic AI garment perception.
    Provides complete automated configuration for 3D reconstruction without manual user inputs.
    """
    model_config = ConfigDict(protected_namespaces=())

    analysis_id: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    # Core Intelligence Sections
    garment_identity: GarmentIdentityDetection
    fabric_intelligence: FabricIntelligenceDetection
    colour_and_appearance: ColourAndAppearanceDetection
    fit_and_silhouette: FitAndSilhouetteDetection
    components: List[ComponentStatusItem] = Field(default_factory=list)

    # Multi-View Telemetry
    views_summary: Dict[str, ViewObservationSummary] = Field(default_factory=dict)

    # Provenance and Model Telemetry
    model_id: str = "yorvyn-neural-garment-intelligence-v2"
    inference_latency_ms: float = 0.0
    device_used: str = "cpu"
    quality_score: float = 1.0
    uncertainty_status: str = Field("CONFIDENT", description="CONFIDENT, LOW_CONFIDENCE, AMBIGUOUS, UNSUPPORTED")
    classification_version: str = Field("3.0.0-generalized", description="Taxonomy and classifier version")
    candidate_hypotheses: List[Dict[str, Any]] = Field(default_factory=list)

    # Multi-Garment Instance Telemetry (Phase 14.2)
    detected_instances: List[Dict[str, Any]] = Field(default_factory=list, description="All detected garment instances in multi-garment scenes")
    selected_instance_id: Optional[str] = Field(None, description="Currently selected instance ID for 3D virtual try-on")

    # User Correction Audit Tracking
    user_correction_state: UserCorrectionRecord = Field(default_factory=UserCorrectionRecord)

