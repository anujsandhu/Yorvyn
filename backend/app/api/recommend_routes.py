"""
POST /recommend — Data-first fragrance recommendation endpoint.

Pipeline:
  1. Normalize & validate input
  2. Filter dataset by gender + at least 1 note match (≤500 candidates)
  3. Score each candidate with deterministic formula
  4. Return top 5–10 ranked matches
  5. Send top 3–5 to LLM for clean UI formatting only

Scoring formula:
  score = (note_match * 0.4) + (accord_match * 0.2)
        + (occasion_match * 0.2) + (season_match * 0.1)
        + (rating_normalized * 0.1)

Caching: identical query → cached result (TTL = 1 hour)
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ..ml_model import recommender, clean_accords, normalize_gender
from ..ai_fallback import (
    _call_groq_text,
    _call_openrouter_text,
    settings,
)

# Optional auth — gracefully degrade if firebase_admin not available
try:
    from ..auth import get_current_user_optional, UserContext as AuthUserContext
    _auth_available = True
except ImportError:
    _auth_available = False
    AuthUserContext = None  # type: ignore
    async def get_current_user_optional(request=None):  # type: ignore
        return None

router = APIRouter()

# ── Cache (TTL = 1 hour) ──────────────────────────────────────────────
_recommend_cache: Dict[str, Dict] = {}
_CACHE_TTL = 3600  # seconds


def _cache_key(payload: Dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.md5(canonical.encode()).hexdigest()


def _cache_get(key: str) -> Optional[Dict]:
    entry = _recommend_cache.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data: Dict) -> None:
    # Evict stale entries if cache grows large
    if len(_recommend_cache) > 1000:
        cutoff = time.time() - _CACHE_TTL
        stale = [k for k, v in _recommend_cache.items() if v["ts"] < cutoff]
        for k in stale:
            del _recommend_cache[k]
    _recommend_cache[key] = {"data": data, "ts": time.time()}
# ── Occasion / Season hint maps ───────────────────────────────────────
OCCASION_NOTES: Dict[str, tuple] = {
    "office":  ("fresh", "clean", "green", "citrus", "musk", "aromatic"),
    "work":    ("fresh", "clean", "green", "citrus", "musk", "aromatic"),
    "daily":   ("fresh", "clean", "soft", "citrus", "aromatic", "light"),
    "date":    ("rose", "vanilla", "amber", "musk", "sweet", "sensual"),
    "night":   ("amber", "oud", "vanilla", "spicy", "woody", "dark"),
    "party":   ("amber", "oud", "sweet", "spicy", "woody", "bold"),
    "wedding": ("rose", "white floral", "musk", "vanilla", "elegant"),
    "gym":     ("fresh", "aquatic", "clean", "citrus", "sport"),
    "outdoor": ("green", "woody", "fresh", "earthy", "citrus"),
}

SEASON_NOTES: Dict[str, tuple] = {
    "summer":  ("citrus", "aquatic", "fresh", "green", "light"),
    "spring":  ("floral", "fresh", "green", "citrus", "light"),
    "winter":  ("amber", "vanilla", "oud", "spicy", "woody", "warm"),
    "autumn":  ("woody", "amber", "spicy", "earthy", "leather"),
    "fall":    ("woody", "amber", "spicy", "earthy", "leather"),
    "monsoon": ("fresh", "green", "woody", "clean", "earthy"),
}


# ── Schemas ───────────────────────────────────────────────────────────

class RecommendRequest(BaseModel):
    notes: List[str] = Field(..., min_items=1, description="Preferred fragrance notes")
    occasion: Optional[str] = Field(None, description="e.g. party, office, date, daily")
    season: Optional[str] = Field(None, description="e.g. winter, summer, spring, autumn")
    gender: Optional[str] = Field(None, description="men | women | unisex")
    intensity: Optional[str] = Field(None, description="light | moderate | strong")
    limit: int = Field(default=8, ge=1, le=20)


class MatchedPerfume(BaseModel):
    rank: int
    name: str
    brand: str
    notes: List[str]
    accords: List[str]
    rating: float
    score: float
    why_match: List[str]
    gender: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    description: Optional[str] = None


class RecommendResponse(BaseModel):
    matches: List[MatchedPerfume]
    llm_reply: Optional[str] = None
    total_candidates: int
    cached: bool = False


# ── Helpers ───────────────────────────────────────────────────────────

def _normalize_notes(raw: Any) -> List[str]:
    """Convert any notes/accords field to a clean lowercase list."""
    if not raw:
        return []
    text = re.sub(r"[\[\]'\"{}()]", " ", str(raw))
    text = text.replace(",", " ")
    tokens = [t.strip().lower() for t in text.split() if len(t.strip()) > 1]
    return list(dict.fromkeys(tokens))  # deduplicate, preserve order


def _token_overlap(query_tokens: List[str], target_tokens: List[str]) -> float:
    """Fraction of query tokens found in target (0.0–1.0)."""
    if not query_tokens or not target_tokens:
        return 0.0
    target_set = set(target_tokens)
    hits = sum(1 for t in query_tokens if t in target_set)
    return hits / len(query_tokens)


def _context_match(query_tokens: List[str], hint_tokens: tuple) -> float:
    """How well query tokens align with occasion/season hints."""
    if not hint_tokens:
        return 0.0
    hint_set = set(hint_tokens)
    hits = sum(1 for t in query_tokens if t in hint_set)
    return min(1.0, hits / max(1, len(hint_tokens) * 0.4))


def _score_perfume(
    row_notes: List[str],
    row_accords: List[str],
    rating: float,
    query_notes: List[str],
    occasion_hints: tuple,
    season_hints: tuple,
) -> float:
    """
    Deterministic scoring formula:
      score = (note_match * 0.4) + (accord_match * 0.2)
            + (occasion_match * 0.2) + (season_match * 0.1)
            + (rating_normalized * 0.1)
    """
    note_match = _token_overlap(query_notes, row_notes + row_accords)
    accord_match = _token_overlap(query_notes, row_accords)
    occasion_match = _context_match(row_notes + row_accords, occasion_hints)
    season_match = _context_match(row_notes + row_accords, season_hints)
    rating_norm = min(1.0, max(0.0, rating / 5.0))

    return (
        note_match    * 0.4
        + accord_match  * 0.2
        + occasion_match * 0.2
        + season_match  * 0.1
        + rating_norm   * 0.1
    )


def _build_why_match(
    row_notes: List[str],
    row_accords: List[str],
    query_notes: List[str],
    occasion: Optional[str],
    season: Optional[str],
    rating: float,
) -> List[str]:
    """Generate human-readable match reasons."""
    reasons: List[str] = []
    all_row = set(row_notes + row_accords)

    matched_notes = [n for n in query_notes if n in all_row]
    if matched_notes:
        reasons.append(f"matches {', '.join(matched_notes[:3])}")

    if occasion:
        hints = set(OCCASION_NOTES.get(occasion.lower(), ()))
        if hints & all_row:
            reasons.append(f"good for {occasion}")

    if season:
        hints = set(SEASON_NOTES.get(season.lower(), ()))
        if hints & all_row:
            reasons.append(f"suits {season}")

    if rating >= 4.3:
        reasons.append(f"highly rated ({rating:.1f}★)")

    return reasons or ["matches your profile"]


# ── LLM formatting layer ──────────────────────────────────────────────

_LLM_SYSTEM = """You are a fragrance recommendation assistant inside a production UI.
This is a DATA-FIRST system. The dataset is the source of truth.
The backend already ranked the perfumes (best → worst).
Do NOT re-rank, filter, or add new items.

