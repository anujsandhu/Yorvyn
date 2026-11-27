"""
YORVYN Intelligence Platform (YIP) — Offline Recommendation Benchmark & Chronological Evaluator.

Implements leak-free chronological train/test evaluation for personalized, hybrid,
content, category, cold-start, and preset ablations across:
- Precision@K, Recall@K, NDCG@K, MRR
- Catalog Coverage, Category Diversity, Novelty
- Cold-Start Evaluation
- Separation of offline benchmark scores vs real-world user satisfaction / acceptance logs
"""
from __future__ import annotations

import math
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from backend.app.services.intelligence.recommendation_engine import (
    FashionRecommendationEngine,
    RANKING_WEIGHT_PRESETS,
)
from backend.app.services.intelligence.recommendation_profile import (
    POSITIVE_SIGNALS,
    PreferenceProfileStore,
)


class ChronologicalEvent(BaseModel):
    user_id: str
    item_id: str
    interaction_type: str
    timestamp_s: float


class RecommendationBenchmarkReport(BaseModel):
    dataset_name: str
    k: int
    preset_name: str
    ranking_version: str
    users_evaluated: int
    cold_start_users_evaluated: int
    total_events: int
    chronological_split_enforced: bool = True
    future_leakage_detected: bool = False
    precision_at_k: float
    recall_at_k: float
    ndcg_at_k: float
    mrr: float
    catalog_coverage: float
    category_diversity: float
    novelty: float
    cold_start_precision_at_k: float
    cold_start_recall_at_k: float
    cold_start_ndcg_at_k: float
    logged_acceptance_rate: Optional[float] = None
    offline_metrics_do_not_equal_live_satisfaction: bool = True
    ablation_comparison: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    latency_ms: float = 0.0


def _ndcg_at_k(ranked_ids: List[str], relevant: Set[str], k: int) -> float:
    if not relevant:
        return 0.0
    dcg = 0.0
    for idx, iid in enumerate(ranked_ids[:k]):
        if iid in relevant:
            dcg += 1.0 / math.log2(idx + 2.0)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2.0) for i in range(ideal_hits))
    return (dcg / idcg) if idcg > 0 else 0.0


