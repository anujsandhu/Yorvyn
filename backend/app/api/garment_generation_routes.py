"""
FastAPI Router for AI Photo-to-3D Garment Generation Pipeline.
Endpoints for upload, job tracking, cancellation, preview asset serving, and wardrobe saving.
"""

import os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Response
from fastapi.responses import FileResponse
from typing import Optional

from backend.app.models.garment_models import GarmentGenJob, GarmentGenJobStatus
from backend.app.services.garments.job_manager import garment_job_manager, PERMANENT_ASSET_DIR
from backend.app.services.wardrobe_service import wardrobe_service

router = APIRouter(prefix="/api/fashion/garment-gen", tags=["Photo-to-3D Garment Generation"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB


@router.post("/jobs")
async def create_generation_job(
    front_image: UploadFile = File(...),
    back_image: Optional[UploadFile] = File(None),
    category: str = Form("top"),
    user_id: str = Form("default_user")
):
    """
    Submits a clothing photograph for AI 3D garment reconstruction.
    The input images are temporarily processed and purged immediately after completion.
    """
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
        
    # 2. Validate optional back image
    back_bytes = None
    if back_image and back_image.filename:
        back_ext = os.path.splitext(back_image.filename)[1].lower()
        if back_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported back image format '{back_ext}'.")
        back_bytes = await back_image.read()
        if len(back_bytes) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="Back image exceeds 15MB limit.")

    # 3. Create asynchronous job
    job = garment_job_manager.create_job(
        user_id=user_id,
        front_image_bytes=front_bytes,
        category=category,
        back_image_bytes=back_bytes
    )
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "current_stage": job.current_stage,
        "created_at": job.created_at.isoformat()
    }


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Checks the progress and outputs of an ongoing 3D generation job."""
    job = garment_job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found.")
        
    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "current_stage": job.current_stage,
        "updated_at": job.updated_at.isoformat(),
        "error": job.error,
        "result": job.result.model_dump() if job.result else None
    }


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancels a job and immediately purges all temporary files."""
    success = garment_job_manager.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or already completed.")
    return {"message": "Job cancelled and temporary input purged."}


@router.post("/jobs/{job_id}/save")
async def save_to_wardrobe(job_id: str, user_id: str = "default_user"):
    """
    Saves the approved generated 3D garment into the user's permanent wardrobe.
    CRITICAL: Only the generated 3D asset, textures, rendered preview, and metadata are saved.
    """
    job = garment_job_manager.get_job(job_id)
    if not job or job.status != GarmentGenJobStatus.COMPLETED or not job.result:
        raise HTTPException(status_code=400, detail="Job is not completed or missing generation results.")
        
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
    
    saved_item = wardrobe_service.add_item(user_id=user_id, item_data=item_payload)
    
    return {
        "success": True,
        "message": f"'{res.garment_name}' saved to My Wardrobe.",
        "item": saved_item
    }


@router.get("/assets/{job_id}/{filename}")
async def get_garment_asset(job_id: str, filename: str):
    """Serves the generated GLB models, diffuse textures, and rendered 3D preview thumbnails."""
    safe_filename = os.path.basename(filename)
    asset_path = os.path.join(PERMANENT_ASSET_DIR, job_id, safe_filename)
    
    if not os.path.exists(asset_path):
        raise HTTPException(status_code=404, detail="Asset not found.")
        
    media_type = "application/octet-stream"
    if safe_filename.endswith(".glb"):
        media_type = "model/gltf-binary"
    elif safe_filename.endswith(".png"):
        media_type = "image/png"
    elif safe_filename.endswith(".jpg") or safe_filename.endswith(".jpeg"):
        media_type = "image/jpeg"
        
    return FileResponse(asset_path, media_type=media_type)
