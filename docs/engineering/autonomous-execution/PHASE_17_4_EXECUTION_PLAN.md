# YORVYN — PHASE 17.4 EXECUTION PLAN & STARTING STATE RECORD

**Date:** 2026-11-26  
**Baseline Git HEAD:** `7139fc7eea4e1f890e28da9140db2e8550081267`  
**Phase:** 17.4 — Intelligence Workflow Reliability, Security Hardening & Production Readiness  

---

## 1. Recorded Starting Environment State

- **Git Working Tree:** Preserved uncommitted Phases 15–17.3 work plus additive Neural Recommendation Generalization (`test_neural_generalization_phase17_4.py`: 77/77 focused backend tests, 10/10 frontend vitest integration tests, production build exit 0). No destructive git commands or commits performed.
- **Python Environment:** `backend/venv/bin/python` (`Python 3.9.6`):
  - `langgraph == 0.6.9`, `langgraph-checkpoint == 2.1.2`, `langgraph-prebuilt == 0.6.5`
  - `asyncpg == 0.32.0`, `httpx == 0.28.1`, `redis == 7.0.1`, `pydantic == 2.13.5`
  - Note: `psycopg2` and `langgraph-checkpoint-postgres` are not installed; PostgreSQL runs natively via `asyncpg`.
- **PostgreSQL 16.14 (`resolve_postgres_dsn()` -> `yorvyn_persistence`):**
  - Existing migrations: `001_initial_supabase_schema.sql` through `012_durable_conversation_sequence.sql`.
  - Existing `yip_langgraph_checkpoints` table columns: `thread_id (text NOT NULL PK)`, `owner_id (text NOT NULL)`, `workflow_name (text NOT NULL)`, `status (text NOT NULL)`, `payload_json (jsonb NOT NULL)`, `updated_at (timestamptz)`.
  - Indexes: `yip_langgraph_checkpoints_pkey`, `idx_yip_lg_owner`.
  - Existing rows at audit start: **36** (`SELECT count(*) FROM yip_langgraph_checkpoints`).
- **Redis (`redis://localhost:6379/0`):** `PING -> True` (`redis 7.0.1`).
- **Tavily Credentials:** `TAVILY_API_KEY` is unset (`False` in runtime `settings`), so live Tavily endpoints remain `BLOCKED_NO_CREDENTIALS` rather than verified live.

---

## 2. Prioritized Audit Findings & Defect List

1. **`F-17.4-001` (Critical / P0) — Non-Durable LangGraph Checkpointing & Node Replay on Restart:**
   - **Location:** `backend/app/services/intelligence/langgraph_workflows.py` (`MemorySaver` + `YIPPostgresCheckpointMirror`).
   - **Root Cause:** Graphs compile with in-memory `MemorySaver` while `YIPPostgresCheckpointMirror` only writes a coarse final/paused JSON snapshot to `yip_langgraph_checkpoints`. After a process restart (`MemorySaver` empty), `resume_workflow` re-invokes `execute_workflow` from `START`, replaying completed stages (`interpret_design`, `identify_components`, `validate_capability`) and lacking LangGraph `BaseCheckpointSaver` tuples, pending writes, `workflow_version`, `checkpoint_id`, `checkpoint_ns`, `interrupt_state`, `resume_metadata`, `created_at`, or optimistic concurrency fencing.
2. **`F-17.4-002` (Critical / P0) — Unbound Confirmation & Missing Atomic State Machine (`design.assistance`):**
   - **Location:** `backend/app/services/intelligence/langgraph_workflows.py` (`resume_workflow`, `execute_design`).
   - **Root Cause:** `human_confirmed=True` is not bound to `operation_hash`, `workflow_version`, `confirmation_expires_at`, or single-use `confirmation_idempotency_key`. Duplicate concurrent resume calls or tampered parameters can re-run `execute_design`. Explicit transitions (`AWAITING_CONFIRMATION -> CONFIRMED -> EXECUTING -> SUCCEEDED`, plus `REJECTED`, `EXPIRED`, `CANCELLED`, `FAILED`, `RECOVERY_REQUIRED`) are not persisted with row-level/optimistic concurrency locks.
