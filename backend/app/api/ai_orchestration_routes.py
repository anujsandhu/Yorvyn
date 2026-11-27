"""
YORVYN — Hybrid AI Orchestration API Routes (Phase 13.2 Remediated)
FastAPI endpoints for client device capability negotiation, workload planning,
authoritative mesh validation, and model registry discovery.
Protected by verified Supabase JWT authentication, sliding-window rate limiting,
streaming bounded upload ingestion, and strict GLB binary validation.
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Request, status
from typing import Optional, Dict, Any, List
import time
import struct
from collections import defaultdict
from pydantic import BaseModel, Field

from backend.app.models.hybrid_ai_contracts import (
    WorkloadType,
    RoutingPolicy,
    DeviceCapabilitiesPayload,
    HybridProcessingRequestPayload,
    HybridGarmentFeaturesPayload,
    HybridGarmentProvenancePayload
)
from backend.app.services.ml.model_registry import unified_model_registry
from backend.app.services.garments.mesh_validation_service import mesh_validation_service
from backend.app.services.orchestration.hybrid_workload_router import hybrid_workload_router
from backend.app.core.security import get_current_user, UserContext

router = APIRouter(prefix="/orchestration", tags=["Hybrid AI Orchestration"])

# Configuration limits
MAX_GLB_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
CHUNK_SIZE_BYTES = 64 * 1024             # 64 KB streaming chunks
RATE_LIMIT_REQUESTS = 60                 # 60 requests
RATE_LIMIT_WINDOW_SECONDS = 60           # per 60 seconds

# In-memory sliding window rate limiter
_user_request_timestamps: Dict[str, List[float]] = defaultdict(list)


def check_user_rate_limit(user_id: str, limit: int = RATE_LIMIT_REQUESTS, window: int = RATE_LIMIT_WINDOW_SECONDS) -> None:
    now = time.time()
    cutoff = now - window
    timestamps = _user_request_timestamps[user_id]
    
    # Prune expired timestamps
    _user_request_timestamps[user_id] = [t for t in timestamps if t > cutoff]
    
    if len(_user_request_timestamps[user_id]) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: maximum {limit} requests per {window} seconds allowed.",
            headers={"Retry-After": str(window)}
        )
    
    _user_request_timestamps[user_id].append(now)


async def stream_and_validate_glb(file: UploadFile, request: Request) -> bytes:
    """
    Streams file in bounded 64KB chunks up to MAX_GLB_UPLOAD_BYTES.
    Validates Content-Length header if present, aborts streaming immediately if limit is exceeded,
    and forensically verifies binary glTF 2.0 structure.
    """
    # 1. Inspect Content-Length header (if present)
    content_length_header = request.headers.get("content-length")
    if content_length_header:
        try:
            cl = int(content_length_header)
            if cl > MAX_GLB_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"Payload Too Large: Content-Length ({cl} bytes) exceeds maximum limit of {MAX_GLB_UPLOAD_BYTES} bytes."
                )
        except ValueError:
            pass

    # 2. Stream in chunks without trusting header blindly
    chunks: List[bytes] = []
    total_bytes = 0

    while True:
        chunk = await file.read(CHUNK_SIZE_BYTES)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > MAX_GLB_UPLOAD_BYTES:
            chunks.clear()
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Payload Too Large: Uploaded stream exceeded maximum limit of {MAX_GLB_UPLOAD_BYTES} bytes."
            )
        chunks.append(chunk)

    glb_bytes = b"".join(chunks)

    # 3. Validate GLB Binary Structure
    if len(glb_bytes) < 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed GLB: Payload is too small to contain a valid Binary glTF 2.0 header."
        )

    # Header layout: 4 bytes magic, 4 bytes version, 4 bytes total length
    magic, version, header_len = struct.unpack_from("<4sII", glb_bytes, 0)
    if magic != b"glTF":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed GLB: Invalid magic bytes {magic!r}. Expected b'glTF'."
        )

    if version != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed GLB: Unsupported glTF version {version}. Only glTF 2.0 is supported."
        )

    if header_len != len(glb_bytes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed GLB: Header declared length ({header_len} bytes) does not match actual received bytes ({len(glb_bytes)} bytes)."
        )

    # First chunk layout (byte 12): 4 bytes chunkLength, 4 bytes chunkType (must be JSON: 0x4E4F534A)
    chunk0_len, chunk0_type = struct.unpack_from("<II", glb_bytes, 12)
    if chunk0_type != 0x4E4F534A:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed GLB: Chunk 0 type must be JSON (0x4E4F534A)."
        )

    return glb_bytes


@router.post("/plan")
def plan_workload(
    workload_type: WorkloadType,
    policy: RoutingPolicy = "AUTO",
    capabilities: Optional[DeviceCapabilitiesPayload] = None,
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Evaluates client hardware capabilities and returns an authoritative execution plan.
    Requires authenticated user token.
    """
    check_user_rate_limit(current_user.user_id)
    return hybrid_workload_router.plan_workload(
        workload_type=workload_type,
        policy=policy,
        capabilities=capabilities
    )


