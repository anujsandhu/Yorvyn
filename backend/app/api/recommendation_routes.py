"""
Recommendation & Perfume API routes — fully public, no auth required.
All data comes from the trained ML model dataset (73K+ perfumes).
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
import numpy as np
import logging
from ..ml_model import recommender, clean_accords

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────
class RecommendationRequest(BaseModel):
    preferences: str
    num_recommendations: int = 10
    preferred_gender: Optional[str] = None
    occasion: Optional[str] = None
    season: Optional[str] = None
    mood: Optional[str] = None
    liked_notes: List[str] = Field(default_factory=list)
    disliked_notes: List[str] = Field(default_factory=list)
    reference_perfumes: List[str] = Field(default_factory=list)
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None


class PerfumeScore(BaseModel):
    perfume_id: str
    name: str
    brand: str
    family: str
    rating: float
    ml_score: float
    rating_score: float
    popularity_score: float
    final_score: float
    description: Optional[str] = None
    price_usd: Optional[float] = None
    image_url: Optional[str] = None
    gender: Optional[str] = None
    accords: Optional[str] = None
    algorithm: Optional[str] = None


class RecommendationResponse(BaseModel):
    recommendations: List[PerfumeScore]
    explanation: str
    total_processed: int
    confidence: float = 0.0
    fallback_used: bool = False
    fallback_provider: Optional[str] = None
    strategy: str = "local_multi_signal"


def _serialize_perfume_row(row, premium_score: Optional[float] = None):
    accords = clean_accords(str(row.get("accords", "")))
    payload = {
        "id": str(row.get("id", "")),
        "name": str(row.get("name", "Unknown")),
        "brand": str(row.get("brand", "Unknown")),
        "family": accords[:60] if accords else "Fragrance",
        "price": float(row.get("price", 0) or 0),
        "rating": float(row.get("rating", 4.0) or 4.0),
        "sold": int(row.get("sold", 0) or 0),
        "rating_count": int(row.get("rating_count", 0) or 0),
        "description": str(row.get("description", ""))[:320],
        "image_url": str(row.get("image_url", "")) or None,
        "gender": str(row.get("gender", "unisex")),
        "accords": accords,
    }
    if premium_score is not None:
        payload["premium_score"] = float(premium_score)
    return payload


def _build_premium_ranked_frame():
    if recommender.data is None or len(recommender.data) == 0:
        return None

    df = recommender.data.copy()
    rating_series = df["rating"].fillna(0).astype(float)
    rating_count_series = df["rating_count"] if "rating_count" in df.columns else np.zeros(len(df))
    if not hasattr(rating_count_series, "fillna"):
        rating_count_series = np.zeros(len(df))
    sold_series = df["sold"] if "sold" in df.columns else np.zeros(len(df))
    if not hasattr(sold_series, "fillna"):
        sold_series = np.zeros(len(df))
    price_series = df["price"] if "price" in df.columns else np.zeros(len(df))
    if not hasattr(price_series, "fillna"):
        price_series = np.zeros(len(df))

    rating_count = np.asarray(rating_count_series, dtype=float)
    sold = np.asarray(sold_series, dtype=float)
    price = np.asarray(price_series, dtype=float)
    desc_len = df["description"].fillna("").astype(str).str.len().clip(0, 450).to_numpy(dtype=float)

    rating_norm = np.clip(rating_series.to_numpy(dtype=float) / 5.0, 0.0, 1.0)
    rating_count_norm = np.log1p(rating_count) / (np.log1p(rating_count).max() + 1e-8)
    sold_norm = np.log1p(sold) / (np.log1p(sold).max() + 1e-8)
    price_norm = np.log1p(price.clip(min=0)) / (np.log1p(price.clip(min=0)).max() + 1e-8)
    desc_norm = desc_len / 450.0

    if getattr(recommender, "quality_scores", np.array([])).size == len(df):
        quality = recommender.quality_scores.astype(float)
        popularity = recommender.popularity_scores.astype(float)
        penalties = recommender.title_penalties.astype(float)
    else:
        quality = 0.45 * rating_norm + 0.25 * rating_count_norm + 0.15 * sold_norm + 0.15 * desc_norm
        popularity = 0.7 * rating_norm + 0.3 * rating_count_norm
        penalties = np.zeros(len(df))

    df["_premium_score"] = (
        0.36 * rating_norm
        + 0.22 * rating_count_norm
        + 0.10 * sold_norm
        + 0.10 * desc_norm
        + 0.08 * price_norm
        + 0.10 * quality
        + 0.08 * popularity
        - 0.14 * penalties
    )

    exclusion_mask = (
        df["name"].fillna("").astype(str).str.contains(
            r"\b(sample|sampler|tester|vial|decant|bundle|set|kit|lot|variety|discovery)\b",
            case=False,
            regex=True,
            na=False,
        )
    )
    filter_mask = (
        (df["rating"].fillna(0) >= 3.8)          # ↑ from 4.0 to 3.8 for better coverage
        & (~exclusion_mask)
        & (df["description"].fillna("").astype(str).str.len() >= 20)
    )

    ranked = df[filter_mask].copy()
    if ranked.empty:
        ranked = df.copy()

    return ranked.nlargest(12, "_premium_score")


# ── Recommendations ──────────────────────────────────────────────────
@router.post("/recommendations", response_model=RecommendationResponse)
def get_recommendations(req: RecommendationRequest):
    """Get ML-powered perfume recommendations from user preferences (public)."""

    logger.info(f"📝 Recommendation request: preferences='{req.preferences[:50]}...', num={req.num_recommendations}")
    
    # Check model readiness
    if recommender.data is None or len(recommender.data) == 0:
        logger.error("❌ ML model data not ready")
        raise HTTPException(
            status_code=503, 
            detail="ML model data not loaded. Please try again in a moment."
        )
    
    if recommender.tfidf_vectorizer is None:
        logger.error("❌ TF-IDF vectorizer not ready")
        raise HTTPException(
            status_code=503, 
            detail="ML model vectorizer not initialized. System is starting up."
        )

    try:
        logger.debug(f"🔍 Building recommendation context with gender={req.preferred_gender}, occasion={req.occasion}")
        
        context = {
            "preferred_gender": req.preferred_gender,
            "occasion": req.occasion,
            "season": req.season,
            "mood": req.mood,
            "liked_notes": req.liked_notes,
            "disliked_notes": req.disliked_notes,
            "reference_perfumes": req.reference_perfumes,
            "budget_min": req.budget_min,
            "budget_max": req.budget_max,
        }
        
        recommendation_result = recommender.recommend_from_user_input(
            preferences=req.preferences,
            limit=req.num_recommendations,
            context=context,
        )
        ml_recs = recommendation_result.get("recommendations", [])
        logger.info(f"✅ Got {len(ml_recs)} recommendations from ML model")

        if not ml_recs and len(recommender.data) > 0:
            logger.info("⚠️ No ML recommendations, falling back to hybrid")
            ml_recs = recommender.recommend_hybrid(
                perfume_id=0, limit=req.num_recommendations
            )

        recommendations: list[PerfumeScore] = []
        for rec in ml_recs:
            pid = None
            try:
                pid = rec.get("id")
                if pid is None:
                    logger.debug("⊘ Skipping recommendation with no ID")
                    continue

                # rec already contains cleaned row data from _safe_row
                match_score  = float(rec.get("match_score", rec.get("score", 0.7)))
                rating       = float(rec.get("rating", 4.0) or 4.0)
                rating_score = rating / 5.0
                popularity   = min(0.95, match_score + 0.1)
                final_score  = min(0.99, max(0.0, match_score * 0.5 + rating_score * 0.3 + popularity * 0.2))

                accords = str(rec.get("accords", ""))

                recommendations.append(
                    PerfumeScore(
                        perfume_id=str(pid),
                        name=str(rec.get("name", "Unknown")),
                        brand=str(rec.get("brand", "Unknown")),
                        family=accords[:60] if accords else "Fragrance",
                        rating=rating,
                        ml_score=match_score,
                        rating_score=rating_score,
                        popularity_score=popularity,
                        final_score=final_score,
                        description=str(rec.get("description", ""))[:250],
                        price_usd=float(rec.get("price", 0) or 0),
                        image_url=str(rec.get("image_url", "")) or None,
                        gender=str(rec.get("gender", "unisex")),
                        accords=accords,
                        algorithm=rec.get("algorithm", "hybrid"),
                    )
                )
            except Exception as e:
                logger.warning(f"⚠️ Error processing recommendation {pid}: {str(e)}")
                continue

        explanation = recommendation_result.get(
            "explanation",
            f"Based on your preference for '{req.preferences}'",
        )
        if not recommendations:
            explanation = "No matching perfumes found. Try different keywords or check back soon."
            logger.warning("⚠️ No recommendations could be processed")

        logger.info(f"✅ Returning {len(recommendations)} recommendations")
        return RecommendationResponse(
            recommendations=recommendations,
            explanation=explanation,
            total_processed=len(recommendations),
            confidence=float(recommendation_result.get("confidence", 0.0) or 0.0),
            fallback_used=bool(recommendation_result.get("ai_fallback_used", False)),
            fallback_provider=recommendation_result.get("fallback_provider"),
            strategy=str(recommendation_result.get("algorithm", "local_multi_signal")),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Recommendation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Recommendation processing failed: {str(e)[:100]}"
        )


# ── Popular Perfumes ──────────────────────────────────────────────────
@router.get("/perfumes/popular")
def get_popular_perfumes(limit: int = 8):
    """Top-rated perfumes from the trained dataset (sorted by rating_count × rating)."""
    if recommender.data is None or len(recommender.data) == 0:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "10"},
            content={
                "error": "Backend is loading ML models, please wait 10–15 seconds and refresh...",
                "status": "loading",
            },
        )

    try:
        df = recommender.data.copy()

        # Score = rating × log(1 + rating_count) — rewards both quality and popularity
        rating_count = df["rating_count"].fillna(0) if "rating_count" in df.columns else 0
        df["_pop_score"] = df["rating"].fillna(0) * np.log1p(rating_count)

        # Filter: must have rating > 3.5, not a sampler/tester
        noise_mask = df["name"].fillna("").astype(str).str.contains(
            r"\b(sample|sampler|tester|vial|decant|bundle|set|kit|lot)\b",
            case=False, regex=True, na=False,
        )
        mask = (df["rating"].fillna(0) > 3.5) & (~noise_mask)
        filtered = df[mask].nlargest(limit, "_pop_score")

        if len(filtered) < limit:
            filtered = df.nlargest(limit, "_pop_score")

        results = []
        for _, row in filtered.iterrows():
            accords = clean_accords(str(row.get("accords", "")))
            results.append({
                "id": str(row.get("id", "")),
                "name": str(row.get("name", "Unknown")),
                "brand": str(row.get("brand", "Unknown")),
                "family": accords[:60] if accords else "Fragrance",
                "price": float(row.get("price", 0) or 0),
                "rating": float(row.get("rating", 4.0) or 4.0),
                "sold": int(row.get("sold", 0) or 0),
                "rating_count": int(row.get("rating_count", 0) or 0),
                "description": str(row.get("description", ""))[:200],
                "image_url": str(row.get("image_url", "")) or None,
                "gender": str(row.get("gender", "unisex")),
                "accords": accords,
            })

        return {"popular": results}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"popular": [], "error": str(e)}


@router.get("/perfumes/featured")
def get_featured_perfumes():
    """Return one featured premium perfume plus a premium collection for the home page."""
    ranked = _build_premium_ranked_frame()
    if ranked is None or ranked.empty:
        return {"featured": None, "premium_collection": []}

    records = ranked.to_dict("records")
    featured = _serialize_perfume_row(records[0], records[0].get("_premium_score", 0.0))
    premium_collection = [
        _serialize_perfume_row(row, row.get("_premium_score", 0.0))
        for row in records[1:7]
    ]
    return {
        "featured": featured,
        "premium_collection": premium_collection,
    }


# ── Search ────────────────────────────────────────────────────────────
@router.get("/perfumes/search")
def search_perfumes(q: str, limit: int = 10):
    """Search perfumes by name, brand, or accords."""
    if not q or len(q) < 1:
        raise HTTPException(status_code=400, detail="Query required")

    raw_results = recommender.search_perfumes(q, limit)

    # Normalize results
    results = []
    for r in raw_results:
        accords = clean_accords(str(r.get("accords", "")))
        results.append({
            "id": str(r.get("id", "")),
            "name": str(r.get("name", "Unknown")),
            "brand": str(r.get("brand", "Unknown")),
            "family": accords[:60] if accords else "Fragrance",
            "rating": float(r.get("rating", 4.0) or 4.0),
            "price": float(r.get("price", 0) or 0),
            "description": str(r.get("description", ""))[:200],
            "image_url": str(r.get("image_url", "")) or None,
            "gender": str(r.get("gender", "unisex")),
            "accords": accords,
        })

    return {"results": results}


# ── Perfume Detail ────────────────────────────────────────────────────
@router.get("/perfumes/{perfume_id}")
def get_perfume_details(perfume_id: str):
    """Get full perfume details by ID."""
    details = recommender.get_perfume_details(perfume_id)
    if not details:
        raise HTTPException(status_code=404, detail="Perfume not found")

    # Ensure accords is clean
    details["accords"] = clean_accords(details.get("accords", ""))

    # Build real shopping links
    name_encoded = str(details.get("name", "perfume")).replace(" ", "+")
    shopping_links = [
        {
            "platform": "Amazon",
            "url": f"https://www.amazon.in/s?k={name_encoded}+perfume",
        },
        {
            "platform": "Flipkart",
            "url": f"https://www.flipkart.com/search?q={name_encoded}+perfume",
        },
        {
            "platform": "Nykaa",
            "url": f"https://www.nykaa.com/search/result/?q={name_encoded}",
        },
    ]

    return {**details, "shopping_links": shopping_links}


# ── Categories ────────────────────────────────────────────────────────
@router.get("/perfumes/categories/list")
def get_categories():
    """Get fragrance categories with counts from the dataset."""
    if recommender.data is None:
        return {"categories": []}

    df = recommender.data
    accords_col = df["accords"].astype(str).str.lower()

    categories: list[dict] = [
        {"name": "Floral", "key": "floral", "emoji": "🌸", "count": 0},
        {"name": "Woody", "key": "woody", "emoji": "🌲", "count": 0},
        {"name": "Fresh", "key": "fresh", "emoji": "💧", "count": 0},
        {"name": "Oriental", "key": "oriental", "emoji": "✨", "count": 0},
        {"name": "Citrus", "key": "citrus", "emoji": "🍋", "count": 0},
        {"name": "Fruity", "key": "fruity", "emoji": "🍇", "count": 0},
        {"name": "Spicy", "key": "spicy", "emoji": "🌶️", "count": 0},
        {"name": "Sweet", "key": "sweet", "emoji": "🍯", "count": 0},
    ]

    for cat in categories:
        cat["count"] = int(accords_col.str.contains(cat["key"], na=False).sum())

    # Sort by count descending
    categories.sort(key=lambda c: c["count"], reverse=True)

    return {"categories": categories}


# ── Stats ─────────────────────────────────────────────────────────────
@router.get("/stats")
def get_stats():
    """Dataset statistics from the trained ML model."""
    if recommender.data is None:
        return {
            "total_perfumes": 0,
            "unique_brands": 0,
            "unique_families": 0,
            "avg_rating": 0,
        }

    df = recommender.data
    return {
        "total_perfumes": len(df),
        "unique_brands": int(
            df["brand"].nunique() if "brand" in df.columns else 0
        ),
        "unique_families": int(
            df["accords"].nunique() if "accords" in df.columns else 0
        ),
        "avg_rating": float(
            df["rating"].mean() if "rating" in df.columns else 0
        ),
    }
