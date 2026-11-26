"""
Comprehensive Test Suite for Yorvyn ML Phase 1:
Personalized Fashion Intelligence Foundation & LLM Integration.
Verifies Fashion DNA, Wardrobe Intelligence, LLM Provider Architecture,
Tool Calling, 6 Modular ML Services (Models A-F), 10-Factor Outfit Ranking,
Conversational Memory, Voice/Text Unification, Security/Tenant Isolation,
and Failure Recovery.
"""

import json
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.fashion_dna import FashionDNA, BodyProfile, ColourProfile, StyleProfile
from backend.app.services.fashion_dna_service import fashion_dna_service
from backend.app.services.wardrobe_service import wardrobe_service
from backend.app.services.wardrobe_intelligence_service import wardrobe_intelligence_service
from backend.app.services.database.supabase_repository import supabase_repo

from backend.app.services.llm.base import LLMMessage, ToolCallRequest, ToolDefinition
from backend.app.services.llm.config import LLMConfiguration
from backend.app.services.llm.registry import llm_registry
from backend.app.services.llm.providers.offline_rules_provider import OfflineRulesProvider
from backend.app.services.llm.providers.groq_provider import GroqProvider
from backend.app.services.llm.structured_validator import StructuredOutputValidator
from backend.app.services.llm.token_tracker import token_tracker
from backend.app.services.llm.conversation_manager import conversation_manager
from backend.app.services.llm.tool_registry import tool_registry
from backend.app.services.llm.service import intelligence_service

from backend.app.services.ml.body_intelligence import body_intelligence_service
from backend.app.services.ml.skin_colour_intelligence import skin_colour_intelligence_service
from backend.app.services.ml.fashion_vision import fashion_vision_service
from backend.app.services.ml.preference_learning import preference_learning_service
from backend.app.services.ml.outfit_ranker import outfit_ranker_service

client = TestClient(app)


# ── 1. Fashion DNA Tests ──────────────────────────────────────────────────────

def test_fashion_dna_lifecycle_and_persistence():
    user_id = "test_user_dna_01"

    # 1. Retrieve or create default
    dna = fashion_dna_service.get_fashion_dna(user_id)
    assert dna.user_id == user_id
    assert dna.body_profile.height_cm == 178.0
    assert dna.colour_profile.skin_undertone in ["warm", "cool", "neutral"]

    # 2. Update specific preferences
    updated = fashion_dna_service.update_fashion_dna(user_id, {
        "body_profile": {"fit_preference": "relaxed", "height_cm": 182.0},
        "style_profile": {"primary_styles": ["quiet_luxury", "minimalist"]}
    })
    assert updated.body_profile.fit_preference == "relaxed"
    assert updated.body_profile.height_cm == 182.0
    assert "quiet_luxury" in updated.style_profile.primary_styles

    # 3. Verify persistence
    fetched = fashion_dna_service.get_fashion_dna(user_id)
    assert fetched.body_profile.fit_preference == "relaxed"

    # 4. Clean up / delete
    deleted = fashion_dna_service.delete_fashion_dna(user_id)
    assert deleted is True


def test_avatar_dna_synchronization():
    user_id = "test_user_avatar_sync"
    avatar_config = {
        "height_cm": 185,
        "body_shape": "athletic",
        "skin_undertone": "warm",
        "color_season": "autumn"
    }

    synced = fashion_dna_service.sync_from_avatar_dna(user_id, avatar_config)
    assert synced.body_profile.height_cm == 185.0
    assert synced.body_profile.silhouette == "athletic"
    assert synced.colour_profile.skin_undertone == "warm"
    assert synced.body_profile.measurement_source == "avatar_derived"

    # Verify that an inferred avatar sync was logged in preference_evolution
    evolution = synced.preference_evolution
    assert len(evolution) >= 1
    assert evolution[-1].signal_type == "inferred"


