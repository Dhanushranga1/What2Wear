#!/bin/bash

# What2Wear Complete Setup Script
# This script helps you complete the final setup steps

echo "🚀 What2Wear - Final Setup"
echo "=========================="
echo

# Check if environment is ready
echo "📋 Checking prerequisites..."
if [ ! -f "backend/.env" ]; then
    echo "❌ backend/.env missing - run the secrets setup first"
    exit 1
fi

if [ ! -f "frontend/.env.local" ]; then
    echo "❌ frontend/.env.local missing - run the secrets setup first"
    exit 1
fi

echo "✅ Environment files found"
echo

# Show SQL setup instructions
echo "🗄️  Database & Storage Setup Required"
echo "======================================"
echo
echo "You need to run these SQL scripts in your Supabase SQL Editor:"
echo "👉 https://app.supabase.com/project/jybbgwubfljrjpdlftcu/sql"
echo
echo "1️⃣  STORAGE SETUP (run setup_storage.sql):"
echo "   - Creates private 'wardrobe' bucket"
echo "   - Sets up user-isolated storage policies"
echo
echo "2️⃣  DATABASE SETUP (run setup_database.sql):"
echo "   - Creates 'garments' table with RLS"
echo "   - Sets up indexes for performance"
echo
echo "📁 SQL files created:"
echo "   ✅ setup_storage.sql - Copy/paste into Supabase SQL Editor"
echo "   ✅ setup_database.sql - Copy/paste into Supabase SQL Editor"
echo

# Show the SQL content for easy copy-paste
echo "🔗 Quick Copy-Paste (Storage Setup):"
echo "======================================"
echo
cat setup_storage.sql
echo
echo "======================================"
echo
echo "🔗 Quick Copy-Paste (Database Setup):"
echo "======================================"
echo  
cat setup_database.sql
echo
echo "======================================"
echo

# Installation check
echo "📦 Checking dependencies..."
cd backend
if python -c "import fastapi, uvicorn, requests, psycopg2, PIL, numpy, sklearn" 2>/dev/null; then
    echo "✅ Backend dependencies installed"
else
    echo "⚠️  Installing backend dependencies..."
    pip install -r requirements.txt
fi
cd ..

cd frontend  
if [ -d "node_modules" ]; then
    echo "✅ Frontend dependencies installed"
else
    echo "⚠️  Installing frontend dependencies..."
    npm install
fi
cd ..

echo
echo "🎯 Next Steps:"
echo "=============="
echo "1. Open Supabase SQL Editor: https://app.supabase.com/project/jybbgwubfljrjpdlftcu/sql"
echo "2. Copy/paste the storage setup SQL above"
echo "3. Copy/paste the database setup SQL above"
echo "4. Run: ./start-dev.sh"
echo "5. Test at: http://localhost:3002"
echo
echo "🧪 Testing Checklist:"
echo "- Sign up/login works"
echo "- Upload image works (compresses to WebP)"
echo "- Save garment works (shows color bins)"
echo "- Wardrobe shows your items"
echo "- Item detail shows suggestions"
echo
echo "Need help? Check the logs or ask for assistance! 🤝"
