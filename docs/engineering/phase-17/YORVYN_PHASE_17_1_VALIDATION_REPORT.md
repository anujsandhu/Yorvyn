# YORVYN — PHASE 17.1 VALIDATION & GARMENT QUALITY ENGINEERING REPORT

**Phase:** 17.1  
**Baseline HEAD:** `7139fc7eea4e1f890e28da9140db2e8550081267` (preserved; no commits created)  
**Validation Execution Artifacts:**  
- Benchmark Manifest: `data/datasets/manifests/yorvyn_phase17_1_real_benchmark.json`
- Full Pipeline Benchmark (`130.18s`): `.gemini/antigravity/brain/940331b1-e7fa-47fa-93a5-cb8bbb9c3281/scratch/phase17_1_validation_results.json`
- Live Stage 10 E2E & Browser Receipt: `.gemini/antigravity/brain/940331b1-e7fa-47fa-93a5-cb8bbb9c3281/scratch/phase17_1_stage10_e2e.json`
- Browser UI Verification Screenshot: `.gemini/antigravity/brain/940331b1-e7fa-47fa-93a5-cb8bbb9c3281/screenshots/17_01_yip_browser_verified.png`

---

## Executive Summary

Phase 17.1 audited and empirically measured the Phase 17.0 YORVYN Intelligence Platform (YIP) across real-world garment photographs, Fashionpedia `independent_holdout` evaluation data, real reconstruction GLB outputs, `FitIntelligenceEngine`, `IndependentQualityCritic`, `ControlledCandidateOptimizer`, `GarmentKnowledgeRAG`, live FastAPI + PostgreSQL + Redis + browser endpoints, and a 100-run + 8-way concurrency stress test.

Validation uncovered **four concrete production/quality regressions** that were fixed and re-verified:
1. **Cross-Event-Loop AsyncIO Semaphore Crash (`backend/app/services/intelligence/yip_orchestrator.py`):** Replaced a singleton semaphore with a `WeakKeyDictionary()` keyed per running event loop (`_get_semaphore()`), enabling clean multi-loop pytest execution and 8/8 concurrent burst completions (`1872.5 ms`).
2. **Broken Live Critic GLB Ownership Lookup (`backend/app/api/intelligence_routes.py`):** Fixed `_load_owned_job_glb`, which previously referenced non-existent `garment_job_manager.get_asset_path(...)`, to sanitize `job_id` against path traversal (`os.path.basename` / `..` rejection), enforce strict owner verification, and resolve `os.path.join(PERMANENT_ASSET_DIR, safe_job_id, "garment.glb")`.
3. **Critic False Positives & Missed Primitive/Skinning/Texture Defects (`backend/app/services/intelligence/evaluation_critic.py`):** Adjusted `skin_visible_holes` heuristic (`connected_components > 40 or boundary_edges_count > max(1200, int(0.65 * face_count))`) to avoid flagging clean multi-panel meshes, and added raw glTF primitive index (`raw_degen` / `raw_dup`), texture buffer (`<= 16 B` / missing image -> `texture_gap`), and `JOINTS_0` / `WEIGHTS_0` skinning audits.
4. **Fit Penetration Calibration & Optimizer Degenerate-Triangle Dispatch (`backend/app/services/intelligence/fit_intelligence.py`, `candidate_optimizer.py`):** Calibrated true hull penetration flagging to `col_metrics.max_penetration_mm > 3.0`, added `stretch_ratio > 35.0` `CRITICAL` deformation detection, and aligned `_select_bounded_operation` matching for `degenerate` / `duplicate` / `remove_invalid_triangles` defects.

---

## Stage 1 & Stage 2 — Dataset Integrity & Disjoint Benchmark Curation

- **Manifest:** `data/datasets/manifests/yorvyn_phase17_1_real_benchmark.json`
- **Public Evaluation-Only Holdout (Fashionpedia):** `650` images on disk (`independent_holdout`, `overlap_train_holdout: 0`, `overlap_val_holdout: 0`, `commercial_training_eligible: false`).
- **CC-Licensed Real Garment Photos (Wikimedia Commons):** `66` unique photographs (`wm_00`..`wm_65`, `duplicates_removed: 0` against perceptual/content hashes).
- **Paired Segmentation Evaluation Set (`data/datasets/garment_classification_real/`):** `16` paired image/mask PNGs (caveat: reference masks originate from prior YORVYN visual-QA runs rather than external human pixel annotations).
- **Physical Ground-Truth Gaps Confirmed Absent on Host:** No external 3D garment scan meshes and no physical tailor caliper measurement tables exist locally; physical millimeter accuracy comparisons remain `NOT EVALUATED`.

