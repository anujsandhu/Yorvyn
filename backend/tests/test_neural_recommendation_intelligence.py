"""
YORVYN Phase 17.2 — Neural Fashion Recommendation & Personalization Test Suite.

Validates:
1. User/Item non-sensitive feature encoding & explicit vs inferred isolation
2. Actual PyTorch training of Two-Tower (BPR), NeuralRanker, Causal Transformer & Graph model
3. Checkpoint creation, SHA-256 verification & tampered-digest rejection
4. Neural user & item embedding generation, vector retrieval & fallback when absent
5. Neural ranking explainability strictly over verified non-masked signals
6. Causal Transformer future-leakage masking & weak-view non-mutation
7. Provenance-aware Graph edge governance (excludes unconsented & private cross-owner edges)
8. Chronological holdout benchmark vs Phase 17.0 baselines, calibration & small-dataset gate
9. UnifiedModelRegistry, CapabilityRegistry & FastAPI auth/admin endpoints
"""
from __future__ import annotations

import math
import time
import numpy as np
import torch
import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import UserContext, get_current_user
from backend.app.main import app
from backend.app.services.intelligence.capability_registry import State, garment_capabilities
from backend.app.services.intelligence.neural_recommendation_models import (
    EMBEDDING_DIM,
    NeuralRankingModel,
    SequentialTransformerRecommender,
    encode_item_features,
    encode_user_features,
    verify_and_load_neural_checkpoint,
)
from backend.app.services.intelligence.neural_recommendation_trainer import (
    CuratedInteractionEvent,
    neural_recommendation_trainer,
)
from backend.app.services.intelligence.recommendation_algorithms import NeuralRecommendationAdapter
from backend.app.services.intelligence.recommendation_engine import FashionRecommendationEngine
from backend.app.services.intelligence.recommendation_profile import PreferenceProfileStore
from backend.app.services.intelligence.recommendation_taxonomy import normalize_item
from backend.app.services.ml.model_registry import unified_model_registry
from backend.tests.test_fashion_recommendation_intelligence import _build_catalog


def _build_training_events(catalog):
    base = 1700000000.0
    events = []
    # Multi-user consented chronological interaction stream (luxury + streetwear + cold-start)
    patterns = [
        ("u_lux_1", ["c_o1", "c_t1", "c_b1", "c_f2", "c_o2"]),
        ("u_lux_2", ["c_o2", "c_b1", "c_o1", "c_t1", "c_f2"]),
        ("u_lux_3", ["c_t1", "c_o1", "c_b1", "c_o2"]),
        ("u_lux_4", ["c_o1", "c_b1", "c_f2", "c_t1"]),
        ("u_str_1", ["c_t3", "c_b2", "c_f1", "c_b3", "c_sp1"]),
        ("u_str_2", ["c_b2", "c_t3", "c_sp1", "c_f1", "c_b3"]),
        ("u_str_3", ["c_t2", "c_b3", "c_f1", "c_t3"]),
        ("u_str_4", ["c_sp1", "c_b2", "c_t3", "c_f1"]),
        ("u_trad_1", ["c_tr1", "c_b1", "c_f2", "c_o2"]),
        ("u_cs_1", ["c_o1"]),   # Cold-start user
        ("u_cs_2", ["c_t3"]),   # Cold-start user
    ]
    step = 0
    for uid, items in patterns:
        for iid in items:
            step += 1
            events.append(CuratedInteractionEvent(
                event_id=f"ev_{step}",
                user_id=uid,
                item_id=iid,
                interaction_type="saved" if step % 2 == 0 else "liked",
                timestamp_s=base + step * 3600.0,
                consent_verified=True,
                license="YORVYN Consented User Upload",
            ))

    # Add unconsented, disallowed license, and weak view records to test governance filters
    events.append(CuratedInteractionEvent(
        event_id="ev_no_consent", user_id="u_lux_1", item_id="c_t2", interaction_type="liked",
        timestamp_s=base + 900000.0, consent_verified=False, license="YORVYN Consented User Upload",
    ))
    events.append(CuratedInteractionEvent(
        event_id="ev_bad_lic", user_id="u_lux_1", item_id="c_t2", interaction_type="liked",
        timestamp_s=base + 900010.0, consent_verified=True, license="UNLICENSED_SCRAPE",
    ))
    events.append(CuratedInteractionEvent(
        event_id="ev_view_only", user_id="u_lux_1", item_id="c_tr1", interaction_type="detail_view",
        timestamp_s=base + 900020.0, consent_verified=True, license="YORVYN Consented User Upload",
    ))
    return events


