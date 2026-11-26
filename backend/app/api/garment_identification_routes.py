"""
YORVYN — Local Multimodal Garment Identification API Routes (Phase 14.24-F)
Provides REST API endpoints for zero-cost local garment identification:
- POST /api/garments/identify: Multipart image upload returning complete StructuredGarmentSpecification
- GET /api/garments/identify/models: Model registry, hardware compatibility, and memory telemetry
- POST /api/garments/identify/reconstruct-handoff: Validates and adapts specification into 3D reconstruction DAG
"""

import io
import hashlib
import time
import logging
from typing import Dict, Any, Optional, List
import json
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Depends
from starlette.concurrency import run_in_threadpool
from PIL import Image
from backend.app.core.security import get_current_user_optional, UserContext

from backend.app.models.structured_garment_specification import (
    StructuredGarmentSpecification,
    GarmentIdentificationResponse,
    GarmentCategory
)
from backend.app.services.garments.intelligence.local_multimodal_identification_engine import multimodal_engine
from backend.app.services.garments.intelligence.sequential_model_manager import model_manager
from backend.app.services.ai.orchestration.orchestrator import ai_orchestrator
from backend.app.services.ai.contracts import (
    CanonicalGarmentSpecification,
    CanonicalGarmentSpecificationV2
)
from backend.app.services.ai.multiview.fusion_engine import multi_view_fusion_engine
from backend.app.services.ai.multiview.view_classifier import GarmentViewType
from backend.app.services.garments.reconstruction.universal_construction_graph import UniversalConstructionGraph

logger = logging.getLogger(__name__)

# Security & limits
MAX_IMAGE_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB per file
MAX_TOTAL_BATCH_SIZE_BYTES = 60 * 1024 * 1024  # 60 MB batch limit
MAX_IMAGES_PER_REQUEST = 10
MAX_CACHED_MULTIVIEW_SPECS = 500
Image.MAX_IMAGE_PIXELS = 50_000_000  # 50 MP decompression-bomb defense

# Bounded hot cache; authoritative evidence metadata is also persisted tenant-scoped for 30 days.
MULTIVIEW_SPECS_STORE: Dict[str, tuple[str, CanonicalGarmentSpecificationV2]] = {}

router = APIRouter(prefix="/api/garments", tags=["garment-identification"])


@router.post(
    "/identify",
    response_model=GarmentIdentificationResponse,
    summary="Identify garment category, components, attributes, and 3D parameters from an image"
)
async def identify_garment_endpoint(
    image: UploadFile = File(..., description="Uploaded garment photograph (JPEG/PNG/WebP)"),
    garment_id: Optional[str] = Form(None, description="Optional custom garment identifier")
) -> GarmentIdentificationResponse:
    """
    Local identification endpoint. Adapter metadata identifies cached model execution
    separately from generic CLIP and hand-built heuristic stages.
    """
    if not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type {image.content_type}. Expected an image."
        )

    try:
        contents = await image.read()
        pil_img = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        logger.error(f"Failed to decode uploaded image: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to decode image data: {str(e)}"
        )

    try:
        spec = multimodal_engine.identify_garment(pil_img, garment_id=garment_id)
        return GarmentIdentificationResponse(
            success=True,
            specification=spec,
            status_message="Garment successfully identified using zero-cost local multimodal engine"
        )
    except Exception as e:
        logger.error(f"Identification pipeline error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference error during garment identification: {str(e)}"
        )


