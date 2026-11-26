# Phase 15.4 staging acceptance

**Decision on November 25, 2026 — PARTIALLY_VERIFIED.** The Stylist created and edited a garment in Chromium. After the original FastAPI process exited, a new process recovered the same four messages and served the same edited GLB to a new browser process. The live inference gate failed before a credentialed conversation could begin.

## Environment and scope

Repository HEAD was `7139fc7eea4e1f890e28da9140db2e8550081267`. The initial working tree had 70 modified tracked files and 366 untracked status entries, including directories. Validation used that working tree. This phase added application changes, migration 012, a staging runner, regression tests and acceptance evidence. No migration was applied to a hosted database.

The disposable environment ran on macOS arm64 with Python 3.9.6, Uvicorn 0.39.0, FastAPI 0.128.8, PostgreSQL 16.14, PostgREST 16.6, Redis 8.8.0 and Playwright Chromium. The full application ran against private temporary asset directories. The test created two disposable PostgreSQL auth identities and signed short-lived test tokens. The tested account fingerprint is `b49fcc9218c6f388`. The browser exercised the existing `/stylist` route. Hosted login, a remote staging deployment and persistence across host or volume replacement remain unverified.

The source photograph was *1980s blue denim jacket, Finland – 01*. The bundled source record identifies its CC BY 4.0 license. The runner verifies the bundled file against its recorded SHA-256 before use. The selected garment crop is PNG, which the orchestrator now labels according to the decoded image. [Source photograph and attribution](https://commons.wikimedia.org/wiki/File:1980s_blue_denim_jacket,_Finland_%E2%80%93_01.jpg)

## Acceptance gates

| Gate | Status | Evidence |
| --- | --- | --- |
| External vision inference | FAILED | Gemini Vision was configured for `gemini-2.5-flash`. Attempts encountered HTTP 403 and TLS verification failure. No upstream model ID or classification was obtained. |
| External structured planner | FAILED | Groq requested `llama-3.3-70b-versatile` and OpenRouter requested `meta-llama/llama-3.3-70b-instruct`. Both returned HTTP 401 in a connectivity-confirmed attempt. Gemini planner requests for `gemini-2.5-flash` returned HTTP 400 or 403 across attempts. TLS failures also occurred. No live validated tool call, returned model ID or token usage was available. |
| Missing-credential control | BLOCKED_MISSING_CREDENTIAL | Clearing the provider settings produced this status for vision and all three planner adapters. The configured attempts above received failures with credentials present. |
| Local reconstruction and editing | VERIFIED_COMPLETE | Local vision selected a jacket, local rules selected reconstruction, and the existing worker produced a GLB. The worker recorded `hybrid_neural_procedural`. The mesh inspector, inline preview, browser download and measured width edit all executed. |
| Durable session and candidate recovery | VERIFIED_COMPLETE | The original backend PID `10096` exited after a forced stop. PID `10204` served identical message records, job result and candidate bytes from durable storage. Chromium restored the saved conversation and downloaded the edited GLB again. |
| Security and failure handling in disposable staging | VERIFIED_COMPLETE | Independently exercised API ownership, database row-level access, authentication expiry, replay, budgets, worker interruption, damaged storage and database loss. |
| Hosted deployment and identity service | BLOCKED_INFRASTRUCTURE | No designated hosted staging target and disposable hosted login were supplied. |
| Physical garment accuracy | Unmeasured | This exercise measured delivery and byte integrity. It had no reference scan, physical fit measurements or annotated multi-view holdout. |

Provider attempts and available upstream request IDs are in the [test history](PHASE_15_4_TEST_HISTORY.json). For example, Groq returned request ID `req_01m88srrf8eexsckf81c1xdkrj` with HTTP 401. No provider supplied usage or billing information for a successful external inference. The runner never counted a local plan toward the live gate.

## Durable evidence from the browser run

| Field | Recorded value |
| --- | --- |
| Conversation and state | `af25fde7-e52b-409e-b7ec-0612ff1d6a39`, active, 4 messages |
| Uploaded photograph SHA-256 | `f87ac6c4b1a7a0279635afe249f8cf519be80f3336b5395fe83e878e9bcb0e61` |
| Selected crop SHA-256 | `5ef1ff93b601ad742db0933834ef2fc68871cae309ba54054efa5e8d78593478` |
| Reconstruction job | `job_6810f48f1f17` |
| Job asset within isolated storage | `job_6810f48f1f17.glb` |
| Original candidate / parent of edit | `3f63341a-b6b6-4117-a9f6-131ffe5c6856` |
| Edited candidate | `26513df1-76b4-450c-82be-90f3960040a5` |
| Committed source asset SHA-256 | `b1d7aa9cedd48dd56939b219d5e459627afe3a612b00a2e669046adc42e6ba5a` |
| Original exported candidate SHA-256 | `b1d7aa9cedd48dd56939b219d5e459627afe3a612b00a2e669046adc42e6ba5a` |
| Edited GLB before restart | `acac202d466acb2281f3a47afda235a2a4e7f4ac37f2cb402e0b3b2c02796aa2` |
| Edited GLB after restart | `acac202d466acb2281f3a47afda235a2a4e7f4ac37f2cb402e0b3b2c02796aa2` |

The runner checked the PostgreSQL job owner, session-scoped idempotency key and committed checksum. It compared the stored recognition specification with the conversation, and each usable image hash with its vision record. It reopened the original and edited candidates through the application, compared the full message list and job metadata after restart, and independently hashed the browser download. The disposable resources were removed when the run ended. Candidate IDs identify this run's evidence.

## Failure results

- Anonymous and expired-token session requests returned 401. An unknown session and another account's conversation or candidate returned 404. Another account's job returned 403. A direct PostgREST read returned four rows to the owner and zero to the other account.
- Duplicate requests before and after restart returned the original reply. A new request above the disposable daily allowance returned 429.
- A failed worker retained its failure after restart. A separate worker was stopped in state `analyzing`. Its job produced no candidate, and its first status check after the configured deadline reported `failed`. This covers the embedded worker dying before publication. Automatic resumption and distributed-worker failover remain unverified.
- Removing the committed asset returned 404. Substituting damaged bytes returned 409. Stopping PostgreSQL returned 503 even after the session had just been read successfully.
- Unit tests exercised malformed planner actions, unexpected arguments, missing arguments, provider authentication failures, a timeout, malformed vision output, exact image forwarding and an unavailable durable store. The mocked responses in these tests contribute no live inference evidence.

## Implementation and reproduction

The main changes are in `backend/app/services/database/supabase_repository.py`, `backend/migrations/012_durable_conversation_sequence.sql`, the AI vision and LLM adapters, the garment candidate and job routes, and `backend/app/services/garments/job_manager.py`. Strict storage is enabled with `YORVYN_REQUIRE_DURABLE_SESSIONS=1` for staging. Migration 012 locks the owning conversation row to allocate message order and update the durable count. Candidate retrieval checks the committed source checksum and, for edited candidates, the saved result checksum. Planner and vision records can carry the upstream model and request IDs. The Gemini planner uses the JSON Schema form of the function declaration. [Gemini API reference](https://ai.google.dev/api/caching#FunctionDeclaration)

Run the following from the repository root. The recovery runner requires PostgreSQL utilities, Redis and PostgREST on the path. `POSTGREST_BIN` can name an alternative executable. Browser mode also requires the frontend dependencies, Chromium and a Node-resolvable Playwright package. This run used a temporary PostgREST binary and a cached Playwright installation via `NODE_PATH`.

```sh
photo=data/datasets/phase_13_6_real_photos/wm_00_jacket_denim.jpg
backend/venv/bin/python scripts/verify_staging_garment.py preflight --photo "$photo"
backend/venv/bin/python scripts/verify_staging_garment.py recovery --browser
REQUESTS_CA_BUNDLE=/etc/ssl/cert.pem backend/venv/bin/python scripts/verify_staging_garment.py recovery --live --photo "$photo"
(cd frontend && npm test)
```

The live command exited 2. The local browser command exited 0 with a phase result of `PARTIALLY_VERIFIED`. The trusted CA bundle above is specific to this host. TLS verification was enabled throughout. The live command enables the browser path when the provider gates succeed.

Backend validation ran `backend/venv/bin/python -m pytest -q` with `test_phase15_4_staging.py`, `test_garment_chat_edits.py`, `test_persistent_ai_sessions.py` and `test_phase15_evaluation_integrity.py` under `backend/tests/`. **54 passed** with external services disabled. Adding `test_hybrid_ai_orchestration.py` yielded **74 passed and 2 failed**. The frontend suite passed **355 tests in 25 files**.

The classifier checkpoint on disk hashes to `08225bd499b33a26920e7c241157fccabc4922addb021884b62c16e2f3e404c3`. The registry expects `44eacae47d318ef7c5508be776d295d71c095e9514e2a8ab5c01946e994c04b8`. The other failing assertion expects four registered models and observed eight. These failures remain open. No checksum or assertion was relaxed.

**Next acceptance run.** Provide staging credentials authorized for Gemini image inference and a supported planner, with a trusted network path to their endpoints. Rerun the live command and require both upstream model receipts in the same browser-created conversation before accepting restart recovery as credentialed. Reconcile the deployed classifier with its approved checkpoint manifest before model certification.
