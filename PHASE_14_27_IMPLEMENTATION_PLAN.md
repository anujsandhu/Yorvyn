# Phase 14.27 Implementation Plan

**Stage 0 disposition:** Audit complete. The user authorized the next implementation stage on 2026-11-24. The plan below remains ordered by dependencies and risk. Every code path is subject to re-reading the current workspace before editing because the repository has extensive pre-existing modifications.

## P0 — Correctness and architecture integrity

### 0.1 Truthful model and provider provenance

- **Priority:** P0
- **Current implementation:** Provider health is mostly declarative; local/HF providers can report available without successfully loading/inferencing. Grounded-SAM2 and Depth-Anything adapters are heuristic; DINOv2 fallback uses random initialized weights. See reconciliation report.
- **Required modification:** Make each adapter report actual backend/model/checkpoint and execution path; remove misleading upstream model names when fallback runs; fail closed or use explicitly named heuristic backend; distinguish startup/configured/loaded/healthy states.
- **Likely files:** `backend/app/services/garments/intelligence/{fashion_clip_adapter.py,siglip_adapter.py,grounded_sam2_adapter.py,local_multimodal_identification_engine.py}`, `backend/app/services/garments/reconstruction/neural/depth_anything_adapter.py`, `backend/app/services/ml/dinov2_feature_extractor.py`, `backend/app/services/ai/{base.py,providers/*.py}`, `backend/app/services/ai/evaluation/model_registry_audit.py`, `models/registry.json`.
- **Dependencies:** P0.2 contract invariants; explicit checkpoint/license facts and approved zero-cost approach.
- **Risks:** Breaking consumers that assume existing provider names or output shapes; accidentally downloading model assets; claims remain invalid without real checkpoint and license evidence.
- **Test strategy:** Unit tests for each reported health state; fake/missing checkpoint test; prove heuristic path labels; controlled local inference only when weights already exist; no network download in tests.
- **Acceptance:** A provider cannot say “operational model X” unless X is loaded and its inference succeeds; fallback output declares heuristic provenance; model registry reflects actual checkpoint, hash, license evidence, device and status.

### 0.2 Canonical evidence contract and validation

- **Priority:** P0
- **Current implementation:** V2 schemas and integrity validator exist; evidence source links are incomplete on V1→V2 and inferred provenance is not fully checked.
- **Required modification:** Define property-level evidence invariants, image ID/hash references, conflict semantics, unknown/abstention confidence rules, schema versioning and backward compatibility; validate all provider output before persistence or reconstruction.
- **Likely files:** `backend/app/services/ai/contracts.py`, `backend/app/services/ai/orchestration/orchestrator.py`, `backend/app/services/ai/multiview/fusion_engine.py`, `backend/app/api/garment_identification_routes.py`.
- **Dependencies:** None beyond current schema inventory; coordinate with 0.1 provenance fields.
- **Risks:** Existing V1 clients and mock contracts; silent defaulting currently creates observed claims.
- **Test strategy:** Contract tests for observed/inferred/unknown/conflicted cases, invalid source IDs, malformed confidence, backward-compatible serialization.
- **Acceptance:** Invalid evidence is rejected or explicitly downgraded; every property traces to image/provider or named inference rule; hidden properties are not fabricated.

## P1 — Core garment intelligence and reconstruction handoff

### 1.1 Durable multi-view association and duplicate handling

- **Priority:** P1
- **Current implementation:** `/api/garments/multiview-identify`, hint parsing, request-scoped fusion, exact SHA-256 duplicate detection; global dictionary storage.
- **Required modification:** Define garment/session identity and tenant ownership; persist uploads’ safe metadata, hashes, view assignment and specification; use exact plus perceptual duplicate detection with transparent thresholds; implement lifecycle/retention behavior.
- **Likely files:** `backend/app/api/garment_identification_routes.py`, `backend/app/services/ai/multiview/{view_classifier.py,fusion_engine.py}`, `backend/app/models/garment_intelligence_models.py`, new migration only after reviewed (no destructive migration), repository layer, `frontend/src/services/fashionApi.ts`.
- **Dependencies:** P0 evidence contract; persistence and auth design.
- **Risks:** Private image retention, tenant leakage, duplicate false positives, migrations.
- **Test strategy:** Isolated database tests using disposable local test DB; same bytes/re-encoded/near-duplicate fixtures; tenant isolation and retention tests.
- **Acceptance:** Same garment can be resumed across requests/workers; evidence is tenant-scoped and retrievable; duplicate decisions preserve original source refs.

