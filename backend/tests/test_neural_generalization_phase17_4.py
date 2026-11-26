"""
Phase 17.4 Test Suite — Neural Recommendation Generalization & Production Readiness.

Covers Stages 1-10:
- Expanded Wikimedia dataset provenance, governance filtering, and non-production labeling
- Stage 1 root-cause fix + Two-Tower objectives & anti-collapse metrics
- Neural Ranker validation-disjoint fitting, feature ablation, and calibration (ECE/Brier)
- Pure-PyTorch Graph propagation across depths 1..3 over-smoothing analysis
- Sequential Transformer positional encoding, residual, and short-sequence fallback (<3)
- NeuralOutfitCompatibilityModel multi-item compatibility vs hard negatives + fallback
- Repeated multi-seed chronological holdout evaluation against Phase 17.0 baselines
- 9-gate Controlled Promotion Decision & rollback protection (refuses fake promotion)
- Live experiment bucketing, owner isolation, purchase auth gate, & API auth checks
"""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import UserContext, get_current_user
from backend.app.core.settings import settings
from backend.app.main import app
from backend.app.services.intelligence.capability_registry import State, garment_capabilities
from backend.app.services.intelligence.neural_generalization_benchmark import (
    evaluate_promotion_gates,
    run_phase17_4_generalization_benchmark,
)
from backend.app.services.intelligence.neural_recommendation_models import (
    MIN_SEQ_LEN_FOR_TRANSFORMER,
    NEURAL_REC_SCHEMA_VERSION,
    NeuralOutfitCompatibilityModel,
    save_neural_checkpoint,
)
from backend.app.services.intelligence.recommendation_algorithms import NeuralRecommendationAdapter
from backend.app.services.intelligence.recommendation_dataset_builder import (
    build_expanded_benchmark_dataset,
    build_outfit_compatibility_dataset,
    load_real_wikimedia_garment_catalog,
)
from backend.app.services.intelligence.recommendation_engine import FashionRecommendationEngine
from backend.app.services.intelligence.recommendation_experiments import (
    MIN_IMPRESSIONS_FOR_POWER,
    RecommendationExperimentManager,
)
from backend.app.services.intelligence.recommendation_profile import PreferenceProfileStore, recommendation_profile_store
from backend.app.services.ml.model_registry import unified_model_registry


@pytest.mark.requires_local_assets
def test_1_expanded_dataset_provenance_and_governance():
    wiki_items = load_real_wikimedia_garment_catalog()
    assert len(wiki_items) >= 60

    ds = build_expanded_benchmark_dataset(seed=42)
    assert ds["is_real_production_traffic"] is False
    assert len(ds["catalog_items"]) >= 65
    evs = ds["events"]
    assert any(not e.consent_verified for e in evs)
    assert any(e.license == "UNLICENSED_SCRAPE" for e in evs)

    outfits = build_outfit_compatibility_dataset(ds["catalog_items"], num_positive=20, num_negative=20, seed=42)
    pos = [o for o in outfits if o["label"] == 1.0]
    neg = [o for o in outfits if o["label"] == 0.0]
    assert len(pos) == 20 and len(neg) == 20
    assert all(2 <= len(o["items"]) <= 4 for o in outfits)


@pytest.mark.requires_local_assets
def test_2_phase17_4_benchmark_stages_1_through_9(tmp_path):
    report = run_phase17_4_generalization_benchmark(
        seeds=(42, 77),
        k=5,
        artifact_dir=str(tmp_path),
    )

    # Provenance & governance audit
    assert report.is_real_production_traffic is False
    assert report.rejected_governance_events >= 2
    assert report.leak_free_negative_sampling_verified is True
    assert "tiny" in report.stage1_diagnostic_note.lower()

    # Stage 3: Two-Tower objectives & non-collapsed embeddings
    assert set(report.two_tower_objectives.keys()) == {"bpr", "in_batch_infonce", "bpr_hard_negative"}
    for obj, stats in report.two_tower_objectives.items():
        assert stats["mean_item_cosine"] < 0.90, f"{obj} suffered representation collapse"
        assert stats["embedding_dim_std"] > 0.02
        assert stats["retrieval_recall_at_10"] > 0.0

    # Stage 4: Neural Ranker ablations & calibration
    assert {"full_verified", "embeddings_only", "calibrated_temp"} <= set(report.neural_ranker_ablations.keys())
    assert report.neural_ranker_ablations["calibrated_temp"]["ece"] <= 0.30

    # Stage 5: Graph propagation depth analysis
    assert {"layers_1", "layers_2", "layers_3"} <= set(report.graph_depth_analysis.keys())
    assert report.graph_depth_analysis["layers_2"]["p50_ms"] >= 0.0

    # Stage 6: Sequential short vs long separation & policy
    assert report.sequential_short_vs_long["min_seq_len_threshold"] == MIN_SEQ_LEN_FOR_TRANSFORMER
    assert "short_seq_policy_gated" in report.sequential_short_vs_long

    # Stage 7: Neural outfit compatibility learning
    assert report.outfit_compatibility["holdout_accuracy"] >= 0.65
    assert report.outfit_compatibility["holdout_ece"] <= 0.35

    # Stage 8: Repeated baseline comparisons exist
    for base in ("hybrid_balanced", "content_focus", "exploration_discovery", "popularity"):
        assert "ndcg_at_k" in report.baseline_summary[base]

    # Stage 9: Honest promotion refusal without real production scale
    for mid, dec in report.promotion_decisions.items():
        assert dec.promotion_approved is False, f"{mid} must not auto-promote on simulation data"
        assert dec.promoted_to_production is False
        assert "minimum_real_volume" in dec.failed_gates


