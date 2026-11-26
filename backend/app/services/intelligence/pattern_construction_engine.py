"""Evidence-driven 2D pattern construction, seam inference, and assembly validation (Phase 16.2)."""
from __future__ import annotations

from collections import deque
import math
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.app.services.ai.contracts import (
    CanonicalGarmentSpecificationV2,
    ComponentAnalysisBundle,
    FusedComponentAssessment,
)
from backend.app.services.garments.reconstruction.engine_registry import reconstruction_registry
from backend.app.services.garments.reconstruction.pattern_geometry import (
    AssemblyValidationIssue,
    AssemblyValidationReport,
    ConstructionInferenceRecord,
    ConstructionToGeometryHandoff,
    ConstructionVerificationState,
    CubicBezierSegment,
    DimensionSourceKind,
    EdgeDirection,
    EdgeRole,
    Grainline2D,
    InternalConstructionLine,
    MeasuredDimension,
    PatternDart,
    PatternEdge,
    PatternNotch,
    PatternPiece2D,
    PatternPieceType,
    Point2DPattern,
    SeamConnection,
    UnifiedConstructionGraphContract,
    polygon_perimeter,
    polyline_length,
    signed_polygon_area,
    validate_polygon_2d,
)
from backend.app.services.garments.reconstruction.proportions import GarmentProportionsEstimator
from backend.app.services.intelligence.component_taxonomy import (
    ComponentEvidenceStatus,
    DetectionState,
    VisibilityState,
)


def _pt(x: float, y: float) -> Point2DPattern:
    return Point2DPattern(x=round(float(x), 5), y=round(float(y), 5))


def _edge(
    edge_id: str,
    role: EdgeRole,
    pts: List[Point2DPattern],
    *,
    bezier: Optional[CubicBezierSegment] = None,
    direction: EdgeDirection = EdgeDirection.FORWARD,
    seam_allowance_m: float = 0.01,
    ease_allowance_m: float = 0.0,
) -> PatternEdge:
    sampled = bezier.sample(8) if bezier is not None else pts
    return PatternEdge(
        edge_id=edge_id,
        role=role,
        vertices=sampled,
        bezier=bezier,
        length_m=polyline_length(sampled),
        direction=direction,
        seam_allowance_m=seam_allowance_m,
        ease_allowance_m=ease_allowance_m,
    )


def _build_piece_from_edges(
    piece_id: str,
    piece_type: PatternPieceType,
    name: str,
    parent_component: str,
    edges: List[PatternEdge],
    *,
    side: Optional[str] = None,
    material_ref: str = "main_shell",
    seam_allowance_m: float = 0.01,
    notches: Optional[List[PatternNotch]] = None,
    darts: Optional[List[PatternDart]] = None,
    fold_lines: Optional[List[InternalConstructionLine]] = None,
    internal_lines: Optional[List[InternalConstructionLine]] = None,
    dimensions: Optional[Dict[str, MeasuredDimension]] = None,
    evidence_refs: Optional[List[str]] = None,
    source_views: Optional[List[str]] = None,
    verification_state: ConstructionVerificationState = ConstructionVerificationState.INFERRED,
    confidence: float = 0.65,
    uncertainty: float = 0.35,
    grain_angle_deg: float = 90.0,
) -> PatternPiece2D:
    # Assemble continuous CCW perimeter vertices without duplicating corner points.
    poly: List[Point2DPattern] = []
    for edge in edges:
        for idx, pt in enumerate(edge.vertices):
            if idx == len(edge.vertices) - 1:
                continue
            if not poly or math.hypot(pt.x - poly[-1].x, pt.y - poly[-1].y) > 1e-6:
                poly.append(pt)
    if len(poly) >= 3 and signed_polygon_area(poly) < 0:
        poly = list(reversed(poly))

    xs = [p.x for p in poly] or [0.0]
    ys = [p.y for p in poly] or [0.0]
    cx = 0.5 * (min(xs) + max(xs))
    y_bot = min(ys) + 0.15 * max(0.02, max(ys) - min(ys))
    y_top = max(ys) - 0.15 * max(0.02, max(ys) - min(ys))
    if abs(grain_angle_deg) < 10.0:
        grain = Grainline2D(start=_pt(min(xs) + 0.15 * (max(xs) - min(xs)), 0.5 * (min(ys) + max(ys))),
                            end=_pt(max(xs) - 0.15 * (max(xs) - min(xs)), 0.5 * (min(ys) + max(ys))),
                            angle_deg=0.0, direction="weft")
    else:
        grain = Grainline2D(start=_pt(cx, y_bot), end=_pt(cx, y_top), angle_deg=grain_angle_deg, direction="warp")

    return PatternPiece2D(
        piece_id=piece_id,
        piece_type=piece_type,
        name=name,
        parent_component=parent_component,
        side_or_orientation=side,
        boundary_polygon=poly,
        edges=edges,
        notches=notches or [],
        darts=darts or [],
        fold_lines=fold_lines or [],
        internal_lines=internal_lines or [],
        grainline=grain,
        seam_allowance_m=seam_allowance_m,
        material_ref=material_ref,
        dimensions=dimensions or {},
        area_m2=round(abs(signed_polygon_area(poly)), 6),
        perimeter_m=polygon_perimeter(poly),
        evidence_refs=evidence_refs or [],
        source_views=source_views or [],
        verification_state=verification_state,
        confidence=round(max(0.0, min(1.0, confidence)), 4),
        uncertainty=round(max(0.0, min(1.0, uncertainty)), 4),
    )


def _rect_piece(
    piece_id: str,
    piece_type: PatternPieceType,
    name: str,
    parent_component: str,
    width_m: float,
    height_m: float,
    *,
    side: Optional[str] = None,
    roles: Tuple[EdgeRole, EdgeRole, EdgeRole, EdgeRole] = (EdgeRole.SEWN, EdgeRole.SEWN, EdgeRole.SEWN, EdgeRole.SEWN),
    edge_names: Tuple[str, str, str, str] = ("bottom", "right", "top", "left"),
    material_ref: str = "main_shell",
    seam_allowance_m: float = 0.01,
    fold_center: bool = False,
    dimensions: Optional[Dict[str, MeasuredDimension]] = None,
    evidence_refs: Optional[List[str]] = None,
    source_views: Optional[List[str]] = None,
    verification_state: ConstructionVerificationState = ConstructionVerificationState.INFERRED,
    confidence: float = 0.65,
    uncertainty: float = 0.35,
) -> PatternPiece2D:
    w = max(0.03, float(width_m))
    h = max(0.03, float(height_m))
    p0, p1, p2, p3 = _pt(0.0, 0.0), _pt(w, 0.0), _pt(w, h), _pt(0.0, h)
    edges = [
        _edge(edge_names[0], roles[0], [p0, p1], seam_allowance_m=seam_allowance_m),
        _edge(edge_names[1], roles[1], [p1, p2], seam_allowance_m=seam_allowance_m),
        _edge(edge_names[2], roles[2], [p2, p3], seam_allowance_m=seam_allowance_m),
        _edge(edge_names[3], roles[3], [p3, p0], seam_allowance_m=seam_allowance_m),
    ]
    folds = [InternalConstructionLine(line_id=f"{piece_id}_fold", kind="fold_line", points=[_pt(w * 0.5, 0.0), _pt(w * 0.5, h)])] if fold_center else []
    dims = dict(dimensions or {})
    dims.setdefault("width", MeasuredDimension(
        name="width", value_m=round(w, 4),
        source=DimensionSourceKind.IMAGE_DERIVED if evidence_refs else DimensionSourceKind.CATEGORY_PRIOR,
        confidence=confidence, uncertainty_m=round(0.015 + uncertainty * 0.04, 4),
        evidence_refs=list(evidence_refs or []),
    ))
    dims.setdefault("height", MeasuredDimension(
        name="height", value_m=round(h, 4),
        source=DimensionSourceKind.IMAGE_DERIVED if evidence_refs else DimensionSourceKind.CATEGORY_PRIOR,
        confidence=confidence, uncertainty_m=round(0.015 + uncertainty * 0.04, 4),
        evidence_refs=list(evidence_refs or []),
    ))
    return _build_piece_from_edges(
        piece_id, piece_type, name, parent_component, edges,
        side=side, material_ref=material_ref, seam_allowance_m=seam_allowance_m,
        fold_lines=folds, dimensions=dims, evidence_refs=evidence_refs,
        source_views=source_views, verification_state=verification_state,
        confidence=confidence, uncertainty=uncertainty,
    )


