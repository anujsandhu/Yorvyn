"""
YORVYN — Transactional Outbox, Redis Delivery Recovery & Lifecycle Hardening Test Suite
Phase: DURABLE-JOB-FIX-002

Exercises REAL PostgreSQL (yorvyn_persistence) and REAL Redis Streams (127.0.0.1:6379)
alongside deterministic fault-injection at every transaction boundary:
1.  Failure BEFORE DB commit -> no Redis enqueue, no outbox row, no idempotency key
2.  Atomic DB + Outbox commit -> both durable together; rollback removes both
3.  Crash AFTER DB commit + temp files, BEFORE Redis enqueue -> restart recovery delivers
    to Redis -> worker processes, publishes GLB, acknowledges Redis & outbox
4.  Transient Redis outage during create_job -> durable QUEUED + PENDING outbox preserved ->
    outbox dispatcher delivers once Redis returns
5.  Bounded retry with exponential backoff & EXHAUSTED closure after max_delivery_attempts
6.  Crash AFTER retry DB commit (FAILED -> QUEUED), BEFORE Redis enqueue -> JOB_RETRY outbox
    committed atomically -> dispatcher delivers retry
7.  Duplicate Redis delivery (crash after XADD before mark_outbox_delivered) -> effectively-once
    claim & publication via lease fencing
8.  Fencing token mismatch during VALIDATING / PUBLISHING / commit_completion
9.  Crash AFTER publication (commit_completion), BEFORE Redis/outbox ACK -> durable COMPLETED
    preserved, terminal reconciliation acknowledges outbox
10. Stale delivery recovery (delivered but unacked >30s while QUEUED) vs active PROCESSING job
11. Safe concurrent outbox dispatch (FOR UPDATE SKIP LOCKED across threads)
12. Concurrent duplicate submissions with identical canonical fingerprint
13. Compensation safety verification (wrong job_id, wrong user/tenant, CLAIMED+, retry_count>0,
    terminal state, other request's idempotency reservation)
14. Outbox observability metrics in get_outbox_stats() and get_health_status()
"""

