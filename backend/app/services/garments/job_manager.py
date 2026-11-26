"""
Stage 8 & 9: Asynchronous Job Architecture & Privacy Cleanup Manager
Manages job lifecycle, progress reporting, background worker execution,
and strictly purges temporary input files upon completion, failure, or cancellation.
"""

import os
import io
import shutil
import uuid
import hashlib
import asyncio
import logging
import heapq
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import numpy as np
from pathlib import Path

from backend.app.models.garment_models import GarmentGenJob, GarmentGenJobStatus, GarmentGenResult, DetectedGarmentFeatures
from backend.app.models.garment_intelligence_models import GarmentDiagnosticsV2, GarmentIntelligenceV2Result
from .garment_analyzer import GarmentAnalyzer
from .garment_mesh_builder import GarmentMeshBuilder
from .garment_texture_synthesizer import garment_texture_synthesizer
from .glb_exporter import glb_exporter
from .preview_renderer import preview_renderer
from backend.app.services.storage.cloudinary_storage import cloudinary_storage
from backend.app.services.database.supabase_repository import supabase_repo
from backend.app.services.garments.orchestration.unified_state_machine import (
    PostgresJobPersistenceAdapter,
    resolve_postgres_dsn,
    compute_canonical_fingerprint,
    UnifiedJobState,
    IdempotencyConflictException,
    TenantSecurityViolationException,
)
from backend.app.services.garments.orchestration.queue_broker import (
    RedisStreamsQueueBroker,
    QueueOverloadedException,
    ConcurrencyLimitExceededException
)
from backend.app.services.garments.orchestration.artifact_committer import (
    AtomicArtifactPublisher,
    ArtifactPublicationException
)

logger = logging.getLogger(__name__)


class DurablePersistenceUnavailableError(RuntimeError):
    """Raised when PostgreSQL durable job creation or mutation cannot be guaranteed."""

    def __init__(self, message: str = "Durable job persistence unavailable."):
        super().__init__(message)
        self.code = "DURABLE_JOB_PERSISTENCE_UNAVAILABLE"


class QueueEnqueueError(RuntimeError):
    """Raised when Redis Streams queue delivery fails before worker dispatch."""

    def __init__(self, message: str = "Reconstruction queue enqueue failed."):
        super().__init__(message)
        self.code = "QUEUE_ENQUEUE_FAILED"

TEMP_BASE_DIR = os.environ.get("YORVYN_GARMENT_TEMP_DIR", "/tmp/yorvyn_garment_pipeline")
PERMANENT_ASSET_DIR = os.environ.get("YORVYN_GARMENT_ASSET_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data/wardrobe_assets")))

# Ensure base directories exist
os.makedirs(TEMP_BASE_DIR, exist_ok=True)
os.makedirs(PERMANENT_ASSET_DIR, exist_ok=True)


JOB_TIMEOUT_SECONDS = int(os.environ.get("YORVYN_GARMENT_JOB_TIMEOUT_SECONDS", "180"))


class PriorityTaskEntry:
    """Heap-ordered task entry for real priority queue scheduling."""
    def __init__(
        self,
        priority: int,
        created_at: float,
        job_id: str,
        front_path: str,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        back_path: Optional[str] = None,
        side_path: Optional[str] = None,
        detail_path: Optional[str] = None,
        detection_metadata: Optional[Dict[str, Any]] = None
    ):
        self.priority = priority  # 1 = Brand/Studio, 2 = Pro Atelier, 3 = Explorer/Free
        self.created_at = created_at
        self.job_id = job_id
        self.front_path = front_path
        self.category = category
        self.subcategory = subcategory
        self.back_path = back_path
        self.side_path = side_path
        self.detail_path = detail_path
        self.detection_metadata = detection_metadata

    def __lt__(self, other: "PriorityTaskEntry") -> bool:
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at


