"""
YORVYN Phase 17.0 Extension — Fashion Recommendation Intelligence Verification Suite.

Covers all 12 acceptance criteria & governance contracts:
1. Normalized fashion taxonomy reusing existing universal garment taxonomy + classifier aliases
2. Owner-isolated preference profile creation & explicit vs inferred separation
3. View-not-positive rule (product views stay in session and never create positive long-term affinity)
4. Time-decayed category & subcategory affinity updates
5. Content-based recommendations + verified local embedding similarity with semantic disclaimer
6. Collaborative filtering minimum multi-user thresholds (insufficient -> disabled; eligible -> peer signal)
7. Hybrid multi-signal ranking with versioned weights, diversity & exploration
8. Cold-start handling without fabricated profiles
9. Explainable ranking strictly backed by actual contributing signals
10. User feedback, consent, retention purge, purchase-authorization gate, sensitive trait blocklist & reset
11. Outfit composition, complementary pairings (prediction disclaimer) & wardrobe gap detection
12. Offline chronological evaluation (Precision@K, Recall@K, NDCG@K, MRR, Coverage, Diversity, Novelty, Cold-Start, Ablation)
13. Capability Registry (8 capabilities, CF kept non-VERIFIED), YIP Orchestrator, and FastAPI Auth/Route integration
"""
from __future__ import annotations

import math
import time
import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import UserContext, get_current_user
from backend.app.main import app
from backend.app.services.intelligence.capability_registry import State, garment_capabilities
from backend.app.services.intelligence.recommendation_engine import (
    FashionRecommendationEngine,
    RankingWeightsConfig,
)
from backend.app.services.intelligence.recommendation_evaluation import (
    ChronologicalEvent,
    recommendation_evaluator,
)
from backend.app.services.intelligence.recommendation_profile import PreferenceProfileStore
from backend.app.services.intelligence.recommendation_taxonomy import (
    get_taxonomy_summary,
    normalize_category_and_subcategory,
    normalize_item,
)
from backend.app.services.intelligence.yip_orchestrator import yip_orchestrator
from backend.app.services.ml.model_registry import unified_model_registry


