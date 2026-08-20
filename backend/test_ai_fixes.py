"""
Test script to verify AI recommendation system fixes.

Tests all 7 bug fixes:
1. AI Hallucination & Dataset Usage
2. Budget Constraint Violations
3. Text-Card Mismatch
4. Weak Pre-Filtering
5. Missing Validation Layer
6. Wrong Category Inclusion
7. Context & Intent Misinterpretation
"""

import sys
import os

# Add backend to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.ai_recommendation_engine import get_ai_recommendations, initialize_ai_engine
from app.ai_text_generator import verify_text_product_alignment, generate_recommendation_text
from app.ml_model import recommender

# Initialize
print("Initializing AI recommendation engine...")
print(f"Backend dir: {backend_dir}")
print(f"Project root: {recommender.project_root}")
print(f"Data dir: {recommender.data_dir}")
print(f"Models dir: {recommender.models_dir}")

if recommender.data is None or len(recommender.data) == 0:
    print("ERROR: Dataset not loaded!")
    print("Please ensure data files exist in the data/ directory")
    sys.exit(1)

initialize_ai_engine()
print(f"Dataset loaded: {len(recommender.data)} perfumes\n")

# Test cases from bugfix.md
test_cases = [
    {
        "name": "Bug #1 & #2: Hallucination + Budget Violation",
        "query": "fresh citrus perfume for summer under ₹2000",
        "context": {"gender": "women", "season": "summer", "budget_max": 23.8},
        "expected": {
            "no_hallucinations": True,
            "budget_compliance": True,
            "max_price": 23.8
        }
    },
    {
        "name": "Bug #2: Budget Violation (woody oud)",
        "query": "woody oud under ₹2000",
        "context": {"gender": "men", "mood": "woody", "budget_max": 23.8},
        "expected": {
            "budget_compliance": True,
            "max_price": 23.8
        }
    },
    {
        "name": "Bug #3: Text-Card Mismatch",
        "query": "floral romantic for a date",
        "context": {"occasion": "date", "mood": "floral"},
        "expected": {
            "text_card_match": True
        }
    },
    {
        "name": "Bug #4 & #6: Weak Filtering + Wrong Category",
        "query": "fresh daily perfume",
        "context": {"occasion": "daily", "mood": "fresh"},
        "expected": {
            "no_samples_testers": True,
            "no_oils_mists": True,
            "min_rating": 3.0
        }
    },
    {
        "name": "Bug #7: Context Misinterpretation (summer)",
        "query": "fresh citrus for summer",
        "context": {"season": "summer", "mood": "fresh", "notes": ["citrus"]},
        "expected": {
            "no_heavy_notes": True
        }
    }
]

def check_hallucinations(recommendations):
    """Check if any recommendations have invalid IDs."""
    invalid_count = 0
    for rec in recommendations:
        idx = recommender._resolve_index(rec['id'])
        if idx is None:
            invalid_count += 1
            print(f"  ❌ HALLUCINATION: Invalid ID {rec['id']}")
    return invalid_count == 0

def check_budget_compliance(recommendations, budget_max):
    """Check if all recommendations are within budget."""
    violations = []
    for rec in recommendations:
        price = rec.get('price', 0)
        if price > budget_max:
            violations.append(f"{rec['name']} (${price:.2f} > ${budget_max:.2f})")
    
    if violations:
        print(f"  ❌ BUDGET VIOLATIONS: {len(violations)}")
        for v in violations:
            print(f"     - {v}")
    return len(violations) == 0

def check_text_card_match(text, recommendations):
    """Check if text mentions only products in recommendations."""
    alignment = verify_text_product_alignment(text, recommendations)
    if not alignment['is_aligned']:
        print(f"  ❌ TEXT-CARD MISMATCH: {alignment['missing_products']}")
        print(f"     Alignment rate: {alignment['alignment_rate']:.1%}")
    return alignment['is_aligned']

def check_no_samples_testers(recommendations):
    """Check if any recommendations are samples/testers."""
    noise_keywords = ['sample', 'tester', 'vial', 'decant', 'mini', 'gift set']
    violations = []
    for rec in recommendations:
        name = rec['name'].lower()
        if any(keyword in name for keyword in noise_keywords):
            violations.append(rec['name'])
    
    if violations:
        print(f"  ❌ SAMPLES/TESTERS FOUND: {violations}")
    return len(violations) == 0

def check_no_oils_mists(recommendations):
    """Check if any recommendations are oils/mists."""
    noise_keywords = ['oil', 'mist', 'body spray', 'lotion']
    violations = []
    for rec in recommendations:
        name = rec['name'].lower()
        if any(keyword in name for keyword in noise_keywords):
            violations.append(rec['name'])
    
    if violations:
        print(f"  ❌ OILS/MISTS FOUND: {violations}")
    return len(violations) == 0

