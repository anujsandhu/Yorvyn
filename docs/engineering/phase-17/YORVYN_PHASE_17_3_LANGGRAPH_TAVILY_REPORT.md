# YORVYN — PHASE 17.3 LANGGRAPH & TAVILY INTEGRATION REPORT

**Architecture:** YORVYN Intelligence Platform (YIP)  
**Baseline HEAD:** `7139fc7eea4e1f890e28da9140db2e8550081267` (preserved; no commits created)

---

## 1. Architecture Integration Summary

Phase 17.3 extends YORVYN with bounded stateful LangGraph workflows and Tavily external web intelligence while preserving `YIPOrchestrator`, `UnifiedModelRegistry`, `GarmentCapabilities`, `GarmentRouter`, `GarmentKnowledgeRAG`, recommendation engines, PostgreSQL, Redis Streams, transactional outbox, and Supabase/FastAPI authentication:

- **Internal vs. External Knowledge Boundary (`backend/app/services/intelligence/unified_knowledge.py`):** Queries `GarmentKnowledgeRAG` (`internal_hits`) separately from `TavilyWebIntelligenceAdapter` (`external_evidence`). Untrusted external content stays labeled (`UNTRUSTED_EXTERNAL_WEB` / `APPROVED_PUBLIC_DOMAIN_EXTERNAL`), carries `executable_authority: false` & `auto_ingested_to_rag: false`, and requires explicit clean validation via `promote_validated_external_item(...)` (blocking any prompt-injection-flagged snippet).
- **LangGraph Workflow Layer (`backend/app/services/intelligence/langgraph_workflows.py`):**
  - Compiled `StateGraph` instances backed by `MemorySaver` + PostgreSQL 16.14 table `yip_langgraph_checkpoints` via `asyncpg` and existing `resolve_postgres_dsn()` (`unified_state_machine.py`).
  - Hard node step ceiling (`MAX_WORKFLOW_STEPS = 8`), `recursion_limit`, `asyncio.wait_for` timeout, sensitive state rejection (`FORBIDDEN_STATE_KEY_FRAGMENTS` blocking API keys, raw body measurements, tokens), filesystem/SQL pattern filtering, and strict `owner_id` enforcement on status/resume/cancel (`PermissionError` / HTTP `403`).
- **Tavily REST Client (`backend/app/services/intelligence/tavily_web_adapter.py`):**
  - Direct `httpx` integration against official `https://api.tavily.com` endpoints (`/search`, `/extract`, `/research`, `/crawl`) using `Authorization: Bearer <TAVILY_API_KEY>`.

---

## 2. Dependency & Licensing Governance Report

| Package | Version Pinned | License | Python Compatibility | Transitive Dependencies Installed | Installation Rationale |
| :--- | :---: | :---: | :---: | :--- | :--- |
| `langgraph` | `0.6.9` | MIT | `>=3.9` (host Python `3.9.6`) | `langchain-core==0.3.86`, `langgraph-checkpoint==2.1.2`, `langgraph-prebuilt==0.6.5`, `langgraph-sdk==0.2.9`, `xxhash==4.1.0`, `langsmith==0.4.37`, `orjson`, `ormsgpack`, `tenacity` | Latest LangGraph supporting Python 3.9; avoids full `langchain` / `llama-index` bloat. (`langgraph>=1.0` & `langgraph-checkpoint-postgres` require `Python>=3.10`, so PG checkpointing reuses existing `asyncpg`.) |
| `httpx` *(existing)* | `0.28.1` | BSD-3-Clause | `>=3.8` | Already installed in `backend/requirements.txt` | Official REST integration against `https://api.tavily.com` without installing `tavily-python`; gives strict SSRF, timeout, byte limit & circuit-breaker control. |

- `pip check` after install: **`No broken requirements found.`**

---

## 3. LangGraph Workflow Inventory

| Workflow Name | Capability ID | State Schema | Nodes & Controls | Interrupt / Resume |
| :--- | :--- | :--- | :--- | :--- |
| `garment.research` | `workflow.garment.research` | `GarmentResearchState` (`17.3.0`) | `parse_request` → `retrieve_internal_rag` → conditional `fetch_external_tavily` → `synthesize_research` (`max_steps <= 8`) | No |
| `fashion.discovery` | `workflow.fashion.discovery` | `FashionDiscoveryState` (`17.3.0`) | `parse_discovery` → `load_owner_profile` (consent-gated) → `gather_fashion_context` → `rank_candidates` | No |
| `design.assistance` | `workflow.design.assistance` | `DesignAssistanceState` (`17.3.0`) | `interpret_design` → `identify_components` → `validate_capability` (closed op set) → conditional `pause_for_confirmation` / `execute_design` | **Yes (`AWAITING_CONFIRMATION` until owner confirms)** |

