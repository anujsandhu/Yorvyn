"""Real-image component execution and independent Fashionpedia evaluation script for Phase 16.1."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List

import pyarrow.parquet as pq
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.ai.evaluation.component_evaluator import ComponentEvaluator
from backend.app.services.garments.evaluation.dataset_manifest import GarmentEvaluationDataset
from backend.app.services.intelligence.component_evidence import analyze_garment_components
from backend.app.services.intelligence.component_taxonomy import ComponentEvidenceStatus, DetectionState

# Fashionpedia val parquet label mapping (HF detection-datasets/fashionpedia README)
FASHIONPEDIA_ID_TO_NAME = {
    0: "shirt, blouse", 1: "top, t-shirt, sweatshirt", 2: "sweater", 3: "cardigan",
    4: "jacket", 5: "vest", 6: "pants", 7: "shorts", 8: "skirt", 9: "coat", 10: "dress",
    27: "hood", 28: "collar", 29: "lapel", 31: "sleeve", 32: "pocket", 33: "neckline", 35: "zipper",
}

FP_TO_YORVYN_CAT = {
    0: "shirt", 1: "tops", 2: "tops", 3: "jacket", 4: "jacket", 5: "jacket",
    6: "bottoms", 7: "bottoms", 8: "skirt", 9: "jacket", 10: "dress",
}

FP_PART_GROUPS = {
    27: "hood",
    28: "collar",
    29: "lapel",
    31: "sleeve",
    32: "pocket",
    33: "neck_opening",
    35: "zipper",
}


def run_real_photos_execution() -> Dict[str, Any]:
    photos = [
        ("wm_00_jacket_denim.jpg", "jacket", "denim_jacket"),
        ("wm_05_hoodie_pullover.jpg", "hoodie", "pullover_hoodie"),
        ("wm_17_shirt_formal.jpg", "shirt", "formal_shirt"),
        ("wm_21_tshirt_graphic.jpg", "tops", "tshirt"),
        ("wm_25_trousers_chinos.jpg", "bottoms", "chinos"),
        ("wm_41_dress_aline.jpg", "dress", "a_line_dress"),
        ("wm_45_kurta_ethnic.jpg", "traditional", "kurta"),
    ]
    records = []
    for fname, cat, subcat in photos:
        fpath = ROOT / "data/datasets/phase_13_6_real_photos" / fname
        if not fpath.is_file():
            continue
        raw = fpath.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        t0 = time.perf_counter()
        bundle = analyze_garment_components(
            [(fname, raw, "front")],
            garment_id=f"real_{fname.split('.')[0]}",
            category=cat,
            subcategory=subcat,
        )
        ms = round((time.perf_counter() - t0) * 1000.0, 2)
        detected = {
            cid: {
                "detection_state": comp.detection_state.value,
                "visibility": comp.best_visibility.value,
                "confidence": comp.confidence,
                "uncertainty": comp.uncertainty.total_uncertainty,
                "bbox": comp.localized_bbox,
                "decision": comp.downstream_decision.value,
            }
            for cid, comp in bundle.fused_components.items()
            if comp.detection_state == DetectionState.DETECTED
        }
        not_obs = sorted(
            cid for cid, comp in bundle.fused_components.items()
            if comp.evidence_status == ComponentEvidenceStatus.NOT_OBSERVED
        )
        backends = sorted({o.execution_provenance.get("backend", o.model_id) for o in bundle.observations})
        records.append({
            "file": str(fpath.relative_to(ROOT)),
            "sha256": sha,
            "category": cat,
            "subcategory": subcat,
            "latency_ms": ms,
            "backends_executed": backends,
            "detected_components": detected,
            "not_observed_components": not_obs,
            "graph_nodes": len(bundle.structure_graph.nodes),
            "graph_edges": len(bundle.structure_graph.edges),
            "clarification_prompts": bundle.handoff.clarification_prompts,
        })
    return {"count": len(records), "samples": records}


def run_fashionpedia_validation_eval(max_samples: int = 50) -> Dict[str, Any]:
    fp_path = Path(os.path.expanduser(
        "~/.cache/huggingface/hub/datasets--detection-datasets--fashionpedia/"
        "snapshots/80845435ce686b8a9dbf70a05452fbfb8e09cdd7/data/val-00000-of-00001-0b29e85429788213.parquet"
    ))
    if not fp_path.is_file():
        return {"status": "BLOCKED_CACHE_MISSING", "sample_count": 0}

    table = pq.read_table(fp_path)
    gt_list: List[Dict[str, Any]] = []
    pred_list: List[Dict[str, Any]] = []
    sample_ids: List[int] = []

    rows = table.slice(0, min(table.num_rows, 200)).to_pydict()
    for i in range(len(rows["image_id"])):
        if len(gt_list) >= max_samples:
            break
        objs = rows["objects"][i]
        cats = objs["category"]
        bboxes = objs["bbox"]
        w = max(1, int(rows["width"][i]))
        h = max(1, int(rows["height"][i]))

        garment_cats = [FP_TO_YORVYN_CAT[c] for c in cats if c in FP_TO_YORVYN_CAT]
        part_indices = [(c, b) for c, b in zip(cats, bboxes) if c in FP_PART_GROUPS]
        if not garment_cats or not part_indices:
            continue
        yorvyn_cat = garment_cats[0]

        img_bytes = rows["image"][i]["bytes"]
        bundle = analyze_garment_components(
            [(f"fp_{rows['image_id'][i]}.jpg", img_bytes, "front")],
            garment_id=f"fp_{rows['image_id'][i]}",
            category=yorvyn_cat,
            subcategory="",
        )

        # Build GT and Pred maps across Fashionpedia part ontology
        gt_entry: Dict[str, Any] = {}
        for part_id, part_name in FP_PART_GROUPS.items():
            boxes = []
            for c, b in part_indices:
                if c == part_id:
                    # Fashionpedia Pascal VOC format: [xmin, ymin, xmax, ymax] (verify clamping)
                    x0, y0, x1, y1 = b[0] / w, b[1] / h, b[2] / w, b[3] / h
                    if y1 > y0 and x1 > x0:
                        boxes.append((max(0.0, y0), max(0.0, x0), min(1.0, y1), min(1.0, x1)))
            gt_entry[part_name] = {"present": bool(boxes), "bboxes": boxes, "bbox": boxes[0] if boxes else None}

        # Map YORVYN fine-grained components back into Fashionpedia coarse groups
        pred_entry: Dict[str, Any] = {}
        group_boxes: Dict[str, List[Any]] = {name: [] for name in FP_PART_GROUPS.values()}
        group_confs: Dict[str, List[float]] = {name: [] for name in FP_PART_GROUPS.values()}
        for obs in bundle.observations:
            if obs.detection_state != DetectionState.DETECTED:
                continue
            target_group = None
            if obs.component_id in ("left_sleeve", "right_sleeve"):
                target_group = "sleeve"
            elif obs.component_id in ("collar", "collar_stand"):
                target_group = "collar"
            elif obs.component_id in ("lapel",):
                target_group = "lapel"
            elif obs.component_id in ("hood",):
                target_group = "hood"
            elif obs.component_id in ("neck_opening", "neckline", "neckband"):
                target_group = "neck_opening"
            elif obs.component_id in ("zipper",):
                target_group = "zipper"
            elif "pocket" in obs.component_id:
                target_group = "pocket"
            if target_group:
                if obs.localized_bbox if hasattr(obs, "localized_bbox") else obs.bbox:
                    group_boxes[target_group].append(obs.bbox)
                if obs.confidence is not None:
                    group_confs[target_group].append(obs.confidence)

        for name in FP_PART_GROUPS.values():
            p_boxes = group_boxes[name]
            pred_entry[name] = {
                "present": bool(p_boxes),
                "bboxes": p_boxes,
                "bbox": p_boxes[0] if p_boxes else None,
                "confidence": max(group_confs[name]) if group_confs[name] else None,
            }

        gt_list.append(gt_entry)
        pred_list.append(pred_entry)
        sample_ids.append(int(rows["image_id"][i]))

    evaluator = ComponentEvaluator()
    metrics_iou_30 = evaluator.evaluate_component_detections(
        gt_list, pred_list, iou_threshold=0.30, require_boxes=True, dataset_kind="fashionpedia_val_academic_single_view"
    )
    metrics_presence = evaluator.evaluate_component_detections(
        gt_list, pred_list, iou_threshold=0.0, require_boxes=False, dataset_kind="fashionpedia_val_academic_single_view"
    )
    return {
        "status": "ACADEMIC_SINGLE_VIEW_PART_EVALUATION",
        "dataset": "detection-datasets/fashionpedia (val parquet)",
        "license_note": "CC BY 4.0 HF card / CC BY-NC-SA 4.0 internal policy; single-view 2D part boxes only.",
        "missing_axes": [
            "No ground-truth visibility state annotations (OCCLUDED vs OUT_OF_FRAME vs FULLY_VISIBLE)",
            "No multi-view pairs or cross-view garment identity IDs",
            "No garment seam/inseam/outseam/cuff/fly/waistband part boxes in this coarse mapping",
        ],
        "sample_count": len(sample_ids),
        "sample_ids_first_10": sample_ids[:10],
        "localization_metrics_iou_0_30": metrics_iou_30,
        "presence_metrics_no_box_threshold": metrics_presence,
    }


def main() -> None:
    pilot = GarmentEvaluationDataset(ROOT / "data/datasets/manifests/garment_evaluation_pilot_v1.json").load()
    real_photos = run_real_photos_execution()
    fp_eval = run_fashionpedia_validation_eval(max_samples=50)

    out = {
        "phase": "16.1",
        "pilot_manifest_status": pilot,
        "scientific_acceptance_status": "BLOCKED_INCOMPLETE_PILOT_MANIFEST" if pilot["evaluation_state"] != "READY_FOR_REAL_EVALUATION" else "READY",
        "real_photo_execution_evidence": real_photos,
        "fashionpedia_single_view_validation": fp_eval,
    }
    dest = ROOT / "docs/reports/PHASE_16_1_EVALUATION_EVIDENCE.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Saved Phase 16.1 evidence to {dest}")
    print("Pilot manifest:", pilot["evaluation_state"])
    print("Real photos executed:", real_photos["count"])
    print("Fashionpedia val samples:", fp_eval.get("sample_count"), "status:", fp_eval.get("status"))


if __name__ == "__main__":
    main()
