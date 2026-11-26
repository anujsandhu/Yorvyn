# YORVYN Phase 14.27 — Stage 0 Repository Audit

**Audit date:** 2026-11-24 (Asia/Kolkata)  
**Scope:** Read-first repository and implementation audit; no feature code changed.  
**Evidence labels:** OBSERVED = repository/tool output; MEASURED = command/test output; STATIC = source inspection; INFERRED = reasoned from observed code; MOCKED = explicit mock path; BLOCKED = unavailable environment; NOT_VERIFIED = no execution evidence.

## 1. Repository baseline

| Item | Finding |
|---|---|
| Root | **OBSERVED** `/Users/anujsandhu/Projects/yorvyn` (`git rev-parse --show-toplevel`) |
| Branch | **OBSERVED** `main` |
| HEAD | **OBSERVED** `7139fc7eea4e1f890e28da9140db2e8550081267` |
| Latest commit | **OBSERVED** `2026-10-26T16:40:23+05:30`, `feat(auth): add reference login aesthetic, multi-step onboarding wizard, and persistent 3D avatar personalization` |
| Expected baseline comparison | **OBSERVED** expected commit object exists and is an ancestor of HEAD; classification **EXACT_BASELINE** |
| Remote | **OBSERVED** `origin` fetch/push both `https://github.com/anujsandhu/Yorvyn.git`; no credentials present in displayed URL |
| Working tree | **OBSERVED** dirty before audit: 70 tracked files modified, extensive untracked files/directories. Exact pre-audit list was captured in the user-facing tool output; no existing changes were intentionally edited. |
| Diff summary | **MEASURED** 70 tracked paths, 25,069 insertions and 4,998 deletions in the tracked diff. Untracked files are additional and not included in that stat. |
| Requested output names | **OBSERVED** all three requested report paths were absent before creation. |

The repository commit is exactly the expected baseline, while the working directory contains a very large, uncommitted overlay, including the hybrid AI code and Phase 14.26/14.27 reports. Consequently, the Phase 14.26 source is present in the *workspace*, but it is not in the recorded HEAD commit. **INFERRED:** the discrepancy likely arises from uncommitted local work versus the committed/GitHub snapshot. No branch or Git state was changed.

## 2. Phase 14.26 architecture inventory

Evidence files are in the untracked workspace and were examined as source, not accepted as proof based on their report prose.

| Component | Expected | Actual | Evidence | Status |
|---|---|---|---|---|
| AIProvider | Phase 14.26 | Abstract base with capability, availability, health and circuit-breaker methods | `backend/app/services/ai/base.py:130-202` | VERIFIED (interface only) |
| AIOrchestrator | Phase 14.26 | Registers five providers; visual stage then text normalization stage; maps response to canonical contract | `backend/app/services/ai/orchestration/orchestrator.py:47-185` | VERIFIED (source path); runtime BLOCKED |
| CapabilityResolver | Phase 14.26 | Resolves task requirements and filters providers | `backend/app/services/ai/orchestration/capability_resolver.py` | PARTIALLY_VERIFIED; resolver is not called in the inspected orchestrator path (fallback manager performs its own filtering) |
| FallbackManager | Phase 14.26 | Creates eligible chain, checks `is_available`, circuit state, executes sequentially | `backend/app/services/ai/orchestration/fallback_manager.py:30-110` | VERIFIED (static); runtime BLOCKED |
| UsageTracker | Phase 14.26 | In-memory response usage aggregation | `backend/app/services/ai/monitoring/usage_tracker.py:37-100` | VERIFIED (ephemeral process-local state) |
| Gemini provider | Phase 14.26 | HTTP provider with mock branch, credentials and failure/circuit handling | `backend/app/services/ai/providers/gemini_provider.py:81-...` | PARTIALLY_VERIFIED; live API NOT_TESTED; mock is MOCKED |
| Groq provider | Phase 14.26 | Text reasoning provider with mock and binary-image guard | `backend/app/services/ai/providers/groq_provider.py:71-...` | PARTIALLY_VERIFIED; live API NOT_TESTED; mock is MOCKED |
| Hugging Face provider | Phase 14.26 | Embedding provider calls DINOv2 feature extractor; registry lists several model names | `backend/app/services/ai/providers/hf_provider.py:100-...` | PARTIALLY_VERIFIED; declared model operations do not prove downloaded checkpoints |
| Local CV provider | Phase 14.26 | Calls local multimodal engine | `backend/app/services/ai/providers/local_cv_provider.py:36-...` | PARTIALLY_VERIFIED; underlying adapters contain heuristic implementations described below |
| Local Rules provider | Phase 14.26 | Deterministic normalization/rules | `backend/app/services/ai/providers/local_rules_provider.py:30-...` | VERIFIED as rule-based fallback; not ML inference |
| Canonical specification | Phase 14.26 | Pydantic contract; V2 extends it with views, conflicts, readiness and evidence validation | `backend/app/services/ai/contracts.py:69-183` | VERIFIED (schema and validator exist) |
| Reconstruction handoff | Phase 14.26 | Handoff data maps to construction graph template; endpoint builds graph and returns node/seam inventory | `orchestrator.py` and `backend/app/api/garment_identification_routes.py` (`hybrid-orchestrated-reconstruct`) | PARTIALLY_VERIFIED; endpoint returns DAG description, not a persisted/generated reconstruction job |