@router.get(
    "/identify/models",
    summary="Get zero-cost local model registry, hardware telemetry and supported categories"
)
async def get_model_registry_status() -> Dict[str, Any]:
    """
    Returns runtime telemetry and distinguishes model-backed adapters from heuristic implementations.
    """
    from backend.app.services.ml.dinov2_feature_extractor import dinov2_extractor

    return {
        "status": "registered",
        "zero_cost_local_policy": True,
        "primary_device": model_manager.preferred_device,
        "peak_memory_mb": model_manager.peak_memory_mb,
        "current_memory_mb": model_manager.get_current_memory_mb(),
        "memory_headroom_limit_mb": model_manager.max_memory_headroom_mb,
        "fallback_triggered": model_manager.fallback_occurred,
        "model_registry": [
            {
                "name": "Generic CLIP prompt classifier",
                "claimed_model": "FashionCLIP",
                "checkpoint": "openai/clip-vit-base-patch32 (generic; not FashionCLIP)",
                "role": "Prompt similarity for category/subcategory suggestions",
                "execution_mode": "local cache only; weights not checked by this endpoint",
                "license": "Not independently verified",
                "device": model_manager.preferred_device,
                "status": "registered"
            },
            {
                "name": "Generic CLIP sigmoid score adapter",
                "claimed_model": "SigLIP",
                "checkpoint": "openai/clip-vit-base-patch32 (not SigLIP)",
                "role": "Prompt similarity scores for visual attribute suggestions",
                "execution_mode": "local cache only; weights not checked by this endpoint",
                "license": "Not independently verified",
                "device": model_manager.preferred_device,
                "status": "registered"
            },
            {
                "name": "DINOv2",
                "checkpoint": "facebook/dinov2-small",
                "role": "Visual embeddings when cached pretrained weights are available",
                "execution_mode": dinov2_extractor.execution_backend,
                "pretrained_weights_loaded": dinov2_extractor.pretrained_weights_loaded,
                "license": "Not independently verified",
                "device": str(dinov2_extractor.device),
                "status": "available" if dinov2_extractor.pretrained_weights_loaded else "registered"
            },
            {
                "name": "OpenCV component-region heuristic",
                "claimed_model": "Grounded-SAM2",
                "checkpoint": None,
                "role": "Otsu silhouette plus proportional prompt regions; not a learned detector",
                "license": "Not independently verified",
                "device": "cpu",
                "status": "heuristic"
            },
            {
                "name": "Analytic relative-disparity heuristic",
                "claimed_model": "Depth Anything V2",
                "checkpoint": None,
                "role": "Image-intensity and torso-prior disparity; not learned depth inference",
                "license": "Not independently verified",
                "device": "cpu",
                "status": "heuristic"
            }
        ],
        "supported_categories": [c.value for c in GarmentCategory],
        "total_categories_count": len(GarmentCategory)
    }


@router.post(
    "/identify/reconstruct-handoff",
    summary="Validate and adapt specification for 3D reconstruction pipeline"
)
async def adapt_reconstruction_handoff(
    specification: StructuredGarmentSpecification
) -> Dict[str, Any]:
    """
    Validates structured specification and returns configured parameters for
    the ImageConditionedReconstructionEngine and UniversalConstructionGraph.
    """
    handoff = specification.reconstruction_handoff
    return {
        "garment_id": specification.garment_id,
        "category": specification.category.value,
        "target_dag": handoff.target_dag_template,
        "parameters": {
            "sleeve_length_scale": handoff.sleeve_length_scale,
            "collar_height_scale": handoff.collar_height_scale,
            "enable_hood_mesh": handoff.enable_hood_mesh,
            "enable_pocket_mesh": handoff.enable_pocket_mesh,
            "pocket_type": handoff.pocket_type,
            "closure_geometry": handoff.closure_geometry,
            "curved_hem": handoff.curved_hem,
            "torso_fit_offset_cm": handoff.torso_fit_offset_cm,
            "material_preset": handoff.material_preset
        },
        "color_palette": specification.attributes.palette_hex,
        "primary_color": specification.attributes.primary_color,
        "status": "READY_FOR_3D_SYNTHESIS"
    }


# =============================================================================
# PHASE 14.26 — HYBRID AI ORCHESTRATION ROUTES (Gemini + Groq + HF + Local CV)
# =============================================================================

