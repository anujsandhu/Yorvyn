# YORVYN Phase 16.3.1 — Extended Construction Constraint Validation

**Primary Module:** [`backend/app/services/garments/transactional_design_engine.py`](../../../backend/app/services/garments/transactional_design_engine.py) (`validate_extended_construction`)  
**Client Geometry Guards:** [`frontend/src/engine/designStudio/DesignStateEngine.ts`](../../../frontend/src/engine/designStudio/DesignStateEngine.ts) (`validatePatternPolygon2D`)

---

## 1. Validation Gates Executed Before Commit

Every pattern edit (2D vertex drag, panel ease, Stylist parametric command, or pattern sync) must pass both base geometric/DAG validation (`AssemblyValidator.validate`) and Phase 16.3.1 extended construction rules:

| Rule Code | Scope | Check & Rejection Criterion |
|---|---|---|
| `SELF_INTERSECTION` / `WINDING` | Per-piece 2D boundary | Minimum 3 non-collinear vertices, strict positive non-self-intersecting area (`>= 0.0005 m²`), CCW orientation |
| `ASSEMBLY_SEAM_LENGTH` | Every seam edge pair | Edge-to-edge Euclidean length mismatch checked against `SEAM_LENGTH_TOLERANCE_M` (inherited from `AssemblyValidator`) |
| `DISCONNECTED_PATTERN_PANELS` | Whole construction graph | BFS traversal across `graph.seams` from anchor piece verifies single connected garment assembly (isolated pieces fail `is_valid=False`) |
| `SYMMETRY_VIOLATION` | Bilaterally paired panels | Left/right mates (`front_left_body`/`front_right_body`, `sleeve_left`/`sleeve_right`, `cuff_left`/`cuff_right`, leg pairs) checked for X-span delta within `0.025 m` unless asymmetric styling is explicit |
| `INVALID_SEAM_ALLOWANCE` | Per-piece seam allowance | Enforces realistic sewing seam allowance bounds `0.005 m <= seam_allowance_m <= 0.030 m` (5 mm to 30 mm) |
| `ORPHAN_NOTCH_REFERENCE` | Per-piece registration notches | Warning emitted if notch indices fall outside valid polygon vertex count |
| `MANIFOLD_3D_MESH` | Candidate GLB binary | `MeshValidationService.validate_glb_bytes` verifies non-empty geometry, finite bounds, and valid category anthropometric envelope |

---

## 2. Failure & Rollback Guarantees

If any validation rule fails during `POST /api/garments/{id}/sync-pattern` or `POST /api/garments/{id}/transactions/execute`:
- `is_valid` is returned `false` with structured `AssemblyValidationIssue` codes (`code`, `severity`, `message`, `affected_pieces`, `affected_seams`).
- No candidate pattern, GLB binary, correspondence hash, or revision record is committed.
- Existing committed revision history remains intact.
