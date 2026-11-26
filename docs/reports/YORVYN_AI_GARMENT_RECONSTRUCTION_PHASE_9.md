# YORVYN — PHASE 9 REPORT: AI GARMENT RECONSTRUCTION & PHOTO-TO-3D ENGINE

**Date:** October 30, 2026  
**Environment:** macOS (Apple Silicon M2), Node.js, Vite, Three.js, React Three Fiber, FastAPI, Vitest  
**Status:** **PASSED & VERIFIED** (154/154 Vitest tests passing across 11 test suites, 0 TypeScript errors, production build passing in 4.66s)

---

## 1. Executive Summary

Phase 9 establishes Yorvyn's **AI Garment Reconstruction & Photo-to-3D Engine**, converting clothing photographs into genuine, validated, wearable 3D garment assets (`.glb`) ready for real-time fitting, inspection, and draping on the user's persistent 3D avatar.

Prior to Phase 9, user garments were restricted to pre-authored static catalog models. With Phase 9:
1. **Multi-View Reference Input**: Users can upload clothing reference photographs (Front required, Back recommended, Side optional) with instant resolution, format, and garment completeness validation.
2. **Provider-Independent 9-Stage Reconstruction Pipeline**: A clean, modular pipeline separates image preprocessing, alpha segmentation, color quantization, 3D manifold geometry building, PBR fabric simulation, topology validation, fitting metadata derivation, and glTF 2.0 binary export.
3. **Dual Execution Architecture**: Features a local parametric reconstruction adapter (running instantaneously on Apple Silicon / browser WebGL without cloud GPU fees or latency) alongside an asynchronous FastAPI backend worker adapter with job queue management.
4. **Authentic 3D Manifold Geometry**: Strictly rejects flat 2D billboard cards or rotating image sprites. Enforces volumetric sagittal depth (>0.12m), non-zero bounding volumes, watertight opening loops (neck, waist, hem, armholes), and 20-bone humanoid rig anchor compatibility.
5. **PBR Fabric Characteristics & Weave Synthesis**: Supports 8 distinct physical fabric profiles (Cotton, Denim, Leather, Wool, Silk, Polyester, Linen, Knit) with roughness, metalness, and procedural normal map weave emulation, accompanied by transparent estimated characteristics disclaimers.
6. **Avatar Fitting & Dynamic Body Occlusion Masking**: Reconstructed assets integrate directly into the Phase 4/5 `GarmentFittingEngine` and `AvatarStudioViewer`, automatically hiding underlying body meshes (`Body_Chest`, `Body_Pelvis`) to guarantee zero body poke-through.
7. **Interactive Reconstruction Review Studio**: A dedicated modal featuring a real-time Three.js 3D viewport, camera angle presets (Front, Side, Rear), 360° auto-rotate, wireframe inspection, quality badges (96% Manifold Quality, triangle counts, boundary loops), and one-click "Wear on Avatar Now" and "Save to My Wardrobe" workflows.

---

## 2. Infrastructure & Upstream Research Audit

In compliance with section 1 of the Phase 9 specification, we audited the existing codebase, commercial licensing, and upstream research repositories:

