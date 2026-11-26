# Phase 15.5 AI infrastructure certification

**Decision on November 25, 2026.** Local software stabilization passed in the existing macOS arm64 workspace. The two Phase 15.4 hybrid failures are resolved. External AI inference remains blocked. The final credentialed command exited 2 before starting a live browser conversation. Hosted deployment and classifier accuracy on a holdout set have no acceptance result from this phase.

The base Git revision was `7139fc7eea4e1f890e28da9140db2e8550081267`. This run included existing working-tree changes and local model files. Checking out that revision alone does not reproduce the tested workspace. The accompanying test history records the runtime, changed-source hashes, provider observations and recovery receipts.

## Checkpoint investigation

| Artifact | SHA-256 | Evidence and decision |
| --- | --- | --- |
| Original Phase 13 server classifier | `44eacae47d318ef7c5508be776d295d71c095e9514e2a8ab5c01946e994c04b8` | Pinned for the historical release. Original 5,012,016-byte artifact unavailable in the files and local Git objects examined. Historical verification rejects the current file. |
| Current `specialized_garment_heads_v3.pt` | `08225bd499b33a26920e7c241157fccabc4922addb021884b62c16e2f3e404c3` | Phase 14.0 records it as a v5 compatibility copy. Its payload declares v5. The Phase 14 training script saves the same payload to v5 and the legacy v3 filename. The current file has 4,799,746 bytes. |
| Active `garment_classifier_v6.pt` | `1cc5d8a9afddb8113ec90258d73e51f8382418f5c7e053ba037286db2a49c3fc` | Matches the named primary classifier, path and 4,803,047-byte size in the Phase 14.1 release record. The Phase 14.5 inventory independently names this file and digest. Certified for identity, compatibility and local execution. |
| Edge classifier ONNX | `d785b3ef38e80492506bcfb1cc70a926047f09921b81b3880dc78b773e34ca9f` | Matches the Phase 14.1 edge release. Health checks now verify bytes for local client artifacts. Browser inference parity was outside this run. |
| Garment landmark checkpoint | `618e2a539fbb80f33d337b0d94f943ba47d1c00042375848ffb2f1b6d993a33b` | Passed its existing independent pin and PyTorch load check. |

The legacy v3 pathname was reused across releases. Even its November 15 checkpoint manifest refers to a different v4 payload. Before this repair the runtime tried the v5 filename first. Its bytes match v6 exactly, consistent with the explicit compatibility copy in `scripts/finish_phase_14_1_export.py`. The active registry and the classifier now use the canonical v6 release, retaining the Phase 13 record intact. No checkpoint was regenerated, rewritten or promoted based on its observed hash.

The training payload declares phase 14.1. All weights load strictly into the MobileNetV3-Small hierarchical classifier. Its ten category labels, 55 subcategory labels and hierarchy mask match the application. The Phase 14.5 summary describes the backbone as MobileNetV3-Large, which conflicts with the training implementation and the architecture that loaded successfully. The Phase 14.1 release record and strict runtime check are the basis for this decision. Verified bytes are also the bytes deserialized. An unpinned or changed checkpoint cannot activate this neural path.

On the licensed denim-jacket photograph, both output vectors were finite, nonnegative and summed to one within 0.00001. The application returned the raw neural category `jacket` with confidence 0.7583. This is one inference observation. Population accuracy and calibration require a separate reference-backed holdout evaluation.

A separate legacy multi-task model still uses the v3 compatibility file. Its configuration shares 259 state entries, has 30 missing entries and encounters four unexpected entries. It now checks the compatibility digest and reports `partial-compatibility`. The missing heads have no trained-weight certification.

## Registry and orchestration

The Phase 13 manifest declares the classifier, landmark regressor, silhouette segmenter and feature embedder. Phase 14.22 explicitly adds DINOv2, Depth Anything V2, Grounded-SAM 2 and xatlas. The eight entries were reproducible in a fresh registry. Importing provider adapters and registering test doubles did not generate them. The original test still assumed the Phase 13 count. The two failures occurred in artifact verification and inventory accounting, before provider routing, fallback or confidence thresholds were exercised.

Canonical IDs now have deterministic order and separate alias lookup. Initialization rejects repeated JSON keys, repeated canonical IDs, alias collisions and collisions with built-ins. Health tests check all eight known identities, exact set equality with the running inventory, unique IDs, both pinned server artifacts and consistent totals. Every entry exposes execution type, release or adapter version, artifact identity, capabilities, input/output descriptions, configuration availability, confidence limits, hardware and cost fields. Unknown artifact identities and unmeasured compute cost remain explicit. A declaration or local file is insufficient for certification.

Two server checkpoints passed release verification. The segmenter and feature-embedder server files are absent. The four Phase 14.22 integrations have declarations without a pinned server checkpoint in this registry. Those six results do not certify an adapter or imply that every optional library is unavailable. The remote client pose asset was not downloaded.

## Provider acceptance

