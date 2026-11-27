# YORVYN — Durable Job Publication Integrity Fix

**Task ID:** DURABLE-JOB-FIX-001  
**Baseline Commit:** `7139fc7eea4e1f890e28da9140db2e8550081267`  
**Recorded:** 2026-11-25

---

## Symptom

```
Reconstruction failed: Reconstruction has no durable job record for publication.
```

Observed in live Wardrobe / 3D Garment Reconstruction workflow with live log evidence:

```
2026-11-25 22:20:16,138 [ERROR] PostgreSQL job creation failed: Cannot create job job_6deca30d8e83:
  Invalid or unauthenticated user_id 'default_user'
POST /api/garments/multiview-reconstruct → 200  ← WRONG: should be 401
2026-11-25 22:20:37,373 [ERROR] Error processing job job_6deca30d8e83:
  Reconstruction has no durable job record for publication.
```

Live PostgreSQL query confirmed zero rows for `job_6deca30d8e83` while Redis held 50 entries.

---

## Root Causes (5 Compounding)

### RC-1: Frontend Missing Auth Tokens on Garment Routes
`fashionApi.ts` lines 309 and 345: `multiviewIdentify` and `multiviewReconstruct` called raw `axios.post('/api/garments/...')` instead of the auth-intercepted `api` instance, stripping `Authorization: Bearer <token>`. `PhotoTo3DGarmentModal.tsx:774` sent no `userId` or `idempotencyKey`.

### RC-2: Backend `allow_guest=True` with Banned Identity Swallowed
`garment_identification_routes.py:627` used `allow_guest=True`, causing `effective_user_id = 'default_user'`. `UnifiedJobState.__init__` rejected it via `BANNED_IDENTITIES` with `TenantSecurityViolationException`, but `job_manager.py:391` swallowed it with a bare `except Exception as pg_err: logger.error(...)` and continued.

### RC-3: Non-Atomic `create_job`: DB Failure → Redis Enqueue → 200 OK
`create_job` split `register_idempotency` (line 311) and `create_job` (line 377) across two sequential non-atomic calls and swallowed **both** exceptions. Result: job enqueued to Redis, `self._jobs[job_id]` populated, API returned `200 OK` — with zero PostgreSQL rows written.

### RC-4: Worker Silently Ran 21s of 3D Compute on Nonexistent Row  
`_process_job` lines 589–597 swallowed the `load_job` failure (`except Exception: pass`) and ran full segmentation/depth/mesh/texture/GLB export before crashing at the publication gate (line 938–939).

### RC-5: `retry_job` and `recover_stranded_jobs` Only In-Memory
`retry_job` only mutated `self._jobs` without DB transition. `recover_stranded_jobs` only scanned `self._jobs` (empty on restart) instead of PostgreSQL.

---

## Fixes Applied

### `unified_state_machine.py`
- Added **`create_job_atomic()`** — single ACID transaction: idempotency key registration + `yorvyn_jobs` insert, with orphan idempotency key cleanup. Returns `(is_new, UnifiedJobState)`.
- Added **`list_non_terminal_jobs()`** — queries PostgreSQL for all non-terminal rows for restart recovery.
- Added **`compensate_enqueue_failure()`** — rolls back a newly-created QUEUED job to `DEAD_LETTERED` and releases its idempotency reservation when Redis enqueue fails.

