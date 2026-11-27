# YORVYN Phase 16.3.1 — Transactional Design Engine Architecture

**Primary Module:** [`backend/app/services/garments/transactional_design_engine.py`](../../../backend/app/services/garments/transactional_design_engine.py)  
**HTTP Routes:** [`backend/app/api/garment_design_routes.py`](../../../backend/app/api/garment_design_routes.py) (`GET /correspondence`, `POST /transactions/execute`, `POST /revisions`, `POST /sync-pattern`, `POST /candidate-edit-gl`)

---

## 1. Candidate-First 13-Stage Atomic Execution Model

Design edits never mutate committed garment state or revision history in place. Instead, `TransactionalDesignEngine.execute_transaction` runs an isolated candidate transaction:

1. **Snapshot capture:** Read current committed `design_version`, `geometry_version`, `pattern_version`, `material_version`.
2. **Idempotency & optimistic concurrency:** If `request_id` already committed on this `(user_id, garment_id)` stream, return the existing revision without duplicate writes; if `expected_parent_version != current_version`, abort immediately with `CONSTRUCTION_CONFLICT` (HTTP `409 Conflict`).
3. **Operation support check:** Validate requested `operation_name` against `SEMANTIC_OPERATION_SPECS` and category (`NOT_SUPPORTED` if unsupported).
4. **Candidate construction & scoped overrides:** Build candidate `UnifiedConstructionGraphContract` via `pattern_construction_engine`, apply explicit polygon overrides and/or scoped `+cm` ease (`apply_panel_ease_to_chest`).
5. **Candidate 3D GLB deformation:** If `glb_base64` is supplied, mutate only targeted GLTF `node`/`extras.component_id` meshes via `apply_parametric_design_edit`.
6. **Semantic correspondence generation:** Build versioned `16.3.1` `SemanticCorrespondenceMap` (`build_semantic_correspondence`).
7. **Cancellation / timeout checkpoint:** Abort cleanly if `cancel_event` is triggered before commit.
8. **Extended construction validation:** Run `validate_extended_construction` (disconnected panels, symmetry, seam allowances, orphan notches, `AssemblyValidator`).
9. **3D mesh structural validation:** Run `MeshValidationService.validate_glb_bytes` on candidate GLB bytes.
10. **Pattern & DXF/SVG/JSON exportability verification:** Smoke-check `export_pattern_json`, `export_pattern_svg`, and `export_pattern_dxf` cleanly without committing partial files.
11. **Correspondence topology verification:** Validate `(vertex_count, triangle_count, component_ids_hash)` invariants (`validate_correspondence_against_topology`).
12. **Atomic persistence commit:** Persist `GarmentDesignRevision` (carrying `request_id`, `correspondence_version`, `sync_status`, `mapping_hash`, `scoped_measurements`, `validation_summary`) through `design_revision_service.save_revision` (PostgreSQL `yorvyn_garment_design_revisions` when configured, process-safe memory fallback with rollback on failure).
13. **Commit result emission:** Return committed `DesignTransactionResult` with `edited_glb_base64`, `correspondence`, `validation_report`, `scoped_measurements`, and `transaction_ms`.

---

## 2. Failure & Rollback Guarantees Tested

- **Pre-commit failure (polygon / symmetry / seam allowance):** Returns `committed=False, rolled_back=True, sync_status="VALIDATION_FAILED"`; revision count remains unchanged.
- **Topology mismatch (`expected_vertex_count` / `expected_triangle_count` mismatch):** Aborts with `sync_status="MAPPING_INVALID"` without saving a revision.
- **Cancelled mid-flight (`threading.Event.set()`):** Aborts cleanly with `stage_failed="cancelled"` and zero side effects.
- **Stale parent revision:** Returns HTTP `409 Conflict` (`CONSTRUCTION_CONFLICT`) with zero overwrite.
- **Duplicate `request_id`:** Replays the original committed revision idempotently.
