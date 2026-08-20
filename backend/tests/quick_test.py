"""Manual smoke test for the recommender.

This file is safe to import during pytest collection because it does not execute
work at module import time.
"""

import os
import sys
from pathlib import Path

import pandas as pd

os.environ["PERFUME_SKIP_AUTOLOAD"] = "1"
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ml_model import AdvancedPerfumeRecommender


def build_sample_recommender() -> AdvancedPerfumeRecommender:
    sample_data = pd.DataFrame(
        {
            "id": [0, 1, 2, 3],
            "name": ["Fresh Marine Breeze", "Rose Vanilla Night", "Smoky Oud Reserve", "Office Citrus Vetiver"],
            "brand": ["Oceanic", "Velvet", "Amber House", "Terra"],
            "gender": ["men", "women", "unisex", "men"],
            "rating": [4.6, 4.8, 4.9, 4.7],
            "rating_count": [220, 300, 280, 180],
            "price": [82, 110, 150, 92],
            "sold": [900, 850, 600, 710],
            "accords": [
                "fresh aquatic citrus",
                "rose vanilla amber musk",
                "oud smoky amber woody",
                "fresh citrus vetiver green",
            ],
            "description": [
                "Bright marine freshness for daytime wear.",
                "Romantic rose and vanilla with warm amber depth.",
                "Dense oud and smoke for evening wear.",
                "A crisp office-safe perfume with citrus and vetiver.",
            ],
            "source": ["fragrantica", "fragrantica", "fragrantica", "fragrantica"],
        }
    )

    rec = AdvancedPerfumeRecommender(autoload=False)
    rec.data = sample_data
    rec._train_all_models()
    return rec


def main():
    rec = build_sample_recommender()

    print("1. Preference recommendations")
    result = rec.recommend_from_user_input("fresh citrus office perfume for men", limit=2, allow_ai_fallback=False)
    for item in result["recommendations"]:
        print(f"   - {item['name']} ({item['match_score']:.3f})")

    print("\n2. Search")
    for item in rec.search_perfumes("oud", limit=2):
        print(f"   - {item['name']}")


if __name__ == "__main__":
    main()
