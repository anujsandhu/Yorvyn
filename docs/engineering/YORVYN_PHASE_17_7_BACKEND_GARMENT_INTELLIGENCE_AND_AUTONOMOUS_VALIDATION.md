# YORVYN — Phase 17.7 Engineering Report
## Backend-First Garment Reconstruction, Intelligent Fitting, Multi-Model Validation & Autonomous Quality Repair Engine

**Date:** 2026-11-27  
**Branch:** `release/stabilize-17.4`  
**Implementation Scope:** **Backend Only** (`git diff -- frontend/` verified empty; existing REST & GLB contracts preserved with additive diagnostics)  
**Overall Acceptance Verdict:** **BACKEND_PIPELINE_AND_TESTS_VERIFIED** *(Real-photo 3D reconstruction, source/fitting repair, independent critic, bounded optimization, headless software visual validation, and 53 pytest tests pass; remote LLM providers `groq`/`gemini`/`openrouter` report `DEGRADED` on invalid/denied API keys and gracefully fall back to `offline_rules`; headless Blender/Open3D/PyRender are not installed so visual validation uses pure CPU NumPy/OpenCV/Pillow software Z-buffered rasterization.)*

---

## 1. Executive Summary

Phase 17.7 remediated severe 3D garment reconstruction and Wear-on-Character fitting distortions strictly on the backend:

- **Eliminated cylindrical torso bloat (`0.346m–0.658m` Z depth -> `0.247m–0.285m`)** by calibrating elliptical collision hulls in [garment_collision_engine.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/fitting/garment_collision_engine.py) (`chest rz=0.118m`), measuring incoming mesh circumferences before scaling in [garment_ease_engine.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/fitting/garment_ease_engine.py), isolating torso pixels below `rel_y < 0.82` in [image_conditioned_reconstruction.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/reconstruction/neural/image_conditioned_reconstruction.py), and removing double `1.25 * s_hip` Z-axis dress flare inflation in [universal_garment_fitting_engine.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/fitting/universal_garment_fitting_engine.py).
- **Eliminated hood/head skull intersections (`103 / 44 / 450` verts -> `0`)** by fixing inverted `phi` hood wrapping (`-0.34*pi..+1.34*pi` across `+Z` face -> symmetric `[-0.64*pi, +0.64*pi]` around `-Z` occiput) in [hoodie_engine.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/reconstruction/hoodie_engine.py) and [component_aware_hoodie_builder.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/reconstruction/component_aware_hoodie_builder.py), adding `neck` and `head` collision capsules, and re-tagging torso collar rings `(0, 64)` from `hood` to `collar`.
- **Fixed swapped bilateral sleeves/legs & unnormalized kurta skinning weights** in [image_conditioned_reconstruction.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/reconstruction/neural/image_conditioned_reconstruction.py) (`+X` = Left arm `[6,7,8]` / leg `[14,15,16]`; `-X` = Right arm `[10,11,12]` / leg `[17,18,19]`, normalized `sum == 1.0`).
- **Eliminated `3.81x` duplicate overlapping GLB triangles (`7,808 -> 2,048`)** via `representation_type="GEOMETRIC_MESH"` filtering + disjoint triangle range tracking in [glb_exporter.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/glb_exporter.py).
- **Fixed `bottoms/jeans -> traditional/kurta` category override** in [garment_hypothesis_resolver.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/intelligence/garment_hypothesis_resolver.py) so `wm_29_jeans_denim.jpg` resolves cleanly to `bottoms/jeans`.
- **Deployed end-to-end YIP backend validation & autonomous repair:** [garment_asset_inspector.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/fitting/garment_asset_inspector.py), [multi_model_reasoning.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/intelligence/multi_model_reasoning.py), [visual_validator.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/visual_validator.py), hardened [evaluation_critic.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/intelligence/evaluation_critic.py) (`GarmentQualityGate`), bounded repair loop in [candidate_optimizer.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/intelligence/candidate_optimizer.py), and pre/post-fit gates in [job_manager.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/job_manager.py).