---

## 4. Tavily Provider, Security, Cost & Performance Report

- **Live Credential Audit:** `TAVILY_API_KEY` is **not set** in process env or `backend/.env`. In uncredentialed mode, `TavilyWebIntelligenceAdapter` returns `status="BLOCKED_NO_CREDENTIALS"` cleanly without network calls or synthetic fallback results.
- **Security Controls Verified:**
  - `ExternalKnowledgeValidator.validate_public_url` blocks non-HTTP schemes (`file://`, `javascript:`), loopback (`127.0.0.1`), link-local (`169.254.169.254`), RFC1918 (`10.0.0.5`), `.local`/`.internal`, and private DNS resolutions.
  - `sanitize_external_content` strips HTML tags, enforces `2 MB` HTTP payload cap / `3000` char snippet limit, neutralizes prompt/SQL/shell injections, and flags `injection_risk_detected=true`.
- **Governance & Performance:**
  - Per-owner sliding-window rate limit (`20 req/min`), TTL search cache (`900 s`, cache miss `0.739 ms` vs hit `0.023 ms`), exponential backoff retries (`<= 2`), failure-threshold circuit breaker (`CIRCUIT_OPEN`), and usage credit accounting (`credits_used`).
  - **LangGraph + PostgreSQL 16.14 Perf (`15` runs):** `p50_ms = 10.987 ms`, `max_ms = 23.913 ms`, **`15/15` verified rows in `yip_langgraph_checkpoints`** (`pg_persisted: true`).

---

## 5. Updated Capabilities, Provider Registry, API & Frontend

- **Capabilities (`capability_registry.py`):**
  - `knowledge.external.search`, `knowledge.external.extract`, `knowledge.external.research` → **`State.DECLARED`** (no `TAVILY_API_KEY` for live verification).
  - `workflow.garment.research`, `workflow.fashion.discovery`, `workflow.design.assistance` → **`State.EXECUTABLE`** (compiled & internally verified).
- **Provider/Framework Registry (`model_registry.py`):** Exposed separately via `get_external_providers_and_frameworks()` and `GET /api/intelligence/providers`; neither Tavily nor LangGraph is registered as a neural AI model, and raw API keys are never returned.
- **FastAPI Endpoints (`intelligence_routes.py`):** `POST /api/intelligence/web/{search,extract,research}`, `POST /api/intelligence/workflows/execute`, `GET /api/intelligence/workflows/status/{thread_id}`, `POST /api/intelligence/workflows/resume`, `GET /api/intelligence/providers`.
- **Frontend (`intelligenceApi.ts`, `StylistChat.tsx`, `DigitalWardrobe.tsx`, `GarmentDesignWorkspace.tsx`):** Added opt-in trend/research triggers clearly labeling `[External Web Reference — Unverified]` separately from verified internal notes without exposing raw agent traces or credentials.

---

## 6. Automated Verification & Remaining Blockers

- **Backend `pytest`** (11 suites including [test_langgraph_tavily_phase17_3.py](file:///Users/anujsandhu/Projects/yorvyn/backend/tests/test_langgraph_tavily_phase17_3.py) `5/5`): **`134 passed, 5 warnings in 20.94s`** (`YORVYN_DISABLE_SEGFORMER=1 YORVYN_DISABLE_COMPONENT_CLIP=1`).
- **Frontend `vitest` & Build:** **`2 test files, 10 passed`** ([IntelligencePlatformIntegration.test.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/components/__tests__/IntelligencePlatformIntegration.test.ts) `4/4`, [PhotoTo3DGarmentModalHandoff.test.tsx](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/components/__tests__/PhotoTo3DGarmentModalHandoff.test.tsx) `6/6`); `tsc && vite build` **`✓ built in 5.74s`**.
- **Remaining Blockers (Explicit Classification):**
  - **`BLOCKED` Live Tavily Authenticated Execution:** Live `https://api.tavily.com` provider verification is blocked until `TAVILY_API_KEY` is configured on the server; all Tavily HTTP behaviors are verified under `httpx.MockTransport` (`verification_status="MOCKED_TEST"`).
  - **Upgrade Path Note:** Upgrading host Python from `3.9.6` to `>=3.10` would permit `langgraph>=1.0` and official `langgraph-checkpoint-postgres` if native LangGraph checkpoint-table schema interoperability is desired later.