### Provider and model reality

- **STATIC:** Gemini and Groq have separate mock execution branches. Mock success proves the mock contract path only; no API call was run during this audit. Credentials were not printed or inspected.
- **STATIC:** `backend/app/services/ai/providers/hf_provider.py` identifies DINOv2 as its execution model and calls `dinov2_extractor`; its registry entries for FashionCLIP, SigLIP, SAM2 and Depth Anything are not evidence those checkpoints are loaded by that provider.
- **STATIC:** `Dinov2FeatureExtractor._ensure_model()` attempts `transformers.AutoModel.from_pretrained`, then silently falls back to a newly initialized lightweight random PyTorch backbone if load fails (`backend/app/services/ml/dinov2_feature_extractor.py:45-90`). Its 384-dimensional shape does not establish DINOv2 semantics. Checkpoint/cache availability and real DINOv2 execution: **NOT_VERIFIED**.
- **STATIC:** `FashionCLIPAdapter` and `SigLIPAdapter` implement prompt/query score calculations and imports of torch but inspection did not establish pretrained transformer model loading. **INFERRED:** their present behavior is hand-built/scoring logic, not verified FashionCLIP or SigLIP inference.
- **STATIC:** `GroundedSAM2Adapter.detect_and_segment()` creates an Otsu foreground mask and prompt-named boxes using fixed proportional regions; the returned model string is a label, not loaded Grounding DINO/SAM2 execution (`backend/app/services/garments/intelligence/grounded_sam2_adapter.py`). Classify as **MOCKED/heuristic behavior**, despite being called from the engine.
- **STATIC:** `DepthAnythingV2Adapter.estimate_depth()` combines an analytic torso prior, grayscale blur and high-frequency residual. It does not load Depth Anything V2 weights (`backend/app/services/garments/reconstruction/neural/depth_anything_adapter.py`). Classify as **MOCKED/heuristic behavior**, and not metric depth.
- **OBSERVED:** `models/checkpoints/` contains locally present project classifier/landmark checkpoint files (~48 KB–4.6 MB each), but there is no proof here that the named third-party FashionCLIP/SigLIP/SAM2/Depth checkpoints exist or were loaded. `models/registry.json` lists OpenCV, BiRefNet, MobileNet and a spatial detector; statuses include `ready_for_checkpoint` and declared accuracy values. **NOT_VERIFIED:** those registry accuracy numbers and license claims lack an independent evaluation/license review in this audit.
- **OBSERVED:** `backend/requirements.txt` declares FastAPI/Pydantic/NumPy/scikit-learn/Pillow and `trimesh`; it does not declare `torch`, `transformers`, Gemini/Groq SDKs or model packages. Some clients use raw HTTP; Python runtime environment and optional ML libraries are not represented by this file.
- Declared version ranges are not installed-version evidence. No package was installed and no large model was downloaded.

## 3. Execution paths and integration

### Hybrid one-image path

`POST /api/garments/hybrid-orchestrated-identify` in `backend/app/api/garment_identification_routes.py` reads image bytes and calls `ai_orchestrator.process_garment_image()` → `FallbackManager.execute_with_fallback()` → Gemini Vision (or local CV) → Groq reasoning (or Local Rules) → `CanonicalGarmentSpecification` construction. The same route registration is included in `backend/app/main.py` via the router. This call path is **STATICALLY_VERIFIED**, not runtime verified.

