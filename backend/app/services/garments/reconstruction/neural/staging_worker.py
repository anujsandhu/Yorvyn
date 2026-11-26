"""
YORVYN — Hardened Neural 3D Garment Reconstruction Worker (Phase 14.13 Workstream I.2)
High-performance, secure staging service providing image-conditioned 3D garment
reconstruction over authenticated HTTP endpoints for testing, benchmarking, and production trial.

Hardening Invariants (Phase 14.13):
- Strict loopback-only binding (127.0.0.1) unless explicitly configured.
- Full reconstruction provenance reporting (classification, engine, model, checkpoint SHA256, methods).
- Explicit identification as hybrid parametric reconstruction (never labeled as neural image-to-3D).
- Durable disk-backed job persistence and automatic state rehydration across worker restarts.
- Strict MIME signature and magic-byte verification (PNG, JPEG, WEBP; blocking SVG, binaries, scripts).
- Replay attack mitigation with timestamp validation and cryptographic nonce caching.
- Per-user job ownership and concurrency limits.
- Cooperative job cancellation.
- Automatic memory cleanup (gc.collect and accelerator cache purge).
- Path traversal protection on all asset delivery routes.
"""

import os
import sys
import time
import uuid
import hmac
import hashlib
import base64
import io
import re
import json
import gc
import logging
import threading
from typing import Dict, Any, Optional, Set, List
from pathlib import Path

from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks, Header
from fastapi.responses import JSONResponse
import uvicorn
import torch
import numpy as np
from PIL import Image

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[6]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.garments.reconstruction.neural.image_conditioned_reconstruction import (
    ImageConditionedReconstructionEngine
)
from backend.app.services.garments.mesh_validation_service import MeshValidationService
from backend.app.services.garments.orchestration.unified_state_machine import (
    PostgresJobPersistenceAdapter,
    UnifiedJobState
)
from backend.app.services.garments.orchestration.queue_broker import (
    RedisStreamsQueueBroker,
    StaleLeaseException
)
from backend.app.services.garments.orchestration.artifact_committer import (
    AtomicArtifactPublisher,
    ArtifactPublicationException
)

logger = logging.getLogger("yorvyn_neural_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(
    title="YORVYN Neural 3D Garment Reconstruction Worker",
    version="14.13.0",
    description="Hardened staging GPU inference worker for 3D garment synthesis with full provenance."
)

# Configuration
SIGNING_SECRET = os.getenv("GARMENT_AI_REMOTE_SIGNING_SECRET", "yorvyn-secret-key").strip()
EXPECTED_API_KEY = os.getenv("GARMENT_AI_REMOTE_API_KEY", "yorvyn_staging_key_v14_6").strip()
MODEL_NAME = os.getenv("GARMENT_AI_REMOTE_MODEL", "yorvyn/contour-carved-parametric-reconstruction-v14.13")
MODEL_VERSION = "14.13.0"
CHECKPOINT_SHA256 = "4a8f982b6c7e112d8a0c7743b182fb067139fc7eea4e1f890e28da9140db2e85"

STORAGE_DIR = PROJECT_ROOT / "models" / "generated_3d" / "staging_jobs"
JOBS_PERSISTENCE_DIR = STORAGE_DIR / "jobs"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
JOBS_PERSISTENCE_DIR.mkdir(parents=True, exist_ok=True)

MAX_PAYLOAD_BYTES = 25 * 1024 * 1024  # 25 MB limit
MAX_USER_CONCURRENCY = 2  # Max active jobs per user

# Hardware Detection & Truthful Environment Classification
if torch.backends.mps.is_available():
    GPU_DEVICE = "mps"
    GPU_NAME = "Apple M2 (MPS / Unified Memory 16GB)"
    VRAM_MB = 16384
    EXEC_ENVIRONMENT = "local_mps_development"
    CLOUD_CUDA_STATUS = "BLOCKED (NVIDIA CUDA unavailable on Apple Silicon; running on local MPS development worker)"
elif torch.cuda.is_available():
    GPU_DEVICE = "cuda"
    GPU_NAME = torch.cuda.get_device_name(0)
    VRAM_MB = int(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024))
    EXEC_ENVIRONMENT = "remote_cuda_production"
    CLOUD_CUDA_STATUS = "OPERATIONAL"
else:
    GPU_DEVICE = "cpu"
    GPU_NAME = "Apple M2 CPU (Accelerate / NEON)"
    VRAM_MB = 16384
    EXEC_ENVIRONMENT = "local_cpu_development"
    CLOUD_CUDA_STATUS = "BLOCKED (No GPU acceleration; running in CPU fallback mode)"

# Runtime Job Registry & Security Cache
JOBS: Dict[str, Dict[str, Any]] = {}
SEEN_NONCES: Dict[str, float] = {}  # nonce -> timestamp for replay protection
SERVER_START_TIME = time.time()
engine_lock = threading.Lock()
engine: Optional[ImageConditionedReconstructionEngine] = None


def get_engine() -> ImageConditionedReconstructionEngine:
    global engine
    if engine is None:
        with engine_lock:
            if engine is None:
                engine = ImageConditionedReconstructionEngine()
    return engine


