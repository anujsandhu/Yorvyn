# YORVYN — DURABLE-JOB-FIX-002-E2E Final Live Acceptance Report

**Task ID:** `DURABLE-JOB-FIX-002-E2E`  
**Baseline HEAD:** `7139fc7eea4e1f890e28da9140db2e8550081267`  
**Recorded:** 2026-11-26  

---

## Executive Acceptance Classification

| Stage / Requirement | Classification | Summary |
|---|---|---|
| Stage 1: Environment Audit | **VERIFIED** | Audited live PostgreSQL 16.14, Redis 6379, PID 60006 (`staging_worker`), PID 34850 (`run.py` pre-fix server), PID 34942 (`vite`). Isolated E2E stack launched without disrupting running processes or existing assets. |
| Stage 2: Live Authenticated Wardrobe Reconstruction | **VERIFIED** | Authenticated Chromium Wardrobe upload of `wm_00_jacket_denim.jpg` (`job_dcc9ac3ac423`) completed full PostgreSQL -> Outbox -> Redis -> Worker -> Fenced GLB Publication -> Three.js WebGL preview -> Save to Wardrobe -> Browser Refresh recovery. |
| Stage 3: Negative Authentication | **PASSED WITH LIMITATIONS** | Unauthenticated `/api/garments/multiview-reconstruct` and `/api/fashion/garment-gen/jobs` returned HTTP 401 with 0 DB jobs, 0 outbox rows, 0 Redis stream additions. (`/api/garments/multiview-identify` still permits guest inspection returning 200 without creating any job or outbox row.) |
| Stage 4: Isolated Redis Outage Recovery | **VERIFIED** | Stopped isolated `redis-server`, submitted `job_1d7fd3120938` (`current_stage: "Queued in durable outbox; awaiting Redis delivery"`, PG `QUEUED`, outbox `PENDING`), restarted Redis, background outbox dispatcher delivered (`attempts: 1`), worker published GLB and acknowledged outbox (`ACKNOWLEDGED`). |
| Stage 5: Worker Restart & Fencing | **VERIFIED** | Mid-processing crash (`job_s5_restart_2014f3d2`, `gen=1`) recovered by `recover_stranded_jobs()` -> `FAILED`; `retry_job_atomic` queued `gen=2` with `JOB_RETRY` outbox; stale worker `worker_1` (`gen=1`) rejected on `VALIDATING` and `commit_completion`; active worker `worker_2` (`gen=2`) published and committed. |
| Stage 6: Retry & Idempotency | **VERIFIED** | Identical resubmission reused `job_2c168dfe91df` (200); conflicting subcategory on same key returned HTTP 409 (`IDEMPOTENCY_CONFLICT`); `retry_job_atomic` + compensation safety verified in live PG tests. |
| Stage 7: DB & Outbox Integrity Audit | **VERIFIED** | Live outbox tables have 0 pending, 0 exhausted, 0 unacked delivered, 0 stale claimed, 0 terminal-with-pending. Pre-existing historical `CREATED`/`FAILED` rows from prior phases cleanly documented without destructive edits. |
| Stage 8: Performance & Fail-Fast Accounting | **VERIFIED** | Live atomic PG TX `22.86 ms`, Redis enqueue `2.35 ms`, total reconstruction `5093.9 ms`, nonexistent-job worker rejection `226.23 ms` (0s 3D compute wasted). |
| Stage 9: Regression & Frontend Build | **VERIFIED** | 104 backend tests passed (`7.27s`), 6 Vitest modal handoff tests passed, `tsc && vite build` exited `0` (`5.65s`). |

---

## 1. Environment Configuration Summary (Stage 1)

- **PostgreSQL:** `PostgreSQL 16.14` on `127.0.0.1:5432`, database `yorvyn_persistence`, user `postgres`.
  - Pre-E2E tables: `yorvyn_jobs` (60 rows), `yorvyn_idempotency_keys` (61 rows), `yorvyn_job_outbox` (0 rows, indexes `yorvyn_job_outbox_pkey`, `idx_outbox_undelivered`, `idx_outbox_unacked`, `idx_outbox_job_id`, unique constraint `outbox_job_id_event_type_key`), `yorvyn_job_attempts` (0 rows), `yorvyn_garment_evidence_specs` (2 rows).
