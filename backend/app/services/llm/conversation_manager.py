"""
Conversation & Multi-turn Session Manager for Yorvyn LLM Architecture.
Maintains session state, distinguishes temporary constraints from persistent Fashion DNA,
and enforces tenant isolation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import defaultdict

from backend.app.services.llm.base import LLMMessage
from backend.app.services.llm.context_builder import context_builder

logger = logging.getLogger(__name__)


class ConversationSession:
    """In-memory active conversation session for an authenticated user."""

    def __init__(self, conversation_id: str, user_id: str):
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.messages: List[LLMMessage] = []
        self.temporary_context: Dict[str, Any] = {}
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()

    def add_message(self, message: LLMMessage) -> None:
        self.messages.append(message)
        self.updated_at = datetime.utcnow().isoformat()

    def set_temporary_constraint(self, key: str, value: Any) -> None:
        """Sets an ephemeral styling constraint valid only for this session."""
        self.temporary_context[key] = value

    def clear_temporary_constraints(self) -> None:
        self.temporary_context.clear()


class ConversationManager:
    """Manages conversational multi-turn sessions per user."""

    def __init__(self):
        # Maps (user_id, conversation_id) -> ConversationSession
        self._sessions: Dict[str, Dict[str, ConversationSession]] = defaultdict(dict)

    def get_or_create_session(
        self,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> ConversationSession:
        """Retrieves an existing session or initializes a fresh isolated session."""
        user_id_str = str(user_id)
        cid = conversation_id or str(uuid.uuid4())[:8]

        if cid not in self._sessions[user_id_str]:
            session = ConversationSession(conversation_id=cid, user_id=user_id_str)
            # Initialize with system message grounded in user Fashion DNA
            initial_msgs = context_builder.build_initial_messages(user_id_str)
            session.messages.extend(initial_msgs)
            self._sessions[user_id_str][cid] = session

        return self._sessions[user_id_str][cid]

    def add_user_message(
        self,
        user_id: str,
        conversation_id: str,
        content: str
    ) -> ConversationSession:
        """Appends a user message to the session."""
        session = self.get_or_create_session(user_id, conversation_id)
        session.add_message(LLMMessage(role="user", content=content))
        return session

    def add_assistant_message(
        self,
        user_id: str,
        conversation_id: str,
        content: str,
        tool_calls: Optional[List[Any]] = None
    ) -> ConversationSession:
        """Appends an assistant message to the session."""
        session = self.get_or_create_session(user_id, conversation_id)
        session.add_message(LLMMessage(role="assistant", content=content, tool_calls=tool_calls))
        return session

    def add_tool_response(
        self,
        user_id: str,
        conversation_id: str,
        tool_call_id: str,
        tool_name: str,
        content: str
    ) -> ConversationSession:
        """Appends a tool execution output to the session."""
        session = self.get_or_create_session(user_id, conversation_id)
        session.add_message(LLMMessage(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            name=tool_name
        ))
        return session

    def get_messages(self, user_id: str, conversation_id: str, max_turns: int = 20) -> List[LLMMessage]:
        """Returns message sequence, preserving system prompt plus the most recent turns."""
        session = self.get_or_create_session(user_id, conversation_id)
        if len(session.messages) <= max_turns:
            return session.messages

        # Keep system message at index 0, take last (max_turns - 1)
        system_msg = [session.messages[0]] if session.messages and session.messages[0].role == "system" else []
        recent_msgs = session.messages[-(max_turns - 1):]
        return system_msg + recent_msgs


# Global singleton
conversation_manager = ConversationManager()

