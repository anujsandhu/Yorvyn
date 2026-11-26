# YORVYN Phase 16.3.1 — Bidirectional Design Synchronization Contract

**Version:** `16.3.1`  
**Primary Modules:**
- Backend: [`backend/app/services/intelligence/semantic_correspondence.py`](../../../backend/app/services/intelligence/semantic_correspondence.py) & [`backend/app/api/garment_design_routes.py`](../../../backend/app/api/garment_design_routes.py)
- Frontend: [`frontend/src/engine/designStudio/DesignStateEngine.ts`](../../../frontend/src/engine/designStudio/DesignStateEngine.ts) & [`frontend/src/engine/designStudio/SemanticCorrespondenceEngine.ts`](../../../frontend/src/engine/designStudio/SemanticCorrespondenceEngine.ts)

---

## 1. Seven-State SyncStatus Contract

Both client (`DesignStateEngine`) and server (`TransactionalDesignEngine`) emit an explicit `SyncStatus`:

| State | Meaning | Behavior |
|---|---|---|
| `SYNCHRONIZED` | Correspondence map, 2D pattern graph, extended construction validator, and 3D mesh topology match with full observed backing | All edits & exports enabled |
| `SYNCHRONIZED_WITH_UNCERTAINTY` | 2D–3D correspondence and topology invariants hold, while one or more seams/panels rely on analytical `INFERRED` geometry | Edits & exports enabled; UI surfaces uncertainty count explicitly |
| `REQUIRES_REBUILD` | Major category/structural edit requires fresh Phase 16.2/3D reconstruction before continuing incremental transforms | Blocks incremental GLB deformation until rebuild |
| `MAPPING_INVALID` | Topology signature changed (`vertexCount`, `triangleCount`, or `componentIdsHash` mismatch against bound map) | Increments `correspondenceVersion`, blocks unsynced mesh writes until rebuilt |
| `CONSTRUCTION_CONFLICT` | Optimistic concurrency version mismatch (`expectedVersion != currentVersion`, HTTP `409 Conflict`) or cross-panel length/symmetry violation | Rejects overwrite and preserves prior state |
| `VALIDATION_FAILED` | Self-intersecting polygon, degenerate area, seam allowance outside `[0.005, 0.030] m`, disconnected seam DAG, or invalid 3D mesh | Aborts atomic transaction and rolls back cleanly |
| `NOT_SUPPORTED` | Operation lacks a valid mapping for the current garment category or missing component (e.g. trouser leg scale on a jacket) | Explicit `NOT_SUPPORTED` failure without guessing geometry |

---

## 2. Topology-Change Invalidation Rules

`TopologySignature` records `(vertexCount, triangleCount, componentIdsHash)`.

When reloading GLB geometry, swapping candidates, or altering vertex/triangle counts:
1. `validateCorrespondenceAgainstTopology` / `validateMappingTopology` compares live mesh counts and component hashes against the active `SemanticCorrespondenceMap`.
2. Any mismatch immediately transitions `syncStatus` to `MAPPING_INVALID`.
3. Silently applying old bounding-box offsets to rebuilt or re-indexed geometry is disallowed; the caller must rebuild via `DesignStateEngine.rebuildCorrespondence(...)` or `POST /api/garments/{id}/transactions/execute`.

---

## 3. Evidence & Uncertainty Preservation

Downstream edits NEVER erase Phase 16.1/16.2 uncertainty:
- Pieces marked `INFERRED` (such as occluded rear panels generated from silhouette cues) retain `evidence_support.source_status = "INFERRED"`.
- Validating a fully connected graph with inferred back panels produces `SYNCHRONIZED_WITH_UNCERTAINTY` rather than falsely claiming full multi-view observation (`SYNCHRONIZED`).
- Stylist commands (`parse_stylist_design_command`) inspect bounded targets (`torso_width`, `sleeve_length`, `collar_width`, `leg_width`, `hem_width`, `pocket_position`) without modifying unrelated panels.
