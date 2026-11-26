# YORVYN — PHASE 17.2 NEURAL FASHION RECOMMENDATION & PERSONALIZATION REPORT

**Subsystem:** YORVYN Intelligence Platform (YIP) — Neural Fashion Recommendation Intelligence  
**Baseline HEAD:** `7139fc7eea4e1f890e28da9140db2e8550081267` (preserved; no commits created)

---

## 1. Architecture & Neural Modules Added

1. **User/Item Feature Encoding & PyTorch Models (`backend/app/services/intelligence/neural_recommendation_models.py`):**
   - `encode_user_features(...)` & `encode_item_features(...)` (`NEURAL_REC_SCHEMA_VERSION = "17.2.0"`): Strictly exclude sensitive attributes (`SENSITIVE_ATTRIBUTE_BLOCKLIST`), keep explicit user preference branches (`explicit_branch`) separated from time-decayed inferred interaction branches (`inferred_branch`), and project optional visual embeddings safely.
   - `TwoTowerRecommendationModel`: Independent user & item MLP encoders producing `32`-dim L2-normalized embeddings, trained with BPR pairwise ranking loss and negative sampling.
   - `NeuralRankingModel`: Combines user/item embeddings, Hadamard interactions, and `5` masked verified scalar context factors (`NEURAL_RANK_SIGNAL_NAMES`), blocking unverified signals (`mask=0`) from inference and explainable attributions.
   - `SequentialTransformerRecommender`: Time-aware causal Transformer (`nn.TransformerEncoder` with upper-triangular causal attention mask and sinusoidal `delta_days` embeddings) preventing future leakage and ignoring weak browsing views.
   - `GraphRecommendationModel`: Provenance-aware LightGCN-style normalized message passing over consented Users ↔ Garments ↔ Categories ↔ Styles (pure PyTorch; `torch_geometric` is not installed).
   - SHA-256 checkpoint helpers: `save_neural_checkpoint(...)` and `verify_and_load_neural_checkpoint(...)`.
2. **Offline Training, Governance & Holdout Benchmark Pipeline (`backend/app/services/intelligence/neural_recommendation_trainer.py`):**
   - Enforces consent & approved license gates (`APPROVED_DATASET_LICENSES`), weak-view exclusion (`view`/`detail_view` never trained as positives), strict chronological `train < val < holdout` splits, negative-sampling collision verification (`0` collisions), reproducible seeds, ECE / Brier calibration (`ConfidenceCalibrator`), and small-dataset non-promotion gates (`promoted_to_production = False`).
3. **Orchestration, Registry, API & UI Integration:**
   - Added `NeuralRecommendationAdapter` in `recommendation_algorithms.py` with automatic fallback to Phase 17.0 algorithms when verified checkpoints are absent.
   - Extended `FashionRecommendationEngine` (`mode="neural_hybrid" | "neural_retrieval" | "neural_ranking" | "neural_sequential"`, `get_neural_embeddings_and_retrieval`), `UnifiedModelRegistry`, `capability_registry.py` (`recommendation.neural_retrieval`, `recommendation.neural_rank`, `recommendation.neural_sequential`, `recommendation.neural_graph`, `recommendation.neural_train`), `/api/intelligence/recommendations/neural/{embeddings,train}` in `intelligence_routes.py`, and `intelligenceApi.ts` / `DigitalWardrobe.tsx` (without exposing embeddings or model internals to end users).

---

## 2. Empirical PyTorch Training & Chronological Holdout Benchmark (`seed=42`, `k=5`)

- **Governance Audit:** `45` events submitted -> `42` accepted (`1` rejected no consent, `1` rejected invalid license, `1` weak view excluded); `44` negative-sampling collision checks verified (`0` leaks); `chronological_split_verified = true`; `future_leakage_detected = false`; `small_dataset_limitation = true` (`42` positive interactions / `11` users < `120` / `25` threshold -> all `promoted_to_production = false`).

