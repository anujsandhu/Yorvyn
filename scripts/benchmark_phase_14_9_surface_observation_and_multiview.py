#!/usr/bin/env python3
"""
YORVYN — Phase 14.9 Workstream D: Multi-View Surface Observation & Uncertainty Benchmark
Evaluates multi-view fusion, concordance, and the 6 physical observation regimes across real multi-view garment sets.

Generates:
- docs/reports/PHASE_14_9_SURFACE_OBSERVATION.json
- docs/reports/PHASE_14_9_MULTIVIEW_EVALUATION.json
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.garments.reconstruction.neural.multi_view_fuser import multi_view_garment_fuser

REPORTS_DIR = PROJECT_ROOT / "docs" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("=" * 80)
    print("YORVYN PHASE 14.9 — WORKSTREAM D: MULTI-VIEW & SURFACE OBSERVATION BENCHMARK")
    print("=" * 80)
    t0 = time.perf_counter()

    multiview_groups = [
        {
            "group_id": "mv_group_01_jacket_denim",
            "category": "outerwear",
            "subcategory": "jacket",
            "front": "data/datasets/phase_13_6_real_photos/wm_00_jacket_denim.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_03_jacket_denim.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_02_jacket_denim.jpg"
        },
        {
            "group_id": "mv_group_02_hoodie_pullover",
            "category": "tops",
            "subcategory": "hoodie",
            "front": "data/datasets/phase_13_6_real_photos/wm_05_hoodie_pullover.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_06_hoodie_pullover.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_07_hoodie_pullover.jpg"
        },
        {
            "group_id": "mv_group_03_sweater_knit",
            "category": "tops",
            "subcategory": "sweater",
            "front": "data/datasets/phase_13_6_real_photos/wm_09_sweater_knit.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_11_sweater_knit.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_10_sweater_knit.jpg"
        },
        {
            "group_id": "mv_group_04_shirt_plaid",
            "category": "tops",
            "subcategory": "shirt",
            "front": "data/datasets/phase_13_6_real_photos/wm_13_shirt_plaid.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_15_shirt_plaid.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_14_shirt_plaid.jpg"
        },
        {
            "group_id": "mv_group_05_shirt_formal",
            "category": "tops",
            "subcategory": "shirt",
            "front": "data/datasets/phase_13_6_real_photos/wm_17_shirt_formal.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_19_shirt_formal.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_18_shirt_formal.jpg"
        },
        {
            "group_id": "mv_group_06_tshirt_graphic",
            "category": "tops",
            "subcategory": "tshirt",
            "front": "data/datasets/phase_13_6_real_photos/wm_21_tshirt_graphic.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_24_tshirt_graphic.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_22_tshirt_graphic.jpg"
        },
        {
            "group_id": "mv_group_07_trousers_chinos",
            "category": "bottoms",
            "subcategory": "trousers",
            "front": "data/datasets/phase_13_6_real_photos/wm_25_trousers_chinos.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_28_trousers_chinos.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_26_trousers_chinos.jpg"
        },
        {
            "group_id": "mv_group_08_jeans_denim",
            "category": "bottoms",
            "subcategory": "jeans",
            "front": "data/datasets/phase_13_6_real_photos/wm_29_jeans_denim.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_31_jeans_denim.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_30_jeans_denim.jpg"
        },
        {
            "group_id": "mv_group_09_shorts_casual",
            "category": "bottoms",
            "subcategory": "shorts",
            "front": "data/datasets/phase_13_6_real_photos/wm_33_shorts_casual.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_36_shorts_casual.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_34_shorts_casual.jpg"
        },
        {
            "group_id": "mv_group_10_skirt_pleated",
            "category": "skirt",
            "subcategory": "pleated_skirt",
            "front": "data/datasets/phase_13_6_real_photos/wm_37_skirt_pleated.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_40_skirt_pleated.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_38_skirt_pleated.jpg"
        },
        {
            "group_id": "mv_group_11_dress_aline",
            "category": "dress",
            "subcategory": "aline_dress",
            "front": "data/datasets/phase_13_6_real_photos/wm_41_dress_aline.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_43_dress_aline.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_42_dress_aline.jpg"
        },
        {
            "group_id": "mv_group_12_kurta_ethnic",
            "category": "tops",
            "subcategory": "kurta",
            "front": "data/datasets/phase_13_6_real_photos/wm_45_kurta_ethnic.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_48_kurta_ethnic.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_46_kurta_ethnic.jpg"
        },
        {
            "group_id": "mv_group_13_jeans_extra",
            "category": "bottoms",
            "subcategory": "jeans",
            "front": "data/datasets/phase_13_6_real_photos/wm_49_jeans_extra.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_51_jeans_extra.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_50_jeans_extra.jpg"
        },
        {
            "group_id": "mv_group_14_shorts_extra",
            "category": "bottoms",
            "subcategory": "shorts",
            "front": "data/datasets/phase_13_6_real_photos/wm_52_shorts_extra.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_54_shorts_extra.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_53_shorts_extra.jpg"
        },
        {
            "group_id": "mv_group_15_dress_extra",
            "category": "dress",
            "subcategory": "dress",
            "front": "data/datasets/phase_13_6_real_photos/wm_57_dress_extra.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_59_dress_extra.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_58_dress_extra.jpg"
        },
        {
            "group_id": "mv_group_16_sweater_extra",
            "category": "tops",
            "subcategory": "sweater",
            "front": "data/datasets/phase_13_6_real_photos/wm_60_sweater_extra.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_62_sweater_extra.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_61_sweater_extra.jpg"
        },
        {
            "group_id": "mv_group_17_tshirt_extra",
            "category": "tops",
            "subcategory": "tshirt",
            "front": "data/datasets/phase_13_6_real_photos/wm_63_tshirt_extra.jpg",
            "rear": "data/datasets/phase_13_6_real_photos/wm_65_tshirt_extra.jpg",
            "side": "data/datasets/phase_13_6_real_photos/wm_64_tshirt_extra.jpg"
        },
        {
            "group_id": "mv_group_18_acc_beanie",
            "category": "accessories",
            "subcategory": "beanie",
            "front": "data/datasets/phase_13_9_real_photos/p13_9_acc_beanie_01.jpg",
            "rear": "data/datasets/phase_13_9_real_photos/p13_9_acc_beanie_02.jpg",
            "side": "data/datasets/phase_13_9_real_photos/p13_9_acc_beanie_03.jpg"
        },
        {
            "group_id": "mv_group_19_acc_belt",
            "category": "accessories",
            "subcategory": "belt",
            "front": "data/datasets/phase_13_9_real_photos/p13_9_acc_belt_01.jpg",
            "rear": "data/datasets/phase_13_9_real_photos/p13_9_acc_belt_02.jpg",
            "side": "data/datasets/phase_13_9_real_photos/p13_9_acc_belt_03.jpg"
        },
        {
            "group_id": "mv_group_20_acc_cap",
            "category": "accessories",
            "subcategory": "cap",
            "front": "data/datasets/phase_13_9_real_photos/p13_9_acc_cap_01.jpg",
            "rear": "data/datasets/phase_13_9_real_photos/p13_9_acc_cap_02.jpg",
            "side": "data/datasets/phase_13_9_real_photos/p13_9_acc_cap_03.jpg"
        }
    ]

    surface_records = []
    multiview_eval_records = []

    for idx, grp in enumerate(multiview_groups, 1):
        gid = grp["group_id"]
        cat = grp["category"]
        subcat = grp["subcategory"]
        f_p = PROJECT_ROOT / grp["front"]
        r_p = PROJECT_ROOT / grp["rear"] if grp.get("rear") else None
        s_p = PROJECT_ROOT / grp["side"] if grp.get("side") else None

        if not f_p.exists():
            continue

        im_front = Image.open(f_p).convert("RGB")
        im_rear = Image.open(r_p).convert("RGB") if (r_p and r_p.exists()) else None
        im_side = Image.open(s_p).convert("RGB") if (s_p and s_p.exists()) else None

        # 1. Single View Evaluation (Front Only)
        _, _, out_s, meta_s = multi_view_garment_fuser.fuse_views(
            im_front, rear_image=None, side_image=None, category=cat, subcategory=subcat
        )

        # 2. Dual View Evaluation (Front + Rear)
        _, _, out_d, meta_d = multi_view_garment_fuser.fuse_views(
            im_front, rear_image=im_rear, side_image=None, category=cat, subcategory=subcat
        )

        # 3. Tri View Evaluation (Front + Rear + Side)
        _, _, out_t, meta_t = multi_view_garment_fuser.fuse_views(
            im_front, rear_image=im_rear, side_image=im_side, category=cat, subcategory=subcat
        )

        surface_records.append({
            "group_id": gid,
            "category": cat,
            "subcategory": subcat,
            "front_path": grp["front"],
            "rear_path": grp.get("rear"),
            "side_path": grp.get("side"),
            "single_view": {
                "regime_ratios": meta_s["regime_breakdown"]["ratios"],
                "mean_confidence": meta_s["regime_breakdown"]["mean_confidence"],
                "uncertainty_score": meta_s["regime_breakdown"]["uncertainty_score"]
            },
            "dual_view": {
                "regime_ratios": meta_d["regime_breakdown"]["ratios"],
                "mean_confidence": meta_d["regime_breakdown"]["mean_confidence"],
                "uncertainty_score": meta_d["regime_breakdown"]["uncertainty_score"]
            },
            "tri_view": {
                "regime_ratios": meta_t["regime_breakdown"]["ratios"],
                "mean_confidence": meta_t["regime_breakdown"]["mean_confidence"],
                "uncertainty_score": meta_t["regime_breakdown"]["uncertainty_score"]
            }
        })

        multiview_eval_records.append({
            "pair_id": gid,
            "category": cat,
            "subcategory": subcat,
            "concordance_score": meta_d["concordance_score"],
            "category_match": meta_d["category_match"],
            "color_similarity": meta_d["color_similarity"],
            "single_view_observed_surface": meta_s["observed_surface_ratio"],
            "dual_view_observed_surface": meta_d["observed_surface_ratio"],
            "tri_view_observed_surface": meta_t["observed_surface_ratio"],
            "reconstruction_time_ms": out_t.reconstruction_time_ms
        })

    # Summary Statistics across all groups
    sv_obs = np.mean([r["single_view"]["regime_ratios"]["directly_observed"] for r in surface_records])
    sv_sym = np.mean([r["single_view"]["regime_ratios"]["symmetry_derived"] for r in surface_records])
    sv_mod = np.mean([r["single_view"]["regime_ratios"]["model_inferred"] for r in surface_records])
    sv_unc = np.mean([r["single_view"]["uncertainty_score"] for r in surface_records])

    dv_obs = np.mean([r["dual_view"]["regime_ratios"]["directly_observed"] for r in surface_records])
    dv_prj = np.mean([r["dual_view"]["regime_ratios"]["multiview_projected"] for r in surface_records])
    dv_unc = np.mean([r["dual_view"]["uncertainty_score"] for r in surface_records])

    tv_obs = np.mean([r["tri_view"]["regime_ratios"]["directly_observed"] for r in surface_records])
    tv_prj = np.mean([r["tri_view"]["regime_ratios"]["multiview_projected"] for r in surface_records])
    tv_unc = np.mean([r["tri_view"]["uncertainty_score"] for r in surface_records])

    mean_concordance = np.mean([r["concordance_score"] for r in multiview_eval_records])
    mean_color_sim = np.mean([r["color_similarity"] for r in multiview_eval_records])
    category_match_rate = sum(1 for r in multiview_eval_records if r["category_match"]) / len(multiview_eval_records)

    surface_doc = {
        "metadata": {
            "phase": "14.9",
            "workstream": "D",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "audit_standard": "Principal Computer Vision & Computational Geometry Engineer",
            "total_groups_evaluated": len(surface_records),
            "six_regimes_defined": [
                "directly_observed",
                "multiview_projected",
                "interpolated",
                "symmetry_derived",
                "model_inferred",
                "unobserved"
            ]
        },
        "aggregate_regime_statistics": {
            "single_view": {
                "directly_observed_mean": round(float(sv_obs), 4),
                "multiview_projected_mean": 0.0,
                "symmetry_derived_mean": round(float(sv_sym), 4),
                "model_inferred_mean": round(float(sv_mod), 4),
                "mean_uncertainty": round(float(sv_unc), 4)
            },
            "dual_view_front_rear": {
                "directly_observed_mean": round(float(dv_obs), 4),
                "multiview_projected_mean": round(float(dv_prj), 4),
                "symmetry_derived_mean": 0.0,
                "total_photographic_observation_mean": round(float(dv_obs + dv_prj), 4),
                "mean_uncertainty": round(float(dv_unc), 4)
            },
            "tri_view_front_side_rear": {
                "directly_observed_mean": round(float(tv_obs), 4),
                "multiview_projected_mean": round(float(tv_prj), 4),
                "symmetry_derived_mean": 0.0,
                "total_photographic_observation_mean": round(float(tv_obs + tv_prj), 4),
                "mean_uncertainty": round(float(tv_unc), 4)
            }
        },
        "evaluations": surface_records
    }

    with open(REPORTS_DIR / "PHASE_14_9_SURFACE_OBSERVATION.json", "w") as f:
        json.dump(surface_doc, f, indent=2)
    print("Saved PHASE_14_9_SURFACE_OBSERVATION.json")

    multiview_doc = {
        "metadata": {
            "phase": "14.9",
            "workstream": "D",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "audit_standard": "Principal Multimodal Retrieval & Vision-Language Engineer",
            "total_pairs_evaluated": len(multiview_eval_records),
            "category_match_rate": round(category_match_rate, 4),
            "mean_color_similarity": round(float(mean_color_sim), 4),
            "mean_concordance_score": round(float(mean_concordance), 4)
        },
        "evaluations": multiview_eval_records
    }

    with open(REPORTS_DIR / "PHASE_14_9_MULTIVIEW_EVALUATION.json", "w") as f:
        json.dump(multiview_doc, f, indent=2)
    print("Saved PHASE_14_9_MULTIVIEW_EVALUATION.json")


if __name__ == "__main__":
    main()
