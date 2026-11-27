"""
YORVYN Intelligence Platform (YIP) — Unified Fashion Recommendation & Ranking Engine.

Implements:
- Configurable, versioned multi-signal ranking presets (never hardcoded un-evaluated magic)
- Normalized 10-dimension scoring across content, category affinity, visual similarity,
  style compatibility, gated collaborative filtering, session context, availability,
  MMR category diversity, novelty, and freshness
- Cold-start handling (explicitly flags cold_start_mode without fabricating profiles)
- Evidence-grounded explainability (reasons only shown when backed by actual factor scores)
- Outfit composition, complementary pairings, wardrobe gap detection, and optional RAG rationale
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from backend.app.services.intelligence.inference_adapters import inference_telemetry
from backend.app.services.intelligence.knowledge_rag import KnowledgeDomain, knowledge_rag
from backend.app.services.intelligence.recommendation_algorithms import (
    AdapterCandidateScore,
    CategoryAffinityAdapter,
    CollaborativeFilteringAdapter,
    CollaborativeStatus,
    ContentBasedAdapter,
    ExplorationDiversityAdapter,
    NeuralRecommendationAdapter,
    SessionContextAdapter,
    VisualSimilarityAdapter,
)
from backend.app.services.intelligence.recommendation_profile import (
    PreferenceProfileStore,
    recommendation_profile_store,
)
from backend.app.services.intelligence.recommendation_taxonomy import (
    CANONICAL_CATEGORIES,
    RecommendationGarmentAttributes,
    normalize_item,
)
from backend.app.services.ml.skin_colour_intelligence import skin_colour_intelligence_service
from backend.app.services.wardrobe_intelligence_service import wardrobe_intelligence_service
from backend.app.services.wardrobe_service import DEFAULT_WARDROBE_ITEMS, WardrobeService


class RankingWeightsConfig(BaseModel):
    version: str = "17.0-rec-v1"
    preset_name: str = "hybrid_balanced"
    user_preference_relevance: float = 0.22
    category_affinity: float = 0.16
    visual_similarity: float = 0.10
    style_compatibility: float = 0.14
    collaborative_relevance: float = 0.10
    contextual_relevance: float = 0.12
    item_availability: float = 0.04
    diversity: float = 0.05
    novelty: float = 0.04
    freshness: float = 0.03


RANKING_WEIGHT_PRESETS: Dict[str, RankingWeightsConfig] = {
    "hybrid_balanced": RankingWeightsConfig(preset_name="hybrid_balanced", version="17.0-rec-v1"),
    "content_focus": RankingWeightsConfig(
        preset_name="content_focus",
        version="17.0-rec-content-v1",
        user_preference_relevance=0.36,
        category_affinity=0.22,
        visual_similarity=0.14,
        style_compatibility=0.14,
        collaborative_relevance=0.0,
        contextual_relevance=0.08,
        item_availability=0.02,
        diversity=0.02,
        novelty=0.01,
        freshness=0.01,
    ),
    "exploration_discovery": RankingWeightsConfig(
        preset_name="exploration_discovery",
        version="17.0-rec-explore-v1",
        user_preference_relevance=0.16,
        category_affinity=0.08,
        visual_similarity=0.10,
        style_compatibility=0.16,
        collaborative_relevance=0.10,
        contextual_relevance=0.12,
        item_availability=0.04,
        diversity=0.11,
        novelty=0.09,
        freshness=0.04,
    ),
    "cold_start": RankingWeightsConfig(
        preset_name="cold_start",
        version="17.0-rec-coldstart-v1",
        user_preference_relevance=0.10,
        category_affinity=0.05,
        visual_similarity=0.12,
        style_compatibility=0.20,
        collaborative_relevance=0.05,
        contextual_relevance=0.22,
        item_availability=0.08,
        diversity=0.08,
        novelty=0.05,
        freshness=0.05,
    ),
}


class RecommendationReason(BaseModel):
    code: str
    message: str
    supporting_signal: str
    signal_value: float


class RankedRecommendationItem(BaseModel):
    item_id: str
    name: str
    category: str
    subcategory: str
    color: str
    style: List[str] = Field(default_factory=list)
    fit: str = "regular"
    material: str = "cotton"
    image_url: Optional[str] = None
    final_score: float
    normalized_signals: Dict[str, float] = Field(default_factory=dict)
    reasons: List[RecommendationReason] = Field(default_factory=list)
    is_exploration: bool = False


class RecommendationResponse(BaseModel):
    owner_id: str
    surface: str
    algorithm_mode: str
    ranking_version: str
    preset_used: str
    consent_granted: bool
    cold_start_mode: bool
    profile_fabricated: bool = False
    neural_active: bool = False
    neural_fallback_used: bool = False
    collaborative_status: CollaborativeStatus
    recommendations: List[RankedRecommendationItem] = Field(default_factory=list)
    category_recommendations: Dict[str, float] = Field(default_factory=dict)
    knowledge_notes: List[str] = Field(default_factory=list)
    latency_ms: float = 0.0


class ComplementarySuggestion(BaseModel):
    slot: str
    item: RankedRecommendationItem
    compatibility_prediction: float
    reason: str


class OutfitRecommendationBundle(BaseModel):
    outfit_id: str
    title: str
    items: List[RankedRecommendationItem]
    compatibility_prediction: float
    compatibility_is_prediction_not_rule: bool = True
    compatibility_backend: str = "algorithmic_pairwise"
    neural_compatibility_used: bool = False
    color_harmony_score: float
    style_compatibility_score: float
    occasion: str
    rationale: List[str] = Field(default_factory=list)


class OutfitRecommendationResponse(BaseModel):
    owner_id: str
    occasion: str
    anchor_item_id: Optional[str] = None
    compatibility_is_prediction_not_rule: bool = True
    compatibility_backend: str = "algorithmic_pairwise"
    neural_compatibility_used: bool = False
    outfits: List[OutfitRecommendationBundle] = Field(default_factory=list)
    complementary_items: List[ComplementarySuggestion] = Field(default_factory=list)
    wardrobe_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    knowledge_guidance: List[str] = Field(default_factory=list)
    latency_ms: float = 0.0


class FashionRecommendationEngine:
    """Unified multi-algorithm recommendation coordinator integrated with YIP."""

    def __init__(
        self,
        profile_store: Optional[PreferenceProfileStore] = None,
        wardrobe_svc: Optional[WardrobeService] = None,
        neural_adapter: Optional[NeuralRecommendationAdapter] = None,
    ) -> None:
        self.profile_store = profile_store or recommendation_profile_store
        self.wardrobe_svc = wardrobe_svc or WardrobeService()
        self.content_adapter = ContentBasedAdapter()
        self.cf_adapter = CollaborativeFilteringAdapter()
        self.category_adapter = CategoryAffinityAdapter()
        self.visual_adapter = VisualSimilarityAdapter()
        self.session_adapter = SessionContextAdapter()
        self.explore_adapter = ExplorationDiversityAdapter()
        self.neural_adapter = neural_adapter or NeuralRecommendationAdapter()

    def get_neural_embeddings_and_retrieval(
        self,
        *,
        owner_id: str,
        candidates: Optional[List[Dict[str, Any]]] = None,
        top_k: int = 8,
    ) -> Dict[str, Any]:
        uid = str(owner_id)
        if not self.profile_store.get_consent(uid):
            return {
                "owner_id": uid,
                "consent_granted": False,
                "neural_available": False,
                "user_embedding": None,
                "item_embeddings": {},
                "retrieved": [],
                "fallback_used": True,
            }
        profile = self.profile_store.get_profile(uid)
        norm_cands = self._resolve_candidates(owner_id=uid, candidates=candidates)
        pos_ids = set(profile.saved_item_ids) | set(profile.liked_item_ids)
        pos_items = [c for c in norm_cands if c.item_id in pos_ids]
        ok, u_emb, i_embs = self.neural_adapter.compute_embeddings(
            profile=profile, candidates=norm_cands, positive_items=pos_items
        )
        rec_res = self.recommend(
            owner_id=uid,
            candidates=candidates,
            mode="neural_retrieval",
            top_k=top_k,
        )
        return {
            "owner_id": uid,
            "consent_granted": True,
            "neural_available": ok,
            "embedding_dim": len(u_emb) if u_emb else 0,
            "user_embedding": u_emb,
            "item_embeddings": i_embs,
            "retrieved": [r.model_dump() for r in rec_res.recommendations],
            "fallback_used": not ok,
        }

    def _resolve_candidates(
        self,
        *,
        owner_id: str,
        candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> List[RecommendationGarmentAttributes]:
        if candidates is not None:
            raw_list = candidates
        else:
            # Strict owner isolation: merge user's owned items + curated public catalog defaults
            user_items = self.wardrobe_svc.get_wardrobe(user_id=owner_id)
            raw_list = [
                it for it in user_items
                if str(it.get("user_id") or owner_id) == str(owner_id)
            ]
            if not raw_list:
                raw_list = list(DEFAULT_WARDROBE_ITEMS)
        seen_ids: Set[str] = set()
        out: List[RecommendationGarmentAttributes] = []
        for raw in raw_list:
            item = normalize_item(raw)
            if item.owner_id and item.owner_id != str(owner_id):
                continue  # Never leak another owner's private garment into candidate pool
            if item.item_id in seen_ids:
                continue
            seen_ids.add(item.item_id)
            out.append(item)
        return out

    def recommend(
        self,
        *,
        owner_id: str,
        candidates: Optional[List[Dict[str, Any]]] = None,
        mode: str = "hybrid",
        surface: str = "wardrobe",
        session_id: Optional[str] = None,
        occasion: Optional[str] = None,
        season: Optional[str] = None,
        search_query: Optional[str] = None,
        anchor_item: Optional[Dict[str, Any]] = None,
        query_embedding: Optional[List[float]] = None,
        preset_name: Optional[str] = None,
        custom_weights: Optional[RankingWeightsConfig] = None,
        top_k: int = 8,
        exploration_rate: float = 0.25,
        include_knowledge: bool = False,
        consent_granted: Optional[bool] = None,
        min_cf_users: Optional[int] = None,
        before_timestamp_s: Optional[float] = None,
        reference_time_s: Optional[float] = None,
    ) -> RecommendationResponse:
        t0 = time.perf_counter()
        uid = str(owner_id)
        stored_consent = self.profile_store.get_consent(uid)
        consent = stored_consent if consent_granted is None else bool(consent_granted and stored_consent)
        profile = self.profile_store.get_profile(
            uid,
            reference_time_s=reference_time_s,
            before_timestamp_s=before_timestamp_s,
        )
        session = (
            self.profile_store.get_or_create_session(uid, session_id)
            if session_id
            else None
        )

        # Resolve CF adapter (allow benchmark override for min users, default 5)
        cf_adapter = (
            CollaborativeFilteringAdapter(min_users=min_cf_users)
            if min_cf_users is not None
            else self.cf_adapter
        )
        all_user_pos = self.profile_store.get_all_owner_positive_items(
            min_positive_interactions=cf_adapter.min_interactions_per_user
        )

        norm_candidates = self._resolve_candidates(owner_id=uid, candidates=candidates)
        if not consent:
            cf_status = cf_adapter.check_eligibility(all_user_pos)
            return RecommendationResponse(
                owner_id=uid,
                surface=surface,
                algorithm_mode=mode,
                ranking_version="17.0-rec-v1",
                preset_used="consent_disabled_popular_only",
                consent_granted=False,
                cold_start_mode=True,
                profile_fabricated=False,
                collaborative_status=cf_status,
                recommendations=[],
                knowledge_notes=["Personalization disabled by user consent setting."],
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            )

        if not norm_candidates:
            cf_status = cf_adapter.check_eligibility(all_user_pos)
            return RecommendationResponse(
                owner_id=uid,
                surface=surface,
                algorithm_mode=mode,
                ranking_version="17.0-rec-v1",
                preset_used=preset_name or "hybrid_balanced",
                consent_granted=consent,
                cold_start_mode=profile.is_cold_start,
                profile_fabricated=False,
                collaborative_status=cf_status,
                recommendations=[],
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
            )

        pos_ids = set(profile.saved_item_ids) | set(profile.liked_item_ids)
        positive_items = [c for c in norm_candidates if c.item_id in pos_ids]
        anchor_norm = normalize_item(anchor_item) if anchor_item else (
            normalize_item(session.anchor_garment) if (session and session.anchor_garment) else None
        )

        # Compute independent algorithm signals
        content_scores = self.content_adapter.score_candidates(
            norm_candidates,
            profile=profile,
            positive_items=positive_items,
            anchor_item=anchor_norm,
        )
        cat_scores = self.category_adapter.score_candidates(norm_candidates, profile=profile)
        cf_status, cf_scores = cf_adapter.score_candidates(
            target_user_id=uid,
            candidates=norm_candidates,
            all_user_positives=all_user_pos,
        )
        vis_scores = self.visual_adapter.score_candidates(
            norm_candidates,
            query_embedding=query_embedding,
            positive_items=positive_items,
        )
        sess_scores = self.session_adapter.score_candidates(
            norm_candidates,
            session=session,
            occasion=occasion,
            season=season,
            search_query=search_query,
        )
        explore_scores = self.explore_adapter.score_candidates(
            norm_candidates,
            profile=profile,
            all_positive_items=positive_items,
            exploration_rate=exploration_rate,
        )

        mode_l = (mode or "hybrid").lower()
        neural_requested = mode_l in {"neural_retrieval", "neural_ranking", "neural_sequential", "neural_hybrid"}
        neural_active = False
        neural_fallback_used = False
        neural_scores: Dict[str, AdapterCandidateScore] = {}
        neural_seq_scores: Dict[str, AdapterCandidateScore] = {}

        if neural_requested:
            use_ranker = mode_l in {"neural_ranking", "neural_hybrid"}
            n_ok, neural_scores = self.neural_adapter.score_candidates(
                norm_candidates,
                profile=profile,
                positive_items=positive_items,
                category_scores=cat_scores,
                visual_scores=vis_scores,
                context_scores=sess_scores,
                explore_scores=explore_scores,
                use_ranker=use_ranker,
            )
            if mode_l == "neural_sequential":
                hist_pos = [
                    normalize_item(r.attributes)
                    for r in self.profile_store.get_interactions(uid, before_timestamp_s=before_timestamp_s)
                    if r.interaction_type in {"liked", "saved", "outfit_selected", "worn", "repeated_selection"}
                    and r.attributes
                ]
                ts_pos = [
                    r.timestamp_s
                    for r in self.profile_store.get_interactions(uid, before_timestamp_s=before_timestamp_s)
                    if r.interaction_type in {"liked", "saved", "outfit_selected", "worn", "repeated_selection"}
                    and r.attributes
                ]
                seq_ok, neural_seq_scores = self.neural_adapter.score_sequence(
                    norm_candidates, positive_history=hist_pos, timestamps_s=ts_pos
                )
                # Short sequences (< MIN_SEQ_LEN_FOR_TRANSFORMER) fall back cleanly to Two-Tower when available
                neural_active = bool(seq_ok or n_ok)
                neural_fallback_used = not seq_ok
            else:
                neural_active = n_ok
                neural_fallback_used = not neural_active

        eff_preset = preset_name or ("cold_start" if profile.is_cold_start else "hybrid_balanced")
        weights = custom_weights or RANKING_WEIGHT_PRESETS.get(eff_preset, RANKING_WEIGHT_PRESETS["hybrid_balanced"])

        # Popularity normalization for cold-start & collaborative fallback check
        max_pop = max([c.popularity_score for c in norm_candidates] or [1.0]) or 1.0
        pref_colors = profile.explicit_preferences.get("color", []) + list(profile.inferred_preferences.get("color", {}).keys())[:3]
        disliked_colors = profile.explicit_preferences.get("disliked_colors", [])
        eff_occasion = (occasion or (session.active_occasion if session else None) or "casual").lower()

        raw_scored: List[Tuple[float, RankedRecommendationItem]] = []
        for item in norm_candidates:
            c_sc = content_scores[item.item_id]
            k_sc = cat_scores[item.item_id]
            v_sc = vis_scores[item.item_id]
            cf_sc = cf_scores[item.item_id]
            s_sc = sess_scores[item.item_id]
            e_sc = explore_scores[item.item_id]
            n_sc = neural_scores.get(item.item_id)
            sq_sc = neural_seq_scores.get(item.item_id)

            # Style & color compatibility signal using existing skin_colour_intelligence_service
            colour_eval = skin_colour_intelligence_service.evaluate_clothing_colour_harmony(
                [item.color],
                personal_palette="neutral",
                preferred_colors=pref_colors,
                disliked_colors=disliked_colors,
            )
            style_compat = max(0.0, min(1.0, float(colour_eval.get("harmony_score", 78.0)) / 100.0))
            if anchor_norm is not None:
                pair_eval = wardrobe_intelligence_service.evaluate_item_pairing_compatibility(
                    anchor_norm.model_dump(), item.model_dump()
                )
                style_compat = 0.5 * style_compat + 0.5 * float(pair_eval.get("compatibility_score", 0.5))

            pop_norm = max(0.0, min(1.0, item.popularity_score / max_pop)) if max_pop > 0 else 0.5
            pref_rel = (c_sc.score or 0.0) if not profile.is_cold_start else max(c_sc.score or 0.0, 0.5 * pop_norm)
            cat_rel = (k_sc.score or 0.0) if not profile.is_cold_start else (
                0.75 if item.category in {"tops", "bottoms", "outerwear"} else 0.45
            )
            avail_val = 1.0 if item.available else 0.0
            fresh_val = float(e_sc.metadata.get("freshness_component", 0.5))
            novelty_val = float(e_sc.score or 0.5)
            vis_val = float(v_sc.score) if v_sc.available and v_sc.score is not None else 0.0
            cf_val = float(cf_sc.score) if cf_sc.available and cf_sc.score is not None else 0.0
            ctx_val = float(s_sc.score or 0.0)
            neural_val = (
                float(sq_sc.score)
                if (mode_l == "neural_sequential" and sq_sc and sq_sc.available and sq_sc.score is not None)
                else (float(n_sc.score) if (n_sc and n_sc.available and n_sc.score is not None) else 0.0)
            )

            if mode_l == "content":
                total = pref_rel
            elif mode_l == "category":
                total = cat_rel
            elif mode_l == "collaborative":
                total = cf_val if cf_sc.available else 0.0
            elif mode_l in {"neural_retrieval", "neural_ranking", "neural_sequential"} and neural_active:
                total = neural_val
            else:
                # Re-normalize weights across active available channels (and fall back seamlessly if neural weights missing)
                active_terms: List[Tuple[str, float, float]] = [
                    ("user_preference_relevance", weights.user_preference_relevance, pref_rel),
                    ("category_affinity", weights.category_affinity, cat_rel),
                    ("style_compatibility", weights.style_compatibility, style_compat),
                    ("contextual_relevance", weights.contextual_relevance, ctx_val),
                    ("item_availability", weights.item_availability, avail_val),
                    ("novelty", weights.novelty, novelty_val),
                    ("freshness", weights.freshness, fresh_val),
                ]
                if v_sc.available and v_sc.score is not None:
                    active_terms.append(("visual_similarity", weights.visual_similarity, vis_val))
                if cf_sc.available and cf_sc.score is not None:
                    active_terms.append(("collaborative_relevance", weights.collaborative_relevance, cf_val))
                if mode_l == "neural_hybrid" and neural_active:
                    active_terms.append(("neural_score", 0.25, neural_val))

                w_sum = sum(w for _, w, _ in active_terms) or 1.0
                total = sum((w / w_sum) * val for _, w, val in active_terms)

                # Penalize explicit disliked/dismissed items even in hybrid/neural ranking
                if item.item_id in set(profile.disliked_item_ids):
                    total *= 0.05
                elif item.item_id in set(profile.dismissed_item_ids):
                    total *= 0.40

            # Build evidence-grounded reasons (only emit what actually scored cleanly)
            reasons: List[RecommendationReason] = []
            if neural_active:
                active_n_sc = sq_sc if (mode_l == "neural_sequential" and sq_sc and sq_sc.available) else n_sc
                if active_n_sc and active_n_sc.evidence:
                    reasons.append(RecommendationReason(
                        code="neural_preference_alignment",
                        message=active_n_sc.evidence[0],
                        supporting_signal="neural_score",
                        signal_value=round(neural_val, 3),
                    ))
            for msg in c_sc.evidence[:2]:
                code = "similar_color_silhouette" if "silhouette" in msg.lower() else "similar_to_saved"
                reasons.append(RecommendationReason(
                    code=code, message=msg, supporting_signal="user_preference_relevance", signal_value=round(pref_rel, 3)
                ))
            for msg in k_sc.evidence[:1]:
                reasons.append(RecommendationReason(
                    code="preferred_category", message=msg, supporting_signal="category_affinity", signal_value=round(cat_rel, 3)
                ))
            if anchor_norm is not None and style_compat >= 0.72:
                reasons.append(RecommendationReason(
                    code="complements_selected",
                    message=f"Complements '{anchor_norm.name}' ({eff_occasion} context)",
                    supporting_signal="style_compatibility",
                    signal_value=round(style_compat, 3),
                ))
            for msg in cf_sc.evidence[:1]:
                reasons.append(RecommendationReason(
                    code="collaborative_peer_signal", message=msg, supporting_signal="collaborative_relevance", signal_value=round(cf_val, 3)
                ))
            for msg in s_sc.evidence[:1]:
                reasons.append(RecommendationReason(
                    code="session_context", message=msg, supporting_signal="contextual_relevance", signal_value=round(ctx_val, 3)
                ))
            for msg in v_sc.evidence[:1]:
                reasons.append(RecommendationReason(
                    code="visual_similarity", message=msg, supporting_signal="visual_similarity", signal_value=round(vis_val, 3)
                ))
            is_exp = False
            if explore_scores[item.item_id].evidence and novelty_val >= 0.55:
                is_exp = True
                reasons.append(RecommendationReason(
                    code="category_exploration",
                    message=explore_scores[item.item_id].evidence[0],
                    supporting_signal="novelty",
                    signal_value=round(novelty_val, 3),
                ))
            if not reasons:
                if profile.is_cold_start:
                    reasons.append(RecommendationReason(
                        code="cold_start_popular_staple",
                        message=f"Popular versatile '{item.category}' baseline for cold-start discovery",
                        supporting_signal="contextual_relevance",
                        signal_value=round(max(pop_norm, style_compat), 3),
                    ))
                else:
                    reasons.append(RecommendationReason(
                        code="style_harmony",
                        message=f"Balanced {item.color} color harmony and fit alignment",
                        supporting_signal="style_compatibility",
                        signal_value=round(style_compat, 3),
                    ))

            signals_map = {
                "user_preference_relevance": round(pref_rel, 4),
                "category_affinity": round(cat_rel, 4),
                "visual_similarity": round(vis_val, 4),
                "style_compatibility": round(style_compat, 4),
                "collaborative_relevance": round(cf_val, 4),
                "contextual_relevance": round(ctx_val, 4),
                "item_availability": round(avail_val, 4),
                "novelty": round(novelty_val, 4),
                "freshness": round(fresh_val, 4),
                "neural_score": round(neural_val, 4),
            }
            ranked_obj = RankedRecommendationItem(
                item_id=item.item_id,
                name=item.name,
                category=item.category,
                subcategory=item.subcategory,
                color=item.color,
                style=item.style,
                fit=item.fit,
                material=item.material,
                image_url=item.image_url,
                final_score=round(max(0.0, min(1.0, total)), 4),
                normalized_signals=signals_map,
                reasons=reasons,
                is_exploration=is_exp,
            )
            raw_scored.append((ranked_obj.final_score, ranked_obj))

        # Apply MMR-style diversity re-ranking so repeated categories don't monopolize results
        selected: List[RankedRecommendationItem] = []
        pool = [r for _, r in sorted(raw_scored, key=lambda x: x[0], reverse=True)]
        cat_counts: Dict[str, int] = {}
        div_weight = weights.diversity if mode_l in {"hybrid", "exploration"} else 0.05

        while pool and len(selected) < max(1, top_k):
            best_idx = 0
            best_mmr = -1e9
            for idx, cand in enumerate(pool):
                seen_same_cat = cat_counts.get(cand.category, 0)
                diversity_score = 1.0 / (1.0 + seen_same_cat)
                mmr_score = cand.final_score + div_weight * diversity_score - (0.08 * seen_same_cat)
                if mmr_score > best_mmr:
                    best_mmr = mmr_score
                    best_idx = idx
            chosen = pool.pop(best_idx)
            chosen.normalized_signals["diversity"] = round(1.0 / (1.0 + cat_counts.get(chosen.category, 0)), 4)
            cat_counts[chosen.category] = cat_counts.get(chosen.category, 0) + 1
            selected.append(chosen)

        # Aggregate category recommendation summary
        cat_summary: Dict[str, float] = {}
        for c in CANONICAL_CATEGORIES:
            aff = profile.category_affinity.get(c, 0.0)
            if aff > 0:
                cat_summary[c] = round(aff, 4)
        for s_it in selected:
            cat_summary[s_it.category] = max(cat_summary.get(s_it.category, 0.0), s_it.final_score)

        knowledge_notes: List[str] = []
        if include_knowledge and selected:
            try:
                rag_res = knowledge_rag.search(
                    f"{selected[0].category} {selected[0].material} fit drape styling",
                    domains=[KnowledgeDomain.FASHION_STYLING, KnowledgeDomain.FABRIC_AND_TEXTILE],
                    owner_id=uid,
                    verified_only=True,
                    top_k=2,
                )
                knowledge_notes = [h.snippet for h in rag_res.hits]
            except Exception:
                pass

        lat_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        inference_telemetry.record("fashion-recommendation-engine", lat_ms, device="cpu", backend="hybrid_ranking")
        if neural_active:
            tel_id = (
                "sequential_transformer_recommender"
                if mode_l == "neural_sequential"
                else ("neural_ranking_network" if mode_l in {"neural_ranking", "neural_hybrid"} else "two_tower_recommender")
            )
            inference_telemetry.record(tel_id, lat_ms, device="cpu", backend="pytorch")
        return RecommendationResponse(
            owner_id=uid,
            surface=surface,
            algorithm_mode=mode_l,
            ranking_version=weights.version,
            preset_used=weights.preset_name,
            consent_granted=consent,
            cold_start_mode=profile.is_cold_start,
            profile_fabricated=False,
            neural_active=neural_active,
            neural_fallback_used=neural_fallback_used,
            collaborative_status=cf_status,
            recommendations=selected,
            category_recommendations=dict(sorted(cat_summary.items(), key=lambda x: x[1], reverse=True)),
            knowledge_notes=knowledge_notes,
            latency_ms=lat_ms,
        )

    def recommend_outfit(
        self,
        *,
        owner_id: str,
        candidates: Optional[List[Dict[str, Any]]] = None,
        anchor_item: Optional[Dict[str, Any]] = None,
        occasion: str = "casual",
        season: Optional[str] = None,
        max_outfits: int = 3,
    ) -> OutfitRecommendationResponse:
        t0 = time.perf_counter()
        uid = str(owner_id)
        ranked_resp = self.recommend(
            owner_id=uid,
            candidates=candidates,
            mode="hybrid",
            surface="outfit",
            occasion=occasion,
            season=season,
            anchor_item=anchor_item,
            top_k=24,
            include_knowledge=True,
        )
        all_candidates = self._resolve_candidates(owner_id=uid, candidates=candidates)
        by_id = {c.item_id: c for c in all_candidates}
        ranked_by_id = {r.item_id: r for r in ranked_resp.recommendations}

        anchor_norm = normalize_item(anchor_item) if anchor_item else None
        if anchor_norm and anchor_norm.item_id not in ranked_by_id:
            ranked_by_id[anchor_norm.item_id] = RankedRecommendationItem(
                item_id=anchor_norm.item_id,
                name=anchor_norm.name,
                category=anchor_norm.category,
                subcategory=anchor_norm.subcategory,
                color=anchor_norm.color,
                style=anchor_norm.style,
                fit=anchor_norm.fit,
                material=anchor_norm.material,
                image_url=anchor_norm.image_url,
                final_score=1.0,
            )

        tops = [r for r in ranked_resp.recommendations if r.category == "tops"]
        bottoms = [r for r in ranked_resp.recommendations if r.category == "bottoms"]
        dresses = [r for r in ranked_resp.recommendations if r.category == "dresses_and_skirts"]
        outerwear = [r for r in ranked_resp.recommendations if r.category == "outerwear"]
        footwear = [r for r in ranked_resp.recommendations if r.category == "footwear"]

        # Complementary pieces relative to anchor or top item
        ref_item = anchor_norm or (by_id.get(tops[0].item_id) if tops else (all_candidates[0] if all_candidates else None))
        complementary: List[ComplementarySuggestion] = []
        if ref_item is not None:
            for cand_r in ranked_resp.recommendations:
                if cand_r.item_id == ref_item.item_id or cand_r.category == ref_item.category:
                    continue
                pair = wardrobe_intelligence_service.evaluate_item_pairing_compatibility(
                    ref_item.model_dump(), by_id[cand_r.item_id].model_dump()
                )
                pred_score = round(0.55 * float(pair.get("compatibility_score", 0.5)) + 0.45 * cand_r.final_score, 4)
                complementary.append(ComplementarySuggestion(
                    slot=cand_r.category,
                    item=cand_r,
                    compatibility_prediction=pred_score,
                    reason=f"Color ({pair.get('color_score', 0.8):.2f}) & style alignment with {ref_item.name}",
                ))
            complementary.sort(key=lambda c: c.compatibility_prediction, reverse=True)

        # Compose complete candidate outfits cleanly
        outfits: List[OutfitRecommendationBundle] = []
        base_combos: List[List[RankedRecommendationItem]] = []
        if anchor_norm and anchor_norm.item_id in ranked_by_id:
            a_r = ranked_by_id[anchor_norm.item_id]
            for b in bottoms[:2] if anchor_norm.category != "bottoms" else tops[:2]:
                combo = [a_r, b]
                if outerwear and anchor_norm.category != "outerwear":
                    combo.append(outerwear[0])
                if footwear and anchor_norm.category != "footwear":
                    combo.append(footwear[0])
                base_combos.append(combo)
        else:
            for t in tops[:2]:
                for b in bottoms[:2]:
                    combo = [t, b]
                    if outerwear:
                        combo.append(outerwear[0])
                    if footwear:
                        combo.append(footwear[0])
                    base_combos.append(combo)
            for d in dresses[:1]:
                combo = [d]
                if outerwear:
                    combo.append(outerwear[0])
                if footwear:
                    combo.append(footwear[0])
                base_combos.append(combo)

        any_neural_outfit = False
        for idx, combo in enumerate(base_combos[:max(1, max_outfits)]):
            cols = [c.color for c in combo]
            c_eval = skin_colour_intelligence_service.evaluate_clothing_colour_harmony(
                cols,
                personal_palette="neutral",
                preferred_colors=[],
                disliked_colors=[],
            )
            colour_h = round(float(c_eval.get("harmony_score", 82.0)) / 100.0, 4)
            pair_scores: List[float] = []
            for i in range(len(combo)):
                for j in range(i + 1, len(combo)):
                    d_a = by_id[combo[i].item_id].model_dump() if combo[i].item_id in by_id else combo[i].model_dump()
                    d_b = by_id[combo[j].item_id].model_dump() if combo[j].item_id in by_id else combo[j].model_dump()
                    pe = wardrobe_intelligence_service.evaluate_item_pairing_compatibility(d_a, d_b)
                    pair_scores.append(float(pe.get("compatibility_score", 0.75)))
            style_c = round(sum(pair_scores) / len(pair_scores), 4) if pair_scores else 0.8
            avg_rank = sum(c.final_score for c in combo) / len(combo)

            combo_norm = [by_id[c.item_id] if c.item_id in by_id else normalize_item(c.model_dump()) for c in combo]
            n_compat_ok, n_compat_prob, _ = self.neural_adapter.score_outfit_compatibility(combo_norm)
            if n_compat_ok and n_compat_prob is not None:
                any_neural_outfit = True
                comp_pred = round(0.45 * float(n_compat_prob) + 0.30 * avg_rank + 0.15 * style_c + 0.10 * colour_h, 4)
                c_backend = "neural_outfit_compatibility"
                rationale = [
                    f"Neural outfit compatibility model predicted {round(n_compat_prob * 100)}% probabilistic cohesion",
                    f"Estimated color harmony {round(colour_h * 100)}% across {', '.join(cols)}",
                ]
            else:
                comp_pred = round(0.45 * avg_rank + 0.30 * style_c + 0.25 * colour_h, 4)
                c_backend = "algorithmic_pairwise"
                rationale = [
                    f"Estimated color harmony {round(colour_h * 100)}% across {', '.join(cols)}",
                    f"Pairwise style/formality prediction {round(style_c * 100)}% (probabilistic ranking score)",
                ]

            outfits.append(OutfitRecommendationBundle(
                outfit_id=f"outfit_{idx + 1}",
                title=f"{occasion.title()} {' & '.join(c.subcategory.replace('_', ' ').title() for c in combo[:2])}",
                items=combo,
                compatibility_prediction=comp_pred,
                compatibility_backend=c_backend,
                neural_compatibility_used=bool(n_compat_ok),
                color_harmony_score=colour_h,
                style_compatibility_score=style_c,
                occasion=occasion,
                rationale=rationale,
            ))

        # Reuse wardrobe intelligence service gap analysis normalized for recommendation categories
        present_cats = {c.category for c in all_candidates}
        gaps: List[Dict[str, Any]] = []
        for req_cat in ("tops", "bottoms", "outerwear", "footwear"):
            if req_cat not in present_cats:
                gaps.append({
                    "missing_category": req_cat,
                    "severity": "high" if req_cat in {"tops", "bottoms"} else "medium",
                    "suggestion": f"Add a versatile {req_cat.rstrip('s')} piece to expand complete {occasion} outfit options.",
                })
        if occasion.lower() in {"formal", "work", "business"} and all(c.formality < 6 for c in all_candidates):
            gaps.append({
                "missing_category": "formalwear",
                "severity": "medium",
                "suggestion": "Adding tailored outerwear or structured trousers would unlock higher-formality looks.",
            })

        return OutfitRecommendationResponse(
            owner_id=uid,
            occasion=occasion,
            anchor_item_id=anchor_norm.item_id if anchor_norm else None,
            compatibility_backend="neural_outfit_compatibility" if any_neural_outfit else "algorithmic_pairwise",
            neural_compatibility_used=any_neural_outfit,
            outfits=outfits,
            complementary_items=complementary[:5],
            wardrobe_gaps=gaps,
            knowledge_guidance=ranked_resp.knowledge_notes,
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )


fashion_recommendation_engine = FashionRecommendationEngine()
