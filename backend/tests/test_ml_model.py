"""Tests for the local-first perfume recommender."""

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

os.environ["PERFUME_SKIP_AUTOLOAD"] = "1"
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ml_model import AdvancedPerfumeRecommender, clean_accords


@pytest.fixture
def sample_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [0, 1, 2, 3, 4, 5],
            "name": [
                "Fresh Marine Breeze",
                "Citrus Office Vetiver",
                "Rose Vanilla Night",
                "Designer Perfume Sampler 10 Vials",
                "Smoky Oud Reserve",
                "Soft Floral Musk",
            ],
            "brand": ["Oceanic", "Terra", "Velvet", "Generic", "Amber House", "Bloom"],
            "gender": ["men", "men", "women", "men", "unisex", "women"],
            "rating": [4.6, 4.7, 4.8, 3.2, 4.9, 4.5],
            "rating_count": [250, 180, 320, 5, 280, 140],
            "price": [82, 90, 110, 20, 150, 78],
            "sold": [900, 740, 860, 12, 610, 430],
            "accords": [
                "fresh aquatic citrus",
                "fresh citrus vetiver green",
                "rose vanilla amber musk",
                "sample designer assorted",
                "oud smoky amber woody",
                "soft floral musk powdery",
            ],
            "description": [
                "Bright marine freshness for clean daytime wear.",
                "A crisp office-safe perfume with citrus and vetiver.",
                "Romantic rose and vanilla with warm amber depth.",
                "A mixed sampler pack of mini vials and tester sprays.",
                "Dense oud and smoke for evening wear.",
                "Soft floral musk for elegant daily use.",
            ],
            "source": [
                "fragrantica",
                "fragrantica",
                "fragrantica",
                "ebay_mens",
                "fragrantica",
                "curated",
            ],
            "image_url": ["", "", "", "", "", ""],
            "url": ["", "", "", "", "", ""],
        }
    )


@pytest.fixture
def recommender(sample_data: pd.DataFrame) -> AdvancedPerfumeRecommender:
    rec = AdvancedPerfumeRecommender(autoload=False)
    rec.data = sample_data.copy()
    rec._train_all_models()
    return rec


def test_clean_accords_handles_list_strings():
    assert clean_accords("['Rose', 'Vanilla']") == "rose vanilla"


def test_training_builds_runtime_artifacts(recommender: AdvancedPerfumeRecommender):
    info = recommender.get_model_info()
    assert info["tfidf_ready"] is True
    assert info["knn_ready"] is True
    assert info["runtime_ready"] is True
    assert len(recommender.data) == 6


def test_preference_query_prefers_relevant_local_match(recommender: AdvancedPerfumeRecommender):
    results = recommender.recommend_by_preference(
        "fresh citrus office perfume for men",
        limit=3,
    )
    assert len(results) == 3
    names = [item["name"] for item in results]
    assert "Designer Perfume Sampler 10 Vials" not in names[:2]
    assert names[0] in {"Fresh Marine Breeze", "Citrus Office Vetiver"}
    assert results[0]["algorithm"] == "local_multi_signal"


def test_structured_context_improves_profile_matching(recommender: AdvancedPerfumeRecommender):
    result = recommender.recommend_from_user_input(
        preferences="something romantic for evening",
        limit=2,
        context={
            "preferred_gender": "women",
            "occasion": "date",
            "liked_notes": ["rose", "vanilla"],
        },
        allow_ai_fallback=False,
    )
    assert result["recommendations"]
    assert result["recommendations"][0]["name"] == "Rose Vanilla Night"
    assert result["confidence"] > 0


def test_empty_preference_uses_popular_local_fallback(recommender: AdvancedPerfumeRecommender):
    result = recommender.recommend_from_user_input("", limit=2, allow_ai_fallback=False)
    assert len(result["recommendations"]) == 2
    assert result["algorithm"] == "popular_fallback"


def test_hybrid_recommendations_exclude_original(recommender: AdvancedPerfumeRecommender):
    results = recommender.recommend_hybrid(0, limit=3)
    assert all(item["id"] != 0 for item in results)


def test_search_ranks_brand_and_note_matches(recommender: AdvancedPerfumeRecommender):
    results = recommender.search_perfumes("oud amber", limit=3)
    assert results
    assert results[0]["name"] == "Smoky Oud Reserve"


def test_backwards_compatible_search_alias(recommender: AdvancedPerfumeRecommender):
    assert recommender.search("Bloom", limit=2)[0]["brand"] == "Bloom"