def _bodice_shell_piece(
    piece_id: str,
    piece_type: PatternPieceType,
    name: str,
    parent_component: str,
    half_width_m: float,
    height_m: float,
    *,
    armhole_depth_m: float = 0.21,
    neck_drop_m: float = 0.08,
    neck_width_m: float = 0.18,
    split_side: Optional[str] = None,
    has_side_slit: bool = False,
    slit_height_m: float = 0.22,
    center_role: EdgeRole = EdgeRole.FOLDED,
    dart: Optional[PatternDart] = None,
    internal_lines: Optional[List[InternalConstructionLine]] = None,
    seam_allowance_m: float = 0.01,
    dimensions: Optional[Dict[str, MeasuredDimension]] = None,
    evidence_refs: Optional[List[str]] = None,
    source_views: Optional[List[str]] = None,
    verification_state: ConstructionVerificationState = ConstructionVerificationState.INFERRED,
    confidence: float = 0.65,
    uncertainty: float = 0.35,
) -> PatternPiece2D:
    """Create a tailored upper-body panel with curved Bézier armscye and neckline."""
    hw = max(0.14, float(half_width_m))
    h = max(0.32, float(height_m))
    ah = min(h * 0.45, max(0.14, float(armhole_depth_m)))
    nw = min(hw * 0.65, max(0.08, float(neck_width_m)))
    nd = min(h * 0.22, max(0.03, float(neck_drop_m)))
    sh_y = h - 0.025
    underarm_y = max(0.12, h - ah)

    # Full panel centered at x = hw (total width = 2*hw), or half-panel (x in [0, hw]) when split
    if split_side in ("left", "right"):
        w = hw
        # Split front panel (center line at x=0, outer side at x=w)
        p_hem_c = _pt(0.0, 0.0)
        p_hem_s = _pt(w, 0.0)
        p_underarm = _pt(w, underarm_y)
        p_sh_outer = _pt(w * 0.88, sh_y)
        p_neck_sh = _pt(nw * 0.55, h)
        p_neck_c = _pt(0.0, h - nd)

        arm_bez = CubicBezierSegment(
            p0=p_underarm, p1=_pt(w * 0.82, underarm_y + ah * 0.35),
            p2=_pt(w * 0.84, sh_y - ah * 0.25), p3=p_sh_outer,
        )
        neck_bez = CubicBezierSegment(
            p0=p_neck_sh, p1=_pt(nw * 0.40, h - nd * 0.65),
            p2=_pt(nw * 0.15, h - nd), p3=p_neck_c,
        )
        edges = [_edge("hem", EdgeRole.HEMMED, [p_hem_c, p_hem_s], seam_allowance_m=0.02)]
        if has_side_slit and slit_height_m < underarm_y - 0.04:
            p_slit = _pt(w, slit_height_m)
            edges.append(_edge("side_slit", EdgeRole.HEMMED, [p_hem_s, p_slit], seam_allowance_m=0.01))
            edges.append(_edge("side_seam", EdgeRole.SEWN, [p_slit, p_underarm], seam_allowance_m=seam_allowance_m))
        else:
            edges.append(_edge("side_seam", EdgeRole.SEWN, [p_hem_s, p_underarm], seam_allowance_m=seam_allowance_m))
        edges.extend([
            _edge("armscye", EdgeRole.SLEEVE_ATTACHMENT, arm_bez.sample(8), bezier=arm_bez, seam_allowance_m=seam_allowance_m),
            _edge("shoulder", EdgeRole.SEWN, [p_sh_outer, p_neck_sh], seam_allowance_m=seam_allowance_m),
            _edge("neckline", EdgeRole.COLLAR_ATTACHMENT, neck_bez.sample(6), bezier=neck_bez, seam_allowance_m=seam_allowance_m),
            _edge("center_closure", center_role, [p_neck_c, p_hem_c], seam_allowance_m=seam_allowance_m),
        ])
    else:
        w = 2.0 * hw
        p_bl = _pt(0.0, 0.0)
        p_br = _pt(w, 0.0)
        p_ur = _pt(w, underarm_y)
        p_shr = _pt(w - hw * 0.12, sh_y)
        p_nr = _pt(hw + nw * 0.5, h)
        p_nl = _pt(hw - nw * 0.5, h)
        p_shl = _pt(hw * 0.12, sh_y)
        p_ul = _pt(0.0, underarm_y)

        arm_r = CubicBezierSegment(p0=p_ur, p1=_pt(w - hw * 0.18, underarm_y + ah * 0.35), p2=_pt(w - hw * 0.16, sh_y - ah * 0.25), p3=p_shr)
        neck_b = CubicBezierSegment(p0=p_nr, p1=_pt(hw + nw * 0.28, h - nd), p2=_pt(hw - nw * 0.28, h - nd), p3=p_nl)
        arm_l = CubicBezierSegment(p0=p_shl, p1=_pt(hw * 0.16, sh_y - ah * 0.25), p2=_pt(hw * 0.18, underarm_y + ah * 0.35), p3=p_ul)

        edges = [_edge("hem", EdgeRole.HEMMED, [p_bl, p_br], seam_allowance_m=0.02)]
        if has_side_slit and slit_height_m < underarm_y - 0.04:
            p_sl_r = _pt(w, slit_height_m)
            edges.append(_edge("side_slit_right", EdgeRole.HEMMED, [p_br, p_sl_r], seam_allowance_m=0.01))
            edges.append(_edge("side_right", EdgeRole.SEWN, [p_sl_r, p_ur], seam_allowance_m=seam_allowance_m))
        else:
            edges.append(_edge("side_right", EdgeRole.SEWN, [p_br, p_ur], seam_allowance_m=seam_allowance_m))

        edges.extend([
            _edge("armscye_right", EdgeRole.SLEEVE_ATTACHMENT, arm_r.sample(8), bezier=arm_r, seam_allowance_m=seam_allowance_m),
            _edge("shoulder_right", EdgeRole.SEWN, [p_shr, p_nr], seam_allowance_m=seam_allowance_m),
            _edge("neckline", EdgeRole.COLLAR_ATTACHMENT, neck_b.sample(8), bezier=neck_b, seam_allowance_m=seam_allowance_m),
            _edge("shoulder_left", EdgeRole.SEWN, [p_nl, p_shl], seam_allowance_m=seam_allowance_m),
            _edge("armscye_left", EdgeRole.SLEEVE_ATTACHMENT, arm_l.sample(8), bezier=arm_l, seam_allowance_m=seam_allowance_m),
        ])
        if has_side_slit and slit_height_m < underarm_y - 0.04:
            p_sl_l = _pt(0.0, slit_height_m)
            edges.append(_edge("side_left", EdgeRole.SEWN, [p_ul, p_sl_l], seam_allowance_m=seam_allowance_m))
            edges.append(_edge("side_slit_left", EdgeRole.HEMMED, [p_sl_l, p_bl], seam_allowance_m=0.01))
        else:
            edges.append(_edge("side_left", EdgeRole.SEWN, [p_ul, p_bl], seam_allowance_m=seam_allowance_m))

    notches = [PatternNotch(notch_id=f"{piece_id}_neck_c", edge_id="neckline", position_t=0.5, style="center")]
    dims = dict(dimensions or {})
    dims.setdefault("chest_width", MeasuredDimension(
        name="chest_width", value_m=round(w, 4),
        source=DimensionSourceKind.IMAGE_DERIVED if evidence_refs else DimensionSourceKind.CATEGORY_PRIOR,
        confidence=confidence, uncertainty_m=round(0.02 + uncertainty * 0.05, 4),
        evidence_refs=list(evidence_refs or []),
    ))
    dims.setdefault("torso_length", MeasuredDimension(
        name="torso_length", value_m=round(h, 4),
        source=DimensionSourceKind.IMAGE_DERIVED if evidence_refs else DimensionSourceKind.CATEGORY_PRIOR,
        confidence=confidence, uncertainty_m=round(0.02 + uncertainty * 0.05, 4),
        evidence_refs=list(evidence_refs or []),
    ))
    return _build_piece_from_edges(
        piece_id, piece_type, name, parent_component, edges,
        side=split_side or ("front" if "front" in piece_id else "back"),
        seam_allowance_m=seam_allowance_m, notches=notches,
        darts=[dart] if dart else [], internal_lines=internal_lines,
        dimensions=dims, evidence_refs=evidence_refs, source_views=source_views,
        verification_state=verification_state, confidence=confidence, uncertainty=uncertainty,
    )


def _sleeve_piece(
    piece_id: str,
    side: str,
    length_m: float,
    armscye_len_m: float,
    cuff_width_m: float,
    *,
    seam_allowance_m: float = 0.01,
    evidence_refs: Optional[List[str]] = None,
    source_views: Optional[List[str]] = None,
    verification_state: ConstructionVerificationState = ConstructionVerificationState.INFERRED,
    confidence: float = 0.65,
    uncertainty: float = 0.35,
) -> PatternPiece2D:
    """Flat tailored sleeve pattern with curved Bézier sleeve cap matching armscye perimeter + ease."""
    sl_len = max(0.14, float(length_m))
    cuff_w = max(0.16, float(cuff_width_m))
    bicep_w = max(cuff_w + 0.08, armscye_len_m * 0.92)
    cap_h = max(0.08, min(0.18, armscye_len_m * 0.38))
    x0_cuff = 0.5 * (bicep_w - cuff_w)
    x1_cuff = x0_cuff + cuff_w

    p_c0 = _pt(x0_cuff, 0.0)
    p_c1 = _pt(x1_cuff, 0.0)
    p_u1 = _pt(bicep_w, sl_len - cap_h)
    p_u0 = _pt(0.0, sl_len - cap_h)

    cap_bez = CubicBezierSegment(
        p0=p_u1,
        p1=_pt(bicep_w * 0.78, sl_len + cap_h * 0.25),
        p2=_pt(bicep_w * 0.22, sl_len + cap_h * 0.25),
        p3=p_u0,
    )
    edges = [
        _edge("cuff_edge", EdgeRole.SEWN, [p_c0, p_c1], seam_allowance_m=seam_allowance_m),
        _edge("underarm_b", EdgeRole.SEWN, [p_c1, p_u1], seam_allowance_m=seam_allowance_m),
        _edge("sleeve_cap", EdgeRole.SLEEVE_ATTACHMENT, cap_bez.sample(10), bezier=cap_bez,
              seam_allowance_m=seam_allowance_m, ease_allowance_m=0.02),
        _edge("underarm_a", EdgeRole.SEWN, [p_u0, p_c0], seam_allowance_m=seam_allowance_m),
    ]
    notches = [PatternNotch(notch_id=f"{piece_id}_cap_top", edge_id="sleeve_cap", position_t=0.5, style="double")]
    dims = {
        "sleeve_length": MeasuredDimension(
            name="sleeve_length", value_m=round(sl_len, 4),
            source=DimensionSourceKind.IMAGE_DERIVED if evidence_refs else DimensionSourceKind.CATEGORY_PRIOR,
            confidence=confidence, uncertainty_m=round(0.02 + uncertainty * 0.05, 4),
            evidence_refs=list(evidence_refs or []),
        )
    }
    return _build_piece_from_edges(
        piece_id,
        PatternPieceType.LEFT_SLEEVE if side == "left" else PatternPieceType.RIGHT_SLEEVE,
        f"{side.capitalize()} Sleeve Panel",
        f"{side}_sleeve",
        edges,
        side=side,
        notches=notches,
        dimensions=dims,
        evidence_refs=evidence_refs,
        source_views=source_views,
        verification_state=verification_state,
        confidence=confidence,
        uncertainty=uncertainty,
    )


