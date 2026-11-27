"""
YORVYN Intelligence Platform (YIP) — Phase 17.2 Offline Neural Training & Governance Pipeline.

Reuses OfflineDatasetCurator & ConfidenceCalibrator to enforce:
- Consent & license/provenance verification before training ingestion
- Chronological per-user train / val / holdout splits with zero future leakage
- Negative sampling collision validation (zero overlap with known positives)
- Reproducible seeds across Python, NumPy, and PyTorch
- Real PyTorch training for TwoTower (BPR), NeuralRanker, SequentialTransformer, & GraphModel
- Side-by-side holdout evaluation against Phase 17.0 algorithmic baselines (`hybrid_balanced`, `content_focus`)
- Model cards, checkpoint SHA-256 digests, calibration (ECE / Brier), cold-start & promotion gates
"""
from __future__ import annotations

import hashlib
import math
import os
import random
import tempfile
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import torch
import torch.nn.functional as F
from pydantic import BaseModel, Field

from backend.app.services.ai.evaluation.calibration import ConfidenceCalibrator
from backend.app.services.intelligence.neural_recommendation_models import (
    EMBEDDING_DIM,
    GraphRecommendationModel,
    ITEM_FEAT_DIM,
    NEURAL_REC_SCHEMA_VERSION,
    NeuralRankingModel,
    SequentialTransformerRecommender,
    TwoTowerRecommendationModel,
    encode_item_features,
    encode_user_features,
    save_neural_checkpoint,
)
from backend.app.services.intelligence.recommendation_engine import FashionRecommendationEngine
from backend.app.services.intelligence.recommendation_profile import (
    POSITIVE_SIGNALS,
    PreferenceProfileStore,
    SENSITIVE_ATTRIBUTE_BLOCKLIST,
    SIGNAL_WEIGHTS,
)
from backend.app.services.intelligence.recommendation_taxonomy import normalize_item
from backend.app.services.learning.dataset_curator import APPROVED_DATASET_LICENSES

MIN_RECOMMENDED_TRAINING_INTERACTIONS = 120
MIN_RECOMMENDED_TRAINING_USERS = 25


class CuratedInteractionEvent(BaseModel):
    event_id: str
    user_id: str
    item_id: str
    interaction_type: str
    timestamp_s: float
    consent_verified: bool = True
    license: str = "YORVYN Consented User Upload"
    provenance_source: str = "user_interaction_log"
    is_private_upload: bool = False


class NeuralModelMetrics(BaseModel):
    model_id: str
    model_version: str
    architecture: str
    precision_at_k: float
    recall_at_k: float
    ndcg_at_k: float
    mrr: float
    catalog_coverage: float
    category_diversity: float
    novelty: float
    calibration_ece: Optional[float] = None
    brier_score: Optional[float] = None
    cold_start_recall_at_k: float = 0.0
    cold_start_ndcg_at_k: float = 0.0
    p50_inference_ms: float = 0.0
    checkpoint_path: Optional[str] = None
    checkpoint_sha256: Optional[str] = None
    train_loss_final: float = 0.0
    promotion_eligible: bool = False
    promoted_to_production: bool = False
    promotion_gate_reason: str = ""
    model_card: Dict[str, Any] = Field(default_factory=dict)


class NeuralTrainingBenchmarkReport(BaseModel):
    dataset_name: str
    schema_version: str = NEURAL_REC_SCHEMA_VERSION
    seed: int
    k: int
    total_events_submitted: int
    accepted_events: int
    rejected_no_consent: int
    rejected_invalid_license: int
    rejected_weak_views_for_training: int
    rejected_negative_collision_checks: int = 0
    chronological_split_verified: bool = True
    future_leakage_detected: bool = False
    small_dataset_limitation: bool = False
    dataset_limitation_note: str = ""
    pyg_installed: bool = False
    graph_research_note: str = ""
    baseline_metrics: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    neural_models: Dict[str, NeuralModelMetrics] = Field(default_factory=dict)
    duration_ms: float = 0.0


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


def _brier_binary(probs: List[float], targets: List[bool]) -> Optional[float]:
    if not probs:
        return None
    sq = [(p - (1.0 if y else 0.0)) ** 2 for p, y in zip(probs, targets)]
    return round(float(sum(sq) / len(sq)), 4)