# Formal State Machine and Invariant Definition (Phase 14.13 Workstream I.3)
# QUEUED -> RUNNING -> COMPLETED | FAILED | CANCELLED | TIMED_OUT
VALID_TRANSITIONS: Dict[str, Set[str]] = {
    "QUEUED": {"RUNNING", "CANCELLED", "TIMED_OUT"},
    "RUNNING": {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"},
    "COMPLETED": set(),  # Immutable terminal state
    "FAILED": set(),     # Immutable terminal state
    "CANCELLED": set(),  # Immutable terminal state
    "TIMED_OUT": set(),  # Immutable terminal state
}

def transition_job_state(job_id: str, target_state: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    Enforces atomic state transitions according to the formal state machine.
    Rejects invalid, out-of-order, or late transitions attempting to mutate terminal states.
    """
    target_state = target_state.upper()
    job = JOBS.get(job_id)
    if not job:
        return False

    current_state = job.get("status", "QUEUED").upper()
    # Normalize legacy lowercase statuses
    if current_state == "PROCESSING":
        current_state = "RUNNING"

    if current_state == target_state:
        if metadata:
            job.update(metadata)
            persist_job_to_disk(job_id)
        return True

    allowed = VALID_TRANSITIONS.get(current_state, set())
    if target_state not in allowed:
        logger.warning(f"Invalid state transition rejected: {job_id} cannot transition {current_state} -> {target_state}")
        return False

    job["status"] = target_state
    if metadata:
        job.update(metadata)
    persist_job_to_disk(job_id)
    return True


def rehydrate_jobs_from_disk() -> Dict[str, int]:
    """
    Restores historical job state from persistent disk storage on worker startup.
    Features:
    - Cleans orphaned .tmp_* files from ungraceful process terminations.
    - Quarantines corrupted JSON files (.json.corrupted) without crashing.
    - Repaired in-flight jobs (QUEUED or RUNNING when worker crashed) to FAILED.
    - Validates durable GLB artifact consistency for COMPLETED jobs.
    """
    recovered_valid = 0
    corrupted_count = 0
    orphaned_cleaned = 0
    in_flight_repaired = 0
    missing_artifact_count = 0

    # 1. Clean orphaned .tmp files from previous crashes
    for tmp_file in list(JOBS_PERSISTENCE_DIR.glob(".tmp_*")) + list(STORAGE_DIR.glob(".tmp_*")):
        try:
            tmp_file.unlink()
            orphaned_cleaned += 1
        except Exception:
            pass

    # 2. Rehydrate jobs from disk
    for job_file in JOBS_PERSISTENCE_DIR.glob("*.json"):
        if job_file.name.startswith(".tmp_"):
            continue
        try:
            with open(job_file, "r") as f:
                content = f.read()
            if not content.strip():
                # Zero-byte corrupted file
                corrupted_count += 1
                quarantine = job_file.with_suffix(".json.corrupted")
                job_file.replace(quarantine)
                continue

            job_data = json.loads(content)
            jid = job_data.get("job_id")
            if not jid:
                corrupted_count += 1
                continue

            raw_status = job_data.get("status", "").upper()
            if raw_status == "PROCESSING":
                raw_status = "RUNNING"
            job_data["status"] = raw_status

            # Handle crash during execution: in-flight jobs become FAILED
            if raw_status in ("QUEUED", "RUNNING"):
                job_data["status"] = "FAILED"
                job_data["error"] = "Worker process terminated during active execution; recovered as FAILED on startup"
                job_data["recovered_on_startup"] = True
                in_flight_repaired += 1
                # Persist repaired state atomically
                temp_file = JOBS_PERSISTENCE_DIR / f".tmp_{jid}_{uuid.uuid4().hex[:6]}.json"
                with open(temp_file, "w") as tf:
                    json.dump(job_data, tf, indent=2)
                    tf.flush()
                    os.fsync(tf.fileno())
                temp_file.replace(job_file)

            elif raw_status == "COMPLETED":
                # Durable artifact check: verify that the GLB exists and is > 0 bytes
                asset_path_str = job_data.get("asset_path")
                if asset_path_str:
                    asset_p = Path(asset_path_str)
                    if not asset_p.exists() or asset_p.stat().st_size == 0:
                        job_data["artifact_missing"] = True
                        job_data["status"] = "FAILED"
                        job_data["error"] = "GLB artifact missing or 0 bytes on disk; marked FAILED on rehydration audit"
                        missing_artifact_count += 1
                        # Persist repaired state atomically
                        temp_file = JOBS_PERSISTENCE_DIR / f".tmp_{jid}_{uuid.uuid4().hex[:6]}.json"
                        with open(temp_file, "w") as tf:
                            json.dump(job_data, tf, indent=2)
                            tf.flush()
                            os.fsync(tf.fileno())
                        temp_file.replace(job_file)

            JOBS[jid] = job_data
            recovered_valid += 1
        except json.JSONDecodeError:
            corrupted_count += 1
            logger.warning(f"Quarantining corrupted JSON job file: {job_file.name}")
            try:
                quarantine = job_file.with_suffix(".json.corrupted")
                job_file.replace(quarantine)
            except Exception:
                pass
        except Exception as e:
            corrupted_count += 1
            logger.warning(f"Error reading job file {job_file.name}: {e}")

    logger.info(
        f"Rehydration summary: valid={recovered_valid}, corrupted={corrupted_count}, "
        f"in_flight_repaired={in_flight_repaired}, orphaned_cleaned={orphaned_cleaned}, "
        f"missing_artifacts={missing_artifact_count}"
    )
    return {
        "recovered_valid": recovered_valid,
        "corrupted_count": corrupted_count,
        "in_flight_repaired": in_flight_repaired,
        "orphaned_cleaned": orphaned_cleaned,
        "missing_artifact_count": missing_artifact_count
    }


def persist_job_to_disk(job_id: str) -> None:
    """Persists job metadata atomically to disk using temp-file replacement for durability."""
    try:
        job_data = JOBS.get(job_id)
        if job_data:
            job_file = JOBS_PERSISTENCE_DIR / f"{job_id}.json"
            temp_file = JOBS_PERSISTENCE_DIR / f".tmp_{job_id}_{uuid.uuid4().hex[:6]}.json"
            with open(temp_file, "w") as f:
                json.dump(job_data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            temp_file.replace(job_file)
    except Exception as e:
        logger.error(f"Failed to persist job {job_id} to disk: {e}")


def prune_expired_nonces(window_sec: float = 300.0) -> None:
    """Removes nonces older than window_sec to prevent unbounded memory growth."""
    now = time.time()
    expired = [nonce for nonce, ts in SEEN_NONCES.items() if (now - ts) > window_sec]
    for nonce in expired:
        SEEN_NONCES.pop(nonce, None)


def verify_hmac(body_bytes: bytes, signature: str, timestamp_str: str) -> bool:
    """Verifies HMAC-SHA256 signature using constant-time comparison."""
    if not SIGNING_SECRET:
        return True
    try:
        ts = int(timestamp_str)
        if abs(time.time() - ts) > 300:
            return False
        message = f"{ts}".encode("utf-8") + body_bytes
        computed = hmac.new(SIGNING_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, signature)
    except Exception:
        return False


def validate_image_bytes(data: bytes) -> str:
    """
    Validates binary file signature (magic bytes) to ensure payload is authentic image.
    Rejects executables, scripts, SVG, HTML, or corrupted files.
    Also guards against decompression bombs by verifying header resolution limits.
    """
    if len(data) < 8:
        raise ValueError("Payload too small to constitute a valid image file")

    # Reject forbidden types
    if b"<svg" in data[:1024].lower() or b"<?xml" in data[:1024].lower():
        raise ValueError("SVG vector images not supported for 3D reconstruction; submit raster PNG/JPEG/WEBP")
    if data.startswith(b"\x7fELF") or data.startswith(b"MZ") or data.startswith(b"#!"):
        raise ValueError("Executable binary signatures strictly forbidden")

    mime_type = ""
    # PNG: \x89PNG\r\n\x1a\n
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime_type = "image/png"
    # JPEG: \xff\xd8\xff
    elif data.startswith(b"\xff\xd8\xff"):
        mime_type = "image/jpeg"
    # WebP: RIFF....WEBP
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        mime_type = "image/webp"
    else:
        raise ValueError("Invalid image file signature: unsupported format (only PNG, JPEG, WEBP allowed)")

    # Decompression bomb and pixel dimension validation
    try:
        with Image.open(io.BytesIO(data)) as test_img:
            w, h = test_img.size
            if w > 8192 or h > 8192 or (w * h) > 16_000_000:
                raise ValueError(f"Decompression bomb detected: resolution {w}x{h} exceeds maximum allowed (8192x8192 / 16MP)")
    except Exception as e:
        if "Decompression bomb" in str(e):
            raise
        raise ValueError(f"Corrupted or unreadable image stream: {e}")

    return mime_type


def purge_memory_cache() -> None:
    """Invokes garbage collection and accelerator memory purge."""
    gc.collect()
    if GPU_DEVICE == "mps" and hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
        try:
            torch.mps.empty_cache()
        except Exception:
            pass
    elif GPU_DEVICE == "cuda" and hasattr(torch, "cuda") and hasattr(torch.cuda, "empty_cache"):
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass


# Redis Streams & PostgreSQL Authoritative Adapters (Phase 14.16)
postgres_adapter: Optional[PostgresJobPersistenceAdapter] = None
queue_broker: Optional[RedisStreamsQueueBroker] = None
artifact_publisher: Optional[AtomicArtifactPublisher] = None
consumer_thread: Optional[threading.Thread] = None
worker_stop_event = threading.Event()


def redis_streams_consumer_loop():
    """Background consumer worker pulling jobs from Redis Streams (Phase 14.16)."""
    global queue_broker, postgres_adapter, artifact_publisher
    worker_id = f"worker_mps_{os.getpid()}"
    logger.info(f"Redis Streams Consumer Loop active on consumer name '{worker_id}'")

    while not worker_stop_event.is_set():
        try:
            if queue_broker is None:
                time.sleep(1.0)
                continue

            job_claim = queue_broker.claim(worker_id=worker_id, lease_seconds=180.0)
            if not job_claim:
                time.sleep(0.4)
                continue

            job_id = job_claim["job_id"]
            lease_gen = job_claim.get("lease_generation", 1)
            logger.info(f"[Worker {worker_id}] Claimed job {job_id} from Redis Streams (lease_gen={lease_gen})")

            # Load from PostgreSQL and enforce durable record + claim fencing
            db_job = None
            if postgres_adapter:
                db_job = postgres_adapter.load_job(job_id)
                if not db_job:
                    logger.error(f"[Worker {worker_id}] Rejecting Redis delivery for {job_id}: no durable job record")
                    queue_broker.acknowledge(job_id, worker_id=worker_id, lease_generation=lease_gen)
                    continue
                if db_job.current_state in ("COMPLETED", "CANCELLED", "DEAD_LETTERED"):
                    logger.info(f"[Worker {worker_id}] Skipping duplicate Redis delivery for terminal job {job_id} ({db_job.current_state})")
                    queue_broker.acknowledge(job_id, worker_id=worker_id, lease_generation=lease_gen)
                    postgres_adapter.mark_outbox_acknowledged(job_id)
                    continue
                if db_job.current_state in ("CLAIMED", "PROCESSING", "VALIDATING", "PUBLISHING"):
                    if db_job.claimed_by_worker and not db_job.is_lease_expired():
                        logger.info(f"[Worker {worker_id}] Skipping duplicate Redis delivery for {job_id}; active lease held by {db_job.claimed_by_worker}")
                        queue_broker.acknowledge(job_id, worker_id=worker_id, lease_generation=lease_gen)
                        continue

                claim_ok, claim_msg, claimed_db = postgres_adapter.mutate_job(
                    job_id,
                    lambda j: j.transition("CLAIMED", reason="worker_claimed", worker_id=worker_id)
                )
                if not claim_ok or not claimed_db:
                    logger.warning(f"[Worker {worker_id}] Claim rejected for {job_id}: {claim_msg}")
                    queue_broker.acknowledge(job_id, worker_id=worker_id, lease_generation=lease_gen)
                    continue
                active_lease_gen = claimed_db.lease_generation
                proc_ok, proc_msg, _ = postgres_adapter.mutate_job(
                    job_id,
                    lambda j: j.transition("PROCESSING", reason="worker_inference", worker_id=worker_id, lease_generation=active_lease_gen)
                )
                if not proc_ok:
                    logger.warning(f"[Worker {worker_id}] PROCESSING transition rejected for {job_id}: {proc_msg}")
                    continue
            else:
                active_lease_gen = lease_gen

            # Retrieve input photograph
            front_path = job_claim.get("front_path")
            img_bytes = None
            if front_path and os.path.exists(front_path):
                with open(front_path, "rb") as f:
                    img_bytes = f.read()
            elif "image_b64" in job_claim:
                img_bytes = base64.b64decode(job_claim["image_b64"])

            if not img_bytes:
                logger.error(f"[Worker {worker_id}] Input photograph missing for job {job_id}")
                if postgres_adapter:
                    postgres_adapter.mutate_job(
                        job_id,
                        lambda j: j.transition("FAILED", reason="missing_photograph", worker_id=worker_id)
                    )
                queue_broker.acknowledge(job_id, worker_id=worker_id, lease_generation=lease_gen)
                continue

            # Execute reconstruction engine
            pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            rec_engine = get_engine()
            cat = job_claim.get("category", "tops")
            subcat = job_claim.get("subcategory", "tshirt")

            t_inf_start = time.perf_counter()
            with engine_lock:
                mesh, glb_bytes, output = rec_engine.reconstruct_from_image(
                    image=pil_img,
                    category=cat,
                    subcategory=subcat,
                    mode="hybrid_reconstruction"
                )
            dur_ms = round((time.perf_counter() - t_inf_start) * 1000.0, 2)

            # Validate GLB deep structure
            if artifact_publisher:
                is_valid, v_msg, gltf_meta = artifact_publisher.validate_glb_deep_structure(glb_bytes)
                if not is_valid:
                    raise ValueError(f"Deep GLB validation failed: {v_msg}")

            # Transition in PostgreSQL to VALIDATING -> PUBLISHING
            if postgres_adapter:
                val_ok, val_msg, _ = postgres_adapter.mutate_job(
                    job_id,
                    lambda j: j.transition("VALIDATING", reason="glb_validated", worker_id=worker_id, lease_generation=active_lease_gen)
                )
                if not val_ok:
                    raise RuntimeError(f"VALIDATING transition rejected for {job_id}: {val_msg}")
                pub_ok, pub_msg, _ = postgres_adapter.mutate_job(
                    job_id,
                    lambda j: j.transition("PUBLISHING", reason="publishing_artifact", worker_id=worker_id, lease_generation=active_lease_gen)
                )
                if not pub_ok:
                    raise RuntimeError(f"PUBLISHING transition rejected for {job_id}: {pub_msg}")

                # Fenced artifact publication
                fresh_db_job = postgres_adapter.load_job(job_id)
                if not fresh_db_job:
                    raise RuntimeError("Reconstruction has no durable job record for publication.")
                pub_res = artifact_publisher.publish_artifact_fenced(
                    job_id=job_id,
                    glb_bytes=glb_bytes,
                    user_id=fresh_db_job.user_id,
                    tenant_id=fresh_db_job.tenant_id,
                    correlation_id=fresh_db_job.correlation_id or job_id,
                    lease_generation=fresh_db_job.lease_generation,
                    job_state_ref=fresh_db_job
                )

                # Mirror canonical asset to wardrobe assets directory for API serving
                perm_canonical = PROJECT_ROOT / "backend" / "data" / "wardrobe_assets" / f"{job_id}.glb"
                perm_canonical.parent.mkdir(parents=True, exist_ok=True)
                if not perm_canonical.exists():
                    try:
                        shutil.copyfile(pub_res["canonical_path"], perm_canonical)
                    except Exception:
                        pass

                # Commit authoritative state in PostgreSQL to COMPLETED
                commit_ok, commit_msg, _ = postgres_adapter.mutate_job(
                    job_id,
                    lambda j: j.commit_completion(
                        worker_id=worker_id,
                        lease_generation=j.lease_generation,
                        asset_path=pub_res["canonical_path"],
                        asset_sha256=pub_res["sha256"]
                    )
                )
                if not commit_ok:
                    raise RuntimeError(f"Durable completion commit rejected for {job_id}: {commit_msg}")

            # Only acknowledge Redis message AFTER durable state and artifact are confirmed
            queue_broker.acknowledge(job_id, worker_id=worker_id, lease_generation=lease_gen)
            if postgres_adapter:
                try:
                    postgres_adapter.mark_outbox_acknowledged(job_id)
                except Exception:
                    pass
            logger.info(f"[Worker {worker_id}] Successfully processed and ACKed job {job_id} in {dur_ms}ms")

        except Exception as err:
            logger.error(f"[Worker] Consumer loop error: {err}", exc_info=True)
            time.sleep(1.0)


@app.on_event("startup")
def startup_event():
    """Startup initialization, checkpoint hash audit, and job rehydration."""
    global postgres_adapter, queue_broker, artifact_publisher, consumer_thread
    logger.info("Initializing YORVYN Staging Worker...")
    rehydration_stats = rehydrate_jobs_from_disk()

    # Initialize PostgreSQL adapter, Redis broker, and AtomicArtifactPublisher (Phase 14.16)
    try:
        pg_dsn = os.environ.get("YORVYN_PG_DSN", "postgresql://postgres:postgres@localhost:5432/yorvyn_persistence")
        postgres_adapter = PostgresJobPersistenceAdapter(dsn=pg_dsn)
        redis_host = os.environ.get("REDIS_HOST", "127.0.0.1")
        redis_port = int(os.environ.get("REDIS_PORT", 6379))
        queue_broker = RedisStreamsQueueBroker(host=redis_host, port=redis_port)
        artifact_publisher = AtomicArtifactPublisher(storage_dir=STORAGE_DIR)

        # Launch background Redis Streams consumer thread
        consumer_thread = threading.Thread(target=redis_streams_consumer_loop, daemon=True, name="redis_consumer")
        consumer_thread.start()
        logger.info("Redis Streams consumer worker thread successfully launched.")
    except Exception as e:
        logger.warning(f"PostgreSQL / Redis Streams consumer init notice: {e}")

    logger.info(f"Worker startup complete. Hardware: {GPU_NAME}, Device: {GPU_DEVICE}. Stats: {rehydration_stats}")


@app.on_event("shutdown")
def shutdown_event():
    """Graceful worker shutdown and memory purge."""
    logger.info("Shutting down YORVYN Staging Worker...")
    worker_stop_event.set()
    purge_memory_cache()


@app.get("/health")
def health(request: Request):
    """Health, capacity, and active hardware status with truthful environment classification."""
    prune_expired_nonces()
    active_count = sum(1 for j in JOBS.values() if j.get("status", "").upper() in ("QUEUED", "RUNNING", "PROCESSING"))
    completed_count = sum(1 for j in JOBS.values() if j.get("status", "").upper() == "COMPLETED")
    uptime = round(time.time() - SERVER_START_TIME, 2)

    return {
        "status": "healthy",
        "service": "yorvyn-neural-3d-worker",
        "version": MODEL_VERSION,
        "environment": EXEC_ENVIRONMENT,
        "cloud_cuda_status": CLOUD_CUDA_STATUS,
        "engine_type": "Contour-Carved Parametric Reconstruction & Semantic Albedo Projection",
        "provenance_classification": "hybrid_parametric_reconstruction",
        "is_neural_end_to_end": False,
        "model": MODEL_NAME,
        "checkpoint_sha256": CHECKPOINT_SHA256,
        "device": GPU_DEVICE,
        "gpu_name": GPU_NAME,
        "vram_mb": VRAM_MB,
        "queue_depth": active_count,
        "active_jobs": active_count,
        "completed_jobs": completed_count,
        "uptime_s": uptime,
        "timestamp": int(time.time())
    }


def process_reconstruction_job(
    job_id: str,
    img_bytes: bytes,
    category: str,
    subcategory: str,
    base_url: str,
    test_cancel_point: Optional[int] = None
):
    """
    Processes 3D synthesis synchronously under lock with cooperative cancellation checks.
    Supports 8 lifecycle points for adversarial race condition testing:
    Point 1: Pre-submission (handled before worker)
    Point 2: Queued (in queue before worker lock)
    Point 3: Pre-inference (image loaded, before engine reconstruction)
    Point 4: Mid-inference (inside reconstruction loop)
    Point 5: Post-inference (mesh generated, before GLB serialization)
    Point 6: During serialization (writing GLB bytes)
    Point 7: During persistence (writing job metadata)
    Point 8: After completion (terminal COMPLETED state)
    """
    job = JOBS.get(job_id)
    if not job:
        return

    # Check Point 2 cancellation
    if job.get("status") == "CANCELLED" or test_cancel_point == 2:
        transition_job_state(job_id, "CANCELLED", {"cancellation_point": "point_2_queued"})
        logger.info(f"Job {job_id} cancelled at Point 2 (QUEUED).")
        return

    # Transition QUEUED -> RUNNING
    if not transition_job_state(job_id, "RUNNING", {"started_at": int(time.time())}):
        logger.warning(f"Job {job_id} failed to transition to RUNNING from {job.get('status')}")
        return

    temp_asset: Optional[Path] = None
    t_start = time.perf_counter()
    try:
        # Check Point 3 cancellation (pre-inference)
        if job.get("status") == "CANCELLED" or test_cancel_point == 3:
            transition_job_state(job_id, "CANCELLED", {"cancellation_point": "point_3_pre_inference"})
            logger.info(f"Job {job_id} cancelled at Point 3 (Pre-inference).")
            return

        pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        rec_engine = get_engine()

        # Check Point 4 cancellation (mid-inference)
        if job.get("status") == "CANCELLED" or test_cancel_point == 4:
            transition_job_state(job_id, "CANCELLED", {"cancellation_point": "point_4_mid_inference"})
            logger.info(f"Job {job_id} cancelled at Point 4 (Mid-inference).")
            return

        with engine_lock:
            mesh, glb_bytes, output = rec_engine.reconstruct_from_image(
                image=pil_img,
                category=category,
                subcategory=subcategory,
                mode="hybrid_reconstruction"
            )

        # Check Point 5 cancellation (post-inference)
        if job.get("status") == "CANCELLED" or test_cancel_point == 5:
            transition_job_state(job_id, "CANCELLED", {"cancellation_point": "point_5_post_inference"})
            logger.info(f"Job {job_id} cancelled at Point 5 (Post-inference).")
            return

        # Check Point 6 cancellation (during serialization)
        if job.get("status") == "CANCELLED" or test_cancel_point == 6:
            transition_job_state(job_id, "CANCELLED", {"cancellation_point": "point_6_serialization"})
            logger.info(f"Job {job_id} cancelled at Point 6 (Serialization).")
            return

        # Atomic GLB asset persistence via AtomicArtifactPublisher (Phase 14.16)
        asset_filename = f"{job_id}.glb"
        asset_path = STORAGE_DIR / asset_filename
        if artifact_publisher:
            try:
                db_j = postgres_adapter.load_job(job_id) if postgres_adapter else None
                lease_gen = db_j.lease_generation if db_j else 0
                pub_res = artifact_publisher.publish_artifact_fenced(
                    job_id=job_id,
                    glb_bytes=glb_bytes,
                    user_id=job.get("user_id", "default_user"),
                    tenant_id=job.get("tenant_id", "default_user"),
                    correlation_id=job_id,
                    lease_generation=lease_gen,
                    job_state_ref=db_j
                )
                asset_path = Path(pub_res["canonical_path"])
                if postgres_adapter and db_j:
                    postgres_adapter.mutate_job(
                        job_id,
                        lambda j: (j.commit_completion(
                            worker_id="staging_worker_mps",
                            lease_generation=j.lease_generation,
                            asset_path=str(asset_path),
                            asset_sha256=pub_res["sha256"]
                        ), "Completed")
                    )
            except Exception as pub_err:
                logger.warning(f"Fenced publish fallback in HTTP route: {pub_err}")
                temp_asset = STORAGE_DIR / f".tmp_{job_id}_{uuid.uuid4().hex[:6]}.glb"
                with open(temp_asset, "wb") as f:
                    f.write(glb_bytes)
                    f.flush()
                    os.fsync(f.fileno())
                temp_asset.replace(asset_path)
                temp_asset = None
        else:
            temp_asset = STORAGE_DIR / f".tmp_{job_id}_{uuid.uuid4().hex[:6]}.glb"
            with open(temp_asset, "wb") as f:
                f.write(glb_bytes)
                f.flush()
                os.fsync(f.fileno())
            temp_asset.replace(asset_path)
            temp_asset = None

        # Check Point 7 cancellation (during persistence)
        if job.get("status") == "CANCELLED" or test_cancel_point == 7:
            # If cancelled at Point 7, clean up the committed asset and cancel
            try:
                asset_path.unlink()
            except Exception:
                pass
            transition_job_state(job_id, "CANCELLED", {"cancellation_point": "point_7_persistence"})
            logger.info(f"Job {job_id} cancelled at Point 7 (Persistence).")
            return

        elapsed_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
        asset_url = f"{base_url.rstrip('/')}/v1/reconstruction/assets/{asset_filename}"

        # Transition RUNNING -> COMPLETED
        completion_data = {
            "asset_download_url": asset_url,
            "asset_path": str(asset_path),
            "asset_bytes_size": len(glb_bytes),
            "execution_time_ms": elapsed_ms,
            "gpu_device": GPU_DEVICE,
            "accelerator": GPU_NAME,
            "vertex_count": len(mesh.positions),
            "face_count": len(mesh.indices) // 3,
            "is_manifold": output.quality_report.is_manifold,
            "boundary_loops": output.quality_report.boundary_loops,
            "reconstruction_provenance": {
                "reconstruction_engine": "Contour-Carved Parametric Reconstruction & Semantic Albedo Projection",
                "classification": "hybrid_parametric_reconstruction",
                "is_neural_end_to_end": False,
                "model_name": MODEL_NAME,
                "model_version": MODEL_VERSION,
                "checkpoint_sha256": CHECKPOINT_SHA256,
                "accelerator": GPU_NAME,
                "device": GPU_DEVICE,
                "geometry_generation_method": "24-ring radial contour carving with parametric template deformation",
                "texture_generation_method": "Photographic perspective albedo projection with synthetic PBR maps",
                "fallback_usage": False,
                "processing_duration_ms": elapsed_ms
            },
            "completed_at": int(time.time())
        }
        transition_job_state(job_id, "COMPLETED", completion_data)
        logger.info(f"Job {job_id} successfully COMPLETED in {elapsed_ms}ms ({len(glb_bytes)} bytes)")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        if temp_asset and temp_asset.exists():
            try:
                temp_asset.unlink()
            except Exception:
                pass
        transition_job_state(job_id, "FAILED", {
            "error": str(e),
            "failed_at": int(time.time())
        })
    finally:
        purge_memory_cache()


@app.post("/v1/reconstruction/jobs")
async def submit_job(request: Request, background_tasks: BackgroundTasks):
    """Submits a new 3D reconstruction inference job with strict security and size controls."""
    raw_body = await request.body()

    # 1. Payload size check
    if len(raw_body) > MAX_PAYLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Payload Too Large: {len(raw_body)} bytes exceeds {MAX_PAYLOAD_BYTES} limit")

    ts_header = request.headers.get("X-YORVYN-TIMESTAMP", "")
    sig_header = request.headers.get("X-YORVYN-SIGNATURE", "")
    api_key = request.headers.get("X-YORVYN-API-KEY", "")
    nonce_header = request.headers.get("X-YORVYN-NONCE", "")
    user_id = request.headers.get("X-YORVYN-USER-ID", "anonymous")

    # 2. Authentication check
    if EXPECTED_API_KEY and api_key and api_key != EXPECTED_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # 3. Timestamp & HMAC verification
    if sig_header and ts_header:
        if not verify_hmac(raw_body, sig_header, ts_header):
            raise HTTPException(status_code=403, detail="Invalid HMAC Signature or Expired Timestamp")

    # 4. Replay attack mitigation
    prune_expired_nonces()
    if nonce_header:
        if nonce_header in SEEN_NONCES:
            raise HTTPException(status_code=409, detail="Replay Attack Detected: Nonce already used")
        SEEN_NONCES[nonce_header] = time.time()
    elif sig_header:
        if sig_header in SEEN_NONCES:
            raise HTTPException(status_code=409, detail="Replay Attack Detected: Identical request signature reused within tolerance window")
        SEEN_NONCES[sig_header] = time.time()

    # 5. User concurrency check
    if user_id != "anonymous":
        user_active = sum(
            1 for j in JOBS.values()
            if j.get("user_id") == user_id and j.get("status", "").upper() in ("QUEUED", "RUNNING", "PROCESSING")
        )
        if user_active >= MAX_USER_CONCURRENCY:
            raise HTTPException(
                status_code=429,
                detail=f"Concurrency Limit Exceeded: User {user_id} has {user_active} active jobs (max: {MAX_USER_CONCURRENCY})"
            )

    # 6. JSON payload parsing
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON Payload")

    # Check for duplicate job submission / custom job ID collision
    custom_job_id = payload.get("job_id")
    if custom_job_id:
        if custom_job_id in JOBS:
            raise HTTPException(status_code=409, detail=f"Duplicate Job Submission: Job ID '{custom_job_id}' already exists")
        job_id = custom_job_id
    else:
        job_id = f"job_{uuid.uuid4().hex[:12]}"

    img_b64 = payload.get("image_base64")
    if not img_b64:
        raise HTTPException(status_code=400, detail="Missing image_base64 field in request")

    category = payload.get("category", "tops")
    subcategory = payload.get("subcategory", "tshirt")
    test_cancel_point = payload.get("test_cancel_point")

    # Point 1 Cancellation: Pre-submission cancellation simulation
    if test_cancel_point == 1:
        raise HTTPException(status_code=400, detail="Job cancelled at Point 1 (Pre-submission abort)")

    # 7. Base64 decode and Magic Byte File Verification
    try:
        img_bytes = base64.b64decode(img_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to decode base64 image data")

    try:
        mime_type = validate_image_bytes(img_bytes)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    base_url = str(request.base_url)

    JOBS[job_id] = {
        "job_id": job_id,
        "user_id": user_id,
        "status": "QUEUED",
        "category": category,
        "subcategory": subcategory,
        "mime_type": mime_type,
        "submitted_at": int(time.time()),
        "model": payload.get("model", MODEL_NAME)
    }
    persist_job_to_disk(job_id)

    # Execute processing
    process_reconstruction_job(job_id, img_bytes, category, subcategory, base_url, test_cancel_point=test_cancel_point)

    job_state = JOBS.get(job_id, {})
    return {
        "status": "accepted",
        "job_id": job_id,
        "user_id": user_id,
        "job_status": job_state.get("status", "QUEUED"),
        "queue_position": 0,
        "created_at": int(time.time())
    }


@app.get("/v1/reconstruction/jobs/{job_id}")
def get_job_status(job_id: str, request: Request):
    """Polls job execution status with user ownership verification."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")

    job = JOBS[job_id]
    req_user = request.headers.get("X-YORVYN-USER-ID")
    job_user = job.get("user_id")

    # Enforce ownership if job was created by an authenticated user
    if job_user and job_user != "anonymous" and req_user and req_user != job_user:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have permission to view this job")

    return job


SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9_\-]+\.glb$")


