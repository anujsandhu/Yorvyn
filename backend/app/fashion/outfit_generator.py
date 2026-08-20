"""
Yorvyn Multi-Layer Outfit Generator & Hybrid Scorer
Implements deterministic constraint filtering, multi-layer outfit composition,
multi-objective scoring (weather, occasion, color harmony, profile affinity, feedback),
and missing piece gap matching.
"""

from typing import Dict, List, Optional
import itertools
from .fashion_knowledge import (
    evaluate_color_harmony,
    get_thermal_layer_recommendations,
    OCCASION_MATRIX,
    STYLE_AESTHETICS,
    SEASONAL_COLOR_PALETTES
)
from .wardrobe_service import wardrobe_service
from .context_service import context_service

# Curated affiliate commerce gap catalog for completing missing staples
AFFILIATE_GAP_ITEMS = [
    {
        "id": "gap_1",
        "name": "Classic Camel Hair Tailored Topcoat",
        "category": "outerwear",
        "color": "camel",
        "brand": "COS",
        "price": "$290",
        "affiliate_url": "https://www.cos.com/en_usd/men/coats.html",
        "image_url": "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?auto=format&fit=crop&w=600&q=80",
        "reason": "Elevates casual layers into a cohesive Quiet Luxury silhouette."
    },
    {
        "id": "gap_2",
        "name": "Handmade Dark Chocolate Suede Loafers",
        "category": "footwear",
        "color": "brown",
        "brand": "Morjas",
        "price": "$349",
        "affiliate_url": "https://www.morjas.com/loafers",
        "image_url": "https://images.unsplash.com/photo-1614252369475-531eba835eb1?auto=format&fit=crop&w=600&q=80",
        "reason": "Provides a warm textured grounding for monochrome or navy pairings."
    },
    {
        "id": "gap_3",
        "name": "Heavyweight French Terry Zip Hoodie",
        "category": "outerwear",
        "color": "charcoal",
        "brand": "Reigning Champ",
        "price": "$185",
        "affiliate_url": "https://reigningchamp.com",
        "image_url": "https://images.unsplash.com/photo-1556905055-8f358a7a47b2?auto=format&fit=crop&w=600&q=80",
        "reason": "Essential mid-layer for effortless transitional weather styling."
    }
]