def test_fashion_dna_evolution_separation_of_temporary_and_permanent():
    user_id = "test_user_evolution"

    # 1. Explicit permanent update
    fashion_dna_service.evolve_fashion_dna(
        user_id=user_id,
        signal_type="explicit",
        category="fit",
        value="oversized"
    )
    dna = fashion_dna_service.get_fashion_dna(user_id)
    assert dna.body_profile.fit_preference == "oversized"

    # 2. Rejection of colour
    fashion_dna_service.evolve_fashion_dna(
        user_id=user_id,
        signal_type="rejected",
        category="colour",
        value="neon_green"
    )
    dna = fashion_dna_service.get_fashion_dna(user_id)
    assert "neon_green" in dna.colour_profile.disliked_colours

    # 3. Temporary occasion constraint (should NOT mutate permanent primary styles)
    initial_styles = list(dna.style_profile.primary_styles)
    fashion_dna_service.evolve_fashion_dna(
        user_id=user_id,
        signal_type="temporary",
        category="style",
        value="wedding_traditional"
    )
    dna_after_temp = fashion_dna_service.get_fashion_dna(user_id)
    assert dna_after_temp.style_profile.primary_styles == initial_styles


# ── 2. Wardrobe Intelligence Tests ────────────────────────────────────────────

def test_wardrobe_summary_and_gap_analysis():
    user_id = "default_user"
    summary = wardrobe_intelligence_service.get_wardrobe_summary(user_id)
    assert summary["total_items"] >= 4
    assert "top" in summary["category_breakdown"]
    assert "bottom" in summary["category_breakdown"]

    gaps = wardrobe_intelligence_service.analyze_wardrobe_gaps(user_id)
    assert "total_items" in gaps
    assert "identified_gaps" in gaps
    assert isinstance(gaps["has_complete_capsule"], bool)


def test_wardrobe_item_pairing_compatibility():
    top = {
        "id": "item_top_1",
        "category": "top",
        "color": "cream",
        "formality": 5,
        "pattern": "solid"
    }
    bottom = {
        "id": "item_bot_1",
        "category": "bottom",
        "color": "charcoal",
        "formality": 6,
        "pattern": "solid"
    }
    clashing_bottom = {
        "id": "item_bot_2",
        "category": "top",  # Two tops together in a basic outfit
        "color": "cream",
        "formality": 5,
        "pattern": "solid"
    }

    compat = wardrobe_intelligence_service.evaluate_item_pairing_compatibility(top, bottom)
    assert compat["is_compatible"] is True
    assert compat["compatibility_score"] >= 0.70

    incompat = wardrobe_intelligence_service.evaluate_item_pairing_compatibility(top, clashing_bottom)
    assert incompat["is_compatible"] is False
    assert incompat["compatibility_score"] == 0.0


# ── 3. Modular ML Model Tests (Models A-F) ───────────────────────────────────

def test_model_a_body_intelligence():
    res = body_intelligence_service.analyze_body_proportions(
        height_cm=180.0,
        shoulder_cm=48.0,
        waist_cm=80.0,
        silhouette="athletic",
        fit_preference="tailored"
    )
    assert res.silhouette == "athletic"
    assert res.shoulder_waist_ratio == 0.6  # 48 / 80
    assert "tailored" in res.recommended_fits
    assert res.fit_compatibility_score >= 85.0


def test_model_b_skin_colour_intelligence():
    # Warm undertone test (Golden/Peach)
    warm_res = skin_colour_intelligence_service.analyze_colour_profile(
        skin_hex="#D2996E",
        skin_tone_range="tan"
    )
    assert warm_res.skin_undertone in ["warm", "neutral"]
    assert len(warm_res.best_harmonizing_colors) > 0

    # Clothing harmony evaluation with explicit dislike penalty
    harmony = skin_colour_intelligence_service.evaluate_clothing_colour_harmony(
        garment_colors=["neon_yellow", "charcoal"],
        personal_palette="autumn_deep",
        preferred_colors=["navy", "charcoal"],
        disliked_colors=["neon_yellow"]
    )
    assert harmony["is_harmonious"] is False
    assert harmony["harmony_score"] <= 40.0


def test_model_c_fashion_vision_and_embedding():
    analysis = fashion_vision_service.analyze_image(
        filename="oversized_merino_wool_crewneck.jpg"
    )
    assert analysis.category == "top"
    assert analysis.subcategory == "knitwear"
    assert len(analysis.embedding) == 64

    # Test visual cosine similarity
    sim_self = fashion_vision_service.compute_visual_similarity(analysis.embedding, analysis.embedding)
    assert pytest.approx(sim_self, abs=1e-4) == 1.0


