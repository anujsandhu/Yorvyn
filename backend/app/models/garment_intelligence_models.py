"""
YORVYN — Garment Intelligence V2 Schema
Defines versioned, structured intelligence representations for AI Garment Understanding,
including multi-model segmentation, taxonomy classification, component localization,
anatomical landmarks, quality assessment, and diagnostics.
"""

from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class BoundingBox2D(BaseModel):
    """Normalized bounding box coordinates in [0.0, 1.0] range."""
    ymin: float = Field(..., ge=0.0, le=1.0)
    xmin: float = Field(..., ge=0.0, le=1.0)
    ymax: float = Field(..., ge=0.0, le=1.0)
    xmax: float = Field(..., ge=0.0, le=1.0)

    @property
    def width(self) -> float:
        return max(0.0, self.xmax - self.xmin)

    @property
    def height(self) -> float:
        return max(0.0, self.ymax - self.ymin)

    @property
    def area(self) -> float:
        return self.width * self.height


class Point2D(BaseModel):
    """Normalized 2D point coordinates in [0.0, 1.0] range."""
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)


class GarmentLandmarkV2(BaseModel):
    """Anatomical garment landmark keypoint."""
    name: str
    position: Point2D
    confidence: float = Field(..., ge=0.0, le=1.0)
    visibility: str = "visible"  # visible, occluded, inferred


class GarmentComponentV2(BaseModel):
    """Category-specific garment component with spatial bounding and provenance."""
    name: str
    component_type: str
    bbox: Optional[BoundingBox2D] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    status: str = "detected"  # detected, not_detected, unknown
    provenance: str = "observed"  # observed, inferred, procedural
    attributes: Dict[str, Any] = Field(default_factory=dict)


class GarmentCategoryProbability(BaseModel):
    """Calibrated probability score for a specific category/subcategory candidate."""
    category: str
    subcategory: str
    calibrated_probability: float = Field(..., ge=0.0, le=1.0)
    display_name: str


class ImageQualityMetrics(BaseModel):
    """Photographic quality assessment metrics."""
    width: int
    height: int
    laplacian_blur_score: float
    is_blurry: bool
    contrast_score: float
    exposure_level: str  # balanced, underexposed, overexposed
    cropping_score: float  # 0.0 (good) to 1.0 (severely cropped at image border)


class SegmentationMetrics(BaseModel):
    """Silhouette isolation and geometric boundary quality metrics."""
    silhouette_quality: float = Field(..., ge=0.0, le=1.0)
    boundary_sharpness: float
    compactness: float
    hole_count: int
    outer_contour_point_count: int
    processing_time_ms: float
    model_id: str
    model_version: str


class ViewAnalysisResult(BaseModel):
    """Multi-view understanding and perspective classification."""
    view_type: str  # front, back, left_side, right_side, detail_macro
    confidence: float = Field(..., ge=0.0, le=1.0)
    is_duplicate: bool = False
    identity_match_with_front: Optional[bool] = None
    similarity_score_with_front: Optional[float] = None


