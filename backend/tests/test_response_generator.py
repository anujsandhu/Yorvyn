"""
Tests for response generator module.
"""
import pytest
from app.response_generator import (
    VibeStyle,
    detect_vibe,
    generate_human_response,
    filter_recommendations,
    handle_vague_input,
    handle_refinement,
    get_hook,
    generate_top_pick_reason,
    generate_other_options,
    generate_mini_explanation,
    generate_follow_up,
)


class TestVibeDetection:
    def test_luxury_vibe(self):
        vibe = detect_vibe("premium oud perfume for special occasion")
        assert vibe.primary_vibe == VibeStyle.LUXURY
        assert vibe.confidence >= 0.3
        assert "oud" in vibe.notes_preference or "amber" in vibe.notes_preference
    
    def test_fresh_vibe(self):
        vibe = detect_vibe("light citrus perfume for daily wear")
        assert vibe.primary_vibe == VibeStyle.FRESH
        assert vibe.confidence > 0.5
        assert "citrus" in vibe.notes_preference
    
    def test_romantic_vibe(self):
        vibe = detect_vibe("perfume for date night with girlfriend")
        assert vibe.primary_vibe == VibeStyle.ROMANTIC
        assert vibe.confidence >= 0.3
    
    def test_bold_vibe(self):
        vibe = detect_vibe("strong perfume with good projection")
        assert vibe.primary_vibe == VibeStyle.BOLD
        assert vibe.confidence > 0.5
    
    def test_soft_vibe(self):
        vibe = detect_vibe("subtle perfume for office work")
        assert vibe.primary_vibe == VibeStyle.SOFT
        assert vibe.confidence > 0.5
    
    def test_mysterious_vibe(self):
        vibe = detect_vibe("dark smoky perfume for night")
        assert vibe.primary_vibe == VibeStyle.MYSTERIOUS
        assert vibe.confidence > 0.5
    
    def test_playful_vibe(self):
        vibe = detect_vibe("fun sweet perfume for party")
        assert vibe.primary_vibe == VibeStyle.PLAYFUL
        assert vibe.confidence > 0.5
    
    def test_professional_vibe(self):
        vibe = detect_vibe("professional perfume for business meeting")
        assert vibe.primary_vibe == VibeStyle.PROFESSIONAL
        assert vibe.confidence > 0.5
    
    def test_context_aware(self):
        vibe = detect_vibe("perfume", context={"occasion": "date"})
        assert vibe.primary_vibe == VibeStyle.ROMANTIC
        assert vibe.confidence > 0.5


class TestHooks:
    def test_luxury_hook(self):
        hook = get_hook(VibeStyle.LUXURY)
        assert "premium" in hook.lower() or "luxury" in hook.lower()
    
    def test_fresh_hook(self):
        hook = get_hook(VibeStyle.FRESH)
        assert "fresh" in hook.lower() or "clean" in hook.lower() or "crisp" in hook.lower()
    
    def test_occasion_specific_hook(self):
        hook = get_hook(VibeStyle.LUXURY, occasion="wedding")
        assert "wedding" in hook.lower()


class TestTopPickReason:
    def test_luxury_oud_perfume(self):
        perfume = {
            "name": "Black Aoud",
            "brand": "Montale",
            "accords": "oud amber woody"
        }
        vibe = detect_vibe("luxury perfume")
        reason = generate_top_pick_reason(perfume, vibe, {})
        
        assert "Black Aoud" in reason
        assert "🔥" in reason
        assert "oud" in reason.lower()
    
    def test_fresh_citrus_perfume(self):
        perfume = {
            "name": "Acqua di Gio",
            "brand": "Giorgio Armani",
            "accords": "citrus aquatic fresh"
        }
        vibe = detect_vibe("fresh perfume")
        reason = generate_top_pick_reason(perfume, vibe, {})
        
        assert "Acqua di Gio" in reason
        assert "🔥" in reason
        assert "citrus" in reason.lower() or "fresh" in reason.lower()