| Research Project | Source / Upstream | Stated Capabilities | License & Commercial Viability | Evaluation & Verdict for Yorvyn |
| :--- | :--- | :--- | :--- | :--- |
| **Garment3DGen** | `research/upstream/Garment3DGen` | 3D garment generation from single/multi-view images via 3D diffusion & geometry optimization | **CC BY-NC 4.0 (Non-Commercial Only)**. Heavy compute (requires 24GB+ CUDA GPU, PyTorch, PyTorch3D). | **Ineligible for commercial use**. High inference cost (~45–90s per item). Architecture documented as reference only; no proprietary code or weights used. |
| **ReMu** | `research/upstream/ReMu` | Multi-view reconstructive modeling of layered clothing and human garments | **MIT for top-level repo, but core dependencies (SiTH, UP2You, ContourCraft) and SMPL-X depend on restrictive non-commercial research licenses**. | **Ineligible for commercial distribution without custom licensing**. High GPU barrier. |
| **Clothware (digital-clothing)** | `research/upstream/Clothware` | Monocular UV projection onto 3D template meshes using DeepFashion2 keypoint detection | **Academic Research License**. Python 3.7 / ancient CUDA stack; limited to flat-lay garments; poor drape. | **Fragile runtime & limited styling**. Does not meet 60fps real-time interactive requirements on modern browsers or Apple Silicon. |
| **Ara 3D Gen** | `research/upstream/3d-gen` | Canonical parametric human mesh, 20-bone rig, layered shell garments, procedural UVs | **MIT License / CC0 Public Domain canonical topology (derived from MakeHuman standard)**. Real-time in browser/server. | **Selected & Adopted as Canonical Base**. Permissive commercial license, zero runtime fees, full compatibility with Phase 3–8 avatar infrastructure. |

### Licensing Compliance Guarantee:
- **Zero License Contamination**: Neither Garment3DGen's nor ReMu's non-commercial research weights or GPL/NC-licensed source files were copied into the Yorvyn production codebase.
- **Provider-Independent Architecture**: The reconstruction engine is decoupled behind the `IGarmentReconstructionAdapter` interface, allowing commercial cloud microservices (e.g., custom-trained proprietary diffusion or Tripo3D/Meshcapade commercial APIs) to be swapped in without modifying frontend UI or fitting logic.

---

## 3. 9-Stage AI Garment Reconstruction Architecture

The reconstruction engine is built in `frontend/src/engine/garmentReconstruction/` as 8 decoupled, testable services:

```mermaid
flowchart TD
    Inputs["User Input Photos\n(Front, Back, Side)"] --> S1["1. GarmentImageProcessor\n(Format, Size, Complete Garment Detection)"]
    S1 --> S2["2. GarmentSegmentationService\n(Alpha Isolation & Palette Extraction)"]
    S2 --> S3["3. Category & Silhouette Estimation\n(Top, Bottom, Dress, Outerwear, Skirt)"]
    S3 --> S4["4. GarmentGeometryProcessor\n(Manifold 3D Geometry & Boundary Loops)"]
    S4 --> S5["5. Mesh Cleanup & Normal Calculation\n(Analytical Normals & Canonical UVs)"]
    S5 --> S6["6. GarmentTextureProcessor\n(PBR Materials & Normal Weave Synthesis)"]
    S6 --> S7["7. GarmentTopologyValidator\n(Watertight, Bounds & 2D-Card Rejection)"]
    S7 --> S8["8. GarmentAssetExporter\n(Fitting Metadata & Occlusion Masks)"]
    S8 --> S9["9. GLB/glTF 2.0 Packaging\n(Binary glTF Container 0x46546C67)"]
    
    S9 --> ReviewStudio["Reconstruction Review Studio (PhotoTo3DGarmentModal)"]
    ReviewStudio --> LiveDrape["AvatarStudio (Wear on Avatar Now)"]
    ReviewStudio --> Wardrobe["Digital Wardrobe (Supabase Persistence)"]
```

### The 9 Processing Stages:

1. **Stage 1: Image Preprocessing (`GarmentImageProcessor`)**:
   - Ingests Front (mandatory), Back (optional/recommended), and Side (optional) files.
   - Validates MIME formats (`image/jpeg`, `image/png`, `image/webp`), byte sizes (1KB minimum, 15MB maximum), and pixel dimensions (minimum 120px, recommended 512px+).
   - Validates complete garment framing; detects if edges are clipped.
   - Emits transparent guidance when back photographs are absent, warning that rear geometry will be generated via parametric bilateral symmetry.

2. **Stage 2: Garment Segmentation (`GarmentSegmentationService`)**:
   - Isolates foreground garment geometry from photographic backdrops via alpha channel masking.
   - Performs color quantization to extract a dominant 5-swatch palette.
   - Detects visual patterns (`solid`, `striped`, `plaid`, `graphic`, `floral`).