OUTPUT FORMAT (strict):
✨ Top Pick — <Name> by <Brand>
<Line 1: specific notes/accords>
<Line 2: occasion + season + vibe>

🔁 Alternatives
• <Name> by <Brand> — 1 short line
• <Name> by <Brand> — 1 short line

🎯 Refine
<ONE short question to narrow preference>

RULES: max ~100 words total, no long paragraphs, no generic phrases like "luxurious" or "commands the room"."""


def _format_with_llm(
    user_profile: Dict,
    top_matches: List[Dict],
) -> Optional[str]:
    """Send top 3–5 matches to LLM for clean UI formatting only."""
    if not top_matches:
        return None

    dataset_payload = [
        {
            "rank": m["rank"],
            "name": m["name"],
            "brand": m["brand"],
            "notes": m["notes"][:5],
            "accords": m["accords"][:5],
            "rating": m["rating"],
        }
        for m in top_matches[:5]
    ]

    prompt = (
        "USER PROFILE:\n"
        + json.dumps(user_profile, indent=2)
        + "\n\nMATCHED PERFUMES (already ranked, best → worst):\n"
        + json.dumps(dataset_payload, indent=2)
        + "\n\nPresent the top pick and alternatives in the required format."
    )

    messages = [
        {"role": "system", "content": _LLM_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    if settings.has_groq:
        try:
            return _call_groq_text(messages)
        except Exception as e:
            print(f"LLM format (groq) failed: {e}")

    if settings.has_openrouter:
        try:
            return _call_openrouter_text(messages)
        except Exception as e:
            print(f"LLM format (openrouter) failed: {e}")

    return None


# ── Main endpoint ─────────────────────────────────────────────────────

@router.post("/recommend", response_model=RecommendResponse)
def recommend(
    req: RecommendRequest,
    auth_user: Optional[AuthUserContext] = Depends(get_current_user_optional),
):
    """
    Data-first fragrance recommendation.

    1. Filter by gender + note overlap
    2. Score with deterministic formula
    3. Return top matches + LLM-formatted reply

    Cache is scoped per user (uid) so results never bleed across accounts.
    """
    # ── Guard: model must be ready ────────────────────────────────────
    if recommender.data is None or len(recommender.data) == 0:
        raise HTTPException(status_code=503, detail="Dataset not loaded yet.")

    # ── Normalize inputs ──────────────────────────────────────────────
    query_notes = [n.strip().lower() for n in req.notes if n.strip()]
    if not query_notes:
        raise HTTPException(status_code=400, detail="At least one note is required.")

    gender_filter = normalize_gender(req.gender) if req.gender else None
    occasion_lower = req.occasion.strip().lower() if req.occasion else None
    season_lower = req.season.strip().lower() if req.season else None

    occasion_hints = OCCASION_NOTES.get(occasion_lower, ()) if occasion_lower else ()
    season_hints = SEASON_NOTES.get(season_lower, ()) if season_lower else ()

    # ── Cache check — scoped by uid to prevent cross-user leakage ────
    uid_prefix = auth_user.user_id if auth_user else "anon"
    cache_payload = {
        "uid": uid_prefix,
        "notes": sorted(query_notes),
        "occasion": occasion_lower,
        "season": season_lower,
        "gender": gender_filter,
        "limit": req.limit,
    }
    ck = _cache_key(cache_payload)
    cached = _cache_get(ck)
    if cached:
        return RecommendResponse(**cached, cached=True)

    # ── Step 1: Filter by gender ──────────────────────────────────────
    df = recommender.data.copy()

    if gender_filter and gender_filter != "unisex":
        gender_mask = df["gender"].isin([gender_filter, "unisex"])
        df = df[gender_mask]

    if df.empty:
        df = recommender.data.copy()  # fallback: ignore gender filter

    # ── Step 2: Filter by at least 1 note match (fast pre-filter) ────
    query_set = set(query_notes)

    def _has_note_match(row_accords: Any) -> bool:
        tokens = set(_normalize_notes(row_accords))
        return bool(tokens & query_set)

    note_mask = df["accords"].apply(_has_note_match)
    candidates = df[note_mask].copy()

    # Fallback: if too few candidates, relax to full gender-filtered set
    if len(candidates) < 20:
        candidates = df.copy()

    # Limit to top 500 candidates before scoring (performance guard)
    if len(candidates) > 500:
        # Pre-sort by rating to keep quality candidates
        candidates = candidates.nlargest(500, "rating")

    # ── Step 3: Score candidates ──────────────────────────────────────
    scores: List[float] = []
    for _, row in candidates.iterrows():
        row_notes = _normalize_notes(row.get("accords", ""))
        row_accords = _normalize_notes(row.get("accords", ""))
        try:
            rating = float(row.get("rating", 4.0) or 4.0)
        except (TypeError, ValueError):
            rating = 4.0

        s = _score_perfume(
            row_notes=row_notes,
            row_accords=row_accords,
            rating=rating,
            query_notes=query_notes,
            occasion_hints=occasion_hints,
            season_hints=season_hints,
        )
        scores.append(s)

    candidates = candidates.copy()
    candidates["_score"] = scores

    # ── Step 4: Rank and select top N ─────────────────────────────────
    top_df = candidates.nlargest(req.limit, "_score")

    matches: List[MatchedPerfume] = []
    top_dicts: List[Dict] = []

    for rank, (_, row) in enumerate(top_df.iterrows(), start=1):
        row_notes = _normalize_notes(row.get("accords", ""))
        row_accords = _normalize_notes(row.get("accords", ""))
        try:
            rating = float(row.get("rating", 4.0) or 4.0)
        except (TypeError, ValueError):
            rating = 4.0

        why = _build_why_match(
            row_notes=row_notes,
            row_accords=row_accords,
            query_notes=query_notes,
            occasion=occasion_lower,
            season=season_lower,
            rating=rating,
        )

        perfume = MatchedPerfume(
            rank=rank,
            name=str(row.get("name", "Unknown")),
            brand=str(row.get("brand", "Unknown")),
            notes=row_notes[:8],
            accords=row_accords[:8],
            rating=round(rating, 2),
            score=round(float(row["_score"]), 4),
            why_match=why,
            gender=str(row.get("gender", "unisex")),
            price=float(row.get("price", 0) or 0) or None,
            image_url=str(row.get("image_url", "")) or None,
            description=str(row.get("description", ""))[:200] or None,
        )
        matches.append(perfume)
        top_dicts.append(perfume.dict())

    if not matches:
        return RecommendResponse(
            matches=[],
            llm_reply="No strong matches found — try refining your preferences.",
            total_candidates=len(candidates),
            cached=False,
        )

    # ── Step 5: LLM formatting (top 3–5 only) ────────────────────────
    user_profile = {
        "notes": query_notes,
        "occasion": occasion_lower,
        "season": season_lower,
        "gender": gender_filter,
        "intensity": req.intensity,
    }
    llm_reply = _format_with_llm(user_profile, top_dicts)

    # ── Cache and return ──────────────────────────────────────────────
    result_data = {
        "matches": [m.dict() for m in matches],
        "llm_reply": llm_reply,
        "total_candidates": len(candidates),
    }
    _cache_set(ck, result_data)

    return RecommendResponse(
        matches=matches,
        llm_reply=llm_reply,
        total_candidates=len(candidates),
        cached=False,
    )