---

## 2. Root Cause Attribution (Source vs Fitting vs Exporter vs Critic)

| Observed Defect | Source Reconstruction Cause | Fitting / Collision Cause | Exporter / Critic / Perception Gap |
|---|---|---|---|
| Cylindrical bloated torso (`0.346m–0.658m` Z) | `tw_norm` switched to full silhouette `sw_norm` at `rel_y >= 0.42`; `sil_scales` inflated single leg tubes in `bottoms_engine.py` | Circular `CollisionCapsule` chest `r=0.170` (`34.6cm` Z); `dress` applied `1.25 * s_hip` to Z; `GarmentEaseEngine` scaled without measuring mesh | `fit_intelligence` & `evaluation_critic` lacked torso core depth & bloated skirt checks |
| Hood/head intersections (`103` src / `450` disk GLB) | `phi = -0.34*pi + u*1.68*pi` closed front `+Z` across face; torso collar `(0, 64)` tagged `semantic_type="hood"` | `GarmentCollisionEngine` had no `neck` or `head` collision capsules; `shoulder_l`/`r` spheres `r=0.060` spiked outer shoulders up to `1.448m` | No skull penetration metric in `FitIntelligenceEngine` |
| Swapped / twisted limbs | `_build_tops_mesh` & `_build_bottoms_mesh` put `"left"` on `-X` with Right joints `[10,11,12]` / `[17,18,19]` | `abs(x) > 0.18` split wide chest meshes symmetrically without using skinning bone masks | Missing bilateral bone X-polarity check in inspector & critic |
| `3.81x` vertical overlap & stripes | `component_aware_hoodie_builder.py` used `cos(48*theta)` flutes; `_build_tops_mesh` emitted overlapping alias/sub-slice `GarmentComponentNode`s | Fitting mutated positions without recomputing `component_graph` bounding boxes | `glb_exporter` emitted overlapping triangle ranges as stacked meshes |
| `wm_29_jeans_denim.jpg` -> `kurta` | Straight leg photo missed 2D crotch void threshold (`0.22`) | Kurta leg weights `[0.6-0.2s, 0.2, 0.1s, 0.1s]` summed to `0.80` (`7 CRITICAL` skinning failures) | `garment_hypothesis_resolver` penalized `bottoms` `-16.0` & boosted `kurta` `+7.5` even with `"bottoms"/"jeans"` hints |

---

## 3. Verified Live LLM Provider & Local CV Model Matrix

All providers and models were tested with real executions prior to acceptance reporting (no API keys were ever logged):

| Model / Provider | Role | Verified State | Measured Evidence / Limitation |
|---|---|---|---|
| `offline_rules` (`OfflineRulesProvider`) | Deterministic reasoning & fallback | `VERIFIED` | `0.0 ms` in `LLMProviderRegistry`; powers deterministic repair proposals when remote providers fail |
| `groq` (`GroqProvider`) | Remote JSON reasoner | `DEGRADED` | Live HTTP probe returned HTTP `401` (`INVALID_CREDENTIAL`), `1524.4 ms`; circuit breaker opens on failure & falls back cleanly |
| `gemini` (`GeminiProvider`) | Remote JSON reasoner | `DEGRADED` | Live HTTP probe returned HTTP `403` (`PERMISSION_DENIED`), `729.0 ms`; circuit breaker + fallback verified |
| `openrouter` (`OpenRouterProvider`) | Remote JSON reasoner | `DEGRADED` | Live HTTP probe returned HTTP `401` (`INVALID_CREDENTIAL`), `1834.8 ms`; circuit breaker + fallback verified |
| `openai`, `anthropic`, `tavily` | Optional external providers | `BLOCKED_NO_CREDENTIALS` | No API keys configured in environment |
| `human_parsing_segformer_b2` (`mattmdjaga/segformer_b2_clothes`) | Human & garment pixel parsing | `VERIFIED` | HuggingFace cache verified; added `local_files_only=True` first + `threading.Lock()` + `low_cpu_mem_usage=False` fixing concurrent `meta` tensor races |
| `universal-garment-classifier` (`models/checkpoints/garment_classifier_v6.pt`) | Garment category + subcategory | `VERIFIED` | SHA-256 `1cc5d8a9afddb8113ec90258d73e51f8382418f5c7e053ba037286db2a49c3fc`, `4.80 MB`, MPS `305.7 ms` |
| `dinov2_small` (`facebook/dinov2-small`) | 384-d visual feature extractor | `VERIFIED` | Cached local weights (`cached_pretrained_dinov2`) on MPS `280.6 ms` |
| `grounded_sam2` & `depth_anything_v2` adapters | Component / relative depth priors | `DECLARED` (heuristic fallback) | No pinned SAM2 or DepthAnythingV2 weights (`11.2 ms` / `29.6 ms` heuristic fallback) |
| `BackendVisualValidator` (`numpy + cv2 + PIL`) | Multi-view wireframe/normal/clearance | `VERIFIED` | Pure CPU software rasterizer (Headless Blender/Open3D/PyRender are not installed) |