- **Pre-existing Running Processes (Untouched):**
  - `PID 60006`: `staging_worker.py` on `127.0.0.1:8088` (started `Mon Nov 23 21:25:00`, Redis `127.0.0.1:6379` `yorvyn:stream:jobs`, left untouched per constraint).
  - `PID 34850`: `run.py` on `127.0.0.1:8002` (started `Wed Nov 25 22:17:17`, running pre-DURABLE-JOB-FIX-001/002 code without `"outbox"` health telemetry).
  - `PID 34942`: `vite --port 5174` (left untouched).
- **Live E2E Stack Used for Stages 2–8:**
  - `uvicorn backend.app.main:app` on loopback ephemeral port running workspace code + background outbox dispatcher.
  - Real PostgreSQL `yorvyn_persistence` (`localhost:5432`).
  - Dedicated isolated `redis-server` on loopback ephemeral port (preventing PID 60006 pre-fix worker interference and allowing live Stage 4 outage testing).
  - Dedicated `vite` dev server + loopback mock Supabase Auth server (`HS256` signed JWTs, `SUPABASE_URL=""` offline backend fallback for Supabase REST).
  - Isolated `YORVYN_GARMENT_ASSET_DIR` and `YORVYN_GARMENT_TEMP_DIR` temp paths so existing wardrobe assets were untouched.

---

## 2. Bugs Found & Repaired During Live E2E Execution

1. **`PhotoTo3DGarmentModal.tsx` GLB Asset Auth (`401` Prevention):** `THREE.GLTFLoader().load(result.glb_url)` previously bypassed Axios auth interceptors when loading `/api/fashion/garment-gen/assets/{job_id}/garment.glb`. Updated to fetch protected `/api/fashion/*` GLBs via `api.get(..., { responseType: 'arraybuffer' })` + `loader.parse(...)` and expose `canvas[data-garment-loaded="true"]`.
2. **`PhotoTo3DGarmentModal.tsx` Async Preprocessing Hash Mismatch (`409` Observed in First Live Browser Run):** Uploading `wm_00_jacket_denim.jpg` and clicking `Reconstruct 3D Garment` before background WebP preprocessing completed caused `multiviewIdentify` to record the JPEG SHA-256 while `handleConfirmEvidenceAndReconstruct` later submitted the WebP, failing with `Source image bytes do not match evidence record 'wm_00_jacket_denim.jpg'`. Fixed by snapshotting `identifiedViewFilesRef.current` at identification time.
3. **`PhotoTo3DGarmentModal.tsx` Browser Refresh Job Recovery:** Persisted active `jobId` per authenticated user (`yorvyn_photo3d_active_job_${uid}`) so refreshing restores completed/in-progress durable jobs from PostgreSQL.
4. **`AvatarStudio.tsx` Wardrobe Route & Reload Persistence:** Fixed `closeTrayWorkflow()` navigating `/wardrobe` back to `/` on Save to My Wardrobe, and added `[user?.id]` wardrobe reload effect.
5. **Redis Stream `event_id` Correlation & Route `PermissionError` Mapping:** Pre-generated `event_id` in `create_job` so Redis Stream `event_id` matches `yorvyn_job_outbox.outbox_id` on fast-path enqueue; mapped `PermissionError` to HTTP `403` (`ENTITLEMENT_QUOTA_EXCEEDED`) instead of `500` in `garment_identification_routes.py` and `garment_generation_routes.py`.

---

## 3. Stage 2 — Live Authenticated Reconstruction Evidence

- **Test User:** `usr_e2e_e38908ef9e`
- **Canonical Job ID:** `job_dcc9ac3ac423`
- **Source Photo:** `data/datasets/phase_13_6_real_photos/wm_00_jacket_denim.jpg`
- **PostgreSQL (`yorvyn_jobs`):**
  - `current_state`: `COMPLETED`
  - `user_id` / `tenant_id`: `usr_e2e_e38908ef9e` / `usr_e2e_e38908ef9e`
  - `idempotency_key`: `mv_garment_381b948c_e9f9c3acc3cf`
  - `lease_generation`: `1`
  - `history` transitions: `CREATED -> QUEUED -> CLAIMED -> PROCESSING -> VALIDATING -> PUBLISHING -> COMPLETED`