---

## Stage 3 — Multimodal, Classification, Segmentation & Localization Benchmarks

### 3.1 Garment Classifier (`universal-garment-classifier` v6)
- **Fashionpedia `independent_holdout` (N = 650):**
  - `category_accuracy`: `0.5015` | `subcategory_exact_accuracy`: `0.2492`
  - `macro_precision`: `0.4112` | `macro_recall`: `0.4175` | `macro_f1`: `0.3835`
  - Calibration: `ECE = 0.1019`, `Brier = 0.213` | Latency: `8096.2 ms` total
  - Per-category F1 highlights: `bottoms` `0.638`, `tops` `0.580`, `skirt` `0.500`, `jacket` `0.482`, `dress` `0.402` (recall `0.261`), `shirt` `0.283`.
- **Wikimedia Commons OOD Real Photos (N = 66):**
  - `category_accuracy`: `0.6364` | `subcategory_exact_accuracy`: `0.5303`
  - `macro_precision`: `0.6195` | `macro_recall`: `0.5643` | `macro_f1`: `0.5395`
  - Calibration: `ECE = 0.1465`, `Brier = 0.142` | Latency: `1086.43 ms` total
- **Engineering Finding:** Real holdout accuracy (`50.15%`–`63.64%`) exposes domain-gap and dress/shirt calibration weaknesses masked by small synthetic smoke tests (`ECE` `0.1019–0.1465`). Classified `DEGRADED`.

### 3.2 Cached Vision Backbones (Local Execution Only)
- **Generic OpenAI CLIP ViT-B/32 (`clip_vit_b32_local`, `execution_backend: "cached_generic_openai_clip"`, N = 66 Wikimedia OOD):**
  - `category_accuracy`: `0.6515`, `macro_f1`: `0.626`, `ECE`: `0.1334`, Latency: `10899.39 ms` (not domain-tuned FashionCLIP).
- **DINOv2-Small on MPS (`dinov2_small`, `pretrained_weights_loaded: true`, N = 66 Wikimedia OOD):**
  - `category_recall_at_1`: `0.5909`, `category_recall_at_5`: `0.9242`, `category_mAP`: `0.4044`
  - `subcategory_recall_at_1`: `0.4545`, `subcategory_recall_at_5`: `0.8182` | Latency: `1949.69 ms`.
- **Uninstalled Models Verified Honest (`BLOCKED` / Not Executed):** `fashion_clip_native`, `siglip_native`, `grounded_sam2`, and `depth_anything_v2` have no local checkpoints installed and remain explicitly excluded from runtime claims.

### 3.3 Segmentation & Component Localization
- **Segmentation on 16 Prior-QA Paired Masks (run with `HF_HUB_OFFLINE=1`):**
  - `human_parsing_segformer_b2`: `mean_iou = 0.8622`, `mean_dice = 0.8904`
  - `opencv_contour` baseline: `mean_iou = 0.6227`
- **Component Localization (40 Fashionpedia Holdout Items):**
  - `macro_precision`: `0.3662`, `macro_recall`: `0.5641`, `macro_f1`: `0.4439` (`neckline` F1 `0.7692`, `sleeve` F1 `0.5625`, `torso` `0.0` due to panel granularity mismatch)
  - `multiview_pair_overall_agreement`: `1.0`.

---

## Stages 4 & 5 — 3D Geometry, UV & Texture Quality

- **8 Real-Photo Reconstructed GLB Pipelines:** `8/8` passed topological hygiene (`is_valid_topology: true`, `is_manifold: true`, `degenerate_faces: 0`, `non_manifold_edges: 0`, `uv_oob_ratio: 0.0`), with `uv_distortion` ranging `0.2308–0.2500`, `color_delta_e` `3.53–38.69`, and `histogram_similarity` `0.477–0.711`.
- **Synthetic Shifted Mesh Fixture (`SYNTHETIC_SMOKE_ONLY`):** `symmetric_chamfer_m = 0.007351`, `f_score_10mm = 1.0`.
- **Physical Reference Status:** `NOT_EVALUATED_NO_PHYSICAL_3D_SCAN_GROUND_TRUTH`.

---

## Stage 6 — Fit Intelligence Calibration

