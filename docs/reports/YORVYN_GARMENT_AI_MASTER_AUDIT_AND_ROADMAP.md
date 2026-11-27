# YORVYN — GARMENT AI RECOVERY & ENGINEERING MASTER AUDIT
**Document ID:** `docs/reports/YORVYN_GARMENT_AI_MASTER_AUDIT_AND_ROADMAP.md`  
**Date:** November 3, 2026  
**Auditor:** Yorvyn Principal AI & 3D Systems Engineering  
**Scope:** Complete Garment AI, 3D Reconstruction, Avatar Virtual Try-On, Machine Learning, and Dataset Infrastructure  
**Classification:** Engineering Architecture & Strategic Technical Audit  

---

## 1. Executive Summary & Ground Truth Disclosure

### 1.1 The Operational Reality vs. Historical Claims
Previous engineering iterations and design documentation across the Yorvyn codebase referenced a "multi-model AI garment reconstruction engine" capable of transforming 2D clothing photographs into wearable, photorealistic 3D garments draped across the Ara humanoid avatar. 

A rigorous, line-by-line forensic audit of the actual repository code (`backend/` and `frontend/src/`) reveals that **no neural 3D reconstruction models are currently executing in production**. 

Specifically:
1. **The Core Reconstruction Illusion**: Neither neural surface reconstruction, multi-view diffusion (e.g., Wonder3D, InstantMesh), nor monocular mesh deformation models are integrated into the active pipeline. What was designated as "AI 3D Reconstruction" is actually **hardcoded parametric geometric primitives** (cylinders, ellipses, and sliced semicircular rings authored in `GarmentGeometryProcessor.ts` and `garment_mesh_builder.py`).
2. **The Texture Pasting Defect**: Rather than extracting PBR material properties, delighting photographic assets, and unwrapping textures across UV islands, the system has relied on **planar photographic cropping**: taking a center crop ($20\%-80\%$ width, $22\%-94\%$ height) of the front photo and pasting it onto a flat canvas UV island, while filling the back, sleeves, hood, and trims with solid synthetic color, procedural noise, and canvas 2D line strokes.
3. **The Silent Routing Failure**: A critical REST URL mismatch exists between the frontend and backend. The backend FastAPI service registers the route at `/api/fashion/garment-gen/jobs`, whereas the frontend `fashionApi.ts` client issues requests to `/api/garment-gen/jobs`. Consequently, **every generation attempt from the web client fails with HTTP 404 Not Found**, silently triggering a catch block that executes the local client-side TypeScript parametric fallback (`LocalParametricReconstructionAdapter`). The backend 3D generation pipeline has never been executed during real user interactions.
4. **Machine Learning Infrastructure Status**:
   - `models/fashion_classifier.pkl` is an `SGDClassifier` from Scikit-Learn trained on the 28x28 grayscale **Fashion-MNIST** toy dataset. It has no capability to process high-resolution RGB clothing photographs, extract 3D contours, or detect tailoring landmarks.
   - `fashion_vision.py` computes an MD5 checksum of the filename and image URL to produce pseudorandom attribute classifications and mock 64-dimensional embeddings. It does not load or run computer vision models.
   - Upstream research repositories (`research/upstream/Clothware`, `Garment3DGen`, `ReMu`) reside on disk as reference clones, but their heavy PyTorch/CUDA dependencies, commercial licensing restrictions (CC-BY-NC 4.0, SMPL-X non-commercial), and incompatible hardware requirements have prevented integration into the running system.

### 1.2 Summary of Pipeline Health Matrix

| Subsystem | Core Files | Claimed Capability | Actual Implementation | Health Status |
|---|---|---|---|---|
| **Upload Workflow** | `PhotoTo3DGarmentModal.tsx`, `GarmentImageProcessor.ts` | Multi-view photo upload & EXIF validation | React modal + HTML5 canvas validation | **Implemented and tested** |
| **Backend API** | `garment_generation_routes.py`, `fashionApi.ts` | Async job processing & CDN persistence | FastAPI router; broken URL routing (`/api/fashion/garment-gen` vs `/api/garment-gen`) | **Implemented but defective** |
| **Preprocessing** | `GarmentImageProcessor.ts`, `garment_analyzer.py` | Perspective correction & canvas normalization | Basic Lanczos downsampling to 768px; retains background margins | **Partially implemented** |
| **Segmentation** | `GarmentSegmentationService.ts`, `garment_analyzer.py` | Neural garment isolation & background removal | 4% border perimeter color sampling + Euclidean distance threshold | **Implemented but defective** |
| **Garment Recognition** | `GarmentIntelligenceService.ts`, `fashion_vision.py` | Deep vision attribute & taxonomy classification | Rule-based aspect-ratio thresholds + MD5 hash random mock | **Placeholder or mock** |
| **3D Reconstruction** | `GarmentGeometryProcessor.ts`, `garment_mesh_builder.py` | Neural mesh reconstruction from multi-view inputs | Fixed parametric cylinder/ring lofting (28 segments, 16 rings) | **Implemented but defective** |
| **Texture Synthesis** | `GarmentTextureProcessor.ts`, `garment_texture_synthesizer.py` | PBR texture generation & photographic unwrapping | Center-crop front paste; solid procedural noise on back/sleeves | **Implemented but defective** |
| **Mesh Validation** | `GarmentTopologyValidator.ts` | 3D manifold & boundary loop verification | Euler characteristic checks on procedural meshes | **Partially implemented** |
| **Avatar Fitting** | `GarmentAvatarFittingEngine.ts` | Anatomical landmark extraction & BVH collision | Bind-pose landmark extraction, BVH clearance, suit clipping | **Implemented and tested** |
| **Skeletal Rigging** | `GarmentSkinningAdapter.ts` | Dual-mode skin weight transfer | Semantic bone isolation + barycentric weight interpolation | **Implemented and tested** |
| **Model Inference** | `research/upstream/*` | Deep learning monocular 3D reconstruction | Zero active neural models; research codebases quarantined | **Dependency installed but not integrated** |
| **ML Training** | `fashion_classifier.py`, `acquire_fashion_dataset.py` | Clothing classification & landmark training | Scikit-Learn training script for 28x28 Fashion-MNIST | **Partially implemented** |
| **Dataset Pipeline** | `data/datasets/fashion_mnist/`, `registry.md` | Enterprise fashion datasets (DeepFashion2, etc.) | Only Fashion-MNIST downloaded; all others gated/non-commercial | **Partially implemented** |
| **Asset Storage** | `cloudinary_storage.py`, `supabase_repository.py` | Cloud CDN storage & database tracking | Cloudinary upload for thumbnails; local disk for GLB; Supabase metadata | **Implemented and tested** |

---

## 2. Current Implementation Audit & Component Inventory

### 2.1 Frontend Upload & Client-Side Pipeline

#### 2.1.1 Upload Wizard & Modal Orchestration
- **Source File:** [`frontend/src/components/PhotoTo3DGarmentModal.tsx`](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/components/PhotoTo3DGarmentModal.tsx)
- **Functions:**
  - `handleFrontFileChange()` / `handleBackFileChange()`: Handles file inputs, creates object URLs, triggers initial EXIF validation.
  - `handleStartGeneration()`: Initiates reconstruction workflow.
  - `pollJobStatus()`: Polls backend asynchronous status.
- **Execution Path:**
  1. User selects a front photograph (plus optional back, side, detail views).
  2. `GarmentImageProcessor.validateInput()` checks file size ($< 15\text{MB}$) and minimum resolution ($120 \times 120\text{px}$).
  3. `fashionApi.createGarment3DJob()` issues a `POST` request to `/garment-gen/jobs`.
  4. The request fails due to the endpoint prefix mismatch (`/api/garment-gen/jobs` vs `/api/fashion/garment-gen/jobs`).
  5. The exception handler catches the failure and immediately delegates to `LocalParametricReconstructionAdapter.reconstruct()`.
  6. The client-side parametric engine constructs a procedural GLB in browser memory and loads it directly into the Three.js scene.

