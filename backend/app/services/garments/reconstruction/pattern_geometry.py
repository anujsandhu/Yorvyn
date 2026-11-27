"""Phase 16.2 2D pattern geometry, edge/seam contracts, and computational geometry validation."""
from __future__ import annotations

from enum import Enum
import math
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field


CONSTRUCTION_SCHEMA_VERSION = "16.2.0"


class EdgeRole(str, Enum):
    SEWN = "SEWN"
    FOLDED = "FOLDED"
    BOUND = "BOUND"
    HEMMED = "HEMMED"
    OPEN = "OPEN"
    ZIPPER_ATTACHMENT = "ZIPPER_ATTACHMENT"
    POCKET_ATTACHMENT = "POCKET_ATTACHMENT"
    COLLAR_ATTACHMENT = "COLLAR_ATTACHMENT"
    SLEEVE_ATTACHMENT = "SLEEVE_ATTACHMENT"
    LINING_ATTACHMENT = "LINING_ATTACHMENT"


class EdgeDirection(str, Enum):
    FORWARD = "FORWARD"
    REVERSE = "REVERSE"
    SYMMETRIC = "SYMMETRIC"


class ConstructionVerificationState(str, Enum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"


class DimensionSourceKind(str, Enum):
    DIRECTLY_MEASURED = "DIRECTLY_MEASURED"
    IMAGE_DERIVED = "IMAGE_DERIVED"
    CATEGORY_PRIOR = "CATEGORY_PRIOR"
    UNOBSERVABLE = "UNOBSERVABLE"


class PatternPieceType(str, Enum):
    FRONT_BODY = "front_body"
    BACK_BODY = "back_body"
    LEFT_SLEEVE = "left_sleeve"
    RIGHT_SLEEVE = "right_sleeve"
    SLEEVE_CUFF = "sleeve_cuff"
    COLLAR = "collar"
    COLLAR_STAND = "collar_stand"
    HOOD_PANEL = "hood_panel"
    POCKET = "pocket"
    WAISTBAND = "waistband"
    PLACKET = "placket"
    LINING = "lining"
    GUSSET = "gusset"
    HEM_FACING = "hem_facing"
    FRONT_LEG = "front_leg"
    BACK_LEG = "back_leg"
    FLY_SHIELD = "fly_shield"
    BODICE_FRONT = "bodice_front"
    BODICE_BACK = "bodice_back"
    SKIRT_FRONT = "skirt_front"
    SKIRT_BACK = "skirt_back"
    SIDE_PANEL = "side_panel"
    LEHENGA_GORE = "lehenga_gore"


class Point2DPattern(BaseModel):
    model_config = ConfigDict(frozen=True)
    x: float
    y: float


class CubicBezierSegment(BaseModel):
    model_config = ConfigDict(frozen=True)
    p0: Point2DPattern
    p1: Point2DPattern
    p2: Point2DPattern
    p3: Point2DPattern

    def sample(self, steps: int = 10) -> List[Point2DPattern]:
        pts: List[Point2DPattern] = []
        n = max(2, steps)
        for i in range(n + 1):
            t = i / float(n)
            u = 1.0 - t
            x = (u ** 3) * self.p0.x + 3 * (u ** 2) * t * self.p1.x + 3 * u * (t ** 2) * self.p2.x + (t ** 3) * self.p3.x
            y = (u ** 3) * self.p0.y + 3 * (u ** 2) * t * self.p1.y + 3 * u * (t ** 2) * self.p2.y + (t ** 3) * self.p3.y
            pts.append(Point2DPattern(x=round(x, 6), y=round(y, 6)))
        return pts


class PatternNotch(BaseModel):
    notch_id: str
    edge_id: str
    position_t: float = Field(..., ge=0.0, le=1.0)
    style: str = "single"  # single | double | center


class PatternDart(BaseModel):
    dart_id: str
    apex: Point2DPattern
    base_left: Point2DPattern
    base_right: Point2DPattern
    depth_m: float = Field(..., gt=0.0)
    angle_deg: float = Field(..., ge=0.0, le=90.0)


class Grainline2D(BaseModel):
    start: Point2DPattern
    end: Point2DPattern
    angle_deg: float = 90.0
    direction: str = "warp"


class InternalConstructionLine(BaseModel):
    line_id: str
    kind: str  # fold_line | pocket_placement | closure_placement | waist_line | slit_marker
    points: List[Point2DPattern]


class MeasuredDimension(BaseModel):
    name: str
    value_m: Optional[float] = None
    source: DimensionSourceKind
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    uncertainty_m: Optional[float] = Field(default=None, ge=0.0)
    evidence_refs: List[str] = Field(default_factory=list)


class PatternEdge(BaseModel):
    edge_id: str
    role: EdgeRole
    vertices: List[Point2DPattern]
    bezier: Optional[CubicBezierSegment] = None
    length_m: float = Field(..., ge=0.0)
    direction: EdgeDirection = EdgeDirection.FORWARD
    seam_allowance_m: float = Field(default=0.01, ge=0.0)
    ease_allowance_m: float = Field(default=0.0, ge=0.0)


class PatternPiece2D(BaseModel):
    piece_id: str
    piece_type: PatternPieceType
    name: str
    parent_component: str
    side_or_orientation: Optional[str] = None
    boundary_polygon: List[Point2DPattern]
    edges: List[PatternEdge]
    notches: List[PatternNotch] = Field(default_factory=list)
    darts: List[PatternDart] = Field(default_factory=list)
    fold_lines: List[InternalConstructionLine] = Field(default_factory=list)
    internal_lines: List[InternalConstructionLine] = Field(default_factory=list)
    grainline: Grainline2D
    seam_allowance_m: float = Field(default=0.01, ge=0.0)
    material_ref: str = "main_shell"
    dimensions: Dict[str, MeasuredDimension] = Field(default_factory=dict)
    area_m2: float = 0.0
    perimeter_m: float = 0.0
    evidence_refs: List[str] = Field(default_factory=list)
    source_views: List[str] = Field(default_factory=list)
    verification_state: ConstructionVerificationState = ConstructionVerificationState.INFERRED
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)