def check_min_rating(recommendations, min_rating=3.0):
    """Check if all recommendations meet minimum rating."""
    violations = []
    for rec in recommendations:
        rating = rec.get('rating', 0)
        if rating < min_rating:
            violations.append(f"{rec['name']} (rating: {rating:.1f})")
    
    if violations:
        print(f"  ❌ LOW RATINGS: {violations}")
    return len(violations) == 0

def check_no_heavy_notes(recommendations):
    """Check if any recommendations have heavy notes (oud, amber, warm)."""
    heavy_keywords = ['oud', 'amber', 'heavy', 'warm', 'intense']
    violations = []
    for rec in recommendations:
        accords = rec.get('accords', '').lower()
        if any(keyword in accords for keyword in heavy_keywords):
            violations.append(f"{rec['name']} ({rec['accords'][:50]})")
    
    if violations:
        print(f"  ⚠️  HEAVY NOTES (should be light for summer): {len(violations)}")
        for v in violations[:3]:  # Show first 3
            print(f"     - {v}")
    return len(violations) == 0

# Run tests
print("=" * 80)
print("RUNNING AI RECOMMENDATION SYSTEM FIX TESTS")
print("=" * 80)

results = []

for i, test in enumerate(test_cases, 1):
    print(f"\n[Test {i}/{len(test_cases)}] {test['name']}")
    print(f"Query: \"{test['query']}\"")
    print(f"Context: {test['context']}")
    
    try:
        # Get recommendations
        result = get_ai_recommendations(
            user_query=test['query'],
            num_recommendations=6,
            user_context=test['context']
        )
        
        recommendations = result['recommendations']
        intent = result['intent']
        confidence = result['confidence']
        provider = result['provider']
        
        print(f"Provider: {provider} | Confidence: {confidence:.2f} | Results: {len(recommendations)}")
        
        # Generate text
        text = generate_recommendation_text(
            recommendations=recommendations,
            user_query=test['query'],
            intent=intent,
            provider=provider
        )
        
        # Run checks
        checks_passed = 0
        checks_total = 0
        
        expected = test['expected']
        
        if expected.get('no_hallucinations'):
            checks_total += 1
            if check_hallucinations(recommendations):
                print("  ✅ No hallucinations")
                checks_passed += 1
        
        if expected.get('budget_compliance'):
            checks_total += 1
            if check_budget_compliance(recommendations, expected['max_price']):
                print("  ✅ Budget compliance")
                checks_passed += 1
        
        if expected.get('text_card_match'):
            checks_total += 1
            if check_text_card_match(text, recommendations):
                print("  ✅ Text-card match")
                checks_passed += 1
        
        if expected.get('no_samples_testers'):
            checks_total += 1
            if check_no_samples_testers(recommendations):
                print("  ✅ No samples/testers")
                checks_passed += 1
        
        if expected.get('no_oils_mists'):
            checks_total += 1
            if check_no_oils_mists(recommendations):
                print("  ✅ No oils/mists")
                checks_passed += 1
        
        if expected.get('min_rating'):
            checks_total += 1
            if check_min_rating(recommendations, expected['min_rating']):
                print("  ✅ Minimum rating met")
                checks_passed += 1
        
        if expected.get('no_heavy_notes'):
            checks_total += 1
            if check_no_heavy_notes(recommendations):
                print("  ✅ No heavy notes")
                checks_passed += 1
        
        # Show sample results
        print(f"\n  Sample recommendations:")
        for j, rec in enumerate(recommendations[:3], 1):
            print(f"    {j}. {rec['name']} by {rec['brand']}")
            print(f"       Price: ${rec['price']:.2f} | Rating: {rec['rating']:.1f} | {rec['accords'][:50]}")
        
        print(f"\n  Generated text (first 150 chars):")
        print(f"    {text[:150]}...")
        
        results.append({
            'test': test['name'],
            'passed': checks_passed,
            'total': checks_total,
            'success_rate': checks_passed / checks_total if checks_total > 0 else 0
        })
        
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        results.append({
            'test': test['name'],
            'passed': 0,
            'total': 1,
            'success_rate': 0
        })

# Summary
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)

total_passed = sum(r['passed'] for r in results)
total_checks = sum(r['total'] for r in results)
overall_rate = total_passed / total_checks if total_checks > 0 else 0

for r in results:
    status = "✅ PASS" if r['success_rate'] == 1.0 else "⚠️  PARTIAL" if r['success_rate'] > 0 else "❌ FAIL"
    print(f"{status} {r['test']}: {r['passed']}/{r['total']} ({r['success_rate']:.0%})")

print(f"\nOVERALL: {total_passed}/{total_checks} checks passed ({overall_rate:.1%})")

if overall_rate >= 0.95:
    print("\n🎉 SUCCESS: All critical bugs fixed! (>= 95% pass rate)")
elif overall_rate >= 0.80:
    print("\n⚠️  PARTIAL SUCCESS: Most bugs fixed, some issues remain (80-95% pass rate)")
else:
    print("\n❌ FAILURE: Significant issues remain (< 80% pass rate)")