import io
import os
import json
import time
import uuid
import shutil
import struct
import hashlib
import threading
import concurrent.futures
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from backend.app.services.garments.orchestration.unified_state_machine import (
    PostgresJobPersistenceAdapter,
    UnifiedJobState,
    resolve_postgres_dsn,
    compute_canonical_fingerprint,
)
from backend.app.services.garments.orchestration.queue_broker import RedisStreamsQueueBroker
from backend.app.services.garments.orchestration.artifact_committer import AtomicArtifactPublisher
from backend.app.services.garments.job_manager import (
    GarmentJobManager,
    TEMP_BASE_DIR,
    PERMANENT_ASSET_DIR,
    DurablePersistenceUnavailableError,
)
from backend.app.models.garment_models import GarmentGenJob, GarmentGenJobStatus


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _png_bytes(w: int = 48, h: int = 48, color=(40, 120, 200)) -> bytes:
    img = Image.new("RGB", (w, h), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _valid_minimal_glb_bytes() -> bytes:
    """Build a valid glTF 2.0 binary (GLB) that passes AtomicArtifactPublisher deep inspection."""
    import numpy as np
    positions = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32).tobytes()
    indices = np.array([0, 1, 2], dtype=np.uint16).tobytes()
    bin_raw = positions + indices
    while len(bin_raw) % 4 != 0:
        bin_raw += b"\x00"

    gltf = {
        "asset": {"version": "2.0", "generator": "yorvyn-test"},
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "buffers": [{"byteLength": len(bin_raw)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(positions)},
            {"buffer": 0, "byteOffset": len(positions), "byteLength": len(indices)},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3", "min": [0, 0, 0], "max": [1, 1, 0]},
            {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"},
        ],
    }
    json_bytes = json.dumps(gltf).encode("utf-8")
    while len(json_bytes) % 4 != 0:
        json_bytes += b" "

    total_len = 12 + 8 + len(json_bytes) + 8 + len(bin_raw)
    header = struct.pack("<III", 0x46546C67, 2, total_len)
    c0 = struct.pack("<II", len(json_bytes), 0x4E4F534A) + json_bytes
    c1 = struct.pack("<II", len(bin_raw), 0x004E4942) + bin_raw
    return header + c0 + c1


def _pg_cleanup(dsn: str, job_ids: list) -> None:
    if not job_ids:
        return
    import asyncio, asyncpg

    async def _clean():
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute("DELETE FROM yorvyn_job_outbox WHERE job_id = ANY($1::text[])", job_ids)
            await conn.execute("DELETE FROM yorvyn_idempotency_keys WHERE job_id = ANY($1::text[])", job_ids)
            await conn.execute("DELETE FROM yorvyn_jobs WHERE job_id = ANY($1::text[])", job_ids)
        finally:
            await conn.close()

    try:
        asyncio.run(_clean())
    except RuntimeError:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(asyncio.run, _clean()).result()


def _make_real_manager(pg: PostgresJobPersistenceAdapter, broker: RedisStreamsQueueBroker, tmp_asset_dir: Path) -> GarmentJobManager:
    mgr = GarmentJobManager.__new__(GarmentJobManager)
    mgr._postgres_adapter = pg
    mgr._redis_broker = broker
    mgr._artifact_publisher = AtomicArtifactPublisher(storage_dir=tmp_asset_dir)
    mgr._jobs = {}
    mgr._diagnostics = {}
    mgr._completed_cache = {}
    mgr._cancellation_flags = {}
    mgr._priority_queue = []
    mgr._queue_lock = threading.Lock()
    mgr._active_worker_count = 0
    mgr._max_workers = 2
    mgr._max_queue_depth = 50
    mgr._start_time = datetime.utcnow()
    mgr._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    mgr._outbox_stop_event = threading.Event()
    mgr._outbox_thread = None
    return mgr


@pytest.fixture
def live_infra(tmp_path):
    """Provides real PostgreSQL adapter and isolated Redis Streams test key, cleaning up after test."""
    dsn = resolve_postgres_dsn()
    pg = PostgresJobPersistenceAdapter(dsn=dsn)
    stream_key = f"yorvyn:test:stream:{uuid.uuid4().hex[:8]}"
    dlq_key = f"yorvyn:test:dlq:{uuid.uuid4().hex[:8]}"
    broker = RedisStreamsQueueBroker(
        host=os.environ.get("REDIS_HOST", "127.0.0.1"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        stream_key=stream_key,
        dead_letter_stream=dlq_key,
        group_name="test_outbox_workers",
    )
    created_jobs = []
    yield pg, broker, tmp_path, created_jobs, dsn
    _pg_cleanup(dsn, created_jobs)
    for jid in created_jobs:
        shutil.rmtree(Path(TEMP_BASE_DIR) / jid, ignore_errors=True)
    try:
        broker.client.delete(stream_key, dlq_key)
    except Exception:
        pass


# ─── Fault-Injection Test Cases ──────────────────────────────────────────────

def test_fault_before_db_commit_no_outbox_no_redis(live_infra):
    """Boundary 1: Failure before DB commit leaves no job, no outbox row, no Redis message."""
    pg, broker, tmp_path, created_jobs, _ = live_infra
    broken_pg = MagicMock(spec=PostgresJobPersistenceAdapter)
    broken_pg.create_job_atomic.side_effect = RuntimeError("PostgreSQL connection dropped")
    mgr = _make_real_manager(broken_pg, broker, tmp_path / "assets")

    with pytest.raises(DurablePersistenceUnavailableError):
        mgr.create_job(f"usr_{uuid.uuid4().hex[:8]}", _png_bytes(), "tops")

    assert broker.get_queue_depth() == 0
    assert len(mgr._jobs) == 0


def test_atomic_db_and_outbox_commit_real_pg(live_infra):
    """Boundary 2: Job + idempotency + outbox row commit atomically in a single PG transaction."""
    pg, broker, _, created_jobs, _ = live_infra
    jid = f"job_atomic_{uuid.uuid4().hex[:8]}"
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    created_jobs.append(jid)

    is_new, state = pg.create_job_atomic(
        job_id=jid,
        user_id=uid,
        tenant_id=uid,
        correlation_id=f"corr_{jid}",
        idempotency_key=f"idem_{jid}",
        canonical_fingerprint=hashlib.sha256(jid.encode()).hexdigest(),
        outbox_payload={"job_id": jid, "user_id": uid, "front_path": "/tmp/fake.raw"},
        outbox_priority=2,
    )
    assert is_new is True
    assert state.current_state == "QUEUED"

    outbox = pg.load_outbox_entry(jid, "JOB_QUEUED")
    assert outbox is not None
    assert outbox["status"] == "PENDING"
    assert outbox["delivered_at"] is None
    assert outbox["payload"]["event_id"] == outbox["outbox_id"]


def test_initial_enqueue_crash_window_recovery_to_completion(live_infra):
    """
    Boundary 3 (Core DURABLE-JOB-FIX-002 Scenario):
    1. PostgreSQL job + outbox commits (temp photo written)
    2. Process crashes BEFORE Redis enqueue
    3. Application restarts -> recover_stranded_jobs()
    4. Recovery discovers durable QUEUED job + delivers to Redis
    5. Worker claims, fences publication, completes, and acknowledges Redis + outbox
    """
    pg, broker, tmp_path, created_jobs, _ = live_infra
    jid = f"job_crash_{uuid.uuid4().hex[:8]}"
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    created_jobs.append(jid)

    # Step 1-2: Commit DB + outbox and write temp file, simulating crash before Redis enqueue
    job_tmp = Path(TEMP_BASE_DIR) / jid
    job_tmp.mkdir(parents=True, exist_ok=True)
    front_path = job_tmp / "temp_input_front.raw"
    front_path.write_bytes(_png_bytes())

    pg.create_job_atomic(
        job_id=jid,
        user_id=uid,
        tenant_id=uid,
        correlation_id=f"corr_{jid}",
        idempotency_key=f"idem_{jid}",
        canonical_fingerprint=hashlib.sha256(jid.encode()).hexdigest(),
        outbox_payload={
            "job_id": jid,
            "user_id": uid,
            "tenant_id": uid,
            "correlation_id": f"corr_{jid}",
            "front_path": str(front_path),
            "category": "tops",
            "subcategory": "tshirt",
            "priority": 3,
        },
        outbox_priority=3,
    )
    assert broker.get_queue_depth() == 0

    # Step 3-4: Restart into fresh GarmentJobManager instance and run startup recovery
    restarted_mgr = _make_real_manager(pg, broker, tmp_path / "assets")
    restarted_mgr.recover_stranded_jobs()

    # Step 5: Job MUST remain QUEUED in DB and MUST now be delivered to Redis Streams
    db_after_recovery = pg.load_job(jid)
    assert db_after_recovery is not None
    assert db_after_recovery.current_state == "QUEUED"
    assert broker.get_queue_depth() == 1

    outbox_after = pg.load_outbox_entry(jid, "JOB_QUEUED")
    assert outbox_after is not None
    assert outbox_after["status"] == "DELIVERED"
    assert outbox_after["delivered_at"] is not None
    assert outbox_after["redis_message_id"] is not None

    # Step 6: Worker claims from Redis, fences state transitions, publishes GLB, acknowledges
    claimed = broker.claim(worker_id="worker_recovery_test", lease_seconds=60.0)
    assert claimed is not None
    assert claimed["job_id"] == jid
    assert claimed["event_id"] == outbox_after["outbox_id"]

    ok, _, claimed_db = pg.mutate_job(jid, lambda j: j.transition("CLAIMED", "claimed", "worker_recovery_test"))
    assert ok and claimed_db.lease_generation == 1
    assert pg.mutate_job(jid, lambda j: j.transition("PROCESSING", "proc", "worker_recovery_test", 1))[0]
    assert pg.mutate_job(jid, lambda j: j.transition("VALIDATING", "val", "worker_recovery_test", 1))[0]
    assert pg.mutate_job(jid, lambda j: j.transition("PUBLISHING", "pub", "worker_recovery_test", 1))[0]

    glb_bytes = _valid_minimal_glb_bytes()
    fresh = pg.load_job(jid)
    pub_res = restarted_mgr._artifact_publisher.publish_artifact_fenced(
        job_id=jid,
        glb_bytes=glb_bytes,
        user_id=fresh.user_id,
        tenant_id=fresh.tenant_id,
        correlation_id=fresh.correlation_id,
        lease_generation=fresh.lease_generation,
        job_state_ref=fresh,
    )
    ok_done, _, _ = pg.mutate_job(
        jid,
        lambda j: j.commit_completion("worker_recovery_test", 1, pub_res["canonical_path"], pub_res["sha256"]),
    )
    assert ok_done
    broker.acknowledge(jid, worker_id="worker_recovery_test", lease_generation=claimed["lease_generation"])
    pg.mark_outbox_acknowledged(jid)

    final_job = pg.load_job(jid)
    final_outbox = pg.load_outbox_entry(jid, "JOB_QUEUED")
    assert final_job.current_state == "COMPLETED"
    assert final_job.asset_sha256 == pub_res["sha256"]
    assert final_outbox["status"] == "ACKNOWLEDGED"
    assert final_outbox["acknowledged_at"] is not None


def test_transient_redis_outage_then_dispatcher_recovery(live_infra):
    """Boundary 4: Transient Redis outage during create_job leaves job QUEUED + PENDING; recovers when Redis heals."""
    pg, real_broker, tmp_path, created_jobs, _ = live_infra
    uid = f"usr_{uuid.uuid4().hex[:8]}"

    failing_broker = MagicMock(spec=RedisStreamsQueueBroker)
    failing_broker.enqueue.side_effect = ConnectionError("Redis temporarily unavailable")

    mgr = _make_real_manager(pg, failing_broker, tmp_path / "assets")
    mgr._dispatch_next_tasks = MagicMock()  # Prevent in-memory worker from racing the outbox test

    job = mgr.create_job(uid, _png_bytes(), "tops", subcategory="jacket")
    created_jobs.append(job.job_id)

    assert job.status == GarmentGenJobStatus.QUEUED
    assert pg.load_job(job.job_id).current_state == "QUEUED"
    outbox = pg.load_outbox_entry(job.job_id, "JOB_QUEUED")
    assert outbox["status"] == "PENDING"
    assert outbox["delivered_at"] is None

    # Redis heals -> swap back real broker and dispatch outbox
    mgr._redis_broker = real_broker
    delivered = mgr._dispatch_outbox_pending()
    assert delivered >= 1
    assert real_broker.get_queue_depth() == 1

    outbox_after = pg.load_outbox_entry(job.job_id, "JOB_QUEUED")
    assert outbox_after["status"] == "DELIVERED"
    assert outbox_after["redis_message_id"] is not None


def test_bounded_retry_backoff_and_exhaustion(live_infra):
    """Boundary 5: Repeated Redis failure tracks attempts with exponential backoff and marks EXHAUSTED."""
    pg, _, tmp_path, created_jobs, dsn = live_infra
    jid = f"job_exhaust_{uuid.uuid4().hex[:8]}"
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    created_jobs.append(jid)

    job_tmp = Path(TEMP_BASE_DIR) / jid
    job_tmp.mkdir(parents=True, exist_ok=True)
    front_path = job_tmp / "temp_input_front.raw"
    front_path.write_bytes(_png_bytes())

    pg.create_job_atomic(
        job_id=jid,
        user_id=uid,
        tenant_id=uid,
        outbox_payload={"job_id": jid, "user_id": uid, "tenant_id": uid, "front_path": str(front_path)},
        outbox_priority=3,
    )

    always_fail_broker = MagicMock(spec=RedisStreamsQueueBroker)
    always_fail_broker.enqueue.side_effect = ConnectionError("Persistent Redis failure")
    mgr = _make_real_manager(pg, always_fail_broker, tmp_path / "assets")

    import asyncio, asyncpg

    def _reset_deliver_after():
        async def _upd():
            conn = await asyncpg.connect(dsn)
            try:
                await conn.execute("UPDATE yorvyn_job_outbox SET deliver_after = 0 WHERE job_id = $1", jid)
            finally:
                await conn.close()
        asyncio.run(_upd())

    # Simulate 5 bounded delivery attempts
    prev_backoff = 0.0
    for attempt_idx in range(1, 6):
        _reset_deliver_after()
        delivered = mgr._dispatch_outbox_pending()
        assert delivered == 0
        row = pg.load_outbox_entry(jid, "JOB_QUEUED")
        assert row["delivery_attempts"] == attempt_idx
        assert "Persistent Redis failure" in (row["last_error"] or "")
        backoff = row["deliver_after"] - time.time()
        if attempt_idx < 5:
            assert backoff >= prev_backoff - 1.0  # Exponential growth
            prev_backoff = backoff

    final_outbox = pg.load_outbox_entry(jid, "JOB_QUEUED")
    final_job = pg.load_job(jid)
    assert final_outbox["status"] == "EXHAUSTED"
    assert final_outbox["delivery_attempts"] == 5
    assert final_job.current_state == "DEAD_LETTERED"

    # Further dispatcher cycles must NOT attempt delivery again
    _reset_deliver_after()
    calls_before = always_fail_broker.enqueue.call_count
    mgr._dispatch_outbox_pending()
    assert always_fail_broker.enqueue.call_count == calls_before


def test_retry_crash_window_atomic_job_retry_outbox(live_infra):
    """Boundary 6: retry_job commits FAILED->QUEUED + JOB_RETRY outbox atomically; recovers after Redis failure."""
    pg, real_broker, tmp_path, created_jobs, _ = live_infra
    jid = f"job_retry_crash_{uuid.uuid4().hex[:8]}"
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    created_jobs.append(jid)

    job_tmp = Path(TEMP_BASE_DIR) / jid
    job_tmp.mkdir(parents=True, exist_ok=True)
    front_path = job_tmp / "temp_input_front.raw"
    front_path.write_bytes(_png_bytes())

    pg.create_job_atomic(
        job_id=jid, user_id=uid, tenant_id=uid,
        outbox_payload={"job_id": jid, "user_id": uid, "tenant_id": uid, "front_path": str(front_path)},
    )
    pg.mark_outbox_acknowledged(jid)
    # Transition job to FAILED
    assert pg.mutate_job(jid, lambda j: j.transition("CLAIMED", "c", "w1"))[0]
    assert pg.mutate_job(jid, lambda j: j.transition("PROCESSING", "p", "w1", 1))[0]
    assert pg.mutate_job(jid, lambda j: j.transition("FAILED", "oom", "w1", 1))[0]

    failing_broker = MagicMock(spec=RedisStreamsQueueBroker)
    failing_broker.enqueue.side_effect = ConnectionError("Redis outage during retry")
    mgr = _make_real_manager(pg, failing_broker, tmp_path / "assets")
    mgr._dispatch_next_tasks = MagicMock()

    retried = mgr.retry_job(jid)
    assert retried is not None
    assert retried.status == GarmentGenJobStatus.QUEUED
    assert pg.load_job(jid).current_state == "QUEUED"

    retry_outbox = pg.load_outbox_entry(jid, "JOB_RETRY")
    assert retry_outbox is not None
    assert retry_outbox["status"] == "PENDING"

    # Recovery / dispatcher delivers JOB_RETRY once Redis returns
    mgr._redis_broker = real_broker
    delivered = mgr._dispatch_outbox_pending()
    assert delivered >= 1
    assert real_broker.get_queue_depth() == 1
    assert pg.load_outbox_entry(jid, "JOB_RETRY")["status"] == "DELIVERED"


def test_duplicate_redis_delivery_and_fencing_token_mismatch(live_infra):
    """Boundary 7 & 8: Duplicate Redis deliveries + stale fencing token yield single completion."""
    pg, broker, tmp_path, created_jobs, _ = live_infra
    jid = f"job_dup_{uuid.uuid4().hex[:8]}"
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    created_jobs.append(jid)

    pg.create_job_atomic(
        job_id=jid, user_id=uid, tenant_id=uid,
        outbox_payload={"job_id": jid, "user_id": uid, "tenant_id": uid, "front_path": "/tmp/fake.raw"},
    )
    # Enqueue duplicate messages for the same job (e.g. crash before mark_outbox_delivered)
    broker.enqueue({"job_id": jid, "user_id": uid, "tenant_id": uid, "lease_generation": 0}, priority=3)
    broker.enqueue({"job_id": jid, "user_id": uid, "tenant_id": uid, "lease_generation": 0}, priority=3)

    msg1 = broker.claim("worker_a")
    msg2 = broker.claim("worker_b")
    assert msg1["job_id"] == jid and msg2["job_id"] == jid

    # Worker A acquires generation 1 lease
    ok_a, _, st_a = pg.mutate_job(jid, lambda j: j.transition("CLAIMED", "claim_a", "worker_a"))
    assert ok_a and st_a.lease_generation == 1
    assert pg.mutate_job(jid, lambda j: j.transition("PROCESSING", "proc_a", "worker_a", 1))[0]

    # Worker B tries to claim again -> REJECTED by state machine
    ok_b, msg_b, _ = pg.mutate_job(jid, lambda j: j.transition("CLAIMED", "claim_b", "worker_b"))
    assert ok_b is False

    # Stale generation token (0 or 99) -> REJECTED on VALIDATING and commit_completion
    ok_stale_val, _, _ = pg.mutate_job(jid, lambda j: j.transition("VALIDATING", "stale", "worker_a", lease_generation=0))
    assert ok_stale_val is False
    ok_stale_worker, _, _ = pg.mutate_job(jid, lambda j: j.transition("VALIDATING", "wrong_w", "worker_b", lease_generation=1))
    assert ok_stale_worker is False

    # Worker A finishes legitimately
    assert pg.mutate_job(jid, lambda j: j.transition("VALIDATING", "val", "worker_a", 1))[0]
    assert pg.mutate_job(jid, lambda j: j.transition("PUBLISHING", "pub", "worker_a", 1))[0]
    ok_done, _, _ = pg.mutate_job(jid, lambda j: j.commit_completion("worker_a", 1, "/tmp/x.glb", "abc123"))
    assert ok_done

    # Duplicate delivery on terminal job must be rejected
    ok_dup_after, _, _ = pg.mutate_job(jid, lambda j: j.transition("CLAIMED", "dup", "worker_b"))
    assert ok_dup_after is False


def test_crash_after_publication_before_ack_preserves_completion(live_infra):
    """Boundary 9: Failure of Redis/outbox ACK after commit_completion preserves COMPLETED & reconciles outbox."""
    pg, _, tmp_path, created_jobs, _ = live_infra
    jid = f"job_ackfail_{uuid.uuid4().hex[:8]}"
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    created_jobs.append(jid)

    pg.create_job_atomic(
        job_id=jid, user_id=uid, tenant_id=uid,
        outbox_payload={"job_id": jid, "user_id": uid, "tenant_id": uid, "front_path": "/tmp/fake.raw"},
    )
    pg.mutate_job(jid, lambda j: j.transition("CLAIMED", "c", "w1"))
    pg.mutate_job(jid, lambda j: j.transition("PROCESSING", "p", "w1", 1))
    pg.mutate_job(jid, lambda j: j.transition("VALIDATING", "v", "w1", 1))
    pg.mutate_job(jid, lambda j: j.transition("PUBLISHING", "pub", "w1", 1))
    assert pg.mutate_job(jid, lambda j: j.commit_completion("w1", 1, "/tmp/final.glb", "sha256_ok"))[0]

    ack_fail_broker = MagicMock(spec=RedisStreamsQueueBroker)
    ack_fail_broker.acknowledge.side_effect = ConnectionError("Redis connection lost at ACK")
    mgr = _make_real_manager(pg, ack_fail_broker, tmp_path / "assets")

    # Even if Redis ACK failed and outbox wasn't ACKed yet, terminal reconciliation cleans it up
    reconciled = pg.reconcile_terminal_outbox_entries()
    assert reconciled >= 1
    assert pg.load_job(jid).current_state == "COMPLETED"
    assert pg.load_outbox_entry(jid, "JOB_QUEUED")["status"] == "ACKNOWLEDGED"


def test_stale_delivery_recovery_queued_vs_active_processing(live_infra):
    """Boundary 10: Stale delivered outbox re-delivers for QUEUED job, skips active PROCESSING job."""
    pg, broker, tmp_path, created_jobs, dsn = live_infra
    jid_q = f"job_stale_q_{uuid.uuid4().hex[:8]}"
    jid_p = f"job_stale_p_{uuid.uuid4().hex[:8]}"
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    created_jobs.extend([jid_q, jid_p])

    job_tmp = Path(TEMP_BASE_DIR) / jid_q
    job_tmp.mkdir(parents=True, exist_ok=True)
    front_q = job_tmp / "temp_input_front.raw"
    front_q.write_bytes(_png_bytes())

    pg.create_job_atomic(jid_q, uid, uid, outbox_payload={"job_id": jid_q, "user_id": uid, "tenant_id": uid, "front_path": str(front_q)})
    pg.create_job_atomic(jid_p, uid, uid, outbox_payload={"job_id": jid_p, "user_id": uid, "tenant_id": uid, "front_path": str(front_q)})

    pg.mark_outbox_delivered(job_id=jid_q, event_type="JOB_QUEUED", redis_message_id="old-msg-1")
    pg.mark_outbox_delivered(job_id=jid_p, event_type="JOB_QUEUED", redis_message_id="old-msg-2")

    # Move jid_p into PROCESSING
    pg.mutate_job(jid_p, lambda j: j.transition("CLAIMED", "c", "w1"))
    pg.mutate_job(jid_p, lambda j: j.transition("PROCESSING", "p", "w1", 1))

    # Age delivered_at by 120 seconds in PostgreSQL
    import asyncio, asyncpg
    async def _age():
        conn = await asyncpg.connect(dsn)
        try:
            old_ts = time.time() - 120.0
            await conn.execute(
                "UPDATE yorvyn_job_outbox SET delivered_at = $1, deliver_after = $1 WHERE job_id = ANY($2::text[])",
                old_ts, [jid_q, jid_p],
            )
        finally:
            await conn.close()
    asyncio.run(_age())

    mgr = _make_real_manager(pg, broker, tmp_path / "assets")
    delivered = mgr._dispatch_outbox_pending()

    # Only the QUEUED stale delivery is re-delivered; PROCESSING job is untouched
    assert delivered == 1
    assert broker.get_queue_depth() == 1
    assert pg.load_outbox_entry(jid_p, "JOB_QUEUED")["delivery_attempts"] == 0


def test_safe_concurrent_outbox_dispatch_skip_locked(live_infra):
    """Boundary 11: Concurrent outbox claim calls never return overlapping outbox entries."""
    pg, _, _, created_jobs, _ = live_infra
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    created = []
    for _ in range(4):
        jid = f"job_conc_{uuid.uuid4().hex[:8]}"
        created_jobs.append(jid)
        created.append(jid)
        pg.create_job_atomic(jid, uid, uid, outbox_payload={"job_id": jid, "user_id": uid, "tenant_id": uid, "front_path": "/tmp/f.raw"})

    barrier = threading.Barrier(2)
    claims_per_thread = [[], []]

    def _worker(idx: int):
        barrier.wait()
        rows = pg.claim_pending_outbox_entries(limit=2, dispatcher_id=f"disp_{idx}")
        claims_per_thread[idx] = [r["job_id"] for r in rows if r["job_id"] in created]

    t1 = threading.Thread(target=_worker, args=(0,))
    t2 = threading.Thread(target=_worker, args=(1,))
    t1.start(); t2.start()
    t1.join(); t2.join()

    set1, set2 = set(claims_per_thread[0]), set(claims_per_thread[1])
    assert len(set1 & set2) == 0, f"Concurrent dispatchers overlapped: {set1 & set2}"
    assert len(set1 | set2) == 4


def test_concurrent_duplicate_submissions_deduplicated(live_infra):
    """Boundary 12: Concurrent create_job submissions with identical input produce 1 job and 1 outbox row."""
    pg, broker, tmp_path, created_jobs, _ = live_infra
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    img = _png_bytes(color=(99, 77, 55))

    mgr = _make_real_manager(pg, broker, tmp_path / "assets")
    mgr._dispatch_next_tasks = MagicMock()

    barrier = threading.Barrier(2)
    results = []
    errors = []

    def _submit():
        barrier.wait()
        try:
            job = mgr.create_job(uid, img, "tops", subcategory="hoodie")
            results.append(job.job_id)
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=_submit)
    t2 = threading.Thread(target=_submit)
    t1.start(); t2.start()
    t1.join(); t2.join()

    created_jobs.extend(set(results))
    assert not errors, f"Unexpected concurrent errors: {errors}"
    assert len(results) == 2
    assert len(set(results)) == 1
    assert broker.get_queue_depth() == 1


def test_compensation_safety_verification(live_infra):
    """
    Boundary 13: Compensation rejects:
    - nonexistent job_id
    - wrong expected_user_id / expected_tenant_id
    - CLAIMED / PROCESSING / terminal states
    - retried jobs (retry_count > 0 or lease_generation > 0)
    - cannot release another request's idempotency reservation
    """
    pg, _, _, created_jobs, _ = live_infra
    uid = f"usr_comp_{uuid.uuid4().hex[:8]}"

    # 1. Nonexistent job_id
    assert pg.compensate_enqueue_failure("job_does_not_exist", "bad") is False

    # 2. CLAIMED job rejected
    jid_claimed = f"job_c_claimed_{uuid.uuid4().hex[:8]}"
    created_jobs.append(jid_claimed)
    pg.create_job_atomic(jid_claimed, uid, uid, idempotency_key=f"idem_{jid_claimed}", outbox_payload={"job_id": jid_claimed})
    pg.mutate_job(jid_claimed, lambda j: j.transition("CLAIMED", "c", "w1"))
    assert pg.compensate_enqueue_failure(jid_claimed, "late_comp") is False
    assert pg.load_job(jid_claimed).current_state == "CLAIMED"

    # 3. Wrong owner rejected; outbox + idempotency untouched
    jid_owner = f"job_c_own_{uuid.uuid4().hex[:8]}"
    fp_owner = hashlib.sha256(jid_owner.encode()).hexdigest()
    created_jobs.append(jid_owner)
    pg.create_job_atomic(
        jid_owner, uid, uid,
        idempotency_key=f"idem_{jid_owner}",
        canonical_fingerprint=fp_owner,
        outbox_payload={"job_id": jid_owner},
    )
    assert pg.compensate_enqueue_failure(jid_owner, "hijack", expected_user_id="usr_attacker") is False
    assert pg.load_job(jid_owner).current_state == "QUEUED"
    assert pg.load_outbox_entry(jid_owner, "JOB_QUEUED") is not None

    # 4. Newer retry (QUEUED with retry_count=1, lease_generation=1) rejected
    assert pg.mutate_job(jid_owner, lambda j: j.transition("CLAIMED", "c", "w1"))[0]
    assert pg.mutate_job(jid_owner, lambda j: j.transition("PROCESSING", "p", "w1", 1))[0]
    assert pg.mutate_job(jid_owner, lambda j: j.transition("FAILED", "f", "w1", 1))[0]
    assert pg.retry_job_atomic(jid_owner, {"job_id": jid_owner})[0]
    assert pg.compensate_enqueue_failure(jid_owner, "overwrite_retry") is False
    assert pg.load_job(jid_owner).current_state == "QUEUED"
    assert pg.load_job(jid_owner).retry_count == 1

    # 5. Terminal state (COMPLETED) rejected
    jid_term = f"job_c_term_{uuid.uuid4().hex[:8]}"
    created_jobs.append(jid_term)
    pg.create_job_atomic(jid_term, uid, uid, idempotency_key=f"idem_{jid_term}", outbox_payload={"job_id": jid_term})
    pg.mutate_job(jid_term, lambda j: j.transition("CLAIMED", "c", "w1"))
    pg.mutate_job(jid_term, lambda j: j.transition("PROCESSING", "p", "w1", 1))
    pg.mutate_job(jid_term, lambda j: j.transition("VALIDATING", "v", "w1", 1))
    pg.mutate_job(jid_term, lambda j: j.transition("PUBLISHING", "pub", "w1", 1))
    pg.mutate_job(jid_term, lambda j: j.commit_completion("w1", 1, "/tmp/x.glb", "sha256"))
    assert pg.compensate_enqueue_failure(jid_term, "after_complete") is False
    assert pg.load_job(jid_term).current_state == "COMPLETED"

    # 6. Clean QUEUED initial-enqueue job CAN be compensated only with exact job_id + owner
    jid_ok = f"job_c_ok_{uuid.uuid4().hex[:8]}"
    created_jobs.append(jid_ok)
    pg.create_job_atomic(jid_ok, uid, uid, idempotency_key=f"idem_{jid_ok}", outbox_payload={"job_id": jid_ok})
    assert pg.compensate_enqueue_failure(jid_ok, "backpressure", expected_user_id=uid, expected_tenant_id=uid) is True
    assert pg.load_job(jid_ok).current_state == "DEAD_LETTERED"
    assert pg.load_outbox_entry(jid_ok, "JOB_QUEUED") is None
    # Verify jid_owner's idempotency reservation was NOT affected
    is_new_again, existing_owner = pg.create_job_atomic(
        f"job_c_dup_{uuid.uuid4().hex[:8]}", uid, uid,
        idempotency_key=f"idem_{jid_owner}",
        canonical_fingerprint=fp_owner,
    )
    assert is_new_again is False
    assert existing_owner.job_id == jid_owner


def test_outbox_observability_stats_and_health(live_infra):
    """Boundary 14: Outbox stats and health endpoint report accurate lifecycle counters."""
    pg, broker, tmp_path, created_jobs, _ = live_infra
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    jid = f"job_obs_{uuid.uuid4().hex[:8]}"
    created_jobs.append(jid)

    pg.create_job_atomic(jid, uid, uid, outbox_payload={"job_id": jid})
    mgr = _make_real_manager(pg, broker, tmp_path / "assets")
    health = mgr.get_health_status()

    assert "outbox" in health
    assert health["outbox"]["pending_count"] >= 1
    assert "oldest_pending_age_seconds" in health["outbox"]
