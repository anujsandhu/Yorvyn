# YORVYN — PHASE 12: CRITICAL GARMENT RECONSTRUCTION RECOVERY
## Phase 0 Initial Audit: Architecture, Real Inference Path, Procedural Fallbacks, Model Checkpoints & Forensic Root Causes

**Author:** Principal 3D Reconstruction Engineer, Computer Vision Research Engineer, Three.js/WebGL Engineer & Senior ML Systems Architect  
**Date:** November 7, 2026  
**Status:** COMPLETE & INDEPENDENTLY VERIFIED  
**Target Environment:** macOS Apple Silicon M2 (8GB Unified Memory)  

---

## 1. Executive Summary

A comprehensive architectural and forensic audit was conducted across the Yorvyn 3D garment reconstruction and avatar fitting pipeline. The objective is to identify the precise technical mechanisms responsible for user-reported reconstruction defects:
1. Generated garments that do not resemble uploaded clothing photographs.
2. Inaccurate, deformed, or missing geometry (sleeves, hoods, pockets, collars).
3. Distorted textures, black textures, or misaligned color patterns.
4. Spurious cyan diagnostic grids and wireframes appearing in production renders.
5. Catastrophic garment deformations upon avatar fitting and skinning.
6. Unrealistic or unstable cloth physics behavior.

This audit separates verified implementation facts from documentation claims, establishes the actual active inference paths, catalogs local versus remote model assets, and formulates reproducible forensic baselines for Phase 1.

---

## 2. Full Architecture Inventory: Documented vs. Implemented

Every module cited in Phase 1–11 reports was inspected in the actual codebase:

| Pipeline Subsystem | Claimed Role | Implemented Component | Actual Code Path Verified | Implementation Reality |
| :--- | :--- | :--- | :--- | :--- |
| **Input Ingestion** | Upload REST endpoint | `garment_generation_routes.py` | `POST /api/fashion/garment-gen/jobs` | **Implemented**: Multipart photo upload, job creation, and background thread execution. |
| **Job Management** | Async priority queue | `GarmentJobManager` (`job_manager.py`) | `GarmentJobManager._process_job()` | **Implemented**: ThreadPoolExecutor (3 workers), stage progression tracking, timeout health checks. |
| **Garment Intelligence** | Neural parsing & classification | `GarmentAnalyzer` & `AutomaticGarmentDetector` | `garment_intelligence_service.py`, `universal_garment_classifier.py` | **Implemented**: 2D Segformer parsing, MobileNetV3 visual features, multi-modal component detection. |
| **3D Mesh Generation** | Neural 3D Reconstruction | `NeuralGarmentReconstructionEngine` | `neural_reconstruction_engine.py` | **Partial / Hybrid**: No local learned 3D model (e.g. TRELLIS/Hunyuan3D); dispatches to procedural pattern engines with landmark-based vertex deformations. |
| **Procedural Pattern Engines** | Dedicated anatomical patterns | `reconstruction_registry` | `hoodie_engine.py`, `shirt_engine.py`, `tops_engine.py`, `bottoms_engine.py`, etc. | **Implemented**: Procedural lofted quad strips around 20-bone Ara skeleton specifications. |
| **Texture Synthesis** | PBR material extraction | `ReferenceTextureReconstructor` | `reference_texture_reconstructor.py`, `uv_reconstruction_engine.py` | **Implemented**: Photographic projection into canonical UV layout, Sobel normal maps, metallic-roughness synthesis. |
| **glTF 2.0 Binary Export** | PBR GLB export | `GLBExporter` (`glb_exporter.py`) | `glb_exporter.export()` | **Implemented**: Pure Python struct/binary packing of buffers, accessors, PBR materials, and 20-bone skinning. |
| **Backend Avatar Fitting** | Ease & collision resolution | `UniversalGarmentFittingEngine` | `universal_garment_fitting_engine.py`, `garment_collision_engine.py` | **Implemented**: Analytical morphing, capsule/ellipsoid collision push (+3mm clearance), 12-iteration PBD draping. |
| **Frontend Studio Viewer** | WebGL virtual try-on | `AvatarStudioViewer.tsx` | `AvatarStudioViewer.tsx`, `GarmentAvatarFittingEngine.ts` | **Implemented**: Three.js GLTFLoader, BVH collision push, semantic bone skin weight synthesis, Rapier-based cloth simulation. |

