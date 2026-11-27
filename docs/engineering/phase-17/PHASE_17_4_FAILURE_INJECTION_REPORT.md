# YORVYN — PHASE 17.4 FAILURE-INJECTION & RECOVERY REPORT

**Date:** 2026-11-26  
**Baseline Git HEAD:** `7139fc7eea4e1f890e28da9140db2e8550081267`  

---

## 1. PostgreSQL & Restart Recovery Tests `[REAL_POSTGRES]`

| Scenario | Mechanism Under Test | Observed Result |
|---|---|---|
| Process restart during paused `design.assistance` interrupt | Fresh `LangGraphWorkflowAdapter`, `YIPPostgresCheckpointMirror`, & `YIPPostgresLangGraphSaver` (empty RAM) restore checkpoint tuple (`yip_langgraph_cp_tuples`) & resume via `Command(resume=True)` | Passed: restored `operation_state == "SUCCEEDED"`; `interpret_design`, `identify_components`, `validate_capability` executed exactly once (zero node replay) |
| Concurrent resumes against single `thread_id` | Per-thread lock + optimistic PG `version = version + 1` compare-and-swap (`WorkflowConflictError` / HTTP 409) | Passed: exactly 1 succeeds, 2nd raises `WorkflowConflictError` / returns HTTP 409 |
| Expired confirmation TTL | `confirmation_expires_at` validated before transition (`ConfirmationExpiredError` / HTTP 410) | Passed: transitions thread to `EXPIRED` cleanly |
| Stale worker write (`expected_version=999999`) | Optimistic locking check in `YIPPostgresCheckpointMirror.save()` | Passed: raises `WorkflowConflictError` |
| PostgreSQL unreachable (`127.0.0.1:1`) | Fallback without fabricating `pg_persisted=True` (`strict_pg=True` raises cleanly) | Passed: `pg_persisted is False`, `checkpoint_backend == "langgraph_memory"` |
| Terminal retention cleanup vs active pause | `cleanup_expired_workflows(max_age_seconds=0.0)` | Passed: deletes terminal rows only; preserves active `AWAITING_CONFIRMATION` thread |

---

## 2. Redis & Durable Job Outbox Checks `[REAL_POSTGRES_REDIS]`

| Scenario | Observed Result |
|---|---|
| Live Redis connectivity (`redis://localhost:6379/0`) | `PING -> True` |
| Transactional outbox, enqueue crash window, stale lease fencing & recovery | `test_durable_job_outbox_fault_injection.py` & `test_durable_job_publication_fix.py` passed inside 11-suite regression (`113 passed`) |

---

## 3. Tavily Provider Fault-Injection & Budget Tests `[MOCKED_PROVIDER]`

> **Honest Scope:** `TAVILY_API_KEY` is unconfigured (`False`), so live Tavily HTTP endpoints remain `BLOCKED_NO_CREDENTIALS`. All fault-injection tests below used `httpx.MockTransport`.

| Scenario | Observed Result |
|---|---|
| Missing API key | Returns `status="BLOCKED_NO_CREDENTIALS"`, `results=[]`, zero network calls |
| HTTP 401 / 403 invalid credentials | Immediate non-retried failure `AUTH_ERROR_401`, increments failure telemetry |
| HTTP 302 redirect to `http://127.0.0.1/meta` | Blocked with `REDIRECT_BLOCKED_SSRF`, `redirect_blocked` telemetry incremented |
| Streamed payload > `2 MB` (`MAX_RESPONSE_BYTES`) | Aborted & closed with `RESPONSE_TOO_LARGE` before unbounded buffering |
| Malformed JSON response | Rejected cleanly (`ERROR` status) without crashing orchestrator |
| Repeated HTTP 500 outages | Opens circuit breaker cleanly (`status="CIRCUIT_OPEN"`) after `failure_threshold` |
| Per-owner & global credit budget exhaustion | Enforces `OWNER_BUDGET_EXCEEDED` and `GLOBAL_BUDGET_EXCEEDED` (`BUDGET_EXCEEDED` status) |
| Multi-tenant cache isolation | Same query from `owner_2` never hits `owner_1`'s cached entry |
