# YORVYN — Transactional Outbox, Redis Delivery Recovery & Lifecycle Hardening

**Task ID:** DURABLE-JOB-FIX-002  
**Baseline Commit:** `7139fc7eea4e1f890e28da9140db2e8550081267`  
**Recorded:** 2026-11-26  
**Depends On:** DURABLE-JOB-FIX-001

---

## Objective

Extend DURABLE-JOB-FIX-001 to close the crash windows between PostgreSQL commits and Redis Streams delivery across initial submission, transient Redis outages, retries, worker restarts, and duplicate deliveries, while preserving PostgreSQL state-machine invariants, lease-generation fencing, and idempotency guarantees.

---

## Gaps Identified in Initial Audit

1. **Initial Enqueue Crash Window**: If the process crashed after `create_job_atomic` committed `QUEUED` and before `_redis_broker.enqueue` completed, `recover_stranded_jobs` previously closed `QUEUED` jobs as `DEAD_LETTERED` instead of re-delivering them.
2. **Retry Crash Window**: `retry_job` previously transitioned `FAILED -> QUEUED` in PostgreSQL before calling `_redis_broker.enqueue`, leaving a crash window where a retried `QUEUED` job had no delivery record.
3. **Concurrent Idempotency Insert Race**: `create_job_atomic` used `SELECT ... FOR UPDATE` before `INSERT` on `yorvyn_idempotency_keys`; simultaneous identical requests acquired no lock on a missing row and hit `UniqueViolationError`.
4. **Staging Worker Claim & Fencing**: `staging_worker.py`'s `redis_streams_consumer_loop` previously ignored `mutate_job` return status and did not short-circuit terminal or actively-leased duplicate deliveries.
5. **Compensation Safety Hardening**: Compensation needed strict checks against `lease_generation == 0`, `retry_count == 0`, ownership (`expected_user_id`, `expected_tenant_id`), terminal states, and exact `(job_id, tenant_id, idempotency_key)` deletion scoping.

---

## Architecture & Implementation

### 1. Additive Outbox Schema (`outbox_migration.sql` & `unified_state_machine.py`)
Created `yorvyn_job_outbox` (additive SQL only — zero existing tables or columns dropped):
- Columns: `outbox_id` (UUID PK), `job_id` (FK `yorvyn_jobs`), `tenant_id`, `event_type` (`JOB_QUEUED` | `JOB_RETRY`), `payload` (JSONB including `event_id` and `correlation_id`), `priority`, `created_at`, `deliver_after`, `delivered_at`, `delivery_attempts`, `max_delivery_attempts` (default 5), `redis_message_id`, `acknowledged_at`, `status` (`PENDING` | `DELIVERED` | `ACKNOWLEDGED` | `EXHAUSTED`), `last_error`, `claimed_by`, `claimed_at`.
- Partial indexes: `idx_outbox_undelivered`, `idx_outbox_unacked`, `idx_outbox_job_id`.

### 2. Atomic Transaction Boundaries (`unified_state_machine.py`)
- **`create_job_atomic`**: Uses atomic `INSERT INTO yorvyn_idempotency_keys ... ON CONFLICT DO NOTHING RETURNING job_id` + `FOR UPDATE` fallback (eliminating concurrent `UniqueViolationError`), inserts `yorvyn_jobs`, and inserts `yorvyn_job_outbox` (`event_type='JOB_QUEUED'`) inside the same ACID transaction.
- **`retry_job_atomic`**: Transitions `FAILED -> QUEUED` and upserts `yorvyn_job_outbox` (`event_type='JOB_RETRY'`) inside a single PostgreSQL transaction.
- **`claim_pending_outbox_entries`**: Runs inside `async with conn.transaction()` using `SELECT ... FOR UPDATE OF o SKIP LOCKED` joined with `yorvyn_jobs` (`current_state IN ('CREATED', 'SUBMITTED', 'QUEUED')`), preventing concurrent dispatchers from claiming overlapping rows or burning attempts on actively `PROCESSING` jobs.
- **`record_outbox_delivery_failure`**: Applies bounded exponential backoff (`min(2.0 * 2**(attempts-1), 60.0)`) and marks `status='EXHAUSTED'` when `delivery_attempts >= max_delivery_attempts`.
- **`mark_outbox_delivered` / `mark_outbox_acknowledged` / `reconcile_terminal_outbox_entries` / `get_outbox_stats`**: Track delivery correlation (`outbox_id` <-> `redis_message_id`), worker acknowledgement, terminal reconciliation, and observability metrics.

### 3. Compensation Safety Guards (`compensate_enqueue_failure`)
Returns `bool` and rejects compensation whenever:
- `job_id` does not exist
- `current_state` is in `TERMINAL_STATES` or not in `("CREATED", "SUBMITTED", "QUEUED")`
- `expected_state` does not match
- `lease_generation != 0` or `retry_count != 0` (protects claimed jobs and newer retries)
- `expected_user_id`, `expected_tenant_id`, or `expected_idempotency_key` does not match
- Scopes idempotency deletion strictly to `WHERE job_id = $1 AND tenant_id = $2 AND idempotency_key = $3`.

### 4. Lifecycle Integration (`job_manager.py`, `queue_broker.py`, `main.py`, `staging_worker.py`)
- **Deterministic temp paths**: Computed prior to `create_job_atomic` so the initial outbox row contains valid view paths immediately upon commit.
- **Transient Redis outage resilience**: On transient `enqueue` failure during `create_job` or `retry_job`, jobs stay `QUEUED` with a `PENDING` outbox row rather than failing or dead-lettering; deterministic backpressure (`QueueOverloadedException` / `ConcurrencyLimitExceededException`) still compensates cleanly.
- **Startup recovery & background dispatcher**: `recover_stranded_jobs()` invokes `_dispatch_outbox_pending()` first, preserves deliverable `QUEUED` jobs awaiting dispatch, and closes only jobs with missing inputs, exceeded timeout, or `EXHAUSTED` outbox rows. `main.py` starts and cleanly stops the background outbox dispatcher thread.
- **Effectively-once processing**: Redis stream messages carry `event_id` and `correlation_id`; both `_process_job` and `staging_worker.py` enforce DB state, `CLAIMED` mutex, and `lease_generation` fencing so duplicate Redis deliveries result in a single completion and publication.
- **Observability**: `GarmentJobManager.get_health_status()` exposes `"outbox"` metrics (`pending_count`, `delivered_unacked_count`, `acknowledged_count`, `exhausted_count`, `oldest_pending_age_seconds`).

---

## Verification Evidence

All tests ran against live local PostgreSQL (`yorvyn_persistence`) and Redis (`127.0.0.1:6379`) after final edits:

```text
py_compile (5 modified backend modules)                                   -> exit code 0
backend/tests/test_durable_job_outbox_fault_injection.py  (13 tests)      -> 13 passed
backend/tests/test_durable_job_publication_fix.py         (30 tests)      -> 30 passed
backend/tests/test_tenant_security.py                     (7 tests)       ->  7 passed
backend/tests/test_production_platform_phase_10.py        (20 tests)      -> 20 passed
backend/tests/test_garment_chat_edits.py                  (8 tests)       ->  8 passed
Total backend acceptance suite                            (78 tests)      -> 78 passed in 8.71s
Frontend production build (npm run build / tsc + vite)                    -> exit code 0 (5.71s)
```
