# Yorvyn Technology Library — Architecture Map

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 YORVYN PLATFORM UI                                     │
│     AvatarStudio.tsx  │  AraAvatarViewer.tsx  │  PhotoTo3DGarmentModal.tsx  │  AppNav  │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        YORVYN PRIVATE TECHNOLOGY PACKAGES                              │
│                                                                                        │
│  [packages/avatar-core]            [packages/avatar-generation]    [packages/avatar-rig] │
│  Anthropometry & Coordinates       Procedural Morphing Engine       65-Bone Joint Rig   │
│                                                                                        │
│  [packages/avatar-animation]       [packages/garment-core]         [packages/fitting]   │
│  Clips (Idle, Wave, Cheer, Turn)   Manifold Topology & Loops        Dynamic Occlusion  │
│                                                                                        │
│  [packages/garment-reconstruction] [packages/materials-textures]   [packages/pipeline] │
│  Silhouette & Neckline Extraction  PBR UV Atlas & Normal Synthesis  Binary GLB / Preview│
│                                                                                        │
│  [packages/three-renderer]         [packages/ai-adapters]          [packages/types]    │
│  Studio Lighting & ACES Tone       Decoupled Worker Target          Unified Schema      │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     ▼                                             ▼
┌──────────────────────────────────────────┐  ┌──────────────────────────────────────────┐
│         PRODUCTION CORE ENGINES          │  │       RESEARCH & EXPERIMENTAL LABS       │
│                                          │  │                                          │
│  • Ara 3D Gen Runtime                    │  │  research/upstream/                      │
│    (frontend/src/engine/ara/)            │  │  ├── 3d-gen/ (Upstream Ara commit)       │
│  • Parametric Garment Pipeline           │  │  ├── Clothware/ (Pattern benchmark)      │
│    (backend/app/fashion/garment_3d/)     │  │  ├── Garment3DGen/ (Neural diffusion)    │
│  • Digital Wardrobe Storage              │  │  └── ReMu/ (Multi-layer peeling)         │
│    (backend/data/wardrobe_items.json)    │  │                                          │
│  • Temporary Zero-Retention Purge        │  │  research/experiments/                   │
│    (backend/data/temp_processing/)       │  │  └── isolates & weight evaluation        │
└──────────────────────────────────────────┘  └──────────────────────────────────────────┘
```

---

## Package Responsibilities & Lineage

### 1. `packages/avatar-core`
- **Purpose**: Defines standardized avatar anthropometry parameters (`height`, `weight`, `muscle`, `gender`, `age`) and metric coordinates (Y-up, Z-front).
- **Lineage**: Adapted from MakeHuman / Ara 3D Gen.

### 2. `packages/avatar-generation`
- **Purpose**: Exposes `IAvatarGeneratorProvider` for synthesizing 3D character geometries from anthropometry inputs.
- **Lineage**: Wrapped around [frontend/src/engine/ara/core/human.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/ara/core/human.ts).

### 3. `packages/avatar-rigging`
- **Purpose**: Computes 65-bone joint hierarchies, landmark bindings, and bone skinning weights (`IAvatarRiggingService`).
- **Lineage**: Standard MakeHuman skeleton mapped to glTF vertex skinning.

### 4. `packages/avatar-animation`
- **Purpose**: Manages animation clips, smooth crossfading, and one-shot playback (`Idle`, `Wave`, `Cheer`, `Turn`).
- **Lineage**: Implemented in [frontend/src/engine/ara/AraAnimationController.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/ara/AraAnimationController.ts).

### 5. `packages/garment-core`
- **Purpose**: Establishes 2-manifold garment geometry contracts with anatomic opening loops (neck, cuffs, waist, hem) and category schemas.
- **Lineage**: Independently authored clean-room manifold representation.

### 6. `packages/garment-reconstruction`
- **Purpose**: Exposes `IGarmentReconstructionEngine` for monocular foreground segmentation, neckline/sleeve classification, and mesh synthesis.
- **Lineage**: Implemented in [backend/app/fashion/garment_3d/garment_analyzer.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/fashion/garment_3d/garment_analyzer.py).

### 7. `packages/garment-fitting`
- **Purpose**: Body-relative scaling, dynamic bone tracking, and body occlusion masking to prevent clipping.
- **Lineage**: Implemented in [frontend/src/components/AraAvatarViewer.tsx](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/components/AraAvatarViewer.tsx).

### 8. `packages/materials-textures`
- **Purpose**: Synthesizes UV texture atlases, de-lights input photographs, and calculates normal and roughness maps.
- **Lineage**: Implemented in [backend/app/fashion/garment_3d/garment_texture_synthesizer.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/fashion/garment_3d/garment_texture_synthesizer.py).

### 9. `packages/three-renderer`
- **Purpose**: Configures WebGL rendering, ACESFilmic tone mapping, soft PCF shadows, and cloud ambiance studio lighting.
- **Lineage**: Production Three.js viewport controller.

### 10. `packages/asset-pipeline`
- **Purpose**: Glb 2.0 binary generation, software depth-buffered thumbnail preview generation, and privacy-preserving storage persistence.
- **Lineage**: Implemented in [backend/app/fashion/garment_3d/glb_exporter.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/fashion/garment_3d/glb_exporter.py) and [preview_renderer.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/fashion/garment_3d/preview_renderer.py).

### 11. `packages/ai-adapters`
- **Purpose**: Abstract worker interface separating local CPU processing from high-end GPU cluster workers (e.g. Wonder3D / Garment3DGen).
- **Lineage**: Architectural decoupling layer preventing non-commercial lock-in.

### 12. `packages/shared-types`
- **Purpose**: Unified TypeScript/Python contracts shared across the entire stack.
