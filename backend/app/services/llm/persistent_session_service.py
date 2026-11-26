"""
Persistent AI Session Orchestrator and Context Manager.
Provides ChatGPT-style multi-turn context retention, token-budget-aware history management,
automatic long-conversation summarization, search provenance tracking, and idempotent message processing.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from backend.app.services.database.supabase_repository import supabase_repo
from backend.app.services.llm.context_builder import context_builder
from backend.app.services.llm.service import intelligence_service
from backend.app.models.ai_session_models import (
    AISearchType,
    AISearchStatus,
    AIMessageRole,
    AIMessageContentType
)

logger = logging.getLogger(__name__)


class PersistentSessionService:
    """Coordinates persistent conversational sessions, context assembly, and search history."""

    SUMMARIZE_THRESHOLD: int = 10  # Messages before triggering summarization
    RECENT_TURNS_BUDGET: int = 8   # Recent messages preserved verbatim in prompt

    def __init__(self, repo=None, intel_svc=None):
        self.repo = repo or supabase_repo
        self.intel_svc = intel_svc or intelligence_service

    def detect_search_intent(self, text: str) -> Tuple[bool, str]:
        """
        Determines whether a user message triggers a search operation and infers its search type.
        Returns: (is_search, search_type)
        """
        lower = text.lower().strip()
        search_indicators = [
            (r"\b(find|search|look for|recommend|suggest|show me)\b.*\b(outfit|look|wear|style|ensemble)s?\b", AISearchType.OUTFIT),
            (r"\b(find|search|where can i buy|shop|buy|price|brand|store)s?\b", AISearchType.PRODUCT),
            (r"\b(garment|reconstruct|3d|mesh|hoodie|jacket|pants|trousers|shirt|t-shirt|sweater|dress|skirt|coat|boot|shoe|footwear)s?\b", AISearchType.GARMENT),
            (r"\b(wardrobe|closet|my clothes|what do i have)\b", AISearchType.WARDROBE),
            (r"\b(match|pair with|combine|goes with)\b", AISearchType.STYLIST),
            (r"\b(find|search|look for|show me|recommend|suggest)\b", AISearchType.GENERAL),
        ]

        for pattern, stype in search_indicators:
            if re.search(pattern, lower):
                return True, stype.value

        return False, AISearchType.GENERAL.value

    def assemble_session_prompt_context(
        self,
        session_id: str,
        user_id: str,
        temporary_constraints: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """
        Builds grounded, token-budget-aware message sequence for the LLM:
        1. Base system prompt (Fashion DNA + Wardrobe inventory).
        2. Injected context summary (if long conversation was summarized).
        3. Most recent $N$ conversational turns from the database.
        """
        # 1. Base system message
        initial_msgs = context_builder.build_initial_messages(
            user_id=user_id,
            temporary_context=temporary_constraints
        )
        system_content = initial_msgs[0].content if initial_msgs else "You are Yorvyn Fashion Intelligence."

        # 2. Check for existing context summary on session
        session = self.repo.get_ai_session(session_id, user_id=user_id)
        if session and session.get("context_summary"):
            system_content += f"\n\n### Prior Conversation Context Summary:\n{session['context_summary']}"

        # 3. Inject Learned User Personalization Memory (Layer A)
        try:
            from backend.app.services.learning.personalization_service import personalization_service
            p_ctx = personalization_service.build_personalized_context(user_id=user_id, session_id=session_id)
            if p_ctx.get("personalization_enabled") and p_ctx.get("preferences_applied", 0) > 0:
                p_lines = []
                if p_ctx.get("fit_preferences"):
                    p_lines.append(f"- Preferred Fit: {', '.join(p_ctx['fit_preferences'])}")
                if p_ctx.get("colour_preferences"):
                    p_lines.append(f"- Preferred Colours: {', '.join(p_ctx['colour_preferences'])}")
                if p_ctx.get("style_preferences"):
                    p_lines.append(f"- Preferred Styles: {', '.join(p_ctx['style_preferences'])}")
                if p_ctx.get("disliked_styles"):
                    p_lines.append(f"- Disliked Styles: {', '.join(p_ctx['disliked_styles'])}")
                if p_lines:
                    system_content += f"\n\n### Learned User Style Personalization Memory:\n" + "\n".join(p_lines)
        except Exception as e:
            logger.debug(f"Personalization context injection notice: {e}")

        prompt_messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_content}
        ]

        # 4. Retrieve historical messages from persistent DB
        history, _ = self.repo.get_ai_session_messages(session_id, user_id=user_id, limit=50)

        # Filter out system messages and grab last RECENT_TURNS_BUDGET
        chat_turns = [m for m in history if m.get("role") in ("user", "assistant")]
        recent_turns = chat_turns[-self.RECENT_TURNS_BUDGET:]

        for m in recent_turns:
            prompt_messages.append({
                "role": m.get("role", "user"),
                "content": m.get("content", "")
            })

        return prompt_messages

    def summarize_conversation_if_needed(self, session_id: str, user_id: str) -> Optional[str]:
        """
        Evaluates message history length and generates an incremental context summary
        preserving important garment entities, styling constraints, and user preferences.
        """
        session = self.repo.get_ai_session(session_id, user_id=user_id)
        if not session:
            return None

        history, _ = self.repo.get_ai_session_messages(session_id, user_id=user_id, limit=100)
        chat_turns = [m for m in history if m.get("role") in ("user", "assistant")]

        if len(chat_turns) < self.SUMMARIZE_THRESHOLD:
            return session.get("context_summary")

        # Compile older turns to summarize (all except the most recent RECENT_TURNS_BUDGET)
        turns_to_summarize = chat_turns[:-self.RECENT_TURNS_BUDGET]
        if not turns_to_summarize:
            return session.get("context_summary")

        # Structured deterministic summarizer: extracts garments, styles, user constraints
        garments_mentioned = set()
        styling_goals = []
        user_queries = []

        for m in turns_to_summarize:
            content = m.get("content", "")
            if m.get("role") == "user":
                user_queries.append(content[:80])
                for term in ("hoodie", "t-shirt", "trousers", "jacket", "coat", "sneakers", "boots", "dress", "jeans"):
                    if term in content.lower():
                        garments_mentioned.add(term)
            elif m.get("role") == "assistant":
                metadata = m.get("metadata", {})
                if "outfits" in metadata:
                    for o in metadata.get("outfits", []):
                        if isinstance(o, dict) and o.get("name"):
                            styling_goals.append(o["name"])

        summary_lines = []
        if session.get("context_summary"):
            summary_lines.append(f"Previous points: {session['context_summary']}")
        if garments_mentioned:
            summary_lines.append(f"Garments referenced: {', '.join(sorted(garments_mentioned))}.")
        if user_queries:
            summary_lines.append(f"Recent topics explored: {'; '.join(user_queries[-3:])}.")
        if styling_goals:
            summary_lines.append(f"Ensembles suggested: {', '.join(styling_goals[-2:])}.")

        summary_text = " ".join(summary_lines)
        if not summary_text:
            summary_text = f"Discussion covering {len(turns_to_summarize)} styling exchanges."

        # Persist summary on session
        self.repo.update_ai_session(session_id, user_id, {"context_summary": summary_text})
        self.repo.record_session_event(
            session_id=session_id,
            user_id=user_id,
            event_type="context_summarized",
            event_data={"summarized_messages_count": len(turns_to_summarize), "summary_preview": summary_text[:120]}
        )

        logger.info(f"[AISession] Summarized session {session_id} ({len(turns_to_summarize)} messages)")
        return summary_text

    def post_message_and_execute(
        self,
        session_id: str,
        user_id: str,
        content: str,
        content_type: str = "text",
        attachments: Optional[List[Dict[str, Any]]] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates full persistent message turn:
        1. Checks idempotency.
        2. Validates session ownership.
        3. Persists user message.
        4. Detects and tracks search operation.
        5. Calls intelligence orchestrator with persistent context.
        6. Persists assistant response & search results.
        7. Triggers summarization if threshold exceeded.
        """
        # 1. Idempotency Check
        if request_id:
            existing_user_msg = self.repo.get_message_by_request_id(user_id, request_id)
            if existing_user_msg:
                # Find matching assistant reply for this user message
                history, _ = self.repo.get_ai_session_messages(session_id, user_id, limit=50)
                assistant_msg = None
                for idx, m in enumerate(history):
                    if m.get("id") == existing_user_msg.get("id") and idx + 1 < len(history):
                        assistant_msg = history[idx + 1]
                        break

                return {
                    "success": True,
                    "session_id": session_id,
                    "user_message_id": existing_user_msg["id"],
                    "assistant_message_id": assistant_msg["id"] if assistant_msg else str(uuid.uuid4()),
                    "search_id": None,
                    "response": {
                        "content": assistant_msg.get("content", "") if assistant_msg else "",
                        "outfits": assistant_msg.get("metadata", {}).get("outfits", []) if assistant_msg else [],
                        "idempotent_replay": True
                    }
                }

        # 2. Verify Session
        session = self.repo.get_ai_session(session_id, user_id=user_id)
        if not session:
            raise ValueError(f"Session {session_id} not found or does not belong to user {user_id}")

        # Auto-title generation if this is the first message and title is default
        if session.get("message_count", 0) == 0 and session.get("title") in ("New conversation", "New Conversation"):
            clean_title = content.strip().capitalize()
            if len(clean_title) > 36:
                clean_title = clean_title[:33] + "..."
            self.repo.update_ai_session(session_id, user_id, {"title": clean_title})

        # 3. Persist User Message
        user_message_record = self.repo.create_ai_message(
            session_id=session_id,
            user_id=user_id,
            role=AIMessageRole.USER.value,
            content=content,
            content_type=content_type,
            attachments=attachments or [],
            metadata=metadata or {},
            request_id=request_id,
            status="completed"
        )

        # 4. Search Intent Detection & Tracking
        is_search, search_type = self.detect_search_intent(content)
        search_record = None
        if is_search:
            search_record = self.repo.create_ai_search(
                session_id=session_id,
                user_id=user_id,
                search_type=search_type,
                query=content,
                message_id=user_message_record["id"],
                provider="yorvyn_hybrid_stylist"
            )

        # 5. Execute Conversation Turn via Intelligence Service
        # Pass conversation_id = session_id so LLM conversation manager maps directly to persistent session!
        start_time = time.time()
        intel_res = self.intel_svc.process_message(
            user_id=user_id,
            message=content,
            conversation_id=session_id,
            temporary_constraints=metadata.get("temporary_constraints") if metadata else None
        )
        duration_ms = int((time.time() - start_time) * 1000)

        response_text = intel_res.response_text or "I have reviewed your request and styled appropriate options."
        outfits = intel_res.outfits or []
        tools_executed = intel_res.tool_calls_executed or []
        anim_intent = intel_res.animation_intent

        # 6. Update Search Record if search was executed
        if search_record:
            summary = f"Generated {len(outfits)} outfit ensemble recommendations." if outfits else response_text[:140]
            self.repo.update_ai_search(
                search_id=search_record["id"],
                user_id=user_id,
                status=AISearchStatus.COMPLETED.value,
                result_summary=summary,
                result_metadata={
                    "outfits_count": len(outfits),
                    "outfit_names": [o.get("name") for o in outfits if isinstance(o, dict)],
                    "duration_ms": duration_ms
                }
            )

        # 7. Persist Assistant Response
        assistant_metadata = {
            "outfits": outfits,
            "tool_calls": tools_executed,
            "animation_intent": anim_intent,
            "provider_used": intel_res.provider_used,
            "search_id": search_record["id"] if search_record else None,
            "duration_ms": duration_ms
        }
        assistant_content_type = (
            AIMessageContentType.OUTFIT_RECOMMENDATION.value
            if outfits
            else AIMessageContentType.TEXT.value
        )

        assistant_message_record = self.repo.create_ai_message(
            session_id=session_id,
            user_id=user_id,
            role=AIMessageRole.ASSISTANT.value,
            content=response_text,
            content_type=assistant_content_type,
            attachments=attachments or [],
            metadata=assistant_metadata,
            parent_message_id=user_message_record["id"],
            status="completed"
        )

        # 8. Check for Automatic Long-Conversation Summarization
        self.summarize_conversation_if_needed(session_id, user_id)

        return {
            "success": True,
            "session_id": session_id,
            "user_message_id": user_message_record["id"],
            "assistant_message_id": assistant_message_record["id"],
            "search_id": search_record["id"] if search_record else None,
            "response": {
                "content": response_text,
                "outfits": outfits,
                "tool_calls": tools_executed,
                "animation_intent": anim_intent,
                "provider_used": intel_res.provider_used
            }
        }


# Global singleton
persistent_session_service = PersistentSessionService()
