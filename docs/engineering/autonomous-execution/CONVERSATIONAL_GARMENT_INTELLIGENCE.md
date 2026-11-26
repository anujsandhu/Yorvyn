# Conversational garment reconstruction

November 24, 2026 · Local working tree based on `7139fc7eea4e1f890e28da9140db2e8550081267`

## Acceptance status

The existing Stylist chat can take a jacket photograph through selection, reconstruction, inspection, export, editing, undo and avatar fitting. The local browser exercise used the mounted application, the real garment worker and the existing avatar fitting engine. The tested recognition and planning path used local services. Live multimodal inference and accuracy against physical garments remain open acceptance items.

## How a turn reaches the avatar

1. The two responsive Stylist layouts in Avatar Studio share the attachment control and send handler. A signed-in user can supply up to ten photos, subject to per-file and batch limits. Styling requests continue to use the existing stylist service.
2. The garment route checks session ownership and upload integrity, reserves a request allowance and validates the planner output against a closed list of actions. An ambiguous photograph produces a garment choice in chat. A matching follow-up uses the retained photos. The original input hashes and the hashes used by the recognition pipeline are recorded separately when cropping is needed.
3. The existing multi-view identification service records observations and missing evidence. Its reconstruction endpoint hands the specification and the matching images to the existing job manager. Redis supplies activity events. The chat follows the job until a terminal state.
4. The candidate route verifies the owner, job and geometry. An eligible topology repair removes duplicate or degenerate indexed triangles and passes through the mesh validator again. If validation fails, the route withholds the preview. A passing structural inspection gives no measurement of resemblance to the photographed item.
5. Edits replay against the original GLB. The chat records measurements before and after an edit, preserves history, and can restore the parent turn. The viewer offers rotation, export and avatar fitting. Fitting success requires a successful fit and a mesh found under the avatar in the Three.js scene graph.

## Files changed for this workstream

Paths below are relative to the repository root. Some files also contain changes from earlier work.

| Files | Changes |
| --- | --- |
| `backend/app/api/conversational_garments.py`, `backend/app/main.py` | Authenticated session tools, validation, ownership, request budgets, event stream, immutable candidate history and route mounting |
| `backend/app/services/llm/garment_plan.py` | Closed action schema, configured provider selection, tool-call validation, usage reporting and local fallback |
| `backend/app/services/garments/chat_candidate.py` | Bounded geometry and appearance edits, topology repair and preservation of unrelated GLB attributes |
| `backend/app/api/garment_identification_routes.py`, `backend/app/services/ai/multiview/fusion_engine.py` | Move fusion off the HTTP event loop, deduplicate views on the repository's Python runtime and exclude failed perceptions from evidence |
| `backend/app/api/garment_generation_routes.py`, `backend/app/services/garments/job_manager.py` | Asset access, real job metadata after a cold read, retry behavior, multi-view inputs, per-job mesh builder and procedural fallback provenance |
| `frontend/src/pages/AvatarStudio.tsx`, `frontend/src/services/aiSessionService.ts` | Both existing chat layouts, authenticated uploads, activity, history restoration and try-on handoff |
| `frontend/src/components/ai/GarmentJobMessage.tsx`, `frontend/src/components/AvatarStudioViewer.tsx` | Attachments, inline 3D artifact, measured dimension comparison, separate avatar asset lifetime and confirmed fitting state |
| `frontend/src/components/PhotoTo3DGarmentModal.tsx` | String replacement compatible with the existing TypeScript build target |
| `backend/tests/test_garment_chat_edits.py`, `scripts/verify_conversational_garment.py`, `scripts/verify_garment_browser.cjs` | Focused regression tests and executable HTTP and browser checks |
| `docs/engineering/autonomous-execution/EXECUTION_LEDGER.json` and this report | Acceptance evidence and outstanding gates |

## Reproduce the checks

Run the following from the repository root. The integration runner starts disposable PostgreSQL and Redis instances. It requires the backend environment, the local perception checkpoints and PostgreSQL and Redis executables on the path. It uses a locally signed test identity. For the browser check, install the frontend dependencies, Chromium and Playwright. This run used Playwright 1.65.1 from a local package cache exposed through `NODE_PATH`.

```sh
backend/venv/bin/python -m pytest -q backend/tests/test_garment_chat_edits.py backend/tests/test_phase15_evaluation_integrity.py backend/tests/test_persistent_ai_sessions.py backend/tests/test_real_world_ai_phase_8.py
(cd frontend && npm test)
(cd frontend && npm run build)
photo=data/datasets/phase_13_6_real_photos/wm_00_jacket_denim.jpg
backend/venv/bin/python scripts/verify_conversational_garment.py "$photo"
backend/venv/bin/python scripts/verify_conversational_garment.py "$photo" --browser
```

## Results

| Check | Observed result |
| --- | --- |
| Backend suites | 56 passed, 350 warnings in 102.29s (0:01:42). Suites cover garment edits, evaluation integrity, conversation sessions and Phase 8 regressions. |
| Frontend suite | 355 tests passed in 25 files |
| Production build | TypeScript and Vite passed. Vite reported a large output chunk and browser externalization notices. |
| Authenticated HTTP workflow | Detected multiple garment objects and accepted the jacket selection. Repeated uploads produced one usable observation. Checked the activity stream, invalid input, cross-user denial, request replay, GLB delivery, a changed edit, byte-identical undo and saved message count. A fresh job manager read the completed result from PostgreSQL and the result metadata on disk. Original and edited exports each contained 1,631,020 bytes. |
| Browser workflow | Opened the existing Stylist, submitted the photograph, observed streamed tool activity, loaded the GLB in WebGL, downloaded it, widened it, compared the measured width, restored the original bytes, refreshed history and confirmed attachment to the avatar. |
| External provider probe | A small text tool-call request received HTTP 401 from Groq and OpenRouter. The Gemini adapter had no configured credential. The fallback planner recorded its own provenance. |

## Limits and next task

- Recognition and reconstruction were exercised on one real photograph. Repeated views exercised evidence deduplication. Calibrated multi-view accuracy, physical fit, rear geometry, fabric identity, print fidelity and fold realism require independently annotated references. The real evaluation pilot manifest currently contains zero samples.
- Width, length, segmented sleeve width and denim appearance have executable edit operations. Sleeve edits require isolated sleeve geometry. The denim operation adjusts appearance. Cloth thickness and fold optimization remain unsupported.
- Page refresh and cold reconstruction metadata reads were verified. The integration run used the existing session repository's in-memory fallback. Hosted Supabase sign-in, durable chat restoration after backend restart and distributed worker failover require separate validation. If a refresh discards photos during clarification, the user must reattach them.
- The isolated browser exercise uses local API handlers and prevents external traffic. It does not establish provider billing, hosted storage, concurrent production capacity or mobile browser compatibility.
- The changes are local to the working tree. The workstream has no release or deployment verification.

**Next implementation task.** Add a credentialed staging acceptance run for the same workflow using an authorized garment photograph and a disposable test account. Require a recorded vision-provider response and model ID, a validated planner tool call, and successful retrieval of the same conversation and candidate hash after restarting the backend. Enable that test when staging credentials are available. Evaluate photographic accuracy separately once the holdout contains licensed, independently measured reference assets.