@router.post(
    "/hybrid-orchestrated-identify",
    response_model=CanonicalGarmentSpecification,
    summary="Identify garment using unified hybrid AI orchestrator (Gemini Vision + Groq + Local CV)"
)
async def hybrid_orchestrated_identify_endpoint(
    image: UploadFile = File(..., description="Uploaded garment photograph (JPEG/PNG/WebP)"),
    garment_id: Optional[str] = Form(None, description="Optional custom garment identifier"),
    preferred_provider: Optional[str] = Form(None, description="Optional preferred vision provider (gemini_vision, local_cv)"),
    mock_mode: bool = Form(False, description="Set True for controlled verification mock testing")
) -> CanonicalGarmentSpecification:
    """
    Unified multimodal orchestration endpoint executing capability-aware provider routing,
    fallback handling, and canonical garment specification synthesis.
    """
    if not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type {image.content_type}. Expected an image."
        )

    try:
        contents = await image.read()
    except Exception as e:
        logger.error(f"Failed to read image bytes: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read image payload: {str(e)}"
        )

    try:
        canonical_spec = await run_in_threadpool(ai_orchestrator.process_garment_image,
            image_bytes=contents,
            garment_id=garment_id,
            preferred_provider=preferred_provider,
            mock_mode=mock_mode
        )
        return canonical_spec
    except Exception as e:
        logger.error(f"Hybrid orchestration error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hybrid AI orchestration pipeline error: {str(e)}"
        )


@router.get(
    "/hybrid-orchestrated-providers",
    summary="Get operational status, health probes, and usage metrics across all hybrid AI providers"
)
async def get_hybrid_providers_status() -> Dict[str, Any]:
    """
    Returns telemetry on registered providers (Gemini, Groq, HF, Local CV),
    circuit breaker statuses, and financial usage tracker summary.
    """
    return {
        "status": "registered",
        "providers_health": ai_orchestrator.get_provider_health(),
        "usage_and_costs": ai_orchestrator.usage_tracker.get_summary()
    }


@router.post(
    "/hybrid-orchestrated-reconstruct",
    summary="Validate canonical specification and synthesize 3D Universal Construction Graph DAG"
)
async def hybrid_orchestrated_reconstruct_endpoint(
    specification: CanonicalGarmentSpecification
) -> Dict[str, Any]:
    """
    Validates canonical specification against Universal Construction Graph DAG,
    assembling functional components and structural seams without hardcoded dimensions.
    """
    cat = specification.garment.category
    subcat = specification.garment.subcategory
    handoff = specification.reconstruction_handoff

    dag = UniversalConstructionGraph(category=cat, subcategory=subcat)

    return {
        "garment_id": specification.garment_id,
        "category": cat,
        "subcategory": subcat,
        "target_dag_template": handoff.target_dag_template,
        "dag_nodes": list(dag.nodes.keys()),
        "dag_seams": list(dag.seams.keys()),
        "dag_nodes_count": len(dag.nodes),
        "dag_seams_count": len(dag.seams),
        "enable_hood_mesh": handoff.enable_hood_mesh,
        "enable_pocket_mesh": handoff.enable_pocket_mesh,
        "pocket_type": handoff.pocket_type,
        "material_preset": handoff.material_preset,
        "evidence_breakdown": {
            "directly_visible": specification.directly_visible_evidence,
            "inferred": specification.inferred_properties,
            "unknown": specification.unknown_unobservable_properties
        },
        "status": "DAG_ASSEMBLED_READY_FOR_3D_SYNTHESIS"
    }


# =============================================================================
# PHASE 14.27: Multi-View Garment Intelligence Endpoints
# =============================================================================

