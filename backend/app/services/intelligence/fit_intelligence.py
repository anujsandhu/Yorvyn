"""
YORVYN Intelligence Platform (YIP) — 3D & Fit Intelligence Subsystem (Phase 17.0 Stage 4).

Coordinates body understanding, garment mesh measurement extraction, ease evaluation,
collision clearance analysis, fit classification, and fit defect reporting without
auto-mutating persisted geometry.
"""
from __future__ import annotations

import io
import math
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field

from backend.app.models.garment_intelligence_models import AvatarMeasurementsV2
from backend.app.services.garments.fitting.avatar_body_measurement_engine import (
    avatar_body_measurement_engine,
)
from backend.app.services.garments.fitting.garment_collision_engine import GarmentCollisionEngine
from backend.app.services.garments.garment_mesh_builder import ARA_SKELETON_SPECS
from backend.app.services.intelligence.inference_adapters import inference_telemetry
from backend.app.services.ml.body_intelligence import BodyIntelligenceService


class MeasurementOrigin(str, Enum):
    MEASURED_GEOMETRY = "measured_geometry"
    ESTIMATED_LANDMARKS = "estimated_landmarks"
    INFERRED_PROPORTION = "inferred_proportion"
    UNSUPPORTED = "unsupported"


class DimensionAssessment(BaseModel):
    name: str
    value_cm: Optional[float] = None
    body_reference_cm: Optional[float] = None
    ease_cm: Optional[float] = None
    origin: MeasurementOrigin
    note: str = ""


class FitDefect(BaseModel):
    defect_type: str  # body_penetration | garment_gap | missing_coverage | incorrect_proportions | asymmetric_fitting | skin_visible_holes | distorted_deformation | invalid_attachments
    severity: str     # CRITICAL | MAJOR | MINOR
    location: str
    measured_metric: str
    suggestion: str
    auto_applied: bool = False


class FitClassification(str, Enum):
    TIGHT = "Tight"
    REGULAR = "Regular"
    RELAXED = "Relaxed"
    OVERSIZED = "Oversized"
    POTENTIALLY_INCORRECT = "Potentially Incorrect"


class FitIntelligenceReport(BaseModel):
    category: str
    avatar_profile_id: str
    fit_classification: FitClassification
    overall_fit_score: float = Field(ge=0.0, le=100.0)
    ease_summary_cm: Dict[str, Optional[float]] = Field(default_factory=dict)
    dimensions: List[DimensionAssessment] = Field(default_factory=list)
    collision_count: int = 0
    max_penetration_mm: float = 0.0
    average_clearance_mm: float = 0.0
    asymmetry_ratio: float = 0.0
    defects: List[FitDefect] = Field(default_factory=list)
    deformation_suggestions: List[str] = Field(default_factory=list)
    geometry_mutated: bool = False
    limitations: str = (
        "Assesses computational vertex-to-avatar hull clearance in Ara Y-up coordinates; "
        "does not certify physical tailoring fit on human skin/fabric stretch."
    )
    latency_ms: float = 0.0


