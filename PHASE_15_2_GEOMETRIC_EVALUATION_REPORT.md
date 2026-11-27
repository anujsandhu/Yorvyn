# YORVYN Phase 15.2 — Geometric Evaluation Engine

**Date:** 2026-11-24  
**HEAD:** `7139fc7eea4e1f890e28da9140db2e8550081267`   
**Status:** Core reference-metric primitives implemented; full phase acceptance remains open. The Phase 15.1 pilot is empty, so no real-world accuracy evaluation has occurred.

## Implemented

`backend/app/services/garments/evaluation/geometric_evaluator.py` adds:

- Deterministic, area-weighted triangle-surface sampling with barycentric point generation.
- Bidirectional nearest sampled-surface mean distances and symmetric Chamfer, threshold precision/recall/F-score, mean/median/P95/max distances, and oriented plus orientation-invariant sampled normal consistency.
- Explicit coordinate contract requirement (`units: m`, coordinate system) and optional dataset-gate enforcement. Ungated outputs are `SYNTHETIC_SMOKE_ONLY`; denied gates return unavailable status.
- Mesh content hashes, sampling configuration, execution time, and warnings in results.
- Reference-mask IoU, Dice, boundary Chamfer and boundary precision/recall at one pixel.
- Reference landmark Euclidean/normalized error and missing landmark rate.
- Camera point projection with matrix shape, finite-value, rotation orthogonality/determinant, intrinsics, and resolution validation.
- Structural mesh validation adapter using the existing `GarmentMeshValidator`.

The existing `GarmentGroundTruthEvaluator` now uses surface sampling when given a reference mesh and explicit coordinate contract. Without that contract, reference geometry remains `NOT_EVALUATED`; vertex-only pseudo-surface metrics are not used by the public evaluation path.

## Validation

- `backend/venv/bin/python -m pytest backend/tests/test_phase15_evaluation_integrity.py backend/tests/test_real_world_ai_phase_8.py -q` — **29 passed** (56.32s; 333 existing Pillow/Transformers warnings). Phase 8 coverage is synthetic smoke testing, not real-world accuracy evidence.
- `backend/venv/bin/python -m py_compile backend/app/services/garments/evaluation/geometric_evaluator.py backend/app/services/garments/evaluation/ground_truth_evaluator.py` — passed.

Synthetic mathematical tests cover repeatability, identical meshes, translation sensitivity, mask overlap/resolution rejection, missing coordinate contract, denied real-data gate, camera validity, and landmark errors. They validate software behavior only.

## Limitations

- Nearest neighbors are computed between deterministic samples on each surface, not exact point-to-triangle closest-point queries. The sampling approximation is explicit and density configurable. SciPy KD-tree is used when installed; fallback uses chunked brute force.
- Area sampling requires valid triangular faces; malformed-index/non-finite/zero-area cases fail, but complete mesh validity analysis remains delegated to existing structural validator and does not implement self-intersection tests.
- F-score currently reports one configurable threshold per call; multi-threshold aggregation is not yet included.
- Surface normals are triangle normals from the sampled face; no reference normal field or vertex-normal interpolation contract exists.
- Silhouette masks are compared only; renderer-to-camera mesh rasterization, calibration-to-image-size consistency, multi-view aggregation, and occlusion-aware reprojection are not implemented.
- Landmark API uses 3D coordinate dictionaries and caller-provided normalization scale; schema-linked category-specific required landmarks and 2D camera reprojection errors remain outstanding.
- Evaluation result contract does not yet include dataset manifest hash, evaluation code version, sample/identity IDs, or reference/prediction source asset hashes beyond computed mesh content hashes.
- No verified real pilot examples exist; `READY_FOR_REAL_EVALUATION` cannot be achieved with the committed empty manifest.

## Next task

Implement the camera-conditioned mesh rasterization and multi-view reprojection evaluator, connected to the sample-level manifest's verified camera and mask records. First deepen camera/coordinate schema validation and preserve per-view results. Do not report accuracy until the real pilot is populated with independently licensed, annotated references.