- **Outbox (`yorvyn_job_outbox`):**
  - `outbox_id`: `f597c364-8e78-4ea4-9a3b-4736c75770a2`
  - `event_type`: `JOB_QUEUED`
  - `status`: `ACKNOWLEDGED` (`delivery_attempts: 0`, `delivered_at: 1795673943.096031`, `acknowledged_at: 1795673768.048173` -> `1795673948.048173`)
  - `redis_message_id`: `1795673943086-0`
- **Redis Stream (`yorvyn:stream:jobs`):**
  - `redis_id`: `1795673943086-0`
  - `job_id`: `job_dcc9ac3ac423`
  - `event_id`: `f597c364-8e78-4ea4-9a3b-4736c75770a2` (matches `outbox_id`)
  - `correlation_id`: `corr_7849a9bc3f9f`
- **Publication & Checksum:**
  - Canonical GLB size: `1,580,672` bytes (`job_dcc9ac3ac423_gen1.glb` & `job_dcc9ac3ac423.glb` both present)
  - SHA-256: `4b2d60cc12f59891ba52b8fa1ea954f60d7a5f0cf3228b3f616954c32af1f73a` (matches PostgreSQL `asset_sha256` bit-for-bit)
  - `mesh_structure`: `PASSED`, `reconstruction_provenance`: `hybrid_neural_procedural`
- **Frontend Browser Verification (`browser_wardrobe_e2e.cjs`):**
  - `pageErrors`: `[]`
  - `identifyStatus`: `200`, `reconstructStatus`: `200`, `glbDownloadStatus`: `200`, `saveStatus`: `200`
  - `refreshRecoveredWardrobeItem`: `true`, `refreshRecoveredPreview`: `true`
  - Screenshots captured in artifact directory `screenshots/`:
    - `01_wardrobe_authenticated.png`
    - `02_evidence_review.png`
    - `03_reconstruction_processing.png`
    - `04_3d_preview_loaded.png`
    - `05_saved_in_wardrobe.png`
    - `06_after_browser_refresh.png`

---

## 4. Negative Auth, Redis Outage, Worker Restart, Retry & Idempotency

### Stage 3 — Negative Authentication
- `POST /api/garments/multiview-reconstruct` (`user_id="default_user"`, no Bearer): **HTTP 401**
- `POST /api/garments/multiview-reconstruct` (`user_id=<test_uid>`, no Bearer): **HTTP 401**
- `POST /api/fashion/garment-gen/jobs` (`user_id="default_user"`, no Bearer): **HTTP 401**
- PostgreSQL `banned_user_jobs`: `0`, `recent_jobs`: `0`, `recent_outbox`: `0`; Redis `XLEN` unchanged (`1 -> 1`).
- Note: `POST /api/garments/multiview-identify` returned `200` as guest-accessible identification (creates no job, outbox, or Redis work).

### Stage 4 — Isolated Redis Outage Recovery (`job_1d7fd3120938`)
- While `redis-server` stopped: `POST /api/garments/multiview-reconstruct` returned HTTP `200` with truthful stage `"Queued in durable outbox; awaiting Redis delivery"`; PostgreSQL `current_state == "QUEUED"`, outbox `status == "PENDING"`, `delivered_at == null`.
- After `redis-server` restarted: background outbox dispatcher delivered (`delivery_attempts: 1`, `redis_message_id: 1795673965829-0`), worker completed reconstruction (`10590.74 ms` total recovery-to-complete), published GLB (`sha256: b76fc2d39682cd5d3281e18029f478b8a56bda8f5c9733d572477971499074c1`), and outbox reached `ACKNOWLEDGED`.

