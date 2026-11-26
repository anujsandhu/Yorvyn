# YORVYN — Phase 17.6 Engineering Report
## Universal Performance Engine, Multi-Layer Caching & Intelligent Asset Delivery

**Date:** 2026-11-26  
**Branch:** `release/stabilize-17.4`  
**Overall Acceptance Status:** Unit & Integration Verified (Live Redis caching + Vite build + SW/CDN rules + ETag/GZip verified; live CDN header verification & PostgreSQL `EXPLAIN ANALYZE` against production traffic remain deployment-dependent)

---

## 1. Initial Performance Baseline

Observed prior to Phase 17.6 changes:
- **Entry Bundle:** `index-*.js` measured `1,109.20 kB` (`311.13 kB` gzip) with `ort-wasm-simd-threaded.jsep-*.wasm` at `29,520.97 kB`.
- **Service Worker (`frontend/public/sw.js`):** Cached **every HTTP 200 GET response** under `yorvyn-v3`, including `/api/*` responses (risking stale or private user data leakage across requests).
- **CDN Headers (`firebase.json`):** Cached `*.js/css/woff2/woff/ttf`, omitted explicit `no-cache` on `/index.html`, omitted `private, no-store` on `/api/**`, and omitted SWR policies on public `/items/**` and `/ara-assets/**`.
- **Frontend API & 3D Cache:** `fashionApi` had unbounded `responseCache` without hit/miss telemetry; `AuthContext.signOut()` and `deleteAccount()` did not invalidate in-memory API caches or private 3D GLBs in `Studio3DAssetManager`.
- **Backend HTTP & Application Caching:** No `GZipMiddleware` in `main.py`, no `ETag` / `Cache-Control` on `/api/billing/plans` or private `/api/fashion/garment-gen/assets/{job_id}/{filename}`, no unified Redis+L1 application cache, and missing composite index on `(user_id, current_state, updated_at DESC)` in `yorvyn_jobs`.

---

## 2. Existing Bottlenecks Addressed

1. Repeated un-compressed JSON payloads from FastAPI endpoints.
2. Re-downloading owned immutable GLBs (`/api/fashion/garment-gen/assets/{job_id}/garment.glb`) on repeat studio views due to missing private `ETag` / `304` handling.
3. Missing stampede protection and shared Redis L2 cache on reusable backend reads and deterministic AI computations.
4. Monolithic frontend entry chunk containing React + ONNX + MediaPipe code without dedicated vendor chunk boundaries.
5. Account switch / sign-out leaving stale user API entries and `/api/` GLBs in browser memory.

---

## 3. Implemented Cache Layers

1. **Browser & HTTP Transport Layer:**
   - Added `GZipMiddleware(minimum_size=500)` in [main.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/main.py).
   - Added `ETag` + `If-None-Match` (`304 Not Modified`) + `Cache-Control: public, max-age=300, stale-while-revalidate=600` on `/api/billing/plans` in [billing_routes.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/api/billing_routes.py).
   - Added `ETag` + `If-None-Match` (`304`) + `Cache-Control: private, max-age=3600` + `Vary: Authorization` on `/api/fashion/garment-gen/assets/{job_id}/{filename}` in [garment_generation_routes.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/api/garment_generation_routes.py).
