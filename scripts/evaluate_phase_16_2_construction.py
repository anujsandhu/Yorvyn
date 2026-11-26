"""Real-image end-to-end Phase 16.2 evaluation & verification script.

Executes Photograph -> Phase 16.1 Components -> Phase 16.2 Construction Graph & 2D Patterns
-> Assembly Validation -> JSON/SVG/DXF Export Verification -> ReconstructionEngineRegistry Handoff,
and enforces fail-closed scientific evaluation integrity on empty pattern ground-truth manifests.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.garments.evaluation.pattern_evaluator import pattern_evaluator
from backend.app.services.garments.reconstruction.engine_registry import reconstruction_registry
from backend.app.services.garments.reconstruction.pattern_exporter import (
    export_pattern_dxf,
    export_pattern_json,
    export_pattern_svg,
    verify_dxf_entities,
    verify_svg_xml,
)
from backend.app.services.garments.reconstruction.pattern_geometry import ConstructionVerificationState
from backend.app.services.intelligence.component_evidence import analyze_garment_components
from backend.app.services.intelligence.pattern_construction_engine import pattern_construction_engine


REAL_PHOTOS = [
    ("wm_00_jacket_denim.jpg", "jacket", "denim_jacket"),
    ("wm_05_hoodie_pullover.jpg", "hoodie", "pullover_hoodie"),
    ("wm_17_shirt_formal.jpg", "shirt", "formal_shirt"),
    ("wm_21_tshirt_graphic.jpg", "tops", "tshirt"),
    ("wm_25_trousers_chinos.jpg", "bottoms", "chinos"),
    ("wm_41_dress_aline.jpg", "dress", "a_line_dress"),
    ("wm_45_kurta_ethnic.jpg", "traditional", "kurta"),
]


def run_real_photo_construction_pipeline() -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for fname, cat, subcat in REAL_PHOTOS:
        fpath = ROOT / "data/datasets/phase_13_6_real_photos" / fname
        raw = fpath.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        gid = f"real_16_2_{fname.split('.')[0]}"

        t0 = time.perf_counter()
        bundle = analyze_garment_components([(fname, raw, "front")], garment_id=gid, category=cat, subcategory=subcat)
        t1 = time.perf_counter()
        handoff = pattern_construction_engine.build_construction(
            gid, cat, subcategory=subcat, component_bundle=bundle,
        )
        t2 = time.perf_counter()

        graph = handoff.construction_graph
        topo = pattern_evaluator.evaluate_topology_and_consistency(graph)
        compat = reconstruction_registry.validate_construction_handoff(handoff)

        svg = export_pattern_svg(handoff)
        dxf = export_pattern_dxf(handoff)
        js = export_pattern_json(handoff)
        svg_ok = verify_svg_xml(svg)
        dxf_ok = verify_dxf_entities(dxf)

        # Evidence integrity check: front-only photo must NEVER mark rear pieces OBSERVED
        rear_observed = [
            pid for pid, p in graph.pieces.items()
            if ("back" in pid or "rear" in pid) and p.verification_state == ConstructionVerificationState.OBSERVED
        ]

        rows.append({
            "file": str(fpath.relative_to(ROOT)),
            "sha256": sha,
            "category": cat,
            "subcategory": subcat,
            "target_engine_id": handoff.target_engine_id,
            "engine_compatible": compat["compatible"],
            "phase_16_1_ms": round((t1 - t0) * 1000.0, 2),
            "phase_16_2_ms": round((t2 - t1) * 1000.0, 2),
            "pieces_count": len(graph.pieces),
            "seams_count": len(graph.seams),
            "pattern_topology_validity_rate": topo["pattern_topology_validity_rate"],
            "assembly_valid": topo["assembly_valid"],
            "has_cycles": topo["has_cycles"],
            "mean_seam_length_mismatch_m": topo["mean_seam_length_mismatch_m"],
            "measurement_consistency": topo["measurement_consistency"],
            "evidence_supported_features": len(handoff.evidence_supported_features),
            "inferred_features": len(handoff.inferred_features),
            "missing_or_ambiguous_features": len(handoff.missing_or_ambiguous_features),
            "rear_marked_observed_violation": len(rear_observed) > 0,
            "json_bytes": len(js.encode("utf-8")),
            "svg_valid_xml": svg_ok["valid_xml"],
            "svg_piece_groups": svg_ok["piece_groups"],
            "dxf_valid": dxf_ok["valid_dxf"],
            "dxf_polylines": dxf_ok["polylines"],
            "piece_ids": list(graph.pieces.keys()),
        })

    return {
        "photo_count": len(rows),
        "all_assembly_valid": all(r["assembly_valid"] for r in rows),
        "all_topology_valid": all(r["pattern_topology_validity_rate"] == 1.0 for r in rows),
        "all_exports_valid": all(r["svg_valid_xml"] and r["dxf_valid"] for r in rows),
        "all_engine_compatible": all(r["engine_compatible"] for r in rows),
        "zero_rear_leakage": all(not r["rear_marked_observed_violation"] for r in rows),
        "samples": rows,
    }


def evaluate_holdout_integrity() -> Dict[str, Any]:
    manifest_path = ROOT / "data/datasets/manifests/garment_evaluation_pilot_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    empty_eval = pattern_evaluator.evaluate_against_reference([], [], dataset_kind="real_holdout")

    # Synthetic self-consistency smoke check (clearly tagged SYNTHETIC_SMOKE_ONLY, not accuracy)
    syn_refs = []
    syn_preds = []
    for _, cat, subcat in REAL_PHOTOS:
        g_ref = pattern_construction_engine.build_construction(f"syn_ref_{cat}", cat, subcategory=subcat).construction_graph
        g_pred = pattern_construction_engine.build_construction(f"syn_pred_{cat}", cat, subcategory=subcat).construction_graph
        syn_refs.append(g_ref)
        syn_preds.append(g_pred)
    syn_eval = pattern_evaluator.evaluate_against_reference(syn_refs, syn_preds, dataset_kind="synthetic")

    return {
        "real_holdout_status": "BLOCKED_NO_LICENSED_PATTERN_GROUND_TRUTH",
        "manifest_path": str(manifest_path.relative_to(ROOT)),
        "manifest_samples": len(manifest.get("samples", [])),
        "fashionpedia_val_parquet_suitability": "NOT_SUITABLE_FOR_2D_PATTERN_OR_SEAM_GROUND_TRUTH (contains single-view 2D bounding boxes only)",
        "fail_closed_evaluator_check": empty_eval,
        "synthetic_smoke_check": syn_eval,
    }


def main() -> None:
    real_exec = run_real_photo_construction_pipeline()
    eval_gate = evaluate_holdout_integrity()
    report = {
        "phase": "16.2",
        "real_photo_execution": real_exec,
        "scientific_evaluation_integrity": eval_gate,
    }
    out_path = ROOT / "docs/reports/PHASE_16_2_EVALUATION_EVIDENCE.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "photo_count": real_exec["photo_count"],
        "all_assembly_valid": real_exec["all_assembly_valid"],
        "all_topology_valid": real_exec["all_topology_valid"],
        "all_exports_valid": real_exec["all_exports_valid"],
        "all_engine_compatible": real_exec["all_engine_compatible"],
        "zero_rear_leakage": real_exec["zero_rear_leakage"],
        "real_holdout_status": eval_gate["real_holdout_status"],
        "report_path": str(out_path.relative_to(ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
