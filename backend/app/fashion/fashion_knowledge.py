"""
Yorvyn Fashion Intelligence Core - Knowledge Base & Rules Engine
Implements Color Theory, Seasonal Palettes, Aesthetic Definitions,
Thermal / Weather Rules, and Occasion Dress Codes.
"""

from typing import Dict, List, Set, Tuple

# ---------------------------------------------------------
# 1. COLOR THEORY & HARMONY ENGINE
# ---------------------------------------------------------

COLOR_PALETTES = {
    "neutrals": {
        "black", "white", "grey", "gray", "charcoal", "cream", "beige",
        "tan", "khaki", "camel", "ivory", "off-white", "navy", "brown", "taupe"
    },
    "warm": {
        "red", "coral", "terracotta", "rust", "orange", "mustard", "yellow",
        "olive", "warm brown", "gold", "amber", "burgundy", "maroon"
    },
    "cool": {
        "blue", "sky blue", "cobalt", "royal blue", "teal", "emerald", "sage",
        "mint", "forest green", "lavender", "purple", "violet", "silver", "pink"
    }
}

# Established harmonious color pairings (Aesthetic & Classical Color Wheel Rules)
HARMONIOUS_PAIRS = {
    ("navy", "white"), ("navy", "beige"), ("navy", "camel"), ("navy", "grey"),
    ("navy", "tan"), ("navy", "burgundy"), ("navy", "sky blue"),
    ("black", "white"), ("black", "grey"), ("black", "camel"), ("black", "charcoal"),
    ("black", "cream"), ("black", "red"), ("black", "olive"), ("black", "silver"),
    ("white", "beige"), ("white", "tan"), ("white", "olive"), ("white", "blue"),
    ("white", "grey"), ("white", "denim"), ("white", "forest green"),
    ("beige", "cream"), ("beige", "brown"), ("beige", "olive"), ("beige", "sage"),
    ("camel", "cream"), ("camel", "black"), ("camel", "navy"), ("camel", "white"),
    ("grey", "pink"), ("grey", "burgundy"), ("grey", "navy"), ("grey", "sky blue"),
    ("olive", "cream"), ("olive", "black"), ("olive", "white"), ("olive", "tan"),
    ("sage", "cream"), ("sage", "white"), ("sage", "tan"), ("sage", "brown"),
    ("burgundy", "grey"), ("burgundy", "navy"), ("burgundy", "cream"), ("burgundy", "black"),
    ("terracotta", "cream"), ("terracotta", "denim"), ("terracotta", "white")
}

# Color Season mappings for skin undertones
SEASONAL_COLOR_PALETTES = {
    "spring": {
        "undertone": "warm-bright",
        "best_colors": ["coral", "peach", "warm yellow", "camel", "light navy", "cream", "sage", "gold"],
        "avoid": ["stark black", "icy grey", "dull brown"]
    },
    "summer": {
        "undertone": "cool-soft",
        "best_colors": ["lavender", "sky blue", "soft grey", "rose", "sage", "navy", "off-white"],
        "avoid": ["bright orange", "mustard", "heavy black"]
    },
    "autumn": {
        "undertone": "warm-deep",
        "best_colors": ["terracotta", "rust", "olive", "forest green", "mustard", "camel", "burgundy", "warm brown"],
        "avoid": ["pure stark white", "neon pink", "icy blue"]
    },
    "winter": {
        "undertone": "cool-bright",
        "best_colors": ["stark black", "pure white", "royal blue", "emerald", "burgundy", "charcoal", "silver", "ruby red"],
        "avoid": ["warm mustard", "dusty orange", "beige"]
    }
}

# ---------------------------------------------------------
# 2. AESTHETIC DEFINITIONS
# ---------------------------------------------------------

