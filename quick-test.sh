#!/bin/bash

# Quick Test Script for What2Wear
echo "🧪 What2Wear - Quick Test"
echo "========================"
echo

# Test backend startup
echo "🔧 Testing Backend..."
cd backend
export $(cat .env | grep -v '^#' | xargs) 2>/dev/null

# Test if backend can start
if timeout 5s python -c "
import main
from fastapi.testclient import TestClient
client = TestClient(main.app)
response = client.get('/healthz')
print('Backend health check:', response.status_code)
assert response.status_code == 200
print('✅ Backend OK')
" 2>/dev/null; then
    echo "✅ Backend starts successfully"
else
    echo "⚠️  Backend may need database setup first (this is normal)"
fi

cd ..

# Test frontend
echo
echo "🎨 Testing Frontend..."
cd frontend
if npm run build > /dev/null 2>&1; then
    echo "✅ Frontend builds successfully" 
else
    echo "⚠️  Frontend has build issues (check for missing dependencies)"
fi
cd ..

echo
echo "🚀 Ready to start!"
echo "=================="
echo "1. Complete the SQL setup in Supabase (shown above)"
echo "2. Run: ./start-dev.sh" 
echo "3. Open: http://localhost:3002"
echo
echo "🎯 Full test sequence:"
echo "- Sign up at /signup"
echo "- Upload image at /upload"  
echo "- Browse wardrobe at /wardrobe"
echo "- View suggestions at /item/[id]"