| Model / Baseline | Precision@5 | Recall@5 | NDCG@5 | MRR | Coverage | Diversity | Novelty | ECE | ColdStart NDCG@5 | p50 (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `hybrid_balanced` (Baseline) | `0.1455` | `0.7273` | `0.4380` | `0.3439` | `1.0000` | `0.7455` | `3.5160` | — | `0.1934` | `2.961` |
| `content_focus` (Baseline) | `0.1636` | `0.8182` | `0.5345` | `0.4424` | `0.9167` | `0.7636` | `3.5250` | — | `0.2153` | `2.708` |
| `popularity` (Baseline) | `0.1455` | `0.7273` | `0.4657` | `0.3788` | `0.6667` | `0.6727` | `3.1485` | — | `0.7500` | `0.002` |
| `two_tower_recommender` | `0.1818` | `0.9091` | `0.7413` | `0.6818` | `1.0000` | `0.8000` | `3.6220` | `0.2864` | `0.3155` | `0.134` |
| `neural_ranking_network` | `0.1818` | `0.9091` | `0.7413` | `0.6818` | `1.0000` | `0.8182` | `3.5723` | `0.1686` | `0.5000` | `2.246` |
| `sequential_transformer_recommender` | `0.0909` | `0.4545` | `0.2617` | `0.2000` | `0.8333` | `0.7273` | `3.2842` | `0.4040` | `0.3155` | `0.299` |
| `graph_recommendation_model` | `0.1818` | `0.9091` | `0.7413` | `0.6818` | `1.0000` | `0.8364` | `3.6482` | `0.2694` | `0.3155` | `0.050` |

**Key Engineering Finding:** On small benchmark interactions, Two-Tower, Neural Ranker, and pure-PyTorch Graph Propagation achieved higher offline NDCG@5 (`0.7413`) than `content_focus` (`0.5345`) while Causal Transformer lagged (`0.2617`) due to short interaction histories (`3–5` events per user). Because host datasets lack large-scale consented multi-user production traffic (`>= 120` interactions / `>= 25` users), promotion gates correctly keep `promoted_to_production = false` and retain Phase 17.0 algorithmic fallbacks in production.

---

## 3. Honest Classification & Verification Status

- **Model Classifications:**
  - `two_tower_recommender`, `neural_ranking_network`, `sequential_transformer_recommender`, `graph_recommendation_model`: **`DECLARED`** in live default registry (`models/checkpoints/recommendation_v17_2/` unpromoted); **`EXECUTED`** in offline benchmark & test runs with `.pt` checkpoints + verified SHA-256 digests (`29127b67...`, `fb4013ac...`, `287c8f1a...`, `80e5a2f5...`). None promoted to production `VERIFIED` pending full-scale interaction datasets.
  - Training/Evaluation Pipeline (`recommendation.neural_train`) & Fallback Orchestration: **`EXECUTED` / Test-Verified**.
- **Automated Verification (`pytest`):** **`129 passed, 4 warnings in 21.10s`** across 10 test files including [test_neural_recommendation_intelligence.py](file:///Users/anujsandhu/Projects/yorvyn/backend/tests/test_neural_recommendation_intelligence.py) (`4/4`) and [test_fashion_recommendation_intelligence.py](file:///Users/anujsandhu/Projects/yorvyn/backend/tests/test_fashion_recommendation_intelligence.py) (`10/10`).
- **Frontend Verification (`vitest` & build):** **`2 test files, 10 passed`** ([IntelligencePlatformIntegration.test.ts](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/components/__tests__/IntelligencePlatformIntegration.test.ts) `4/4` + [PhotoTo3DGarmentModalHandoff.test.tsx](file:///Users/anujsandhu/Projects/yorvyn/frontend/src/components/__tests__/PhotoTo3DGarmentModalHandoff.test.tsx) `6/6`); `tsc && vite build` **`✓ built in 5.47s`**.
