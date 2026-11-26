"""
FastAPI Router for AI Photo-to-3D Garment Generation Pipeline.
Endpoints for upload, job tracking, cancellation, preview asset serving, and wardrobe saving.
"""

import os
import uuid
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Response, Depends, Request, Header
from fastapi.responses import FileResponse

from backend.app.core.security import get_current_user_optional, UserContext
from backend.app.models.garment_models import GarmentGenJob, GarmentGenJobStatus
from backend.app.services.garments.job_manager import garment_job_manager, PERMANENT_ASSET_DIR
from backend.app.services.wardrobe_service import wardrobe_service

router = APIRouter(prefix="/api/fashion/garment-gen", tags=["Photo-to-3D Garment Generation"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB

from fastapi.params import Depends as DependsClass

def _is_registered_user_id(uid: Optional[str]) -> bool:
    if not uid or uid in ("default_user", "guest", "anonymous"):
        return False
    if uid.startswith("usr_"):
        return True
    if len(uid) == 36 and uid.count("-") == 4:
        return True
    return False

def _resolve_effective_user_id(
    client_user_id: Optional[str],
    current_user: Optional[UserContext],
    allow_guest: bool = True
) -> str:
    """Enforces cross-tenant isolation and authentication boundaries on generation jobs."""
    if isinstance(current_user, DependsClass):
        return client_user_id or "default_user"

    if isinstance(current_user, UserContext):
        if client_user_id and client_user_id not in ("default_user", current_user.user_id):
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Cross-tenant data access is not permitted."
            )
        return current_user.user_id

    if not allow_guest:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: Please provide a valid Bearer token."
        )

    if _is_registered_user_id(client_user_id):
        raise HTTPException(
            status_code=401,
            detail="Authentication required to access registered user records."
        )

    return client_user_id or "default_user"


def _assert_job_ownership(job: GarmentGenJob, current_user: Optional[UserContext]):
    """Strictly validates whether current_user owns the job."""
    if isinstance(current_user, DependsClass):
        return

    if _is_registered_user_id(job.user_id):
        if not isinstance(current_user, UserContext):
            raise HTTPException(
                status_code=401,
                detail="Authentication required: This job belongs to a registered user."
            )
        if job.user_id != current_user.user_id:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: You do not have permission to access this job."
            )
    elif isinstance(current_user, UserContext):
        if job.user_id != "default_user" and job.user_id != current_user.user_id:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: You do not have permission to access this job."
            )


