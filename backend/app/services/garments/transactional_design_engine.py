"""Phase 16.3.1 Construction Constraint Validator & Atomic 13-Step Transactional Design Engine."""
from __future__ import annotations

import base64
from collections import deque
import hashlib
import json
import math
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from backend.app.services.garments.chat_candidate import apply_parametric_design_edit
from backend.app.services.garments.design_revisions import (
    DesignOperationRecord,
    GarmentDesignRevision,
    GeometryDesignParams,
    MaterialRevisionConfig,
    SaveDesignRevisionRequest,
    compute_canonical_hash,
    design_revision_service,
)
from backend.app.services.garments.mesh_validation_service import MeshValidationService
from backend.app.services.garments.reconstruction.pattern_exporter import (
    export_pattern_dxf,
    export_pattern_json,
    export_pattern_svg,
)
from backend.app.services.garments.reconstruction.pattern_geometry import (
    AssemblyValidationIssue,
    AssemblyValidationReport,
    ConstructionVerificationState,
    EdgeRole,
    PatternPiece2D,
    Point2DPattern,
    UnifiedConstructionGraphContract,
    polygon_perimeter,
    signed_polygon_area,
    validate_polygon_2d,
)
from backend.app.services.intelligence.pattern_construction_engine import (
    AssemblyValidator,
    pattern_construction_engine,
)
from backend.app.services.intelligence.semantic_correspondence import (
    CORRESPONDENCE_VERSION,
    MeasurementScope,
    SEMANTIC_OPERATION_SPECS,
    SemanticCorrespondenceMap,
    SyncStatus,
    TopologySignature,
    apply_panel_ease_to_chest,
    build_semantic_correspondence,
    validate_correspondence_against_topology,
)


class PatternOverrideSpec(BaseModel):
    piece_id: str
    boundary_polygon: List[Dict[str, float]]


class DesignTransactionRequest(BaseModel):
    request_id: Optional[str] = None
    candidate_id: Optional[str] = None
    expected_parent_version: Optional[int] = None
    expected_geometry_version: Optional[int] = None
    expected_pattern_version: Optional[int] = None
    operation_name: Optional[str] = None  # key in SEMANTIC_OPERATION_SPECS or "pattern_edit" or "material_edit"
    category: str = "jacket"
    subcategory: str = ""
    fit: str = "regular"
    source: str = "studio"  # studio | pattern_2d | stylist_chat
    geometry_params: GeometryDesignParams = Field(default_factory=GeometryDesignParams)
    material_config: MaterialRevisionConfig = Field(default_factory=MaterialRevisionConfig)
    piece_overrides: List[PatternOverrideSpec] = Field(default_factory=list)
    panel_ease_delta_m: Optional[float] = None
    target_piece_id: Optional[str] = None
    symmetric_ease: bool = True
    glb_base64: Optional[str] = None
    expected_vertex_count: Optional[int] = None
    expected_triangle_count: Optional[int] = None
    allow_asymmetric: bool = False
    include_exports: bool = True


class DesignTransactionResult(BaseModel):
    committed: bool
    rolled_back: bool
    sync_status: SyncStatus
    stage_failed: Optional[str] = None
    issues: List[str] = Field(default_factory=list)
    revision: Optional[GarmentDesignRevision] = None
    previous_revision_version: int = 0
    correspondence: Optional[SemanticCorrespondenceMap] = None
    validation_report: Optional[AssemblyValidationReport] = None
    scoped_measurements: Dict[str, Any] = Field(default_factory=dict)
    mesh_report: Optional[Dict[str, Any]] = None
    edited_glb_base64: Optional[str] = None
    exports: Dict[str, str] = Field(default_factory=dict)
    transaction_ms: float = 0.0


