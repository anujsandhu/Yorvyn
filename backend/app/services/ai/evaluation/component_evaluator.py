"""YORVYN — Independent Component Detection, Localization, Visibility & Calibration Evaluator (Phase 14.27 / Phase 16.1)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from backend.app.services.ai.evaluation.calibration import ConfidenceCalibrator


class ComponentEvaluator:
    """Evaluates per-component precision, recall, F1, box/mask IoU, landmark L2, visibility, and calibration."""

    @staticmethod
    def compute_bbox_iou(
        box_a: Tuple[float, float, float, float],
        box_b: Tuple[float, float, float, float],
    ) -> float:
        y_min_a, x_min_a, y_max_a, x_max_a = box_a
        y_min_b, x_min_b, y_max_b, x_max_b = box_b
        inter_ymin = max(y_min_a, y_min_b)
        inter_xmin = max(x_min_a, x_min_b)
        inter_ymax = min(y_max_a, y_max_b)
        inter_xmax = min(x_max_a, x_max_b)
        inter_area = max(0.0, inter_ymax - inter_ymin) * max(0.0, inter_xmax - inter_xmin)
        area_a = max(0.0, y_max_a - y_min_a) * max(0.0, x_max_a - x_min_a)
        area_b = max(0.0, y_max_b - y_min_b) * max(0.0, x_max_b - x_min_b)
        union_area = area_a + area_b - inter_area
        if union_area <= 0.0:
            return 0.0
        return round(float(inter_area / union_area), 4)

    @staticmethod
    def compute_mask_iou(mask_a: np.ndarray, mask_b: np.ndarray) -> Optional[float]:
        a = np.asarray(mask_a) > 0
        b = np.asarray(mask_b) > 0
        if a.ndim != 2 or a.shape != b.shape:
            return None
        union = int(np.logical_or(a, b).sum())
        if union == 0:
            return 1.0
        return round(float(np.logical_and(a, b).sum() / union), 4)

    @staticmethod
    def best_multi_instance_iou(
        gt_boxes: List[Tuple[float, float, float, float]],
        pred_boxes: List[Tuple[float, float, float, float]],
    ) -> float:
        """Greedy max-IoU bipartite match across multiple annotated instances (e.g. pockets or sleeves)."""
        if not gt_boxes or not pred_boxes:
            return 0.0
        scores = []
        used_pred = set()
        for g_box in gt_boxes:
            best_i = -1
            best_iou = 0.0
            for idx, p_box in enumerate(pred_boxes):
                if idx in used_pred:
                    continue
                val = ComponentEvaluator.compute_bbox_iou(g_box, p_box)
                if val > best_iou:
                    best_iou = val
                    best_i = idx
            if best_i >= 0:
                used_pred.add(best_i)
            scores.append(best_iou)
        return round(float(np.mean(scores)), 4)

    def evaluate_component_detections(
        self,
        ground_truth: List[Dict[str, Any]],
        predictions: List[Dict[str, Any]],
        iou_threshold: float = 0.50,
        require_boxes: bool = False,
        dataset_kind: str = "provided_annotations",
    ) -> Dict[str, Any]:
        """Compute category-by-category detection, localization, visibility, false-absence, and calibration metrics."""
        if len(ground_truth) != len(predictions):
            raise ValueError(
                "Ground-truth and prediction sample counts must match; "
                f"got {len(ground_truth)} and {len(predictions)}."
            )
        if not ground_truth:
            return {
                "macro_precision": 0.0,
                "macro_recall": 0.0,
                "macro_f1": 0.0,
                "macro_iou": None,
                "macro_mask_iou": None,
                "landmark_error": None,
                "visibility_accuracy": None,
                "false_absence_rate": None,
                "per_view_consistency": None,
                "evidence_completeness": None,
                "calibration_ece": None,
                "calibration_brier": None,
                "components": {},
                "sample_count": 0,
                "evaluation_status": "NOT_EVALUATED_EMPTY_DATASET",
            }

        all_comp_names = sorted({k for sample in ground_truth for k in sample.keys()})
        component_stats: Dict[str, Dict[str, Any]] = {}
        vis_matches: List[bool] = []
        false_absence_cases = 0
        total_gt_present = 0
        lm_errors: List[float] = []
        view_consistencies: List[float] = []
        completeness_vals: List[float] = []
        cal_probs: List[float] = []
        cal_hits: List[bool] = []

        for c_name in all_comp_names:
            tp = fp = fn = tn = 0
            c_false_abs = 0
            c_gt_pres = 0
            box_ious: List[float] = []
            mask_ious: List[float] = []
            c_vis_matches: List[bool] = []

            for gt_sample, pred_sample in zip(ground_truth, predictions):
                gt_comp = gt_sample.get(c_name, {"present": False, "bbox": None})
                pred_comp = pred_sample.get(c_name, {"present": False, "bbox": None})
                gt_pres = bool(gt_comp.get("present", False))
                pred_pres = bool(pred_comp.get("present", False))
                pred_absent_verified = bool(pred_comp.get("absent_verified", False))

                if gt_pres:
                    total_gt_present += 1
                    c_gt_pres += 1
                    if pred_absent_verified:
                        false_absence_cases += 1
                        c_false_abs += 1

                if "visibility" in gt_comp and "visibility" in pred_comp and gt_comp["visibility"]:
                    hit = gt_comp["visibility"] == pred_comp["visibility"]
                    vis_matches.append(hit)
                    c_vis_matches.append(hit)

                if "landmark_error" in pred_comp and pred_comp["landmark_error"] is not None:
                    lm_errors.append(float(pred_comp["landmark_error"]))
                if "view_consistency" in pred_comp and pred_comp["view_consistency"] is not None:
                    view_consistencies.append(float(pred_comp["view_consistency"]))
                if "evidence_completeness" in pred_comp and pred_comp["evidence_completeness"] is not None:
                    completeness_vals.append(float(pred_comp["evidence_completeness"]))

                gt_boxes = gt_comp.get("bboxes") or ([gt_comp["bbox"]] if gt_comp.get("bbox") else [])
                pred_boxes = pred_comp.get("bboxes") or ([pred_comp["bbox"]] if pred_comp.get("bbox") else [])

                if gt_pres and pred_pres:
                    if gt_boxes and pred_boxes:
                        iou = self.best_multi_instance_iou(gt_boxes, pred_boxes)
                        box_ious.append(iou)
                        if iou >= iou_threshold:
                            tp += 1
                        else:
                            fp += 1
                    elif require_boxes:
                        # Localization required but missing predicted box: do not fabricate IoU 1.0
                        box_ious.append(0.0)
                        fp += 1
                    else:
                        tp += 1
                    if gt_comp.get("mask") is not None and pred_comp.get("mask") is not None:
                        m_iou = self.compute_mask_iou(gt_comp["mask"], pred_comp["mask"])
                        if m_iou is not None:
                            mask_ious.append(m_iou)
                elif gt_pres and not pred_pres:
                    fn += 1
                elif not gt_pres and pred_pres:
                    fp += 1
                else:
                    tn += 1

                conf = pred_comp.get("confidence")
                if conf is not None and (gt_pres or pred_pres):
                    cal_probs.append(float(conf))
                    cal_hits.append(bool(gt_pres == pred_pres))

            prec = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
            rec = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
            f1 = round(2 * prec * rec / (prec + rec), 4) if (prec + rec) > 0 else 0.0
            mean_box_iou = round(float(np.mean(box_ious)), 4) if box_ious else None
            mean_mask_iou = round(float(np.mean(mask_ious)), 4) if mask_ious else None
            c_vis_acc = round(float(np.mean(c_vis_matches)), 4) if c_vis_matches else None
            c_far = round(c_false_abs / c_gt_pres, 4) if c_gt_pres > 0 else None

            component_stats[c_name] = {
                "precision": prec,
                "recall": rec,
                "f1": f1,
                "mean_iou": mean_box_iou if mean_box_iou is not None else 0.0,
                "bbox_iou": mean_box_iou,
                "mask_iou": mean_mask_iou,
                "visibility_accuracy": c_vis_acc,
                "false_absence_rate": c_far,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "support_positive": c_gt_pres,
                "evaluated_samples": len(ground_truth),
            }

        macro_prec = round(float(np.mean([s["precision"] for s in component_stats.values()])), 4)
        macro_rec = round(float(np.mean([s["recall"] for s in component_stats.values()])), 4)
        macro_f1 = round(float(np.mean([s["f1"] for s in component_stats.values()])), 4)
        valid_box_ious = [s["bbox_iou"] for s in component_stats.values() if s["bbox_iou"] is not None]
        macro_iou = round(float(np.mean(valid_box_ious)), 4) if valid_box_ious else None
        valid_mask_ious = [s["mask_iou"] for s in component_stats.values() if s["mask_iou"] is not None]
        macro_mask_iou = round(float(np.mean(valid_mask_ious)), 4) if valid_mask_ious else None

        ece = ConfidenceCalibrator.compute_ece(cal_probs, cal_hits) if len(cal_probs) >= 10 else None
        brier = ConfidenceCalibrator.compute_brier_score(cal_probs, cal_hits) if len(cal_probs) >= 10 else None

        return {
            "macro_precision": macro_prec,
            "macro_recall": macro_rec,
            "macro_f1": macro_f1,
            "macro_iou": macro_iou if macro_iou is not None else 0.0,
            "macro_bbox_iou": macro_iou,
            "macro_mask_iou": macro_mask_iou,
            "landmark_error": round(float(np.mean(lm_errors)), 4) if lm_errors else None,
            "visibility_accuracy": round(float(np.mean(vis_matches)), 4) if vis_matches else None,
            "false_absence_rate": round(false_absence_cases / total_gt_present, 4) if total_gt_present > 0 else None,
            "per_view_consistency": round(float(np.mean(view_consistencies)), 4) if view_consistencies else None,
            "evidence_completeness": round(float(np.mean(completeness_vals)), 4) if completeness_vals else None,
            "calibration_ece": ece,
            "calibration_brier": brier,
            "components": component_stats,
            "sample_count": len(ground_truth),
            "dataset_kind": dataset_kind,
            "evaluation_status": (
                "SYNTHETIC_SMOKE_ONLY" if dataset_kind == "synthetic"
                else "EVALUATED_AGAINST_PROVIDED_ANNOTATIONS"
            ),
        }


component_evaluator = ComponentEvaluator()