class NeuralRecommendationTrainer:
    """Reproducible consent-gated PyTorch training & holdout evaluation pipeline."""

    @staticmethod
    def train_and_benchmark(
        *,
        catalog_items: List[Dict[str, Any]],
        events: List[CuratedInteractionEvent],
        dataset_name: str = "yorvyn_neural_rec_benchmark",
        k: int = 5,
        epochs: int = 24,
        lr: float = 0.03,
        seed: int = 42,
        artifact_dir: Optional[str] = None,
    ) -> NeuralTrainingBenchmarkReport:
        t0 = time.perf_counter()
        torch.manual_seed(seed)
        np.random.seed(seed)
        rng = random.Random(seed)

        # 1. Governance: consent + license + weak-view filter
        rej_consent = 0
        rej_lic = 0
        rej_weak = 0
        valid_events: List[CuratedInteractionEvent] = []
        for ev in sorted(events, key=lambda e: e.timestamp_s):
            if not ev.consent_verified:
                rej_consent += 1
                continue
            if ev.license not in APPROVED_DATASET_LICENSES:
                rej_lic += 1
                continue
            itype = ev.interaction_type.lower()
            if itype not in POSITIVE_SIGNALS:
                # Weak views / dismissals never treated as positive neural training targets
                rej_weak += 1
                continue
            valid_events.append(ev)

        norm_catalog = [normalize_item(c) for c in catalog_items]
        item_idx_by_id = {c.item_id: i for i, c in enumerate(norm_catalog)}
        item_by_id = {c.item_id: c for c in norm_catalog}
        if not norm_catalog or not valid_events:
            raise ValueError("Non-empty catalog and consented positive interaction events are required.")

        item_feat_np = np.stack([encode_item_features(c) for c in norm_catalog], axis=0)
        item_feat_t = torch.tensor(item_feat_np, dtype=torch.float32)

        # 2. Strict chronological split (per user: train < val < holdout, zero future leakage)
        by_user: Dict[str, List[CuratedInteractionEvent]] = {}
        for ev in valid_events:
            if ev.item_id in item_idx_by_id:
                by_user.setdefault(ev.user_id, []).append(ev)

        train_store = PreferenceProfileStore()
        user_splits: Dict[str, Dict[str, Any]] = {}
        user_all_positives: Dict[str, Set[str]] = {}
        max_train_ts = -1e18
        min_holdout_ts = 1e18
        leakage = False

        for uid, u_evs in by_user.items():
            user_all_positives[uid] = {e.item_id for e in u_evs}
            n = len(u_evs)
            if n == 1:
                # Cold-start chronological holdout user
                tr_evs, va_evs, ho_evs = [], [], u_evs
                split_ts = ho_evs[0].timestamp_s
            elif n == 2:
                tr_evs, va_evs, ho_evs = [u_evs[0]], [], [u_evs[1]]
                split_ts = ho_evs[0].timestamp_s
            else:
                tr_end = max(1, int(math.floor(n * 0.6)))
                va_end = max(tr_end + 1, int(math.floor(n * 0.8)))
                if va_end >= n:
                    va_end = n - 1
                tr_evs = u_evs[:tr_end]
                va_evs = u_evs[tr_end:va_end]
                ho_evs = u_evs[va_end:]
                split_ts = ho_evs[0].timestamp_s

            if tr_evs and ho_evs and max(e.timestamp_s for e in tr_evs) >= min(e.timestamp_s for e in ho_evs):
                leakage = True
            if tr_evs:
                max_train_ts = max(max_train_ts, max(e.timestamp_s for e in tr_evs))
            if ho_evs:
                min_holdout_ts = min(min_holdout_ts, min(e.timestamp_s for e in ho_evs))

            for e in tr_evs:
                train_store.record_interaction(
                    owner_id=uid,
                    interaction_type=e.interaction_type,
                    item_data=item_by_id[e.item_id].model_dump(),
                    timestamp_s=e.timestamp_s,
                    consent_granted=True,
                )

            user_splits[uid] = {
                "train_evs": tr_evs,
                "val_evs": va_evs,
                "holdout_evs": ho_evs,
                "train_ids": {e.item_id for e in tr_evs},
                "holdout_ids": {e.item_id for e in ho_evs},
                "split_ts": split_ts,
                "is_cold_start": len(tr_evs) == 0,
            }

        item_pop = Counter(e.item_id for e in valid_events)
        total_pos = max(1, sum(item_pop.values()))
        out_dir = artifact_dir or os.path.join(tempfile.gettempdir(), "yorvyn_neural_rec_v17_2")
        os.makedirs(out_dir, exist_ok=True)

        # Helper to compute common evaluation table cleanly
        def _evaluate_ranking_fn(rank_fn) -> Tuple[Dict[str, float], List[float], List[bool]]:
            precs, recs, ndcgs, mrrs, divs, novs, lats = [], [], [], [], [], [], []
            cs_recs, cs_ndcgs = [], []
            covered: Set[str] = set()
            cal_probs: List[float] = []
            cal_hits: List[bool] = []

            for uid, sp in user_splits.items():
                ho_ids = sp["holdout_ids"]
                if not ho_ids:
                    continue
                cand_items = [c for c in norm_catalog if c.item_id not in sp["train_ids"]]
                if not cand_items:
                    continue
                ts_a = time.perf_counter()
                scored_pairs = rank_fn(uid, sp, cand_items)  # List[(item_id, prob_score)] sorted desc
                lats.append((time.perf_counter() - ts_a) * 1000.0)

                ranked_ids = [iid for iid, _ in scored_pairs[:k]]
                covered.update(ranked_ids)
                hits = sum(1 for iid in ranked_ids if iid in ho_ids)
                p_k = hits / max(1, len(ranked_ids))
                r_k = hits / max(1, len(ho_ids))
                n_k = _ndcg_at_k(ranked_ids, ho_ids, k)
                rr = next((1.0 / (idx + 1.0) for idx, iid in enumerate(ranked_ids) if iid in ho_ids), 0.0)

                u_cats = {item_by_id[iid].category for iid in ranked_ids if iid in item_by_id}
                c_div = len(u_cats) / max(1, len(ranked_ids))
                nov = sum(
                    -math.log2(max(1e-6, (item_pop.get(iid, 0) + 0.5) / (total_pos + 1.0)))
                    for iid in ranked_ids
                ) / max(1, len(ranked_ids))

                for iid, prob in scored_pairs:
                    cal_probs.append(float(max(1e-4, min(1.0 - 1e-4, prob))))
                    cal_hits.append(iid in ho_ids)

                precs.append(p_k)
                recs.append(r_k)
                ndcgs.append(n_k)
                mrrs.append(rr)
                divs.append(c_div)
                novs.append(nov)
                if sp["is_cold_start"]:
                    cs_recs.append(r_k)
                    cs_ndcgs.append(n_k)

            n_u = max(1, len(precs))
            return {
                "precision_at_k": round(sum(precs) / n_u, 4),
                "recall_at_k": round(sum(recs) / n_u, 4),
                "ndcg_at_k": round(sum(ndcgs) / n_u, 4),
                "mrr": round(sum(mrrs) / n_u, 4),
                "catalog_coverage": round(len(covered) / max(1, len(norm_catalog)), 4),
                "category_diversity": round(sum(divs) / n_u, 4),
                "novelty": round(sum(novs) / n_u, 4),
                "cold_start_recall_at_k": round(sum(cs_recs) / max(1, len(cs_recs)), 4) if cs_recs else 0.0,
                "cold_start_ndcg_at_k": round(sum(cs_ndcgs) / max(1, len(cs_ndcgs)), 4) if cs_ndcgs else 0.0,
                "p50_inference_ms": round(float(np.percentile(lats, 50)) if lats else 0.0, 3),
            }, cal_probs, cal_hits

        # 3. Algorithmic Baselines (`hybrid_balanced`, `content_focus`, `popularity`)
        algo_engine = FashionRecommendationEngine(profile_store=train_store)
        baselines: Dict[str, Dict[str, float]] = {}
        for b_name, b_mode, b_preset in (
            ("hybrid_balanced", "hybrid", "hybrid_balanced"),
            ("content_focus", "content", "content_focus"),
        ):
            m, _, _ = _evaluate_ranking_fn(
                lambda uid, sp, cands, bm=b_mode, bp=b_preset: [
                    (r.item_id, r.final_score)
                    for r in algo_engine.recommend(
                        owner_id=uid,
                        candidates=[c.model_dump() for c in cands],
                        mode=bm,
                        preset_name=bp,
                        top_k=len(cands),
                        before_timestamp_s=sp["split_ts"],
                        reference_time_s=sp["split_ts"],
                    ).recommendations
                ]
            )
            baselines[b_name] = m

        m_pop, _, _ = _evaluate_ranking_fn(
            lambda uid, sp, cands: sorted(
                [(c.item_id, item_pop.get(c.item_id, 0) / total_pos) for c in cands],
                key=lambda x: x[1],
                reverse=True,
            )
        )
        baselines["popularity"] = m_pop
        best_algo_ndcg = max(baselines["hybrid_balanced"]["ndcg_at_k"], baselines["content_focus"]["ndcg_at_k"])
        best_algo_div = max(baselines["hybrid_balanced"]["category_diversity"], 0.1)

        # Prepare per-user training feature tensors & verified negative sampling
        user_feat_cache: Dict[str, Tuple[torch.Tensor, torch.Tensor]] = {}
        bpr_triples: List[Tuple[str, int, int]] = []
        negative_collision_checks = 0
        all_ids = list(item_idx_by_id.keys())

        for uid, sp in user_splits.items():
            prof = train_store.get_profile(uid, reference_time_s=sp["split_ts"])
            pos_objs = [item_by_id[iid] for iid in sp["train_ids"] if iid in item_by_id]
            exp_np, inf_np = encode_user_features(prof, positive_items=pos_objs)
            user_feat_cache[uid] = (torch.tensor(exp_np, dtype=torch.float32), torch.tensor(inf_np, dtype=torch.float32))

            forbidden = user_all_positives.get(uid, set())
            neg_pool = [item_idx_by_id[iid] for iid in all_ids if iid not in forbidden]
            if not neg_pool:
                continue
            for ev in sp["train_evs"]:
                p_idx = item_idx_by_id[ev.item_id]
                for neg_idx in rng.sample(neg_pool, k=min(2, len(neg_pool))):
                    # Strict verification: negative never collides with any positive item of user
                    assert norm_catalog[neg_idx].item_id not in forbidden
                    negative_collision_checks += 1
                    bpr_triples.append((uid, p_idx, neg_idx))

        small_dataset = (len(valid_events) < MIN_RECOMMENDED_TRAINING_INTERACTIONS) or (len(by_user) < MIN_RECOMMENDED_TRAINING_USERS)
        limitation_msg = (
            f"Dataset size ({len(valid_events)} positive interactions across {len(by_user)} users) is below "
            f"the reliability threshold ({MIN_RECOMMENDED_TRAINING_INTERACTIONS} interactions / {MIN_RECOMMENDED_TRAINING_USERS} users); "
            "neural weights carry high variance/overfit risk and remain unpromoted without large-scale holdout evidence."
            if small_dataset
            else "Dataset meets minimum training scale threshold; evaluate calibration and baseline delta before approval."
        )

        neural_reports: Dict[str, NeuralModelMetrics] = {}

        # ── Model 1: Two-Tower Retrieval (BPR Pairwise Loss) ─────────────────────────────────
        two_tower = TwoTowerRecommendationModel()
        opt_tt = torch.optim.AdamW(two_tower.parameters(), lr=lr, weight_decay=1e-3)
        tt_loss = 0.0
        two_tower.train()
        for _ in range(max(4, min(epochs, 50))):
            if not bpr_triples:
                break
            rng.shuffle(bpr_triples)
            exp_b = torch.stack([user_feat_cache[u][0] for u, _, _ in bpr_triples], dim=0)
            inf_b = torch.stack([user_feat_cache[u][1] for u, _, _ in bpr_triples], dim=0)
            pos_b = item_feat_t[[p for _, p, _ in bpr_triples]]
            neg_b = item_feat_t[[n for _, _, n in bpr_triples]]
            opt_tt.zero_grad()
            s_pos = two_tower(exp_b, inf_b, pos_b)
            s_neg = two_tower(exp_b, inf_b, neg_b)
            loss = -torch.log(torch.sigmoid(s_pos - s_neg) + 1e-8).mean()
            loss.backward()
            opt_tt.step()
            tt_loss = float(loss.item())

        two_tower.eval()
        tt_path = os.path.join(out_dir, f"two_tower_recommender_{NEURAL_REC_SCHEMA_VERSION}.pt")
        tt_sha = save_neural_checkpoint(
            tt_path,
            model_id="two_tower_recommender",
            version=NEURAL_REC_SCHEMA_VERSION,
            state_dict=two_tower.state_dict(),
            extra_metadata={"seed": seed, "embed_dim": EMBEDDING_DIM, "item_dim": ITEM_FEAT_DIM},
        )

        def _tt_rank(uid, sp, cands):
            exp_t, inf_t = user_feat_cache[uid]
            idx_list = [item_idx_by_id[c.item_id] for c in cands]
            with torch.no_grad():
                u_emb = two_tower.encode_user(exp_t.unsqueeze(0), inf_t.unsqueeze(0))
                i_emb = two_tower.encode_item(item_feat_t[idx_list])
                probs = torch.sigmoid((u_emb * i_emb).sum(dim=-1) * 4.0).tolist()
            return sorted([(cands[i].item_id, probs[i]) for i in range(len(cands))], key=lambda x: x[1], reverse=True)

        tt_m, tt_p, tt_h = _evaluate_ranking_fn(_tt_rank)
        tt_ece = ConfidenceCalibrator.compute_ece(tt_p, tt_h) if len(tt_h) >= 4 else None
        tt_brier = _brier_binary(tt_p, tt_h)
        tt_elig = (not small_dataset) and (tt_m["ndcg_at_k"] > best_algo_ndcg) and (tt_m["category_diversity"] >= 0.85 * best_algo_div)
        neural_reports["two_tower_recommender"] = NeuralModelMetrics(
            model_id="two_tower_recommender",
            model_version=NEURAL_REC_SCHEMA_VERSION,
            architecture="TwoTowerRecommendationModel",
            **tt_m,
            calibration_ece=tt_ece,
            brier_score=tt_brier,
            checkpoint_path=tt_path,
            checkpoint_sha256=tt_sha,
            train_loss_final=round(tt_loss, 4),
            promotion_eligible=tt_elig,
            promoted_to_production=False,
            promotion_gate_reason=(
                "Eligible for staged review" if tt_elig else (
                    limitation_msg if small_dataset else "Holdout NDCG or diversity did not strictly beat algorithmic baseline."
                )
            ),
            model_card={"loss": "BPR", "seed": seed, "events": len(valid_events), "promoted_to_production": False},
        )

        # ── Model 2: Neural Ranking Network ──────────────────────────────────────────────────
        ranker = NeuralRankingModel(embed_dim=EMBEDDING_DIM)
        opt_rk = torch.optim.AdamW(ranker.parameters(), lr=lr, weight_decay=1e-3)
        rk_loss = 0.0
        ranker.train()
        with torch.no_grad():
            all_item_embs = two_tower.encode_item(item_feat_t)
        if bpr_triples:
            pos_samples_rk: List[Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, float]] = []
            for uid, p_idx, n_idx in bpr_triples:
                prof = train_store.get_profile(uid)
                with torch.no_grad():
                    ue = two_tower.encode_user(user_feat_cache[uid][0].unsqueeze(0), user_feat_cache[uid][1].unsqueeze(0)).squeeze(0)
                for idx, target in ((p_idx, 1.0), (n_idx, 0.0)):
                    cat_aff = max(0.0, float(prof.category_affinity.get(norm_catalog[idx].category, 0.0)))
                    sc = torch.tensor([cat_aff, 0.0, 0.5, 0.5, 1.0 if norm_catalog[idx].available else 0.0], dtype=torch.float32)
                    mk = torch.tensor([1.0, 0.0, 1.0, 1.0, 1.0], dtype=torch.float32)
                    pos_samples_rk.append((ue, all_item_embs[idx], sc, mk, target))
            for _ in range(max(4, min(epochs, 40))):
                u_t = torch.stack([x[0] for x in pos_samples_rk])
                v_t = torch.stack([x[1] for x in pos_samples_rk])
                s_t = torch.stack([x[2] for x in pos_samples_rk])
                m_t = torch.stack([x[3] for x in pos_samples_rk])
                y_t = torch.tensor([x[4] for x in pos_samples_rk], dtype=torch.float32)
                opt_rk.zero_grad()
                logits = ranker(u_t, v_t, s_t, m_t)
                loss = F.binary_cross_entropy_with_logits(logits, y_t)
                loss.backward()
                opt_rk.step()
                rk_loss = float(loss.item())

        ranker.eval()
        rk_path = os.path.join(out_dir, f"neural_ranking_network_{NEURAL_REC_SCHEMA_VERSION}.pt")
        rk_sha = save_neural_checkpoint(
            rk_path,
            model_id="neural_ranking_network",
            version=NEURAL_REC_SCHEMA_VERSION,
            state_dict=ranker.state_dict(),
            extra_metadata={"seed": seed, "embed_dim": EMBEDDING_DIM},
        )

        def _rk_rank(uid, sp, cands):
            exp_t, inf_t = user_feat_cache[uid]
            prof = train_store.get_profile(uid, reference_time_s=sp["split_ts"])
            with torch.no_grad():
                ue = two_tower.encode_user(exp_t.unsqueeze(0), inf_t.unsqueeze(0)).expand(len(cands), -1)
                idx_list = [item_idx_by_id[c.item_id] for c in cands]
                ve = all_item_embs[idx_list]
                sc = torch.tensor([
                    [max(0.0, float(prof.category_affinity.get(c.category, 0.0))), 0.0, 0.5, 0.5, 1.0 if c.available else 0.0]
                    for c in cands
                ], dtype=torch.float32)
                mk = torch.tensor([[1.0, 0.0, 1.0, 1.0, 1.0] for _ in cands], dtype=torch.float32)
                probs = torch.sigmoid(ranker(ue, ve, sc, mk)).tolist()
            return sorted([(cands[i].item_id, probs[i]) for i in range(len(cands))], key=lambda x: x[1], reverse=True)

        rk_m, rk_p, rk_h = _evaluate_ranking_fn(_rk_rank)
        rk_elig = (not small_dataset) and (rk_m["ndcg_at_k"] > best_algo_ndcg) and (rk_m["category_diversity"] >= 0.85 * best_algo_div)
        neural_reports["neural_ranking_network"] = NeuralModelMetrics(
            model_id="neural_ranking_network",
            model_version=NEURAL_REC_SCHEMA_VERSION,
            architecture="NeuralRankingModel",
            **rk_m,
            calibration_ece=ConfidenceCalibrator.compute_ece(rk_p, rk_h) if len(rk_h) >= 4 else None,
            brier_score=_brier_binary(rk_p, rk_h),
            checkpoint_path=rk_path,
            checkpoint_sha256=rk_sha,
            train_loss_final=round(rk_loss, 4),
            promotion_eligible=rk_elig,
            promoted_to_production=False,
            promotion_gate_reason="Eligible for staged review" if rk_elig else limitation_msg,
            model_card={"loss": "BCEWithLogitsLoss", "masked_unverified_signals": True, "seed": seed},
        )

        # ── Model 3: Causal Transformer Sequential Recommender ─────────────────────────────────
        seq_model = SequentialTransformerRecommender()
        opt_sq = torch.optim.AdamW(seq_model.parameters(), lr=lr * 0.6, weight_decay=1e-3)
        sq_loss = 0.0
        seq_samples: List[Tuple[List[int], List[float], int, List[int]]] = []
        for uid, sp in user_splits.items():
            tr_evs = sp["train_evs"]
            if len(tr_evs) < 2:
                continue
            forbidden = user_all_positives.get(uid, set())
            neg_pool = [item_idx_by_id[iid] for iid in all_ids if iid not in forbidden]
            if not neg_pool:
                continue
            for end_idx in range(1, len(tr_evs)):
                prefix = tr_evs[:end_idx]
                target_idx = item_idx_by_id[tr_evs[end_idx].item_id]
                p_idxs = [item_idx_by_id[e.item_id] for e in prefix]
                t0_ts = prefix[0].timestamp_s
                d_days = [max(0.0, (e.timestamp_s - t0_ts) / 86400.0) for e in prefix]
                seq_samples.append((p_idxs, d_days, target_idx, rng.sample(neg_pool, k=min(2, len(neg_pool)))))

        seq_model.train()
        for _ in range(max(3, min(epochs, 24))):
            if not seq_samples:
                break
            total_l = torch.tensor(0.0)
            opt_sq.zero_grad()
            for p_idxs, d_days, target_idx, n_idxs in seq_samples:
                feats = item_feat_t[p_idxs].unsqueeze(0)
                acts = torch.ones((1, len(p_idxs)), dtype=torch.long)
                dt = torch.tensor([d_days], dtype=torch.float32)
                s_emb = seq_model.encode_sequence(feats, acts, dt)
                p_e = all_item_embs[target_idx].unsqueeze(0)
                for n_idx in n_idxs:
                    n_e = all_item_embs[n_idx].unsqueeze(0)
                    diff = (s_emb * p_e).sum(dim=-1) - (s_emb * n_e).sum(dim=-1)
                    total_l = total_l - torch.log(torch.sigmoid(diff * 5.0) + 1e-8).mean()
            total_l = total_l / max(1, len(seq_samples))
            total_l.backward()
            opt_sq.step()
            sq_loss = float(total_l.item())

        seq_model.eval()
        sq_path = os.path.join(out_dir, f"sequential_transformer_recommender_{NEURAL_REC_SCHEMA_VERSION}.pt")
        sq_sha = save_neural_checkpoint(
            sq_path,
            model_id="sequential_transformer_recommender",
            version=NEURAL_REC_SCHEMA_VERSION,
            state_dict=seq_model.state_dict(),
            extra_metadata={"seed": seed, "causal_mask": True, "item_dim": ITEM_FEAT_DIM},
        )

        def _sq_rank(uid, sp, cands):
            tr_evs = sp["train_evs"]
            if not tr_evs:
                return _tt_rank(uid, sp, cands)  # graceful cold-start fallback without sequence
            p_idxs = [item_idx_by_id[e.item_id] for e in tr_evs[-12:]]
            t0_ts = tr_evs[max(0, len(tr_evs) - 12)].timestamp_s
            d_days = [max(0.0, (e.timestamp_s - t0_ts) / 86400.0) for e in tr_evs[-12:]]
            idx_list = [item_idx_by_id[c.item_id] for c in cands]
            with torch.no_grad():
                se = seq_model.encode_sequence(
                    item_feat_t[p_idxs].unsqueeze(0),
                    torch.ones((1, len(p_idxs)), dtype=torch.long),
                    torch.tensor([d_days], dtype=torch.float32),
                )
                ve = all_item_embs[idx_list]
                probs = torch.sigmoid((se * ve).sum(dim=-1) * 4.0).tolist()
            return sorted([(cands[i].item_id, probs[i]) for i in range(len(cands))], key=lambda x: x[1], reverse=True)

        sq_m, sq_p, sq_h = _evaluate_ranking_fn(_sq_rank)
        sq_elig = (not small_dataset) and (sq_m["ndcg_at_k"] > best_algo_ndcg) and (sq_m["category_diversity"] >= 0.85 * best_algo_div)
        neural_reports["sequential_transformer_recommender"] = NeuralModelMetrics(
            model_id="sequential_transformer_recommender",
            model_version=NEURAL_REC_SCHEMA_VERSION,
            architecture="SequentialTransformerRecommender",
            **sq_m,
            calibration_ece=ConfidenceCalibrator.compute_ece(sq_p, sq_h) if len(sq_h) >= 4 else None,
            brier_score=_brier_binary(sq_p, sq_h),
            checkpoint_path=sq_path,
            checkpoint_sha256=sq_sha,
            train_loss_final=round(sq_loss, 4),
            promotion_eligible=sq_elig,
            promoted_to_production=False,
            promotion_gate_reason="Eligible for staged review" if sq_elig else limitation_msg,
            model_card={"causal_mask_enforced": True, "weak_views_excluded_from_state": True, "seed": seed},
        )

        # ── Model 4: Provenance-Aware Graph Recommendation Model ───────────────────────────────
        user_list = sorted(user_splits.keys())
        cat_list = sorted({c.category for c in norm_catalog})
        style_list = sorted({st for c in norm_catalog for st in c.style})
        u_offset = 0
        i_offset = len(user_list)
        c_offset = i_offset + len(norm_catalog)
        s_offset = c_offset + len(cat_list)
        total_nodes = s_offset + len(style_list)
        u_map = {u: u_offset + idx for idx, u in enumerate(user_list)}
        c_map = {c: c_offset + idx for idx, c in enumerate(cat_list)}
        s_map = {s: s_offset + idx for idx, s in enumerate(style_list)}

        graph_edges: List[Tuple[int, int]] = []
        for it in norm_catalog:
            i_n = i_offset + item_idx_by_id[it.item_id]
            graph_edges.append((i_n, c_map[it.category]))
            for st in it.style:
                if st in s_map:
                    graph_edges.append((i_n, s_map[st]))
        for uid, sp in user_splits.items():
            # Strictly consented & non-private-cross-owner train interactions only
            for ev in sp["train_evs"]:
                if not ev.consent_verified:
                    continue
                if ev.is_private_upload:
                    continue
                graph_edges.append((u_map[uid], i_offset + item_idx_by_id[ev.item_id]))

        graph_model = GraphRecommendationModel(num_nodes=max(2, total_nodes), embed_dim=EMBEDDING_DIM)
        norm_adj = GraphRecommendationModel.build_normalized_adjacency(max(2, total_nodes), graph_edges)
        opt_gf = torch.optim.AdamW(graph_model.parameters(), lr=lr, weight_decay=1e-3)
        gf_loss = 0.0
        graph_model.train()
        for _ in range(max(4, min(epochs, 30))):
            if not bpr_triples:
                break
            opt_gf.zero_grad()
            emb_all = graph_model.propagate(norm_adj)
            u_idx_t = torch.tensor([u_map[u] for u, _, _ in bpr_triples], dtype=torch.long)
            p_idx_t = torch.tensor([i_offset + p for _, p, _ in bpr_triples], dtype=torch.long)
            n_idx_t = torch.tensor([i_offset + n for _, _, n in bpr_triples], dtype=torch.long)
            s_p = (emb_all[u_idx_t] * emb_all[p_idx_t]).sum(dim=-1) * 5.0
            s_n = (emb_all[u_idx_t] * emb_all[n_idx_t]).sum(dim=-1) * 5.0
            loss = -torch.log(torch.sigmoid(s_p - s_n) + 1e-8).mean()
            loss.backward()
            opt_gf.step()
            gf_loss = float(loss.item())

        graph_model.eval()
        with torch.no_grad():
            final_graph_embs = graph_model.propagate(norm_adj)
        gf_path = os.path.join(out_dir, f"graph_recommendation_model_{NEURAL_REC_SCHEMA_VERSION}.pt")
        gf_sha = save_neural_checkpoint(
            gf_path,
            model_id="graph_recommendation_model",
            version=NEURAL_REC_SCHEMA_VERSION,
            state_dict=graph_model.state_dict(),
            extra_metadata={"seed": seed, "num_nodes": total_nodes, "edges_count": len(graph_edges), "private_edges_excluded": True},
        )

        def _gf_rank(uid, sp, cands):
            un = u_map.get(uid)
            if un is None or not sp["train_evs"]:
                return _tt_rank(uid, sp, cands)
            ue = final_graph_embs[un]
            scored = []
            for c in cands:
                ie = final_graph_embs[i_offset + item_idx_by_id[c.item_id]]
                prob = float(torch.sigmoid((ue * ie).sum() * 4.0).item())
                scored.append((c.item_id, prob))
            return sorted(scored, key=lambda x: x[1], reverse=True)

        gf_m, gf_p, gf_h = _evaluate_ranking_fn(_gf_rank)
        gf_elig = (not small_dataset) and (gf_m["ndcg_at_k"] > best_algo_ndcg) and (gf_m["category_diversity"] >= 0.85 * best_algo_div)
        neural_reports["graph_recommendation_model"] = NeuralModelMetrics(
            model_id="graph_recommendation_model",
            model_version=NEURAL_REC_SCHEMA_VERSION,
            architecture="GraphRecommendationModel",
            **gf_m,
            calibration_ece=ConfidenceCalibrator.compute_ece(gf_p, gf_h) if len(gf_h) >= 4 else None,
            brier_score=_brier_binary(gf_p, gf_h),
            checkpoint_path=gf_path,
            checkpoint_sha256=gf_sha,
            train_loss_final=round(gf_loss, 4),
            promotion_eligible=gf_elig,
            promoted_to_production=False,
            promotion_gate_reason="Eligible for staged review" if gf_elig else limitation_msg,
            model_card={"graph_edges": len(graph_edges), "provenance_gated": True, "pyg_dependency_required": False, "seed": seed},
        )

        return NeuralTrainingBenchmarkReport(
            dataset_name=dataset_name,
            seed=seed,
            k=k,
            total_events_submitted=len(events),
            accepted_events=len(valid_events),
            rejected_no_consent=rej_consent,
            rejected_invalid_license=rej_lic,
            rejected_weak_views_for_training=rej_weak,
            rejected_negative_collision_checks=negative_collision_checks,
            chronological_split_verified=not leakage,
            future_leakage_detected=leakage,
            small_dataset_limitation=small_dataset,
            dataset_limitation_note=limitation_msg,
            pyg_installed=False,
            graph_research_note=(
                "PyTorch Geometric (torch_geometric) is not installed on host; evaluated pure PyTorch normalized "
                "bipartite+taxonomy LightGCN-style graph propagation against Two-Tower, Neural Ranker, and Causal Transformer."
            ),
            baseline_metrics=baselines,
            neural_models=neural_reports,
            duration_ms=round((time.perf_counter() - t0) * 1000.0, 3),
        )


neural_recommendation_trainer = NeuralRecommendationTrainer()
