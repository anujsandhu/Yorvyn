# YORVYN Phase 15 — Autonomous Image-to-3D Reconstruction Plan

**Status:** Audit complete; Stage 0 integrity fixes and a first evidence-to-geometry adapter are implemented. Phase 15 remains in progress.  
**Baseline:** `7139fc7eea4e1f890e28da9140db2e8550081267` plus extensive uncommitted workspace overlay.  
**Guiding constraint:** improve the existing path and validate each stage; do not claim full Phase 15 until a real-image end-to-end acceptance run succeeds.

## Repository reuse map

- Input validation and evidence: `backend/app/api/garment_identification_routes.py`, `backend/app/services/ai/contracts.py`, `backend/app/services/ai/multiview/*`.
- Semantic/intelligence adapters: `backend/app/services/garments/intelligence/*` and `backend/app/services/ai/providers/*` (some named model stages are generic or heuristic; provenance must remain explicit).
- Geometry: `backend/app/services/garments/reconstruction/{engine_registry.py,universal_construction_graph.py,*_engine.py}`, `garment_mesh_builder.py`.
- Mesh/appearance/export: `mesh_validation_service.py`, `reconstruction/mesh_validator.py`, `appearance/{uv_reconstruction_engine.py,materialx_pbr_system.py,reference_texture_reconstructor.py}`, `glb_exporter.py`.
- Fit/physics: `fitting/{avatar_body_measurement_engine.py,universal_garment_fitting_engine.py,garment_physics_engine.py}` and frontend `engine/clothPhysics/*`.
- Jobs/UI: `job_manager.py`, `garment_generation_routes.py`, frontend `PhotoTo3DGarmentModal.tsx`, `fashionApi.ts`, Three.js viewer.

## Execution sequence and gates

### Stage 0 — Evidence honesty and regression baseline (P0, first implementation)

- Correct evaluation code so metrics require actual references; missing ground truth yields `NOT_EVALUATED`, never plausible synthetic values.
- Fix component evaluator sample-count mismatch; add unit tests for evaluator edge cases and non-fabrication of unavailable metrics.
- Label existing generated fixture suites as synthetic smoke tests; supersede misleading Phase 14.27 claims with a reconciliation record.
- **Progress:** component evaluator rejects mismatched sample counts and reports empty datasets as not evaluated. Ground-truth evaluator returns null for absent reference-dependent metrics and computes only from explicitly supplied references. Generated fixture suites are labeled synthetic smoke; unsupported accuracy/IoU/manifold claims have been removed.
- **Acceptance:** wrong-sized prediction arrays fail loudly; unavailable reference metrics are not generated; synthetic fixtures cannot be reported as real-world accuracy. Combined rerun of the Phase 15 integrity tests and full legacy Phase 8 module is in progress after worker integration.

### Stage 1 — Input intelligence and semantic decomposition

- Establish schema-backed image manifest with decoded dimensions/orientation, file hash, view source, usable/occlusion status, and explicit unknown state.
- Use current taxonomy/component graph; add category-specific decomposition completeness checks, not duplicate classifiers.
- **Acceptance:** deterministic manifests, image hash traceability, view classification abstention measured on a labeled pilot set, inferred/unknown distinction retained.

### Stage 2 — Evidence-aware multi-view geometry

- Define supported projection/landmark inputs from V2; worker must consume them and record which mesh constraints each observation affected.
- Keep category construction templates; fit front/back/side silhouettes and landmarks under confidence-weighted constraints. Single view constrains visible surface only; unseen geometry remains inferred.
- **Acceptance:** held-out multi-view reprojection error and silhouette IoU improve over unconditioned parametric baseline without topology regressions; per-view evidence lineage present.
- **Progress:** the worker now preserves front-view V2 intelligence across back-view analysis and adapts only source-cited `OBSERVED` component presence into the existing reconstruction intelligence (`detected`/`not_detected` plus source IDs/provider provenance). Inferred, unknown, conflicted, and uncited evidence is not promoted. This is a narrow bridge: boxes, landmarks, dimensions, patterns, texture correspondences, and per-vertex uncertainty are not yet consumed by geometry; no complete real-image job has been validated.

