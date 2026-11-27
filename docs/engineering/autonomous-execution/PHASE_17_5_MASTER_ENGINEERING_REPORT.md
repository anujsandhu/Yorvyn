# YORVYN — PHASE 17.5 MASTER ENGINEERING REPORT
## Guided Live Garment Capture & Reconstruction Readiness Intelligence

**Date:** 2026-11-26  
**Baseline Git HEAD:** `7139fc7eea4e1f890e28da9140db2e8550081267`  
**Scope:** Live camera capture UI, lightweight throttled preview guidance, 4 garment capture modes, adaptive category checklists, server-side quality & multi-view consistency verification, Reconstruction Readiness Gate, and idempotent durable job handoff.

---

## 1. Existing Architecture Inspected & Preserved

- Inspected `frontend/src/components/PhotoTo3DGarmentModal.tsx`, `frontend/src/services/intelligenceApi.ts`, `backend/app/api/garment_generation_routes.py`, `backend/app/services/ai/multiview/view_classifier.py`, `backend/app/services/ai/multiview/fusion_engine.py`, `backend/app/services/intelligence/capability_registry.py`, and `backend/app/services/ml/model_registry.py`.
- Preserved the existing `YIPOrchestrator`, `UnifiedModelRegistry`, `GarmentRouter`, `GarmentKnowledgeRAG`, `GarmentJobManager` + transactional outbox, and Three.js `.glb` review studio. Did not create a parallel 3D reconstruction engine.

---

## 2. Files Changed & New Components

- **Backend Created:**
  - `backend/app/services/intelligence/capture_intelligence.py` (`CaptureMode`, `EvidenceState`, `SessionStatus`, `ReadinessOutcome`, `evaluate_capture_image_quality`, `CaptureSessionStore`, `capture_session_store`)
  - `backend/tests/test_phase17_5_capture_intelligence.py`
- **Backend Updated:**
  - `backend/app/services/intelligence/capability_registry.py` (+6 capabilities: `capture.session.create`, `capture.image.validate`, `capture.view.classify`, `capture.multiview.validate`, `capture.readiness.evaluate`, `capture.session.finalize`)
  - `backend/app/api/intelligence_routes.py` (+7 authenticated `/api/intelligence/capture/*` endpoints with 15 MB stream-capped upload & owner isolation)
- **Frontend Created:**
  - `frontend/src/utils/captureFrameAnalyzer.ts` (`analyzeLivePreviewImageData` — local ~350 ms throttled frame analysis without per-frame neural inference or continuous frame upload)
  - `frontend/src/components/capture/GuidedGarmentCapture.tsx` (explicit `"Open Camera"`, secure-context check, camera device enumeration & front/back flip, SVG framing guide, adaptive checklist, retake/remove, Readiness Gate display, idempotent reconstruction handoff, clean stream track release)
  - `frontend/src/components/__tests__/GuidedGarmentCapture.test.tsx`
- **Frontend Updated:**
  - `frontend/src/services/intelligenceApi.ts` (+7 capture session client methods)
  - `frontend/src/components/PhotoTo3DGarmentModal.tsx` (added `"Upload Prepared Photos"` | `"Guided Live Camera"` entry toggle preserving prepared-image uploads and existing Three.js viewer)

---

## 3. Capture Modes, Category Rules & Quality Intelligence

- **Supported Capture Modes (`CaptureMode`):**
  - `hanger`: full garment visibility, hanger-free collar, plain background, natural sleeve spread.
  - `mannequin`: upright mannequin, front/back/side views, unobstructed seams.
  - `flat_lay`: flat clean surface, full outline; explicitly discloses that flat-lay lacks true 3D side depth and is not equivalent to full 3D views.
  - `worn`: neutral pose, arms away from torso, avoid unnecessary face framing; explicitly discloses body/pose influence and that ordinary worn photos do not yield manufacturing-grade geometry.
- **Category-Adaptive View Checklists (`CATEGORY_VIEW_CHECKLISTS`):**
  - `tops`, `bottoms`, `outerwear`, `dresses_and_skirts`, `traditional`: `required = ["front", "back"]`, recommended `left_side`, `right_side`, and category-relevant detail shots (`collar_detail`, `sleeve_detail`, `hem_detail`, `texture_closeup`).
  - `footwear`: `required = ["front", "left_side", "right_side"]`, recommended `back`, `texture_closeup`.
  - `accessories`: `required = ["front"]`, recommended `back`, `left_side`, `texture_closeup`.
