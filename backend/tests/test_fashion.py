"""
Unit tests for Yorvyn Fashion Intelligence Core
"""
import pytest
from backend.app.fashion.fashion_knowledge import (
    evaluate_color_harmony,
    get_thermal_layer_recommendations,
    STYLE_AESTHETICS,
    OCCASION_MATRIX
)
from backend.app.fashion.wardrobe_service import wardrobe_service
from backend.app.fashion.context_service import context_service
from backend.app.fashion.outfit_generator import outfit_generator
from backend.app.fashion.fashion_orchestrator import fashion_orchestrator

def test_color_harmony():
    score, desc = evaluate_color_harmony(["navy", "white", "camel"])
    assert score >= 0.8
    assert "harmony" in desc.lower() or "neutral" in desc.lower()

def test_thermal_layer_recommendations():
    winter = get_thermal_layer_recommendations(3.0, "rainy")
    assert winter["min_warmth_score"] >= 8
    assert winter["rain_protection"] is True
    
    summer = get_thermal_layer_recommendations(27.0, "clear")
    assert summer["min_warmth_score"] <= 2

def test_wardrobe_service_and_analytics():
    items = wardrobe_service.get_wardrobe("default_user")
    assert len(items) >= 5
    
    # Test filtering
    tops = wardrobe_service.get_wardrobe("default_user", category="top")
    assert all(i["category"] == "top" for i in tops)
    
    # Test analytics
    stats = wardrobe_service.get_closet_analytics("default_user")
    assert stats["total_items"] >= 5
    assert "top" in stats["category_breakdown"]

def test_context_parser():
    parsed = context_service.parse_context_from_query("Recommend an outfit for a business dinner in 12C rain")
    assert parsed["occasion"] in ["work_office", "date_night"]
    assert parsed["temperature_celsius"] == 12.0
    assert parsed["condition"] == "rainy"

def test_outfit_generator_and_scoring():
    res = outfit_generator.generate_outfits(
        user_id="default_user",
        occasion="work_office",
        temp_celsius=14.0,
        condition="clear",
        target_aesthetic="quiet_luxury"
    )
    assert "outfits" in res
    assert len(res["outfits"]) > 0
    top_look = res["outfits"][0]
    assert top_look["match_score"] > 60
    assert "layer_breakdown" in top_look
    assert "top" in top_look["layer_breakdown"]
    assert "bottom" in top_look["layer_breakdown"]
    assert "footwear" in top_look["layer_breakdown"]

def test_fashion_orchestrator_chat():
    chat_res = fashion_orchestrator.chat_stylist(
        message="What should I wear for a rainy date night in 10C?",
        user_id="default_user"
    )
    assert "reply" in chat_res
    assert len(chat_res["outfits"]) > 0
    assert "Date Night" in chat_res["reply"] or "10" in chat_res["reply"]