class TestOtherOptions:
    def test_generate_options(self):
        perfumes = [
            {"name": "Perfume 1", "accords": "woody fresh"},
            {"name": "Perfume 2", "accords": "spicy amber"},
            {"name": "Perfume 3", "accords": "citrus aquatic"},
        ]
        vibe = detect_vibe("fresh perfume")
        options = generate_other_options(perfumes, vibe)
        
        assert len(options) <= 4
        assert all("**" in opt for opt in options)
        assert all("→" in opt for opt in options)


class TestMiniExplanation:
    def test_luxury_explanation(self):
        perfumes = [
            {"accords": "oud amber woody"},
            {"accords": "oud spicy leather"},
        ]
        vibe = detect_vibe("luxury perfume")
        explanation = generate_mini_explanation(vibe, perfumes)
        
        assert "oud" in explanation.lower()
        assert "premium" in explanation.lower() or "quality" in explanation.lower()
    
    def test_fresh_explanation(self):
        perfumes = [
            {"accords": "citrus fresh aquatic"},
            {"accords": "green fresh clean"},
        ]
        vibe = detect_vibe("fresh perfume")
        explanation = generate_mini_explanation(vibe, perfumes)
        
        assert "fresh" in explanation.lower()
        assert "light" in explanation.lower() or "clean" in explanation.lower()


class TestFollowUp:
    def test_luxury_follow_up(self):
        vibe = detect_vibe("luxury perfume")
        follow_up = generate_follow_up(vibe, {})
        
        assert "?" in follow_up
        assert len(follow_up) > 10
    
    def test_occasion_specific_follow_up(self):
        vibe = detect_vibe("perfume")
        follow_up = generate_follow_up(vibe, {"occasion": "wedding"})
        
        assert "?" in follow_up
        assert "fresh" in follow_up.lower() or "bold" in follow_up.lower()


class TestFilterRecommendations:
    def test_remove_duplicates(self):
        recommendations = [
            {"name": "Dior Sauvage", "score": 0.9},
            {"name": "Dior Sauvage", "score": 0.8},
            {"name": "Bleu de Chanel", "score": 0.85},
        ]
        filtered = filter_recommendations(recommendations)
        
        assert len(filtered) == 2
        assert filtered[0]["name"] == "Dior Sauvage"
        assert filtered[1]["name"] == "Bleu de Chanel"
    
    def test_remove_samples(self):
        recommendations = [
            {"name": "Dior Sauvage", "score": 0.9},
            {"name": "Dior Sauvage Sample Set", "score": 0.8},
            {"name": "Dior Sauvage Tester", "score": 0.7},
            {"name": "Bleu de Chanel", "score": 0.85},
        ]
        filtered = filter_recommendations(recommendations)
        
        assert len(filtered) == 2
        assert all("sample" not in r["name"].lower() for r in filtered)
        assert all("tester" not in r["name"].lower() for r in filtered)
    
    def test_remove_low_scores(self):
        recommendations = [
            {"name": "Good Perfume", "score": 0.8},
            {"name": "Bad Perfume", "score": 0.2},
            {"name": "Another Good", "score": 0.7},
        ]
        filtered = filter_recommendations(recommendations)
        
        assert len(filtered) == 2
        assert all(r["score"] >= 0.3 for r in filtered)
    
    def test_max_six_recommendations(self):
        recommendations = [
            {"name": f"Perfume {i}", "score": 0.8} for i in range(10)
        ]
        filtered = filter_recommendations(recommendations)
        
        assert len(filtered) <= 6