`POST /api/garments/hybrid-orchestrated-reconstruct` accepts that canonical schema and instantiates `UniversalConstructionGraph`, returning its node/seam inventory and handoff fields. It does not call the persistent garment job manager, write artifacts, or demonstrate GLB creation. Thus the report-described continuous path “specification → actual reconstruction artifact” is **PARTIAL**, not verified end-to-end.

### Local identification path

`POST /api/garments/identify` → `multimodal_engine.identify_garment()` → sequential adapter calls for FashionCLIP/SigLIP/DINOv2/Grounded-SAM2/Depth-Anything named stages → `StructuredGarmentSpecification`. The source wiring is present; some named stages are heuristic and do not establish third-party model inference.

### Multi-view path (already present in workspace)

Frontend API helper `frontend/src/services/fashionApi.ts:291-327` posts multipart images to `/api/garments/multiview-identify`; backend validates file count/size/type, infers hints from filenames, then calls `multi_view_fusion_engine.fuse_garment_views()`. It records image SHA-256, classifies view/quality, calls the hybrid orchestrator for usable images, fuses evidence, and returns V2 schema (`backend/app/services/ai/multiview/{view_classifier,fusion_engine}.py`; route in `garment_identification_routes.py`). The result is stored only in module-level `MULTIVIEW_SPECS_STORE`, so evidence/specification retrieval is process-local and is lost on restart or another worker. Deduplication is source-byte SHA-256, not perceptual similarity. Viewpoint classification is heuristic and may prioritize user hints. **PARTIALLY_VERIFIED**; no backend route tests ran.

### Frontend integration status

The API client helper exists. The primary `PhotoTo3DGarmentModal` has separate front/back upload state and hints reconstruction based on whether a back file is present, but the inspected integration does not call `multiviewIdentify`; it uses the established analyze/job API flow. **INFERRED:** multi-view backend is not wired into the primary reconstruction UI. Existing design system is present; evidence review/missing-view guidance for V2 output is not verified in UI.

### Backend persistence and reliability

The broader garment generation system has a job manager, Postgres adapter, Redis stream broker, local thread pool and artifact publisher (`backend/app/services/garments/job_manager.py`; `docker-compose.yml`). That is a separate reconstruction/job execution path, not invoked by the hybrid reconstruct endpoint. Database/Redis failure behavior was not dynamically tested. The AI usage tracker and recent V2 specification store are in-memory. Provider health classes expose status/circuit values, but the inspected local CV and HF providers report always available; their health is not an inference/readiness probe. API auth/tenant behavior for identification endpoints is **NOT_VERIFIED**.

## 4. Phase 14.27 readiness gap matrix

| Requirement | Finding |
|---|---|
| Multi-view association | **PARTIALLY_IMPLEMENTED** — upload batch and shared garment ID exist; grouping is request-local, no durable association. |
| Viewpoint classification | **PARTIALLY_IMPLEMENTED** — heuristic classifier and optional hints; no independent validation. |
| Duplicate detection | **PARTIALLY_IMPLEMENTED** — exact-byte SHA-256 only; re-encoded/perceptual duplicates pass. |
| Evidence provenance | **PARTIALLY_IMPLEMENTED** — V2 source-image properties and validator exist; hybrid V1 synthesis marks some data observed generically and does not preserve fine-grained source-level provenance. |
| Multi-view evidence fusion | **PARTIALLY_IMPLEMENTED** — code exists; execution/tests absent and upstream “model” evidence includes heuristics. |
| Canonical specification V2 | **IMPLEMENTED_BUT_UNVERIFIED** — Pydantic schema and integrity check exist; validation is limited and no tests ran. |
| Component detection | **PARTIALLY_IMPLEMENTED** — component API and adapter exist; SAM2/DINO execution claims are unsupported by actual adapter implementation. |
| Independent accuracy evaluation | **NOT_IMPLEMENTED/NOT_VERIFIED** — scripts and reports exist, but no independent labeled holdout results reproduced. |
| Model registry correctness | **PARTIALLY_IMPLEMENTED** — registry/checksum code and project checkpoints exist; third-party registry identifiers/status are inconsistent with adapter code. |
| Model licensing | **NOT_VERIFIED** — license strings in code/reports are claims; checkpoint-specific primary license evidence absent from this audit. |
| Provider health states | **PARTIALLY_IMPLEMENTED** — status/circuit interfaces exist; local/HF health reports availability without verifying model load or successful inference. |
| Live provider verification | **NOT_TESTED** — no credentials inspected or cloud requests made. |
| Confidence calibration | **IMPLEMENTED_BUT_UNVERIFIED** — calibration utility exists; no measured independent calibration run. |
| Abstention | **PARTIALLY_IMPLEMENTED** — low-evidence/unknown contract pathways exist; operating thresholds not validated. |
| Reconstruction handoff V2 | **PARTIALLY_IMPLEMENTED** — contract/endpoint return DAG metadata; not connected to durable job/GLB generation in this path. |
| Latency tracing | **PARTIALLY_IMPLEMENTED** — elapsed timings and a separate job observability service exist; hybrid AI spans are not demonstrated as distributed traces. |
| Circuit breaker reliability | **IMPLEMENTED_BUT_UNVERIFIED** — base breaker and provider hooks exist; no suite execution due missing dependency, and local/HF bypass meaningful health checks. |
| Database/Redis failure handling | **PARTIALLY_IMPLEMENTED / NOT_TESTED** — job infrastructure includes adapters/fallbacks; no safe integration test or failure injection run. |
| Security/privacy | **PARTIALLY_IMPLEMENTED** — upload constraints and image pixel cap exist; route auth, tenant scoping, durable evidence access, and lifecycle claims are unverified. |
| Frontend integration | **PARTIALLY_IMPLEMENTED** — API helper and existing upload controls; primary reconstruction workflow does not call the multi-view helper based on inspected call sites. |