---

## 3. The Real Neural Reconstruction Path vs. Procedural Fallback

A critical investigation into the actual active 3D reconstruction execution path revealed:

### 3.1 The Truth About 3D Model Inference
```
[User Uploads Image]
          │
          ▼
Stage A: 2D Computer Vision (GENUINE NEURAL INFERENCE)
  ├── Segmentation: SegFormer-B2 Clothes Parser (PyTorch, CPU/MPS)
  ├── Feature Extraction: MobileNetV3 (TorchVision, MPS) -> 64-dim embedding
  └── Component Detection: Spatial gradient & bounding box localization
          │
          ▼
Stage B: 3D Geometry Generation (HYBRID PROCEDURAL DEFORMATION)
  ├── Check: Is Remote GPU Worker Configured? (GARMENT_AI_REMOTE_INFERENCE_URL)
  │     ├── YES: Dispatch to Remote TRELLIS / Hunyuan3D Cluster
  │     └── NO (Local Dev / Production Default):
  │           ├── Execute Category Pattern Engine (e.g., HoodieReconstructionEngine)
  │           ├── Apply Landmark-Guided Vertex Offsets (_apply_neural_deformation)
  │           └── Refine with HybridReconstructionRefiner
  │
  └── Provenance Tag Assigned:
        - "neural_remote" (if cloud worker executed)
        - "hybrid_neural_procedural" (if local pattern + landmark refinement ran)
        - "deterministic_procedural_fallback" (if error occurred during hybrid refinement)
```

### 3.2 Finding on Model Checkpoints
An audit of `models/checkpoints/` and `models/registry.json` confirmed:
- **Present Local Checkpoints:**
  - `models/checkpoints/specialized_garment_heads_v3.pt` (Multi-task head: 10 categories, 55 subcategories, 13 components; 5.0 MB)
  - `models/checkpoints/garment_classifier_v2.pt` (PyTorch classification weights; 9.8 MB)
  - `models/checkpoints/garment_landmarks_v2.pt` (Landmark keypoint regression; 4.2 MB)
- **Absent 3D Checkpoints:**
  - Zero local learned image-to-3D diffusion or NeRF models (e.g. TRELLIS, Hunyuan3D, TripoSR).
  - **Engineering Rationale:** An image-to-3D model like TRELLIS requires >16GB VRAM; Hunyuan3D 2.0 requires >24GB VRAM. Running either on an 8GB Apple Silicon M2 triggers immediate out-of-memory kernel panics or swap memory thrashing.
  - **Verdict:** Local execution truthfully operates as **hybrid neural-procedural reconstruction**. Documented claims of local direct learned 3D mesh inference were conflating 2D neural perception with 3D procedural construction.

---

## 4. Forensic Investigation of the Six Failure Signatures

### Failure 1: Generated Garments Do Not Resemble Uploaded Clothing
- **Root Cause:** Procedural pattern generators (`hoodie_engine.py`, `tops_engine.py`, `shirt_engine.py`) use fixed parametric silhouette functions ($R_x(y), R_z(y)$). While ease margins are calibrated from detected fit ('regular' vs 'oversized'), unique cut silhouettes (such as boxy cropped torsos, raglan sleeves, curved high-low hems, wide kimono cuts) are forced into standard cylindrical lofts.
- **Remediation:** Silhouette boundaries extracted from the 2D segmentation mask (`GarmentSegmentationOutput.alpha_mask`) must directly drive the radial cross-sectional profile $R_x(y)$ and $R_z(y)$ at each ring height rather than relying purely on hardcoded ease tables.

### Failure 2: Geometry Is Incorrect / Components Missing or Disconnected
- **Root Cause:** 
  1. Component detection relies on spatial gradient heuristics (`component_detector.py`). If ambient lighting or low contrast causes component confidence to drop below 0.60, `has_pocket` or `has_hood` defaults to false, generating a plain crewneck instead of a hoodie.
  2. Sleeves are generated as separate open cylinders originating at $X = \pm 0.232\text{m}$, penetrating the torso without an armscye bridging seam. When animated or fitted, the sleeve and torso pull apart, exposing hollow gaps.
