#!/bin/bash
# VoiceGuard: start FastAPI (REST + WebSockets) + React UI together
set -e
cd "$(dirname "$0")"
echo "[1/2] Starting FastAPI API on :8000 ..."
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!
echo "      REST  : http://localhost:8000/api/health"
echo "      WS    : ws://localhost:8000/ws/simulator | ws://localhost:8000/ws/dashboard"
echo "[2/2] Starting React UI on :5173 ..."
cd frontend && npm run dev
kill $API_PID 2>/dev/null || true