def _build_catalog():
    return [
        {"id": "c_t1", "name": "Merino Knit Crew", "category": "tops", "subcategory": "sweater", "color": "navy", "style": ["quiet_luxury", "minimalist"], "fit": "regular", "material": "wool", "formality": 5, "popularity_score": 18, "freshness_days": 4, "visual_embedding": [0.9, 0.1, 0.0, 0.0]},
        {"id": "c_t2", "name": "Heavy Cotton Tee", "category": "tshirt", "subcategory": "t-shirt", "color": "white", "style": ["minimalist", "casual"], "fit": "relaxed", "material": "cotton", "formality": 2, "popularity_score": 30, "freshness_days": 12, "visual_embedding": [0.7, 0.2, 0.1, 0.0]},
        {"id": "c_t3", "name": "Oversized Fleece Hoodie", "category": "hoodie", "subcategory": "pullover_hoodie", "color": "charcoal", "style": ["streetwear"], "fit": "oversized", "material": "fleece", "formality": 2, "popularity_score": 25, "freshness_days": 8, "visual_embedding": [0.2, 0.8, 0.0, 0.1]},
        {"id": "c_b1", "name": "Tailored Charcoal Trousers", "category": "bottoms", "subcategory": "trousers", "color": "charcoal", "style": ["quiet_luxury", "formalwear"], "fit": "tailored", "material": "wool", "formality": 7, "popularity_score": 15, "freshness_days": 5, "visual_embedding": [0.1, 0.1, 0.9, 0.1]},
        {"id": "c_b2", "name": "Cargo Utility Pants", "category": "bottoms", "subcategory": "cargo pants", "color": "olive", "style": ["streetwear", "sportswear"], "fit": "relaxed", "material": "ripstop", "formality": 2, "popularity_score": 10, "freshness_days": 2, "visual_embedding": [0.1, 0.2, 0.1, 0.9]},
        {"id": "c_b3", "name": "Raw Selvedge Jeans", "category": "jeans", "subcategory": "jeans", "color": "navy", "style": ["casual", "streetwear"], "fit": "straight", "material": "denim", "formality": 3, "popularity_score": 22, "freshness_days": 20, "visual_embedding": [0.85, 0.15, 0.1, 0.0]},
        {"id": "c_o1", "name": "Structured Wool Blazer", "category": "outerwear", "subcategory": "blazer", "color": "navy", "style": ["quiet_luxury", "formalwear"], "fit": "tailored", "material": "wool", "formality": 8, "popularity_score": 12, "freshness_days": 3, "visual_embedding": [0.88, 0.12, 0.05, 0.0]},
        {"id": "c_o2", "name": "Camel Wool Overcoat", "category": "coat", "subcategory": "formal_coat", "color": "camel", "style": ["quiet_luxury"], "fit": "regular", "material": "virgin wool", "formality": 8, "popularity_score": 14, "freshness_days": 7, "visual_embedding": [0.6, 0.3, 0.2, 0.1]},
        {"id": "c_f1", "name": "Minimal Leather Sneakers", "category": "footwear", "subcategory": "sneakers", "color": "white", "style": ["minimalist", "streetwear"], "fit": "regular", "material": "leather", "formality": 3, "popularity_score": 26, "freshness_days": 6, "visual_embedding": [0.4, 0.4, 0.4, 0.4]},
        {"id": "c_f2", "name": "Leather Penny Loafers", "category": "footwear", "subcategory": "loafers", "color": "dark brown", "style": ["quiet_luxury", "formalwear"], "fit": "regular", "material": "leather", "formality": 8, "popularity_score": 8, "freshness_days": 15, "visual_embedding": [0.2, 0.2, 0.8, 0.0]},
        {"id": "c_tr1", "name": "Embroidered Silk Kurta", "category": "traditional", "subcategory": "kurta", "color": "cream", "style": ["traditional"], "fit": "regular", "material": "silk", "formality": 7, "popularity_score": 6, "freshness_days": 1, "visual_embedding": [0.0, 0.0, 0.2, 0.8]},
        {"id": "c_sp1", "name": "Technical Running Shell", "category": "sportswear", "subcategory": "windbreaker", "color": "black", "style": ["sportswear"], "fit": "slim", "material": "nylon", "formality": 2, "popularity_score": 9, "freshness_days": 2, "visual_embedding": [0.1, 0.7, 0.1, 0.3]},
    ]


def test_1_taxonomy_reuse_and_normalization():
    tax = get_taxonomy_summary()
    assert "tops" in tax["categories"]
    assert "bottoms" in tax["categories"]
    assert "outerwear" in tax["categories"]
    assert "sportswear" in tax["categories"]
    assert "formalwear" in tax["categories"]
    assert "streetwear" in tax["categories"]

    assert normalize_category_and_subcategory("T-Shirts") == ("tops", "tshirt")
    assert normalize_category_and_subcategory("blazer") == ("outerwear", "blazers")
    assert normalize_category_and_subcategory("cargo pants") == ("bottoms", "cargo_pants")
    item = normalize_item({"id": "x1", "name": "Oxford", "category": "shirt", "subcategory": "oxford_shirt", "color": "Sky Blue"})
    assert item.category == "tops"
    assert item.color == "sky blue"