class GarmentIntelligenceV2Result(BaseModel):
    """
    Standardized, canonical garment intelligence result (v2.0).
    Directly parameterizes 3D mesh building, PBR texture synthesis, and avatar drape.
    """
    model_config = ConfigDict(protected_namespaces=())

    job_id: str
    schema_version: str = "2.0.0"

    # Taxonomy Classification
    category: str
    subcategory: str
    display_name: str
    category_confidence: float = Field(..., ge=0.0, le=1.0)
    requires_confirmation: bool = False
    candidate_categories: List[GarmentCategoryProbability] = Field(default_factory=list)

    # Phase 12.3: Uncertainty, Provenance & Reasoning Telemetry
    uncertainty_status: str = "CONFIDENT"  # CONFIDENT, LOW_CONFIDENCE, AMBIGUOUS, UNSUPPORTED
    original_prediction: Dict[str, Any] = Field(default_factory=dict)
    heuristic_adjustments: List[Dict[str, Any]] = Field(default_factory=list)
    reasoning_signals: List[str] = Field(default_factory=list)
    rejected_alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    classification_version: str = "3.0.0-generalized"

    # Phase 13.9: Learned vs Rule Model Separation
    model_prediction: Optional[Dict[str, Any]] = None
    model_confidence: Optional[float] = None
    model_probabilities: Optional[Dict[str, float]] = None
    rule_hypothesis: Optional[Dict[str, Any]] = None
    rule_confidence: Optional[float] = None
    final_prediction: Optional[Dict[str, Any]] = None
    final_confidence: Optional[float] = None
    decision_reason: Optional[str] = None

    # Spatial Components & Landmarks
    components: List[GarmentComponentV2] = Field(default_factory=list)
    landmarks: Dict[str, GarmentLandmarkV2] = Field(default_factory=dict)

    # Stylistic, Color & Material Attributes
    primary_color_name: str
    primary_color_hex: str
    secondary_color_name: Optional[str] = None
    secondary_color_hex: Optional[str] = None
    palette: List[str] = Field(default_factory=list)
    pattern: str = "solid"
    material_hint: str = "cotton"
    fit: str = "regular"
    neckline_type: str = "crewneck"
    sleeve_length: str = "short"
    hem_length: str = "standard"
    closure_type: str = "pullover"
    formality: int = 4
    warmth: int = 4

    # Visual Semantic Embedding (64-dimensional normalized vector)
    semantic_embedding: List[float] = Field(default_factory=list)

    # Phase 11B: On-Body & Human Parsing Telemetry
    image_type: str = "isolated_product"
    occlusion_ratio: float = 0.0
    visible_surface_ratio: float = 1.0
    inferred_surface_ratio: float = 0.0
    detected_body_parts: Dict[str, float] = Field(default_factory=dict)

    # Quality & Segmentation Telemetry
    quality_metrics: ImageQualityMetrics
    segmentation_metrics: SegmentationMetrics

    # Multi-view consistency
    views: Dict[str, ViewAnalysisResult] = Field(default_factory=dict)

    # Provenance and telemetry
    warnings: List[str] = Field(default_factory=list)
    model_provenance: Dict[str, str] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class FabricPBRPropertiesV2(BaseModel):
    """Physically based rendering material properties for garment textiles."""
    fabric_category: str  # cotton, denim, leather, wool, silk, satin, knitwear, synthetic, linen
    surface_texture: str  # plain_weave, twill_diagonal, ribbed_knit, cable_knit, smooth_sheen, pebble_leather, canvas
    roughness: float = Field(..., ge=0.0, le=1.0)
    metalness: float = Field(..., ge=0.0, le=1.0)
    sheen: float = Field(0.0, ge=0.0, le=1.0)
    clearcoat: float = Field(0.0, ge=0.0, le=1.0)
    normal_strength: float = Field(1.0, ge=0.0, le=3.0)
    is_estimated: bool = True
    confidence: float = Field(..., ge=0.0, le=1.0)


class GraphicPrintPlacementV2(BaseModel):
    """Detected graphic or text print placement and dimensions."""
    detected: bool = False
    bbox: Optional[BoundingBox2D] = None
    target_region: str = "chest"  # chest, back, left_sleeve, right_sleeve, hem
    contrast_ratio: float = 1.0
    aspect_ratio: float = 1.0
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class HardwareElementV2(BaseModel):
    """Detected structural hardware (buttons, zippers, eyelets, snaps)."""
    hardware_type: str  # button, zipper, metal_eyelet, buckle, drawstring_aglet
    count: int = 1
    location: str  # front_placket, waistband, collar, pocket
    metalness: float = 0.90
    roughness: float = 0.25
    confidence: float = Field(..., ge=0.0, le=1.0)


