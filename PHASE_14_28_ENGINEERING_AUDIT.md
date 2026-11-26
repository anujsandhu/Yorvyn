# YORVYN Phase 14.28 — Engineering Continuation Audit

**Audit date:** 2026-11-24 (Asia/Kolkata)  
**Repository:** `/Users/anujsandhu/Projects/yorvyn`  
**HEAD:** `7139fc7eea4e1f890e28da9140db2e8550081267` (`main`, exact expected baseline)  
**Evidence labels:** STATIC = source inspection; OBSERVED = filesystem/Git evidence; MEASURED = command-run result; REPORTED = pre-existing report claim not independently reproduced; NOT_VERIFIED = no acceptable runtime evidence.

## Executive finding

Phase 14.27 is **not fully validated**. The repository contains a substantial local implementation overlay, but the commit remains at the older baseline and source presence is not production evidence. Phase 14.27's own benchmark file reports five passing categories, yet its “accuracy” ground truth and predictions are manually authored arrays, calibration values are calculated on a 20-item hand-authored binary list, and its latency trace labels mock/partial calls as stages of an end-to-end pipeline. The report claims 100% component precision/recall and verified third-party model/license execution; current adapter source contradicts those claims. Treat those metrics and the `PASS` verdict as **REPORTED, NOT independently valid**.

The most consequential Phase 15 prerequisite is to make validation honest and reproducible before optimizing geometry. A credible geometry critic cannot converge safely if its score is synthesized or self-referential.

## A. Repository state and architecture

- **OBSERVED:** current branch `main`; current HEAD exactly matches the expected Phase 14.27 baseline. Latest commit is 2026-10-26.
- **OBSERVED:** working tree is heavily overlaid with modified tracked files and many untracked application, model, test, data, and report files. Phase 14.26/14.27 work lives in this uncommitted workspace overlay; it is not represented by HEAD. No cleanup/reset was performed.
- **OBSERVED:** local backend venv and frontend `node_modules` exist. Their presence does not establish which dependencies were used for the report artifact.
- **Architecture verified statically:** FastAPI identification routes; AI provider/orchestrator/fallback abstractions; canonical V2 specification; multi-view fusion; reconstruction engine registry; category-specific parametric mesh builders; UV/appearance and GLB services; job manager; avatar fitting, collision and cloth simulation systems; frontend Three.js garment viewer and fitting/cloth modules.
- **Not verified:** production service configuration, external provider calls, multi-worker continuity, measured real-image reconstruction quality, independent asset import/export, or full user workflow under current changes.

### Actual end-to-end route

Frontend Photo-to-3D upload → `/api/garments/multiview-identify` → hybrid orchestrator per usable image → V2 evidence record/fusion → user review → `/api/garments/multiview-reconstruct` → job manager.

The V2 specification is serialized into `detection_metadata`. Initial Phase 15 work now validates it in the worker and promotes only source-cited `OBSERVED` component presence into legacy reconstruction intelligence; front-view intelligence is retained across back-view analysis. This is a narrow bridge, not full evidence-driven geometry: boxes, landmarks, dimensions, patterns, texture correspondences, and uncertainty fields are not consumed, and no complete real-image job has been validated (STATIC: `backend/app/services/garments/job_manager.py`, `_process_job`; `backend/app/services/garments/reconstruction/evidence_adapter.py`).

## B. Phase 14.27 verification

| Area | Finding | Status |
|---|---|---|
| Evidence contract | V2 model and checks exist. Current validation covers selected invariants; no direct test file for this exact contract found. | Implemented, unverified |
| View classification | Uses hand-built image heuristics and caller hints; view hints at 0.60 are explicitly not visual verification. No labeled holdout confusion matrix. | Heuristic, unvalidated |
| Duplicate detection | SHA-256 and dHash distance <=2 are implemented. False-positive/false-negative tradeoff has not been evaluated against a duplicate corpus. | Implemented, unvalidated |
| Fusion/correspondence | Evidence records and component/category aggregation exist. Component association is by matching string keys and does not establish geometric cross-view correspondence. | Partial |
| Confidence calibration | Utility computes ECE/Brier, but Phase 14.27 benchmark uses 20 authored probabilities/labels and does not fit/validate a deployable calibrator on held-out model outputs. | Not independently validated |
| Occlusion/missing views | Some rear details become UNKNOWN when no back view exists. Quality assessment hardcodes occlusion false; front/back availability relies on heuristic view assignment. | Partial |
| Model provenance | FashionCLIP/SigLIP adapters use generic CLIP or scoring heuristics; GroundedSAM2 and DepthAnything-named paths are OpenCV/analytic heuristics. DINOv2 fallback is marked nonsemantic in current code. | Claims corrected in code; real checkpoint execution unverified |
| Providers/fallback | Provider and circuit-breaker source exists. No live cloud call; current health is more truthful than Phase 14.27 report. No full failure-injection evidence. | Partial, runtime unverified |
| Persistence | New evidence-spec table is created through runtime DDL in the PostgreSQL adapter; 30-day metadata persistence code exists. It stores no source image bytes. Worker DSN now resolves `YORVYN_PG_DSN` → `DATABASE_URL` → local fallback; no live DB runtime verification. | Code present, configuration aligned, runtime unverified |
| Candidate/reconstruction handoff | Handoff route sends views and evidence metadata to current job manager; geometry worker reanalyzes images and does not consume V2 components/confidence. | Partial; evidence is not geometry-authoritative |
| UI evidence review | UI now displays view/evidence/readiness and lets users correct view labels; direct property-value correction and workflow/browser verification are absent. | Partial |
| Security/retention | Uploads are bounded and tenant checks exist. Multi-view identify only checks MIME prefix before PIL decode; exact magic-byte validation was not established. New DB retention behavior not exercised. | Partial |

