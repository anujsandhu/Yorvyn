#!/bin/bash
# Quick startup script for Yorvyn with ChatBot

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_PORT=8002
FRONTEND_PORT=5174
BACKEND_DIR="./backend"
FRONTEND_DIR="./frontend"

echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Yorvyn ChatBot - Quick Start                      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if we're in the right directory
if [ ! -d "$BACKEND_DIR" ] || [ ! -d "$FRONTEND_DIR" ]; then
    echo -e "${RED}❌ Error: backend/ and frontend/ directories not found${NC}"
    echo -e "${YELLOW}Please run this script from the project root directory${NC}"
    exit 1
fi

# Function to check if port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"
    
    # Kill any background processes
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
        echo -e "${GREEN}✓${NC} Backend stopped (PID: $BACKEND_PID)"
    fi
    
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
        echo -e "${GREEN}✓${NC} Frontend stopped (PID: $FRONTEND_PID)"
    fi
    
    echo -e "${BLUE}All servers stopped. Goodbye!${NC}"
}

# Set trap to cleanup on exit
trap cleanup EXIT

# ═══════════════════════════════════════════════════════════════════
# Check & Start Backend
# ═══════════════════════════════════════════════════════════════════
echo -e "${YELLOW}🔧 Checking Backend...${NC}"

echo -e "${YELLOW}📦 Starting Backend (FastAPI)...${NC}"

cd "$BACKEND_DIR"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
else
    source venv/bin/activate
fi

# Start backend in background using run.py (TCP for development)
BACKEND_TCP=true PYTHONUNBUFFERED=1 python3 run.py > backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
echo -e "${YELLOW}Waiting for backend to start...${NC}"
BACKEND_PORT_CHECK=8002
BACKEND_WAIT=0
BACKEND_MAX_WAIT=35
while ! check_port $BACKEND_PORT_CHECK; do
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "${RED}❌ Backend process exited unexpectedly${NC}"
        echo -e "${YELLOW}Check backend/backend.log for details:${NC}"
        if [ -f "$BACKEND_DIR/backend.log" ]; then
            tail -20 "$BACKEND_DIR/backend.log"
        fi
        exit 1
    fi
    sleep 1
    BACKEND_WAIT=$((BACKEND_WAIT + 1))
    if [ $BACKEND_WAIT -ge $BACKEND_MAX_WAIT ]; then
        echo -e "${RED}❌ Backend failed to start within ${BACKEND_MAX_WAIT} seconds${NC}"
        echo -e "${YELLOW}Check backend/backend.log for details:${NC}"
        if [ -f "$BACKEND_DIR/backend.log" ]; then
            tail -20 "$BACKEND_DIR/backend.log"
        else
            echo -e "${RED}Log file not found${NC}"
        fi
        exit 1
    fi
done

echo -e "${GREEN}✓${NC} Backend running on http://127.0.0.1:8002"
echo -e "${GREEN}✓${NC} API Docs: http://localhost:5174/docs (via Vite proxy)"

# ═══════════════════════════════════════════════════════════════════
# Check & Start Frontend
# ═══════════════════════════════════════════════════════════════════
echo ""
echo -e "${YELLOW}🔧 Checking Frontend...${NC}"

if check_port $FRONTEND_PORT; then
    echo -e "${YELLOW}⚠️  Port $FRONTEND_PORT is already in use${NC}"
    read -p "Use different port? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        FRONTEND_PORT=5175
        echo -e "${BLUE}ℹ${NC} Using port $FRONTEND_PORT instead"
    else
        echo -e "${RED}❌ Cannot start frontend on port $FRONTEND_PORT${NC}"
        exit 1
    fi
fi

echo -e "${YELLOW}⚛️  Starting Frontend (React/Vite)...${NC}"

cd "$FRONTEND_DIR"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies (this may take a minute)...${NC}"
    npm install --quiet
fi

# Start frontend in background
npm run dev -- --port $FRONTEND_PORT > frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Wait for frontend to start
echo -e "${YELLOW}Waiting for frontend to start...${NC}"
FRONTEND_WAIT=0
FRONTEND_MAX_WAIT=20
while ! check_port $FRONTEND_PORT; do
    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo -e "${RED}❌ Frontend process exited unexpectedly${NC}"
        echo -e "${YELLOW}Check frontend/frontend.log for details:${NC}"
        if [ -f "$FRONTEND_DIR/frontend.log" ]; then
            tail -20 "$FRONTEND_DIR/frontend.log"
        fi
        exit 1
    fi
    sleep 1
    FRONTEND_WAIT=$((FRONTEND_WAIT + 1))
    if [ $FRONTEND_WAIT -ge $FRONTEND_MAX_WAIT ]; then
        echo -e "${YELLOW}⚠️  Frontend may still be starting...${NC}"
        break
    fi
done

# ═══════════════════════════════════════════════════════════════════
# Success! Display info
# ═══════════════════════════════════════════════════════════════════
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           🎉 All Systems Ready! 🎉               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BLUE}📍 Access Points:${NC}"
echo -e "  ${GREEN}🌐 Frontend (App):${NC}     http://localhost:$FRONTEND_PORT"
echo -e "  ${GREEN}💬 ChatBot:${NC}             http://localhost:$FRONTEND_PORT/chat"
echo -e "  ${GREEN}📚 Backend (API Docs):${NC}  http://localhost:$FRONTEND_PORT/docs"
echo -e "  ${GREEN}🏥 Health Check:${NC}        http://localhost:$FRONTEND_PORT/health"
echo ""

echo -e "${BLUE}📋 Process IDs:${NC}"
echo -e "  Backend:  $BACKEND_PID"
echo -e "  Frontend: $FRONTEND_PID"
echo ""

echo -e "${YELLOW}Tip: To stop the servers, press Ctrl+C${NC}"
echo ""

echo -e "${BLUE}🚀 What to do next:${NC}"
echo -e "  1. Open http://localhost:$FRONTEND_PORT in your browser"
echo -e "  2. Click the chat icon (💬) in the navbar"
echo -e "  3. Start chatting to get perfume recommendations!"
echo ""

# Keep script running
wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