@pytest.mark.requires_local_assets
def test_3_sequential_short_history_and_neural_outfit_adapter(tmp_path):
    ds = build_expanded_benchmark_dataset(seed=42)
    catalog = ds["catalog_items"]

    # Run generalization benchmark first into tmp_path? Just use freshly saved valid checkpoints for outfit + two_tower/seq
    from backend.app.services.intelligence.neural_recommendation_models import (
        SequentialTransformerRecommender,
        TwoTowerRecommendationModel,
        verify_and_load_neural_checkpoint,
    )

    tt = TwoTowerRecommendationModel()
    sq = SequentialTransformerRecommender()
    of = NeuralOutfitCompatibilityModel()

    tt_p = str(tmp_path / f"two_tower_recommender_{NEURAL_REC_SCHEMA_VERSION}.pt")
    sq_p = str(tmp_path / f"sequential_transformer_recommender_{NEURAL_REC_SCHEMA_VERSION}.pt")
    of_p = str(tmp_path / f"neural_outfit_compatibility_{NEURAL_REC_SCHEMA_VERSION}.pt")
    tt_sha = save_neural_checkpoint(tt_p, model_id="two_tower_recommender", version="17.4.0", state_dict=tt.state_dict(), extra_metadata={})
    sq_sha = save_neural_checkpoint(sq_p, model_id="sequential_transformer_recommender", version="17.4.0", state_dict=sq.state_dict(), extra_metadata={})
    of_sha = save_neural_checkpoint(of_p, model_id="neural_outfit_compatibility", version="17.4.0", state_dict=of.state_dict(), extra_metadata={})

    adapter = NeuralRecommendationAdapter(checkpoint_dir=str(tmp_path))
    loaded = adapter.load_verified_checkpoints(
        two_tower_path=tt_p, two_tower_sha=tt_sha,
        seq_path=sq_p, seq_sha=sq_sha,
        outfit_path=of_p, outfit_sha=of_sha,
    )
    assert loaded["neural_outfit_compatibility"]["loaded"] is True

    # Tampered SHA must fail cleanly
    ok_bad, _, msg_bad = verify_and_load_neural_checkpoint(of_p, expected_sha256="f" * 64)
    assert ok_bad is False and "mismatch" in msg_bad.lower()

    # Short sequence (< 3) triggers short_sequence_policy_fallback and falls back cleanly in engine
    store = PreferenceProfileStore(sync_remote=False)
    store.record_interaction(owner_id="seq_user", interaction_type="liked", item_data=catalog[0], timestamp_s=100.0)
    store.record_interaction(owner_id="seq_user", interaction_type="saved", item_data=catalog[1], timestamp_s=200.0)
    engine = FashionRecommendationEngine(profile_store=store, neural_adapter=adapter)
    seq_short = engine.recommend(owner_id="seq_user", candidates=catalog, mode="neural_sequential", top_k=4)
    assert seq_short.neural_active is True  # Fell back to Two-Tower cleanly
    assert seq_short.neural_fallback_used is True

    # >= 3 interactions activates Transformer cleanly
    store.record_interaction(owner_id="seq_user", interaction_type="liked", item_data=catalog[2], timestamp_s=300.0)
    seq_long = engine.recommend(owner_id="seq_user", candidates=catalog, mode="neural_sequential", top_k=4)
    assert seq_long.neural_active is True
    assert seq_long.neural_fallback_used is False

    # Neural outfit scoring vs fallback when missing checkpoints
    outfit_neural = engine.recommend_outfit(owner_id="seq_user", candidates=catalog, max_outfits=2)
    assert outfit_neural.neural_compatibility_used is True
    assert outfit_neural.compatibility_backend == "neural_outfit_compatibility"
    assert outfit_neural.compatibility_is_prediction_not_rule is True

    empty_adapter = NeuralRecommendationAdapter(checkpoint_dir=str(tmp_path / "nonexistent"))
    fb_engine = FashionRecommendationEngine(profile_store=store, neural_adapter=empty_adapter)
    outfit_fb = fb_engine.recommend_outfit(owner_id="seq_user", candidates=catalog, max_outfits=2)
    assert outfit_fb.neural_compatibility_used is False
    assert outfit_fb.compatibility_backend == "algorithmic_pairwise"