### Benchmark/report integrity defects (P0)

1. `scripts/benchmark_phase_14_27_multiview.py` Category D creates `raw_confidences`, `ground_truth_matches`, `gt_components`, and `pred_components` inline. The evaluator therefore measures its own fixture construction, not a model on an independent annotated set. Perfect component metrics are not model accuracy.
2. The same script labels a sequence “cold/warm end-to-end latency” while manually timing unrelated pieces; Gemini is called with `mock_mode=True`, fusion is also called with `mock_mode=True`, and the stages are not a single request trace. It is not a valid full-pipeline trace.
3. `backend/app/services/garments/evaluation/ground_truth_evaluator.py` fabricates Chamfer/F-score distances from a sine function over predicted vertices, synthesizes silhouette IoU from Chamfer, derives SSIM from color error, and returns a hardcoded 0.92 fabric accuracy. `real_world_benchmark.py` synthesizes its images. These are unsuitable as real-world ground-truth metrics.
4. `backend/app/services/ai/evaluation/component_evaluator.py` zips target and prediction arrays without rejecting length mismatch, allowing silent sample loss.
5. Phase 14.27 report claims a license audit and MPS execution for model names whose current adapters explicitly say the checkpoints are absent/not used or heuristics. The current safer code and older report/evidence JSON disagree; the report must be superseded, not used as acceptance evidence.

### Phase 15 Stage 0 remediation (2026-11-24)

The evaluator defects above were addressed after the audit: component evaluation rejects unequal sample counts and returns not-evaluated for empty data. Ground-truth evaluation no longer invents geometry, appearance, pattern, scale, or fabric accuracy metrics. It requires explicit reference vertices, matching masks, or reference labels. Generated fixture suites and the Phase 8 helper are labeled synthetic smoke evidence. The PostgreSQL DSN resolver now honors `YORVYN_PG_DSN`, then container-provided `DATABASE_URL`, then the existing local fallback. The Phase 14.27 benchmark script still contains authored Category D examples and a partial/mock latency trace and remains unsuitable as accuracy evidence until separately corrected.

### Existing test evidence

The Stage 0 audit recorded a pre-implementation frontend baseline of 355 passing tests/build and backend collection blocked by missing `trimesh`. This is historical and does not verify current edits. Phase 14.27 master benchmark JSON is a generated report artifact, not an independent test suite. No Phase 14.27 contract/persistence regression test files were found by focused search.

## C. Cross-system gap ranking

| Priority | Gap | Impact / evidence | Dependency / cost |
|---|---|---|---|
| P0 | Evaluation fabricates or overstates quality | Critical: false convergence/production claims possible; static source proof above. | Replace with explicit reference inputs and honest unavailable states; medium |
| P0 | V2 evidence is not consumed by reconstruction geometry | Critical: view provenance/readiness does not control mesh details. | Define backward-compatible evidence-aware reconstruction input; medium-high |
| P0 | DB DSN/schema startup mismatch risk | High: persistence may connect to wrong DB or fail at app import; static mismatch between `YORVYN_PG_DSN` default and compose `DATABASE_URL`. | Configuration and disposable DB tests; low-medium |
| P1 | Reconstruction is mostly parametric/procedural | High: builders create category-specific ring/tube meshes and deterministic parts; not image-optimized full surfaces/patterns. | Better silhouette constraints and multiview geometry; high |
| P1 | Body measurement fallbacks and preset profiles | High for fit: defaults/fallback circumference values are used; validate measurement provenance and per-avatar calibration. | Measurement confidence/scale inputs; medium |
| P1 | Cloth parameters are preset heuristics | High for physical claims: parameter values are hardcoded, physics uses simplified PBD and approximate constraints, not calibrated textile data. | Physical reference tests and measured material samples; high |
| P1 | Mesh quality acceptance is incomplete | High: topology services exist but fallback paths fabricate nominal mesh statistics when trimesh missing; garment-specific openings vs watertightness need policy. | Real GLB fixture tests; medium |
| P2 | Texture/UV and rear-surface completion | Medium-high: projection and synthetic fill exist; occlusion/multiview texture continuity not benchmarked. | Evidence-to-surface UV correspondence; high |
| P2 | Scale/latency/resource observability | Medium: process telemetry exists; no reproducible deployment/device profile across model cold/warm and concurrency. | Instrument real boundaries; medium |
| P2 | Asset versioning and rollback | Medium: current job/artifact pipeline exists but not a per-iteration candidate lineage with best-known rollback. | Candidate metadata and storage lifecycle; medium |

