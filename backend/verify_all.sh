#!/bin/bash

# Verification script for perfume recommendation system
# Tests all components: intent classification, spell correction, response generation

echo "🧪 Perfume Recommendation System - Complete Verification"
echo "=========================================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run test
run_test() {
    local test_name=$1
    local test_command=$2
    
    echo -e "${YELLOW}Testing: ${test_name}${NC}"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PASSED${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}❌ FAILED${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    echo ""
}

# 1. Import Tests
echo "📦 1. Import Tests"
echo "-------------------"
run_test "Response Generator Import" "python3 -c 'from app.response_generator import generate_human_response'"
run_test "Spell Corrector Import" "python3 -c 'from app.spell_corrector import correct_text'"
run_test "Intent Classifier Import" "python3 -c 'from app.intent_classifier import classify_intent'"
run_test "Chat Routes Import" "python3 -c 'from app.api.chat_routes import router'"
echo ""

# 2. Unit Tests
echo "🧪 2. Unit Tests"
echo "----------------"
run_test "Response Generator Tests" "python3 -m pytest tests/test_response_generator.py --tb=short -q"
if [ -f "tests/test_spell_corrector.py" ]; then
    run_test "Spell Corrector Tests" "python3 -m pytest tests/test_spell_corrector.py --tb=short -q"
fi
if [ -f "tests/test_intent_classifier.py" ]; then
    run_test "Intent Classifier Tests" "python3 -m pytest tests/test_intent_classifier.py --tb=short -q"
fi
echo ""

# 3. Integration Tests
echo "🔗 3. Integration Tests"
echo "-----------------------"
run_test "Full Chat Flow" "python3 -c '
from app.response_generator import generate_human_response, detect_vibe
from app.spell_corrector import correct_text
from app.intent_classifier import classify_intent

# Test spell correction
corrected, _ = correct_text(\"nikw perfume\")
assert \"nike\" in corrected.lower()

# Test intent classification
intent = classify_intent(\"luxury perfume for wedding\", [])
assert intent.intent.value == \"query\"

# Test vibe detection
vibe = detect_vibe(\"luxury perfume for wedding\")
assert vibe.primary_vibe.value == \"luxury\"

# Test response generation
recs = [{\"name\": \"Test\", \"brand\": \"Brand\", \"accords\": \"oud woody\", \"score\": 0.9}]
response = generate_human_response(recs, \"luxury perfume\", {})
assert \"message\" in response
assert \"🔥 Top pick\" in response[\"message\"]
print(\"All integration tests passed\")
'"
echo ""

# 4. Performance Tests
echo "⚡ 4. Performance Tests"
echo "-----------------------"
run_test "Response Generation Speed" "python3 -c '
import time
from app.response_generator import generate_human_response

recs = [{\"name\": \"Test\", \"brand\": \"Brand\", \"accords\": \"oud woody\", \"score\": 0.9}]
start = time.time()
for _ in range(100):
    generate_human_response(recs, \"luxury perfume\", {})
elapsed = (time.time() - start) / 100 * 1000
assert elapsed < 20, f\"Too slow: {elapsed}ms\"
print(f\"Average: {elapsed:.2f}ms\")
'"

run_test "Spell Correction Speed" "python3 -c '
import time
from app.spell_corrector import correct_text

start = time.time()
for _ in range(100):
    correct_text(\"nikw perfume for doir savage\")
elapsed = (time.time() - start) / 100 * 1000
assert elapsed < 15, f\"Too slow: {elapsed}ms\"
print(f\"Average: {elapsed:.2f}ms\")
'"

run_test "Vibe Detection Speed" "python3 -c '
import time
from app.response_generator import detect_vibe

start = time.time()
for _ in range(100):
    detect_vibe(\"luxury perfume for wedding\")
elapsed = (time.time() - start) / 100 * 1000
assert elapsed < 5, f\"Too slow: {elapsed}ms\"
print(f\"Average: {elapsed:.2f}ms\")
'"
echo ""

# Summary
echo "=========================================================="
echo "📊 Test Summary"
echo "=========================================================="
echo -e "Total Tests:  ${TOTAL_TESTS}"
echo -e "Passed:       ${GREEN}${PASSED_TESTS}${NC}"
echo -e "Failed:       ${RED}${FAILED_TESTS}${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}🎉 ALL TESTS PASSED! System is ready for deployment.${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Please review the errors above.${NC}"
    exit 1
fi
