"""
Model E: Personal Preference Learning Engine.
Learns preferences from likes, dislikes, outfit selections, and repeated wear patterns.
Calibrates preference weights without mistaking transient clicks for genuine affinity.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FeedbackSignal(BaseModel):
    user_id: str
    target_id: str
    interaction_type: str = Field(
        ...,
        description="liked, saved, worn, rejected, viewed, clicked"
    )
    attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted attributes: colors, brand, aesthetic, category, fit"
    )
    weight: float = Field(1.0)


class PreferenceLearningService:
    """Model E: Personal preference model learning from positive and negative feedback."""

    # Interaction weight matrix
    INTERACTION_WEIGHTS: Dict[str, float] = {
        "liked": 0.25,
        "saved": 0.30,
        "worn": 0.15,
        "rejected": -0.50,
        "disliked": -0.50,
        "clicked": 0.02,   # Very low weight; does not assume affinity from a click
        "viewed": 0.01
    }

    def __init__(self):
        # Maps user_id -> attribute_type -> attribute_value -> calibrated_weight
        self._user_weights: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )

    def record_interaction(
        self,
        user_id: str,
        interaction_type: str,
        item_or_outfit_data: Dict[str, Any]
    ) -> float:
        """
        Updates preference weights for the user based on item attributes.
        Returns the delta weight applied.
        """
        user_id_str = str(user_id)
        delta = self.INTERACTION_WEIGHTS.get(interaction_type.lower(), 0.05)

        # Extract attributes
        colors = [item_or_outfit_data.get("color")] if item_or_outfit_data.get("color") else item_or_outfit_data.get("colors", [])
        brand = item_or_outfit_data.get("brand")
        fit = item_or_outfit_data.get("fit") or item_or_outfit_data.get("fit_preference")
        aesthetics = item_or_outfit_data.get("aesthetic") or item_or_outfit_data.get("aesthetics", [])

        # Update colors
        for c in colors:
            if c:
                self._user_weights[user_id_str]["color"][c.lower()] += delta

        # Update brand
        if brand:
            self._user_weights[user_id_str]["brand"][brand.lower()] += delta

        # Update fit
        if fit:
            self._user_weights[user_id_str]["fit"][fit.lower()] += delta

        # Update aesthetics
        if isinstance(aesthetics, list):
            for a in aesthetics:
                self._user_weights[user_id_str]["aesthetic"][a.lower()] += delta
        elif isinstance(aesthetics, str):
            self._user_weights[user_id_str]["aesthetic"][aesthetics.lower()] += delta

        return delta

    def score_item_affinity(self, user_id: str, item_data: Dict[str, Any]) -> float:
        """
        Computes personal affinity score (0.0 to 100.0) for an item based on learned weights.
        Baseline is neutral (80.0), boosted by positive interactions and penalized by negative feedback.
        """
        user_id_str = str(user_id)
        user_model = self._user_weights.get(user_id_str)
        if not user_model:
            return 82.0  # Neutral high baseline for new items

        score = 80.0

        # Color affinity
        col = (item_data.get("color") or "").lower()
        if col in user_model.get("color", {}):
            score += user_model["color"][col] * 20.0

        # Brand affinity
        brand = (item_data.get("brand") or "").lower()
        if brand in user_model.get("brand", {}):
            score += user_model["brand"][brand] * 15.0

        # Fit affinity
        fit = (item_data.get("fit") or "").lower()
        if fit in user_model.get("fit", {}):
            score += user_model["fit"][fit] * 15.0

        # Clamp between 20.0 and 100.0
        return float(min(100.0, max(20.0, round(score, 1))))


# Global singleton
preference_learning_service = PreferenceLearningService()