2. **Service Worker / PWA Layer ([sw.js](file:///Users/anujsandhu/Projects/yorvyn/frontend/public/sw.js)):**
   - Upgraded to `yorvyn-static-v4` & `yorvyn-swr-v4`.
   - Enforces **Network Only** for `/api/`, `/auth/`, `/rest/v1/`, `/storage/v1/`, non-GET methods, and requests carrying `Authorization` headers.
   - Applies **Cache First** for content-hashed `/assets/*` & fonts, **Stale While Revalidate** for `/ara-assets/*` & `/items/*`, and **Network First + offline `/index.html` fallback** for navigations.
3. **CDN / Hosting Layer ([firebase.json](file:///Users/anujsandhu/Projects/yorvyn/firebase.json)):**
   - `/index.html`: `no-cache`; `/assets/**`: `public, max-age=31536000, immutable`; `/items/**` & `/ara-assets/**`: `public, max-age=86400, stale-while-revalidate=604800`; `/api/**`: `private, no-store`.
4. **Frontend API & Account Isolation Layer ([fashionApi.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/services/fashionApi.ts), [AuthContext.tsx](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/context/AuthContext.tsx)):**
   - Bounded LRU (`MAX_RESPONSE_CACHE_ENTRIES = 200`), single-flight request deduplication, hit/miss telemetry (`getApiCacheStats()`), and automatic cache clearing on `signOut()` and `deleteAccount()`.
5. **Redis L2 + Bounded L1 Application Cache ([cache_service.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/core/cache_service.py)):**
   - `AppCacheService` with thread-safe LRU L1 (`max_l1_entries=1024`), optional Redis L2 with automatic graceful fallback on Redis connection failure, and per-key lock stampede protection (`get_or_set`).
6. **AI Computation Cache ([ai_computation_cache.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/ai/ai_computation_cache.py)):**
   - Caches deterministic AI/geometry results by `(operation, pipeline_version, model_id, checkpoint_sha256[:16], config_hash, input_sha256)` scoped by `owner_id`.
7. **3D Asset Cache ([Studio3DAssetManager.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/ara/Studio3DAssetManager.ts)):**
   - LRU GLB (`max=12`) + Texture (`max=30`) caches returning cloned scene graphs so mutable garment fitting never corrupts cached source geometry, with `getCacheStats()`, `invalidateAsset()`, and `clearPrivateAssets()`.
8. **Telemetry Endpoint ([ops_routes.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/api/ops_routes.py)):**
   - Added `GET /api/ops/performance` exposing non-PII L1/Redis/AI cache stats and process peak RSS.

---

## 4. Cache Key Architecture

- **Backend L1/Redis keys:** `yorvyn:cache:v{ns_ver}:{namespace}:{public|owner:<owner_id>}:{key_or_sha256[:24]}`
- **AI computation keys:** `{operation}:{pipeline_version}:{model_id}:{checkpoint_sha256[:16]}:{config_hash}:{input_sha256}` (always wrapped inside `owner:<owner_id>`)
- **Non-public safety guard:** `AppCacheService.build_key` raises `ValueError` if `is_public=False` and `owner_id` is missing.

---

## 5. TTL Policies

| Resource | Layer | TTL / Directive |
|---|---|---|
| Immutable Vite JS/CSS/WASM/Fonts | CDN + Browser + SW | `max-age=31536000, immutable` |
| Public `/items/`, `/ara-assets/` | CDN + SW | `max-age=86400, stale-while-revalidate=604800` |
| `/api/billing/plans` | Backend Cache + HTTP | Redis/L1 600s; HTTP `max-age=300` + `ETag` |
| Owned `garment.glb` (`/api/fashion/garment-gen/assets/...`) | Browser (Private) + 3D Cache | `private, max-age=3600`, `Vary: Authorization`, `ETag` |
| AI deterministic inference cache | Backend L1/Redis | `3600s` (auto-invalidated on checkpoint SHA change) |
| Frontend `fashionApi` reads | Memory LRU (`<=200`) | `15s` (health), `45s` (default), `60s` (knowledge) |

---

## 6. Invalidation Rules & 7. Security Boundaries

- **Account Sign-out / Deletion:** `AuthContext` clears `fashionApi` (`invalidateApiCache()`) and private `/api/` 3D GLBs (`studio3DAssetManager.clearPrivateAssets()`).
- **Checkpoint / Model Change:** `AIComputationCache` encodes `checkpoint_sha256` and `PIPELINE_VERSION` directly in keys.
- **Namespace Bump / Owner Purge:** `AppCacheService.bump_namespace_version()` and `invalidate_owner(owner_id)` purge stale keys without dropping unrelated tenants.
- **Auth & Payment Isolation:** Service worker bypasses `/api/`, `/auth/`, non-GET requests, and `Authorization` requests completely; Firebase Hosting marks `/api/**` as `private, no-store`.

---

## 8. 3D Asset Caching & 9. AI Computation Caching

- `Studio3DAssetManager.loadGLB` deduplicates concurrent requests, returns cloned scenes (`gltf.scene.clone(true)`), attaches `Authorization: Bearer` tokens for `/api/` assets, disposes evicted GPU meshes (`disposeObject3D`), and separates immutable cached master scenes from per-instance fitted meshes.
- `AIComputationCache` prevents cross-tenant leakage (different owners never share cached results for identical image payloads) and automatically misses when model checkpoint hashes change.

---

## 10. Database Optimizations

- Added composite owner-state index `idx_jobs_user_state ON yorvyn_jobs(user_id, current_state, updated_at DESC)` and `idx_attempts_job_id ON yorvyn_job_attempts(job_id)` in [unified_state_machine.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/orchestration/unified_state_machine.py#L922-L927).

---

## 11. Test Results & 12. Performance Benchmarks

- **Frontend (`cd frontend && npm test && npm run build`):**
  - **33/33 test files passed, 393/393 tests passed** (including [phase17_6_cachingAndBundle.test.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/ara/__tests__/phase17_6_cachingAndBundle.test.ts)).
  - **Entry Bundle Improvement (`vite build`):** `index-*.js` decreased from **`1,109.20 kB` (`311.13 kB` gzip)** before Phase 17.6 to **`953.34 kB` (`260.30 kB` gzip)** after chunk splitting (`-155.86 kB` raw, `-50.83 kB` gzipped), separating `react-vendor` (`344.12 kB`), `onnx-runtime` (`418.29 kB`), and `mediapipe-vision` (`155.54 kB`).
- **Backend (`cd backend && ./venv/bin/pytest -v tests/test_phase17_6_caching_and_performance.py tests/test_phase17_5_universal_fitting.py tests/test_phase1_security.py`):**
  - **23/23 passed** in `9.70s` covering cache hit/miss/TTL/LRU, 12-thread stampede protection (1 compute execution across 12 concurrent callers), Redis outage L1 fallback, owner isolation, checkpoint hash invalidation, `ETag`/`304`/private GLB headers, and cached vs uncached latency benchmark (`cached_ms < uncached_ms`).

---

## 13. Remaining Bottlenecks & 14. Deployment Requirements

- **WASM Asset Size:** `ort-wasm-simd-threaded.jsep-*.wasm` remains `28 MB` on disk (loaded on demand when edge ONNX preprocessing runs). Removing or remote-hosting it belongs to UI/bundle cleanup if edge ONNX pre-check is not actively invoked.
- **Production Verification Needed on Deploy:** Verify live Firebase Hosting response headers (`Cache-Control` / `Vary`) and PostgreSQL `EXPLAIN ANALYZE` query plans under live multi-user database load.

---

## 15. Final Acceptance Status

- **Backend Multi-Tier Cache, HTTP Compression/ETag, AI Reuse & Tests:** **PASS (Unit & Integration Verified)**
- **Frontend SW Security Fix, Data LRU, Auth Cache Clear, 3D Cache Stats & Vite Bundle Split:** **PASS (Build & Test Verified)**
- **Production CDN / DB Load Verification:** **PENDING DEPLOYMENT**
