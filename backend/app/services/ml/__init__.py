"""
Modular ML Intelligence Services for Yorvyn.
Implements Models A through F:
- Model A: Body Intelligence (proportions, silhouette, fit compatibility)
- Model B: Skin & Colour Intelligence (undertone estimation, palettes, color harmony)
- Model C: Fashion Vision (classification, color/pattern extraction, embeddings)
- Model D: Wardrobe Intelligence (pairing matrices, co-wear, gap analysis)
- Model E: Personal Preference Learning (likes, dislikes, calibrated weights)
- Model F: Multi-Factor Outfit Ranking (10-factor composite scoring)
"""

from backend.app.services.ml.body_intelligence import body_intelligence_service, BodyIntelligenceService
from backend.app.services.ml.skin_colour_intelligence import skin_colour_intelligence_service, SkinColourIntelligenceService
from backend.app.services.ml.fashion_vision import fashion_vision_service, FashionVisionService
from backend.app.services.ml.preference_learning import preference_learning_service, PreferenceLearningService
from backend.app.services.ml.outfit_ranker import outfit_ranker_service, OutfitRankerService
from backend.app.services.wardrobe_intelligence_service import wardrobe_intelligence_service, WardrobeIntelligenceService

__all__ = [
    "body_intelligence_service",
    "BodyIntelligenceService",
    "skin_colour_intelligence_service",
    "SkinColourIntelligenceService",
    "fashion_vision_service",
    "FashionVisionService",
    "preference_learning_service",
    "PreferenceLearningService",
    "outfit_ranker_service",
    "OutfitRankerService",
    "wardrobe_intelligence_service",
    "WardrobeIntelligenceService",
]