@router.post("/analyze")
async def analyze_garment_photo(
    front_image: UploadFile = File(...),
    back_image: Optional[UploadFile] = File(None),
    side_image: Optional[UploadFile] = File(None),
    detail_image: Optional[UploadFile] = File(None),
    user_corrections: Optional[str] = Form(None),
    user_id: str = Form("default_user"),
    session_id: Optional[str] = Form(None),
    search_id: Optional[str] = Form(None),
    inference_id: Optional[str] = Form(None),
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """
    AI-First automatic garment perception endpoint.
    Performs autonomous multi-task understanding without manual user configuration:
    detects garment identity, fabric family, composition, construction, colour,
    fit silhouette, components, and multi-view observation telemetry.
    Preserves original predictions while capturing user correction provenance.
    """
    effective_uid = _resolve_effective_user_id(user_id, current_user)

    # 1. Validate front image
    front_ext = os.path.splitext(front_image.filename or "")[1].lower()
    if front_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image format '{front_ext}'. Please upload a PNG, JPG, or WEBP photograph."
        )
    front_bytes = await front_image.read()
    if len(front_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Front image exceeds 15MB limit.")
    if len(front_bytes) < 1024:
        raise HTTPException(status_code=400, detail="Front image file is empty or corrupted.")

    import io
    import json
    from PIL import Image
    from backend.app.services.garments.intelligence.automatic_garment_detector import automatic_garment_detector

    front_pil = Image.open(io.BytesIO(front_bytes)).convert("RGB")

    back_pil = None
    if back_image and back_image.filename:
        b_bytes = await back_image.read()
        if len(b_bytes) >= 1024:
            back_pil = Image.open(io.BytesIO(b_bytes)).convert("RGB")

    side_pil = None
    if side_image and side_image.filename:
        s_bytes = await side_image.read()
        if len(s_bytes) >= 1024:
            side_pil = Image.open(io.BytesIO(s_bytes)).convert("RGB")

    detail_pil = None
    if detail_image and detail_image.filename:
        d_bytes = await detail_image.read()
        if len(d_bytes) >= 1024:
            detail_pil = Image.open(io.BytesIO(d_bytes)).convert("RGB")

    corrections_dict = None
    if user_corrections:
        try:
            corrections_dict = json.loads(user_corrections)
        except Exception:
            corrections_dict = None

    result = automatic_garment_detector.detect(
        front_image=front_pil,
        back_image=back_pil,
        side_image=side_pil,
        detail_image=detail_pil,
        user_corrections=corrections_dict,
        session_id=session_id,
        search_id=search_id,
        inference_id=inference_id,
        user_id=effective_uid
    )

    return result.model_dump()


@router.post("/detect-instances")
async def detect_garment_instances(
    image: UploadFile = File(...),
    category_hint: Optional[str] = Form(None),
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """
    Multi-garment instance detection & segmentation endpoint (Phase 14.2).
    Detects and isolates every wearable garment in outfit grids, flat-lays, and on-body scenes.
    """
    ext = os.path.splitext(image.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image format '{ext}'. Please upload a PNG, JPG, or WEBP photograph."
        )
    img_bytes = await image.read()
    if len(img_bytes) < 1024:
        raise HTTPException(status_code=400, detail="Image file is empty or corrupted.")

    import io
    from PIL import Image
    from backend.app.services.garments.intelligence.garment_instance_detector import garment_instance_detector

    pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    scene = garment_instance_detector.detect_instances(pil_img, category_hint=category_hint)
    return scene.model_dump()


@router.post("/feedback")
@router.post("/learning-signal")
async def submit_garment_learning_feedback(
    request: Request,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """
    Captures fine-grained user corrections and feedback signals on garment perception
    and 3D reconstruction, routing through continuous learning memory and pipelines.
    """
    from backend.app.services.garments.intelligence.automatic_garment_detector import automatic_garment_detector
    body = await request.json()
    effective_uid = current_user.user_id if current_user else (body.get("user_id") or "default_user")

    event_type = body.get("event_type", "reconstruction_acceptance")
    inference_id = body.get("inference_id") or f"inf_{uuid.uuid4().hex[:12]}"
    original_pred = body.get("original_value") or body.get("original_prediction") or {}
    corrected_val = body.get("corrected_value") or body.get("user_correction") or {}

    res = automatic_garment_detector.record_user_correction_signal(
        inference_id=inference_id,
        user_id=effective_uid,
        event_type=event_type,
        original_prediction=original_pred,
        user_correction=corrected_val,
        session_id=body.get("session_id"),
        search_id=body.get("search_id"),
        feedback_text=body.get("feedback_text"),
        rating=body.get("rating"),
        metadata=body.get("metadata") or {}
    )

    return res


@router.post("/jobs")
async def create_generation_job(
    front_image: UploadFile = File(...),
    back_image: Optional[UploadFile] = File(None),
    side_image: Optional[UploadFile] = File(None),
    detail_image: Optional[UploadFile] = File(None),
    category: Optional[str] = Form(None),
    subcategory: Optional[str] = Form(None),
    user_id: str = Form("default_user"),
    detection_metadata: Optional[str] = Form(None),
    idempotency_key: Optional[str] = Form(None),
    current_user: Optional[UserContext] = Depends(get_current_user_optional),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key")
):
    """
    Submits a clothing photograph for AI 3D garment reconstruction.
    Category is optional: Yorvyn automatically uses detected AI model attributes.
    The input images are temporarily processed and purged immediately after completion.
    """
    effective_uid = _resolve_effective_user_id(user_id, current_user)
    effective_idem_key = idempotency_key or x_idempotency_key

    from backend.app.core.upload_validation import read_and_validate_image_upload

    # 1. Validate front image (streaming size, magic bytes, pixel dimensions)
    front_bytes = await read_and_validate_image_upload(front_image, field_name="front_image", min_bytes=64)

    # 2. Validate optional back, side, and detail images
    back_bytes = None
    if back_image and back_image.filename:
        back_bytes = await read_and_validate_image_upload(back_image, field_name="back_image", min_bytes=64)

    side_bytes = None
    if side_image and side_image.filename:
        side_bytes = await read_and_validate_image_upload(side_image, field_name="side_image", min_bytes=64)

    detail_bytes = None
    if detail_image and detail_image.filename:
        detail_bytes = await read_and_validate_image_upload(detail_image, field_name="detail_image", min_bytes=64)

    import json
    parsed_metadata = None
    if detection_metadata:
        try:
            parsed_metadata = json.loads(detection_metadata)
        except Exception:
            parsed_metadata = None

    # 3. Server-side entitlement validation & atomic slot reservation
    from backend.app.services.billing.entitlement_service import entitlement_service
    allowed, reason = entitlement_service.reserve_reconstruction_slot(effective_uid)
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)

    # 4. Create asynchronous job with PostgreSQL persistence & Redis Streams publication
    try:
        from backend.app.services.garments.orchestration.unified_state_machine import (
            IdempotencyConflictException,
            TenantSecurityViolationException,
        )
        from backend.app.services.garments.orchestration.queue_broker import (
            QueueOverloadedException,
            ConcurrencyLimitExceededException,
        )
        from backend.app.services.garments.job_manager import (
            DurablePersistenceUnavailableError,
            QueueEnqueueError,
        )
        job = garment_job_manager.create_job(
            user_id=effective_uid,
            front_image_bytes=front_bytes,
            category=category,
            subcategory=subcategory,
            back_image_bytes=back_bytes,
            side_image_bytes=side_bytes,
            detail_image_bytes=detail_bytes,
            detection_metadata=parsed_metadata,
            idempotency_key=effective_idem_key
        )
    except PermissionError as perm_exc:
        entitlement_service.release_reconstruction_slot(effective_uid)
        raise HTTPException(
            status_code=403,
            detail={"code": "ENTITLEMENT_QUOTA_EXCEEDED", "message": str(perm_exc), "retryable": False},
        ) from perm_exc
    except TenantSecurityViolationException as sec_exc:
        entitlement_service.release_reconstruction_slot(effective_uid)
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHENTICATED_RECONSTRUCTION", "message": str(sec_exc), "retryable": False},
        )
    except IdempotencyConflictException as ice:
        entitlement_service.release_reconstruction_slot(effective_uid)
        raise HTTPException(status_code=409, detail=str(ice))
    except (QueueOverloadedException, ConcurrencyLimitExceededException) as q_exc:
        entitlement_service.release_reconstruction_slot(effective_uid)
        raise HTTPException(status_code=429, detail=str(q_exc))
    except (DurablePersistenceUnavailableError, QueueEnqueueError) as dur_exc:
        entitlement_service.release_reconstruction_slot(effective_uid)
        raise HTTPException(
            status_code=503,
            detail={"code": dur_exc.code, "message": str(dur_exc), "retryable": True},
        )
    except Exception:
        entitlement_service.release_reconstruction_slot(effective_uid)
        raise
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "current_stage": job.current_stage,
        "created_at": job.created_at.isoformat()
    }


