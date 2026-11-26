# YORVYN — PHASE 13.1: INDEPENDENT AUDIT BLOCKER REGISTER
## Prioritized Inventory of Verified Defects, Integrity Violations & Production Gate Blockers

**Audit Reference:** Phase 13.1 Hybrid AI Verification  
**Auditor Mode:** Independent Forensic Quality Audit  
**Status:** 10 Production Blockers Identified  
**Production Gate Verdict:** **BLOCKED — DEPLOYMENT NOT AUTHORIZED**  

---

## 1. Blocker Summary Matrix

| Blocker ID | Severity | Category | Title | Exact Source Location | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **BLK-01** | **CRITICAL** | Security / DoS | Unbounded GLB file stream ingestion risking memory exhaustion | `backend/app/api/ai_orchestration_routes.py:54-66` | **OPEN** |
| **BLK-02** | **CRITICAL** | Security / Auth | Unauthenticated orchestration API endpoints | `backend/app/api/ai_orchestration_routes.py:26-114` | **OPEN** |
| **BLK-03** | **CRITICAL** | Routing Engine | Routing policy violations (17 pathways) ignoring `LOCAL_REQUIRED` and `CLOUD_REQUIRED` | `hybrid_workload_router.py:44-147`, `DeviceCapabilityManager.ts:180-291` | **OPEN** |
| **BLK-04** | **CRITICAL** | AI Model Integrity | Edge ONNX model missing from disk; mock stub returns hardcoded features | `UnifiedAIOrchestrator.ts:220-236`, `/models/edge/garment_classifier_edge.onnx` | **OPEN** |
| **BLK-05** | **CRITICAL** | Model Registry | 3 of 4 server models fail integrity verification (1 SHA mismatch, 2 invalid URI paths) | `backend/app/services/ml/model_registry.py:81-125`, `docs/reports/YORVYN_PHASE_13_MODEL_REGISTRY.json` | **OPEN** |
| **BLK-06** | **HIGH** | Concurrency | Claimed Web Worker off-thread execution is non-existent scaffold | `frontend/src/engine/orchestration/EdgeImagePreprocessor.ts:50-65` | **OPEN** |
| **BLK-07** | **HIGH** | 3D Geometry | Server Trimesh manifold check conflates winding consistency with 2-manifold topology | `backend/app/services/garments/mesh_validation_service.py:169` | **OPEN** |
| **BLK-08** | **HIGH** | Pipeline / UX | Multi-view upload preprocessing asymmetry and event listener state desynchronization | `frontend/src/components/PhotoTo3DGarmentModal.tsx:520-571` | **OPEN** |
| **BLK-09** | **MEDIUM** | Capability Probe | WASM SIMD capability probe returns false positive on standard WebAssembly MVP | `frontend/src/engine/orchestration/DeviceCapabilityManager.ts:87-92` | **OPEN** |
| **BLK-10** | **MEDIUM** | Audit Integrity | Hardcoded synthetic benchmark script and fabricated 96.5% bandwidth reduction claim | `backend/tests/benchmark_hybrid_ai_phase_13.py:46-51` | **OPEN** |

---

## 2. Detailed Blocker Dossiers

### BLK-01: Unbounded File Ingestion Vulnerability (Memory Exhaustion DoS)
- **Severity:** Critical
- **Category:** API Security / Reliability
- **Exact Source:** `backend/app/api/ai_orchestration_routes.py:64`
- **Reproduction Procedure:**
  ```bash
  head -c 200M </dev/urandom > large_fake.glb
  curl -X POST http://127.0.0.1:8002/orchestration/validate-mesh \
    -F "file=@large_fake.glb" \
    -F "category=top"
  ```
- **Observed Behavior:** FastAPI attempts to buffer the entire stream into memory simultaneously, causing spike in server memory consumption.
- **Impact:** Memory exhaustion, unhandled OOM crash on constrained instances.
- **Remediation:** Enforce `Content-Length` header check and maximum file size ceiling (e.g., 50 MB) before calling `await file.read()`.

---

### BLK-02: Unauthenticated Orchestration API Endpoints
- **Severity:** Critical
- **Category:** Access Control
- **Exact Source:** `backend/app/api/ai_orchestration_routes.py:26, 42, 54, 86`
- **Reproduction Procedure:**
  ```bash
  curl -X POST http://127.0.0.1:8002/orchestration/plan \
    -H "Content-Type: application/json" \
    -d '{"workload_type":"NEURAL_RECONSTRUCTION"}'
  ```