## D. Technology evaluation

| Technique | Limitation addressed | Recommendation now | Cost / validation |
|---|---|---|---|
| Parametric/pattern construction + multiview silhouette constraints | Current mesh is procedural and does not consume V2 evidence. | **First choice**: preserve current category builders; add evidence-grounded landmark/silhouette constraints and confidence gates before introducing a new neural stack. | Low recurring inference cost; medium integration. Measure held-out silhouette IoU, landmark error, topology, and view reprojection by garment identity. |
| Vision Transformer / DINO features | Weak semantic correspondence and identity verification. | Defer model selection until a pinned checkpoint, license evidence, cache status and annotated holdout are available. Generic CLIP or random fallback is not a substitute. | MPS memory/cold start. Compare against simple color/shape baseline and calibrated retrieval on held-out identities. |
| Garment pattern-space diffusion | Single-view ambiguity and plausible unseen garment panels. | Research candidate, not production dependency. The 2025 paper “Single View Garment Reconstruction Using Diffusion Mapping Via Pattern Coordinates” links diffusion priors with implicit sewing patterns; applicability requires code/checkpoint/license/runtime audit. [Paper](https://arxiv.org/abs/2504.08353) | High training/inference/integration cost. Compare surface distance, silhouette, pattern topology and uncertainty against parametric baseline on licensed 3D ground truth. |
| Dress-1-to-3 / differentiable cloth simulation | Simulation-ready separated garments from single image. | Research candidate for a later stage; only after geometry metric and pattern representation are reliable. [Paper](https://arxiv.org/abs/2502.03449) | High GPU/training and pipeline complexity. Evaluate sewing topology, geometry fit and dynamic stability on registered reference scans. |
| Gaussian Splatting | Photorealistic view synthesis. | Do not use as garment mesh replacement: appearance representation does not itself provide editable sewing topology or cloth constraints. Could be a preview critic/reference only. | GPU/storage heavy; assess novel-view image metrics separately from mesh topology. |
| XPBD / existing PBD | Stable interactive drape and collision. | Keep current lightweight PBD for preview; calibrate against measured drape/swatches before claiming fabric physics. | Moderate; use standardized gravity/drape and collision fixtures, measure settling time, strain and penetration. |

## E. Phase 14.28 execution plan

1. **P0 evidence and benchmark integrity:** label/split synthetic smoke fixtures from real annotated evaluation; fix silent evaluator truncation; remove fabricated metric outputs or require actual ground truth; produce reproducible manifests with hashes and split grouping by garment identity/session.
2. **P0 evidence-to-geometry contract:** pass canonical V2 view/component evidence into worker, preserve UNKNOWN/INFERRED statuses, and have the reconstruction engine explicitly consume supported observations; avoid changing V1 callers.
3. **P0 persistence/config:** unify persistence DSN selection (`YORVYN_PG_DSN`/`DATABASE_URL`), add non-destructive schema migration for evidence metadata, expire rows safely, and verify owner isolation with a disposable DB.
4. **P1 segmentation and view evaluation:** build a consent/license-cleared annotated mini-set; report per-view confusion, coverage-risk and duplicate thresholds; add occlusion and image-quality annotations.
5. **P1 mesh/critic baseline:** actual mesh validation plus rendered silhouette comparison against original masks from front/back/side; critical topology defects gate candidate acceptance.
6. **P1 iterative candidates:** candidate lineage, bounded iterations, deterministic configuration, independent scorer, rollback to best valid candidate, explicit stop reasons. Implement only after critic metrics pass.
7. **P2 textures/material/physics:** use source-to-surface UV correspondence and measured fabric swatches/drape; report confidence and missing data.
8. **P2 UI/export:** candidate history, defect list, evidence-linked uncertainty, preview/high-quality export; independently reopen exported GLB in Three.js and a second parser.

**Acceptance gate:** No accuracy or convergence claim until the model is evaluated on non-synthetic, identity-separated, independently labeled holdout inputs; every metric records source IDs, code/checkpoint hashes, command and environment. Critical mesh defects block acceptance independent of any aggregate score.