## 5. Test and check results

| Command | Result |
|---|---|
| `npm test --prefix frontend` | **MEASURED PASS** — exit 0; 25 test files, 355 tests passed (Vitest 4.1.12). Vite emitted config/plugin deprecation warnings. |
| `npm run build --prefix frontend` | **MEASURED PASS** — exit 0; TypeScript (`tsc`) and Vite production bundle completed. Warnings: Node built-ins externalized from `@gltf-transform/core`, dynamic/static Firebase import, large chunks; generated ONNX WASM is ~29.5 MB. |
| `python -m pytest backend/tests/test_hybrid_ai_orchestration.py -q` | **BLOCKED** — `python` executable unavailable. |
| `python3 -m pytest backend/tests/test_hybrid_ai_orchestration.py -q` | **BLOCKED** — exit 2 during collection: `ModuleNotFoundError: No module named 'trimesh'`; pytest also reports unknown `asyncio_mode` option. No tests executed. |
| Python static type check | **NOT_CONFIGURED/NOT_TESTED** — no Python type-check command/config found. |
| Live Gemini/Groq or downloaded-model tests | **NOT_RUN** — would require credentials/network/model availability; excluded from safe baseline. |

No code was changed to make tests pass. No dependencies or models were installed/downloaded. Frontend builds can write ignored `dist/` artifacts; the final Git status should be checked when preparing follow-up work.

## 6. Production readiness assessment

**NOT PRODUCTION READY for Phase 14.27 multi-view reconstruction claims.** The repository contains useful scaffolding and callable endpoints, but backend execution is blocked in this environment; several announced foundation-model adapters are deterministic image heuristics or random-weight fallback code; V2 results are process-local; the hybrid reconstruction endpoint reports DAG assembly rather than submitting the existing persistent job flow; and accuracy, calibration, privacy, tenant isolation, and cloud provider behavior remain unverified. The frontend baseline itself builds and its current tests pass.

## 7. Critical defects to resolve first

1. **STATIC:** Model names/provenance overstate actual execution: Grounded-SAM2 and Depth-Anything adapters are analytical heuristics; DINOv2 can silently become random-weight ViT features; FashionCLIP/SigLIP pretrained loading is not established.
2. **STATIC:** Hybrid orchestration labels category/appearance/components as observed from a provider response but its normalization does not consistently carry source image/property provenance.
3. **STATIC:** Multi-view evidence cache is in-memory and endpoint-local; not suitable for multi-worker persistence/recovery.
4. **STATIC:** Multi-view route/handoff and persistent reconstruction job workflow are separate; no complete request-to-artifact path was established.
5. **BLOCKED:** Backend tests cannot collect because `trimesh` is not installed in the active Python environment.
6. **INFERRED:** Reports and benchmark output should be treated as claims until their source datasets, model weights, commands and results are reproducible.

See `PHASE_14_27_ARCHITECTURE_RECONCILIATION.md` for the evidence table and `PHASE_14_27_IMPLEMENTATION_PLAN.md` for ordered work.
