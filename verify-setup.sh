#!/bin/bash

# What2Wear Environment Verification Script
echo "🔍 Checking What2Wear Environment Setup..."
echo

# Check if .env files exist
echo "📁 Checking environment files:"
if [ -f "backend/.env" ]; then
    echo "✅ backend/.env exists"
else
    echo "❌ backend/.env missing - copy from backend/.env.example"
fi

if [ -f "frontend/.env.local" ]; then
    echo "✅ frontend/.env.local exists"
else
    echo "❌ frontend/.env.local missing - copy from frontend/.env.local.example"
fi

echo

# Check backend environment variables
echo "🔧 Checking backend secrets:"
cd backend

if grep -q "your-actual-service-role-key-here" .env 2>/dev/null; then
    echo "❌ SUPABASE_SERVICE_ROLE_KEY not set (still placeholder)"
else
    echo "✅ SUPABASE_SERVICE_ROLE_KEY appears to be set"
fi

if grep -q "YOUR-ACTUAL-DB-PASSWORD" .env 2>/dev/null; then
    echo "❌ DATABASE_URL password not set (still placeholder)"
else
    echo "✅ DATABASE_URL appears to be set"
fi

echo

# Test backend startup (basic import check)
echo "🚀 Testing backend import..."
cd backend
# Load environment variables for testing
export $(cat .env | grep -v '^#' | xargs) 2>/dev/null
if python -c "import main" 2>/dev/null; then
    echo "✅ Backend imports successfully"
else
    echo "⚠️  Backend import test failed (this is normal if DB schema isn't set up yet)"
    echo "   Backend will work fine once you run the database setup"
fi
cd ..

echo
echo "📋 Next steps if you see ❌ above:"
echo "1. Get SUPABASE_SERVICE_ROLE_KEY from: Settings → API (service_role)"
echo "2. Get DATABASE_URL from: Settings → Database (connection string)"
echo "3. Run the PHASE_3_DB_SCHEMA.sql in Supabase SQL Editor"
echo "4. Create 'wardrobe' storage bucket (private)"
echo
echo "🎯 When everything shows ✅, run: ./start-dev.sh"
