# YORVYN — PHASE 17.4 SECURITY AUDIT REPORT

**Date:** 2026-11-26  
**Baseline Git HEAD:** `7139fc7eea4e1f890e28da9140db2e8550081267`  

---

## 1. Detailed Security Findings, Remediations & Evidence

### Finding `F-17.4-002` — Confirmation Replay, Tampering & Missing Expiry Binding (CRITICAL)
- **Root Cause:** `resume_workflow()` accepted boolean `human_confirmed=True` without binding to operation hash, confirmation TTL, single-use idempotency key, or atomic PostgreSQL compare-and-swap transitions.
- **Affected Files:** `backend/app/services/intelligence/langgraph_workflows.py`, `backend/app/api/intelligence_routes.py`, `backend/migrations/013_phase17_4_langgraph_hardening.sql`.
- **Reproduction:** Two concurrent calls or tampered payload after `AWAITING_CONFIRMATION` could re-invoke `execute_design`.
- **Remediation:** Bound every confirmation to `compute_operation_hash(...)`, `confirmation_expires_at`, single-use `confirmation_idempotency_key`, thread lock, and optimistic `WHERE thread_id=$1 AND version=$expected RETURNING version`; transitions follow `AWAITING_CONFIRMATION -> CONFIRMED -> EXECUTING -> SUCCEEDED` (plus `REJECTED`, `EXPIRED`, `CANCELLED`, `FAILED`, `RECOVERY_REQUIRED`).
- **Test Evidence:** `test_phase17_4_hardening.py::test_2` (concurrent resume conflict -> 1 succeeds + 1 `WorkflowConflictError`; HTTP 409/410 checks in `test_5`; expiry & tampered hash rejected).
- **Remaining Limitation:** Worker side-effect idempotency for external webhooks relies on idempotency keys (at-least-once semantics if external side-effects are later added).

### Finding `F-17.4-003` — IPv4-Mapped IPv6 SSRF Bypass & Redirect / Streaming Caps (CRITICAL)
- **Root Cause:** Observed directly on Python 3.9.6: `ipaddress.ip_address('::ffff:127.0.0.1').is_loopback` is `False`, allowing `http://[::ffff:127.0.0.1]:8000/` to bypass `validate_public_url()`. Decimal/hex/octal IPs, CGNAT `100.64.0.0/10`, `@` userinfo spoofing, redirect destinations, and pre-download streaming response byte limits were unguarded.
- **Affected Files:** `backend/app/services/intelligence/tavily_web_adapter.py`.
- **Reproduction:** Calling `ExternalKnowledgeValidator.validate_public_url("http://[::ffff:127.0.0.1]:8000/", resolve_dns=False)` returned `200`-eligible URL prior to Phase 17.4.
- **Remediation:** `_is_unsafe_ip` recursively inspects `.ipv4_mapped`, `.sixtofour`, `.teredo`, and CGNAT; regex blocks obfuscated numeric/octal/hex hosts and `@` userinfo; `validate_redirect_target` rejects private/cross-origin HTTP `3xx` hops; streaming `client.stream("POST", ...)` aborts and closes response stream above `MAX_RESPONSE_BYTES` (2 MB).
- **Test Evidence:** `test_phase17_4_hardening.py::test_3` (10 SSRF vectors, 302 localhost redirect block, >2 MB streamed payload aborted cleanly).
- **Remaining Limitation:** Application-level DNS checks reduce DNS rebinding window, but kernel/egress firewall controls are still recommended in production VPC deployment.

### Finding `F-17.4-005` — Pre-Strip HTML Comment Prompt-Injection Blind Spot (HIGH)
- **Root Cause:** `ExternalKnowledgeValidator.sanitize_external_content` stripped `<[^>]+>` BEFORE calling `sanitize_retrieved_text`, removing `<!-- system prompt override -->` without setting `injection_risk_detected=True` when surrounding text was benign. Caught by `test_4` first run!
- **Affected Files:** `backend/app/services/intelligence/tavily_web_adapter.py`, `backend/app/services/intelligence/knowledge_rag.py`.
- **Remediation:** Reordered `sanitize_external_content` to run `sanitize_retrieved_text` BEFORE `_TAG_RE` stripping and again AFTER whitespace collapse; expanded `_INJECTION_PATTERNS` for HTML comments, Markdown `javascript:`/`data:`, `<|im_start|>`, `SYSTEM:`, `"role":"system"`, and `tool_call(`.
- **Test Evidence:** `test_phase17_4_hardening.py::test_4` passed cleanly after fix.
- **Remaining Limitation:** Regex firewall is defense-in-depth; untrusted external items still keep `executable_authority = False` and remain excluded from automatic RAG ingestion.

### Finding `F-17.4-004` — External Evidence Promotion & Multi-Tenant Endpoint Coverage (HIGH)
- **Root Cause:** `promote_validated_external_item` lacked explicit approval, SHA-256 content-hash verification, domain/rights enforcement, duplicate blocking, and promotion routes; `/workflows/cancel` & `/workflows/{thread_id}/events` routes were absent.
- **Affected Files:** `backend/app/services/intelligence/unified_knowledge.py`, `backend/app/api/intelligence_routes.py`.
- **Remediation:** Required `explicit_approval=True`, non-injection, intact SHA-256 `content_hash`, approved domain or `rights_verified=True`, `ALLOWED_LICENSES`, duplicate suppression, and `PromotionAuditEntry` log; exposed owner/admin-guarded `/workflows/cancel`, `/workflows/{thread_id}/events`, `/knowledge/external/promote`.
- **Test Evidence:** `test_phase17_4_hardening.py::test_4` & `test_5` (HTTP 401 anonymous denied; HTTP 403 cross-owner status/events/resume/cancel denied).
