"""Adapters that pass verified canonical garment evidence to legacy mesh builders."""

from __future__ import annotations

from typing import Any, Optional

from backend.app.services.ai.base import EvidenceStatus
from backend.app.services.ai.contracts import CanonicalGarmentSpecificationV2
from backend.app.models.garment_intelligence_models import GarmentComponentV2


def apply_observed_components(
    intelligence: Optional[Any],
    specification: Optional[CanonicalGarmentSpecificationV2],
) -> Optional[Any]:
    """Copy only explicitly OBSERVED, source-cited component presence into legacy intelligence.

    Inferred, unknown, conflicted, or uncited V2 evidence is deliberately not promoted
    into a hard mesh-construction decision.
    """
    if intelligence is None or specification is None:
        return intelligence

    integrity_errors = specification.validate_evidence_integrity()
    if integrity_errors:
        raise ValueError("Cannot adapt invalid V2 evidence: " + "; ".join(integrity_errors))

    components = list(getattr(intelligence, "components", []) or [])
    applied = []
    for name, component in specification.v2_components.items():
        presence = component.presence
        if presence.status != EvidenceStatus.OBSERVED or not presence.source_image_ids:
            continue
        if not isinstance(presence.value, bool):
            continue
        component_type = component.name or name
        components = [
            existing for existing in components
            if getattr(existing, "component_type", None) != component_type
            and getattr(existing, "name", None) != component_type
        ]
        components.append(GarmentComponentV2(
            name=component_type,
            component_type=component_type,
            bbox=None,
            confidence=presence.confidence if presence.confidence is not None else 0.0,
            status="detected" if presence.value else "not_detected",
            provenance="observed",
            attributes={
                "evidence_source_image_ids": list(presence.source_image_ids),
                "evidence_provider": presence.source_provider,
                "evidence_adapter": "canonical_v2_observed_presence",
            },
        ))
        applied.append(component_type)

    try:
        adapted = intelligence.model_copy(deep=True)
    except AttributeError:
        adapted = intelligence.copy(deep=True)
    adapted.components = components
    adapted.model_provenance = dict(getattr(adapted, "model_provenance", {}) or {})
    adapted.model_provenance["canonical_v2_observed_components"] = ",".join(sorted(applied))
    return adapted