class GarmentAppearanceResultV2(BaseModel):
    """
    Standardized, canonical garment appearance intelligence representation (v2.0).
    Directly drives PBR texture synthesis, UV projection, and material configuration.
    """
    model_config = ConfigDict(protected_namespaces=())

    job_id: str
    primary_color_hex: str
    primary_color_name: str
    secondary_color_hex: Optional[str] = None
    secondary_color_name: Optional[str] = None
    palette: List[str] = Field(default_factory=list)
    color_distribution: Dict[str, float] = Field(default_factory=dict)
    is_color_blocked: bool = False
    pattern_type: str = "solid"  # solid, stripes_vertical, stripes_horizontal, checks_plaid, floral, geometric, graphic_print
    pattern_confidence: float = Field(0.85, ge=0.0, le=1.0)
    fabric: FabricPBRPropertiesV2
    graphic: GraphicPrintPlacementV2
    hardware: List[HardwareElementV2] = Field(default_factory=list)
    has_contrast_stitching: bool = False
    stitching_color_hex: Optional[str] = None
    observed_front_surface_ratio: float = 0.95
    inferred_rear_surface_ratio: float = 0.05
    provenance: str = "observed_front_inferred_rear"
    analysis_time_ms: float = 0.0


class GarmentDiagnosticsV2(BaseModel):
    """Comprehensive diagnostic payload for inspection UI."""
    model_config = ConfigDict(protected_namespaces=())

    job_id: str
    schema_version: str = "2.0.0"
    intelligence: GarmentIntelligenceV2Result
    alpha_mask_data_url: Optional[str] = None
    segmented_preview_data_url: Optional[str] = None
    outer_contour_polygon: List[List[float]] = Field(default_factory=list)
    holes_polygons: List[List[List[float]]] = Field(default_factory=list)
    pipeline_stage_latencies_ms: Dict[str, float] = Field(default_factory=dict)
    mesh_telemetry: Optional[Dict[str, Any]] = None
    appearance_telemetry: Optional[Dict[str, Any]] = None
    diffuse_preview_data_url: Optional[str] = None
    normal_preview_data_url: Optional[str] = None
    roughness_preview_data_url: Optional[str] = None
    uv_layout_preview_data_url: Optional[str] = None
    fitting_telemetry: Optional[Dict[str, Any]] = None
    motion_telemetry: Optional[Dict[str, Any]] = None
    wrinkle_telemetry: Optional[Dict[str, Any]] = None
    reliability_assessment: Optional[Dict[str, Any]] = None
    audit_telemetry: Optional[Dict[str, Any]] = None
    human_parsing_preview_data_url: Optional[str] = None
    occlusion_preview_data_url: Optional[str] = None
    garment_crop_preview_data_url: Optional[str] = None
    on_body_telemetry: Optional[Dict[str, Any]] = None


class AvatarMeasurementsV2(BaseModel):
    """Anatomical human body measurements for avatar-aware garment fitting (Phase 5)."""
    model_config = ConfigDict(protected_namespaces=())

    profile_id: str = "standard_175"
    display_name: str = "Standard Adult (1.75m)"
    height_cm: float = 175.0
    shoulder_width_cm: float = 43.5
    chest_circumference_cm: float = 96.0
    waist_circumference_cm: float = 78.0
    hip_circumference_cm: float = 98.0
    neck_circumference_cm: float = 38.0
    arm_length_cm: float = 60.0
    upper_arm_circumference_cm: float = 30.0
    wrist_circumference_cm: float = 17.0
    inseam_cm: float = 78.0
    thigh_circumference_cm: float = 54.0
    calf_circumference_cm: float = 36.0
    foot_length_cm: float = 26.5
    foot_width_cm: float = 9.8
    unit: str = "cm"


class GarmentEaseAnalysisV2(BaseModel):
    """Calculated ease dimensions and fit classification."""
    fit_classification: str = "regular"  # slim, regular, relaxed, oversized, compression
    chest_ease_cm: float = 6.0
    waist_ease_cm: float = 6.0
    hip_ease_cm: float = 6.0
    shoulder_ease_cm: float = 2.0
    inseam_ease_cm: float = 0.0
    is_negative_ease: bool = False
    segment_scale_factors: Dict[str, float] = Field(default_factory=dict)


