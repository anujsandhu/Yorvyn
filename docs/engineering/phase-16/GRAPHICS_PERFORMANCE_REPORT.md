# Phase 16.3 Graphics Performance & Browser Telemetry Report

Evidence file: [PHASE_16_3_BROWSER_PERF_EVIDENCE.json](file:///Users/anujsandhu/Projects/yorvyn/docs/reports/PHASE_16_3_BROWSER_PERF_EVIDENCE.json).

## 1. Measured Real Browser Execution (`wm_00_jacket_denim.jpg`)

Executed via `backend/venv/bin/python scripts/verify_phase16_3_browser.py data/datasets/phase_13_6_real_photos/wm_00_jacket_denim.jpg` against disposable PostgreSQL + Redis + FastAPI + Vite + headless Chromium (`--enable-unsafe-swiftshader`):

| Metric / Probe | Measured Observation |
| --- | --- |
| Active Graphics Backend | `webgl2` (device capability tier: `high`) |
| WebGPU Adapter Detection (`navigator.gpu`) | Adapter probe reported available; production viewport cleanly maintained WebGL2 path |
| Real-Time Frame Rate / Frame Time | **60 FPS** (`16.67 ms` per frame reported by Chromium HUD) |
| Draw Calls & Triangle Count | **20 draw calls**, **7,808 triangles** for live multi-node denim jacket |
| 2D -> 3D Pattern Sync | `+3 cm Panel Ease` updated synced Chest measurement **`54.0 cm -> 61.5 cm`** immediately |
| Undo / Redo Round-Trip | `undo_restored: true`, `redo_reapplied: true` |
| Edited GLB Export Size & Hash | `1,631,028` bytes (`sha256: bd059b97e03e62ae55d31de3cdf56eb6669e24c699449de12f342cf7fd8e854f`), `glTF` binary valid |
| Context Loss & Resize Resilience | Viewport resize (`1440x1000 -> 1180x820`) + simulated `webglcontextlost`/`webglcontextrestored` passed (`page_errors: []`) |
| Avatar Attachment | **Wear on Avatar** fitted custom edited jacket onto `AvatarStudioViewer` (`Fitted custom 3D` verified) |

## 2. Optimization Measures Applied

- Single immutable `WeakMap<THREE.Mesh, RestMeshBuffers>` avoids cloning vertex buffers across sliders or undo/redo snapshots.
- Cached procedural weave and UV checker `CanvasTexture` instances reused and explicitly disposed on unmount.
- In-place `BufferAttribute.needsUpdate = true` mutations decouple interactive sliders (zero server round-trip) from full skeletal GLB rebuilds (`candidate-edit-gl` on export / avatar drape).

*Note*: Metrics above were measured in headless Chromium (`--enable-unsafe-swiftshader`). Native client GPU performance varies by browser and hardware; WebGPU native rendering frame-rate benchmarks remain unmeasured and gated.
