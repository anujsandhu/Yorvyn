"""
FastAPI Routes for the Yorvyn Continuous AI Learning & Personalization Engine.
Provides authenticated endpoints for:
- User Personalization Memory & Preference Controls (Layer A)
- Structured AI Feedback Collection & Ingestion Pipeline (Layer B)
- Granular Consent Toggles & Auditable Settings
- Administrator Learning Dashboard, Evaluation, Deployment & Rollback Gates
"""

from __future__ import annotations

import uuid
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.app.core.security import get_current_user, UserContext
from backend.app.core.settings import settings
from backend.app.services.database.supabase_repository import supabase_repo
from backend.app.services.learning.personalization_service import personalization_service
from backend.app.services.learning.feedback_pipeline import feedback_pipeline
from backend.app.services.learning.model_training_service import model_training_service
from backend.app.models.learning_models import (
    CreateUserPreferenceRequest,
    UpdateUserPreferenceRequest,
    CreateAIFeedbackRequest,
    UpdateConsentRequest,
    RegisterModelRequest,
    DeployModelRequest,
    RollbackModelRequest,
    CreateTrainingJobRequest
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/learning", tags=["Continuous AI Learning & Personalization"])


def _verify_admin_access(request: Request, current_user: UserContext) -> None:
    """Verifies that the caller has admin or service_role authorization."""
    admin_header = request.headers.get("X-Admin-Key")
    is_admin_header = bool(admin_header and admin_header == settings.secret_key)
    is_admin_user = (
        current_user.role in ("admin", "service_role")
        or (current_user.email and current_user.email.endswith("@internal.yorvyn.ai"))
    )
    if not (is_admin_header or is_admin_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin or service-role privileges required."
        )


# ============================================================================
# Layer A: User Personalization Memory Endpoints
# ============================================================================

@router.get("/preferences", response_model=List[Dict[str, Any]])
def get_preferences(
    category: Optional[str] = Query(None, description="Optional preference category"),
    current_user: UserContext = Depends(get_current_user)
):
    """Retrieves authenticated user's active personalized styling preferences."""
    return personalization_service.get_user_preferences(
        user_id=current_user.user_id,
        category=category
    )


@router.post("/preferences", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def create_preference(
    req: CreateUserPreferenceRequest,
    current_user: UserContext = Depends(get_current_user)
):
    """Explicitly saves or updates an individual preference for the authenticated user."""
    return personalization_service.upsert_user_preference(
        user_id=current_user.user_id,
        category=req.category.value,
        key=req.key,
        value=req.value,
        source=req.source.value,
        confidence=req.confidence,
        evidence_count=req.evidence_count
    )


@router.patch("/preferences/{pref_id}", response_model=Dict[str, Any])
def update_preference(
    pref_id: str,
    req: UpdateUserPreferenceRequest,
    current_user: UserContext = Depends(get_current_user)
):
    """Updates an existing preference (e.g. value, confidence, active status)."""
    updates = req.dict(exclude_unset=True) if hasattr(req, "dict") else req.model_dump(exclude_unset=True)
    res = personalization_service.update_user_preference(
        user_id=current_user.user_id,
        pref_id=pref_id,
        updates=updates
    )
    if not res:
        raise HTTPException(status_code=404, detail=f"Preference '{pref_id}' not found.")
    return res


@router.delete("/preferences/{pref_id}", response_model=Dict[str, Any])
def delete_preference(
    pref_id: str,
    current_user: UserContext = Depends(get_current_user)
):
    """Deletes an individual preference record."""
    deleted = personalization_service.delete_user_preference(
        user_id=current_user.user_id,
        pref_id=pref_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Preference '{pref_id}' not found.")
    return {"success": True, "deleted_id": pref_id}


@router.post("/preferences/reset", response_model=Dict[str, Any])
def reset_preferences(
    category: Optional[str] = Query(None, description="Optional category to reset"),
    current_user: UserContext = Depends(get_current_user)
):
    """Resets all or categorical preferences for the user."""
    count = personalization_service.reset_user_preferences(
        user_id=current_user.user_id,
        category=category
    )
    return {"success": True, "reset_count": count, "category": category}


@router.get("/preferences/export", response_model=Dict[str, Any])
def export_user_data(
    current_user: UserContext = Depends(get_current_user)
):
    """GDPR/CCPA compliant export of all user personalization, consent, and feedback history."""
    return personalization_service.export_user_learning_data(user_id=current_user.user_id)


# ============================================================================
# Granular Consent Settings Endpoints
# ============================================================================

@router.get("/consent", response_model=Dict[str, Any])
def get_consent(
    current_user: UserContext = Depends(get_current_user)
):
    """Retrieves current user's learning and personalization consent toggles."""
    return supabase_repo.get_learning_consent(user_id=current_user.user_id)


@router.put("/consent", response_model=Dict[str, Any])
def update_consent(
    req: UpdateConsentRequest,
    current_user: UserContext = Depends(get_current_user)
):
    """Updates user's independent training and personalization consent toggles."""
    return supabase_repo.update_learning_consent(
        user_id=current_user.user_id,
        personalization_enabled=req.personalization_enabled,
        global_model_training_enabled=req.global_model_training_enabled,
        image_training_enabled=req.image_training_enabled,
        conversation_training_enabled=req.conversation_training_enabled,
        consent_version=req.consent_version or "v1.0"
    )


# ============================================================================
# User Feedback Collection & Validation Intake
# ============================================================================

@router.post("/feedback", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def submit_feedback(
    req: CreateAIFeedbackRequest,
    current_user: UserContext = Depends(get_current_user)
):
    """
    Submits structured feedback.
    1. Immediately informs Layer A personalization memory if applicable.
    2. Enqueues through the sanitized poisoning-guarded feedback pipeline for Layer B.
    """
    payload = {
        "user_id": current_user.user_id,
        "feedback_type": req.feedback_type.value,
        "session_id": req.session_id,
        "message_id": req.message_id,
        "search_id": req.search_id,
        "rating": req.rating,
        "original_output": req.original_output,
        "corrected_output": req.corrected_output,
        "feedback_text": req.feedback_text,
        "metadata": req.metadata or {}
    }

    # 1. Record in Layer A personalization memory
    feedback_rec = personalization_service.record_user_feedback(payload)

    # 2. Process through Layer B global model improvement pipeline
    pipeline_result = feedback_pipeline.process_and_route_feedback(
        feedback_id=feedback_rec["id"]
    )

    return {
        "success": True,
        "feedback": feedback_rec,
        "pipeline_status": pipeline_result
    }


@router.delete("/user-data", response_model=Dict[str, Any])
def purge_user_data(
    current_user: UserContext = Depends(get_current_user)
):
    """
    Complete user data deletion request:
    - Purges all personal preferences.
    - Propagates deletion to quarantine/remove any derived training examples.
    """
    prefs_purged = personalization_service.reset_user_preferences(user_id=current_user.user_id)
    examples_purged = supabase_repo.delete_learning_examples_by_user(user_id=current_user.user_id)

    return {
        "success": True,
        "user_id": current_user.user_id,
        "preferences_purged": prefs_purged,
        "training_examples_purged": examples_purged,
        "message": "User personalization and derived learning data completely expunged."
    }


# ============================================================================
# Administrator Learning Dashboard & Governance Endpoints
# ============================================================================

@router.get("/admin/dashboard", response_model=Dict[str, Any])
def get_admin_dashboard(
    request: Request,
    current_user: UserContext = Depends(get_current_user)
):
    """Aggregated administrator dashboard with privacy-preserving statistics."""
    _verify_admin_access(request, current_user)

    all_models = supabase_repo.list_models()
    all_jobs = supabase_repo.list_training_jobs(limit=20)
    all_examples = supabase_repo.list_learning_examples(limit=500)

    validated_count = sum(1 for e in all_examples if e.get("validation_status") == "validated")
    quarantined_count = sum(1 for e in all_examples if e.get("validation_status") == "quarantined")
    pending_count = sum(1 for e in all_examples if e.get("validation_status") == "pending")

    deployed_models = [m for m in all_models if m.get("status") == "deployed"]

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_examples": len(all_examples),
        "validated_examples": validated_count,
        "quarantined_examples": quarantined_count,
        "pending_examples": pending_count,
        "active_training_jobs_count": sum(1 for j in all_jobs if j.get("status") in ("queued", "running")),
        "deployed_models_count": len(deployed_models),
        "deployed_models": deployed_models,
        "recent_jobs": all_jobs[:5]
    }


@router.get("/admin/models", response_model=List[Dict[str, Any]])
def list_models(
    request: Request,
    task_type: Optional[str] = None,
    status: Optional[str] = None,
    current_user: UserContext = Depends(get_current_user)
):
    """Lists registered models."""
    _verify_admin_access(request, current_user)
    return supabase_repo.list_models(task_type=task_type, status=status)


@router.post("/admin/training-jobs", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def enqueue_training_job(
    req: CreateTrainingJobRequest,
    request: Request,
    current_user: UserContext = Depends(get_current_user)
):
    """Enqueues an asynchronous remote model training job."""
    _verify_admin_access(request, current_user)
    return model_training_service.trigger_training_job(
        model_name=req.model_name,
        task_type=req.task_type.value,
        dataset_version=req.dataset_version,
        training_config=req.training_config
    )


@router.post("/admin/training-jobs/{job_id}/execute", response_model=Dict[str, Any])
def execute_training_job(
    job_id: str,
    request: Request,
    current_user: UserContext = Depends(get_current_user)
):
    """Executes a queued training job and registers candidate model."""
    _verify_admin_access(request, current_user)
    return model_training_service.execute_training_job(job_id=job_id)


@router.post("/admin/evaluate-model", response_model=Dict[str, Any])
def evaluate_model(
    model_name: str = Query(...),
    model_version: str = Query(...),
    request: Request = None,
    current_user: UserContext = Depends(get_current_user)
):
    """Runs candidate model against held-out benchmark and checks quality gates."""
    _verify_admin_access(request, current_user)
    return model_training_service.evaluate_candidate_model(
        model_name=model_name,
        model_version=model_version
    )


@router.post("/admin/deploy-model", response_model=Dict[str, Any])
def deploy_model(
    req: DeployModelRequest,
    request: Request,
    current_user: UserContext = Depends(get_current_user)
):
    """Promotes an approved candidate model to production."""
    _verify_admin_access(request, current_user)
    return model_training_service.deploy_approved_model(
        model_name=req.model_name,
        model_version=req.model_version
    )


@router.post("/admin/rollback-model", response_model=Dict[str, Any])
def rollback_model(
    req: RollbackModelRequest,
    request: Request,
    current_user: UserContext = Depends(get_current_user)
):
    """Rolls back the production model for a task to a previous version."""
    _verify_admin_access(request, current_user)
    return model_training_service.rollback_task_model(
        task_type=req.task_type,
        target_version=req.target_version
    )