class CollisionMetricsV2(BaseModel):
    """Garment-to-avatar and self-collision diagnostics."""
    penetration_count: int = 0
    initial_penetration_count: int = 0
    resolved_penetration_count: int = 0
    penetration_ratio: float = 0.0
    max_penetration_mm: float = 0.0
    average_clearance_mm: float = 3.2
    self_intersection_count: int = 0
    is_collision_free: bool = True
    min_clearance_guaranteed_mm: float = 3.0


class ClothPhysicsMetricsV2(BaseModel):
    """PBD cloth simulation parameters and convergence telemetry."""
    fabric_preset: str = "cotton"
    mass_g_m2: float = 220.0
    stretch_stiffness: float = 0.88
    bending_stiffness: float = 0.42
    shear_stiffness: float = 0.60
    damping: float = 0.93
    thickness_mm: float = 2.5
    air_resistance: float = 0.05
    recovery_rate: float = 0.95
    elasticity_limit: float = 1.30
    simulation_iterations: int = 15
    convergence_score: float = 0.96
    simulation_status: str = "converged"


class WrinkleDeformationMetricsV2(BaseModel):
    """Dynamic strain analysis and wrinkle/fold generation telemetry (Phase 6)."""
    model_config = ConfigDict(protected_namespaces=())

    compression_vertex_ratio: float = 0.15
    tension_vertex_ratio: float = 0.25
    max_strain: float = 0.08
    min_strain: float = -0.12
    wrinkle_amplitude_mm: float = 3.5
    wrinkle_wavelength_mm: float = 24.0
    recovery_rate: float = 0.92
    generated_fold_count: int = 18
    is_strain_balanced: bool = True


class MotionSequenceSimulationMetricsV2(BaseModel):
    """Continuous motion-aware simulation metrics across motion cycles (Phase 6)."""
    model_config = ConfigDict(protected_namespaces=())

    sequence_names: List[str] = Field(default_factory=lambda: [
        "idle", "walking", "running", "arm_raising", "arm_bending",
        "sitting", "squatting", "forward_bending", "turning", "jumping"
    ])
    total_simulated_frames: int = 120
    mean_frame_time_ms: float = 4.2
    max_frame_time_ms: float = 8.6
    kinetic_energy_stable: bool = True
    mean_constraint_error_mm: float = 0.18
    max_penetration_during_motion_mm: float = 0.0
    residual_motion_penetrations: int = 0
    motion_stability_score: float = 0.97
    frame_rate_fps: float = 60.0
    dynamic_collision_clearance_mm: float = 3.8


class AnimationDeformationMetricsV2(BaseModel):
    """Rigged skeletal deformation telemetry across canonical animation poses."""
    tested_poses: List[str] = Field(default_factory=lambda: ["idle", "walking", "arm_raising", "arm_bending", "sitting", "squatting"])
    max_vertex_displacement_mm: float = 12.5
    normal_inversion_count: int = 0
    motion_penetration_count: int = 0
    deformation_stability_score: float = 0.98
    skinning_compliance_20_bones: bool = True


class GarmentFittingResultV2(BaseModel):
    """Comprehensive avatar-aware garment fitting and physics simulation result."""
    model_config = ConfigDict(protected_namespaces=())

    job_id: str
    category: str
    subcategory: str
    avatar_measurements: AvatarMeasurementsV2
    ease_analysis: GarmentEaseAnalysisV2
    collision: CollisionMetricsV2
    physics: ClothPhysicsMetricsV2
    animation_deformation: AnimationDeformationMetricsV2
    motion_simulation: Optional[MotionSequenceSimulationMetricsV2] = None
    wrinkle_deformation: Optional[WrinkleDeformationMetricsV2] = None
    anchor_points: Dict[str, List[float]] = Field(default_factory=dict)
    fitting_time_ms: float = 0.0
    warnings: List[str] = Field(default_factory=list)


