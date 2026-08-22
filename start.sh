#!/bin/bash
echo "🚀 Starting Sentinel — API Failure Detection Agent"

# Postgres and Redis must already be running locally — this script doesn't
# start them, since how you run them (Homebrew services, Docker, a system
# daemon) is a local setup choice, not something to assume.
if ! pg_isready -q 2>/dev/null; then
  echo "⚠️  Postgres doesn't look reachable — start it and run 'createdb sentinel' first."
fi
if ! redis-cli ping >/dev/null 2>&1; then
  echo "⚠️  Redis doesn't look reachable — start it before continuing."
fi

# Start backend
cd backend
cp .env.example .env 2>/dev/null || true
echo "Starting FastAPI backend on :8000..."
# --forwarded-allow-ips="" disables uvicorn's own independent trust of
# X-Forwarded-For from loopback connections (its default). Without this,
# uvicorn rewrites request.client.host from that header for any request
# arriving via 127.0.0.1 regardless of the app-level TRUST_PROXY_HEADERS
# setting in ratelimit.py — two separate, independent "trust this header"
# switches is exactly how a rate-limit bypass slips through unnoticed.
# TRUST_PROXY_HEADERS is the one and only toggle; set it (not this flag)
# when deploying behind a real reverse proxy.
uvicorn main:app --reload --port 8000 --forwarded-allow-ips="" &
BACKEND_PID=$!

# Start frontend
cd ../frontend
echo "Starting React frontend on :5173..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Sentinel is running!"
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "⚠️  Add your GROQ_API_KEY to backend/.env to enable AI analysis"
echo ""
echo "Press Ctrl+C to stop both servers"

trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait

