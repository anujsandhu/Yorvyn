"""Independent 2D pattern geometry, seam topology, and construction graph evaluator (Phase 16.2)."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from backend.app.services.garments.reconstruction.pattern_geometry import (
    Point2DPattern,
    UnifiedConstructionGraphContract,
    validate_polygon_2d,
)


def _poly_chamfer_distance_m(poly_a: List[Point2DPattern], poly_b: List[Point2DPattern]) -> Optional[float]:
    if len(poly_a) < 3 or len(poly_b) < 3:
        return None
    pts_a = np.array([(p.x, p.y) for p in poly_a], dtype=np.float64)
    pts_b = np.array([(p.x, p.y) for p in poly_b], dtype=np.float64)
    d_ab = np.sqrt(((pts_a[:, None, :] - pts_b[None, :, :]) ** 2).sum(axis=2))
    mean_ab = float(d_ab.min(axis=1).mean())
    mean_ba = float(d_ab.min(axis=0).mean())
    return round(0.5 * (mean_ab + mean_ba), 5)


class PatternEvaluator:
    """Evaluates generated construction graphs and 2D pattern geometry against independent references."""

    @staticmethod
    def evaluate_topology_and_consistency(graph: UnifiedConstructionGraphContract) -> Dict[str, Any]:
        """Measure self-contained software topology validity and seam consistency (not accuracy)."""
        valid_polys = 0
        for piece in graph.pieces.values():
            if not validate_polygon_2d(piece.boundary_polygon, piece.edges):
                valid_polys += 1
        total_pieces = max(1, len(graph.pieces))
        deltas = [
            abs(s.edge_a_length_m - s.edge_b_length_m)
            for s in graph.seams
            if s.seam_type.value not in ("POCKET_ATTACHMENT", "LINING_ATTACHMENT")
        ]
        mean_mismatch = round(float(np.mean(deltas)), 5) if deltas else 0.0
        max_mismatch = round(float(np.max(deltas)), 5) if deltas else 0.0
        val_ok = bool(graph.validation_report and graph.validation_report.is_valid)
        return {
            "category": graph.category,
            "pieces_count": len(graph.pieces),
            "seams_count": len(graph.seams),
            "pattern_topology_validity_rate": round(valid_polys / total_pieces, 4),
            "assembly_valid": val_ok,
            "has_cycles": bool(graph.validation_report and graph.validation_report.has_cycles),
            "mean_seam_length_mismatch_m": mean_mismatch,
            "max_seam_length_mismatch_m": max_mismatch,
            "seam_length_mismatch_count": len(graph.validation_report.seam_length_mismatches) if graph.validation_report else 0,
            "measurement_consistency": round(max(0.0, 1.0 - min(1.0, mean_mismatch / 0.10)), 4),
        }

    @staticmethod
    def evaluate_against_reference(
        references: List[UnifiedConstructionGraphContract],
        predictions: List[UnifiedConstructionGraphContract],
        *,
        dataset_kind: str = "synthetic",
    ) -> Dict[str, Any]:
        """Compute boundary error, area error, dimension error, seam precision/recall/F1, and connectivity."""
        if len(references) != len(predictions):
            raise ValueError("Reference and prediction graph counts must match.")
        if not references:
            return {
                "evaluation_status": "NOT_EVALUATED_EMPTY_DATASET",
                "sample_count": 0,
                "by_category": {},
            }

        by_cat: Dict[str, List[Dict[str, Any]]] = {}
        for ref, pred in zip(references, predictions):
            boundary_errs: List[float] = []
            area_errs_pct: List[float] = []
            dim_errs_m: List[float] = []

            matched_pieces = set(ref.pieces.keys()) & set(pred.pieces.keys())
            for pid in matched_pieces:
                rp, pp = ref.pieces[pid], pred.pieces[pid]
                b_err = _poly_chamfer_distance_m(pp.boundary_polygon, rp.boundary_polygon)
                if b_err is not None:
                    boundary_errs.append(b_err)
                if rp.area_m2 > 1e-6:
                    area_errs_pct.append(abs(pp.area_m2 - rp.area_m2) / rp.area_m2 * 100.0)
                for dk, rv in rp.dimensions.items():
                    pv = pp.dimensions.get(dk)
                    if rv.value_m is not None and pv and pv.value_m is not None:
                        dim_errs_m.append(abs(pv.value_m - rv.value_m))

            piece_prec = len(matched_pieces) / max(1, len(pred.pieces))
            piece_rec = len(matched_pieces) / max(1, len(ref.pieces))

            def seam_pair(s):
                pair = tuple(sorted([s.piece_a, s.piece_b]))
                return (pair[0], pair[1], s.seam_type.value)

            ref_seams = {seam_pair(s) for s in ref.seams}
            pred_seams = {seam_pair(s) for s in pred.seams}
            tp_s = len(ref_seams & pred_seams)
            s_prec = tp_s / max(1, len(pred_seams))
            s_rec = tp_s / max(1, len(ref_seams))
            s_f1 = (2 * s_prec * s_rec / (s_prec + s_rec)) if (s_prec + s_rec) > 0 else 0.0

            topo = PatternEvaluator.evaluate_topology_and_consistency(pred)
            rec_dict = {
                "pattern_boundary_error_m": round(float(np.mean(boundary_errs)), 5) if boundary_errs else None,
                "panel_area_error_pct": round(float(np.mean(area_errs_pct)), 3) if area_errs_pct else None,
                "panel_dimension_error_m": round(float(np.mean(dim_errs_m)), 5) if dim_errs_m else None,
                "seam_length_mismatch_m": topo["mean_seam_length_mismatch_m"],
                "seam_precision": round(s_prec, 4),
                "seam_recall": round(s_rec, 4),
                "seam_f1": round(s_f1, 4),
                "panel_connectivity_accuracy": round(0.5 * (piece_prec + piece_rec), 4),
                "construction_graph_accuracy": round(0.5 * (s_f1 + 0.5 * (piece_prec + piece_rec)), 4),
                "pattern_topology_validity": topo["pattern_topology_validity_rate"],
                "measurement_consistency": topo["measurement_consistency"],
            }
            by_cat.setdefault(ref.category, []).append(rec_dict)

        cat_summary: Dict[str, Any] = {}
        for cat, rows in sorted(by_cat.items()):
            summary: Dict[str, Any] = {"sample_count": len(rows)}
            for key in rows[0].keys():
                vals = [r[key] for r in rows if r[key] is not None]
                summary[key] = round(float(np.mean(vals)), 4) if vals else None
            cat_summary[cat] = summary

        return {
            "evaluation_status": (
                "SYNTHETIC_SMOKE_ONLY" if dataset_kind == "synthetic"
                else "EVALUATED_AGAINST_REFERENCE_PATTERNS"
            ),
            "sample_count": len(references),
            "by_category": cat_summary,
        }


pattern_evaluator = PatternEvaluator()