- **Observed Behavior:** Request succeeds with HTTP 200 without Authorization header or cookies.
- **Impact:** Anonymous exploitation of compute-heavy 3D mesh analysis and internal schema discovery.
- **Remediation:** Attach `dependencies=[Depends(get_current_user)]` to protected endpoints.

---

### BLK-03: Routing Policy Violations (17 Pathways)
- **Severity:** Critical
- **Category:** Core Hybrid Architecture
- **Exact Source:**
  - `backend/app/services/orchestration/hybrid_workload_router.py:45-147`
  - `frontend/src/engine/orchestration/DeviceCapabilityManager.ts:180-291`
- **Reproduction Procedure:**
  1. Call `hybrid_workload_router.plan_workload(workload_type="NEURAL_RECONSTRUCTION", policy="LOCAL_REQUIRED")`.
  2. Call `hybrid_workload_router.plan_workload(workload_type="IMAGE_PREPROCESS", policy="CLOUD_REQUIRED")`.
- **Observed Behavior:**
  1. Returns `selected_location: "CLOUD_GPU"` despite explicit `LOCAL_REQUIRED` policy.
  2. Returns `selected_location: "CLIENT_WORKER"` despite explicit `CLOUD_REQUIRED` policy.
- **Impact:** Complete failure to respect privacy constraints (`LOCAL_REQUIRED`) and cloud offloading policies (`CLOUD_REQUIRED`).
- **Remediation:** Refactor routers to evaluate `policy` first; if a required policy cannot be fulfilled, return `POLICY_UNSATISFIED` error instead of silently violating the constraint.

---

### BLK-04: Missing Edge ONNX Model & Hardcoded Mock Execution
- **Severity:** Critical
- **Category:** Machine Learning Integrity
- **Exact Source:**
  - `frontend/src/engine/orchestration/UnifiedAIOrchestrator.ts:220-236`
  - `/models/edge/garment_classifier_edge.onnx`
- **Reproduction Procedure:**
  1. Search filesystem for `garment_classifier_edge.onnx`.
  2. Inspect `UnifiedAIOrchestrator.ts:executeEdgeClassification`.
- **Observed Behavior:**
  1. The `.onnx` file does not exist anywhere in the repository.
  2. `executeEdgeClassification` returns a hardcoded mock dictionary (`confidence_score: 0.88`, `'Dark Brown'`, `'hoodie_collar'`).
- **Impact:** Edge classification is simulated by a hardcoded stub rather than actual AI model inference.
- **Remediation:** Export a genuine lightweight quantized MobileNetV3/ViT ONNX model to `frontend/public/models/edge/` and wire `onnxRuntimeWebAdapter.runInference()` in `UnifiedAIOrchestrator.ts`.

---

### BLK-05: Server Model Registry Verification Failure
- **Severity:** Critical
- **Category:** Provenance & Model Lifecycle
- **Exact Source:** `backend/app/services/ml/model_registry.py:81-125`
- **Reproduction Procedure:**
  Run `backend/venv/bin/python -c "from backend.app.services.ml.model_registry import unified_model_registry; [print(m, unified_model_registry.verify_server_checkpoint(m)) for m in ['human-pose-and-landmarks', 'garment-silhouette-segmenter', 'feature-embedder']]"`
- **Observed Behavior:**
  - `human-pose-and-landmarks`: Checksum mismatch.
  - `garment-silhouette-segmenter`: Non-existent path `models/registry.json#birefnet_general_onnx`.
  - `feature-embedder`: Non-existent path `models/registry.json#mobilenet_v3_fashion_features`.
- **Impact:** Production registry is broken; 75% of server model checkpoints fail integrity audits.
- **Remediation:** Update `docs/reports/YORVYN_PHASE_13_MODEL_REGISTRY.json` with accurate relative paths and recalculate SHA256 hashes against actual files on disk.

---

### BLK-06: Web Worker Execution Claim is Non-Existent Scaffold
- **Severity:** High
- **Category:** Frontend Architecture / Performance
- **Exact Source:** `frontend/src/engine/orchestration/EdgeImagePreprocessor.ts:50-65`
- **Reproduction Procedure:**
  Inspect `EdgeImagePreprocessor.ts` and search codebase for `.worker.ts` or `new Worker()`.
