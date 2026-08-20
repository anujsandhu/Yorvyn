#!/bin/bash
# Quick restart script for backend only

echo "🔄 Restarting Backend..."

# Stop existing backend
echo "Stopping existing backend..."
pkill -f "uvicorn app.main:app" 2>/dev/null
sleep 2

# Start backend
echo "Starting backend..."
cd backend
source venv/bin/activate
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8002 > backend.log 2>&1 &
BACKEND_PID=$!
cd ..

echo "Waiting for backend to start..."
sleep 3

# Check if started
if lsof -Pi :8002 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "✅ Backend running on http://localhost:8002 (PID: $BACKEND_PID)"
    echo "✅ API Docs: http://localhost:8002/docs"
    echo "✅ Health: http://localhost:8002/health"
    echo ""
    echo "📋 Check logs: tail -f backend/backend.log"
else
    echo "❌ Backend failed to start"
    echo "Check backend/backend.log for errors"
    exit 1
fi
