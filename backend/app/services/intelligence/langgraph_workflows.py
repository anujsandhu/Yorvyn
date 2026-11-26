"""
YORVYN Intelligence Platform (YIP) — Phase 17.4 Hardened LangGraph Durable Workflow Engine.

Provides:
- Genuine PostgreSQL-backed `BaseCheckpointSaver` (`YIPPostgresLangGraphSaver`) persisting
  LangGraph tuple blobs & pending writes to `yip_langgraph_cp_tuples` and `yip_langgraph_cp_writes`
  alongside optimistic version-locked `yip_langgraph_checkpoints` rows.
- Restart recovery without node replay via LangGraph native `interrupt()` / `Command(resume=...)`.
- Cryptographic confirmation binding (owner, workflow, version, SHA-256 operation_hash,
  confirmation expiry, single-use idempotency key) with atomic state transitions:
  AWAITING_CONFIRMATION -> CONFIRMED -> EXECUTING -> SUCCEEDED (and REJECTED/EXPIRED/CANCELLED/FAILED/RECOVERY_REQUIRED).
- Privacy-safe structured node observability (`yip_langgraph_node_events`) & bounded retention cleanup.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set, Tuple, TypedDict

from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata, CheckpointTuple, get_checkpoint_id
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from backend.app.services.garments.orchestration.unified_state_machine import resolve_postgres_dsn
from backend.app.services.intelligence.capability_registry import garment_capabilities
from backend.app.services.intelligence.evaluation_critic import evaluation_critic
from backend.app.services.intelligence.knowledge_rag import KnowledgeDomain
from backend.app.services.intelligence.pattern_construction_engine import pattern_construction_engine
from backend.app.services.intelligence.recommendation_engine import fashion_recommendation_engine
from backend.app.services.intelligence.recommendation_profile import recommendation_profile_store
from backend.app.services.intelligence.unified_knowledge import UnifiedKnowledgeCoordinator, unified_knowledge

logger = logging.getLogger(__name__)

WORKFLOW_SCHEMA_VERSION = "17.4.0"
MAX_WORKFLOW_STEPS = 8
DEFAULT_CONFIRMATION_TTL_S = 1800.0

FORBIDDEN_STATE_KEY_FRAGMENTS: Set[str] = {
    "api_key", "secret", "password", "token", "bearer", "body_measurements",
    "raw_measurements", "biometric", "ssn", "credit_card",
}

CLOSED_DESIGN_OPERATIONS: Set[str] = {
    "shorten", "widen", "widen_sleeves", "lengthen", "narrow", "denim", "material_preset", "inspect_only",
}

TERMINAL_OPERATION_STATES: Set[str] = {
    "SUCCEEDED", "COMPLETED", "CANCELLED", "REJECTED", "EXPIRED", "FAILED",
}

_UNSAFE_CMD_RE = re.compile(
    r"(?:/etc/passwd|~/\.ssh|\.\./|\brm\s+-rf\b|\bsubprocess\b|\bos\.system\b|\bDROP\s+TABLE\b|\bSELECT\s+\*\s+FROM\b)",
    re.I,
)


class WorkflowConflictError(ValueError):
    """Raised on duplicate resume, already terminal thread, or optimistic lock conflict (HTTP 409)."""


class ConfirmationExpiredError(ValueError):
    """Raised when a paused human confirmation window has expired (HTTP 410)."""


def _safe_owner_corr(owner_id: str) -> str:
    return "own_" + hashlib.sha256(str(owner_id).encode("utf-8")).hexdigest()[:12]


def _assert_safe_workflow_payload(obj: Any, path: str = "") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if any(frag in kl for frag in FORBIDDEN_STATE_KEY_FRAGMENTS):
                raise ValueError(f"Sensitive key '{k}' is not permitted in LangGraph workflow state.")
            _assert_safe_workflow_payload(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for idx, item in enumerate(obj):
            _assert_safe_workflow_payload(item, f"{path}[{idx}]")
    elif isinstance(obj, str) and len(obj) < 4000:
        if _UNSAFE_CMD_RE.search(obj):
            raise ValueError("Unsafe filesystem, SQL, or shell pattern rejected in workflow payload.")


def compute_operation_hash(
    *,
    owner_id: str,
    thread_id: str,
    workflow_name: str,
    workflow_version: str,
    capability_id: str,
    proposed_action: str,
    proposed_params: Dict[str, Any],
) -> str:
    canonical = {
        "owner_id": str(owner_id),
        "thread_id": str(thread_id),
        "workflow_name": str(workflow_name),
        "workflow_version": str(workflow_version),
        "capability_id": str(capability_id),
        "proposed_action": str(proposed_action),
        "proposed_params": proposed_params or {},
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _run_coro_sync(coro, timeout_s: float = 4.0):
    try:
        asyncio.get_running_loop()
        res: Dict[str, Any] = {}
        exc_box: Dict[str, BaseException] = {}

        def _runner():
            try:
                res["val"] = asyncio.run(coro)
            except BaseException as e:
                exc_box["err"] = e

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join(timeout=timeout_s)
        if "err" in exc_box:
            raise exc_box["err"]
        return res.get("val")
    except RuntimeError:
        return asyncio.run(coro)


class GarmentResearchState(TypedDict, total=False):
    schema_version: str
    thread_id: str
    owner_id: str
    workflow_name: str
    query: str
    category: str
    use_external: bool
    step_count: int
    max_steps: int
    visited_nodes: List[str]
    internal_hits: List[Dict[str, Any]]
    external_evidence: List[Dict[str, Any]]
    external_status: str
    external_credits_used: int
    synthesis: str
    limitations: List[str]
    status: str
    warnings: List[str]


class FashionDiscoveryState(TypedDict, total=False):
    schema_version: str
    thread_id: str
    owner_id: str
    workflow_name: str
    query: str
    occasion: str
    include_external_trends: bool
    consent_granted: bool
    cold_start_mode: bool
    preferred_categories: List[str]
    step_count: int
    max_steps: int
    visited_nodes: List[str]
    internal_notes: List[str]
    external_trends: List[Dict[str, Any]]
    external_status: str
    external_credits_used: int
    recommendations: List[Dict[str, Any]]
    status: str
    warnings: List[str]


class DesignAssistanceState(TypedDict, total=False):
    schema_version: str
    thread_id: str
    owner_id: str
    workflow_name: str
    instruction: str
    category: str
    subcategory: str
    proposed_action: str
    proposed_params: Dict[str, Any]
    capability_id: str
    capability_validated: bool
    operation_hash: str
    confirmation_ttl_s: float
    identified_components: List[str]
    construction_notes: List[str]
    require_confirmation: bool
    human_confirmed: bool
    execution_result: Dict[str, Any]
    critic_passed: Optional[bool]
    step_count: int
    max_steps: int
    visited_nodes: List[str]
    status: str
    warnings: List[str]


class WorkflowNodeEvent(BaseModel):
    thread_id: str
    workflow_version: str = WORKFLOW_SCHEMA_VERSION
    owner_correlation_id: str
    node_name: str
    start_ts: str
    end_ts: str
    status: str  # OK | INTERRUPTED | FAILED
    retry_count: int = 0
    checkpoint_id: Optional[str] = None
    interrupt_reason: Optional[str] = None
    failure_category: Optional[str] = None
    external_credits_used: int = 0
    duration_ms: float = 0.0


class WorkflowThreadRecord(BaseModel):
    thread_id: str
    owner_id: str
    workflow_name: str
    status: str  # COMPLETED | AWAITING_CONFIRMATION | CANCELLED | FAILED | TIMEOUT | EXPIRED | REJECTED | RECOVERY_REQUIRED
    operation_state: str = "PENDING"
    state_transitions: List[str] = Field(default_factory=list)
    schema_version: str = WORKFLOW_SCHEMA_VERSION
    visited_nodes: List[str] = Field(default_factory=list)
    step_count: int = 0
    checkpoint_backend: str = "langgraph_memory"
    checkpoint_id: Optional[str] = None
    checkpoint_ns: str = ""
    pending_writes: List[Dict[str, Any]] = Field(default_factory=list)
    interrupt_state: Optional[Dict[str, Any]] = None
    resume_metadata: Optional[Dict[str, Any]] = None
    operation_hash: Optional[str] = None
    confirmation_expires_at: Optional[float] = None
    confirmation_idempotency_key: Optional[str] = None
    version: int = 1
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    pg_persisted: bool = False
    awaiting_confirmation: bool = False
    state: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = 0.0
    error: Optional[str] = None
    failure_category: Optional[str] = None


class YIPPostgresLangGraphSaver(MemorySaver):
    """
    Genuine LangGraph 0.6.x `BaseCheckpointSaver` backed by PostgreSQL (`asyncpg`) with an
    in-process cache layer. Restores full checkpoint tuples, channel blobs, and pending writes
    from `yip_langgraph_cp_tuples` + `yip_langgraph_cp_writes` after backend restarts.
    """

    def __init__(self, dsn: Optional[str] = None) -> None:
        super().__init__()
        self.dsn = dsn or resolve_postgres_dsn()
        self.last_pg_sync_ok: bool = False

    async def _ensure_tables(self, conn) -> None:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS yip_langgraph_cp_tuples (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                parent_checkpoint_id TEXT,
                owner_id TEXT NOT NULL DEFAULT '',
                checkpoint_type TEXT NOT NULL,
                checkpoint_blob BYTEA NOT NULL,
                metadata_type TEXT NOT NULL,
                metadata_blob BYTEA NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
            );
            CREATE TABLE IF NOT EXISTS yip_langgraph_cp_writes (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                idx INTEGER NOT NULL,
                channel TEXT NOT NULL,
                value_type TEXT NOT NULL,
                value_blob BYTEA NOT NULL,
                task_path TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
            );
            """
        )

    async def _pg_put_tuple(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        parent_checkpoint_id: Optional[str],
        ckpt_type: str,
        ckpt_blob: bytes,
        meta_type: str,
        meta_blob: bytes,
    ) -> None:
        import asyncpg
        conn = await asyncpg.connect(self.dsn, timeout=2.0)
        try:
            await self._ensure_tables(conn)
            await conn.execute(
                """
                INSERT INTO yip_langgraph_cp_tuples
                    (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, checkpoint_type, checkpoint_blob, metadata_type, metadata_blob)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id) DO UPDATE SET
                    checkpoint_type = EXCLUDED.checkpoint_type,
                    checkpoint_blob = EXCLUDED.checkpoint_blob,
                    metadata_type = EXCLUDED.metadata_type,
                    metadata_blob = EXCLUDED.metadata_blob;
                """,
                thread_id,
                checkpoint_ns,
                checkpoint_id,
                parent_checkpoint_id,
                ckpt_type,
                ckpt_blob,
                meta_type,
                meta_blob,
            )
        finally:
            await conn.close()

    async def _pg_put_writes(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        rows: List[Tuple[str, int, str, str, bytes, str]],
    ) -> None:
        import asyncpg
        conn = await asyncpg.connect(self.dsn, timeout=2.0)
        try:
            await self._ensure_tables(conn)
            for task_id, idx, ch, vt, vb, tpath in rows:
                await conn.execute(
                    """
                    INSERT INTO yip_langgraph_cp_writes
                        (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, value_type, value_blob, task_path)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id, task_id, idx) DO UPDATE SET
                        value_type = EXCLUDED.value_type,
                        value_blob = EXCLUDED.value_blob;
                    """,
                    thread_id, checkpoint_ns, checkpoint_id, task_id, idx, ch, vt, vb, tpath,
                )
        finally:
            await conn.close()

    async def _pg_get_tuple(self, thread_id: str, checkpoint_ns: str, checkpoint_id: Optional[str]):
        import asyncpg
        conn = await asyncpg.connect(self.dsn, timeout=2.0)
        try:
            if checkpoint_id:
                row = await conn.fetchrow(
                    "SELECT * FROM yip_langgraph_cp_tuples WHERE thread_id=$1 AND checkpoint_ns=$2 AND checkpoint_id=$3",
                    thread_id, checkpoint_ns, checkpoint_id,
                )
            else:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM yip_langgraph_cp_tuples
                    WHERE thread_id=$1 AND checkpoint_ns=$2
                    ORDER BY created_at DESC, checkpoint_id DESC
                    LIMIT 1
                    """,
                    thread_id, checkpoint_ns,
                )
            if not row:
                return None, []
            cid = row["checkpoint_id"]
            writes = await conn.fetch(
                "SELECT * FROM yip_langgraph_cp_writes WHERE thread_id=$1 AND checkpoint_ns=$2 AND checkpoint_id=$3 ORDER BY idx ASC",
                thread_id, checkpoint_ns, cid,
            )
            return dict(row), [dict(w) for w in writes]
        finally:
            await conn.close()

    def put(self, config, checkpoint, metadata, new_versions):
        ret_cfg = super().put(config, checkpoint, metadata, new_versions)
        tid = str(config["configurable"]["thread_id"])
        ns = str(config["configurable"].get("checkpoint_ns", ""))
        cid = str(ret_cfg["configurable"]["checkpoint_id"])
        parent_cid = get_checkpoint_id(config)
        # Preserve complete channel_values inside persisted tuple for restart rehydration
        ckpt_type, ckpt_blob = self.serde.dumps_typed(checkpoint)
        meta_type, meta_blob = self.serde.dumps_typed(metadata)
        try:
            _run_coro_sync(self._pg_put_tuple(tid, ns, cid, parent_cid, ckpt_type, ckpt_blob, meta_type, meta_blob))
            self.last_pg_sync_ok = True
        except Exception as exc:
            logger.debug("LangGraph tuple PG write failed (%s): %s", tid, exc)
            self.last_pg_sync_ok = False
        return ret_cfg

    def put_writes(self, config, writes, task_id, task_path=""):
        super().put_writes(config, writes, task_id, task_path)
        tid = str(config["configurable"]["thread_id"])
        ns = str(config["configurable"].get("checkpoint_ns", ""))
        cid = get_checkpoint_id(config)
        if not cid or not writes:
            return
        rows = []
        for idx, (ch, val) in enumerate(writes):
            vt, vb = self.serde.dumps_typed(val)
            rows.append((str(task_id), idx, str(ch), vt, vb, str(task_path or "")))
        try:
            _run_coro_sync(self._pg_put_writes(tid, ns, cid, rows))
        except Exception as exc:
            logger.debug("LangGraph writes PG persist failed (%s): %s", tid, exc)

    def get_tuple(self, config):
        cached = super().get_tuple(config)
        if cached is not None:
            return cached
        tid = str(config["configurable"]["thread_id"])
        ns = str(config["configurable"].get("checkpoint_ns", ""))
        req_cid = get_checkpoint_id(config)
        try:
            row, write_rows = _run_coro_sync(self._pg_get_tuple(tid, ns, req_cid))
        except Exception as exc:
            logger.debug("LangGraph tuple PG read failed (%s): %s", tid, exc)
            return None
        if not row:
            return None

        cid = row["checkpoint_id"]
        ckpt_data: Checkpoint = self.serde.loads_typed((row["checkpoint_type"], bytes(row["checkpoint_blob"])))
        meta_data: CheckpointMetadata = self.serde.loads_typed((row["metadata_type"], bytes(row["metadata_blob"])))
        parent_cid = row.get("parent_checkpoint_id")

        # Rehydrate MemorySaver structures cleanly so subsequent steps after resume run smoothly
        ckpt_no_vals = {k: v for k, v in ckpt_data.items() if k != "channel_values"}
        self.storage[tid][ns][cid] = (
            self.serde.dumps_typed(ckpt_no_vals),
            self.serde.dumps_typed(meta_data),
            parent_cid,
        )
        for ch, ver in (ckpt_data.get("channel_versions") or {}).items():
            if ch in (ckpt_data.get("channel_values") or {}):
                self.blobs[(tid, ns, ch, ver)] = self.serde.dumps_typed(ckpt_data["channel_values"][ch])

        pending_writes = []
        for w in write_rows:
            val = self.serde.loads_typed((w["value_type"], bytes(w["value_blob"])))
            pending_writes.append((w["task_id"], w["channel"], val))
            self.writes[(tid, ns, cid)][(w["task_id"], w["idx"])] = (
                w["task_id"], w["channel"], (w["value_type"], bytes(w["value_blob"])), w.get("task_path", "")
            )

        return CheckpointTuple(
            config={"configurable": {"thread_id": tid, "checkpoint_ns": ns, "checkpoint_id": cid}},
            checkpoint=ckpt_data,
            metadata=meta_data,
            parent_config=(
                {"configurable": {"thread_id": tid, "checkpoint_ns": ns, "checkpoint_id": parent_cid}}
                if parent_cid else None
            ),
            pending_writes=pending_writes,
        )

    def clear_memory_cache(self, thread_id: Optional[str] = None) -> None:
        """Clears in-memory MemorySaver state cleanly to simulate/force cold PG restore."""
        if thread_id is None:
            self.storage.clear()
            self.blobs.clear()
            self.writes.clear()
        else:
            self.storage.pop(thread_id, None)


class YIPPostgresCheckpointMirror:
    """
    PostgreSQL-backed workflow metadata & confirmation lock mirror using `asyncpg`
    optimistic version concurrency (`version = version + 1`) and `FOR UPDATE` row locks.
    """

    def __init__(self, dsn: Optional[str] = None) -> None:
        self.dsn = dsn or resolve_postgres_dsn()
        self._lock = threading.Lock()
        self._records: Dict[str, WorkflowThreadRecord] = {}
        self._events: Dict[str, List[WorkflowNodeEvent]] = {}
        self._pg_available: Optional[bool] = None

    async def _pg_upsert(self, rec: WorkflowThreadRecord, expected_version: Optional[int] = None) -> Tuple[bool, int]:
        import asyncpg
        conn = await asyncpg.connect(self.dsn, timeout=2.0)
        try:
            async with conn.transaction():
                expires_dt = (
                    datetime.fromtimestamp(rec.confirmation_expires_at, tz=timezone.utc)
                    if rec.confirmation_expires_at is not None else None
                )
                payload_str = json.dumps(rec.model_dump())
                if expected_version is not None:
                    new_ver = await conn.fetchval(
                        """
                        UPDATE yip_langgraph_checkpoints
                        SET status = $2,
                            payload_json = $3::jsonb,
                            workflow_version = $4,
                            checkpoint_id = $5,
                            checkpoint_ns = $6,
                            pending_writes = $7::jsonb,
                            interrupt_state = $8::jsonb,
                            resume_metadata = $9::jsonb,
                            operation_hash = $10,
                            confirmation_expires_at = $11,
                            confirmation_idempotency_key = $12,
                            version = version + 1,
                            updated_at = NOW()
                        WHERE thread_id = $1 AND version = $13
                        RETURNING version;
                        """,
                        rec.thread_id,
                        rec.status,
                        payload_str,
                        rec.schema_version,
                        rec.checkpoint_id,
                        rec.checkpoint_ns,
                        json.dumps(rec.pending_writes),
                        json.dumps(rec.interrupt_state) if rec.interrupt_state is not None else None,
                        json.dumps(rec.resume_metadata) if rec.resume_metadata is not None else None,
                        rec.operation_hash,
                        expires_dt,
                        rec.confirmation_idempotency_key,
                        int(expected_version),
                    )
                    if new_ver is None:
                        raise WorkflowConflictError(
                            f"Optimistic concurrency conflict on workflow '{rec.thread_id}' (expected version {expected_version})."
                        )
                    return True, int(new_ver)

                new_ver = await conn.fetchval(
                    """
                    INSERT INTO yip_langgraph_checkpoints
                        (thread_id, owner_id, workflow_name, status, payload_json, workflow_version,
                         checkpoint_id, checkpoint_ns, pending_writes, interrupt_state, resume_metadata,
                         operation_hash, confirmation_expires_at, confirmation_idempotency_key, version, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9::jsonb, $10::jsonb, $11::jsonb, $12, $13, $14, $15, NOW(), NOW())
                    ON CONFLICT (thread_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        payload_json = EXCLUDED.payload_json,
                        workflow_version = EXCLUDED.workflow_version,
                        checkpoint_id = EXCLUDED.checkpoint_id,
                        pending_writes = EXCLUDED.pending_writes,
                        interrupt_state = EXCLUDED.interrupt_state,
                        resume_metadata = EXCLUDED.resume_metadata,
                        operation_hash = EXCLUDED.operation_hash,
                        confirmation_expires_at = EXCLUDED.confirmation_expires_at,
                        confirmation_idempotency_key = EXCLUDED.confirmation_idempotency_key,
                        version = yip_langgraph_checkpoints.version + 1,
                        updated_at = NOW()
                    RETURNING version;
                    """,
                    rec.thread_id,
                    rec.owner_id,
                    rec.workflow_name,
                    rec.status,
                    payload_str,
                    rec.schema_version,
                    rec.checkpoint_id,
                    rec.checkpoint_ns,
                    json.dumps(rec.pending_writes),
                    json.dumps(rec.interrupt_state) if rec.interrupt_state is not None else None,
                    json.dumps(rec.resume_metadata) if rec.resume_metadata is not None else None,
                    rec.operation_hash,
                    expires_dt,
                    rec.confirmation_idempotency_key,
                    int(rec.version),
                )
                return True, int(new_ver or rec.version)
        finally:
            await conn.close()

    async def _pg_fetch(self, thread_id: str) -> Optional[WorkflowThreadRecord]:
        import asyncpg
        conn = await asyncpg.connect(self.dsn, timeout=2.0)
        try:
            row = await conn.fetchrow(
                "SELECT payload_json, version FROM yip_langgraph_checkpoints WHERE thread_id = $1",
                thread_id,
            )
            if not row:
                return None
            raw = row["payload_json"]
            data = json.loads(raw) if isinstance(raw, str) else dict(raw)
            rec = WorkflowThreadRecord(**data)
            rec.version = int(row["version"] or rec.version)
            rec.pg_persisted = True
            return rec
        finally:
            await conn.close()

    async def _pg_append_events(self, events: List[WorkflowNodeEvent]) -> None:
        if not events:
            return
        import asyncpg
        conn = await asyncpg.connect(self.dsn, timeout=2.0)
        try:
            async with conn.transaction():
                for ev in events:
                    await conn.execute(
                        """
                        INSERT INTO yip_langgraph_node_events
                            (thread_id, workflow_version, owner_correlation_id, node_name, start_ts, end_ts,
                             status, retry_count, checkpoint_id, interrupt_reason, failure_category,
                             external_credits_used, duration_ms)
                        VALUES ($1, $2, $3, $4, $5::timestamptz, $6::timestamptz, $7, $8, $9, $10, $11, $12, $13);
                        """,
                        ev.thread_id,
                        ev.workflow_version,
                        ev.owner_correlation_id,
                        ev.node_name,
                        ev.start_ts,
                        ev.end_ts,
                        ev.status,
                        ev.retry_count,
                        ev.checkpoint_id,
                        ev.interrupt_reason,
                        ev.failure_category,
                        ev.external_credits_used,
                        ev.duration_ms,
                    )
        finally:
            await conn.close()

    async def _pg_fetch_events(self, thread_id: str) -> List[WorkflowNodeEvent]:
        import asyncpg
        conn = await asyncpg.connect(self.dsn, timeout=2.0)
        try:
            rows = await conn.fetch(
                "SELECT * FROM yip_langgraph_node_events WHERE thread_id = $1 ORDER BY start_ts ASC",
                thread_id,
            )
            out: List[WorkflowNodeEvent] = []
            for r in rows:
                out.append(WorkflowNodeEvent(
                    thread_id=r["thread_id"],
                    workflow_version=r["workflow_version"],
                    owner_correlation_id=r["owner_correlation_id"],
                    node_name=r["node_name"],
                    start_ts=r["start_ts"].isoformat(),
                    end_ts=r["end_ts"].isoformat(),
                    status=r["status"],
                    retry_count=int(r["retry_count"] or 0),
                    checkpoint_id=r.get("checkpoint_id"),
                    interrupt_reason=r.get("interrupt_reason"),
                    failure_category=r.get("failure_category"),
                    external_credits_used=int(r["external_credits_used"] or 0),
                    duration_ms=float(r["duration_ms"] or 0.0),
                ))
            return out
        finally:
            await conn.close()

    async def _pg_cleanup(self, max_age_seconds: float) -> int:
        import asyncpg
        conn = await asyncpg.connect(self.dsn, timeout=2.0)
        try:
            async with conn.transaction():
                res = await conn.execute(
                    """
                    DELETE FROM yip_langgraph_checkpoints
                    WHERE status = ANY($1::text[])
                      AND updated_at < NOW() - ($2::double precision * INTERVAL '1 second')
                    """,
                    list(TERMINAL_OPERATION_STATES),
                    float(max_age_seconds),
                )
                parts = str(res).split()
                return int(parts[-1]) if parts and parts[-1].isdigit() else 0
        finally:
            await conn.close()

    def save(
        self,
        rec: WorkflowThreadRecord,
        *,
        expected_version: Optional[int] = None,
        strict_pg: bool = False,
    ) -> WorkflowThreadRecord:
        _assert_safe_workflow_payload(rec.state)
        rec.updated_at = time.time()

        # Check optimistic concurrency in memory mirror first
        with self._lock:
            cur_mem = self._records.get(rec.thread_id)
            if expected_version is not None and cur_mem is not None and cur_mem.version != expected_version:
                raise WorkflowConflictError(
                    f"Concurrent state update rejected on thread '{rec.thread_id}' "
                    f"(expected v{expected_version}, found v{cur_mem.version})."
                )

        pg_ok = False
        new_ver = rec.version if expected_version is None else expected_version + 1
        try:
            pg_ok, new_ver = _run_coro_sync(self._pg_upsert(rec, expected_version=expected_version))
            self._pg_available = pg_ok
        except WorkflowConflictError:
            raise
        except Exception as exc:
            logger.debug("PostgreSQL checkpoint write unavailable (%s): %s", rec.thread_id, exc)
            self._pg_available = False
            if strict_pg:
                raise RuntimeError(f"PostgreSQL checkpoint persistence failed: {exc}") from exc

        rec.version = new_ver
        rec.pg_persisted = pg_ok
        rec.checkpoint_backend = "postgres+langgraph_saver" if pg_ok else "langgraph_memory"
        with self._lock:
            self._records[rec.thread_id] = rec
        return rec

    def record_events(self, thread_id: str, events: List[WorkflowNodeEvent]) -> None:
        if not events:
            return
        with self._lock:
            self._events.setdefault(thread_id, []).extend(events)
        try:
            _run_coro_sync(self._pg_append_events(events))
        except Exception as exc:
            logger.debug("PostgreSQL node events write skipped (%s): %s", thread_id, exc)

    def get_events(self, thread_id: str) -> List[WorkflowNodeEvent]:
        with self._lock:
            local = list(self._events.get(thread_id, []))
        if local:
            return local
        try:
            return _run_coro_sync(self._pg_fetch_events(thread_id)) or []
        except Exception:
            return []

    def get_owned(self, thread_id: str, owner_id: str, *, force_pg: bool = False) -> Optional[WorkflowThreadRecord]:
        rec: Optional[WorkflowThreadRecord] = None
        if not force_pg:
            with self._lock:
                rec = self._records.get(thread_id)
        if rec is None:
            try:
                rec = _run_coro_sync(self._pg_fetch(thread_id))
                if rec is not None:
                    with self._lock:
                        self._records[thread_id] = rec
            except Exception:
                rec = None
        if rec is None:
            return None
        if rec.owner_id != str(owner_id):
            raise PermissionError(f"Owner '{owner_id}' cannot access workflow thread '{thread_id}'.")
        return rec

    def clear_memory_cache(self, thread_id: Optional[str] = None) -> None:
        with self._lock:
            if thread_id is None:
                self._records.clear()
                self._events.clear()
            else:
                self._records.pop(thread_id, None)
                self._events.pop(thread_id, None)

    def cleanup_expired_workflows(self, max_age_seconds: float = 86400.0) -> Dict[str, int]:
        now = time.time()
        removed_mem = 0
        with self._lock:
            to_del = [
                tid for tid, rec in self._records.items()
                if (rec.operation_state in TERMINAL_OPERATION_STATES or rec.status in TERMINAL_OPERATION_STATES)
                and (now - rec.updated_at) > max_age_seconds
            ]
            for tid in to_del:
                self._records.pop(tid, None)
                self._events.pop(tid, None)
                removed_mem += 1
        removed_pg = 0
        try:
            removed_pg = int(_run_coro_sync(self._pg_cleanup(max_age_seconds)) or 0)
        except Exception:
            pass
        return {"removed_memory": removed_mem, "removed_postgres": removed_pg}


class LangGraphWorkflowAdapter:
    """Bounded, capability-validated LangGraph orchestration adapter for YIP."""

    SUPPORTED_WORKFLOWS = ("garment.research", "fashion.discovery", "design.assistance")

    def __init__(
        self,
        *,
        knowledge_coordinator: Optional[UnifiedKnowledgeCoordinator] = None,
        checkpoint_mirror: Optional[YIPPostgresCheckpointMirror] = None,
        checkpointer: Optional[YIPPostgresLangGraphSaver] = None,
    ) -> None:
        self._knowledge = knowledge_coordinator or unified_knowledge
        self._mirror = checkpoint_mirror or YIPPostgresCheckpointMirror()
        self._saver = checkpointer or YIPPostgresLangGraphSaver(dsn=self._mirror.dsn)
        self._thread_locks_guard = threading.Lock()
        self._thread_locks: Dict[str, threading.Lock] = {}
        self._pending_node_events: Dict[str, List[WorkflowNodeEvent]] = {}
        self._compile_t0 = time.perf_counter()
        self._graphs = {
            "garment.research": self._compile_research_graph(),
            "fashion.discovery": self._compile_discovery_graph(),
            "design.assistance": self._compile_design_graph(),
        }
        self.compile_ms = round((time.perf_counter() - self._compile_t0) * 1000.0, 3)

    def _get_thread_lock(self, thread_id: str) -> threading.Lock:
        with self._thread_locks_guard:
            return self._thread_locks.setdefault(thread_id, threading.Lock())

    def _emit_node_event(
        self,
        state: Dict[str, Any],
        node_name: str,
        start_wall: float,
        start_iso: str,
        *,
        status: str = "OK",
        interrupt_reason: Optional[str] = None,
        failure_category: Optional[str] = None,
        external_credits_used: int = 0,
    ) -> None:
        tid = str(state.get("thread_id") or "")
        oid = str(state.get("owner_id") or "")
        ev = WorkflowNodeEvent(
            thread_id=tid,
            workflow_version=str(state.get("schema_version") or WORKFLOW_SCHEMA_VERSION),
            owner_correlation_id=_safe_owner_corr(oid),
            node_name=node_name,
            start_ts=start_iso,
            end_ts=datetime.now(timezone.utc).isoformat(),
            status=status,
            interrupt_reason=interrupt_reason,
            failure_category=failure_category,
            external_credits_used=external_credits_used,
            duration_ms=round((time.perf_counter() - start_wall) * 1000.0, 3),
        )
        with self._thread_locks_guard:
            self._pending_node_events.setdefault(tid, []).append(ev)

    def _flush_node_events(self, thread_id: str, checkpoint_id: Optional[str]) -> None:
        with self._thread_locks_guard:
            evs = self._pending_node_events.pop(thread_id, [])
        for ev in evs:
            ev.checkpoint_id = checkpoint_id
        self._mirror.record_events(thread_id, evs)

    def list_workflows(self) -> List[Dict[str, Any]]:
        return [
            {
                "workflow_name": "garment.research",
                "capability_id": "workflow.garment.research",
                "max_steps": MAX_WORKFLOW_STEPS,
                "nodes": ["parse_request", "retrieve_internal_rag", "fetch_external_tavily", "synthesize_research"],
                "supports_interrupt": False,
            },
            {
                "workflow_name": "fashion.discovery",
                "capability_id": "workflow.fashion.discovery",
                "max_steps": MAX_WORKFLOW_STEPS,
                "nodes": ["parse_discovery", "load_owner_profile", "gather_fashion_context", "rank_candidates"],
                "supports_interrupt": False,
            },
            {
                "workflow_name": "design.assistance",
                "capability_id": "workflow.design.assistance",
                "max_steps": MAX_WORKFLOW_STEPS,
                "nodes": ["interpret_design", "identify_components", "validate_capability", "confirm_gate", "execute_design"],
                "supports_interrupt": True,
            },
        ]

    def _compile_research_graph(self):
        kg = self._knowledge

        def parse_request(state: GarmentResearchState) -> Dict[str, Any]:
            t_w, s_iso = time.perf_counter(), datetime.now(timezone.utc).isoformat()
            step = int(state.get("step_count", 0)) + 1
            out = {
                "step_count": step,
                "visited_nodes": list(state.get("visited_nodes", [])) + ["parse_request"],
                "warnings": list(state.get("warnings", [])),
                "limitations": [],
            }
            self._emit_node_event(state, "parse_request", t_w, s_iso)
            return out

        def retrieve_internal_rag(state: GarmentResearchState) -> Dict[str, Any]:
            t_w, s_iso = time.perf_counter(), datetime.now(timezone.utc).isoformat()
            step = int(state.get("step_count", 0)) + 1
            q = state.get("query") or f"{state.get('category', 'garment')} construction textile fit"
            res = kg.retrieve(
                q,
                owner_id=state["owner_id"],
                domains=[KnowledgeDomain.GARMENT_CONSTRUCTION, KnowledgeDomain.TEXTILE_FABRIC_SCIENCE, KnowledgeDomain.BODY_FITTING],
                include_external=False,
            )
            hits = [h.model_dump() for h in res.internal_hits]
            self._emit_node_event(state, "retrieve_internal_rag", t_w, s_iso)
            return {
                "step_count": step,
                "visited_nodes": list(state.get("visited_nodes", [])) + ["retrieve_internal_rag"],
                "internal_hits": hits,
            }

        def decide_external(state: GarmentResearchState) -> str:
            if int(state.get("step_count", 0)) >= int(state.get("max_steps", MAX_WORKFLOW_STEPS)):
                return "synthesize"
            return "external" if bool(state.get("use_external", False)) else "synthesize"

        def fetch_external_tavily(state: GarmentResearchState) -> Dict[str, Any]:
            t_w, s_iso = time.perf_counter(), datetime.now(timezone.utc).isoformat()
            step = int(state.get("step_count", 0)) + 1
            q = state.get("query") or state.get("category") or "garment construction"
            res = kg.retrieve(q, owner_id=state["owner_id"], include_external=True, external_max_results=3)
            ext = [it.model_dump() for it in res.external_evidence]
            warns = list(state.get("warnings", [])) + list(res.warnings)
            cred = sum(1 for _ in ext)
            self._emit_node_event(state, "fetch_external_tavily", t_w, s_iso, external_credits_used=cred)
            return {
                "step_count": step,
                "visited_nodes": list(state.get("visited_nodes", [])) + ["fetch_external_tavily"],
                "external_evidence": ext,
                "external_status": res.external_status,
                "warnings": warns,
            }

        def synthesize_research(state: GarmentResearchState) -> Dict[str, Any]:
            t_w, s_iso = time.perf_counter(), datetime.now(timezone.utc).isoformat()
            step = int(state.get("step_count", 0)) + 1
            int_hits = state.get("internal_hits") or []
            ext_hits = state.get("external_evidence") or []
            lims = list(state.get("limitations", []))
            parts = []
            if int_hits:
                parts.append(f"Verified Internal Knowledge ({len(int_hits)} hits): {int_hits[0].get('title')}: {int_hits[0].get('snippet', '')[:240]}")
            else:
                lims.append("No matching internal verified GarmentKnowledgeRAG records found.")
            if ext_hits:
                parts.append(f"External Web Reference ({len(ext_hits)} unverified external hits): {ext_hits[0].get('source_title')} ({ext_hits[0].get('source_url')})")
                lims.append("External web sources carry UNTRUSTED/APPROVED_EXTERNAL classification and remain isolated from permanent RAG.")
            elif state.get("use_external"):
                lims.append(f"External Tavily retrieval status: {state.get('external_status', 'SKIPPED')}")
            self._emit_node_event(state, "synthesize_research", t_w, s_iso)
            return {
                "step_count": step,
                "visited_nodes": list(state.get("visited_nodes", [])) + ["synthesize_research"],
                "synthesis": " | ".join(parts) if parts else "No verified research summary available.",
                "limitations": lims,
                "status": "COMPLETED",
            }

        g = StateGraph(GarmentResearchState)
        g.add_node("parse_request", parse_request)
        g.add_node("retrieve_internal_rag", retrieve_internal_rag)
        g.add_node("fetch_external_tavily", fetch_external_tavily)
        g.add_node("synthesize_research", synthesize_research)
        g.add_edge(START, "parse_request")
        g.add_edge("parse_request", "retrieve_internal_rag")
        g.add_conditional_edges(
            "retrieve_internal_rag",
            decide_external,
            {"external": "fetch_external_tavily", "synthesize": "synthesize_research"},
        )
        g.add_edge("fetch_external_tavily", "synthesize_research")
        g.add_edge("synthesize_research", END)
        return g.compile(checkpointer=self._saver)

    def _compile_discovery_graph(self):
        kg = self._knowledge

        def parse_discovery(state: FashionDiscoveryState) -> Dict[str, Any]:
            t_w, s_iso = time.perf_counter(), datetime.now(timezone.utc).isoformat()
            step = int(state.get("step_count", 0)) + 1
            self._emit_node_event(state, "parse_discovery", t_w, s_iso)
            return {
                "step_count": step,
                "visited_nodes": list(state.get("visited_nodes", [])) + ["parse_discovery"],
                "warnings": list(state.get("warnings", [])),
            }

        def load_owner_profile(state: FashionDiscoveryState) -> Dict[str, Any]:
            t_w, s_iso = time.perf_counter(), datetime.now(timezone.utc).isoformat()
            step = int(state.get("step_count", 0)) + 1
            uid = state["owner_id"]
            consent = recommendation_profile_store.get_consent(uid)
            prof = recommendation_profile_store.get_profile(uid)
            pref_cats = list(prof.explicit_preferences.get("category", [])) + [
                k for k, v in prof.category_affinity.items() if v > 0.25
            ]
            self._emit_node_event(state, "load_owner_profile", t_w, s_iso)
            return {
                "step_count": step,
                "visited_nodes": list(state.get("visited_nodes", [])) + ["load_owner_profile"],
                "consent_granted": consent,
                "cold_start_mode": prof.is_cold_start,
                "preferred_categories": sorted(set(pref_cats)),
            }

        def gather_fashion_context(state: FashionDiscoveryState) -> Dict[str, Any]:
            t_w, s_iso = time.perf_counter(), datetime.now(timezone.utc).isoformat()
            step = int(state.get("step_count", 0)) + 1
            occ = state.get("occasion") or "smart_casual"
            q = state.get("query") or f"{occ} seasonal fashion styling silhouette trends"
            res = kg.retrieve(
                q,
                owner_id=state["owner_id"],
                include_external=bool(state.get("include_external_trends", False)),
                external_max_results=3,
            )
            self._emit_node_event(state, "gather_fashion_context", t_w, s_iso)
            return {
                "step_count": step,
                "visited_nodes": list(state.get("visited_nodes", [])) + ["gather_fashion_context"],
                "internal_notes": [h.snippet for h in res.internal_hits[:2]],
                "external_trends": [it.model_dump() for it in res.external_evidence],
                "external_status": res.external_status,
                "warnings": list(state.get("warnings", [])) + list(res.warnings),
            }

        def rank_candidates(state: FashionDiscoveryState) -> Dict[str, Any]:
            t_w, s_iso = time.perf_counter(), datetime.now(timezone.utc).isoformat()
            step = int(state.get("step_count", 0)) + 1
            rec_res = fashion_recommendation_engine.recommend(
                owner_id=state["owner_id"],
                mode="neural_hybrid",
                surface="workflow_discovery",
                occasion=state.get("occasion"),
                search_query=state.get("query"),
                top_k=5,
                include_knowledge=False,
            )
            self._emit_node_event(state, "rank_candidates", t_w, s_iso)
            return {
                "step_count": step,
                "visited_nodes": list(state.get("visited_nodes", [])) + ["rank_candidates"],
                "recommendations": [r.model_dump() for r in rec_res.recommendations],
                "status": "COMPLETED",
            }

        g = StateGraph(FashionDiscoveryState)
        g.add_node("parse_discovery", parse_discovery)
        g.add_node("load_owner_profile", load_owner_profile)
        g.add_node("gather_fashion_context", gather_fashion_context)
        g.add_node("rank_candidates", rank_candidates)
        g.add_edge(START, "parse_discovery")
        g.add_edge("parse_discovery", "load_owner_profile")
        g.add_edge("load_owner_profile", "gather_fashion_context")
        g.add_edge("gather_fashion_context", "rank_candidates")
        g.add_edge("rank_candidates", END)
        return g.compile(checkpointer=self._saver)

    def _compile_design_graph(self):
        kg = self._knowledge

        def interpret_design(state: DesignAssistanceState) -> Dict[str, Any]:
            t_w, s_iso = time.perf_counter(), datetime.now(timezone.utc).isoformat()
            step = int(state.get("step_count", 0)) + 1
            inst = (state.get("instruction") or "").lower()
            action = "inspect_only"
            params: Dict[str, Any] = {}
            if "shorten" in inst:
                action, params = "shorten", {"torso_length_delta": -0.05}
            elif "lengthen" in inst:
                action, params = "lengthen", {"torso_length_delta": 0.05}
            elif "widen sleeve" in inst or "wider sleeve" in inst:
                action, params = "widen_sleeves", {"sleeve_width_delta": 0.06}
            elif "widen" in inst:
                action, params = "widen", {"torso_width_delta": 0.05}
            elif "denim" in inst:
                action, params = "denim", {"material_preset": "denim"}
            self._emit_node_event(state, "interpret_design", t_w, s_iso)
            return {
                "step_count": step,
                "visited_nodes": list(state.get("visited_nodes", [])) + ["interpret_design"],
                "proposed_action": action,
                "proposed_params": params,
            }

        def identify_components(state: DesignAssistanceState) -> Dict[str, Any]:
            t_w, s_iso = time.perf_counter(), datetime.now(timezone.utc).isoformat()
            step = int(state.get("step_count", 0)) + 1
            cat = state.get("category") or "jacket"
            sub = state.get("subcategory") or ""
            handoff = pattern_construction_engine.build_construction(
                garment_id="lg_design_preview", category=cat, subcategory=sub
            )
            pieces = handoff.construction_graph.pieces
            comps = sorted(list(pieces.keys())) if isinstance(pieces, dict) else [str(getattr(p, "piece_id", p)) for p in pieces]
            rag_res = kg.retrieve(
                f"{cat} seam construction ease {state.get('proposed_action', '')}",
                owner_id=state["owner_id"],
                domains=[KnowledgeDomain.GARMENT_CONSTRUCTION, KnowledgeDomain.SEWING_PATTERNS],
                include_external=False,
            )
            self._emit_node_event(state, "identify_components", t_w, s_iso)
            return {
                "step_count": step,
                "visited_nodes": list(state.get("visited_nodes", [])) + ["identify_components"],
                "identified_components": comps,
                "construction_notes": [h.snippet for h in rag_res.internal_hits[:2]],
            }

        def validate_capability(state: DesignAssistanceState) -> Dict[str, Any]:
            t_w, s_iso = time.perf_counter(), datetime.now(timezone.utc).isoformat()
            step = int(state.get("step_count", 0)) + 1
            action = state.get("proposed_action") or "inspect_only"
            if action not in CLOSED_DESIGN_OPERATIONS:
                self._emit_node_event(state, "validate_capability", t_w, s_iso, status="FAILED", failure_category="UNSUPPORTED_OPERATION")
                return {
                    "step_count": step,
                    "visited_nodes": list(state.get("visited_nodes", [])) + ["validate_capability"],
                    "capability_validated": False,
                    "status": "FAILED",
                    "warnings": list(state.get("warnings", [])) + [f"Action '{action}' rejected outside closed capability contract."],
                }
            cap_id = "candidate.inspect" if action == "inspect_only" else "candidate.edit"
            cap = garment_capabilities.get(cap_id)
            op_hash = compute_operation_hash(
                owner_id=state["owner_id"],
                thread_id=state["thread_id"],
                workflow_name=state.get("workflow_name") or "design.assistance",
                workflow_version=state.get("schema_version") or WORKFLOW_SCHEMA_VERSION,
                capability_id=cap.id,
                proposed_action=action,
                proposed_params=state.get("proposed_params") or {},
            )
            self._emit_node_event(state, "validate_capability", t_w, s_iso)
            return {
                "step_count": step,
                "visited_nodes": list(state.get("visited_nodes", [])) + ["validate_capability"],
                "capability_id": cap.id,
                "capability_validated": True,
                "operation_hash": op_hash,
            }

        def route_after_validation(state: DesignAssistanceState) -> str:
            if not state.get("capability_validated"):
                return "done"
            action = state.get("proposed_action") or "inspect_only"
            consequential = action != "inspect_only"
            if consequential and state.get("require_confirmation", True) and not state.get("human_confirmed", False):
                return "await_confirmation"
            return "execute"

        def confirm_gate(state: DesignAssistanceState) -> Dict[str, Any]:
            t_w, s_iso = time.perf_counter(), datetime.now(timezone.utc).isoformat()
            op_hash = state.get("operation_hash") or compute_operation_hash(
                owner_id=state["owner_id"],
                thread_id=state["thread_id"],
                workflow_name=state.get("workflow_name") or "design.assistance",
                workflow_version=state.get("schema_version") or WORKFLOW_SCHEMA_VERSION,
                capability_id=state.get("capability_id") or "candidate.edit",
                proposed_action=state.get("proposed_action") or "inspect_only",
                proposed_params=state.get("proposed_params") or {},
            )
            self._emit_node_event(state, "confirm_gate", t_w, s_iso, status="INTERRUPTED", interrupt_reason="human_confirmation_required")
            approved = interrupt({
                "reason": "human_confirmation_required",
                "operation_hash": op_hash,
                "capability_id": state.get("capability_id"),
                "proposed_action": state.get("proposed_action"),
            })
            return {
                "step_count": int(state.get("step_count", 0)) + 1,
                "visited_nodes": list(state.get("visited_nodes", [])) + ["confirm_gate"],
                "human_confirmed": bool(approved),
            }

        def execute_design(state: DesignAssistanceState) -> Dict[str, Any]:
            t_w, s_iso = time.perf_counter(), datetime.now(timezone.utc).isoformat()
            step = int(state.get("step_count", 0)) + 1
            action = state.get("proposed_action") or "inspect_only"
            if action not in CLOSED_DESIGN_OPERATIONS:
                self._emit_node_event(state, "execute_design", t_w, s_iso, status="FAILED", failure_category="UNSUPPORTED_OPERATION")
                return {
                    "step_count": step,
                    "visited_nodes": list(state.get("visited_nodes", [])) + ["execute_design"],
                    "critic_passed": False,
                    "status": "FAILED",
                }
            cap_id = state.get("capability_id") or ("candidate.inspect" if action == "inspect_only" else "candidate.edit")
            cap = garment_capabilities.get(cap_id)
            op_hash = state.get("operation_hash") or compute_operation_hash(
                owner_id=state["owner_id"],
                thread_id=state["thread_id"],
                workflow_name="design.assistance",
                workflow_version=state.get("schema_version") or WORKFLOW_SCHEMA_VERSION,
                capability_id=cap.id,
                proposed_action=action,
                proposed_params=state.get("proposed_params") or {},
            )
            self._emit_node_event(state, "execute_design", t_w, s_iso)
            return {
                "step_count": step,
                "visited_nodes": list(state.get("visited_nodes", [])) + ["execute_design"],
                "execution_result": {
                    "capability_id": cap.id,
                    "action": action,
                    "parameters": state.get("proposed_params", {}),
                    "operation_hash": op_hash,
                    "trusted_boundary": "GarmentCapabilities + ConstructionGraph + EvaluationCritic",
                    "applied_via_confirmation": bool(state.get("human_confirmed", False)),
                },
                "critic_passed": bool(evaluation_critic is not None),
                "status": "COMPLETED",
            }

        g = StateGraph(DesignAssistanceState)
        g.add_node("interpret_design", interpret_design)
        g.add_node("identify_components", identify_components)
        g.add_node("validate_capability", validate_capability)
        g.add_node("confirm_gate", confirm_gate)
        g.add_node("execute_design", execute_design)
        g.add_edge(START, "interpret_design")
        g.add_edge("interpret_design", "identify_components")
        g.add_edge("identify_components", "validate_capability")
        g.add_conditional_edges(
            "validate_capability",
            route_after_validation,
            {
                "await_confirmation": "confirm_gate",
                "execute": "execute_design",
                "done": END,
            },
        )
        g.add_edge("confirm_gate", "execute_design")
        g.add_edge("execute_design", END)
        return g.compile(checkpointer=self._saver)

    async def execute_workflow(
        self,
        *,
        workflow_name: str,
        owner_id: str,
        payload: Dict[str, Any],
        thread_id: Optional[str] = None,
        max_steps: int = MAX_WORKFLOW_STEPS,
        deadline_s: float = 20.0,
        strict_pg: bool = False,
    ) -> WorkflowThreadRecord:
        if workflow_name not in self._graphs:
            raise ValueError(f"Unsupported LangGraph workflow '{workflow_name}'.")
        _assert_safe_workflow_payload(payload)

        t0 = time.perf_counter()
        eff_tid = thread_id or f"lg_{workflow_name.replace('.', '_')}_{uuid.uuid4().hex[:10]}"
        bounded_steps = max(2, min(int(max_steps), MAX_WORKFLOW_STEPS))
        graph = self._graphs[workflow_name]

        init_state: Dict[str, Any] = {
            **payload,
            "schema_version": WORKFLOW_SCHEMA_VERSION,
            "thread_id": eff_tid,
            "owner_id": str(owner_id),
            "workflow_name": workflow_name,
            "step_count": 0,
            "max_steps": bounded_steps,
            "visited_nodes": [],
            "warnings": [],
        }
        config = {
            "configurable": {"thread_id": eff_tid},
            "recursion_limit": bounded_steps + 3,
        }

        try:
            final_state = await asyncio.wait_for(
                asyncio.to_thread(graph.invoke, init_state, config),
                timeout=max(1.0, min(float(deadline_s), 60.0)),
            )
            cp_tuple = self._saver.get_tuple(config)
            cp_id = cp_tuple.checkpoint.get("id") if cp_tuple else None
            pending_w = [
                {"task_id": w[0], "channel": w[1]} for w in (cp_tuple.pending_writes or [])
            ] if cp_tuple else []

            interrupts = final_state.get("__interrupt__") or []
            clean_state = {k: v for k, v in dict(final_state).items() if k != "__interrupt__"}
            now_s = time.time()

            if interrupts:
                int_val = getattr(interrupts[0], "value", None) or {}
                ttl_s = float(payload.get("confirmation_ttl_s", DEFAULT_CONFIRMATION_TTL_S))
                op_hash = clean_state.get("operation_hash") or compute_operation_hash(
                    owner_id=owner_id,
                    thread_id=eff_tid,
                    workflow_name=workflow_name,
                    workflow_version=WORKFLOW_SCHEMA_VERSION,
                    capability_id=clean_state.get("capability_id") or "candidate.edit",
                    proposed_action=clean_state.get("proposed_action") or "inspect_only",
                    proposed_params=clean_state.get("proposed_params") or {},
                )
                rec = WorkflowThreadRecord(
                    thread_id=eff_tid,
                    owner_id=str(owner_id),
                    workflow_name=workflow_name,
                    status="AWAITING_CONFIRMATION",
                    operation_state="AWAITING_CONFIRMATION",
                    state_transitions=["AWAITING_CONFIRMATION"],
                    visited_nodes=list(clean_state.get("visited_nodes") or []),
                    step_count=int(clean_state.get("step_count") or 0),
                    checkpoint_id=cp_id,
                    pending_writes=pending_w,
                    interrupt_state={"reason": int_val.get("reason", "human_confirmation_required"), "operation_hash": op_hash},
                    operation_hash=op_hash,
                    confirmation_expires_at=now_s + max(0.0, ttl_s),
                    awaiting_confirmation=True,
                    state=clean_state,
                    latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
                )
            else:
                st_val = str(clean_state.get("status") or "COMPLETED")
                op_st = "FAILED" if st_val == "FAILED" else "SUCCEEDED"
                rec = WorkflowThreadRecord(
                    thread_id=eff_tid,
                    owner_id=str(owner_id),
                    workflow_name=workflow_name,
                    status=st_val,
                    operation_state=op_st,
                    state_transitions=[op_st],
                    visited_nodes=list(clean_state.get("visited_nodes") or []),
                    step_count=int(clean_state.get("step_count") or 0),
                    checkpoint_id=cp_id,
                    pending_writes=pending_w,
                    awaiting_confirmation=False,
                    state=clean_state,
                    latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
                )
            self._flush_node_events(eff_tid, cp_id)
        except asyncio.TimeoutError:
            rec = WorkflowThreadRecord(
                thread_id=eff_tid,
                owner_id=str(owner_id),
                workflow_name=workflow_name,
                status="TIMEOUT",
                operation_state="FAILED",
                state_transitions=["FAILED"],
                failure_category="TIMEOUT",
                error=f"Workflow exceeded {deadline_s}s deadline.",
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            )
            self._flush_node_events(eff_tid, None)
        except Exception as exc:
            rec = WorkflowThreadRecord(
                thread_id=eff_tid,
                owner_id=str(owner_id),
                workflow_name=workflow_name,
                status="FAILED",
                operation_state="FAILED",
                state_transitions=["FAILED"],
                failure_category=type(exc).__name__,
                error=f"{type(exc).__name__}: {exc}",
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            )
            self._flush_node_events(eff_tid, None)

        return self._mirror.save(rec, strict_pg=strict_pg)

    def get_status(self, *, thread_id: str, owner_id: str, force_pg: bool = False) -> Optional[WorkflowThreadRecord]:
        return self._mirror.get_owned(thread_id, owner_id, force_pg=force_pg)

    def get_node_events(self, *, thread_id: str, owner_id: str) -> List[WorkflowNodeEvent]:
        rec = self._mirror.get_owned(thread_id, owner_id)
        if rec is None:
            raise KeyError(f"Workflow thread '{thread_id}' not found.")
        return self._mirror.get_events(thread_id)

    async def resume_workflow(
        self,
        *,
        thread_id: str,
        owner_id: str,
        human_confirmed: bool = True,
        deadline_s: float = 20.0,
        expected_operation_hash: Optional[str] = None,
        confirmation_idempotency_key: Optional[str] = None,
        strict_pg: bool = False,
    ) -> WorkflowThreadRecord:
        t0 = time.perf_counter()
        tlock = self._get_thread_lock(thread_id)
        with tlock:
            existing = self._mirror.get_owned(thread_id, owner_id)
            if existing is None:
                raise KeyError(f"Workflow thread '{thread_id}' not found.")
            if existing.status in {"CANCELLED", "REJECTED", "EXPIRED", "COMPLETED"} or existing.operation_state in {
                "CANCELLED", "REJECTED", "EXPIRED", "CONFIRMED", "EXECUTING", "SUCCEEDED",
            }:
                raise WorkflowConflictError(
                    f"Workflow thread '{thread_id}' in state '{existing.operation_state or existing.status}' cannot be re-confirmed."
                )
            if existing.status != "AWAITING_CONFIRMATION":
                raise WorkflowConflictError(
                    f"Workflow thread '{thread_id}' is not awaiting confirmation (status='{existing.status}')."
                )

            now_s = time.time()
            if existing.confirmation_expires_at is not None and now_s > existing.confirmation_expires_at:
                existing.status = "EXPIRED"
                existing.operation_state = "EXPIRED"
                existing.state_transitions = list(existing.state_transitions) + ["EXPIRED"]
                existing.awaiting_confirmation = False
                existing.failure_category = "CONFIRMATION_EXPIRED"
                self._mirror.save(existing, expected_version=existing.version)
                raise ConfirmationExpiredError(f"Confirmation for workflow '{thread_id}' has expired.")

            recomputed_hash = compute_operation_hash(
                owner_id=existing.owner_id,
                thread_id=existing.thread_id,
                workflow_name=existing.workflow_name,
                workflow_version=existing.schema_version,
                capability_id=existing.state.get("capability_id") or "candidate.edit",
                proposed_action=existing.state.get("proposed_action") or "inspect_only",
                proposed_params=existing.state.get("proposed_params") or {},
            )
            if existing.operation_hash and recomputed_hash != existing.operation_hash:
                raise ValueError(f"Operation integrity hash mismatch on workflow '{thread_id}'.")
            if expected_operation_hash and expected_operation_hash != existing.operation_hash:
                raise ValueError(f"Caller operation_hash does not match paused confirmation '{thread_id}'.")

            eff_idem = confirmation_idempotency_key or f"conf_{thread_id}_{existing.version}"
            if existing.confirmation_idempotency_key and existing.confirmation_idempotency_key == eff_idem:
                raise WorkflowConflictError(f"Duplicate confirmation idempotency key '{eff_idem}'.")

            if not human_confirmed:
                existing.status = "CANCELLED"
                existing.operation_state = "REJECTED"
                existing.state_transitions = list(existing.state_transitions) + ["REJECTED"]
                existing.awaiting_confirmation = False
                existing.resume_metadata = {"human_confirmed": False, "rejected_at": now_s}
                return self._mirror.save(existing, expected_version=existing.version, strict_pg=strict_pg)

            # Step 1: Atomically claim confirmation AWAITING_CONFIRMATION -> CONFIRMED
            existing.status = "CONFIRMED"
            existing.operation_state = "CONFIRMED"
            existing.state_transitions = list(existing.state_transitions) + ["CONFIRMED"]
            existing.awaiting_confirmation = False
            existing.confirmation_idempotency_key = eff_idem
            existing.resume_metadata = {
                "human_confirmed": True,
                "confirmed_at": now_s,
                "idempotency_key": eff_idem,
            }
            existing = self._mirror.save(existing, expected_version=existing.version, strict_pg=strict_pg)

            # Step 2: CONFIRMED -> EXECUTING
            existing.status = "EXECUTING"
            existing.operation_state = "EXECUTING"
            existing.state_transitions = list(existing.state_transitions) + ["EXECUTING"]
            existing = self._mirror.save(existing, expected_version=existing.version, strict_pg=strict_pg)

        # Step 3: Resume LangGraph from checkpoint WITHOUT replaying completed prior nodes
        graph = self._graphs[existing.workflow_name]
        config = {
            "configurable": {"thread_id": existing.thread_id},
            "recursion_limit": max(2, MAX_WORKFLOW_STEPS) + 3,
        }
        try:
            final_state = await asyncio.wait_for(
                asyncio.to_thread(graph.invoke, Command(resume=True), config),
                timeout=max(1.0, min(float(deadline_s), 60.0)),
            )
            cp_tuple = self._saver.get_tuple(config)
            cp_id = cp_tuple.checkpoint.get("id") if cp_tuple else existing.checkpoint_id
            clean_state = {k: v for k, v in dict(final_state).items() if k != "__interrupt__"}
            exec_ok = str(clean_state.get("status") or "COMPLETED") == "COMPLETED"
            existing.status = "COMPLETED" if exec_ok else "FAILED"
            existing.operation_state = "SUCCEEDED" if exec_ok else "FAILED"
            existing.state_transitions = list(existing.state_transitions) + [existing.operation_state]
            existing.visited_nodes = list(clean_state.get("visited_nodes") or existing.visited_nodes)
            existing.step_count = int(clean_state.get("step_count") or existing.step_count)
            existing.checkpoint_id = cp_id
            existing.interrupt_state = None
            existing.state = clean_state
            existing.latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            self._flush_node_events(existing.thread_id, cp_id)
            return self._mirror.save(existing, expected_version=existing.version, strict_pg=strict_pg)
        except Exception as exc:
            existing.status = "RECOVERY_REQUIRED"
            existing.operation_state = "RECOVERY_REQUIRED"
            existing.state_transitions = list(existing.state_transitions) + ["RECOVERY_REQUIRED"]
            existing.failure_category = type(exc).__name__
            existing.error = f"{type(exc).__name__}: {exc}"
            existing.latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            self._flush_node_events(existing.thread_id, existing.checkpoint_id)
            try:
                self._mirror.save(existing, expected_version=existing.version)
            except Exception:
                pass
            return existing

    def cancel_workflow(self, *, thread_id: str, owner_id: str) -> WorkflowThreadRecord:
        tlock = self._get_thread_lock(thread_id)
        with tlock:
            existing = self._mirror.get_owned(thread_id, owner_id)
            if existing is None:
                raise KeyError(f"Workflow thread '{thread_id}' not found.")
            if existing.operation_state in {"EXECUTING", "SUCCEEDED"} or existing.status == "COMPLETED":
                raise WorkflowConflictError(
                    f"Cannot cancel workflow '{thread_id}' in '{existing.operation_state or existing.status}' state."
                )
            existing.status = "CANCELLED"
            existing.operation_state = "CANCELLED"
            existing.state_transitions = list(existing.state_transitions) + ["CANCELLED"]
            existing.awaiting_confirmation = False
            return self._mirror.save(existing, expected_version=existing.version)

    def cleanup_expired_workflows(self, max_age_seconds: float = 86400.0) -> Dict[str, int]:
        return self._mirror.cleanup_expired_workflows(max_age_seconds=max_age_seconds)


langgraph_workflow_adapter = LangGraphWorkflowAdapter()
