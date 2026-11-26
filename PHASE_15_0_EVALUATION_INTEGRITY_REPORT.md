# YORVYN Phase 15.0 — Evaluation Integrity & Reproducible Benchmarking

**Date:** 2026-11-24  
**Repository HEAD:** `7139fc7eea4e1f890e28da9140db2e8550081267`  
**Status:** Integrity remediation implemented; scientific holdout acceptance remains blocked by the absence of a verified real-image/reference dataset.

## Executive summary

Phase 15.0 removed fabricated metric paths from the garment ground-truth evaluator, marked the procedural garment suite as synthetic, fixed a GLB validation fallback that claimed invented topology, and relabeled the Phase 14.27 authored accuracy examples as evaluator smoke tests. The existing application and frontend tests passed in the available environment.

This does **not** establish real-world reconstruction accuracy or complete Phase 15.0's scientific holdout acceptance. The repository has no verified reference mesh/mask/landmark holdout with identity-disjoint splits and provenance sufficient to compute those results. The earlier Phase 8 report is now explicitly superseded for its generated-image accuracy claims.

## Repository findings

- `ground_truth_evaluator.py` now leaves reference-dependent Chamfer/F-scores, silhouette IoU, scale error, SSIM, pattern preservation, and fabric correctness unavailable unless suitable explicit reference inputs are supplied. Geometry metrics no longer use a sine-function proxy or fixed fabric score.
- `real_world_benchmark.py` procedurally synthesizes images despite its historical “real-world” naming and authored metadata. Its class, docstrings, and exported manifest now state that it is a synthetic smoke suite. Its historical module/API name remains for compatibility.
- `scripts/benchmark_phase_14_27_multiview.py` contains hand-authored confidence and component examples, plus mock provider/fusion calls in its latency trace. Category D is labeled a synthetic evaluator-contract smoke test; the hand-authored component scores no longer gate acceptance and are nested under `synthetic_fixture_metrics`.
- `mesh_validation_service.py` previously returned fabricated vertex/face counts, bounds, volume, watertightness, and manifoldness when Trimesh was missing. It now returns invalid/unverified with zero measured counts and an explicit warning.
- Component evaluation rejects unequal sample counts and reports empty input as `NOT_EVALUATED_EMPTY_DATASET`.
- PostgreSQL DSN selection now respects `YORVYN_PG_DSN`, then `DATABASE_URL`, then the local fallback.

## Changes made

- Strengthened `backend/tests/test_phase15_evaluation_integrity.py` with checks for metric non-fabrication, component count mismatch/empty input, explicit reference distance/mask requirements, observed-evidence adaptation, DSN precedence, unverified GLB fallback, and synthetic manifest status.
- Preserved the previous Phase 15 Stage 0 changes and extended the Phase 15 plan/audit with worker integration and mesh validation progress.
- Added a supersession notice to the historical Phase 8 report; no historical output artifacts were rewritten.

## Validation

Commands executed from the repository root unless stated otherwise:

- `backend/venv/bin/python -m pytest backend/tests/test_phase15_evaluation_integrity.py backend/tests/test_real_world_ai_phase_8.py -q` — **19 passed** (52.04s; 333 Pillow/Transformers warnings).
- After adding the synthetic manifest regression: `backend/venv/bin/python -m pytest backend/tests/test_phase15_evaluation_integrity.py -q` — **9 passed** (5.63s).
- `npm test -- --run` from `frontend/` — **25 test files, 355 tests passed** (3.91s; Vite configuration/deprecation warnings).
- `python3 -m py_compile scripts/benchmark_phase_14_27_multiview.py backend/app/services/garments/evaluation/real_world_benchmark.py backend/app/services/garments/evaluation/ground_truth_evaluator.py` — passed.
- Earlier targeted compile also covered job manager, evidence adapter, DSN resolver, mesh validator, component evaluator, and generalization evaluator — passed.

The Phase 8 module is synthetic smoke coverage; its pass result is not real-image accuracy evidence. No live provider call, PostgreSQL connection, full job execution, real holdout evaluation, or browser reconstruction was performed.

## Acceptance status

1. **Fabricated metrics removed from evaluator acceptance paths:** addressed for the audited evaluators and fallback.
2. **Every reported metric traceable to reference evidence:** reference-required evaluation API supports explicit reference geometry/masks/labels; repo-wide guarantee is incomplete, particularly historical generated reports and other benchmark scripts.
3. **Synthetic and real-world results separated:** procedural suite and Phase 14.27 Category D are labeled synthetic; historical Phase 8 report superseded. Other legacy “real-world” naming should be audited.
4. **Holdout reproducibility:** not met; no verified identity-disjoint real-image holdout, full execution metadata recorder, or sufficient reference asset corpus is present.
5. **Unavailable measurements disclosed:** addressed in target evaluator and synthetic manifests, not verified across every report producer.
6. **Relevant regressions pass:** targeted backend suites and frontend suite pass.
7. **Application functionality:** frontend suite passes; the broad backend suite and complete real-photo flow were not run/verified.

## Known limitations

- Chamfer/F-score currently compares supplied mesh vertex samples; it does not yet implement area-weighted surface sampling, camera-conditioned multi-view reprojection, or normal correspondence against a reference surface.
- Reference-camera/landmark/multi-view metric APIs and provenance-linked dataset manifest validation remain incomplete.
- Dataset manifest `data/datasets/manifests/garment_dataset_manifest_v3.json` is a license/policy inventory, not the requested sample-level evaluation manifest; its `split_summary` is empty.
- Component evaluator still treats missing boxes on jointly present components as IoU 1.0, which is valid for presence-only scoring but unsuitable for localization scoring without explicit box-annotation completeness.
- The Phase 14.27 script still runs mocked provider/fusion calls in its latency category. These calls and stage timings are not live end-to-end latency measurements; the script should not be presented as a production benchmark.
- Large unrelated pre-existing workspace modifications remain untouched. HEAD remains unchanged.

## Exact next recommended task

Create a sample-level, license-cleared real evaluation pilot manifest and loader with stable sample/garment IDs, image and reference-asset hashes, view/camera/landmark/component annotations, annotation and consent provenance, and identity-disjoint train/calibration/holdout enforcement. Require the runner to refuse “real-world evaluation” status when any reference, provenance, or split integrity check is missing. Only then implement surface-sampled geometry, mask boundary, landmark, and multi-view reprojection metrics against that pilot set.
