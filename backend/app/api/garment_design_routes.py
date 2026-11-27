"""Phase 16.3 FastAPI Routes: Design Revisions, 2D-to-3D Pattern Sync, and Real-Time Candidate GLB Edits."""
from __future__ import annotations

import base64
import hashlib
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.app.core.security import UserContext, get_current_user_optional
from backend.app.services.garments.chat_candidate import apply_parametric_design_edit
from backend.app.services.garments.design_revisions import (
    SaveDesignRevisionRequest,
    design_revision_service,
)
from backend.app.services.garments.transactional_design_engine import (
    DesignTransactionRequest,
    transactional_design_engine,
)
from backend.app.services.garments.mesh_validation_service import MeshValidationService
from backend.app.services.garments.reconstruction.pattern_exporter import (
    export_pattern_dxf,
    export_pattern_json,
    export_pattern_svg,
)
from backend.app.services.garments.reconstruction.pattern_geometry import (
    Point2DPattern,
    validate_polygon_2d,
)
from backend.app.services.intelligence.pattern_construction_engine import pattern_construction_engine
from backend.app.services.intelligence.semantic_correspondence import (
    SEMANTIC_OPERATION_SPECS,
    SyncStatus,
    build_semantic_correspondence,
)


router = APIRouter(prefix="/api/garments", tags=["Real-Time Garment Design"])


def _effective_user(user: Optional[UserContext]) -> str:
    return user.user_id if user and getattr(user, "user_id", None) else "default_user"


class PatternPieceOverride(BaseModel):
    piece_id: str
    boundary_polygon: List[Dict[str, float]]


class SyncPatternRequest(BaseModel):
    category: str = "jacket"
    subcategory: str = ""
    fit: str = "regular"
    expected_version: Optional[int] = None
    piece_overrides: List[PatternPieceOverride] = Field(default_factory=list)
    include_exports: bool = True


class ParametricGLBEditRequest(BaseModel):
    glb_base64: str
    category: str = "jacket"
    torso_length_scale: float = Field(default=1.0, ge=0.65, le=1.40)
    torso_width_scale: float = Field(default=1.0, ge=0.70, le=1.45)
    shoulder_width_scale: float = Field(default=1.0, ge=0.80, le=1.30)
    sleeve_length_scale: float = Field(default=1.0, ge=0.50, le=1.35)
    sleeve_width_scale: float = Field(default=1.0, ge=0.70, le=1.45)
    collar_width_scale: float = Field(default=1.0, ge=0.70, le=1.35)
    cuff_width_scale: float = Field(default=1.0, ge=0.75, le=1.35)
    hem_width_scale: float = Field(default=1.0, ge=0.75, le=1.40)
    waistband_width_scale: float = Field(default=1.0, ge=0.75, le=1.40)
    leg_width_scale: float = Field(default=1.0, ge=0.75, le=1.45)
    leg_length_scale: float = Field(default=1.0, ge=0.60, le=1.35)
    pocket_offset_y_m: float = Field(default=0.0, ge=-0.06, le=0.06)
    base_color_rgba: Optional[List[float]] = None
    roughness: Optional[float] = Field(default=None, ge=0.04, le=1.0)
    metalness: Optional[float] = Field(default=None, ge=0.0, le=1.0)