class SeamConnection(BaseModel):
    seam_id: str
    piece_a: str
    edge_a: str
    piece_b: str
    edge_b: str
    seam_type: EdgeRole
    matching_direction: EdgeDirection = EdgeDirection.FORWARD
    edge_a_length_m: float = Field(..., ge=0.0)
    edge_b_length_m: float = Field(..., ge=0.0)
    length_m: float = Field(..., ge=0.0)
    ease_allowance_m: float = Field(default=0.0, ge=0.0)
    seam_allowance_m: float = Field(default=0.01, ge=0.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)
    verification_state: ConstructionVerificationState = ConstructionVerificationState.INFERRED
    source_evidence: List[str] = Field(default_factory=list)
    notes: str = ""


class ConstructionInferenceRecord(BaseModel):
    decision_id: str
    construction_feature: str
    source_component: str
    supporting_image_ids: List[str] = Field(default_factory=list)
    supporting_views: List[str] = Field(default_factory=list)
    visibility: str = "UNKNOWN"
    evidence_completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    uncertainty: float = Field(default=1.0, ge=0.0, le=1.0)
    inference_method: str = "category_construction_rule"
    verification_state: ConstructionVerificationState = ConstructionVerificationState.INFERRED
    notes: str = ""


class AssemblyValidationIssue(BaseModel):
    severity: str  # ERROR | WARNING
    code: str
    message: str
    piece_ids: List[str] = Field(default_factory=list)
    seam_id: Optional[str] = None


class AssemblyValidationReport(BaseModel):
    is_valid: bool
    pieces_checked: int
    seams_checked: int
    has_cycles: bool = False
    seam_length_mismatches: List[Dict[str, Any]] = Field(default_factory=list)
    issues: List[AssemblyValidationIssue] = Field(default_factory=list)
    unsupported_features: List[str] = Field(default_factory=list)