def test_4_promotion_gates_experiments_and_api_routes(tmp_path, monkeypatch):
    from backend.app.core.settings import settings
    monkeypatch.setattr(settings, "admin_api_key", "test-admin-key-phase174")
    # Gate enforcement test: fail on non-real traffic, succeed only when ALL 9 real-world gates pass
    blocked = evaluate_promotion_gates(
        model_id="two_tower_recommender",
        version="17.4.0-rc1",
        is_real_production_traffic=False,
        accepted_events=1200,
        user_count=100,
        consent_compliant=True,
        leak_free=True,
        model_metrics={"ndcg": 0.70, "ece": 0.05, "mean_item_cosine": 0.2, "diversity": 0.65, "mean_latency_ms": 10.0},
        baseline_ndcg=0.50,
        baseline_diversity=0.50,
        checkpoint_path=None,
        checkpoint_sha256=None,
    )
    assert blocked.promotion_approved is False
    assert "minimum_real_volume" in blocked.failed_gates
    assert "checkpoint_sha256_verified" in blocked.failed_gates

    # Short-history (< 3) sequential adapter test also uses sync_remote=False cleanly above in test_3
    recommendation_profile_store.set_consent("exp_opt_out_u", False)
    mgr = RecommendationExperimentManager()
    opt_assign = mgr.assign_arm(owner_id="exp_opt_out_u")
    assert opt_assign["consent_granted"] is False
    assert opt_assign["assigned_arm"] == "control_unpersonalized"

    imp = mgr.log_impression(
        owner_id="exp_owner_1",
        recommended_items=[{"item_id": "item_a", "category": "tops"}, {"item_id": "item_b", "category": "bottoms"}],
    )
    # Cross-owner outcome rejected
    try:
        mgr.log_outcome(impression_id=imp.impression_id, owner_id="exp_intruder", item_id="item_a", outcome_type="click")
        assert False, "Expected PermissionError"
    except PermissionError:
        pass
    # Unauthorized purchase rejected cleanly
    res_purch = mgr.log_outcome(
        impression_id=imp.impression_id,
        owner_id="exp_owner_1",
        item_id="item_a",
        outcome_type="purchase",
        purchase_authorized=False,
    )
    assert res_purch["recorded"] is False
    assert "unauthorized" in res_purch["reason"].lower()
    mgr.log_outcome(impression_id=imp.impression_id, owner_id="exp_owner_1", item_id="item_a", outcome_type="save")
    rep = mgr.get_report()
    assert rep.statistically_powered is False
    assert rep.min_impressions_per_arm_required == MIN_IMPRESSIONS_FOR_POWER

    # Registry & capabilities check
    reg_ids = {m.model_id: m for m in unified_model_registry.get_yip_model_catalog()}
    assert "neural_outfit_compatibility" in reg_ids
    assert reg_ids["neural_outfit_compatibility"].verification_state == "DECLARED"
    assert garment_capabilities.get("recommendation.outfit_neural").availability == State.DECLARED
    assert garment_capabilities.get("recommendation.experiment").availability == State.EXECUTABLE
    assert garment_capabilities.get("recommendation.promote").availability == State.EXECUTABLE

    # Auth & admin guards on Phase 17.4 FastAPI routes
    client = TestClient(app)
    assert client.post("/api/intelligence/recommendations/experiments/assign", json={}).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: UserContext(
        user_id="p174_user", email="u@yorvyn.ai", role="user"
    )
    try:
        r_assign = client.post("/api/intelligence/recommendations/experiments/assign", json={})
        assert r_assign.status_code == 200
        assert r_assign.json()["owner_id"] == "p174_user"

        r_log = client.post(
            "/api/intelligence/recommendations/experiments/log",
            json={
                "action": "impression",
                "recommended_items": [{"item_id": "g1", "category": "tops"}],
            },
        )
        assert r_log.status_code == 200

        # Non-admin denied promotion / generalize routes
        assert client.post("/api/intelligence/recommendations/neural/generalize").status_code == 403
        assert client.post(
            "/api/intelligence/recommendations/neural/promote",
            json={"model_id": "two_tower_recommender"},
        ).status_code == 403

        # Admin promotion route executes and honestly blocks fake promotion
        r_prom = client.post(
            "/api/intelligence/recommendations/neural/promote",
            headers={"X-Admin-Key": "test-admin-key-phase174"},
            json={
                "model_id": "two_tower_recommender",
                "is_real_production_traffic": False,
                "accepted_events": 100,
                "user_count": 10,
            },
        )
        assert r_prom.status_code == 200
        assert r_prom.json()["promotion_approved"] is False
    finally:
        app.dependency_overrides.pop(get_current_user, None)
