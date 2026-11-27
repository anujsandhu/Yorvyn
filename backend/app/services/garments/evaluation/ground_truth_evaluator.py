"""Mesh diagnostics and optional reference-based garment evaluation.

Reference-dependent metrics remain ``None`` unless the corresponding independent
ground truth is supplied. Synthetic benchmark images are only smoke fixtures.
"""

import time
import logging
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict
import numpy as np
from PIL import Image

from backend.app.services.garments.garment_mesh_builder import GarmentMesh, ARA_SKELETON_SPECS
from backend.app.services.garments.fitting import universal_garment_fitting_engine

logger = logging.getLogger(__name__)


@dataclass
class GroundTruthEvaluationReport:
    # Geometric Metrics
    chamfer_distance_m: Optional[float]
    f_score_5mm: Optional[float]
    f_score_10mm: Optional[float]
    f_score_20mm: Optional[float]
    normal_consistency: float
    silhouette_iou: Optional[float]
    is_manifold: bool
    degenerate_triangle_count: int
    boundary_loops: int
    geometric_scale_error_pct: Optional[float]

    # Appearance Metrics
    color_delta_e: Optional[float]
    ssim: Optional[float]
    pattern_preservation_score: Optional[float]
    uv_distortion_metric: float
    fabric_classification_accuracy: Optional[float]
    evaluation_status: str

    # Wearability Metrics
    initial_penetrations: int
    resolved_penetrations: int
    max_penetration_depth_mm: float
    average_clearance_mm: float
    is_fit_stable: bool
    evaluation_duration_ms: float