### Stage 5 — Worker Restart & Fencing (`job_s5_restart_2014f3d2`)
- Worker 1 (`gen=1`) claimed and entered `PROCESSING`; simulated crash -> lease expired -> `recover_stranded_jobs()` recovered `1` job (`FAILED`).
- `retry_job_atomic` transitioned `FAILED -> QUEUED` and created `JOB_RETRY` outbox (`c37f2cc1-2b19-44f6-b756-1982cd04610f`); Worker 2 claimed (`gen=2`).
- Stale `worker_1` (`gen=1`) rejected on both `VALIDATING` (`"Fencing token rejected: Worker worker_1 provided stale lease generation 1 (current active generation is 2)"`) and `commit_completion` (`"Commit rejected: Stale lease generation 1 (active is 2)"`).
- Active `worker_2` (`gen=2`) published & committed `COMPLETED` (`asset_sha256: 4b2d60cc12f59891ba52b8fa1ea954f60d7a5f0cf3228b3f616954c32af1f73a`).

### Stage 6 — Live Retry & Idempotency (`job_2c168dfe91df`)
- Identical request with `idempotency_key`: reused `job_2c168dfe91df` (`HTTP 200`, `same_job_reused: true`).
- Changed `final_subcategory="blazer"` with same `idempotency_key`: rejected **HTTP 409** (`code: "IDEMPOTENCY_CONFLICT"`).

---

## 5. Stage 7 — PostgreSQL & Outbox Integrity Audit

- `pending_outbox_entries`: **0**
- `exhausted_outbox_entries`: **0**
- `unacked_delivered_entries`: **0**
- `stale_claimed_entries`: **0**
- `terminal_jobs_with_pending_events`: **0**
- `non_terminal_jobs`: **23** historical pre-outbox rows from prior test runs (`12 FAILED`, `11 CREATED` without outbox: `job_lock_*` x10 + `job_bdfa7076afd8`, timestamps `1795415699..1795627462`). Zero `QUEUED` or `IN_FLIGHT` jobs from DURABLE-JOB-FIX-002 remain unclosed or undelivered.

---

## 6. Stage 8 & 9 — Performance & Regression Verification

| Metric | Measured Value |
|---|---|
| PostgreSQL `create_job_atomic` + outbox TX | `22.86 ms` |
| Redis Streams `enqueue` (`XADD`) | `2.35 ms` |
| Live Wardrobe full reconstruction duration | `5093.9 ms` (`geometry_ms: 1341.81`, `evaluation_ms: 292.04`, `render_ms: 87.24`) |
| Redis outage submit latency | `68.2 ms` |
| Outbox outage recovery -> GLB completion | `10590.74 ms` |
| Nonexistent DB job fail-fast gate | `226.23 ms` (`Reconstruction has no durable job record for publication.`) |

- **Backend Regression Command (exit code `0`, 104 passed in `7.27s`):**
  ```bash
  YORVYN_DISABLE_SEGFORMER=1 YORVYN_DISABLE_COMPONENT_CLIP=1 backend/venv/bin/pytest \
    backend/tests/test_durable_job_outbox_fault_injection.py \
    backend/tests/test_durable_job_publication_fix.py \
    backend/tests/test_tenant_security.py \
    backend/tests/test_production_platform_phase_10.py \
    backend/tests/test_garment_chat_edits.py \
    backend/tests/test_phase16_intelligence.py -v --tb=short
  ```
- **Frontend Unit + Production Build (`exit code 0`):**
  - `npx vitest run src/components/__tests__/PhotoTo3DGarmentModalHandoff.test.tsx`: **6 passed**
  - `npm run build` (`tsc && vite build`): **exit code 0** (`5.65s`)

---

## 7. Remaining Blockers / Notes

1. Pre-existing long-running `run.py` (`PID 34850` on port `8002`) and `staging_worker.py` (`PID 60006` on port `8088` / Redis `6379`) remain active from before these fixes and were left untouched per constraints; restarting them in a controlled window will activate the new code on default ports `8002`/`8088`.
2. In-memory `WardrobeService` persists saved 3D wardrobe items across browser refreshes while the backend process stays alive, and `PhotoTo3DGarmentModal` restores durable PostgreSQL job status/GLB preview across refreshes; full database-backed `WardrobeService` persistence across backend restarts remains future scope.
3. External AI provider inference (Gemini/Groq/OpenRouter) and Cloudinary CDN upload ran in offline/local mode during this test.