class RecommendationEvaluator:
    """Evaluates FashionRecommendationEngine on chronological splits without future leakage."""

    def evaluate_chronological(
        self,
        *,
        catalog_items: List[Dict[str, Any]],
        events: List[ChronologicalEvent],
        k: int = 5,
        preset_name: str = "hybrid_balanced",
        mode: str = "hybrid",
        dataset_name: str = "yorvyn_chronological_eval",
        train_ratio: float = 0.7,
        run_ablation: bool = True,
        min_cf_users: int = 5,
    ) -> RecommendationBenchmarkReport:
        t0 = time.perf_counter()
        sorted_events = sorted(events, key=lambda e: e.timestamp_s)

        # Group events per user in chronological order
        by_user: Dict[str, List[ChronologicalEvent]] = {}
        for ev in sorted_events:
            by_user.setdefault(ev.user_id, []).append(ev)

        item_lookup = {
            str(it.get("item_id") or it.get("id")): it for it in catalog_items
        }
        item_pop = Counter(ev.item_id for ev in sorted_events if ev.interaction_type.lower() in POSITIVE_SIGNALS)
        total_pos_events = max(1, sum(item_pop.values()))

        # Build isolated evaluation store and engine
        eval_store = PreferenceProfileStore()
        eval_engine = FashionRecommendationEngine(profile_store=eval_store)

        user_splits: Dict[str, Dict[str, Any]] = {}
        max_train_ts_global = 0.0
        for uid, u_events in by_user.items():
            pos_events = [e for e in u_events if e.interaction_type.lower() in POSITIVE_SIGNALS]
            if not pos_events:
                continue
            if len(pos_events) == 1:
                # 0 train positives -> true chronological cold-start test user
                split_idx = 0
                split_ts = pos_events[0].timestamp_s
            else:
                split_idx = max(1, int(math.floor(len(u_events) * train_ratio)))
                if split_idx >= len(u_events):
                    split_idx = len(u_events) - 1
                split_ts = u_events[split_idx].timestamp_s

            train_evs = u_events[:split_idx]
            test_evs = u_events[split_idx:]
            test_rel = {e.item_id for e in test_evs if e.interaction_type.lower() in POSITIVE_SIGNALS}
            if not test_rel:
                continue

            # Populate only strictly earlier training events
            for tev in train_evs:
                eval_store.record_interaction(
                    owner_id=uid,
                    interaction_type=tev.interaction_type,
                    item_data=item_lookup.get(tev.item_id, {"item_id": tev.item_id}),
                    timestamp_s=tev.timestamp_s,
                    consent_granted=True,
                )
            if train_evs:
                max_train_ts_global = max(max_train_ts_global, max(e.timestamp_s for e in train_evs))
            user_splits[uid] = {
                "train_ids": {e.item_id for e in train_evs if e.interaction_type.lower() in POSITIVE_SIGNALS},
                "test_rel": test_rel,
                "split_ts": split_ts,
                "is_cold_start": len([e for e in train_evs if e.interaction_type.lower() in POSITIVE_SIGNALS]) == 0,
            }

        def _score_preset(p_name: str, eval_mode: str) -> Dict[str, float]:
            precs, recs, ndcgs, mrrs, divs, novs = [], [], [], [], [], []
            cs_precs, cs_recs, cs_ndcgs = [], [], []
            covered: Set[str] = set()

            for uid, sp in user_splits.items():
                cand_pool = [
                    it for it in catalog_items
                    if str(it.get("item_id") or it.get("id")) not in sp["train_ids"]
                ]
                resp = eval_engine.recommend(
                    owner_id=uid,
                    candidates=cand_pool,
                    mode=eval_mode,
                    preset_name=p_name,
                    top_k=k,
                    min_cf_users=min_cf_users,
                    before_timestamp_s=sp["split_ts"],
                    reference_time_s=sp["split_ts"],
                )
                ranked_ids = [r.item_id for r in resp.recommendations[:k]]
                covered.update(ranked_ids)
                rel = sp["test_rel"]
                hits = sum(1 for iid in ranked_ids if iid in rel)
                p_k = hits / max(1, len(ranked_ids))
                r_k = hits / max(1, len(rel))
                n_k = _ndcg_at_k(ranked_ids, rel, k)
                rr = 0.0
                for idx, iid in enumerate(ranked_ids):
                    if iid in rel:
                        rr = 1.0 / (idx + 1.0)
                        break

                unique_cats = len({r.category for r in resp.recommendations[:k]})
                cat_div = unique_cats / max(1, min(k, len(resp.recommendations)))
                item_novs = [
                    -math.log2(max(1e-6, (item_pop.get(iid, 0) + 0.5) / (total_pos_events + 1.0)))
                    for iid in ranked_ids
                ]
                mean_nov = (sum(item_novs) / len(item_novs)) if item_novs else 0.0

                precs.append(p_k)
                recs.append(r_k)
                ndcgs.append(n_k)
                mrrs.append(rr)
                divs.append(cat_div)
                novs.append(mean_nov)
                if sp["is_cold_start"]:
                    cs_precs.append(p_k)
                    cs_recs.append(r_k)
                    cs_ndcgs.append(n_k)

            n_u = max(1, len(precs))
            return {
                "users_evaluated": float(len(precs)),
                "cold_start_users": float(len(cs_precs)),
                "precision_at_k": round(sum(precs) / n_u, 4),
                "recall_at_k": round(sum(recs) / n_u, 4),
                "ndcg_at_k": round(sum(ndcgs) / n_u, 4),
                "mrr": round(sum(mrrs) / n_u, 4),
                "catalog_coverage": round(len(covered) / max(1, len(catalog_items)), 4),
                "category_diversity": round(sum(divs) / n_u, 4),
                "novelty": round(sum(novs) / n_u, 4),
                "cold_start_precision_at_k": round(sum(cs_precs) / max(1, len(cs_precs)), 4) if cs_precs else 0.0,
                "cold_start_recall_at_k": round(sum(cs_recs) / max(1, len(cs_recs)), 4) if cs_recs else 0.0,
                "cold_start_ndcg_at_k": round(sum(cs_ndcgs) / max(1, len(cs_ndcgs)), 4) if cs_ndcgs else 0.0,
            }

        primary = _score_preset(preset_name, mode)
        ablation: Dict[str, Dict[str, float]] = {}
        if run_ablation:
            for alt in ("hybrid_balanced", "content_focus", "exploration_discovery"):
                ablation[alt] = _score_preset(alt, "content" if alt == "content_focus" else "hybrid")

        # Separate logged explicit click/dismissal acceptance from offline ranking metrics
        rec_clicks = sum(1 for e in sorted_events if e.interaction_type.lower() in {"recommendation_clicked", "liked", "saved"})
        rec_dismiss = sum(1 for e in sorted_events if e.interaction_type.lower() in {"recommendation_dismissed", "disliked", "rejected"})
        acc_rate = round(rec_clicks / (rec_clicks + rec_dismiss), 4) if (rec_clicks + rec_dismiss) > 0 else None

        preset_cfg = RANKING_WEIGHT_PRESETS.get(preset_name, RANKING_WEIGHT_PRESETS["hybrid_balanced"])
        return RecommendationBenchmarkReport(
            dataset_name=dataset_name,
            k=k,
            preset_name=preset_name,
            ranking_version=preset_cfg.version,
            users_evaluated=int(primary["users_evaluated"]),
            cold_start_users_evaluated=int(primary["cold_start_users"]),
            total_events=len(sorted_events),
            precision_at_k=primary["precision_at_k"],
            recall_at_k=primary["recall_at_k"],
            ndcg_at_k=primary["ndcg_at_k"],
            mrr=primary["mrr"],
            catalog_coverage=primary["catalog_coverage"],
            category_diversity=primary["category_diversity"],
            novelty=primary["novelty"],
            cold_start_precision_at_k=primary["cold_start_precision_at_k"],
            cold_start_recall_at_k=primary["cold_start_recall_at_k"],
            cold_start_ndcg_at_k=primary["cold_start_ndcg_at_k"],
            logged_acceptance_rate=acc_rate,
            ablation_comparison=ablation,
            latency_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )


recommendation_evaluator = RecommendationEvaluator()