@router.post("/{garment_id}/revisions", summary="Persist a versioned interactive design revision")
async def save_design_revision(
    garment_id: str,
    payload: SaveDesignRevisionRequest,
    current_user: Optional[UserContext] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    uid = _effective_user(current_user)
    try:
        rev = await run_in_threadpool(design_revision_service.save_revision, uid, garment_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"revision": rev.model_dump(mode="json")}


@router.get("/{garment_id}/revisions", summary="List owner-scoped saved design revisions")
async def list_design_revisions(
    garment_id: str,
    current_user: Optional[UserContext] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    uid = _effective_user(current_user)
    revs = await run_in_threadpool(design_revision_service.list_revisions, uid, garment_id)
    return {
        "garment_id": garment_id,
        "count": len(revs),
        "revisions": [r.model_dump(mode="json") for r in revs],
    }


@router.get("/{garment_id}/revisions/{revision_id}", summary="Restore a specific saved design revision")
async def get_design_revision(
    garment_id: str,
    revision_id: str,
    current_user: Optional[UserContext] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    uid = _effective_user(current_user)
    rev = await run_in_threadpool(design_revision_service.get_revision, uid, garment_id, revision_id)
    if not rev:
        raise HTTPException(status_code=404, detail=f"Design revision '{revision_id}' unavailable.")
    return {"revision": rev.model_dump(mode="json")}


@router.post("/{garment_id}/sync-pattern", summary="Validate 2D pattern edits and synchronize 3D parameters & exports")
async def sync_pattern_to_construction(
    garment_id: str,
    payload: SyncPatternRequest,
    current_user: Optional[UserContext] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    uid = _effective_user(current_user)
    existing = design_revision_service.list_revisions(uid, garment_id)
    current_ver = existing[-1].design_version if existing else 0
    if payload.expected_version is not None and payload.expected_version != current_ver:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict: expected {payload.expected_version}, stored {current_ver}.",
        )

    handoff = await run_in_threadpool(
        pattern_construction_engine.build_construction,
        garment_id,
        payload.category,
        subcategory=payload.subcategory,
        fit=payload.fit,
    )
    graph = handoff.construction_graph
    synced_geometry_params = {
        "torso_length_scale": 1.0,
        "torso_width_scale": 1.0,
        "sleeve_length_scale": 1.0,
        "sleeve_width_scale": 1.0,
        "collar_width_scale": 1.0,
        "hem_width_scale": 1.0,
    }

    for ov in payload.piece_overrides:
        if ov.piece_id not in graph.pieces:
            raise HTTPException(status_code=422, detail=f"Unknown pattern piece '{ov.piece_id}'.")
        new_pts = [Point2DPattern(x=float(pt["x"]), y=float(pt["y"])) for pt in ov.boundary_polygon]
        poly_errors = validate_polygon_2d(new_pts)
        if poly_errors:
            raise HTTPException(
                status_code=422,
                detail={"message": f"Invalid pattern polygon for '{ov.piece_id}'", "errors": poly_errors},
            )
        piece = graph.pieces[ov.piece_id]
        old_xs = [p.x for p in piece.boundary_polygon]
        old_ys = [p.y for p in piece.boundary_polygon]
        new_xs = [p.x for p in new_pts]
        new_ys = [p.y for p in new_pts]
        rw = (max(new_xs) - min(new_xs)) / max(1e-4, max(old_xs) - min(old_xs))
        rh = (max(new_ys) - min(new_ys)) / max(1e-4, max(old_ys) - min(old_ys))
        piece.boundary_polygon = new_pts
        if "sleeve" in ov.piece_id:
            synced_geometry_params["sleeve_width_scale"] = round(max(0.7, min(1.45, rw)), 4)
            synced_geometry_params["sleeve_length_scale"] = round(max(0.5, min(1.35, rh)), 4)
        elif "collar" in ov.piece_id:
            synced_geometry_params["collar_width_scale"] = round(max(0.7, min(1.35, rw)), 4)
        else:
            synced_geometry_params["torso_width_scale"] = round(max(0.7, min(1.45, rw)), 4)
            synced_geometry_params["torso_length_scale"] = round(max(0.65, min(1.40, rh)), 4)

    corr = build_semantic_correspondence(garment_id=garment_id, candidate_id=None, graph=handoff.construction_graph)
    sync_status = (
        SyncStatus.SYNCHRONIZED_WITH_UNCERTAINTY
        if any(m.verification_state.value != "OBSERVED" for m in corr.piece_mappings.values())
        else SyncStatus.SYNCHRONIZED
    )
    result: Dict[str, Any] = {
        "garment_id": garment_id,
        "sync_status": sync_status.value,
        "synced_geometry_params": synced_geometry_params,
        "correspondence": corr.model_dump(mode="json"),
        "handoff": handoff.model_dump(mode="json"),
    }
    if payload.include_exports:
        result["exports"] = {
            "svg": export_pattern_svg(handoff),
            "dxf": export_pattern_dxf(handoff),
            "construction_json": export_pattern_json(handoff),
        }
    return result


@router.get("/{garment_id}/correspondence", summary="Get semantic 2D pattern-to-3D mesh correspondence")
async def get_semantic_correspondence(
    garment_id: str,
    category: str = "jacket",
    subcategory: str = "",
    current_user: Optional[UserContext] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    handoff = await run_in_threadpool(
        pattern_construction_engine.build_construction,
        garment_id, category, subcategory=subcategory,
    )
    corr = build_semantic_correspondence(garment_id=garment_id, candidate_id=None, graph=handoff.construction_graph)
    supported_ops = [
        spec.model_dump()
        for spec in SEMANTIC_OPERATION_SPECS.values()
        if any(c in category.lower() or category.lower() in c for c in spec.supported_categories)
    ]
    return {
        "garment_id": garment_id,
        "correspondence": corr.model_dump(mode="json"),
        "supported_operations": supported_ops,
    }


@router.post("/{garment_id}/transactions/execute", summary="Execute candidate-first atomic design transaction")
async def execute_design_transaction(
    garment_id: str,
    payload: DesignTransactionRequest,
    current_user: Optional[UserContext] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    uid = _effective_user(current_user)
    res = await run_in_threadpool(
        transactional_design_engine.execute_transaction,
        user_id=uid, garment_id=garment_id, req=payload,
    )
    if not res.committed:
        code = 409 if res.sync_status == SyncStatus.CONSTRUCTION_CONFLICT else 422
        raise HTTPException(status_code=code, detail=res.model_dump(mode="json"))
    return res.model_dump(mode="json")


@router.post("/{garment_id}/candidate-edit-gl", summary="Apply bounded real-time parametric edit to candidate GLB")
async def apply_candidate_parametric_glb(
    garment_id: str,
    payload: ParametricGLBEditRequest,
    current_user: Optional[UserContext] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    try:
        src_bytes = base64.b64decode(payload.glb_base64)
        edited = await run_in_threadpool(
            apply_parametric_design_edit,
            src_bytes,
            torso_length_scale=payload.torso_length_scale,
            torso_width_scale=payload.torso_width_scale,
            shoulder_width_scale=payload.shoulder_width_scale,
            sleeve_length_scale=payload.sleeve_length_scale,
            sleeve_width_scale=payload.sleeve_width_scale,
            collar_width_scale=payload.collar_width_scale,
            cuff_width_scale=payload.cuff_width_scale,
            hem_width_scale=payload.hem_width_scale,
            waistband_width_scale=payload.waistband_width_scale,
            leg_width_scale=payload.leg_width_scale,
            leg_length_scale=payload.leg_length_scale,
            pocket_offset_y_m=payload.pocket_offset_y_m,
            base_color_rgba=payload.base_color_rgba,
            roughness=payload.roughness,
            metalness=payload.metalness,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    report = await run_in_threadpool(MeshValidationService.validate_glb_bytes, edited, payload.category)
    if not report.is_valid:
        raise HTTPException(status_code=422, detail="Edited mesh failed structural validation: " + "; ".join(report.issues[:3]))
    return {
        "garment_id": garment_id,
        "candidate_sha256": hashlib.sha256(edited).hexdigest(),
        "mesh_report": report.to_dict(),
        "glb_base64": base64.b64encode(edited).decode("ascii"),
    }
