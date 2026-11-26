# Real-Time Garment Design State Architecture

Source: [DesignStateEngine.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/engine/designStudio/DesignStateEngine.ts) and [design_revisions.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/design_revisions.py).

## 1. Tracked Versioned State

`GarmentDesignState` tracks:
- Identities: `garmentId`, `candidateId`, `category`, `subcategory`
- Independent monotonic versions: `designVersion`, `geometryVersion`, `patternVersion`, `materialVersion`, `textureVersion`
- Geometry parameters (`GeometryDeformationParams`): bounded `torsoLengthScale`, `torsoWidthScale`, `sleeveLengthScale`, `sleeveWidthScale`, `collarWidthScale`, `hemWidthScale`
- Authoritative pattern pieces & seams: `patternPieces`, `patternSeams`, `selectedPieceId`, `patternLayers`, `patternValidationErrors`
- Material & UV state (`DesignMaterialState`): `preset`, `baseColor`, `roughness`, `metalness`, `sheen`, `clearcoat`, `normalIntensity`, `repeatX/Y`, `rotationDeg`, `offsetX/Y`, `stitchVisible`, `stitchColor`, `printScale`, `isPhysicallyVerified: false`
- Simulation & viewport state: `simulationMode`, `cameraPreset`, `viewModes` (`wireframe`, `showNormals`, `showUVs`, `showPanels`, `showSeams`, `showMeasurements`, `lightingPreset`, `exposure`), `selectedComponent`, `hoveredComponent`

## 2. Compact Undo/Redo & Conflict Protection

- Undo/redo stacks (`DesignHistoryDelta[]`) store lightweight scalar parameter snapshots, material configs, measurements, and 2D pattern piece JSON — **never duplicating WebGL `Float32Array` mesh buffers** (`RealtimeMeshEditor` keeps a single immutable `WeakMap<THREE.Mesh, RestMeshBuffers>`).
- Optimistic concurrency (`expectedVersion` in `applyGeometryEdit` and `expected_parent_version` in `POST /api/garments/{garment_id}/revisions`) fails closed (`sync_conflict` / HTTP `409 Conflict`) to prevent silent overwrites of newer revisions.
- Persistence strictly scopes revisions by `user_id` (PostgreSQL `garment_design_revisions` when configured + owner-isolated fallback store returning HTTP `404` across users).