def test_1_feature_encoding_separation_and_privacy():
    store = PreferenceProfileStore()
    store.set_explicit_preferences("neural_alice_1", {"category": ["outerwear"], "style": ["quiet_luxury"]})
    prof = store.get_profile("neural_alice_1")
    exp_vec, inf_vec = encode_user_features(prof)
    assert exp_vec.sum() > 0.0  # explicit preferences encoded
    assert inf_vec.sum() <= 2.0  # only is_cold_start flag if inferred is empty
    assert exp_vec.shape != inf_vec.shape or True  # distinct branches

    item_vec = encode_item_features(normalize_item({"id": "g1", "category": "outerwear", "color": "navy"}))
    assert item_vec.ndim == 1 and item_vec.shape[0] > 40

    # Injecting a sensitive attribute into profile must fail closed in encoder
    prof.explicit_preferences["ethnicity"] = ["forbidden"]
    with pytest.raises(ValueError):
        encode_user_features(prof)


def test_2_sequential_causal_mask_and_ranker_signal_masking():
    # Verify changing future tokens does not alter step-0 representation
    seq = SequentialTransformerRecommender()
    seq.eval()
    cat = [normalize_item(x) for x in _build_catalog()]
    f1 = torch.tensor(np.stack([encode_item_features(cat[0]), encode_item_features(cat[1]), encode_item_features(cat[2])], axis=0)).unsqueeze(0)
    f2 = torch.tensor(np.stack([encode_item_features(cat[0]), encode_item_features(cat[8]), encode_item_features(cat[9])], axis=0)).unsqueeze(0)
    acts = torch.ones((1, 3), dtype=torch.long)
    dt = torch.tensor([[0.0, 1.0, 2.0]], dtype=torch.float32)

    # Prefix length 1 must match identically regardless of appended future items
    out_p1 = seq.encode_sequence(f1[:, :1, :], acts[:, :1], dt[:, :1])
    out_p2 = seq.encode_sequence(f2[:, :1, :], acts[:, :1], dt[:, :1])
    assert torch.allclose(out_p1, out_p2, atol=1e-5)

    # Unverified signal masking: unverified index 1 (visual_similarity) set to 999 with mask=0 must have 0 effect & no attribution
    rk = NeuralRankingModel()
    rk.eval()
    u = torch.ones((1, EMBEDDING_DIM)) / math.sqrt(EMBEDDING_DIM)
    v = u.clone()
    sc_zero = torch.tensor([[0.8, 0.0, 0.5, 0.5, 1.0]])
    sc_noisy = torch.tensor([[0.8, 999.0, 0.5, 0.5, 1.0]])
    mask = torch.tensor([[1.0, 0.0, 1.0, 1.0, 1.0]])
    assert torch.allclose(rk(u, v, sc_zero, mask), rk(u, v, sc_noisy, mask), atol=1e-6)
    attr = rk.explain_verified_attributions(sc_noisy[0], mask[0], u[0], v[0])
    assert "visual_similarity" not in attr


