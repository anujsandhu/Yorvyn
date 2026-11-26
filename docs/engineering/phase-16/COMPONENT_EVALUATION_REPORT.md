# YORVYN — Phase 16.1 Component Evaluation Report

**Date:** 2026-11-25  
**Evaluator Module:** [component_evaluator.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/ai/evaluation/component_evaluator.py)  
**Evaluation Script:** [evaluate_phase_16_1_components.py](file:///Users/anujsandhu/Projects/yorvyn/scripts/evaluate_phase_16_1_components.py)  
**Recorded Evidence:** [PHASE_16_1_EVALUATION_EVIDENCE.json](file:///Users/anujsandhu/Projects/yorvyn/docs/reports/PHASE_16_1_EVALUATION_EVIDENCE.json)

## 1. Scientific Dataset & Holdout Readiness

| Artifact / Source | Status | Reason |
| :--- | :--- | :--- |
| [garment_evaluation_pilot_v1.json](file:///Users/anujsandhu/Projects/yorvyn/data/datasets/manifests/garment_evaluation_pilot_v1.json) | `REAL_DATASET_INCOMPLETE` (`samples: []`) | No multi-view, identity-disjoint, visibility-annotated pilot dataset is populated in the workspace. Full scientific holdout acceptance is **BLOCKED**. |
| `detection-datasets/fashionpedia` (`val` parquet, locally cached) | `ACADEMIC_SINGLE_VIEW_PART_EVALUATION` | Independently human-annotated CC BY 4.0 / CC BY-NC-SA 4.0 academic dataset with 2D part bounding boxes across 50 validation samples. Lacks visibility states (`OCCLUDED` / `OUT_OF_FRAME`), multi-view pairs, and seam/cuff/fly/waistband mappings. |

## 2. Measured Single-View Component Evaluation (50 Fashionpedia Validation Images)

Executed on real cached `val-00000-of-00001-0b29e85429788213.parquet` images (first 50 apparel+part rows) running cached `SegFormer-B2 Clothes`, cached `OpenAI CLIP ViT-B/32`, and deterministic Sobel/contour localizers on Apple Silicon MPS/CPU.

### 2.1 Presence & False Absence (No IoU Threshold)

| Component | Support (`pos`) | Precision | Recall | F1 | Mean Box IoU | False Absence Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `neck_opening` | 40 | 0.9630 | 0.6500 | 0.7761 | 0.2851 | 0.0000 |
| `sleeve` | 28 | 0.7857 | 0.3929 | 0.5238 | 0.1981 | 0.0000 |
| `collar` | 6 | 0.3000 | 0.5000 | 0.3750 | 0.1794 | 0.0000 |
| `lapel` | 5 | 0.5000 | 0.2000 | 0.2857 | 0.2770 | 0.0000 |
| `pocket` | 13 | 0.6667 | 0.1538 | 0.2499 | 0.0069 | 0.0000 |
| `hood` | 1 | 0.0000 | 0.0000 | 0.0000 | — | 0.0000 |
| `zipper` | 3 | 0.0000 | 0.0000 | 0.0000 | — | 0.0000 |
| **Macro Average** | **50 imgs** | **0.4593** | **0.2710** | **0.3158** | **0.1893** | **0.0000** |

- **Calibration (50 samples):** `ECE = 0.1267`, `Brier = 0.1843`.

### 2.2 Localization (`IoU >= 0.30`, Box Required)

- **Macro Precision:** `0.1186`, **Macro Recall:** `0.1289`, **Macro F1:** `0.1178`, **Macro Box IoU:** `0.1893`.
- **Diagnostic Conclusion:** Zero false absences occurred (`0.0000`), confirming the non-fabrication contract (`NOT_OBSERVED != ABSENT`). However, deterministic silhouette-column slicing and coarse crop CLIP checks do not tightly localize small in-the-wild Fashionpedia parts (`pocket` IoU `0.0069`, `zipper` recall `0.0`). Downstream geometry should continue treating low-IoU local detections cautiously until a dedicated part detector (e.g., pinned Grounded-SAM 2 / YOLO-Fashionpedia) is trained and certified.

## 3. Real-Photo Pipeline Execution Evidence (`data/datasets/phase_13_6_real_photos/`)

All 7 category photos (`wm_00_jacket_denim.jpg`, `wm_05_hoodie_pullover.jpg`, `wm_17_shirt_formal.jpg`, `wm_21_tshirt_graphic.jpg`, `wm_25_trousers_chinos.jpg`, `wm_41_dress_aline.jpg`, `wm_45_kurta_ethnic.jpg`) executed cleanly on `segformer_b2_clothes` + CLIP + OpenCV:
- `wm_00_jacket_denim.jpg` (`jacket`): Detected `collar` (`SAFE_TO_USE`, `0.90`), `button_placket` (`SAFE_TO_USE`, `0.774`), `chest_pocket` (`SAFE_TO_USE`, `0.86`), `left_sleeve` (`SAFE_TO_USE`), `right_sleeve` (`SAFE_TO_USE`), `cuff` (`SAFE_TO_USE`), `hem` (`OCCLUDED` -> `REQUIRE_MORE_EVIDENCE`); kept `back_body` / `zipper` / `lapel` / `flap_pocket` as `NOT_OBSERVED`; built `16` graph nodes and `39` typed edges.
- `wm_25_trousers_chinos.jpg` (`bottoms`): Detected `lower_waistband` (`SAFE_TO_USE`), `fly` (`SAFE_TO_USE`), `right_leg` (`USE_WITH_UNCERTAINTY`), `left_leg` (`OCCLUDED`), `leg_opening` (`OCCLUDED`); kept `back_pocket` and `back_rise` as `NOT_OBSERVED`.
- `wm_41_dress_aline.jpg` (`dress`): Detected `bodice` (`SAFE_TO_USE`), `waistline` (`SAFE_TO_USE`), `skirt` (`SAFE_TO_USE`), `neckline` (`SAFE_TO_USE`), `hem` (`PARTIALLY_VISIBLE`); kept `dress_closures` as `NOT_OBSERVED`.

## 4. Open Scientific Evaluation Gaps

- Visibility accuracy, landmark normalized error, segmentation mask IoU, and multi-view per-component consistency metrics have no real-world measurements yet because no visibility/mask/multi-view reference manifest exists in `garment_evaluation_pilot_v1.json`.