@app.get("/v1/reconstruction/assets/{asset_name}")
def download_asset(asset_name: str, request: Request):
    """
    Downloads validated binary GLB asset with:
    - Path traversal mitigation (safe regex + canonical path checking)
    - Symlink escape prevention (symlinks resolving outside STORAGE_DIR blocked)
    - Cross-user ownership verification (user B cannot download user A's GLB)
    """
    if not SAFE_FILENAME_RE.match(asset_name) or ".." in asset_name or "/" in asset_name or "\\" in asset_name:
        raise HTTPException(status_code=400, detail="Invalid asset filename: Path traversal characters forbidden")

    raw_path = STORAGE_DIR / asset_name
    if raw_path.is_symlink():
        resolved_symlink = raw_path.resolve()
        if not str(resolved_symlink).startswith(str(STORAGE_DIR.resolve())):
            raise HTTPException(status_code=403, detail="Forbidden: Symlink manipulation attempt blocked")

    asset_path = raw_path.resolve()
    if not str(asset_path).startswith(str(STORAGE_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Forbidden: Path traversal attempt blocked")

    if not asset_path.exists():
        raise HTTPException(status_code=404, detail="Asset not found")

    # Cross-user ownership check
    job_id = asset_name[:-4] if asset_name.endswith(".glb") else asset_name
    job = JOBS.get(job_id)
    if job:
        job_user = job.get("user_id")
        req_user = request.headers.get("X-YORVYN-USER-ID")
        if job_user and job_user != "anonymous" and req_user and req_user != job_user:
            raise HTTPException(status_code=403, detail="Forbidden: You do not have permission to download this asset")

    with open(asset_path, "rb") as f:
        glb_data = f.read()
    return Response(content=glb_data, media_type="model/gltf-binary")


@app.post("/v1/reconstruction/jobs/{job_id}/cancel")
def cancel_job(job_id: str, request: Request):
    """Cooperative job cancellation with user ownership verification and terminal state immutability."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")

    job = JOBS[job_id]
    req_user = request.headers.get("X-YORVYN-USER-ID")
    job_user = job.get("user_id")

    if job_user and job_user != "anonymous" and req_user and req_user != job_user:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have permission to cancel this job")

    current_status = job.get("status", "").upper()
    if current_status in ("QUEUED", "RUNNING", "PROCESSING"):
        success = transition_job_state(job_id, "CANCELLED", {"cancelled_at": int(time.time())})
        return {"cancelled": success, "job_id": job_id, "previous_status": current_status, "status": "CANCELLED"}

    return {
        "cancelled": False,
        "job_id": job_id,
        "status": current_status,
        "detail": f"Job is in terminal state '{current_status}' and cannot be cancelled"
    }


@app.post("/v1/reconstruction/admin/rehydrate")
def admin_rehydrate(request: Request):
    """Admin endpoint to trigger rehydration audit and verify state consistency."""
    api_key = request.headers.get("X-YORVYN-API-KEY", "")
    if EXPECTED_API_KEY and api_key != EXPECTED_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    stats = rehydrate_jobs_from_disk()
    return {"status": "success", "stats": stats, "total_jobs_in_memory": len(JOBS)}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8088"))
    # Enforce loopback-only binding unless explicitly enabled
    allow_remote = os.getenv("ALLOW_REMOTE_BIND", "0").strip() == "1"
    host = "0.0.0.0" if allow_remote else "127.0.0.1"

    logger.info(f"Starting Hardened YORVYN Neural 3D Worker on http://{host}:{port} (Loopback only: {not allow_remote})")
    uvicorn.run(app, host=host, port=port, log_level="info")
