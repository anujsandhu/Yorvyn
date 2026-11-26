# Phase 14.27 Architecture Reconciliation

**Audit date:** 2026-11-24  
**Evidence labels:** OBSERVED, MEASURED, INFERRED, MOCKED, STATIC, BLOCKED, NOT_VERIFIED.

## Repository truth

**OBSERVED:** root `/Users/anujsandhu/Projects/yorvyn`; branch `main`; HEAD `7139fc7eea4e1f890e28da9140db2e8550081267`; latest commit date `2026-10-26T16:40:23+05:30`. This equals the requested expected baseline (**EXACT_BASELINE**). `origin` is `https://github.com/anujsandhu/Yorvyn.git` for fetch and push. The working tree was dirty before audit, with 70 modified tracked files and numerous untracked files. The Phase 14.26 implementation files and reports are untracked/modified workspace content, not part of HEAD.

## Phase 14.26 component evidence

| Component | Expected | Actual | Evidence | Status |
|---|---|---|---|---|
| AIProvider | Phase14.26 | Abstract provider interface, health/circuit hooks | `backend/app/services/ai/base.py:130-202` | VERIFIED (interface) |
| AIOrchestrator | Phase14.26 | Registers Gemini, Groq, LocalCV, HF, LocalRules; two-stage request | `backend/app/services/ai/orchestration/orchestrator.py:47-185` | PARTIALLY_VERIFIED (static path; runtime blocked) |
| CapabilityResolver | Phase14.26 | Task requirement/provider filtering utility | `backend/app/services/ai/orchestration/capability_resolver.py` | PARTIALLY_VERIFIED (not called by inspected top-level orchestrator) |
| FallbackManager | Phase14.26 | Selects providers and sequentially falls back | `backend/app/services/ai/orchestration/fallback_manager.py:30-110` | VERIFIED (static) |
| UsageTracker | Phase14.26 | In-memory counters/cost summary | `backend/app/services/ai/monitoring/usage_tracker.py:37-100` | VERIFIED (process-local) |
| Gemini provider | Phase14.26 | HTTP implementation plus explicit mock branch | `backend/app/services/ai/providers/gemini_provider.py:81+` | PARTIALLY_VERIFIED; live NOT_TESTED |
| Groq provider | Phase14.26 | HTTP implementation, text capability guard, mock branch | `backend/app/services/ai/providers/groq_provider.py:71+` | PARTIALLY_VERIFIED; live NOT_TESTED |
| HF provider | Phase14.26 | Calls DINOv2 extractor; advertises broader model registry | `backend/app/services/ai/providers/hf_provider.py:100+` | PARTIALLY_VERIFIED |
| Local CV | Phase14.26 | Calls local multi-adapter engine | `backend/app/services/ai/providers/local_cv_provider.py:36+` | PARTIALLY_VERIFIED |
| Local Rules | Phase14.26 | Deterministic structured normalization | `backend/app/services/ai/providers/local_rules_provider.py:30+` | VERIFIED as rules path |
| Canonical specification | Phase14.26 | V1 contract plus V2 extension and validator | `backend/app/services/ai/contracts.py:69-183` | VERIFIED (schema) |
| Reconstruction handoff | Phase14.26 | Returns UniversalConstructionGraph metadata | `backend/app/api/garment_identification_routes.py`, hybrid reconstruct route | PARTIALLY_VERIFIED (no generated/persisted artifact) |

## End-to-end call graph

```text
Frontend PhotoTo3DGarmentModal
  └─ analyze / garment-gen job APIs (existing path)
       └─ garment routes → garment_job_manager → Postgres/Redis/local workers → artifact publisher

Frontend fashionApi.multiviewIdentify helper (present, primary UI caller not found)
  └─ POST /api/garments/multiview-identify
       └─ validation + filename/user view hints
            └─ MultiViewGarmentFusionEngine
                 ├─ ViewClassifier (image heuristics + exact SHA-256 dedup)
                 ├─ AIOrchestrator per usable view
                 │    └─ FallbackManager → Gemini Vision OR LocalCV
                 │         └─ Groq reasoning OR LocalRules
                 ├─ V2 specification/evidence validation
                 └─ process-local MULTIVIEW_SPECS_STORE

POST /api/garments/hybrid-orchestrated-reconstruct
  └─ V1 canonical specification → UniversalConstructionGraph → DAG inventory JSON
       └─ no observed call to garment_job_manager or artifact generation
```

