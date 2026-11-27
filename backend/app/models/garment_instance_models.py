"""
YORVYN — Garment Instance Models
Pydantic schemas for multi-garment instance detection, segmentation, and perception.
Provides discrete instance tracking for outfit grids, multi-garment on-body scenes,
flat-lays, and isolated product crops.
"""

from typing import List, Tuple, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class GarmentInstanceRecord(BaseModel):
    """
    Complete state record for a single detected garment instance in an image.
    Preserves independent classification, segmentation mask, bounding box,
    visual attributes, and provenance.
    """
    model_config = ConfigDict(protected_namespaces=())

    instance_id: str = Field(..., description="Unique instance identifier, e.g. inst_0_tops")
    bbox: Tuple[int, int, int, int] = Field(..., description="Pixel bounding box (min_x, min_y, max_x, max_y)")
    normalized_bbox: Tuple[float, float, float, float] = Field(..., description="Normalized coordinates [x1, y1, x2, y2] in [0.0, 1.0]")
    area_pixels: int = Field(..., ge=0)
    area_ratio: float = Field(..., ge=0.0, le=1.0, description="Garment area relative to full image")

    # Classification & Perception
    category: str = Field(..., description="Predicted top-level category (tops, bottoms, dress, skirt, jacket, etc.)")
    subcategory: str = Field(..., description="Predicted fine-grained subcategory (hoodie, tshirt, jeans, etc.)")
    display_name: str = Field(..., description="Human-readable title (e.g. Relaxed Fit Hoodie)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Calibrated confidence score")
    selective_outcome: str = Field("accepted_high_confidence", description="One of the 6 MECE selective outcomes")
    photography_domain: str = Field("on_body", description="on_body, flat_lay, product, lifestyle, mannequin")

    # Geometry & Segmentation
    visibility_ratio: float = Field(1.0, ge=0.0, le=1.0, description="Estimated unoccluded visible fraction")
    occlusion_ratio: float = Field(0.0, ge=0.0, le=1.0, description="Estimated occluded fraction")
    outer_contour: List[List[int]] = Field(default_factory=list, description="Primary outer perimeter polygon")
    holes: List[List[List[int]]] = Field(default_factory=list, description="Internal hole polygons (neck, armholes, cutouts)")
    mask_data_url: Optional[str] = Field(None, description="Base64 PNG data URL of binary instance alpha mask")
    crop_data_url: Optional[str] = Field(None, description="Base64 JPEG/PNG data URL of neutral letterboxed crop")
    letterbox_metadata: Dict[str, Any] = Field(default_factory=dict, description="Padding & scale transform parameters")

    # Fashion Attributes
    dominant_colors: List[Dict[str, Any]] = Field(default_factory=list, description="Hex, RGB, fashion name, and percentage")
    fabric_family: str = Field("cotton_jersey", description="Textile family (fleece, jersey, denim, wool, etc.)")
    silhouette: str = Field("regular", description="Garment silhouette (regular, oversized, slim, relaxed)")
    sleeve_type: Optional[str] = Field(None, description="long_sleeve, short_sleeve, sleeveless")
    neckline: Optional[str] = Field(None, description="crew_neck, v_neck, hooded, collar")
    length: Optional[str] = Field(None, description="regular, cropped, full_length, knee_length")
    visible_components: List[str] = Field(default_factory=list, description="Detected structural components (hood, collar, pockets)")

    # Model & Provenance
    detector_model: str = Field("segformer_b2_clothes-v2+adaptive_contour", description="Instance detection engine")
    source_strategy: str = Field("human_parsing_semantic", description="Detection strategy used (human_parsing_semantic, underlayer_extraction, contour_cluster)")
    classifier_model: str = Field("HierarchicalMultiTaskNetworkV6", description="Classification engine")
    reconstruction_eligible: bool = Field(True, description="Whether instance meets quality requirements for 3D try-on")
    rejection_reason: Optional[str] = None


class MultiGarmentSceneAnalysis(BaseModel):
    """
    Aggregated multi-instance analysis of a photograph.
    Enables user selection of individual garments from an outfit or flat-lay scene.
    """
    model_config = ConfigDict(protected_namespaces=())

    analysis_id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    image_width: int
    image_height: int
    scene_type: str = Field("on_body", description="on_body, outfit_grid, flat_lay, product_packshot")
    total_instances_detected: int = Field(0, ge=0)
    instances: List[GarmentInstanceRecord] = Field(default_factory=list)
    selected_instance_id: Optional[str] = None
    outfit_pairing_detected: bool = False
    ensemble_categories: List[str] = Field(default_factory=list)
    processing_time_ms: float = 0.0
    provenance_statement: str = "Analytical garment instance perception; procedural 3D reconstruction"
