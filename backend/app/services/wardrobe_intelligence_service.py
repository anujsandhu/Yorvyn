"""
Yorvyn Wardrobe Intelligence Engine.
Computes wardrobe compatibility matrices, co-wear relationships, color harmony across owned items,
utilization analytics, and gap detection (missing versatile layers, missing footwear, or category imbalances).
Operates exclusively on real recorded wardrobe items.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict

from backend.app.domain.fashion_knowledge import (
    COLOR_PALETTES,
    SEASONAL_COLOR_PALETTES,
    evaluate_color_harmony,
)
from backend.app.services.wardrobe_service import WardrobeService, DEFAULT_WARDROBE_ITEMS

logger = logging.getLogger(__name__)

COLOR_HARMONY_COMPLEMENTARY = {
    ("navy", "camel"), ("camel", "navy"),
    ("olive", "burgundy"), ("burgundy", "olive"),
    ("charcoal", "cream"), ("cream", "charcoal"),
    ("blue", "orange"), ("orange", "blue"),
    ("black", "white"), ("white", "black")
}

COLOR_HARMONY_ANALOGOUS = {
    ("navy", "charcoal"), ("charcoal", "navy"),
    ("olive", "forest_green"), ("forest_green", "olive"),
    ("cream", "camel"), ("camel", "cream"),
    ("beige", "tan"), ("tan", "beige")
}

# Valid item categories and pairing affinities
CATEGORY_PAIRING_AFFINITY: Dict[str, List[str]] = {
    "top": ["bottom", "outerwear", "footwear", "accessory"],
    "bottom": ["top", "footwear", "outerwear", "accessory"],
    "outerwear": ["top", "bottom", "footwear", "accessory"],
    "footwear": ["top", "bottom", "outerwear"],
    "accessory": ["top", "bottom", "outerwear"]
}

ESSENTIAL_CATEGORIES = ["top", "bottom", "footwear", "outerwear"]


class WardrobeIntelligenceService:
    """Intelligent graph-based analysis of user digital wardrobe inventory."""

    def __init__(self, wardrobe_svc: Optional[WardrobeService] = None):
        self.wardrobe_svc = wardrobe_svc or WardrobeService()

    def get_wardrobe_summary(self, user_id: str) -> Dict[str, Any]:
        """Returns structured inventory summary and category counts."""
        items = self.wardrobe_svc.get_wardrobe(user_id)
        category_counts: Dict[str, int] = defaultdict(int)
        color_counts: Dict[str, int] = defaultdict(int)
        favorite_count = 0
        worn_items = 0
        total_wears = 0

        for item in items:
            cat = item.get("category", "other").lower()
            category_counts[cat] += 1
            col = item.get("color", "unknown").lower()
            color_counts[col] += 1
            if item.get("favorite"):
                favorite_count += 1
            wears = item.get("wear_count", 0)
            if wears > 0:
                worn_items += 1
                total_wears += wears

        total_items = len(items)
        utilization_rate = round(worn_items / total_items, 2) if total_items > 0 else 0.0

        return {
            "total_items": total_items,
            "category_breakdown": dict(category_counts),
            "dominant_colors": dict(sorted(color_counts.items(), key=lambda x: x[1], reverse=True)[:5]),
            "favorite_count": favorite_count,
            "utilization_rate": utilization_rate,
            "total_recorded_wears": total_wears
        }

    def evaluate_item_pairing_compatibility(self, item_a: Dict[str, Any], item_b: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates deterministic compatibility between two specific wardrobe items:
        checks category harmony, color compatibility, formality congruence, and pattern mixing.
        """
        cat_a = item_a.get("category", "").lower()
        cat_b = item_b.get("category", "").lower()

        # Cannot pair two items of the same primary category (e.g. two bottoms) unless subcategory layering permits
        if cat_a == cat_b and cat_a not in ["accessory", "outerwear"]:
            return {
                "compatibility_score": 0.0,
                "is_compatible": False,
                "reason": f"Cannot pair two primary {cat_a} items together in a standard outfit.",
                "color_harmony": 0.0,
                "formality_delta": abs(item_a.get("formality", 5) - item_b.get("formality", 5))
            }

        # 1. Color Harmony
        col_a = item_a.get("color", "black").lower()
        col_b = item_b.get("color", "black").lower()
        color_score = 0.8
        if col_a == col_b:
            color_score = 0.95  # Monochromatic / matching
        elif (col_a, col_b) in COLOR_HARMONY_COMPLEMENTARY or (col_b, col_a) in COLOR_HARMONY_COMPLEMENTARY:
            color_score = 1.0  # Complementary
        elif (col_a, col_b) in COLOR_HARMONY_ANALOGOUS or (col_b, col_a) in COLOR_HARMONY_ANALOGOUS:
            color_score = 0.9  # Analogous
        elif col_a in ["black", "white", "grey", "charcoal", "navy", "cream", "beige"] or \
             col_b in ["black", "white", "grey", "charcoal", "navy", "cream", "beige"]:
            color_score = 0.85  # Neutral anchor pairing

        # 2. Formality Congruence (1-10 scale)
        form_a = item_a.get("formality", 5)
        form_b = item_b.get("formality", 5)
        form_delta = abs(form_a - form_b)
        # Delta 0-2: great match (1.0), 3-4: acceptable (0.75), 5+: stylistic clash (0.4)
        if form_delta <= 2:
            formality_score = 1.0
        elif form_delta <= 4:
            formality_score = 0.75
        else:
            formality_score = 0.4

        # 3. Pattern Mixing Rules
        pat_a = item_a.get("pattern", "solid").lower()
        pat_b = item_b.get("pattern", "solid").lower()
        pattern_score = 1.0
        if pat_a != "solid" and pat_b != "solid":
            # Two clashing patterns (e.g. stripes + plaid)
            pattern_score = 0.5 if pat_a == pat_b else 0.35

        # Composite score
        composite = round(0.40 * color_score + 0.35 * formality_score + 0.25 * pattern_score, 2)
        is_compatible = composite >= 0.65

        return {
            "compatibility_score": composite,
            "is_compatible": is_compatible,
            "color_score": color_score,
            "formality_score": formality_score,
            "pattern_score": pattern_score,
            "reason": "Harmonious pairing" if is_compatible else "Style or formality dissonance detected."
        }

    def find_matching_items(
        self,
        user_id: str,
        target_item_id: str,
        target_category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Finds items in user wardrobe that pair harmoniously with target item."""
        items = self.wardrobe_svc.get_wardrobe(user_id)
        target = next((i for i in items if i.get("id") == target_item_id), None)
        if not target:
            return []

        results = []
        for other in items:
            if other.get("id") == target_item_id:
                continue
            if target_category and other.get("category") != target_category:
                continue

            evaluation = self.evaluate_item_pairing_compatibility(target, other)
            if evaluation["is_compatible"]:
                results.append({
                    "item": other,
                    "compatibility_score": evaluation["compatibility_score"],
                    "reason": evaluation["reason"]
                })

        # Sort highest compatibility first
        results.sort(key=lambda x: x["compatibility_score"], reverse=True)
        return results

    def analyze_wardrobe_gaps(self, user_id: str) -> Dict[str, Any]:
        """
        Analyzes the user's wardrobe for missing essentials, color variety gaps,
        or layering deficits without fabricating products.
        """
        items = self.wardrobe_svc.get_wardrobe(user_id)
        categories_present = {i.get("category", "").lower() for i in items}
        missing_essentials = [cat for cat in ESSENTIAL_CATEGORIES if cat not in categories_present]

        # Analyze color distribution
        colors = {i.get("color", "").lower() for i in items}
        has_neutral_anchor = bool(colors.intersection({"black", "white", "navy", "charcoal", "grey", "cream"}))

        # Check formality range
        formalities = [i.get("formality", 5) for i in items]
        max_formality = max(formalities) if formalities else 5
        min_formality = min(formalities) if formalities else 5

        gaps = []
        if missing_essentials:
            for m in missing_essentials:
                gaps.append({
                    "type": "missing_category",
                    "severity": "high",
                    "category": m,
                    "description": f"No {m} garments found in your wardrobe. Adding a versatile {m} would unlock multiple outfit combinations."
                })

        if not has_neutral_anchor and len(items) > 0:
            gaps.append({
                "type": "color_anchor_gap",
                "severity": "medium",
                "category": "palette",
                "description": "Your wardrobe lacks neutral anchor pieces (such as navy, charcoal, or off-white) to ground bold statements."
            })

        if max_formality < 7 and len(items) >= 4:
            gaps.append({
                "type": "formality_gap",
                "severity": "low",
                "category": "formalwear",
                "description": "Your collection is heavily relaxed. A structured blazer or formal trouser would improve smart-formal versatility."
            })

        return {
            "total_items": len(items),
            "missing_essential_categories": missing_essentials,
            "identified_gaps": gaps,
            "has_complete_capsule": len(missing_essentials) == 0 and len(items) >= 4
        }


# Global singleton
wardrobe_intelligence_service = WardrobeIntelligenceService()
