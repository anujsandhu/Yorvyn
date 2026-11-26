"""Phase 16.2 Pattern Export (JSON, SVG layout sheet, and ASCII DXF R12 entities) with structural parsing checks."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple
import xml.etree.ElementTree as ET

from backend.app.services.garments.reconstruction.pattern_geometry import (
    ConstructionToGeometryHandoff,
    PatternPiece2D,
    UnifiedConstructionGraphContract,
    compute_seam_allowance_polygon,
)


def _layout_pieces(pieces: Dict[str, PatternPiece2D], padding_m: float = 0.08) -> Dict[str, Tuple[float, float]]:
    """Arrange pattern pieces cleanly onto a 2D cutting sheet without overlap."""
    offsets: Dict[str, Tuple[float, float]] = {}
    cursor_x = padding_m
    cursor_y = padding_m
    row_height = 0.0
    max_row_w = 2.20
    for pid, piece in pieces.items():
        xs = [p.x for p in piece.boundary_polygon] or [0.0]
        ys = [p.y for p in piece.boundary_polygon] or [0.0]
        pw = max(xs) - min(xs)
        ph = max(ys) - min(ys)
        if cursor_x + pw + padding_m > max_row_w and cursor_x > padding_m:
            cursor_x = padding_m
            cursor_y += row_height + padding_m
            row_height = 0.0
        offsets[pid] = (cursor_x - min(xs), cursor_y - min(ys))
        cursor_x += pw + padding_m
        row_height = max(row_height, ph)
    return offsets


def export_pattern_json(handoff: ConstructionToGeometryHandoff) -> str:
    return handoff.model_dump_json(indent=2)


def export_pattern_svg(handoff: ConstructionToGeometryHandoff, scale_px_per_m: float = 400.0) -> str:
    graph = handoff.construction_graph
    offsets = _layout_pieces(graph.pieces)
    max_x, max_y = 1.0, 1.0
    for pid, piece in graph.pieces.items():
        ox, oy = offsets[pid]
        for p in piece.boundary_polygon:
            max_x = max(max_x, p.x + ox + 0.1)
            max_y = max(max_y, p.y + oy + 0.1)

    w_px = int(round(max_x * scale_px_per_m))
    h_px = int(round(max_y * scale_px_per_m))
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_px}" height="{h_px}" viewBox="0 0 {w_px} {h_px}">',
        f'  <title>YORVYN Pattern {graph.garment_id} ({graph.category})</title>',
        '  <rect width="100%" height="100%" fill="#ffffff"/>',
    ]

    for pid, piece in graph.pieces.items():
        ox, oy = offsets[pid]
        cut_pts = " ".join(
            f"{round((p.x + ox) * scale_px_per_m, 2)},{round((max_y - (p.y + oy)) * scale_px_per_m, 2)}"
            for p in piece.boundary_polygon
        )
        sa_poly = compute_seam_allowance_polygon(piece.boundary_polygon, piece.seam_allowance_m)
        sa_pts = " ".join(
            f"{round((p.x + ox) * scale_px_per_m, 2)},{round((max_y - (p.y + oy)) * scale_px_per_m, 2)}"
            for p in sa_poly
        )
        stroke_col = "#1e3a8a" if piece.verification_state.value == "OBSERVED" else "#b45309"
        lines.append(f'  <g id="{pid}">')
        lines.append(f'    <polygon points="{sa_pts}" fill="none" stroke="#94a3b8" stroke-width="1" stroke-dasharray="4,3"/>')
        lines.append(f'    <polygon points="{cut_pts}" fill="#f8fafc" fill-opacity="0.6" stroke="{stroke_col}" stroke-width="2"/>')
        gx1, gy1 = round((piece.grainline.start.x + ox) * scale_px_per_m, 2), round((max_y - (piece.grainline.start.y + oy)) * scale_px_per_m, 2)
        gx2, gy2 = round((piece.grainline.end.x + ox) * scale_px_per_m, 2), round((max_y - (piece.grainline.end.y + oy)) * scale_px_per_m, 2)
        lines.append(f'    <line x1="{gx1}" y1="{gy1}" x2="{gx2}" y2="{gy2}" stroke="#0f172a" stroke-width="1.2"/>')
        for dart in piece.darts:
            pts = " ".join(
                f"{round((p.x + ox) * scale_px_per_m, 2)},{round((max_y - (p.y + oy)) * scale_px_per_m, 2)}"
                for p in (dart.base_left, dart.apex, dart.base_right)
            )
            lines.append(f'    <polyline points="{pts}" fill="none" stroke="#dc2626" stroke-width="1.4"/>')
        lx = round((0.5 * (piece.grainline.start.x + piece.grainline.end.x) + ox) * scale_px_per_m, 2)
        ly = round((max_y - (0.5 * (piece.grainline.start.y + piece.grainline.end.y) + oy)) * scale_px_per_m, 2)
        lines.append(f'    <text x="{lx}" y="{ly}" font-size="11" font-family="monospace" text-anchor="middle" fill="#0f172a">{pid} ({piece.area_m2:.3f}m2)</text>')
        lines.append("  </g>")

    lines.append("</svg>")
    return "\n".join(lines)


def export_pattern_dxf(handoff: ConstructionToGeometryHandoff) -> str:
    """Export millimeter-scaled ASCII R12 DXF entities (POLYLINE cut lines, seam allowance, grainline, text)."""
    graph = handoff.construction_graph
    offsets = _layout_pieces(graph.pieces)
    mm = 1000.0
    out: List[str] = [
        "0", "SECTION", "2", "HEADER",
        "9", "$INSUNITS", "70", "4",
        "0", "ENDSEC",
        "0", "SECTION", "2", "ENTITIES",
    ]

    def add_poly(pts, layer: str) -> None:
        out.extend(["0", "POLYLINE", "8", layer, "66", "1", "70", "1"])
        for x, y in pts:
            out.extend(["0", "VERTEX", "8", layer, "10", f"{x:.3f}", "20", f"{y:.3f}", "30", "0.0"])
        out.extend(["0", "SEQEND"])

    for pid, piece in graph.pieces.items():
        ox, oy = offsets[pid]
        add_poly([((p.x + ox) * mm, (p.y + oy) * mm) for p in piece.boundary_polygon], "CUT")
        sa_poly = compute_seam_allowance_polygon(piece.boundary_polygon, piece.seam_allowance_m)
        add_poly([((p.x + ox) * mm, (p.y + oy) * mm) for p in sa_poly], "SEAM_ALLOWANCE")
        out.extend([
            "0", "LINE", "8", "GRAINLINE",
            "10", f"{(piece.grainline.start.x + ox) * mm:.3f}",
            "20", f"{(piece.grainline.start.y + oy) * mm:.3f}",
            "11", f"{(piece.grainline.end.x + ox) * mm:.3f}",
            "21", f"{(piece.grainline.end.y + oy) * mm:.3f}",
        ])
        out.extend([
            "0", "TEXT", "8", "TEXT",
            "10", f"{(piece.grainline.start.x + ox) * mm:.3f}",
            "20", f"{(piece.grainline.start.y + oy) * mm:.3f}",
            "40", "15.0",
            "1", f"{pid}",
        ])

    out.extend(["0", "ENDSEC", "0", "EOF"])
    return "\n".join(out)


def verify_svg_xml(svg_text: str) -> Dict[str, Any]:
    root = ET.fromstring(svg_text)
    groups = root.findall("{http://www.w3.org/2000/svg}g")
    return {"valid_xml": True, "piece_groups": len(groups)}


def verify_dxf_entities(dxf_text: str) -> Dict[str, Any]:
    lines = [line.strip() for line in dxf_text.splitlines()]
    if not lines or lines[-1] != "EOF":
        return {"valid_dxf": False, "reason": "Missing EOF"}
    polylines = sum(1 for i in range(len(lines) - 1) if lines[i] == "0" and lines[i + 1] == "POLYLINE")
    seqends = sum(1 for i in range(len(lines) - 1) if lines[i] == "0" and lines[i + 1] == "SEQEND")
    vertices = sum(1 for i in range(len(lines) - 1) if lines[i] == "0" and lines[i + 1] == "VERTEX")
    return {
        "valid_dxf": polylines > 0 and polylines == seqends and vertices >= polylines * 3,
        "polylines": polylines,
        "seqends": seqends,
        "vertices": vertices,
    }
