# YORVYN Phase 16.9 — Technology Selection & Dependency Audit

**Baseline Packages Reused (Zero Unaudited Bloat Installed):**

| Domain | Selected Primary Runtime | Installed / Verified Status | Alternatives Kept Behind Adapters / Gated |
|---|---|---|---|
| Character Animation | Three.js `0.186.1` (`AnimationMixer`, `AnimationClip`, `AnimationAction`, `Skeleton`, `SkinnedMesh`, morph targets) + Ara `Animator` clips | Production active | Blender offline GLB authoring supported; Mixamo optional via `RetargetingEngine` (`mixamorig:*` aliases) — zero mandatory Mixamo runtime coupling |
| Inverse Kinematics | Post-clip damped 2-bone limb IK & joint angle clamping inside `InverseKinematicsEngine` | Production active | `CCDIKSolver` compatibility behind adapter |
| Motion Capture (Optional) | Confidence-weighted `PoseInputAdapter` (reusing installed `@mediapipe/tasks-vision ^1.2.2`) | Optional / degraded offline (`motion.capture`) | MoveNet adapter shape; live webcam is strictly optional — core acceptance runs offline |
| Cloth Physics | Existing YORVYN XPBD `ClothConstraintSolver` + `ClothCollisionSystem` + `GarmentDynamicsEngine` | Production primary | Rapier / Havok NOT swapped in (policy: never replace XPBD without comparative proof) |
| Collision Spatial Acceleration | Capsule bone hulls + installed `three-mesh-bvh ^0.9.17` (`MeshBVH`) + `SelfCollisionAdapter` spatial grid | Production active | Full cloth self-BVH remains gated to `high`/`maximum` vertex budgets |
| Rendering & Compute | Three.js **WebGL2** primary | Production primary | WebGPU (`three.webgpu.js`) & TSL remain strictly `webgpuExperimentalOnly: true` until shader/simulation parity & device-loss parity pass |
| Off-Main-Thread / CPU Acceleration | Typed `Float32Array` buffers + `Worker` & `WebAssembly.validate` WASM SIMD probe in `ComputeOrchestrator` | Probed & policy-routed | `workerExecutionMs` reported honestly (`0` when running inline CPU) |
| Asset Export | `@gltf-transform/core` + Ara binary glTF v2 writer (`export/glb.ts`) + `validateAnimatedGLBExport` | Production active | Explicitly distinguishes `skeletal_animation_export`, `skeletal_with_garment_deformation`, `baked_simulation_export`, `static_garment_export` |

## Explicit Non-Claims

1. **No physical laboratory fabric accuracy claim:** `AdaptiveFabricProfileService` and `AdaptiveFabricPhysicsResolver` set `is_measured_physical: false` / `isMeasuredPhysical: false` on every category/evidence profile (`denim_jacket`, `hoodie`, `shirt`, `tshirt`, `trousers`, `jeans`, `dress`, `skirt`, `traditional`, `sportswear`, `footwear`).
2. **No baked-cloth forgery on skeletal exports:** Exporting an animated avatar GLB classifies honestly as `skeletal_animation_export` unless morph/vertex delta tracks are present and verified.
3. **No SwiftShader misrepresentation:** Browser E2E explicitly sets `isSoftwareRendered: true` and `environment: "headless_chromium_swiftshader_not_native_gpu"`.
