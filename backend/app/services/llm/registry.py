"""
LLM Provider Registry for Yorvyn LLM Architecture.
Manages provider adapters, health checking, dynamic selection, and fallback resolution.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from backend.app.services.llm.base import LLMProvider
from backend.app.services.llm.providers.groq_provider import GroqProvider
from backend.app.services.llm.providers.gemini_provider import GeminiProvider
from backend.app.services.llm.providers.openrouter_provider import OpenRouterProvider
from backend.app.services.llm.providers.offline_rules_provider import OfflineRulesProvider

logger = logging.getLogger(__name__)


class LLMProviderRegistry:
    """Registry managing available LLM provider adapters."""

    def __init__(self):
        self._providers: Dict[str, LLMProvider] = {}
        # Register default adapters
        self.register(OfflineRulesProvider())
        self.register(GroqProvider())
        self.register(GeminiProvider())
        self.register(OpenRouterProvider())

    def register(self, provider: LLMProvider) -> None:
        """Registers a provider adapter instance."""
        name = provider.provider_name.lower()
        if name in self._providers:
            raise ValueError(f"Duplicate provider registration: {name}")
        self._providers[name] = provider

    def get_provider(self, name: str) -> Optional[LLMProvider]:
        """Retrieves provider by name."""
        return self._providers.get(name.lower())

    def resolve_provider(self, primary_preference: str = "groq", fallback_preference: str = "offline_rules") -> LLMProvider:
        """
        Resolves best available provider:
        Checks primary health, otherwise tries fallback, and always guarantees OfflineRulesProvider as ultimate safeguard.
        """
        primary = self.get_provider(primary_preference)
        if primary and primary.health_check():
            return primary

        fallback = self.get_provider(fallback_preference)
        if fallback and fallback.health_check():
            return fallback

        # Default guaranteed fallback
        return self._providers["offline_rules"]


# Global singleton
llm_registry = LLMProviderRegistry()

