"""
YORVYN Phase 17.7 — GarmentAssetInspector, AvatarGeometryAnalyzer, and GeometryRepairEngine.

Provides:
1. Pre-fitting 3D source asset inspection (bounds, depth/aspect sanity, normals, UVs,
   skinning normalization, left/right bone polarity, duplicate/degenerate topology,
   head/neck penetration check, component overlap detection).
2. Ground-aligned Ara avatar geometry & anatomical envelope analyzer (calibrated from real
   decoded Ara humanoid bounds + AvatarMeasurementsV2).
3. Bounded deterministic GeometryRepairEngine emitting explicit before/after receipts.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field

from backend.app.services.garments.reconstruction.geometry_utils import calculate_smooth_normals

logger = logging.getLogger(__name__)


class AssetDefect(BaseModel):
    code: str
    severity: str  # CRITICAL, MAJOR, MINOR
    message: str
    region: str = "global"
    measured_value: Optional[float] = None
    expected_range: Optional[str] = None


class GarmentAssetInspectionReport(BaseModel):
    vertex_count: int
    triangle_count: int
    unique_triangle_count: int
    overlap_ratio: float = 1.0
    bounds_min: List[float]
    bounds_max: List[float]
    width_x_m: float
    height_y_m: float
    depth_z_m: float
    torso_core_width_m: Optional[float] = None
    torso_core_depth_m: Optional[float] = None
    head_penetration_count: int = 0
    neck_penetration_count: int = 0
    zero_area_faces: int = 0
    duplicate_faces: int = 0
    non_finite_vertices: int = 0
    inverted_normal_ratio: float = 0.0
    uv_present: bool = False
    uv_degenerate_ratio: float = 0.0
    has_skinning: bool = False
    unnormalized_skin_rows: int = 0
    out_of_range_bone_indices: int = 0
    bilateral_bone_mismatch: bool = False
    needs_repair: bool = False
    is_critically_broken: bool = False
    defects: List[AssetDefect] = Field(default_factory=list)


class AvatarAnatomicalEnvelope(BaseModel):
    avatar_profile_id: str = "standard_175"
    height_m: float = 1.695
    head_center: List[float] = Field(default_factory=lambda: [0.0, 1.585, 0.056])
    head_rx: float = 0.114
    head_ry: float = 0.135
    head_rz: float = 0.114
    neck_center: List[float] = Field(default_factory=lambda: [0.0, 1.415, 0.021])
    neck_rx: float = 0.072
    neck_rz: float = 0.068
    chest_center_y: float = 1.260
    chest_z_center: float = 0.052
    chest_width_m: float = 0.378
    chest_depth_m: float = 0.237
    waist_center_y: float = 1.040
    waist_z_center: float = 0.050
    waist_width_m: float = 0.315
    waist_depth_m: float = 0.220
    hip_center_y: float = 0.880
    hip_z_center: float = 0.020
    hip_width_m: float = 0.374
    hip_depth_m: float = 0.260
    shoulder_span_m: float = 0.402
    inseam_y: float = 0.805
    ankle_y: float = 0.090
    bones: Dict[str, List[float]] = Field(default_factory=dict)


class GeometryRepairReceipt(BaseModel):
    applied: bool = False
    operations: List[str] = Field(default_factory=list)
    max_vertex_displacement_m: float = 0.0
    rms_displacement_m: float = 0.0
    before_vertex_count: int = 0
    after_vertex_count: int = 0
    before_triangle_count: int = 0
    after_triangle_count: int = 0
    before_depth_z_m: float = 0.0
    after_depth_z_m: float = 0.0
    before_head_penetrations: int = 0
    after_head_penetrations: int = 0
    rejected_reason: Optional[str] = None


class AvatarGeometryAnalyzer:
    """Computes calibrated Ara humanoid anatomical bounds & elliptical body proxies."""

    # Ground-aligned canonical Ara reference (decoded from ara-assets/base.pack, 19,158 verts)
    CANONICAL_HEIGHT_M = 1.695

    def analyze(
        self,
        avatar_profile_id: str = "standard_175",
        custom_measurements: Optional[Dict[str, Any]] = None,
        custom_bones: Optional[Dict[str, np.ndarray]] = None,
    ) -> AvatarAnatomicalEnvelope:
        from backend.app.services.garments.garment_mesh_builder import ARA_SKELETON_SPECS

        height_m = self.CANONICAL_HEIGHT_M
        chest_cm = 96.0
        waist_cm = 80.0
        hip_cm = 96.0
        shoulder_cm = 42.0

        if isinstance(custom_measurements, dict):
            h_cm = custom_measurements.get("height_cm") or custom_measurements.get("height")
            if isinstance(h_cm, (int, float)) and 120.0 <= float(h_cm) <= 220.0:
                height_m = float(h_cm) / 100.0
            c_cm = custom_measurements.get("chest_cm") or custom_measurements.get("chest_circumference_cm")
            if isinstance(c_cm, (int, float)) and 65.0 <= float(c_cm) <= 150.0:
                chest_cm = float(c_cm)
            w_cm = custom_measurements.get("waist_cm") or custom_measurements.get("waist_circumference_cm")
            if isinstance(w_cm, (int, float)) and 52.0 <= float(w_cm) <= 145.0:
                waist_cm = float(w_cm)
            hp_cm = custom_measurements.get("hip_cm") or custom_measurements.get("hips_cm") or custom_measurements.get("hip_circumference_cm")
            if isinstance(hp_cm, (int, float)) and 68.0 <= float(hp_cm) <= 160.0:
                hip_cm = float(hp_cm)
            sh_cm = custom_measurements.get("shoulder_width_cm")
            if isinstance(sh_cm, (int, float)) and 30.0 <= float(sh_cm) <= 65.0:
                shoulder_cm = float(sh_cm)

        y_scale = height_m / self.CANONICAL_HEIGHT_M
        chest_scale = chest_cm / 96.0
        waist_scale = waist_cm / 80.0
        hip_scale = hip_cm / 96.0
        sh_scale = shoulder_cm / 42.0

        bones: Dict[str, List[float]] = {}
        for spec in ARA_SKELETON_SPECS:
            b_name = spec[0]
            if custom_bones and b_name in custom_bones:
                bones[b_name] = [float(v) for v in custom_bones[b_name]]
            else:
                bx, by, bz = spec[3]
                bones[b_name] = [round(bx * sh_scale, 4), round(by * y_scale, 4), round(bz, 4)]

        return AvatarAnatomicalEnvelope(
            avatar_profile_id=avatar_profile_id or "standard_175",
            height_m=round(height_m, 4),
            head_center=[0.0, round(1.585 * y_scale, 4), 0.056],
            head_rx=round(0.114 * max(0.92, min(1.12, y_scale)), 4),
            head_ry=round(0.135 * y_scale, 4),
            head_rz=round(0.114 * max(0.92, min(1.12, y_scale)), 4),
            neck_center=[0.0, round(1.415 * y_scale, 4), 0.021],
            neck_rx=round(0.072 * chest_scale ** 0.5, 4),
            neck_rz=round(0.068 * chest_scale ** 0.5, 4),
            chest_center_y=round(1.260 * y_scale, 4),
            chest_z_center=0.052,
            chest_width_m=round(0.378 * chest_scale, 4),
            chest_depth_m=round(0.237 * chest_scale, 4),
            waist_center_y=round(1.040 * y_scale, 4),
            waist_z_center=0.050,
            waist_width_m=round(0.315 * waist_scale, 4),
            waist_depth_m=round(0.220 * waist_scale, 4),
            hip_center_y=round(0.880 * y_scale, 4),
            hip_z_center=0.020,
            hip_width_m=round(0.374 * hip_scale, 4),
            hip_depth_m=round(0.260 * hip_scale, 4),
            shoulder_span_m=round(0.402 * sh_scale, 4),
            inseam_y=round(0.805 * y_scale, 4),
            ankle_y=round(0.090 * y_scale, 4),
            bones=bones,
        )


class GarmentAssetInspector:
    """Inspects source or fitted garment meshes for geometry, skinning, UV, and anatomical sanity."""

    def inspect(
        self,
        positions: np.ndarray,
        indices: Optional[np.ndarray],
        *,
        normals: Optional[np.ndarray] = None,
        uvs: Optional[np.ndarray] = None,
        joint_indices: Optional[np.ndarray] = None,
        joint_weights: Optional[np.ndarray] = None,
        category: str = "tops",
        subcategory: str = "",
        avatar: Optional[AvatarAnatomicalEnvelope] = None,
        component_graph: Optional[Any] = None,
    ) -> GarmentAssetInspectionReport:
        pos = np.asarray(positions, dtype=np.float32)
        v_cnt = int(pos.shape[0]) if pos.ndim == 2 else 0
        idx = np.asarray(indices, dtype=np.int64).reshape(-1, 3) if indices is not None and len(indices) > 0 else np.zeros((0, 3), dtype=np.int64)
        t_cnt = int(idx.shape[0])
        avatar = avatar or AvatarGeometryAnalyzer().analyze()
        defects: List[AssetDefect] = []

        if v_cnt < 3 or pos.ndim != 2 or pos.shape[1] != 3:
            defects.append(AssetDefect(code="INVALID_VERTEX_ARRAY", severity="CRITICAL", message="Vertex buffer missing or malformed."))
            return GarmentAssetInspectionReport(
                vertex_count=v_cnt,
                triangle_count=t_cnt,
                unique_triangle_count=0,
                bounds_min=[0.0, 0.0, 0.0],
                bounds_max=[0.0, 0.0, 0.0],
                width_x_m=0.0,
                height_y_m=0.0,
                depth_z_m=0.0,
                needs_repair=True,
                is_critically_broken=True,
                defects=defects,
            )

        finite_mask = np.all(np.isfinite(pos), axis=1)
        non_finite = int(np.sum(~finite_mask))
        safe_pos = np.where(finite_mask[:, None], pos, 0.0)
        if non_finite > 0:
            defects.append(AssetDefect(
                code="NON_FINITE_VERTICES",
                severity="CRITICAL",
                message=f"{non_finite} vertices contain NaN/Inf coordinates.",
                measured_value=float(non_finite),
            ))

        bmin = np.min(safe_pos, axis=0)
        bmax = np.max(safe_pos, axis=0)
        dims = bmax - bmin
        width_x, height_y, depth_z = float(dims[0]), float(dims[1]), float(dims[2])

        if width_x > 2.4 or height_y > 2.4 or depth_z > 1.8:
            defects.append(AssetDefect(
                code="OVERSIZED_ENVELOPE",
                severity="CRITICAL",
                message=f"Garment bounds ({width_x:.2f}x{height_y:.2f}x{depth_z:.2f}m) exceed sane human scale.",
                measured_value=max(width_x, height_y, depth_z),
                expected_range="<= 2.2m",
            ))

        # Torso core estimate excluding lateral sleeve spans
        cat_l = (category or "tops").lower()
        sub_l = (subcategory or "").lower()
        torso_core_w = None
        torso_core_d = None
        if cat_l in {"tops", "outerwear", "dresses_and_skirts", "traditional"} and "skirt" not in sub_l:
            core_mask = (
                (safe_pos[:, 1] >= max(float(bmin[1]) + 0.08, avatar.waist_center_y - 0.10))
                & (safe_pos[:, 1] <= min(float(bmax[1]) - 0.05, avatar.chest_center_y + 0.14))
                & (np.abs(safe_pos[:, 0]) <= 0.28)
            )
            if int(np.sum(core_mask)) >= 12:
                core_pts = safe_pos[core_mask]
                torso_core_w = round(float(np.max(core_pts[:, 0]) - np.min(core_pts[:, 0])), 4)
                torso_core_d = round(float(np.max(core_pts[:, 2]) - np.min(core_pts[:, 2])), 4)
                if torso_core_d > max(0.32, avatar.chest_depth_m * 1.38):
                    defects.append(AssetDefect(
                        code="EXCESSIVE_TORSO_DEPTH",
                        severity="MAJOR",
                        region="torso",
                        message=f"Torso Z depth {torso_core_d:.3f}m is bloated compared to Ara chest {avatar.chest_depth_m:.3f}m.",
                        measured_value=torso_core_d,
                        expected_range=f"0.22..{avatar.chest_depth_m * 1.32:.3f}m",
                    ))
                if torso_core_w > max(0.56, avatar.chest_width_m * 1.48):
                    defects.append(AssetDefect(
                        code="EXCESSIVE_TORSO_WIDTH",
                        severity="MAJOR",
                        region="torso",
                        message=f"Torso core width {torso_core_w:.3f}m is excessively wide.",
                        measured_value=torso_core_w,
                        expected_range=f"0.32..{avatar.chest_width_m * 1.40:.3f}m",
                    ))

        # Head & neck intersection check (primarily hoods / high collars / tops)
        hc = np.array(avatar.head_center, dtype=np.float32)
        h_radii = np.array([max(0.08, avatar.head_rx - 0.008), max(0.09, avatar.head_ry - 0.012), max(0.08, avatar.head_rz - 0.008)], dtype=np.float32)
        head_norm_dist = np.linalg.norm((safe_pos - hc) / h_radii, axis=1)
        head_pens = int(np.sum(head_norm_dist < 1.0)) if cat_l not in {"accessories", "headwear"} else 0

        nc = np.array(avatar.neck_center, dtype=np.float32)
        neck_band = (safe_pos[:, 1] >= avatar.neck_center[1] - 0.04) & (safe_pos[:, 1] <= avatar.neck_center[1] + 0.045)
        neck_norm = np.sqrt(((safe_pos[:, 0] - nc[0]) / max(0.05, avatar.neck_rx - 0.005)) ** 2 + ((safe_pos[:, 2] - nc[2]) / max(0.05, avatar.neck_rz - 0.005)) ** 2)
        neck_pens = int(np.sum(neck_band & (neck_norm < 1.0))) if cat_l not in {"accessories", "headwear"} else 0

        if head_pens > 0:
            defects.append(AssetDefect(
                code="HOOD_HEAD_PENETRATION",
                severity="CRITICAL" if head_pens > 12 else "MAJOR",
                region="head",
                message=f"{head_pens} vertices intersect Ara skull envelope.",
                measured_value=float(head_pens),
                expected_range="0",
            ))

        # Triangle quality: out-of-range, zero-area, duplicate
        zero_area = 0
        dup_faces = 0
        unique_t = t_cnt
        if t_cnt > 0:
            if int(np.max(idx)) >= v_cnt or int(np.min(idx)) < 0:
                defects.append(AssetDefect(code="INDEX_OUT_OF_BOUNDS", severity="CRITICAL", message="Triangle index exceeds vertex buffer."))
            else:
                sorted_idx = np.sort(idx, axis=1)
                _, counts = np.unique(sorted_idx, axis=0, return_counts=True)
                unique_t = int(len(counts))
                dup_faces = int(t_cnt - unique_t)
                v0 = safe_pos[idx[:, 0]]
                v1 = safe_pos[idx[:, 1]]
                v2 = safe_pos[idx[:, 2]]
                cross = np.cross(v1 - v0, v2 - v0)
                areas = 0.5 * np.linalg.norm(cross, axis=1)
                zero_area = int(np.sum(areas < 1e-9))
                if dup_faces > 0:
                    defects.append(AssetDefect(
                        code="DUPLICATE_TRIANGLES",
                        severity="MAJOR" if dup_faces > max(8, int(t_cnt * 0.05)) else "MINOR",
                        message=f"{dup_faces} duplicate/stacked faces detected.",
                        measured_value=float(dup_faces),
                    ))
                if zero_area > max(16, int(t_cnt * 0.05)):
                    defects.append(AssetDefect(
                        code="DEGENERATE_TRIANGLES",
                        severity="MAJOR",
                        message=f"{zero_area} zero-area degenerate triangles.",
                        measured_value=float(zero_area),
                    ))

        overlap_ratio = round(float(t_cnt) / max(1.0, float(unique_t)), 3)
        if component_graph and getattr(component_graph, "nodes", None):
            tri_seen: List[Tuple[int, int]] = []
            comp_overlap_count = 0
            for c in component_graph.nodes.values():
                if getattr(c, "representation_type", "GEOMETRIC_MESH") != "GEOMETRIC_MESH":
                    continue
                ts, tc = c.triangle_range
                if tc <= 0:
                    continue
                if any(not (ts + tc <= s0 or ts >= e0) for s0, e0 in tri_seen):
                    comp_overlap_count += 1
                else:
                    tri_seen.append((ts, ts + tc))
            if comp_overlap_count > 0:
                defects.append(AssetDefect(
                    code="OVERLAPPING_COMPONENT_PRIMITIVES",
                    severity="MAJOR",
                    message=f"{comp_overlap_count} GEOMETRIC_MESH component nodes reference overlapping triangle ranges.",
                    measured_value=float(comp_overlap_count),
                ))

        # Normals orientation heuristic (outward relative to slice XZ center)
        inv_norm_ratio = 0.0
        if normals is not None and len(normals) == v_cnt:
            n_arr = np.asarray(normals, dtype=np.float32)
            bad_n = int(np.sum(~np.all(np.isfinite(n_arr), axis=1)))
            if bad_n > 0:
                defects.append(AssetDefect(code="NON_FINITE_NORMALS", severity="MAJOR", message=f"{bad_n} invalid normals."))
            # Check dot against radial vector for exterior verts
            cen_xz = np.array([float(np.mean(safe_pos[:, 0])), 0.0, float(np.mean(safe_pos[:, 2]))], dtype=np.float32)
            rad_xz = safe_pos - cen_xz
            rad_xz[:, 1] = 0.0
            rad_len = np.linalg.norm(rad_xz, axis=1)
            ext = rad_len > 0.06
            if np.any(ext):
                dots = np.sum(rad_xz[ext] * n_arr[ext], axis=1)
                inv_norm_ratio = round(float(np.mean(dots < -0.2)), 3)

        # UVs
        uv_present = uvs is not None and len(uvs) == v_cnt
        uv_deg = 0.0
        if not uv_present:
            defects.append(AssetDefect(code="MISSING_UVS", severity="MINOR", message="UV coordinates missing."))
        else:
            uv_arr = np.asarray(uvs, dtype=np.float32)
            if not np.all(np.isfinite(uv_arr)):
                defects.append(AssetDefect(code="NON_FINITE_UVS", severity="MAJOR", message="UV array contains NaN/Inf."))
                uv_deg = 1.0
            elif np.max(np.abs(uv_arr)) < 1e-6:
                defects.append(AssetDefect(code="DEGENERATE_UVS", severity="MAJOR", message="All UV coordinates are zero."))
                uv_deg = 1.0

        # Skinning & bilateral bone consistency (+X = Left joints 6..8, 14..16; -X = Right joints 10..12, 17..19)
        has_skin = joint_indices is not None and joint_weights is not None and len(joint_indices) == v_cnt and len(joint_weights) == v_cnt
        unnorm_rows = 0
        oob_bones = 0
        bilateral_swap = False
        if not has_skin:
            if cat_l in {"tops", "outerwear", "bottoms", "dresses_and_skirts", "traditional"}:
                defects.append(AssetDefect(code="MISSING_SKINNING", severity="MAJOR", message="Wearable garment lacks skinning weights."))
        else:
            ji = np.asarray(joint_indices, dtype=np.int64)
            jw = np.asarray(joint_weights, dtype=np.float32)
            w_sum = np.sum(jw, axis=1)
            bad_w = (~np.isfinite(w_sum)) | (np.abs(w_sum - 1.0) > 1e-2) | (np.min(jw, axis=1) < -1e-4)
            unnorm_rows = int(np.sum(bad_w))
            if unnorm_rows > 0:
                defects.append(AssetDefect(
                    code="UNNORMALIZED_SKIN_WEIGHTS",
                    severity="CRITICAL" if unnorm_rows > max(8, int(v_cnt * 0.02)) else "MAJOR",
                    message=f"{unnorm_rows} vertices have unnormalized/negative skinning weights.",
                    measured_value=float(unnorm_rows),
                ))
            oob_mask = (ji < 0) | (ji > 19)
            oob_bones = int(np.sum(np.any(oob_mask, axis=1)))
            if oob_bones > 0:
                defects.append(AssetDefect(
                    code="INVALID_BONE_INDEX",
                    severity="CRITICAL",
                    message=f"{oob_bones} vertices reference bones outside 20-bone Ara skeleton.",
                    measured_value=float(oob_bones),
                ))
            # Check primary bone vs X polarity for arms/legs
            primary_bone = ji[np.arange(v_cnt), np.argmax(jw, axis=1)]
            left_bones_mask = np.isin(primary_bone, [6, 7, 8, 14, 15, 16]) & (jw.max(axis=1) > 0.35)
            right_bones_mask = np.isin(primary_bone, [10, 11, 12, 17, 18, 19]) & (jw.max(axis=1) > 0.35)
            swapped_l = int(np.sum(left_bones_mask & (safe_pos[:, 0] < -0.05)))
            swapped_r = int(np.sum(right_bones_mask & (safe_pos[:, 0] > 0.05)))
            if (swapped_l > 12 or swapped_r > 12) and (
                swapped_l > int(np.sum(left_bones_mask) * 0.5) or swapped_r > int(np.sum(right_bones_mask) * 0.5)
            ):
                bilateral_swap = True
                defects.append(AssetDefect(
                    code="BILATERAL_BONE_POLARITY_SWAP",
                    severity="CRITICAL",
                    region="limbs",
                    message=f"Left/Right limb bones inverted relative to X coordinates (swapped_l={swapped_l}, swapped_r={swapped_r}).",
                ))

        crit = any(d.severity == "CRITICAL" for d in defects)
        needs_rep = len(defects) > 0
        return GarmentAssetInspectionReport(
            vertex_count=v_cnt,
            triangle_count=t_cnt,
            unique_triangle_count=unique_t,
            overlap_ratio=overlap_ratio,
            bounds_min=[round(float(x), 4) for x in bmin],
            bounds_max=[round(float(x), 4) for x in bmax],
            width_x_m=round(width_x, 4),
            height_y_m=round(height_y, 4),
            depth_z_m=round(depth_z, 4),
            torso_core_width_m=torso_core_w,
            torso_core_depth_m=torso_core_d,
            head_penetration_count=head_pens,
            neck_penetration_count=neck_pens,
            zero_area_faces=zero_area,
            duplicate_faces=dup_faces,
            non_finite_vertices=non_finite,
            inverted_normal_ratio=inv_norm_ratio,
            uv_present=uv_present,
            uv_degenerate_ratio=uv_deg,
            has_skinning=has_skin,
            unnormalized_skin_rows=unnorm_rows,
            out_of_range_bone_indices=oob_bones,
            bilateral_bone_mismatch=bilateral_swap,
            needs_repair=needs_rep,
            is_critically_broken=crit,
            defects=defects,
        )


class GeometryRepairEngine:
    """Bounded deterministic geometry repair engine for malformed/bloated source or fitted meshes."""

    def repair(
        self,
        positions: np.ndarray,
        indices: np.ndarray,
        *,
        normals: Optional[np.ndarray] = None,
        uvs: Optional[np.ndarray] = None,
        joint_indices: Optional[np.ndarray] = None,
        joint_weights: Optional[np.ndarray] = None,
        category: str = "tops",
        subcategory: str = "",
        avatar: Optional[AvatarAnatomicalEnvelope] = None,
        proposal: Optional[Dict[str, Any]] = None,
        component_graph: Optional[Any] = None,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Optional[np.ndarray], Optional[np.ndarray], GeometryRepairReceipt]:
        pos = np.array(positions, dtype=np.float32, copy=True)
        idx = np.array(indices, dtype=np.uint32, copy=True).reshape(-1, 3)
        norm = np.array(normals, dtype=np.float32, copy=True) if normals is not None else np.zeros_like(pos)
        uv = np.array(uvs, dtype=np.float32, copy=True) if uvs is not None else np.zeros((len(pos), 2), dtype=np.float32)
        ji = np.array(joint_indices, dtype=np.uint16, copy=True) if joint_indices is not None else None
        jw = np.array(joint_weights, dtype=np.float32, copy=True) if joint_weights is not None else None
        avatar = avatar or AvatarGeometryAnalyzer().analyze()
        orig_pos = np.copy(pos)
        before_v = len(pos)
        before_t = len(idx)
        before_depth = float(np.max(pos[:, 2]) - np.min(pos[:, 2])) if len(pos) > 0 else 0.0

        ops: List[str] = []
        cat_l = (category or "tops").lower()
        sub_l = (subcategory or "").lower()

        # 1. Reject severely non-finite meshes (>10% corrupt) or repair isolated NaN vertices
        finite = np.all(np.isfinite(pos), axis=1)
        if not np.all(finite):
            bad_frac = 1.0 - float(np.mean(finite))
            if bad_frac > 0.10 or np.sum(finite) < 12:
                return pos, idx, norm, uv, ji, jw, GeometryRepairReceipt(
                    applied=False,
                    rejected_reason=f"Excessive non-finite coordinates ({bad_frac:.1%}); unrepairable.",
                    before_vertex_count=before_v,
                    after_vertex_count=len(pos),
                    before_triangle_count=before_t,
                    after_triangle_count=len(idx),
                )
            centroid = np.mean(pos[finite], axis=0)
            pos[~finite] = centroid
            orig_pos[~finite] = centroid
            ops.append("sanitize_isolated_non_finite")

        # 2. Deduplicate overlapping component nodes and duplicate triangles cleanly when requested/needed
        if component_graph and getattr(component_graph, "nodes", None):
            seen_ranges: List[Tuple[int, int]] = []
            deduped = 0
            for comp in component_graph.nodes.values():
                if getattr(comp, "representation_type", "GEOMETRIC_MESH") != "GEOMETRIC_MESH":
                    continue
                ts, tc = comp.triangle_range
                if tc <= 0:
                    continue
                if any(not (ts + tc <= s0 or ts >= e0) for s0, e0 in seen_ranges):
                    comp.representation_type = "SEMANTIC_REGION"
                    deduped += 1
                else:
                    seen_ranges.append((ts, ts + tc))
            if deduped > 0:
                ops.append(f"deduplicate_component_primitives({deduped})")

        # 3. Skinning weight normalization & bilateral bone polarity fix
        if ji is not None and jw is not None and len(ji) == len(pos) and len(jw) == len(pos):
            ji = np.clip(ji, 0, 19).astype(np.uint16)
            jw = np.where(np.isfinite(jw), np.maximum(0.0, jw), 0.0).astype(np.float32)
            sums = np.sum(jw, axis=1)
            bad = sums <= 1e-6
            if np.any(bad):
                ji[bad] = np.array([1 if cat_l in {"tops", "outerwear"} else 0, 0, 0, 0], dtype=np.uint16)
                jw[bad] = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
            sums = np.sum(jw, axis=1, keepdims=True)
            if np.any(np.abs(sums[:, 0] - 1.0) > 1e-4):
                jw = jw / np.maximum(1e-6, sums)
                ops.append("normalize_skin_weights")

            # Swap inverted limb bones (+X left, -X right)
            swap_to_left = {10: 6, 11: 7, 12: 8, 17: 14, 18: 15, 19: 16}
            swap_to_right = {v: k for k, v in swap_to_left.items()}
            primary_b = ji[np.arange(len(pos)), np.argmax(jw, axis=1)]
            left_on_neg = int(np.sum(np.isin(primary_b, [6, 7, 8, 14, 15, 16]) & (pos[:, 0] < -0.06)))
            right_on_pos = int(np.sum(np.isin(primary_b, [10, 11, 12, 17, 18, 19]) & (pos[:, 0] > 0.06)))
            if left_on_neg > 15 and right_on_pos > 15:
                for vi in range(len(pos)):
                    if pos[vi, 0] > 0.04:
                        for k in range(4):
                            if int(ji[vi, k]) in swap_to_left:
                                ji[vi, k] = swap_to_left[int(ji[vi, k])]
                    elif pos[vi, 0] < -0.04:
                        for k in range(4):
                            if int(ji[vi, k]) in swap_to_right:
                                ji[vi, k] = swap_to_right[int(ji[vi, k])]
                ops.append("fix_bilateral_bone_polarity")

        # 4. Bounded anatomical torso depth / width correction (torso core only, keeping sleeves intact)
        if cat_l in {"tops", "outerwear", "traditional"} or (cat_l == "dresses_and_skirts" and "skirt" not in sub_l):
            max_allowed_depth = max(0.285, avatar.chest_depth_m * 1.28)
            core_mask = (np.abs(pos[:, 0]) <= 0.24) & (pos[:, 1] >= avatar.waist_center_y - 0.14) & (pos[:, 1] <= avatar.chest_center_y + 0.16)
            if int(np.sum(core_mask)) >= 12:
                cur_d = float(np.max(pos[core_mask, 2]) - np.min(pos[core_mask, 2]))
                prop_sz = float((proposal or {}).get("target_torso_scale_z", 1.0))
                if cur_d > max_allowed_depth or prop_sz < 0.99:
                    target_d = min(max_allowed_depth, cur_d * max(0.68, min(1.0, prop_sz)))
                    scale_z = max(0.66, min(1.0, target_d / max(cur_d, 1e-4)))
                    z_ctr = avatar.chest_z_center
                    # Smooth falloff across X so sleeve attachment never kinks
                    x_blend = np.clip(1.0 - np.maximum(0.0, np.abs(pos[:, 0]) - 0.18) / 0.12, 0.0, 1.0)
                    y_blend = np.where(pos[:, 1] <= avatar.neck_center[1] + 0.03, 1.0, 0.25)
                    w = x_blend * y_blend
                    pos[:, 2] = z_ctr + (pos[:, 2] - z_ctr) * (1.0 - w + w * scale_z)
                    ops.append(f"compress_torso_depth(scale_z={scale_z:.3f})")

        # 5. Hood / collar head clearance repair (never push across face +Z)
        hc = np.array(avatar.head_center, dtype=np.float32)
        head_rx = avatar.head_rx + 0.008
        head_ry = avatar.head_ry + 0.008
        head_rz = avatar.head_rz + 0.008
        before_head_pens = int(np.sum(np.linalg.norm((orig_pos - hc) / np.array([head_rx - 0.012, head_ry - 0.012, head_rz - 0.012]), axis=1) < 1.0)) if cat_l not in {"accessories", "headwear"} else 0
        if cat_l not in {"accessories", "headwear"} and before_head_pens > 0:
            upper_mask = pos[:, 1] >= (avatar.neck_center[1] - 0.02)
            if np.any(upper_mask):
                rel = pos[upper_mask] - hc
                ell_r = np.array([head_rx, head_ry, head_rz], dtype=np.float32)
                norm_d = np.linalg.norm(rel / ell_r, axis=1)
                inside = norm_d < 1.0
                if np.any(inside):
                    idxs = np.where(upper_mask)[0][inside]
                    for vi in idxs:
                        rvec = (pos[vi] - hc) / ell_r
                        # Bias escape backward (-Z) and laterally (+-X) if near front face aperture
                        if rvec[2] > 0.25:
                            rvec[2] = -0.35
                            if abs(rvec[0]) < 0.25:
                                rvec[0] = 0.6 if pos[vi, 0] >= 0 else -0.6
                        d = float(np.linalg.norm(rvec)) or 1.0
                        pos[vi] = hc + (rvec / d) * ell_r * 1.04
                    ops.append(f"enforce_hood_head_clearance({len(idxs)})")

        # 6. Lower garment hem flare clamp (for pants/jeans/chinos only)
        if cat_l == "bottoms":
            hem_zone = pos[:, 1] < (avatar.hip_center_y - 0.08)
            if np.any(hem_zone):
                max_hem_w = avatar.hip_width_m * 1.45
                cur_w = float(np.max(pos[hem_zone, 0]) - np.min(pos[hem_zone, 0]))
                if cur_w > max_hem_w:
                    sx = max(0.68, max_hem_w / cur_w)
                    pos[hem_zone, 0] *= sx
                    ops.append(f"constrain_bottom_flare(scale_x={sx:.3f})")

        # 7. Repair invalid UVs or recompute smooth vertex normals
        if len(uv) != len(pos) or not np.all(np.isfinite(uv)) or np.max(np.abs(uv)) < 1e-6:
            xr = max(1e-4, float(np.max(pos[:, 0]) - np.min(pos[:, 0])))
            yr = max(1e-4, float(np.max(pos[:, 1]) - np.min(pos[:, 1])))
            uv = np.column_stack([
                np.clip((pos[:, 0] - float(np.min(pos[:, 0]))) / xr, 0.0, 1.0),
                np.clip((pos[:, 1] - float(np.min(pos[:, 1]))) / yr, 0.0, 1.0),
            ]).astype(np.float32)
            ops.append("rebuild_planar_uvs")

        norm = calculate_smooth_normals(pos, idx) if len(idx) > 0 else norm
        ops.append("recompute_smooth_normals")

        disp = np.linalg.norm(pos - orig_pos, axis=1)
        max_disp = float(np.max(disp)) if len(disp) > 0 else 0.0
        rms_disp = float(np.sqrt(np.mean(disp ** 2))) if len(disp) > 0 else 0.0
        after_depth = float(np.max(pos[:, 2]) - np.min(pos[:, 2])) if len(pos) > 0 else 0.0
        after_head_pens = int(np.sum(np.linalg.norm((pos - hc) / np.array([head_rx - 0.012, head_ry - 0.012, head_rz - 0.012]), axis=1) < 1.0)) if cat_l not in {"accessories", "headwear"} else 0

        receipt = GeometryRepairReceipt(
            applied=True,
            operations=ops,
            max_vertex_displacement_m=round(max_disp, 5),
            rms_displacement_m=round(rms_disp, 5),
            before_vertex_count=before_v,
            after_vertex_count=len(pos),
            before_triangle_count=before_t,
            after_triangle_count=len(idx),
            before_depth_z_m=round(before_depth, 4),
            after_depth_z_m=round(after_depth, 4),
            before_head_penetrations=before_head_pens,
            after_head_penetrations=after_head_pens,
        )
        return pos, idx, norm, uv, ji, jw, receipt


avatar_geometry_analyzer = AvatarGeometryAnalyzer()
garment_asset_inspector = GarmentAssetInspector()
geometry_repair_engine = GeometryRepairEngine()
