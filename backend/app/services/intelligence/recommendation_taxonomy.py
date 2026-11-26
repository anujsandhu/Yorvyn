"""
YORVYN Intelligence Platform (YIP) — Normalized Fashion Recommendation Taxonomy.

Reuses existing YORVYN taxonomy sources (`universal_garment_taxonomy.json`,
`universal_garment_classifier.py` mappings, `fashion_knowledge.py`, and
`component_taxonomy.py`) without duplicating model taxonomies. Supports rich
recommendation attributes: style, silhouette, fit, color, pattern, material,
occasion, season, and gender-neutral metadata.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from backend.app.domain.fashion_knowledge import STYLE_AESTHETICS
from backend.app.services.garments.intelligence.universal_garment_classifier import (
    DOMAIN_TO_SUBCATEGORIES,
    NEURAL_TO_TAXONOMY_CAT,
)
from backend.app.services.intelligence.component_taxonomy import GarmentFamily

UNIVERSAL_TAXONOMY_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../../data/taxonomy/universal_garment_taxonomy.json")
)


CANONICAL_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "tops": {
        "display_name": "Tops",
        "family": GarmentFamily.UPPER_BODY.value,
        "gender_neutral": True,
        "subcategories": [
            "tshirt", "shirt", "formal_shirt", "casual_shirt", "oxford_shirt",
            "oversized_shirt", "polo_shirt", "tank_top", "crop_top",
            "hoodie", "pullover_hoodie", "zip_hoodie", "sweater", "knitwear",
        ],
    },
    "bottoms": {
        "display_name": "Bottoms",
        "family": GarmentFamily.LOWER_BODY.value,
        "gender_neutral": True,
        "subcategories": [
            "jeans", "straight_jeans", "slim_jeans", "wide_leg_jeans",
            "trousers", "formal_trousers", "chinos", "cargo_pants", "shorts",
        ],
    },
    "outerwear": {
        "display_name": "Outerwear",
        "family": GarmentFamily.UPPER_BODY.value,
        "gender_neutral": True,
        "subcategories": [
            "jackets", "denim_jacket", "bomber_jacket", "leather_jacket",
            "puffer_jacket", "coats", "formal_coat", "trench_coat", "blazers", "blazer",
        ],
    },
    "dresses_and_skirts": {
        "display_name": "Dresses & Skirts",
        "family": GarmentFamily.DRESS_ONE_PIECE.value,
        "gender_neutral": False,
        "subcategories": [
            "dress", "a_line_dress", "bodycon_dress", "maxi_dress", "shift_dress",
            "wrap_dress", "slip_dress", "skirt", "a_line_skirt", "pencil_skirt",
            "pleated_skirt", "mini_skirt", "maxi_skirt",
        ],
    },
    "footwear": {
        "display_name": "Footwear",
        "family": GarmentFamily.FOOTWEAR.value,
        "gender_neutral": True,
        "subcategories": [
            "sneakers", "running_shoes", "boots", "loafers", "sandals", "formal_shoes",
        ],
    },
    "accessories": {
        "display_name": "Accessories",
        "family": GarmentFamily.ACCESSORY.value,
        "gender_neutral": True,
        "subcategories": ["cap", "beanie", "scarf", "belt", "tote_bag", "tie"],
    },
    "traditional": {
        "display_name": "Traditional Wear",
        "family": GarmentFamily.UPPER_BODY.value,
        "gender_neutral": False,
        "subcategories": ["kurta", "sherwani", "saree", "lehenga", "salwar_kameez"],
    },
    "sportswear": {
        "display_name": "Sportswear",
        "family": GarmentFamily.UPPER_BODY.value,
        "gender_neutral": True,
        "subcategories": ["athletic_top", "track_pants", "joggers", "windbreaker", "training_shorts"],
    },
    "formalwear": {
        "display_name": "Formalwear",
        "family": GarmentFamily.UPPER_BODY.value,
        "gender_neutral": True,
        "subcategories": ["suit_jacket", "tuxedo", "dress_shirt", "tailored_trousers", "evening_gown"],
    },
    "streetwear": {
        "display_name": "Streetwear",
        "family": GarmentFamily.UPPER_BODY.value,
        "gender_neutral": True,
        "subcategories": ["oversized_tee", "boxy_hoodie", "cargo_pants", "varsity_jacket", "bucket_hat"],
    },
}

_CATEGORY_ALIASES: Dict[str, str] = {
    "top": "tops",
    "tops": "tops",
    "shirt": "tops",
    "shirts": "tops",
    "tshirt": "tops",
    "t-shirt": "tops",
    "t-shirts": "tops",
    "hoodie": "tops",
    "hoodies": "tops",
    "sweater": "tops",
    "sweaters": "tops",
    "knitwear": "tops",
    "bottom": "bottoms",
    "bottoms": "bottoms",
    "jeans": "bottoms",
    "trousers": "bottoms",
    "pants": "bottoms",
    "cargo": "bottoms",
    "cargo_pants": "bottoms",
    "shorts": "bottoms",
    "jacket": "outerwear",
    "jackets": "outerwear",
    "coat": "outerwear",
    "coats": "outerwear",
    "blazer": "outerwear",
    "blazers": "outerwear",
    "outerwear": "outerwear",
    "dress": "dresses_and_skirts",
    "dresses": "dresses_and_skirts",
    "skirt": "dresses_and_skirts",
    "skirts": "dresses_and_skirts",
    "dresses_and_skirts": "dresses_and_skirts",
    "shoe": "footwear",
    "shoes": "footwear",
    "footwear": "footwear",
    "sneakers": "footwear",
    "accessory": "accessories",
    "accessories": "accessories",
    "traditional": "traditional",
    "traditional_wear": "traditional",
    "ethnic": "traditional",
    "sportswear": "sportswear",
    "activewear": "sportswear",
    "athletic": "sportswear",
    "formal": "formalwear",
    "formalwear": "formalwear",
    "streetwear": "streetwear",
}

_SUBCATEGORY_ALIASES: Dict[str, Tuple[str, str]] = {
    "t-shirt": ("tops", "tshirt"),
    "t-shirts": ("tops", "tshirt"),
    "tshirt": ("tops", "tshirt"),
    "tshirts": ("tops", "tshirt"),
    "shirt": ("tops", "shirt"),
    "shirts": ("tops", "shirt"),
    "button-down": ("tops", "formal_shirt"),
    "hoodie": ("tops", "hoodie"),
    "hoodies": ("tops", "hoodie"),
    "sweater": ("tops", "sweater"),
    "sweaters": ("tops", "sweater"),
    "knitwear": ("tops", "knitwear"),
    "jeans": ("bottoms", "jeans"),
    "trousers": ("bottoms", "trousers"),
    "cargo": ("bottoms", "cargo_pants"),
    "cargo pants": ("bottoms", "cargo_pants"),
    "cargo_pants": ("bottoms", "cargo_pants"),
    "shorts": ("bottoms", "shorts"),
    "jacket": ("outerwear", "jackets"),
    "jackets": ("outerwear", "jackets"),
    "coat": ("outerwear", "coats"),
    "coats": ("outerwear", "coats"),
    "blazer": ("outerwear", "blazers"),
    "blazers": ("outerwear", "blazers"),
}


class RecommendationGarmentAttributes(BaseModel):
    """Extensible garment attribute metadata normalized across taxonomy sources."""

    item_id: str
    name: str
    category: str
    subcategory: str = ""
    family: str = GarmentFamily.UPPER_BODY.value
    style: List[str] = Field(default_factory=list)
    silhouette: str = "regular"
    fit: str = "regular"
    color: str = "neutral"
    secondary_color: Optional[str] = None
    pattern: str = "solid"
    material: str = "cotton"
    occasion: List[str] = Field(default_factory=lambda: ["casual"])
    season: List[str] = Field(default_factory=lambda: ["all_season"])
    gender_neutral: bool = True
    formality: int = 5
    warmth: int = 5
    available: bool = True
    brand: str = ""
    owner_id: Optional[str] = None
    image_url: Optional[str] = None
    visual_embedding: Optional[List[float]] = None
    embedding_model_id: Optional[str] = None
    popularity_score: float = 0.0
    freshness_days: float = 30.0


@lru_cache(maxsize=1)
def load_universal_taxonomy() -> Dict[str, Any]:
    """Loads existing `universal_garment_taxonomy.json` safely."""
    try:
        with open(UNIVERSAL_TAXONOMY_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"version": "2.0.0", "categories": {}}


def normalize_category_and_subcategory(
    category: Optional[str],
    subcategory: Optional[str] = None,
) -> Tuple[str, str]:
    """Maps neural classifier labels, wardrobe labels, or user terms into canonical categories."""
    sub_clean = (subcategory or "").strip().lower().replace(" ", "_")
    cat_clean = (category or "").strip().lower().replace(" ", "_")

    if sub_clean in _SUBCATEGORY_ALIASES:
        inferred_cat, norm_sub = _SUBCATEGORY_ALIASES[sub_clean]
        if not cat_clean or cat_clean in {"other", "garment", "apparel"}:
            cat_clean = inferred_cat
        sub_clean = norm_sub
    elif not sub_clean and cat_clean in _SUBCATEGORY_ALIASES:
        cat_clean, sub_clean = _SUBCATEGORY_ALIASES[cat_clean]

    # Reuse classifier domain map if applicable
    if cat_clean in NEURAL_TO_TAXONOMY_CAT:
        norm_cat = NEURAL_TO_TAXONOMY_CAT[cat_clean]
        if not sub_clean and cat_clean in DOMAIN_TO_SUBCATEGORIES:
            sub_clean = cat_clean
    elif cat_clean in _CATEGORY_ALIASES:
        norm_cat = _CATEGORY_ALIASES[cat_clean]
    elif cat_clean in CANONICAL_CATEGORIES:
        norm_cat = cat_clean
    else:
        norm_cat = cat_clean or "tops"

    if not sub_clean:
        sub_clean = cat_clean if cat_clean and cat_clean != norm_cat else norm_cat
    return norm_cat, sub_clean


def normalize_item(raw: Dict[str, Any]) -> RecommendationGarmentAttributes:
    """Converts a wardrobe dict or catalog record into normalized recommendation attributes."""
    raw_cat = raw.get("category") or raw.get("garment_category") or "tops"
    raw_sub = raw.get("subcategory") or raw.get("sub_category") or ""
    norm_cat, norm_sub = normalize_category_and_subcategory(str(raw_cat), str(raw_sub))

    # Secondary contextual macro-tags if specified (sportswear, formalwear, streetwear)
    raw_styles = raw.get("style") or raw.get("styles") or raw.get("aesthetic") or []
    if isinstance(raw_styles, str):
        styles = [s.strip().lower() for s in raw_styles.split(",") if s.strip()]
    else:
        styles = [str(s).strip().lower() for s in raw_styles if str(s).strip()]

    occasions_raw = raw.get("occasion") or raw.get("occasions") or []
    if isinstance(occasions_raw, str):
        occasions = [o.strip().lower() for o in occasions_raw.split(",") if o.strip()]
    elif occasions_raw:
        occasions = [str(o).strip().lower() for o in occasions_raw if str(o).strip()]
    else:
        formality = int(raw.get("formality", 5) or 5)
        occasions = ["formal", "work"] if formality >= 7 else (["business", "smart_casual"] if formality >= 5 else ["casual", "everyday"])

    seasons_raw = raw.get("season") or raw.get("seasons") or ["all_season"]
    if isinstance(seasons_raw, str):
        seasons = [s.strip().lower() for s in seasons_raw.split(",") if s.strip()]
    else:
        seasons = [str(s).strip().lower() for s in seasons_raw if str(s).strip()]

    cat_meta = CANONICAL_CATEGORIES.get(norm_cat, {})
    return RecommendationGarmentAttributes(
        item_id=str(raw.get("item_id") or raw.get("id") or raw.get("garment_id") or raw.get("name") or "item"),
        name=str(raw.get("name") or f"{norm_sub.replace('_', ' ').title()}"),
        category=norm_cat,
        subcategory=norm_sub,
        family=str(cat_meta.get("family", GarmentFamily.UPPER_BODY.value)),
        style=styles or ["casual"],
        silhouette=str(raw.get("silhouette") or raw.get("cut") or "regular").lower(),
        fit=str(raw.get("fit") or raw.get("fit_preference") or "regular").lower(),
        color=str(raw.get("color") or "neutral").lower(),
        secondary_color=(str(raw["secondary_color"]).lower() if raw.get("secondary_color") else None),
        pattern=str(raw.get("pattern") or "solid").lower(),
        material=str(raw.get("material") or raw.get("fabric") or "cotton").lower(),
        occasion=occasions,
        season=seasons,
        gender_neutral=bool(raw.get("gender_neutral", cat_meta.get("gender_neutral", True))),
        formality=int(raw.get("formality", 5) or 5),
        warmth=int(raw.get("warmth", 5) or 5),
        available=bool(raw.get("available", True)),
        brand=str(raw.get("brand") or ""),
        owner_id=(str(raw["user_id"]) if raw.get("user_id") else (str(raw["owner_id"]) if raw.get("owner_id") else None)),
        image_url=raw.get("image_url"),
        visual_embedding=raw.get("visual_embedding"),
        embedding_model_id=raw.get("embedding_model_id"),
        popularity_score=float(raw.get("popularity_score", raw.get("wear_count", 0)) or 0.0),
        freshness_days=float(raw.get("freshness_days", 14.0) or 14.0),
    )


def get_taxonomy_summary() -> Dict[str, Any]:
    """Returns merged recommendation taxonomy reusing universal_garment_taxonomy.json."""
    u_tax = load_universal_taxonomy()
    return {
        "universal_taxonomy_version": u_tax.get("version", "2.0.0"),
        "categories": CANONICAL_CATEGORIES,
        "universal_category_keys": sorted(list((u_tax.get("categories") or {}).keys())),
        "supported_attribute_dimensions": [
            "style", "silhouette", "fit", "color", "pattern",
            "material", "occasion", "season", "gender_neutral",
        ],
        "known_style_aesthetics": sorted(list(STYLE_AESTHETICS.keys())),
    }
