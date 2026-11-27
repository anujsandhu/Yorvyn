"""
YORVYN — Unified Distributed Job State Machine & Durable State Manager (Phase 14.13 Workstream I.6)
Implements:
1. Canonical 8-state machine with lease generation fencing tokens.
2. TrustedSecurityContext: Cryptographically verified server-side admin claims (rejects client-provided is_admin flags).
3. DurableJobStateManager: Cross-process atomic state persistence using POSIX fcntl.flock mutual exclusion.
4. DurableIdempotencyRegistry: Cross-process atomic idempotency using O_CREAT | O_EXCL with 409 conflict detection.
5. Append-only attempt history preserved across retries, crashes, and restarts.
6. Fail-closed tenant isolation.
"""

import os
import sys
import time
import json
import uuid
import hmac
import fcntl
import hashlib
import logging
import threading
import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple, Callable

logger = logging.getLogger("yorvyn_state_machine")


def resolve_postgres_dsn(environ: Optional[Dict[str, str]] = None) -> str:
    """Resolve the persistence DSN using the deployment's canonical environment."""
    env = os.environ if environ is None else environ
    return (
        env.get("YORVYN_PG_DSN")
        or env.get("DATABASE_URL")
        or "postgresql://postgres:postgres@localhost:5432/yorvyn_persistence"
    )

LEGAL_TRANSITIONS: Dict[str, Set[str]] = {
    "CREATED": {"QUEUED", "CANCELLED"},
    "SUBMITTED": {"QUEUED", "CANCELLED"},  # Backwards compatibility alias
    "QUEUED": {"CLAIMED", "CANCELLED", "DEAD_LETTERED"},
    "CLAIMED": {"PROCESSING", "QUEUED", "FAILED", "CANCELLED", "DEAD_LETTERED"},
    "PROCESSING": {"VALIDATING", "COMPLETED", "FAILED", "CANCELLED", "DEAD_LETTERED", "QUEUED"},  # Re-queued if worker lease expires
    "VALIDATING": {"PUBLISHING", "FAILED", "CANCELLED", "DEAD_LETTERED", "QUEUED"},
    "PUBLISHING": {"COMPLETED", "FAILED", "CANCELLED", "DEAD_LETTERED"},
    "COMPLETED": set(),      # Immutable terminal state
    "FAILED": {"QUEUED", "DEAD_LETTERED"},  # Re-queued if retry_count < max_retries
    "CANCELLED": set(),      # Immutable terminal state
    "DEAD_LETTERED": set(),  # Immutable terminal state
}

TERMINAL_STATES: Set[str] = {"COMPLETED", "CANCELLED", "DEAD_LETTERED"}

BANNED_IDENTITIES: Set[str] = {
    "anonymous", "default_user", "default_tenant", "guest", "null", "none", "", "undefined"
}

# Default server secret for cryptographic admin token verification
SERVER_HMAC_SECRET = os.environ.get("YORVYN_SECURITY_SECRET", "yorvyn_internal_cryptographic_secret_2026")


def compute_canonical_fingerprint(
    tenant_id: str,
    user_id: str,
    image_sha256: str,
    garment_category: str,
    garment_subcategory: str,
    reconstruction_config: Dict[str, Any],
    model_version: str,
    pipeline_version: str
) -> str:
    """Computes a deterministic, collision-resistant canonical request fingerprint."""
    canonical_payload = {
        "tenant_id": str(tenant_id).strip(),
        "user_id": str(user_id).strip(),
        "image_sha256": str(image_sha256).strip().lower(),
        "garment_category": str(garment_category).strip().lower(),
        "garment_subcategory": str(garment_subcategory).strip().lower(),
        "reconstruction_config": json.dumps(reconstruction_config, sort_keys=True),
        "model_version": str(model_version).strip(),
        "pipeline_version": str(pipeline_version).strip()
    }
    canonical_str = json.dumps(canonical_payload, sort_keys=True)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


class IdempotencyConflictException(Exception):
    """Raised when an explicit idempotency key is reused with mismatched payload parameters (HTTP 409)."""
    pass


class StaleWorkerException(Exception):
    """Raised when a worker with an expired lease or stale fencing token attempts state mutation."""
    pass


class TenantSecurityViolationException(Exception):
    """Raised when an unauthorized, unauthenticated, or cross-tenant request attempts job manipulation."""
    pass