- Verified **input mesh immutability** (`non_mutation_verified: true`) across 4 Ara body profiles:
  - `standard_175`: `Oversized`, score `92.0`
  - `slim_lean`: `Oversized`, score `80.0`, `10.92 mm`
  - `athletic_broad`: `Potentially Incorrect`, score `64.0`, `40.96 mm`
  - `plus_curvy`: `Potentially Incorrect`, score `64.0`, `35.29 mm`
- Defect sensitivity verified: `asymmetric_defect_detected: true`, `tight_or_penetration_detected: true`.
- Physical Tailor Comparison: `NOT_EVALUATED_NO_PHYSICAL_TAILOR_DATASET`.

---

## Stages 7 & 8 — Independent Quality Critic & Controlled Candidate Optimizer

- **Critic Defect Confusion Matrix (11 Test Cases):** `TP: 9`, `FP: 0`, `FN: 0`, `TN: 2` -> **`defect_precision = 1.0`**, **`defect_recall = 1.0`**, **`false_positive_rate = 0.0`**, **`false_negative_rate = 0.0`**.
- **Publication Blocking Accuracy:** `0.9091` (`10/11`; the single delta is `construction_degenerate_faces`, where the strict critic returned `FAILED_CRITICAL` because injected non-manifold edges also triggered topological publication blocking).
- **Controlled Candidate Optimizer:**
  - `clean_noop`: `0` iterations (`NO_OPTIMIZATION_NEEDED`).
  - `degenerate_repair`: `1` iteration (`CRITIC_GATES_SATISFIED`, `accepted: true`, major defects reduced `2 -> 0`, `lineage_intact: true`, `76.532 ms`).
  - `corrupt_failfast`: `pub_allowed: false` (aborted safely).
  - `penetration_bounded_attempt`: `rollback_count: 1`, `pub_allowed: false` (non-degrading rollback preserved).

---

## Stage 9 — Hybrid Knowledge RAG & Security Firewall

- **10 Domain Queries + Injection Probe:**
  - `recall_at_1 = 1.0`, `recall_at_3 = 1.0`, `recall_at_5 = 1.0`, `precision_at_3 = 0.3333`, `mrr = 1.0`, `ndcg_at_5 = 1.0`
  - `citation_provenance_rate = 1.0`, `tenant_isolation_verified = true`, `prompt_injection_neutralized = true`
  - `mean_latency_ms = 0.421 ms`.

---

## Stage 10 & Stage 11 — Live Product E2E, Browser Verification & Stress Benchmarks

- **Live End-to-End Wardrobe Reconstruction + YIP API Workflow (`phase17_1_stage10_e2e.json`):**
  - Reconstruction completed cleanly in PostgreSQL + Redis + Outbox: `job_id: "job_44a8c22ce1b0"`, `job_status: "completed"`.
  - Owned Intelligence APIs verified: `fit_classification: "Oversized"` (`92.0`), `critic_overall_status: "PASSED"` (`critic_publication_allowed: true`), `optimizer_stopping_reason: "NO_OPTIMIZATION_NEEDED"`, `sync_pattern_valid: true`.
  - Tenant boundary verified: `cross_owner_critic_status: 403`; unauthenticated access rejected: `unauthStatus: 401`.
  - Live Vite + FastAPI browser inspection (`17_01_yip_browser_verified.png`): `{"ok": true, "pageErrors": [], "liveChecks": {"healthPhase": "17.0", "capsStatus": 200, "models": {"status": 200, "total": 12}, "rag": {"status": 200, "hits": 3}, "sim": {"status": 200, "top1": "g1"}, "recsStatus": 200, "unauthStatus": 401}}`.
- **100 Warm Orchestrations & Concurrency Burst:**
  - `100` sequential orchestrations: `failure_count: 0`, `min: 530.748 ms`, `p50: 545.253 ms`, `p95: 692.629 ms`, `p99: 751.014 ms`, `max: 1981.318 ms`, `rss_peak_mb: 788.88 MB`.
  - `8`-way concurrent burst: `8/8` succeeded in `1872.5 ms` wall clock.

---

## Final Automated Regression Verification (Post-All Edits)