class TestHumanResponse:
    def test_generate_response_with_recommendations(self):
        recommendations = [
            {"name": "Black Aoud", "brand": "Montale", "accords": "oud amber woody", "score": 0.9},
            {"name": "Oud Wood", "brand": "Tom Ford", "accords": "oud woody spicy", "score": 0.85},
        ]
        
        response = generate_human_response(
            recommendations=recommendations,
            user_input="luxury perfume for wedding",
            context={"occasion": "wedding"},
            user_name="Anuj"
        )
        
        assert "message" in response
        assert "Anuj" in response["message"]
        assert "🔥 Top pick" in response["message"]
        assert "Black Aoud" in response["message"]
        assert response["vibe_detected"] == "luxury"
        assert response["confidence"] >= 0.3
        assert "?" in response["message"]  # Has follow-up
        assert "top_pick_id" in response  # NEW: ID tracking
        assert "recommended_ids" in response  # NEW: ID list
        assert len(response["recommended_ids"]) > 0  # NEW: Has IDs
    
    def test_generate_response_no_recommendations(self):
        response = generate_human_response(
            recommendations=[],
            user_input="something random",
            context={},
        )
        
        assert "message" in response
        assert "couldn't find" in response["message"].lower() or "hmm" in response["message"].lower()
        assert response["confidence"] == 0.0
    
    def test_generate_response_without_name(self):
        recommendations = [
            {"name": "Dior Sauvage", "brand": "Dior", "accords": "fresh woody", "score": 0.9},
        ]
        
        response = generate_human_response(
            recommendations=recommendations,
            user_input="fresh perfume",
            context={},
            user_name=None
        )
        
        assert "message" in response
        assert "🔥 Top pick" in response["message"]


class TestVagueInput:
    def test_handle_vague(self):
        response = handle_vague_input("something good")
        
        assert "message" in response
        assert "vibe" in response["message"].lower()
        assert response["needs_clarification"] is True
        assert response["confidence"] == 0.0


class TestRefinement:
    def test_handle_stronger_refinement(self):
        previous = [
            {"name": "Perfume 1", "accords": "fresh citrus"},
        ]
        
        response = handle_refinement(
            previous_recommendations=previous,
            refinement="make it stronger",
            context={}
        )
        
        assert "message" in response
        assert "stronger" in response["message"].lower()
        assert response["is_refinement"] is True
    
    def test_handle_lighter_refinement(self):
        previous = [
            {"name": "Perfume 1", "accords": "oud woody"},
        ]
        
        response = handle_refinement(
            previous_recommendations=previous,
            refinement="make it lighter",
            context={}
        )
        
        assert "message" in response
        assert "lighter" in response["message"].lower()
        assert response["is_refinement"] is True


# Integration tests
class TestIntegration:
    def test_full_flow_luxury_wedding(self):
        # User input
        user_input = "luxury perfume for wedding"
        
        # Detect vibe
        vibe = detect_vibe(user_input, context={"occasion": "wedding"})
        assert vibe.primary_vibe == VibeStyle.LUXURY
        
        # Generate response
        recommendations = [
            {"name": "Black Aoud", "brand": "Montale", "accords": "oud amber woody", "score": 0.9},
            {"name": "Oud Wood", "brand": "Tom Ford", "accords": "oud woody spicy", "score": 0.85},
        ]
        
        response = generate_human_response(
            recommendations=recommendations,
            user_input=user_input,
            context={"occasion": "wedding"},
            user_name="Anuj"
        )
        
        # Assertions
        assert "Anuj" in response["message"]
        assert "wedding" in response["message"].lower()
        assert "🔥 Top pick" in response["message"]
        assert "Black Aoud" in response["message"]
        assert "?" in response["message"]
        assert response["vibe_detected"] == "luxury"
        assert response["confidence"] >= 0.3
        assert "top_pick_id" in response  # NEW: ID tracking
        assert "recommended_ids" in response  # NEW: ID list
    
    def test_full_flow_fresh_daily(self):
        # User input
        user_input = "fresh perfume for daily wear"
        
        # Detect vibe
        vibe = detect_vibe(user_input)
        assert vibe.primary_vibe == VibeStyle.FRESH
        
        # Generate response
        recommendations = [
            {"name": "Acqua di Gio", "brand": "Giorgio Armani", "accords": "citrus aquatic fresh", "score": 0.9},
        ]
        
        response = generate_human_response(
            recommendations=recommendations,
            user_input=user_input,
            context={},
        )
        
        # Assertions
        assert "🔥 Top pick" in response["message"]
        assert "Acqua di Gio" in response["message"]
        assert "fresh" in response["message"].lower()
        assert response["vibe_detected"] == "fresh"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