The preflight sends the authorized photograph to Gemini vision and a text-to-tool operation separately to each configured planner. The planner probe executes only its named provider. It requires the returned model and a validated `plan_garment` reconstruction action. The vision gate requires an uncached cloud response, a returned model and a valid garment result. Request IDs are retained when supplied. An explicitly selected planner must qualify. With no explicit selection the runner can use a planner that passed. The live recovery gate checks the selected planner and nonempty live vision receipts again in the actual conversation.

| Final probe | Configured model | HTTP | Decision |
| --- | --- | --- | --- |
| Gemini vision | gemini-2.5-flash | 403 | Permission denied |
| Gemini planner | gemini-2.5-flash | 403 | Permission denied |
| Groq planner | llama-3.1-8b-instant | 401 | Credential rejected |
| OpenRouter planner | google/gemma-3-12b-it:free | 401 | Credential rejected |

Both final commands reached an HTTP endpoint and produced these results. Earlier attempts also encountered TLS verification failures. All four final probes had configured credentials, no returned model ID and no request ID. The responses establish neither modality support nor tool support for these accounts. TLS verification remained enabled. Diagnostics distinguish missing credentials, rejected credentials, permissions, model or modality errors, invalid schemas, throttling, exhausted quota, transport failures, TLS, timeout and malformed output. Unit tests use response doubles for these paths. No credential values or upstream error bodies are retained in the report.

## Regression evidence

| Check | Observed result |
| --- | --- |
| Original two hybrid tests | 2 failed, 20 deselected before the repair |
| Final eight backend suites | 128 passed, 31 warnings, 10.69 s |
| Frontend | 355 passed in 25 files, 3.43 s |
| Frontend production build | Passed in 8.30 s with a chunk-size advisory |
| Stylist browser workflow | Upload, preview, GLB downloads, edit, undo, restored history and avatar attachment passed |
| Durable browser recovery | Four messages recovered. Browser download and restart checks passed. Edited asset SHA-256 before and after restart was `afe509595cf245bfa3fce2866920fd7a690bfc75509516ca943fd9efd0c6ae14` |
| Failure and ownership checks | Anonymous, expired and cross-user access, database row ownership, replay, quota, missing or corrupt assets, database outage and failed or interrupted workers passed the disposable staging checks |
| Credentialed recovery | Blocked at preflight, exit 2. No live conversation receipt |
| Backend container | The image recipe now includes the three runtime registry and provenance records. The Docker daemon was unavailable, so no image build or container execution was verified. |

The local runner classified recovery as `PARTIALLY_VERIFIED` because it used local recognition and planning. The photo, original candidate, edited candidate and recovered export are tied to the same run in the test history. Container deployment also needs the ML runtime and release artifacts available in the tested workspace.

## Reproduction

Use the repository root, the existing backend virtual environment and frontend dependencies. The browser commands require PostgreSQL utilities, Redis, PostgREST, Chromium and Node-resolvable Playwright. On this host the following two executable paths were available. The certificate bundle path is host-specific.

```sh
photo=data/datasets/phase_13_6_real_photos/wm_00_jacket_denim.jpg
export NODE_PATH="$HOME/.npm/_npx/420ff84f11983ee5/node_modules"
export POSTGREST_BIN=/tmp/yorvyn-pgrest-o82ybk/postgrest/16.6/bin/postgrest

shasum -a 256 models/checkpoints/*.pt frontend/public/models/edge/garment_classifier_edge.onnx
SUPABASE_URL='' NEXT_PUBLIC_SUPABASE_URL='' backend/venv/bin/python -m pytest -q \
  backend/tests/test_hybrid_ai_orchestration.py -k 'verify_real_server_checkpoints_on_disk or registry_health_report'

SUPABASE_URL='' NEXT_PUBLIC_SUPABASE_URL='' GEMINI_API_KEY='' GOOGLE_API_KEY='' \
GROQ_API_KEY='' OPENROUTER_API_KEY='' backend/venv/bin/python -m pytest -q \
  backend/tests/test_phase15_5_certification.py backend/tests/test_hybrid_ai_orchestration.py \
  backend/tests/test_phase15_4_staging.py backend/tests/test_garment_chat_edits.py \
  backend/tests/test_persistent_ai_sessions.py backend/tests/test_phase15_evaluation_integrity.py \
  backend/tests/test_neural_garment_ai_phase_7.py backend/tests/test_ai_stylist.py

backend/venv/bin/python -m pytest -qs backend/tests/test_phase15_5_certification.py -k real_photo
(cd frontend && npm test)
(cd frontend && npm run build)
backend/venv/bin/python scripts/verify_conversational_garment.py "$photo" --browser
backend/venv/bin/python scripts/verify_staging_garment.py recovery --browser
backend/venv/bin/python scripts/verify_staging_garment.py preflight --photo "$photo"
REQUESTS_CA_BUNDLE=/etc/ssl/cert.pem backend/venv/bin/python scripts/verify_staging_garment.py recovery --live --photo "$photo"
```

## Next acceptance task

Provide a staging Gemini credential authorized for image inference and at least one authorized structured planner on a trusted network path. Rerun the last two commands. Close external acceptance only after the same Stylist conversation records the live vision and planner receipts, passes ownership checks and recovers the identical edited GLB after restart. The Phase 15.5 test history identifies all changed files and the independent local checks.