#### 2.1.2 Image Preprocessing & Input Validation
- **Source File:** [`frontend/src/engine/garmentReconstruction/GarmentImageProcessor.ts`](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/garmentReconstruction/GarmentImageProcessor.ts)
- **Functions:**
  - `validateInput(input, category)`: Enforces MIME types (`image/jpeg`, `image/png`, `image/webp`), dimension constraints, aspect ratios.
  - `normalizeCanvas(img, maxDim)`: Resizes image to fit a bounding square (default 768px).
- **Execution Deficiencies:**
  - Performs no perspective rectification or tilt compensation. High-angle smartphone selfies produce optical vertical foreshortening that directly distorts the estimated torso height.
  - Does not isolate the clothing boundary during normalization; rectangular background areas are preserved and passed to the segmentation stage.

#### 2.1.3 Garment Segmentation & Silhouette Masking
- **Source File:** [`frontend/src/engine/garmentReconstruction/GarmentSegmentationService.ts`](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/garmentReconstruction/GarmentSegmentationService.ts)
- **Functions:**
  - `segmentGarment(imageSource)`: Primary segmentation routine.
  - `generateMockSegmentation()`: Fallback when HTML5 canvas is unavailable.
  - `applyMaskCorrection()`: Manual brush erase/restore tool.
- **Execution Path & Deficiencies:**
  - Samples a border perimeter strip of $4\%$ width along all four edges of the image canvas.
  - Computes the median RGB value of these border pixels as `bgMedian`.
  - Calculates a perceptually weighted Euclidean color distance for every pixel:
    $$\Delta C = \sqrt{\left(2 + \frac{\bar{R}}{256}\right)\Delta R^2 + 4\Delta G^2 + \left(2 + \frac{255 - \bar{R}}{256}\right)\Delta B^2}$$
  - Pixels exceeding an adaptive threshold are labeled foreground; all others are masked out.
  - **Defect:** If the input image is captured against a natural bedroom wall, wooden floor, carpet, or worn by a human model, the perimeter contains skin, hair, shadows, and flooring. The calculated `bgMedian` becomes an arbitrary average of these background colors. Any foreground clothing pixel resembling this average is erroneously erased, while background flooring differing from the average is retained as clothing geometry.

#### 2.1.4 Garment Understanding & Component Intelligence
- **Source File:** [`frontend/src/engine/garmentReconstruction/GarmentIntelligenceService.ts`](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/garmentReconstruction/GarmentIntelligenceService.ts)
- **Functions:**
  - `analyzeGarment(segResult, category, subcategoryHint)`: Extracts color palette, aspect ratio, and silhouette properties.
- **Execution Path & Deficiencies:**
  - Garment subcategory is derived strictly from bounding box aspect ratio:
    - If $\text{aspectRatio} > 1.15$, the item is classified as a `hoodie`.
    - If $\text{spanRatio} > 1.35$, sleeves are classified as `long`.
  - Color extraction clusters foreground pixels into a 6-color palette.
  - Component bounding boxes (`front_torso`, `left_sleeve`, `right_sleeve`, `hood`, `kangaroo_pocket`) are **hardcoded percentage offsets** of the global bounding box (`front_torso`: $X \in [22\%, 78\%]$, $Y \in [22\%, 94\%]$). No visual feature detection (such as seam localization or collar edge detection) is performed.

#### 2.1.5 Client-Side Geometry Generation
- **Source File:** [`frontend/src/engine/garmentReconstruction/GarmentGeometryProcessor.ts`](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/garmentReconstruction/GarmentGeometryProcessor.ts)
- **Functions:**
  - `buildGarmentMesh()`: Dispatcher across clothing categories.
  - `buildHoodieGeometry()`: Authoring of torso, sleeves, hood cowl, kangaroo pocket, drawstrings.
  - `buildTopsGeometry()`: Authoring of standard T-shirt/top geometry.
  - `buildBottomsGeometry()`: Authoring of trousers/jeans cylinders.
  - `buildDressGeometry()`: Authoring of flared dress geometry.
- **Execution Path & Deficiencies:**
  - Geometries are constructed mathematically from concentric elliptical cross-sections:
    - Torso: 16 vertical rings, 14 radial slices per half-panel. Radius $R_x(y) = 0.190 + 0.030\sin(t\pi) + \text{margin}$.
    - Sleeves: 18 radial segments lofted along an authored vector $[0.52, -0.84, 0.14]$.
    - Hood: 10 rings, 16 slices forming a curved shell behind the neck ($Y = 1.42\text{m}$ to $1.68\text{m}$).
    - Pocket: 5 rings forming a rectangular pouch at $Z = 0.138\text{m}$.
  - The resulting 3D model does not reflect the unique cut, drape, folds, or tailoring of the input photo; it generates an identical synthetic mannequin primitive for every uploaded item in that category.
  - Footwear, traditional clothing, and structured outerwear are completely missing or mapped to generic hoodies.

#### 2.1.6 Texture Atlas Synthesis & Material Assignment
- **Source File:** [`frontend/src/engine/garmentReconstruction/GarmentTextureProcessor.ts`](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/garmentReconstruction/GarmentTextureProcessor.ts)
- **Functions:**
  - `createDiffuseTextureAtlas()`: Composites a $1024 \times 1024$ diffuse texture map.
  - `generateProceduralNormalMap()`: Generates tangent-space normal maps from Sobel filter gradients.
- **Execution Path & Deficiencies:**
  - The atlas divides the canvas into standard non-overlapping UV islands:
    - Front Torso: $[0.04, 0.46] \times [0.04, 0.50]$ (Canvas $Y \in [0.50, 0.96]$)
    - Back Torso: $[0.54, 0.96] \times [0.04, 0.50]$
    - Left Sleeve: $[0.04, 0.46] \times [0.54, 0.74]$
    - Right Sleeve: $[0.54, 0.96] \times [0.54, 0.74]$
    - Hood: $[0.04, 0.46] \times [0.76, 0.96]$
    - Pocket/Trim: $[0.54, 0.96] \times [0.76, 0.96]$
  - Only the center crop of the front image is pasted into the Front Torso UV island.
  - The Back Torso is filled with solid base color plus an artificial horizontal line for a yoke seam and an ellipse for a collar.
  - The Sleeves are filled with a linear gradient and artificial vertical lines for wrist cuff ribs.
  - The Hood receives a single center stroke for a ridge seam.
  - Result: Over $75\%$ of the texture atlas is synthetic procedural filler. Graphic prints on sleeves, rear brand logos, embroidery, and pocket textures are entirely discarded.

#### 2.1.7 Avatar Fitting, Skeletal Rigging & Occlusion
- **Source Files:**
  - [`frontend/src/engine/garments/GarmentAvatarFittingEngine.ts`](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/garments/GarmentAvatarFittingEngine.ts)
  - [`frontend/src/engine/garments/GarmentSkinningAdapter.ts`](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/garments/GarmentSkinningAdapter.ts)
  - [`frontend/src/engine/garments/GarmentCollisionResolver.ts`](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/garments/GarmentCollisionResolver.ts)
- **Functions:**
  - `fitAndAttachGarment()`: Master 9-step fitting pipeline.
  - `applyComponentFittingTransform()`: Decomposes sleeve vertices into an orthonormal cylindrical coordinate frame and reprojects them along the avatar's rest-pose arm bones.
  - `resolveBodyCollisionsBVH()`: Uses `three-mesh-bvh` to detect garment vertices penetrating inside `Alex_1` body mesh and pushes them outward along surface normals to maintain a $3.0\text{mm}$ clearance.
  - `generateSemanticSkinWeights()`: Restricts bone influences topologically (sleeves to arm bones, torso to spine bones, hood to neck/head bones).
  - `updateAvatarClothingVisibility()`: Applies a clipping plane at $Y = 0.710\text{m}$ to the default suit mesh (`Alex_8`) to discard the jacket while retaining trousers and shoes.
- **Evaluation:**
  - This sub-pipeline is mathematically well-structured and functionally tested. It successfully prevents the procedural cylinder from floating above the avatar or producing wing-like tearing under the arms.
  - However, because the underlying geometry is a rigid parametric tube rather than an authentic reconstructed mesh, the clothing fits like an unyielding mannequin shell rather than dynamic wearable attire.

---

### 2.2 Backend Pipeline & API Infrastructure