### Stage 1 — Job configuration reliability

- **Progress:** PostgreSQL DSN resolution now uses `YORVYN_PG_DSN`, then container-provided `DATABASE_URL`, then the existing local fallback.
- **Acceptance:** resolver tests check override precedence and container fallback. Live database connectivity remains environment-dependent and is not claimed.

### Stage 3 — Mesh validity and optimization

- Fix fallback validators that report invented nominal topology when optional parser dependencies are absent; return `UNVERIFIED` instead.
- Add actual checks for degenerate/duplicate/nonmanifold/self-intersecting geometry, connected components, boundary loops/openings, normals and scale.
- **Acceptance:** defect-specific regression fixtures; no silent success on parser absence; critical defect gates independent of aggregate score.
- **Progress:** GLB validation no longer fabricates topology counts, bounds, volume, manifoldness, or watertightness when Trimesh is unavailable. It returns invalid/unverified status with zero measured counts and a warning. Full defect coverage and the in-memory validator's edge-case handling remain open.

### Stage 4 — Texture, UV and materials

- Preserve current UV/PBR exporters; connect visible source regions to surface UVs and report unobserved fills as inferred.
- Use calibrated swatch data before estimating physical roughness/stretch/thickness.
- **Acceptance:** UV stretch and texture alignment metrics computed against real references; unseen regions visibly/provenance-marked; no fake fabric accuracy.

### Stage 5 — Fit and cloth simulation

- Separate avatar measurement sources/fallbacks and confidence; calibrate preset dynamics using repeatable hanging/drape fixtures.
- Keep PBD preview until measured comparisons justify heavier XPBD/FEM/PhysX dependency.
- **Acceptance:** measured penetration/clearance, settling, strain and deformation stability; no physics-accuracy claim from presets alone.

### Stage 6 — Independent visual critic

- Render fixed front/back/left/right/three-quarter, wireframe, normals, UV and material views using current renderer.
- Compare source silhouettes only from matching observed views; mesh validity and component completeness gate separately.
- Produce structured defects (id/category/severity/region/confidence/root cause/recommended action/test).
- **Acceptance:** critic metrics validated against manual annotations; no self-referential score path.

### Stage 7 — Bounded autonomous optimization and candidate lineage

- Store immutable iteration candidates, config/model/input hashes, reports and parent pointers; keep best valid candidate; rollback on regressions.
- Deterministic localized correction policies first; bounded iterations/time/compute; stop for acceptance, plateau, evidence insufficiency or failure.
- **Acceptance:** repeatable run, explicit stop reason, no best-candidate overwrite, seeded replay, monotonic best-so-far quality, critical blockers never masked by composite score.

### Stage 8 — Export and product review

- Keep GLB/glTF as primary runtime target; add OBJ only if it preserves required material/texture semantics. FBX/USDZ only after a concrete consumer needs them.
- Re-import generated artifacts in independent parsers and current Three.js viewer; add side-by-side original/best/history and defect inspection to UI.
- **Acceptance:** real-image full-flow run yields validated asset, auditable candidate history, confirmed/unknown provenance, and reproducible quality report.

## Data and research constraints

`data/datasets/manifests/garment_dataset_manifest_v3.json` has an empty `split_summary`; it records several non-commercial datasets as restricted and says user photos are not training eligible by default. Do not use restricted data for commercial training or convert synthetic benchmark renders into real-image validation. Prepare a license-cleared, identity/session-disjoint pilot set with explicit annotation/version/hash records. Evaluate research reconstruction approaches only after code, checkpoint, license, MPS/CPU memory, latency, and export compatibility are verified.

## Phase completion rule

Phase 15 remains open until a real-image flow produces an editable mesh with appropriate topology, usable UV/material export, evidence-aware uncertainty, independent critic defects, bounded iterative correction, candidate rollback, and reproducible measurements. Successful compile, synthetic smoke tests, or attractive screenshots are insufficient.
