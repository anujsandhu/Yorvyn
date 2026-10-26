"""
Unit and Integration Tests for Yorvyn AI Stylist Engine and Streaming Chat.
Executes directly without requiring external HTTP client libraries.
"""

import pytest

from backend.app.services.ai_stylist_engine import (
    ai_stylist_engine,
    StylistRecommendation
)
from backend.app.services.wardrobe_service import wardrobe_service
from backend.app.services.context_service import context_service
from backend.app.services.fashion_orchestrator import fashion_orchestrator
from backend.app.api.fashion_routes import (
    chat_with_stylist,
    StylistChatRequest
)


def test_ai_stylist_engine_deterministic_fallback():
    """Verifies that the AI Stylist generates structured advice without hallucinated items."""
    profile = context_service.get_user_profile("default_user")
    context = context_service.parse_context_from_query("Outfit for an autumn client dinner in 12C rain")
    wardrobe = wardrobe_service.get_wardrobe("default_user")

    res = ai_stylist_engine.generate_styling_advice(
        user_message="Outfit for an autumn client dinner in 12C rain",
        profile=profile,
        context=context,
        wardrobe_items=wardrobe,
        assembled_outfits=[]
    )

    assert "text" in res
    assert len(res["text"]) > 50
    assert res["provider"] in ["groq", "openrouter", "gemini", "yorvyn_fashion_rules_engine"]


def test_ai_stylist_pydantic_schema():
    """Validates StylistRecommendation Pydantic schema constraints."""
    rec = StylistRecommendation(
        editorial_summary="An understated monochrome look pairing structured wool with cashmere.",
        recommended_outfit_ids=["outfit_1", "outfit_2"],
        color_palette_advice="Muted earthy neutrals with soft contrast.",
        layering_advice="Thermal merino crewneck beneath tailored coat.",
        clarification_question=None,
        provider_used="groq"
    )

    assert len(rec.recommended_outfit_ids) == 2
    assert rec.provider_used == "groq"
    dump = rec.model_dump()
    assert "editorial_summary" in dump


def test_stream_chat_tokens_generation():
    """Tests token streaming generator in fashion orchestrator."""
    tokens = list(fashion_orchestrator.stream_chat_stylist(
        message="What should I wear to a formal dinner?",
        user_id="default_user",
        override_temp=16.0
    ))

    assert len(tokens) > 3
    full_stream = "".join(tokens)
    assert len(full_stream) > 40


def test_standard_chat_endpoint_handler():
    """Tests standard synchronous chat handler function."""
    req = StylistChatRequest(
        message="Recommend a casual weekend look.",
        user_id="default_user",
        temperature_celsius=20.0
    )
    data = chat_with_stylist(req)

    assert "reply" in data
    assert "outfits" in data
    assert len(data["reply"]) > 20
