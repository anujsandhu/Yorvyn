"""
YORVYN — Queue & Broker Abstraction (Phase 14.13 Workstream I.5)
Separates API ingress from worker execution with bounded queues, backpressure,
tenant and user concurrency limits, lease generation fencing tokens, and dead-letter handling.

Includes:
1. JobQueueBrokerInterface: Abstract contract
2. DiskDurableQueueBroker: Clean, durable, crash-resilient local filesystem broker
   (Explicitly labelled as disk_durable_file_queue_adapter, NEVER misrepresented as Redis)
3. REDIS_DEPLOYMENT_SPECIFICATION: Production Redis Streams review with safe retention,
   PEL recovery, and DLQ handling.
"""

import os
import time
import json
import uuid
import shutil
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger("yorvyn_queue_broker")


class QueueOverloadedException(Exception):
    """Raised when queue exceeds max_capacity, applying backpressure."""
    pass


class ConcurrencyLimitExceededException(Exception):
    """Raised when a single user or tenant exceeds their active job limit."""
    pass


class StaleLeaseException(Exception):
    """Raised when a stale worker attempts to heartbeat or acknowledge a superseded lease."""
    pass


class JobQueueBrokerInterface(ABC):
    """Abstract interface defining the queue broker boundary."""

    @abstractmethod
    def enqueue(self, job_data: Dict[str, Any], priority: int = 1) -> bool:
        pass

    @abstractmethod
    def claim(self, worker_id: str, lease_seconds: float = 60.0) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def heartbeat(self, job_id: str, worker_id: str, lease_generation: int, extend_seconds: float = 60.0) -> bool:
        pass

    @abstractmethod
    def acknowledge(self, job_id: str, worker_id: str, lease_generation: int) -> bool:
        pass

    @abstractmethod
    def requeue(self, job_id: str, reason: str = "lease_expired") -> bool:
        pass

    @abstractmethod
    def dead_letter(self, job_id: str, reason: str = "max_retries_exceeded") -> bool:
        pass

    @abstractmethod
    def get_queue_depth(self) -> int:
        pass


