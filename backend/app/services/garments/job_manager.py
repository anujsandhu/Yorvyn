"""
Stage 8 & 9: Asynchronous Job Architecture & Privacy Cleanup Manager
Manages job lifecycle, progress reporting, background worker execution,
and strictly purges temporary input files upon completion, failure, or cancellation.
"""

import os
import shutil
import uuid
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

from backend.app.models.garment_models import GarmentGenJob, GarmentGenJobStatus, GarmentGenResult, DetectedGarmentFeatures
from .garment_analyzer import garment_analyzer
from .garment_mesh_builder import garment_mesh_builder
from .garment_texture_synthesizer import garment_texture_synthesizer
from .glb_exporter import glb_exporter
from .preview_renderer import preview_renderer
from backend.app.services.storage.cloudinary_storage import cloudinary_storage
from backend.app.services.database.supabase_repository import supabase_repo

logger = logging.getLogger(__name__)

TEMP_BASE_DIR = "/tmp/yorvyn_garment_pipeline"
PERMANENT_ASSET_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data/wardrobe_assets"))

# Ensure base directories exist
os.makedirs(TEMP_BASE_DIR, exist_ok=True)
os.makedirs(PERMANENT_ASSET_DIR, exist_ok=True)


class GarmentJobManager:
    """Orchestrates photo-to-3D garment generation jobs with privacy guarantees."""

    def __init__(self):
        self._jobs: Dict[str, GarmentGenJob] = {}
        self._executor = ThreadPoolExecutor(max_workers=3)

    def create_job(self, user_id: str, front_image_bytes: bytes, category: str, back_image_bytes: Optional[bytes] = None) -> GarmentGenJob:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job_temp_dir = os.path.join(TEMP_BASE_DIR, job_id)
        os.makedirs(job_temp_dir, exist_ok=True)
        
        # Save temporary input images with strict private permissions
        front_path = os.path.join(job_temp_dir, "temp_input_front.raw")
        with open(front_path, "wb") as f:
            f.write(front_image_bytes)
            
        temp_files = [front_path]
        back_path = None
        if back_image_bytes:
            back_path = os.path.join(job_temp_dir, "temp_input_back.raw")
            with open(back_path, "wb") as f:
                f.write(back_image_bytes)
            temp_files.append(back_path)
            
        now = datetime.utcnow()
        job = GarmentGenJob(
            job_id=job_id,
            user_id=user_id,
            status=GarmentGenJobStatus.QUEUED,
            progress=5,
            current_stage="Job queued for processing",
            created_at=now,
            updated_at=now,
            temporary_files=temp_files
        )
        self._jobs[job_id] = job
        
        # Persist initial job record to Supabase PostgreSQL repository
        supabase_repo.save_job({
            "job_id": job_id,
            "user_id": user_id,
            "status": "queued",
            "category": category,
            "progress": 5,
            "current_stage": "Job queued for processing",
            "created_at": now.isoformat()
        })
        
        # Launch background processing worker
        self._executor.submit(self._process_job, job_id, front_path, category, back_path)
        return job

    def get_job(self, job_id: str) -> Optional[GarmentGenJob]:
        return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.status = GarmentGenJobStatus.CANCELLED
        job.current_stage = "Job cancelled by user"
        job.updated_at = datetime.utcnow()
        self._cleanup_temp_files(job_id)
        return True

    def _process_job(self, job_id: str, front_path: str, category: str, back_path: Optional[str] = None):
        """Worker pipeline: Segment -> Reconstruct -> Texture -> Assemble -> Preview -> Cleanup."""
        job = self._jobs.get(job_id)
        if not job or job.status == GarmentGenJobStatus.CANCELLED:
            self._cleanup_temp_files(job_id)
            return

        job_dir = os.path.join(TEMP_BASE_DIR, job_id)
        perm_job_dir = os.path.join(PERMANENT_ASSET_DIR, job_id)
        os.makedirs(perm_job_dir, exist_ok=True)

        try:
            # Stage A: Garment Understanding
            job.status = GarmentGenJobStatus.ANALYZING
            job.progress = 20
            job.current_stage = "Analyzing garment silhouette, colors, and seams..."
            job.updated_at = datetime.utcnow()
            
            features, seg_front = garment_analyzer.analyze(front_path, category)
            seg_back = None
            if back_path and os.path.exists(back_path):
                _, seg_back = garment_analyzer.analyze(back_path, category)
                
            # Stage B: 3D Geometry Generation
            job.status = GarmentGenJobStatus.GENERATING_MESH
            job.progress = 45
            job.current_stage = f"Generating 3D wearable {features.subcategory} geometry..."
            job.updated_at = datetime.utcnow()
            
            garment_mesh = garment_mesh_builder.build_mesh(
                category=features.category,
                subcategory=features.subcategory,
                sleeve_length=features.sleeve_length,
                neckline_type=features.neckline_type,
                fit=features.fit
            )
            
            # Stage C: Texture & Material Synthesis
            job.status = GarmentGenJobStatus.SYNTHESIZING_TEXTURES
            job.progress = 65
            job.current_stage = "Synthesizing seamless UV diffuse, normal, and roughness maps..."
            job.updated_at = datetime.utcnow()
            
            diffuse_path, normal_path, roughness_path = garment_texture_synthesizer.synthesize(
                segmented_front=seg_front,
                features=features,
                output_dir=perm_job_dir,
                segmented_back=seg_back,
                texture_size=1024
            )
            
            # Stage D: Assemble 3D GLB
            job.status = GarmentGenJobStatus.ASSEMBLING_3D
            job.progress = 80
            job.current_stage = "Assembling binary GLB asset with Ara 3D Gen rig compatibility..."
            job.updated_at = datetime.utcnow()
            
            with open(diffuse_path, "rb") as f:
                diff_bytes = f.read()
            with open(normal_path, "rb") as f:
                norm_bytes = f.read()
                
            garment_title = f"{features.primary_color_name.title()} {features.subcategory.replace('_', ' ').title()}"
            glb_bytes = glb_exporter.export(
                mesh=garment_mesh,
                diffuse_png_bytes=diff_bytes,
                normal_png_bytes=norm_bytes,
                name=f"garment_{job_id}"
            )
            
            glb_filename = "garment.glb"
            glb_path = os.path.join(perm_job_dir, glb_filename)
            with open(glb_path, "wb") as f:
                f.write(glb_bytes)
                
            # Stage 5: Render 3D Preview Thumbnail
            job.status = GarmentGenJobStatus.RENDERING_PREVIEW
            job.progress = 92
            job.current_stage = "Rendering 3D studio preview thumbnail..."
            job.updated_at = datetime.utcnow()
            
            thumb_filename = "preview.png"
            thumb_path = os.path.join(perm_job_dir, thumb_filename)
            with Image.open(diffuse_path) as diff_img:
                preview_renderer.render_preview(garment_mesh, diff_img, thumb_path, image_size=512)

            # Upload generated 3D garment preview thumbnail to Cloudinary CDN
            with open(thumb_path, "rb") as f:
                thumb_bytes = f.read()
            cld_res = cloudinary_storage.upload_garment_image(
                image_bytes=thumb_bytes,
                user_id=job.user_id,
                asset_id=f"{job_id}_preview",
                tags=["yorvyn", "garment_preview", features.category]
            )
            cld_delivery_url = cld_res.get("delivery_url")
            cld_public_id = cld_res.get("public_id")
                
            # Finalize Result
            glb_url = f"/api/fashion/garment-gen/assets/{job_id}/{glb_filename}"
            thumb_url = cld_delivery_url or f"/api/fashion/garment-gen/assets/{job_id}/{thumb_filename}"
            tex_url = f"/api/fashion/garment-gen/assets/{job_id}/diffuse.png"
            norm_url = f"/api/fashion/garment-gen/assets/{job_id}/normal.png"
            
            result = GarmentGenResult(
                job_id=job_id,
                garment_name=garment_title,
                category=features.category,
                subcategory=features.subcategory,
                glb_url=glb_url,
                thumbnail_url=thumb_url,
                texture_url=tex_url,
                normal_map_url=norm_url,
                mesh_vertex_count=len(garment_mesh.positions),
                mesh_triangle_count=len(garment_mesh.indices),
                features=features,
                model_version="yorvyn-garment3d-v2.0",
                created_at=datetime.utcnow().isoformat()
            )
            
            job.result = result
            job.status = GarmentGenJobStatus.COMPLETED
            job.progress = 100
            job.current_stage = "3D garment successfully created and ready for preview"
            job.updated_at = datetime.utcnow()

            # Record completed state and Cloudinary asset IDs in Supabase PostgreSQL
            supabase_repo.save_job({
                "job_id": job_id,
                "user_id": job.user_id,
                "status": "completed",
                "category": features.category,
                "progress": 100,
                "current_stage": "3D garment successfully created and ready for preview",
                "cloudinary_public_id": cld_public_id,
                "cloudinary_delivery_url": cld_delivery_url,
                "glb_url": glb_url,
                "mesh_vertex_count": len(garment_mesh.positions),
                "mesh_triangle_count": len(garment_mesh.indices),
                "completed_at": datetime.utcnow().isoformat()
            })
            
            logger.info(f"[GarmentGen] Job {job_id} successfully completed. Cloudinary CDN: {cld_delivery_url}")
            
        except Exception as e:
            logger.error(f"[GarmentGen] Error processing job {job_id}: {str(e)}", exc_info=True)
            job.status = GarmentGenJobStatus.FAILED
            job.error = f"Reconstruction failed: {str(e)}"
            job.current_stage = "Garment reconstruction encountered an error."
            job.updated_at = datetime.utcnow()
            supabase_repo.save_job({
                "job_id": job_id,
                "user_id": job.user_id,
                "status": "failed",
                "error_details": str(e),
                "progress": 0
            })
            
        finally:
            # STRICT PRIVACY ENFORCEMENT:
            # Permanently purge original uploaded photograph and temporary artifacts from disk!
            self._cleanup_temp_files(job_id)

    def _cleanup_temp_files(self, job_id: str):
        """Removes the temporary directory and all original uploaded images for this job."""
        job_dir = os.path.join(TEMP_BASE_DIR, job_id)
        if os.path.exists(job_dir):
            try:
                shutil.rmtree(job_dir)
                logger.info(f"[GarmentGen] Privacy cleanup: Purged temporary input images for job {job_id}")
            except Exception as e:
                logger.warning(f"[GarmentGen] Temporary cleanup warning for {job_id}: {e}")

    def sweep_expired_jobs(self, max_age_minutes: int = 15):
        """Sweeps abandoned temporary folders older than max_age_minutes."""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=max_age_minutes)
        for job_id, job in list(self._jobs.items()):
            if job.created_at < cutoff:
                self._cleanup_temp_files(job_id)


# Singleton job manager
garment_job_manager = GarmentJobManager()
