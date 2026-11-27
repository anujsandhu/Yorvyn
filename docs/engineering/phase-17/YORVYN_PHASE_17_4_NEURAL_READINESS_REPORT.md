# YORVYN — PHASE 17.4 NEURAL RECOMMENDATION GENERALIZATION & READINESS REPORT

**Date:** 2026-11-26  
**Baseline Git HEAD:** `7139fc7eea4e1f890e28da9140db2e8550081267`  
**Scope:** Stage 1-10 neural recommendation generalization audit, expanded Wikimedia simulation benchmark, outfit compatibility modeling, promotion gate enforcement, and experimentation telemetry.

---

## 1. Stage 1 Root-Cause Diagnosis (Phase 17.2 Tie Artifact)

- Audited PostgreSQL (`yorvyn_persistence`) table counts and local datasets: zero real human production recommendation clickstream logs exist on this host.
- Identified three mathematical causes for identical Phase 17.2 `Precision@5=0.1818 / Recall@5=0.9091 / NDCG@5=0.7413` across Two-Tower, NeuralRanker, and Graph models:
  1. Small 12-item candidate set leaving 7-8 unseen holdout items at `k=5`.
  2. Training negative sampling excluding `user_all_positives` (`train | holdout`) rather than strictly `train_ids` alone.
  3. Downstream `NeuralRankingModel` consuming already-converged upstream Two-Tower embeddings paired with constant `0.5` scalar defaults.

---

## 2. Observed Multi-Seed Generalization Results (`k=5`, `seeds=[42, 77]`, 71 Real Wikimedia+Staple Items)

- **Dataset (`yorvyn_phase17_4_expanded_simulation`):** 71 items (66 real Wikimedia Commons CC-BY garments + 5 outerwear/bottoms/footwear staples), 36 warm users + 8 cold-start users, 406 submitted events (`332` accepted positive events, `74` rejected by governance/weak-view filtering), `is_real_production_traffic = false`, `leak_free_negative_sampling_verified = true`, total benchmark runtime `3386.99 ms`.
- **Algorithmic Baselines (Mean across seeds 42, 77):**
  - `hybrid_balanced`: `NDCG@5 = 0.3036`, `MRR = 0.3663`, `Coverage = 0.9155`, `Category Diversity = 0.6909`, `Cold-Start NDCG@5 = 0.5000`, `p50 = 3.676 ms`.
  - `content_focus`: `NDCG@5 = 0.3521`, `MRR = 0.3955`, `Coverage = 0.9437`, `Category Diversity = 0.6045`, `Cold-Start NDCG@5 = 0.4866`, `p50 = 3.500 ms`.
  - `exploration_discovery`: `NDCG@5 = 0.3245`, `MRR = 0.3807`, `Category Diversity = 0.8091`, `p50 = 3.643 ms`.
  - `popularity`: `NDCG@5 = 0.1525`, `Coverage = 0.1268`, `p50 = 0.0115 ms`.
- **Two-Tower Objectives & Anti-Collapse Check:**
  - `bpr`: `NDCG@5 = 0.2467 ± 0.0165`, `Recall@10 = 0.6988`.
  - `in_batch_infonce`: `NDCG@5 = 0.2007`, `MRR = 0.1951`, `Coverage = 0.7183`, `mean_item_cosine = 0.2322 ± 0.0262`, `embedding_dim_std = 0.1420`.
  - `bpr_hard_negative`: `NDCG@5 = 0.2130 ± 0.0154`, `Recall@10 = 0.5228`, `mean_item_cosine = 0.5797`, `embedding_dim_std = 0.1038`, `p50 = 0.1615 ms`.
- **Neural Ranker Ablations & Calibration (Validation-Disjoint Items):**
  - `embeddings_only`: `NDCG@5 = 0.2102 ± 0.0054`, `ECE = 0.2924`, `Brier = 0.1805`, `p50 = 0.1915 ms`.
  - `full_verified`: `NDCG@5 = 0.3229 ± 0.0047`, `ECE = 0.2181`, `Brier = 0.1378`, `Coverage = 0.8028`, `p50 = 0.2110 ms`.
  - `calibrated_temp`: `NDCG@5 = 0.3229 ± 0.0047`, `ECE = 0.2549`, `Brier = 0.1341`, `p50 = 0.2055 ms`.
- **Pure-PyTorch Graph Propagation Depth Analysis:**
  - `layers_1`: `NDCG@5 = 0.2514 ± 0.0037`, `over_smoothing_cosine = -0.0062`, `node_coverage = 0.9385`, `p50 = 0.329 ms`.
  - `layers_2`: `NDCG@5 = 0.2482 ± 0.0049`, `over_smoothing_cosine = -0.0020`, `Cold-Start NDCG@5 = 0.0625`, `p50 = 0.327 ms`.
  - `layers_3`: `NDCG@5 = 0.2611 ± 0.0045`, `over_smoothing_cosine = +0.0024`, `p50 = 0.3285 ms`.
- **Sequential Transformer (`MIN_SEQ_LEN_FOR_TRANSFORMER = 3`):**
  - `short_seq_policy_gated`: `NDCG@5 = 0.2646 ± 0.0040`, `Recall@10 = 0.6193`, `p50 = 0.387 ms`. Short interaction histories (`< 3`) route cleanly to Two-Tower / algorithmic hybrid fallback.
- **Neural Outfit Compatibility (`NeuralOutfitCompatibilityModel`):**
  - `train_outfits = 196`, `holdout_outfits = 84`, `holdout_accuracy = 0.9762`, `hard_negative_rejection_rate = 0.9787`, `holdout_ece = 0.0253`, `compatibility_is_prediction_not_rule = true`.

---

## 3. Promotion & Registry Classification Decision

- **All candidate neural models (`two_tower_recommender`, `neural_ranking_network`, `sequential_transformer_recommender`, `graph_recommendation_model`, `neural_outfit_compatibility`) remain `promotion_approved = false` (`DECLARED` until verified real traffic volume `>= 500` events and `>= 50` distinct users + holdout NDCG gain over `content_focus` baseline are satisfied).**
- Phase 17.0 `fashion-recommendation-engine` algorithmic hybrid stays the active production default, backed by `PreferenceProfileStore(sync_remote=...)` offline isolation, `RecommendationExperimentManager` (`MIN_IMPRESSIONS_FOR_POWER = 100`), and FastAPI routes under `/api/intelligence/recommendations/*`.

---

## 4. Verification Summary

- **Backend pytest (8 suites):** `77 passed` (`test_neural_generalization_phase17_4.py`, `test_neural_recommendation_intelligence.py`, `test_fashion_recommendation_intelligence.py`, `test_langgraph_tavily_phase17_3.py`, `test_phase17_yip.py`, `test_phase17_1_validation.py`, `test_durable_job_outbox_fault_injection.py`, `test_durable_job_publication_fix.py`).
- **Frontend vitest:** `2 test files, 10 passed` (`IntelligencePlatformIntegration.test.ts`, `PhotoTo3DGarmentModalHandoff.test.tsx`).
- **Frontend build (`tsc && vite build`):** exited `0` (`6.62s`).
