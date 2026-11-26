"""Reference-based geometric metrics for triangular garment surfaces."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, Optional

import numpy as np


def _mesh_digest(mesh: Any) -> str:
    h = hashlib.sha256()
    for arr in (mesh.positions, mesh.indices):
        h.update(np.ascontiguousarray(arr).tobytes())
    return h.hexdigest()


def _sample_surface(mesh: Any, count: int, seed: int):
    vertices = np.asarray(mesh.positions, dtype=np.float64)
    faces = np.asarray(mesh.indices, dtype=np.int64)
    if count <= 0 or vertices.ndim != 2 or vertices.shape[1] != 3 or faces.ndim != 2 or faces.shape[1] != 3:
        raise ValueError("Expected a non-empty triangular mesh and positive sample count")
    if not np.isfinite(vertices).all() or faces.min(initial=0) < 0 or faces.max(initial=-1) >= len(vertices):
        raise ValueError("Mesh has non-finite vertices or invalid face indices")
    triangles = vertices[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    twice_area = np.linalg.norm(cross, axis=1)
    valid = twice_area > 1e-12
    if not valid.any():
        raise ValueError("Mesh has no non-degenerate surface area")
    triangles, cross, areas = triangles[valid], cross[valid], twice_area[valid] / 2
    rng = np.random.default_rng(seed)
    face_ids = rng.choice(len(triangles), size=count, p=areas / areas.sum())
    uv = rng.random((count, 2))
    root = np.sqrt(uv[:, 0])
    bary = np.column_stack((1 - root, root * (1 - uv[:, 1]), root * uv[:, 1]))
    points = np.einsum("ij,ijk->ik", bary, triangles[face_ids])
    normals = cross[face_ids] / np.linalg.norm(cross[face_ids], axis=1, keepdims=True)
    return points, normals


def _nearest(a: np.ndarray, b: np.ndarray):
    try:
        from scipy.spatial import cKDTree
        distances, indices = cKDTree(b).query(a, k=1, workers=1)
        return distances, indices
    except ImportError:
        d = np.empty(len(a), dtype=np.float64)
        ix = np.empty(len(a), dtype=np.int64)
        for start in range(0, len(a), 512):
            delta = a[start:start + 512, None, :] - b[None, :, :]
            sq = np.einsum("ijk,ijk->ij", delta, delta)
            ix[start:start + len(sq)] = sq.argmin(axis=1)
            d[start:start + len(sq)] = np.sqrt(sq.min(axis=1))
        return d, ix


class GeometricEvaluator:
    @staticmethod
    def evaluate_surfaces(prediction: Any, reference: Any, *, sample_count: int = 10000,
                          seed: int = 0, threshold_m: float = 0.01,
                          coordinate_contract: Optional[Dict[str, Any]] = None,
                          evaluation_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        started = time.perf_counter()
        if not coordinate_contract or coordinate_contract.get("units") != "m" or not coordinate_contract.get("coordinate_system"):
            return {"status": "NOT_EVALUATED", "reason": "explicit compatible metric coordinate contract required"}
        if evaluation_context is not None and (evaluation_context.get("allowed") is not True or evaluation_context.get("evaluation_state") != "READY_FOR_REAL_EVALUATION"):
            return {"status": evaluation_context.get("evaluation_state", "NOT_EVALUATED"), "reason": "dataset evaluation gate denied access"}
        if threshold_m <= 0:
            raise ValueError("F-score threshold must be positive")
        pred, pred_n = _sample_surface(prediction, sample_count, seed)
        ref, ref_n = _sample_surface(reference, sample_count, seed)
        p2r, pidx = _nearest(pred, ref)
        r2p, ridx = _nearest(ref, pred)
        precision, recall = float(np.mean(p2r <= threshold_m)), float(np.mean(r2p <= threshold_m))
        fscore = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        normal_dot = np.einsum("ij,ij->i", pred_n, ref_n[pidx])
        abs_normal_dot = np.abs(normal_dot)
        dist = np.concatenate((p2r, r2p))
        return {
            "status": "EVALUATED_WITH_REFERENCE_GEOMETRY" if evaluation_context else "SYNTHETIC_SMOKE_ONLY",
            "metric_name": "surface_geometry", "units": "m",
            "chamfer": {"prediction_to_reference_mean_m": float(p2r.mean()), "reference_to_prediction_mean_m": float(r2p.mean()), "symmetric_mean_m": float((p2r.mean() + r2p.mean()) / 2)},
            "f_score": {"threshold_m": threshold_m, "precision": precision, "recall": recall, "f_score": fscore, "sample_count_per_surface": sample_count},
            "surface_distance": {"mean_m": float(dist.mean()), "median_m": float(np.median(dist)), "p95_m": float(np.percentile(dist, 95)), "max_m": float(dist.max())},
            "normal_consistency": {"oriented_cosine_mean": float(np.mean(normal_dot)), "orientation_invariant_abs_cosine_mean": float(np.mean(abs_normal_dot))},
            "sampling": {"method": "area_weighted_triangle_surface_barycentric", "seed": seed, "sample_count_per_surface": sample_count},
            "coordinate_contract": dict(coordinate_contract), "prediction_sha256": _mesh_digest(prediction), "reference_sha256": _mesh_digest(reference),
            "execution_duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "warnings": ["Synthetic mathematical fixtures are smoke evidence only."] if evaluation_context is None else [],
        }

    @staticmethod
    def evaluate_silhouette(reference_mask: np.ndarray, predicted_mask: np.ndarray) -> Dict[str, Any]:
        ref, pred = np.asarray(reference_mask, dtype=bool), np.asarray(predicted_mask, dtype=bool)
        if ref.ndim != 2 or ref.shape != pred.shape:
            return {"status": "NOT_EVALUATED", "reason": "masks must be two-dimensional with identical resolution"}
        union = np.logical_or(ref, pred).sum()
        inter = np.logical_and(ref, pred).sum()
        iou = float(inter / union) if union else 1.0
        dice = float(2 * inter / (ref.sum() + pred.sum())) if (ref.sum() + pred.sum()) else 1.0
        ref_boundary = ref ^ _erode(ref)
        pred_boundary = pred ^ _erode(pred)
        ref_xy, pred_xy = np.argwhere(ref_boundary), np.argwhere(pred_boundary)
        if len(ref_xy) and len(pred_xy):
            a, _ = _nearest(ref_xy.astype(float), pred_xy.astype(float))
            b, _ = _nearest(pred_xy.astype(float), ref_xy.astype(float))
            boundary = float((a.mean() + b.mean()) / 2)
            precision, recall = float(np.mean(b <= 1.0)), float(np.mean(a <= 1.0))
        else:
            boundary, precision, recall = (0.0, 1.0, 1.0) if not len(ref_xy) and not len(pred_xy) else (float("inf"), 0.0, 0.0)
        return {"status": "SYNTHETIC_SMOKE_ONLY", "iou": iou, "dice": dice, "boundary_chamfer_pixels": boundary,
                "boundary_precision_1px": precision, "boundary_recall_1px": recall, "resolution": list(ref.shape)}

    @staticmethod
    def evaluate_landmarks(reference: Dict[str, Any], prediction: Dict[str, Any], *, normalization_scale: float) -> Dict[str, Any]:
        if not reference or normalization_scale <= 0:
            return {"status": "NOT_EVALUATED", "reason": "reference landmarks and positive normalization scale required"}
        errors = {}
        for name, ref_point in reference.items():
            if name not in prediction:
                continue
            a, b = np.asarray(ref_point, dtype=float), np.asarray(prediction[name], dtype=float)
            if a.shape != (3,) or b.shape != (3,) or not np.isfinite(a).all() or not np.isfinite(b).all():
                return {"status": "NOT_EVALUATED", "reason": f"invalid landmark coordinates: {name}"}
            errors[name] = float(np.linalg.norm(a - b))
        if not errors:
            return {"status": "NOT_EVALUATED", "reason": "no matching landmarks"}
        vals = np.asarray(list(errors.values()))
        return {"status": "SYNTHETIC_SMOKE_ONLY", "mean_error_m": float(vals.mean()),
                "normalized_mean_error": float(vals.mean() / normalization_scale),
                "missing_landmark_rate": float((len(reference) - len(errors)) / len(reference)),
                "per_landmark_error_m": errors}

    @staticmethod
    def project_points(points: np.ndarray, intrinsics: np.ndarray, extrinsics: np.ndarray,
                       image_size: tuple[int, int]) -> Dict[str, Any]:
        """Project world points using K(3x3), world-to-camera [R|t](3x4) and pixel image size (w,h)."""
        K, E, P = np.asarray(intrinsics, float), np.asarray(extrinsics, float), np.asarray(points, float)
        width, height = image_size
        if K.shape != (3, 3) or E.shape != (3, 4) or P.ndim != 2 or P.shape[1] != 3:
            return {"status": "NOT_EVALUATED", "reason": "invalid camera or point matrix shape"}
        if not np.isfinite(K).all() or not np.isfinite(E).all() or not np.isfinite(P).all() or width <= 0 or height <= 0:
            return {"status": "NOT_EVALUATED", "reason": "non-finite camera/points or invalid image resolution"}
        R = E[:, :3]
        if not np.allclose(R @ R.T, np.eye(3), atol=1e-3) or np.linalg.det(R) <= 0 or abs(np.linalg.det(K)) < 1e-12:
            return {"status": "NOT_EVALUATED", "reason": "camera calibration matrices are not valid"}
        camera = (R @ P.T + E[:, 3:4]).T
        visible = camera[:, 2] > 1e-8
        homogeneous = (K @ camera.T).T
        pixels = np.full((len(P), 2), np.nan)
        pixels[visible] = homogeneous[visible, :2] / homogeneous[visible, 2:3]
        return {"status": "SYNTHETIC_SMOKE_ONLY", "pixels": pixels.tolist(), "visible": visible.tolist(),
                "image_size": [width, height], "coordinate_convention": "world_to_camera_positive_z"}

    @staticmethod
    def validate_mesh(mesh: Any) -> Dict[str, Any]:
        from backend.app.services.garments.reconstruction.mesh_validator import GarmentMeshValidator
        report = GarmentMeshValidator.validate(mesh)
        return {"status": "STRUCTURAL_DIAGNOSTICS_ONLY", "is_valid": bool(report.is_valid),
                "is_manifold": bool(report.is_manifold), "degenerate_triangle_count": report.degenerate_triangle_count,
                "boundary_loops": report.boundary_loops, "issues": list(report.issues),
                "quality_score": report.quality_score}


def _erode(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask, 1, constant_values=False)
    result = np.ones(mask.shape, dtype=bool)
    for dy in range(3):
        for dx in range(3):
            result &= padded[dy:dy + mask.shape[0], dx:dx + mask.shape[1]]
    return result
