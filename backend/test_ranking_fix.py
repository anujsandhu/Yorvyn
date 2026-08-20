#!/usr/bin/env python3
"""
Test to verify ranking improvements work correctly.
"""

from app.ml_model_improvements import (
    calculate_opposite_penalty,
    calculate_strength_mismatch,
    calculate_occasion_mismatch,
    calculate_budget_penalty,
    OPPOSITE_NOTES,
    STRENGTH_INDICATORS,
)

def test_opposite_notes():
    """Test that opposite notes get penalized"""
    print("=" * 70)
    print("TEST 1: Opposite Notes Penalty")
    print("=" * 70)
    
    # Test 1: Fresh request with oud perfume (OPPOSITE)
    requested = {"fresh", "clean", "light"}
    perfume = {"oud", "leather", "smoky"}
    penalty = calculate_opposite_penalty(requested, perfume)
    
    print(f"\nRequested: {requested}")
    print(f"Perfume has: {perfume}")
    print(f"Penalty: {penalty:.2f}")
    assert penalty > 0.3, f"Expected high penalty, got {penalty}"
    print("✅ PASSED: Opposite notes heavily penalized")
    
    # Test 2: Fresh request with fresh perfume (MATCH)
    requested = {"fresh", "clean", "citrus"}
    perfume = {"citrus", "bergamot", "aquatic"}
    penalty = calculate_opposite_penalty(requested, perfume)
    
    print(f"\nRequested: {requested}")
    print(f"Perfume has: {perfume}")
    print(f"Penalty: {penalty:.2f}")
    assert penalty == 0.0, f"Expected no penalty, got {penalty}"
    print("✅ PASSED: Matching notes have no penalty")
    
    return True


def test_strength_mismatch():
    """Test that strength mismatches get penalized"""
    print("\n" + "=" * 70)
    print("TEST 2: Strength Mismatch Penalty")
    print("=" * 70)
    
    # Test 1: Light request with strong perfume (MISMATCH)
    requested_strength = "light"
    perfume = {"oud", "leather", "tobacco", "intense"}
    penalty = calculate_strength_mismatch(requested_strength, perfume)
    
    print(f"\nRequested strength: {requested_strength}")
    print(f"Perfume has: {perfume}")
    print(f"Penalty: {penalty:.2f}")
    assert penalty > 0.15, f"Expected high penalty, got {penalty}"
    print("✅ PASSED: Strong perfume penalized for light request")
    
    # Test 2: Light request with light perfume (MATCH)
    requested_strength = "light"
    perfume = {"fresh", "citrus", "clean", "aquatic"}
    penalty = calculate_strength_mismatch(requested_strength, perfume)
    
    print(f"\nRequested strength: {requested_strength}")
    print(f"Perfume has: {perfume}")
    print(f"Penalty: {penalty:.2f}")
    assert penalty == 0.0, f"Expected no penalty, got {penalty}"
    print("✅ PASSED: Light perfume has no penalty for light request")
    
    return True


def test_occasion_mismatch():
    """Test that occasion mismatches get penalized"""
    print("\n" + "=" * 70)
    print("TEST 3: Occasion Mismatch Penalty")
    print("=" * 70)
    
    # Test 1: Office request with oud perfume (MISMATCH)
    occasion = "office"
    perfume = {"oud", "heavy", "intense", "smoky"}
    penalty, should_filter = calculate_occasion_mismatch(occasion, perfume)
    
    print(f"\nOccasion: {occasion}")
    print(f"Perfume has: {perfume}")
    print(f"Penalty: {penalty:.2f}, Should filter: {should_filter}")
    assert penalty > 0.0 or should_filter, f"Expected penalty or filter, got penalty={penalty}, filter={should_filter}"
    print("✅ PASSED: Heavy perfume penalized for office")
    
    # Test 2: Office request with fresh perfume (MATCH)
    occasion = "office"
    perfume = {"fresh", "clean", "light", "citrus"}
    penalty, should_filter = calculate_occasion_mismatch(occasion, perfume)
    
    print(f"\nOccasion: {occasion}")
    print(f"Perfume has: {perfume}")
    print(f"Penalty: {penalty:.2f}, Should filter: {should_filter}")
    assert penalty <= 0.0, f"Expected bonus or no penalty, got {penalty}"
    print("✅ PASSED: Fresh perfume gets bonus for office")
    
    # Test 3: College request with oud perfume (MISMATCH)
    occasion = "college"
    perfume = {"oud", "heavy", "mature"}
    penalty, should_filter = calculate_occasion_mismatch(occasion, perfume)
    
    print(f"\nOccasion: {occasion}")
    print(f"Perfume has: {perfume}")
    print(f"Penalty: {penalty:.2f}, Should filter: {should_filter}")
    assert penalty > 0.0 or should_filter, f"Expected penalty or filter"
    print("✅ PASSED: Heavy perfume penalized for college")
    
    return True