STYLE_AESTHETICS = {
    "quiet_luxury": {
        "name": "Quiet Luxury / Old Money",
        "key_colors": ["camel", "cream", "navy", "white", "charcoal", "beige", "olive"],
        "fabrics": ["cashmere", "wool", "silk", "linen", "structured cotton"],
        "silhouettes": ["tailored", "relaxed-tapered", "clean lines"],
        "forbidden_patterns": ["loud logo", "graphic print", "distressed denim"],
        "description": "Understated elegance, high-quality fabrication, monochromatic or muted neutral palette with pristine tailoring."
    },
    "minimalist_scandi": {
        "name": "Minimalist Scandinavian",
        "key_colors": ["black", "white", "grey", "charcoal", "oatmeal", "navy"],
        "fabrics": ["heavy cotton", "raw denim", "merino wool", "matte leather"],
        "silhouettes": ["boxy", "oversized clean", "architectural", "straight-leg"],
        "forbidden_patterns": ["loud florals", "tie-dye"],
        "description": "Functional, clean geometries, high-contrast monochrome, effortlessly structured."
    },
    "streetwear_tech": {
        "name": "Elevated Streetwear / Techwear",
        "key_colors": ["black", "charcoal", "olive", "grey", "silver", "khaki", "white"],
        "fabrics": ["technical nylon", "gore-tex", "fleece", "heavyweight jersey", "leather"],
        "silhouettes": ["cargo", "oversized hoodie", "chunky footwear", "layered modular"],
        "forbidden_patterns": ["formal suiting", "lace"],
        "description": "Modern urban silhouette, utility pockets, technical textiles, and chunky footwear."
    },
    "smart_casual": {
        "name": "Smart Casual / Modern Professional",
        "key_colors": ["navy", "white", "grey", "tan", "olive", "burgundy", "light blue"],
        "fabrics": ["oxford cotton", "knitwear", "chino twill", "unstructured blazer"],
        "silhouettes": ["fitted", "clean taper", "layer-friendly"],
        "forbidden_patterns": ["distressed", "beachwear"],
        "description": "Polished yet versatile, bridging casual ease with professional structure."
    },
    "parisian_chic": {
        "name": "Parisian Chic",
        "key_colors": ["black", "white", "navy", "stripes", "camel", "red accent", "denim"],
        "fabrics": ["trench gabardine", "breton knit", "denim", "silk scarf", "leather"],
        "silhouettes": ["high-waisted", "effortless drape", "classic trench", "loafers"],
        "forbidden_patterns": ["neon", "athleisure"],
        "description": "Timeless French nonchalance, iconic wardrobe staples, balanced contrast."
    },
    "formal_evening": {
        "name": "Formal Gala / Black Tie",
        "key_colors": ["black", "midnight navy", "white", "emerald", "burgundy", "silver"],
        "fabrics": ["tuxedo wool", "satin", "silk", "velvet"],
        "silhouettes": ["structured suit", "floor-length", "tailored tuxedo"],
        "forbidden_patterns": ["denim", "sneakers", "t-shirts", "sweatshirts"],
        "description": "Highest level of formal dressing, precision tailoring, polished finish."
    }
}

# ---------------------------------------------------------
# 3. OCCASION RULES & DRESS CODES
# ---------------------------------------------------------

OCCASION_MATRIX = {
    "casual_day": {
        "name": "Casual Day Out / Weekend",
        "min_formality": 1,
        "max_formality": 4,
        "suitable_categories": ["t-shirt", "shirt", "hoodie", "jeans", "chinos", "sneakers", "loafers", "jacket"],
        "vibe": "Relaxed, comfortable, stylish"
    },
    "work_office": {
        "name": "Office / Business Professional",
        "min_formality": 4,
        "max_formality": 7,
        "suitable_categories": ["button-down", "blouse", "knit sweater", "trousers", "chinos", "blazer", "oxfords", "loafers", "skirt"],
        "forbidden": ["distressed denim", "sweatpants", "graphic tee", "flip-flops"],
        "vibe": "Clean, competent, sharp"
    },
    "date_night": {
        "name": "Date Night / Evening Drinks",
        "min_formality": 4,
        "max_formality": 8,
        "suitable_categories": ["fitted shirt", "silk blouse", "tailored trousers", "dark denim", "leather jacket", "blazer", "boots", "heels", "dress"],
        "vibe": "Alluring, sophisticated, confident"
    },
    "formal_event": {
        "name": "Formal Event / Wedding / Gala",
        "min_formality": 7,
        "max_formality": 10,
        "suitable_categories": ["suit", "tuxedo", "formal dress", "dress shoes", "oxfords", "heels", "blazer"],
        "forbidden": ["jeans", "t-shirt", "sneakers", "hoodie", "shorts"],
        "vibe": "Elevated, regal, timeless"
    },
    "summer_vacation": {
        "name": "Summer Vacation / Resort",
        "min_formality": 1,
        "max_formality": 5,
        "suitable_categories": ["linen shirt", "t-shirt", "shorts", "light trousers", "sandals", "loafers", "sunglasses", "sundress"],
        "vibe": "Breezy, effortless, sun-kissed"
    }
}