@router.post(
    "/multiview-identify",
    response_model=CanonicalGarmentSpecificationV2,
    summary="Multi-view garment identification and forensic evidence fusion"
)
async def multiview_identify_endpoint(
    images: List[UploadFile] = File(..., description="1 to 10 garment viewpoint photographs"),
    garment_id: Optional[str] = Form(None, description="Optional custom garment identifier"),
    view_hints: Optional[str] = Form(None, description="Optional JSON mapping filename/index to view (front, back, etc.)"),
    mock_mode: bool = Form(False, description="Controlled mock validation mode"),
    user_id: str = Form("default_user"),
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
) -> CanonicalGarmentSpecificationV2:
    """
    Ingests multiple viewpoint photographs (Front, Back, Side, Detail, Label),
    validates security constraints, fuses observations without fabricating hidden geometry,
    and returns an evidence-backed CanonicalGarmentSpecificationV2.
    """
    if not images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one garment photograph is required for multi-view identification."
        )

    if len(images) > MAX_IMAGES_PER_REQUEST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many images. Maximum allowed is {MAX_IMAGES_PER_REQUEST}."
        )

    # Parse view hints if provided
    hints_dict: Dict[str, str] = {}
    if view_hints:
        try:
            hints_dict = json.loads(view_hints)
        except Exception:
            logger.warning(f"Failed to parse view_hints JSON: {view_hints}")

    total_batch_bytes = 0
    images_payload: List[Tuple[str, bytes, Optional[str]]] = []

    for idx, upload in enumerate(images):
        if not upload.content_type or not upload.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File '{upload.filename}' is not a supported image MIME type."
            )

        try:
            contents = await upload.read()
            total_batch_bytes += len(contents)

            if len(contents) > MAX_IMAGE_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File '{upload.filename}' exceeds {MAX_IMAGE_FILE_SIZE_BYTES // (1024*1024)}MB limit."
                )

            # Decompression bomb and format validation
            pil_img = Image.open(io.BytesIO(contents))
            pil_img.verify()

            # Determine view hint from user dictionary or filename semantic patterns
            hint = hints_dict.get(upload.filename) or hints_dict.get(str(idx))
            if not hint and upload.filename:
                fn_lower = upload.filename.lower()
                for cand in ["front", "back", "rear", "three_quarter", "3_4", "close_up", "closeup", "left_side", "right_side", "side", "detail", "label"]:
                    if cand in fn_lower:
                        hint = "back" if cand == "rear" else ("three_quarter" if cand == "3_4" else ("close_up" if cand == "closeup" else cand))
                        break
            img_id = upload.filename or f"img_{idx+1:02d}"
            images_payload.append((img_id, contents, hint))

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Image validation failed for '{upload.filename}': {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to process or decode image '{upload.filename}': {str(e)}"
            )

    if total_batch_bytes > MAX_TOTAL_BATCH_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Batch size exceeds maximum limit of {MAX_TOTAL_BATCH_SIZE_BYTES // (1024*1024)}MB."
        )

    from backend.app.api.garment_generation_routes import _resolve_effective_user_id
    effective_user_id = _resolve_effective_user_id(user_id, current_user)

    try:
        fused_spec = await run_in_threadpool(
            multi_view_fusion_engine.fuse_garment_views,
            images_input=images_payload,
            garment_id=garment_id,
            mock_mode=mock_mode
        )
        existing = MULTIVIEW_SPECS_STORE.get(fused_spec.garment_id)
        if existing and existing[0] != effective_user_id:
            raise HTTPException(status_code=409, detail="The requested garment identifier is already assigned to another user.")
        from backend.app.services.garments.job_manager import garment_job_manager
        try:
            await run_in_threadpool(garment_job_manager._postgres_adapter.save_garment_evidence_spec,
                fused_spec.garment_id,
                effective_user_id,
                fused_spec.model_dump(mode="json")
            )
        except PermissionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("Durable evidence specification write failed", exc_info=True)
            raise HTTPException(status_code=503, detail="Evidence storage is unavailable; no reconstruction-ready specification was issued.") from exc
        # Bounded tenant-scoped metadata cache; raw image bytes are not retained here.
        if fused_spec.garment_id not in MULTIVIEW_SPECS_STORE and len(MULTIVIEW_SPECS_STORE) >= MAX_CACHED_MULTIVIEW_SPECS:
            MULTIVIEW_SPECS_STORE.pop(next(iter(MULTIVIEW_SPECS_STORE)))
        MULTIVIEW_SPECS_STORE[fused_spec.garment_id] = (effective_user_id, fused_spec)
        return fused_spec
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Multi-view fusion error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Multi-view fusion pipeline failed."
        )