def test_2_and_3_profile_isolation_view_non_promotion_and_time_decay():
    store = PreferenceProfileStore(half_life_days=30.0)
    now_s = time.time()

    # View alone must NOT promote a positive preference or turn off cold_start
    view_res = store.record_interaction(
        owner_id="alice",
        interaction_type="detail_view",
        item_data={"id": "c_tr1", "category": "traditional", "color": "cream"},
        session_id="sess_1",
        timestamp_s=now_s,
    )
    assert view_res["treated_as_positive_preference"] is False
    assert view_res["session_only"] is True
    p_view = store.get_profile("alice", reference_time_s=now_s)
    assert p_view.is_cold_start is True
    assert p_view.positive_interaction_count == 0
    assert p_view.view_only_count == 1
    assert "traditional" not in p_view.category_affinity

    # Older interaction (90 days ago = 3 half-lives -> weight / 8) vs recent outerwear save
    store.record_interaction(
        owner_id="alice",
        interaction_type="saved",
        item_data={"id": "c_t1", "category": "tops", "subcategory": "sweater", "color": "navy"},
        timestamp_s=now_s - (90.0 * 86400.0),
    )
    store.record_interaction(
        owner_id="alice",
        interaction_type="saved",
        item_data={"id": "c_o1", "category": "outerwear", "subcategory": "blazer", "color": "navy"},
        timestamp_s=now_s,
    )
    store.set_explicit_preferences("alice", {"fit": ["tailored"], "race": ["redacted"]})  # sensitive trait must be ignored

    p_alice = store.get_profile("alice", reference_time_s=now_s)
    p_bob = store.get_profile("bob", reference_time_s=now_s)
    assert p_alice.category_affinity["outerwear"] > p_alice.category_affinity["tops"]
    assert "tailored" in p_alice.explicit_preferences.get("fit", [])
    assert "race" not in p_alice.explicit_preferences
    assert p_alice.sensitive_traits_inferred is False
    assert p_bob.is_cold_start is True
    assert p_bob.positive_interaction_count == 0


def test_4_5_6_content_collaborative_gates_and_hybrid_explainable_ranking():
    store = PreferenceProfileStore()
    engine = FashionRecommendationEngine(profile_store=store)
    catalog = _build_catalog()
    now_s = time.time()

    # Alice prefers quiet_luxury + navy + wool outerwear/tops
    store.set_explicit_preferences("alice", {"category": ["outerwear", "tops"], "style": ["quiet_luxury"], "color": ["navy"]})
    store.record_interaction(owner_id="alice", interaction_type="saved", item_data=catalog[6], timestamp_s=now_s)
    store.record_interaction(owner_id="alice", interaction_type="liked", item_data=catalog[0], timestamp_s=now_s)
    store.record_interaction(owner_id="alice", interaction_type="disliked", item_data=catalog[4], timestamp_s=now_s)

    # 1. With < 5 multi-user histories, CF must NOT fabricate scores
    res_no_cf = engine.recommend(
        owner_id="alice",
        candidates=catalog,
        mode="hybrid",
        surface="wardrobe",
        query_embedding=[0.89, 0.11, 0.0, 0.0],
        top_k=6,
    )
    assert res_no_cf.collaborative_status.eligible is False
    assert all(r.normalized_signals["collaborative_relevance"] == 0.0 for r in res_no_cf.recommendations)
    assert all(
        all("Popular among" not in reason.message for reason in r.reasons)
        for r in res_no_cf.recommendations
    )
    # Disliked item c_b2 must stay out of top results
    assert "c_b2" not in [r.item_id for r in res_no_cf.recommendations[:4]]
    # Diversity & exploration should include >= 3 distinct categories across top 6
    assert len({r.category for r in res_no_cf.recommendations}) >= 3
    # Every recommendation carries valid signal-grounded reasons
    assert all(len(r.reasons) >= 1 and r.reasons[0].signal_value >= 0.0 for r in res_no_cf.recommendations)

    # 2. Content-only mode also surfaces relevant navy wool/tailored matches + visual similarity
    res_content = engine.recommend(
        owner_id="alice",
        candidates=catalog,
        mode="content",
        query_embedding=[0.89, 0.11, 0.0, 0.0],
        top_k=4,
    )
    assert res_content.recommendations[0].category in {"outerwear", "tops", "bottoms"}

    # 3. Once >= 5 consented users meet >= 3 positive interactions each, CF becomes eligible
    store.record_interaction(owner_id="alice", interaction_type="saved", item_data=catalog[3], timestamp_s=now_s)
    for idx in range(5):
        peer = f"peer_{idx}"
        for item in (catalog[0], catalog[6], catalog[7]):
            store.record_interaction(owner_id=peer, interaction_type="saved", item_data=item, timestamp_s=now_s)

    res_with_cf = engine.recommend(owner_id="alice", candidates=catalog, mode="collaborative", top_k=5)
    assert res_with_cf.collaborative_status.eligible is True
    assert res_with_cf.collaborative_status.active_user_count >= 5
    assert any(r.normalized_signals["collaborative_relevance"] > 0.0 for r in res_with_cf.recommendations)


