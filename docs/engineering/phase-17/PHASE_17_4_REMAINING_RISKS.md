# YORVYN — PHASE 17.4 REMAINING RISKS & PRODUCTION BLOCKERS

**Date:** 2026-11-26  
**Baseline Git HEAD:** `7139fc7eea4e1f890e28da9140db2e8550081267`  

---

## 1. Documented Unresolved Production Blockers

1. **BLOCKER-17.4-EXT-01 — Live Tavily Provider Verification Blocked (`NO_CREDENTIALS`):**
   - `TAVILY_API_KEY` is unconfigured (`False`) in local `.env`/environment settings. All live HTTP behavior (`/search`, `/extract`, `/research`, `/crawl`), TLS/DNS interaction with `api.tavily.com`, and live provider latency SLAs remain unverified (`knowledge.external.*` stays `DECLARED`).
2. **BLOCKER-17.4-NET-02 — Egress Network Controls Not Enforced at Kernel/VPC Layer:**
   - Application-level SSRF defenses (`ExternalKnowledgeValidator` + `follow_redirects=False` + redirect/IPv4-mapped IPv6/obfuscated IP blocking) are verified, but production deployment must pair them with host/container egress firewall rules blocking RFC1918, loopback, and cloud metadata `169.254.169.254` at the network layer.
3. **BLOCKER-17.4-DB-03 — Per-Call `asyncpg.connect()` Overhead & Process-Local Lock Scope:**
   - `YIPPostgresLangGraphSaver` and `YIPPostgresCheckpointMirror` establish short-lived per-operation `asyncpg` connections (`~5.5–6.4 ms` locally) and rely on PostgreSQL `version = version + 1` compare-and-swap across processes while keeping `threading.Lock` per thread ID in memory. Multi-worker production deployment will benefit from a shared async connection pool and SQL `SELECT ... FOR UPDATE` row locking inside multi-step transitions when horizontal scaling exceeds single-process traffic.
4. **BLOCKER-17.4-REC-04 — Real Recommendation Traffic Volume Unavailable:**
   - Local PostgreSQL contains zero real production human recommendation click/save interaction logs, keeping neural recommenders (`two_tower_recommender`, `neural_ranking_network`, `sequential_transformer_recommender`, `graph_recommendation_model`, `neural_outfit_compatibility`) unpromoted (`promotion_approved=false`) in favor of Phase 17.0 `fashion-recommendation-engine`.
5. **BLOCKER-17.4-OBS-05 — Supabase Remote Profile Sync Unreachable Offline:**
   - In offline sandboxes without internet DNS, `PreferenceProfileStore(sync_remote=True)` emits HTTPS connection warnings before falling back to local state (`sync_remote=False` cleanly isolates offline benchmarks).