### 1.2 View classification and quality abstention

- **Priority:** P1
- **Current implementation:** Hand-built edge/symmetry/contrast rules plus user/file hints.
- **Required modification:** Establish a documented, deterministic baseline classifier with calibrated confidence and abstention; keep user hint as untrusted metadata or reviewed override; track viewpoint evidence and uncertain states.
- **Likely files:** `backend/app/services/ai/multiview/view_classifier.py`, `backend/app/services/ai/contracts.py`, API route, test fixtures.
- **Dependencies:** P2 labeled dataset plan; P0 confidence/evidence semantics.
- **Risks:** Dataset bias across garment categories, photography styles, orientation and lighting.
- **Test strategy:** Labeled holdout by garment identity and capture session; per-view confusion matrix, coverage vs accuracy, calibration and abstention metrics.
- **Acceptance:** Per-class metrics published; uncertain/unsupported images abstain; hints cannot silently convert unsupported image into verified view.

### 1.3 Evidence fusion and V2 reconstruction handoff

- **Priority:** P1
- **Current implementation:** Fusion engine and V2 handoff contracts exist, but backend test/runtime evidence is absent and hybrid reconstruct endpoint returns graph metadata only.
- **Required modification:** Fuse only validated property-level evidence; persist conflicts and uncertainty; create a versioned handoff that explicitly maps confidence/provenance to reconstruction inputs; submit the validated spec to the existing job manager and return a durable job ID/artifact state.
- **Likely files:** `backend/app/services/ai/multiview/fusion_engine.py`, `backend/app/services/ai/contracts.py`, `backend/app/api/garment_identification_routes.py`, `backend/app/services/garments/job_manager.py`, `backend/app/services/garments/reconstruction/universal_construction_graph.py`, frontend API/service.
- **Dependencies:** 1.1, 1.2, P0.2.
- **Risks:** Existing job API expects a different input shape; inferred geometry can be mistaken for observed; avoid blocking API thread with reconstruction.
- **Test strategy:** Contract-to-job integration test using local fake provider and disposable storage; verify provenance survives to artifact/job diagnostics.
- **Acceptance:** One supported UI operation takes user images through identification, validation, persisted job, reconstruction and recoverable artifact; failure states remain inspectable.

## P2 — Independent validation

### 2.1 Dataset, component metrics, calibration and abstention

- **Priority:** P2
- **Current implementation:** Evaluation/calibration utilities and many scripts exist, but their numbers are not independently reproduced; no trustworthy labeled holdout established by this audit.
- **Required modification:** Define license-cleared, versioned train/dev/holdout data separated by garment identity and capture session; report classification, component detection, segmentation, view classification, Brier/ECE, coverage-risk and abstention metrics; compare with simple baselines.
- **Likely files:** `backend/app/services/ai/evaluation/{calibration.py,component_evaluator.py,model_registry_audit.py}`, selected `scripts/evaluate_*`, new dataset manifest/docs and benchmark report.
- **Dependencies:** P0 truthful model provenance; P1 classifier/evidence interfaces.
- **Risks:** Data leakage, unlicensed images, test-set tuning, unsupported accuracy claims.
- **Test strategy:** Reproducible offline benchmark with pinned dataset manifest, seeds, model/checkpoint hashes and exact command; bootstrap confidence intervals; independent review of split.
- **Acceptance:** Results reproducible on a clean environment with no hidden API/model fetch; every reported metric maps to test IDs and implementation version.

## P3 — Reliability and operational behavior

### 3.1 Failure semantics, circuit breakers, concurrency and recovery