def test_7_cold_start_and_governance_controls():
    store = PreferenceProfileStore()
    engine = FashionRecommendationEngine(profile_store=store)
    catalog = _build_catalog()

    cs = engine.recommend(owner_id="new_user_cold", candidates=catalog, occasion="formal", top_k=5)
    assert cs.cold_start_mode is True
    assert cs.profile_fabricated is False
    assert len(cs.recommendations) == 5

    # Unauthorized purchase history rejected
    p_denied = store.record_interaction(
        owner_id="new_user_cold",
        interaction_type="purchase",
        item_data=catalog[0],
        purchase_authorized=False,
    )
    assert p_denied["recorded"] is False

    # Retention purge & consent opt-out & profile reset
    old_t = time.time() - (220 * 86400)
    store.record_interaction(owner_id="gov_u", interaction_type="liked", item_data=catalog[0], timestamp_s=old_t)
    purged = store.purge_expired_interactions("gov_u")
    assert purged == 1
    assert len(store.get_interactions("gov_u")) == 0

    store.record_interaction(owner_id="gov_u", interaction_type="liked", item_data=catalog[0])
    store.set_consent("gov_u", False)
    opt_out_res = engine.recommend(owner_id="gov_u", candidates=catalog, top_k=5)
    assert opt_out_res.consent_granted is False
    assert opt_out_res.recommendations == []

    store.set_consent("gov_u", True)
    reset_info = store.reset_profile("gov_u", scope="all")
    assert reset_info["purged_interactions"] == 1
    assert store.get_profile("gov_u").is_cold_start is True


def test_8_outfit_complementary_and_wardrobe_gaps():
    store = PreferenceProfileStore()
    engine = FashionRecommendationEngine(profile_store=store)
    catalog = _build_catalog()
    incomplete_wardrobe = [catalog[0], catalog[6]]  # tops + outerwear only (missing bottoms + footwear)

    out = engine.recommend_outfit(
        owner_id="stylist_user",
        candidates=incomplete_wardrobe,
        anchor_item=catalog[6],
        occasion="formal",
    )
    assert out.compatibility_is_prediction_not_rule is True
    gap_cats = {g["missing_category"] for g in out.wardrobe_gaps}
    assert "bottoms" in gap_cats
    assert "footwear" in gap_cats

    full_out = engine.recommend_outfit(
        owner_id="stylist_user",
        candidates=catalog,
        anchor_item=catalog[6],
        occasion="formal",
    )
    assert len(full_out.outfits) >= 1
    assert len(full_out.complementary_items) >= 1
    assert full_out.outfits[0].compatibility_prediction > 0.0


def test_9_offline_chronological_benchmark():
    catalog = _build_catalog()
    base_t = 1700000000.0
    events = []
    # 6 warm users + 2 chronological cold-start users (1 positive event)
    warm_patterns = [
        ("u1", ["c_o1", "c_t1", "c_b1", "c_f2"]),
        ("u2", ["c_o2", "c_t1", "c_b1", "c_o1"]),
        ("u3", ["c_t3", "c_b2", "c_f1", "c_b3"]),
        ("u4", ["c_t2", "c_b3", "c_f1", "c_t3"]),
        ("u5", ["c_o1", "c_b1", "c_f2", "c_o2"]),
        ("u6", ["c_sp1", "c_b2", "c_f1", "c_t3"]),
    ]
    step = 0
    for uid, items in warm_patterns:
        for iid in items:
            step += 1
            events.append(ChronologicalEvent(
                user_id=uid,
                item_id=iid,
                interaction_type="saved" if step % 2 == 0 else "liked",
                timestamp_s=base_t + step * 3600.0,
            ))
    # Recommendation acceptance & dismissal logs + cold start users
    events.append(ChronologicalEvent(user_id="cs1", item_id="c_t1", interaction_type="recommendation_clicked", timestamp_s=base_t + 90000.0))
    events.append(ChronologicalEvent(user_id="cs2", item_id="c_b1", interaction_type="saved", timestamp_s=base_t + 95000.0))
    events.append(ChronologicalEvent(user_id="u1", item_id="c_b2", interaction_type="recommendation_dismissed", timestamp_s=base_t + 1000.0))

    rep = recommendation_evaluator.evaluate_chronological(
        catalog_items=catalog,
        events=events,
        k=5,
        run_ablation=True,
        min_cf_users=5,
    )
    assert rep.chronological_split_enforced is True
    assert rep.future_leakage_detected is False
    assert rep.offline_metrics_do_not_equal_live_satisfaction is True
    assert rep.users_evaluated == 8
    assert rep.cold_start_users_evaluated == 2
    assert 0.0 <= rep.precision_at_k <= 1.0
    assert rep.ndcg_at_k > 0.0
    assert rep.mrr > 0.0
    assert rep.catalog_coverage > 0.0
    assert rep.category_diversity > 0.0
    assert rep.novelty > 0.0
    assert rep.logged_acceptance_rate is not None
    assert "hybrid_balanced" in rep.ablation_comparison
    assert "content_focus" in rep.ablation_comparison
    assert "exploration_discovery" in rep.ablation_comparison