---

## 4. Architecture & Phase 17.7 Backend Changes

1. **LLM Resilience & Multi-Model Reasoning:**
   - [registry.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/llm/registry.py): Added `ProviderState` (`VERIFIED`, `AVAILABLE`, `DEGRADED`, `UNAVAILABLE`, `BLOCKED_NO_CREDENTIALS`), circuit breakers, retries/backoff (skipping retries on `401`/`403`), token/latency accounting, and `generate_with_fallback(..., expect_json=..., schema_cls=...)`.
   - [multi_model_reasoning.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/intelligence/multi_model_reasoning.py): Added `MultiModelReasoningService` (`inspect_garment_semantics`, `propose_geometry_repair_plan`) with control-character sanitization (`sanitize_prompt_field`) and Pydantic schemas (`SemanticInspectionPlan`, `GeometryRepairProposal`).
2. **Perception & Classification:**
   - [human_parsing_segmenter.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/segmentation/human_parsing_segmenter.py): Thread-safe lazy initialization with local cache priority and `low_cpu_mem_usage=False`.
   - [garment_hypothesis_resolver.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/intelligence/garment_hypothesis_resolver.py): Early normalization of `bottoms`/`jeans`/`trousers` hints prevents false `-16.0` crotch-gap veto and prevents `kurta_morphology` from overriding explicit non-kurta categories.
3. **Source Reconstruction & GLB Deduplication:**
   - [hoodie_engine.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/reconstruction/hoodie_engine.py), [component_aware_hoodie_builder.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/reconstruction/component_aware_hoodie_builder.py): Fixed symmetric hood wrap (`phi` in `[-0.64*pi, +0.64*pi]`), calibrated cranial clearance center/radii, removed `cos(48*theta)` vertical flutes.
   - [image_conditioned_reconstruction.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/reconstruction/neural/image_conditioned_reconstruction.py), [bottoms_engine.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/reconstruction/bottoms_engine.py), [glb_exporter.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/glb_exporter.py): Restored bilateral left/right orientation, normalized kurta skin weights, clamped per-leg `sil_scales`, stopped tagging torso collars as `hood`, and deduplicated overlapping primitive triangle intervals.