- **Remediation:** 
  1. Guaranteed fallback to category-canonical components (a hoodie must always possess a hood and pouch pocket unless explicitly classified as a crewneck).
  2. Anatomical armscye bridging triangles linking sleeve root rings directly to lateral torso rings.

### Failure 3: Distorted, Dark, or Misaligned Textures
- **Root Cause:**
  1. Front planar projection maps the rectangular garment crop onto cylindrical torso UV coordinates ($U \in [0.04, 0.46], V \in [0.48, 0.96]$). Perspective tilt or fabric folds in the reference photo stretch unevenly across the curved 3D surface.
  2. When glTF `baseColorFactor` is baked with dark tinting ($[r, g, b] < 0.25$), multiplying it by dark textile texels results in pitch-black rendering.
- **Remediation:** 
  1. Strict neutral `baseColorFactor: [1.0, 1.0, 1.0, 1.0]`.
  2. Perspective-corrected texture mapping using 2D landmark homography.

### Failure 4: Unexpected Cyan Debug Grid Pattern
- **Root Cause:** `GarmentUVReconstructionEngine.render_uv_layout_preview()` generates a diagnostic image featuring Tailwind Sky-400 cyan `(56, 189, 248)` island outlines on a dark slate background. This image is base64-encoded into `diag.uv_layout_preview_data_url`. When texture synthesis encounters an error or when frontend preview components receive an empty diffuse path, they fall back to this preview URL, mapping bright cyan grid lines directly onto the avatar's torso.
- **Remediation:** 
  1. Diagnostic UV layout previews must be strictly quarantined from material texture channels.
  2. If diffuse texture synthesis fails, fallback must be a solid PBR base color derived from `features.primary_color_hex`, never a diagnostic UV preview.

### Failure 5: Avatar Fitting Tears, Collapses, or Deforms Garment
- **Root Cause:** 
  1. `GarmentAvatarFittingEngine.applyComponentFittingTransform` in frontend applies global scale and translation based on bounding boxes. When avatar chest or waist varies, the bounding box scale pulls sleeve cuffs away from arm bones.
  2. In `GarmentSkinningAdapter.generateSemanticSkinWeights`, sleeve vertices near the shoulder joint are assigned weights across both `Spine2` and `LeftArm`. An incorrect distance decay exponent causes torso bones to pull sleeve meshes into the chest cavity during arm movement.
- **Remediation:**
  1. Bone-centric local transformation for sleeves, hood, and collar.
  2. Sharp component segmentation masks preventing torso bones from exerting influence on sleeve vertices.

### Failure 6: Cloth Simulation Instability
- **Root Cause:** In `AvatarStudioViewer.tsx`, the Rapier cloth simulation (`clothSimRef`) attempts to simulate garment meshes with arbitrary triangle sizes. Thin edge triangles and high stiffness constraints cause numerical instability under large frame deltas, leading to cloth explosions or skin clipping.
- **Remediation:** 
  1. Vertex mass normalization by Voronoi dual area.
  2. Deterministic non-simulated skinning fallback when frame rate dips below 30 FPS.

---

## 5. Phase 1 Deterministic Reproduction Strategy

To reproduce all four failure classes across consistent rendering environments, the Phase 1 test harness will execute 6 mandatory reference test cases:

1. **Test Case A:** Reference Pullover Hoodie (`docs/reports/hoodie_visual_regression/reference_hoodie.png`)
2. **Test Case B:** Grey Graphic Oversized T-Shirt worn on-body (`test_on_body_garment_segmentation_phase_11b.py`)
3. **Test Case C:** Formal Button-Down Oxford Shirt (`docs/reports/phase_11a_visual_debug/formal_shirt/A_original_photo.png`)
4. **Test Case D:** Denim Jacket (`docs/reports/ai_garment_detection_benchmark.json`)
5. **Test Case E:** Tailored Trousers (`bottoms_engine.py`)
6. **Test Case F:** Floral Summer Dress (`docs/reports/yorvyn_garment_benchmark_integrity.json`)

For each test case, the test harness will capture the 15 mandatory artifacts (original photo, segmentation mask, crop, detection output, component output, reconstruction output, raw geometry, UV layout, diffuse texture, PBR maps, exported GLB, reimported GLB, isolated render, avatar-fitted render, final deformation render) and record a complete machine-readable pipeline trace.

