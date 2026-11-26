"""
YORVYN — AI Provider Capability Resolver (Phase 14.26)
Resolves appropriate AI providers for tasks based on explicit capabilities:
- Enforces strict capability matching
- Guarantees binary images are NEVER routed to text-only models
- Filters available and non-tripped (circuit closed) providers
"""

from __future__ import annotations

from typing import Dict, List, Optional
from backend.app.services.ai.base import (
    AIProvider,
    AIRequest,
    ProviderCapability,
    TaskType
)


class CapabilityResolver:
    """Matches task requirements against verified provider capabilities."""

    @staticmethod
    def get_required_capabilities(task_type: TaskType, request: AIRequest) -> List[ProviderCapability]:
        """Determines required capabilities for a given request."""
        caps: List[ProviderCapability] = []

        if task_type == TaskType.GARMENT_IMAGE_UNDERSTANDING:
            caps.append(ProviderCapability.VISION_MULTIMODAL)
            caps.append(ProviderCapability.STRUCTURED_JSON)

        elif task_type in [TaskType.ATTRIBUTE_NORMALIZATION, TaskType.TAXONOMY_MAPPING, TaskType.CONFLICT_RESOLUTION]:
            caps.append(ProviderCapability.TEXT_REASONING)
            caps.append(ProviderCapability.STRUCTURED_JSON)

        elif task_type == TaskType.VISUAL_EMBEDDINGS:
            caps.append(ProviderCapability.EMBEDDINGS)

        elif task_type == TaskType.LOCAL_SEGMENTATION:
            caps.append(ProviderCapability.COMPONENT_SEGMENTATION)
            caps.append(ProviderCapability.OFFLINE_LOCAL)

        # If binary image is included in request, provider MUST support vision
        if request.image_bytes is not None or request.image_path is not None:
            if ProviderCapability.VISION_MULTIMODAL not in caps:
                caps.append(ProviderCapability.VISION_MULTIMODAL)

        return caps

    @classmethod
    def filter_eligible_providers(
        cls,
        providers: Dict[str, AIProvider],
        request: AIRequest
    ) -> List[AIProvider]:
        """Returns list of providers capable of executing request."""
        required_caps = cls.get_required_capabilities(request.task_type, request)
        eligible: List[AIProvider] = []

        for p in providers.values():
            provider_caps = p.capabilities()
            # Must possess all required capabilities
            has_all_caps = all(rc in provider_caps for rc in required_caps)
            if not has_all_caps:
                continue

            # Must not send image to text-only provider
            if (request.image_bytes or request.image_path) and ProviderCapability.VISION_MULTIMODAL not in provider_caps:
                continue

            eligible.append(p)

        return eligible