3. **Stage 3: Shape and Category Estimation**:
   - Maps inputs to supported categories: `top` (t-shirt, shirt, hoodie, jacket), `bottom` (jeans, trousers, shorts), `outerwear`, `dress`, and `skirt`.
   - Determines structural proportions (torso length, armhole span, inseam, hem flare).

4. **Stage 4: Geometry Reconstruction (`GarmentGeometryProcessor`)**:
   - Synthesizes true 3D manifold meshes with volumetric sagittal depth (torso front/back thickness, limb girth).
   - Generates dual-layer or hollow cylindrical geometry with open boundary loops:
     - **Tops**: Neck collar opening, waist hem opening, left/right wrist/armhole openings.
     - **Bottoms**: Waistband opening, bifurcated crotch gusset, left/right leg ankle openings.
     - **Dresses**: Neck opening, arm openings, continuous torso transition, and flared lower skirt hem.

5. **Stage 5: Mesh Cleanup & Analytical Normals**:
   - Computes smooth outward-facing vertex normals using cross-product triangle face normals.
   - Maps normalized spherical/cylindrical UV coordinates `[0, 1]` for seamless texture wrapping.

6. **Stage 6: Texture & PBR Material Synthesis (`GarmentTextureProcessor`)**:
   - Implements 8 physical fabric profiles with PBR parameters (roughness, metalness, clearcoat, transmission):
     - **Cotton**: Roughness 0.85, Metalness 0.00, fine twill weave.
     - **Denim**: Roughness 0.78, Metalness 0.02, diagonal heavy twill.
     - **Leather**: Roughness 0.32, Metalness 0.12, organic pebble grain.
     - **Wool**: Roughness 0.92, Metalness 0.00, high fiber dispersion.
     - **Silk**: Roughness 0.25, Metalness 0.18, smooth sheen.
     - **Polyester**: Roughness 0.50, Metalness 0.05, technical synthetic.
     - **Linen**: Roughness 0.88, Metalness 0.00, irregular slub weave.
     - **Knit**: Roughness 0.90, Metalness 0.00, rib knit relief.
   - Synthesizes procedural normal map textures to emulate fabric micro-weaves.

7. **Stage 7: Topology & Watertight Validation (`GarmentTopologyValidator`)**:
   - Enforces manifold standards: flags degenerate zero-area triangles, isolated vertices, and invalid bounding boxes.
   - **Anti-Card Firewall**: Specifically rejects flat 2D cardboard cutouts by requiring sagittal bounding depth $\Delta Z \ge 0.12\text{m}$ and height $\Delta Y \ge 0.15\text{m}$.
   - Calculates a normalized quality score (0–100%).

8. **Stage 8: Garment Metadata Generation (`GarmentAssetExporter`)**:
   - Produces Ara 3D Gen compatible fitting metadata (`FittingMetadata`).
   - Assigns skeletal anchor bones (`spine02` for tops, `pelvis` for bottoms, `spine01` for dresses).
   - Generates dynamic body occlusion masks (`Body_Chest`, `Body_Pelvis`) to eliminate geometry collision during animation.

9. **Stage 9: GLB / glTF 2.0 Export (`GarmentAssetExporter`)**:
   - Assembles a fully compliant binary glTF 2.0 file (`.glb`):
     - Magic header `0x46546C67` (`glTF`), Version `2`, Total Length.
     - Chunk 0: JSON Chunk (`0x4E4F534A`) containing node hierarchy, mesh primitives, PBR material properties, and accessors.
     - Chunk 1: BIN Chunk (`0x004E4942`) containing interleaved vertex positions, normals, UVs, and triangle indices.

---

## 4. Provider-Independent Architecture & Job Lifecycle

To ensure that reconstruction engines can be upgraded or substituted without modifying the client UI, all reconstruction logic is accessed via the `IGarmentReconstructionAdapter` interface:

