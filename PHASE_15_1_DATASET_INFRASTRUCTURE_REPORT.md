# YORVYN Phase 15.1 — Dataset Intelligence & Ground-Truth Infrastructure

**Date:** 2026-11-24  
**Repository HEAD:** `7139fc7eea4e1f890e28da9140db2e8550081267`  
**Software infrastructure status:** Verified for the implemented scope  
**Scientific pilot status:** Not populated; real evaluation is not ready.

## Architecture

Added `GarmentEvaluationDataset`, a fail-closed JSON manifest loader. It validates schema version and sample structure; confines asset paths to the manifest directory; verifies SHA-256, image decoding and dimensions; checks license rights, consent and annotation provenance; checks category/view/split/identity records; detects duplicate sample IDs, repeated views, reused image hashes and identity split leakage; and returns a machine-readable quality report.

`evaluation_gate(metric, split)` only permits an evaluation when the manifest is valid and the selected split has samples with the required reference type. Geometry requires reference geometry, silhouette requires masks, landmarks require landmark annotations, and components require component annotations. Synthetic manifests receive `SYNTHETIC_SMOKE_ONLY` and cannot enter real evaluation. Deterministic identity splitting uses a seeded SHA-256 bucket assignment and does not mutate existing manifest splits.

## Dataset artifacts

- `data/datasets/manifests/garment_evaluation_manifest_v1.schema.json`: JSON Schema for sample-level datasets.
- `data/datasets/manifests/garment_evaluation_pilot_v1.json`: versioned, explicitly real pilot shell with zero samples. This accurately records that target categories are not yet acquired.
- The existing dataset policy inventory remains unchanged; it is not treated as an evaluation manifest.

Each sample supports identity/category/subcategory/split, multiple views and image hashes/dimensions/camera metadata, reference geometry/masks, annotations with ownership/provenance, and license/consent provenance. License checks require documented source, evaluation permission, redistribution permission declaration, attribution declaration, restrictions, and non-expired terms when an expiry is supplied. Consent requires an evidence ID and evaluation permission.

## Verification

- `backend/venv/bin/python -m pytest backend/tests/test_phase15_evaluation_integrity.py -q` — **14 passed** (4.13s).
- `python3 -m py_compile backend/app/services/garments/evaluation/dataset_manifest.py` — passed.

Tests exercise the actual loader and readiness gate, including valid sample asset hashes, missing assets/provenance, identity split leakage, empty real pilot, synthetic-only classification, deterministic splitting, reference metric gating, and prior Phase 15.0 integrity behavior.

## Limitations and acceptance boundary

- Pilot contains **0 samples**, so no real evaluation can run. No images, reference meshes, annotations, license grants, or consent were fabricated.
- Near-duplicate image detection is not implemented; exact SHA-256 duplicate detection is.
- Reference geometry format and coordinate-system metadata are not yet deeply parsed or validated. Camera metadata currently checks required intrinsics/extrinsics presence, not numeric calibration semantics.
- License and consent checks validate declared provenance fields; they do not independently adjudicate legal terms or verify external source URLs.
- The JSON Schema provides structural validation, while loader-specific semantic and filesystem checks are authoritative. The loader currently accepts only schema version 1.0.0.
- Frontend was not changed, so no frontend test was required for this data/backend-only task.

## Exact next milestone

Populate the pilot only from a supplied or independently sourced license-cleared dataset. Add reviewed provenance records and identity-level split assignments, then deepen loader validation for camera calibration and reference mesh coordinate/scale contracts. Do not run or label real-world accuracy benchmarks until those samples pass the loader and metric-specific holdout gates.
