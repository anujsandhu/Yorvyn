# YORVYN — PHASE 5 REPORT: BASE AVATAR BODY, TRUE DRESS/UNDRESS SYSTEM & GARMENT REPLACEMENT

**Date:** October 29, 2026  
**Environment:** Apple Silicon M2 (macOS), Node.js, Vite, Three.js, Vitest  
**Status:** **PASSED & VERIFIED** (65/65 Vitest tests passing, 0 TypeScript/build errors)

---

## 1. Executive Summary

Phase 5 re-engineered the avatar body and clothing lifecycle to eliminate destructive geometry mutations. Previously, MakeHuman proxy outfits and procedural garments physically deleted body faces via `compact(fullBody, ...)`. This resulted in missing torsos, hollow groin cavities, and floating limbs when garments were toggled, undressed, or replaced with separate layers.

In Phase 5:
1. **Persistent Complete Base Body:** The base body is established as an anatomically continuous, watertight, 13,380-vertex single mesh covering head, neck, chest, torso, arms, hands, pelvis, legs, and feet. It is never physically excised or amputated.
2. **Centralized Outfit State Machine:** Built `OutfitStateManager` with strongly-typed categories (`baseBody`, `underwear`, `top`, `bottom`, `outfit`, `outerwear`, `shoes`, `accessories`), supporting atomic `dress`, `undress`, `replace`, `undressAll`, `restore`, and `rollback`.
3. **GPU Resource Tracking & Cleanup:** Built `GarmentResourceManager` to automatically dispose of unused geometries, materials, and textures when garments are replaced or removed, preventing memory leaks on Apple Silicon M2.
4. **Reversible Region Masking:** Built `GarmentVisibilityManager` to dynamically synchronize sub-mesh visibility. Removing a top instantly restores the torso; removing trousers restores the legs and modesty briefs.
5. **Rig & Scale Compatibility:** Built `GarmentCompatibilityValidator` to verify Y-up orientations, auto-detect metric vs millimeter assets, and validate skeleton bone bounds.

---

## 2. Root Cause Analysis

| Problem Observed | File & Line | Mechanical Root Cause | Resolution |
| :--- | :--- | :--- | :--- |
| **Missing Torso & Floating Limbs** | `human.ts:275-281` | When `pOutfit` or `gparts` had `hides` or `deleteVerts`, `compact()` physically deleted all covered quad faces from the base body. Hiding the outfit mesh in Three.js or equipping a separate piece left the avatar with no torso skin. | Base body is now always preserved as `fullBody`. Body faces are never permanently deleted from geometry. |
| **Underwear Void & Hollow Perineum** | `catalog.ts:334-339` | `briefs` used default `hide = true`, excising the pelvis. Boundary relaxation on briefs created gap misalignments with the excised body opening. | Explicitly set `hide: false` on `briefs`; relaxed boundary vertices with normal re-projection; ensured $1.8\text{ mm}$ hem clearance. |
| **Garment Duplication & Stacking** | `AvatarStudio.tsx:550-620` | Equipping pieces without centralized resource disposal left previous mesh bindings in Three.js memory, causing visual overlaps and z-fighting. | Created `GarmentResourceManager` which disposes previous geometries and textures whenever a category is replaced or undressed. |
| **Forced Clothing Re-equip on Undress** | `AvatarStudio.tsx:609-614` | The UI artificially forced `uniform_trousers` or `uniform_shirt_long` back onto the avatar when a slot was cleared to hide body amputation holes. | With persistent complete base body, avatar cleanly supports independent undressing (e.g., bare torso with jeans, bare legs with shirt, or full undress to mannequin). |

---

## 3. Base-Body Asset & Rig Findings

1. **Topology & Geometry**:
   - Source: ARA MakeHuman canonical base body topology (`lib.base.arrays`).
   - Topology: Single water-tight manifold mesh consisting of 13,380 vertices with quad polygonal layout.
   - Coverage: Fully covers crown, face, neck, clavicles, chest, abdomen, back, shoulders, elbows, wrists, hands/fingers, glutes, groin, thighs, knees, calves, ankles, and feet/toes.
2. **Skeleton & Rigging**:
   - Humanoid rig using 20 standard bones (`Hips`, `Spine`, `Spine1`, `Spine2`, `Neck`, `Head`, `LeftUpLeg`, `LeftLeg`, `LeftFoot`, `RightUpLeg`, `RightLeg`, `RightFoot`, `LeftShoulder`, `LeftArm`, `LeftForeArm`, `LeftHand`, `RightShoulder`, `RightArm`, `RightForeArm`, `RightHand`).
   - 4-influence linear blend skinning normalized strictly to $\sum w = 1.0$.
3. **Facial Blendshapes & Morphs**:
   - 32 speech and expression targets (blinking, smile, jaw width, cheek definition) bound as morph targets to head vertices.

---

## 4. Architecture Changes & New Modules

The garment engine in `frontend/src/engine/garments/` now provides:

```
frontend/src/engine/garments/
├── BaseBodyController.ts           # Verifies anatomical integrity and modesty base
├── OutfitStateManager.ts           # Centralized dress, undress, atomic swap, and rollback state machine
├── GarmentResourceManager.ts       # Three.js GPU resource disposal and deduplication
├── GarmentVisibilityManager.ts     # Reversible category-aware visibility masking
├── GarmentCompatibilityValidator.ts # Rig alignment, bounds checking, and auto-scale
├── GarmentGeometryValidator.ts     # Filters degenerates, NaNs, and needle spikes
├── GarmentCollisionResolver.ts     # Spatial clearance solver against body normals
├── GarmentSkinningAdapter.ts       # Normalizes bone weights and clamps bone indices
├── GarmentMaterialSystem.ts        # Physically based fabric shading profiles
├── GarmentDiagnostics.ts           # Verification metrics (penetration depth, clearance)
├── GarmentFittingEngine.ts         # Master orchestrator combining all fitting stages
└── index.ts                        # Barrel export
```

### Module Responsibilities:
- **`BaseBodyController`**: Ensures the base body has complete coverage across all 7 anatomical height bands (head, neck, torso, arms, hands, legs, feet) and provides modesty underwear specifications (`offsetMeters: 0.0038`, `hidesSkin: false`).
- **`OutfitStateManager`**: Maintains immutable historical snapshots up to 15 steps; ensures equipping an `outfit` clears `top`, `bottom`, and `outerwear`; equipping a `top` or `bottom` clears `outfit`; supports `undressAll(keepModestyUnderwear = true)` and `rollback()`.
- **`GarmentResourceManager`**: Tracks `THREE.BufferGeometry`, `THREE.Material`, and `THREE.Texture` allocations; safely unlinks meshes from the scene graph and calls `.dispose()` to eliminate memory leaks.
- **`GarmentVisibilityManager`**: Protects skin, hair, and eyes from ever being hidden; synchronizes top, bottom, outfit, and shoe visibility reversibly based on active outfit state.
- **`GarmentCompatibilityValidator`**: Detects centimeter/millimeter scale discrepancies, verifies Y-up coordinate frames, and checks skeletal bone limits.

---

## 5. Automated Test Results

All 6 test suites passed cleanly with **65 passing tests**:

- `src/engine/garments/__tests__/baseBodyAndDressUndress.test.ts` (17 tests) — **PASS**
  - Anatomical completeness verification across head, neck, torso, arms, hands, legs, feet.
  - Modesty underwear specification generation.
  - Initial state with modesty underwear and clean base body.
  - Dressing top and preserving compatible garments.
  - Full outfit clearing separate top and bottom.
  - Undressing single garment without affecting other categories.
  - Clean `undressAll` back to bare modesty base.
  - Atomic garment replacement in the same slot.
  - Rollback to previous valid state upon failure.
  - Restoring persistent outfit states.
  - Resource registration and GPU asset tracking.
  - Disposal of old geometries/materials on replacement.
  - Complete disposal of all resources on teardown.
  - Compatibility validation and Y-up check.
  - Auto-detection and correction of millimeter scale.
  - Protection of avatar skin, eyes, and hair.
  - Dynamic visibility synchronization for equipped tops.
- `src/engine/garments/__tests__/garmentFittingAndDeformation.test.ts` (12 tests) — **PASS**
- `src/engine/ara/__tests__/fittingAndLayerReplacement.test.ts` (5 tests) — **PASS**
- `src/engine/ara/__tests__/avatarProfileAndExpressions.test.ts` (10 tests) — **PASS**
- `src/engine/ara/__tests__/avatarQualityAndReactions.test.ts` (15 tests) — **PASS**
- `src/features/onboarding/__tests__/onboardingBodyStructure.test.ts` (6 tests) — **PASS**

### Build Verification:
- Command: `npm run build --prefix frontend`
- Result: `tsc && vite build` passed in **4.52s with 0 errors**.

---

## 6. Files Changed in Phase 5

1. `frontend/src/engine/ara/core/human.ts`: Preserved `fullBody` as continuous water-tight mesh without destructive `compact()` excision.
2. `frontend/src/engine/garments/BaseBodyController.ts`: Created anatomical completeness validator and modesty base manager.
3. `frontend/src/engine/garments/OutfitStateManager.ts`: Created centralized clothing state machine.
4. `frontend/src/engine/garments/GarmentResourceManager.ts`: Created GPU memory tracker and scene deduplicator.
5. `frontend/src/engine/garments/GarmentVisibilityManager.ts`: Created reversible visibility manager.
6. `frontend/src/engine/garments/GarmentCompatibilityValidator.ts`: Created rig, scale, and bounding-box validator.
7. `frontend/src/engine/garments/index.ts`: Exported all Phase 4 and 5 modules.
8. `frontend/src/engine/garments/__tests__/baseBodyAndDressUndress.test.ts`: Authored comprehensive test suite.
9. `docs/reports/YORVYN_BASE_BODY_DRESS_UNDRESS_PHASE_5.md`: Authored Phase 5 engineering report.

---

## 7. Recommended Next-Phase Tasks

1. **Procedural Fabric Physics & Secondary Motion**: Introduce lightweight Verlet or Position-Based Dynamics (PBD) for hem flutter on walking animations.
2. **Dynamic Wrinkle Normal Synthesis**: Implement tension-map driven micro-folds on elbows and knees during joint flexion.
3. **High-Poly Marvelous Designer / CLO3D GLTF Importer**: Expand `GarmentAssetLoader` to ingest production CAD patterns with multi-UV panel unwraps.