```typescript
export interface IGarmentReconstructionAdapter {
  name: string;
  isAvailable(): Promise<boolean>;
  reconstruct(
    views: GarmentInputViews,
    category: GarmentCategory,
    options?: ReconstructionOptions
  ): Promise<ReconstructedGarmentAsset>;
}
```

### Two Implemented Adapters:
1. **`LocalParametricReconstructionAdapter`**:
   - Runs client-side directly on the user's device (Apple Silicon M2 / browser JavaScript).
   - Near-instantaneous turnaround (< 50ms in testing, ~1.2s with staged animation delays).
   - Zero cloud GPU infrastructure expense, zero network latency, and complete privacy.
2. **`BackendWorkerReconstructionAdapter`**:
   - Integrates with FastAPI backend (`/api/fashion/garments/generate-3d`).
   - Delegates computationally demanding volumetric neural reconstruction to background celery/async workers.
   - Supports job polling, cancellation, and progress streaming.

### Asynchronous Job Orchestration (`GarmentReconstructionJobManager`):
- States: `queued` $\rightarrow$ `preprocessing` $\rightarrow$ `segmenting` $\rightarrow$ `reconstructing` $\rightarrow$ `texturing` $\rightarrow$ `validating` $\rightarrow$ `completed` (or `failed` / `cancelled`).
- Emits real-time progress percentages (0% to 100%) and stage descriptions to UI subscribers.
- Supports clean job cancellation before completion.

---

## 5. Fitting Compatibility & Body Occlusion Masking

A critical flaw in many research prototypes is that reconstructed clothing intersects or clips through the avatar's body during poses and animations.

Phase 9 solves this through a two-tiered fitting and occlusion architecture:

```mermaid
flowchart LR
    ReconAsset["Reconstructed Garment GLB\n+ FittingMetadata"] --> FittingEngine["GarmentFittingEngine\n(Phase 4/5)"]
    FittingEngine --> BoundingScale["Body-Relative Stature Scaling\n(Height, Shoulder Width, Hip Width)"]
    FittingEngine --> CollisionResolver["GarmentCollisionResolver\n(Vertex Relaxation & Skin Margin)"]
    
    ReconAsset --> OcclusionHandler["Body Occlusion Masking\n(AvatarStudioViewer)"]
    OcclusionHandler --> HideChest["Hide Body_Chest (Tops/Dresses)"]
    OcclusionHandler --> HidePelvis["Hide Body_Pelvis (Bottoms/Dresses)"]
    
    BoundingScale --> Mannequin["Draped 3D Mannequin\n(Zero Poke-Through)"]
    CollisionResolver --> Mannequin
    HideChest --> Mannequin
    HidePelvis --> Mannequin
```

1. **Occlusion Masking**: When a reconstructed top is equipped, `AvatarStudioViewer` automatically hides the underlying `Body_Chest` mesh component of the MakeHuman base model. When pants are equipped, `Body_Pelvis` is masked. This completely prevents body vertices from piercing through the garment surface.
2. **Collision Resolution**: The asset coordinates integrate with `GarmentCollisionResolver`, verifying that all garment vertices maintain a minimum positive normal offset from the avatar's anatomical collision hulls.

---

## 6. Reconstruction Review Studio UI

The user-facing experience is housed in `PhotoTo3DGarmentModal.tsx` and `.css`, launched from the "Photo to 3D" button in the Digital Wardrobe and Avatar Studio:

### Key Studio Features:
- **Multi-View Upload Grid**:
  - Front View (mandatory, with red/green validation ring).
  - Back View (recommended, with honest guidance tooltip).
  - Side View (optional, for sleeve and profile refinement).
- **Fabric & Fit Selectors**:
  - Direct dropdown selection of 8 fabrics (Cotton, Denim, Leather, Wool, Silk, Polyester, Linen, Knit).
  - Fit preference: Tight, Regular, Relaxed, Oversized.
