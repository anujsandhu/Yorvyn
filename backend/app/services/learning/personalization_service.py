"""
Personalization Service (Layer A — User Personalization Memory)
Manages structured, editable individual preferences with confidence scoring,
evidence counting, session context integration, and privacy isolation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.app.services.database.supabase_repository import SupabaseRepository, supabase_repo

logger = logging.getLogger(__name__)


class PersonalizationService:
    """Manages user-specific memory, preference updates, and context synthesis."""

    def __init__(self, repo: Optional[SupabaseRepository] = None):
        self.repo = repo or supabase_repo

    def get_user_preferences(
        self,
        user_id: str,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieves active preferences for a user."""
        return self.repo.get_user_preferences(user_id=user_id, category=category, status="active")

    def get_user_preference(self, user_id: str, pref_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a specific preference by ID."""
        return self.repo.get_user_preference(user_id=user_id, pref_id=pref_id)

    def upsert_user_preference(
        self,
        user_id: str,
        category: str,
        key: str,
        value: Any,
        source: str = "explicit",
        confidence: float = 0.8,
        evidence_count: int = 1
    ) -> Dict[str, Any]:
        """
        Upserts preference with evidence and confidence updates.
        Explicit inputs and user corrections set high baseline confidence.
        """
        return self.repo.upsert_user_preference(
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            source=source,
            confidence=confidence,
            evidence_count=evidence_count
        )

    def update_user_preference(
        self,
        user_id: str,
        pref_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Updates a preference value or status (e.g. user manual edit)."""
        return self.repo.update_user_preference(user_id=user_id, pref_id=pref_id, updates=updates)

    def delete_user_preference(self, user_id: str, pref_id: str) -> bool:
        """Deletes a preference record for the user."""
        return self.repo.delete_user_preference(user_id=user_id, pref_id=pref_id)

    def reset_user_preferences(self, user_id: str, category: Optional[str] = None) -> int:
        """Resets all or categorical preferences for the user."""
        return self.repo.reset_user_preferences(user_id=user_id, category=category)

    def export_user_learning_data(self, user_id: str) -> Dict[str, Any]:
        """Exports all learning data for the user."""
        return self.repo.export_user_learning_data(user_id=user_id)

    def record_user_feedback(self, feedback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Records feedback and automatically updates Layer A personalization memory
        if the feedback contains preferences, accepted/rejected styles, or corrections.
        """
        user_id = str(feedback_data["user_id"])
        fb_type = feedback_data.get("feedback_type")
        corrected_output = feedback_data.get("corrected_output") or {}
        metadata = feedback_data.get("metadata") or {}

        # 1. Persist feedback record
        feedback_record = self.repo.create_ai_feedback(
            user_id=user_id,
            feedback_type=fb_type,
            session_id=feedback_data.get("session_id"),
            message_id=feedback_data.get("message_id"),
            search_id=feedback_data.get("search_id"),
            rating=feedback_data.get("rating"),
            original_output=feedback_data.get("original_output"),
            corrected_output=corrected_output,
            feedback_text=feedback_data.get("feedback_text"),
            metadata=metadata
        )

        # 2. Check if user has personalization enabled
        consent = self.repo.get_learning_consent(user_id)
        if not consent.get("personalization_enabled", True):
            return feedback_record

        # 3. Derive Layer A Personalization Memory from feedback
        if fb_type == "correction" and corrected_output:
            # User corrected a garment attribute or style
            for key, val in corrected_output.items():
                cat = "fit" if "fit" in key else "colour" if "colour" in key or "color" in key else "style"
                self.upsert_user_preference(
                    user_id=user_id,
                    category=cat,
                    key=key,
                    value=val,
                    source="correction",
                    confidence=0.95,
                    evidence_count=1
                )

        elif fb_type == "preference":
            # Direct preference expressed
            pref_cat = metadata.get("preference_category", "general")
            pref_key = metadata.get("preference_key", "preferred_style")
            pref_val = metadata.get("preference_value", feedback_data.get("feedback_text"))
            if pref_val:
                self.upsert_user_preference(
                    user_id=user_id,
                    category=pref_cat,
                    key=pref_key,
                    value=pref_val,
                    source="explicit",
                    confidence=0.90,
                    evidence_count=1
                )

        elif fb_type in ("accepted_recommendation", "positive"):
            # Behavioral reinforcement
            outfit_data = metadata.get("outfit") or {}
            styles = outfit_data.get("style_tags") or metadata.get("styles", [])
            for st in styles:
                self.upsert_user_preference(
                    user_id=user_id,
                    category="style",
                    key=str(st).lower(),
                    value=True,
                    source="behavioral",
                    confidence=0.60,
                    evidence_count=1
                )

        elif fb_type in ("rejected_recommendation", "negative"):
            # Behavioral avoidance
            disliked = metadata.get("disliked_style") or metadata.get("style")
            if disliked:
                self.upsert_user_preference(
                    user_id=user_id,
                    category="style",
                    key=f"dislike_{str(disliked).lower()}",
                    value=False,
                    source="behavioral",
                    confidence=0.65,
                    evidence_count=1
                )

        return feedback_record

    def build_personalized_context(
        self,
        user_id: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dynamically builds the personalization context for LLM prompt synthesis.
        Guarantees:
        - If personalization is disabled in user consent, returns empty dictionary.
        - User A's preferences are completely isolated from User B.
        - In-session context is merged from session_id if available.
        """
        uid = str(user_id)
        consent = self.repo.get_learning_consent(uid)

        # Respect consent toggle
        if not consent.get("personalization_enabled", True):
            return {
                "personalization_enabled": False,
                "preferences_applied": 0,
                "fit_preferences": [],
                "colour_preferences": [],
                "style_preferences": [],
                "disliked_styles": [],
                "brand_preferences": [],
                "confidence": {}
            }

        # Gather preferences
        prefs = self.repo.get_user_preferences(uid, status="active")

        fit_prefs: List[str] = []
        colour_prefs: List[str] = []
        style_prefs: List[str] = []
        disliked_styles: List[str] = []
        brand_prefs: List[str] = []
        confidence_map: Dict[str, float] = {}

        for p in prefs:
            cat = p.get("preference_category")
            key = p.get("preference_key")
            val = p.get("preference_value")
            conf = float(p.get("confidence", 0.5))

            # Only include preferences with sufficient confidence (>= 0.40)
            if conf < 0.40:
                continue

            confidence_map[key] = conf

            if cat == "fit":
                fit_prefs.append(str(val if isinstance(val, (str, int, float)) else key))
            elif cat == "colour":
                colour_prefs.append(str(val if isinstance(val, (str, int, float)) else key))
            elif cat == "brand":
                brand_prefs.append(str(val if isinstance(val, (str, int, float)) else key))
            elif cat == "style":
                if str(key).startswith("dislike_") or val is False:
                    disliked_styles.append(str(key).replace("dislike_", ""))
                else:
                    style_prefs.append(str(val if isinstance(val, (str, int, float)) else key))

        # Retrieve in-session context if session_id is provided
        session_context = None
        if session_id:
            sess = self.repo.get_ai_session(session_id, user_id=uid)
            if sess and sess.get("context_summary"):
                session_context = sess.get("context_summary")

        return {
            "personalization_enabled": True,
            "preferences_applied": len(prefs),
            "fit_preferences": sorted(list(set(fit_prefs))),
            "colour_preferences": sorted(list(set(colour_prefs))),
            "style_preferences": sorted(list(set(style_prefs))),
            "disliked_styles": sorted(list(set(disliked_styles))),
            "brand_preferences": sorted(list(set(brand_prefs))),
            "confidence": confidence_map,
            "session_context": session_context
        }


# Global singleton
personalization_service = PersonalizationService()

