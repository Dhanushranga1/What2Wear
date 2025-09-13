#!/bin/bash

# Navigate to backend directory
cd /home/dhanush/Documents/Nexora/What2Wear/what2wear/backend

# Set environment variables from .env file
export SUPABASE_PROJECT_REF=jybbgwubfljrjpdlftcu
export SUPABASE_URL=https://jybbgwubfljrjpdlftcu.supabase.co
export SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp5YmJnd3ViZmxqcmpwZGxmdGN1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY1ODM0NjYsImV4cCI6MjA3MjE1OTQ2Nn0.yMZg4h4zBYOLwsqahIaLLa39h9BxCaW8yd8WRHtsTjQ
export SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp5YmJnd3ViZmxqcmpwZGxmdGN1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NjU4MzQ2NiwiZXhwIjoyMDcyMTU5NDY2fQ.601Y367AAyshsafwaRdz22x6bR-8S6jDFR016CV19Ps
export DATABASE_URL=postgresql://postgres:3MDzhsFbFXD5GHFU@db.jybbgwubfljrjpdlftcu.supabase.co:5432/postgres
export JWT_VERIFY_URL=https://jybbgwubfljrjpdlftcu.supabase.co/auth/v1/user
export STORAGE_BUCKET=wardrobe

# Start the server
echo "Starting FastAPI backend..."
/home/dhanush/Documents/Nexora/What2Wear/.venv/bin/python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