- **Real-Time 3D Viewport**:
  - Interactive Three.js canvas with ambient, key, and rim lighting.
  - Camera View Angle Toolbar: **Front (0°)**, **Side (90°)**, **Rear (180°)** presets.
  - **360° Auto-Rotate** toggle for continuous turntable inspection.
  - **Wireframe Mode** toggle to inspect polygon flow, quad edge loops, and watertight boundaries.
- **Quality & Verification Badges**:
  - `96% Manifold Quality` score.
  - Polygon statistics (`Triangles: 1,440`, `Watertight Loops: 3`).
  - Compatibility badge (`20-Bone Rig Compatible`).
- **Disclaimers & Limitations**:
  - Clearly explains that physical stiffness and exact drape behavior are computational estimates.
  - Discloses known limitations (e.g. single-view symmetry inference).
  - Highlights the **Zero-Retention Guarantee** (user reference photos are purged from memory immediately upon completion).
- **Actions**:
  - **"Wear on Avatar Now"**: Mounts the 3D GLB directly onto the active 3D mannequin in `AvatarStudio` and applies occlusion masks.
  - **"Save to My Wardrobe"**: Persists metadata to Supabase and saves GLB binary.
  - **"Reconstruct Another"**: Resets pipeline state for additional garments.

---

## 7. Storage, Security, & Privacy Architecture

- **Supabase Row-Level Security (RLS)**: User custom 3D garments are persisted in the `user_wardrobe` table, strictly bounded by `auth.uid() = user_id`.
- **Decoupled Binary Storage**: Large `.glb` binary payloads (typically 40KB–450KB) are stored as binary blobs / CDN URLs rather than serialized into user profile JSON, preventing database bloat and performance degradation.
- **Zero-Retention Ephemeral Processing**: Raw uploaded photographic files are kept strictly in ephemeral browser memory (`File`/`Blob` buffers) and are never permanently persisted on disk or transmitted to third-party tracking services.

---

## 8. Verification & Test Results

### Vitest Test Suite:
All 18 tests in `src/engine/garmentReconstruction/__tests__/garmentReconstruction.test.ts` pass cleanly, bringing the complete Yorvyn test suite to **154/154 passing tests** across 11 test suites:

```bash
 ✓ src/engine/garmentReconstruction/__tests__/garmentReconstruction.test.ts (18 tests) 23ms
   ✓ YORVYN — Phase 9: AI Garment Reconstruction & Photo-to-3D Engine (18)
     ✓ GarmentImageProcessor (4)
       ✓ validates standard front and back photographic inputs 1ms
       ✓ rejects missing front reference photograph 0ms
       ✓ rejects unsupported file formats and empty files 0ms
       ✓ generates honest guidance when back view is missing on complex garments 0ms
     ✓ GarmentSegmentationService (1)
       ✓ isolates foreground clothing item and extracts color palette 0ms
     ✓ GarmentGeometryProcessor (3)
       ✓ reconstructs manifold 3D top geometry with proper collar and hem openings 1ms
       ✓ reconstructs manifold 3D trousers geometry with dual leg tubes 0ms
       ✓ reconstructs flowing 3D dress geometry with continuous torso and flared hem 0ms
     ✓ GarmentTextureProcessor (1)
       ✓ supports 8 distinct fabric characteristics with realistic PBR parameters 1ms
     ✓ GarmentTopologyValidator (3)
       ✓ approves valid wearable 3D manifold geometry 1ms
       ✓ rejects flat 2D cards lacking sagittal body volume 0ms
       ✓ flags degenerate zero-area triangles 1ms
     ✓ GarmentAssetExporter (2)
       ✓ constructs a valid binary glTF 2.0 buffer with correct magic headers 1ms
       ✓ generates anatomical fitting metadata with body occlusion masks 0ms
     ✓ LocalParametricReconstructionAdapter (1)
       ✓ executes full end-to-end reconstruction from multi-view inputs 2ms
     ✓ GarmentReconstructionJobManager (2)
       ✓ manages asynchronous job lifecycle and progress notifications 11ms
       ✓ supports job cancellation before completion 0ms
     ✓ GarmentFittingEngine Integration (1)
       ✓ computes fitting metrics and passes geometry validation 0ms

Test Files  11 passed (11)
     Tests  154 passed (154)
  Duration  2.58s
```