class UnifiedConstructionGraphContract(BaseModel):
    schema_version: str = CONSTRUCTION_SCHEMA_VERSION
    garment_id: str
    category: str
    subcategory: str = ""
    construction_type: str
    component_refs: List[str] = Field(default_factory=list)
    pattern_piece_ids: List[str] = Field(default_factory=list)
    pieces: Dict[str, PatternPiece2D] = Field(default_factory=dict)
    seams: List[SeamConnection] = Field(default_factory=list)
    assembly_order: List[str] = Field(default_factory=list)
    assembly_dependencies: List[Tuple[str, str]] = Field(default_factory=list)
    inference_records: List[ConstructionInferenceRecord] = Field(default_factory=list)
    construction_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    construction_uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_provenance: Dict[str, Any] = Field(default_factory=dict)
    validation_report: Optional[AssemblyValidationReport] = None


class ConstructionToGeometryHandoff(BaseModel):
    schema_version: str = CONSTRUCTION_SCHEMA_VERSION
    garment_id: str
    category: str
    subcategory: str = ""
    target_engine_id: str
    engine_compatible: bool = True
    construction_graph: UnifiedConstructionGraphContract
    measurements: Dict[str, MeasuredDimension] = Field(default_factory=dict)
    material_references: Dict[str, str] = Field(default_factory=dict)
    evidence_supported_features: List[str] = Field(default_factory=list)
    inferred_features: List[str] = Field(default_factory=list)
    missing_or_ambiguous_features: List[str] = Field(default_factory=list)
    invalid_features: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)
    validation_report: AssemblyValidationReport


# ---------------------------------------------------------------------------
# Deterministic 2D Polygon & Edge Computational Geometry Helpers
# ---------------------------------------------------------------------------

def polyline_length(pts: List[Point2DPattern]) -> float:
    total = 0.0
    for i in range(len(pts) - 1):
        total += math.hypot(pts[i + 1].x - pts[i].x, pts[i + 1].y - pts[i].y)
    return round(total, 6)


def signed_polygon_area(poly: List[Point2DPattern]) -> float:
    n = len(poly)
    if n < 3:
        return 0.0
    area2 = 0.0
    for i in range(n):
        p1 = poly[i]
        p2 = poly[(i + 1) % n]
        area2 += p1.x * p2.y - p2.x * p1.y
    return 0.5 * area2


def polygon_perimeter(poly: List[Point2DPattern]) -> float:
    n = len(poly)
    if n < 2:
        return 0.0
    total = 0.0
    for i in range(n):
        p1, p2 = poly[i], poly[(i + 1) % n]
        total += math.hypot(p2.x - p1.x, p2.y - p1.y)
    return round(total, 6)


def _orient(a: Point2DPattern, b: Point2DPattern, c: Point2DPattern) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _on_segment(a: Point2DPattern, b: Point2DPattern, p: Point2DPattern, eps: float = 1e-9) -> bool:
    return (
        min(a.x, b.x) - eps <= p.x <= max(a.x, b.x) + eps
        and min(a.y, b.y) - eps <= p.y <= max(a.y, b.y) + eps
    )


def segments_intersect(a1: Point2DPattern, a2: Point2DPattern, b1: Point2DPattern, b2: Point2DPattern) -> bool:
    o1 = _orient(a1, a2, b1)
    o2 = _orient(a1, a2, b2)
    o3 = _orient(b1, b2, a1)
    o4 = _orient(b1, b2, a2)
    eps = 1e-9
    if (o1 > eps and o2 < -eps or o1 < -eps and o2 > eps) and (o3 > eps and o4 < -eps or o3 < -eps and o4 > eps):
        return True
    if abs(o1) <= eps and _on_segment(a1, a2, b1, eps):
        return True
    if abs(o2) <= eps and _on_segment(a1, a2, b2, eps):
        return True
    if abs(o3) <= eps and _on_segment(b1, b2, a1, eps):
        return True
    if abs(o4) <= eps and _on_segment(b1, b2, a2, eps):
        return True
    return False