class GarmentJobManager:
    """Orchestrates photo-to-3D garment generation jobs with privacy guarantees."""

    def __init__(self):
        self._jobs: Dict[str, GarmentGenJob] = {}
        self._diagnostics: Dict[str, GarmentDiagnosticsV2] = {}
        self._completed_cache: Dict[str, GarmentGenResult] = {}
        self._cancellation_flags: Dict[str, bool] = {}
        self._max_workers = 3
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        self._active_worker_count = 0
        self._queue_lock = threading.Lock()
        self._priority_queue: List[PriorityTaskEntry] = []
        self._max_queue_depth = 50
        self._start_time = datetime.utcnow()

        # Phase 14.16: Authoritative PostgreSQL & Redis Streams Integration
        pg_dsn = resolve_postgres_dsn()
        self._postgres_adapter = PostgresJobPersistenceAdapter(dsn=pg_dsn)
        redis_host = os.environ.get("REDIS_HOST", "127.0.0.1")
        redis_port = int(os.environ.get("REDIS_PORT", 6379))
        self._redis_broker = RedisStreamsQueueBroker(host=redis_host, port=redis_port)
        self._artifact_publisher = AtomicArtifactPublisher(storage_dir=Path(PERMANENT_ASSET_DIR))
        self._outbox_stop_event = threading.Event()
        self._outbox_thread: Optional[threading.Thread] = None

    def start_outbox_dispatcher(self, poll_interval_seconds: float = 5.0) -> None:
        """Starts the background transactional outbox dispatcher thread (idempotent)."""
        if getattr(self, "_outbox_thread", None) and self._outbox_thread.is_alive():
            return
        if not hasattr(self, "_outbox_stop_event") or self._outbox_stop_event is None:
            self._outbox_stop_event = threading.Event()
        self._outbox_stop_event.clear()

        def _loop():
            while not self._outbox_stop_event.is_set():
                try:
                    self._dispatch_outbox_pending()
                except Exception as exc:
                    logger.debug(f"[Outbox] Background dispatch cycle notice: {exc}")
                self._outbox_stop_event.wait(poll_interval_seconds)

        self._outbox_thread = threading.Thread(
            target=_loop, daemon=True, name="yorvyn_outbox_dispatcher"
        )
        self._outbox_thread.start()

    def stop_outbox_dispatcher(self) -> None:
        """Stops the background outbox dispatcher thread."""
        stop_ev = getattr(self, "_outbox_stop_event", None)
        if stop_ev is not None:
            stop_ev.set()
        thr = getattr(self, "_outbox_thread", None)
        if thr is not None and thr.is_alive():
            thr.join(timeout=2.0)

    def _db_job_to_garment_job(self, db_job: UnifiedJobState) -> GarmentGenJob:
        mem_job = self._jobs.get(db_job.job_id)

        status_map = {
            "CREATED": GarmentGenJobStatus.QUEUED,
            "QUEUED": GarmentGenJobStatus.QUEUED,
            "CLAIMED": GarmentGenJobStatus.ANALYZING,
            "PROCESSING": GarmentGenJobStatus.GENERATING_MESH,
            "VALIDATING": GarmentGenJobStatus.ASSEMBLING_3D,
            "PUBLISHING": GarmentGenJobStatus.RENDERING_PREVIEW,
            "COMPLETED": GarmentGenJobStatus.COMPLETED,
            "FAILED": GarmentGenJobStatus.FAILED,
            "CANCELLED": GarmentGenJobStatus.CANCELLED,
            "DEAD_LETTERED": GarmentGenJobStatus.FAILED
        }
        progress_map = {
            "CREATED": 5, "QUEUED": 10, "CLAIMED": 25, "PROCESSING": 55,
            "VALIDATING": 80, "PUBLISHING": 90, "COMPLETED": 100,
            "FAILED": 0, "CANCELLED": 0, "DEAD_LETTERED": 0
        }

        gen_status = status_map.get(db_job.current_state, GarmentGenJobStatus.QUEUED)
        progress = progress_map.get(db_job.current_state, 10)

        created_dt = datetime.utcfromtimestamp(db_job.created_at) if db_job.created_at else datetime.utcnow()
        updated_dt = datetime.utcfromtimestamp(db_job.updated_at) if db_job.updated_at else datetime.utcnow()

        result = None
        if mem_job and mem_job.result:
            result = mem_job.result
        elif db_job.current_state == "COMPLETED":
            metadata = Path(PERMANENT_ASSET_DIR) / db_job.job_id / "result.json"
            if metadata.is_file():
                result = GarmentGenResult.model_validate_json(metadata.read_bytes())

        err_msg = None
        if db_job.current_state in ("FAILED", "DEAD_LETTERED"):
            err_msg = db_job.attempts[-1].get("error_details") if db_job.attempts else "Job failed during execution."

        return GarmentGenJob(
            job_id=db_job.job_id,
            user_id=db_job.user_id,
            status=gen_status,
            progress=progress,
            current_stage=f"State: {db_job.current_state}",
            created_at=created_dt,
            updated_at=updated_dt,
            temporary_files=[],
            asset_sha256=db_job.asset_sha256,
            input_sha256=db_job.canonical_fingerprint,
            error=err_msg,
            result=result
        )

    def _dispatch_next_tasks(self):
        """Pops highest-priority tasks and dispatches them to free worker threads."""
        with self._queue_lock:
            while self._active_worker_count < self._max_workers and self._priority_queue:
                task = heapq.heappop(self._priority_queue)
                job = self._jobs.get(task.job_id)
                if job and (self._cancellation_flags.get(task.job_id) or job.status == GarmentGenJobStatus.CANCELLED):
                    self._cleanup_temp_files(task.job_id)
                    continue

                self._active_worker_count += 1
                self._executor.submit(self._worker_wrapper, task)

    def _dispatch_outbox_pending(self) -> int:
        """
        Re-delivers pending or stale outbox entries to Redis (DURABLE-JOB-FIX-002).
        Called on startup recovery, periodic outbox sweeps, and after job creation.
        Returns the number of entries successfully delivered.
        """
        delivered_count = 0
        try:
            if hasattr(self._postgres_adapter, "reconcile_terminal_outbox_entries"):
                self._postgres_adapter.reconcile_terminal_outbox_entries()
        except Exception as rec_err:
            logger.debug(f"[Outbox] Terminal reconciliation notice: {rec_err}")

        try:
            pending = self._postgres_adapter.claim_pending_outbox_entries(limit=50, stale_after_seconds=30.0)
        except Exception as claim_err:
            logger.warning(f"[Outbox] Failed to claim pending outbox entries: {claim_err}")
            return 0

        for entry in pending:
            job_id = entry.get("job_id", "unknown")
            outbox_id = entry.get("outbox_id")
            try:
                # Re-verify durable job state
                db_job = self._postgres_adapter.load_job(job_id)
                if not db_job:
                    try:
                        self._postgres_adapter.mark_outbox_delivered(
                            outbox_id=outbox_id, redis_message_id="state_missing"
                        )
                    except Exception:
                        pass
                    continue

                if db_job.current_state in ("COMPLETED", "CANCELLED", "DEAD_LETTERED"):
                    try:
                        self._postgres_adapter.mark_outbox_acknowledged(job_id)
                    except Exception:
                        pass
                    continue

                if db_job.current_state not in ("QUEUED", "CREATED", "SUBMITTED"):
                    # Actively CLAIMED / PROCESSING / VALIDATING / PUBLISHING — do not re-enqueue
                    continue

                # Verify temp files exist for the job before delivering to Redis
                payload = dict(entry.get("payload") or {})
                front_path = payload.get("front_path")
                if not front_path or not os.path.isfile(front_path):
                    logger.warning(f"[Outbox] Temp input missing for {job_id}; closing undeliverable job.")
                    self._close_unfinished_job(job_id, "Temp input files missing during outbox delivery.")
                    try:
                        self._postgres_adapter.mark_outbox_acknowledged(job_id)
                    except Exception:
                        pass
                    continue

                if outbox_id:
                    payload.setdefault("event_id", outbox_id)
                self._redis_broker.enqueue(payload, priority=entry.get("priority", 3))
                msg_id = (
                    self._redis_broker.get_last_message_id(job_id)
                    if hasattr(self._redis_broker, "get_last_message_id")
                    else None
                ) or "outbox_redelivery"
                self._postgres_adapter.mark_outbox_delivered(
                    outbox_id=outbox_id, redis_message_id=msg_id
                )
                delivered_count += 1
                logger.info(
                    f"[Outbox] Re-delivered job {job_id} (event={outbox_id}, redis_msg={msg_id}) to Redis."
                )
                in_mem_job = self._jobs.get(job_id)
                if in_mem_job and in_mem_job.status == GarmentGenJobStatus.QUEUED and payload.get("front_path"):
                    in_mem_job.current_stage = "Job queued for processing"
                    in_mem_job.updated_at = datetime.utcnow()
                    with self._queue_lock:
                        already_queued = any(t.job_id == job_id for t in self._priority_queue)
                        if not already_queued:
                            heapq.heappush(
                                self._priority_queue,
                                PriorityTaskEntry(
                                    entry.get("priority", 3),
                                    time.time(),
                                    job_id,
                                    payload["front_path"],
                                    payload.get("category"),
                                    payload.get("subcategory"),
                                    payload.get("back_path"),
                                    payload.get("side_path"),
                                    payload.get("detail_path"),
                                    payload.get("detection_metadata"),
                                ),
                            )
                    self._dispatch_next_tasks()
            except Exception as red_err:
                logger.warning(f"[Outbox] Re-delivery failed for {job_id}: {red_err}")
                try:
                    if outbox_id and hasattr(self._postgres_adapter, "record_outbox_delivery_failure"):
                        fail_info = self._postgres_adapter.record_outbox_delivery_failure(
                            outbox_id=outbox_id, error_message=str(red_err)
                        )
                        if fail_info.get("exhausted"):
                            self._close_unfinished_job(
                                job_id,
                                f"Outbox delivery exhausted after {fail_info.get('attempts')} attempts: {red_err}",
                            )
                            self._cleanup_temp_files(job_id)
                except Exception:
                    pass
        return delivered_count

    def _worker_wrapper(self, task: PriorityTaskEntry):
        """Executes task and dispatches next priority task upon worker completion."""
        try:
            self._process_job(
                task.job_id,
                task.front_path,
                task.category,
                task.subcategory,
                task.back_path,
                task.side_path,
                task.detail_path,
                task.detection_metadata
            )
        finally:
            with self._queue_lock:
                self._active_worker_count = max(0, self._active_worker_count - 1)
            self._dispatch_next_tasks()

    def recover_stranded_jobs(self) -> int:
        """Recovers jobs stranded in non-terminal states across memory, PostgreSQL, and staging artifacts."""
        recovered = 0
        non_terminal = (
            GarmentGenJobStatus.QUEUED,
            GarmentGenJobStatus.ANALYZING,
            GarmentGenJobStatus.GENERATING_MESH,
            GarmentGenJobStatus.SYNTHESIZING_TEXTURES,
            GarmentGenJobStatus.ASSEMBLING_3D,
            GarmentGenJobStatus.RENDERING_PREVIEW
        )
        for job_id, job in list(self._jobs.items()):
            if job.status in non_terminal:
                job.status = GarmentGenJobStatus.FAILED
                job.error = "Job interrupted by server restart. Attach the source photos again."
                job.updated_at = datetime.utcnow()
                self._cleanup_temp_files(job_id)
                recovered += 1
        with self._queue_lock:
            self._priority_queue.clear()
            self._active_worker_count = 0

        # Phase 002: Dispatch pending outbox entries FIRST — this re-delivers
        # any QUEUED jobs whose Redis enqueue was lost due to a process crash.
        outbox_dispatched = 0
        try:
            outbox_dispatched = self._dispatch_outbox_pending()
        except Exception as outbox_err:
            logger.warning(f"[GarmentJobManager] Outbox dispatch during recovery: {outbox_err}")

        active_jobs_metadata: Dict[str, Dict[str, Any]] = {}
        try:
            persisted_non_terminal = self._postgres_adapter.list_non_terminal_jobs()
            for db_job in persisted_non_terminal:
                jid = db_job.job_id
                active_jobs_metadata[jid] = {
                    "current_state": db_job.current_state,
                    "asset_path": db_job.asset_path,
                    "asset_sha256": db_job.asset_sha256,
                }
                reason = "Job interrupted by server restart before artifact publication."
                if db_job.current_state in ("CLAIMED", "PROCESSING", "VALIDATING", "PUBLISHING"):
                    def _recover_inflight(state):
                        if state.current_state in ("COMPLETED", "CANCELLED", "DEAD_LETTERED"):
                            return False, "Already terminal"
                        state.record_failure_attempt("supervisor_recovery", state.lease_generation, "worker_restarted", reason)
                        if state.is_lease_expired():
                            state.lease_expires_at = None
                        ok, msg = state.transition("FAILED", reason=reason, worker_id="supervisor_recovery")
                        if not ok:
                            ok, msg = state.transition("DEAD_LETTERED", reason=reason, worker_id="supervisor_recovery")
                        return ok, msg
                    ok, _, _ = self._postgres_adapter.mutate_job(jid, _recover_inflight)
                    if ok:
                        recovered += 1
                        self._cleanup_temp_files(jid)
                        perm_dir = Path(PERMANENT_ASSET_DIR) / jid
                        if perm_dir.is_dir() and not (perm_dir / "result.json").is_file():
                            shutil.rmtree(perm_dir, ignore_errors=True)
                elif db_job.current_state == "QUEUED":
                    front_exists = (Path(TEMP_BASE_DIR) / jid / "temp_input_front.raw").is_file()
                    expired = (time.time() - (db_job.created_at or 0.0)) > JOB_TIMEOUT_SECONDS

                    outbox_entry = None
                    try:
                        if hasattr(self._postgres_adapter, "load_latest_outbox_entry"):
                            outbox_entry = self._postgres_adapter.load_latest_outbox_entry(jid)
                        else:
                            outbox_entry = self._postgres_adapter.load_outbox_entry(jid, "JOB_QUEUED")
                    except Exception:
                        pass

                    outbox_exhausted = bool(
                        outbox_entry
                        and (
                            outbox_entry.get("status") == "EXHAUSTED"
                            or (
                                outbox_entry.get("delivered_at") is None
                                and outbox_entry.get("delivery_attempts", 0)
                                >= outbox_entry.get("max_delivery_attempts", 5)
                            )
                        )
                    )

                    if front_exists and not expired and not outbox_exhausted:
                        # Temp files exist, job is within deadline, and outbox can still deliver.
                        if outbox_entry and outbox_entry.get("delivered_at") is None:
                            logger.info(
                                f"[GarmentJobManager] QUEUED job {jid} has pending outbox entry; "
                                f"awaiting outbox dispatcher re-delivery."
                            )
                        continue
                    elif not front_exists or expired or outbox_exhausted:
                        # Temp files are gone, job timed out, or outbox exhausted — close it
                        close_reason = "Queued job interrupted or orphaned after server restart."
                        if outbox_exhausted:
                            close_reason = "Queued job exceeded outbox max delivery attempts."
                        ok, _, _ = self._close_unfinished_job(
                            jid,
                            close_reason,
                            expired_only=False,
                        )
                        if ok:
                            recovered += 1
                            self._cleanup_temp_files(jid)
                            try:
                                self._postgres_adapter.mark_outbox_acknowledged(jid)
                            except Exception:
                                pass
        except Exception as rec_err:
            logger.warning(f"[GarmentJobManager] PostgreSQL restart recovery notice: {rec_err}")

        try:
            self._artifact_publisher.startup_reconciliation(active_jobs_metadata)
        except Exception as art_err:
            logger.warning(f"[GarmentJobManager] Artifact startup reconciliation notice: {art_err}")

        logger.info(
            f"[GarmentJobManager] Server restart recovery: {recovered} stranded jobs cleared, "
            f"{outbox_dispatched} outbox entries dispatched."
        )
        return recovered

    def create_job(
        self,
        user_id: str,
        front_image_bytes: bytes,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        back_image_bytes: Optional[bytes] = None,
        side_image_bytes: Optional[bytes] = None,
        detail_image_bytes: Optional[bytes] = None,
        detection_metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None
    ) -> GarmentGenJob:
        # 1. Queue saturation check
        active_jobs = [
            j for j in self._jobs.values()
            if j.status in (
                GarmentGenJobStatus.QUEUED,
                GarmentGenJobStatus.ANALYZING,
                GarmentGenJobStatus.GENERATING_MESH,
                GarmentGenJobStatus.SYNTHESIZING_TEXTURES
            )
        ]
        if len(active_jobs) >= self._max_queue_depth:
            raise RuntimeError(f"Worker queue at maximum capacity ({self._max_queue_depth}). Please retry in a few moments.")

        # 2. Abuse protection & input limits
        if len(front_image_bytes) > 25 * 1024 * 1024:
            raise ValueError("Uploaded clothing photograph exceeds maximum file size limit of 25MB.")
        user_active = [j for j in active_jobs if j.user_id == user_id]
        if len(user_active) >= 2:
            raise ValueError("Maximum concurrent job limit reached (2). Please wait for active reconstruction to complete.")

        # 3. Server-side subscription entitlement check
        try:
            from backend.app.services.billing.entitlement_service import entitlement_service
            allowed, reason = entitlement_service.check_reconstruction_entitlement(user_id)
            if not allowed:
                raise PermissionError(reason)
        except PermissionError:
            raise
        except Exception as ent_err:
            logger.warning(f"[GarmentGen] Entitlement verification notice: {ent_err}")

        # Check duplicate photograph SHA256 cache for user
        img_sha = hashlib.sha256(front_image_bytes).hexdigest()
        cache_key = f"{user_id}:{img_sha}"

        if not detection_metadata and cache_key in self._completed_cache:
            cached_res = self._completed_cache[cache_key]
            existing_cached_db = self._postgres_adapter.load_job(cached_res.job_id)
            if existing_cached_db and existing_cached_db.user_id == user_id and existing_cached_db.current_state == "COMPLETED":
                restored_job = self._db_job_to_garment_job(existing_cached_db)
                restored_job.result = cached_res.model_copy(update={"is_cached": True})
                restored_job.current_stage = "3D garment restored from cached completed reconstruction."
                self._jobs[restored_job.job_id] = restored_job
                logger.info(f"[GarmentGen] Duplicate photograph detected for user {user_id}. Restored persisted 3D asset {restored_job.job_id}.")
                return restored_job
            self._completed_cache.pop(cache_key, None)

        # Canonical request fingerprint for idempotent registration & deduplication
        canonical_fp = compute_canonical_fingerprint(
            tenant_id=user_id,
            user_id=user_id,
            image_sha256=img_sha,
            garment_category=category or "auto",
            garment_subcategory=subcategory or "auto",
            reconstruction_config={"category": category, "subcategory": subcategory},
            model_version="14.16.0",
            pipeline_version="14.16.0"
        )

        job_id = f"job_{uuid.uuid4().hex[:12]}"
        effective_idem_key = idempotency_key or f"idem_{user_id}_{img_sha[:16]}"
        now = datetime.utcnow()
        correlation_id = f"corr_{uuid.uuid4().hex[:12]}"

        # Determine user priority level: 1 = Brand/Studio, 2 = Pro Atelier, 3 = Explorer/Free
        priority = 3
        try:
            from backend.app.services.billing.entitlement_service import entitlement_service
            plan, _ = entitlement_service.get_user_plan_and_sub(user_id)
            if plan.id == "studio":
                priority = 1
            elif plan.id == "pro":
                priority = 2 if entitlement_service.is_priority_queue(user_id) else 3
            else:
                priority = 3
        except Exception as prio_err:
            logger.debug(f"Priority lookup fallback for user {user_id}: {prio_err}")
            priority = 3

        # 1. PostgreSQL Atomic Idempotency + Durable Job Creation BEFORE temp I/O or Redis enqueue
        # Compute deterministic temp file paths up front so the transactional outbox row
        # committed inside create_job_atomic already has complete, accurate view paths.
        job_temp_dir = os.path.join(TEMP_BASE_DIR, job_id)
        front_path = os.path.join(job_temp_dir, "temp_input_front.raw")
        back_path = os.path.join(job_temp_dir, "temp_input_back.raw") if back_image_bytes else None
        side_path = os.path.join(job_temp_dir, "temp_input_side.raw") if side_image_bytes else None
        detail_path = os.path.join(job_temp_dir, "temp_input_detail.raw") if detail_image_bytes else None

        event_id = str(uuid.uuid4())
        outbox_payload = {
            "job_id": job_id,
            "event_id": event_id,
            "user_id": user_id,
            "tenant_id": user_id,
            "correlation_id": correlation_id,
            "lease_generation": 0,
            "category": category or "tops",
            "subcategory": subcategory or "tshirt",
            "front_path": front_path,
            "back_path": back_path,
            "side_path": side_path,
            "detail_path": detail_path,
            "detection_metadata": detection_metadata,
            "input_sha256": img_sha,
            "priority": priority
        }
        try:
            is_new, persisted_db_job = self._postgres_adapter.create_job_atomic(
                job_id=job_id,
                user_id=user_id,
                tenant_id=user_id,
                correlation_id=correlation_id,
                idempotency_key=effective_idem_key,
                canonical_fingerprint=canonical_fp,
                initial_queued=True,
                max_retries=3,
                lease_seconds=180.0,
                outbox_payload=outbox_payload,
                outbox_priority=priority,
            )
        except (TenantSecurityViolationException, IdempotencyConflictException):
            raise
        except Exception as pg_err:
            logger.error(f"[GarmentJobManager] PostgreSQL durable job creation failed for {job_id}: {pg_err}", exc_info=True)
            raise DurablePersistenceUnavailableError(
                f"PostgreSQL durable job creation failed: {pg_err}"
            ) from pg_err

        if not is_new:
            logger.info(
                f"[GarmentJobManager] Idempotent key '{effective_idem_key}' matched durable job {persisted_db_job.job_id}"
            )
            return self._db_job_to_garment_job(persisted_db_job)

        # 2. Write temporary input views ONLY after durable DB commit succeeded
        try:
            os.makedirs(job_temp_dir, exist_ok=True)
            with open(front_path, "wb") as f:
                f.write(front_image_bytes)

            temp_files = [front_path]
            if back_image_bytes and back_path:
                with open(back_path, "wb") as f:
                    f.write(back_image_bytes)
                temp_files.append(back_path)

            if side_image_bytes and side_path:
                with open(side_path, "wb") as f:
                    f.write(side_image_bytes)
                temp_files.append(side_path)

            if detail_image_bytes and detail_path:
                with open(detail_path, "wb") as f:
                    f.write(detail_image_bytes)
                temp_files.append(detail_path)
        except Exception as io_err:
            self._cleanup_temp_files(job_id)
            try:
                self._postgres_adapter.compensate_enqueue_failure(
                    job_id,
                    f"Temp input write failed: {io_err}",
                    expected_user_id=user_id,
                    expected_tenant_id=user_id,
                )
            except Exception:
                pass
            raise

        # 3. Enqueue canonical job_id to Redis Streams Broker (fast-path delivery).
        # If transient Redis failure occurs, the outbox entry committed atomically
        # above remains durable and will be re-delivered by the outbox dispatcher.
        enqueue_payload = dict(outbox_payload)
        enqueue_payload["lease_generation"] = persisted_db_job.lease_generation
        redis_delivered = False
        try:
            self._redis_broker.enqueue(enqueue_payload, priority=priority)
            redis_delivered = True
            msg_id = (
                self._redis_broker.get_last_message_id(job_id)
                if hasattr(self._redis_broker, "get_last_message_id")
                else None
            ) or "sync_enqueue"
            try:
                self._postgres_adapter.mark_outbox_delivered(
                    job_id=job_id,
                    event_type="JOB_QUEUED",
                    redis_message_id=msg_id,
                )
            except Exception:
                pass
        except (QueueOverloadedException, ConcurrencyLimitExceededException) as limit_err:
            # Backpressure: deterministic rejection, not transient outage.
            self._cleanup_temp_files(job_id)
            try:
                self._postgres_adapter.compensate_enqueue_failure(
                    job_id,
                    f"Broker backpressure: {limit_err}",
                    expected_user_id=user_id,
                    expected_tenant_id=user_id,
                )
            except Exception as comp_err:
                logger.error(f"[GarmentJobManager] Failed compensating DB job {job_id}: {comp_err}")
            raise
        except Exception as red_err:
            # Transient Redis failure: outbox record stays PENDING for eventual delivery.
            logger.warning(
                f"[GarmentJobManager] Redis Streams enqueue failed for {job_id}: {red_err}. "
                f"Outbox entry is durable — job will be re-delivered on next dispatcher cycle."
            )

        job = GarmentGenJob(
            job_id=job_id,
            user_id=user_id,
            status=GarmentGenJobStatus.QUEUED,
            progress=5,
            current_stage="Job queued for processing" if redis_delivered else "Queued in durable outbox; awaiting Redis delivery",
            created_at=now,
            updated_at=now,
            category=category,
            subcategory=subcategory,
            detection_metadata=detection_metadata,
            temporary_files=temp_files,
            input_sha256=img_sha,
            priority=priority
        )
        self._jobs[job_id] = job

        if redis_delivered:
            # Enqueue with real priority queue scheduling for local worker execution
            with self._queue_lock:
                task_entry = PriorityTaskEntry(
                    priority=priority,
                    created_at=time.time(),
                    job_id=job_id,
                    front_path=front_path,
                    category=category,
                    subcategory=subcategory,
                    back_path=back_path,
                    side_path=side_path,
                    detail_path=detail_path,
                    detection_metadata=detection_metadata
                )
                heapq.heappush(self._priority_queue, task_entry)

            # Dispatch next available priority tasks
            self._dispatch_next_tasks()
        return job

    def _close_unfinished_job(self, job_id, reason, expired_only=False):
        """Do not supersede a broker worker that acquired the queued job."""
        def close(state):
            if state.current_state != "QUEUED":
                return False, "Job already claimed or terminal"
            if expired_only and time.time() - state.created_at <= JOB_TIMEOUT_SECONDS:
                return False, "Job still within deadline"
            state.record_failure_attempt("local_worker", state.lease_generation, "worker_interrupted", reason)
            return state.transition("DEAD_LETTERED", reason, "supervisor_local_worker")
        return self._postgres_adapter.mutate_job(job_id, close)

    def get_job(self, job_id: str) -> Optional[GarmentGenJob]:
        # Authoritative PostgreSQL query
        try:
            db_job = self._postgres_adapter.load_job(job_id)
            if db_job:
                # The embedded worker records detailed stages before artifact publication.
                local = self._jobs.get(job_id)
                if (supabase_repo.require_durable_sessions and db_job.current_state == "QUEUED" and not local
                        and time.time() - db_job.created_at > JOB_TIMEOUT_SECONDS):
                    closed, _, latest = self._close_unfinished_job(job_id, "Reconstruction expired before publication.", True)
                    if closed:
                        self._cleanup_temp_files(job_id)
                    if latest:
                        return self._db_job_to_garment_job(latest)
                if db_job.current_state == "QUEUED" and local and local.user_id == db_job.user_id and local.status not in (
                    GarmentGenJobStatus.QUEUED, GarmentGenJobStatus.COMPLETED
                ):
                    return local
                return self._db_job_to_garment_job(db_job)
        except Exception as e:
            if supabase_repo.require_durable_sessions:
                from fastapi import HTTPException
                raise HTTPException(503, "Durable reconstruction storage is unavailable.") from None
            logger.debug(f"[GarmentJobManager] PostgreSQL read fallback for {job_id}: {e}")
        return None if supabase_repo.require_durable_sessions else self._jobs.get(job_id)

    def get_diagnostics(self, job_id: str) -> Optional[GarmentDiagnosticsV2]:
        return self._diagnostics.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        # 1. Authoritative cancellation in PostgreSQL
        try:
            ok, _, persisted = self._postgres_adapter.mutate_job(
                job_id,
                lambda j: j.transition("CANCELLED", reason="user_cancelled", worker_id="supervisor")
            )
            if persisted and not ok:
                return False
        except Exception as e:
            logger.warning(f"[GarmentJobManager] PostgreSQL cancellation notice for {job_id}: {e}")

        # 2. In-memory flag & local queue cancellation
        job = self._jobs.get(job_id)
        self._cancellation_flags[job_id] = True
        if job:
            job.status = GarmentGenJobStatus.CANCELLED
            job.current_stage = "Job cancelled by user"
            job.updated_at = datetime.utcnow()
        self._cleanup_temp_files(job_id)
        return True

    def _check_execution_health(self, job: GarmentGenJob, attempt_started: Optional[datetime] = None):
        """Cooperative cancellation and strict execution timeout check."""
        if self._cancellation_flags.get(job.job_id) or job.status == GarmentGenJobStatus.CANCELLED:
            raise RuntimeError(f"Job {job.job_id} cancelled by user.")
        elapsed = (datetime.utcnow() - (attempt_started or job.created_at)).total_seconds()
        if elapsed > JOB_TIMEOUT_SECONDS:
            raise TimeoutError(f"Job {job.job_id} exceeded maximum processing timeout of {JOB_TIMEOUT_SECONDS}s (elapsed: {elapsed:.1f}s).")

    def retry_job(self, job_id: str) -> Optional[GarmentGenJob]:
        """Retries a failed durable job if eligible, enforcing PostgreSQL transition before Redis enqueue."""
        with self._queue_lock:
            job = self._jobs.get(job_id)
            db_job = None
            try:
                db_job = self._postgres_adapter.load_job(job_id)
            except Exception as db_err:
                logger.error(f"[GarmentJobManager] Retry failed to load durable job {job_id}: {db_err}")
                return None

            if not db_job:
                return None
            if not job:
                job = self._db_job_to_garment_job(db_job)
                self._jobs[job_id] = job

            if job.status not in (GarmentGenJobStatus.FAILED, GarmentGenJobStatus.TIMED_OUT):
                return None
            if db_job.current_state != "FAILED" or db_job.retry_count >= db_job.max_retries:
                return None

            input_dir = Path(TEMP_BASE_DIR) / job_id
            front = input_dir / "temp_input_front.raw"
            if not front.is_file():
                return None
            extra_views = [input_dir / f"temp_input_{view}.raw" for view in ("back", "side", "detail")]
            back_p, side_p, detail_p = (str(path) if path.is_file() else None for path in extra_views)

            retry_payload = {
                "job_id": job_id,
                "user_id": db_job.user_id,
                "tenant_id": db_job.tenant_id,
                "correlation_id": db_job.correlation_id or job_id,
                "lease_generation": db_job.lease_generation,
                "category": job.category or "tops",
                "subcategory": job.subcategory or "tshirt",
                "front_path": str(front),
                "back_path": back_p,
                "side_path": side_p,
                "detail_path": detail_p,
                "detection_metadata": job.detection_metadata,
                "input_sha256": job.input_sha256 or "",
                "priority": job.priority
            }
            outbox_id = None
            if hasattr(self._postgres_adapter, "retry_job_atomic"):
                ok, msg, updated_db, outbox_id = self._postgres_adapter.retry_job_atomic(
                    job_id=job_id,
                    outbox_payload=retry_payload,
                    priority=job.priority,
                    reason="user_retry",
                )
            else:
                ok, msg, updated_db = self._postgres_adapter.mutate_job(
                    job_id,
                    lambda j: j.transition("QUEUED", reason="user_retry", worker_id="api_gateway")
                )
            if not ok or not updated_db:
                logger.warning(f"[GarmentJobManager] Retry transition rejected for {job_id}: {msg}")
                return None

            retry_payload["lease_generation"] = updated_db.lease_generation
            if outbox_id:
                retry_payload["event_id"] = outbox_id

            retry_delivered = False
            try:
                self._redis_broker.enqueue(retry_payload, priority=job.priority)
                retry_delivered = True
                msg_id = (
                    self._redis_broker.get_last_message_id(job_id)
                    if hasattr(self._redis_broker, "get_last_message_id")
                    else None
                ) or "sync_retry_enqueue"
                try:
                    self._postgres_adapter.mark_outbox_delivered(
                        outbox_id=outbox_id,
                        job_id=job_id,
                        event_type="JOB_RETRY",
                        redis_message_id=msg_id,
                    )
                except Exception:
                    pass
            except Exception as red_err:
                logger.warning(
                    f"[GarmentJobManager] Redis enqueue failed during retry of {job_id}: {red_err}. "
                    f"Outbox entry ({outbox_id}) will re-deliver on next dispatcher cycle."
                )

            job.status = GarmentGenJobStatus.QUEUED
            job.progress = 5
            job.current_stage = "Retrying garment reconstruction..." if retry_delivered else "Retry queued in durable outbox; awaiting Redis delivery"
            job.error = None
            job.retry_count = updated_db.retry_count
            job.updated_at = datetime.utcnow()
            if retry_delivered:
                task = PriorityTaskEntry(
                    job.priority, time.time(), job_id, str(front), job.category, job.subcategory,
                    back_p, side_p, detail_p, job.detection_metadata
                )
                heapq.heappush(self._priority_queue, task)
        if retry_delivered:
            self._dispatch_next_tasks()
        return job

    def get_health_status(self) -> Dict[str, Any]:
        """Provides operational observability and monitoring telemetry."""
        import resource
        now = datetime.utcnow()
        uptime_s = round((now - self._start_time).total_seconds(), 1)
        rss_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0 / 1024.0, 2)

        statuses = {}
        for j in self._jobs.values():
            st = str(j.status.value if hasattr(j.status, "value") else j.status)
            statuses[st] = statuses.get(st, 0) + 1

        outbox_stats: Dict[str, Any] = {}
        try:
            if hasattr(self._postgres_adapter, "get_outbox_stats"):
                outbox_stats = self._postgres_adapter.get_outbox_stats()
        except Exception:
            outbox_stats = {}

        return {
            "service": "YorvynGarmentJobManager",
            "status": "healthy",
            "uptime_seconds": uptime_s,
            "worker_threads_max": self._max_workers,
            "worker_threads_active": self._active_worker_count,
            "priority_queue_depth": len(self._priority_queue),
            "jobs_total": len(self._jobs),
            "jobs_by_status": statuses,
            "cache_entries_count": len(self._completed_cache),
            "peak_rss_mb": rss_mb,
            "job_timeout_seconds": JOB_TIMEOUT_SECONDS,
            "outbox": outbox_stats,
        }

    def _process_job(
        self,
        job_id: str,
        front_path: str,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        back_path: Optional[str] = None,
        side_path: Optional[str] = None,
        detail_path: Optional[str] = None,
        detection_metadata: Optional[Dict[str, Any]] = None
    ):
        """Worker pipeline: Segment -> Reconstruct -> Texture -> Assemble -> Preview -> Cleanup."""
        job = self._jobs.get(job_id)
        if not job or job.status == GarmentGenJobStatus.CANCELLED:
            self._cleanup_temp_files(job_id)
            return

        job_dir = os.path.join(TEMP_BASE_DIR, job_id)
        attempt_started = datetime.utcnow() if job.retry_count else job.created_at
        perm_job_dir = os.path.join(PERMANENT_ASSET_DIR, job_id)
        active_worker_id = f"local_worker_{threading.get_ident()}"
        active_lease_gen: Optional[int] = None

        try:
            # Mandatory Pre-Compute Durable Record & Lease Gate: never execute 3D compute for an unpersisted or terminal job
            db_state = self._postgres_adapter.load_job(job_id)
            if not db_state:
                raise RuntimeError("Reconstruction has no durable job record for publication.")
            if db_state.user_id != job.user_id or db_state.tenant_id != job.user_id:
                raise RuntimeError(f"Reconstruction owner mismatch for durable job {job_id}.")
            if db_state.current_state in ("COMPLETED", "CANCELLED", "DEAD_LETTERED"):
                logger.info(
                    f"[GarmentJobManager] Durable job {job_id} already terminal ({db_state.current_state}); skipping worker execution."
                )
                self._cleanup_temp_files(job_id)
                return
            if db_state.current_state in ("CLAIMED", "PROCESSING", "VALIDATING", "PUBLISHING"):
                if db_state.claimed_by_worker and not db_state.is_lease_expired():
                    logger.info(
                        f"[GarmentJobManager] Job {job_id} already leased by '{db_state.claimed_by_worker}' (gen={db_state.lease_generation}); skipping duplicate execution."
                    )
                    self._cleanup_temp_files(job_id)
                    return

            claim_ok, claim_msg, claimed_db = self._postgres_adapter.mutate_job(
                job_id,
                lambda j: j.transition("CLAIMED", reason="worker_claimed", worker_id=active_worker_id)
            )
            if not claim_ok or not claimed_db:
                raise RuntimeError(f"Failed to acquire durable lease for job {job_id}: {claim_msg}")
            active_lease_gen = claimed_db.lease_generation

            proc_ok, proc_msg, _ = self._postgres_adapter.mutate_job(
                job_id,
                lambda j: j.transition(
                    "PROCESSING",
                    reason="local_execution",
                    worker_id=active_worker_id,
                    lease_generation=active_lease_gen,
                )
            )
            if not proc_ok:
                raise RuntimeError(f"Failed to transition durable job {job_id} to PROCESSING: {proc_msg}")

            os.makedirs(perm_job_dir, exist_ok=True)
            self._check_execution_health(job, attempt_started)

            # Stage A: Garment Understanding
            job.status = GarmentGenJobStatus.ANALYZING
            job.progress = 20
            job.current_stage = "Analyzing garment silhouette, colors, and seams..."
            job.updated_at = datetime.utcnow()
            
            # Authoritative category and subcategory resolution with correction provenance
            resolved_cat = None
            resolved_sub = subcategory
            if category and category not in ("auto", "undefined", "none"):
                resolved_cat = category

            # Check user correction state in detection metadata
            if detection_metadata:
                ucs = detection_metadata.get("user_correction_state", {})
                if isinstance(ucs, dict) and "final_reconstruction_input" in ucs:
                    fri = ucs["final_reconstruction_input"]
                    if fri.get("category"):
                        resolved_cat = fri.get("category")
                    if fri.get("subcategory"):
                        resolved_sub = fri.get("subcategory")

            canonical_specification_v2 = None
            if detection_metadata and detection_metadata.get("canonical_specification_v2"):
                from backend.app.services.ai.contracts import CanonicalGarmentSpecificationV2
                canonical_specification_v2 = CanonicalGarmentSpecificationV2.model_validate(
                    detection_metadata["canonical_specification_v2"]
                )
                evidence_errors = canonical_specification_v2.validate_evidence_integrity()
                if evidence_errors:
                    raise ValueError("Queued canonical evidence failed integrity validation: " + "; ".join(evidence_errors))
                elif "final_reconstruction_input" in detection_metadata:
                    fri = detection_metadata["final_reconstruction_input"]
                    if fri.get("category"):
                        resolved_cat = fri.get("category")
                    if fri.get("subcategory"):
                        resolved_sub = fri.get("subcategory")

            # Per-job diagnostics and perception state; the analyzer reuses shared model weights.
            garment_analyzer = GarmentAnalyzer()
            features, seg_front = garment_analyzer.analyze(
                front_path,
                category_hint=resolved_cat,
                subcategory_hint=resolved_sub,
                job_id=job_id
            )
            front_intelligence = garment_analyzer.latest_intelligence_v2
            # If subcategory was authoritatively resolved from user correction, enforce it on features
            if resolved_sub and resolved_sub not in ("auto", "none", "undefined"):
                features.subcategory = resolved_sub
            if resolved_cat and resolved_cat not in ("auto", "none", "undefined"):
                features.category = resolved_cat

            if garment_analyzer.latest_diagnostics_v2:
                self._diagnostics[job_id] = garment_analyzer.latest_diagnostics_v2
            if detection_metadata and job_id in self._diagnostics:
                try:
                    if hasattr(self._diagnostics[job_id], "__dict__"):
                        setattr(self._diagnostics[job_id], "user_correction_state", detection_metadata.get("user_correction_state"))
                except Exception:
                    pass

            seg_back = None
            if back_path and os.path.exists(back_path):
                _, seg_back = garment_analyzer.analyze(back_path, category_hint=features.category, job_id=f"{job_id}_back")

            # Preserve front-view perception (the back analyzer updates the legacy
            # singleton) and merge only source-cited OBSERVED V2 component presence.
            reconstruction_intelligence = front_intelligence
            if canonical_specification_v2 is not None:
                from backend.app.services.garments.reconstruction.evidence_adapter import apply_observed_components
                reconstruction_intelligence = apply_observed_components(
                    front_intelligence,
                    canonical_specification_v2
                )
                
            self._check_execution_health(job, attempt_started)

            # Stage B: 3D Geometry Generation
            job.status = GarmentGenJobStatus.GENERATING_MESH
            job.progress = 45
            job.current_stage = f"Generating 3D wearable {features.subcategory} geometry..."
            job.updated_at = datetime.utcnow()
            
            from backend.app.services.intelligence.garment_policy import geometry_strategy
            strategy = geometry_strategy(features.category, features.subcategory) if canonical_specification_v2 else None
            geometry_start = time.monotonic()
            builder = GarmentMeshBuilder()
            garment_mesh = builder.build_mesh(
                category=features.category,
                subcategory=features.subcategory,
                sleeve_length=features.sleeve_length,
                neckline_type=features.neckline_type,
                fit=features.fit,
                intelligence=reconstruction_intelligence,
                front_image=seg_front,
                back_image=seg_back, local_strategy=strategy
            )
            
            # Enrich diagnostics with 3D mesh telemetry and multi-view fusion
            rec_out = builder.latest_reconstruction_output
            if rec_out and ((seg_back and os.path.exists(back_path)) or (side_path and os.path.exists(side_path))):
                from .reconstruction import MultiViewGarmentFuser
                with Image.open(front_path) as f_img:
                    b_img = Image.open(back_path) if (back_path and os.path.exists(back_path)) else None
                    s_img = Image.open(side_path) if (side_path and os.path.exists(side_path)) else None
                    rec_out = MultiViewGarmentFuser.fuse_views(
                        rec_out,
                        front_image=f_img,
                        back_image=b_img,
                        side_image=s_img,
                        intelligence=reconstruction_intelligence
                    )
                    garment_mesh = rec_out.mesh

            # Phase 7: Learned Multi-View & Missing Surface Disentanglement
            from .intelligence import learned_multiview_engine
            with Image.open(front_path) as f_img:
                b_img = Image.open(back_path) if (back_path and os.path.exists(back_path)) else None
                mv_res = learned_multiview_engine.analyze_views(
                    front_image=f_img,
                    back_image=b_img,
                    category=features.category,
                    subcategory=features.subcategory
                )

            # Phase 8: Neural Reconstruction Execution Audit Logging
            from dataclasses import asdict
            from backend.app.services.garments.evaluation.reconstruction_auditor import neural_reconstruction_execution_auditor
            audit_dict = None
            if rec_out:
                with Image.open(front_path) as f_img:
                    audit_rec = neural_reconstruction_execution_auditor.record_execution(
                        job_id=job_id,
                        front_image=f_img,
                        reconstruction_output=rec_out,
                        intelligence=reconstruction_intelligence
                    )
                    audit_dict = asdict(audit_rec)

            if job_id in self._diagnostics and rec_out:
                self._diagnostics[job_id].audit_telemetry = audit_dict
                self._diagnostics[job_id].mesh_telemetry = {
                    "vertex_count": len(garment_mesh.positions),
                    "triangle_count": len(garment_mesh.indices),
                    "is_manifold": rec_out.quality_report.is_manifold,
                    "quality_score": rec_out.quality_report.quality_score,
                    "boundary_loops": rec_out.quality_report.boundary_loops,
                    "degenerate_triangle_count": rec_out.quality_report.degenerate_triangle_count,
                    "panels": [p.name for p in rec_out.panels],
                    "observed_surface_ratio": mv_res.observed_surface_ratio,
                    "inferred_surface_ratio": mv_res.inferred_surface_ratio,
                    "provenance": rec_out.provenance,
                    "engine_id": rec_out.engine_id,
                    "reconstruction_time_ms": rec_out.reconstruction_time_ms,
                    "panel_provenance": mv_res.panel_provenance,
                    "cross_view_similarity": mv_res.cross_view_similarity,
                    "component_graph": rec_out.component_graph.to_dict() if (rec_out and rec_out.component_graph) else None,
                    "proportions": {
                        "shoulder_width_m": rec_out.proportions.shoulder_width_m,
                        "chest_width_m": rec_out.proportions.chest_width_m,
                        "waist_width_m": rec_out.proportions.waist_width_m,
                        "torso_length_m": rec_out.proportions.torso_length_m,
                        "sleeve_length_m": rec_out.proportions.sleeve_length_m,
                        "inseam_length_m": rec_out.proportions.inseam_length_m,
                        "ease_margin_m": rec_out.proportions.ease_margin_m,
                        "scale_calibration": rec_out.proportions.scale_calibration
                    }
                }
            
            self._check_execution_health(job, attempt_started)

            geometry_ms = (time.monotonic() - geometry_start) * 1000
            # Stage C: Texture & Material Synthesis
            job.status = GarmentGenJobStatus.SYNTHESIZING_TEXTURES
            job.progress = 65
            job.current_stage = "Synthesizing category-tailored PBR diffuse, normal, and metallic-roughness maps..."
            job.updated_at = datetime.utcnow()
            
            # Phase 4: Intelligent Garment Appearance Analysis & Reference-Driven Reconstruction
            from .appearance import garment_appearance_analyzer, reference_texture_reconstructor, GarmentUVReconstructionEngine
            import base64

            seg_front_alpha = np.array(seg_front.split()[-1]) if seg_front.mode == "RGBA" else np.array(seg_front.convert("L"))
            appearance = garment_appearance_analyzer.analyze_appearance(
                image=seg_front,
                alpha_mask=seg_front_alpha,
                category=features.category,
                subcategory=features.subcategory,
                has_back_view=(seg_back is not None),
                job_id=job_id,
                intelligence=reconstruction_intelligence
            )

            tex_res = reference_texture_reconstructor.reconstruct_textures(
                segmented_front=seg_front,
                appearance=appearance,
                category=features.category,
                subcategory=features.subcategory,
                output_dir=perm_job_dir,
                segmented_back=seg_back,
                texture_size=1024
            )

            diffuse_path = tex_res["diffuse_path"]
            normal_path = tex_res["normal_path"]
            mr_path = tex_res["metallic_roughness_path"]
            ao_path = tex_res["occlusion_path"]
            roughness_path = mr_path  # Backward compatibility

            if job_id in self._diagnostics:
                diag = self._diagnostics[job_id]
                uv_layout = GarmentUVReconstructionEngine.get_layout(features.category, features.subcategory)
                uv_preview_img = GarmentUVReconstructionEngine.render_uv_layout_preview(uv_layout, size=256)
                uv_buf = io.BytesIO()
                uv_preview_img.save(uv_buf, format="PNG")
                uv_b64 = base64.b64encode(uv_buf.getvalue()).decode("utf-8")

                def _file_to_b64(path: str, max_dim: int = 256) -> str:
                    with Image.open(path) as im:
                        im_c = im.copy()
                        im_c.thumbnail((max_dim, max_dim))
                        b = io.BytesIO()
                        im_c.save(b, format="PNG")
                        return f"data:image/png;base64,{base64.b64encode(b.getvalue()).decode('utf-8')}"

                diag.appearance_telemetry = {
                    "fabric": appearance.fabric.model_dump(),
                    "pattern_type": appearance.pattern_type,
                    "pattern_confidence": appearance.pattern_confidence,
                    "graphic": appearance.graphic.model_dump(),
                    "hardware": [h.model_dump() for h in appearance.hardware],
                    "color_delta_e": tex_res["color_delta_e"],
                    "histogram_similarity": tex_res["histogram_similarity"],
                    "layout_category": tex_res["layout_category"],
                    "islands_count": tex_res["islands_count"],
                    "provenance": appearance.provenance
                }
                diag.diffuse_preview_data_url = _file_to_b64(diffuse_path)
                diag.normal_preview_data_url = _file_to_b64(normal_path)
                diag.roughness_preview_data_url = _file_to_b64(mr_path)
                diag.uv_layout_preview_data_url = f"data:image/png;base64,{uv_b64}"
            
            # Phase 5: Universal Avatar-Aware Garment Fitting, Collision Resolution & Cloth Draping
            from .fitting import universal_garment_fitting_engine
            garment_mesh, fit_res = universal_garment_fitting_engine.fit_garment(
                mesh=garment_mesh,
                category=features.category,
                subcategory=features.subcategory,
                fabric_type=appearance.fabric.fabric_category,
                job_id=job_id
            )
            if job_id in self._diagnostics:
                diag_entry = self._diagnostics[job_id]
                diag_entry.fitting_telemetry = fit_res.model_dump()
                if fit_res.motion_simulation:
                    diag_entry.motion_telemetry = fit_res.motion_simulation.model_dump()
                if fit_res.wrinkle_deformation:
                    diag_entry.wrinkle_telemetry = fit_res.wrinkle_deformation.model_dump()
            
            self._check_execution_health(job, attempt_started)

            # Stage D: Assemble 3D GLB
            job.status = GarmentGenJobStatus.ASSEMBLING_3D
            job.progress = 80
            job.current_stage = "Assembling binary GLB asset with full PBR materials and Ara 3D rig..."
            job.updated_at = datetime.utcnow()
            
            with open(diffuse_path, "rb") as f:
                diff_bytes = f.read()
            with open(normal_path, "rb") as f:
                norm_bytes = f.read()
            with open(mr_path, "rb") as f:
                mr_bytes = f.read()
            with open(ao_path, "rb") as f:
                ao_bytes = f.read()
                
            garment_title = f"{features.primary_color_name.title()} {features.subcategory.replace('_', ' ').title()}"
            glb_bytes = glb_exporter.export(
                mesh=garment_mesh,
                diffuse_png_bytes=diff_bytes,
                normal_png_bytes=norm_bytes,
                metallic_roughness_png_bytes=mr_bytes,
                occlusion_png_bytes=ao_bytes,
                name=f"garment_{job_id}",
                metallic_factor=appearance.fabric.metalness,
                roughness_factor=appearance.fabric.roughness,
                component_graph=rec_out.component_graph if rec_out else None
            )
            
            evaluation_start = time.monotonic()
            inspection = None
            repaired = False
            if canonical_specification_v2:
                from .mesh_validation_service import MeshValidationService
                from .chat_candidate import remove_invalid_triangles
                inspection = MeshValidationService.validate_glb_bytes(glb_bytes, features.category)
                if not inspection.is_valid and (inspection.duplicate_faces or inspection.degenerate_faces):
                    glb_bytes = remove_invalid_triangles(glb_bytes)
                    inspection = MeshValidationService.validate_glb_bytes(glb_bytes, features.category)
                    repaired = True
                if not inspection.is_valid:
                    raise ValueError("Candidate failed structural validation before publication.")
            evaluation_ms = (time.monotonic() - evaluation_start) * 1000
            glb_filename = "garment.glb"
            glb_path = os.path.join(perm_job_dir, glb_filename)
            with open(glb_path, "wb") as f:
                f.write(glb_bytes)

            # Fenced Artifact Publication & PostgreSQL Authoritative State Commit (Phase 14.16)
            val_ok, val_msg, _ = self._postgres_adapter.mutate_job(
                job_id,
                lambda j: j.transition(
                    "VALIDATING",
                    reason="glb_export_validated",
                    worker_id=active_worker_id,
                    lease_generation=active_lease_gen,
                )
            )
            if not val_ok:
                raise RuntimeError(f"Failed durable VALIDATING transition for {job_id}: {val_msg}")

            pub_ok, pub_msg, _ = self._postgres_adapter.mutate_job(
                job_id,
                lambda j: j.transition(
                    "PUBLISHING",
                    reason="publishing_artifact",
                    worker_id=active_worker_id,
                    lease_generation=active_lease_gen,
                )
            )
            if not pub_ok:
                raise RuntimeError(f"Failed durable PUBLISHING transition for {job_id}: {pub_msg}")

            db_j = self._postgres_adapter.load_job(job_id)
            if not db_j:
                raise RuntimeError("Reconstruction has no durable job record for publication.")
            if db_j.user_id != job.user_id or db_j.tenant_id != job.user_id:
                raise RuntimeError(f"Publication ownership verification failed for job {job_id}.")
            if db_j.current_state != "PUBLISHING" or db_j.lease_generation != active_lease_gen:
                raise RuntimeError(
                    f"Fenced publication aborted: durable state '{db_j.current_state}' gen={db_j.lease_generation} "
                    f"(expected PUBLISHING gen={active_lease_gen})"
                )

            pub_res = self._artifact_publisher.publish_artifact_fenced(
                job_id=job_id,
                glb_bytes=glb_bytes,
                user_id=db_j.user_id,
                tenant_id=db_j.tenant_id,
                correlation_id=db_j.correlation_id or job_id,
                lease_generation=active_lease_gen,
                job_state_ref=db_j
            )
            canonical_glb_path = pub_res["canonical_path"]
            canonical_sha256 = pub_res["sha256"]

            commit_ok, commit_msg, _ = self._postgres_adapter.mutate_job(
                job_id,
                lambda j: j.commit_completion(
                    worker_id=active_worker_id,
                    lease_generation=active_lease_gen,
                    asset_path=canonical_glb_path,
                    asset_sha256=canonical_sha256
                )
            )
            if not commit_ok:
                raise RuntimeError(f"Durable completion commit rejected for {job_id}: {commit_msg}")

            try:
                self._redis_broker.acknowledge(job_id, worker_id=active_worker_id)
            except Exception as ack_err:
                logger.warning(f"[GarmentJobManager] Redis stream acknowledge notice for {job_id}: {ack_err}")

            # Mark outbox as acknowledged (DURABLE-JOB-FIX-002)
            try:
                self._postgres_adapter.mark_outbox_acknowledged(job_id)
            except Exception as outbox_ack_err:
                logger.warning(f"[GarmentJobManager] Outbox acknowledgement notice for {job_id}: {outbox_ack_err}")

            self._check_execution_health(job, attempt_started)

            # Stage 5: Render 3D Preview Thumbnail
            job.status = GarmentGenJobStatus.RENDERING_PREVIEW
            job.progress = 92
            job.current_stage = "Rendering 3D studio preview thumbnail..."
            job.updated_at = datetime.utcnow()
            
            thumb_filename = "preview.png"
            thumb_path = os.path.join(perm_job_dir, thumb_filename)
            render_start = time.monotonic()
            with Image.open(diffuse_path) as diff_img:
                preview_renderer.render_preview(garment_mesh, diff_img, thumb_path, image_size=512)

            render_ms = (time.monotonic() - render_start) * 1000
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
            
            job_dur_ms = round((datetime.utcnow() - job.created_at).total_seconds() * 1000.0, 2)
            cost_usd = 0.0000
            rec_prov = rec_out.provenance if rec_out else "procedural_fallback"

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
                created_at=datetime.utcnow().isoformat(),
                cost_usd=cost_usd,
                duration_ms=job_dur_ms,
                reconstruction_provenance=rec_prov,
                intelligence_execution={"schema_version": "16.0", "strategy": strategy,
                                        "engine": rec_out.engine_id if rec_out else "legacy_procedural",
                                        "fallback_reason": None if rec_out else "category_engine_failed",
                                        "geometry_ms": geometry_ms, "render_ms": render_ms,
                                        "evaluation_ms": evaluation_ms, "structural_repair": repaired,
                                        "mesh_structure": "PASSED", "mesh_report": inspection.to_dict(),
                                        "committed_sha256": canonical_sha256, "geometry_accuracy": "NOT_EVALUATED",
                                        "visual_accuracy": "NOT_EVALUATED", "material_accuracy": "NOT_EVALUATED",
                                        "fit_accuracy": "NOT_EVALUATED"} if inspection else None,
                is_cached=False
            )
            
            # Save in duplicate session cache
            if job.input_sha256:
                self._completed_cache[f"{job.user_id}:{job.input_sha256}"] = result

            # Purge raw input images immediately before completing to guarantee privacy
            self._cleanup_temp_files(job_id)

            metadata = Path(perm_job_dir) / "result.json"
            pending = metadata.with_suffix(".tmp")
            pending.write_text(result.model_dump_json(), encoding="utf-8")
            pending.replace(metadata)
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

            # Record reconstruction usage in centralized entitlement service
            try:
                from backend.app.services.billing.entitlement_service import entitlement_service
                entitlement_service.record_reconstruction_usage(
                    user_id=job.user_id,
                    job_id=job_id,
                    cost_usd=cost_usd,
                    provenance=rec_prov
                )
            except Exception as ent_rec_err:
                logger.warning(f"[GarmentGen] Error recording entitlement usage for {job_id}: {ent_rec_err}")
            
            logger.info(f"[GarmentGen] Job {job_id} successfully completed. Cloudinary CDN: {cld_delivery_url}")
            
        except TimeoutError as te:
            logger.warning(f"[GarmentGen] Job {job_id} timed out: {te}")
            job.status = GarmentGenJobStatus.TIMED_OUT
            job.error = str(te)
            job.current_stage = "Garment reconstruction timed out."
            job.updated_at = datetime.utcnow()
            if os.path.exists(perm_job_dir) and not job.result:
                try:
                    shutil.rmtree(perm_job_dir)
                except Exception:
                    pass
            supabase_repo.save_job({
                "job_id": job_id,
                "user_id": job.user_id,
                "status": "timed_out",
                "error_details": str(te),
                "progress": 0
            })

        except Exception as e:
            logger.error(f"[GarmentGen] Error processing job {job_id}: {str(e)}", exc_info=True)
            job.status = GarmentGenJobStatus.FAILED
            job.error = f"Reconstruction failed: {str(e)}"
            job.current_stage = "Garment reconstruction encountered an error."
            job.updated_at = datetime.utcnow()
            # Clean up incomplete permanent asset dir if generation failed
            if os.path.exists(perm_job_dir) and not job.result:
                try:
                    shutil.rmtree(perm_job_dir)
                except Exception as cleanup_err:
                    logger.warning(f"[GarmentGen] Error removing failed permanent dir for {job_id}: {cleanup_err}")
            supabase_repo.save_job({
                "job_id": job_id,
                "user_id": job.user_id,
                "status": "failed",
                "error_details": str(e),
                "progress": 0
            })
            
        finally:
            if job.status in (GarmentGenJobStatus.FAILED, GarmentGenJobStatus.TIMED_OUT):
                err_reason = job.error or "Worker failed before artifact publication."
                try:
                    if active_lease_gen is not None:
                        def _mark_failed(state):
                            if state.current_state in ("COMPLETED", "CANCELLED", "DEAD_LETTERED", "FAILED"):
                                return False, "Already terminal or failed"
                            state.record_failure_attempt(
                                active_worker_id,
                                active_lease_gen,
                                "worker_failed",
                                err_reason,
                            )
                            return state.transition(
                                "FAILED",
                                reason=err_reason,
                                worker_id=active_worker_id,
                                lease_generation=active_lease_gen,
                            )
                        closed, _, _ = self._postgres_adapter.mutate_job(job_id, _mark_failed)
                        if not closed:
                            self._close_unfinished_job(job_id, err_reason)
                    else:
                        self._close_unfinished_job(job_id, err_reason)
                except Exception as pg_cleanup_err:
                    logger.error(f"[GarmentJobManager] Could not persist failure closure for {job_id}: {pg_cleanup_err}")
            # Release reservation quota slot in entitlement service
            try:
                from backend.app.services.billing.entitlement_service import entitlement_service
                entitlement_service.release_reconstruction_slot(job.user_id)
            except Exception:
                pass

            # STRICT PRIVACY ENFORCEMENT:
            # Permanently purge original uploaded photograph and temporary artifacts from disk across all terminal states!
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