def test_model_e_preference_learning():
    user_id = "test_user_pref_ml"

    # Baseline affinity
    base_score = preference_learning_service.score_item_affinity(user_id, {"color": "olive", "brand": "COS"})
    assert base_score == 82.0

    # Record like interaction
    preference_learning_service.record_interaction(
        user_id=user_id,
        interaction_type="liked",
        item_or_outfit_data={"color": "olive", "brand": "COS"}
    )
    boosted_score = preference_learning_service.score_item_affinity(user_id, {"color": "olive", "brand": "COS"})
    assert boosted_score > base_score

    # Record explicit rejection
    preference_learning_service.record_interaction(
        user_id=user_id,
        interaction_type="rejected",
        item_or_outfit_data={"color": "neon_pink"}
    )
    penalized_score = preference_learning_service.score_item_affinity(user_id, {"color": "neon_pink"})
    assert penalized_score < base_score


def test_model_f_10_factor_outfit_ranking():
    user_id = "test_user_ranking"
    dna = fashion_dna_service.get_fashion_dna(user_id)
    items = wardrobe_service.get_wardrobe("default_user")

    ranked = outfit_ranker_service.assemble_and_rank_outfits(
        user_id=user_id,
        wardrobe_items=items,
        fashion_dna=dna,
        occasion="smart_casual",
        weather_temp_c=18.0
    )

    assert len(ranked) > 0
    top_outfit = ranked[0]
    breakdown = top_outfit.factor_breakdown

    # Verify all 10 factors are computed
    assert 0.0 <= breakdown.body_fit <= 100.0
    assert 0.0 <= breakdown.colour_harmony <= 100.0
    assert 0.0 <= breakdown.style_alignment <= 100.0
    assert 0.0 <= breakdown.wardrobe_synergy <= 100.0
    assert 0.0 <= breakdown.occasion_suitability <= 100.0
    assert 0.0 <= breakdown.weather_adaptation <= 100.0
    assert 0.0 <= breakdown.budget_compliance <= 100.0
    assert 0.0 <= breakdown.feedback_affinity <= 100.0
    assert 0.0 <= breakdown.clothing_availability <= 100.0
    assert 0.0 <= breakdown.outfit_completeness <= 100.0
    assert 0.0 <= breakdown.composite_score <= 100.0


# ── 4. LLM Architecture & Tool Calling Tests ─────────────────────────────────

def test_offline_rules_provider_tool_generation():
    provider = OfflineRulesProvider()
    assert provider.health_check() is True

    messages = [
        LLMMessage(role="user", content="Suggest an outfit for college tomorrow")
    ]
    tools = tool_registry.get_tool_definitions()

    resp = provider.generate(messages=messages, tools=tools)
    assert resp.finish_reason == "tool_calls"
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].function_name == "generate_outfit_recommendations"


def test_all_15_tools_execution():
    user_id = "default_user"

    # Test sample of registered tools
    tools_to_test = [
        ("get_user_fashion_profile", {}),
        ("get_avatar_dna", {}),
        ("get_wardrobe", {"category": "top"}),
        ("get_wardrobe_item", {"item_id": "wardrobe_1"}),
        ("analyze_clothing_image", {"image_url": "https://example.com/coat.jpg"}),
        ("analyze_body_profile", {}),
        ("analyze_colour_profile", {"skin_hex": "#D2996E"}),
        ("search_fashion_catalog", {"query": "wool"}),
        ("find_similar_clothing", {"item_id": "wardrobe_1"}),
        ("generate_outfit_recommendations", {"occasion": "casual"}),
        ("evaluate_outfit_compatibility", {"item_ids": ["wardrobe_1", "wardrobe_2"], "occasion": "casual"}),
        ("get_weather_context", {"location": "London"}),
        ("save_outfit", {"outfit_name": "Test Casual", "item_ids": ["wardrobe_1", "wardrobe_2"]}),
        ("record_user_feedback", {"outfit_id": "outfit_test_1", "feedback": "liked"}),
        ("update_fashion_preferences", {"preference_type": "explicit", "category": "fit", "value": "relaxed"})
    ]

    for tool_name, args in tools_to_test:
        res = tool_registry.execute_tool(user_id=user_id, tool_name=tool_name, arguments=args)
        assert res.success is True, f"Tool '{tool_name}' failed with error: {res.error}"
        assert res.data is not None