def _trouser_leg_piece(
    piece_id: str,
    piece_type: PatternPieceType,
    name: str,
    parent_component: str,
    side: str,
    waist_w_m: float,
    hip_w_m: float,
    hem_w_m: float,
    inseam_m: float,
    rise_m: float,
    crotch_ext_m: float,
    *,
    has_fly: bool = False,
    seam_allowance_m: float = 0.012,
    evidence_refs: Optional[List[str]] = None,
    source_views: Optional[List[str]] = None,
    verification_state: ConstructionVerificationState = ConstructionVerificationState.INFERRED,
    confidence: float = 0.65,
    uncertainty: float = 0.35,
) -> PatternPiece2D:
    """CCW trouser leg panel with contoured Bézier crotch J-curve, inseam, outseam, waistband edge, hem."""
    tot_h = inseam_m + rise_m
    p_hem_in = _pt(crotch_ext_m, 0.0)
    p_hem_out = _pt(crotch_ext_m + hem_w_m, 0.0)
    p_hip_out = _pt(crotch_ext_m + hip_w_m, inseam_m)
    p_waist_out = _pt(crotch_ext_m + waist_w_m, tot_h)
    p_waist_in = _pt(crotch_ext_m, tot_h)
    p_crotch_pt = _pt(0.0, inseam_m)

    edges = [
        _edge("leg_hem", EdgeRole.HEMMED, [p_hem_in, p_hem_out], seam_allowance_m=0.025),
        _edge("outseam", EdgeRole.SEWN, [p_hem_out, p_hip_out, p_waist_out], seam_allowance_m=seam_allowance_m),
        _edge("waist_top", EdgeRole.SEWN, [p_waist_out, p_waist_in], seam_allowance_m=seam_allowance_m),
    ]
    if has_fly:
        fly_bot = _pt(crotch_ext_m * 0.85, tot_h - min(0.16, rise_m * 0.60))
        crotch_bez = CubicBezierSegment(
            p0=fly_bot,
            p1=_pt(crotch_ext_m * 0.72, inseam_m + rise_m * 0.16),
            p2=_pt(crotch_ext_m * 0.30, inseam_m + rise_m * 0.04),
            p3=p_crotch_pt,
        )
        edges.append(_edge("fly_opening", EdgeRole.ZIPPER_ATTACHMENT, [p_waist_in, fly_bot], seam_allowance_m=seam_allowance_m))
        edges.append(_edge("crotch_rise", EdgeRole.SEWN, crotch_bez.sample(6), bezier=crotch_bez, seam_allowance_m=seam_allowance_m))
    else:
        crotch_bez = CubicBezierSegment(
            p0=p_waist_in,
            p1=_pt(crotch_ext_m * 0.92, inseam_m + rise_m * 0.25),
            p2=_pt(crotch_ext_m * 0.35, inseam_m + rise_m * 0.05),
            p3=p_crotch_pt,
        )
        edges.append(_edge("crotch_rise", EdgeRole.SEWN, crotch_bez.sample(8), bezier=crotch_bez, seam_allowance_m=seam_allowance_m))
    edges.append(_edge("inseam", EdgeRole.SEWN, [p_crotch_pt, p_hem_in], seam_allowance_m=seam_allowance_m))
    return _build_piece_from_edges(
        piece_id, piece_type, name, parent_component, edges, side=side,
        seam_allowance_m=seam_allowance_m,
        notches=[PatternNotch(notch_id=f"{piece_id}_knee", edge_id="outseam", position_t=0.45, style="single")],
        evidence_refs=evidence_refs, source_views=source_views,
        verification_state=verification_state, confidence=confidence, uncertainty=uncertainty,
    )


class AssemblyValidator:
    """Validates panel polygon geometry, seam edge endpoints, edge lengths, and DAG acyclicity."""

    @staticmethod
    def validate(
        graph: UnifiedConstructionGraphContract,
        required_components: Tuple[str, ...] = (),
        length_tolerance_m: float = 0.04,
    ) -> AssemblyValidationReport:
        issues: List[AssemblyValidationIssue] = []
        mismatches: List[Dict[str, Any]] = []
        unsupported: List[str] = []

        # 1. Validate every 2D piece polygon and edges
        for pid, piece in graph.pieces.items():
            poly_errs = validate_polygon_2d(piece.boundary_polygon, piece.edges)
            for err in poly_errs:
                issues.append(AssemblyValidationIssue(
                    severity="ERROR", code="INVALID_PANEL_GEOMETRY",
                    message=f"{pid}: {err}", piece_ids=[pid],
                ))

        # 2. Validate every seam endpoint, edge existence, and edge length compatibility
        for seam in graph.seams:
            pa = graph.pieces.get(seam.piece_a)
            pb = graph.pieces.get(seam.piece_b)
            if pa is None or pb is None:
                issues.append(AssemblyValidationIssue(
                    severity="ERROR", code="MISSING_SEAM_PIECE",
                    message=f"Seam '{seam.seam_id}' references missing piece ({seam.piece_a} / {seam.piece_b}).",
                    seam_id=seam.seam_id, piece_ids=[seam.piece_a, seam.piece_b],
                ))
                continue
            ea = next((e for e in pa.edges if e.edge_id == seam.edge_a), None)
            eb = next((e for e in pb.edges if e.edge_id == seam.edge_b), None)
            if ea is None or eb is None:
                issues.append(AssemblyValidationIssue(
                    severity="ERROR", code="MISSING_SEAM_EDGE",
                    message=f"Seam '{seam.seam_id}' references missing edge ({seam.piece_a}.{seam.edge_a} / {seam.piece_b}.{seam.edge_b}).",
                    seam_id=seam.seam_id, piece_ids=[seam.piece_a, seam.piece_b],
                ))
                continue

            # Applique / internal placement seams (pocket on body, placket on center) attach onto face interior, not full perimeter equality
            if seam.seam_type not in (EdgeRole.POCKET_ATTACHMENT, EdgeRole.LINING_ATTACHMENT):
                expected_diff = abs(ea.length_m - eb.length_m) - seam.ease_allowance_m
                if expected_diff > length_tolerance_m:
                    mismatches.append({
                        "seam_id": seam.seam_id,
                        "piece_a": seam.piece_a,
                        "edge_a": seam.edge_a,
                        "len_a_m": ea.length_m,
                        "piece_b": seam.piece_b,
                        "edge_b": seam.edge_b,
                        "len_b_m": eb.length_m,
                        "delta_m": round(abs(ea.length_m - eb.length_m), 4),
                    })
                    issues.append(AssemblyValidationIssue(
                        severity="WARNING", code="SEAM_LENGTH_MISMATCH",
                        message=f"Seam '{seam.seam_id}' length mismatch: {ea.length_m:.3f}m vs {eb.length_m:.3f}m.",
                        seam_id=seam.seam_id, piece_ids=[seam.piece_a, seam.piece_b],
                    ))

        # 3. Assembly order cycle detection (validate ordering references and check seam-dependency cycles)
        adj: Dict[str, List[str]] = {pid: [] for pid in graph.pieces}
        indeg: Dict[str, int] = {pid: 0 for pid in graph.pieces}
        order_idx = {pid: idx for idx, pid in enumerate(graph.assembly_order)}
        for pid in graph.assembly_order:
            if pid not in graph.pieces:
                issues.append(AssemblyValidationIssue(
                    severity="ERROR", code="INVALID_ASSEMBLY_REFERENCE",
                    message=f"Assembly order references unknown piece '{pid}'.", piece_ids=[pid],
                ))
        if graph.assembly_dependencies:
            for src, dst in graph.assembly_dependencies:
                if src in adj and dst in adj and dst not in adj[src]:
                    adj[src].append(dst)
                    indeg[dst] += 1
        else:
            for seam in graph.seams:
                if seam.piece_a in order_idx and seam.piece_b in order_idx and seam.piece_a != seam.piece_b:
                    src, dst = (seam.piece_a, seam.piece_b) if order_idx[seam.piece_a] < order_idx[seam.piece_b] else (seam.piece_b, seam.piece_a)
                    if dst not in adj[src]:
                        adj[src].append(dst)
                        indeg[dst] += 1
        q = deque([k for k, v in indeg.items() if v == 0])
        visited_cnt = 0
        while q:
            cur = q.popleft()
            visited_cnt += 1
            for nxt in adj[cur]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    q.append(nxt)
        has_cycles = visited_cnt != len(graph.pieces) and len(graph.pieces) > 0
        if has_cycles:
            issues.append(AssemblyValidationIssue(
                severity="ERROR", code="ASSEMBLY_GRAPH_CYCLE",
                message="Assembly dependencies contain a cycle.",
            ))

        # 4. Check required category components and unsupported inference records
        present_components = set(graph.component_refs) | {p.parent_component for p in graph.pieces.values()}
        for req in required_components:
            if req not in present_components and not any(req in pc for pc in present_components):
                issues.append(AssemblyValidationIssue(
                    severity="WARNING", code="MISSING_REQUIRED_COMPONENT",
                    message=f"Required category component '{req}' has no pattern representation.",
                ))

        for rec in graph.inference_records:
            if rec.verification_state in (ConstructionVerificationState.UNSUPPORTED, ConstructionVerificationState.AMBIGUOUS):
                unsupported.append(rec.construction_feature)

        has_errors = any(i.severity == "ERROR" for i in issues)
        return AssemblyValidationReport(
            is_valid=not has_errors,
            pieces_checked=len(graph.pieces),
            seams_checked=len(graph.seams),
            has_cycles=has_cycles,
            seam_length_mismatches=mismatches,
            issues=issues,
            unsupported_features=sorted(set(unsupported)),
        )


