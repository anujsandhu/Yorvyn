"""
YORVYN — AI Provider Fallback & Failure Manager (Phase 14.26)
Executes capability-aware graceful degradation and circuit breaker routing:
- Vision Fallback: Gemini Vision -> Local CV -> Validated Partial Result
- Reasoning Fallback: Groq Reasoning -> Local Rule-based Normalizer
- Embeddings Fallback: Local HuggingFace (DINOv2) -> FashionCLIP
- Preserves explicit failure status without fabricating data
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional
from backend.app.services.ai.base import (
    AIProvider,
    AIRequest,
    AIProviderResponse,
    ProviderError,
    ModelMetadata,
    TaskType
)
from backend.app.services.ai.orchestration.capability_resolver import CapabilityResolver

logger = logging.getLogger(__name__)


class FallbackManager:
    """Manages ordered provider fallback chains when primary providers fail."""

    def __init__(self, providers: Dict[str, AIProvider]):
        self.providers = providers

    def get_fallback_chain(self, task_type: TaskType, request: AIRequest) -> List[AIProvider]:
        """Returns ordered sequence of fallback providers matching task capabilities."""
        eligible = CapabilityResolver.filter_eligible_providers(self.providers, request)

        if task_type == TaskType.GARMENT_IMAGE_UNDERSTANDING:
            # Preferred order: Gemini Vision (if available) -> Local CV
            chain = []
            gemini = self.providers.get("gemini_vision")
            local = self.providers.get("local_cv")

            if gemini and gemini in eligible:
                chain.append(gemini)
            if local and local in eligible:
                chain.append(local)
            return chain

        elif task_type in [TaskType.ATTRIBUTE_NORMALIZATION, TaskType.TAXONOMY_MAPPING, TaskType.CONFLICT_RESOLUTION]:
            # Preferred order: Groq Reasoning (if available) -> Local Rules Normalizer
            chain = []
            groq = self.providers.get("groq_reasoning")
            rules = self.providers.get("local_rules")
            if groq and groq in eligible:
                chain.append(groq)
            if rules and rules in eligible:
                chain.append(rules)
            return chain

        elif task_type == TaskType.VISUAL_EMBEDDINGS:
            # Preferred order: HuggingFace DINOv2 -> Local CV
            chain = []
            hf = self.providers.get("huggingface")
            local = self.providers.get("local_cv")
            if hf and hf in eligible:
                chain.append(hf)
            if local and local in eligible:
                chain.append(local)
            return chain

        return eligible

    def execute_with_fallback(self, request: AIRequest) -> AIProviderResponse:
        """Executes request along ordered fallback chain until success or exhaustion."""
        chain = self.get_fallback_chain(request.task_type, request)

        if not chain:
            return AIProviderResponse(
                request_id=request.request_id,
                provider_name="none",
                model_metadata=ModelMetadata(provider_name="none", model_name="none"),
                task_type=request.task_type,
                success=False,
                error=ProviderError(
                    provider_name="fallback_manager",
                    error_code="NO_CAPABLE_PROVIDERS",
                    message=f"No capable or available providers found for task '{request.task_type.value}'.",
                    is_retryable=False
                )
            )

        errors: List[ProviderError] = []

        for provider in chain:
            # Skip if circuit is currently open and not in mock mode
            if not request.mock_mode and not provider.is_available():
                logger.info(f"Skipping provider {provider.name}: not available or circuit open.")
                continue

            try:
                response = provider.execute(request)
                if response.success:
                    if errors:
                        response.provenance_notes.append(
                            f"Resolved via fallback to '{provider.name}' after errors: {[e.error_code for e in errors]}"
                        )
                    return response
                else:
                    if response.error:
                        errors.append(response.error)
            except Exception as e:
                logger.warning(f"Provider {provider.name} raised {type(e).__name__}")
                errors.append(ProviderError(
                    provider_name=provider.name,
                    error_code="EXECUTION_EXCEPTION",
                    message=type(e).__name__,
                    is_retryable=False
                ))

        # All providers in chain failed
        return AIProviderResponse(
            request_id=request.request_id,
            provider_name="exhausted",
            model_metadata=ModelMetadata(provider_name="exhausted", model_name="exhausted"),
            task_type=request.task_type,
            success=False,
            error=ProviderError(
                provider_name="fallback_manager",
                error_code="ALL_PROVIDERS_FAILED",
                message=f"All candidate providers failed: {[e.message for e in errors]}",
                is_retryable=False
            )
        )
