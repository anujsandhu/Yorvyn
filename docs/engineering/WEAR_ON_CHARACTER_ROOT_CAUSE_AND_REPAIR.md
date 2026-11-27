# YORVYN — Wear on Character Root Cause & Engineering Repair

**Date:** 2026-11-26  
**Branch:** `release/stabilize-17.4`  
**Status:** Repaired and unit/build-verified (browser WebGL visual inspection not executed in this turn)

---

## 1. Root Causes Identified

1. **Unauthenticated GLB Asset Retrieval (`Studio3DAssetManager` & `GarmentDesignWorkspace`):**
   - `GET /api/fashion/garment-gen/assets/{job_id}/{filename}` in [garment_generation_routes.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/api/garment_generation_routes.py#L592-L611) enforces `_assert_job_ownership(job, current_user)`. For any authenticated user's reconstructed garment, fetching `garment.glb` without `Authorization: Bearer <token>` returns HTTP `401`/`403`.
   - [Studio3DAssetManager.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/ara/Studio3DAssetManager.ts#L186-L204) invoked `this.gltfLoader.load(url, ...)` without setting the active Supabase Bearer token header, and [GarmentDesignWorkspace.tsx](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/components/design/GarmentDesignWorkspace.tsx#L439) called bare `fetch(glbUrl)` without auth headers.
2. **Silent Error Swallowing & Desynchronized UI State (`AvatarStudioViewer` & `AvatarStudio`):**
   - When `studio3DAssetManager.loadGLB(...)` rejected or `GarmentAvatarFittingEngine.fitAndAttachGarment(...)` threw, [AvatarStudioViewer.tsx](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/components/AvatarStudioViewer.tsx#L1096-L1108) logged to `console.error` and restored base clothing visibility locally without notifying [AvatarStudio.tsx](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/pages/AvatarStudio.tsx). `activeCustomGarment` stayed set (`"Wearing: ..."` banner) even though nothing was attached to the avatar.
3. **Async Race & Duplicate-Attachment Guard (`AvatarStudioViewer`):**
   - In `AvatarStudioViewer.tsx`, the async `.then(...)` handler did not verify `currentModelRef.current === modelRoot` or re-run `GarmentAvatarFittingEngine.detachGarment(modelRoot)` immediately prior to `fitAndAttachGarment` if an avatar rebuild or rapid garment switch overlapped.
4. **Penetration Diagnostic Flag (`GarmentAvatarFittingEngine`):**
   - `GarmentAvatarFittingEngine.fitAndAttachGarment` computed `penetrationCount` and `maxPenetrationMm` in `diagnostics`, but did not expose a structured `majorPenetrationDetected` flag to the viewer/UI.

---

## 2. Files Changed

- [Studio3DAssetManager.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/ara/Studio3DAssetManager.ts) — Attaches Supabase `Authorization: Bearer <token>` via `gltfLoader.setRequestHeader(...)` for `/api/` asset URLs and emits descriptive load errors.
- [GarmentDesignWorkspace.tsx](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/components/design/GarmentDesignWorkspace.tsx) — Attaches `Authorization: Bearer <token>` and checks `srcResp.ok` when fetching `glbUrl` in `handleExportGLB`.
- [GarmentAvatarFittingEngine.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/garments/GarmentAvatarFittingEngine.ts) — Adds `majorPenetrationDetected` (`maxPenetrationMm > 8.0 || penetrationCount > 25`) to `GarmentAvatarFitResult.diagnostics` for both single-mesh and multi-component paths.
- [AvatarStudioViewer.tsx](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/components/AvatarStudioViewer.tsx) — Adds `onCustomGarmentFitResult` callback, guards against stale `currentModelRef.current`, runs atomic `detachGarment(modelRoot)` before attach, and propagates load/fit errors and penetration diagnostics.
- [AvatarStudio.tsx](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/pages/AvatarStudio.tsx) — Rolls back `activeCustomGarment` on fit/load failure with `toast.error(...)` and surfaces minor overlap warnings when `majorPenetrationDetected` is true.
- [wearOnCharacterPipeline.test.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/garments/__tests__/wearOnCharacterPipeline.test.ts) — Controlled regression matrix (T-shirt, jacket, jeans, missing skeleton fallback, invalid/empty GLB, short/tall/wide avatar proportions, repeated equip & switching, authenticated `/api/` GLB header).

---

## 3. Verification Results

- **Command:** `cd frontend && npm test && npm run build`
  - **Vitest:** **31/31 test files passed, 384/384 tests passed** (including all 8 tests in `wearOnCharacterPipeline.test.ts`, 9 tests in `garmentAvatarFittingEngine.test.ts`, 10 tests in `fittingAndLayerReplacement.test.ts`, and 6 tests in `studio3DAssetManagerAndLazyLoading.test.ts`).
  - **TypeScript + Vite Build:** `tsc && vite build` exited `0` (`✓ built in 6.83s`).

---

## 4. Remaining Limitations & Acceptance Status

- **Single custom 3D slot:** `AvatarStudio.tsx` still tracks one `activeCustomGarment` at a time (multi-slot custom 3D layering belongs to V1 Phase 2.3).
- **Live WebGL browser screenshot:** Not re-run against a live backend server in this turn; all scene-graph placement, scaling, skeleton fallback, deduplication, and auth header behavior are verified via Vitest + `tsc` + Vite build.
- **Acceptance Status:** **Unit & Build Verified**; ready for live browser smoke verification.
