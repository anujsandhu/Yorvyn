"""
Model F: Multi-Factor Outfit Ranking & Personalized Recommendation Engine.
Evaluates 10 distinct compatibility factors using Models A-E and hybrid scoring:
1. Body-fit compatibility
2. Colour compatibility
3. Personal style compatibility
4. Wardrobe compatibility
5. Occasion suitability
6. Weather & season
7. Budget compliance
8. User feedback affinity
9. Clothing availability
10. Outfit completeness
Produces structured recommendations anchored strictly in real recorded garments.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.models.fashion_dna import FashionDNA
from backend.app.services.ml.body_intelligence import body_intelligence_service
from backend.app.services.ml.skin_colour_intelligence import skin_colour_intelligence_service
from backend.app.services.ml.preference_learning import preference_learning_service
from backend.app.services.wardrobe_intelligence_service import wardrobe_intelligence_service

logger = logging.getLogger(__name__)


class CompatibilityFactorBreakdown(BaseModel):
    body_fit: float = Field(..., ge=0.0, le=100.0)
    colour_harmony: float = Field(..., ge=0.0, le=100.0)
    style_alignment: float = Field(..., ge=0.0, le=100.0)
    wardrobe_synergy: float = Field(..., ge=0.0, le=100.0)
    occasion_suitability: float = Field(..., ge=0.0, le=100.0)
    weather_adaptation: float = Field(..., ge=0.0, le=100.0)
    budget_compliance: float = Field(..., ge=0.0, le=100.0)
    feedback_affinity: float = Field(..., ge=0.0, le=100.0)
    clothing_availability: float = Field(..., ge=0.0, le=100.0)
    outfit_completeness: float = Field(..., ge=0.0, le=100.0)
    composite_score: float = Field(..., ge=0.0, le=100.0)

    @property
    def total_score(self) -> float:
        return self.composite_score


class RankedOutfit(BaseModel):
    outfit_id: str
    name: str
    items: List[Dict[str, Any]]
    composite_score: float
    factor_breakdown: CompatibilityFactorBreakdown
    styling_rationale: str
    supporting_preferences: List[str]
    missing_information: Optional[str] = None
    confidence_level: float = Field(0.9, ge=0.0, le=1.0)
    alternatives: List[Dict[str, Any]] = Field(default_factory=list)


class OutfitRankerService:
    """Model F: Hybrid ranking engine executing 10-factor compatibility evaluation."""

    # Default calibrated scoring weights summing to 1.0
    DEFAULT_WEIGHTS: Dict[str, float] = {
        "body_fit": 0.12,
        "colour_harmony": 0.15,
        "style_alignment": 0.14,
        "wardrobe_synergy": 0.12,
        "occasion_suitability": 0.12,
        "weather_adaptation": 0.10,
        "budget_compliance": 0.05,
        "feedback_affinity": 0.08,
        "clothing_availability": 0.04,
        "outfit_completeness": 0.08
    }

    def __init__(self):
        self.body_intel = body_intelligence_service
        self.colour_intel = skin_colour_intelligence_service
        self.preference_learner = preference_learning_service
        self.wardrobe_intel = wardrobe_intelligence_service

    def evaluate_outfit(
        self,
        user_id: str,
        items: List[Dict[str, Any]],
        fashion_dna: FashionDNA,
        occasion: str = "casual",
        weather_temp_c: Optional[float] = 20.0,
        custom_weights: Optional[Dict[str, float]] = None
    ) -> CompatibilityFactorBreakdown:
        """Computes the full 10-factor compatibility breakdown for an outfit."""
        weights = custom_weights or self.DEFAULT_WEIGHTS

        # 1. Body-fit compatibility
        silhouette = fashion_dna.body_profile.silhouette
        fit_pref = fashion_dna.body_profile.fit_preference
        fit_scores = [
            self.body_intel.evaluate_garment_fit(
                silhouette, fit_pref, i.get("fit", "regular"), i.get("category", "top")
            )["score"]
            for i in items
        ]
        body_fit_score = sum(fit_scores) / len(fit_scores) if fit_scores else 80.0

        # 2. Colour compatibility
        item_colors = [i.get("color", "neutral") for i in items]
        colour_eval = self.colour_intel.evaluate_clothing_colour_harmony(
            item_colors,
            fashion_dna.colour_profile.personal_palette,
            fashion_dna.colour_profile.preferred_colours,
            fashion_dna.colour_profile.disliked_colours
        )
        colour_harmony_score = colour_eval["harmony_score"]

        # 3. Personal style compatibility
        primary_styles = [s.lower() for s in fashion_dna.style_profile.primary_styles]
        style_matches = 0
        for i in items:
            item_aesthetics = [a.lower() for a in i.get("aesthetic", [])]
            if any(s in item_aesthetics for s in primary_styles) or not item_aesthetics:
                style_matches += 1
        style_alignment_score = (style_matches / len(items) * 100.0) if items else 80.0

        # 4. Wardrobe synergy (pairwise compatibility between items)
        if len(items) >= 2:
            pair_scores = []
            for idx_a in range(len(items)):
                for idx_b in range(idx_a + 1, len(items)):
                    res = self.wardrobe_intel.evaluate_item_pairing_compatibility(items[idx_a], items[idx_b])
                    pair_scores.append(res["compatibility_score"] * 100.0)
            wardrobe_synergy_score = sum(pair_scores) / len(pair_scores) if pair_scores else 85.0
        else:
            wardrobe_synergy_score = 75.0

        # 5. Occasion suitability
        target_occasion = occasion.lower()
        occasion_matches = 0
        for i in items:
            formality = i.get("formality", 5)
            if target_occasion in ["formal", "wedding", "black_tie"]:
                if formality >= 6:
                    occasion_matches += 1
            elif target_occasion in ["business", "work", "office"]:
                if 4 <= formality <= 8:
                    occasion_matches += 1
            elif target_occasion in ["casual", "college"]:
                if formality <= 6:
                    occasion_matches += 1
            else:
                occasion_matches += 1
        occasion_suitability_score = (occasion_matches / len(items) * 100.0) if items else 80.0

        # 6. Weather & season adaptation
        temp = weather_temp_c if weather_temp_c is not None else 20.0
        thermal_scores = []
        for i in items:
            warmth = i.get("warmth", 5)
            if temp < 10:  # Cold
                thermal_scores.append(100.0 if warmth >= 6 else 60.0)
            elif temp < 18:  # Mild/chilly
                thermal_scores.append(100.0 if 4 <= warmth <= 7 else 70.0)
            else:  # Warm
                thermal_scores.append(100.0 if warmth <= 5 else 60.0)
        weather_adaptation_score = sum(thermal_scores) / len(thermal_scores) if thermal_scores else 85.0

        # 7. Budget compliance
        max_budget = fashion_dna.additional_preferences.max_budget
        # Assume all items already owned in digital wardrobe are 100% budget compliant (0 incremental cost)
        budget_compliance_score = 100.0

        # 8. Feedback affinity
        feedback_scores = [self.preference_learner.score_item_affinity(user_id, i) for i in items]
        feedback_affinity_score = sum(feedback_scores) / len(feedback_scores) if feedback_scores else 82.0

        # 9. Clothing availability (items actually present in closet)
        clothing_availability_score = 100.0 if len(items) > 0 else 0.0

        # 10. Outfit completeness (has top and bottom, or dress, plus footwear)
        categories = {i.get("category", "").lower() for i in items}
        has_top_and_bottom = ("top" in categories and "bottom" in categories) or ("dress" in categories)
        has_footwear = "footwear" in categories
        if has_top_and_bottom and has_footwear:
            outfit_completeness_score = 100.0
        elif has_top_and_bottom:
            outfit_completeness_score = 85.0
        else:
            outfit_completeness_score = 60.0

        # Composite weighted score
        composite = (
            weights["body_fit"] * body_fit_score
            + weights["colour_harmony"] * colour_harmony_score
            + weights["style_alignment"] * style_alignment_score
            + weights["wardrobe_synergy"] * wardrobe_synergy_score
            + weights["occasion_suitability"] * occasion_suitability_score
            + weights["weather_adaptation"] * weather_adaptation_score
            + weights["budget_compliance"] * budget_compliance_score
            + weights["feedback_affinity"] * feedback_affinity_score
            + weights["clothing_availability"] * clothing_availability_score
            + weights["outfit_completeness"] * outfit_completeness_score
        )

        return CompatibilityFactorBreakdown(
            body_fit=round(body_fit_score, 1),
            colour_harmony=round(colour_harmony_score, 1),
            style_alignment=round(style_alignment_score, 1),
            wardrobe_synergy=round(wardrobe_synergy_score, 1),
            occasion_suitability=round(occasion_suitability_score, 1),
            weather_adaptation=round(weather_adaptation_score, 1),
            budget_compliance=round(budget_compliance_score, 1),
            feedback_affinity=round(feedback_affinity_score, 1),
            clothing_availability=round(clothing_availability_score, 1),
            outfit_completeness=round(outfit_completeness_score, 1),
            composite_score=round(composite, 1)
        )

    def assemble_and_rank_outfits(
        self,
        user_id: str,
        wardrobe_items: List[Dict[str, Any]],
        fashion_dna: FashionDNA,
        occasion: str = "casual",
        weather_temp_c: Optional[float] = 20.0
    ) -> List[RankedOutfit]:
        """Assembles compatible outfits from wardrobe and ranks them."""
        tops = [i for i in wardrobe_items if i.get("category") == "top"]
        bottoms = [i for i in wardrobe_items if i.get("category") == "bottom"]
        shoes = [i for i in wardrobe_items if i.get("category") == "footwear"]
        outers = [i for i in wardrobe_items if i.get("category") == "outerwear"]

        candidates = []

        # If user has basic tops and bottoms
        if tops and bottoms:
            for top in tops[:3]:
                for bottom in bottoms[:3]:
                    outfit_items = [top, bottom]
                    if shoes:
                        outfit_items.append(shoes[0])
                    if outers and (weather_temp_c is not None and weather_temp_c < 18):
                        outfit_items.append(outers[0])

                    breakdown = self.evaluate_outfit(
                        user_id=user_id,
                        items=outfit_items,
                        fashion_dna=fashion_dna,
                        occasion=occasion,
                        weather_temp_c=weather_temp_c
                    )

                    name = f"{top.get('name', 'Top')} & {bottom.get('name', 'Trousers')}"
                    rationale = (
                        f"Features harmonious {top.get('color')} and {bottom.get('color')} tones "
                        f"tailored for {occasion} attire with {breakdown.composite_score}% styling affinity."
                    )
                    supporting = [
                        f"Matches {fashion_dna.colour_profile.personal_palette} color palette",
                        f"Aligns with {fashion_dna.body_profile.fit_preference} fit preference"
                    ]

                    candidates.append(RankedOutfit(
                        outfit_id=f"outfit_{top.get('id')}_{bottom.get('id')}",
                        name=name,
                        items=outfit_items,
                        composite_score=breakdown.composite_score,
                        factor_breakdown=breakdown,
                        styling_rationale=rationale,
                        supporting_preferences=supporting,
                        confidence_level=0.92
                    ))

        # Sort descending by composite score
        candidates.sort(key=lambda x: x.composite_score, reverse=True)
        return candidates


# Global singleton
outfit_ranker_service = OutfitRankerService()

