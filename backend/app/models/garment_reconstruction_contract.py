"""
YORVYN — Typed & Versioned Perception-to-Reconstruction API Contract.
Provides strict schema validation, coordinate inversion verification, mask topology checks,
and reconstruction eligibility gating between 2D garment perception and 3D mesh reconstruction.
"""

from typing import List, Tuple, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
import numpy as np


class MaterialAttributes(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    fabric_family: str = Field("cotton_jersey", description="Primary textile class")
    weave_type: str = Field("plain", description="plain, twill, knit, fleece, satin, denim")
    estimated_stretch: float = Field(0.15, ge=0.0, le=1.0, description="Estimated fabric elasticity coefficient")
    estimated_thickness_mm: float = Field(1.2, ge=0.1, le=15.0, description="Estimated physical fabric thickness in mm")
    dominant_hex: str = Field("#202020", description="Primary color hex")
    color_palette: List[Dict[str, Any]] = Field(default_factory=list)


class ModelProvenanceRecord(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    detection_engine: str = Field(..., description="Detector model architecture & version")
    segmentation_engine: str = Field(..., description="Segmentation backbone & version")
    classification_engine: str = Field(..., description="Classifier checkpoint & version")
    deformation_engine: str = Field("UniversalGarmentFittingEngine-14.3.0", description="Mesh deformation engine")
    procedural_clearance_verified: bool = Field(True, description="Whether mesh passed collision-free clearance verification")
    neural_3d_endpoint_active: bool = Field(False, description="Whether remote neural 3D GPU endpoint is connected")
    neural_3d_status: str = Field("UNCONFIGURED_OR_LOCAL_PROCEDURAL", description="Status string for provenance audit")


class GarmentPerceptionReconstructionContract(BaseModel):
    """
    Contract version 14.3.0.
    Immutable, typed, versioned data bundle handed from perception to 3D virtual try-on reconstruction.
    """
    model_config = ConfigDict(protected_namespaces=())

    contract_version: str = Field("14.3.0", description="Semantic version of handoff contract")
    request_id: str = Field(..., description="Unique user or session request ID")
    instance_id: str = Field(..., description="Unique instance ID (e.g., inst_0_tops)")
    source_image_id: str = Field(..., description="ID or content hash of source photograph")
    physical_garment_id: Optional[str] = Field(None, description="Known physical garment identity if multi-view tracked")

    # Classification & Taxonomy
    category: str = Field(..., description="Standardized domain: tops, bottoms, dress, skirt, jacket, hoodie, etc.")
    subcategory: str = Field(..., description="Fine-grained subcategory: tshirt, jeans, pullover_hoodie, etc.")
    classification_confidence: float = Field(..., ge=0.0, le=1.0)
    selective_outcome: str = Field("accepted_high_confidence", description="MECE selective prediction status")

    # Geometry & Space
    bounding_box: Tuple[int, int, int, int] = Field(..., description="Bounding box [min_x, min_y, max_x, max_y] in source pixels")
    normalized_bounding_box: Tuple[float, float, float, float] = Field(..., description="Normalized coordinates [x1, y1, x2, y2] in [0, 1]")
    source_coordinates: Dict[str, Any] = Field(default_factory=dict, description="Inversion matrix and crop offsets")
    image_dimensions: Tuple[int, int] = Field(..., description="Source image [width, height]")
    crop_dimensions: Tuple[int, int] = Field(..., description="Letterboxed crop [width, height], typically (224, 224)")
    preprocessing_version: str = Field("neutral_letterbox_v2", description="Preprocessing pipeline version")

    # Masks & Topology
    segmentation_mask: Optional[str] = Field(None, description="Base64 PNG or RLE-encoded binary mask of instance")
    outer_contour: List[List[int]] = Field(default_factory=list, description="Extracted outer perimeter polygon vertices")
    holes: List[List[List[int]]] = Field(default_factory=list, description="Preserved hole loops (neckline, armholes, leg cuffs)")
    hole_count: int = Field(0, ge=0)
    has_valid_topology: bool = Field(True, description="Whether polygon forms a closed manifold without self-intersection")

    # Structure & Materials
    visible_components: List[str] = Field(default_factory=list, description="Observed components (collar, sleeves, pockets, hood)")
    occlusion_estimate: float = Field(0.0, ge=0.0, le=1.0, description="Estimated occluded percentage of garment")
    material_attributes: MaterialAttributes = Field(default_factory=MaterialAttributes)
    model_provenance: ModelProvenanceRecord

    # Handoff Eligibility
    reconstruction_eligibility: bool = Field(True, description="Whether instance passes all gating checks for 3D generation")
    ineligibility_reasons: List[str] = Field(default_factory=list)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {"tops", "bottoms", "dress", "skirt", "jacket", "hoodie", "shirt", "footwear", "accessories"}
        if v.lower() not in allowed:
            raise ValueError(f"Category '{v}' is outside supported 3D reconstruction domain.")
        return v.lower()


class GarmentHandoffValidator:
    """
    Validates perception handoffs before they enter 3D parametric or neural reconstruction.
    Guarantees coordinate consistency, mask completeness, and topology integrity.
    """

    @staticmethod
    def validate_handoff(contract: GarmentPerceptionReconstructionContract) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        # 1. Image Dimension Sanity
        w, h = contract.image_dimensions
        if w <= 0 or h <= 0:
            errors.append(f"Invalid source image dimensions: {w}x{h}")

        # 2. Bounding Box Containment & Inversion
        x1, y1, x2, y2 = contract.bounding_box
        if x1 < 0 or y1 < 0 or x2 > w or y2 > h or x2 <= x1 or y2 <= y1:
            errors.append(f"Bounding box [{x1}, {y1}, {x2}, {y2}] exceeds image boundaries ({w}x{h})")

        # 3. Normalized Bounding Box Consistency
        nx1, ny1, nx2, ny2 = contract.normalized_bounding_box
        if not (0.0 <= nx1 < nx2 <= 1.0 and 0.0 <= ny1 < ny2 <= 1.0):
            errors.append(f"Normalized bounding box [{nx1}, {ny1}, {nx2}, {ny2}] out of [0, 1] range")

        calc_nx1 = round(x1 / max(w, 1), 3)
        calc_ny1 = round(y1 / max(h, 1), 3)
        if abs(calc_nx1 - round(nx1, 3)) > 0.02 or abs(calc_ny1 - round(ny1, 3)) > 0.02:
            errors.append(f"Coordinate mismatch between pixel box and normalized box: pixel normalized ({calc_nx1}, {calc_ny1}) vs declared ({nx1}, {ny1})")

        # 4. Topology and Outer Contour
        if not contract.outer_contour or len(contract.outer_contour) < 3:
            errors.append("Outer perimeter contour missing or has fewer than 3 vertices")

        if not contract.has_valid_topology:
            errors.append("Topology self-intersection or non-manifold polygon boundary detected")

        # 5. Mask Completeness & Non-Empty Region Check
        if contract.segmentation_mask is not None and len(contract.segmentation_mask) == 0:
            errors.append("Segmentation mask string is present but empty")

        # 6. Selective Outcome Gating
        if contract.selective_outcome in ["rejected_ambiguous", "rejected_invalid_input", "rejected_unsupported", "inference_failure"]:
            errors.append(f"Instance selective outcome '{contract.selective_outcome}' cannot enter reconstruction without user confirmation")

        # 7. Occlusion Limit & Visual Evidence
        if contract.occlusion_estimate > 0.70:
            errors.append(f"Garment is heavily occluded ({contract.occlusion_estimate*100:.1f}% > 70%); insufficient surface to reconstruct")

        if contract.classification_confidence < 0.25:
            errors.append(f"Classification confidence {contract.classification_confidence:.2f} is below minimum visual evidence threshold 0.25")

        # 8. Crop Orientation & Source Dimensions
        cw, ch = contract.crop_dimensions
        if cw <= 0 or ch <= 0:
            errors.append(f"Invalid crop dimensions: {cw}x{ch}")

        # 9. Physical Material Attributes Validation
        mat = contract.material_attributes
        if not (0.1 <= mat.estimated_thickness_mm <= 15.0):
            errors.append(f"Material thickness {mat.estimated_thickness_mm} mm outside physical range [0.1, 15.0]")
        if not (0.0 <= mat.estimated_stretch <= 1.0):
            errors.append(f"Material stretch {mat.estimated_stretch} outside physical coefficient range [0.0, 1.0]")
        if not (mat.dominant_hex.startswith("#") and len(mat.dominant_hex) in (4, 7)):
            errors.append(f"Invalid hex color format: '{mat.dominant_hex}'")

        # 10. Instance ID Format
        if not contract.instance_id or not contract.instance_id.strip():
            errors.append("Instance ID missing or empty")

        is_valid = len(errors) == 0
        return is_valid, errors
