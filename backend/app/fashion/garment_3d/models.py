"""
Pydantic Models for AI Photo-to-3D Garment Generation Pipeline.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class GarmentGenJobStatus(str, Enum):
    QUEUED = "queued"
    ANALYZING = "analyzing"
    GENERATING_MESH = "generating_mesh"
    SYNTHESIZING_TEXTURES = "synthesizing_textures"
    ASSEMBLING_3D = "assembling_3d"
    RENDERING_PREVIEW = "rendering_preview"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GarmentCategory(str, Enum):
    TOP = "top"
    BOTTOM = "bottom"
    OUTERWEAR = "outerwear"
    DRESS = "dress"
    SKIRT = "skirt"
    FOOTWEAR = "footwear"


class DetectedGarmentFeatures(BaseModel):
    category: str
    subcategory: str
    primary_color_name: str
    primary_color_hex: str
    secondary_color_name: Optional[str] = None
    secondary_color_hex: Optional[str] = None
    palette: List[str] = Field(default_factory=list)
    pattern: str = "solid"
    material_hint: str = "cotton"
    neckline_type: Optional[str] = "crewneck"  # crewneck, v_neck, collar, scoop, turtle
    sleeve_length: Optional[str] = "short"     # sleeveless, short, three_quarter, long
    hem_length: Optional[str] = "standard"     # cropped, standard, long
    fit: str = "regular"                       # slim, regular, relaxed, oversized
    formality: int = 4
    warmth: int = 4
    confidence_score: float = 0.85
    requires_additional_view: bool = False
    quality_notes: Optional[str] = None


class GarmentGenResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    job_id: str
    garment_name: str
    category: str
    subcategory: str
    glb_url: str
    thumbnail_url: str
    texture_url: Optional[str] = None
    normal_map_url: Optional[str] = None
    mesh_vertex_count: int
    mesh_triangle_count: int
    features: DetectedGarmentFeatures
    model_version: str = "yorvyn-garment3d-v2.0"
    created_at: str
    rig_compatibility: Dict[str, Any] = Field(default_factory=lambda: {
        "engine": "Ara 3D Gen",
        "rig_type": "standard_humanoid",
        "skinning": "anatomic_projection",
        "occlusion_masking": True
    })


class GarmentGenJob(BaseModel):
    job_id: str
    user_id: str
    status: GarmentGenJobStatus
    progress: int = 0
    current_stage: str = "Initializing job..."
    created_at: datetime
    updated_at: datetime
    error: Optional[str] = None
    result: Optional[GarmentGenResult] = None
    temporary_files: List[str] = Field(default_factory=list)