# ---------------------------------------------------------
# 4. THERMAL & WEATHER LAYERING RULES
# ---------------------------------------------------------

def get_thermal_layer_recommendations(temp_celsius: float, condition: str = "clear") -> Dict:
    """
    Returns required garment layers and thermal score constraints
    based on weather temperature and conditions.
    """
    is_rainy = "rain" in condition.lower() or "drizzle" in condition.lower()
    is_windy = "wind" in condition.lower() or "storm" in condition.lower()
    
    if temp_celsius < 5:
        # Freezing / Heavy Winter
        return {
            "tier": "Heavy Cold (<5°C)",
            "required_layers": ["base_top", "thermal_knit", "heavy_outerwear", "insulating_bottom", "winter_footwear"],
            "outerwear_type": ["heavy coat", "puffer jacket", "wool overcoat", "parka"],
            "accessory_recs": ["wool scarf", "gloves", "beanie"],
            "rain_protection": is_rainy,
            "min_warmth_score": 8,
            "max_warmth_score": 10
        }
    elif 5 <= temp_celsius < 15:
        # Chilly / Autumn-Early Spring
        return {
            "tier": "Chilly / Transition (5-15°C)",
            "required_layers": ["top", "mid_layer_or_light_jacket", "bottom", "closed_footwear"],
            "outerwear_type": ["trench coat", "leather jacket", "wool jacket", "bomber", "tweed blazer"],
            "accessory_recs": ["light scarf"] if is_windy else [],
            "rain_protection": is_rainy,
            "min_warmth_score": 5,
            "max_warmth_score": 8
        }
    elif 15 <= temp_celsius < 22:
        # Mild / Ideal Layering
        return {
            "tier": "Mild / Temperate (15-22°C)",
            "required_layers": ["top", "bottom", "light_layer_optional", "footwear"],
            "outerwear_type": ["cardigan", "overshirt", "light blazer", "denim jacket"],
            "accessory_recs": ["sunglasses"],
            "rain_protection": is_rainy,
            "min_warmth_score": 3,
            "max_warmth_score": 6
        }
    else:
        # Warm / Summer (>22°C)
        return {
            "tier": "Warm / Summer (22°C+)",
            "required_layers": ["breathable_top", "breathable_bottom", "breathable_footwear"],
            "outerwear_type": ["none_or_linen_overshirt"],
            "accessory_recs": ["sunglasses", "linen cap"],
            "rain_protection": is_rainy,
            "min_warmth_score": 1,
            "max_warmth_score": 4
        }

# ---------------------------------------------------------
# 5. HARMONY EVALUATOR
# ---------------------------------------------------------

def evaluate_color_harmony(color_list: List[str]) -> Tuple[float, str]:
    """
    Computes a harmony score (0.0 to 1.0) and explanation for a list of garment colors.
    """
    if not color_list:
        return 0.5, "No colors provided"
    
    cleaned = [c.lower().strip() for c in color_list]
    unique_colors = list(set(cleaned))
    
    # 1. Check Monochromatic / Tonal (same color family or all neutrals)
    neutrals_count = sum(1 for c in unique_colors if any(n in c for n in COLOR_PALETTES["neutrals"]))
    is_all_neutral = neutrals_count == len(unique_colors)
    
    if is_all_neutral:
        return 0.95, "Flawless neutral palette (sophisticated and timeless)"
    
    # 2. Check 3-color rule (rule of thumb: <= 3 prominent colors in an outfit)
    if len(unique_colors) <= 3:
        # Check if pairs are harmonious
        matched_pairs = 0
        total_pairs = 0
        for i in range(len(unique_colors)):
            for j in range(i + 1, len(unique_colors)):
                total_pairs += 1
                c1, c2 = unique_colors[i], unique_colors[j]
                if (c1, c2) in HARMONIOUS_PAIRS or (c2, c1) in HARMONIOUS_PAIRS:
                    matched_pairs += 1
                elif any(n in c1 for n in COLOR_PALETTES["neutrals"]) or any(n in c2 for n in COLOR_PALETTES["neutrals"]):
                    # Neutral anchors pair with almost everything
                    matched_pairs += 0.85
        
        ratio = (matched_pairs / total_pairs) if total_pairs > 0 else 0.8
        score = min(1.0, 0.6 + (0.4 * ratio))
        return score, "Balanced 3-color harmony with neutral anchoring"
    
    # More than 3 distinct colors: slight penalty for color clutter unless coordinated
    return 0.65, "Bold multi-color mix; consider anchoring with more neutral pieces"