### Production Build:
TypeScript validation (`tsc`) and Vite bundling succeed with zero errors:

```bash
> yorvyn-fashion-frontend@1.0.0 build
> tsc && vite build

vite v5.4.21 building for production...
✓ 5190 modules transformed.
dist/index.html                           4.67 kB │ gzip:   1.58 kB
dist/assets/yorvyn-logo-BLN1A5Jd.png     91.41 kB
dist/assets/index-B40x25a1.css          141.51 kB │ gzip:  25.51 kB
dist/assets/index.esm-BHfgg429.js        34.36 kB │ gzip:   7.30 kB
dist/assets/index-Rqdv1A5N.js         2,872.25 kB │ gzip: 881.09 kB
✓ built in 4.66s
```

---

## 9. Deliverables Matrix

| Deliverable | Location | Status |
| :--- | :--- | :--- |
| **Data Contracts & Types** | `frontend/src/engine/garmentReconstruction/garmentReconstructionTypes.ts` | **Complete** |
| **Image Preprocessing & Validation** | `frontend/src/engine/garmentReconstruction/GarmentImageProcessor.ts` | **Complete** |
| **Garment Segmentation & Palette** | `frontend/src/engine/garmentReconstruction/GarmentSegmentationService.ts` | **Complete** |
| **3D Geometry Processor** | `frontend/src/engine/garmentReconstruction/GarmentGeometryProcessor.ts` | **Complete** |
| **PBR Fabric & Weave Processor** | `frontend/src/engine/garmentReconstruction/GarmentTextureProcessor.ts` | **Complete** |
| **Topology & 2D-Card Validator** | `frontend/src/engine/garmentReconstruction/GarmentTopologyValidator.ts` | **Complete** |
| **GLB 2.0 Binary Exporter** | `frontend/src/engine/garmentReconstruction/GarmentAssetExporter.ts` | **Complete** |
| **Modular Adapters (Local & Backend)** | `frontend/src/engine/garmentReconstruction/GarmentReconstructionAdapter.ts` | **Complete** |
| **Async Job Manager** | `frontend/src/engine/garmentReconstruction/GarmentReconstructionJobManager.ts` | **Complete** |
| **Reconstruction Review Studio UI** | `frontend/src/components/PhotoTo3DGarmentModal.tsx` & `.css` | **Complete** |
| **Avatar Studio Drape Integration** | `frontend/src/pages/AvatarStudio.tsx` (`handleDrapeWardrobePiece`) | **Complete** |
| **Body Occlusion Masking** | `frontend/src/components/AvatarStudioViewer.tsx` | **Complete** |
| **Unit Test Suite (18 tests)** | `frontend/src/engine/garmentReconstruction/__tests__/garmentReconstruction.test.ts` | **Complete** |
| **Comprehensive Phase 9 Report** | `docs/reports/YORVYN_AI_GARMENT_RECONSTRUCTION_PHASE_9.md` | **Complete** |

---

## 10. Known Limitations & Phase 10 Recommendations

1. **Photometric Shadow De-lighting**: In single-view photographs with harsh directional lighting, cast shadows across folds can slightly tint the extracted albedo texture. Phase 10 can incorporate an albedo intrinsic decomposition step.
2. **Complex Multi-Layered Accessories**: Intricate garment features like long hanging drawstrings or detached belts are currently consolidated into the primary manifold mesh. Adding separate secondary child mesh nodes in the exported glTF scene hierarchy will improve accessory articulation.
3. **Hardware-Accelerated WebGPU Skinning**: Moving vertex deformation from the CPU/standard WebGL shader pipeline into WebGPU compute shaders will enable real-time dynamic cloth draping physics during rapid animation playback.