@router.get("/jobs/{job_id}/artifact")
async def get_job_canonical_artifact(
    job_id: str,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """
    Serves the canonical GLB 3D model generated and published under fenced atomic commit.
    Enforces tenant isolation, ownership verification, and path security.
    """
    job = garment_job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    _assert_job_ownership(job, current_user)

    canon_p = Path(PERMANENT_ASSET_DIR) / f"{job_id}.glb"
    legacy_p = Path(PERMANENT_ASSET_DIR) / job_id / "garment.glb"
    staging_p = Path(__file__).resolve().parents[4] / "models" / "generated_3d" / "staging_jobs" / f"{job_id}.glb"

    chosen_p = None
    paths = [canon_p] if os.getenv("YORVYN_REQUIRE_DURABLE_SESSIONS") == "1" else [canon_p, legacy_p, staging_p]
    for p in paths:
        if p.exists() and p.stat().st_size > 0:
            chosen_p = p
            break

    if not chosen_p:
        raise HTTPException(status_code=404, detail="3D GLB artifact not found or generation not completed.")

    return FileResponse(
        str(chosen_p),
        media_type="model/gltf-binary",
        headers={"Content-Disposition": f"attachment; filename={job_id}.glb"}
    )


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Checks the progress and outputs of an ongoing 3D generation job."""
    job = garment_job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found.")
        
    _assert_job_ownership(job, current_user)

    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "current_stage": job.current_stage,
        "updated_at": job.updated_at.isoformat(),
        "error": job.error,
        "result": job.result.model_dump() if job.result else None
    }


@router.get("/jobs/{job_id}/diagnostics")
async def get_job_diagnostics(
    job_id: str,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """
    Retrieves deep neural garment intelligence diagnostics including alpha mask previews,
    boundary contours, internal opening holes, component bounding boxes, and anatomical landmarks.
    """
    job = garment_job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found.")
        
    _assert_job_ownership(job, current_user)

    diag = garment_job_manager.get_diagnostics(job_id)
    if not diag:
        return {
            "job_id": job_id,
            "status": job.status,
            "message": "Diagnostics are generated during the analysis stage."
        }

    return diag.model_dump()


@router.get("/neural-evaluations")
async def get_neural_reconstruction_evaluations():
    """
    Returns comparative technical evaluation of open-weight neural 3D generators
    (Microsoft TRELLIS, Tencent Hunyuan3D, InstantMesh, TripoSR, SF3D) against
    Apple Silicon M2 8GB hardware constraints and commercial licensing status.
    """
    from backend.app.services.garments.reconstruction.neural import LearnedModelEvaluator
    return LearnedModelEvaluator.get_summary_report()


@router.get("/appearance-evaluations")
async def get_appearance_model_evaluations():
    """
    Returns comparative technical evaluation of learned material classification,
    texture delighting, and texture inpainting models (FabricNet, SF3D Delighter,
    Paint3D, ControlNet Tile) against Apple Silicon M2 8GB constraints and licensing.
    """
    from backend.app.services.garments.appearance import AppearanceModelEvaluator
    return AppearanceModelEvaluator.get_summary_report()


@router.get("/avatar-profiles")
async def get_avatar_profiles():
    """
    Returns calibrated avatar measurement archetypes (Standard 1.75m, Athletic, Slim, Curvy/Plus)
    supporting universal garment fitting across 14 anatomical measurements.
    """
    from backend.app.services.garments.fitting import avatar_body_measurement_engine
    return {
        "profiles": avatar_body_measurement_engine.ARCHETYPES,
        "supported_measurements": [
            "height_cm", "shoulder_width_cm", "chest_circumference_cm",
            "waist_circumference_cm", "hip_circumference_cm", "neck_circumference_cm",
            "arm_length_cm", "upper_arm_circumference_cm", "wrist_circumference_cm",
            "inseam_cm", "thigh_circumference_cm", "calf_circumference_cm",
            "foot_length_cm", "foot_width_cm"
        ]
    }


@router.get("/avatar-profiles/{profile_id}")
async def get_avatar_profile(profile_id: str):
    """Retrieves a specific calibrated avatar measurement profile."""
    from backend.app.services.garments.fitting import avatar_body_measurement_engine
    if profile_id not in avatar_body_measurement_engine.ARCHETYPES:
        raise HTTPException(status_code=404, detail=f"Avatar profile '{profile_id}' not found.")
    return avatar_body_measurement_engine.get_profile(profile_id).model_dump()


@router.post("/jobs/{job_id}/cancel")
@router.delete("/jobs/{job_id}")
async def cancel_job(
    job_id: str,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Cancels a job and immediately purges all temporary files."""
    job = garment_job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or already completed.")

    _assert_job_ownership(job, current_user)

    success = garment_job_manager.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or already completed.")
    return {"message": "Job cancelled and temporary input purged."}


@router.post("/jobs/{job_id}/retry")
async def retry_job(
    job_id: str,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """Retries a failed reconstruction job if temporary inputs remain available."""
    job = garment_job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    _assert_job_ownership(job, current_user)

    retried = garment_job_manager.retry_job(job_id)
    if not retried:
        raise HTTPException(status_code=400, detail="Retry requires a failed job with its source photos available. If the photos expired, attach them again.")

    return {
        "job_id": retried.job_id,
        "status": retried.status,
        "retry_count": retried.retry_count,
        "current_stage": retried.current_stage
    }


@router.get("/health")
async def get_pipeline_health():
    """Provides operational health telemetry for the garment reconstruction worker pool."""
    return garment_job_manager.get_health_status()


@router.post("/jobs/{job_id}/save")
@router.post("/jobs/{job_id}/save-to-wardrobe")
async def save_to_wardrobe(
    job_id: str,
    user_id: str = "default_user",
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """
    Saves the approved generated 3D garment into the user's permanent wardrobe.
    CRITICAL: Only the generated 3D asset, textures, rendered preview, and metadata are saved.
    """
    job = garment_job_manager.get_job(job_id)
    if not job or job.status != GarmentGenJobStatus.COMPLETED or not job.result:
        raise HTTPException(status_code=400, detail="Job is not completed or missing generation results.")

    effective_uid = _resolve_effective_user_id(user_id, current_user)
    _assert_job_ownership(job, current_user)
        
    res = job.result
    
    # Construct wardrobe record
    item_payload = {
        "id": f"3d_{job_id}",
        "name": res.garment_name,
        "category": res.category,
        "subcategory": res.subcategory,
        "color": res.features.primary_color_name,
        "secondary_color": res.features.secondary_color_name or "",
        "material": res.features.material_hint,
        "pattern": res.features.pattern,
        "formality": res.features.formality,
        "warmth": res.features.warmth,
        "brand": "Custom Atelier 3D",
        "image_url": res.thumbnail_url, # DERIVED 3D RENDER PREVIEW (NOT ORIGINAL PHOTO!)
        "thumbnail_url": res.thumbnail_url,
        "glb_url": res.glb_url,
        "is_custom_3d": True,
        "model_version": res.model_version,
        "reconstruction_metadata": {
            "mesh_vertex_count": res.mesh_vertex_count,
            "mesh_triangle_count": res.mesh_triangle_count,
            "rig_compatibility": res.rig_compatibility,
            "palette": res.features.palette,
            "neckline": res.features.neckline_type,
            "sleeve_length": res.features.sleeve_length
        }
    }
    
    saved_item = wardrobe_service.add_item(user_id=effective_uid, item_data=item_payload)
    
    return {
        "success": True,
        "message": f"'{res.garment_name}' saved to My Wardrobe.",
        "item": saved_item
    }


@router.get("/assets/{job_id}/{filename}")
async def get_garment_asset(
    job_id: str,
    filename: str,
    request: Request,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """
    Serves the generated GLB models, diffuse textures, and rendered 3D preview thumbnails.
    Enforces tenant isolation, ownership verification, path traversal prevention,
    and private ETag caching (`Cache-Control: private, max-age=3600`, `Vary: Authorization`).
    """
    import hashlib
    from fastapi import Response

    # 1. Strict path traversal & character sanitization
    safe_filename = os.path.basename(filename)
    if safe_filename != filename or ".." in filename or "/" in filename or "\\" in filename or "\0" in filename:
        raise HTTPException(status_code=400, detail="Invalid or insecure filename.")

    # 2. Enforce job ownership & tenant boundary
    job = garment_job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Garment job unavailable.")
    _assert_job_ownership(job, current_user)

    asset_path = os.path.join(PERMANENT_ASSET_DIR, job_id, safe_filename)

    if not os.path.exists(asset_path):
        raise HTTPException(status_code=404, detail="Asset not found.")

    stat = os.stat(asset_path)
    etag = f'"{hashlib.sha256(f"{job_id}:{safe_filename}:{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()[:20]}"'
    private_headers = {
        "ETag": etag,
        "Cache-Control": "private, max-age=3600",
        "Vary": "Authorization",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=private_headers)

    media_type = "application/octet-stream"
    if safe_filename.endswith(".glb"):
        media_type = "model/gltf-binary"
    elif safe_filename.endswith(".png"):
        media_type = "image/png"
    elif safe_filename.endswith(".jpg") or safe_filename.endswith(".jpeg"):
        media_type = "image/jpeg"

    return FileResponse(asset_path, media_type=media_type, headers=private_headers)
