"""
YORVYN Intelligence Platform (YIP) — Independent Recommendation Algorithm Adapters.

Implements clean, composable algorithm adapters operating over normalized
RecommendationGarmentAttributes and owner-isolated UserPreferenceProfile:
- ContentBasedAdapter (metadata, taxonomy, attribute & embedding similarity)
- CollaborativeFilteringAdapter (privacy-preserving implicit CF, strictly gated on multi-user thresholds)
- CategoryAffinityAdapter (time-decayed category & subcategory affinity)
- VisualSimilarityAdapter (verified local DINOv2 / CLIP cosine proximity with explicit semantic disclaimer)
- SessionContextAdapter (ephemeral session context without permanent weak-signal profile drift)
- ExplorationDiversityAdapter (category/style novelty & anti-saturation exploration)
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
from pydantic import BaseModel, Field

from backend.app.services.intelligence.recommendation_profile import (
    SessionBrowsingContext,
    UserPreferenceProfile,
)
from backend.app.services.intelligence.recommendation_taxonomy import (
    CANONICAL_CATEGORIES,
    RecommendationGarmentAttributes,
)


class AdapterCandidateScore(BaseModel):
    item_id: str
    score: Optional[float] = None
    available: bool = True
    evidence: List[str] = Field(default_factory=list)
    matched_attributes: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CollaborativeStatus(BaseModel):
    eligible: bool
    active_user_count: int
    min_users_required: int
    min_interactions_per_user: int
    reason: str
    privacy_mode: str = "aggregated_anonymous_item_cooccurrence"


def _cosine_l2(vec_a: List[float], vec_b: List[float]) -> Optional[float]:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return None
    a = np.asarray(vec_a, dtype=np.float32)
    b = np.asarray(vec_b, dtype=np.float32)
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na <= 1e-8 or nb <= 1e-8:
        return None
    cos = float(np.dot(a, b) / (na * nb))
    # Map cosine [-1, 1] cleanly into [0, 1]
    return max(0.0, min(1.0, (cos + 1.0) * 0.5))


class ContentBasedAdapter:
    """Recommends items matching user positive explicit & inferred attributes and anchor references."""

    def score_candidates(
        self,
        candidates: List[RecommendationGarmentAttributes],
        *,
        profile: UserPreferenceProfile,
        positive_items: Optional[List[RecommendationGarmentAttributes]] = None,
        anchor_item: Optional[RecommendationGarmentAttributes] = None,
    ) -> Dict[str, AdapterCandidateScore]:
        pos_items = list(positive_items or [])
        if anchor_item is not None:
            pos_items = [anchor_item] + pos_items

        exp = profile.explicit_preferences or {}
        inf = profile.inferred_preferences or {}
        disliked_cats = set(exp.get("disliked_categories", []))
        disliked_cols = set(exp.get("disliked_colors", []))
        disliked_ids = set(profile.disliked_item_ids)
        dismissed_ids = set(profile.dismissed_item_ids)

        results: Dict[str, AdapterCandidateScore] = {}
        for item in candidates:
            if item.item_id in disliked_ids:
                results[item.item_id] = AdapterCandidateScore(
                    item_id=item.item_id,
                    score=0.0,
                    evidence=["Excluded or heavily penalized due to prior user dislike"],
                )
                continue

            score = 0.0
            total_w = 0.0
            evidence: List[str] = []
            matched_attrs: List[str] = []

            def _dim_match(dim_name: str, values: List[str], w: float) -> float:
                nonlocal total_w
                total_w += w
                exp_vals = {v.lower() for v in exp.get(dim_name, [])}
                inf_map = inf.get(dim_name, {}) or {}
                best = 0.0
                for val in values:
                    vl = val.lower()
                    if vl in exp_vals:
                        best = max(best, 1.0)
                        matched_attrs.append(f"{dim_name}:{vl}")
                    elif vl in inf_map and inf_map[vl] > 0:
                        norm_inf = min(1.0, inf_map[vl] / max(1.0, max(inf_map.values())))
                        best = max(best, 0.85 * norm_inf)
                        matched_attrs.append(f"{dim_name}:{vl}")
                return best * w

            score += _dim_match("category", [item.category], 0.24)
            score += _dim_match("subcategory", [item.subcategory], 0.14)
            score += _dim_match("color", [c for c in (item.color, item.secondary_color or "") if c], 0.18)
            score += _dim_match("style", item.style, 0.16)
            score += _dim_match("fit", [item.fit], 0.10)
            score += _dim_match("material", [item.material], 0.08)
            score += _dim_match("silhouette", [item.silhouette], 0.05)
            score += _dim_match("occasion", item.occasion, 0.05)

            # Anchor or prior saved item content similarity boost
            anchor_sim = 0.0
            best_ref_name: Optional[str] = None
            for ref in pos_items[:8]:
                if ref.item_id == item.item_id:
                    continue
                sim_pts = 0.0
                if ref.category == item.category:
                    sim_pts += 0.25
                if ref.subcategory == item.subcategory:
                    sim_pts += 0.15
                if ref.color == item.color:
                    sim_pts += 0.25
                if ref.silhouette == item.silhouette:
                    sim_pts += 0.15
                if ref.material == item.material:
                    sim_pts += 0.10
                if set(ref.style).intersection(set(item.style)):
                    sim_pts += 0.10
                if sim_pts > anchor_sim:
                    anchor_sim = sim_pts
                    best_ref_name = ref.name

            base_norm = (score / total_w) if total_w > 0 else 0.0
            blended = max(base_norm, 0.55 * base_norm + 0.45 * min(1.0, anchor_sim))

            if item.category in disliked_cats or item.color in disliked_cols:
                blended *= 0.15
            if item.item_id in dismissed_ids:
                blended *= 0.45

            if anchor_sim >= 0.45 and best_ref_name:
                if anchor_item is not None and best_ref_name == anchor_item.name:
                    evidence.append(f"Similar style/silhouette to current garment '{best_ref_name}'")
                else:
                    evidence.append(f"Similar to previously saved/liked garment '{best_ref_name}'")
            if f"color:{item.color}" in matched_attrs or f"silhouette:{item.silhouette}" in matched_attrs:
                evidence.append(f"Matches preferred {item.color} color and {item.silhouette} silhouette")

            results[item.item_id] = AdapterCandidateScore(
                item_id=item.item_id,
                score=round(max(0.0, min(1.0, blended)), 4),
                evidence=evidence,
                matched_attributes=sorted(set(matched_attrs)),
            )
        return results


class CollaborativeFilteringAdapter:
    """
    Privacy-preserving implicit collaborative filtering via anonymized user-item overlap.
    Strictly enforces minimum active-user & interaction thresholds before contributing scores.
    """

    def __init__(self, min_users: int = 5, min_interactions_per_user: int = 3) -> None:
        self.min_users = int(min_users)
        self.min_interactions_per_user = int(min_interactions_per_user)

    def check_eligibility(
        self,
        all_user_positives: Dict[str, Set[str]],
    ) -> CollaborativeStatus:
        qualified = {
            uid: items for uid, items in (all_user_positives or {}).items()
            if len(items) >= self.min_interactions_per_user
        }
        eligible = len(qualified) >= self.min_users
        reason = (
            f"Eligible: {len(qualified)} users meet >= {self.min_interactions_per_user} positive interactions."
            if eligible
            else (
                f"Insufficient multi-user interaction history: {len(qualified)} qualified users "
                f"(minimum {self.min_users} users with >= {self.min_interactions_per_user} positive items required)."
            )
        )
        return CollaborativeStatus(
            eligible=eligible,
            active_user_count=len(qualified),
            min_users_required=self.min_users,
            min_interactions_per_user=self.min_interactions_per_user,
            reason=reason,
        )

    def score_candidates(
        self,
        *,
        target_user_id: str,
        candidates: List[RecommendationGarmentAttributes],
        all_user_positives: Dict[str, Set[str]],
    ) -> Tuple[CollaborativeStatus, Dict[str, AdapterCandidateScore]]:
        status = self.check_eligibility(all_user_positives)
        results: Dict[str, AdapterCandidateScore] = {}
        if not status.eligible:
            for item in candidates:
                results[item.item_id] = AdapterCandidateScore(
                    item_id=item.item_id,
                    score=None,
                    available=False,
                    evidence=[],
                    metadata={"status": "INSUFFICIENT_DATA"},
                )
            return status, results

        target_pos = set(all_user_positives.get(target_user_id, set()))
        if not target_pos:
            # User has no positive interactions yet -> CF cannot personalize via user neighborhood
            return CollaborativeStatus(
                eligible=False,
                active_user_count=status.active_user_count,
                min_users_required=self.min_users,
                min_interactions_per_user=self.min_interactions_per_user,
                reason="Target user has zero positive interactions for collaborative neighborhood matching.",
            ), {
                item.item_id: AdapterCandidateScore(item_id=item.item_id, score=None, available=False)
                for item in candidates
            }

        # Privacy-preserving cosine similarity across anonymous peer sets
        peer_sims: List[Tuple[float, Set[str]]] = []
        for other_uid, other_items in all_user_positives.items():
            if other_uid == target_user_id or len(other_items) < self.min_interactions_per_user:
                continue
            inter = len(target_pos.intersection(other_items))
            if inter == 0:
                continue
            sim = inter / math.sqrt(len(target_pos) * len(other_items))
            peer_sims.append((sim, other_items))

        if not peer_sims:
            return CollaborativeStatus(
                eligible=False,
                active_user_count=status.active_user_count,
                min_users_required=self.min_users,
                min_interactions_per_user=self.min_interactions_per_user,
                reason="No overlapping peer interaction neighborhoods available yet.",
            ), {
                item.item_id: AdapterCandidateScore(item_id=item.item_id, score=None, available=False)
                for item in candidates
            }

        raw_scores: Dict[str, float] = {}
        support_counts: Dict[str, int] = {}
        total_sim = sum(s for s, _ in peer_sims) or 1.0
        for item in candidates:
            s_acc = 0.0
            sup = 0
            for sim, oset in peer_sims:
                if item.item_id in oset:
                    s_acc += sim
                    sup += 1
            raw_scores[item.item_id] = s_acc / total_sim
            support_counts[item.item_id] = sup

        max_s = max(raw_scores.values() or [1.0]) or 1.0
        for item in candidates:
            norm = raw_scores[item.item_id] / max_s if max_s > 0 else 0.0
            sup = support_counts[item.item_id]
            ev = (
                [f"Popular among {sup} peers with overlapping fashion preferences"]
                if norm >= 0.25 and sup >= 2
                else []
            )
            results[item.item_id] = AdapterCandidateScore(
                item_id=item.item_id,
                score=round(max(0.0, min(1.0, norm)), 4),
                available=True,
                evidence=ev,
                metadata={"peer_support": sup},
            )
        return status, results


class CategoryAffinityAdapter:
    """Scores candidates using time-decayed category & subcategory affinities."""

    def score_candidates(
        self,
        candidates: List[RecommendationGarmentAttributes],
        *,
        profile: UserPreferenceProfile,
    ) -> Dict[str, AdapterCandidateScore]:
        exp_cats = set(profile.explicit_preferences.get("category", []))
        exp_subs = set(profile.explicit_preferences.get("subcategory", []))
        out: Dict[str, AdapterCandidateScore] = {}
        for item in candidates:
            cat_score = float(profile.category_affinity.get(item.category, 0.0))
            sub_score = float(profile.subcategory_affinity.get(item.subcategory, 0.0))
            if item.category in exp_cats:
                cat_score = max(cat_score, 0.85)
            if item.subcategory in exp_subs:
                sub_score = max(sub_score, 0.90)

            combined = max(0.0, min(1.0, 0.65 * max(0.0, cat_score) + 0.35 * max(0.0, sub_score)))
            ev = []
            if combined >= 0.45:
                ev.append(f"Matches preferred categories: {item.category} ({item.subcategory})")
            out[item.item_id] = AdapterCandidateScore(
                item_id=item.item_id,
                score=round(combined, 4),
                available=True,
                evidence=ev,
            )
        return out


class VisualSimilarityAdapter:
    """Uses verified L2-normalized local visual embeddings (DINOv2 / CLIP) when present."""

    DISCLAIMER = "Visual embedding cosine similarity reflects appearance proximity and is not guaranteed fashion-semantic equivalence."

    def score_candidates(
        self,
        candidates: List[RecommendationGarmentAttributes],
        *,
        query_embedding: Optional[List[float]] = None,
        positive_items: Optional[List[RecommendationGarmentAttributes]] = None,
    ) -> Dict[str, AdapterCandidateScore]:
        ref_vecs: List[Tuple[str, List[float]]] = []
        if query_embedding:
            ref_vecs.append(("current visual query", query_embedding))
        for it in (positive_items or []):
            if it.visual_embedding:
                ref_vecs.append((it.name, it.visual_embedding))

        out: Dict[str, AdapterCandidateScore] = {}
        for item in candidates:
            if not ref_vecs or not item.visual_embedding:
                out[item.item_id] = AdapterCandidateScore(
                    item_id=item.item_id,
                    score=None,
                    available=False,
                    metadata={"disclaimer": self.DISCLAIMER},
                )
                continue

            best_sim = 0.0
            best_name = ""
            for name, vec in ref_vecs:
                sim = _cosine_l2(item.visual_embedding, vec)
                if sim is not None and sim > best_sim:
                    best_sim = sim
                    best_name = name
            ev = [f"Visually proximate appearance to '{best_name}' (local embedding similarity)"] if best_sim >= 0.72 else []
            out[item.item_id] = AdapterCandidateScore(
                item_id=item.item_id,
                score=round(best_sim, 4),
                available=True,
                evidence=ev,
                metadata={"disclaimer": self.DISCLAIMER, "model_id": item.embedding_model_id or "local_embedding"},
            )
        return out


class SessionContextAdapter:
    """Scores candidates for current browsing/Design Studio/Stylist session without mutating long-term profile."""

    def score_candidates(
        self,
        candidates: List[RecommendationGarmentAttributes],
        *,
        session: Optional[SessionBrowsingContext] = None,
        occasion: Optional[str] = None,
        season: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> Dict[str, AdapterCandidateScore]:
        eff_occasion = (occasion or (session.active_occasion if session else None) or "").strip().lower()
        eff_season = (season or "").strip().lower()
        q_tokens: Set[str] = set()
        if search_query:
            q_tokens.update(t for t in search_query.lower().split() if len(t) >= 2)
        if session and session.search_terms:
            for st in session.search_terms[-3:]:
                q_tokens.update(t for t in st.split() if len(t) >= 2)

        out: Dict[str, AdapterCandidateScore] = {}
        for item in candidates:
            s = 0.0
            ev: List[str] = []
            if session:
                s += 0.35 * session.active_categories.get(item.category, 0.0)
                s += 0.25 * session.active_colors.get(item.color, 0.0)
                for st in item.style:
                    s += 0.15 * session.active_styles.get(st, 0.0)
            if eff_occasion and (eff_occasion in item.occasion or (
                eff_occasion in {"formal", "wedding"} and item.formality >= 7
            ) or (eff_occasion in {"casual", "everyday"} and item.formality <= 6)):
                s += 0.45
                ev.append(f"Contextually suited for {eff_occasion} occasion")
            if eff_season and ("all_season" in item.season or eff_season in item.season):
                s += 0.20
            if q_tokens:
                haystack = f"{item.name} {item.category} {item.subcategory} {item.color} {item.material} {' '.join(item.style)}".lower()
                overlap = sum(1 for tok in q_tokens if tok in haystack)
                if overlap > 0:
                    s += min(0.6, 0.25 * overlap)
                    ev.append("Aligned with current session search & focus")
            out[item.item_id] = AdapterCandidateScore(
                item_id=item.item_id,
                score=round(max(0.0, min(1.0, s)), 4),
                available=bool(session or eff_occasion or eff_season or q_tokens),
                evidence=ev,
            )
        return out


class ExplorationDiversityAdapter:
    """Computes bounded exploration novelty & inverse category-saturation reward."""

    def score_candidates(
        self,
        candidates: List[RecommendationGarmentAttributes],
        *,
        profile: UserPreferenceProfile,
        all_positive_items: Optional[List[RecommendationGarmentAttributes]] = None,
        exploration_rate: float = 0.25,
    ) -> Dict[str, AdapterCandidateScore]:
        pos_items = all_positive_items or []
        seen_cats: Dict[str, int] = {}
        seen_styles: Dict[str, int] = {}
        for it in pos_items:
            seen_cats[it.category] = seen_cats.get(it.category, 0) + 1
            for st in it.style:
                seen_styles[st] = seen_styles.get(st, 0) + 1

        max_cat_count = max(seen_cats.values() or [1])
        out: Dict[str, AdapterCandidateScore] = {}
        for item in candidates:
            cat_freq = seen_cats.get(item.category, 0)
            # Adjacent novel category with high style compatibility gets highest exploration score
            cat_novelty = 1.0 - (cat_freq / (max_cat_count + 1.0)) if pos_items else 0.7
            pop_inv = 1.0 / (1.0 + math.log1p(max(0.0, item.popularity_score)))
            freshness = max(0.0, min(1.0, math.exp(-max(0.0, item.freshness_days) / 60.0)))
            novelty = max(0.0, min(1.0, 0.50 * cat_novelty + 0.30 * pop_inv + 0.20 * freshness))
            ev: List[str] = []
            if cat_freq == 0 and exploration_rate > 0:
                ev.append(f"Introduces unexplored '{item.category}' category aligned with broader aesthetic")
            out[item.item_id] = AdapterCandidateScore(
                item_id=item.item_id,
                score=round(novelty, 4),
                available=True,
                evidence=ev,
                metadata={"freshness_component": round(freshness, 4), "cat_novelty": round(cat_novelty, 4)},
            )
        return out


class NeuralRecommendationAdapter:
    """
    Phase 17.2 Neural Retrieval, Ranking & Sequential Adapter.

    Loads SHA-256 verified PyTorch checkpoints for TwoTowerRecommendationModel,
    NeuralRankingModel, and SequentialTransformerRecommender. Returns `available=False`
    cleanly if checkpoints are missing or digest verification fails so callers fall back
    deterministically to algorithmic Phase 17.0 recommenders.
    """

    def __init__(self, checkpoint_dir: Optional[str] = None) -> None:
        import os
        self.checkpoint_dir = checkpoint_dir or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../../../../models/checkpoints/recommendation_v17_2")
        )
        self._two_tower = None
        self._ranker = None
        self._seq_model = None
        self._outfit_model = None
        self._loaded_shas: Dict[str, str] = {}

    def load_verified_checkpoints(
        self,
        *,
        two_tower_path: Optional[str] = None,
        two_tower_sha: Optional[str] = None,
        ranker_path: Optional[str] = None,
        ranker_sha: Optional[str] = None,
        seq_path: Optional[str] = None,
        seq_sha: Optional[str] = None,
        outfit_path: Optional[str] = None,
        outfit_sha: Optional[str] = None,
    ) -> Dict[str, Any]:
        import os
        from backend.app.services.intelligence.neural_recommendation_models import (
            NEURAL_REC_SCHEMA_VERSION,
            NeuralOutfitCompatibilityModel,
            NeuralRankingModel,
            SequentialTransformerRecommender,
            TwoTowerRecommendationModel,
            verify_and_load_neural_checkpoint,
        )

        tt_p = two_tower_path or os.path.join(self.checkpoint_dir, f"two_tower_recommender_{NEURAL_REC_SCHEMA_VERSION}.pt")
        rk_p = ranker_path or os.path.join(self.checkpoint_dir, f"neural_ranking_network_{NEURAL_REC_SCHEMA_VERSION}.pt")
        sq_p = seq_path or os.path.join(self.checkpoint_dir, f"sequential_transformer_recommender_{NEURAL_REC_SCHEMA_VERSION}.pt")
        of_p = outfit_path or os.path.join(self.checkpoint_dir, f"neural_outfit_compatibility_{NEURAL_REC_SCHEMA_VERSION}.pt")

        status: Dict[str, Any] = {}
        ok_tt, data_tt, sha_tt = verify_and_load_neural_checkpoint(tt_p, expected_sha256=two_tower_sha)
        if ok_tt and data_tt is not None:
            m = TwoTowerRecommendationModel()
            m.load_state_dict(data_tt["state_dict"])
            m.eval()
            self._two_tower = m
            self._loaded_shas["two_tower_recommender"] = sha_tt
            status["two_tower_recommender"] = {"loaded": True, "sha256": sha_tt}
        else:
            status["two_tower_recommender"] = {"loaded": False, "reason": sha_tt}

        ok_rk, data_rk, sha_rk = verify_and_load_neural_checkpoint(rk_p, expected_sha256=ranker_sha)
        if ok_rk and data_rk is not None:
            m_rk = NeuralRankingModel()
            m_rk.load_state_dict(data_rk["state_dict"])
            m_rk.eval()
            self._ranker = m_rk
            self._loaded_shas["neural_ranking_network"] = sha_rk
            status["neural_ranking_network"] = {"loaded": True, "sha256": sha_rk}
        else:
            status["neural_ranking_network"] = {"loaded": False, "reason": sha_rk}

        ok_sq, data_sq, sha_sq = verify_and_load_neural_checkpoint(sq_p, expected_sha256=seq_sha)
        if ok_sq and data_sq is not None:
            m_sq = SequentialTransformerRecommender()
            m_sq.load_state_dict(data_sq["state_dict"])
            m_sq.eval()
            self._seq_model = m_sq
            self._loaded_shas["sequential_transformer_recommender"] = sha_sq
            status["sequential_transformer_recommender"] = {"loaded": True, "sha256": sha_sq}
        else:
            status["sequential_transformer_recommender"] = {"loaded": False, "reason": sha_sq}

        ok_of, data_of, sha_of = verify_and_load_neural_checkpoint(of_p, expected_sha256=outfit_sha)
        if ok_of and data_of is not None:
            m_of = NeuralOutfitCompatibilityModel()
            m_of.load_state_dict(data_of["state_dict"])
            m_of.eval()
            self._outfit_model = m_of
            self._loaded_shas["neural_outfit_compatibility"] = sha_of
            status["neural_outfit_compatibility"] = {"loaded": True, "sha256": sha_of}
        else:
            status["neural_outfit_compatibility"] = {"loaded": False, "reason": sha_of}

        return status

    def _ensure_loaded(self) -> None:
        if self._two_tower is None and self._ranker is None and self._seq_model is None and self._outfit_model is None:
            self.load_verified_checkpoints()

    def compute_embeddings(
        self,
        *,
        profile: UserPreferenceProfile,
        candidates: List[RecommendationGarmentAttributes],
        positive_items: Optional[List[RecommendationGarmentAttributes]] = None,
    ) -> Tuple[bool, Optional[List[float]], Dict[str, List[float]]]:
        import torch
        from backend.app.services.intelligence.neural_recommendation_models import (
            encode_item_features,
            encode_user_features,
        )

        self._ensure_loaded()
        if self._two_tower is None or not candidates:
            return False, None, {}
        exp_np, inf_np = encode_user_features(profile, positive_items=positive_items)
        item_np = np.stack([encode_item_features(c) for c in candidates], axis=0)
        with torch.no_grad():
            u_emb = self._two_tower.encode_user(
                torch.tensor(exp_np, dtype=torch.float32).unsqueeze(0),
                torch.tensor(inf_np, dtype=torch.float32).unsqueeze(0),
            ).squeeze(0).tolist()
            i_embs = self._two_tower.encode_item(torch.tensor(item_np, dtype=torch.float32)).tolist()
        return True, [round(float(x), 6) for x in u_emb], {
            candidates[idx].item_id: [round(float(x), 6) for x in i_embs[idx]]
            for idx in range(len(candidates))
        }

    def score_candidates(
        self,
        candidates: List[RecommendationGarmentAttributes],
        *,
        profile: UserPreferenceProfile,
        positive_items: Optional[List[RecommendationGarmentAttributes]] = None,
        category_scores: Optional[Dict[str, AdapterCandidateScore]] = None,
        visual_scores: Optional[Dict[str, AdapterCandidateScore]] = None,
        context_scores: Optional[Dict[str, AdapterCandidateScore]] = None,
        explore_scores: Optional[Dict[str, AdapterCandidateScore]] = None,
        use_ranker: bool = True,
    ) -> Tuple[bool, Dict[str, AdapterCandidateScore]]:
        import torch
        from backend.app.services.intelligence.neural_recommendation_models import (
            encode_item_features,
            encode_user_features,
        )

        self._ensure_loaded()
        if self._two_tower is None or not candidates:
            return False, {
                c.item_id: AdapterCandidateScore(item_id=c.item_id, score=None, available=False)
                for c in candidates
            }

        exp_np, inf_np = encode_user_features(profile, positive_items=positive_items)
        item_np = np.stack([encode_item_features(c) for c in candidates], axis=0)

        out: Dict[str, AdapterCandidateScore] = {}
        with torch.no_grad():
            ue = self._two_tower.encode_user(
                torch.tensor(exp_np, dtype=torch.float32).unsqueeze(0),
                torch.tensor(inf_np, dtype=torch.float32).unsqueeze(0),
            ).expand(len(candidates), -1)
            ve = self._two_tower.encode_item(torch.tensor(item_np, dtype=torch.float32))
            tt_probs = torch.sigmoid((ue * ve).sum(dim=-1) * 4.0).tolist()

            if use_ranker and self._ranker is not None:
                sc_rows = []
                mk_rows = []
                for c in candidates:
                    cat_s = category_scores[c.item_id].score if (category_scores and c.item_id in category_scores and category_scores[c.item_id].score is not None) else 0.0
                    vis_entry = visual_scores.get(c.item_id) if visual_scores else None
                    vis_ok = bool(vis_entry and vis_entry.available and vis_entry.score is not None)
                    vis_s = float(vis_entry.score) if vis_ok else 0.0
                    ctx_entry = context_scores.get(c.item_id) if context_scores else None
                    ctx_ok = bool(ctx_entry and ctx_entry.available and ctx_entry.score is not None)
                    ctx_s = float(ctx_entry.score) if ctx_ok else 0.5
                    exp_s = float(explore_scores[c.item_id].score or 0.5) if (explore_scores and c.item_id in explore_scores) else 0.5
                    avail_s = 1.0 if c.available else 0.0
                    sc_rows.append([float(cat_s), vis_s, ctx_s, exp_s, avail_s])
                    mk_rows.append([1.0, 1.0 if vis_ok else 0.0, 1.0 if ctx_ok else 0.0, 1.0, 1.0])
                sc_t = torch.tensor(sc_rows, dtype=torch.float32)
                mk_t = torch.tensor(mk_rows, dtype=torch.float32)
                rk_probs = torch.sigmoid(self._ranker(ue, ve, sc_t, mk_t)).tolist()
                for idx, c in enumerate(candidates):
                    attr = self._ranker.explain_verified_attributions(sc_t[idx], mk_t[idx], ue[idx], ve[idx])
                    ev = ["Aligned with learned neural ranking preferences"] if rk_probs[idx] >= 0.55 else []
                    out[c.item_id] = AdapterCandidateScore(
                        item_id=c.item_id,
                        score=round(float(rk_probs[idx]), 4),
                        available=True,
                        evidence=ev,
                        metadata={
                            "two_tower_prob": round(float(tt_probs[idx]), 4),
                            "verified_attributions": attr,
                            "two_tower_sha256": self._loaded_shas.get("two_tower_recommender"),
                            "ranker_sha256": self._loaded_shas.get("neural_ranking_network"),
                        },
                    )
            else:
                for idx, c in enumerate(candidates):
                    ev = ["Retrieved via learned Two-Tower fashion embedding affinity"] if tt_probs[idx] >= 0.55 else []
                    out[c.item_id] = AdapterCandidateScore(
                        item_id=c.item_id,
                        score=round(float(tt_probs[idx]), 4),
                        available=True,
                        evidence=ev,
                        metadata={"two_tower_sha256": self._loaded_shas.get("two_tower_recommender")},
                    )
        return True, out

    def score_sequence(
        self,
        candidates: List[RecommendationGarmentAttributes],
        *,
        positive_history: List[RecommendationGarmentAttributes],
        timestamps_s: Optional[List[float]] = None,
        min_seq_len: Optional[int] = None,
    ) -> Tuple[bool, Dict[str, AdapterCandidateScore]]:
        import torch
        from backend.app.services.intelligence.neural_recommendation_models import (
            MIN_SEQ_LEN_FOR_TRANSFORMER,
            encode_item_features,
        )

        self._ensure_loaded()
        req_len = MIN_SEQ_LEN_FOR_TRANSFORMER if min_seq_len is None else max(1, int(min_seq_len))
        if (
            self._seq_model is None
            or self._two_tower is None
            or not positive_history
            or len(positive_history) < req_len
            or not candidates
        ):
            reason = "short_sequence_policy_fallback" if len(positive_history) < req_len else "checkpoint_unavailable"
            return False, {
                c.item_id: AdapterCandidateScore(
                    item_id=c.item_id,
                    score=None,
                    available=False,
                    metadata={"reason": reason, "min_seq_len": req_len, "history_len": len(positive_history)},
                )
                for c in candidates
            }

        hist = positive_history[-12:]
        hist_feats = torch.tensor(np.stack([encode_item_features(it) for it in hist], axis=0), dtype=torch.float32).unsqueeze(0)
        acts = torch.ones((1, len(hist)), dtype=torch.long)
        if timestamps_s and len(timestamps_s) >= len(hist):
            ts_slice = timestamps_s[-len(hist):]
            t0 = ts_slice[0]
            dt_vals = [max(0.0, (t - t0) / 86400.0) for t in ts_slice]
        else:
            dt_vals = [float(i) for i in range(len(hist))]
        dt_t = torch.tensor([dt_vals], dtype=torch.float32)

        cand_feats = torch.tensor(np.stack([encode_item_features(c) for c in candidates], axis=0), dtype=torch.float32)
        with torch.no_grad():
            seq_emb = self._seq_model.encode_sequence(hist_feats, acts, dt_t)
            cand_embs = self._two_tower.encode_item(cand_feats)
            probs = torch.sigmoid((seq_emb * cand_embs).sum(dim=-1) * 4.0).tolist()

        out: Dict[str, AdapterCandidateScore] = {}
        for idx, c in enumerate(candidates):
            ev = ["Matches evolving sequential interest progression"] if probs[idx] >= 0.55 else []
            out[c.item_id] = AdapterCandidateScore(
                item_id=c.item_id,
                score=round(float(probs[idx]), 4),
                available=True,
                evidence=ev,
                metadata={"sequential_sha256": self._loaded_shas.get("sequential_transformer_recommender")},
            )
        return True, out

    def score_outfit_compatibility(
        self,
        items: List[RecommendationGarmentAttributes],
    ) -> Tuple[bool, Optional[float], Dict[str, Any]]:
        """Scores a 2..4 garment outfit using NeuralOutfitCompatibilityModel when verified, else returns unavailable."""
        import torch
        from backend.app.services.intelligence.neural_recommendation_models import encode_item_features

        self._ensure_loaded()
        if self._outfit_model is None or len(items) < 2:
            return False, None, {"reason": "neural_outfit_checkpoint_unavailable"}
        bundle = items[:4]
        feats = torch.tensor(
            np.stack([encode_item_features(it) for it in bundle], axis=0), dtype=torch.float32
        ).unsqueeze(0)
        cats = [it.category for it in bundle]
        unique_cat_ratio = len(set(cats)) / max(1, len(bundle))
        forms = [float(it.formality) for it in bundle]
        formal_spread = (max(forms) - min(forms)) / 10.0 if forms else 0.0
        dup_primary = 1.0 if (cats.count("tops") > 1 or cats.count("bottoms") > 1) else 0.0
        slot_stats = torch.tensor([[unique_cat_ratio, formal_spread, dup_primary]], dtype=torch.float32)
        mask = torch.ones((1, len(bundle)), dtype=torch.float32)
        with torch.no_grad():
            prob = float(torch.sigmoid(self._outfit_model.encode_outfit(feats, slot_stats, mask)).item())
        return True, round(prob, 4), {
            "neural_outfit_sha256": self._loaded_shas.get("neural_outfit_compatibility"),
            "slot_coherence_ratio": round(unique_cat_ratio, 3),
        }