### `job_manager.py`
- Added `DurablePersistenceUnavailableError` (`code=DURABLE_JOB_PERSISTENCE_UNAVAILABLE`)
- Added `QueueEnqueueError` (`code=QUEUE_ENQUEUE_FAILED`)
- **`create_job`**: `create_job_atomic` called **before** temp file writes and Redis enqueue. `TenantSecurityViolationException` and `IdempotencyConflictException` propagate directly. DB failure → `DurablePersistenceUnavailableError`. Redis failure → `compensate_enqueue_failure` + `QueueEnqueueError`. Phantom cached `job_id` fixed to load from persisted COMPLETED DB row.
- **`_process_job`**: Mandatory DB presence gate pre-compute. Owner/tenant mismatch check. Terminal state skip. Atomic `CLAIMED/PROCESSING` with `active_lease_gen`. Strict `VALIDATING/PUBLISHING` transitions with `lease_generation` fencing. Fenced publication. `commit_completion` with lease_gen check. Redis `acknowledge`. `finally` block closes PostgreSQL non-terminal states to `FAILED` via `active_lease_gen`.
- **`retry_job`**: Loads persisted DB state. Enforces DB `FAILED` state and `retry_count < max_retries`. Transitions `FAILED→QUEUED` in DB **first**, then Redis enqueue. Returns `None` when temp files purged (preserves `test_garment_chat_edits` contract).
- **`recover_stranded_jobs`**: DB-backed recovery via `list_non_terminal_jobs`. `CLAIMED/PROCESSING/VALIDATING/PUBLISHING` → `FAILED`. Orphaned `QUEUED` → `DEAD_LETTERED`. Artifact reconciliation via `startup_reconciliation`.

### `garment_identification_routes.py`
- `allow_guest=False`. HTTP `401` on `TenantSecurityViolationException`, `409` on `IdempotencyConflictException`, `429` on queue limits, `503` on `DurablePersistenceUnavailableError`/`QueueEnqueueError`.

### `garment_generation_routes.py`
- Same structured error mapping in `create_generation_job`.

### `fashionApi.ts`
- Added `garmentsApi` (auth-intercepted Axios instance for `/api/garments/*`).
- Added `buildStructuredApiError()` helper extracting `{ message, code, retryable, status }` from structured `detail`.
- `multiviewIdentify`, `getGarmentEvidence`, `validateGarmentSpecification`, `multiviewReconstruct` switched to `garmentsApi`.

### `AuthContext.tsx`
- Added `useOptionalAuth()` export (non-throwing version for modals not inside `AuthProvider`).

### `PhotoTo3DGarmentModal.tsx`
- `useOptionalAuth()` for `user?.id` passed to `multiviewIdentify` and `multiviewReconstruct`.
- `submissionInFlightRef` duplicate-click guard.
- `idempotencyKeyRef` per-evidence key (cleared on `409` conflict).
- `errorMeta` state: `{ retryable, code, status, failedJobId }`.
- `handleRetryFailedSubmission`: retries via `retryGarmentGenJob(failedJobId)` when retryable, else falls back to re-identify.
- Polling handles `timed_out` status. Failed jobs return to `evidence_review` step with retryable error banner.

---

## Lifecycle Invariants Now Enforced

| # | Invariant | Enforced By |
|---|-----------|-------------|
| 1 | PostgreSQL row **before** Redis enqueue | `create_job_atomic` + sequential order in `create_job` |
| 2 | API never returns 200 before DB commit | Exception propagation from `create_job` |
| 3 | Redis carries canonical `job_id` | Explicit `job_id` from `create_job_atomic` result |
| 4 | Workers load DB row **before** 3D compute | `_process_job` pre-compute gate |
| 5 | Publication requires PUBLISHING + lease fencing | `active_lease_gen` checks throughout |
| 6 | Retry increments DB `retry_count` before requeue | `retry_job` DB-first transition |
| 7 | Restart recovery covers DB non-terminal rows | `list_non_terminal_jobs` + `compensate` |
| 8 | Duplicate request returns same persisted job | `create_job_atomic` idempotency |
| 9 | Payload mismatch raises 409, not silently re-queued | `IdempotencyConflictException` propagation |
| 10 | Banned identities rejected at API layer | `allow_guest=False` + 401 routing |

---

## Test Evidence

```
backend/tests/test_durable_job_publication_fix.py  → 30 passed in 4.17s
backend/tests/test_tenant_security.py              →  7 passed
backend/tests/test_production_platform_phase_10.py → 20 passed
backend/tests/test_garment_chat_edits.py           →  8 passed
frontend build (tsc + vite)                        →  exit code 0, built in 7.06s
```

7 pre-existing failures in `test_phase_12_3_2_remediation.py` and `test_production_platform_phase_11.py` are confirmed pre-existing on baseline commit (verified by `git stash` test run) and are unrelated to these changes.