3. **`F-17.4-003` (Critical / P0) — Python IPv4-Mapped IPv6 SSRF Bypass & Unvalidated Redirects / Resource Limits:**
   - **Location:** `backend/app/services/intelligence/tavily_web_adapter.py` (`ExternalKnowledgeValidator.validate_public_url`, `_post_with_retry`).
   - **Root Cause:** Verified directly that `ipaddress.ip_address('::ffff:127.0.0.1').is_loopback` evaluates to `False` in Python 3.9 without inspecting `.ipv4_mapped`, bypassing SSRF checks. Octal/hex/integer IP forms and CGNAT (`100.64.0.0/10`) are not blocked; redirect chains lack a strict validator rejecting private/cross-origin hops; HTTP streaming downloads `resp.content` before checking `MAX_RESPONSE_BYTES`; global `monthly_credit_budget`, max concurrent requests, and retry deadline caps are unenforced.
4. **`F-17.4-004` (High / P1) — Weak External Promotion Governance & Missing API Cancel / Promote Endpoints:**
   - **Location:** `backend/app/services/intelligence/unified_knowledge.py`, `backend/app/api/intelligence_routes.py`.
   - **Root Cause:** `promote_validated_external_item()` only checks `injection_risk_detected`, without requiring explicit approval, verified `content_hash`, rights/license checks, duplicate detection, versioning, or an audit trail. FastAPI routes lack `/workflows/cancel`, `/workflows/{thread_id}/events`, and `/knowledge/external/promote`.
5. **`F-17.4-005` (High / P1) — Partial Prompt-Injection Coverage:**
   - **Location:** `backend/app/services/intelligence/knowledge_rag.py` (`_INJECTION_PATTERNS`).
   - **Root Cause:** HTML `<script>` and `ignore previous instructions` are filtered, but Markdown `javascript:` links, HTML comments (`<!-- ... -->`), fenced code-block jailbreak headers (`<|im_start|>`, `ASSISTANT:`, `"role":"system"`), and JSON-embedded instruction overrides pass through unflagged.
6. **`F-17.4-006` (Medium / P1) — Missing Structured Workflow Observability & Bounded Retention:**
   - **Location:** `backend/app/services/intelligence/langgraph_workflows.py`, PostgreSQL schema.
   - **Root Cause:** No node-level timing/retry/checkpoint/failure telemetry records or safe retention cleanup that purges old terminal records while preserving active/recoverable threads.

---

## 3. Bounded Implementation Stages

- **Stage 1 (Migration + LangGraph Durable PostgreSQL Checkpointer + Confirmation Hardening):**
  - Create non-destructive additive `backend/migrations/013_phase17_4_langgraph_hardening.sql`.
  - Implement `YIPPostgresLangGraphSaver(BaseCheckpointSaver)` backed by PostgreSQL `yip_langgraph_cp_tuples` + `yip_langgraph_cp_writes` alongside optimistic version-locked `yip_langgraph_checkpoints` transitions.
  - Bind confirmations to SHA-256 `operation_hash`, `owner_id`, `workflow_name`, `workflow_version`, `confirmation_expires_at`, and single-use `confirmation_idempotency_key`; restore interrupted workflows across fresh `LangGraphWorkflowAdapter` instances ("restarts") without replaying prior nodes.
- **Stage 2 (Tavily Security, Streaming Resource Limits, Budgets, Firewall & Promotion):**
  - Harden SSRF (IPv4-mapped IPv6, integer/hex/octal IPs, CGNAT, DNS rebinding guard, strict redirect-hop validator).
  - Add streaming byte cap, concurrency semaphore, deadline enforcement, jittered backoff, owner-scoped cache isolation + LRU eviction, duplicate suppression, and global + per-owner budgets.
  - Expand prompt-injection rules and harden `promote_validated_external_item()` + API routes (`/workflows/cancel`, `/workflows/{thread_id}/events`, `/knowledge/external/promote`).
- **Stage 3 (Observability, Retention Cleanup, Fault Injection & Performance Benchmark):**
  - Implement `yip_langgraph_node_events` telemetry and `cleanup_expired_workflows()`.
  - Build comprehensive fault-injection, concurrency, multi-tenant, SSRF, restart recovery, and latency distribution (P50/P95/P99/max) test & benchmark suite (`test_phase17_4_hardening.py`).
- **Stage 4 (Regression Suites & 6 Engineering Deliverables):**
  - Run all backend Phase 16/17 + durable-job tests and frontend Vitest/Vite build; write all 6 required Phase 17.4 reports and update `EXECUTION_LEDGER.json`.
