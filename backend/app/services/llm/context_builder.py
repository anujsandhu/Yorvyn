"""
Context Builder for Yorvyn LLM Architecture.
Assembles tenant-isolated, grounded prompt context combining Fashion DNA, Wardrobe inventory,
and environmental conditions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.app.services.fashion_dna_service import fashion_dna_service
from backend.app.services.wardrobe_intelligence_service import wardrobe_intelligence_service
from backend.app.services.wardrobe_service import WardrobeService
from backend.app.services.llm.base import LLMMessage
from backend.app.services.llm.prompt_manager import prompt_manager

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Constructs prompt context and message history for an authenticated user."""

    def __init__(self, wardrobe_svc: Optional[WardrobeService] = None):
        self.dna_service = fashion_dna_service
        self.wardrobe_intel = wardrobe_intelligence_service
        self.wardrobe_svc = wardrobe_svc or WardrobeService()

    def build_initial_messages(
        self,
        user_id: str,
        temporary_context: Optional[Dict[str, Any]] = None,
        weather_context: Optional[Dict[str, Any]] = None
    ) -> List[LLMMessage]:
        """Builds system message with user Fashion DNA, wardrobe summary, and active constraints."""
        # 1. Retrieve Fashion DNA
        dna = self.dna_service.get_fashion_dna(user_id)
        dna_dict = dna.dict()

        # 2. Retrieve Wardrobe Summary
        wardrobe_summary = self.wardrobe_intel.get_wardrobe_summary(user_id)

        # 3. Compile System Prompt
        system_text = prompt_manager.get_system_prompt(
            fashion_dna=dna_dict,
            wardrobe_summary=wardrobe_summary,
            weather_context=weather_context,
            temporary_context=temporary_context
        )

        return [LLMMessage(role="system", content=system_text)]


# Global singleton
context_builder = ContextBuilder()