- **Observed Behavior:**
  - `EdgeImagePreprocessor.ts` creates a synchronous `document.createElement('canvas')` and reads pixels on the main UI thread.
  - There are zero worker implementations in `frontend/src`.
- **Impact:** Processing 1200px images, Laplacian variance, and RGB quantization blocks the browser main thread, causing frame drops and input latency.
- **Remediation:** Implement a real Web Worker with `OffscreenCanvas` and Transferable ArrayBuffers for background image processing.

---

### BLK-07: Incomplete Server Trimesh Manifold Validation
- **Severity:** High
- **Category:** 3D Asset Geometry Quality
- **Exact Source:** `backend/app/services/garments/mesh_validation_service.py:169`
- **Reproduction Procedure:**
  Inspect line 169: `is_manifold = bool(mesh.is_winding_consistent and not mesh.is_empty)`.
- **Observed Behavior:** Normal winding consistency does not verify that edges share exactly two faces. Non-manifold geometries (e.g. self-intersecting T-junctions) falsely pass as manifold.
- **Impact:** Defective non-manifold 3D meshes pass validation and cause vertex tearing during avatar fitting.
- **Remediation:** Update `mesh_validation_service.py` to check `mesh.is_watertight` and `len(trimesh.grouping.group_rows(mesh.edges_sorted, require_count=2)[1]) == 0`.

---

### BLK-08: Pipeline Asymmetry & Event Handler State Desynchronization
- **Severity:** High
- **Category:** Pipeline Integration / User Experience
- **Exact Source:** `frontend/src/components/PhotoTo3DGarmentModal.tsx:520-571`
- **Reproduction Procedure:**
  1. Select a front photo (triggers preprocessing).
  2. Select a back photo (triggers `triggerAiAnalysis` passing `frontFile` instead of `activeFrontUpload`).
- **Observed Behavior:**
  1. Back and side uploads are never preprocessed or compressed to WebP.
  2. Selecting a back photo silently reverts the front input from compressed WebP to uncompressed original.
- **Impact:** Unpredictable server inputs, inflated bandwidth consumption, and inconsistent reconstruction behavior.
- **Remediation:** Store `activeFrontUpload` in component state and invoke `preprocessUpload` for all uploaded views (front, back, side, detail).

---

### BLK-09: WASM SIMD Feature Detection False Positive
- **Severity:** Medium
- **Category:** Hardware Probing Accuracy
- **Exact Source:** `frontend/src/engine/orchestration/DeviceCapabilityManager.ts:87-92`
- **Reproduction Procedure:**
  Inspect capability probe: `simdWasmSupported = typeof WebAssembly === 'object' && typeof WebAssembly.validate === 'function'`.
- **Observed Behavior:** This validates basic MVP WebAssembly (available in all modern browsers since 2017), not SIMD instruction extension support.
- **Impact:** Low-tier devices lacking WASM SIMD support are incorrectly flagged as SIMD-capable.
- **Remediation:** Use standard WASM SIMD test bytecode probe `WebAssembly.validate(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 1, 5, 1, 96, 0, 1, 123, 3, 2, 1, 0, 10, 10, 1, 8, 0, 65, 0, 253, 15, 26, 11]))`.

---

### BLK-10: Synthetic Benchmark Script & Fabricated Bandwidth Savings Claim
- **Severity:** Medium
- **Category:** Benchmark Integrity / Governance
- **Exact Source:** `backend/tests/benchmark_hybrid_ai_phase_13.py:46-51`
- **Reproduction Procedure:**
  Inspect `benchmark_hybrid_ai_phase_13.py` lines 46-51.
- **Observed Behavior:** The script hardcoded synthetic input sizes (`18.4MB`, `16.8MB`) and multiplied by `0.035`, claiming 96.5% savings without measuring any real files.
- **Impact:** Misleading performance claims in Phase 13 reporting. Actual measured savings across benchmark assets is 51.38%.
- **Remediation:** Replace synthetic benchmark script with empirical measurement against real benchmark datasets in `docs/reports/YORVYN_PHASE_12_VISUAL_QA/`.