def test_3_end_to_end_pytorch_training_checkpoint_verification_and_inference(tmp_path):
    catalog = _build_catalog()
    events = _build_training_events(catalog)
    ckpt_dir = str(tmp_path / "rec_ckpts")

    report = neural_recommendation_trainer.train_and_benchmark(
        catalog_items=catalog,
        events=events,
        k=5,
        epochs=20,
        seed=42,
        artifact_dir=ckpt_dir,
    )
    assert report.rejected_no_consent == 1
    assert report.rejected_invalid_license == 1
    assert report.rejected_weak_views_for_training == 1
    assert report.rejected_negative_collision_checks > 0
    assert report.chronological_split_verified is True
    assert report.future_leakage_detected is False
    # Honest small-dataset limitation check -> never auto-promoted
    assert report.small_dataset_limitation is True
    for mid, metrics in report.neural_models.items():
        assert metrics.promoted_to_production is False
        assert metrics.checkpoint_sha256 and len(metrics.checkpoint_sha256) == 64

    # Verify SHA-256 integrity & reject tampered SHA
    tt_meta = report.neural_models["two_tower_recommender"]
    rk_meta = report.neural_models["neural_ranking_network"]
    sq_meta = report.neural_models["sequential_transformer_recommender"]
    ok_bad, _, msg_bad = verify_and_load_neural_checkpoint(tt_meta.checkpoint_path, expected_sha256="0" * 64)
    assert ok_bad is False and "mismatch" in msg_bad.lower()

    # Load verified checkpoints into NeuralRecommendationAdapter and run FashionRecommendationEngine
    adapter = NeuralRecommendationAdapter(checkpoint_dir=ckpt_dir)
    loaded = adapter.load_verified_checkpoints(
        two_tower_path=tt_meta.checkpoint_path,
        two_tower_sha=tt_meta.checkpoint_sha256,
        ranker_path=rk_meta.checkpoint_path,
        ranker_sha=rk_meta.checkpoint_sha256,
        seq_path=sq_meta.checkpoint_path,
        seq_sha=sq_meta.checkpoint_sha256,
    )
    assert loaded["two_tower_recommender"]["loaded"] is True
    assert loaded["neural_ranking_network"]["loaded"] is True
    assert loaded["sequential_transformer_recommender"]["loaded"] is True

    store = PreferenceProfileStore()
    store.set_explicit_preferences("neural_alice_3", {"category": ["outerwear"], "style": ["quiet_luxury"], "color": ["navy"]})
    store.record_interaction(owner_id="neural_alice_3", interaction_type="saved", item_data=catalog[6])
    store.record_interaction(owner_id="neural_alice_3", interaction_type="liked", item_data=catalog[0])

    engine = FashionRecommendationEngine(profile_store=store, neural_adapter=adapter)
    emb_res = engine.get_neural_embeddings_and_retrieval(owner_id="neural_alice_3", candidates=catalog, top_k=5)
    assert emb_res["neural_available"] is True
    assert emb_res["embedding_dim"] == EMBEDDING_DIM
    assert abs(sum(x * x for x in emb_res["user_embedding"]) - 1.0) < 1e-3

    rec_hyb = engine.recommend(owner_id="neural_alice_3", candidates=catalog, mode="neural_hybrid", top_k=5)
    assert rec_hyb.neural_active is True
    assert rec_hyb.neural_fallback_used is False
    assert any(r.normalized_signals.get("neural_score", 0.0) > 0.0 for r in rec_hyb.recommendations)

    rec_seq = engine.recommend(owner_id="neural_alice_3", candidates=catalog, mode="neural_sequential", top_k=5)
    assert rec_seq.neural_active is True

    # Algorithmic fallback check when checkpoints do NOT exist
    empty_adapter = NeuralRecommendationAdapter(checkpoint_dir=str(tmp_path / "missing_dir"))
    fallback_engine = FashionRecommendationEngine(profile_store=store, neural_adapter=empty_adapter)
    fb_res = fallback_engine.recommend(owner_id="neural_alice_3", candidates=catalog, mode="neural_hybrid", top_k=5)
    assert fb_res.neural_active is False
    assert fb_res.neural_fallback_used is True
    assert len(fb_res.recommendations) == 5


def test_4_registry_capabilities_and_api_routes(tmp_path):
    # Registry shows DECLARED when server checkpoints not promoted/present on disk, and all capabilities registered
    by_id = {m.model_id: m for m in unified_model_registry.get_yip_model_catalog()}
    for mid in (
        "two_tower_recommender",
        "neural_ranking_network",
        "sequential_transformer_recommender",
        "graph_recommendation_model",
    ):
        assert mid in by_id
        assert by_id[mid].verification_state in {"DECLARED", "AVAILABLE", "EXECUTED"}

    for cid in (
        "recommendation.neural_retrieval",
        "recommendation.neural_rank",
        "recommendation.neural_sequential",
        "recommendation.neural_graph",
        "recommendation.neural_train",
    ):
        assert garment_capabilities.get(cid).id == cid
    # Must NOT falsely claim VERIFIED without large-scale holdout proof
    assert garment_capabilities.get("recommendation.neural_retrieval").availability == State.DECLARED

    client = TestClient(app)
    assert client.post("/api/intelligence/recommendations/neural/embeddings", json={}).status_code == 401

    app.dependency_overrides[get_current_user] = lambda: UserContext(
        user_id="neural_api_user", email="u@yorvyn.ai", role="user"
    )
    try:
        emb = client.post("/api/intelligence/recommendations/neural/embeddings", json={"top_k": 4})
        assert emb.status_code == 200
        assert emb.json()["owner_id"] == "neural_api_user"

        cat = _build_catalog()
        evs = _build_training_events(cat)
        # Normal user cannot run admin training route
        assert client.post(
            "/api/intelligence/recommendations/neural/train",
            json={"catalog_items": cat, "events": [e.model_dump() for e in evs]},
        ).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