@router.get(
    "/{garment_id}/evidence",
    summary="Get multi-view evidence breakdown, viewpoint quality, and conflict logs"
)
async def get_garment_evidence_endpoint(
    garment_id: str,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """Returns granular viewpoint evidence records and conflict resolutions for a garment."""
    from backend.app.api.garment_generation_routes import _resolve_effective_user_id
    effective_user_id = _resolve_effective_user_id(None, current_user)
    stored = MULTIVIEW_SPECS_STORE.get(garment_id)
    if stored and stored[0] == effective_user_id:
        spec = stored[1]
    else:
        from backend.app.services.garments.job_manager import garment_job_manager
        try:
            persisted = garment_job_manager._postgres_adapter.load_garment_evidence_spec(garment_id, effective_user_id)
        except Exception as exc:
            logger.error("Durable evidence specification read failed", exc_info=True)
            raise HTTPException(status_code=503, detail="Evidence storage is unavailable.") from exc
        if not persisted:
            raise HTTPException(status_code=404, detail=f"No multi-view specification found for garment_id '{garment_id}'.")
        spec = CanonicalGarmentSpecificationV2.model_validate(persisted)
    if stored and stored[0] != effective_user_id:
        raise HTTPException(status_code=404, detail=f"No multi-view specification found for garment_id '{garment_id}'.")

    return {
        "garment_id": spec.garment_id,
        "views_count": len(spec.views),
        "views": [v.model_dump() if hasattr(v, 'model_dump') else v.dict() for v in spec.views],
        "conflicts": [c.model_dump() if hasattr(c, 'model_dump') else c.dict() for c in spec.conflicts],
        "reconstruction_readiness": spec.reconstruction_readiness.model_dump() if hasattr(spec.reconstruction_readiness, 'model_dump') else spec.reconstruction_readiness.dict(),
        "property_evidence": {k: v.model_dump() if hasattr(v, 'model_dump') else v.dict() for k, v in spec.property_evidence.items()}
    }


@router.get(
    "/{garment_id}/specification",
    response_model=CanonicalGarmentSpecificationV2,
    summary="Get latest Canonical Garment Specification V2"
)
async def get_garment_specification_endpoint(
    garment_id: str,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
) -> CanonicalGarmentSpecificationV2:
    """Returns the full CanonicalGarmentSpecificationV2 for a garment."""
    from backend.app.api.garment_generation_routes import _resolve_effective_user_id
    effective_user_id = _resolve_effective_user_id(None, current_user)
    stored = MULTIVIEW_SPECS_STORE.get(garment_id)
    if stored and stored[0] == effective_user_id:
        spec = stored[1]
    else:
        from backend.app.services.garments.job_manager import garment_job_manager
        try:
            persisted = garment_job_manager._postgres_adapter.load_garment_evidence_spec(garment_id, effective_user_id)
        except Exception as exc:
            logger.error("Durable evidence specification read failed", exc_info=True)
            raise HTTPException(status_code=503, detail="Evidence storage is unavailable.") from exc
        if not persisted:
            raise HTTPException(status_code=404, detail=f"No multi-view specification found for garment_id '{garment_id}'.")
        spec = CanonicalGarmentSpecificationV2.model_validate(persisted)
    if stored and stored[0] != effective_user_id:
        raise HTTPException(status_code=404, detail=f"No multi-view specification found for garment_id '{garment_id}'.")
    return spec


@router.post(
    "/{garment_id}/validate",
    summary="Validate specification evidence integrity and non-fabrication rules"
)
async def validate_garment_specification_endpoint(
    garment_id: str,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """Validates that OBSERVED properties cite source images and UNKNOWN properties have no fake confidence."""
    from backend.app.api.garment_generation_routes import _resolve_effective_user_id
    effective_user_id = _resolve_effective_user_id(None, current_user)
    stored = MULTIVIEW_SPECS_STORE.get(garment_id)
    if stored and stored[0] == effective_user_id:
        spec = stored[1]
    else:
        from backend.app.services.garments.job_manager import garment_job_manager
        try:
            persisted = garment_job_manager._postgres_adapter.load_garment_evidence_spec(garment_id, effective_user_id)
        except Exception as exc:
            logger.error("Durable evidence specification read failed", exc_info=True)
            raise HTTPException(status_code=503, detail="Evidence storage is unavailable.") from exc
        if not persisted:
            raise HTTPException(status_code=404, detail=f"No multi-view specification found for garment_id '{garment_id}'.")
        spec = CanonicalGarmentSpecificationV2.model_validate(persisted)
    if stored and stored[0] != effective_user_id:
        raise HTTPException(status_code=404, detail=f"No multi-view specification found for garment_id '{garment_id}'.")
    errors = spec.validate_evidence_integrity()
    return {
        "garment_id": garment_id,
        "valid": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "readiness_status": spec.reconstruction_readiness.status,
        "missing_evidence": spec.reconstruction_readiness.missing_evidence,
        "status_message": "Specification evidence integrity verified" if not errors else "Evidence integrity violations detected"
    }


@router.post(
    "/{garment_id}/construction-plan",
    summary="Build Phase 16.2 construction graph, 2D pattern geometry, assembly validation, and optional SVG/DXF export"
)
async def build_garment_construction_plan_endpoint(
    garment_id: str,
    include_svg: bool = Form(False),
    include_dxf: bool = Form(False),
    fit: str = Form("regular"),
    current_user: Optional[UserContext] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """Convert stored V2 multi-view & component evidence into a validated Phase 16.2 construction handoff."""
    from backend.app.api.garment_generation_routes import _resolve_effective_user_id
    from backend.app.services.intelligence.pattern_construction_engine import pattern_construction_engine
    from backend.app.services.garments.reconstruction.engine_registry import reconstruction_registry
    from backend.app.services.garments.reconstruction.pattern_exporter import export_pattern_dxf, export_pattern_svg

    effective_user_id = _resolve_effective_user_id(None, current_user)
    stored = MULTIVIEW_SPECS_STORE.get(garment_id)
    if stored and stored[0] == effective_user_id:
        spec = stored[1]
    else:
        from backend.app.services.garments.job_manager import garment_job_manager
        persisted = garment_job_manager._postgres_adapter.load_garment_evidence_spec(garment_id, effective_user_id)
        if not persisted:
            raise HTTPException(status_code=404, detail=f"No multi-view specification found for garment_id '{garment_id}'.")
        spec = CanonicalGarmentSpecificationV2.model_validate(persisted)

    handoff = await run_in_threadpool(
        pattern_construction_engine.build_construction,
        garment_id=spec.garment_id,
        category=spec.garment.category,
        subcategory=spec.garment.subcategory,
        specification=spec,
        fit=fit,
    )
    compat = reconstruction_registry.validate_construction_handoff(handoff)
    payload: Dict[str, Any] = {
        "handoff": handoff.model_dump(mode="json"),
        "registry_compatibility": compat,
    }
    if include_svg:
        payload["svg"] = export_pattern_svg(handoff)
    if include_dxf:
        payload["dxf"] = export_pattern_dxf(handoff)
    return payload


@router.post(
    "/multiview-reconstruct",
    summary="Validate a V2 specification and submit its source views to the persistent reconstruction job pipeline"
)
async def multiview_reconstruct_endpoint(
    specification_json: str = Form(..., description="CanonicalGarmentSpecificationV2 JSON from multiview-identify"),
    images: List[UploadFile] = File(..., description="The same source images in the same order as the specification views"),
    user_id: str = Form("default_user"),
    final_category: Optional[str] = Form(None),
    final_subcategory: Optional[str] = Form(None),
    idempotency_key: Optional[str] = Form(None),
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """Persist a validated V2 evidence handoff through the existing queued reconstruction system."""
    try:
        specification = CanonicalGarmentSpecificationV2.model_validate_json(specification_json)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid canonical V2 specification: {exc}") from exc

    integrity_errors = specification.validate_evidence_integrity()
    if integrity_errors:
        raise HTTPException(status_code=422, detail={"message": "Evidence integrity validation failed", "errors": integrity_errors})
    if specification.reconstruction_readiness.status in ("INSUFFICIENT_EVIDENCE", "CONFLICTED"):
        raise HTTPException(
            status_code=409,
            detail=f"Reconstruction is blocked while evidence readiness is {specification.reconstruction_readiness.status}."
        )
    if len(images) != len(specification.views):
        raise HTTPException(status_code=422, detail="Upload images must match the specification view count and order.")
    if not images or len(images) > MAX_IMAGES_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f"Provide between 1 and {MAX_IMAGES_PER_REQUEST} source images.")

    from backend.app.api.garment_generation_routes import _resolve_effective_user_id
    from backend.app.services.garments.job_manager import garment_job_manager, DurablePersistenceUnavailableError, QueueEnqueueError
    from backend.app.services.garments.orchestration.unified_state_machine import (
        BANNED_IDENTITIES,
        IdempotencyConflictException,
        TenantSecurityViolationException,
    )
    from backend.app.services.garments.orchestration.queue_broker import (
        QueueOverloadedException,
        ConcurrencyLimitExceededException,
    )
    from backend.app.services.billing.entitlement_service import entitlement_service

    effective_user_id = _resolve_effective_user_id(user_id, current_user, allow_guest=False)
    if str(effective_user_id).strip().lower() in BANNED_IDENTITIES:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "Authentication required before 3D garment reconstruction can start.", "retryable": False},
        )
    images_by_view: Dict[str, bytes] = {}
    total_bytes = 0
    for upload, evidence in zip(images, specification.views):
        if not upload.content_type or not upload.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"Source for view '{evidence.image_id}' is not an image.")
        contents = await upload.read()
        total_bytes += len(contents)
        if not contents or len(contents) > MAX_IMAGE_FILE_SIZE_BYTES:
            raise HTTPException(status_code=413, detail=f"Source image '{evidence.image_id}' is empty or exceeds the per-image limit.")
        if hashlib.sha256(contents).hexdigest() != evidence.image_hash:
            raise HTTPException(status_code=409, detail=f"Source image bytes do not match evidence record '{evidence.image_id}'.")
        try:
            with Image.open(io.BytesIO(contents)) as image:
                image.verify()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Source image '{evidence.image_id}' cannot be decoded.") from exc
        if evidence.usable:
            images_by_view.setdefault(evidence.view_type.lower(), contents)

    if total_bytes > MAX_TOTAL_BATCH_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Source image batch exceeds the total size limit.")
    front_bytes = images_by_view.get("front")
    if front_bytes is None:
        raise HTTPException(status_code=422, detail="A usable front view is required before reconstruction can start.")

    final_input = {
        "category": final_category or specification.garment.category,
        "subcategory": final_subcategory or specification.garment.subcategory
    }
    detection_metadata = {
        "canonical_specification_v2": specification.model_dump(mode="json"),
        "canonical_specification_version": specification.specification_version,
        "canonical_specification_garment_id": specification.garment_id,
        "evidence_integrity_validated": True,
        "evidence_image_hashes": [view.image_hash for view in specification.views],
        "user_correction_state": {"final_reconstruction_input": final_input}
    }

    allowed, reason = entitlement_service.reserve_reconstruction_slot(effective_user_id)
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)
    try:
        job = await run_in_threadpool(garment_job_manager.create_job,
            user_id=effective_user_id,
            front_image_bytes=front_bytes,
            category=str(final_input["category"]),
            subcategory=str(final_input["subcategory"]),
            back_image_bytes=images_by_view.get("back"),
            side_image_bytes=images_by_view.get("side") or images_by_view.get("left_side") or images_by_view.get("right_side"),
            detail_image_bytes=images_by_view.get("detail"),
            detection_metadata=detection_metadata,
            idempotency_key=idempotency_key
        )
    except PermissionError as perm_exc:
        entitlement_service.release_reconstruction_slot(effective_user_id)
        raise HTTPException(
            status_code=403,
            detail={"code": "ENTITLEMENT_QUOTA_EXCEEDED", "message": str(perm_exc), "retryable": False},
        ) from perm_exc
    except TenantSecurityViolationException as sec_exc:
        entitlement_service.release_reconstruction_slot(effective_user_id)
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHENTICATED_RECONSTRUCTION", "message": str(sec_exc), "retryable": False},
        ) from sec_exc
    except IdempotencyConflictException as ice:
        entitlement_service.release_reconstruction_slot(effective_user_id)
        raise HTTPException(
            status_code=409,
            detail={"code": "IDEMPOTENCY_CONFLICT", "message": str(ice), "retryable": False},
        ) from ice
    except (QueueOverloadedException, ConcurrencyLimitExceededException) as q_exc:
        entitlement_service.release_reconstruction_slot(effective_user_id)
        raise HTTPException(
            status_code=429,
            detail={"code": "RECONSTRUCTION_QUEUE_BUSY", "message": str(q_exc), "retryable": True},
        ) from q_exc
    except (DurablePersistenceUnavailableError, QueueEnqueueError) as dur_exc:
        entitlement_service.release_reconstruction_slot(effective_user_id)
        raise HTTPException(
            status_code=503,
            detail={"code": dur_exc.code, "message": str(dur_exc), "retryable": True},
        ) from dur_exc
    except Exception:
        entitlement_service.release_reconstruction_slot(effective_user_id)
        raise

    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "current_stage": job.current_stage,
        "created_at": job.created_at.isoformat(),
        "canonical_specification_version": specification.specification_version,
        "evidence_integrity_validated": True
    }


