"""
YORVYN — Structured Garment Specification Contract (Phase 14.24-F)
Defines strongly-typed schemas for multimodal local garment identification:
- 15 Standard Garment Categories and fine-grained subcategories
- Component spatial bounds, segmentation provenance, and area fractions
- Visual attributes: colors, patterns, fit, sleeve length, collar, closure, pockets, cuffs, hem
- Explicit uncertainty analysis: entropy, margin, low-contrast, occlusion, model disagreement
- Multi-model execution provenance: device, latency, peak memory, model tags
- Deterministic 3D reconstruction handoff parameters
"""

from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field


class GarmentCategory(str, Enum):
    TSHIRT = "tshirt"
    SHIRT = "shirt"
    HOODIE = "hoodie"
    SWEATSHIRT = "sweatshirt"
    SWEATER = "sweater"
    JACKET = "jacket"
    COAT = "coat"
    DRESS = "dress"
    KURTA = "kurta"
    TUNIC = "tunic"
    JEANS = "jeans"
    TROUSERS = "trousers"
    SHORTS = "shorts"
    SKIRT = "skirt"
    TRADITIONAL_CLOTHING = "traditional_clothing"


class ComponentLocation(BaseModel):
    name: str = Field(..., description="Canonical component name (e.g. hood, left_sleeve, torso, kangaroo_pocket)")
    bbox: Tuple[float, float, float, float] = Field(..., description="(ymin, xmin, ymax, xmax) normalized in [0.0, 1.0]")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    area_fraction: float = Field(default=0.0, ge=0.0, le=1.0, description="Fraction of total silhouette area")
    source_model: str = Field(default="grounded_sam2", description="Model producing localization")
    prompt_used: str = Field(default="", description="Text prompt conditioned on")


class GarmentVisualAttributes(BaseModel):
    primary_color: str = Field(default="unknown")
    secondary_color: Optional[str] = Field(default=None)
    palette_hex: List[str] = Field(default_factory=list)
    pattern: str = Field(default="solid", description="solid, striped, plaid, graphic, floral, cable_knit, checkered")
    pattern_confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    fit: str = Field(default="regular", description="regular, oversized, slim, relaxed, loose")
    sleeve_type: str = Field(default="long_sleeve", description="long_sleeve, short_sleeve, sleeveless, raglan, drop_shoulder")
    neckline: str = Field(default="crew_neck", description="crew_neck, v_neck, hooded, mandarin, collared, scoop, turtle_neck")
    collar: Optional[str] = Field(default=None, description="button_down, spread, mandarin, ribbed, none")
    closure: str = Field(default="pullover", description="pullover, front_zipper, full_button_placket, half_zip, drawstring, elastic")
    pockets: List[str] = Field(default_factory=list, description="kangaroo_pocket, chest_pockets, welt_pockets, patch_pockets, five_pocket")
    cuffs: Optional[str] = Field(default=None, description="ribbed_knit, buttoned_barrel, elastic, straight_hem")
    hem: Optional[str] = Field(default=None, description="ribbed_waistband, curved_shirttail, straight_hem, drawstring_hem")
    hood: Optional[str] = Field(default=None, description="cowl_hood, drawstrings, none")
    seams: List[str] = Field(default_factory=list, description="side_seams, raglan_seams, yoke_seam, flatlock_seams")
    fabric_texture: str = Field(default="cotton_fleece", description="inferred fabric surface texture")


class UncertaintyAnalysis(BaseModel):
    entropy: float = Field(default=0.0, description="Softmax prediction distribution entropy")
    top1_top2_margin: float = Field(default=1.0, description="Margin between top candidate and runner up")
    low_contrast_flag: bool = Field(default=False, description="Flag indicating low contrast silhouette")
    occlusion_flag: bool = Field(default=False, description="Flag indicating high silhouette crop or occlusion")
    model_disagreement_flag: bool = Field(default=False, description="Flag when ensemble models diverge on category")
    confidence_score: float = Field(default=0.90, ge=0.0, le=1.0)
    verdict: str = Field(default="HIGH_CONFIDENCE", description="HIGH_CONFIDENCE, MODERATE_CONFIDENCE, REQUIRES_REVIEW")


class IdentificationModelProvenance(BaseModel):
    fashion_clip_model: str = "Not verified"
    fashion_clip_device: str = "mps"
    siglip_model: str = "Not verified"
    siglip_device: str = "mps"
    dinov2_model: str = "Not verified"
    dinov2_device: str = "mps"
    grounded_sam2_model: str = "Not verified"
    grounded_sam2_device: str = "mps"
    depth_model: str = "Not verified"
    depth_device: str = "mps"
    total_latency_ms: float = 0.0
    peak_memory_mb: float = 0.0
    execution_order: List[str] = Field(default_factory=lambda: [
        "aspect_ratio_preprocessor",
        "fashion_clip",
        "siglip",
        "dinov2_features",
        "grounded_sam2",
        "depth_anything_v2"
    ])
    fallback_triggered: bool = False
    zero_cost_local_verified: bool = False
    model_execution_details: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class ReconstructionHandoffSpec(BaseModel):
    target_dag_template: str = Field(..., description="DAG template (hoodie_construction, jacket_construction, etc.)")
    sleeve_length_scale: float = Field(default=1.0, ge=0.0, le=2.0)
    collar_height_scale: float = Field(default=1.0, ge=0.0, le=2.0)
    enable_hood_mesh: bool = False
    enable_pocket_mesh: bool = False
    pocket_type: Optional[str] = None
    closure_geometry: str = "none"
    curved_hem: bool = False
    torso_fit_offset_cm: float = 2.0
    material_preset: str = "heavy_cotton_fleece"


class StructuredGarmentSpecification(BaseModel):
    garment_id: str
    category: GarmentCategory
    subcategory: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    attributes: GarmentVisualAttributes
    components: List[ComponentLocation] = Field(default_factory=list)
    relative_depth_stats: Dict[str, float] = Field(default_factory=dict)
    uncertainty: UncertaintyAnalysis
    provenance: IdentificationModelProvenance
    reconstruction_handoff: ReconstructionHandoffSpec
    natural_language_explanation: str = Field(default="", description="Structured explanation of garment characteristics")


class GarmentIdentificationResponse(BaseModel):
    success: bool = True
    specification: StructuredGarmentSpecification
    status_message: str = "Garment successfully identified using zero-cost local multimodal engine"