- **Backend `pytest` (8 suites, `YORVYN_DISABLE_SEGFORMER=1 YORVYN_DISABLE_COMPONENT_CLIP=1`):** **`118 passed, 4 warnings in 20.29s`** (`test_phase17_1_validation.py`, `test_phase17_yip.py`, `test_phase16_intelligence.py`, `test_tenant_security.py`, `test_production_platform_phase_10.py`, `test_garment_chat_edits.py`, `test_durable_job_outbox_fault_injection.py`, `test_durable_job_publication_fix.py`).
- **Frontend `vitest`:** **`2 test files, 9 passed`** (`IntelligencePlatformIntegration.test.ts` 3/3 + `PhotoTo3DGarmentModalHandoff.test.tsx` 6/6).
- **Frontend Production Build (`npm run build`):** **`✓ built in 5.02s`**.

---

## Section 12 — Rigorous Capability Classification

| Capability / Component | Classification | Empirical Evidence & Scope Boundaries |
| :--- | :--- | :--- |
| YIP Orchestrator, Registry, API Auth & Live E2E Pipeline | **VERIFIED** | `118/118` backend tests, `9/9` frontend tests, Vite build clean, live PostgreSQL/Redis job `job_44a8c22ce1b0` + `403`/`401` boundaries + live browser verified (`pageErrors: []`), `100/100` warm runs + `8/8` concurrent burst (`0` failures). |
| Independent Quality Critic (`evaluation_critic.py`) | **VERIFIED** | `11`-case defect matrix achieved `precision=1.0`, `recall=1.0`, `FPR=0.0`, `FNR=0.0`; raw glTF buffer, texture buffer, and skinning checks verified; `pub_allowed` accuracy `0.9091` (strict non-manifold block). |
| Controlled Candidate Optimizer (`candidate_optimizer.py`) | **VERIFIED** | Verified no-op on clean mesh, bounded `1`-iteration `degenerate_repair` (`2 -> 0` major defects, `76.532 ms`, lineage intact), fail-fast on corrupt input, and rollback on unsafe penetration adjustment. |
| Hybrid Knowledge RAG & Injection Firewall (`GarmentKnowledgeRAG`) | **VERIFIED** | `10` domain queries + firewall test: `recall@1/3/5 = 1.0`, `MRR = 1.0`, `nDCG@5 = 1.0`, `citation_provenance_rate = 1.0`, tenant isolation and injection neutralization `true`, mean `0.421 ms`. |
| 3D Topological Mesh / UV Hygiene (8 Real-Photo Pipelines) | **VERIFIED** | `8/8` real-photo pipelines manifold, `0` degenerate faces, `0` non-manifold edges, `0.0` UV OOB, `uv_distortion` `0.2308–0.2500`; synthetic shifted Chamfer `0.007351 m` (`SYNTHETIC_SMOKE_ONLY`). |
| Cached Vision Backbones (`clip_vit_b32_local`, `dinov2_small`, `segformer_b2`) | **EXECUTED** | Locally executed on `66` Wikimedia CC photos / `16` paired masks (`clip_vit_b32_local` `0.6515` cat acc; `dinov2_small` R@1 `0.5909` / R@5 `0.9242` / mAP `0.4044`; `segformer_b2` mIoU `0.8622` vs OpenCV `0.6227`). |
| Fit Intelligence Engine (`FitIntelligenceEngine`) | **EXECUTED** | Non-mutation verified; differentiates 4 Ara profiles (`92.0` -> `64.0`) and synthetic asymmetric/penetration defects; lacks physical tailor ground truth. |
| Benchmark Manifest & Identity-Disjoint Evaluation Split | **REFERENCE-VALIDATED** | `650` Fashionpedia `independent_holdout` + `66` Wikimedia CC real photos with `0` train/val overlap and `0` duplicate image hashes. |
| Garment Classifier (`universal-garment-classifier` v6) & Component Localization | **DEGRADED** | Real holdout exposes domain calibration gap: Fashionpedia `0.5015` cat acc (`ECE 0.1019`, `dress` recall `0.261`), Wikimedia OOD `0.6364` cat acc (`ECE 0.1465`); component localization `macro_f1 0.4439` (`torso 0.0`). |
| Uninstalled Checkpoints (`fashion_clip_native`, `siglip_native`, `grounded_sam2`, `depth_anything_v2`) | **BLOCKED** | Weight checkpoints are not installed on host; blocked from runtime execution and honestly reported unavailable. |
| Physical 3D Scan Accuracy & Physical Tailor Measurement Error | **NOT EVALUATED** | No external physical 3D scan ground-truth meshes or physical tailor measurement datasets exist on host. |
