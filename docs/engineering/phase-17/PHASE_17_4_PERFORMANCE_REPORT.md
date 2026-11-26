# YORVYN — PHASE 17.4 PERFORMANCE REPORT

**Date:** 2026-11-26  
**Baseline Git HEAD:** `7139fc7eea4e1f890e28da9140db2e8550081267`  
**Hardware / Runtime Environment:** `macOS-27.2.1-arm64-arm-64bit`, `Python 3.9.6`, PostgreSQL `16.14`, Peak Process RSS `448.42 MB`.  

> **Scope Disclaimer:** These measurements are local microbenchmarks (`n=10` to `n=25`) separating real local PostgreSQL operations from mocked `httpx.MockTransport` Tavily latencies. They do not represent a hosted multi-region production SLA, and live Tavily provider latency could not be measured because `TAVILY_API_KEY` is unconfigured.

---

## 1. Reproducible Latency Distribution Table (Observed Tool Output)

| Metric / Operation | Environment | Samples (`n`) | P50 (ms) | P95 (ms) | P99 (ms) | Max (ms) |
|---|---|---|---|---|---|---|
| Workflow Graph Compilation | Local Python + LangGraph `0.6.9` | 10 | `12.982` | `16.243` | `16.244` | `16.244` |
| Cold Execution (`garment.research`, internal RAG) | Local Python + PG | 1 | — | — | — | `135.010` |
| Warm Paused Execution (`design.assistance`) | Local Python + PG `16.14` | 25 | `56.224` | `65.749` | `66.123` | `66.241` |
| PostgreSQL Checkpoint Write (`YIPPostgresCheckpointMirror`) | Real Local PG `16.14` | 25 | `6.353` | `7.917` | `8.537` | `8.731` |
| PostgreSQL Checkpoint Restore (`force_pg=True`) | Real Local PG `16.14` | 25 | `5.542` | `6.612` | `12.872` | `14.818` |
| Full Restart Recovery + Resume (`Command(resume=True)`) | Real Local PG `16.14` (fresh adapter) | 25 | `79.515` | `127.368` | `136.457` | `137.359` |
| Concurrent 8-Workflow Burst Wall Time | Real Local PG `16.14` | 8 | — | — | — | `479.915` (wall) |
| Tavily Search Cache Miss (`httpx.MockTransport`) | **Mocked HTTP Provider** | 25 | `0.003` | `1.724` | `30.736` | `39.797` |
| Tavily Search Cache Hit | **In-Memory LRU Cache** | 25 | `0.003` | `0.067` | `0.180` | `0.214` |
