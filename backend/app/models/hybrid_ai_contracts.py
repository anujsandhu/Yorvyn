"""
YORVYN — Unified Hybrid AI Processing Contracts (Phase 13)
Pydantic models for client-side edge computing, server-side GPU processing,
and unified workload orchestration.
"""

from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime

WorkloadType = Literal[
    'IMAGE_PREPROCESS',
    'BLUR_DETECTION',
    'COLOR_PALETTE',
    'GARMENT_CLASSIFICATION',
    'GARMENT_SEGMENTATION',
    'POSE_ESTIMATION',
    'NEURAL_RECONSTRUCTION',
    'TEXTURE_SYNTHESIS',
    'MESH_VALIDATION',
    'CLOTH_SIMULATION',
    'AVATAR_FITTING'
]

RoutingPolicy = Literal[
    'AUTO',
    'LOCAL_PREFERRED',
    'CLOUD_PREFERRED',
    'LOCAL_REQUIRED',
    'CLOUD_REQUIRED'
]

ExecutionLocation = Literal[
    'CLIENT_WEBGPU',
    'CLIENT_WASM',
    'CLIENT_WORKER',
    'CLOUD_GPU',
    'CLOUD_CPU',
    'HYBRID_COLLABORATIVE'
]

DeviceTier = Literal['LOW', 'MID', 'HIGH', 'ULTRA']


class DeviceCapabilitiesPayload(BaseModel):
    webgpu_supported: bool = False
    webgl_supported: bool = True
    simd_wasm_supported: bool = True
    web_workers_supported: bool = True
    hardware_concurrency: int = 4
    device_memory_gb: Optional[float] = 4.0
    max_texture_size: int = 4096
    device_tier: DeviceTier = 'MID'
    network_effective_type: Optional[str] = '4g'
    network_save_data: Optional[bool] = False
    downlink_speed_mbps: Optional[float] = 10.0
    round_trip_time_ms: Optional[float] = 50.0
    battery_level: Optional[float] = 1.0
    battery_charging: Optional[bool] = True
    user_processing_preference: RoutingPolicy = 'AUTO'


class HybridGarmentFeaturesPayload(BaseModel):
    category: str
    subcategory: str
    confidence_score: float = 0.90
    palette: List[str] = Field(default_factory=list)
    primary_color_hex: str = '#333333'
    primary_color_name: str = 'Dark'
    secondary_color_name: Optional[str] = None
    pattern: str = 'solid'
    material_hint: str = 'cotton'
    fit: str = 'regular'
    neckline_type: Optional[str] = 'crewneck'
    sleeve_length: Optional[str] = 'long'
    has_hood: Optional[bool] = False
    has_kangaroo_pocket: Optional[bool] = False
    has_collar: Optional[bool] = False
    components: List[str] = Field(default_factory=list)


class HybridGarmentProvenancePayload(BaseModel):
    original_ai_prediction: Optional[HybridGarmentFeaturesPayload] = None
    edge_prediction: Optional[HybridGarmentFeaturesPayload] = None
    cloud_prediction: Optional[HybridGarmentFeaturesPayload] = None
    user_correction: Optional[Dict[str, Any]] = None
    final_authoritative_features: HybridGarmentFeaturesPayload
    execution_location: ExecutionLocation
    routing_reason: str
    edge_latency_ms: Optional[float] = None
    cloud_latency_ms: Optional[float] = None
    total_duration_ms: float = 0.0
    bandwidth_saved_bytes: Optional[int] = 0
    model_id: str
    model_version: str


class HybridProcessingRequestPayload(BaseModel):
    request_id: str
    workload_type: WorkloadType
    policy: RoutingPolicy = 'AUTO'
    client_capabilities: Optional[DeviceCapabilitiesPayload] = None
    edge_prediction: Optional[HybridGarmentFeaturesPayload] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class HybridProcessingResponsePayload(BaseModel):
    request_id: str
    status: Literal['success', 'fallback', 'failed'] = 'success'
    execution_location: ExecutionLocation
    model_id: str
    model_version: str
    duration_ms: float
    result: Optional[Dict[str, Any]] = None
    provenance: HybridGarmentProvenancePayload
    fallback_reason: Optional[str] = None
    error: Optional[str] = None