class TrustedSecurityContext:
    """
    Validated server-side security context.
    Administrative privileges can NEVER be granted by a client-provided boolean flag.
    Admin status must be cryptographically signed by the server using standard HMAC-SHA256,
    verifying token expiration, issuer, audience, and scope.
    """

    def __init__(
        self,
        user_id: str,
        tenant_id: str,
        roles: Optional[List[str]] = None,
        server_signature: Optional[str] = None,
        token_expires_at: Optional[float] = None,
        issuer: str = "yorvyn-auth-server",
        audience: str = "yorvyn-internal",
        scopes: Optional[List[str]] = None
    ):
        self.user_id = str(user_id).strip()
        self.tenant_id = str(tenant_id).strip()
        self.roles: List[str] = [str(r).strip().upper() for r in (roles or [])]
        self.server_signature = server_signature
        self.token_expires_at = token_expires_at
        self.issuer = str(issuer).strip()
        self.audience = str(audience).strip()
        self.scopes: List[str] = [str(s).strip() for s in (scopes or ["garment:reconstruct"])]

    @classmethod
    def create_admin_context(
        cls,
        user_id: str,
        tenant_id: str,
        ttl_seconds: float = 3600.0,
        issuer: str = "yorvyn-auth-server",
        audience: str = "yorvyn-internal",
        scopes: Optional[List[str]] = None,
        server_secret: str = SERVER_HMAC_SECRET
    ) -> "TrustedSecurityContext":
        """Factory creating a cryptographically signed administrative security context."""
        expires = time.time() + ttl_seconds
        admin_scopes = scopes or ["garment:reconstruct", "garment:admin"]
        scope_str = ",".join(sorted(admin_scopes))
        payload = f"{user_id}:{tenant_id}:ADMIN:{expires}:{issuer}:{audience}:{scope_str}"
        # Standard HMAC-SHA256 cryptographic verification
        sig = hmac.new(server_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return cls(
            user_id=user_id,
            tenant_id=tenant_id,
            roles=["ADMIN"],
            server_signature=sig,
            token_expires_at=expires,
            issuer=issuer,
            audience=audience,
            scopes=admin_scopes
        )

    def is_verified_admin(
        self,
        server_secret: str = SERVER_HMAC_SECRET,
        expected_issuer: str = "yorvyn-auth-server",
        expected_audience: str = "yorvyn-internal",
        required_scope: str = "garment:admin"
    ) -> bool:
        """
        Cryptographically verifies that the admin claim was issued by the server using standard HMAC-SHA256,
        verifies that it has not expired, and confirms issuer, audience, and required scope.
        """
        if "ADMIN" not in self.roles:
            return False
        if not self.server_signature:
            return False
        if self.token_expires_at and time.time() > self.token_expires_at:
            return False
        if self.issuer != expected_issuer:
            return False
        if self.audience != expected_audience:
            return False
        if required_scope and required_scope not in self.scopes:
            return False

        scope_str = ",".join(sorted(self.scopes))
        expected_payload = f"{self.user_id}:{self.tenant_id}:ADMIN:{self.token_expires_at}:{self.issuer}:{self.audience}:{scope_str}"
        expected_sig = hmac.new(server_secret.encode("utf-8"), expected_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if hmac.compare_digest(self.server_signature, expected_sig):
            return True

        # Fallback for legacy Phase 14.13 HMAC format without issuer/audience
        legacy_payload = f"{self.user_id}:{self.tenant_id}:ADMIN:{self.token_expires_at}:{server_secret}"
        legacy_sig = hashlib.sha256(legacy_payload.encode("utf-8")).hexdigest()
        return hmac.compare_digest(self.server_signature, legacy_sig)


class DurableIdempotencyRegistry:
    """
    Cross-process durable atomic idempotency registry backed by POSIX O_CREAT | O_EXCL.
    Coordinates atomically across multiple OS processes without memory sharing.
    """

    def __init__(self, registry_dir: Path, ttl_seconds: float = 86400.0):
        self.registry_dir = Path(registry_dir).resolve()
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    def register_or_get(
        self,
        tenant_id: str,
        idempotency_key: str,
        canonical_fingerprint: str,
        job_id: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Atomically registers an idempotency key or retrieves an existing one.
        Returns: (is_new: bool, job_id: str, metadata: dict).
        Raises IdempotencyConflictException if key exists with different fingerprint.
        """
        # Scoped by tenant
        safe_tenant = hashlib.sha256(tenant_id.encode()).hexdigest()[:16]
        safe_key = hashlib.sha256(idempotency_key.encode()).hexdigest()[:24]
        target_file = self.registry_dir / f"idp_{safe_tenant}_{safe_key}.json"

        # Attempt atomic creation
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(str(target_file), flags, 0o644)
            try:
                record = {
                    "tenant_id": tenant_id,
                    "idempotency_key": idempotency_key,
                    "canonical_fingerprint": canonical_fingerprint,
                    "job_id": job_id,
                    "registered_at": time.time()
                }
                data = json.dumps(record, indent=2).encode("utf-8")
                os.write(fd, data)
                os.fsync(fd)
                return True, job_id, record
            finally:
                os.close(fd)

        except FileExistsError:
            # File already exists: another process won the race or previously registered
            with open(target_file, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    existing = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Check for parameter conflict
            if existing["canonical_fingerprint"] != canonical_fingerprint:
                raise IdempotencyConflictException(
                    f"Idempotency key '{idempotency_key}' for tenant '{tenant_id}' was previously "
                    f"registered with different request parameters (existing: {existing['canonical_fingerprint'][:12]}, "
                    f"new: {canonical_fingerprint[:12]})"
                )

            return False, existing["job_id"], existing


# In-memory alias for backwards compatibility
class IdempotencyRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._registry: Dict[str, Dict[str, Any]] = {}

    def register_or_get(self, tenant_id: str, idempotency_key: str, canonical_fingerprint: str, job_id: str):
        scoped = f"{tenant_id}:{idempotency_key}"
        with self._lock:
            if scoped in self._registry:
                existing = self._registry[scoped]
                if existing["canonical_fingerprint"] != canonical_fingerprint:
                    raise IdempotencyConflictException("Payload mismatch on reused idempotency key")
                return False, existing["job_id"], existing
            rec = {
                "tenant_id": tenant_id,
                "idempotency_key": idempotency_key,
                "canonical_fingerprint": canonical_fingerprint,
                "job_id": job_id,
                "registered_at": time.time()
            }
            self._registry[scoped] = rec
            return True, job_id, rec


class UnifiedJobState:
    """Manages the in-memory representation of an inference job's lifecycle and validation rules."""

    def __init__(
        self,
        job_id: str,
        user_id: str,
        tenant_id: str,
        correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        canonical_fingerprint: Optional[str] = None,
        max_retries: int = 3,
        lease_seconds: float = 60.0
    ):
        u = str(user_id).strip().lower() if user_id else ""
        t = str(tenant_id).strip().lower() if tenant_id else ""
        if not u or u in BANNED_IDENTITIES:
            raise TenantSecurityViolationException(
                f"Cannot create job {job_id}: Invalid or unauthenticated user_id '{user_id}'"
            )
        if not t or t in BANNED_IDENTITIES:
            raise TenantSecurityViolationException(
                f"Cannot create job {job_id}: Invalid or unauthenticated tenant_id '{tenant_id}'"
            )

        self._lock = threading.RLock()
        self.job_id = job_id
        self.user_id = str(user_id).strip()
        self.tenant_id = str(tenant_id).strip()
        self.correlation_id = correlation_id or f"corr_{uuid.uuid4().hex[:12]}"
        self.idempotency_key = idempotency_key or job_id
        self.canonical_fingerprint = canonical_fingerprint
        self.current_state = "CREATED"
        self.max_retries = max_retries
        self.retry_count = 0
        self.lease_seconds = lease_seconds
        self.lease_generation = 0
        self.lease_expires_at: Optional[float] = None
        self.claimed_by_worker: Optional[str] = None
        self.created_at = time.time()
        self.updated_at = self.created_at
        self.completed_at: Optional[float] = None
        self.asset_path: Optional[str] = None
        self.asset_sha256: Optional[str] = None

        self.history: List[Dict[str, Any]] = []
        self.attempts: List[Dict[str, Any]] = []

        self._record_transition(
            from_state=None,
            to_state="CREATED",
            reason="Job creation received and validated",
            worker_id="api_gateway",
            lease_generation=0
        )

    def _record_transition(
        self,
        from_state: Optional[str],
        to_state: str,
        reason: str,
        worker_id: str,
        lease_generation: int
    ):
        now = time.time()
        self.history.append({
            "from_state": from_state,
            "to_state": to_state,
            "timestamp": now,
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "reason": reason,
            "worker_id": worker_id,
            "lease_generation": lease_generation,
            "correlation_id": self.correlation_id,
            "retry_count": self.retry_count
        })
        self.current_state = to_state
        self.updated_at = now

    def record_failure_attempt(
        self,
        worker_id: str,
        lease_generation: int,
        error_code: str,
        error_details: str
    ):
        with self._lock:
            self.attempts.append({
                "attempt_number": len(self.attempts) + 1,
                "worker_id": worker_id,
                "lease_generation": lease_generation,
                "failed_at": time.time(),
                "error_code": error_code,
                "error_details": error_details,
                "retry_count_at_failure": self.retry_count
            })

    def transition(
        self,
        target_state: str,
        reason: str,
        worker_id: str,
        lease_generation: Optional[int] = None
    ) -> Tuple[bool, str]:
        with self._lock:
            target_state = target_state.upper()

            if self.current_state in TERMINAL_STATES:
                return False, f"Illegal transition: Job {self.job_id} is in immutable terminal state '{self.current_state}'"

            allowed = LEGAL_TRANSITIONS.get(self.current_state, set())
            if target_state not in allowed:
                return False, f"Illegal transition: '{self.current_state}' -> '{target_state}' is not allowed"

            from_st = self.current_state

            if from_st in ("CLAIMED", "PROCESSING", "VALIDATING", "PUBLISHING") and target_state in ("PROCESSING", "VALIDATING", "PUBLISHING", "COMPLETED", "FAILED"):
                if lease_generation is not None:
                    if lease_generation != self.lease_generation:
                        return False, (
                            f"Fencing token rejected: Worker {worker_id} provided stale lease generation {lease_generation} "
                            f"(current active generation is {self.lease_generation})"
                        )
                if worker_id != self.claimed_by_worker and not worker_id.startswith("supervisor"):
                    return False, f"Worker mismatch: Job claimed by '{self.claimed_by_worker}', caller is '{worker_id}'"
                if self.is_lease_expired():
                    return False, f"Lease expired: Worker {worker_id} lease expired at {self.lease_expires_at}"

            if target_state == "CLAIMED":
                self.lease_generation += 1
                self.claimed_by_worker = worker_id
                self.lease_expires_at = time.time() + self.lease_seconds

            if target_state in ("COMPLETED", "FAILED", "CANCELLED", "DEAD_LETTERED", "QUEUED"):
                self.lease_expires_at = None
                if target_state in ("COMPLETED", "CANCELLED", "DEAD_LETTERED", "QUEUED"):
                    self.claimed_by_worker = None
                    if target_state == "COMPLETED":
                        self.completed_at = time.time()

            if from_st == "FAILED" and target_state == "QUEUED":
                self.retry_count += 1
                if self.retry_count > self.max_retries:
                    self._record_transition(from_st, "DEAD_LETTERED", "Retry limit exhausted", worker_id, self.lease_generation)
                    return False, f"Retry limit ({self.max_retries}) exhausted; moved to DEAD_LETTERED"

            self._record_transition(from_st, target_state, reason, worker_id, self.lease_generation)
            return True, f"Successfully transitioned to {target_state}"

    def heartbeat(
        self,
        worker_id: str,
        lease_generation: int,
        extend_seconds: Optional[float] = None
    ) -> Tuple[bool, str]:
        with self._lock:
            if self.current_state not in ("CLAIMED", "PROCESSING"):
                return False, f"Heartbeat rejected: Job is in state '{self.current_state}'"
            if self.claimed_by_worker != worker_id:
                return False, f"Heartbeat rejected: Worker '{worker_id}' does not own claim"
            if self.lease_generation != lease_generation:
                return False, f"Heartbeat rejected: Stale fencing token {lease_generation} (current is {self.lease_generation})"
            if self.is_lease_expired():
                return False, "Heartbeat rejected: Lease has already expired"

            ext = extend_seconds or self.lease_seconds
            self.lease_expires_at = time.time() + ext
            self.updated_at = time.time()
            return True, f"Lease extended by {ext}s (generation {self.lease_generation})"

    def is_lease_expired(self) -> bool:
        if self.current_state in ("CLAIMED", "PROCESSING") and self.lease_expires_at:
            return time.time() > self.lease_expires_at
        return False

    def recover_abandoned_claim(self, supervisor_id: str = "supervisor") -> Tuple[bool, str]:
        with self._lock:
            if not self.is_lease_expired():
                return False, "Lease has not expired"

            if self.retry_count < self.max_retries:
                self.retry_count += 1
                t_ok, t_msg = self.transition(
                    "QUEUED",
                    f"Lease expired for worker {self.claimed_by_worker} (gen {self.lease_generation}); re-queued (retry {self.retry_count}/{self.max_retries})",
                    supervisor_id
                )
                return t_ok, f"Abandoned claim recovered; re-queued (retry {self.retry_count})"
            else:
                t_ok, t_msg = self.transition(
                    "DEAD_LETTERED",
                    f"Lease expired (gen {self.lease_generation}) and max retries ({self.max_retries}) exhausted",
                    supervisor_id
                )
                return t_ok, "Abandoned claim moved to DEAD_LETTERED"

    def assert_ownership(
        self,
        security_context_or_user_id: Any,
        requesting_tenant_id: Optional[str] = None,
        is_admin: bool = False,
        action: str = "access"
    ) -> Tuple[bool, str]:
        """
        Enforces tenant isolation and user ownership boundaries.
        Accepts either a TrustedSecurityContext or raw IDs (for backwards compatibility).
        Never trusts client-provided is_admin=True flags; verifies server HMAC signature.
        """
        # If passed TrustedSecurityContext directly
        if isinstance(security_context_or_user_id, TrustedSecurityContext):
            sec = security_context_or_user_id
            u_req = sec.user_id.lower()
            t_req = sec.tenant_id.lower()

            if not u_req or not t_req or u_req in BANNED_IDENTITIES or t_req in BANNED_IDENTITIES:
                msg = f"SECURITY_AUDIT: REJECT_INVALID_CONTEXT - Disallowed identity pattern for '{action}' on job '{self.job_id}'"
                logger.warning(msg)
                return False, msg

            # Cryptographically verified admin role
            if sec.is_verified_admin():
                msg = f"SECURITY_AUDIT: ALLOW_VERIFIED_ADMIN - Verified admin '{sec.user_id}' accessed job '{self.job_id}' for '{action}'"
                logger.info(msg)
                return True, msg

            # Check tenant and user boundaries
            if self.tenant_id != sec.tenant_id:
                msg = f"SECURITY_AUDIT: REJECT_CROSS_TENANT - Cross-tenant access attempted on job '{self.job_id}'"
                logger.warning(msg)
                return False, msg

            if self.user_id != sec.user_id:
                msg = f"SECURITY_AUDIT: REJECT_CROSS_USER - Cross-user access attempted on job '{self.job_id}'"
                logger.warning(msg)
                return False, msg

            msg = f"SECURITY_AUDIT: ALLOW - Authorized access to job '{self.job_id}' for '{action}'"
            return True, msg

        # Backwards compatibility path for raw user_id / tenant_id
        u_raw = str(security_context_or_user_id).strip().lower() if security_context_or_user_id else ""
        t_raw = str(requesting_tenant_id).strip().lower() if requesting_tenant_id else ""

        if not u_raw or not t_raw or u_raw in BANNED_IDENTITIES or t_raw in BANNED_IDENTITIES:
            msg = f"SECURITY_AUDIT: REJECT - Missing/disallowed credentials for action '{action}' on job '{self.job_id}'"
            logger.warning(msg)
            return False, msg

        # If a caller passes is_admin=True without a verified TrustedSecurityContext, REJECT!
        if is_admin:
            msg = f"SECURITY_AUDIT: REJECT_FORGED_ADMIN - Unverified client-supplied admin flag rejected for job '{self.job_id}'"
            logger.warning(msg)
            return False, msg

        if self.tenant_id.lower() != t_raw:
            msg = f"SECURITY_AUDIT: REJECT_CROSS_TENANT - Cross-tenant access attempted on job '{self.job_id}'"
            logger.warning(msg)
            return False, msg

        if self.user_id.lower() != u_raw:
            msg = f"SECURITY_AUDIT: REJECT_CROSS_USER - Cross-user access within tenant attempted on job '{self.job_id}'"
            logger.warning(msg)
            return False, msg

        msg = f"SECURITY_AUDIT: ALLOW - Authorized access to job '{self.job_id}' for action '{action}'"
        return True, msg

    def start_validation(
        self,
        worker_id: str,
        lease_generation: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Transitions job to VALIDATING phase under active lease."""
        return self.transition("VALIDATING", "Mesh and GLB validation started", worker_id, lease_generation)

    def start_publishing(
        self,
        worker_id: str,
        lease_generation: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Transitions job to PUBLISHING phase under active lease."""
        return self.transition("PUBLISHING", "Artifact packaging and publication started", worker_id, lease_generation)

    def commit_completion(
        self,
        worker_id: str,
        lease_generation: int,
        asset_path: str,
        asset_sha256: str
    ) -> Tuple[bool, str]:
        with self._lock:
            if self.current_state not in ("CLAIMED", "PROCESSING", "VALIDATING", "PUBLISHING"):
                return False, f"Cannot commit completion: Job is in state '{self.current_state}'"

            if not asset_path or not asset_sha256:
                return False, "Cannot commit completion: Authoritative asset path and SHA256 checksum required"

            if self.lease_generation != lease_generation:
                return False, f"Commit rejected: Stale lease generation {lease_generation} (active is {self.lease_generation})"

            if self.claimed_by_worker != worker_id and not worker_id.startswith("supervisor"):
                return False, f"Commit rejected: Worker '{worker_id}' does not own claim"

            if self.is_lease_expired():
                return False, f"Commit rejected: Lease expired at {self.lease_expires_at}"

            self.asset_path = asset_path
            self.asset_sha256 = asset_sha256
            return self.transition("COMPLETED", f"Artifact committed (sha256: {asset_sha256[:8]})", worker_id, lease_generation)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "job_id": self.job_id,
                "user_id": self.user_id,
                "tenant_id": self.tenant_id,
                "correlation_id": self.correlation_id,
                "idempotency_key": self.idempotency_key,
                "canonical_fingerprint": self.canonical_fingerprint,
                "current_state": self.current_state,
                "claimed_by_worker": self.claimed_by_worker,
                "lease_generation": self.lease_generation,
                "lease_expires_at": self.lease_expires_at,
                "is_lease_expired": self.is_lease_expired(),
                "retry_count": self.retry_count,
                "max_retries": self.max_retries,
                "lease_seconds": self.lease_seconds,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "completed_at": self.completed_at,
                "asset_path": self.asset_path,
                "asset_sha256": self.asset_sha256,
                "transition_count": len(self.history),
                "history": self.history,
                "attempt_count": len(self.attempts),
                "attempts": self.attempts
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnifiedJobState":
        job = cls.__new__(cls)
        job._lock = threading.RLock()
        job.job_id = data["job_id"]
        job.user_id = data["user_id"]
        job.tenant_id = data["tenant_id"]
        job.correlation_id = data.get("correlation_id", "")
        job.idempotency_key = data.get("idempotency_key", "")
        job.canonical_fingerprint = data.get("canonical_fingerprint")
        job.current_state = data.get("current_state", "SUBMITTED")
        job.max_retries = data.get("max_retries", 3)
        job.retry_count = data.get("retry_count", 0)
        job.lease_seconds = data.get("lease_seconds", 60.0)
        job.lease_generation = data.get("lease_generation", 0)
        job.lease_expires_at = data.get("lease_expires_at")
        job.claimed_by_worker = data.get("claimed_by_worker")
        job.created_at = data.get("created_at", time.time())
        job.updated_at = data.get("updated_at", time.time())
        job.completed_at = data.get("completed_at")
        job.asset_path = data.get("asset_path")
        job.asset_sha256 = data.get("asset_sha256")
        job.history = data.get("history", [])
        job.attempts = data.get("attempts", [])
        return job


class JobPersistenceInterface(ABC):
    """
    Authoritative abstraction for job state persistence.
    Enforces transactional conditional updates, lease generation fencing,
    immutable attempt records, and idempotency coordination.
    """

    @abstractmethod
    def create_job(
        self,
        job_id: str,
        user_id: str,
        tenant_id: str,
        correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        canonical_fingerprint: Optional[str] = None,
        max_retries: int = 3,
        lease_seconds: float = 60.0
    ) -> UnifiedJobState:
        pass

    @abstractmethod
    def load_job(self, job_id: str) -> Optional[UnifiedJobState]:
        pass

    @abstractmethod
    def mutate_job(
        self,
        job_id: str,
        mutation_fn: Callable[[UnifiedJobState], Tuple[bool, str]]
    ) -> Tuple[bool, str, Optional[UnifiedJobState]]:
        pass

    @abstractmethod
    def register_idempotency(
        self,
        tenant_id: str,
        idempotency_key: str,
        canonical_fingerprint: str,
        job_id: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        pass


class DurableJobStateManager(JobPersistenceInterface):
    """
    Coordinates state mutations across independent operating system processes
    using POSIX fcntl.flock file locking on <state_dir>/{job_id}.lock.
    Guarantees cross-process consistency, terminal state immutability, and zero lost updates.
    """

    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir).resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _get_paths(self, job_id: str) -> Tuple[Path, Path]:
        state_file = self.state_dir / f"{job_id}.state.json"
        lock_file = self.state_dir / f"{job_id}.lock"
        return state_file, lock_file

    def register_idempotency(
        self,
        tenant_id: str,
        idempotency_key: str,
        canonical_fingerprint: str,
        job_id: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        registry = DurableIdempotencyRegistry(self.state_dir / "idempotency")
        return registry.register_or_get(tenant_id, idempotency_key, canonical_fingerprint, job_id)

    def create_job(
        self,
        job_id: str,
        user_id: str,
        tenant_id: str,
        correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        canonical_fingerprint: Optional[str] = None,
        max_retries: int = 3,
        lease_seconds: float = 60.0
    ) -> UnifiedJobState:
        """Atomically creates and persists a new job state on disk."""
        state_file, lock_file = self._get_paths(job_id)
        job = UnifiedJobState(
            job_id=job_id,
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            canonical_fingerprint=canonical_fingerprint,
            max_retries=max_retries,
            lease_seconds=lease_seconds
        )

        with open(lock_file, "w") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                temp_file = self.state_dir / f".tmp_{job_id}_{uuid.uuid4().hex[:6]}.json"
                with open(temp_file, "w") as tf:
                    json.dump(job.to_dict(), tf, indent=2)
                    tf.flush()
                    os.fsync(tf.fileno())
                temp_file.replace(state_file)
                return job
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

    def load_job(self, job_id: str) -> Optional[UnifiedJobState]:
        """Loads a job state from disk under shared read lock."""
        state_file, lock_file = self._get_paths(job_id)
        if not state_file.exists():
            return None

        with open(lock_file, "w") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_SH)
            try:
                with open(state_file, "r") as sf:
                    data = json.load(sf)
                return UnifiedJobState.from_dict(data)
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

    def mutate_job(
        self,
        job_id: str,
        mutation_fn: Callable[[UnifiedJobState], Tuple[bool, str]]
    ) -> Tuple[bool, str, Optional[UnifiedJobState]]:
        """
        Executes a state mutation under exclusive POSIX process lock.
        Reads latest state from disk, executes mutation_fn, validates, fsyncs, and replaces file.
        """
        state_file, lock_file = self._get_paths(job_id)
        if not state_file.exists():
            return False, f"Job {job_id} not found on disk", None

        with open(lock_file, "w") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                with open(state_file, "r") as sf:
                    data = json.load(sf)
                job = UnifiedJobState.from_dict(data)

                # Execute mutation
                success, msg = mutation_fn(job)
                if success:
                    temp_file = self.state_dir / f".tmp_mut_{job_id}_{uuid.uuid4().hex[:6]}.json"
                    with open(temp_file, "w") as tf:
                        json.dump(job.to_dict(), tf, indent=2)
                        tf.flush()
                        os.fsync(tf.fileno())
                    temp_file.replace(state_file)

                return success, msg, job
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


class PostgresJobPersistenceAdapter(JobPersistenceInterface):
    """
    Transactional PostgreSQL Job Persistence Adapter (Phase 14.14).
    Provides ACID transactional job persistence, row-level locking (SELECT ... FOR UPDATE),
    database-enforced lease fencing, tenant isolation, and durable idempotency.
    """

    def __init__(self, dsn: str = "postgresql://localhost:5432/yorvyn_persistence"):
        self.dsn = dsn
        self._init_tables()

    def _run_async(self, coro):
        """Helper executing asyncpg coroutines synchronously across any calling thread."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, coro).result()
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    def _init_tables(self):
        async def _init():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS yorvyn_jobs (
                        job_id VARCHAR(64) PRIMARY KEY,
                        user_id VARCHAR(128) NOT NULL,
                        tenant_id VARCHAR(128) NOT NULL,
                        correlation_id VARCHAR(128),
                        idempotency_key VARCHAR(128),
                        canonical_fingerprint VARCHAR(64),
                        current_state VARCHAR(32) NOT NULL,
                        claimed_by_worker VARCHAR(128),
                        lease_generation INT NOT NULL DEFAULT 0,
                        lease_expires_at DOUBLE PRECISION,
                        retry_count INT NOT NULL DEFAULT 0,
                        max_retries INT NOT NULL DEFAULT 3,
                        lease_seconds DOUBLE PRECISION NOT NULL DEFAULT 60.0,
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL,
                        completed_at DOUBLE PRECISION,
                        asset_path TEXT,
                        asset_sha256 VARCHAR(64),
                        history JSONB NOT NULL DEFAULT '[]'::jsonb,
                        attempts JSONB NOT NULL DEFAULT '[]'::jsonb
                    );

                    CREATE TABLE IF NOT EXISTS yorvyn_idempotency_keys (
                        tenant_id VARCHAR(128) NOT NULL,
                        idempotency_key VARCHAR(128) NOT NULL,
                        canonical_fingerprint VARCHAR(64) NOT NULL,
                        job_id VARCHAR(64) NOT NULL,
                        registered_at DOUBLE PRECISION NOT NULL,
                        PRIMARY KEY (tenant_id, idempotency_key)
                    );

                    CREATE TABLE IF NOT EXISTS yorvyn_job_attempts (
                        attempt_id SERIAL PRIMARY KEY,
                        job_id VARCHAR(64) NOT NULL REFERENCES yorvyn_jobs(job_id) ON DELETE CASCADE,
                        worker_id VARCHAR(128) NOT NULL,
                        lease_generation INT NOT NULL,
                        failed_at DOUBLE PRECISION NOT NULL,
                        error_code VARCHAR(64) NOT NULL,
                        error_details TEXT NOT NULL,
                        retry_count INT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS yorvyn_garment_evidence_specs (
                        garment_id VARCHAR(128) PRIMARY KEY,
                        user_id VARCHAR(128) NOT NULL,
                        specification JSONB NOT NULL,
                        created_at DOUBLE PRECISION NOT NULL,
                        expires_at DOUBLE PRECISION NOT NULL,
                        reconstruction_job_id VARCHAR(64)
                    );
                    CREATE INDEX IF NOT EXISTS idx_garment_evidence_owner
                        ON yorvyn_garment_evidence_specs(user_id, expires_at);

                    CREATE TABLE IF NOT EXISTS yorvyn_job_outbox (
                        outbox_id       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
                        job_id          TEXT            NOT NULL REFERENCES yorvyn_jobs(job_id) ON DELETE CASCADE,
                        tenant_id       TEXT            NOT NULL,
                        event_type      TEXT            NOT NULL DEFAULT 'JOB_QUEUED',
                        payload         JSONB           NOT NULL,
                        priority        INTEGER         NOT NULL DEFAULT 3,
                        created_at      DOUBLE PRECISION NOT NULL,
                        deliver_after   DOUBLE PRECISION NOT NULL DEFAULT 0,
                        delivered_at    DOUBLE PRECISION,
                        delivery_attempts INTEGER       NOT NULL DEFAULT 0,
                        max_delivery_attempts INTEGER   NOT NULL DEFAULT 5,
                        redis_message_id TEXT,
                        acknowledged_at DOUBLE PRECISION,
                        status          TEXT            NOT NULL DEFAULT 'PENDING',
                        last_error      TEXT,
                        claimed_by      TEXT,
                        claimed_at      DOUBLE PRECISION,
                        CONSTRAINT outbox_job_id_event_type_key UNIQUE (job_id, event_type)
                    );
                    ALTER TABLE yorvyn_job_outbox ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'PENDING';
                    ALTER TABLE yorvyn_job_outbox ADD COLUMN IF NOT EXISTS last_error TEXT;
                    ALTER TABLE yorvyn_job_outbox ADD COLUMN IF NOT EXISTS claimed_by TEXT;
                    ALTER TABLE yorvyn_job_outbox ADD COLUMN IF NOT EXISTS claimed_at DOUBLE PRECISION;
                    CREATE INDEX IF NOT EXISTS idx_outbox_undelivered
                        ON yorvyn_job_outbox(deliver_after) WHERE delivered_at IS NULL;
                    CREATE INDEX IF NOT EXISTS idx_outbox_unacked
                        ON yorvyn_job_outbox(delivered_at) WHERE delivered_at IS NOT NULL AND acknowledged_at IS NULL;
                    CREATE INDEX IF NOT EXISTS idx_outbox_job_id
                        ON yorvyn_job_outbox(job_id);
                    CREATE INDEX IF NOT EXISTS idx_jobs_user_state
                        ON yorvyn_jobs(user_id, current_state, updated_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_attempts_job_id
                        ON yorvyn_job_attempts(job_id);
                """)
            finally:
                await conn.close()

        self._run_async(_init())

    def save_garment_evidence_spec(self, garment_id: str, user_id: str, specification: Dict[str, Any], ttl_seconds: int = 2592000) -> None:
        """Persist evidence metadata without retaining source image bytes; default retention is 30 days."""
        now = time.time()
        async def _save():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                async with conn.transaction():
                    row = await conn.fetchrow(
                        "SELECT user_id FROM yorvyn_garment_evidence_specs WHERE garment_id = $1 FOR UPDATE",
                        garment_id
                    )
                    if row and row["user_id"] != user_id:
                        raise PermissionError("Garment evidence identifier belongs to another user.")
                    await conn.execute("""
                        INSERT INTO yorvyn_garment_evidence_specs
                            (garment_id, user_id, specification, created_at, expires_at)
                        VALUES ($1, $2, $3::jsonb, $4, $5)
                        ON CONFLICT (garment_id) DO UPDATE SET
                            specification = EXCLUDED.specification,
                            created_at = EXCLUDED.created_at,
                            expires_at = EXCLUDED.expires_at
                    """, garment_id, user_id, json.dumps(specification), now, now + ttl_seconds)
                    await conn.execute("DELETE FROM yorvyn_garment_evidence_specs WHERE expires_at <= $1", now)
            finally:
                await conn.close()
        self._run_async(_save())

    def load_garment_evidence_spec(self, garment_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Load unexpired evidence metadata only for its owning user."""
        async def _load():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                now = time.time()
                row = await conn.fetchrow("""
                    SELECT specification FROM yorvyn_garment_evidence_specs
                    WHERE garment_id = $1 AND user_id = $2 AND expires_at > $3
                """, garment_id, user_id, now)
                if not row:
                    await conn.execute(
                        "DELETE FROM yorvyn_garment_evidence_specs WHERE garment_id = $1 AND expires_at <= $2",
                        garment_id, now
                    )
                    return None
                value = row["specification"]
                return json.loads(value) if isinstance(value, str) else dict(value)
            finally:
                await conn.close()
        return self._run_async(_load())

    def create_job(
        self,
        job_id: str,
        user_id: str,
        tenant_id: str,
        correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        canonical_fingerprint: Optional[str] = None,
        max_retries: int = 3,
        lease_seconds: float = 60.0
    ) -> UnifiedJobState:
        job = UnifiedJobState(
            job_id=job_id,
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            canonical_fingerprint=canonical_fingerprint,
            max_retries=max_retries,
            lease_seconds=lease_seconds
        )
        d = job.to_dict()

        async def _insert():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                await conn.execute("""
                    INSERT INTO yorvyn_jobs (
                        job_id, user_id, tenant_id, correlation_id, idempotency_key,
                        canonical_fingerprint, current_state, claimed_by_worker,
                        lease_generation, lease_expires_at, retry_count, max_retries,
                        lease_seconds, created_at, updated_at, completed_at,
                        asset_path, asset_sha256, history, attempts
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19::jsonb, $20::jsonb
                    )
                """,
                d["job_id"], d["user_id"], d["tenant_id"], d["correlation_id"], d["idempotency_key"],
                d["canonical_fingerprint"], d["current_state"], d["claimed_by_worker"],
                d["lease_generation"], d["lease_expires_at"], d["retry_count"], d["max_retries"],
                d["lease_seconds"], d["created_at"], d["updated_at"], d["completed_at"],
                d["asset_path"], d["asset_sha256"], json.dumps(d["history"]), json.dumps(d["attempts"])
                )
            finally:
                await conn.close()

        self._run_async(_insert())
        return job

    def create_job_atomic(
        self,
        job_id: str,
        user_id: str,
        tenant_id: str,
        correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        canonical_fingerprint: Optional[str] = None,
        initial_queued: bool = True,
        max_retries: int = 3,
        lease_seconds: float = 180.0,
        outbox_payload: Optional[Dict[str, Any]] = None,
        outbox_priority: Optional[int] = None,
    ) -> Tuple[bool, UnifiedJobState]:
        """
        Atomically registers idempotency key and inserts the authoritative PostgreSQL job row
        within a single ACID transaction. Prevents orphan idempotency keys or unpersisted jobs.
        Returns (is_new, UnifiedJobState).
        """
        candidate = UnifiedJobState(
            job_id=job_id,
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            canonical_fingerprint=canonical_fingerprint,
            max_retries=max_retries,
            lease_seconds=lease_seconds,
        )
        if initial_queued:
            ok, msg = candidate.transition("QUEUED", reason="enqueued_to_broker", worker_id="api_gateway")
            if not ok:
                raise RuntimeError(msg)

        eff_key = candidate.idempotency_key
        eff_fp = candidate.canonical_fingerprint or hashlib.sha256(job_id.encode("utf-8")).hexdigest()
        d = candidate.to_dict()

        async def _tx():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                async with conn.transaction():
                    now_ts = time.time()
                    # Atomic upsert-attempt: prevents concurrent INSERT UniqueViolationError
                    # when two requests with the same (tenant_id, idempotency_key) arrive simultaneously.
                    inserted_key = await conn.fetchrow("""
                        INSERT INTO yorvyn_idempotency_keys (
                            tenant_id, idempotency_key, canonical_fingerprint, job_id, registered_at
                        ) VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
                        RETURNING job_id
                    """, candidate.tenant_id, eff_key, eff_fp, candidate.job_id, now_ts)

                    if not inserted_key:
                        existing_key = await conn.fetchrow("""
                            SELECT * FROM yorvyn_idempotency_keys
                            WHERE tenant_id = $1 AND idempotency_key = $2
                            FOR UPDATE
                        """, candidate.tenant_id, eff_key)

                        if existing_key:
                            if existing_key["canonical_fingerprint"] != eff_fp:
                                raise IdempotencyConflictException(
                                    f"Idempotency key '{eff_key}' for tenant '{candidate.tenant_id}' was previously "
                                    f"registered with different request parameters "
                                    f"(existing: {existing_key['canonical_fingerprint'][:12]}, new: {eff_fp[:12]})"
                                )
                            existing_job_row = await conn.fetchrow(
                                "SELECT * FROM yorvyn_jobs WHERE job_id = $1", existing_key["job_id"]
                            )
                            if existing_job_row:
                                data = dict(existing_job_row)
                                data["history"] = json.loads(data["history"]) if isinstance(data["history"], str) else (data["history"] or [])
                                data["attempts"] = json.loads(data["attempts"]) if isinstance(data["attempts"], str) else (data["attempts"] or [])
                                return False, UnifiedJobState.from_dict(data)
                            # Orphaned idempotency row pointing to missing job: claim it atomically
                            await conn.execute("""
                                UPDATE yorvyn_idempotency_keys
                                SET job_id = $3, canonical_fingerprint = $4, registered_at = $5
                                WHERE tenant_id = $1 AND idempotency_key = $2
                            """, candidate.tenant_id, eff_key, candidate.job_id, eff_fp, now_ts)

                    await conn.execute("""
                        INSERT INTO yorvyn_jobs (
                            job_id, user_id, tenant_id, correlation_id, idempotency_key,
                            canonical_fingerprint, current_state, claimed_by_worker,
                            lease_generation, lease_expires_at, retry_count, max_retries,
                            lease_seconds, created_at, updated_at, completed_at,
                            asset_path, asset_sha256, history, attempts
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19::jsonb, $20::jsonb
                        )
                    """,
                    d["job_id"], d["user_id"], d["tenant_id"], d["correlation_id"], d["idempotency_key"],
                    d["canonical_fingerprint"], d["current_state"], d["claimed_by_worker"],
                    d["lease_generation"], d["lease_expires_at"], d["retry_count"], d["max_retries"],
                    d["lease_seconds"], d["created_at"], d["updated_at"], d["completed_at"],
                    d["asset_path"], d["asset_sha256"], json.dumps(d["history"]), json.dumps(d["attempts"])
                    )

                    # Atomically insert outbox entry within the same ACID transaction
                    # so the outbox record is durable if and only if the job row is durable.
                    if outbox_payload is not None:
                        now_ts = time.time()
                        enriched_payload = dict(outbox_payload)
                        outbox_uuid = str(enriched_payload.get("event_id") or uuid.uuid4())
                        enriched_payload["event_id"] = outbox_uuid
                        enriched_payload.setdefault("lease_generation", candidate.lease_generation)
                        await conn.execute("""
                            INSERT INTO yorvyn_job_outbox (
                                outbox_id, job_id, tenant_id, event_type, payload, priority,
                                created_at, deliver_after, status
                            ) VALUES ($1::uuid, $2, $3, 'JOB_QUEUED', $4::jsonb, $5, $6, $6, 'PENDING')
                            ON CONFLICT (job_id, event_type) DO NOTHING
                        """, outbox_uuid, candidate.job_id, candidate.tenant_id,
                        json.dumps(enriched_payload), outbox_priority or 3, now_ts)

                    return True, candidate
            finally:
                await conn.close()

        return self._run_async(_tx())

    def list_non_terminal_jobs(self) -> List[UnifiedJobState]:
        """Returns all non-terminal persisted jobs for restart recovery and reconciliation."""
        async def _list():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                rows = await conn.fetch("""
                    SELECT * FROM yorvyn_jobs
                    WHERE current_state IN ('CREATED', 'SUBMITTED', 'QUEUED', 'CLAIMED', 'PROCESSING', 'VALIDATING', 'PUBLISHING')
                    ORDER BY created_at ASC
                """)
                out: List[UnifiedJobState] = []
                for row in rows:
                    data = dict(row)
                    data["history"] = json.loads(data["history"]) if isinstance(data["history"], str) else (data["history"] or [])
                    data["attempts"] = json.loads(data["attempts"]) if isinstance(data["attempts"], str) else (data["attempts"] or [])
                    out.append(UnifiedJobState.from_dict(data))
                return out
            finally:
                await conn.close()
        return self._run_async(_list())

    def compensate_enqueue_failure(
        self,
        job_id: str,
        reason: str,
        expected_user_id: Optional[str] = None,
        expected_tenant_id: Optional[str] = None,
        expected_idempotency_key: Optional[str] = None,
        expected_state: Optional[str] = None,
    ) -> bool:
        """
        Compensate a newly created PostgreSQL job whose Redis queue enqueue failed before
        any worker could claim it: record failure attempt, move row out of QUEUED into
        DEAD_LETTERED for auditability, and release its idempotency reservation so a
        subsequent clean retry is not pinned to the undelivered attempt.

        Safety guards (DURABLE-JOB-FIX-002):
        - Exact job_id lock via SELECT ... FOR UPDATE
        - Only compensates CREATED/SUBMITTED/QUEUED state (never touches CLAIMED+/FAILED/TERMINAL)
        - Verifies expected_state if supplied
        - Verifies lease_generation == 0 and retry_count == 0 (never overwrites a claimed job or newer retry)
        - Verifies expected_user_id, expected_tenant_id, expected_idempotency_key if supplied
        - Deletes idempotency reservation scoped strictly to (tenant_id, idempotency_key, job_id)
        - Returns True if compensated, False if skipped/rejected by safety guard
        """
        async def _compensate() -> bool:
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                async with conn.transaction():
                    row = await conn.fetchrow("SELECT * FROM yorvyn_jobs WHERE job_id = $1 FOR UPDATE", job_id)
                    if not row:
                        return False
                    data = dict(row)
                    data["history"] = json.loads(data["history"]) if isinstance(data["history"], str) else (data["history"] or [])
                    data["attempts"] = json.loads(data["attempts"]) if isinstance(data["attempts"], str) else (data["attempts"] or [])
                    state = UnifiedJobState.from_dict(data)

                    # Safety: never compensate terminal states or claimed/in-flight/failed jobs
                    if state.current_state in TERMINAL_STATES:
                        logger.warning(
                            f"[Outbox] compensate_enqueue_failure skipped for {job_id}: "
                            f"job is in immutable terminal state {state.current_state}"
                        )
                        return False
                    if state.current_state not in ("CREATED", "SUBMITTED", "QUEUED"):
                        logger.warning(
                            f"[Outbox] compensate_enqueue_failure skipped for {job_id}: "
                            f"state is {state.current_state}, not CREATED/SUBMITTED/QUEUED"
                        )
                        return False
                    if expected_state and state.current_state != expected_state.upper():
                        logger.warning(
                            f"[Outbox] compensate_enqueue_failure skipped for {job_id}: "
                            f"expected_state={expected_state}, actual={state.current_state}"
                        )
                        return False
                    if state.lease_generation != 0 or state.retry_count != 0:
                        logger.warning(
                            f"[Outbox] compensate_enqueue_failure skipped for {job_id}: "
                            f"lease_generation={state.lease_generation}, retry_count={state.retry_count} (expected 0/0)"
                        )
                        return False
                    if expected_user_id and state.user_id != expected_user_id:
                        logger.warning(
                            f"[Outbox] compensate_enqueue_failure rejected for {job_id}: "
                            f"user_id mismatch (expected={expected_user_id}, actual={state.user_id})"
                        )
                        return False
                    if expected_tenant_id and state.tenant_id != expected_tenant_id:
                        logger.warning(
                            f"[Outbox] compensate_enqueue_failure rejected for {job_id}: "
                            f"tenant_id mismatch (expected={expected_tenant_id}, actual={state.tenant_id})"
                        )
                        return False
                    if expected_idempotency_key and state.idempotency_key != expected_idempotency_key:
                        logger.warning(
                            f"[Outbox] compensate_enqueue_failure rejected for {job_id}: "
                            f"idempotency_key mismatch"
                        )
                        return False

                    target = "CANCELLED" if state.current_state in ("CREATED", "SUBMITTED") else "DEAD_LETTERED"
                    state.record_failure_attempt("api_gateway", state.lease_generation, "broker_enqueue_failed", reason)
                    ok, _ = state.transition(target, reason=reason, worker_id="api_gateway")
                    if not ok:
                        return False
                    nd = state.to_dict()
                    await conn.execute("""
                        UPDATE yorvyn_jobs
                        SET current_state = $2, claimed_by_worker = $3, lease_generation = $4,
                            lease_expires_at = $5, updated_at = $6, history = $7::jsonb, attempts = $8::jsonb
                        WHERE job_id = $1
                    """,
                    state.job_id, nd["current_state"], nd["claimed_by_worker"], nd["lease_generation"],
                    nd["lease_expires_at"], nd["updated_at"], json.dumps(nd["history"]), json.dumps(nd["attempts"])
                    )
                    # Delete associated outbox entry and ONLY this job's own idempotency reservation
                    await conn.execute("DELETE FROM yorvyn_job_outbox WHERE job_id = $1", job_id)
                    await conn.execute("""
                        DELETE FROM yorvyn_idempotency_keys
                        WHERE job_id = $1 AND tenant_id = $2 AND idempotency_key = $3
                    """, job_id, state.tenant_id, state.idempotency_key)
                    return True
            finally:
                await conn.close()
        return self._run_async(_compensate())

    def retry_job_atomic(
        self,
        job_id: str,
        outbox_payload: Dict[str, Any],
        priority: int = 3,
        reason: str = "user_retry",
    ) -> Tuple[bool, str, Optional[UnifiedJobState], Optional[str]]:
        """
        Atomically transitions a FAILED job to QUEUED and writes its JOB_RETRY outbox row
        in a single PostgreSQL ACID transaction, closing the crash window on retries.
        Returns (ok, msg, updated_state, outbox_id).
        """
        async def _retry():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                async with conn.transaction():
                    row = await conn.fetchrow("SELECT * FROM yorvyn_jobs WHERE job_id = $1 FOR UPDATE", job_id)
                    if not row:
                        return False, f"Job {job_id} not found in database", None, None
                    data = dict(row)
                    data["history"] = json.loads(data["history"]) if isinstance(data["history"], str) else (data["history"] or [])
                    data["attempts"] = json.loads(data["attempts"]) if isinstance(data["attempts"], str) else (data["attempts"] or [])
                    job = UnifiedJobState.from_dict(data)

                    if job.current_state != "FAILED" or job.retry_count >= job.max_retries:
                        return False, f"Job {job_id} not eligible for retry (state={job.current_state}, retries={job.retry_count}/{job.max_retries})", job, None

                    ok, msg = job.transition("QUEUED", reason=reason, worker_id="api_gateway")
                    if not ok:
                        return False, msg, job, None

                    d = job.to_dict()
                    await conn.execute("""
                        UPDATE yorvyn_jobs
                        SET current_state = $1,
                            claimed_by_worker = $2,
                            lease_generation = $3,
                            lease_expires_at = $4,
                            retry_count = $5,
                            updated_at = $6,
                            completed_at = $7,
                            asset_path = $8,
                            asset_sha256 = $9,
                            history = $10::jsonb,
                            attempts = $11::jsonb
                        WHERE job_id = $12
                    """,
                    d["current_state"], d["claimed_by_worker"], d["lease_generation"],
                    d["lease_expires_at"], d["retry_count"], d["updated_at"],
                    d["completed_at"], d["asset_path"], d["asset_sha256"],
                    json.dumps(d["history"]), json.dumps(d["attempts"]), job_id
                    )

                    now_ts = time.time()
                    outbox_uuid = str(uuid.uuid4())
                    enriched_payload = dict(outbox_payload)
                    enriched_payload["event_id"] = outbox_uuid
                    enriched_payload["lease_generation"] = job.lease_generation
                    enriched_payload["retry_count"] = job.retry_count

                    out_row = await conn.fetchrow("""
                        INSERT INTO yorvyn_job_outbox (
                            outbox_id, job_id, tenant_id, event_type, payload, priority,
                            created_at, deliver_after, delivery_attempts, delivered_at,
                            redis_message_id, acknowledged_at, status, last_error,
                            claimed_by, claimed_at
                        ) VALUES ($1::uuid, $2, $3, 'JOB_RETRY', $4::jsonb, $5, $6, $6, 0, NULL, NULL, NULL, 'PENDING', NULL, NULL, NULL)
                        ON CONFLICT (job_id, event_type) DO UPDATE SET
                            outbox_id = EXCLUDED.outbox_id,
                            payload = EXCLUDED.payload,
                            priority = EXCLUDED.priority,
                            created_at = EXCLUDED.created_at,
                            deliver_after = EXCLUDED.deliver_after,
                            delivery_attempts = 0,
                            delivered_at = NULL,
                            redis_message_id = NULL,
                            acknowledged_at = NULL,
                            status = 'PENDING',
                            last_error = NULL,
                            claimed_by = NULL,
                            claimed_at = NULL
                        RETURNING outbox_id::text
                    """, outbox_uuid, job.job_id, job.tenant_id, json.dumps(enriched_payload), priority, now_ts)
                    return True, msg, job, (out_row["outbox_id"] if out_row else outbox_uuid)
            finally:
                await conn.close()
        return self._run_async(_retry())

    # ─── Transactional Outbox Methods (DURABLE-JOB-FIX-002) ──────────────────

    def insert_outbox_entry(
        self,
        job_id: str,
        tenant_id: str,
        payload: Dict[str, Any],
        priority: int = 3,
        event_type: str = "JOB_QUEUED",
    ) -> Optional[str]:
        """
        Insert or update an outbox entry outside of create_job_atomic (e.g. for retry/backfill).
        Uses ON CONFLICT DO UPDATE to reset delivery state for (job_id, event_type).
        Returns the outbox_id.
        """
        async def _insert():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                now_ts = time.time()
                outbox_uuid = str(uuid.uuid4())
                enriched = dict(payload)
                enriched.setdefault("event_id", outbox_uuid)
                row = await conn.fetchrow("""
                    INSERT INTO yorvyn_job_outbox (
                        outbox_id, job_id, tenant_id, event_type, payload, priority,
                        created_at, deliver_after, delivery_attempts, delivered_at, status
                    ) VALUES ($1::uuid, $2, $3, $4, $5::jsonb, $6, $7, $7, 0, NULL, 'PENDING')
                    ON CONFLICT (job_id, event_type) DO UPDATE SET
                        payload = EXCLUDED.payload,
                        priority = EXCLUDED.priority,
                        deliver_after = EXCLUDED.deliver_after,
                        delivery_attempts = 0,
                        delivered_at = NULL,
                        redis_message_id = NULL,
                        acknowledged_at = NULL,
                        status = 'PENDING',
                        last_error = NULL
                    RETURNING outbox_id::text
                """, outbox_uuid, job_id, tenant_id, event_type, json.dumps(enriched), priority, now_ts)
                return row["outbox_id"] if row else None
            finally:
                await conn.close()
        return self._run_async(_insert())

    def claim_pending_outbox_entries(
        self,
        limit: int = 50,
        stale_after_seconds: float = 30.0,
        dispatcher_id: str = "outbox_dispatcher",
        claim_lease_seconds: float = 15.0,
    ) -> List[Dict[str, Any]]:
        """
        Atomically claims undelivered or stale outbox entries eligible for (re-)delivery
        using a PostgreSQL transaction with SELECT ... FOR UPDATE OF o SKIP LOCKED.
        Joins yorvyn_jobs so active PROCESSING jobs never burn outbox attempts.
        """
        async def _claim():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                async with conn.transaction():
                    now_ts = time.time()
                    stale_cutoff = now_ts - stale_after_seconds
                    claim_until = now_ts + claim_lease_seconds
                    rows = await conn.fetch("""
                        SELECT o.outbox_id::text, o.job_id, o.tenant_id, o.event_type, o.payload,
                               o.priority, o.created_at, o.deliver_after, o.delivered_at,
                               o.delivery_attempts, o.max_delivery_attempts, o.redis_message_id,
                               o.status, j.current_state AS job_current_state
                        FROM yorvyn_job_outbox o
                        JOIN yorvyn_jobs j ON j.job_id = o.job_id
                        WHERE j.current_state IN ('CREATED', 'SUBMITTED', 'QUEUED')
                          AND o.delivery_attempts < o.max_delivery_attempts
                          AND o.status != 'EXHAUSTED'
                          AND o.deliver_after <= $1
                          AND (
                              o.delivered_at IS NULL
                              OR (o.delivered_at IS NOT NULL AND o.acknowledged_at IS NULL AND o.delivered_at < $2)
                          )
                        ORDER BY o.priority ASC, o.created_at ASC
                        LIMIT $3
                        FOR UPDATE OF o SKIP LOCKED
                    """, now_ts, stale_cutoff, limit)
                    results = []
                    for row in rows:
                        entry = dict(row)
                        p = entry["payload"]
                        entry["payload"] = json.loads(p) if isinstance(p, str) else dict(p)
                        entry["payload"].setdefault("event_id", entry["outbox_id"])
                        entry["delivery_attempts"] = int(entry["delivery_attempts"] or 0) + 1
                        results.append(entry)
                    if results:
                        ids = [r["outbox_id"] for r in results]
                        await conn.execute("""
                            UPDATE yorvyn_job_outbox
                            SET delivery_attempts = delivery_attempts + 1,
                                deliver_after = $2,
                                claimed_by = $3,
                                claimed_at = $4
                            WHERE outbox_id::text = ANY($1::text[])
                        """, ids, claim_until, dispatcher_id, now_ts)
                    return results
            finally:
                await conn.close()
        return self._run_async(_claim())

    def mark_outbox_delivered(
        self,
        outbox_id: Optional[str] = None,
        redis_message_id: str = "delivered",
        job_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> None:
        """Mark an outbox entry as successfully delivered to Redis by outbox_id or job_id/event_type."""
        async def _mark():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                now_ts = time.time()
                if outbox_id:
                    await conn.execute("""
                        UPDATE yorvyn_job_outbox
                        SET delivered_at = $2, redis_message_id = $3, status = 'DELIVERED', last_error = NULL
                        WHERE outbox_id = $1::uuid
                    """, outbox_id, now_ts, redis_message_id)
                elif job_id and event_type:
                    await conn.execute("""
                        UPDATE yorvyn_job_outbox
                        SET delivered_at = $3, redis_message_id = $4, status = 'DELIVERED', last_error = NULL
                        WHERE job_id = $1 AND event_type = $2
                    """, job_id, event_type, now_ts, redis_message_id)
                elif job_id:
                    await conn.execute("""
                        UPDATE yorvyn_job_outbox
                        SET delivered_at = $2, redis_message_id = $3, status = 'DELIVERED', last_error = NULL
                        WHERE job_id = $1 AND delivered_at IS NULL
                    """, job_id, now_ts, redis_message_id)
            finally:
                await conn.close()
        self._run_async(_mark())

    def record_outbox_delivery_failure(
        self,
        outbox_id: str,
        error_message: str,
        base_backoff_seconds: float = 2.0,
        max_backoff_seconds: float = 60.0,
    ) -> Dict[str, Any]:
        """Record a failed Redis delivery attempt with bounded exponential backoff."""
        async def _fail():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                async with conn.transaction():
                    row = await conn.fetchrow("""
                        SELECT delivery_attempts, max_delivery_attempts, job_id
                        FROM yorvyn_job_outbox
                        WHERE outbox_id = $1::uuid
                        FOR UPDATE
                    """, outbox_id)
                    if not row:
                        return {"outbox_id": outbox_id, "exhausted": False, "attempts": 0}
                    attempts = int(row["delivery_attempts"] or 1)
                    max_attempts = int(row["max_delivery_attempts"] or 5)
                    exhausted = attempts >= max_attempts
                    delay = min(base_backoff_seconds * (2 ** max(0, attempts - 1)), max_backoff_seconds)
                    next_ts = time.time() + delay
                    new_status = "EXHAUSTED" if exhausted else "PENDING"
                    await conn.execute("""
                        UPDATE yorvyn_job_outbox
                        SET deliver_after = $2,
                            last_error = $3,
                            status = $4
                        WHERE outbox_id = $1::uuid
                    """, outbox_id, next_ts, str(error_message)[:1000], new_status)
                    return {
                        "outbox_id": outbox_id,
                        "job_id": row["job_id"],
                        "attempts": attempts,
                        "max_attempts": max_attempts,
                        "exhausted": exhausted,
                        "deliver_after": next_ts,
                        "backoff_seconds": delay,
                        "status": new_status,
                    }
            finally:
                await conn.close()
        return self._run_async(_fail())

    def reconcile_terminal_outbox_entries(self) -> int:
        """Mark outbox entries for already-completed/terminal jobs as acknowledged."""
        async def _reconcile():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                now_ts = time.time()
                res = await conn.execute("""
                    UPDATE yorvyn_job_outbox o
                    SET acknowledged_at = COALESCE(o.acknowledged_at, $1),
                        delivered_at = COALESCE(o.delivered_at, $1),
                        status = 'ACKNOWLEDGED'
                    FROM yorvyn_jobs j
                    WHERE o.job_id = j.job_id
                      AND j.current_state IN ('COMPLETED', 'CANCELLED', 'DEAD_LETTERED')
                      AND o.acknowledged_at IS NULL
                """, now_ts)
                try:
                    return int(str(res).split()[-1])
                except Exception:
                    return 0
            finally:
                await conn.close()
        return self._run_async(_reconcile())

    def mark_outbox_acknowledged(self, job_id: str) -> None:
        """Mark outbox entries for a job as fully acknowledged (worker processed/completed)."""
        async def _ack():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                now_ts = time.time()
                await conn.execute("""
                    UPDATE yorvyn_job_outbox
                    SET acknowledged_at = $2,
                        delivered_at = COALESCE(delivered_at, $2),
                        status = 'ACKNOWLEDGED'
                    WHERE job_id = $1 AND acknowledged_at IS NULL
                """, job_id, now_ts)
            finally:
                await conn.close()
        self._run_async(_ack())

    def delete_outbox_entry(self, job_id: str) -> None:
        """Delete all outbox entries for a job (used by compensation)."""
        async def _del():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                await conn.execute("DELETE FROM yorvyn_job_outbox WHERE job_id = $1", job_id)
            finally:
                await conn.close()
        self._run_async(_del())

    def load_outbox_entry(self, job_id: str, event_type: str = "JOB_QUEUED") -> Optional[Dict[str, Any]]:
        """Load a specific outbox entry by job_id and event_type."""
        async def _load():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                row = await conn.fetchrow("""
                    SELECT outbox_id::text, job_id, tenant_id, event_type, payload,
                           priority, created_at, deliver_after, delivered_at,
                           delivery_attempts, max_delivery_attempts, redis_message_id,
                           acknowledged_at, status, last_error, claimed_by, claimed_at
                    FROM yorvyn_job_outbox
                    WHERE job_id = $1 AND event_type = $2
                """, job_id, event_type)
                if not row:
                    return None
                entry = dict(row)
                p = entry["payload"]
                entry["payload"] = json.loads(p) if isinstance(p, str) else dict(p)
                return entry
            finally:
                await conn.close()
        return self._run_async(_load())

    def load_latest_outbox_entry(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Load the most recent outbox entry for a job_id."""
        async def _load():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                row = await conn.fetchrow("""
                    SELECT outbox_id::text, job_id, tenant_id, event_type, payload,
                           priority, created_at, deliver_after, delivered_at,
                           delivery_attempts, max_delivery_attempts, redis_message_id,
                           acknowledged_at, status, last_error, claimed_by, claimed_at
                    FROM yorvyn_job_outbox
                    WHERE job_id = $1
                    ORDER BY created_at DESC
                    LIMIT 1
                """, job_id)
                if not row:
                    return None
                entry = dict(row)
                p = entry["payload"]
                entry["payload"] = json.loads(p) if isinstance(p, str) else dict(p)
                return entry
            finally:
                await conn.close()
        return self._run_async(_load())

    def get_outbox_stats(self) -> Dict[str, Any]:
        """Return operational observability counts for the transactional outbox."""
        async def _stats():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                now_ts = time.time()
                row = await conn.fetchrow("""
                    SELECT
                        COUNT(*) FILTER (WHERE delivered_at IS NULL AND status != 'EXHAUSTED') AS pending_count,
                        COUNT(*) FILTER (WHERE delivered_at IS NOT NULL AND acknowledged_at IS NULL) AS delivered_unacked_count,
                        COUNT(*) FILTER (WHERE acknowledged_at IS NOT NULL OR status = 'ACKNOWLEDGED') AS acknowledged_count,
                        COUNT(*) FILTER (WHERE status = 'EXHAUSTED' OR (delivered_at IS NULL AND delivery_attempts >= max_delivery_attempts)) AS exhausted_count,
                        MIN(created_at) FILTER (WHERE delivered_at IS NULL AND status != 'EXHAUSTED') AS oldest_pending_created_at
                    FROM yorvyn_job_outbox
                """)
                oldest_age = round(now_ts - float(row["oldest_pending_created_at"]), 2) if row and row["oldest_pending_created_at"] else 0.0
                return {
                    "pending_count": int(row["pending_count"] or 0) if row else 0,
                    "delivered_unacked_count": int(row["delivered_unacked_count"] or 0) if row else 0,
                    "acknowledged_count": int(row["acknowledged_count"] or 0) if row else 0,
                    "exhausted_count": int(row["exhausted_count"] or 0) if row else 0,
                    "oldest_pending_age_seconds": oldest_age,
                }
            finally:
                await conn.close()
        return self._run_async(_stats())

    def load_job(self, job_id: str) -> Optional[UnifiedJobState]:
        async def _load():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                row = await conn.fetchrow("SELECT * FROM yorvyn_jobs WHERE job_id = $1", job_id)
                if not row:
                    return None
                data = dict(row)
                data["history"] = json.loads(data["history"]) if isinstance(data["history"], str) else (data["history"] or [])
                data["attempts"] = json.loads(data["attempts"]) if isinstance(data["attempts"], str) else (data["attempts"] or [])
                return UnifiedJobState.from_dict(data)
            finally:
                await conn.close()

        return self._run_async(_load())

    def mutate_job(
        self,
        job_id: str,
        mutation_fn: Callable[[UnifiedJobState], Tuple[bool, str]]
    ) -> Tuple[bool, str, Optional[UnifiedJobState]]:
        async def _mutate():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                async with conn.transaction():
                    row = await conn.fetchrow("SELECT * FROM yorvyn_jobs WHERE job_id = $1 FOR UPDATE", job_id)
                    if not row:
                        return False, f"Job {job_id} not found in database", None
                    data = dict(row)
                    data["history"] = json.loads(data["history"]) if isinstance(data["history"], str) else (data["history"] or [])
                    data["attempts"] = json.loads(data["attempts"]) if isinstance(data["attempts"], str) else (data["attempts"] or [])
                    job = UnifiedJobState.from_dict(data)

                    success, msg = mutation_fn(job)
                    if success:
                        d = job.to_dict()
                        await conn.execute("""
                            UPDATE yorvyn_jobs
                            SET current_state = $1,
                                claimed_by_worker = $2,
                                lease_generation = $3,
                                lease_expires_at = $4,
                                retry_count = $5,
                                updated_at = $6,
                                completed_at = $7,
                                asset_path = $8,
                                asset_sha256 = $9,
                                history = $10::jsonb,
                                attempts = $11::jsonb
                            WHERE job_id = $12
                        """,
                        d["current_state"], d["claimed_by_worker"], d["lease_generation"],
                        d["lease_expires_at"], d["retry_count"], d["updated_at"],
                        d["completed_at"], d["asset_path"], d["asset_sha256"],
                        json.dumps(d["history"]), json.dumps(d["attempts"]), job_id
                        )
                    return success, msg, job
            finally:
                await conn.close()

        return self._run_async(_mutate())

    def register_idempotency(
        self,
        tenant_id: str,
        idempotency_key: str,
        canonical_fingerprint: str,
        job_id: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        async def _reg():
            import asyncpg
            conn = await asyncpg.connect(self.dsn)
            try:
                async with conn.transaction():
                    res = await conn.execute("""
                        INSERT INTO yorvyn_idempotency_keys (
                            tenant_id, idempotency_key, canonical_fingerprint, job_id, registered_at
                        ) VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
                    """, tenant_id, idempotency_key, canonical_fingerprint, job_id, time.time())

                    if res == "INSERT 0 1":
                        record = {
                            "tenant_id": tenant_id,
                            "idempotency_key": idempotency_key,
                            "canonical_fingerprint": canonical_fingerprint,
                            "job_id": job_id,
                            "registered_at": time.time()
                        }
                        return True, job_id, record

                    existing = await conn.fetchrow("""
                        SELECT * FROM yorvyn_idempotency_keys
                        WHERE tenant_id = $1 AND idempotency_key = $2
                    """, tenant_id, idempotency_key)

                    if existing["canonical_fingerprint"] != canonical_fingerprint:
                        raise IdempotencyConflictException(
                            f"Idempotency key '{idempotency_key}' for tenant '{tenant_id}' was previously "
                            f"registered with different request parameters (existing: {existing['canonical_fingerprint'][:12]}, "
                            f"new: {canonical_fingerprint[:12]})"
                        )
                    return False, existing["job_id"], dict(existing)
            finally:
                await conn.close()

        return self._run_async(_reg())
