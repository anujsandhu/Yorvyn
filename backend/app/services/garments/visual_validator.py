"""
YORVYN Phase 17.7 — Server-Side Headless Visual Validation & Diagnostic Renderer.

Renders genuine orthographic multi-view (front, side, rear), wireframe topology,
normal orientation, penetration clearance heatmap, and skeletal landmark overlays
using NumPy + OpenCV + Pillow directly from real loaded garment triangles and Ara
body proxy hulls.

Capability Honesty Note:
Open3D, PyRender, PyVista, and headless Blender are not installed in this runtime, so
this module uses a pure software Z-buffered triangle rasterizer over NumPy/OpenCV/Pillow.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw
from pydantic import BaseModel, Field

from backend.app.services.garments.fitting.garment_asset_inspector import (
    AvatarAnatomicalEnvelope,
    avatar_geometry_analyzer,
)
from backend.app.services.garments.fitting.garment_collision_engine import GarmentCollisionEngine

logger = logging.getLogger(__name__)


class VisualDiagnosticsMetrics(BaseModel):
    renderer_backend: str = "numpy_cv2_software_zbuffer"
    limitation_note: str = (
        "Pure CPU software triangle rasterizer (Open3D/PyRender/Blender not installed); "
        "measures real 3D mesh projections against Ara elliptical body proxy."
    )
    front_coverage_ratio: float = 0.0
    side_depth_to_height_ratio: float = 0.0
    chest_depth_z_m: float = 0.0
    torso_width_x_m: float = 0.0
    head_penetrating_vertices: int = 0
    body_penetrating_vertices: int = 0
    bilateral_symmetry_score: float = 1.0
    outward_normal_score: float = 1.0
    silhouette_spike_anomaly: bool = False
    rendered_views: Dict[str, str] = Field(default_factory=dict)


class BackendVisualValidator:
    """Renders real mesh diagnostics and computes headless visual inspection metrics."""

    CANVAS_W = 360
    CANVAS_H = 520

    def _project_points(
        self,
        pts: np.ndarray,
        view: str,
        *,
        y_min: float = -0.05,
        y_max: float = 1.82,
        x_span: float = 1.15,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Orthographic camera projection (+Z front, +X side, -Z rear) into pixel + depth coords."""
        w, h = self.CANVAS_W, self.CANVAS_H
        scale_y = (h - 40) / max(0.4, (y_max - y_min))
        scale_x = (w - 40) / max(0.4, x_span)
        s = min(scale_x, scale_y)

        px = np.zeros(len(pts), dtype=np.float32)
        depth = np.zeros(len(pts), dtype=np.float32)
        if view == "front":
            px = w * 0.5 + pts[:, 0] * s
            depth = pts[:, 2]
        elif view == "side":
            # Looking from +X so +Z front face is to the right (+px) and -Z back is left
            px = w * 0.5 + (pts[:, 2] - 0.03) * s
            depth = pts[:, 0]
        elif view == "rear":
            px = w * 0.5 - pts[:, 0] * s
            depth = -pts[:, 2]
        else:  # 3/4 view
            ang = math.radians(32.0)
            rx = pts[:, 0] * math.cos(ang) + (pts[:, 2] - 0.03) * math.sin(ang)
            rz = -pts[:, 0] * math.sin(ang) + (pts[:, 2] - 0.03) * math.cos(ang)
            px = w * 0.5 + rx * s
            depth = rz

        py = h - 20.0 - (pts[:, 1] - y_min) * s
        return np.column_stack([px, py]).astype(np.float32), depth

    def _draw_ara_proxy(
        self,
        canvas: np.ndarray,
        view: str,
        avatar: AvatarAnatomicalEnvelope,
    ) -> None:
        """Draws semi-transparent calibrated Ara anatomical silhouette under the garment."""
        overlay = canvas.copy()
        col_body = (72, 82, 98)
        col_head = (95, 108, 128)

        def _ell_poly(cx: float, cy: float, cz: float, rx: float, rz: float, y0: float, y1: float):
            pts = np.array([
                [cx - (rx if view != "side" else rz), y0, cz - (rz if view != "side" else rx)],
                [cx + (rx if view != "side" else rz), y0, cz + (rz if view != "side" else rx)],
                [cx + (rx if view != "side" else rz), y1, cz + (rz if view != "side" else rx)],
                [cx - (rx if view != "side" else rz), y1, cz - (rz if view != "side" else rx)],
            ], dtype=np.float32)
            # In front/rear view X is horizontal, in side view Z is horizontal
            if view == "side":
                p0, _ = self._project_points(np.array([[0.0, y0, cz - rz], [0.0, y0, cz + rz], [0.0, y1, cz + rz], [0.0, y1, cz - rz]], dtype=np.float32), "side")
            else:
                p0, _ = self._project_points(np.array([[cx - rx, y0, cz], [cx + rx, y0, cz], [cx + rx, y1, cz], [cx - rx, y1, cz]], dtype=np.float32), view)
            return p0.astype(np.int32)

        # Torso & pelvis & legs & head
        cv2.fillPoly(overlay, [_ell_poly(0.0, avatar.chest_center_y, avatar.chest_z_center, avatar.chest_width_m * 0.48, avatar.chest_depth_m * 0.50, 0.90, 1.38)], col_body)
        cv2.fillPoly(overlay, [_ell_poly(0.0, avatar.hip_center_y, avatar.hip_z_center, avatar.hip_width_m * 0.48, avatar.hip_depth_m * 0.48, 0.78, 0.96)], col_body)
        for lx in (-0.10, 0.10) if view != "side" else (0.0,):
            cv2.fillPoly(overlay, [_ell_poly(lx, 0.42, 0.01, 0.068, 0.085, 0.04, 0.80)], col_body)
        # Neck & Head circle/ellipse
        hc = np.array([avatar.head_center], dtype=np.float32)
        hp, _ = self._project_points(hc, view)
        hr_px = int(avatar.head_rx * 250)
        hr_py = int(avatar.head_ry * 250)
        cv2.ellipse(overlay, (int(hp[0, 0]), int(hp[0, 1])), (hr_px, hr_py), 0, 0, 360, col_head, -1)
        cv2.fillPoly(overlay, [_ell_poly(0.0, avatar.neck_center[1], avatar.neck_center[2], avatar.neck_rx, avatar.neck_rz, 1.37, 1.48)], col_head)
        cv2.addWeighted(overlay, 0.55, canvas, 0.45, 0, dst=canvas)

    def _rasterize_mesh_view(
        self,
        positions: np.ndarray,
        indices: np.ndarray,
        view: str,
        *,
        mode: str = "shaded",  # shaded, wireframe, normals, penetration
        vertex_colors: Optional[np.ndarray] = None,
        face_normals: Optional[np.ndarray] = None,
        avatar: Optional[AvatarAnatomicalEnvelope] = None,
        title: str = "",
    ) -> np.ndarray:
        w, h = self.CANVAS_W, self.CANVAS_H
        canvas = np.full((h, w, 3), 24, dtype=np.uint8)
        avatar = avatar or avatar_geometry_analyzer.analyze()

        # Subtle grid + ground baseline
        for gy in range(60, h, 60):
            cv2.line(canvas, (0, gy), (w, gy), (34, 38, 46), 1)
        cv2.line(canvas, (w // 2, 20), (w // 2, h - 20), (40, 44, 54), 1)
        self._draw_ara_proxy(canvas, view, avatar)

        pos = np.asarray(positions, dtype=np.float32)
        idx = np.asarray(indices, dtype=np.int64).reshape(-1, 3) if indices is not None and len(indices) > 0 else np.zeros((0, 3), dtype=np.int64)
        if len(pos) < 3 or len(idx) == 0:
            cv2.putText(canvas, f"{title} [EMPTY]", (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 90, 90), 1)
            return canvas

        xy, depth = self._project_points(pos, view)
        pts_tri = xy[idx]  # (T, 3, 2)
        tri_depth = np.mean(depth[idx], axis=1)
        order = np.argsort(tri_depth)  # painter's back-to-front

        # Compute lighting / face colors
        if face_normals is None:
            v0 = pos[idx[:, 0]]
            v1 = pos[idx[:, 1]]
            v2 = pos[idx[:, 2]]
            fn = np.cross(v1 - v0, v2 - v0)
            fn_len = np.linalg.norm(fn, axis=1, keepdims=True)
            face_normals = fn / np.maximum(1e-6, fn_len)

        light_dir = np.array([0.35, 0.55, 0.75] if view != "rear" else [-0.35, 0.55, -0.75], dtype=np.float32)
        light_dir /= np.linalg.norm(light_dir)

        for ti in order:
            poly = pts_tri[ti].astype(np.int32)
            # In front view, skip back-wall triangles behind the torso/head midplane that fall inside head silhouette
            # only so open-front hoods display the face inside the hood opening cleanly; clearance/wireframe/rear show all.
            if view == "front" and mode in {"shaded", "normals"} and tri_depth[ti] < -0.025:
                cy_tri = float(np.mean(pos[idx[ti], 1]))
                cx_tri = float(np.mean(pos[idx[ti], 0]))
                if cy_tri >= 1.46 and abs(cx_tri) <= 0.105:
                    continue
            if mode == "wireframe":
                cv2.polylines(canvas, [poly], True, (110, 210, 255), 1, lineType=cv2.LINE_AA)
                continue

            if mode == "normals":
                n = face_normals[ti]
                col = tuple(int(np.clip((c * 0.5 + 0.5) * 255.0, 20, 250)) for c in (n[2], n[1], n[0]))
            elif mode == "penetration" and vertex_colors is not None:
                c_avg = np.mean(vertex_colors[idx[ti]], axis=0)
                col = (int(c_avg[2]), int(c_avg[1]), int(c_avg[0]))
            else:
                lambert = float(max(0.22, abs(np.dot(face_normals[ti], light_dir))))
                base = np.mean(vertex_colors[idx[ti]], axis=0) if vertex_colors is not None else np.array([150.0, 185.0, 225.0])
                c_lit = np.clip(base * (0.35 + 0.65 * lambert), 20, 252)
                col = (int(c_lit[2]), int(c_lit[1]), int(c_lit[0]))

            cv2.fillConvexPoly(canvas, poly, col)
            if mode == "shaded":
                cv2.polylines(canvas, [poly], True, (38, 46, 60), 1)

        if mode == "landmarks":
            for label, y_val, col_lm in [
                ("HEAD", avatar.head_center[1], (255, 200, 90)),
                ("CHEST", avatar.chest_center_y, (90, 240, 170)),
                ("WAIST", avatar.waist_center_y, (100, 190, 255)),
                ("HIPS", avatar.hip_center_y, (240, 130, 220)),
            ]:
                p_lm, _ = self._project_points(np.array([[-0.35, y_val, 0.0], [0.35, y_val, 0.0]], dtype=np.float32), view)
                y_px = int(p_lm[0, 1])
                cv2.line(canvas, (18, y_px), (w - 18, y_px), col_lm, 1, lineType=cv2.LINE_AA)
                cv2.putText(canvas, label, (14, max(18, y_px - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.40, col_lm, 1)

        if title:
            cv2.putText(canvas, title, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (235, 240, 248), 1, lineType=cv2.LINE_AA)
        return canvas

    def validate_and_render(
        self,
        positions: np.ndarray,
        indices: np.ndarray,
        *,
        normals: Optional[np.ndarray] = None,
        category: str = "tops",
        subcategory: str = "",
        avatar: Optional[AvatarAnatomicalEnvelope] = None,
        output_dir: Optional[Path] = None,
        asset_name: str = "garment",
    ) -> VisualDiagnosticsMetrics:
        pos = np.asarray(positions, dtype=np.float32)
        idx = np.asarray(indices, dtype=np.int64).reshape(-1, 3) if indices is not None and len(indices) > 0 else np.zeros((0, 3), dtype=np.int64)
        avatar = avatar or avatar_geometry_analyzer.analyze()

        if len(pos) < 3 or len(idx) == 0 or not np.all(np.isfinite(pos)):
            return VisualDiagnosticsMetrics(silhouette_spike_anomaly=True)

        # Evaluate vertex clearance vs elliptical Ara body/head/neck hulls
        coll = GarmentCollisionEngine()
        cat_l = (category or "tops").lower()
        sub_l = (subcategory or "").lower()
        is_head_acc = cat_l in {"headwear", "glasses"} or (cat_l == "accessories" and any(k in sub_l for k in ("hat", "cap", "beanie", "glass")))

        max_pen_v = np.zeros(len(pos), dtype=np.float32)
        for h in coll.hulls:
            if is_head_acc and h.name == "head":
                continue
            pen, _, _ = h.resolve_penetrations_batch(pos, min_clearance=0.0030)
            max_pen_v = np.maximum(max_pen_v, pen)

        body_pens = int(np.sum(max_pen_v > 1e-5))
        head_hull = [h for h in coll.hulls if h.name == "head"]
        head_pens = 0
        if head_hull and not is_head_acc:
            hp, _, hm = head_hull[0].resolve_penetrations_batch(pos, min_clearance=0.0020)
            head_pens = int(np.sum(hm))

        # Vertex clearance RGB colors (green = clean, amber = tight <4mm, red = penetrating)
        pen_colors = np.zeros((len(pos), 3), dtype=np.float32)
        pen_colors[:, 1] = 205.0
        pen_colors[:, 0] = 70.0
        pen_colors[:, 2] = 95.0
        tight = (max_pen_v > 0.0) & (max_pen_v <= 0.006)
        severe = max_pen_v > 0.006
        pen_colors[tight] = [245.0, 185.0, 55.0]
        pen_colors[severe] = [240.0, 60.0, 60.0]

        # Quantitative visual / geometric sanity signals
        dims = np.max(pos, axis=0) - np.min(pos, axis=0)
        chest_band = (pos[:, 1] >= 1.12) & (pos[:, 1] <= 1.38) & (np.abs(pos[:, 0]) <= 0.27)
        chest_d = float(np.max(pos[chest_band, 2]) - np.min(pos[chest_band, 2])) if int(np.sum(chest_band)) >= 8 else float(dims[2])
        torso_w = float(np.max(pos[chest_band, 0]) - np.min(pos[chest_band, 0])) if int(np.sum(chest_band)) >= 8 else float(dims[0])
        side_ratio = round(float(dims[2]) / max(0.25, float(dims[1])), 3)

        # X symmetry score
        pos_max_x = float(np.max(pos[:, 0]))
        neg_min_x = float(abs(np.min(pos[:, 0])))
        asym = abs(pos_max_x - neg_min_x) / max(0.05, pos_max_x + neg_min_x)
        sym_score = round(max(0.0, 1.0 - asym), 3)

        # Spike anomaly check (edge length > 25x median)
        v0, v1, v2 = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
        e_lens = np.concatenate([
            np.linalg.norm(v1 - v0, axis=1),
            np.linalg.norm(v2 - v1, axis=1),
            np.linalg.norm(v0 - v2, axis=1),
        ])
        spike = bool(len(e_lens) > 0 and float(np.max(e_lens)) > 25.0 * max(1e-4, float(np.median(e_lens))))

        out_normal_score = 1.0
        if normals is not None and len(normals) == len(pos):
            cen = np.mean(pos, axis=0)
            rad = pos - cen
            rad[:, 1] = 0.0
            valid = np.linalg.norm(rad, axis=1) > 0.06
            if np.any(valid):
                out_normal_score = round(float(np.mean(np.sum(rad[valid] * normals[valid], axis=1) >= -0.25)), 3)

        # Render front silhouette to measure rendered pixel coverage ratio
        front_img = self._rasterize_mesh_view(pos, idx, "front", mode="shaded", avatar=avatar, title=f"{asset_name} FRONT")
        fg_mask = np.any(front_img > 68, axis=2)
        front_cov = round(float(np.mean(fg_mask)), 4)

        rendered_paths: Dict[str, str] = {}
        if output_dir is not None:
            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            side_img = self._rasterize_mesh_view(pos, idx, "side", mode="shaded", avatar=avatar, title=f"{asset_name} SIDE")
            rear_img = self._rasterize_mesh_view(pos, idx, "rear", mode="shaded", avatar=avatar, title=f"{asset_name} REAR")
            wire_img = self._rasterize_mesh_view(pos, idx, "front", mode="wireframe", avatar=avatar, title=f"{asset_name} WIRE")
            norm_img = self._rasterize_mesh_view(pos, idx, "front", mode="normals", avatar=avatar, title=f"{asset_name} NORMALS")
            pen_img = self._rasterize_mesh_view(pos, idx, "side", mode="penetration", vertex_colors=pen_colors, avatar=avatar, title=f"{asset_name} CLEARANCE")
            lm_img = self._rasterize_mesh_view(pos, idx, "front", mode="landmarks", avatar=avatar, title=f"{asset_name} LANDMARKS")

            grid = np.vstack([
                np.hstack([front_img, side_img, rear_img]),
                np.hstack([wire_img, norm_img, pen_img]),
            ])
            files_map = {
                "front": front_img,
                "side": side_img,
                "wireframe": wire_img,
                "penetration": pen_img,
                "landmarks": lm_img,
                "sheet": grid,
            }
            for tag, bgr in files_map.items():
                p = out_dir / f"{asset_name}_{tag}.png"
                Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).save(p)
                rendered_paths[tag] = str(p)

        return VisualDiagnosticsMetrics(
            front_coverage_ratio=front_cov,
            side_depth_to_height_ratio=side_ratio,
            chest_depth_z_m=round(chest_d, 4),
            torso_width_x_m=round(torso_w, 4),
            head_penetrating_vertices=head_pens,
            body_penetrating_vertices=body_pens,
            bilateral_symmetry_score=sym_score,
            outward_normal_score=out_normal_score,
            silhouette_spike_anomaly=spike,
            rendered_views=rendered_paths,
        )


backend_visual_validator = BackendVisualValidator()
