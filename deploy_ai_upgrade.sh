#!/bin/bash

# AI Upgrade Deployment Script
# This script helps you deploy the AI-powered recommendation system

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   AI-Powered Perfume Recommendations - Deployment Script      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "backend/app/main.py" ]; then
    echo -e "${RED}❌ Error: Please run this script from the project root directory${NC}"
    exit 1
fi

echo -e "${BLUE}Step 1: Installing Python dependencies...${NC}"
cd backend

# Check if pip is available
if ! command -v pip &> /dev/null; then
    echo -e "${RED}❌ Error: pip is not installed${NC}"
    exit 1
fi

# Install dependencies
echo "Installing google-generativeai..."
pip install google-generativeai --quiet

echo "Installing openai..."
pip install openai --quiet

echo "Installing scikit-learn (if not already installed)..."
pip install scikit-learn --quiet

echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Check if .env file exists
echo -e "${BLUE}Step 2: Checking configuration...${NC}"

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  No .env file found. Creating template...${NC}"
    cat > .env << 'EOF'
# AI Providers (at least one required)
GEMINI_API_KEY=
OPENAI_API_KEY=

# AI Configuration
AI_FALLBACK_ENABLED=true
AI_FALLBACK_CONFIDENCE_THRESHOLD=0.6
AI_MAX_RESPONSE_TOKENS=150
AI_CACHE_TTL=3600

# Existing settings (keep your current values)
DEBUG=true
EOF
    echo -e "${GREEN}✅ Created .env template${NC}"
    echo -e "${YELLOW}⚠️  Please edit backend/.env and add your API keys:${NC}"
    echo "   - GEMINI_API_KEY (get from: https://makersuite.google.com/app/apikey)"
    echo "   - OPENAI_API_KEY (optional, get from: https://platform.openai.com/api-keys)"
    echo ""
    echo "After adding keys, run this script again."
    exit 0
fi

# Check if API keys are configured
source .env

if [ -z "$GEMINI_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}❌ Error: No AI API keys configured${NC}"
    echo "Please add at least one API key to backend/.env:"
    echo "   - GEMINI_API_KEY (recommended)"
    echo "   - OPENAI_API_KEY (optional fallback)"
    exit 1
fi

if [ -n "$GEMINI_API_KEY" ]; then
    echo -e "${GREEN}✅ Gemini API key configured${NC}"
fi

if [ -n "$OPENAI_API_KEY" ]; then
    echo -e "${GREEN}✅ OpenAI API key configured${NC}"
fi

echo ""

# Test backend startup
echo -e "${BLUE}Step 3: Testing backend...${NC}"
echo "Starting backend server (this may take 20-30 seconds)..."

# Start backend in background
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to be ready
echo "Waiting for backend to initialize..."
MAX_WAIT=60
WAITED=0

while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend is running${NC}"
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    echo -n "."
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${RED}❌ Backend failed to start within ${MAX_WAIT} seconds${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo ""

# Test the new endpoint
echo -e "${BLUE}Step 4: Testing AI endpoint...${NC}"
echo "Sending test query: 'fresh citrus for summer'..."

RESPONSE=$(curl -s -X POST http://localhost:8000/api/ai/chat-v2 \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "text": "fresh citrus for summer"}
    ],
    "num_recommendations": 6
  }')

# Check if response is valid JSON
if echo "$RESPONSE" | jq . > /dev/null 2>&1; then
    echo -e "${GREEN}✅ AI endpoint is working${NC}"
    
    # Extract key metrics
    CONFIDENCE=$(echo "$RESPONSE" | jq -r '.confidence // 0')
    PROVIDER=$(echo "$RESPONSE" | jq -r '.ai_provider // "unknown"')
    NUM_RECS=$(echo "$RESPONSE" | jq -r '.recommendations | length')
    
    echo ""
    echo "Test Results:"
    echo "  • AI Provider: $PROVIDER"
    echo "  • Confidence: $CONFIDENCE"
    echo "  • Recommendations: $NUM_RECS"
    echo ""
    
    if [ "$PROVIDER" = "local" ]; then
        echo -e "${YELLOW}⚠️  Warning: Using local fallback (AI providers may not be working)${NC}"
        echo "Check your API keys and try again."
    fi
else
    echo -e "${RED}❌ AI endpoint returned invalid response${NC}"
    echo "Response: $RESPONSE"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

# Stop backend
echo ""
echo -e "${BLUE}Step 5: Cleaning up...${NC}"
kill $BACKEND_PID 2>/dev/null || true
echo -e "${GREEN}✅ Test complete${NC}"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    🎉 DEPLOYMENT SUCCESSFUL 🎉                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Next Steps:"
echo ""
echo "1. Start your backend:"
echo "   cd backend"
echo "   python -m uvicorn app.main:app --reload --port 8000"
echo ""
echo "2. Update your frontend to use the new endpoint:"
echo "   • Replace: apiClient.chat()"
echo "   • With: apiClient.chatV2()"
echo ""
echo "3. Test in your browser:"
echo "   • Try query: 'fresh citrus for summer'"
echo "   • Verify recommendations match explanation text"
echo "   • Check confidence scores (should be > 0.7)"
echo ""
echo "4. Monitor performance:"
echo "   • Check logs for AI provider usage"
echo "   • Monitor response times (should be 2-3s)"
echo "   • Track user feedback"
echo ""
echo "5. Deploy gradually:"
echo "   • Start with 10% A/B test"
echo "   • Monitor metrics"
echo "   • Gradually increase to 100%"
echo ""
echo "Documentation:"
echo "  • Quick Start: AI_UPGRADE_QUICKSTART.md"
echo "  • Full Docs: AI_UPGRADE_DOCUMENTATION.md"
echo "  • Integration: AI_UPGRADE_INTEGRATION_COMPLETE.md"
echo ""
echo "Need help? Check the troubleshooting section in the docs."
echo ""