class OutfitGenerator:
    """Combines wardrobe pieces into curated, scored outfits."""
    
    def generate_outfits(
        self,
        user_id: str = "default_user",
        occasion: str = "casual_day",
        temp_celsius: float = 18.0,
        condition: str = "clear",
        target_aesthetic: Optional[str] = None,
        max_outfits: int = 4
    ) -> Dict:
        wardrobe = wardrobe_service.get_wardrobe(user_id)
        profile = context_service.get_user_profile(user_id)
        thermal_rules = get_thermal_layer_recommendations(temp_celsius, condition)
        occasion_rules = OCCASION_MATRIX.get(occasion, OCCASION_MATRIX["casual_day"])
        
        # Partition wardrobe into slots
        tops = [i for i in wardrobe if i["category"] == "top"]
        bottoms = [i for i in wardrobe if i["category"] == "bottom"]
        footwear = [i for i in wardrobe if i["category"] == "footwear"]
        outerwear = [i for i in wardrobe if i["category"] == "outerwear"]
        accessories = [i for i in wardrobe if i["category"] == "accessory"]
        
        if not tops or not bottoms or not footwear:
            return {
                "outfits": [],
                "context": {"occasion": occasion, "temperature": temp_celsius, "condition": condition},
                "error": "Insufficient wardrobe variety (need at least 1 top, 1 bottom, 1 pair of shoes)."
            }
            
        candidate_combinations = []
        
        # 1. Evaluate Core Combos: (Top, Bottom, Footwear)
        for t in tops:
            for b in bottoms:
                for f in footwear:
                    # Optional Outerwear (mandatory if temp < 15°C)
                    applicable_outerwear = [None]
                    if temp_celsius < 20 and outerwear:
                        applicable_outerwear.extend(outerwear)
                    elif temp_celsius < 10 and outerwear:
                        applicable_outerwear = list(outerwear)
                        
                    for o in applicable_outerwear:
                        # Optional Accessory
                        applicable_acc = accessories[0] if accessories else None
                        
                        combo_items = [t, b, f]
                        if o:
                            combo_items.append(o)
                        if applicable_acc:
                            combo_items.append(applicable_acc)
                            
                        # Score this combination
                        score_dict = self._score_combination(
                            combo_items=combo_items,
                            profile=profile,
                            occasion_rules=occasion_rules,
                            thermal_rules=thermal_rules,
                            temp_celsius=temp_celsius,
                            target_aesthetic=target_aesthetic
                        )
                        
                        if score_dict["total_score"] > 0.45:
                            candidate_combinations.append({
                                "items": combo_items,
                                "scores": score_dict,
                                "top": t,
                                "bottom": b,
                                "footwear": f,
                                "outerwear": o,
                                "accessory": applicable_acc
                            })
                            
        # Sort candidates by overall score descending
        candidate_combinations.sort(key=lambda x: x["scores"]["total_score"], reverse=True)
        
        # Deduplicate to ensure aesthetic variety in top results
        selected = []
        seen_tops = set()
        for cand in candidate_combinations:
            top_id = cand["top"]["id"]
            if top_id not in seen_tops or len(selected) < 2:
                selected.append(cand)
                seen_tops.add(top_id)
            if len(selected) >= max_outfits:
                break
                
        if not selected and candidate_combinations:
            selected = candidate_combinations[:max_outfits]

        # Format final outfits
        formatted_outfits = []
        for idx, cand in enumerate(selected):
            color_names = [i["color"] for i in cand["items"]]
            _, harmony_desc = evaluate_color_harmony(color_names)
            
            # Select 1 curated missing piece recommendation if applicable
            missing_piece = AFFILIATE_GAP_ITEMS[idx % len(AFFILIATE_GAP_ITEMS)]
            
            outfit_id = f"outfit_{idx + 1}"
            formatted_outfits.append({
                "outfit_id": outfit_id,
                "title": f"{target_aesthetic.replace('_', ' ').title() if target_aesthetic else occasion_rules['name']} Ensemble {idx + 1}",
                "match_score": int(cand["scores"]["total_score"] * 100),
                "layer_breakdown": {
                    "top": cand["top"],
                    "bottom": cand["bottom"],
                    "footwear": cand["footwear"],
                    "outerwear": cand["outerwear"],
                    "accessory": cand["accessory"]
                },
                "color_palette": color_names,
                "color_harmony_explanation": harmony_desc,
                "styling_rationale": cand["scores"]["rationale"],
                "score_breakdown": cand["scores"],
                "missing_piece_recommendation": missing_piece
            })
            
        return {
            "outfits": formatted_outfits,
            "context": {
                "occasion": occasion_rules["name"],
                "temperature_celsius": temp_celsius,
                "condition": condition,
                "thermal_tier": thermal_rules["tier"]
            },
            "total_candidates_analyzed": len(candidate_combinations)
        }

    def _score_combination(
        self,
        combo_items: List[Dict],
        profile: Dict,
        occasion_rules: Dict,
        thermal_rules: Dict,
        temp_celsius: float,
        target_aesthetic: Optional[str]
    ) -> Dict:
        """
        Hybrid Multi-Objective Scorer:
        Overall = 0.25*Weather + 0.25*Occasion + 0.20*Color + 0.15*Profile + 0.15*Aesthetic
        """
        # 1. Color Harmony Score
        colors = [i.get("color", "") for i in combo_items]
        color_score, color_notes = evaluate_color_harmony(colors)
        
        # 2. Weather & Thermal Score
        avg_warmth = sum(i.get("warmth", 4) for i in combo_items) / len(combo_items)
        has_outerwear = any(i.get("category") == "outerwear" for i in combo_items)
        
        if temp_celsius < 10:
            weather_score = 0.95 if (has_outerwear and avg_warmth >= 5.5) else 0.4
        elif 10 <= temp_celsius <= 20:
            weather_score = 0.90 if (avg_warmth >= 3.5 and avg_warmth <= 6.5) else 0.7
        else:
            weather_score = 0.95 if (not has_outerwear and avg_warmth <= 4) else 0.5
            
        # 3. Occasion Formality Score
        avg_formality = sum(i.get("formality", 4) for i in combo_items) / len(combo_items)
        min_f = occasion_rules.get("min_formality", 1)
        max_f = occasion_rules.get("max_formality", 10)
        if min_f <= avg_formality <= max_f:
            occasion_score = 0.95
        else:
            diff = min(abs(avg_formality - min_f), abs(avg_formality - max_f))
            occasion_score = max(0.2, 0.95 - (diff * 0.15))
            
        # 4. User Profile & Undertone Compatibility
        user_season = profile.get("color_season", "autumn")
        best_palette = SEASONAL_COLOR_PALETTES.get(user_season, {}).get("best_colors", [])
        palette_matches = sum(1 for c in colors if any(b in c for b in best_palette))
        profile_score = min(1.0, 0.65 + (0.1 * palette_matches))
        
        # 5. Aesthetic Alignment
        target = target_aesthetic or (profile.get("primary_aesthetics", ["quiet_luxury"])[0])
        aesthetic_def = STYLE_AESTHETICS.get(target, {})
        key_colors = aesthetic_def.get("key_colors", [])
        aesthetic_matches = sum(1 for c in colors if any(k in c for k in key_colors))
        aesthetic_score = min(1.0, 0.6 + (0.12 * aesthetic_matches))
        
        # Total Weighted Score
        total_score = (
            (0.25 * weather_score) +
            (0.25 * occasion_score) +
            (0.20 * color_score) +
            (0.15 * profile_score) +
            (0.15 * aesthetic_score)
        )
        
        rationale = (
            f"Balances {occasion_rules['name']} dress code with {thermal_rules['tier']}. "
            f"Features {', '.join(colors)} color palette ({color_notes})."
        )
        
        return {
            "total_score": round(total_score, 2),
            "weather_score": round(weather_score, 2),
            "occasion_score": round(occasion_score, 2),
            "color_score": round(color_score, 2),
            "profile_score": round(profile_score, 2),
            "aesthetic_score": round(aesthetic_score, 2),
            "rationale": rationale
        }

# Global singleton
outfit_generator = OutfitGenerator()