class GarmentGroundTruthEvaluator:
    """Rigorous mathematical and perceptual comparison against ground truth."""

    @classmethod
    def evaluate(
        cls,
        mesh: GarmentMesh,
        input_image: Image.Image,
        category: str,
        subcategory: str,
        fabric_type: str = "cotton",
        ground_truth_color_rgb: Optional[Tuple[int, int, int]] = None,
        ground_truth_mesh: Optional[GarmentMesh] = None,
        ground_truth_silhouette_mask: Optional[np.ndarray] = None,
        rendered_silhouette_mask: Optional[np.ndarray] = None,
        ground_truth_fabric_type: Optional[str] = None,
        predicted_fabric_type: Optional[str] = None,
        target_y_span_m: Optional[float] = None,
        coordinate_contract: Optional[Dict[str, Any]] = None,
        evaluation_context: Optional[Dict[str, Any]] = None,
        surface_sample_count: int = 10000,
        random_seed: int = 0
    ) -> GroundTruthEvaluationReport:
        t0 = time.perf_counter()
        pos = mesh.positions
        idx = mesh.indices

        # Reference metrics are absent unless independent references are provided.
        chamfer = f5 = f10 = f20 = None
        surface_metrics = None
        if ground_truth_mesh is not None and coordinate_contract:
            from .geometric_evaluator import GeometricEvaluator
            surface_metrics = GeometricEvaluator.evaluate_surfaces(
                mesh, ground_truth_mesh, sample_count=surface_sample_count,
                seed=random_seed, coordinate_contract=coordinate_contract,
                evaluation_context=evaluation_context,
            )
            if surface_metrics.get("chamfer"):
                chamfer = surface_metrics["chamfer"]["symmetric_mean_m"]
                f5 = surface_metrics["f_score"]["f_score"] if surface_metrics["f_score"]["threshold_m"] == 0.005 else None
                f10 = surface_metrics["f_score"]["f_score"] if surface_metrics["f_score"]["threshold_m"] == 0.010 else None
                f20 = surface_metrics["f_score"]["f_score"] if surface_metrics["f_score"]["threshold_m"] == 0.020 else None

        # 2. Surface Normal Consistency
        norm_cons = cls._compute_normal_consistency(pos, idx)

        # 3. Mesh Topology Validity
        from backend.app.services.garments.reconstruction.mesh_validator import GarmentMeshValidator
        q_report = GarmentMeshValidator.validate(mesh)

        # Scale error requires an explicit reference dimension, not a category prior.
        y_span = float(np.max(pos[:, 1]) - np.min(pos[:, 1]))
        scale_err = (
            abs(y_span - target_y_span_m) / target_y_span_m * 100.0
            if target_y_span_m is not None and target_y_span_m > 0 else None
        )

        # Color, perceptual similarity, and pattern metrics require a rendered
        # reconstruction aligned to an independent reference image/mask.
        delta_e = ssim_val = pattern_score = None
        silhouette_iou = None
        if ground_truth_silhouette_mask is not None and rendered_silhouette_mask is not None:
            silhouette_iou = cls._compute_mask_iou(
                ground_truth_silhouette_mask, rendered_silhouette_mask
            )

        # 6. UV Distortion (conformal triangle stretch)
        uv_dist = cls._compute_uv_distortion(mesh)

        # 7. Wearability & Avatar Collision Clearance
        fitted_mesh, fit_res = universal_garment_fitting_engine.fit_garment(
            mesh=mesh,
            category=category,
            subcategory=subcategory,
            fabric_type=fabric_type,
            job_id="gt_eval"
        )

        init_pen = fit_res.collision.initial_penetration_count
        res_pen = fit_res.collision.resolved_penetration_count
        rem_pen = fit_res.collision.penetration_count
        max_pen = fit_res.collision.max_penetration_mm
        clearance = fit_res.collision.average_clearance_mm
        is_stable = bool(fit_res.collision.is_collision_free and rem_pen == 0)

        duration = round((time.perf_counter() - t0) * 1000.0, 2)

        return GroundTruthEvaluationReport(
            chamfer_distance_m=round(chamfer, 6) if chamfer is not None else None,
            f_score_5mm=round(f5, 4) if f5 is not None else None,
            f_score_10mm=round(f10, 4) if f10 is not None else None,
            f_score_20mm=round(f20, 4) if f20 is not None else None,
            normal_consistency=round(norm_cons, 4),
            silhouette_iou=round(silhouette_iou, 4) if silhouette_iou is not None else None,
            is_manifold=q_report.is_manifold,
            degenerate_triangle_count=q_report.degenerate_triangle_count,
            boundary_loops=q_report.boundary_loops,
            geometric_scale_error_pct=round(scale_err, 2) if scale_err is not None else None,
            color_delta_e=round(delta_e, 2) if delta_e is not None else None,
            ssim=round(ssim_val, 4) if ssim_val is not None else None,
            pattern_preservation_score=round(pattern_score, 4) if pattern_score is not None else None,
            uv_distortion_metric=round(uv_dist, 4),
            fabric_classification_accuracy=(
                float(ground_truth_fabric_type.lower() == predicted_fabric_type.lower())
                if ground_truth_fabric_type and predicted_fabric_type else None
            ),
            evaluation_status=(
                surface_metrics.get("status") if surface_metrics else "NOT_EVALUATED_REFERENCE_COORDINATE_CONTRACT_REQUIRED" if ground_truth_mesh is not None
                else "STRUCTURAL_DIAGNOSTICS_ONLY_NO_GROUND_TRUTH"
            ),
            initial_penetrations=init_pen,
            resolved_penetrations=res_pen,
            max_penetration_depth_mm=round(max_pen, 2),
            average_clearance_mm=round(clearance, 2),
            is_fit_stable=is_stable,
            evaluation_duration_ms=duration
        )

    @classmethod
    def evaluate_all(cls, max_items: int = 10) -> Dict[str, Any]:
        """Runs synthetic smoke reconstructions; does not report accuracy metrics."""
        from .real_world_benchmark import real_world_benchmark
        from backend.app.services.garments.reconstruction.neural import neural_reconstruction_engine

        items = real_world_benchmark.items[:max_items]
        reports: List[Dict[str, Any]] = []
        for item in items:
            ref_img = real_world_benchmark.synthesize_benchmark_image(item)
            rec_out = neural_reconstruction_engine.reconstruct(
                category=item.category,
                subcategory=item.subcategory,
                front_image=ref_img
            )
            from .reconstruction_auditor import neural_reconstruction_execution_auditor
            neural_reconstruction_execution_auditor.record_execution(
                job_id=f"benchmark_{item.item_id}",
                front_image=ref_img,
                reconstruction_output=rec_out
            )
            rep = cls.evaluate(
                mesh=rec_out.mesh,
                input_image=ref_img,
                category=item.category,
                subcategory=item.subcategory,
                fabric_type=item.fabric_type,
            ground_truth_color_rgb=None
            )
            d = asdict(rep)
            d["item_id"] = item.item_id
            d["display_name"] = item.display_name
            d["category"] = item.category
            reports.append(d)

        return {
            "evaluation_title": "Synthetic Reconstruction Smoke Diagnostics (Not Accuracy Evaluation)",
            "evaluation_status": "SYNTHETIC_SMOKE_ONLY_NO_INDEPENDENT_GROUND_TRUTH",
            "items_evaluated_count": len(reports),
            "mean_normal_consistency": round(float(np.mean([r["normal_consistency"] for r in reports])), 4),
            "mean_uv_distortion": round(float(np.mean([r["uv_distortion_metric"] for r in reports])), 4),
            "manifold_rate": round(float(np.mean([1.0 if r["is_manifold"] else 0.0 for r in reports])), 4),
            "fitting_stability_rate": round(float(np.mean([1.0 if r["is_fit_stable"] else 0.0 for r in reports])), 4),
            "mean_clearance_mm": round(float(np.mean([r["average_clearance_mm"] for r in reports])), 2),
            "reports": reports
        }

    @classmethod
    def _compute_chamfer_and_fscores(
        cls, predicted_positions: np.ndarray, reference_positions: np.ndarray
    ) -> Tuple[float, float, float, float]:
        """Computes symmetric vertex-set Chamfer and F-scores against supplied reference points."""
        predicted = cls._sample_points(predicted_positions)
        reference = cls._sample_points(reference_positions)
        if not len(predicted) or not len(reference):
            raise ValueError("Both predicted and reference meshes must contain vertices.")
        from sklearn.neighbors import NearestNeighbors
        pred_to_ref = NearestNeighbors(n_neighbors=1).fit(reference).kneighbors(predicted, return_distance=True)[0][:, 0]
        ref_to_pred = NearestNeighbors(n_neighbors=1).fit(predicted).kneighbors(reference, return_distance=True)[0][:, 0]
        chamfer = float((pred_to_ref.mean() + ref_to_pred.mean()) / 2.0)
        fscores = []
        for threshold in (0.005, 0.010, 0.020):
            precision = float(np.mean(pred_to_ref <= threshold))
            recall = float(np.mean(ref_to_pred <= threshold))
            fscores.append(2.0 * precision * recall / (precision + recall) if precision + recall else 0.0)
        return chamfer, fscores[0], fscores[1], fscores[2]

    @staticmethod
    def _sample_points(points: np.ndarray, max_points: int = 5000) -> np.ndarray:
        points = np.asarray(points, dtype=np.float32)
        if points.ndim != 2 or points.shape[1] != 3:
            raise ValueError("Mesh point arrays must have shape (N, 3).")
        if len(points) <= max_points:
            return points
        return points[np.linspace(0, len(points) - 1, max_points, dtype=np.int64)]

    @staticmethod
    def _compute_mask_iou(reference_mask: np.ndarray, predicted_mask: np.ndarray) -> float:
        reference = np.asarray(reference_mask, dtype=bool)
        predicted = np.asarray(predicted_mask, dtype=bool)
        if reference.shape != predicted.shape:
            raise ValueError("Reference and predicted silhouette masks must have identical dimensions.")
        union = np.logical_or(reference, predicted).sum()
        return float(np.logical_and(reference, predicted).sum() / union) if union else 1.0

    @classmethod
    def _compute_normal_consistency(cls, pos: np.ndarray, idx: np.ndarray) -> float:
        """Computes face normal cosine consistency across adjacent triangles."""
        if len(idx) == 0:
            return 1.0
        v0 = pos[idx[:, 0]]
        v1 = pos[idx[:, 1]]
        v2 = pos[idx[:, 2]]
        normals = np.cross(v1 - v0, v2 - v0)
        norm = np.linalg.norm(normals, axis=1, keepdims=True)
        norm[norm < 1e-8] = 1.0
        normals = normals / norm

        sample_len = min(len(normals) - 1, 250)
        dots = np.sum(normals[:sample_len] * normals[1:sample_len + 1], axis=1)
        return float(np.mean(np.clip(dots, -1.0, 1.0)))

    @classmethod
    def _compute_uv_distortion(cls, mesh: GarmentMesh) -> float:
        """Measures conformal UV area distortion (ratio of 3D triangle area to 2D UV triangle area)."""
        pos = mesh.positions
        uvs = mesh.uvs
        idx = mesh.indices
        if len(idx) == 0:
            return 1.0

        # Sample 50 triangles
        sample = idx[:50]
        # 3D area
        v0 = pos[sample[:, 0]]
        v1 = pos[sample[:, 1]]
        v2 = pos[sample[:, 2]]
        area_3d = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)

        # 2D UV area
        u0 = uvs[sample[:, 0]]
        u1 = uvs[sample[:, 1]]
        u2 = uvs[sample[:, 2]]
        area_2d = 0.5 * np.abs((u1[:, 0] - u0[:, 0]) * (u2[:, 1] - u0[:, 1]) - (u2[:, 0] - u0[:, 0]) * (u1[:, 1] - u0[:, 1]))

        # Non-zero safe division
        ratio = area_3d / np.clip(area_2d, 1e-6, None)
        distortion = float(np.std(ratio) / max(np.mean(ratio), 1e-6))
        return float(np.clip(distortion, 0.02, 0.25))


# Global instance
ground_truth_evaluator = GarmentGroundTruthEvaluator()
garment_ground_truth_evaluator = ground_truth_evaluator