@router.get("/models")
def get_model_registry(
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Returns the centralized model registry containing client & server specs, checksums, and version mappings.
    Requires authenticated user token.
    """
    check_user_rate_limit(current_user.user_id)
    return {
        "status": "success",
        "taxonomy_version": "v3.2",
        "models": unified_model_registry.list_models()
    }


@router.post("/validate-mesh")
async def validate_mesh_topology(
    request: Request,
    file: UploadFile = File(...),
    category: str = Form("top"),
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Authoritative server-side 3D mesh inspection using Trimesh.
    Protected against memory exhaustion with bounded streaming and strict GLB binary validation.
    Requires authenticated user token.
    """
    check_user_rate_limit(current_user.user_id)
    start_t = time.perf_counter()

    glb_bytes = await stream_and_validate_glb(file, request)
    report = mesh_validation_service.validate_glb_bytes(glb_bytes, category=category)
    duration_ms = (time.perf_counter() - start_t) * 1000.0

    return {
        "status": "success" if report.is_valid else "warning",
        "duration_ms": round(duration_ms, 2),
        "validation_report": report.to_dict()
    }


class ReconcileProvenanceRequest(BaseModel):
    user_id: Optional[str] = None
    edge_prediction: Optional[HybridGarmentFeaturesPayload] = None
    server_prediction: Optional[HybridGarmentFeaturesPayload] = None
    user_correction: Optional[Dict[str, Any]] = None
    bandwidth_saved_bytes: int = Field(default=0, ge=0, le=100 * 1024 * 1024)
    edge_latency_ms: float = Field(default=0.0, ge=0.0, le=60000.0)
    cloud_latency_ms: float = Field(default=0.0, ge=0.0, le=60000.0)


@router.post("/reconcile-provenance")
def reconcile_provenance(
    payload: ReconcileProvenanceRequest,
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Authoritatively reconciles edge prediction, cloud prediction, and user corrections,
    strictly recording non-repudiable provenance bound to the authenticated user ID.
    """
    check_user_rate_limit(current_user.user_id)

    if payload.user_id and payload.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-user provenance rejected: payload user_id '{payload.user_id}' does not match authenticated token '{current_user.user_id}'."
        )

    baseline_server = payload.server_prediction or HybridGarmentFeaturesPayload(
        category="top",
        subcategory="tshirt",
        confidence_score=0.90
    )

    provenance = hybrid_workload_router.validate_and_reconcile_features(
        edge_prediction=payload.edge_prediction,
        server_prediction=baseline_server,
        user_correction=payload.user_correction,
        bandwidth_saved_bytes=payload.bandwidth_saved_bytes,
        edge_latency_ms=payload.edge_latency_ms,
        cloud_latency_ms=payload.cloud_latency_ms
    )

    prov_dict = provenance.model_dump()
    prov_dict["user_id"] = current_user.user_id

    return {
        "status": "success",
        "provenance": prov_dict
    }


@router.get("/health")
def get_orchestration_health() -> Dict[str, Any]:
    """
    Telemetry on backend GPU, MPS, CPU, and Trimesh capabilities.
    Public health check endpoint.
    """
    import torch
    device_type = "cpu"
    if torch.cuda.is_available():
        device_type = f"cuda:{torch.cuda.get_device_name(0)}"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device_type = "apple_silicon_mps"

    from backend.app.services.garments.mesh_validation_service import TRIMESH_AVAILABLE

    return {
        "status": "operational",
        "server_acceleration": device_type,
        "trimesh_available": TRIMESH_AVAILABLE,
        "supported_routing_policies": ["AUTO", "LOCAL_PREFERRED", "CLOUD_PREFERRED", "LOCAL_REQUIRED", "CLOUD_REQUIRED"],
        "client_edge_supported": True,
        "max_upload_bytes": MAX_GLB_UPLOAD_BYTES
    }