@router.get(
    "/multiview/health",
    summary="Get multi-view subsystem operational health, limits, and view options"
)
async def get_multiview_subsystem_health() -> Dict[str, Any]:
    """Returns multi-view pipeline health, supported viewpoints, and file upload limits."""
    provider_health = ai_orchestrator.get_provider_health()
    vision_provider_names = ("gemini_vision", "local_cv")
    configured_providers = [
        name for name in vision_provider_names
        if name in provider_health
        for health in (provider_health[name],)
        if health.get("state") in ("configured", "available", "authenticated")
    ]
    return {
        "status": "configured" if configured_providers else "degraded",
        "configured_providers": configured_providers,
        "provider_health": provider_health,
        "subsystem": "MultiViewGarmentFusionEngine_v14_27",
        "supported_viewpoints": [v.value for v in GarmentViewType],
        "max_images_per_request": MAX_IMAGES_PER_REQUEST,
        "max_cached_specifications": MAX_CACHED_MULTIVIEW_SPECS,
        "max_file_size_mb": MAX_IMAGE_FILE_SIZE_BYTES // (1024 * 1024),
        "decompression_bomb_limit_pixels": Image.MAX_IMAGE_PIXELS,
        "cached_garments_count": len(MULTIVIEW_SPECS_STORE)
    }