4. **Inspection, Correspondence, Elliptical Fitting & Autonomous Repair:**
   - [garment_asset_inspector.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/fitting/garment_asset_inspector.py): Added `AvatarGeometryAnalyzer`, `GarmentAssetInspector`, and `GeometryRepairEngine`.
   - [semantic_correspondence.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/intelligence/semantic_correspondence.py): Added `SemanticCorrespondenceEngine` spanning tops, outerwear, bottoms, dresses/skirts, traditional, footwear, headwear, glasses, bags, belts, jewelry, and scarves/gloves with bone-polarity conflict blocking.
   - [universal_garment_fitting_engine.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/fitting/universal_garment_fitting_engine.py): Measures incoming mesh circumferences before ease scaling, applies skin-mask shoulder separation, caps dress Z flare, and fits footwear/headwear/glasses/belts/bags/accessories cleanly.
   - [fit_intelligence.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/intelligence/fit_intelligence.py), [evaluation_critic.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/intelligence/evaluation_critic.py), [candidate_optimizer.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/intelligence/candidate_optimizer.py), [job_manager.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/services/garments/job_manager.py), [intelligence_routes.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/api/intelligence_routes.py): Integrated `AcceptanceVerdict` (`PASS`, `PASS_WITH_WARNINGS`, `DEGRADED`, `FAILED`, `NOT_EVALUATED`), `GarmentQualityGate`, post-fit component bounds recomputation, bounded 3-iteration `repair_geometry_and_refit` with automatic rollback, `/api/intelligence/providers/status`, and `/api/intelligence/fitting/validate-glb`.

---

## 5. Verified Real-Asset Acceptance Metrics

| Asset (`phase_13_6_real_photos` & `wardrobe_assets`) | Category Resolved | Chest Depth Z (m) | Head Pens | Body Pens | Final Gate Verdict | Publication Allowed |
|---|---|---|---|---|---|---|
| `wm_05_hoodie_pullover.jpg` | `tops/hoodie` | `0.2544` (`0.2846` w/ updated shoulder hull) | `0` (was `103`/`44`) | `0` | `PASS` | `true` |
| `wm_21_tshirt_graphic.jpg` | `tops/tshirt` | `0.2513` | `0` | `0` | `PASS` | `true` |
| `wm_00_jacket_denim.jpg` | `outerwear/denim_jacket` | `0.2472` (`0.2676` w/ updated shoulder hull) | `0` | `0` | `PASS` | `true` |
| `wm_29_jeans_denim.jpg` | `bottoms/jeans` (was `traditional/kurta`) | `0.3078` | `0` | `0` | `PASS` | `true` |
| `wm_41_dress_aline.jpg` | `dresses_and_skirts/maxi_dress` | `0.2646` (was `0.658`) | `0` | `0` | `PASS` | `true` |
| `disk_job_447cad742e6f.glb` | `tops` | `0.346m -> repaired` | `450 -> 0` | `1,836 -> 0` | `FAILED` (before, 3 crit / 1 maj) -> **`PASS`** (after, 0 crit / 0 maj) | `true` (after repair) |

---

## 6. Verification & Automated Test Results

Executed post-final edit under `ENVIRONMENT=test`:

```bash
ENVIRONMENT=test ./backend/venv/bin/pytest -q \
  backend/tests/test_phase17_1_validation.py \
  backend/tests/test_phase17_4_hardening.py \
  backend/tests/test_phase17_5_capture_intelligence.py \
  backend/tests/test_phase17_5_universal_fitting.py \
  backend/tests/test_phase17_6_caching_and_performance.py \
  backend/tests/test_phase_17_7_garment_fitting_intelligence.py \
  backend/tests/test_phase17_yip.py \
  backend/tests/test_garment_fitting_phase_5.py
```

- **Result:** `53 passed, 46 warnings in 78.23s` (0 failures, 0 skipped).
- **Compilation & Secret Hygiene:** `./backend/venv/bin/python -m compileall -q backend/app backend/tests/test_phase_17_7_garment_fitting_intelligence.py` exited `0`; secret scan across modified code confirmed zero leaked credentials; `git diff --stat -- frontend/` is empty.

## 7. Remaining Limitations
- Remote LLM providers (`groq`, `gemini`, `openrouter`) are `DEGRADED` until valid active API keys are supplied; pipeline operates deterministically on `offline_rules`.
- Headless GPU photoreal rendering (`Blender`, `Open3D`, `PyRender`) is not installed in this runtime, so backend visual validation uses a pure CPU NumPy/OpenCV/Pillow software Z-buffer rasterizer.
- Fine-grained physical cloth drape fidelity and live Three.js browser re-capture remain outside this backend-only Phase 17.7 execution scope.