def validate_extended_construction(
    graph: UnifiedConstructionGraphContract,
    *,
    allow_asymmetric: bool = False,
) -> AssemblyValidationReport:
    """Validate 2D polygons, seams, connectivity (disconnected panels), symmetry, curves, and allowances."""
    base_report = AssemblyValidator.validate(graph)
    issues: List[AssemblyValidationIssue] = list(base_report.issues)

    # 1. Seam allowance, dart/notch & closed curve consistency
    for pid, piece in graph.pieces.items():
        if piece.seam_allowance_m < 0.0 or piece.seam_allowance_m > 0.06:
            issues.append(AssemblyValidationIssue(
                severity="ERROR", code="INVALID_SEAM_ALLOWANCE",
                message=f"Piece '{pid}' has invalid seam allowance {piece.seam_allowance_m}m.",
                piece_ids=[pid],
            ))
        for notch in piece.notches:
            if not any(e.edge_id == notch.edge_id for e in piece.edges):
                issues.append(AssemblyValidationIssue(
                    severity="ERROR", code="ORPHAN_NOTCH_EDGE",
                    message=f"Notch '{notch.notch_id}' on '{pid}' points to missing edge '{notch.edge_id}'.",
                    piece_ids=[pid],
                ))

    # 2. Disconnected panel component check (BFS across seams)
    if len(graph.pieces) > 1:
        adj: Dict[str, List[str]] = {pid: [] for pid in graph.pieces}
        for s in graph.seams:
            if s.piece_a in adj and s.piece_b in adj:
                adj[s.piece_a].append(s.piece_b)
                adj[s.piece_b].append(s.piece_a)
        start = next(iter(graph.pieces))
        seen = {start}
        q = deque([start])
        while q:
            cur = q.popleft()
            for nxt in adj[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
        disconnected = sorted(set(graph.pieces.keys()) - seen)
        if disconnected:
            issues.append(AssemblyValidationIssue(
                severity="ERROR", code="DISCONNECTED_PATTERN_PANELS",
                message=f"Pattern pieces disconnected from assembly graph: {disconnected}.",
                piece_ids=disconnected,
            ))

    # 3. Left/Right pair symmetry tolerance check (unless explicitly asymmetric)
    if not allow_asymmetric:
        for l_id, r_id in (("front_left_body", "front_right_body"), ("left_sleeve", "right_sleeve"), ("left_front_leg", "right_front_leg")):
            lp = graph.pieces.get(l_id)
            rp = graph.pieces.get(r_id)
            if lp and rp:
                rel_diff = abs(lp.area_m2 - rp.area_m2) / max(1e-4, lp.area_m2)
                if rel_diff > 0.18:
                    issues.append(AssemblyValidationIssue(
                        severity="ERROR", code="SYMMETRY_VIOLATION",
                        message=f"Symmetric pair ({l_id}, {r_id}) diverged by {rel_diff * 100:.1f}%.",
                        piece_ids=[l_id, r_id],
                    ))

    has_err = any(i.severity == "ERROR" for i in issues)
    return AssemblyValidationReport(
        is_valid=not has_err,
        pieces_checked=base_report.pieces_checked,
        seams_checked=base_report.seams_checked,
        has_cycles=base_report.has_cycles,
        seam_length_mismatches=base_report.seam_length_mismatches,
        issues=issues,
        unsupported_features=base_report.unsupported_features,
    )


class TransactionalDesignEngine:
    """Candidate-first atomic design transaction executor with automatic rollback."""

    def execute_transaction(
        self,
        *,
        user_id: str,
        garment_id: str,
        req: DesignTransactionRequest,
        cancel_event: Optional[threading.Event] = None,
    ) -> DesignTransactionResult:
        t0 = time.perf_counter()

        def abort(stage: str, status: SyncStatus, issues: List[str], prev_ver: int, corr: Optional[SemanticCorrespondenceMap] = None, val: Optional[AssemblyValidationReport] = None) -> DesignTransactionResult:
            return DesignTransactionResult(
                committed=False,
                rolled_back=True,
                sync_status=status,
                stage_failed=stage,
                issues=issues,
                previous_revision_version=prev_ver,
                correspondence=corr,
                validation_report=val,
                transaction_ms=round((time.perf_counter() - t0) * 1000.0, 2),
            )

        # Stage 1 & 2: Capture current revision & check optimistic concurrency
        history = design_revision_service.list_revisions(user_id, garment_id)
        if req.request_id:
            for existing in history:
                if existing.request_id == req.request_id:
                    return DesignTransactionResult(
                        committed=True,
                        rolled_back=False,
                        sync_status=SyncStatus(existing.sync_status),
                        revision=existing,
                        previous_revision_version=existing.parent_version or 0,
                        scoped_measurements=existing.scoped_measurements,
                        transaction_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                    )

        prev_version = history[-1].design_version if history else 0
        prev_geom_ver = history[-1].geometry_version if history else 1
        prev_pat_ver = history[-1].pattern_version if history else 1

        if req.expected_parent_version is not None and req.expected_parent_version != prev_version:
            return abort(
                "concurrency_check",
                SyncStatus.CONSTRUCTION_CONFLICT,
                [f"Stale revision: expected parent version {req.expected_parent_version}, stored is {prev_version}."],
                prev_version,
            )

        if cancel_event and cancel_event.is_set():
            return abort("cancelled", SyncStatus.VALIDATION_FAILED, ["Transaction interrupted before execution."], prev_version)

        # Stage 3: Validate operation parameters
        op_spec = None
        if req.operation_name and req.operation_name in SEMANTIC_OPERATION_SPECS:
            op_spec = SEMANTIC_OPERATION_SPECS[req.operation_name]
            cat = req.category.lower().strip()
            if not any(c in cat or cat in c for c in op_spec.supported_categories):
                return abort(
                    "parameter_validation",
                    SyncStatus.NOT_SUPPORTED,
                    [f"Operation '{req.operation_name}' is not supported for category '{req.category}'."],
                    prev_version,
                )
        elif req.operation_name and req.operation_name not in ("pattern_edit", "material_edit"):
            return abort(
                "parameter_validation",
                SyncStatus.NOT_SUPPORTED,
                [f"Unknown or unsupported design operation '{req.operation_name}'."],
                prev_version,
            )

        # Stage 4: Build authoritative candidate pattern graph & apply overrides / dimensional ease
        handoff = pattern_construction_engine.build_construction(
            garment_id, req.category, subcategory=req.subcategory, fit=req.fit, cancel_event=cancel_event,
        )
        graph = handoff.construction_graph
        geom_params = req.geometry_params.model_copy()

        scoped_meas: Dict[str, Any] = {}
        # Apply explicit piece polygon overrides cleanly in candidate graph before validation
        for ov in req.piece_overrides:
            if ov.piece_id not in graph.pieces:
                return abort("candidate_pattern", SyncStatus.VALIDATION_FAILED, [f"Unknown piece '{ov.piece_id}'."], prev_version)
            pts = [Point2DPattern(x=float(p["x"]), y=float(p["y"])) for p in ov.boundary_polygon]
            poly_err = validate_polygon_2d(pts)
            if poly_err:
                return abort("pattern_validation", SyncStatus.VALIDATION_FAILED, poly_err, prev_version)
            piece = graph.pieces[ov.piece_id]
            piece.boundary_polygon = pts
            piece.area_m2 = round(abs(signed_polygon_area(pts)), 6)
            piece.perimeter_m = polygon_perimeter(pts)
            xs = [p.x for p in pts]
            ys = [p.y for p in pts]
            new_w = max(0.05, max(xs) - min(xs))
            old_w = piece.dimensions.get("chest_width").value_m if "chest_width" in piece.dimensions else new_w
            if old_w and old_w > 0.05:
                ratio = max(0.75, min(1.40, new_w / old_w))
                geom_params.torso_width_scale = round(ratio, 4)

        # Apply explicit scoped panel ease delta cleanly without ambiguous scaling
        if req.panel_ease_delta_m is not None:
            pid = req.target_piece_id or ("front_left_body" if "front_left_body" in graph.pieces else ("front_body" if "front_body" in graph.pieces else next(iter(graph.pieces))))
            target_p = graph.pieces.get(pid)
            if not target_p:
                return abort("dimensional_contract", SyncStatus.VALIDATION_FAILED, [f"Target piece '{pid}' absent."], prev_version)
            xs = [p.x for p in target_p.boundary_polygon]
            old_pw = max(xs) - min(xs)
            scope = MeasurementScope.PATTERN_PANEL_HALF if ("front_left" in pid or "front_right" in pid) else MeasurementScope.PATTERN_PANEL_FULL
            try:
                conv = apply_panel_ease_to_chest(
                    panel_width_m=old_pw,
                    panel_scope=scope,
                    ease_delta_m=req.panel_ease_delta_m,
                    apply_symmetrically=req.symmetric_ease,
                )
            except ValueError as exc:
                return abort("dimensional_contract", SyncStatus.VALIDATION_FAILED, [str(exc)], prev_version)
            scoped_meas = {k: v.model_dump() | {"value_cm": v.value_cm} for k, v in conv.items()}
            scale_x = conv["panel_width"].value_m / max(1e-4, old_pw)
            target_p.boundary_polygon = [Point2DPattern(x=round(p.x * scale_x, 5), y=p.y) for p in target_p.boundary_polygon]
            target_p.area_m2 = round(abs(signed_polygon_area(target_p.boundary_polygon)), 6)
            target_p.perimeter_m = polygon_perimeter(target_p.boundary_polygon)
            if req.symmetric_ease:
                mate_id = "front_right_body" if pid == "front_left_body" else ("front_left_body" if pid == "front_right_body" else None)
                if mate_id and mate_id in graph.pieces:
                    mate = graph.pieces[mate_id]
                    mate.boundary_polygon = [Point2DPattern(x=round(p.x * scale_x, 5), y=p.y) for p in mate.boundary_polygon]
                    mate.area_m2 = round(abs(signed_polygon_area(mate.boundary_polygon)), 6)
                    mate.perimeter_m = polygon_perimeter(mate.boundary_polygon)
                if "back_body" in graph.pieces:
                    bk = graph.pieces["back_body"]
                    bk.boundary_polygon = [Point2DPattern(x=round(p.x * scale_x, 5), y=p.y) for p in bk.boundary_polygon]
                    bk.area_m2 = round(abs(signed_polygon_area(bk.boundary_polygon)), 6)
                    bk.perimeter_m = polygon_perimeter(bk.boundary_polygon)
            geom_params.torso_width_scale = round(max(0.75, min(1.40, scale_x)), 4)

        # Stage 5 & 9: Candidate 3D GLB edit + structural MeshValidationService check (if binary GLB provided)
        edited_glb_bytes: Optional[bytes] = None
        mesh_report_dict: Optional[Dict[str, Any]] = None
        available_3d_regions: List[str] = []
        v_cnt = 0
        t_cnt = 0
        if req.glb_base64:
            try:
                src_bytes = base64.b64decode(req.glb_base64)
                # Inspect node extras from GLTF header for semantic regions
                magic, _, _, j_len, _ = __import__("struct").unpack_from("<4sIII4s", src_bytes)
                if magic == b"glTF":
                    gl_json = json.loads(src_bytes[20:20 + j_len])
                    available_3d_regions = [
                        str(n.get("extras", {}).get("component_id") or n.get("name", ""))
                        for n in gl_json.get("nodes", [])
                        if "mesh" in n
                    ]
                    if gl_json.get("accessors"):
                        pos_accs = [a for a in gl_json["accessors"] if a.get("type") == "VEC3"]
                        v_cnt = pos_accs[0]["count"] if pos_accs else 0
                raw_dict = geom_params.model_dump()
                mat = req.material_config
                edited_glb_bytes = apply_parametric_design_edit(
                    src_bytes,
                    torso_length_scale=raw_dict.get("torso_length_scale", 1.0),
                    torso_width_scale=raw_dict.get("torso_width_scale", 1.0),
                    shoulder_width_scale=raw_dict.get("shoulder_width_scale", 1.0),
                    sleeve_length_scale=raw_dict.get("sleeve_length_scale", 1.0),
                    sleeve_width_scale=raw_dict.get("sleeve_width_scale", 1.0),
                    collar_width_scale=raw_dict.get("collar_width_scale", 1.0),
                    cuff_width_scale=raw_dict.get("cuff_width_scale", 1.0),
                    hem_width_scale=raw_dict.get("hem_width_scale", 1.0),
                    waistband_width_scale=raw_dict.get("waistband_width_scale", 1.0),
                    leg_width_scale=raw_dict.get("leg_width_scale", 1.0),
                    leg_length_scale=raw_dict.get("leg_length_scale", 1.0),
                    pocket_offset_y_m=raw_dict.get("pocket_offset_y_m", 0.0),
                    roughness=mat.roughness,
                    metalness=mat.metalness,
                )
            except Exception as exc:
                return abort("geometry_edit", SyncStatus.VALIDATION_FAILED, [str(exc)], prev_version)

            val_3d = MeshValidationService.validate_glb_bytes(edited_glb_bytes, req.category)
            mesh_report_dict = val_3d.to_dict()
            v_cnt = val_3d.vertex_count
            t_cnt = val_3d.face_count
            if not val_3d.is_valid:
                return abort("3d_mesh_validation", SyncStatus.VALIDATION_FAILED, val_3d.issues, prev_version)

        if cancel_event and cancel_event.is_set():
            return abort("cancelled", SyncStatus.VALIDATION_FAILED, ["Transaction interrupted before commit."], prev_version)

        # Stage 6 & 11: Build semantic correspondence + validate topology invariants
        topo_sig = TopologySignature(
            vertex_count=req.expected_vertex_count or v_cnt,
            triangle_count=req.expected_triangle_count or t_cnt,
            component_ids_hash=hashlib.sha256(json.dumps(sorted(available_3d_regions)).encode()).hexdigest()[:16],
        )
        corr = build_semantic_correspondence(
            garment_id=garment_id,
            candidate_id=req.candidate_id,
            graph=graph,
            available_3d_regions=available_3d_regions,
            topology_signature=topo_sig,
            pattern_version=prev_pat_ver + 1,
            geometry_version=prev_geom_ver + 1,
        )
        corr_ok, sync_status, corr_issues = validate_correspondence_against_topology(
            corr,
            expected_vertex_count=v_cnt or topo_sig.vertex_count,
            expected_triangle_count=t_cnt or topo_sig.triangle_count,
            operation_name=req.operation_name if req.operation_name in SEMANTIC_OPERATION_SPECS else None,
        )
        if not corr_ok:
            return abort("correspondence_sync", sync_status, corr_issues, prev_version, corr=corr)

        # Stage 7 & 8: Extended pattern + seam + connectivity + symmetry validation
        val_report = validate_extended_construction(graph, allow_asymmetric=req.allow_asymmetric)
        if not val_report.is_valid:
            err_msgs = [i.message for i in val_report.issues if i.severity == "ERROR"]
            return abort("construction_validation", SyncStatus.CONSTRUCTION_CONFLICT, err_msgs, prev_version, corr=corr, val=val_report)

        # Stage 10: Dimensional consistency check
        for pid, piece in graph.pieces.items():
            if piece.area_m2 <= 0.0005 or piece.perimeter_m <= 0.04:
                return abort(
                    "dimensional_consistency",
                    SyncStatus.VALIDATION_FAILED,
                    [f"Piece '{pid}' collapsed below physical minimums (area={piece.area_m2})."],
                    prev_version, corr=corr, val=val_report,
                )

        # Stage 12: Commit complete revision atomically
        mapping_hash = compute_canonical_hash(corr.model_dump())
        exports: Dict[str, str] = {}
        if req.include_exports:
            exports = {
                "svg": export_pattern_svg(handoff),
                "dxf": export_pattern_dxf(handoff),
                "construction_json": export_pattern_json(handoff),
            }

        save_req = SaveDesignRevisionRequest(
            candidate_id=req.candidate_id,
            request_id=req.request_id,
            expected_parent_version=prev_version,
            geometry_version=prev_geom_ver + 1,
            pattern_version=prev_pat_ver + 1,
            material_version=(history[-1].material_version + 1) if history else 1,
            texture_version=history[-1].texture_version if history else 1,
            correspondence_version=CORRESPONDENCE_VERSION,
            sync_status=sync_status.value,
            mapping_hash=mapping_hash,
            candidate_sha256=hashlib.sha256(edited_glb_bytes).hexdigest() if edited_glb_bytes else None,
            category=req.category,
            subcategory=req.subcategory,
            geometry_params=geom_params,
            material_config=req.material_config,
            pattern_overrides={pid: p.model_dump(mode="json") for pid, p in graph.pieces.items()},
            measurements={
                "garment_length_m": round(graph.pieces[next(iter(graph.pieces))].perimeter_m, 4) if graph.pieces else 0.0,
            },
            scoped_measurements=scoped_meas,
            validation_summary=val_report.model_dump(mode="json"),
            operation_history=[
                DesignOperationRecord(
                    kind=req.operation_name or "design_transaction",
                    target_component=op_spec.target_component if op_spec else (req.target_piece_id or "garment"),
                    source=req.source,
                    parameters={"sync_status": sync_status.value, "allow_asymmetric": req.allow_asymmetric},
                )
            ],
        )
        try:
            rev = design_revision_service.save_revision(user_id, garment_id, save_req)
        except ValueError as exc:
            return abort("atomic_commit", SyncStatus.CONSTRUCTION_CONFLICT, [str(exc)], prev_version, corr=corr, val=val_report)

        return DesignTransactionResult(
            committed=True,
            rolled_back=False,
            sync_status=sync_status,
            revision=rev,
            previous_revision_version=prev_version,
            correspondence=corr,
            validation_report=val_report,
            scoped_measurements=scoped_meas,
            mesh_report=mesh_report_dict,
            edited_glb_base64=base64.b64encode(edited_glb_bytes).decode("ascii") if edited_glb_bytes else None,
            exports=exports,
            transaction_ms=round((time.perf_counter() - t0) * 1000.0, 2),
        )


transactional_design_engine = TransactionalDesignEngine()