**STATIC:** `backend/app/main.py` imports/includes the garment identification router. **NOT_VERIFIED:** no backend route/test execution succeeded. The separate `garment-gen` workflow has Postgres/Redis/job/artifact code but is not joined to the hybrid reconstruction endpoint in the observed path. No complete `Frontend → API → Orchestrator → provider → durable canonical record → generated GLB` path is verified.

## Provider/model execution distinctions

| Name in reports/registry | Source implementation finding | State |
|---|---|---|
| Gemini | HTTP client code and mock mode exist; no live request made | Live NOT_TESTED; mock MOCKED |
| Groq | HTTP client code and mock mode exist; text-only guard exists | Live NOT_TESTED; mock MOCKED |
| FashionCLIP | Adapter uses prompt-bank scoring, pretrained FashionCLIP checkpoint loading not established | NOT_VERIFIED as FashionCLIP; heuristic path present |
| SigLIP | Query-bank scoring logic; pretrained SigLIP loading not established | NOT_VERIFIED as SigLIP; heuristic path present |
| DINOv2 | Attempts Hugging Face model load; if it fails, constructs a random-weight lightweight ViT with matching dimension | Conditional; fallback is not DINOv2 |
| Grounded-SAM2 | Otsu thresholding and fixed prompt-to-proportional-box mapping, no Grounding DINO/SAM weights loaded | Heuristic/MOCKED |
| Depth Anything V2 | Analytic body shape prior + grayscale/high-frequency components, no model weights loaded | Heuristic/MOCKED |
| Local Rules | Deterministic rules | Real rule-based behavior, not ML |
| Project checkpoints | Several local `.pt` files are present under `models/checkpoints` | Presence OBSERVED; loaded execution NOT_VERIFIED |

`backend/requirements.txt` does not declare torch/transformers and the runtime test failed at missing `trimesh`. `models/registry.json` contains model status and accuracy metadata, but this audit did not independently verify those measurements, licenses, third-party checkpoints, or runtime loading. Generic CLIP weights are not counted as FashionCLIP.

## Existing multi-view functionality and limitations

- **STATIC:** endpoint supports up to ten images and per-image/total byte limits, validates image MIME/decoding, computes SHA-256 identities, optionally uses caller/file-name view hints, classifies viewpoint and quality, fuses evidence, returns `CanonicalGarmentSpecificationV2`, exposes evidence/spec validation endpoints.
- **STATIC:** `CanonicalGarmentSpecificationV2.validate_evidence_integrity()` checks observed source IDs, unknown confidence, and conflicted record presence, but does not check every declared inferred provenance requirement described in its docstring.
- **STATIC:** duplicate check is exact byte hash; view type heuristics depend on geometry/texture and may rely on hints.
- **STATIC:** multi-view result storage is a global Python dictionary; no DB/recovery/tenant isolation demonstrated.
- **INFERRED:** frontend multi-view API helper is not integrated into the primary PhotoTo3D reconstruction path, which has independent front/back upload state and currently uses the existing garment analysis/job calls.

## Test evidence

- **MEASURED PASS:** `npm test --prefix frontend`: 25 files, 355 tests passed, exit 0.
- **MEASURED PASS:** `npm run build --prefix frontend`: `tsc` plus Vite build exit 0. Warnings include Node built-ins externalized, dynamic/static module import, large chunks and ~29.5 MB ONNX WASM.
- **BLOCKED:** `python -m pytest backend/tests/test_hybrid_ai_orchestration.py -q`: no `python` executable.
- **BLOCKED:** `python3 -m pytest backend/tests/test_hybrid_ai_orchestration.py -q`: collection aborts because `trimesh` is missing; no test cases executed. Pytest reports `asyncio_mode` unknown in active environment.
- Cloud calls/model download/inference **NOT_TESTED**. No install/download was performed.

## Reconciliation conclusion

**OBSERVED:** Phase 14.26 and substantial Phase 14.27 scaffold code exist in the uncommitted local workspace. **INFERRED:** the baseline GitHub snapshot discrepancy is explained by these local changes not being committed. **STATIC:** hybrid orchestration is genuinely wired from an API route through provider fallback and canonical schema creation. **NOT_VERIFIED:** production integration and end-to-end reconstruction. Some providers are only scaffolding or heuristics under foundation-model names; therefore the claimed hybrid foundation-model architecture is **partially integrated, not verified as described**.

Detailed findings and priority order: `PHASE_14_27_STAGE_0_REPOSITORY_AUDIT.md` and `PHASE_14_27_IMPLEMENTATION_PLAN.md`.