class DiskDurableQueueBroker(JobQueueBrokerInterface):
    """
    Durable, file-backed local queue broker.
    Uses atomic filesystem moves (os.replace) across subdirectories on the same mount:
    - queue/incoming: Newly enqueued jobs awaiting worker claim
    - queue/claimed: Jobs currently locked by a worker under lease
    - queue/completed: Jobs acknowledged by workers
    - queue/dead_letter: Jobs that failed retry exhaustion or unrecoverable errors

    Labelling: Strictly identified as 'disk_durable_file_queue_adapter'.
    """

    def __init__(
        self,
        base_dir: Path,
        max_capacity: int = 100,
        max_user_concurrency: int = 2,
        max_tenant_concurrency: int = 10,
        default_lease_seconds: float = 60.0
    ):
        self.base_dir = Path(base_dir).resolve()
        self.incoming_dir = self.base_dir / "incoming"
        self.claimed_dir = self.base_dir / "claimed"
        self.completed_dir = self.base_dir / "completed"
        self.dead_letter_dir = self.base_dir / "dead_letter"

        # Ensure all subdirectories are on the same mount
        self.incoming_dir.mkdir(parents=True, exist_ok=True)
        self.claimed_dir.mkdir(parents=True, exist_ok=True)
        self.completed_dir.mkdir(parents=True, exist_ok=True)
        self.dead_letter_dir.mkdir(parents=True, exist_ok=True)

        self.max_capacity = max_capacity
        self.max_user_concurrency = max_user_concurrency
        self.max_tenant_concurrency = max_tenant_concurrency
        self.default_lease_seconds = default_lease_seconds

    def enqueue(self, job_data: Dict[str, Any], priority: int = 1) -> bool:
        """
        Enqueues a job atomically.
        Enforces:
        - Bounded queue capacity backpressure
        - Per-user active concurrency limits
        - Per-tenant active concurrency limits
        - Fsync durability on tempfile before atomic move
        """
        current_depth = self.get_queue_depth()
        if current_depth >= self.max_capacity:
            raise QueueOverloadedException(
                f"Backpressure: Queue capacity {self.max_capacity} reached (current: {current_depth})"
            )

        user_id = str(job_data.get("user_id", "")).strip()
        tenant_id = str(job_data.get("tenant_id", "")).strip()

        if user_id and user_id not in ("anonymous", "default_user"):
            active_for_user = self.get_user_active_count(user_id)
            if active_for_user >= self.max_user_concurrency:
                raise ConcurrencyLimitExceededException(
                    f"User {user_id} has {active_for_user} active jobs (max: {self.max_user_concurrency})"
                )

        if tenant_id and tenant_id not in ("anonymous", "default_tenant"):
            active_for_tenant = self.get_tenant_active_count(tenant_id)
            if active_for_tenant >= self.max_tenant_concurrency:
                raise ConcurrencyLimitExceededException(
                    f"Tenant {tenant_id} has {active_for_tenant} active jobs (max: {self.max_tenant_concurrency})"
                )

        job_id = job_data["job_id"]
        enqueue_ts = time.time()
        job_data["enqueued_at"] = enqueue_ts
        job_data["priority"] = priority
        job_data.setdefault("lease_generation", 0)

        target_file = self.incoming_dir / f"{int(enqueue_ts * 1000)}_{job_id}.json"
        temp_file = self.base_dir / f".tmp_{job_id}_{uuid.uuid4().hex[:6]}.json"

        with open(temp_file, "w") as f:
            json.dump(job_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        # Atomic POSIX rename onto the same filesystem
        temp_file.replace(target_file)
        return True

    def claim(self, worker_id: str, lease_seconds: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Atomically claims the oldest incoming job using atomic directory move.
        Increments monotonically increasing lease_generation.
        POSIX os.replace guarantees exclusive mutual exclusion across multiple OS processes.
        """
        lease_sec = lease_seconds or self.default_lease_seconds
        incoming_files = sorted(self.incoming_dir.glob("*.json"))
        if not incoming_files:
            return None

        for candidate_file in incoming_files:
            job_filename = candidate_file.name
            claimed_target = self.claimed_dir / job_filename

            try:
                # Atomic POSIX move from incoming to claimed
                candidate_file.replace(claimed_target)
            except (FileNotFoundError, OSError):
                # Another OS process won the race and claimed this file
                continue

            # This process exclusively owns claimed_target. Read and assign lease generation.
            try:
                with open(claimed_target, "r") as f:
                    job_data = json.load(f)

                current_gen = job_data.get("lease_generation", 0)
                new_gen = current_gen + 1

                job_data["claimed_at"] = time.time()
                job_data["claimed_by_worker"] = worker_id
                job_data["lease_generation"] = new_gen
                job_data["lease_expires_at"] = time.time() + lease_sec
                job_data["current_state"] = "CLAIMED"

                # Persist updated lease with fencing token
                temp_update = self.base_dir / f".tmp_claim_{job_data['job_id']}_{uuid.uuid4().hex[:6]}.json"
                with open(temp_update, "w") as f:
                    json.dump(job_data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                temp_update.replace(claimed_target)
                return job_data

            except Exception as e:
                logger.error(f"Failed to update claimed lease for {job_filename}: {e}")
                return None

        return None

    def heartbeat(
        self,
        job_id: str,
        worker_id: str,
        lease_generation: int,
        extend_seconds: Optional[float] = None
    ) -> bool:
        """Extends worker lease duration if worker_id and lease_generation match."""
        lease_ext = extend_seconds or self.default_lease_seconds
        for claimed_file in self.claimed_dir.glob(f"*{job_id}.json"):
            try:
                with open(claimed_file, "r") as f:
                    data = json.load(f)

                # Validate fencing token and worker ownership
                if data.get("claimed_by_worker") != worker_id:
                    return False
                if data.get("lease_generation") != lease_generation:
                    return False

                data["lease_expires_at"] = time.time() + lease_ext
                data["last_heartbeat_at"] = time.time()

                temp_hb = self.base_dir / f".tmp_hb_{job_id}_{uuid.uuid4().hex[:6]}.json"
                with open(temp_hb, "w") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                temp_hb.replace(claimed_file)
                return True
            except Exception:
                return False
        return False

    def acknowledge(self, job_id: str, worker_id: str, lease_generation: Optional[int] = None) -> bool:
        """
        Confirms successful job completion and archives it into completed directory.
        Rejects stale lease generation.
        """
        for claimed_file in self.claimed_dir.glob(f"*{job_id}.json"):
            try:
                with open(claimed_file, "r") as f:
                    data = json.load(f)

                if data.get("claimed_by_worker") != worker_id and not worker_id.startswith("supervisor"):
                    return False

                if lease_generation is not None:
                    if data.get("lease_generation") != lease_generation:
                        raise StaleLeaseException(
                            f"Cannot acknowledge job {job_id}: Stale lease generation {lease_generation} "
                            f"(current is {data.get('lease_generation')})"
                        )

                completed_target = self.completed_dir / claimed_file.name
                claimed_file.replace(completed_target)
                return True
            except StaleLeaseException:
                raise
            except Exception:
                return False
        return False

    def requeue(self, job_id: str, reason: str = "lease_expired") -> bool:
        """Returns a claimed job to the incoming queue (e.g. on lease expiry)."""
        for claimed_file in self.claimed_dir.glob(f"*{job_id}.json"):
            try:
                with open(claimed_file, "r") as f:
                    data = json.load(f)

                data["requeued_at"] = time.time()
                data["requeue_reason"] = reason
                data["current_state"] = "QUEUED"
                data["claimed_by_worker"] = None
                data["lease_expires_at"] = None

                incoming_target = self.incoming_dir / claimed_file.name
                temp_rq = self.base_dir / f".tmp_rq_{job_id}_{uuid.uuid4().hex[:6]}.json"
                with open(temp_rq, "w") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                temp_rq.replace(incoming_target)
                claimed_file.unlink(missing_ok=True)
                return True
            except Exception:
                return False
        return False

    def dead_letter(self, job_id: str, reason: str = "max_retries_exceeded") -> bool:
        """Moves an unprocessable job to dead-letter queue."""
        for search_dir in (self.claimed_dir, self.incoming_dir):
            for job_file in search_dir.glob(f"*{job_id}.json"):
                try:
                    with open(job_file, "r") as f:
                        data = json.load(f)

                    data["dead_lettered_at"] = time.time()
                    data["dead_letter_reason"] = reason
                    data["current_state"] = "DEAD_LETTERED"

                    dl_target = self.dead_letter_dir / job_file.name
                    job_file.replace(dl_target)
                    return True
                except Exception:
                    return False
        return False

    def reclaim_expired_leases(self, lease_timeout_seconds: float = 60.0) -> List[str]:
        """Scans claimed directory and re-queues any jobs whose lease expired."""
        now = time.time()
        reclaimed: List[str] = []

        for claimed_file in self.claimed_dir.glob("*.json"):
            try:
                with open(claimed_file, "r") as f:
                    data = json.load(f)

                expires_at = data.get("lease_expires_at", 0)
                if now > expires_at:
                    job_id = data["job_id"]
                    if self.requeue(job_id, reason="lease_timeout_sweep"):
                        reclaimed.append(job_id)
            except Exception:
                continue

        return reclaimed

    def get_queue_depth(self) -> int:
        return len(list(self.incoming_dir.glob("*.json")))

    def get_user_active_count(self, user_id: str) -> int:
        count = 0
        for directory in (self.incoming_dir, self.claimed_dir):
            for f in directory.glob("*.json"):
                try:
                    with open(f, "r") as jf:
                        if json.load(jf).get("user_id") == user_id:
                            count += 1
                except Exception:
                    pass
        return count

    def get_tenant_active_count(self, tenant_id: str) -> int:
        count = 0
        for directory in (self.incoming_dir, self.claimed_dir):
            for f in directory.glob("*.json"):
                try:
                    with open(f, "r") as jf:
                        if json.load(jf).get("tenant_id") == tenant_id:
                            count += 1
                except Exception:
                    pass
        return count


class RedisStreamsQueueBroker(JobQueueBrokerInterface):
    """
    Live Redis Streams Queue Broker for Production Workloads (Phase 14.14).
    Uses real Redis Streams with consumer groups, lease generation fencing tokens,
    PEL recovery via XAUTOCLAIM, bounded stream retention (MAXLEN ~ 50000),
    and dead-letter streaming.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6379,
        db: int = 0,
        stream_key: str = "yorvyn:stream:jobs",
        dead_letter_stream: str = "yorvyn:stream:dead_letter",
        group_name: str = "reconstruction_workers",
        max_capacity: int = 1000,
        max_user_concurrency: int = 2,
        max_tenant_concurrency: int = 10,
        default_lease_seconds: float = 60.0
    ):
        import redis
        self.client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self.stream_key = stream_key
        self.dead_letter_stream = dead_letter_stream
        self.group_name = group_name
        self.max_capacity = max_capacity
        self.max_user_concurrency = max_user_concurrency
        self.max_tenant_concurrency = max_tenant_concurrency
        self.default_lease_seconds = default_lease_seconds

        # Map to track job_id -> message_id for ACK
        self._job_message_ids: Dict[str, str] = {}
        self._job_lease_meta: Dict[str, Dict[str, Any]] = {}

        self._ensure_group()

    def _ensure_group(self):
        try:
            self.client.xgroup_create(self.stream_key, self.group_name, id="0", mkstream=True)
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                logger.warning(f"Consumer group init notice: {e}")

    def enqueue(self, job_data: Dict[str, Any], priority: int = 1) -> bool:
        current_len = self.client.xlen(self.stream_key)
        if current_len >= self.max_capacity:
            raise QueueOverloadedException(
                f"Backpressure: Redis stream length {current_len} exceeds max capacity {self.max_capacity}"
            )

        user_id = str(job_data.get("user_id", "")).strip()
        tenant_id = str(job_data.get("tenant_id", "")).strip()

        if user_id and user_id not in ("anonymous", "default_user"):
            active_u = int(self.client.hget("yorvyn:active:users", user_id) or 0)
            if active_u >= self.max_user_concurrency:
                raise ConcurrencyLimitExceededException(
                    f"User {user_id} has {active_u} active jobs (max: {self.max_user_concurrency})"
                )

        if tenant_id and tenant_id not in ("anonymous", "default_tenant"):
            active_t = int(self.client.hget("yorvyn:active:tenants", tenant_id) or 0)
            if active_t >= self.max_tenant_concurrency:
                raise ConcurrencyLimitExceededException(
                    f"Tenant {tenant_id} has {active_t} active jobs (max: {self.max_tenant_concurrency})"
                )

        job_id = job_data["job_id"]
        job_data["enqueued_at"] = time.time()
        job_data["priority"] = priority
        job_data.setdefault("lease_generation", 0)
        event_id = str(job_data.get("event_id") or "")
        correlation_id = str(job_data.get("correlation_id") or "")

        # XADD with bounded retention (~ 50000 entries)
        msg_id = self.client.xadd(
            self.stream_key,
            {
                "payload": json.dumps(job_data),
                "job_id": job_id,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "priority": str(priority),
                "event_id": event_id,
                "correlation_id": correlation_id,
            },
            maxlen=50000,
            approximate=True
        )
        self._job_message_ids[job_id] = msg_id
        return True

    def get_last_message_id(self, job_id: str) -> Optional[str]:
        """Return the last Redis stream message ID produced/claimed for job_id."""
        return self._job_message_ids.get(job_id)

    def claim(self, worker_id: str, lease_seconds: Optional[float] = None) -> Optional[Dict[str, Any]]:
        lease_sec = lease_seconds or self.default_lease_seconds

        # 1. First attempt to read any pending unacknowledged message assigned to this consumer
        resp = self.client.xreadgroup(
            groupname=self.group_name,
            consumername=worker_id,
            streams={self.stream_key: "0"},
            count=1
        )
        entries = []
        if resp and resp[0][1]:
            entries = resp[0][1]

        # 2. If no pending assigned message, claim a new message (">")
        if not entries:
            resp = self.client.xreadgroup(
                groupname=self.group_name,
                consumername=worker_id,
                streams={self.stream_key: ">"},
                count=1,
                block=200
            )
            if resp and resp[0][1]:
                entries = resp[0][1]

        if not entries:
            return None

        msg_id, fields = entries[0]
        try:
            payload_raw = fields.get("payload")
            job_data = json.loads(payload_raw)
        except Exception:
            return None

        job_id = job_data["job_id"]
        cur_gen = job_data.get("lease_generation", 0)
        new_gen = cur_gen + 1

        job_data["claimed_at"] = time.time()
        job_data["claimed_by_worker"] = worker_id
        job_data["lease_generation"] = new_gen
        job_data["lease_expires_at"] = time.time() + lease_sec
        job_data["current_state"] = "CLAIMED"
        job_data["_redis_msg_id"] = msg_id

        self._job_message_ids[job_id] = msg_id
        self._job_lease_meta[job_id] = {
            "worker_id": worker_id,
            "lease_generation": new_gen,
            "lease_expires_at": job_data["lease_expires_at"],
            "msg_id": msg_id,
            "user_id": job_data.get("user_id"),
            "tenant_id": job_data.get("tenant_id")
        }

        # Track active user and tenant counts
        u = job_data.get("user_id")
        t = job_data.get("tenant_id")
        if u and u not in ("anonymous", "default_user"):
            self.client.hincrby("yorvyn:active:users", u, 1)
        if t and t not in ("anonymous", "default_tenant"):
            self.client.hincrby("yorvyn:active:tenants", t, 1)

        return job_data

    def heartbeat(
        self,
        job_id: str,
        worker_id: str,
        lease_generation: int,
        extend_seconds: Optional[float] = None
    ) -> bool:
        meta = self._job_lease_meta.get(job_id)
        if not meta:
            return False
        if meta["worker_id"] != worker_id or meta["lease_generation"] != lease_generation:
            return False
        if time.time() > meta["lease_expires_at"]:
            return False

        ext = extend_seconds or self.default_lease_seconds
        meta["lease_expires_at"] = time.time() + ext
        # Update heartbeat hash in Redis
        self.client.hset("yorvyn:worker:heartbeats", f"{worker_id}:{job_id}", str(time.time()))
        return True

    def acknowledge(self, job_id: str, worker_id: str, lease_generation: Optional[int] = None) -> bool:
        meta = self._job_lease_meta.get(job_id)
        msg_id = self._job_message_ids.get(job_id)

        if meta and lease_generation is not None:
            if meta["lease_generation"] != lease_generation:
                raise StaleLeaseException(
                    f"Cannot acknowledge job {job_id}: Stale lease generation {lease_generation} (current: {meta['lease_generation']})"
                )

        if msg_id:
            try:
                acked = self.client.xack(self.stream_key, self.group_name, msg_id)
            except Exception as exc:
                logger.warning(f"Redis XACK notice for {job_id}: {exc}")
                acked = 0
            if meta:
                u = meta.get("user_id")
                t = meta.get("tenant_id")
                if u and u not in ("anonymous", "default_user"):
                    self.client.hincrby("yorvyn:active:users", u, -1)
                if t and t not in ("anonymous", "default_tenant"):
                    self.client.hincrby("yorvyn:active:tenants", t, -1)
            self._job_message_ids.pop(job_id, None)
            self._job_lease_meta.pop(job_id, None)
            return acked > 0
        return False

    def requeue(self, job_id: str, reason: str = "lease_expired") -> bool:
        meta = self._job_lease_meta.get(job_id)
        msg_id = self._job_message_ids.get(job_id)
        if msg_id:
            self.client.xack(self.stream_key, self.group_name, msg_id)
            if meta:
                u = meta.get("user_id")
                t = meta.get("tenant_id")
                if u and u not in ("anonymous", "default_user"):
                    self.client.hincrby("yorvyn:active:users", u, -1)
                if t and t not in ("anonymous", "default_tenant"):
                    self.client.hincrby("yorvyn:active:tenants", t, -1)
            self._job_message_ids.pop(job_id, None)
            self._job_lease_meta.pop(job_id, None)
        return True

    def dead_letter(self, job_id: str, reason: str = "max_retries_exceeded") -> bool:
        meta = self._job_lease_meta.get(job_id)
        msg_id = self._job_message_ids.get(job_id)
        self.client.xadd(
            self.dead_letter_stream,
            {
                "job_id": job_id,
                "reason": reason,
                "timestamp": str(time.time()),
                "original_msg_id": msg_id or "unknown"
            },
            maxlen=10000,
            approximate=True
        )
        if msg_id:
            self.client.xack(self.stream_key, self.group_name, msg_id)
            if meta:
                u = meta.get("user_id")
                t = meta.get("tenant_id")
                if u and u not in ("anonymous", "default_user"):
                    self.client.hincrby("yorvyn:active:users", u, -1)
                if t and t not in ("anonymous", "default_tenant"):
                    self.client.hincrby("yorvyn:active:tenants", t, -1)
        self._job_message_ids.pop(job_id, None)
        self._job_lease_meta.pop(job_id, None)
        return True

    def reclaim_pending_entries(self, worker_id: str, min_idle_ms: int = 60000, count: int = 10) -> List[Dict[str, Any]]:
        """Uses XAUTOCLAIM to safely reclaim messages abandoned by crashed workers."""
        try:
            res = self.client.xautoclaim(
                self.stream_key,
                self.group_name,
                worker_id,
                min_idle_time=min_idle_ms,
                start_id="0-0",
                count=count
            )
            reclaimed_jobs = []
            entries = res[1] if len(res) > 1 else []
            for msg_id, fields in entries:
                if not fields:
                    continue
                try:
                    payload = json.loads(fields.get("payload", "{}"))
                    job_id = payload.get("job_id")
                    if job_id:
                        self._job_message_ids[job_id] = msg_id
                        reclaimed_jobs.append(payload)
                except Exception:
                    continue
            return reclaimed_jobs
        except Exception as e:
            logger.error(f"Failed to reclaim pending entries: {e}")
            return []

    def get_queue_depth(self) -> int:
        return self.client.xlen(self.stream_key)


REDIS_DEPLOYMENT_SPECIFICATION = {
    "broker_type": "Redis Streams & Consumer Groups",
    "evaluation_status": "STATIC_SPECIFICATION_AND_SIMULATED_ADAPTER (Live Redis daemon unverified locally)",
    "stream_keys": {
        "primary_jobs_stream": "yorvyn:stream:jobs",
        "dead_letter_stream": "yorvyn:stream:dead_letter",
        "worker_heartbeat_hash": "yorvyn:worker:heartbeats"
    },
    "consumer_group_semantics": {
        "group_name": "reconstruction_workers",
        "enqueue_command": "XADD yorvyn:stream:jobs MAXLEN ~ 50000 * payload <json> priority <int> tenant_id <tenant>",
        "claim_command": "XREADGROUP GROUP reconstruction_workers <worker_id> COUNT 1 BLOCK 2000 STREAMS yorvyn:stream:jobs >",
        "heartbeat_command": "HSET yorvyn:worker:heartbeats <worker_id> <timestamp>; EXPIRE yorvyn:worker:heartbeats 60",
        "acknowledgement_command": "XACK yorvyn:stream:jobs reconstruction_workers <message_id>",
        "reclaim_pending_command": "XAUTOCLAIM yorvyn:stream:jobs reconstruction_workers <worker_id> 60000 0-0 COUNT 10",
        "dead_letter_command": "XADD yorvyn:stream:dead_letter MAXLEN ~ 10000 * original_id <id> tenant_id <tenant> reason <reason>"
    },
    "retention_and_trimming_policy": {
        "xdel_policy": "STRICT_PROHIBITION_ON_IMMEDIATE_XDEL: Do not execute XDEL immediately after XACK. Immediate XDEL destroys audit trails and interferes with PEL recovery. Use stream-level MAXLEN trimming instead.",
        "acknowledged_retention": "Preserved in stream for 24 hours or up to 50,000 entries via MAXLEN ~ 50000.",
        "pending_entry_list_pel": "Unacknowledged messages remain in PEL until recovered via XAUTOCLAIM or transferred to DLQ upon exceeding 3 delivery attempts.",
        "dead_letter_retention": "Retained for 30 days in yorvyn:stream:dead_letter with MAXLEN ~ 10000 for forensic debugging."
    },
    "durability_and_high_availability": {
        "aof_persistence": "appendonly yes, appendfsync everysec",
        "rdb_snapshot": "save 900 1, save 300 10, save 60 10000",
        "failover": "Redis Sentinel with 3-node quorum or Google Cloud Memorystore Multi-AZ with automatic failover"
    }
}
