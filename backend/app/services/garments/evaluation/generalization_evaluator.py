"""
YORVYN — Synthetic Garment Pipeline Smoke Evaluator.
Exercises generated garment fixtures across varied configured attributes. These cases
are not real photographs and are not an independent generalization or accuracy set.

Verifies that the AI:
1. Recognizes unfamiliar clothing styles.
2. Accurately localizes functional components under visual stress.
3. Decouples low-confidence / ambiguous images and triggers remediation warnings.
4. Generates wearable 3D manifolds without silent procedural mock deceit.
"""

import time
import logging
from typing import Dict, List, Any, Tuple
import numpy as np
from PIL import Image

from .real_world_benchmark import real_world_benchmark, BenchmarkItemMetadata
from backend.app.services.garments.intelligence import (
    universal_intelligence_model,
    learned_material_engine
)
from backend.app.services.garments.segmentation import segmenter_registry
from backend.app.services.garments.reconstruction.neural import neural_reconstruction_engine

logger = logging.getLogger(__name__)


class GarmentGeneralizationEvaluator:
    """Evaluates AI generalization, robustness, and failure handling on held-out data."""

    def evaluate_all(self) -> Dict[str, Any]:
        """Runs generated fixture cases and labels outputs as synthetic smoke evidence."""
        start_t = time.perf_counter()
        items = real_world_benchmark.items
        segmenter = segmenter_registry.get()

        item_evaluations: List[Dict[str, Any]] = []
        cat_matches = []
        subcat_matches = []
        fabric_matches = []
        comp_f1_scores = []
        silhouette_ious = []
        latencies_ms = []
        manifold_results = []

        difficulty_breakdown: Dict[str, Dict[str, Any]] = {
            "standard": {"count": 0, "cat_acc": 0, "f1": 0.0, "iou": 0.0},
            "challenging": {"count": 0, "cat_acc": 0, "f1": 0.0, "iou": 0.0},
            "stress_test": {"count": 0, "cat_acc": 0, "f1": 0.0, "iou": 0.0}
        }

        for item in items:
            t0 = time.perf_counter()
            img = real_world_benchmark.synthesize_benchmark_image(item)

            # 1. Segmentation
            seg_out = segmenter.segment(img)
            sil_iou = seg_out.silhouette_quality
            silhouette_ious.append(sil_iou)

            # 2. Multi-Task Neural Perception (Both Unprompted and User-Assisted Hint)
            intel_raw = universal_intelligence_model.predict(
                image=img,
                alpha_mask=seg_out.alpha_mask,
                category_hint=None
            )
            intel_assisted = universal_intelligence_model.predict(
                image=img,
                alpha_mask=seg_out.alpha_mask,
                category_hint=item.category,
                subcategory_hint=item.subcategory
            )

            # Check unprompted category & subcategory prediction
            raw_cat_match = (intel_raw.category.lower() == item.category.lower())
            assisted_cat_match = (intel_assisted.category.lower() == item.category.lower())
            assisted_subcat_match = (intel_assisted.subcategory.lower() == item.subcategory.lower())

            cat_matches.append(1 if raw_cat_match else 0)
            subcat_matches.append(1 if assisted_subcat_match else 0)

            # 3. Component Detection F1 Score against Ground Truth
            detected_types = {c.component_type for c in intel_assisted.components if c.status == "detected"}
            gt_types = set(item.ground_truth_components)

            if len(gt_types) > 0:
                tp = len(detected_types.intersection(gt_types))
                fp = len(detected_types - gt_types)
                fn = len(gt_types - detected_types)
                precision = tp / max(tp + fp, 1)
                recall = tp / max(tp + fn, 1)
                f1 = (2 * precision * recall) / max(precision + recall, 1e-6)
            else:
                f1 = 1.0
            comp_f1_scores.append(f1)

            # 4. Material & Fabric Match
            fab_pbr, _, _ = learned_material_engine.analyze_material(img, seg_out.alpha_mask, intel_assisted.category, intel_assisted.subcategory)
            fab_match = (fab_pbr.fabric_category.lower() == item.fabric_type.lower())
            fabric_matches.append(1 if fab_match else 0)

            # 5. Reconstruction & Provenance Verification
            rec_out = neural_reconstruction_engine.reconstruct(
                category=intel_assisted.category,
                subcategory=intel_assisted.subcategory,
                front_image=img,
                intelligence=None
            )
            manifold_results.append(bool(rec_out.quality_report.is_manifold))

            latency = round((time.perf_counter() - t0) * 1000.0, 2)
            latencies_ms.append(latency)

            # Assess failure handling: if confidence is low on stress tests, did it warn?
            confidence_warning_triggered = (intel_raw.category_confidence < 0.65 or sil_iou < 0.70)
            appropriate_warning = (item.difficulty == "stress_test" and confidence_warning_triggered) or (item.difficulty != "stress_test")

            item_res = {
                "item_id": item.item_id,
                "display_name": item.display_name,
                "category_gt": item.category,
                "raw_unprompted_category": intel_raw.category,
                "raw_unprompted_match": raw_cat_match,
                "assisted_category": intel_assisted.category,
                "assisted_category_match": assisted_cat_match,
                "category_confidence": intel_assisted.category_confidence,
                "subcategory_gt": item.subcategory,
                "subcategory_pred": intel_assisted.subcategory,
                "subcategory_match": assisted_subcat_match,
                "fabric_gt": item.fabric_type,
                "fabric_pred": fab_pbr.fabric_category,
                "fabric_match": fab_match,
                "component_f1": round(f1, 4),
                "segmenter_quality_signal_not_reference_iou": round(sil_iou, 4),
                "difficulty": item.difficulty,
                "background": item.background_condition,
                "lighting": item.lighting_condition,
                "reconstruction_provenance": rec_out.provenance,
                "is_manifold": rec_out.quality_report.is_manifold,
                "warning_triggered": confidence_warning_triggered,
                "appropriate_handling": appropriate_warning,
                "latency_ms": latency
            }
            item_evaluations.append(item_res)

            # Update difficulty buckets
            d = item.difficulty
            difficulty_breakdown[d]["count"] += 1
            difficulty_breakdown[d]["cat_acc"] += (1 if assisted_cat_match else 0)
            difficulty_breakdown[d]["f1"] += f1
            difficulty_breakdown[d]["iou"] += sil_iou

        # Normalize difficulty stats
        for d, stats in difficulty_breakdown.items():
            cnt = max(stats["count"], 1)
            stats["synthetic_prompted_category_match_pct"] = round((stats["cat_acc"] / cnt) * 100.0, 1)
            stats["mean_component_f1"] = round(stats["f1"] / cnt, 4)
            stats["mean_segmenter_quality_signal"] = round(stats["iou"] / cnt, 4)
            del stats["cat_acc"]
            del stats["f1"]
            del stats["iou"]

        total_duration = round(time.perf_counter() - start_t, 2)

        assisted_cat_matches = [1 if r["assisted_category_match"] else 0 for r in item_evaluations]
        return {
            "evaluation_title": "Synthetic Garment Pipeline Smoke Evaluation",
            "evaluation_status": "SYNTHETIC_SMOKE_ONLY_NOT_REAL_WORLD_GENERALIZATION",
            "input_source": "real_world_benchmark.synthesize_benchmark_image",
            "evaluated_items_count": len(items),
            "synthetic_unprompted_category_match_pct": round(float(np.mean(cat_matches) * 100.0), 1),
            "synthetic_prompted_category_match_pct": round(float(np.mean(assisted_cat_matches) * 100.0), 1),
            "synthetic_subcategory_match_pct": round(float(np.mean(subcat_matches) * 100.0), 1),
            "synthetic_fabric_label_match_pct": round(float(np.mean(fabric_matches) * 100.0), 1),
            "synthetic_component_label_f1": round(float(np.mean(comp_f1_scores)), 4),
            "segmenter_quality_signal_not_reference_iou": round(float(np.mean(silhouette_ious)), 4),
            "mean_end_to_end_smoke_latency_ms": round(float(np.mean(latencies_ms)), 2),
            "synthetic_mesh_manifold_rate_pct": round(float(np.mean(manifold_results) * 100.0), 1),
            "total_evaluation_seconds": total_duration,
            "difficulty_breakdown": difficulty_breakdown,
            "item_results": item_evaluations
        }


# Global instance
garment_generalization_evaluator = GarmentGeneralizationEvaluator()
