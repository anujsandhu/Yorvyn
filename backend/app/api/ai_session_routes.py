"""
FastAPI Routes for Yorvyn Persistent AI Sessions, Messages, and Search History.
Implements ChatGPT-style conversation persistence, multi-tenant isolation via Supabase JWT,
cursor-based pagination, session archiving/deletion, and idempotent message processing.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.app.core.security import get_current_user, UserContext
from backend.app.services.database.supabase_repository import supabase_repo
from backend.app.services.llm.persistent_session_service import persistent_session_service
from backend.app.models.ai_session_models import (
    CreateSessionRequest,
    UpdateSessionRequest,
    SessionResponse,
    SessionListResponse,
    SendMessageRequest,
    SendMessageResult,
    MessageResponse,
    MessageListResponse,
    SearchRecordResponse,
    SearchListResponse,
    AISessionStatus
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["AI Persistent Sessions & Searches"])


# ── Correlation Helper ────────────────────────────────────────────────────────

def _get_correlation_id(request: Request) -> str:
    return request.headers.get("X-Correlation-ID") or f"req_{uuid.uuid4().hex[:10]}"


# ── Session Lifecycle Endpoints ───────────────────────────────────────────────

@router.post("/sessions", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def create_session(
    req: CreateSessionRequest,
    request: Request,
    current_user: UserContext = Depends(get_current_user)
):
    """
    Creates a new persistent conversation session with a permanent UUID.
    Strictly owned by the authenticated Supabase user.
    """
    corr_id = _get_correlation_id(request)
    logger.info(f"[{corr_id}] Creating AI session for user={current_user.user_id}")

    session_record = supabase_repo.create_ai_session(
        user_id=current_user.user_id,
        title=req.title or "New conversation",
        session_type=req.session_type.value,
        metadata=req.metadata or {},
        description=req.description
    )

    return {
        "success": True,
        "session": session_record
    }


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    request: Request,
    status: Optional[str] = Query("active", description="Session status filter: active, archived, or all"),
    session_type: Optional[str] = Query(None, description="Optional session type filter"),
    search: Optional[str] = Query(None, description="Search filter by session title"),
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None, description="Pagination cursor (session ID)"),
    current_user: UserContext = Depends(get_current_user)
):
    """
    Lists conversation sessions for the authenticated user with cursor pagination.
    Ordered by last_message_at DESC (fallback created_at DESC).
    """
    filter_status = None if status == "all" else status
    items, next_cursor = supabase_repo.list_ai_sessions(
        user_id=current_user.user_id,
        status=filter_status,
        session_type=session_type,
        search=search,
        limit=limit,
        cursor=cursor
    )

    return SessionListResponse(
        items=[SessionResponse(**item) for item in items],
        next_cursor=next_cursor,
        total=len(items)
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    request: Request,
    current_user: UserContext = Depends(get_current_user)
):
    """
    Retrieves full session metadata for an authenticated user.
    Rejects unauthorized or cross-tenant access with HTTP 404.
    """
    session = supabase_repo.get_ai_session(session_id, user_id=current_user.user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session '{session_id}' not found."
        )

    return SessionResponse(**session)


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: str,
    req: UpdateSessionRequest,
    request: Request,
    current_user: UserContext = Depends(get_current_user)
):
    """
    Renames a session or updates description/metadata with server-side validation.
    """
    updates = req.dict(exclude_unset=True)
    if not updates:
        session = supabase_repo.get_ai_session(session_id, user_id=current_user.user_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
        return SessionResponse(**session)

    updated = supabase_repo.update_ai_session(session_id, current_user.user_id, updates)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session '{session_id}' not found or access denied."
        )

    return SessionResponse(**updated)


@router.post("/sessions/{session_id}/archive", response_model=SessionResponse)
def archive_session(
    session_id: str,
    request: Request,
    current_user: UserContext = Depends(get_current_user)
):
    """
    Archives a conversation session.
    """
    archived = supabase_repo.archive_ai_session(session_id, current_user.user_id)
    if not archived:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session '{session_id}' not found or access denied."
        )
    return SessionResponse(**archived)


@router.post("/sessions/{session_id}/restore", response_model=SessionResponse)
def restore_session(
    session_id: str,
    request: Request,
    current_user: UserContext = Depends(get_current_user)
):
    """
    Restores an archived session to active status.
    """
    restored = supabase_repo.restore_ai_session(session_id, current_user.user_id)
    if not restored:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session '{session_id}' not found or access denied."
        )
    return SessionResponse(**restored)


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    request: Request,
    current_user: UserContext = Depends(get_current_user)
):
    """
    Applies soft-deletion to an AI session. Unrelated wardrobe assets,
    reconstruction jobs, and avatars are preserved.
    """
    success = supabase_repo.delete_ai_session(session_id, current_user.user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session '{session_id}' not found or access denied."
        )
    return {
        "success": True,
        "message": f"Session '{session_id}' deleted successfully."
    }


# ── Message Endpoints ─────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
def get_session_messages(
    session_id: str,
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    cursor: Optional[str] = Query(None, description="Pagination cursor (message ID)"),
    current_user: UserContext = Depends(get_current_user)
):
    """
    Loads messages for an active session in deterministic chronological sequence.
    Verifies user ownership of the session.
    """
    session = supabase_repo.get_ai_session(session_id, user_id=current_user.user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session '{session_id}' not found or access denied."
        )

    messages, next_cursor = supabase_repo.get_ai_session_messages(
        session_id=session_id,
        user_id=current_user.user_id,
        limit=limit,
        cursor=cursor
    )

    return MessageListResponse(
        items=[MessageResponse(**m) for m in messages],
        next_cursor=next_cursor
    )


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResult)
def send_session_message(
    session_id: str,
    req: SendMessageRequest,
    request: Request,
    current_user: UserContext = Depends(get_current_user)
):
    """
    Sends a user prompt to a persistent session and executes conversational AI reasoning.
    1. Verifies session ownership.
    2. Enforces idempotency via client request_id.
    3. Persists user message.
    4. Tracks searches where applicable.
    5. Returns unified AI response with outfits, tool calls, and provenance.
    """
    corr_id = _get_correlation_id(request)
    session = supabase_repo.get_ai_session(session_id, user_id=current_user.user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session '{session_id}' not found or access denied."
        )

    if session.get("status") == AISessionStatus.ARCHIVED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot post messages to an archived session. Please restore it first."
        )

    logger.info(
        f"[{corr_id}] Message received for session={session_id} user={current_user.user_id} req_id={req.request_id}"
    )

    try:
        result = persistent_session_service.post_message_and_execute(
            session_id=session_id,
            user_id=current_user.user_id,
            content=req.content,
            content_type=req.content_type.value,
            attachments=req.attachments,
            request_id=req.request_id,
            metadata=req.metadata
        )
        return SendMessageResult(**result)
    except Exception as e:
        logger.error(f"[{corr_id}] Failed executing session message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Styling intelligence execution error: {str(e)}"
        )


# ── Search Provenance & History Endpoints ─────────────────────────────────────

@router.get("/sessions/{session_id}/searches", response_model=SearchListResponse)
def get_session_searches(
    session_id: str,
    request: Request,
    search_type: Optional[str] = Query(None, description="Optional search type filter"),
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    current_user: UserContext = Depends(get_current_user)
):
    """
    Retrieves all search operations executed within a specific session.
    """
    session = supabase_repo.get_ai_session(session_id, user_id=current_user.user_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session '{session_id}' not found or access denied."
        )

    searches, next_cursor = supabase_repo.get_session_searches(
        session_id=session_id,
        user_id=current_user.user_id,
        search_type=search_type,
        limit=limit,
        cursor=cursor
    )

    return SearchListResponse(
        items=[SearchRecordResponse(**s) for s in searches],
        next_cursor=next_cursor
    )


@router.get("/searches", response_model=SearchListResponse)
def list_global_searches(
    request: Request,
    q: Optional[str] = Query(None, description="Text filter for search query"),
    search_type: Optional[str] = Query(None, description="Search category filter"),
    status: Optional[str] = Query(None, description="Search status filter: pending, completed, failed"),
    start_date: Optional[str] = Query(None, description="ISO start date filter"),
    end_date: Optional[str] = Query(None, description="ISO end date filter"),
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    current_user: UserContext = Depends(get_current_user)
):
    """
    Global search history across all conversations belonging exclusively to the authenticated user.
    """
    searches, next_cursor = supabase_repo.list_global_searches(
        user_id=current_user.user_id,
        query=q,
        search_type=search_type,
        status=status,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        cursor=cursor
    )

    return SearchListResponse(
        items=[SearchRecordResponse(**s) for s in searches],
        next_cursor=next_cursor
    )
