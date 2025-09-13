#!/bin/bash

# What2Wear Development Server Startup Script

echo "🚀 Starting What2Wear Development Environment..."

# Function to kill background processes on exit
cleanup() {
    echo "🛑 Shutting down servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit
}
trap cleanup EXIT

# Start backend server
echo "📦 Starting FastAPI backend on port 8000..."
cd backend
python3 -m uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start frontend server  
echo "🎨 Starting Next.js frontend..."
cd ../frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Development servers started!"
echo "🎨 Frontend: http://localhost:3000 (or available port)"
echo "📦 Backend:  http://localhost:8000"
echo "🔍 API Docs: http://localhost:8000/docs"
echo "❤️  Health:  http://localhost:8000/healthz"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for user to press Ctrl+C
wait