- **Priority:** P3
- **Current implementation:** Basic breaker methods; mixed async route/synchronous inference; local thread pool plus optional Redis/Postgres persistence; health endpoints can be declarative.
- **Required modification:** Validate breaker transitions, timeouts, retry/idempotency, cancellation, worker ownership and recovery; isolate inference concurrency according to actual device/memory; add provider/job failure status and latency spans.
- **Likely files:** `backend/app/services/ai/base.py`, `fallback_manager.py`, providers, `backend/app/services/garments/{job_manager.py,orchestration/*}`, API routes, Docker compose and tests.
- **Dependencies:** P0.1 truthful health; P1 durable handoff.
- **Risks:** Deadlocks, duplicate work, local MPS memory pressure, Redis/Postgres partial outage, retry storms.
- **Test strategy:** Fault injection in disposable local services; deterministic fake providers; concurrent/cancel/restart tests; no production credentials or data.
- **Acceptance:** Accurate live health, bounded retries, safe recovery without duplicate artifact publication, measured end-to-end latency spans and documented degradation.

### 3.2 Security and privacy review

- **Priority:** P3, before any production rollout
- **Current implementation:** Upload MIME/size/pixel checks; broader auth and tenant machinery exists but route enforcement and multi-view storage ownership are unverified.
- **Required modification:** Enforce authentication/authorization and tenant scope on all identify/evidence/specification/reconstruction routes; rate/size limits; safe upload storage; retention/deletion; avoid exposing raw exception internals.
- **Likely files:** `backend/app/api/garment_identification_routes.py`, `backend/app/core/security.py`, persistence repository, frontend session handling, security tests.
- **Dependencies:** 1.1 persistence design.
- **Risks:** PII/image exposure and cross-tenant access.
- **Test strategy:** Negative auth/tenant tests and file validation tests in isolated environment.
- **Acceptance:** No unauthenticated/cross-tenant evidence access; documented image retention and deletion behavior; adversarial MIME/decompression tests pass.

## P4 — User experience

### 4.1 Multi-view upload, evidence review, missing-view guidance

- **Priority:** P4
- **Current implementation:** Existing front/back inputs and multi-view API helper, but no confirmed primary-workflow call into that helper; some messaging indicates inferred rear geometry.
- **Required modification:** Connect supported upload flow to multi-view endpoint and durable job; display detected view, provenance, conflicts, uncertainty, missing-view recommendations and user correction affordances; avoid implying full 360° evidence unless measured.
- **Likely files:** `frontend/src/components/PhotoTo3DGarmentModal.tsx`, related CSS, `frontend/src/services/fashionApi.ts`, typed V2 response models.
- **Dependencies:** P0 evidence contract; P1 end-to-end handoff; P3 authorization/recovery semantics.
- **Risks:** Overstating confidence, accessibility and mobile upload friction.
- **Test strategy:** Component tests for 1/2/many images, duplicate/unknown views, conflicts, abstention and job failures; browser flow against local backend.
- **Acceptance:** User can submit multiple views, inspect actual evidence and missing views, correct associations, and continue only when readiness state allows.

## Recommended sequence

1. Establish truthful model/provider provenance and canonical evidence invariants (P0).
2. Implement durable tenant-scoped multi-view association and exact/perceptual duplicate policy (P1.1).
3. Validate view classification and quality/abstention on a held-out dataset (P1.2 + P2 data foundation).
4. Implement evidence fusion and connect V2 handoff to persistent reconstruction jobs (P1.3).
5. Run independent model/component/calibration evaluation and publish reproducible results (P2).
6. Harden health, breaker, concurrency, recovery, latency, database/Redis failure and privacy behavior (P3).
7. Integrate evidence review and missing-view guidance in the frontend (P4).

## Next-stage likely change set

Initial implementation should be narrowly scoped to these files, with additions only when tests or the chosen contract require them:

- `backend/app/services/ai/contracts.py`
- `backend/app/services/ai/orchestration/orchestrator.py`
- `backend/app/services/ai/multiview/view_classifier.py`
- `backend/app/services/ai/multiview/fusion_engine.py`
- `backend/app/services/ai/base.py`
- `backend/app/services/ai/providers/{local_cv_provider.py,hf_provider.py,gemini_provider.py,groq_provider.py}`
- `backend/app/services/garments/intelligence/{fashion_clip_adapter.py,siglip_adapter.py,grounded_sam2_adapter.py,local_multimodal_identification_engine.py}`
- `backend/app/services/ml/dinov2_feature_extractor.py`
- `backend/app/services/garments/reconstruction/neural/depth_anything_adapter.py`
- `backend/app/api/garment_identification_routes.py`
- `backend/app/services/garments/job_manager.py` and relevant persistence adapter/migration only for durable handoff
- `backend/tests/` targeted provider, contract, multi-view and recovery tests
- `frontend/src/services/fashionApi.ts`
- `frontend/src/components/PhotoTo3DGarmentModal.tsx` and its styles/tests
- `models/registry.json` and model/license manifests

This was the expected initial scope at the end of Stage 0. Stage 0 itself made no feature-code changes; the subsequent implementation work is recorded below. Continue to recheck `git status` and preserve all pre-existing changes before each edit.

## Implementation progress — 2026-11-24

The following focused changes are now in the workspace:

- **P0.1 — PARTIALLY IMPLEMENTED:** model metadata no longer defaults to a verified commercial license; generic OpenAI CLIP is labeled as generic CLIP rather than FashionCLIP/SigLIP; model adapters now load cached weights only and do not initiate downloads; Grounded-SAM2 and Depth-Anything heuristic outputs are labeled as heuristics; DINOv2's untrained fallback is marked non-semantic and is not returned as a successful Hugging Face embedding. Per-stage checkpoint/load/backend/calibration status now flows into the canonical specification. The Phase 14.27 model audit catalog no longer reports unverified checkpoints, measured accuracy, or licenses as validated. Local/cloud provider health distinguishes unavailable/configured from live-verified.
- **P0.2 — IMPLEMENTED IN CONTRACT LAYER, NOT YET RUNTIME-VERIFIED:** V2 evidence validation checks unique image IDs, duplicate hashes among usable records, valid/usable source-image references, observed citations, inferred justifications, unknown confidence, conflict records, and normalized component boxes. Local category predictions are marked inferred; fusion preserves inferred status and justification.
- **P1.1 — IMPLEMENTED IN CODE, NOT RUNTIME-VERIFIED:** exact-byte and conservative dHash near-duplicate detection record duplicate provenance; caller-supplied view hints are recorded separately from heuristic classification; V2 specification metadata is stored in the existing PostgreSQL persistence adapter, owner-scoped on reads/writes, and expires after 30 days. Source image bytes are not stored in this evidence table. A bounded process cache remains for hot reads.
- **P1.3 — PARTIALLY IMPLEMENTED:** `POST /api/garments/multiview-reconstruct` validates the V2 contract, verifies that re-uploaded source bytes match the evidence hashes, resolves the effective user, reserves the existing reconstruction entitlement, and submits the views and V2 metadata to the current job manager. The Photo-to-3D flow now calls multi-view identification and this handoff. The job manager's canonical-spec persistence across process restarts and whether reconstruction geometry consumes all V2 component evidence remain unverified.
- **P4 — PARTIALLY IMPLEMENTED:** the Photo-to-3D flow now pauses after identification and displays assigned views, assignment confidence, usability/duplicate status, readiness, missing evidence, recommended views, conflicts, and property evidence status. Users can correct view labels and rerun classification before reconstruction; insufficient or conflicted readiness blocks continuation. This remains a compact review step and does not yet provide direct correction of garment property values.
- **NOT DONE:** independently evaluated view classification/fusion, a labeled validation dataset, confidence calibration, broader failure injection, runtime verification of durable multi-view evidence lookup across restarts, and full end-to-end recovery/privacy validation.
- **Verification:** no post-edit tests or builds have been run. The pre-edit Stage 0 baseline remains recorded above; backend test collection was blocked by missing `trimesh`.

The Stage 0 audit reports remain historical snapshots of the repository before implementation. No dependencies were changed, no models were downloaded, and no commits or deployments were made.
