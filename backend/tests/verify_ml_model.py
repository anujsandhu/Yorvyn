"""Manual verification helper for the current ML model API."""

import os
import sys
from pathlib import Path

import pandas as pd

os.environ["PERFUME_SKIP_AUTOLOAD"] = "1"
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ml_model import AdvancedPerfumeRecommender


def main():
    sample_data = pd.DataFrame(
        {
            "id": [0, 1, 2, 3, 4],
            "name": [
                "Fresh Marine Breeze",
                "Citrus Office Vetiver",
                "Rose Vanilla Night",
                "Smoky Oud Reserve",
                "Soft Floral Musk",
            ],
            "brand": ["Oceanic", "Terra", "Velvet", "Amber House", "Bloom"],
            "gender": ["men", "men", "women", "unisex", "women"],
            "rating": [4.6, 4.7, 4.8, 4.9, 4.5],
            "rating_count": [250, 180, 320, 280, 140],
            "price": [82, 90, 110, 150, 78],
            "sold": [900, 740, 860, 610, 430],
            "accords": [
                "fresh aquatic citrus",
                "fresh citrus vetiver green",
                "rose vanilla amber musk",
                "oud smoky amber woody",
                "soft floral musk powdery",
            ],
            "description": [
                "Bright marine freshness for clean daytime wear.",
                "A crisp office-safe perfume with citrus and vetiver.",
                "Romantic rose and vanilla with warm amber depth.",
                "Dense oud and smoke for evening wear.",
                "Soft floral musk for elegant daily use.",
            ],
            "source": ["fragrantica", "fragrantica", "fragrantica", "fragrantica", "curated"],
        }
    )

    rec = AdvancedPerfumeRecommender(autoload=False)
    rec.data = sample_data.copy()
    rec._train_all_models()

    print("Model info:", rec.get_model_info())
    print("\nPreference query:")
    result = rec.recommend_from_user_input(
        "romantic vanilla rose perfume for women",
        limit=3,
        allow_ai_fallback=False,
    )
    for item in result["recommendations"]:
        print(f"- {item['name']} ({item['match_score']:.3f})")


if __name__ == "__main__":
    main()
