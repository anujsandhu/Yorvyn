# Pattern Geometry Schema Specification (`16.2.0`)

Source definition: `backend/app/services/garments/reconstruction/pattern_geometry.py`.

## 1. Enumerations

- `EdgeRole`: `SEWN`, `FOLDED`, `BOUND`, `HEMMED`, `OPEN`, `ZIPPER_ATTACHMENT`, `POCKET_ATTACHMENT`, `COLLAR_ATTACHMENT`, `SLEEVE_ATTACHMENT`, `LINING_ATTACHMENT`
- `EdgeDirection`: `FORWARD`, `REVERSE`, `SYMMETRIC`
- `ConstructionVerificationState`: `OBSERVED`, `INFERRED`, `AMBIGUOUS`, `UNSUPPORTED`
- `DimensionSourceKind`: `DIRECTLY_MEASURED`, `IMAGE_DERIVED`, `CATEGORY_PRIOR`, `UNOBSERVABLE`
- `PatternPieceType`: `front_body`, `back_body`, `left_sleeve`, `right_sleeve`, `sleeve_cuff`, `collar`, `collar_stand`, `hood_panel`, `pocket`, `waistband`, `placket`, `lining`, `gusset`, `hem_facing`, `front_leg`, `back_leg`, `fly_shield`, `bodice_front`, `bodice_back`, `skirt_front`, `skirt_back`, `side_panel`, `lehenga_gore`

## 2. Core Contracts

### `PatternPiece2D`
Represents a single flat garment panel in local metric coordinates (meters):
- `piece_id`, `piece_type`, `name`, `parent_component`, `side_or_orientation`
- `boundary_polygon`: ordered `List[Point2DPattern]` validated to be finite, >= 3 distinct vertices, non-degenerate, non-self-intersecting, and counter-clockwise (`signed_polygon_area > 0`)
- `edges`: ordered `List[PatternEdge]`, where curved armholes, sleeve caps, necklines, and trouser rises include `CubicBezierSegment` (`p0`, `p1`, `p2`, `p3`) and discrete sampled polyline length (`length_m`)
- `notches`: `List[PatternNotch]` (`notch_id`, `edge_id`, `position_t`, `style`)
- `darts`: `List[PatternDart]` (`apex`, `base_left`, `base_right`, `depth_m`, `angle_deg`)
- `fold_lines`, `internal_lines`: `List[InternalConstructionLine]` (e.g. `fold_line`, `slit_marker`)
- `grainline`: `Grainline2D` (`start`, `end`, `angle_deg`, `direction`)
- `dimensions`: `Dict[str, MeasuredDimension]` tracking value (`value_m`), `source` (`DimensionSourceKind`), `confidence`, `uncertainty_m`, and `evidence_refs`
- `area_m2`, `perimeter_m`, `seam_allowance_m`, `material_ref`
- `evidence_refs`, `source_views`, `verification_state`, `confidence`, `uncertainty`

### `SeamConnection`
Explicit directed sewing / attachment edge between `(piece_a, edge_a)` and `(piece_b, edge_b)` carrying `seam_type` (`EdgeRole`), `matching_direction`, `edge_a_length_m`, `edge_b_length_m`, `ease_allowance_m`, `seam_allowance_m`, `confidence`, `uncertainty`, `verification_state`, and `source_evidence`.

### `UnifiedConstructionGraphContract` & `ConstructionToGeometryHandoff`
Unites `pieces`, `seams`, `assembly_order`, `assembly_dependencies` (validated DAG edges), `inference_records`, `validation_report` (`AssemblyValidationReport`), `target_engine_id`, `engine_compatible`, `measurements`, `material_references`, and separated lists (`evidence_supported_features`, `inferred_features`, `missing_or_ambiguous_features`, `invalid_features`).

## 3. Computational Geometry Checks (Without `shapely`)

Because `shapely`, `ezdxf`, and `svgwrite` are absent from the runtime environment, `pattern_geometry.py` implements self-contained deterministic computational geometry:
- **Shoelace signed area** (`signed_polygon_area`): enforces CCW outer contour orientation.
- **Degenerate / duplicate vertex check**: rejects consecutive edges shorter than `1e-5` m and duplicate vertices.
- **Non-adjacent segment intersection** (`segments_intersect`): detects self-intersecting bowtie polygons cleanly.
- **Seam-allowance offset** (`compute_seam_allowance_polygon`): outward edge-normal bisector offset for cutting sheets and DXF `SEAM_ALLOWANCE` layers.
