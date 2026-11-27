# YORVYN Phase 16.9 — MotionCore Architecture & Subsystems

**Phase:** `16.9`  
**Engine:** **YORVYN MotionCore** (Unified Character Animation, Adaptive Garment Physics & Motion Intelligence Engine)  
**Architectural Alignment:** Phase 16.0 Capability Registry & Execution Boundary (`Authenticated Stylist Turn -> Local Intent & Evidence Policy -> Capability Registry -> MotionCore Orchestrator -> Specialized Adapters -> Independent Validation -> Durable Result & Provenance`)

---

## 1. Unified Single-Coordinator Design

Prior to Phase 16.9, `AvatarStudioViewer.tsx` drove `LiveMannequinEngine` (`araAnim`), `faceExpressionController`, `avatarPerformanceController`, and `ClothSimulationController` independently inside `requestAnimationFrame`, and only single-`Mesh` garments (not multi-component `THREE.Group` reconstructions) attached to XPBD.

MotionCore replaces fragmented updates with a single deterministic pipeline executed once per frame inside [`MotionCoreOrchestrator`](../../../frontend/src/engine/motionCore/MotionCoreOrchestrator.ts):

1. Advance single `THREE.AnimationMixer` via [`MotionStateManager`](../../../frontend/src/engine/motionCore/MotionStateManager.ts) (`IDLE`, `WALK`, `RUN`, `TURN`, `RAISE_ARMS`, `BEND`, `SIT`, `STAND`, `CUSTOM`, `PAUSED`, `RESETTING`, `ERROR`).
2. Apply optional confidence-weighted `PoseInputAdapter` landmarks and ordered **post-clip / pre-cloth** damped 2-bone `InverseKinematicsEngine`.
3. Update facial expressions & gesture micro-layers and flush `modelRoot.updateMatrixWorld(true)`.
4. Synchronize avatar capsule hulls (`ClothCollisionSystem`) and optional `three-mesh-bvh` body BVH proxies in [`GarmentDynamicsEngine`](../../../frontend/src/engine/motionCore/GarmentDynamicsEngine.ts).
5. Derive avatar translational/rotational inertia + optional wind vector.
6. Execute fixed-timestep XPBD constraints (`ClothConstraintSolver.solveStep`) across single or multi-component garments without replacing YORVYN's XPBD solver.
7. Resolve bounded spatial-hash self-collision (`SelfCollisionAdapter`, enabled on `high`/`maximum` tiers) and clamp local bind-space drift on `SkinnedMesh` parts (`<= 0.065 m`) so GPU skin matrices and XPBD drape never double-deform or detach.
8. Solve bounded spring inertia on `SecondaryMotionSolver` nodes (hair, sunglasses/accessories, unsimulated hems/panels), explicitly skipping any mesh registered as an XPBD cloth body.
9. Commit updated buffers in-place without mutating design revisions or candidate assets.
10. Record P50/P95/P99 timings and adaptive telemetry via `MotionPerformanceEvaluator` and adapt internal `QualityTier` when sustained frame spikes occur.

---

## 2. Internal Separation Without Exposing Technical Knobs

- Ordinary users in [`AvatarStudio.tsx`](../../../frontend/src/pages/AvatarStudio.tsx) see clean semantic controls (`Idle`, `Walk`, `Run`, `Turn`, `Raise Arms`, `Bend`, `Sit`, `Stand`, `Pause/Resume`, `Reset Pose`, `Export Animated`).
- Internal quality tiers (`low`, `balanced`, `high`, `maximum`), compute backends (`cpu_xpbd`, `webworker_xpbd`, `wasm_simd_xpbd`, `webgpu_experimental`), substeps, solver iterations, and SwiftShader/hardware separation are decided silently inside [`ComputeOrchestrator`](../../../frontend/src/engine/motionCore/ComputeOrchestrator.ts) and [`ComputePolicyAdvisor`](../../../backend/app/services/motion/motion_core.py).