- **Quality & Consistency Measurements (Real Computed Metrics Only):**
  - Measures Laplacian-style `sharpness`, `exposure` (mean luminance + dark/bright clip + quadrant illumination spread), `garment_visibility` (foreground vs border background separation), `framing` (edge-clipping & minimum resolution), `occlusion` (fold/overlap/multi-garment horizontal cluster split), `background_quality`, and `view_confidence` (`ViewClassifier.classify_view`).
  - Returns one prioritized plain-English corrective instruction per check (never contradictory instructions).
  - Multi-view consistency checks exact SHA-256 duplicates, perceptual dHash near-duplicates (`hamming <= 2`), and dominant RGB garment spread across views (`> 155.0` triggers `CONTRADICTED` -> `RETAKE_REQUIRED`).
- **Server-Authoritative Readiness Gate (`evaluate_readiness`):**
  - Ignores client scores, validates `UnifiedModelRegistry` availability (`universal-garment-classifier`, `human_parsing_segformer_b2`, `xatlas_unwrapper`), and blocks insufficient/contradicted sessions (`MORE_EVIDENCE_REQUIRED`, `RETAKE_REQUIRED`, `UNSUPPORTED_CATEGORY`, `MODEL_UNAVAILABLE`, `RECONSTRUCTION_BLOCKED`).

---

## 4. Security, Privacy & Performance Evidence

- **Security & Privacy:** Explicit user click required before `getUserMedia`; no continuous video frame uploads; strict owner isolation (`401` anonymous / `403` cross-owner); `15 MB` streaming byte limit (`413` over limit); PIL format validation (`JPEG`/`PNG`/`WEBP`) + `ImageOps.exif_transpose` + re-encode to WebP stripping sensitive EXIF metadata; 1-hour session retention expiry & explicit cancel/purge endpoint (`DELETE /capture/sessions/{id}`); idempotent frozen handoff (`finalize_and_handoff`).
- **Measured Performance (`n = 20` on real Wikimedia photo `wm_02_jacket_denim.jpg`):**
  - `evaluate_capture_image_quality` latency: **`p50 = 42.6 ms`**, **`p95 = 45.7 ms`**.
  - Measured metrics on `wm_02_jacket_denim.jpg`: `sharpness = 0.500`, `exposure = 1.000`, `garment_visibility = 0.860`, `framing = 1.000`, `background_quality = 0.727`, `usable = True`.
  - On cropped `wm_00_jacket_denim.jpg`: `clip_max_edge = 0.959`, accurately flagged `usable = False` (`primary_issue = "bottom_cut_off"`).

---

## 5. Verification Results (Real vs Mocked)

- **Backend Pytest (`60 passed, 0 failed in 57.52s`):**
  - `test_phase17_5_capture_intelligence.py` (`4` tests), `test_phase17_4_hardening.py`, `test_phase17_yip.py`, `test_durable_job_publication_fix.py`, `test_durable_job_outbox_fault_injection.py`.
  - **Real End-to-End Reconstruction (`test_3`):** Real Wikimedia `wm_02_jacket_denim.jpg` front + matching denim-toned back -> `ReadinessOutcome.APPROVED_WITH_LIMITATIONS` -> `finalize_and_handoff` -> idempotent durable PG/Redis job `COMPLETED` -> `.glb` file written under `models/generated_3d/staging_jobs/` -> `MeshValidationService().validate_glb_bytes()` passed (`passed=True`).
  - **Synthetic Defect Fixtures (`test_1`, `test_2`):** Programmatically generated underexposed, Gaussian-blurred, bottom-clipped, and color-mismatched PNG/JPEG fixtures verified defect triggers; live browser `getUserMedia` mocked in `GuidedGarmentCapture.test.tsx`.
- **Frontend Vitest (`3 test files, 14 passed in 6.96s`):** `GuidedGarmentCapture.test.tsx`, `PhotoTo3DGarmentModalHandoff.test.tsx`, `IntelligencePlatformIntegration.test.ts`.
- **Frontend Build (`tsc && vite build`):** Verified cleanly after final edit.

---

## 6. Remaining Limitations

1. Live interactive browser camera hardware (`getUserMedia` on physical mobile/desktop hardware) was verified via unit/API integration tests and `tsc && vite build`, not a live webcam Playwright fixture.
2. `ViewClassifier` & `evaluate_capture_image_quality` remain pixel/contour CV heuristics (honestly labeled in `capability_registry.py`); `remote_neural_3d_available` remains `False`.
3. `CaptureSessionStore` keeps temporary capture session state in process memory with 1-hour expiry; multi-worker capture sessions across separate API processes would require storing session metadata/blobs in PostgreSQL/object storage before handoff.