class FitIntelligenceEngine:
    """Coordinates anthropometric body profiles, mesh extraction, collision hulls, and fit defects."""

    def __init__(self) -> None:
        self._body_svc = BodyIntelligenceService()

    @staticmethod
    def extract_mesh_arrays_from_glb(glb_bytes: bytes) -> Tuple[np.ndarray, np.ndarray]:
        import trimesh

        loaded = trimesh.load(io.BytesIO(glb_bytes), file_type="glb", force="scene")
        if isinstance(loaded, trimesh.Scene):
            geoms = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh) and len(g.vertices) > 0]
            if not geoms:
                return np.zeros((0, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.int32)
            # Apply node transforms to preserve true world/Ara pose coordinates
            verts_all: List[np.ndarray] = []
            faces_all: List[np.ndarray] = []
            offset = 0
            for node_name in loaded.graph.nodes_geometry:
                xf, geom_name = loaded.graph[node_name]
                g = loaded.geometry.get(geom_name)
                if not isinstance(g, trimesh.Trimesh) or len(g.vertices) == 0:
                    continue
                v = np.asarray(g.vertices, dtype=np.float64)
                hom = np.concatenate([v, np.ones((len(v), 1))], axis=1) @ xf.T
                verts_all.append(hom[:, :3].astype(np.float32))
                faces_all.append((np.asarray(g.faces, dtype=np.int32) + offset))
                offset += len(v)
            if not verts_all:
                return np.zeros((0, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.int32)
            return np.vstack(verts_all), np.vstack(faces_all)
        return np.asarray(loaded.vertices, dtype=np.float32), np.asarray(loaded.faces, dtype=np.int32)

    @staticmethod
    def _estimate_circumference_from_slice(pts: np.ndarray) -> Optional[float]:
        if len(pts) < 6:
            return None
        w_half = float(np.max(pts[:, 0]) - np.min(pts[:, 0])) * 50.0  # meters -> half-width cm
        d_half = float(np.max(pts[:, 2]) - np.min(pts[:, 2])) * 50.0
        if w_half <= 0.1 or d_half <= 0.1:
            return None
        # Ramanujan ellipse perimeter in cm
        perim = math.pi * (3.0 * (w_half + d_half) - math.sqrt(max(1e-6, (3.0 * w_half + d_half) * (w_half + 3.0 * d_half))))
        return round(perim, 2)

    def analyze_fit(
        self,
        *,
        category: str = "tops",
        positions: Optional[np.ndarray] = None,
        indices: Optional[np.ndarray] = None,
        glb_bytes: Optional[bytes] = None,
        avatar_profile_id: str = "standard_175",
        custom_measurements: Optional[Dict[str, float]] = None,
    ) -> FitIntelligenceReport:
        t0 = time.perf_counter()
        if positions is None and glb_bytes is not None:
            positions, indices = self.extract_mesh_arrays_from_glb(glb_bytes)

        profile: AvatarMeasurementsV2 = avatar_body_measurement_engine.get_profile(avatar_profile_id)
        if custom_measurements:
            for key, val in custom_measurements.items():
                if hasattr(profile, key) and isinstance(val, (int, float)) and val > 0:
                    setattr(profile, key, float(val))

        cat_l = (category or "tops").lower()
        defects: List[FitDefect] = []
        suggestions: List[str] = []
        dimensions: List[DimensionAssessment] = []

        if positions is None or len(positions) < 4:
            defects.append(FitDefect(
                defect_type="missing_coverage",
                severity="CRITICAL",
                location="full_garment",
                measured_metric="vertex_count=0",
                suggestion="Provide valid 3D garment vertex geometry to evaluate anatomical fit.",
            ))
            return FitIntelligenceReport(
                category=cat_l,
                avatar_profile_id=avatar_profile_id,
                fit_classification=FitClassification.POTENTIALLY_INCORRECT,
                overall_fit_score=0.0,
                dimensions=[
                    DimensionAssessment(name="physical_fabric_stretch", origin=MeasurementOrigin.UNSUPPORTED, note="Lab textile test unavailable"),
                ],
                defects=defects,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            )

        pts = np.asarray(positions, dtype=np.float32)
        if not np.all(np.isfinite(pts)):
            defects.append(FitDefect(
                defect_type="invalid_attachments",
                severity="CRITICAL",
                location="vertex_buffer",
                measured_metric="non_finite_coordinates",
                suggestion="Sanitize NaN/Inf vertex coordinates before attaching garment.",
            ))
            pts = np.nan_to_num(pts, nan=0.0, posinf=0.0, neginf=0.0)

        min_xyz = np.min(pts, axis=0)
        max_xyz = np.max(pts, axis=0)
        extents_cm = (max_xyz - min_xyz) * 100.0

        # Invalid attachment frame check (extreme origin drift or tiny scale)
        if float(extents_cm[1]) < 8.0 or float(extents_cm[0]) < 5.0 or abs(float(np.mean(pts[:, 0]))) > 0.65:
            defects.append(FitDefect(
                defect_type="invalid_attachments",
                severity="MAJOR",
                location="root_coordinate_frame",
                measured_metric=f"extents_cm={[round(float(x), 1) for x in extents_cm]}",
                suggestion="Re-center garment to Ara humanoid Y-up body frame and recalibrate metric height.",
            ))

        # Asymmetry inspection across X=0 midline
        pos_x = pts[pts[:, 0] > 0.01]
        neg_x = pts[pts[:, 0] < -0.01]
        if len(pos_x) > 0 and len(neg_x) > 0:
            r_span = float(np.max(pos_x[:, 0]))
            l_span = float(abs(np.min(neg_x[:, 0])))
            asym = abs(r_span - l_span) / max(0.05, max(r_span, l_span))
        else:
            asym = 1.0
        if asym > 0.22:
            defects.append(FitDefect(
                defect_type="asymmetric_fitting",
                severity="MAJOR",
                location="left_right_bilateral_envelope",
                measured_metric=f"asymmetry_ratio={asym:.3f}",
                suggestion="Check sleeve/hem symmetry balance across midline X=0.",
            ))

        # Horizontal slice estimation for chest/waist/hip
        y_min, y_max = float(min_xyz[1]), float(max_xyz[1])
        y_span = max(0.05, y_max - y_min)
        upper_slice = pts[(pts[:, 1] >= y_min + 0.55 * y_span) & (pts[:, 1] <= y_min + 0.78 * y_span)]
        mid_slice = pts[(pts[:, 1] >= y_min + 0.15 * y_span) & (pts[:, 1] <= y_min + 0.42 * y_span)]

        chest_circ_cm = self._estimate_circumference_from_slice(upper_slice)
        waist_circ_cm = self._estimate_circumference_from_slice(mid_slice)
        chest_ease = round(chest_circ_cm - profile.chest_circumference_cm, 2) if chest_circ_cm is not None else None
        waist_ease = round(waist_circ_cm - profile.waist_circumference_cm, 2) if waist_circ_cm is not None else None

        dimensions.append(DimensionAssessment(
            name="garment_height_cm",
            value_cm=round(float(extents_cm[1]), 2),
            origin=MeasurementOrigin.MEASURED_GEOMETRY,
            note="Directly measured mesh Y-extent",
        ))
        dimensions.append(DimensionAssessment(
            name="garment_width_cm",
            value_cm=round(float(extents_cm[0]), 2),
            body_reference_cm=round(profile.shoulder_width_cm, 2),
            origin=MeasurementOrigin.MEASURED_GEOMETRY,
            note="Directly measured mesh X-extent vs estimated shoulder width",
        ))
        if chest_circ_cm is not None:
            dimensions.append(DimensionAssessment(
                name="chest_circumference_cm",
                value_cm=chest_circ_cm,
                body_reference_cm=profile.chest_circumference_cm,
                ease_cm=chest_ease,
                origin=MeasurementOrigin.INFERRED_PROPORTION,
                note="Ramanujan elliptical slice estimate over upper torso band",
            ))
        if waist_circ_cm is not None:
            dimensions.append(DimensionAssessment(
                name="waist_circumference_cm",
                value_cm=waist_circ_cm,
                body_reference_cm=profile.waist_circumference_cm,
                ease_cm=waist_ease,
                origin=MeasurementOrigin.INFERRED_PROPORTION,
                note="Ramanujan elliptical slice estimate over mid torso band",
            ))
        dimensions.append(DimensionAssessment(
            name="physical_fabric_stretch_pct",
            value_cm=None,
            origin=MeasurementOrigin.UNSUPPORTED,
            note="Requires physical tensile lab testing",
        ))

        # Body collision & clearance evaluation against non-mutated geometry (with elliptical + head/neck hulls)
        coll_engine = GarmentCollisionEngine()
        scale_f = profile.height_cm / 175.0
        bones = {spec[0]: np.array(spec[3], dtype=np.float32) * scale_f for spec in ARA_SKELETON_SPECS}
        coll_engine.update_hulls_from_avatar(bones, scale_factor=scale_f)
        face_arr = np.asarray(indices, dtype=np.int32) if (indices is not None and len(indices) > 0) else np.zeros((0, 3), dtype=np.int32)
        is_head_acc = cat_l in {"headwear", "glasses"} or any(k in cat_l for k in ("hat", "cap", "beanie", "glass", "headwear"))
        _, col_metrics = coll_engine.detect_and_resolve_collisions(
            positions=pts.copy(),
            indices=face_arr,
            min_clearance_m=0.003,
            exclude_head=is_head_acc,
        )

        # Oversized envelope, cylindrical torso Z bloat & head/neck penetration diagnostics
        if float(np.max(extents_cm)) > 235.0:
            defects.append(FitDefect(
                defect_type="oversized_envelope",
                severity="CRITICAL",
                location="bounding_box",
                measured_metric=f"max_extent_cm={float(np.max(extents_cm)):.1f}",
                suggestion="Garment exceeds maximum wearable meter-scale envelope; rescale or reject.",
            ))

        if cat_l in {"tops", "outerwear", "shirt", "hoodie", "jacket", "traditional"} or "kurta" in cat_l:
            core_pts = pts[(pts[:, 1] >= y_min + 0.15 * y_span) & (pts[:, 1] <= y_min + 0.80 * y_span) & (np.abs(pts[:, 0]) <= 0.27)]
            if len(core_pts) >= 12:
                core_depth_m = float(np.max(core_pts[:, 2]) - np.min(core_pts[:, 2]))
                if core_depth_m > 0.34:
                    defects.append(FitDefect(
                        defect_type="cylindrical_torso_bloat",
                        severity="CRITICAL" if core_depth_m > 0.42 else "MAJOR",
                        location="torso_core",
                        measured_metric=f"core_depth_z_m={core_depth_m:.3f}",
                        suggestion="Compress torso front-back Z depth to anatomical chest ellipse (~0.24-0.31m).",
                    ))
        elif "dress" in cat_l or "skirt" in cat_l:
            total_depth_m = float(extents_cm[2]) / 100.0
            if total_depth_m > 0.48:
                defects.append(FitDefect(
                    defect_type="cylindrical_torso_bloat",
                    severity="CRITICAL" if total_depth_m > 0.56 else "MAJOR",
                    location="skirt_or_bodice_depth",
                    measured_metric=f"depth_z_m={total_depth_m:.3f}",
                    suggestion="Constrain lower skirt & bodice Z depth against anatomical hips.",
                ))

        if not is_head_acc:
            head_hulls = [h for h in coll_engine.hulls if h.name == "head"]
            if head_hulls:
                _, _, h_mask = head_hulls[0].resolve_penetrations_batch(pts, min_clearance=0.002)
                head_pen_cnt = int(np.sum(h_mask))
                if head_pen_cnt > 0:
                    defects.append(FitDefect(
                        defect_type="hood_head_penetration",
                        severity="CRITICAL" if head_pen_cnt > 12 else "MAJOR",
                        location="head_skull",
                        measured_metric=f"head_penetration_count={head_pen_cnt}",
                        suggestion="Open hood front aperture (+Z) and project hood cowl outside skull capsule.",
                    ))

        # Degenerate distortion / extreme edge stretch / hole diagnostics when faces supplied
        if len(face_arr) > 0:
            tris = pts[face_arr.reshape(-1, 3)]
            e0 = np.linalg.norm(tris[:, 1] - tris[:, 0], axis=1)
            e1 = np.linalg.norm(tris[:, 2] - tris[:, 1], axis=1)
            e2 = np.linalg.norm(tris[:, 0] - tris[:, 2], axis=1)
            edges_all = np.concatenate([e0, e1, e2])
            areas = 0.5 * np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)
            degen_ratio = float(np.mean(areas < 1e-8))
            med_edge = float(np.median(edges_all)) if len(edges_all) > 0 else 0.0
            max_edge = float(np.max(edges_all)) if len(edges_all) > 0 else 0.0
            stretch_ratio = (max_edge / max(1e-5, med_edge)) if med_edge > 0 else 0.0
            if degen_ratio > 0.05 or stretch_ratio > 35.0:
                defects.append(FitDefect(
                    defect_type="distorted_deformation",
                    severity="CRITICAL" if stretch_ratio > 35.0 else "MAJOR",
                    location="triangle_mesh",
                    measured_metric=f"degenerate_ratio={degen_ratio:.3f}, edge_stretch_ratio={stretch_ratio:.1f}",
                    suggestion="Run bounded triangle repair (`remove_invalid_triangles`) or clamp unstable stretched vertices.",
                ))

        if col_metrics.max_penetration_mm > 3.0:
            defects.append(FitDefect(
                defect_type="body_penetration",
                severity="CRITICAL" if col_metrics.max_penetration_mm > 12.0 else "MAJOR",
                location="torso_or_armscye_hull",
                measured_metric=f"initial_penetrations={col_metrics.initial_penetration_count}, max_depth_mm={col_metrics.max_penetration_mm}",
                suggestion="Increase chest/shoulder radial ease offset (+6mm to +12mm) and run XPBD collision relaxation.",
            ))
            suggestions.append("Increase garment radial clearance by at least 6mm around penetrating body zones.")

        if col_metrics.average_clearance_mm > 85.0:
            defects.append(FitDefect(
                defect_type="garment_gap",
                severity="MINOR",
                location="silhouette_envelope",
                measured_metric=f"avg_clearance_mm={col_metrics.average_clearance_mm}",
                suggestion="Excess stand-off clearance relative to target avatar; review scale/fit preference.",
            ))

        if float(extents_cm[1]) < 24.0 and cat_l in {"tops", "shirt", "hoodie", "jacket", "dress"}:
            defects.append(FitDefect(
                defect_type="missing_coverage",
                severity="CRITICAL",
                location="torso_vertical_coverage",
                measured_metric=f"height_cm={extents_cm[1]:.1f}",
                suggestion="Torso vertical coverage below minimum wearable garment span.",
            ))

        # Fit classification (never arbitrary)
        primary_ease = chest_ease if cat_l not in {"bottoms", "jeans", "trousers", "skirt"} else waist_ease
        if any(d.severity == "CRITICAL" for d in defects):
            fit_class = FitClassification.POTENTIALLY_INCORRECT
        elif primary_ease is None:
            fit_class = FitClassification.POTENTIALLY_INCORRECT
        elif primary_ease < 0.0:
            fit_class = FitClassification.TIGHT
            defects.append(FitDefect(
                defect_type="incorrect_proportions",
                severity="MAJOR",
                location="torso_circumference",
                measured_metric=f"negative_ease_cm={primary_ease}",
                suggestion="Size up or widen torso ease allowance to remove negative garment ease.",
            ))
            suggestions.append(f"Detected negative ease ({primary_ease} cm); recommend widening chest/torso block.")
        elif primary_ease < 5.5:
            fit_class = FitClassification.TIGHT
        elif primary_ease < 12.0:
            fit_class = FitClassification.REGULAR
        elif primary_ease < 19.0:
            fit_class = FitClassification.RELAXED
        else:
            fit_class = FitClassification.OVERSIZED

        # Score calibration from defects & ease
        score = 92.0
        for d in defects:
            score -= 28.0 if d.severity == "CRITICAL" else (12.0 if d.severity == "MAJOR" else 4.0)
        score = round(max(0.0, min(100.0, score)), 1)

        lat_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        inference_telemetry.record("fit-intelligence-v17", lat_ms, device="cpu", backend="geometric_physics")
        return FitIntelligenceReport(
            category=cat_l,
            avatar_profile_id=avatar_profile_id,
            fit_classification=fit_class,
            overall_fit_score=score,
            ease_summary_cm={"chest_ease_cm": chest_ease, "waist_ease_cm": waist_ease},
            dimensions=dimensions,
            collision_count=col_metrics.initial_penetration_count,
            max_penetration_mm=round(float(col_metrics.max_penetration_mm), 2),
            average_clearance_mm=round(float(col_metrics.average_clearance_mm), 2),
            asymmetry_ratio=round(float(asym), 4),
            defects=defects,
            deformation_suggestions=suggestions,
            geometry_mutated=False,
            latency_ms=lat_ms,
        )


fit_intelligence = FitIntelligenceEngine()
