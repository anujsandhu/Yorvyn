"""
YORVYN Intelligence Platform (YIP) — Privacy-Preserving Personalization Engine (Phase 17.0 Stage 7).

Coordinates existing PersonalizationService (Layer A preferences) and PreferenceLearningService
to score and explain personalized garment/outfit suggestions with:
- Strict owner isolation (zero cross-user leakage)
- Explicit consent checks before learning behavioral signals
- Read-only protection for saved body measurements (never mutated implicitly)
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.app.services.learning.personalization_service import personalization_service
from backend.app.services.ml.preference_learning import preference_learning_service
from backend.app.services.wardrobe_service import WardrobeService


class PersonalizedGarmentSuggestion(BaseModel):
    item_id: str
    name: str
    category: str
    color: str
    affinity_score: float
    rationale: List[str] = Field(default_factory=list)


class PersonalizationRecommendationResponse(BaseModel):
    user_id: str
    consent_personalization_active: bool
    body_measurements_protected: bool = True
    preferred_categories: List[str] = Field(default_factory=list)
    preferred_colors: List[str] = Field(default_factory=list)
    preferred_fits: List[str] = Field(default_factory=list)
    suggestions: List[PersonalizedGarmentSuggestion] = Field(default_factory=list)
    privacy_note: str = "Recommendations are strictly scoped to owner user_id with explicit consent controls."
    latency_ms: float = 0.0


class YIPPersonalizationEngine:
    """Owner-isolated fashion & fit personalization coordinator."""

    def __init__(self) -> None:
        self._wardrobe = WardrobeService()

    def record_consented_signal(
        self,
        *,
        user_id: str,
        interaction_type: str,
        item_data: Dict[str, Any],
        consent_granted: bool,
    ) -> Dict[str, Any]:
        from backend.app.services.intelligence.recommendation_profile import recommendation_profile_store

        if not consent_granted:
            recommendation_profile_store.set_consent(user_id, False)
            return {"recorded": False, "reason": "Explicit personalization consent not granted."}
        recommendation_profile_store.set_consent(user_id, True)
        res = recommendation_profile_store.record_interaction(
            owner_id=user_id,
            interaction_type=interaction_type,
            item_data=item_data,
            consent_granted=consent_granted,
        )
        return {
            "recorded": bool(res.get("recorded")),
            "user_id": user_id,
            "delta_applied": res.get("treated_as_positive_preference", False),
            "details": res,
        }

    def recommend_for_user(
        self,
        *,
        user_id: str,
        wardrobe_items: Optional[List[Dict[str, Any]]] = None,
        consent_granted: bool = True,
        occasion: Optional[str] = None,
        top_k: int = 6,
    ) -> PersonalizationRecommendationResponse:
        from backend.app.services.intelligence.recommendation_engine import fashion_recommendation_engine
        from backend.app.services.intelligence.recommendation_profile import recommendation_profile_store

        t0 = time.perf_counter()
        if not consent_granted:
            return PersonalizationRecommendationResponse(
                user_id=user_id,
                consent_personalization_active=False,
                suggestions=[],
                privacy_note="Personalization disabled by user consent preference.",
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            )

        rec_resp = fashion_recommendation_engine.recommend(
            owner_id=user_id,
            candidates=wardrobe_items,
            mode="hybrid",
            surface="wardrobe",
            occasion=occasion,
            top_k=top_k,
            consent_granted=consent_granted,
        )
        profile = recommendation_profile_store.get_profile(user_id)
        pref_cats = set(profile.explicit_preferences.get("category", [])) | set(
            k for k, v in profile.category_affinity.items() if v > 0.2
        )
        pref_colors = set(profile.explicit_preferences.get("color", [])) | set(
            list((profile.inferred_preferences.get("color") or {}).keys())[:4]
        )
        pref_fits = set(profile.explicit_preferences.get("fit", [])) | set(
            list((profile.inferred_preferences.get("fit") or {}).keys())[:3]
        )

        # Preserve Layer A preference visibility alongside hybrid ranking scores
        suggestions: List[PersonalizedGarmentSuggestion] = []
        for it in rec_resp.recommendations:
            base = round(float(it.final_score) * 100.0, 1)
            reasons = [r.message for r in it.reasons] or ["Balanced wardrobe staple baseline"]
            suggestions.append(PersonalizedGarmentSuggestion(
                item_id=it.item_id,
                name=it.name,
                category=it.category,
                color=it.color,
                affinity_score=base,
                rationale=reasons,
            ))

        return PersonalizationRecommendationResponse(
            user_id=user_id,
            consent_personalization_active=True,
            preferred_categories=sorted(pref_cats),
            preferred_colors=sorted(pref_colors),
            preferred_fits=sorted(pref_fits),
            suggestions=suggestions,
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )


personalization_engine = YIPPersonalizationEngine()