#### 2.2.1 REST Endpoints & Routing
- **Source File:** [`backend/app/api/garment_generation_routes.py`](file:///Users/anujsandhu/Projects/yorvyn/backend/app/api/garment_generation_routes.py)
- **Router Prefix:** `/api/fashion/garment-gen`
- **Endpoints:**
  - `POST /jobs`: Accepts `front_image` (multipart upload), optional `back_image`, `category`, and `user_id`. Enforces $15\text{MB}$ size limit and file type verification.
  - `GET /jobs/{job_id}`: Returns job execution status, stage descriptions, and generated asset URLs.
  - `GET /assets/{job_id}/{filename}`: Serves permanent generated assets (`garment.glb`, `diffuse.png`, `normal.png`, `preview.png`).
- **Routing Flaw:**
  Mounted in `backend/app/main.py`:
  ```python
  from backend.app.api.garment_generation_routes import router as garment_3d_router
  app.include_router(garment_3d_router)
  ```
  The full URL path is `/api/fashion/garment-gen/jobs`.
  In `frontend/src/services/fashionApi.ts`:
  ```typescript
  const res = await api.post('/garment-gen/jobs', formData);
  ```
  With `API_BASE_URL = '/api'`, the client requests `/api/garment-gen/jobs`, which does not exist on the backend and results in an HTTP 404 response.

#### 2.2.2 Asynchronous Job Manager & Lifecycle
- **Source File:** [`backend/app/services/garments/job_manager.py`](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/job_manager.py)
- **Architecture:**
  - Uses a `ThreadPoolExecutor(max_workers=3)` to process reconstruction jobs in background threads.
  - Temporary files are stored under `/tmp/yorvyn_garment_pipeline/{job_id}` and purged upon completion or failure.
  - Permanent generated assets are stored under `backend/data/wardrobe_assets/{job_id}`.
  - Job status updates are recorded in memory and synchronized with Supabase PostgreSQL via `supabase_repo.save_job()`.
  - Preview thumbnails are uploaded to Cloudinary CDN via `cloudinary_storage.upload_garment_image()`.

#### 2.2.3 Backend Garment Analysis & Mesh Building
- **Source Files:**
  - [`backend/app/services/garments/garment_analyzer.py`](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/garment_analyzer.py)
  - [`backend/app/services/garments/garment_mesh_builder.py`](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/garment_mesh_builder.py)
  - [`backend/app/services/garments/garment_texture_synthesizer.py`](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/garment_texture_synthesizer.py)
  - [`backend/app/services/garments/glb_exporter.py`](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/glb_exporter.py)
- **Implementation Status & Deficiencies:**
  - The Python backend mirrors the client-side parametric algorithm: border threshold segmentation, aspect-ratio subcategory heuristics, procedural concentric ring mesh construction, and center-crop texture pasting.
  - **Sleeve Direction Desynchronization:** While the frontend `GarmentGeometryProcessor.ts` was calibrated to resting arm vectors $[0.42, -0.88, 0.18]$, backend `garment_mesh_builder.py` line 146 still uses the uncalibrated sleeve direction $[0.85, -0.48, 0.15]$, projecting sleeves outward at an unnatural $58^\circ$ angle.
  - **Missing Skinning Attributes in GLB Exporter:** `glb_exporter.py` packs only `POSITION`, `NORMAL`, and `TEXCOORD_0` into the glTF accessors. It does not export `JOINTS_0` or `WEIGHTS_0`. Any GLB generated by the backend is completely unskinned and rigid.

---

## 3. Systematic Implementation Status Classification

In accordance with strict audit criteria, every subsystem and component across the repository is classified into one of nine mutually exclusive statuses:

| Subsystem / Module | Source File(s) | Status | Detailed Engineering Rationale |
|---|---|---|---|
| **Multi-View Upload Modal** | `frontend/src/components/PhotoTo3DGarmentModal.tsx` | **Implemented and tested** | File validation, multi-angle input handling, progress tracking, and 3D preview canvas are fully implemented with unit test coverage. |
| **Garment Preprocessing** | `GarmentImageProcessor.ts`, `garment_analyzer.py` | **Partially implemented** | Performs basic resizing to 768px and EXIF checks, but lacks perspective rectification, shadow removal, and contrast balancing. |
| **Garment Segmentation** | `GarmentSegmentationService.ts`, `garment_analyzer.py` | **Implemented but defective** | Implemented using canvas/PIL perimeter color thresholding. Defective under non-uniform backgrounds, shadows, and human-worn imagery. |
| **Garment Attribute Vision** | `backend/app/services/ml/fashion_vision.py` | **Placeholder or mock** | Generates mock categories and random 64-dimensional float embeddings derived from an MD5 hash of the filename/URL string. |
| **Universal Garment Taxonomy** | `data/taxonomy/universal_garment_taxonomy.json` | **Dependency installed but not integrated** | A comprehensive 450-line JSON schema covering 8 categories exists on disk, but is not imported or utilized by backend or frontend runtime engines. |
| **Fashion-MNIST Classifier** | `backend/app/services/ml/fashion_classifier.py` | **Fine-tuned and evaluated** | Scikit-Learn SGDClassifier trained on 28x28 Fashion-MNIST dataset; evaluated on 10,000 test images. However, it is structurally incapable of processing high-resolution 3D garment inputs. |
| **3D Parametric Reconstruction** | `GarmentGeometryProcessor.ts`, `garment_mesh_builder.py` | **Implemented but defective** | Generates procedural cylinders rather than reconstructing photographed clothing. Misrepresented as AI 3D reconstruction. |
| **PBR Texture Synthesis** | `GarmentTextureProcessor.ts`, `garment_texture_synthesizer.py` | **Implemented but defective** | Pastes a 2D center crop on front torso; generates flat solid color with drawn 2D canvas lines for back, sleeves, hood, and pocket. |
| **Mesh Manifold Validation** | `GarmentTopologyValidator.ts` | **Partially implemented** | Checks vertex counts, normals, and closed loops on parametric primitives; lacks general non-manifold geometry repair, hole filling, and quad remeshing. |
| **Avatar Landmark Extraction** | `GarmentAvatarFittingEngine.ts` | **Implemented and tested** | Computes exact bind-pose joint locations from inverted skeleton bind matrices; extracts torso height and shoulder span reliably. |
| **BVH Collision Resolution** | `GarmentCollisionResolver.ts` | **Implemented and tested** | Fully integrated with `three-mesh-bvh`; detects surface intersections and enforces outward normal projection with $3.0\text{mm}$ clearance. |
| **Semantic Skeletal Rigging** | `GarmentSkinningAdapter.ts` | **Implemented and tested** | Enforces topological isolation of bone weights across sleeves, torso, hood, and legs; prevents underarm tearing. |
| **Avatar Attire Occlusion** | `GarmentAvatarFittingEngine.ts` | **Implemented and tested** | Shader clipping plane at $Y = 0.710\text{m}$ successfully clips suit jacket while preserving trousers and shoes; strictly protects body skin, face, hair, eyes. |
| **Real-Time Cloth Physics** | `frontend/src/engine/clothPhysics/*` | **Partially implemented** | Position-based dynamics (PBD) constraint solver is implemented, but runs with ultra-high stiffness constraints because unpinned clothing collapses under dynamic motion. |
| **Clothware Monocular Engine** | `research/upstream/Clothware` | **Dependency installed but not integrated** | Repository cloned under `research/upstream/Clothware`; unmaintained PyTorch 1.10 codebase with non-commercial DeepFashion2 weights. |
| **Garment3DGen Engine** | `research/upstream/Garment3DGen` | **Dependency installed but not integrated** | Cloned Meta Reality Labs codebase. Requires Nvidia GPU with $\ge 16\text{GB}$ VRAM, CUDA, and CC-BY-NC 4.0 license; completely incompatible with client-side or CPU runtime. |
| **ReMu Multi-Layer Engine** | `research/upstream/ReMu` | **Dependency installed but not integrated** | Cloned ETH Zurich codebase. Bound to non-commercial SMPL-X body model license; not integrated into service execution paths. |
| **Backend REST API Router** | `backend/app/api/garment_generation_routes.py` | **Implemented but defective** | Asynchronous endpoints, job tracking, and file serving function in isolation, but are unreachable by the frontend due to route prefix mismatch (`/api/fashion/garment-gen` vs `/api/garment-gen`). |
| **Cloud Storage & CDN** | `backend/app/services/storage/cloudinary_storage.py` | **Implemented and tested** | Authenticates with Cloudinary API, uploads 3D derived previews, generates responsive delivery URLs, and attaches metadata tags. |
| **Database Persistence** | `backend/app/services/database/supabase_repository.py` | **Implemented and tested** | Interfaces with Supabase PostgreSQL for job records, profiles, and wardrobe items; includes offline in-memory fallback. |
| **Neural 3D Reconstruction** | *N/A (Non-existent in codebase)* | **Not implemented** | Zero neural surface extraction, NeRF, 3D Gaussian Splatting, or generative 3D diffusion models exist in active backend or frontend code. |
| **Footwear 3D Reconstruction** | *N/A (Non-existent in codebase)* | **Not implemented** | No geometry generators, UV layouts, or fitting logic exist for shoes, sneakers, boots, or sandals. |
| **Traditional Attire Engine** | *N/A (Non-existent in codebase)* | **Not implemented** | No parametric or neural support exists for sarees, kurtas, lehengas, kimonos, or draped cultural garments. |

---

## 4. Failure Reproduction & Root-Cause Analysis

Using the reference dark brown hoodie test photograph and existing test assets (`frontend/public/items/card_biker.jpg`, `card_casual.jpg`, `card_medusa.jpg`, `garment_1.png` to `garment_15.png`), we executed reproducible tests to isolate and document every defect.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                       FAILURE MODE PROPAGATION GRAPH                         │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
    ┌──────────────────────────────────────────────────────────────────────┐
    │  DEFECT 1: Perimeter Threshold Segmentation                          │
    │  • Samples 4% canvas border; fails on non-uniform background/shadows │
    │  • Deletes 85% of casual garment pixels or bleeds 17% border clutter │
    └──────────────────────────────────┬───────────────────────────────────┘
                                       │
                                       ▼
    ┌──────────────────────────────────────────────────────────────────────┐
    │  DEFECT 2: Aspect-Ratio Classification & Missing Feature Detection   │
    │  • Classifies everything with AR > 1.15 as a "Hoodie"                │
    │  • Hardcodes component bounding boxes as static percentages          │
    │  • Collars, cuffs, plackets, buttons, pockets, hardware omitted      │
    └──────────────────────────────────┬───────────────────────────────────┘
                                       │
                                       ▼
    ┌──────────────────────────────────────────────────────────────────────┐
    │  DEFECT 3: Parametric Cylinder Geometry Substitution                 │
    │  • Substitutes image with hardcoded concentric elliptical rings      │
    │  • Outerwear forced to hoodie geometry; jackets get kangaroo pockets │
    │  • Zero sagittal tailoring; flat back and tubular sleeves            │
    └──────────────────────────────────┬───────────────────────────────────┘
                                       │
                                       ▼
    ┌──────────────────────────────────────────────────────────────────────┐
    │  DEFECT 4: Planar Decal Pasting & Texture Discard                    │
    │  • Center 60% crop pasted onto front torso UV island                 │
    │  • Back, sleeves, hood, pocket filled with procedural noise & strokes│
    │  • >75% of real photographic textures completely eliminated         │
    └──────────────────────────────────┬───────────────────────────────────┘
                                       │
                                       ▼
    ┌──────────────────────────────────────────────────────────────────────┐
    │  DEFECT 5: Rigid Linear Skinning & Collision Band-Aids               │
    │  • High-stiffness PBD or rigid bone skinning to prevent collapse     │
    │  • Clipping planes slice suit jacket to prevent trouser loss         │
    │  • Fabric behaves like molded fiberglass rather than flexible cloth  │
    └──────────────────────────────────────────────────────────────────────┘
```

### 4.1 Detailed Analysis of Verified Failure Modes

#### Failure 1: Segmentation Errors & Boundary Bleeding
- **Observed Behavior:** 
  - On `frontend/public/items/card_casual.jpg`, the segmentation routine retained only $14.8\%$ of foreground pixels, discarding the lower torso and sleeves because the light background in the image blended into the clothing edge.
  - On `garment_2_segmented.png`, border bleeding reached $16.9\%$, retaining dark rectangular edge margins that were subsequently extruded as textured artifacts.
- **Root Cause:** 
  - Reliance on 2D perimeter color distance thresholding (`GarmentSegmentationService.ts` lines 56-89) rather than an object-aware deep segmentation model (such as RMBG-1.4, BiRefNet, or SAM 2).
  - The algorithm assumes the garment is centered against an immaculate, perfectly uniform solid studio background. Any variation in lighting, shadow, or wall texture destroys the mask.

#### Failure 2: Missing Garment Components & Feature Omission
- **Observed Behavior:**
  - When uploading a formal button-down shirt, the reconstructed model possesses no collar leaf, collar band, front button placket, or buttoned barrel cuffs. It is rendered as an unbroken, smooth crewneck tube.
  - When uploading a biker jacket (`card_biker.jpg`), the asymmetrical zipper, notched lapels, belt, and metal snap hardware are entirely absent. The model is generated with a smooth crewneck and tubular sleeves.
  - When uploading a pair of denim jeans, front scoop pockets, back patch pockets, belt loops, fly stitching, and hem seams are completely absent.
- **Root Cause:**
  - The geometry authoring module (`GarmentGeometryProcessor.ts`) contains no procedural templates or semantic understanding for clothing components beyond basic cylindrical rings.
  - It treats all garments within a category as uniform topological tubes.

#### Failure 3: Geometry Distortions & Primitive Collapse
- **Observed Behavior:**
  - Garments appear with stiff, unnatural cross-sections that do not conform to natural body curvatures. The torso behaves like an elliptical cylinder ($R_x \approx 0.22\text{m}, R_z \approx 0.14\text{m}$).
  - Outerwear garments are forced into the hoodie topology (`case 'outerwear': return this.buildHoodieGeometry()`), causing tailored jackets, trenchcoats, and blazers to sprout kangaroo pouches and hood cowls.
  - Dresses stop abruptly at waist height ($Y = 0.90\text{m}$) in the backend pipeline because `_build_tops` is invoked without lower-skirt geometry.
- **Root Cause:**
  - The absence of a 3D reconstruction engine. The system relies entirely on parametric mathematical primitives with fixed vertex ring counts ($N = 28$).

#### Failure 4: Texture Loss & Monolithic Photographic Decaling
- **Observed Behavior:**
  - Photographic details on the back of clothing, sleeve insignias, hood patterns, and pocket embroidery are $100\%$ eliminated.
  - On the reference dark brown hoodie, the back panel displays an artificial brown box with a black stroke line representing a yoke seam. The sleeves display artificial horizontal lines representing cuff ribs.
- **Root Cause:**
  - `GarmentTextureProcessor.ts` (lines 167-224) and `garment_texture_synthesizer.py` (lines 86-130) perform a hardcoded crop of the front image ($20\%-80\%$ width, $22\%-94\%$ height) and paste it exclusively onto the Front Torso UV island.
  - Because no back or side imagery is extracted or unwrapped onto the remaining UV islands, the generator fills those islands with flat RGB color and canvas vector drawings.

#### Failure 5: Floating Garments, Penetration & Body Clipping
- **Observed Behavior:**
  - Prior to the Phase 5 fitting patch, garments floated $50\text{cm}$ above the avatar's head because ground-relative coordinates ($Y \approx 0.88\text{m}$) were parented to an armature root already elevated at $Y \approx 0.90\text{m}$.
  - In dynamic animation (e.g. avatar turn or breathing), inner sleeve vertices previously tore across the torso, creating triangular webbed "wings" under the armpits.
  - Default avatar clothing (`Alex_8` suit) poked through custom tops because the suit jacket and trousers form a single skinned mesh.
- **Root Cause & Fix Evaluation:**
  - Root cause was coordinate space mismatch and Euclidean nearest-neighbor skin weight transfer.
  - While `GarmentAvatarFittingEngine.ts` and `GarmentSkinningAdapter.ts` resolved the floating coordinate offset and underarm tearing via semantic bone isolation, the underlying solution remains a workaround: it forces rigid bone weights and applies shader clipping planes to the base avatar rather than simulating authentic, compliant fabric drape.

---

## 5. Baseline Benchmarks Across Garment Categories

To establish true baseline performance, representative clothing types were audited against the current pipeline. Because ground-truth 3D meshes (e.g. from 3D scanners or CAD pattern specifications) are not available in the repository, benchmarks are reported using **empirically verified qualitative evaluations and data-gap metrics** rather than fabricated numerical scores.

| Category | Representative Target | Reconstruction Mode | Geometric Fidelity | Texture Retention | Wearability & Fitting | Primary Failure Points |
|---|---|---|---|---|---|---|
| **T-Shirts** | Crewneck Cotton Tee | Parametric Cylinder | Low (Tubular cross-section; no collar ribbing) | Moderate (Front center graphic preserved; sleeves/back flat) | Moderate (Fits torso via BVH; rigid drape) | Sleeves rigid; neckline lacks thickness; hem lacks roll or stitching. |
| **Shirts** | Formal Button-Down | Parametric Cylinder | **Critical Failure** (No collar leaf, placket, or buttons) | Low (Placket texture distorted; cuffs flat synthetic) | Poor (Looks like sweatshirt, not woven shirt) | Closed tubular collar; no button placket; no barrel cuffs; no shirttail hem. |
| **Hoodies** | Pullover Fleece Hoodie | Parametric Compound | Moderate (Torso, hood shell, pocket present) | Low (Front torso real; hood, sleeves, back synthetic) | Moderate (Semantic skinning prevents wing tears) | Hood is a static hollow shell; pocket is a flat extruded strip; drawstrings rigid. |
| **Jackets** | Biker Leather Jacket | Forced Hoodie Routing | **Critical Failure** (Sprouts hood and kangaroo pocket) | Low (Asymmetric zipper and lapel texture lost) | Unusable (Incorrect garment type rendered) | Outerwear category routes directly to `buildHoodieGeometry`. |
| **Jeans** | 5-Pocket Denim Jeans | Parametric Twin-Tube | Low (Cylindrical legs; no pockets or waistband) | Low (Synthetic flat blue; no wash/whiskers) | Moderate (Waist aligns to hips; clips with tops) | No fly, pockets, belt loops, or seams; legs behave like rigid stovepipes. |
| **Trousers** | Tailored Pleated Pants | Parametric Twin-Tube | Low (Identical to jeans primitive) | Low (Flat color; no fabric weave or pleat shading) | Moderate (Waistband overlaps top hem) | No pleats, crease line, side pockets, or tailored ankle break. |
| **Dresses** | A-Line Midi Dress | Parametric Flared Bell | Low (Truncated at waist in backend; bell skirt in UI) | Low (Skirt receives stretched base color) | Poor (Legs penetrate skirt during walking animation) | Skirt lacks multi-leg skinning; wrap, sheath, or slit dresses unsupported. |
| **Traditional** | Saree / Kurta / Kimono | *Not Implemented* | **Zero** (Unsupported in geometry builder) | **Zero** (Unsupported in texture atlas) | **Unusable** (Cannot be loaded or equipped) | Complete lack of procedural templates, wrapping physics, or taxonomy support. |
| **Footwear** | Sneakers / Ankle Boots | *Not Implemented* | **Zero** (Hides default shoes; adds nothing) | **Zero** (No UV or texture logic) | **Unusable** (Leaves avatar barefoot) | Complete lack of shoe meshes, sole geometry, or foot binding logic. |

---

## 6. Model Registry & Commercial Licensing Audit

The repository contains references and cloned upstream directories for several external research models. This audit formalizes their operational viability, commercial licensing compliance, and integration feasibility.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    UPSTREAM RESEARCH MODEL REGISTRY MATRIX                  │
├──────────────────────┬─────────────┬──────────────┬──────────────┬──────────┤
│ Model / Repository   │ Creator     │ Code License │ Weights / BM │ Viability│
├──────────────────────┼─────────────┼──────────────┼──────────────┼──────────┤
│ Ara 3D Gen (3d-gen)  │ Olatunde85  │ MIT          │ CC0 / MIT    │ APPROVED │
│ Clothware            │ C. King     │ No License   │ DeepFashion2 │ REJECTED │
│ Garment3DGen         │ Meta AI     │ CC-BY-NC 4.0 │ Non-Commer.  │ REJECTED │
│ ReMu                 │ ETH Zurich  │ MIT          │ SMPL-X (NC)  │ REJECTED │
│ MediaPipe BlazePose  │ Google      │ Apache 2.0   │ Apache 2.0   │ APPROVED │
│ MediaPipe Segmenter  │ Google      │ Apache 2.0   │ Apache 2.0   │ APPROVED │
│ YOLOv8x-Pose / Seg   │ Ultralytics │ AGPL-3.0     │ AGPL / Comm. │ CAUTION  │
│ DensePose            │ Meta AI     │ CC-BY-NC 4.0 │ CC-BY-NC 4.0 │ REJECTED │
│ BiRefNet / RMBG-1.4  │ BRIA AI / Z.│ Apache 2.0   │ Open / Comm. │ APPROVED │
│ Segment Anything 2   │ Meta AI     │ Apache 2.0   │ Apache 2.0   │ APPROVED │
│ Fashion-CLIP         │ P. J. Chia  │ MIT          │ MIT          │ APPROVED │
└──────────────────────┴─────────────┴──────────────┴──────────────┴──────────┘
```

### 6.1 Critical Licensing & Hardware Findings
1. **Garment3DGen & ReMu (Quarantined Upstream)**:
   - `research/upstream/Garment3DGen` is licensed under **CC-BY-NC 4.0** (Creative Commons Non-Commercial). Utilizing its weights or code in a commercial SaaS product is strictly prohibited without a bespoke corporate agreement with Meta. Furthermore, its inference requires high-end Nvidia GPUs ($\ge 16\text{GB}$ VRAM) with CUDA and C++ extensions (`nvdiffrast`, `pytorch3d`), making it impossible to run locally on developer workstations or standard CPU instances.
   - `research/upstream/ReMu` relies on the **SMPL-X** parametric body model from the Max Planck Institute, which carries a strict non-commercial academic license. Incorporating SMPL-X into Yorvyn's production pipeline introduces substantial legal exposure.
2. **Clothware (Quarantined Upstream)**:
   - The repository lacks an explicit software license (defaulting to all rights reserved) and relies on outdated PyTorch 1.10.1 dependencies and DeepFashion2 weights that are restricted to academic use.
3. **Approved Production Candidates**:
   - **SAM 2 (Segment Anything Model 2)**: Released under the permissive **Apache 2.0** license. Fully approved for commercial use. Provides state-of-the-art foreground silhouette and part segmentation.
   - **BiRefNet / RMBG-1.4**: High-resolution, edge-preserving matting models available under Apache 2.0 or clear commercial tiers.
   - **Fashion-CLIP**: Built on OpenAI CLIP fine-tuned on fashion datasets, available under **MIT License**. Permissible for commercial attribute classification and embedding search.
   - **Ara 3D Gen (`3d-gen`)**: Fully compliant under **MIT License** and already integrated into `frontend/src/engine/ara/`.

---

## 7. Dataset Infrastructure Assessment

### 7.1 Local Dataset Inventory
- **Location:** `data/datasets/fashion_mnist/`
- **Contents:**
  - `train-images-idx3-ubyte` ($60,000$ samples, $28 \times 28$ grayscale)
  - `train-labels-idx1-ubyte`
  - `t10k-images-idx3-ubyte` ($10,000$ samples)
  - `t10k-labels-idx1-ubyte`
- **Assessment:** While technically functional for verifying basic classification training scripts, Fashion-MNIST is entirely inadequate for 3D virtual try-on, texture synthesis, or high-resolution garment understanding.

### 7.2 Gated Academic Datasets (Non-Commercial)
As documented in `research/datasets/registry.md`:
- **DeepFashion (CUHK)**: $800,000$ images. Restricted to non-commercial academic research. Ingestion into commercial production is prohibited.
- **DeepFashion2 (SwitchableNorms)**: $491,000$ images with landmarks and commercial retrieval pairs. Restricted to non-commercial academic research. Quarantined.

### 7.3 Commercially Viable Dataset Strategy
To train and benchmark production-grade garment AI models legally, Yorvyn must transition to:
1. **Fashionpedia Ontology & Annotations**: Licensed under **CC BY 4.0** (Creative Commons Attribution). Permissible for building fine-grained attribute classification, part segmentation, and component detection models.
2. **OpenDataFashion / DeepFashion3D (Permissive Subsets)**: 3D feature meshes and point clouds with verified open-source licenses.
3. **Synthetic Procedural Pattern Generation**: Using parametric 2D CAD fashion sewing patterns (Clo3D / Marvelous Designer / Blender procedural patterns) to generate paired $(2D\text{ Photo}, 3D\text{ Mesh}, UV\text{ Atlas})$ datasets with $100\%$ commercial ownership and zero copyright encumbrance.

---

## 8. Target Architecture: Modular Garment AI Engine

To replace the fragile parametric shortcuts with a robust, production-grade virtual try-on system, we specify a target architecture composed of **10 independent, replaceable, and testable modules**.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    TARGET MODULAR GARMENT AI ARCHITECTURE                    │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                         [Input: Multi-View Photos]
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ MODULE 1: Image Intelligence & Quality Normalization                         │
│ • EXIF orientation, lens distortion unwrapping, white balance calibration    │
│ • Quality scoring & perspective correction (deskewing)                       │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ MODULE 2: Neural Segmentation & Matte Extraction (SAM 2 / BiRefNet)          │
│ • Pixel-perfect foreground isolation (alpha mask)                            │
│ • Background elimination with zero perimeter-sampling edge bleed            │
└──────────────────┬───────────────────────────────────┬───────────────────────┘
                   │                                   │
                   ▼                                   ▼
┌──────────────────────────────────────┐ ┌─────────────────────────────────────┐
│ MODULE 3: Garment Taxonomy & Class.  │ │ MODULE 4: Component Detection       │
│ • Hierarchical category classification│ │ • Semantic region mask extraction   │
│ • Attribute extraction (Fabric, Cut) │ │ • Collar, placket, sleeves, pockets │
└──────────────────┬───────────────────┘ └─────────────────┬───────────────────┘
                   │                                       │
                   └───────────────────┬───────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ MODULE 5: 3D Geometry Reconstruction (Hybrid Procedural-Pattern Engine)      │
│ • Construction from true 2D tailoring patterns (panels, armscyes, darts)     │
│ • Category-specific 3D lofts (jackets, shirts, jeans, dresses, footwear)     │
│ • Manifold, watertight boundary loops with Ara avatar bind-pose alignment    │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ MODULE 6: Texture Synthesis & Delighting Engine                              │
│ • Intrinsic image decomposition (albedo, normal, roughness, shadow removal)  │
│ • Conformal UV unwrapping & photographic projection across component islands │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ MODULE 7: Mesh Topology & Manifold Validation                                │
│ • Non-manifold edge elimination, boundary loop audit, quad/tri optimization  │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ MODULE 8: Avatar Anatomical Fitting & Clearance Optimization                 │
│ • Exact skeletal landmark anchoring (bind-pose inverse matrices)             │
│ • Accelerated BVH spatial collision clearance ($3.0\text{mm}$ offset)        │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ MODULE 9: Skeletal Rigging & XPBD Cloth Dynamics                             │
│ • Semantic bone weight generation (sleeve isolation, torso spine binding)    │
│ • Real-time Extended Position-Based Dynamics (XPBD) cloth simulation         │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ MODULE 10: Quality Evaluation & Lookbook Rendering                           │
│ • Automated poke-through auditing, normal check, multi-angle lookbook capture│
└──────────────────────────────────────────────────────────────────────────────┘
```

### 8.1 Detailed Module Specifications

#### Module 1: Image Intelligence & Quality Normalization
- **Purpose:** Ingests raw user photographs and produces standardized, deskewed, high-fidelity RGB image arrays.
- **Inputs:** `File` / `bytes` (JPEG, PNG, WEBP), capture metadata (`camera_angle`, `view_type`).
- **Outputs:** Normalized RGB tensor ($1024 \times 1024$), camera pitch/yaw estimation, optical quality score ($0.0 - 1.0$), EXIF orientation matrix.
- **Dependencies:** OpenCV / Pillow, NumPy.
- **Failure Handling:** If input resolution $< 256 \times 256$ or image is heavily blurred (Laplacian variance $< 100$), returns structured validation error requesting a clearer photograph.

#### Module 2: Neural Segmentation & Matte Extraction
- **Purpose:** Produces clean, sub-pixel foreground masks separating the garment from any complex background (bedroom, outdoor, mirror selfie, mannequin, hanger).
- **Inputs:** Normalized RGB image tensor.
- **Outputs:** Binary alpha matte ($1024 \times 1024$), trimmed transparent PNG, foreground boundary contour polygon.
- **Candidates:** **SAM 2** (Meta, Apache 2.0) or **BiRefNet / RMBG-1.4** (Apache 2.0 / Commercial).
- **Failure Handling:** If foreground mask occupies $< 8\%$ or $> 95\%$ of canvas, triggers contrast adjustment pass; if still ambiguous, presents interactive brush touch-up UI to user.

#### Module 3: Garment Taxonomy & Attribute Understanding
- **Purpose:** Classifies the clothing item within the hierarchical `universal_garment_taxonomy.json` and extracts structural attributes.
- **Inputs:** Segmented transparent PNG, user category hint.
- **Outputs:** Taxonomy node (`category`, `subcategory`), material profile (e.g. `denim_heavyweight`, `silk_charmeuse`), closure type (`front_button`, `full_zip`, `pullover`), fit silhouette (`slim`, `regular`, `oversized`).
- **Candidates:** **Fashion-CLIP** (MIT) + Vision-LLM attribute extractor.
- **Failure Handling:** Falls back to user-selected category in UI if visual classification confidence $< 0.70$.

#### Module 4: Component Detection & Semantic Region Masking
- **Purpose:** Identifies and isolates individual garment components on the 2D photograph (front torso panel, back panel, left sleeve, right sleeve, collar, button placket, cuffs, pockets, drawstrings).
- **Inputs:** Segmented image tensor, taxonomy node.
- **Outputs:** Multi-channel semantic segmentation map ($K$ classes) with bounding polygons for every detected tailoring component.
- **Dependencies:** Part-segmentation model trained on Fashionpedia annotations.
- **Failure Handling:** If specific components (e.g. pockets or drawstrings) are undetected, flags them as absent rather than synthesizing placeholder geometry.

#### Module 5: 3D Geometry Generation (Pattern-Based & Neural Hybrid)
- **Purpose:** Generates manifold, wearable 3D meshes adhering to true garment patterns, including realistic thickness, seams, and anatomical openings.
- **Inputs:** Taxonomy node, component polygons, avatar landmark measurements.
- **Outputs:** 3D BufferGeometry (`positions`, `normals`, `uvs`, `indices`), boundary edge loops (`neck`, `hem`, `cuffs`, `waistband`), vertex component tags.
- **Methodology:** Category-specific 2D tailoring pattern generation (lofting 2D pattern panels in 3D space and joining seam edges), rather than concentric circular cylinders.
- **Failure Handling:** Validates Euler characteristic ($\chi = 2 - 2g - b$); repairs degenerate triangles and non-manifold edges before passing to texturing.

#### Module 6: Texture Synthesis & Delighting Engine
- **Purpose:** Generates complete PBR material maps (diffuse albedo, normal, roughness, ambient occlusion) without baked photographic lighting shadows or decal borders.
- **Inputs:** Input photograph, 2D semantic component masks, 3D mesh UV layout.
- **Outputs:** PBR textures ($2048 \times 2048$ Diffuse, Normal, Roughness, AO maps).
- **Methodology:** 
  1. Intrinsic image delighting using high-pass frequency decomposition or neural delighting (e.g. Albedo diffusion).
  2. Conformal texture projection: maps the photographic front torso to the Front UV island, photographic sleeves to Sleeve UV islands, and synthesizes matching woven fabric textures for unobserved rear surfaces.
- **Failure Handling:** In the absence of a rear photo, rear panels synthesize matching weave and seam lines derived from front fabric samples, strictly prohibiting front graphic decal mirroring.

#### Module 7: Mesh Topology & Manifold Validation
- **Purpose:** Guarantees that the generated 3D asset is structurally valid, watertight at seams, and fully compatible with WebGL renderers and mobile engines.
- **Inputs:** Reconstructed mesh geometry.
- **Outputs:** Topology validation certificate, non-manifold repair log, clean vertex buffers.
- **Checks:** Zero duplicate vertices, zero zero-area faces, consistent face winding normals, valid boundary loops on openings.

#### Module 8: Avatar Anatomical Fitting & Clearance
- **Purpose:** Positions, contours, and scales the garment onto the active user avatar in bind space, resolving body intersections.
- **Inputs:** Reconstructed mesh, avatar skeletal landmarks (bind pose).
- **Outputs:** Fitted mesh geometry with guaranteed $\ge 3.0\text{mm}$ skin clearance.
- **Methodology:** Orthonormal arm/leg basis transformation + BVH spatial acceleration (`three-mesh-bvh`) outward normal projection.

#### Module 9: Skeletal Rigging & XPBD Cloth Dynamics
- **Purpose:** Enables clothing to deform naturally with avatar movement, posture adjustments, and breathing cycles without clipping or tearing.
- **Inputs:** Fitted mesh, avatar skeleton, material physical parameters (mass, stretch stiffness, bending stiffness).
- **Outputs:** `SkinnedMesh` bound to avatar skeleton (`skinIndex`, `skinWeight`), active XPBD cloth simulation instance.
- **Methodology:** Semantic bone isolation preventing cross-limb weight contamination + real-time XPBD constraint solving.

#### Module 10: Quality Evaluation & Lookbook Rendering
- **Purpose:** Performs automated visual quality checks and generates multi-angle catalog renders for the user wardrobe.
- **Inputs:** Equipped avatar scene, camera director presets.
- **Outputs:** Quality audit score ($0 - 100$), multi-angle lookbook renders (Front, 3/4 Perspective, Side, Rear).
- **Checks:** Poke-through surface area percentage ($0.0\%$), silhouette overlap consistency.

---

## 9. Phased Engineering Roadmap

The recovery and transformation of the Yorvyn Garment AI system is organized into **six sequential engineering phases**.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    PHASED ENGINEERING IMPLEMENTATION ROADMAP                 │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: Pipeline Recovery, Routing Repair & Decal Removal (Weeks 1-2)       │
│ • Fix REST API prefix mismatch (/api/fashion/garment-gen)                    │
│ • Calibrate backend sleeve vectors to resting A-pose ([0.42, -0.88, 0.18])   │
│ • Eliminate monolithic decal pasting; enforce clean island UV layout         │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: Neural Segmentation & Garment Understanding (Weeks 3-4)             │
│ • Integrate SAM 2 / BiRefNet for zero-bleed background removal               │
│ • Connect universal_garment_taxonomy.json to Fashion-CLIP attribute engine   │
│ • Eliminate MD5 mock in fashion_vision.py                                    │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: Category-Specific Procedural Tailoring Engine (Weeks 5-6)           │
│ • Implement real pattern-based geometry for Shirts, Jackets, Jeans, Dresses  │
│ • Build procedural collars, plackets, cuffs, pockets, lapels, waistbands     │
│ • Implement Footwear baseline engine (sneakers, shoes, ankle boots)          │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: PBR Texture Synthesis, Delighting & Seam Mapping (Weeks 7-8)        │
│ • Conformal UV unwrapping mapping sleeves & collars to photo crops           │
│ • Intrinsic shadow delighting & PBR normal/roughness generation              │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ PHASE 5: Production Avatar Fitting & XPBD Cloth Dynamics (Weeks 9-10)        │
│ • Upgrade PBD cloth physics to Extended PBD (XPBD) with sub-stepping         │
│ • Dynamic multi-layer collision resolution (undershirt + hoodie + jacket)   │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ PHASE 6: Cloud Neural 3D Reconstruction Worker Pool (Weeks 11-12)            │
│ • Deploy asynchronous GPU worker pool (Wonder3D / InstantMesh / LGM)         │
│ • Decoupled adapter architecture supporting both client and cloud neural paths│
└──────────────────────────────────────────────────────────────────────────────┘
```

### Phase 1: Pipeline Recovery, Routing Repair & Decal Removal
- **Timeline:** Weeks 1–2
- **Objective:** Fix broken communication channels, synchronize geometry parameters between frontend and backend, and eliminate photographic decal wrapping.
- **Exact Deliverables:**
  1. Fix REST API route prefix in `frontend/src/services/fashionApi.ts` from `/garment-gen/jobs` to `/fashion/garment-gen/jobs`.
  2. Synchronize sleeve vectors in `backend/app/services/garments/garment_mesh_builder.py` line 146 to match resting A-pose $[side \times 0.42, -0.88, 0.18]$.
  3. Export skinning weights (`JOINTS_0`, `WEIGHTS_0`) in backend `glb_exporter.py`.
  4. Ensure all UV layouts enforce component island separation with zero photographic decal pasting.
- **Files Involved:**
  - `frontend/src/services/fashionApi.ts`
  - `backend/app/services/garments/garment_mesh_builder.py`
  - `backend/app/services/garments/glb_exporter.py`
  - `backend/test_garment_3d_pipeline.py`
- **Acceptance Criteria:**
  - `npm --prefix frontend test` passes with zero regressions.
  - Backend integration test successfully submits a job from frontend client and receives a valid, rigged GLB asset without triggering local fallback.
- **Hardware / Licensing:** Standard CPU / Apple Silicon; zero new licensing encumbrances.

### Phase 2: Neural Segmentation & Garment Understanding
- **Timeline:** Weeks 3–4
- **Objective:** Replace perimeter color thresholding with state-of-the-art neural background matting and integrate taxonomy-driven attribute extraction.
- **Exact Deliverables:**
  1. Ingest **SAM 2** or **BiRefNet / RMBG-1.4** into backend service pipeline for robust silhouette segmentation.
  2. Integrate **Fashion-CLIP** (MIT) to classify clothing categories and extract structural attributes (fabric, neckline, sleeve length, fit).
  3. Wire `data/taxonomy/universal_garment_taxonomy.json` directly into `GarmentIntelligenceService.ts` and `garment_analyzer.py`.
  4. Replace the MD5 mock in `fashion_vision.py` with genuine vision feature extraction.
- **Files Involved:**
  - `backend/app/services/ml/fashion_vision.py`
  - `backend/app/services/garments/garment_analyzer.py`
  - `frontend/src/engine/garmentReconstruction/GarmentSegmentationService.ts`
  - `frontend/src/engine/garmentReconstruction/GarmentIntelligenceService.ts`
- **Acceptance Criteria:**
  - Test set of 50 complex garment photos (including worn garments, patterned rugs, shadows) achieves $\ge 96\%$ IoU (Intersection-over-Union) segmentation accuracy with $0\%$ background bleed.
- **Licensing Considerations:** Apache 2.0 (SAM 2, BiRefNet) and MIT (Fashion-CLIP); 100% commercially compliant.

### Phase 3: Category-Specific Procedural Tailoring Engine
- **Timeline:** Weeks 5–6
- **Objective:** Replace primitive cylindrical tubes with pattern-based procedural construction across all 9 target categories.
- **Exact Deliverables:**
  1. **Shirts:** Procedural collar band, collar leaf, front button placket, button geometry, barrel cuffs, curved hem.
  2. **Jackets:** Notch/peak lapels, front zipper/buttons, welt pockets, shoulder pads, structured waistband.
  3. **Jeans & Trousers:** 5-pocket denim patterns, fly zipper, belt loops, tailored pleats, ankle breaks.
  4. **Dresses:** A-line, sheath, and wrap dress geometry with lower skirt panels extending down to knee/ankle.
  5. **Footwear:** Dedicated procedural shoe engine for sneakers and boots anchored to foot bones (`LeftFoot`, `RightFoot`).
  6. **Traditional Attire:** Draped kurta and tunic pattern lofts.
- **Files Involved:**
  - `frontend/src/engine/garmentReconstruction/GarmentGeometryProcessor.ts`
  - `backend/app/services/garments/garment_mesh_builder.py`
  - `frontend/src/engine/garmentReconstruction/garmentReconstructionTypes.ts`
- **Acceptance Criteria:**
  - Generated shirts, jackets, pants, and dresses exhibit authentic tailored components with zero tubular cylinder appearance.
  - Footwear successfully equips onto avatar without leaving the model barefoot.

### Phase 4: PBR Texture Synthesis, Delighting & Seam Mapping
- **Timeline:** Weeks 7–8
- **Objective:** Synthesize photorealistic PBR material maps with delighting and authentic multi-view photographic unwrapping.
- **Exact Deliverables:**
  1. Implement high-pass frequency decomposition delighting to strip baked ambient shadows and specular glare.
  2. Map photographic crops of sleeves, collars, and pockets directly to their respective UV islands instead of drawing synthetic canvas strokes.
  3. Synthesize micro-normal maps and PBR roughness maps calibrated to the detected fabric type (cotton, denim, leather, wool, silk, fleece).
- **Files Involved:**
  - `frontend/src/engine/garmentReconstruction/GarmentTextureProcessor.ts`
  - `backend/app/services/garments/garment_texture_synthesizer.py`
- **Acceptance Criteria:**
  - Full-body renders show seamless texture continuity between front torso, sleeves, and collar.
  - Zero flat single-color procedural fillers on visible outer panels.

### Phase 5: Production Avatar Fitting & XPBD Cloth Dynamics
- **Timeline:** Weeks 9–10
- **Objective:** Upgrade avatar fitting and cloth physics for compliant, dynamic fabric simulation during animation.
- **Exact Deliverables:**
  1. Upgrade position-based dynamics in `frontend/src/engine/clothPhysics/` to Extended Position-Based Dynamics (XPBD) with compliance parameters ($1/\text{stiffness}$).
  2. Implement sub-stepped constraint solving ($4$ sub-steps per frame) to prevent jitter and stretching.
  3. Implement multi-layer clothing collision resolution in `GarmentLayerManager.ts` (e.g. T-shirt layer 0, hoodie layer 1, overcoat layer 2).
- **Files Involved:**
  - `frontend/src/engine/clothPhysics/ClothConstraintSolver.ts`
  - `frontend/src/engine/clothPhysics/ClothSimulationController.ts`
  - `frontend/src/engine/garments/GarmentLayerManager.ts`
  - `frontend/src/engine/garments/GarmentAvatarFittingEngine.ts`
- **Acceptance Criteria:**
  - Garments drape with realistic gravitational settling and wrinkle formation during avatar breathing and turning animations.
  - Zero body penetration or poke-through across dynamic animation sequences.

### Phase 6: Cloud Neural 3D Reconstruction Worker Pool
- **Timeline:** Weeks 11–12
- **Objective:** Deploy an asynchronous cloud GPU worker pool capable of running true multi-view generative 3D neural reconstruction for premium users.
- **Exact Deliverables:**
  1. Build Dockerized worker running an open-weight, commercially licensed multi-view reconstruction pipeline (e.g. **LGM / Large Gaussian Model** or **InstantMesh** with commercial clearance).
  2. Implement queue consumer listening to Redis/Celery or AWS SQS.
  3. Wire `BackendWorkerReconstructionAdapter.ts` to seamlessly route requests to cloud GPU workers when online, falling back to local procedural engines on edge devices.
- **Files Involved:**
  - `backend/app/services/garments/job_manager.py`
  - `frontend/src/engine/garmentReconstruction/GarmentReconstructionAdapter.ts`
- **Acceptance Criteria:**
  - End-to-end multi-view photo upload produces high-density neural mesh ($> 20,000$ vertices) with photorealistic geometry in $< 25\text{s}$ on GPU worker.

---

## 10. Components to Reuse vs. Components to Replace

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       REUSE VS. REPLACE AUDIT MATRIX                        │
├─────────────────────────────────────┬──────────────┬────────────────────────┤
│ Subsystem / Component               │ Action       │ Technical Justification│
├─────────────────────────────────────┼──────────────┼────────────────────────┤
│ PhotoTo3DGarmentModal.tsx           │ REUSE        │ Clean React UI, robust │
│                                     │              │ file & preview handling│
│ GarmentAvatarFittingEngine.ts       │ REUSE        │ Excellent bind-matrix  │
│                                     │              │ landmark extraction    │
│ GarmentCollisionResolver.ts         │ REUSE        │ Robust three-mesh-bvh  │
│                                     │              │ clearance projection   │
│ GarmentSkinningAdapter.ts           │ REUSE        │ Proven semantic bone   │
│                                     │              │ isolation eliminates   │
│                                     │              │ underarm wing defects  │
│ universal_garment_taxonomy.json     │ REUSE        │ Comprehensive 450-line │
│                                     │              │ category specification │
│ CloudinaryStorage / SupabaseRepo    │ REUSE        │ Reliable asset CDN and │
│                                     │              │ database architecture  │
│─────────────────────────────────────┼──────────────┼────────────────────────┤
│ GarmentSegmentationService (Canvas) │ REPLACE      │ Fails on non-uniform   │
│                                     │              │ backgrounds; replace   │
│                                     │              │ with SAM 2 / BiRefNet  │
│ fashion_vision.py (MD5 mock)        │ REPLACE      │ Replace with Fashion-  │
│                                     │              │ CLIP vision embeddings │
│ fashion_classifier.py (MNIST)       │ REPLACE      │ 28x28 grayscale toy    │
│                                     │              │ model; replace with    │
│                                     │              │ Fashionpedia detector  │
│ GarmentGeometryProcessor (Cylinders)│ REPLACE      │ Replace with 2D sewing │
│                                     │              │ pattern CAD lofts      │
│ GarmentTextureProcessor (Decal crop)│ REPLACE      │ Replace with conformal │
│                                     │              │ UV unwrapping & delight│
│ PBD Cloth Solver (Rigid springs)    │ UPGRADE      │ Upgrade to sub-stepped │
│                                     │              │ XPBD compliance solver │
└─────────────────────────────────────┴──────────────┴────────────────────────┘
```

---

## 11. Resource & Infrastructure Requirements

### 11.1 Local Development Environment (Apple Silicon / Standard PC)
- **Minimum Specifications:** Apple M1/M2/M3 with $8\text{GB}-16\text{GB}$ unified memory, or x86_64 CPU with $16\text{GB}$ RAM.
- **Capabilities:** Runs Vite React frontend, Three.js WebGL canvas, FastAPI backend service, local procedural tailoring engine, and client-side XPBD physics at 60 FPS.
- **Constraints:** Neural training and heavy CUDA diffusion models (`Garment3DGen`, `nvdiffrast`) cannot run on this tier.

### 11.2 Production Cloud GPU Infrastructure (Phase 6 Neural Tier)
- **GPU Instance:** AWS `g5.xlarge` (1x Nvidia A10G, $24\text{GB}$ VRAM) or RunPod / Lambda Labs equivalent (1x RTX 4090 / A5000, $24\text{GB}$ VRAM).
- **Storage:** $100\text{GB}$ NVMe disk for model weight caching (SAM 2, BiRefNet, Fashion-CLIP, neural mesh generators).
- **Throughput:** $1$ instance handles $\approx 120-180$ reconstructions per hour.
- **Estimated Cost:** $\approx \$0.50 - \$1.00$ per hour spot / on-demand instance pricing ($\approx \$0.005$ compute cost per generated garment).

---

## 12. Verification & Master Sign-Off

### 12.1 Automated Test Baseline
- **Frontend Test Suite:** 22 test files, 314 tests passed in $3.09\text{s}$ (`npm --prefix frontend test`).
- **Backend Test Suite:** 10 fashion ML tests and 15 phase-2 intelligence tests passed in $3.77\text{s}$ and $15.37\text{s}$ (`backend/venv/bin/pytest`).
- **Production Build:** `npm --prefix frontend run build` completes in $5.39\text{s}$ with zero TypeScript errors.

### 12.2 Concluding Summary
The Yorvyn Garment AI Recovery Audit establishes complete operational truth. By dismantling the illusion of non-existent neural models, pinpointing the silent REST API routing bug, documenting the limitations of 2D perimeter thresholding and parametric cylinders, and laying out an achievable six-phase roadmap based on commercially unencumbered models (SAM 2, BiRefNet, Fashion-CLIP, procedural pattern lofts, and XPBD physics), this report provides the definitive master plan for delivering truly wearable, high-fidelity 3D clothing across the Yorvyn virtual try-on platform.

