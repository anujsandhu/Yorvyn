# Interactive 2D Pattern Editor & 2D/3D Sync Specification

Source: [Pattern2DEditor.tsx](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/components/design/Pattern2DEditor.tsx) and [garment_design_routes.py](file:///Users/anujsandhu/Projects/yorvyn/backend/app/api/garment_design_routes.py).

## 1. Capabilities

- **Renderer-Independent Model**: Consumes `DesignPatternPiece` hydrated directly from Phase 16.2 (`POST /api/garments/{garment_id}/sync-pattern`), keeping geometry authoritative regardless of Canvas2D rendering.
- **Direct Control-Point Manipulation**: Dragging any boundary vertex triggers `validatePatternPolygon2D()` (finite checks, >= 3 distinct vertices, non-zero area, strict CCW winding, non-adjacent segment self-intersection rejection) before updating design state.
- **CAD Features**:
  - 5 cm background grid + optional 1 cm vertex snap (`GRID_STEP_M = 0.01`).
  - Independent zoom (`140..700 px/m`) and canvas pan.
  - Seam allowance outer dashed offset outline.
  - Color-coded piece confidence (`OBSERVED` blue vs `INFERRED` amber), darts, grainline, and live area/perimeter readouts.
  - Independent visibility toggles: `Cut`, `Seam Allow.`, `Seams`, `Darts/Notches`, `Grain/Dims`, `Grid`.

## 2. 2D <-> 3D Synchronization Contract

- **2D -> 3D**: Bounding-box ratios `(newW/oldW, newH/oldH)` computed from validated vertex edits update the mapped bounded `GeometryDeformationParams` and `measurements` (`geometryVersion++`), immediately deforming `RealtimeMeshEditor` buffers in Three.js.
- **3D -> 2D**: Applying bounded geometry edits (`applyGeometryEdit`) proportionally scales matching `patternPieces` (`front`/`back` torso, `sleeve`, `collar`, `hem`/`waistband`) and recalculates `area_m2` and `perimeter_m` (`patternVersion++`).
- **Server Sync Validation**: `POST /api/garments/{garment_id}/sync-pattern` runs Phase 16.2 `validate_polygon_2d` on incoming overrides, rejecting self-intersections with HTTP `422` and returning regenerated `SVG`, `DXF`, and `Construction JSON`.
