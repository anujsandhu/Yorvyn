# YORVYN — PHASE 17.4 CAPABILITY REGISTRY DIFF & LIFECYCLE CLASSIFICATIONS

**Date:** 2026-11-26  
**Baseline Git HEAD:** `7139fc7eea4e1f890e28da9140db2e8550081267`  

---

## 1. Registry Additions & Updates (`capability_registry.py`)

| Capability ID | Lifecycle State | What Changed in Phase 17.4 | Honest Justification |
|---|---|---|---|
| `knowledge.external.promote` *(NEW)* | `EXECUTABLE` | Added explicit approval, SHA-256 content-hash, rights/license, duplicate suppression, and promotion audit gate (`UnifiedKnowledgeCoordinator.promote_validated_external_item`) + admin route | Executes locally and verified in unit/API tests with clean audit trail |
| `workflow.garment.research` | `EXECUTABLE` | Upgraded limitation metadata; backed by `YIPPostgresLangGraphSaver` tuple/write persistence + node observability | Tested end-to-end against real local PG 16.14; external web branch remains gated/mocked without `TAVILY_API_KEY` |
| `workflow.fashion.discovery` | `EXECUTABLE` | Preserved consent & owner profile boundaries under hard durability & concurrency locks | Verified across repeated discovery runs |
| `workflow.design.assistance` | `EXECUTABLE` | Bound confirmation to `operation_hash`, TTL, single-use idempotency key, optimistic PG locks, and `Command(resume=True)` restart recovery without node replay | Verified across fresh adapter restarts against real local PG 16.14 |
| `knowledge.external.search` | `DECLARED` | Security/SSRF/streaming/budget hardening applied, but kept strictly `DECLARED` | Cannot promote to `VERIFIED` without live `TAVILY_API_KEY` verification |
| `knowledge.external.extract` | `DECLARED` | Redirect/SSRF/byte-cap hardening applied, kept `DECLARED` | Cannot promote to `VERIFIED` without live credentials |
| `knowledge.external.research` | `DECLARED` | Deadline/budget/sanitization hardening applied, kept `DECLARED` | Cannot promote to `VERIFIED` without live credentials |
| `recommendation.outfit_neural` *(Neural Track)* | `DECLARED` | Integrated symmetric multi-item compatibility + algorithmic fallback | Blocked from promotion (`minimum_real_volume`) pending live traffic |
| `recommendation.experiment` *(Neural Track)* | `EXECUTABLE` | Owner-isolated bucketing, outcome logging, `MIN_IMPRESSIONS_FOR_POWER=100` | Verified locally |
| `recommendation.promote` *(Neural Track)* | `EXECUTABLE` | Multi-gate promotion blocker preserving Phase 17.0 default | Blocks unverified promotion cleanly |
