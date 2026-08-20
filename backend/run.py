#!/usr/bin/env python3
"""Backend server runner — supports TCP port for dev and Unix socket for production."""
import sys
import os
from pathlib import Path

# Add project directory to path to allow absolute imports
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))

from backend.app.main import app
import uvicorn

SOCKET_PATH = os.path.join(project_dir, "backend.sock")

if __name__ == "__main__":
    # Check if we should use TCP (development) or Unix socket (production)
    use_tcp = os.getenv("BACKEND_TCP", "true").lower() == "true"
    
    if use_tcp:
        # Development mode: listen on TCP port
        print("🚀 Starting Yorvyn Backend (Development Mode)...")
        print("📍 Listening on http://127.0.0.1:8002")
        print("📚 API docs: http://127.0.0.1:8002/docs")
        print("💬 Vite proxy: http://localhost:5174/docs")
        uvicorn.run(app, host="127.0.0.1", port=8002)
    else:
        # Production mode: use Unix socket
        # Clean up stale socket file if it exists
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)

        print("🚀 Starting Yorvyn Backend (Production Mode)...")
        print(f"📍 Listening on Unix socket: {SOCKET_PATH}")
        print("📚 API docs available via Vite proxy on http://localhost:5174/docs")
        uvicorn.run(app, uds=SOCKET_PATH)
