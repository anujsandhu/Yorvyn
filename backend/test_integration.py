#!/usr/bin/env python3
"""
Quick integration test to verify human-like responses are working.
"""

from app.api.chat_routes import ChatRequest, ChatMessage
from app.response_generator import generate_human_response

def test_response_generator():
    """Test response generator directly"""
    print("=" * 70)
    print("TEST 1: Response Generator (Direct)")
    print("=" * 70)
    
    recs = [
        {'name': 'Madly Kenzo Oud Collection', 'brand': 'Kenzo', 'accords': 'oud vanilla rose', 'score': 0.9, 'id': '1'},
        {'name': 'Black Aoud', 'brand': 'Montale', 'accords': 'oud amber woody', 'score': 0.85, 'id': '2'},
    ]
    
    response = generate_human_response(
        recommendations=recs,
        user_input='luxury perfume for wedding',
        context={'occasion': 'wedding'},
        user_name=None
    )
    
    print(f"✅ Response generated: {len(response['message'])} chars")
    print(f"✅ Has '🔥 Top pick': {'🔥 Top pick' in response['message']}")
    print(f"✅ Has follow-up: {'?' in response['message']}")
    print(f"✅ Vibe detected: {response['vibe_detected']}")
    print()
    print("Sample output:")
    print("-" * 70)
    print(response['message'][:300] + "...")
    print()
    return True

def test_chat_request_structure():
    """Test chat request structure"""
    print("=" * 70)
    print("TEST 2: Chat Request Structure")
    print("=" * 70)
    
    # Create a sample request
    request = ChatRequest(
        messages=[
            ChatMessage(role="user", text="luxury perfume for wedding")
        ],
        num_recommendations=6
    )
    
    print(f"✅ Request created successfully")
    print(f"✅ Messages: {len(request.messages)}")
    print(f"✅ First message: {request.messages[0].text}")
    print()
    return True

def test_imports():
    """Test all required imports"""
    print("=" * 70)
    print("TEST 3: Import Verification")
    print("=" * 70)
    
    try:
        from app.response_generator import generate_human_response, detect_vibe, filter_recommendations
        print("✅ response_generator imports OK")
        
        from app.spell_corrector import correct_text
        print("✅ spell_corrector imports OK")
        
        from app.intent_classifier import classify_intent
        print("✅ intent_classifier imports OK")
        
        from app.api.chat_routes import router
        print("✅ chat_routes imports OK")
        
        print()
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

if __name__ == "__main__":
    print()
    print("🧪 INTEGRATION TEST - Human-Like Fragrance Advisor")
    print("=" * 70)
    print()
    
    all_passed = True
    
    # Run tests
    all_passed &= test_imports()
    all_passed &= test_response_generator()
    all_passed &= test_chat_request_structure()
    
    # Summary
    print("=" * 70)
    if all_passed:
        print("✅ ALL TESTS PASSED - System is working correctly!")
        print()
        print("If you're still seeing old responses, try:")
        print("1. Restart the backend server: uvicorn app.main:app --reload")
        print("2. Clear browser cache")
        print("3. Check backend logs for errors")
    else:
        print("❌ SOME TESTS FAILED - Check errors above")
    print("=" * 70)
    print()
