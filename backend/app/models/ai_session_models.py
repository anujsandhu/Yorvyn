"""
Yorvyn AI Persistent Session, Message, and Search Data Models.
Defines Pydantic schemas, enums, validation constraints, and serialization structures.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Canonical Enums ───────────────────────────────────────────────────────────

class AISessionType(str, Enum):
    GENERAL = "general"
    FASHION_STYLIST = "fashion_stylist"
    GARMENT_RECONSTRUCTION = "garment_reconstruction"
    WARDROBE = "wardrobe"
    AVATAR = "avatar"
    SHOPPING = "shopping"
    OUTFIT_RECOMMENDATION = "outfit_recommendation"


class AISessionStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class AIMessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class AIMessageContentType(str, Enum):
    TEXT = "text"
    IMAGE_REFERENCE = "image_reference"
    OUTFIT_RECOMMENDATION = "outfit_recommendation"
    GARMENT_ANALYSIS = "garment_analysis"
    RECONSTRUCTION_RESULT = "reconstruction_result"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"


class AISearchType(str, Enum):
    GENERAL = "general"
    GARMENT = "garment"
    OUTFIT = "outfit"
    WARDROBE = "wardrobe"
    PRODUCT = "product"
    STYLIST = "stylist"
    IMAGE_ANALYSIS = "image_analysis"
    RECONSTRUCTION = "reconstruction"


class AISearchStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Session Schemas ───────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    title: Optional[str] = Field("New conversation", max_length=200)
    session_type: AISessionType = Field(default=AISessionType.GENERAL)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    description: Optional[str] = Field(None, max_length=1000)


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    metadata: Optional[Dict[str, Any]] = None


class SessionResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: Optional[str] = None
    session_type: str
    status: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    context_summary: Optional[str] = None
    message_count: int = 0
    search_count: int = 0
    last_message_at: Optional[str] = None
    created_at: str
    updated_at: str
    archived_at: Optional[str] = None


class SessionListResponse(BaseModel):
    items: List[SessionResponse]
    next_cursor: Optional[str] = None
    total: Optional[int] = None


# ── Message Schemas ───────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Text prompt or message content")
    content_type: AIMessageContentType = Field(default=AIMessageContentType.TEXT)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    request_id: Optional[str] = Field(None, max_length=128, description="Client idempotency key")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MessageResponse(BaseModel):
    id: str
    session_id: str
    user_id: str
    role: str
    content: str
    content_type: str = "text"
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = None
    parent_message_id: Optional[str] = None
    sequence_number: int = 1
    status: str = "completed"
    created_at: str
    updated_at: str


class MessageListResponse(BaseModel):
    items: List[MessageResponse]
    next_cursor: Optional[str] = None


# ── Search Record Schemas ─────────────────────────────────────────────────────

class SearchRecordResponse(BaseModel):
    id: str
    session_id: str
    user_id: str
    message_id: Optional[str] = None
    search_type: str
    query: str
    normalized_query: Optional[str] = None
    status: str
    result_summary: Optional[str] = None
    result_metadata: Dict[str, Any] = Field(default_factory=dict)
    provider: Optional[str] = None
    model_name: Optional[str] = None
    execution_provenance: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str


class SearchListResponse(BaseModel):
    items: List[SearchRecordResponse]
    next_cursor: Optional[str] = None


# ── Orchestrated Turn Response ────────────────────────────────────────────────

class SendMessageResult(BaseModel):
    success: bool = True
    session_id: str
    user_message_id: str
    assistant_message_id: str
    search_id: Optional[str] = None
    response: Dict[str, Any]

