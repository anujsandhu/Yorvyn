"""Phase 16.9 MotionCore FastAPI Routes: Capability Discovery, State Validation, Material Physics Profiles, Compute Selection & Animated GLB Validation."""
from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
import numpy as np

from backend.app.core.security import UserContext, get_current_user_optional
from backend.app.services.intelligence.capability_registry import garment_capabilities
from backend.app.services.motion.motion_core import (
    AdaptiveFabricProfileService,
    AnimationAssetSecurityValidator,
    ComputePolicyAdvisor,
    ComputeSelectionRequest,
    MotionEvaluationService,
    MotionStateMachine,
    MotionTransitionRequest,
    SkeletonRetargetingValidator,
)


router = APIRouter(prefix="/api/motion", tags=["MotionCore Animation & Cloth Simulation"])


def _effective_user(user: Optional[UserContext]) -> str:
    return user.user_id if user and getattr(user, "user_id", None) else "default_user"


class FabricProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str = Field(..., min_length=1, max_length=64)
    subcategory: Optional[str] = Field(None, max_length=64)
    fabric_hint: Optional[str] = Field(None, max_length=64)
    observed_components: List[str] = Field(default_factory=list)
    inferred_components: List[str] = Field(default_factory=list)
    has_construction_seams: bool = False
    seam_count: int = Field(0, ge=0, le=5000)
    visual_roughness: float = Field(0.65, ge=0.0, le=1.0)


class SkeletonRetargetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bone_names: List[str] = Field(..., max_length=256)
    parent_pairs: Optional[List[List[Optional[str]]]] = None


class GLBValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_ref: str = Field("avatar_motion_export.glb", min_length=1, max_length=256)
    glb_base64: str = Field(..., min_length=8)
    claimed_baked_cloth: bool = False


class MotionEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vertices: List[List[float]] = Field(..., min_length=3, max_length=20000)
    triangles: List[List[int]] = Field(..., min_length=1, max_length=40000)
    poses: Optional[List[str]] = None


@router.get("/capabilities")
async def list_motion_capabilities():
    caps = [
        c.model_dump()
        for c in garment_capabilities.entries()
        if c.id.startswith(("animation.", "motion.", "cloth.", "collision.", "fabric.", "secondary.", "compute."))
    ]
    return {"schema_version": "16.9", "capabilities": caps}


@router.post("/transition/validate")
async def validate_motion_transition(
    req: MotionTransitionRequest,
    user: Optional[UserContext] = Depends(get_current_user_optional),
):
    uid = _effective_user(user)
    res = MotionStateMachine.evaluate_transition(req)
    return {"owner_id": uid, **res.model_dump()}


@router.post("/fabric-profile")
async def resolve_fabric_physics_profile(
    req: FabricProfileRequest,
    user: Optional[UserContext] = Depends(get_current_user_optional),
):
    uid = _effective_user(user)
    profile = AdaptiveFabricProfileService.resolve_profile(
        category=req.category,
        subcategory=req.subcategory,
        fabric_hint=req.fabric_hint,
        observed_components=req.observed_components,
        inferred_components=req.inferred_components,
        has_construction_seams=req.has_construction_seams,
        seam_count=req.seam_count,
        visual_roughness=req.visual_roughness,
    )
    return {"owner_id": uid, "profile": profile.model_dump()}


@router.post("/skeleton/retarget-check")
async def check_skeleton_retargeting(
    req: SkeletonRetargetRequest,
    user: Optional[UserContext] = Depends(get_current_user_optional),
):
    _ = _effective_user(user)
    pairs = [(str(p[0]), p[1]) for p in req.parent_pairs] if req.parent_pairs else None
    plan = SkeletonRetargetingValidator.validate_and_plan(req.bone_names, pairs)
    return plan.model_dump()


@router.post("/compute/select")
async def select_compute_backend(
    req: ComputeSelectionRequest,
    user: Optional[UserContext] = Depends(get_current_user_optional),
):
    _ = _effective_user(user)
    return ComputePolicyAdvisor.select(req).model_dump()


@router.post("/glb/validate")
async def validate_animated_glb(
    req: GLBValidateRequest,
    user: Optional[UserContext] = Depends(get_current_user_optional),
):
    uid = _effective_user(user)
    try:
        AnimationAssetSecurityValidator.validate_safe_asset_ref(req.asset_ref)
        raw = base64.b64decode(req.glb_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    report = AnimationAssetSecurityValidator.validate_glb_animation_payload(
        raw, claimed_baked_cloth=req.claimed_baked_cloth
    )
    return {"owner_id": uid, "asset_ref": req.asset_ref, **report.model_dump()}


@router.post("/evaluate")
async def evaluate_motion_stability(
    req: MotionEvaluateRequest,
    user: Optional[UserContext] = Depends(get_current_user_optional),
):
    uid = _effective_user(user)
    pos = np.asarray(req.vertices, dtype=np.float32)
    tri = np.asarray(req.triangles, dtype=np.uint32)
    if pos.ndim != 2 or pos.shape[1] != 3 or tri.ndim != 2 or tri.shape[1] != 3:
        raise HTTPException(status_code=400, detail="Vertices must be Nx3 and triangles Mx3.")
    report = MotionEvaluationService.evaluate_canonical_sequences(
        positions=pos, indices=tri, poses=req.poses
    )
    return {"owner_id": uid, **report.model_dump()}