@pytest.mark.asyncio
async def test_10_capability_registry_orchestrator_and_api_routes():
    # Registry check: all 8 capabilities registered, CF not marked VERIFIED
    for cid in (
        "recommendation.profile",
        "recommendation.category",
        "recommendation.content",
        "recommendation.collaborative",
        "recommendation.hybrid",
        "recommendation.outfit",
        "recommendation.feedback",
        "recommendation.evaluate",
    ):
        cap = garment_capabilities.get(cid)
        assert cap.id == cid
    assert garment_capabilities.get("recommendation.collaborative").availability != State.VERIFIED

    # Model registry includes recommendation adapter cleanly
    by_id = {m.model_id: m for m in unified_model_registry.get_yip_model_catalog()}
    assert "fashion-recommendation-engine" in by_id

    # Orchestrator coordinates recommendations cleanly when personalization enabled
    orch = await yip_orchestrator.execute_plan(
        owner_id="orch_rec_u",
        category="outerwear",
        subcategory="blazer",
        include_knowledge=False,
        include_personalization=True,
    )
    assert orch.recommendations is not None
    assert len(orch.recommendations.recommendations) >= 1

    # FastAPI endpoints: unauthenticated must return 401; authenticated works with owner scoping
    client = TestClient(app)
    assert client.get("/api/intelligence/recommendations/profile").status_code == 401
    assert client.post("/api/intelligence/recommendations/hybrid", json={}).status_code == 401

    app.dependency_overrides[get_current_user] = lambda: UserContext(
        user_id="api_rec_user", email="rec@yorvyn.ai", role="user"
    )
    try:
        r_tax = client.get("/api/intelligence/recommendations/taxonomy")
        assert r_tax.status_code == 200
        assert "tops" in r_tax.json()["categories"]

        r_pref = client.post(
            "/api/intelligence/recommendations/profile/preferences",
            json={"preferences": {"category": ["outerwear"], "color": ["navy"]}},
        )
        assert r_pref.status_code == 200
        assert "outerwear" in r_pref.json()["explicit_preferences"]["category"]

        r_hyb = client.post(
            "/api/intelligence/recommendations/hybrid",
            json={"surface": "design_studio", "occasion": "smart_casual", "top_k": 4},
        )
        assert r_hyb.status_code == 200
        assert r_hyb.json()["owner_id"] == "api_rec_user"
        assert len(r_hyb.json()["recommendations"]) >= 1

        r_out = client.post(
            "/api/intelligence/recommendations/outfit",
            json={"occasion": "formal", "max_outfits": 2},
        )
        assert r_out.status_code == 200
        assert r_out.json()["compatibility_is_prediction_not_rule"] is True

        r_fb = client.post(
            "/api/intelligence/recommendations/feedback",
            json={"interaction_type": "view", "item_data": {"id": "w1", "category": "tops"}, "session_id": "s_api"},
        )
        assert r_fb.status_code == 200
        assert r_fb.json()["treated_as_positive_preference"] is False

        # Non-admin user must be blocked from offline evaluation benchmark endpoint
        r_eval_forbidden = client.post(
            "/api/intelligence/recommendations/evaluate",
            json={"catalog_items": _build_catalog(), "events": []},
        )
        assert r_eval_forbidden.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
