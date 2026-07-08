#!/bin/bash
echo "🚀 Starting Sentinel — API Failure Detection Agent"

# Start backend
cd backend
cp .env.example .env 2>/dev/null || true
echo "Starting FastAPI backend on :8000..."
uvicorn main:app --reload --port 8000 &
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
echo "⚠️  Add your ANTHROPIC_API_KEY to backend/.env to enable AI analysis"
echo ""
echo "Press Ctrl+C to stop both servers"

trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait

