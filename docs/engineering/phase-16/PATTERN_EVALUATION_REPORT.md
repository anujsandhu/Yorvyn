# Phase 16.2 Pattern Construction Evaluation Report

Evidence file: [`docs/reports/PHASE_16_2_EVALUATION_EVIDENCE.json`](../../reports/PHASE_16_2_EVALUATION_EVIDENCE.json).

## 1. Scientific Evaluation Status: **BLOCKED**

- **Target Holdout Manifest**: `data/datasets/manifests/garment_evaluation_pilot_v1.json` currently contains **`0` samples** (`samples: []`, `REAL_DATASET_INCOMPLETE`).
- **Cached Public Dataset Inspection**: Cached `fashionpedia_val.parquet` contains single-view 2D bounding boxes only and lacks sewing pattern contours, seam-edge correspondences, metric panel dimensions, and multi-view garment observations. It is **not suitable** as pattern/construction ground truth.
- **Evaluator Fail-Closed Behavior**: Calling `PatternEvaluator.evaluate_against_reference([], [], dataset_kind="real_holdout")` deterministically returns `evaluation_status: "NOT_EVALUATED_EMPTY_DATASET"` with `sample_count: 0`.
- **Policy Compliance**: No fabricated pattern accuracy, Chamfer boundary accuracy, or commercial CAD compliance scores are reported.

## 2. Software & Real-Photo Execution Verification (`scripts/evaluate_phase_16_2_construction.py`)

All 7 representative real YORVYN garment photos ran end-to-end through **Phase 16.1 (`analyze_garment_components` with local SegFormer + CLIP on macOS/MPS) -> Phase 16.2 (`PatternConstructionEngine`) -> `AssemblyValidator` -> JSON/SVG/DXF Export -> `ReconstructionEngineRegistry.validate_construction_handoff`**:

| Photo | Category / Subcategory | Pieces | Seams | Topology Valid | Assembly Valid | SVG XML / DXF R12 Valid | Rear Marked Observed Violation | Target Engine Match |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- |
| `wm_00_jacket_denim.jpg` | `jacket` / `denim_jacket` | 12 | 16 | 100% | Yes | Yes (`12` groups / `24` polylines) | None (`false`) | `jacket_pattern_engine_v1` |
| `wm_05_hoodie_pullover.jpg` | `hoodie` / `pullover_hoodie` | 11 | 15 | 100% | Yes | Yes (`11` groups / `22` polylines) | None (`false`) | `hoodie_pattern_engine_v1` |
| `wm_17_shirt_formal.jpg` | `shirt` / `formal_shirt` | 11 | 15 | 100% | Yes | Yes (`11` groups / `22` polylines) | None (`false`) | `shirt_pattern_engine_v1` |
| `wm_21_tshirt_graphic.jpg` | `tops` / `tshirt` | 6 | 8 | 100% | Yes | Yes (`6` groups / `12` polylines) | None (`false`) | `tops_pattern_engine_v1` |
| `wm_25_trousers_chinos.jpg` | `bottoms` / `chinos` | 6 | 11 | 100% | Yes | Yes (`6` groups / `12` polylines) | None (`false`) | `bottoms_pattern_engine_v1` |
| `wm_41_dress_aline.jpg` | `dress` / `a_line_dress` | 4 | 8 | 100% | Yes | Yes (`4` groups / `8` polylines) | None (`false`) | `dress_pattern_engine_v1` |
| `wm_45_kurta_ethnic.jpg` | `traditional` / `kurta` | 6 | 9 | 100% | Yes | Yes (`6` groups / `12` polylines) | None (`false`) | `traditional_pattern_engine_v1` |

## 3. Synthetic Smoke Check (Not Accuracy Evidence)

`PatternEvaluator.evaluate_against_reference` executed a self-consistency smoke check (`evaluation_status: "SYNTHETIC_SMOKE_ONLY"`) across 7 synthetic category pairs, verifying all metric fields compute (`seam_f1: 1.0`, `pattern_topology_validity: 1.0`). These numbers measure deterministic software self-consistency only and must never be cited as empirical accuracy.
