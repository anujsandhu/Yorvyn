"""
Pydantic Data Transfer Objects and Enums for the
Yorvyn Continuous AI Learning & Personalization Engine.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PreferenceCategory(str, Enum):
    FIT = "fit"
    STYLE = "style"
    COLOUR = "colour"
    FABRIC = "fabric"
    BRAND = "brand"
    OCCASION = "occasion"
    BUDGET = "budget"
    OUTFIT = "outfit"
    SHOPPING = "shopping"
    GENERAL = "general"


class PreferenceSource(str, Enum):
    EXPLICIT = "explicit"
    BEHAVIORAL = "behavioral"
    TEMPORARY = "temporary"
    INFERRED = "inferred"
    CORRECTION = "correction"


class PreferenceStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    DELETED = "deleted"


class FeedbackType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    CORRECTION = "correction"
    PREFERENCE = "preference"
    ACCEPTED_RECOMMENDATION = "accepted_recommendation"
    REJECTED_RECOMMENDATION = "rejected_recommendation"
    EDITED_RESULT = "edited_result"
    CONFIRMED_RESULT = "confirmed_result"
    REPORTED_ERROR = "reported_error"


class LearningTaskType(str, Enum):
    CLASSIFICATION = "classification"
    SUBCATEGORIZATION = "subcategorization"
    SEGMENTATION = "segmentation"
    HUMAN_PARSING = "human_parsing"
    COMPONENT_DETECTION = "component_detection"
    FABRIC_ESTIMATION = "fabric_estimation"
    COLOR_PATTERN = "color_pattern"
    SILHOUETTE_PREDICTION = "silhouette_prediction"
    RECONSTRUCTION = "reconstruction"
    AVATAR_FITTING = "avatar_fitting"
    RECOMMENDATION_RANKING = "recommendation_ranking"
    PREFERENCE_PREDICTION = "preference_prediction"
    RESPONSE_QUALITY = "response_quality"


class ValidationStatus(str, Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"
    QUARANTINED = "quarantined"


class ConsentScope(str, Enum):
    PERSONALIZATION_ONLY = "personalization_only"
    GLOBAL_MODEL_TRAINING = "global_model_training"
    RESEARCH_INTERNAL = "research_internal"


class ModelStatus(str, Enum):
    CANDIDATE = "candidate"
    TRAINING = "training"
    EVALUATION = "evaluation"
    APPROVED = "approved"
    DEPLOYED = "deployed"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class TrainingJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================================
# Request & Response Schemas
# ============================================================================

class CreateUserPreferenceRequest(BaseModel):
    category: PreferenceCategory
    key: str = Field(..., min_length=1, max_length=128)
    value: Any
    source: PreferenceSource = PreferenceSource.EXPLICIT
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    evidence_count: int = Field(default=1, ge=1)


class UpdateUserPreferenceRequest(BaseModel):
    value: Optional[Any] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    status: Optional[PreferenceStatus] = None


class UserPreferenceResponse(BaseModel):
    id: str
    user_id: str
    preference_category: str
    preference_key: str
    preference_value: Any
    source: str
    confidence: float
    evidence_count: int
    status: str
    last_confirmed_at: Optional[str] = None
    created_at: str
    updated_at: str


class CreateAIFeedbackRequest(BaseModel):
    feedback_type: FeedbackType
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    search_id: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    original_output: Optional[Dict[str, Any]] = None
    corrected_output: Optional[Dict[str, Any]] = None
    feedback_text: Optional[str] = Field(None, max_length=2000)
    metadata: Optional[Dict[str, Any]] = None


class AIFeedbackResponse(BaseModel):
    id: str
    user_id: str
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    search_id: Optional[str] = None
    feedback_type: str
    rating: Optional[int] = None
    original_output: Dict[str, Any]
    corrected_output: Dict[str, Any]
    feedback_text: Optional[str] = None
    metadata: Dict[str, Any]
    consent_snapshot: Dict[str, Any]
    created_at: str


class UpdateConsentRequest(BaseModel):
    personalization_enabled: Optional[bool] = None
    global_model_training_enabled: Optional[bool] = None
    image_training_enabled: Optional[bool] = None
    conversation_training_enabled: Optional[bool] = None
    consent_version: Optional[str] = "v1.0"


class ConsentResponse(BaseModel):
    id: str
    user_id: str
    personalization_enabled: bool
    global_model_training_enabled: bool
    image_training_enabled: bool
    conversation_training_enabled: bool
    consent_version: str
    consent_updated_at: str


class RegisterModelRequest(BaseModel):
    model_name: str
    model_version: str
    task_type: LearningTaskType
    artifact_uri: str
    artifact_checksum: str
    base_model: Optional[str] = None
    training_dataset_version: Optional[str] = None
    evaluation_metrics: Optional[Dict[str, Any]] = None
    status: ModelStatus = ModelStatus.CANDIDATE


class DeployModelRequest(BaseModel):
    model_name: str
    model_version: str


class RollbackModelRequest(BaseModel):
    task_type: str
    target_version: Optional[str] = None


class CreateTrainingJobRequest(BaseModel):
    model_name: str
    task_type: LearningTaskType
    dataset_version: str
    training_config: Optional[Dict[str, Any]] = None

