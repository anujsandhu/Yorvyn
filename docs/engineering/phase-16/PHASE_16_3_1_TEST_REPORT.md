# YORVYN Phase 16.3.1 — Test, Latency & Verification Report

**Date:** 2026-11-25  
**Baseline Commit:** `7139fc7eea4e1f890e28da9140db2e8550081267`  
**Phase Status:** Implementation & Verification Passing (Scientific CAD Sewing & Physical Simulation Accuracy Remain Explicitly Unclaimed Without Benchmark Datasets)

---

## 1. Test Suites Executed After Final Code Edit

| Suite / Command | Scope | Result | Timing |
|---|---|---|---|
| `backend/tests/test_phase16_3_1_transactional_sync.py` | Scoped ease reconciliation (`21.75 -> 24.75 cm`), topology invalidation (`MAPPING_INVALID`), extended validator (disconnected, symmetry, seam allowance, orphan notches), 13-stage atomic rollback/idempotency/cancellation, FastAPI `correspondence` / `transactions/execute` / `sync-pattern` / Stylist commands | **5 passed** | Run with 16.3 suite: 5.13s |
| Full Backend Regression (`17` suites, `backend/tests/`) | Phase 3–7, 15.4, 15.5, 16.0, 16.1, 16.2, 16.3, 16.3.1, AI sessions, stylist chat edits, hybrid orchestration | **246 passed** | 35.07s |
| Full Frontend Vitest (`27` files, `npm test -- --run`) | Includes `designStudioPhase16_3_1.test.ts` (4 tests) & `designStudioPhase16_3.test.ts` (5 tests) | **364 passed across 27 files** | 4.81s |
| Production Frontend Build (`tsc && vite build`) | Strict TypeScript compilation + Vite production bundle | **Exited 0** (`6.55s`) | 6.55s |
| Live Chromium E2E (`verify_phase16_3_browser.py` -> [`PHASE_16_3_1_BROWSER_EVIDENCE.json`](../../reports/PHASE_16_3_1_BROWSER_EVIDENCE.json)) | Real jacket photo upload (`wm_00_jacket_denim.jpg`), Design Studio 3D WebGL2 canvas, `+3 cm Panel Ease`, Undo/Redo, Wireframe/Seams toggles, Stylist quick command, `Validate & Sync Graph`, `Save Revision v1` (PostgreSQL), `1,631,028`-byte GLB export, WebGL context-loss recovery, viewport resize, `Wear on Avatar` | **PASSED** (`0` page errors) | SwiftShader headless Chromium |

---

## 2. Live Browser Chromium Evidence Summary

- **Telemetry HUD:** `Backend: webgl2 (high) | WebGPU: adapterFPS: 60.1 (16.64ms) | Calls: 20 | Tris: 7808` (headless Chromium with SwiftShader software rasterizer — **not** claimed as native hardware GPU performance).
- **Sync Status Badge:** `Design v5 | Geom v4 | Pattern v5 | Mat v4 | Sync: SYNCHRONIZED_WITH_UNCERTAINTY`
- **Scoped Measurements Before `+3 cm Panel Ease`:**  
  `Synced Measurements (PATTERN_PANEL_HALF): Panel 21.8 cm | Half Chest 43.5 cm | Circumference 87.0 cm | Length 52.0 cm | SA 1.0 cm` (`21.75 cm` net panel width rounded to 1 decimal place).
- **Scoped Measurements After `+3 cm Panel Ease`:**  
  `Synced Measurements (PATTERN_PANEL_HALF): Panel 24.8 cm | Half Chest 49.5 cm | Circumference 99.0 cm | Length 52.0 cm | SA 1.0 cm` (`24.75 cm` net panel width -> exact `+3.0 cm` panel delta, `+6.0 cm` half-chest symmetric, `+12.0 cm` full circumference symmetric).
- **Undo / Redo:** `undo_restored: true`, `redo_reapplied: true`.
- **GLB Export SHA-256:** `afeef09847bbd1734140011fc3dad415babbc5ac43501ef9f7638f032be0d107` (`1,631,028` bytes).

---

## 3. Observed Server-Side Overhead Benchmarks

Measured directly with Python `time.perf_counter()` on Apple Silicon M2 (`4,316`-byte multi-component rigged jacket GLB, `144` vertices / `216` triangles in test fixture):

| Operation | Measured Latency |
|---|---|
| `build_semantic_correspondence` (`16.3.1` map construction) | `0.212 ms` |
| `validate_correspondence_against_topology` | `0.006 ms` |
| `validate_extended_construction` (DAG connectivity + symmetry + seam allowance + notches) | `1.423 ms` |
| `apply_parametric_design_edit` (component-targeted GLB mutation) | `0.389 ms` |
| `TransactionalDesignEngine.execute_transaction` (full 13-stage candidate + validation + commit) | `12.44 ms` (`tx_reported_ms`: `12.37 ms`) |

*Note: All latency numbers above reflect synthetic fixture / SwiftShader execution environments observed in test runs and do not assert native GPU throughput or large high-poly production mesh timings beyond the `7,808`-triangle browser test fixture.*