def validate_polygon_2d(poly: List[Point2DPattern], edges: Optional[List[PatternEdge]] = None) -> List[str]:
    """Validate 2D polygon geometry: vertex count, duplicates, degenerate edges, winding, connectivity, self-intersection."""
    errors: List[str] = []
    n = len(poly)
    if n < 3:
        return ["Polygon must have at least 3 vertices."]

    for i in range(n):
        p1, p2 = poly[i], poly[(i + 1) % n]
        if not (math.isfinite(p1.x) and math.isfinite(p1.y)):
            errors.append(f"Vertex {i} contains non-finite coordinates.")
            continue
        if math.hypot(p2.x - p1.x, p2.y - p1.y) < 1e-5:
            errors.append(f"Duplicate or degenerate edge between vertex {i} and {(i + 1) % n}.")

    seen = set()
    for p in poly:
        key = (round(p.x, 6), round(p.y, 6))
        if key in seen:
            errors.append(f"Duplicate polygon vertex at ({key[0]}, {key[1]}).")
            break
        seen.add(key)

    s_area = signed_polygon_area(poly)
    if abs(s_area) < 1e-7:
        errors.append("Polygon area is near zero (collinear or degenerate).")
    elif s_area < 0:
        errors.append("Polygon winding is clockwise; counter-clockwise orientation is required.")

    # Non-adjacent edge self-intersection test
    for i in range(n):
        a1, a2 = poly[i], poly[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            b1, b2 = poly[j], poly[(j + 1) % n]
            if segments_intersect(a1, a2, b1, b2):
                errors.append(f"Polygon self-intersects between edge {i} and edge {j}.")
                break

    if edges is not None:
        if not edges:
            errors.append("Pattern piece has no edges.")
        else:
            for idx, edge in enumerate(edges):
                if len(edge.vertices) < 2 or edge.length_m <= 1e-5:
                    errors.append(f"Edge '{edge.edge_id}' is degenerate.")
                    continue
                nxt = edges[(idx + 1) % len(edges)]
                if nxt.vertices:
                    end_pt = edge.vertices[-1]
                    start_pt = nxt.vertices[0]
                    if math.hypot(end_pt.x - start_pt.x, end_pt.y - start_pt.y) > 2e-3:
                        errors.append(f"Disconnected boundary between '{edge.edge_id}' and '{nxt.edge_id}'.")
    return errors


def compute_seam_allowance_polygon(poly: List[Point2DPattern], allowance_m: float) -> List[Point2DPattern]:
    """Compute an outward miter-clamped 2D seam allowance offset for a CCW closed polygon."""
    if len(poly) < 3 or allowance_m <= 0:
        return list(poly)
    n = len(poly)
    offset_pts: List[Point2DPattern] = []
    for i in range(n):
        p_prev = poly[(i - 1) % n]
        p_curr = poly[i]
        p_next = poly[(i + 1) % n]
        e1x, e1y = p_curr.x - p_prev.x, p_curr.y - p_prev.y
        e2x, e2y = p_next.x - p_curr.x, p_next.y - p_curr.y
        l1 = max(1e-8, math.hypot(e1x, e1y))
        l2 = max(1e-8, math.hypot(e2x, e2y))
        # Outward unit normals for CCW polygon: (dy, -dx)
        n1x, n1y = e1y / l1, -e1x / l1
        n2x, n2y = e2y / l2, -e2x / l2
        bx, by = n1x + n2x, n1y + n2y
        bl = math.hypot(bx, by)
        if bl < 1e-6:
            nx, ny = n1x, n1y
            scale = allowance_m
        else:
            nx, ny = bx / bl, by / bl
            dot = max(0.35, nx * n1x + ny * n1y)
            scale = min(allowance_m * 2.0, allowance_m / dot)
        offset_pts.append(Point2DPattern(x=round(p_curr.x + nx * scale, 5), y=round(p_curr.y + ny * scale, 5)))
    return offset_pts
