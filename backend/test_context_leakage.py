#!/usr/bin/env python3
"""
Test to verify context leakage is fixed.
"""

from app.api.chat_routes import _merge_context, _extract_intent, ChatMessage

def test_no_context_leakage():
    """Test that new queries don't leak context from previous queries"""
    print("=" * 70)
    print("TEST: Context Leakage Prevention")
    print("=" * 70)
    
    # Simulate conversation history
    messages = [
        ChatMessage(role="user", text="perfume for wedding"),
        ChatMessage(role="advisor", text="Here are some wedding perfumes..."),
        ChatMessage(role="user", text="perfume for college"),
    ]
    
    # Extract context WITHOUT refinement flag (new query)
    ctx = _merge_context(messages, user_ctx=None, is_refinement=False)
    
    print(f"\nQuery 1: 'perfume for wedding'")
    print(f"Query 2: 'perfume for college' (NEW QUERY)")
    print(f"\nExtracted context:")
    print(f"  - Occasion: {ctx.get('occasion')}")
    print(f"  - Mood: {ctx.get('mood')}")
    print(f"  - Season: {ctx.get('season')}")
    
    # Verify: Should be "college" or "daily", NOT "wedding"
    assert ctx.get('occasion') != 'wedding', "❌ FAILED: Context leaked from previous query!"
    assert ctx.get('occasion') in ['daily', 'office', None], f"❌ FAILED: Expected 'daily' or 'office', got '{ctx.get('occasion')}'"
    
    print(f"\n✅ PASSED: No context leakage detected!")
    print(f"✅ Context correctly extracted from latest message only")
    return True


def test_refinement_uses_context():
    """Test that refinements DO use previous context"""
    print("\n" + "=" * 70)
    print("TEST: Refinement Context Preservation")
    print("=" * 70)
    
    # Simulate conversation with refinement
    messages = [
        ChatMessage(role="user", text="perfume for wedding"),
        ChatMessage(role="advisor", text="Here are some wedding perfumes..."),
        ChatMessage(role="user", text="make it stronger"),
    ]
    
    # Extract context WITH refinement flag
    ctx = _merge_context(messages, user_ctx=None, is_refinement=True)
    
    print(f"\nQuery 1: 'perfume for wedding'")
    print(f"Query 2: 'make it stronger' (REFINEMENT)")
    print(f"\nExtracted context:")
    print(f"  - Occasion: {ctx.get('occasion')}")
    print(f"  - Mood: {ctx.get('mood')}")
    
    # Verify: Should preserve "wedding" context for refinement
    assert ctx.get('occasion') == 'wedding', f"❌ FAILED: Refinement should preserve context! Got '{ctx.get('occasion')}'"
    
    print(f"\n✅ PASSED: Refinement correctly preserves context")
    return True


def test_intent_extraction():
    """Test intent extraction for different occasions"""
    print("\n" + "=" * 70)
    print("TEST: Intent Extraction")
    print("=" * 70)
    
    test_cases = [
        ("perfume for wedding", "wedding"),
        ("perfume for college", "daily"),
        ("perfume for office", "office"),
        ("perfume for party", "party"),
        ("perfume for date", "date"),
    ]
    
    all_passed = True
    for query, expected_occasion in test_cases:
        intent = _extract_intent(query)
        actual_occasion = intent.get('occasion')
        
        if actual_occasion == expected_occasion:
            print(f"✅ '{query}' → occasion: {actual_occasion}")
        else:
            print(f"❌ '{query}' → expected: {expected_occasion}, got: {actual_occasion}")
            all_passed = False
    
    if all_passed:
        print(f"\n✅ PASSED: All intent extractions correct")
    else:
        print(f"\n⚠️  PARTIAL: Some intent extractions need adjustment")
    
    return all_passed


def test_latest_message_only():
    """Test that only the latest message is used for new queries"""
    print("\n" + "=" * 70)
    print("TEST: Latest Message Only")
    print("=" * 70)
    
    # Simulate multiple different queries
    messages = [
        ChatMessage(role="user", text="perfume for wedding"),
        ChatMessage(role="advisor", text="..."),
        ChatMessage(role="user", text="perfume for party"),
        ChatMessage(role="advisor", text="..."),
        ChatMessage(role="user", text="perfume for office"),
    ]
    
    # Extract context (not a refinement)
    ctx = _merge_context(messages, user_ctx=None, is_refinement=False)
    
    print(f"\nQuery history:")
    print(f"  1. 'perfume for wedding'")
    print(f"  2. 'perfume for party'")
    print(f"  3. 'perfume for office' (LATEST)")
    print(f"\nExtracted context:")
    print(f"  - Occasion: {ctx.get('occasion')}")
    
    # Verify: Should ONLY use latest message
    assert ctx.get('occasion') == 'office', f"❌ FAILED: Should use latest message only! Got '{ctx.get('occasion')}'"
    assert ctx.get('occasion') != 'wedding', "❌ FAILED: Context leaked from first query!"
    assert ctx.get('occasion') != 'party', "❌ FAILED: Context leaked from second query!"
    
    print(f"\n✅ PASSED: Only latest message used")
    return True


if __name__ == "__main__":
    print()
    print("🧪 CONTEXT LEAKAGE FIX - VERIFICATION TESTS")
    print("=" * 70)
    print()
    
    all_passed = True
    
    try:
        all_passed &= test_no_context_leakage()
        all_passed &= test_refinement_uses_context()
        all_passed &= test_intent_extraction()
        all_passed &= test_latest_message_only()
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # Summary
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL TESTS PASSED - Context leakage is FIXED!")
        print()
        print("Key fixes:")
        print("  1. ✅ New queries use ONLY latest message")
        print("  2. ✅ Refinements preserve previous context")
        print("  3. ✅ No context leakage between queries")
        print("  4. ✅ Intent extraction works correctly")
    else:
        print("❌ SOME TESTS FAILED - Check errors above")
    print("=" * 70)
    print()
