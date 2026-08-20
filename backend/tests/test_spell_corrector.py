"""
Tests for spell corrector module.
"""
import pytest
from app.spell_corrector import (
    correct_brand_name,
    correct_perfume_name,
    correct_note,
    correct_text,
    extract_brand_and_perfume,
    should_use_web_search,
    build_search_query,
    similarity_score,
    fuzzy_match,
)


class TestSimilarityScore:
    def test_identical_strings(self):
        assert similarity_score("dior", "dior") == 1.0
    
    def test_similar_strings(self):
        score = similarity_score("doir", "dior")
        assert score > 0.8
    
    def test_different_strings(self):
        score = similarity_score("nike", "chanel")
        assert score < 0.3


class TestFuzzyMatch:
    def test_exact_match(self):
        candidates = ["dior", "chanel", "gucci"]
        assert fuzzy_match("dior", candidates) == "dior"
    
    def test_close_match(self):
        candidates = ["dior", "chanel", "gucci"]
        assert fuzzy_match("doir", candidates) == "dior"
    
    def test_no_match(self):
        candidates = ["dior", "chanel", "gucci"]
        assert fuzzy_match("xyz", candidates) is None
    
    def test_threshold(self):
        candidates = ["dior"]
        # Low threshold - should match
        assert fuzzy_match("doir", candidates, threshold=0.7) == "dior"
        # High threshold - should not match
        assert fuzzy_match("xyz", candidates, threshold=0.9) is None


class TestBrandCorrection:
    def test_correct_brand_typo(self):
        corrected, was_corrected = correct_brand_name("doir")
        assert corrected == "dior"
        assert was_corrected is True
    
    def test_correct_brand_already_correct(self):
        corrected, was_corrected = correct_brand_name("dior")
        assert corrected == "dior"
        assert was_corrected is False
    
    def test_correct_brand_fuzzy(self):
        corrected, was_corrected = correct_brand_name("chanell")
        assert corrected == "chanel"
        assert was_corrected is True
    
    def test_correct_brand_unknown(self):
        corrected, was_corrected = correct_brand_name("unknownbrand")
        assert corrected == "unknownbrand"
        assert was_corrected is False


class TestPerfumeCorrection:
    def test_correct_perfume_typo(self):
        corrected, was_corrected = correct_perfume_name("savage")
        assert corrected == "sauvage"
        assert was_corrected is True
    
    def test_correct_perfume_already_correct(self):
        corrected, was_corrected = correct_perfume_name("sauvage")
        assert corrected == "sauvage"
        assert was_corrected is False
    
    def test_correct_perfume_fuzzy(self):
        corrected, was_corrected = correct_perfume_name("aqua di gio")
        assert corrected == "acqua di gio"
        assert was_corrected is True


class TestNoteCorrection:
    def test_correct_note_typo(self):
        corrected, was_corrected = correct_note("ood")
        assert corrected == "oud"
        assert was_corrected is True
    
    def test_correct_note_already_correct(self):
        corrected, was_corrected = correct_note("oud")
        assert corrected == "oud"
        assert was_corrected is False
    
    def test_correct_note_fuzzy(self):
        corrected, was_corrected = correct_note("vanila")
        assert corrected == "vanilla"
        assert was_corrected is True


class TestTextCorrection:
    def test_correct_single_typo(self):
        corrected, corrections = correct_text("perfume like doir savage")
        assert "dior" in corrected
        assert "sauvage" in corrected
        assert len(corrections) == 2
    
    def test_correct_multiple_typos(self):
        corrected, corrections = correct_text("chanell perfume with ood and vanila")
        assert "chanel" in corrected
        assert "oud" in corrected
        assert "vanilla" in corrected
        assert len(corrections) == 3
    
    def test_correct_no_typos(self):
        corrected, corrections = correct_text("dior sauvage perfume")
        assert corrected == "dior sauvage perfume"
        assert len(corrections) == 0


class TestExtractBrandAndPerfume:
    def test_extract_brand_perfume_pattern(self):
        brand, perfume = extract_brand_and_perfume("dior sauvage")
        assert brand == "dior"
        assert perfume == "sauvage"
    
    def test_extract_by_pattern(self):
        brand, perfume = extract_brand_and_perfume("sauvage by dior")
        assert brand == "dior"
        assert perfume == "sauvage"
    
    def test_extract_with_typos(self):
        brand, perfume = extract_brand_and_perfume("doir savage")
        assert brand == "dior"
        # Note: perfume extraction may vary based on implementation
    
    def test_extract_no_match(self):
        brand, perfume = extract_brand_and_perfume("fresh citrus perfume")
        # Should return None for both if no brand/perfume detected
        assert brand is None or perfume is None


class TestShouldUseWebSearch:
    def test_use_web_search_with_corrections(self):
        corrections = ["doir → dior"]
        assert should_use_web_search("dior sauvage", corrections) is True
    
    def test_use_web_search_with_brand(self):
        assert should_use_web_search("dior perfume", []) is True
    
    def test_use_web_search_with_like_pattern(self):
        assert should_use_web_search("something like sauvage", []) is True
    
    def test_no_web_search_generic(self):
        assert should_use_web_search("fresh perfume", []) is False


class TestBuildSearchQuery:
    def test_build_query_with_brand_and_perfume(self):
        query = build_search_query("test", brand="dior", perfume="sauvage")
        assert "dior" in query
        assert "sauvage" in query
        assert "perfume" in query
    
    def test_build_query_with_brand_only(self):
        query = build_search_query("test", brand="dior")
        assert "dior" in query
        assert "perfume" in query
    
    def test_build_query_with_perfume_only(self):
        query = build_search_query("test", perfume="sauvage")
        assert "sauvage" in query
        assert "perfume" in query
    
    def test_build_query_generic(self):
        query = build_search_query("fresh citrus perfume")
        assert "fresh" in query or "citrus" in query


# Integration tests
class TestIntegration:
    def test_full_correction_flow(self):
        # User input with typo
        user_input = "perfume like doir savage"
        
        # Correct text
        corrected, corrections = correct_text(user_input)
        
        # Extract brand and perfume
        brand, perfume = extract_brand_and_perfume(corrected)
        
        # Check if web search should be used
        use_search = should_use_web_search(corrected, corrections)
        
        # Build search query
        search_query = build_search_query(corrected, brand, perfume)
        
        # Assertions
        assert "dior" in corrected
        assert "sauvage" in corrected
        assert len(corrections) > 0
        assert brand == "dior"
        assert use_search is True
        assert "dior" in search_query
        assert "sauvage" in search_query
    
    def test_no_correction_needed(self):
        # User input without typos
        user_input = "dior sauvage perfume"
        
        # Correct text
        corrected, corrections = correct_text(user_input)
        
        # Extract brand and perfume
        brand, perfume = extract_brand_and_perfume(corrected)
        
        # Check if web search should be used
        use_search = should_use_web_search(corrected, corrections)
        
        # Assertions
        assert corrected == user_input
        assert len(corrections) == 0
        assert brand == "dior"
        assert use_search is True  # Still use web search for specific brand


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
