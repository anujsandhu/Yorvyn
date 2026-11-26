"""
Yorvyn Beta Onboarding, Invitation Management & User Feedback Routes.
Handles controlled private beta access, token validation, participant tracking,
and structured in-product defect and quality feedback collection.
"""

import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field

from backend.app.core.security import get_current_user, get_current_user_optional, UserContext
from backend.app.services.database.supabase_repository import supabase_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/beta", tags=["Beta Operations"])


# ── Pydantic Request / Response Models ──────────────────────────────────────

class ValidateInviteRequest(BaseModel):
    token: str = Field(..., min_length=4, max_length=64)


class ActivateInviteRequest(BaseModel):
    token: str = Field(..., min_length=4, max_length=64)


class UpdateCohortStatusRequest(BaseModel):
    token_or_id: str
    status: str = Field(..., pattern="^(pending|active|suspended|revoked)$")


class SubmitBetaFeedbackRequest(BaseModel):
    job_id: Optional[str] = None
    correlation_id: Optional[str] = None
    software_version: str = "v2026.11-beta"
    reconstruction_rating: Optional[int] = Field(None, ge=1, le=5)
    fitting_rating: Optional[int] = Field(None, ge=1, le=5)
    texture_rating: Optional[int] = Field(None, ge=1, le=5)
    category_correct: bool = True
    usability_rating: Optional[int] = Field(None, ge=1, le=5)
    feedback_text: Optional[str] = None
    failure_category: Optional[str] = None
    reproduction_steps: Optional[str] = None
    include_raw_image: bool = False
    severity: str = Field("normal", pattern="^(low|normal|high|critical)$")


# ── Beta Onboarding Endpoints ────────────────────────────────────────────────

@router.post("/validate-invite")
async def validate_invitation(req: ValidateInviteRequest):
    """
    Public validation endpoint for prospective beta testers.
    Verifies that the invitation code is authentic, unexpired, and not redeemed.
    """
    valid, message, inv = supabase_repo.validate_beta_token(req.token)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    return {
        "valid": True,
        "message": message,
        "cohort": inv.get("cohort", "closed_pilot") if inv else "closed_pilot",
        "email_hint": inv.get("email")[:3] + "***" if inv and inv.get("email") else None
    }


@router.post("/activate-invite")
async def activate_invitation(
    req: ActivateInviteRequest,
    current_user: UserContext = Depends(get_current_user)
):
    """
    Links a validated invitation token to the newly signed-in user's account.
    """
    if current_user.role == "anon":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated account required to activate beta invitation."
        )

    success, message = supabase_repo.activate_beta_invitation(req.token, current_user.user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    return {
        "success": True,
        "message": message,
        "user_id": current_user.user_id
    }


@router.get("/cohort")
async def get_beta_cohort(
    cohort: Optional[str] = None,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """
    Returns the list of active beta cohort members and activation status.
    Requires authenticated account.
    """
    if not current_user or current_user.role == "anon":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to inspect beta cohort."
        )

    members = supabase_repo.list_beta_cohort(cohort=cohort)
    active_count = sum(1 for m in members if m.get("status") == "active")
    pending_count = sum(1 for m in members if m.get("status") == "pending")

    # Scrub sensitive tokens for security unless admin/service-role
    sanitized = []
    for m in members:
        sanitized.append({
            "id": m.get("id"),
            "email_masked": m.get("email", "")[:3] + "***",
            "cohort": m.get("cohort"),
            "status": m.get("status"),
            "activated_at": m.get("activated_at"),
            "created_at": m.get("created_at")
        })

    return {
        "total_cohort_size": len(members),
        "active_participants": active_count,
        "pending_invitations": pending_count,
        "cohort": cohort or "all",
        "participants": sanitized
    }


@router.post("/cohort/status")
async def update_cohort_status(
    req: UpdateCohortStatusRequest,
    current_user: UserContext = Depends(get_current_user)
):
    """
    Suspends, revokes, or reactivates a beta participant.
    """
    updated = supabase_repo.update_beta_status(req.token_or_id, req.status)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Beta participant or invitation token not found."
        )

    return {
        "success": True,
        "status": req.status,
        "token_or_id": req.token_or_id
    }


# ── Beta User Feedback & Defect Reporting ───────────────────────────────────

@router.post("/feedback")
async def submit_beta_feedback(
    req: SubmitBetaFeedbackRequest,
    request: Request,
    current_user: UserContext = Depends(get_current_user)
):
    """
    Records in-product quality ratings (reconstruction, fitting, textures)
    and reproducible bug/defect reports without storing unconsented raw images.
    """
    correlation_id = req.correlation_id or request.headers.get("X-Correlation-ID")
    feedback_data = req.model_dump()
    feedback_data["user_id"] = current_user.user_id
    feedback_data["correlation_id"] = correlation_id

    # Strict privacy safeguard:
    # If the user did NOT explicitly opt in to include the raw image for debugging,
    # force include_raw_image to false
    if not req.include_raw_image:
        feedback_data["include_raw_image"] = False

    record = supabase_repo.record_beta_feedback(feedback_data)
    return {
        "success": True,
        "feedback_id": record["id"],
        "message": "Thank you for supporting the Yorvyn Private Beta! Your feedback helps train our models and refine avatar simulation."
    }


@router.get("/feedback")
async def list_beta_feedback(
    current_user: UserContext = Depends(get_current_user)
):
    """
    Retrieves submitted feedback for the authenticated user.
    """
    feedbacks = supabase_repo.get_beta_feedbacks(user_id=current_user.user_id)
    return {
        "count": len(feedbacks),
        "feedbacks": feedbacks
    }


@router.get("/defects")
async def list_beta_defects(
    severity: Optional[str] = None,
    current_user: Optional[UserContext] = Depends(get_current_user_optional)
):
    """
    Returns defect reports from the beta defect registry for quality tracking.
    """
    if not current_user or current_user.role == "anon":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to inspect defect registry."
        )

    defects = supabase_repo.get_beta_defects(severity=severity)
    return {
        "total_defects": len(defects),
        "severity_filter": severity or "all",
        "defects": defects
    }