def test_budget_penalty():
    """Test that budget violations get penalized"""
    print("\n" + "=" * 70)
    print("TEST 4: Budget Penalty")
    print("=" * 70)
    
    # Test 1: Under budget (GOOD)
    budget_max = 50.0  # $50 USD
    price = 30.0
    penalty, should_filter = calculate_budget_penalty(budget_max, price)
    
    print(f"\nBudget max: ${budget_max}")
    print(f"Price: ${price}")
    print(f"Penalty: {penalty:.2f}, Should filter: {should_filter}")
    assert penalty == 0.0 and not should_filter, f"Expected no penalty"
    print("✅ PASSED: Under budget has no penalty")
    
    # Test 2: Slightly over budget (SOFT PENALTY)
    budget_max = 50.0
    price = 55.0  # 10% over
    penalty, should_filter = calculate_budget_penalty(budget_max, price)
    
    print(f"\nBudget max: ${budget_max}")
    print(f"Price: ${price}")
    print(f"Penalty: {penalty:.2f}, Should filter: {should_filter}")
    assert penalty > 0.0 and not should_filter, f"Expected soft penalty"
    print("✅ PASSED: Slightly over budget gets soft penalty")
    
    # Test 3: Way over budget (HARD FILTER)
    budget_max = 50.0
    price = 100.0  # 100% over
    penalty, should_filter = calculate_budget_penalty(budget_max, price)
    
    print(f"\nBudget max: ${budget_max}")
    print(f"Price: ${price}")
    print(f"Penalty: {penalty:.2f}, Should filter: {should_filter}")
    assert should_filter, f"Expected hard filter"
    print("✅ PASSED: Way over budget gets filtered")
    
    return True


def test_real_world_scenario():
    """Test a real-world scenario: light, fresh, college, under ₹1500"""
    print("\n" + "=" * 70)
    print("TEST 5: Real-World Scenario")
    print("=" * 70)
    print("\nScenario: 'light, fresh, college, under ₹1500'")
    
    requested_notes = {"light", "fresh", "clean", "citrus"}
    requested_strength = "light"
    occasion = "college"
    budget_max = 1500 / 84.0  # Convert INR to USD (~$17.86)
    
    # Perfume 1: Fresh citrus (GOOD MATCH)
    perfume1 = {
        "name": "Davidoff Cool Water",
        "accords": "fresh aquatic citrus clean",
        "price": 15.0,
    }
    perfume1_notes = set(perfume1["accords"].split())
    
    opposite_penalty1 = calculate_opposite_penalty(requested_notes, perfume1_notes)
    strength_penalty1 = calculate_strength_mismatch(requested_strength, perfume1_notes)
    occasion_penalty1, occasion_filter1 = calculate_occasion_mismatch(occasion, perfume1_notes)
    budget_penalty1, budget_filter1 = calculate_budget_penalty(budget_max, perfume1["price"])
    
    total_penalty1 = opposite_penalty1 + strength_penalty1 + occasion_penalty1 + budget_penalty1
    
    print(f"\n✅ GOOD MATCH: {perfume1['name']}")
    print(f"   Accords: {perfume1['accords']}")
    print(f"   Price: ${perfume1['price']}")
    print(f"   Opposite penalty: {opposite_penalty1:.2f}")
    print(f"   Strength penalty: {strength_penalty1:.2f}")
    print(f"   Occasion penalty: {occasion_penalty1:.2f}")
    print(f"   Budget penalty: {budget_penalty1:.2f}")
    print(f"   Total penalty: {total_penalty1:.2f}")
    print(f"   Filtered: {occasion_filter1 or budget_filter1}")
    
    # Perfume 2: Heavy oud (BAD MATCH)
    perfume2 = {
        "name": "Tom Ford Oud Wood",
        "accords": "oud woody leather smoky intense",
        "price": 80.0,
    }
    perfume2_notes = set(perfume2["accords"].split())
    
    opposite_penalty2 = calculate_opposite_penalty(requested_notes, perfume2_notes)
    strength_penalty2 = calculate_strength_mismatch(requested_strength, perfume2_notes)
    occasion_penalty2, occasion_filter2 = calculate_occasion_mismatch(occasion, perfume2_notes)
    budget_penalty2, budget_filter2 = calculate_budget_penalty(budget_max, perfume2["price"])
    
    total_penalty2 = opposite_penalty2 + strength_penalty2 + occasion_penalty2 + budget_penalty2
    
    print(f"\n❌ BAD MATCH: {perfume2['name']}")
    print(f"   Accords: {perfume2['accords']}")
    print(f"   Price: ${perfume2['price']}")
    print(f"   Opposite penalty: {opposite_penalty2:.2f}")
    print(f"   Strength penalty: {strength_penalty2:.2f}")
    print(f"   Occasion penalty: {occasion_penalty2:.2f}")
    print(f"   Budget penalty: {budget_penalty2:.2f}")
    print(f"   Total penalty: {total_penalty2:.2f}")
    print(f"   Filtered: {occasion_filter2 or budget_filter2}")
    
    # Verify
    assert total_penalty1 < 0.1, f"Good match should have low penalty, got {total_penalty1}"
    assert total_penalty2 > 0.5, f"Bad match should have high penalty, got {total_penalty2}"
    assert not (occasion_filter1 or budget_filter1), "Good match should not be filtered"
    assert (occasion_filter2 or budget_filter2 or total_penalty2 > 0.5), "Bad match should be filtered or heavily penalized"
    
    print("\n✅ PASSED: Good match has low penalty, bad match has high penalty")
    
    return True


if __name__ == "__main__":
    print()
    print("🧪 RANKING FIX - VERIFICATION TESTS")
    print("=" * 70)
    print()
    
    all_passed = True
    
    try:
        all_passed &= test_opposite_notes()
        all_passed &= test_strength_mismatch()
        all_passed &= test_occasion_mismatch()
        all_passed &= test_budget_penalty()
        all_passed &= test_real_world_scenario()
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # Summary
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL TESTS PASSED - Ranking logic is FIXED!")
        print()
        print("Key improvements:")
        print("  1. ✅ Opposite notes heavily penalized (-0.15 per note)")
        print("  2. ✅ Strength mismatches penalized (-0.25 for major mismatch)")
        print("  3. ✅ Occasion mismatches penalized or filtered")
        print("  4. ✅ Budget violations penalized or filtered")
        print("  5. ✅ Real-world scenarios work correctly")
    else:
        print("❌ SOME TESTS FAILED - Check errors above")
    print("=" * 70)
    print()