class PatternConstructionEngine:
    """Synthesizes evidence-backed construction graphs & 2D pattern pieces across all garment categories."""

    def build_construction(
        self,
        garment_id: str,
        category: str,
        subcategory: str = "",
        component_bundle: Optional[ComponentAnalysisBundle] = None,
        specification: Optional[CanonicalGarmentSpecificationV2] = None,
        fit: str = "regular",
        cancel_event: Optional[threading.Event] = None,
    ) -> ConstructionToGeometryHandoff:
        t0 = time.perf_counter()
        if cancel_event and cancel_event.is_set():
            raise TimeoutError("Pattern construction cancelled before execution.")

        fused: Dict[str, FusedComponentAssessment] = {}
        if component_bundle is not None:
            fused = component_bundle.fused_components
        elif specification is not None and specification.fused_components:
            fused = specification.fused_components

        cat = (category or "tops").lower().strip()
        sub = (subcategory or "").lower().strip()
        props = GarmentProportionsEstimator.estimate(category=cat, subcategory=sub, fit=fit, intelligence=None)

        has_back_view = any(
            v.usable and v.counts_as_independent_view and v.view_type == "back"
            for v in (specification.views if specification else (component_bundle.views_analyzed if component_bundle else []))
        )

        # Helpers to inspect Phase 16.1 evidence honestly
        def comp_state(cid: str) -> Tuple[ConstructionVerificationState, float, float, List[str], List[str], str]:
            fc = fused.get(cid)
            if fc is None:
                return ConstructionVerificationState.INFERRED, 0.45, 0.55, [], [], VisibilityState.UNKNOWN.value
            if fc.contradicted or fc.evidence_status == ComponentEvidenceStatus.CONTRADICTED:
                return (
                    ConstructionVerificationState.AMBIGUOUS, 0.35, 1.0,
                    list(fc.source_image_ids), list(fc.source_views), fc.best_visibility.value,
                )
            if fc.evidence_status == ComponentEvidenceStatus.OBSERVED and fc.detection_state == DetectionState.DETECTED:
                c = fc.confidence if fc.confidence is not None else 0.75
                u = fc.uncertainty.total_uncertainty
                return (
                    ConstructionVerificationState.OBSERVED, c, u,
                    list(fc.source_image_ids), list(fc.source_views), fc.best_visibility.value,
                )
            if fc.evidence_status in (ComponentEvidenceStatus.NOT_OBSERVED, ComponentEvidenceStatus.UNVERIFIED):
                return (
                    ConstructionVerificationState.UNSUPPORTED, 0.25, 0.90,
                    list(fc.source_image_ids), list(fc.source_views), fc.best_visibility.value,
                )
            return (
                ConstructionVerificationState.INFERRED, fc.confidence or 0.45, fc.uncertainty.total_uncertainty,
                list(fc.source_image_ids), list(fc.source_views), fc.best_visibility.value,
            )

        def is_absent(cid: str) -> bool:
            fc = fused.get(cid)
            return bool(fc and fc.detection_state == DetectionState.ABSENT_VERIFIED and fc.evidence_status == ComponentEvidenceStatus.OBSERVED)

        def is_detected_or_candidate(cid: str, default: bool = False) -> bool:
            fc = fused.get(cid)
            if fc is None:
                return default
            if fc.detection_state == DetectionState.ABSENT_VERIFIED:
                return False
            if fc.detection_state == DetectionState.DETECTED:
                return True
            return default

        pieces: Dict[str, PatternPiece2D] = {}
        seams: List[SeamConnection] = []
        records: List[ConstructionInferenceRecord] = []

        def add_record(feature: str, src_comp: str, method: str, cid_for_ev: Optional[str] = None, force_state: Optional[ConstructionVerificationState] = None, note: str = "") -> None:
            st, conf, unc, imgs, views, vis = comp_state(cid_for_ev or src_comp)
            if force_state is not None:
                st = force_state
            comp_obj = fused.get(cid_for_ev or src_comp)
            completeness = comp_obj.evidence_completeness if comp_obj else 0.0
            records.append(ConstructionInferenceRecord(
                decision_id=f"dec_{len(records) + 1:03d}",
                construction_feature=feature,
                source_component=src_comp,
                supporting_image_ids=imgs,
                supporting_views=views,
                visibility=vis,
                evidence_completeness=completeness,
                confidence=conf,
                uncertainty=unc,
                inference_method=method,
                verification_state=st,
                notes=note,
            ))

        def add_seam(sid: str, pa: str, ea: str, pb: str, eb: str, stype: EdgeRole,
                     ease: float = 0.0, sa: float = 0.01, ev_cid: Optional[str] = None,
                     force_state: Optional[ConstructionVerificationState] = None, note: str = "") -> None:
            p_a, p_b = pieces.get(pa), pieces.get(pb)
            if not p_a or not p_b:
                return
            edge_a_obj = next((e for e in p_a.edges if e.edge_id == ea), None)
            edge_b_obj = next((e for e in p_b.edges if e.edge_id == eb), None)
            la = edge_a_obj.length_m if edge_a_obj else 0.0
            lb = edge_b_obj.length_m if edge_b_obj else 0.0
            st, conf, unc, imgs, _, _ = comp_state(ev_cid or pa)
            if force_state is not None:
                st = force_state
            elif not has_back_view and ("back" in pa or "back" in pb):
                st = ConstructionVerificationState.INFERRED
                unc = max(unc, 0.70)
            seams.append(SeamConnection(
                seam_id=sid, piece_a=pa, edge_a=ea, piece_b=pb, edge_b=eb,
                seam_type=stype, edge_a_length_m=la, edge_b_length_m=lb,
                length_m=round(0.5 * (la + lb), 4), ease_allowance_m=ease,
                seam_allowance_m=sa, confidence=conf, uncertainty=unc,
                verification_state=st, source_evidence=imgs, notes=note,
            ))

        # Image-conditioned torso aspect ratio adjustment (if front_body/bodice bbox observed)
        front_bbox = (fused.get("front_body") or fused.get("bodice")).localized_bbox if (fused.get("front_body") or fused.get("bodice")) else None
        aspect_scale = 1.0
        if front_bbox is not None:
            bh = max(0.05, front_bbox[2] - front_bbox[0])
            bw = max(0.05, front_bbox[3] - front_bbox[1])
            aspect_scale = max(0.85, min(1.20, (bw / bh) / 0.72))

        chest_half = props.chest_width_m * 0.5 * aspect_scale
        torso_h = props.torso_length_m
        sleeve_len = props.sleeve_length_m

        # ── CATEGORY 1: BOTTOM GARMENTS (Trousers / Jeans / Shorts) ──────────
        if cat in {"bottoms", "jeans", "trousers", "shorts"} or any(k in sub for k in ("jean", "trouser", "pant", "chino", "short")):
            ctype = "shorts_construction" if "short" in sub or cat == "shorts" else "trouser_four_panel"
            inseam_m = 0.26 if "short" in sub or cat == "shorts" else props.inseam_length_m
            rise_m = 0.27
            waist_w = props.waist_width_m * 0.5
            hip_w = props.hem_width_m * 0.55
            hem_w = 0.24 if "short" in sub else 0.19
            front_st, fc, fu, f_imgs, f_views, _ = comp_state("left_leg")
            back_st = ConstructionVerificationState.OBSERVED if has_back_view else ConstructionVerificationState.INFERRED
            back_u = 0.25 if has_back_view else 0.78

            has_fly = is_detected_or_candidate("fly", default=True)
            for side in ("left", "right"):
                f_id = f"{side}_front_leg"
                b_id = f"{side}_back_leg"
                pieces[f_id] = _trouser_leg_piece(
                    f_id, PatternPieceType.FRONT_LEG, f"{side.capitalize()} Front Leg", f"{side}_leg", side,
                    waist_w, hip_w, hem_w, inseam_m, rise_m, 0.05, has_fly=(has_fly and side == "left"),
                    evidence_refs=f_imgs, source_views=f_views, verification_state=front_st, confidence=fc, uncertainty=fu,
                )
                pieces[b_id] = _trouser_leg_piece(
                    b_id, PatternPieceType.BACK_LEG, f"{side.capitalize()} Back Leg", "back_rise", side,
                    waist_w + 0.015, hip_w + 0.02, hem_w + 0.015, inseam_m, rise_m + 0.02, 0.08,
                    evidence_refs=f_imgs if has_back_view else [],
                    source_views=["back"] if has_back_view else [],
                    verification_state=back_st, confidence=0.80 if has_back_view else 0.42, uncertainty=back_u,
                )
                add_seam(f"seam_{side}_inseam", f_id, "inseam", b_id, "inseam", EdgeRole.SEWN, ev_cid=f"{side}_leg")
                add_seam(f"seam_{side}_outseam", f_id, "outseam", b_id, "outseam", EdgeRole.SEWN, ev_cid=f"{side}_leg")

            add_seam("seam_front_crotch_rise", "left_front_leg", "crotch_rise", "right_front_leg", "crotch_rise",
                     EdgeRole.SEWN, ev_cid="crotch_seam")
            add_seam("seam_back_crotch_rise", "left_back_leg", "crotch_rise", "right_back_leg", "crotch_rise",
                     EdgeRole.SEWN, ev_cid="back_rise", force_state=back_st)

            wb_st, wbc, wbu, wb_imgs, wb_views, _ = comp_state("lower_waistband")
            # Split waistband bottom edge to match left/right front & back waist_top edges cleanly.
            w_f = waist_w
            w_b = waist_w + 0.015
            wb_pts = [_pt(0.0, 0.0), _pt(w_f, 0.0), _pt(2 * w_f, 0.0), _pt(2 * w_f + w_b, 0.0), _pt(2 * w_f + 2 * w_b, 0.0)]
            wb_top = [_pt(2 * w_f + 2 * w_b, 0.045), _pt(0.0, 0.045)]
            wb_edges = [
                _edge("attach_front_left", EdgeRole.SEWN, [wb_pts[0], wb_pts[1]]),
                _edge("attach_front_right", EdgeRole.SEWN, [wb_pts[1], wb_pts[2]]),
                _edge("attach_back_left", EdgeRole.SEWN, [wb_pts[2], wb_pts[3]]),
                _edge("attach_back_right", EdgeRole.SEWN, [wb_pts[3], wb_pts[4]]),
                _edge("right", EdgeRole.SEWN, [wb_pts[4], wb_top[0]]),
                _edge("top", EdgeRole.FOLDED, [wb_top[0], wb_top[1]]),
                _edge("left", EdgeRole.SEWN, [wb_top[1], wb_pts[0]]),
            ]
            pieces["waistband"] = _build_piece_from_edges(
                "waistband", PatternPieceType.WAISTBAND, "Contoured Waistband", "lower_waistband", wb_edges,
                evidence_refs=wb_imgs, source_views=wb_views, verification_state=wb_st, confidence=wbc, uncertainty=wbu,
                grain_angle_deg=0.0,
            )
            add_seam("seam_waist_left_front", "waistband", "attach_front_left", "left_front_leg", "waist_top", EdgeRole.SEWN, ev_cid="lower_waistband")
            add_seam("seam_waist_right_front", "waistband", "attach_front_right", "right_front_leg", "waist_top", EdgeRole.SEWN, ev_cid="lower_waistband")
            add_seam("seam_waist_left_back", "waistband", "attach_back_left", "left_back_leg", "waist_top", EdgeRole.SEWN, ev_cid="lower_waistband", force_state=back_st)
            add_seam("seam_waist_right_back", "waistband", "attach_back_right", "right_back_leg", "waist_top", EdgeRole.SEWN, ev_cid="lower_waistband", force_state=back_st)

            if has_fly:
                fl_st, flc, flu, fl_imgs, fl_views, _ = comp_state("fly")
                fly_len = next(e.length_m for e in pieces["left_front_leg"].edges if e.edge_id == "fly_opening")
                pieces["fly_shield"] = _rect_piece(
                    "fly_shield", PatternPieceType.FLY_SHIELD, "Center Front Fly Shield", "fly",
                    0.055, fly_len, evidence_refs=fl_imgs, source_views=fl_views,
                    verification_state=fl_st, confidence=flc, uncertainty=flu,
                )
                add_seam("seam_fly_left", "left_front_leg", "fly_opening", "fly_shield", "left", EdgeRole.ZIPPER_ATTACHMENT, ev_cid="fly")

            if not is_absent("back_pocket"):
                bp_st, bpc, bpu, bp_imgs, bp_views, _ = comp_state("back_pocket")
                if has_back_view or is_detected_or_candidate("back_pocket", default=False):
                    pieces["back_pocket_left"] = _rect_piece(
                        "back_pocket_left", PatternPieceType.POCKET, "Rear Patch Pocket (Left)", "back_pocket",
                        0.13, 0.14, roles=(EdgeRole.POCKET_ATTACHMENT, EdgeRole.POCKET_ATTACHMENT, EdgeRole.HEMMED, EdgeRole.POCKET_ATTACHMENT),
                        evidence_refs=bp_imgs, source_views=bp_views, verification_state=bp_st, confidence=bpc, uncertainty=bpu,
                    )
                    add_seam("seam_back_pocket_l", "left_back_leg", "waist_top", "back_pocket_left", "bottom", EdgeRole.POCKET_ATTACHMENT, ev_cid="back_pocket")
                else:
                    add_record("rear_pocket_construction", "back_pocket", "rear_view_missing", "back_pocket",
                               force_state=ConstructionVerificationState.UNSUPPORTED,
                               note="Rear pockets unobservable without a rear trouser photograph.")

            add_record("trouser_four_panel_assembly", "left_leg", "bifurcated_leg_topology")
            add_record("crotch_fly_closure", "fly", "center_rise_evidence")
            req_comps = ("lower_waistband", "left_leg", "right_leg")
            order = [pid for pid in ("left_front_leg", "right_front_leg", "left_back_leg", "right_back_leg",
                                     "fly_shield", "waistband", "back_pocket_left") if pid in pieces]

        # ── CATEGORY 2: TRADITIONAL GARMENTS ─────────────────────────────────
        elif cat in {"traditional", "ethnic_wear", "cultural_wear"} or any(k in sub for k in ("kurta", "sherwani", "lehenga", "saree", "salwar")):
            if "lehenga" in sub:
                ctype = "lehenga_gored_skirt_and_choli"
                for g_i in range(1, 5):
                    pieces[f"lehenga_gore_{g_i}"] = _rect_piece(
                        f"lehenga_gore_{g_i}", PatternPieceType.LEHENGA_GORE, f"Flared Lehenga Gore {g_i}", "skirt",
                        0.38, 0.96, evidence_refs=comp_state("front_body")[3],
                    )
                for g_i in range(1, 4):
                    add_seam(f"seam_gore_{g_i}", f"lehenga_gore_{g_i}", "right", f"lehenga_gore_{g_i + 1}", "left", EdgeRole.SEWN)
                pieces["waistband"] = _rect_piece("waistband", PatternPieceType.WAISTBAND, "Lehenga Waistband", "lower_waistband", 0.78, 0.05)
                add_seam("seam_lehenga_waist", "waistband", "bottom", "lehenga_gore_1", "top", EdgeRole.SEWN)
                add_record("gored_skirt_panel_layout", "skirt", "traditional_lehenga_profile")
                req_comps = ("skirt",)
                order = list(pieces.keys())
            else:
                ctype = "traditional_kurta_chak"
                tunic_h = max(0.82, torso_h)
                slit_h = 0.24
                fb_st, fbc, fbu, fb_imgs, fb_views, _ = comp_state("front_body")
                bb_st = ConstructionVerificationState.OBSERVED if has_back_view else ConstructionVerificationState.INFERRED
                bb_u = 0.25 if has_back_view else 0.72

                pieces["front_body"] = _bodice_shell_piece(
                    "front_body", PatternPieceType.FRONT_BODY, "Kurta Front Tunic Panel", "front_body",
                    chest_half, tunic_h, has_side_slit=True, slit_height_m=slit_h,
                    evidence_refs=fb_imgs, source_views=fb_views,
                    verification_state=fb_st, confidence=fbc, uncertainty=fbu,
                )
                pieces["back_body"] = _bodice_shell_piece(
                    "back_body", PatternPieceType.BACK_BODY, "Kurta Back Tunic Panel", "back_body",
                    chest_half, tunic_h, neck_drop_m=0.03, has_side_slit=True, slit_height_m=slit_h,
                    evidence_refs=fb_imgs if has_back_view else [],
                    source_views=["back"] if has_back_view else [],
                    verification_state=bb_st, confidence=0.80 if has_back_view else 0.45, uncertainty=bb_u,
                )
                add_seam("seam_shoulder_left", "front_body", "shoulder_left", "back_body", "shoulder_left", EdgeRole.SEWN, ev_cid="front_body")
                add_seam("seam_shoulder_right", "front_body", "shoulder_right", "back_body", "shoulder_right", EdgeRole.SEWN, ev_cid="front_body")
                # Side seams explicitly stop at chak slit! Lower slit edges remain EdgeRole.HEMMED.
                add_seam("seam_side_upper_left", "front_body", "side_left", "back_body", "side_left", EdgeRole.SEWN, ev_cid="front_body",
                         note="Seam terminates above lateral chak side slit.")
                add_seam("seam_side_upper_right", "front_body", "side_right", "back_body", "side_right", EdgeRole.SEWN, ev_cid="front_body",
                         note="Seam terminates above lateral chak side slit.")

                arm_len = next(e.length_m for e in pieces["front_body"].edges if e.edge_id == "armscye_left")
                for side in ("left", "right"):
                    s_st, sc, su, s_imgs, s_views, _ = comp_state(f"{side}_sleeve")
                    pieces[f"{side}_sleeve"] = _sleeve_piece(
                        f"{side}_sleeve", side, sleeve_len, arm_len, 0.26,
                        evidence_refs=s_imgs, source_views=s_views, verification_state=s_st, confidence=sc, uncertainty=su,
                    )
                    add_seam(f"seam_armscye_{side}", "front_body", f"armscye_{side}", f"{side}_sleeve", "sleeve_cap",
                             EdgeRole.SLEEVE_ATTACHMENT, ease=0.02, ev_cid=f"{side}_sleeve")

                neck_len = next(e.length_m for e in pieces["front_body"].edges if e.edge_id == "neckline")
                back_neck_len = next(e.length_m for e in pieces["back_body"].edges if e.edge_id == "neckline")
                col_st, cc, cu, c_imgs, c_views, _ = comp_state("collar")
                col_edges = [
                    _edge("attach_front", EdgeRole.COLLAR_ATTACHMENT, [_pt(0.0, 0.0), _pt(neck_len, 0.0)]),
                    _edge("attach_back", EdgeRole.COLLAR_ATTACHMENT, [_pt(neck_len, 0.0), _pt(neck_len + back_neck_len, 0.0)]),
                    _edge("right", EdgeRole.SEWN, [_pt(neck_len + back_neck_len, 0.0), _pt(neck_len + back_neck_len, 0.035)]),
                    _edge("top", EdgeRole.FOLDED, [_pt(neck_len + back_neck_len, 0.035), _pt(0.0, 0.035)]),
                    _edge("left", EdgeRole.SEWN, [_pt(0.0, 0.035), _pt(0.0, 0.0)]),
                ]
                pieces["mandarin_collar"] = _build_piece_from_edges(
                    "mandarin_collar", PatternPieceType.COLLAR_STAND, "Mandarin Band Collar", "collar", col_edges,
                    evidence_refs=c_imgs, source_views=c_views, verification_state=col_st, confidence=cc, uncertainty=cu,
                    grain_angle_deg=0.0,
                )
                add_seam("seam_mandarin_front", "front_body", "neckline", "mandarin_collar", "attach_front", EdgeRole.COLLAR_ATTACHMENT, ev_cid="collar")
                add_seam("seam_mandarin_back", "back_body", "neckline", "mandarin_collar", "attach_back", EdgeRole.COLLAR_ATTACHMENT, ev_cid="collar")
                pieces["chest_slit_placket"] = _rect_piece(
                    "chest_slit_placket", PatternPieceType.PLACKET, "Center Chest Slit Placket", "button_placket",
                    0.035, 0.24, evidence_refs=comp_state("button_placket")[3],
                    verification_state=comp_state("button_placket")[0],
                )
                add_seam("seam_kurta_placket", "front_body", "hem", "chest_slit_placket", "bottom", EdgeRole.POCKET_ATTACHMENT, ev_cid="button_placket")
                add_record("kurta_side_slits_chak", "front_body", "traditional_kurta_rule",
                           note="Side seams stop at hip level; lower side edges hemmed open.")
                add_record("mandarin_collar_band", "collar", "traditional_kurta_rule")
                req_comps = ("front_body", "collar")
                order = ["front_body", "back_body", "left_sleeve", "right_sleeve", "mandarin_collar", "chest_slit_placket"]

        # ── CATEGORY 3: DRESSES & SKIRTS ─────────────────────────────────────
        elif cat in {"dress", "skirt", "dresses_and_skirts"} or "dress" in sub or "skirt" in sub:
            is_skirt_only = (cat == "skirt" or "skirt" in sub) and "dress" not in sub
            fb_st, fbc, fbu, fb_imgs, fb_views, _ = comp_state("skirt" if is_skirt_only else "bodice")
            back_st = ConstructionVerificationState.OBSERVED if has_back_view else ConstructionVerificationState.INFERRED
            back_u = 0.25 if has_back_view else 0.74

            if is_skirt_only:
                ctype = "skirt_two_panel_waistband"
                sk_len = 0.60
                pieces["skirt_front"] = _rect_piece("skirt_front", PatternPieceType.SKIRT_FRONT, "Front Skirt Panel", "skirt",
                                                    props.hem_width_m, sk_len, evidence_refs=fb_imgs, source_views=fb_views,
                                                    verification_state=fb_st, confidence=fbc, uncertainty=fbu)
                pieces["skirt_back"] = _rect_piece("skirt_back", PatternPieceType.SKIRT_BACK, "Back Skirt Panel", "skirt",
                                                   props.hem_width_m, sk_len,
                                                   evidence_refs=fb_imgs if has_back_view else [],
                                                   verification_state=back_st, confidence=0.78 if has_back_view else 0.42, uncertainty=back_u)
                pieces["waistband"] = _rect_piece("waistband", PatternPieceType.WAISTBAND, "Skirt Waistband", "lower_waistband",
                                                  props.waist_width_m * 2.0, 0.04, evidence_refs=comp_state("lower_waistband")[3])
                add_seam("seam_skirt_side_l", "skirt_front", "left", "skirt_back", "left", EdgeRole.SEWN, ev_cid="skirt")
                add_seam("seam_skirt_side_r", "skirt_front", "right", "skirt_back", "right", EdgeRole.SEWN, ev_cid="skirt")
                add_seam("seam_skirt_waist", "waistband", "bottom", "skirt_front", "top", EdgeRole.SEWN, ev_cid="lower_waistband")
                req_comps = ("skirt",)
                order = ["skirt_front", "skirt_back", "waistband"]
            else:
                ctype = "dress_bodice_skirt_darted"
                bod_h = 0.40
                sk_h = max(0.50, torso_h - bod_h)
                waist_dart = PatternDart(
                    dart_id="bodice_front_waist_dart",
                    apex=_pt(chest_half, 0.14),
                    base_left=_pt(chest_half - 0.015, 0.0),
                    base_right=_pt(chest_half + 0.015, 0.0),
                    depth_m=0.14,
                    angle_deg=12.2,
                )
                pieces["bodice_front"] = _bodice_shell_piece(
                    "bodice_front", PatternPieceType.BODICE_FRONT, "Front Dress Bodice", "bodice",
                    chest_half, bod_h, dart=waist_dart,
                    evidence_refs=fb_imgs, source_views=fb_views,
                    verification_state=fb_st, confidence=fbc, uncertainty=fbu,
                )
                pieces["bodice_back"] = _bodice_shell_piece(
                    "bodice_back", PatternPieceType.BODICE_BACK, "Back Dress Bodice", "bodice",
                    chest_half, bod_h, neck_drop_m=0.04,
                    evidence_refs=fb_imgs if has_back_view else [],
                    verification_state=back_st, confidence=0.78 if has_back_view else 0.42, uncertainty=back_u,
                )
                sk_st, skc, sku, sk_imgs, sk_views, _ = comp_state("skirt")
                pieces["skirt_front"] = _rect_piece(
                    "skirt_front", PatternPieceType.SKIRT_FRONT, "Front Dress Skirt", "skirt",
                    chest_half * 2.0, sk_h, roles=(EdgeRole.HEMMED, EdgeRole.SEWN, EdgeRole.SEWN, EdgeRole.SEWN),
                    evidence_refs=sk_imgs, source_views=sk_views, verification_state=sk_st, confidence=skc, uncertainty=sku,
                )
                pieces["skirt_back"] = _rect_piece(
                    "skirt_back", PatternPieceType.SKIRT_BACK, "Back Dress Skirt", "skirt",
                    chest_half * 2.0, sk_h, roles=(EdgeRole.HEMMED, EdgeRole.SEWN, EdgeRole.SEWN, EdgeRole.SEWN),
                    evidence_refs=sk_imgs if has_back_view else [],
                    verification_state=back_st, confidence=0.78 if has_back_view else 0.42, uncertainty=back_u,
                )
                add_seam("seam_bodice_shoulder_l", "bodice_front", "shoulder_left", "bodice_back", "shoulder_left", EdgeRole.SEWN, ev_cid="bodice")
                add_seam("seam_bodice_shoulder_r", "bodice_front", "shoulder_right", "bodice_back", "shoulder_right", EdgeRole.SEWN, ev_cid="bodice")
                add_seam("seam_bodice_side_l", "bodice_front", "side_left", "bodice_back", "side_left", EdgeRole.SEWN, ev_cid="bodice")
                add_seam("seam_bodice_side_r", "bodice_front", "side_right", "bodice_back", "side_right", EdgeRole.SEWN, ev_cid="bodice")
                add_seam("seam_waist_front", "bodice_front", "hem", "skirt_front", "top", EdgeRole.SEWN, ev_cid="waistline")
                add_seam("seam_waist_back", "bodice_back", "hem", "skirt_back", "top", EdgeRole.SEWN, ev_cid="waistline", force_state=back_st)
                add_seam("seam_skirt_side_l", "skirt_front", "left", "skirt_back", "left", EdgeRole.SEWN, ev_cid="skirt")
                add_seam("seam_skirt_side_r", "skirt_front", "right", "skirt_back", "right", EdgeRole.SEWN, ev_cid="skirt")

                # Sleeves only if observed (e.g. sleeveless dresses omit sleeves cleanly)
                if is_detected_or_candidate("left_sleeve", default=False) or is_detected_or_candidate("right_sleeve", default=False):
                    arm_len = next(e.length_m for e in pieces["bodice_front"].edges if e.edge_id == "armscye_left")
                    for side in ("left", "right"):
                        if not is_absent(f"{side}_sleeve"):
                            s_st, sc, su, s_imgs, s_views, _ = comp_state(f"{side}_sleeve")
                            pieces[f"{side}_sleeve"] = _sleeve_piece(
                                f"{side}_sleeve", side, 0.24, arm_len, 0.22,
                                evidence_refs=s_imgs, source_views=s_views, verification_state=s_st, confidence=sc, uncertainty=su,
                            )
                            add_seam(f"seam_armscye_{side}", "bodice_front", f"armscye_{side}", f"{side}_sleeve", "sleeve_cap", EdgeRole.SLEEVE_ATTACHMENT, ease=0.015, ev_cid=f"{side}_sleeve")

                if not has_back_view:
                    add_record("dress_rear_closure", "dress_closures", "rear_view_missing", "dress_closures",
                               force_state=ConstructionVerificationState.UNSUPPORTED,
                               note="Rear dress zipper/buttons cannot be verified from front view.")
                add_record("bodice_waist_dart_shaping", "bodice", "dress_construction_rule")
                req_comps = ("bodice", "skirt", "waistline")
                order = [p for p in ("bodice_front", "bodice_back", "skirt_front", "skirt_back", "left_sleeve", "right_sleeve") if p in pieces]

        # ── CATEGORY 4: HOODIES ──────────────────────────────────────────────
        elif "hoodie" in sub or cat == "hoodie":
            is_zip = "zip" in sub or is_detected_or_candidate("zipper", default=False)
            ctype = "zip_hoodie_panel_construction" if is_zip else "pullover_hoodie_panel_construction"
            fb_st, fbc, fbu, fb_imgs, fb_views, _ = comp_state("front_body")
            bb_st = ConstructionVerificationState.OBSERVED if has_back_view else ConstructionVerificationState.INFERRED
            bb_u = 0.25 if has_back_view else 0.72

            if is_zip:
                pieces["front_left_body"] = _bodice_shell_piece(
                    "front_left_body", PatternPieceType.FRONT_BODY, "Front Left Hoodie Panel", "front_body",
                    chest_half, torso_h, split_side="left", center_role=EdgeRole.ZIPPER_ATTACHMENT,
                    evidence_refs=fb_imgs, source_views=fb_views, verification_state=fb_st, confidence=fbc, uncertainty=fbu,
                )
                pieces["front_right_body"] = _bodice_shell_piece(
                    "front_right_body", PatternPieceType.FRONT_BODY, "Front Right Hoodie Panel", "front_body",
                    chest_half, torso_h, split_side="right", center_role=EdgeRole.ZIPPER_ATTACHMENT,
                    evidence_refs=fb_imgs, source_views=fb_views, verification_state=fb_st, confidence=fbc, uncertainty=fbu,
                )
                add_seam("seam_front_zipper", "front_left_body", "center_closure", "front_right_body", "center_closure",
                         EdgeRole.ZIPPER_ATTACHMENT, ev_cid="zipper")
                front_anchor = "front_left_body"
            else:
                pieces["front_body"] = _bodice_shell_piece(
                    "front_body", PatternPieceType.FRONT_BODY, "Front Hoodie Body Panel", "front_body",
                    chest_half, torso_h, evidence_refs=fb_imgs, source_views=fb_views,
                    verification_state=fb_st, confidence=fbc, uncertainty=fbu,
                )
                front_anchor = "front_body"

            pieces["back_body"] = _bodice_shell_piece(
                "back_body", PatternPieceType.BACK_BODY, "Back Hoodie Body Panel", "back_body",
                chest_half, torso_h, neck_drop_m=0.03,
                evidence_refs=fb_imgs if has_back_view else [],
                source_views=["back"] if has_back_view else [],
                verification_state=bb_st, confidence=0.80 if has_back_view else 0.45, uncertainty=bb_u,
            )
            if is_zip:
                add_seam("seam_shoulder_left", "front_left_body", "shoulder", "back_body", "shoulder_left", EdgeRole.SEWN, ev_cid="front_body")
                add_seam("seam_shoulder_right", "front_right_body", "shoulder", "back_body", "shoulder_right", EdgeRole.SEWN, ev_cid="front_body")
                add_seam("seam_side_left", "front_left_body", "side_seam", "back_body", "side_left", EdgeRole.SEWN, ev_cid="front_body")
                add_seam("seam_side_right", "front_right_body", "side_seam", "back_body", "side_right", EdgeRole.SEWN, ev_cid="front_body")
                arm_len = next(e.length_m for e in pieces["front_left_body"].edges if e.edge_id == "armscye")
            else:
                add_seam("seam_shoulder_left", "front_body", "shoulder_left", "back_body", "shoulder_left", EdgeRole.SEWN, ev_cid="front_body")
                add_seam("seam_shoulder_right", "front_body", "shoulder_right", "back_body", "shoulder_right", EdgeRole.SEWN, ev_cid="front_body")
                add_seam("seam_side_left", "front_body", "side_left", "back_body", "side_left", EdgeRole.SEWN, ev_cid="front_body")
                add_seam("seam_side_right", "front_body", "side_right", "back_body", "side_right", EdgeRole.SEWN, ev_cid="front_body")
                arm_len = next(e.length_m for e in pieces["front_body"].edges if e.edge_id == "armscye_left")

            for side in ("left", "right"):
                s_st, sc, su, s_imgs, s_views, _ = comp_state(f"{side}_sleeve")
                pieces[f"{side}_sleeve"] = _sleeve_piece(
                    f"{side}_sleeve", side, sleeve_len, arm_len, 0.22,
                    evidence_refs=s_imgs, source_views=s_views, verification_state=s_st, confidence=sc, uncertainty=su,
                )
                b_piece = f"front_{side}_body" if is_zip else "front_body"
                b_edge = "armscye" if is_zip else f"armscye_{side}"
                add_seam(f"seam_armscye_{side}", b_piece, b_edge, f"{side}_sleeve", "sleeve_cap",
                         EdgeRole.SLEEVE_ATTACHMENT, ease=0.02, ev_cid=f"{side}_sleeve")

                c_st, cc, cu, c_imgs, c_views, _ = comp_state("cuff")
                pieces[f"{side}_cuff"] = _rect_piece(
                    f"{side}_cuff", PatternPieceType.SLEEVE_CUFF, f"{side.capitalize()} Ribbed Cuff", "cuff",
                    0.22, 0.065, material_ref="ribbed_knit",
                    evidence_refs=c_imgs, source_views=c_views, verification_state=c_st, confidence=cc, uncertainty=cu,
                )
                add_seam(f"seam_cuff_{side}", f"{side}_sleeve", "cuff_edge", f"{side}_cuff", "top", EdgeRole.SEWN, ev_cid="cuff")

            # Dual-panel hood + hood lining + drawstring channel fold
            h_st, hc, hu, h_imgs, h_views, _ = comp_state("hood")
            hood_neck_w = next(e.length_m for e in pieces[front_anchor].edges if e.edge_id == "neckline")
            if not is_zip:
                hood_neck_w = hood_neck_w * 0.5
            draw_fold = [InternalConstructionLine(line_id="drawstring_channel", kind="fold_line", points=[_pt(0.02, 0.0), _pt(0.02, 0.34)])]
            for side in ("left", "right"):
                pieces[f"hood_{side}_panel"] = _rect_piece(
                    f"hood_{side}_panel", PatternPieceType.HOOD_PANEL, f"Hood {side.capitalize()} Lateral Panel", "hood",
                    max(0.10, hood_neck_w), 0.34, roles=(EdgeRole.COLLAR_ATTACHMENT, EdgeRole.SEWN, EdgeRole.SEWN, EdgeRole.OPEN),
                    evidence_refs=h_imgs, source_views=h_views, verification_state=h_st, confidence=hc, uncertainty=hu,
                )
                pieces[f"hood_{side}_panel"].fold_lines.extend(draw_fold)
            pieces["hood_lining"] = _rect_piece(
                "hood_lining", PatternPieceType.LINING, "Hood Inner Lining", "hood",
                max(0.10, hood_neck_w), 0.34, material_ref="brushed_fleece", verification_state=ConstructionVerificationState.INFERRED,
                confidence=0.50, uncertainty=0.60,
            )
            add_seam("seam_hood_sagittal", "hood_left_panel", "right", "hood_right_panel", "right", EdgeRole.SEWN, ev_cid="hood")
            if is_zip:
                add_seam("seam_hood_neck_l", "front_left_body", "neckline", "hood_left_panel", "bottom", EdgeRole.COLLAR_ATTACHMENT, ev_cid="hood")
                add_seam("seam_hood_neck_r", "front_right_body", "neckline", "hood_right_panel", "bottom", EdgeRole.COLLAR_ATTACHMENT, ev_cid="hood")
            else:
                add_seam("seam_hood_neck", "front_body", "neckline", "hood_left_panel", "bottom", EdgeRole.COLLAR_ATTACHMENT, ease=0.10, ev_cid="hood")
            add_seam("seam_hood_lining", "hood_left_panel", "top", "hood_lining", "top", EdgeRole.LINING_ATTACHMENT, ev_cid="hood",
                     force_state=ConstructionVerificationState.INFERRED)

            wb_st, wbc, wbu, wb_imgs, wb_views, _ = comp_state("waistband")
            if is_zip:
                wb_edges = [
                    _edge("bottom", EdgeRole.FOLDED, [_pt(0.0, 0.0), _pt(chest_half * 2.0, 0.0)]),
                    _edge("right", EdgeRole.SEWN, [_pt(chest_half * 2.0, 0.0), _pt(chest_half * 2.0, 0.065)]),
                    _edge("top_right", EdgeRole.SEWN, [_pt(chest_half * 2.0, 0.065), _pt(chest_half, 0.065)]),
                    _edge("top_left", EdgeRole.SEWN, [_pt(chest_half, 0.065), _pt(0.0, 0.065)]),
                    _edge("left", EdgeRole.SEWN, [_pt(0.0, 0.065), _pt(0.0, 0.0)]),
                ]
                pieces["waistband"] = _build_piece_from_edges(
                    "waistband", PatternPieceType.WAISTBAND, "Ribbed Waistband Hem", "waistband", wb_edges,
                    material_ref="ribbed_knit", evidence_refs=wb_imgs, source_views=wb_views,
                    verification_state=wb_st, confidence=wbc, uncertainty=wbu, grain_angle_deg=0.0,
                )
                add_seam("seam_waistband_hem_l", "front_left_body", "hem", "waistband", "top_left", EdgeRole.SEWN, ev_cid="waistband")
                add_seam("seam_waistband_hem_r", "front_right_body", "hem", "waistband", "top_right", EdgeRole.SEWN, ev_cid="waistband")
            else:
                pieces["waistband"] = _rect_piece(
                    "waistband", PatternPieceType.WAISTBAND, "Ribbed Waistband Hem", "waistband",
                    chest_half * 2.0, 0.065, material_ref="ribbed_knit",
                    evidence_refs=wb_imgs, source_views=wb_views, verification_state=wb_st, confidence=wbc, uncertainty=wbu,
                )
                add_seam("seam_waistband_hem", "front_body", "hem", "waistband", "top", EdgeRole.SEWN, ev_cid="waistband")

            if not is_zip and not is_absent("kangaroo_pocket"):
                kp_st, kpc, kpu, kp_imgs, kp_views, _ = comp_state("kangaroo_pocket")
                pieces["kangaroo_pocket"] = _rect_piece(
                    "kangaroo_pocket", PatternPieceType.POCKET, "Kangaroo Front Pouch Pocket", "kangaroo_pocket",
                    0.34, 0.21, roles=(EdgeRole.POCKET_ATTACHMENT, EdgeRole.OPEN, EdgeRole.POCKET_ATTACHMENT, EdgeRole.OPEN),
                    evidence_refs=kp_imgs, source_views=kp_views, verification_state=kp_st, confidence=kpc, uncertainty=kpu,
                )
                add_seam("seam_kangaroo_pocket", front_anchor, "hem", "kangaroo_pocket", "bottom", EdgeRole.POCKET_ATTACHMENT, ev_cid="kangaroo_pocket")

            add_record("hood_dual_panel_sagittal", "hood", "hoodie_construction_rule")
            add_record("ribbed_waistband_cuffs", "waistband", "hoodie_construction_rule")
            req_comps = ("front_body", "hood", "left_sleeve", "right_sleeve", "waistband")
            order = [p for p in ("front_body", "front_left_body", "front_right_body", "back_body",
                                 "left_sleeve", "right_sleeve", "left_cuff", "right_cuff",
                                 "waistband", "hood_left_panel", "hood_right_panel", "hood_lining", "kangaroo_pocket") if p in pieces]

        # ── CATEGORY 5: JACKETS, SHIRTS, AND GENERAL TOPS ────────────────────
        else:
            is_jacket = cat in {"jacket", "outerwear", "coat"} or any(k in sub for k in ("jacket", "blazer", "coat", "parka"))
            is_shirt = cat == "shirt" or "shirt" in sub and "tshirt" not in sub and "sweatshirt" not in sub
            has_front_split = is_jacket or is_shirt or is_detected_or_candidate("zipper", default=False) or is_detected_or_candidate("button_placket", default=False)
            ctype = "jacket_tailored_construction" if is_jacket else ("tailored_shirt_construction" if is_shirt else "knit_top_construction")
            fb_st, fbc, fbu, fb_imgs, fb_views, _ = comp_state("front_body")
            bb_st = ConstructionVerificationState.OBSERVED if has_back_view else ConstructionVerificationState.INFERRED
            bb_u = 0.25 if has_back_view else 0.72

            closure_role = EdgeRole.ZIPPER_ATTACHMENT if is_detected_or_candidate("zipper", default=False) else EdgeRole.SEWN
            if has_front_split:
                pieces["front_left_body"] = _bodice_shell_piece(
                    "front_left_body", PatternPieceType.FRONT_BODY, "Front Left Body Panel", "front_body",
                    chest_half, torso_h, split_side="left", center_role=closure_role,
                    evidence_refs=fb_imgs, source_views=fb_views, verification_state=fb_st, confidence=fbc, uncertainty=fbu,
                )
                pieces["front_right_body"] = _bodice_shell_piece(
                    "front_right_body", PatternPieceType.FRONT_BODY, "Front Right Body Panel", "front_body",
                    chest_half, torso_h, split_side="right", center_role=closure_role,
                    evidence_refs=fb_imgs, source_views=fb_views, verification_state=fb_st, confidence=fbc, uncertainty=fbu,
                )
                pl_cid = "zipper" if is_detected_or_candidate("zipper", default=False) else "button_placket"
                pl_st, plc, plu, pl_imgs, pl_views, _ = comp_state(pl_cid)
                pieces["placket"] = _rect_piece(
                    "placket", PatternPieceType.PLACKET, "Center Front Closure Placket / Facing", pl_cid,
                    0.045, torso_h * 0.85, evidence_refs=pl_imgs, source_views=pl_views,
                    verification_state=pl_st, confidence=plc, uncertainty=plu,
                )
                add_seam("seam_front_placket_l", "front_left_body", "center_closure", "placket", "left", closure_role, ev_cid=pl_cid)
                add_seam("seam_front_placket_r", "front_right_body", "center_closure", "placket", "right", closure_role, ev_cid=pl_cid)
                neck_host = "front_left_body"
            else:
                pieces["front_body"] = _bodice_shell_piece(
                    "front_body", PatternPieceType.FRONT_BODY, "Front Torso Panel", "front_body",
                    chest_half, torso_h, evidence_refs=fb_imgs, source_views=fb_views,
                    verification_state=fb_st, confidence=fbc, uncertainty=fbu,
                )
                neck_host = "front_body"

            pieces["back_body"] = _bodice_shell_piece(
                "back_body", PatternPieceType.BACK_BODY, "Back Torso Panel", "back_body",
                chest_half, torso_h, neck_drop_m=0.03,
                evidence_refs=fb_imgs if has_back_view else [],
                source_views=["back"] if has_back_view else [],
                verification_state=bb_st, confidence=0.80 if has_back_view else 0.45, uncertainty=bb_u,
            )
            if has_front_split:
                add_seam("seam_shoulder_left", "front_left_body", "shoulder", "back_body", "shoulder_left", EdgeRole.SEWN, ev_cid="front_body")
                add_seam("seam_shoulder_right", "front_right_body", "shoulder", "back_body", "shoulder_right", EdgeRole.SEWN, ev_cid="front_body")
                add_seam("seam_side_left", "front_left_body", "side_seam", "back_body", "side_left", EdgeRole.SEWN, ev_cid="front_body")
                add_seam("seam_side_right", "front_right_body", "side_seam", "back_body", "side_right", EdgeRole.SEWN, ev_cid="front_body")
                arm_len = next(e.length_m for e in pieces["front_left_body"].edges if e.edge_id == "armscye")
            else:
                add_seam("seam_shoulder_left", "front_body", "shoulder_left", "back_body", "shoulder_left", EdgeRole.SEWN, ev_cid="front_body")
                add_seam("seam_shoulder_right", "front_body", "shoulder_right", "back_body", "shoulder_right", EdgeRole.SEWN, ev_cid="front_body")
                add_seam("seam_side_left", "front_body", "side_left", "back_body", "side_left", EdgeRole.SEWN, ev_cid="front_body")
                add_seam("seam_side_right", "front_body", "side_right", "back_body", "side_right", EdgeRole.SEWN, ev_cid="front_body")
                arm_len = next(e.length_m for e in pieces["front_body"].edges if e.edge_id == "armscye_left")

            for side in ("left", "right"):
                if is_absent(f"{side}_sleeve"):
                    continue
                s_st, sc, su, s_imgs, s_views, _ = comp_state(f"{side}_sleeve")
                pieces[f"{side}_sleeve"] = _sleeve_piece(
                    f"{side}_sleeve", side, sleeve_len, arm_len, 0.22 if sleeve_len > 0.3 else 0.30,
                    evidence_refs=s_imgs, source_views=s_views, verification_state=s_st, confidence=sc, uncertainty=su,
                )
                b_piece = f"front_{side}_body" if has_front_split else "front_body"
                b_edge = "armscye" if has_front_split else f"armscye_{side}"
                add_seam(f"seam_armscye_{side}", b_piece, b_edge, f"{side}_sleeve", "sleeve_cap",
                         EdgeRole.SLEEVE_ATTACHMENT, ease=0.02, ev_cid=f"{side}_sleeve")
                if is_jacket or is_shirt or sleeve_len > 0.35:
                    c_st, cc, cu, c_imgs, c_views, _ = comp_state("cuff")
                    pieces[f"{side}_cuff"] = _rect_piece(
                        f"{side}_cuff", PatternPieceType.SLEEVE_CUFF, f"{side.capitalize()} Sleeve Cuff", "cuff",
                        0.22, 0.055, evidence_refs=c_imgs, source_views=c_views, verification_state=c_st, confidence=cc, uncertainty=cu,
                    )
                    add_seam(f"seam_cuff_{side}", f"{side}_sleeve", "cuff_edge", f"{side}_cuff", "top", EdgeRole.SEWN, ev_cid="cuff")

            neck_len = next(e.length_m for e in pieces[neck_host].edges if e.edge_id == "neckline")
            back_neck_len = next(e.length_m for e in pieces["back_body"].edges if e.edge_id == "neckline")
            if is_jacket or is_shirt:
                col_st, cc, cu, c_imgs, c_views, _ = comp_state("collar")
                tot_col_w = (neck_len * 2.0 if has_front_split else neck_len) + back_neck_len
                cs_edges = [
                    _edge("attach_front_l", EdgeRole.COLLAR_ATTACHMENT, [_pt(0.0, 0.0), _pt(neck_len, 0.0)]),
                    _edge("attach_back", EdgeRole.COLLAR_ATTACHMENT, [_pt(neck_len, 0.0), _pt(neck_len + back_neck_len, 0.0)]),
                    _edge("attach_front_r", EdgeRole.COLLAR_ATTACHMENT, [_pt(neck_len + back_neck_len, 0.0), _pt(tot_col_w, 0.0)]),
                    _edge("right", EdgeRole.SEWN, [_pt(tot_col_w, 0.0), _pt(tot_col_w, 0.032)]),
                    _edge("top", EdgeRole.COLLAR_ATTACHMENT, [_pt(tot_col_w, 0.032), _pt(0.0, 0.032)]),
                    _edge("left", EdgeRole.SEWN, [_pt(0.0, 0.032), _pt(0.0, 0.0)]),
                ]
                pieces["collar_stand"] = _build_piece_from_edges(
                    "collar_stand", PatternPieceType.COLLAR_STAND, "Collar Stand Band", "collar_stand", cs_edges,
                    evidence_refs=c_imgs, source_views=c_views, verification_state=col_st, confidence=cc, uncertainty=cu,
                    grain_angle_deg=0.0,
                )
                pieces["collar"] = _rect_piece(
                    "collar", PatternPieceType.COLLAR, "Upper Collar Leaf", "collar",
                    tot_col_w, 0.065, roles=(EdgeRole.COLLAR_ATTACHMENT, EdgeRole.SEWN, EdgeRole.FOLDED, EdgeRole.SEWN),
                    evidence_refs=c_imgs, source_views=c_views, verification_state=col_st, confidence=cc, uncertainty=cu,
                )
                add_seam("seam_collar_to_stand", "collar", "bottom", "collar_stand", "top", EdgeRole.COLLAR_ATTACHMENT, ev_cid="collar")
                add_seam("seam_stand_to_front_l", neck_host, "neckline", "collar_stand", "attach_front_l", EdgeRole.COLLAR_ATTACHMENT, ev_cid="collar")
                add_seam("seam_stand_to_back", "back_body", "neckline", "collar_stand", "attach_back", EdgeRole.COLLAR_ATTACHMENT, ev_cid="collar")
                if has_front_split:
                    add_seam("seam_stand_to_front_r", "front_right_body", "neckline", "collar_stand", "attach_front_r", EdgeRole.COLLAR_ATTACHMENT, ev_cid="collar")
            else:
                nb_st, nbc, nbu, nb_imgs, nb_views, _ = comp_state("neck_opening")
                pieces["neckband"] = _rect_piece(
                    "neckband", PatternPieceType.COLLAR_STAND, "Ribbed Neckband Binding", "neck_opening",
                    neck_len, 0.025, roles=(EdgeRole.BOUND, EdgeRole.SEWN, EdgeRole.FOLDED, EdgeRole.SEWN),
                    evidence_refs=nb_imgs, source_views=nb_views, verification_state=nb_st, confidence=nbc, uncertainty=nbu,
                )
                add_seam("seam_neckband", neck_host, "neckline", "neckband", "bottom", EdgeRole.BOUND, ev_cid="neck_opening")

            if is_jacket and is_detected_or_candidate("chest_pocket", default=False):
                cp_st, cpc, cpu, cp_imgs, cp_views, _ = comp_state("chest_pocket")
                pieces["chest_pocket_left"] = _rect_piece(
                    "chest_pocket_left", PatternPieceType.POCKET, "Left Chest Patch Pocket", "chest_pocket",
                    0.12, 0.13, roles=(EdgeRole.POCKET_ATTACHMENT, EdgeRole.POCKET_ATTACHMENT, EdgeRole.HEMMED, EdgeRole.POCKET_ATTACHMENT),
                    evidence_refs=cp_imgs, source_views=cp_views, verification_state=cp_st, confidence=cpc, uncertainty=cpu,
                )
                add_seam("seam_chest_pocket_l", neck_host, "hem", "chest_pocket_left", "bottom", EdgeRole.POCKET_ATTACHMENT, ev_cid="chest_pocket")

            pieces["hem_facing"] = _rect_piece(
                "hem_facing", PatternPieceType.HEM_FACING, "Lower Hem Facing", "hem",
                chest_half * (1.0 if has_front_split else 2.0), 0.035,
                verification_state=comp_state("hem")[0], evidence_refs=comp_state("hem")[3],
            )
            add_seam("seam_hem_facing", neck_host, "hem", "hem_facing", "top", EdgeRole.HEMMED, ev_cid="hem")
            add_record("upper_body_panel_assembly", "front_body", "category_construction_rule")
            if not has_back_view:
                add_record("rear_body_symmetry_hypothesis", "back_body", "bilateral_symmetry_prior", "back_body",
                           force_state=ConstructionVerificationState.INFERRED,
                           note="Back view not supplied; rear body dimensions follow bilateral symmetry prior.")
            req_comps = ("front_body", "collar") if (is_jacket or is_shirt) else ("front_body", "neck_opening")
            order = [p for p in ("front_body", "front_left_body", "front_right_body", "back_body",
                                 "left_sleeve", "right_sleeve", "left_cuff", "right_cuff",
                                 "collar_stand", "collar", "neckband", "placket", "chest_pocket_left", "hem_facing") if p in pieces]

        # Build UnifiedConstructionGraphContract & Validate Assembly
        confs = [p.confidence for p in pieces.values()] or [0.5]
        uncs = [p.uncertainty for p in pieces.values()] or [0.5]
        ord_idx = {pid: idx for idx, pid in enumerate(order)}
        deps: List[Tuple[str, str]] = []
        seen_deps = set()
        for seam in seams:
            if seam.piece_a in ord_idx and seam.piece_b in ord_idx and seam.piece_a != seam.piece_b:
                pair = (seam.piece_a, seam.piece_b) if ord_idx[seam.piece_a] < ord_idx[seam.piece_b] else (seam.piece_b, seam.piece_a)
                if pair not in seen_deps:
                    seen_deps.add(pair)
                    deps.append(pair)
        graph = UnifiedConstructionGraphContract(
            garment_id=garment_id,
            category=cat,
            subcategory=sub,
            construction_type=ctype,
            component_refs=sorted(fused.keys()) if fused else sorted({p.parent_component for p in pieces.values()}),
            pattern_piece_ids=list(pieces.keys()),
            pieces=pieces,
            seams=seams,
            assembly_order=order,
            assembly_dependencies=deps,
            inference_records=records,
            construction_confidence=round(sum(confs) / len(confs), 4),
            construction_uncertainty=round(sum(uncs) / len(uncs), 4),
            evidence_provenance={
                "has_back_view": has_back_view,
                "generation_latency_ms": round((time.perf_counter() - t0) * 1000.0, 2),
                "taxonomy_version": component_bundle.taxonomy_version if component_bundle else "16.1.0",
            },
        )
        val_report = AssemblyValidator.validate(graph, required_components=req_comps)
        graph.validation_report = val_report

        # Connect target engine compatibility via existing ReconstructionEngineRegistry without modifying builders
        target_engine = reconstruction_registry.get_engine(cat, sub)
        measurements: Dict[str, MeasuredDimension] = {}
        materials: Dict[str, str] = {}
        for piece in pieces.values():
            materials[piece.piece_id] = piece.material_ref
            for dk, dv in piece.dimensions.items():
                measurements.setdefault(f"{piece.piece_id}.{dk}", dv)

        supported_feats = [r.construction_feature for r in records if r.verification_state == ConstructionVerificationState.OBSERVED]
        inferred_feats = [r.construction_feature for r in records if r.verification_state == ConstructionVerificationState.INFERRED]
        missing_feats = [r.construction_feature for r in records if r.verification_state in (ConstructionVerificationState.AMBIGUOUS, ConstructionVerificationState.UNSUPPORTED)]
        invalid_feats = [i.message for i in val_report.issues if i.severity == "ERROR"]

        return ConstructionToGeometryHandoff(
            garment_id=garment_id,
            category=cat,
            subcategory=sub,
            target_engine_id=target_engine.engine_id,
            engine_compatible=val_report.is_valid,
            construction_graph=graph,
            measurements=measurements,
            material_references=materials,
            evidence_supported_features=supported_feats,
            inferred_features=inferred_feats,
            missing_or_ambiguous_features=missing_feats,
            invalid_features=invalid_feats,
            confidence=graph.construction_confidence,
            uncertainty=graph.construction_uncertainty,
            validation_report=val_report,
        )


pattern_construction_engine = PatternConstructionEngine()
