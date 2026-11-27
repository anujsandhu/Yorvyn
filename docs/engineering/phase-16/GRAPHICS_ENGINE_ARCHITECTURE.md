# Phase 16.3 Graphics Engine Architecture & Technology Evaluation

## 1. Repository Graphics Audit

Existing stack prior to Phase 16.3:
- `three` `^0.186.1` + `three-mesh-bvh` `^0.9.17` powering `AvatarStudioViewer.tsx`, `PhotoTo3DGarmentModal.tsx`, `GarmentJobMessage.tsx`, `GarmentAvatarFittingEngine.ts`, and `ClothSimulationController.ts`.
- `three` `0.186.1` already bundles `three.webgpu.js` and `three.tsl.js` inside `node_modules/three/build/`.

## 2. Technology Evaluation Matrix

| Technology | Evaluation Decision | Rationale & Evidence |
| --- | --- | --- |
| **Three.js (`0.186.1`)** | **Primary 3D Engine (Adopted & Upgraded)** | In-place `BufferGeometry` attribute mutation, PBR `MeshStandardMaterial` updates, procedural `CanvasTexture` weave/stitching/UV-grid maps, `Raycaster` component picking, `Box3Helper`, `EdgesGeometry`, `GLTFExporter`, and full WebGL context-loss handling cleanly integrate without duplicating engines. |
| **WebGPU (`three/webgpu` + `navigator.gpu`)** | **Probed / Gated Fallback to WebGL2** | [GraphicsCapabilityService.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/designStudio/GraphicsCapabilityService.ts) probes `webgl2` and `navigator.gpu.requestAdapter()`. Headless Chromium detected an adapter while production rendering remains on WebGL2 (`webgl2 (high)`) to preserve full material/shader and GLB parity across all client drivers until dedicated TSL parity testing passes. |
| **PixiJS vs Canvas2D CAD** | **Independent Geometry + Canvas2D Adopted** | Authoritative 2D pattern data lives independently in `DesignStateEngine` / Phase 16.2 Python models. Rendering the 2D pattern editor via high-DPI Canvas2D avoids adding ~450KB bundle weight AND preserves scarce browser WebGL context slots alongside `AvatarStudioViewer`, `GarmentJobMessage`, and `InteractiveGarment3DEditor`. |
| **Rapier** | **Deferred (Not Substituted for Cloth XPBD)** | Rigid-body physics is unsuitable for fabric drape and fold mechanics. Existing XPBD `ClothSimulationController` (`ClothConstraintSolver` + `ClothCollisionSystem`) already handles distance/bend constraints and avatar capsule collisions. |
| **OpenCascade.js** | **Deferred (Not Added to Production Bundle)** | Multi-MB WASM footprint is unjustified while deterministic 2D CCW/Bézier polygon validation, seam offsets, SVG XML, and ASCII DXF R12 generation run natively in milliseconds on CPU/TypeScript & Python. |