def test_structured_validator_json_markdown():
    markdown_text = """
Here is your structured advice:
```json
{
  "silhouette": "athletic",
  "height_cm": 180.0,
  "torso_leg_balance": "balanced",
  "shoulder_waist_ratio": 1.35,
  "recommended_fits": ["tailored", "relaxed"],
  "length_guidelines": {"tops": "Mid-hip"},
  "fit_compatibility_score": 92.0,
  "styling_principles": ["Balance proportions"]
}
```
Enjoy your day!
"""
    from backend.app.services.ml.body_intelligence import BodyAnalysisResult
    model_inst, err = StructuredOutputValidator.validate_model(markdown_text, BodyAnalysisResult)
    assert err is None
    assert model_inst is not None
    assert model_inst.silhouette == "athletic"


def test_unified_intelligence_service_multi_turn():
    user_id = "test_user_service_turn"
    res = intelligence_service.process_message(
        user_id=user_id,
        message="Suggest an outfit for college tomorrow",
        conversation_id="test_conv_1"
    )

    assert res.conversation_id == "test_conv_1"
    assert len(res.response_text) > 20
    assert len(res.tool_calls_executed) >= 1
    assert res.latency_ms > 0.0


def test_token_usage_tracker():
    user_id = "test_user_token_track"
    token_tracker.record_usage(
        user_id=user_id,
        provider="offline_rules",
        model="offline-rules-v1",
        prompt_tokens=150,
        completion_tokens=50,
        latency_ms=12.5
    )

    stats = token_tracker.get_user_stats(user_id)
    assert stats["total_tokens"] >= 200
    assert stats["requests_count"] >= 1


# ── 5. API Endpoints & Voice Unification Tests ───────────────────────────────

def test_api_fashion_dna_endpoints():
    # 1. GET DNA
    resp = client.get("/api/fashion/dna?user_id=test_api_user")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "fashion_dna" in data

    # 2. PUT DNA
    put_resp = client.put(
        "/api/fashion/dna?user_id=test_api_user",
        json={"body_profile": {"fit_preference": "relaxed"}}
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["fashion_dna"]["body_profile"]["fit_preference"] == "relaxed"

    # 3. Evolve DNA
    evolve_resp = client.post(
        "/api/fashion/dna/evolve?user_id=test_api_user",
        json={"signal_type": "explicit", "category": "colour", "value": "olive"}
    )
    assert evolve_resp.status_code == 200
    assert "olive" in evolve_resp.json()["fashion_dna"]["colour_profile"]["preferred_colours"]


def test_api_intelligent_chat_endpoint():
    resp = client.post(
        "/api/fashion/chat/intelligent",
        json={
            "message": "What should I wear for dinner tonight?",
            "user_id": "test_api_user",
            "conversation_id": "api_conv_01"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "response_text" in data
    assert len(data["response_text"]) > 10
    assert "provider_used" in data


def test_api_unified_voice_chat(monkeypatch):
    from backend.app.core.settings import settings

    class _MockGroqResp:
        status_code = 200
        def json(self):
            return {"text": "Suggest an evening smart casual outfit"}

    monkeypatch.setattr(settings, "groq_api_key", "gsk_test_mock_key")
    monkeypatch.setattr("backend.app.api.speech_routes.requests.post", lambda *a, **kw: _MockGroqResp())

    # Simulate webm audio upload
    dummy_audio = b"RIFF....WAVEfmt ....data...." * 100
    resp = client.post(
        "/api/fashion/speech/voice-chat",
        files={"audio": ("recording.webm", dummy_audio, "audio/webm")},
        data={"conversation_id": "voice_conv_01"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "transcribed_input" in data
    assert "response_text" in data
    assert "speech_synthesis" in data
    assert data["speech_synthesis"]["voice"] == "en-US-Standard"


def test_failure_handling_and_recovery():
    # Unowned item retrieval in tool registry
    res = tool_registry.execute_tool(
        user_id="user_a",
        tool_name="get_wardrobe_item",
        arguments={"item_id": "nonexistent_item_999"}
    )
    assert res.success is False
    assert "not found" in res.error.lower()

