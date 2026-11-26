# Phase 16.0 local architecture acceptance

**Decision, November 25, 2026.** The local intelligence architecture passed the garment regression and Stylist recovery gates. The credentialed external integration remains separately blocked. No hosted deployment, production migration or reference-backed garment accuracy measurement was performed.

The base revision was `7139fc7eea4e1f890e28da9140db2e8550081267`. The tested checkout included the existing uncommitted implementation, installed backend/frontend dependencies, local model releases and cached perception adapters. The base revision in isolation is insufficient to reproduce this run.

## Acceptance evidence

| Criteria | Executed evidence | Result |
| --- | --- | --- |
| 1–4. Audit, interface, catalog and identities | Source inventory, 39 typed capability records, server bindings, duplicate/unknown rejection, active checkpoint and hardware eligibility tests. The classifier ran in the browser workflow with its recorded v6 identity. | Passed for the documented local runtime. Declaration-only and reference-dependent entries retain their individual states. |
| 5–8. Local routing, deterministic fallback, confidence and supplemental failures | Ordinary intent, weak or missing classifier evidence, hardware failure, deterministic edits, conflicting identity, missing front view, valid/invalid supplemental plan and provider-failure branches exercised. | Passed. Controlled response doubles are used for external diagnostic branches. |
| 9–11. Operation validation, provenance and accounting | Named actions, parameter rejection, validated result contracts, task and input references, bounded concurrent execution, timeouts, cancellation, ownership, measured token usage, missing usage and cost tested. Browser receipts link the initiating turn to its sources, classifier and job. | Passed. GPU utilization, unreported billing and physical fit remain unknown. |
| 12. Existing Stylist | Browser upload, recognition, reconstruction, edit, undo, GLB download, re-opened history and avatar attachment. Separate durable run checked browser download, backend restart and row-level ownership. | Passed locally. |
| 13–14. Regressions and Phase 16 suite | Thirteen backend suites, frontend tests and production build. See the exact commands below. | Passed. |
| 15. Documentation and continuity | Architecture inventory and diagram, capability inventory, model matrix, routing policy, cost report and execution ledger. | Recorded. |

## Photographed garment and recovery

The disposable Chromium/PostgreSQL/PostgREST/Redis run used the licensed denim-jacket photo with SHA-256 `f87ac6c4b1a7a0279635afe249f8cf519be80f3336b5395fe83e878e9bcb0e61`. The initial turn ran intent planning, subject selection, multi-view identification and geometry submission. The selected crop was classified as `jacket / denim_jacket` on MPS. The classifier reported 0.9078 category confidence. It issued zero external requests. No user model or provider selection was needed.

Job `job_281355795ac1` reported the image-conditioned strategy, engine `neural_garment_reconstruction_engine_v3`, and `hybrid_neural_procedural` geometry provenance. Independent inspection passed on the exported candidate before publication. The committed GLB had SHA-256 `ee40176044654ab19ff21808b46316cd27a4010896b72883d80bd855b7750141`. The edited GLB had SHA-256 `0b8ed9dd98dc7a4e2852888504f74d1578967de66b0c12b1cdc8ab64967fd81b` before and after the backend restart. Four messages were recovered in the original conversation.

The runner exercised anonymous and expired sessions, cross-user jobs and candidates, row-level reads, duplicate submission, quota, database outage, missing and damaged assets, failed and interrupted workers. The local runner returned exit 0 and `PARTIALLY_VERIFIED` for combined staging, with `VERIFIED_COMPLETE` for browser and restart checks. Its combined status reserves credentialed verification for a real upstream run.

The initial integrated browser run caught scalar provenance fields which violated the V2 nested-object contract. They now live inside a per-view routing record. The extended regression run also found five failures from the kurta builder reading obsolete vertex/triangle offset attributes. The builder now uses the start indices in the actual panel contract. All five failing tests were retained and rerun.

## Test results

| Run | Actual result |
| --- | --- |
| Final backend run, including 26 Phase 16 cases | 207 passed, 31 warnings in 14.41 s |
| Frontend tests | 355 passed in 25 files, 4.26 s |
| Frontend production build | Passed in 9.81 s with a bundle-size advisory |
| Stylist and durable browser commands | Both exited 0 |
| Preflight with credentials explicitly empty | Exited 2, blocked |

## Commands

Run from the repository root in zsh or bash. The browser checks require installed PostgreSQL utilities, Redis, PostgREST, Chromium, frontend dependencies and Node-resolvable Playwright. These executable overrides were used on this host.

```sh
photo=data/datasets/phase_13_6_real_photos/wm_00_jacket_denim.jpg
export NODE_PATH="$HOME/.npm/_npx/420ff84f11983ee5/node_modules"
export POSTGREST_BIN=/tmp/yorvyn-pgrest-o82ybk/postgrest/16.6/bin/postgrest
SUPABASE_URL='' NEXT_PUBLIC_SUPABASE_URL='' GEMINI_API_KEY='' GOOGLE_API_KEY='' \
GROQ_API_KEY='' OPENROUTER_API_KEY='' backend/venv/bin/python -m pytest -q \
  backend/tests/{test_phase16_intelligence,test_phase15_5_certification,test_hybrid_ai_orchestration,test_phase15_4_staging,test_garment_chat_edits,test_persistent_ai_sessions,test_phase15_evaluation_integrity,test_neural_garment_ai_phase_7,test_ai_stylist,test_garment_reconstruction_phase_3,test_garment_material_texture_phase_4,test_garment_fitting_phase_5,test_garment_dynamics_phase_6}.py
(cd frontend && npm test && npm run build)
backend/venv/bin/python scripts/verify_conversational_garment.py "$photo" --browser
backend/venv/bin/python scripts/verify_staging_garment.py recovery --browser
GEMINI_API_KEY='' GOOGLE_API_KEY='' GROQ_API_KEY='' OPENROUTER_API_KEY='' \
  backend/venv/bin/python scripts/verify_staging_garment.py preflight
```

The deliberately credential-free preflight returned `BLOCKED_MISSING_CREDENTIAL` and exit 2. Phase 15.5's last credentialed attempt received HTTP 403 from Gemini and HTTP 401 from Groq and OpenRouter. Phase 16 did not repeat that photograph transmission. To reopen external acceptance, provision authorized staging credentials and run `backend/venv/bin/python scripts/verify_staging_garment.py recovery --live --photo "$photo"` with normal TLS verification.

## Remaining limitations and next task

- Real-world holdout reconstruction accuracy, camera-conditioned multi-view evaluation, material fidelity and physical fit remain unverified. Structural inspection and a rendered avatar do not measure them.
- The supported policy uses explicit abstention thresholds, model eligibility and relative compute preference. There is no measured cost/quality frontier across every optional model.
- Native work may outlive a disconnected caller. It retains its execution slot. An already submitted job uses the durable job cancellation path. Cross-host capacity enforcement and production load testing remain open.
- The architecture carries 39 descriptors. Some dispatch directly through the server, some execute inside an existing job or browser, and others are declared future capabilities. Each is identified in the capability registry.
- **Next implementation task:** Phase 16.1 should bind a component-evidence operation that returns source view, visibility and uncertainty for each sleeve, collar, pocket and closure. Evaluate it against licensed, identity-separated annotations before letting those predictions select construction details.
