# Phase 3 Quick Setup Guide

## Before Testing Phase 3

### 1. Database Setup
Run this SQL in your Supabase SQL Editor:

```sql
-- Create garments table with RLS and indexes
-- (Copy content from PHASE_3_DB_SCHEMA.sql)
```

### 2. Backend Environment Setup
```bash
cd backend
cp .env.example .env
# Edit .env with your real Supabase credentials:
# - SUPABASE_URL
# - SUPABASE_SERVICE_ROLE_KEY  
# - DATABASE_URL
# - etc.
```

### 3. Start Servers
```bash
# From project root
./start-dev.sh
```

### 4. Test the Complete Flow

1. **Visit:** http://localhost:3000 (or 3002 if port 3000 is busy)
2. **Login/Signup:** Create account or login
3. **Upload:** Go to `/upload` page
4. **Step 1:** Upload an image (3-5MB recommended)
5. **Step 2:** Fill garment details:
   - Category: top/bottom/one_piece
   - Subtype: e.g., "t-shirt" (optional)
   - Tags: e.g., "casual,summer" (optional)
6. **Save:** Click "Save Garment"
7. **Verify:** Color bins should appear

### 5. API Testing
```bash
# Get JWT from browser dev tools (Application → Local Storage)
curl -X POST http://localhost:8000/garments \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
        "image_path": "wardrobe/<user_id>/<uuid>.webp",
        "category": "top",
        "subtype": "t-shirt",
        "meta_tags": ["casual", "summer"]
      }'
```

### 6. Database Verification
- Check Supabase Table Editor
- Verify new row in `garments` table
- Check `color_bins` array contains reasonable values

## Expected Behavior

✅ **Success Response:**
```json
{
  "id": "uuid-string",
  "color_bins": ["blue", "neutral"]
}
```

✅ **Color Bins Should Include:**
- Realistic colors like "blue", "red", "green", etc.
- Always includes "neutral" 
- Usually 2-4 bins total

❌ **Common Issues:**
- Backend fails to start → Missing .env file
- 401 errors → Invalid Supabase credentials
- 400 "not owned by user" → User ID mismatch in path
- 422 "could not extract color bins" → Image processing failure

## Phase 3 Complete! 🎉

The garment creation pipeline is fully implemented and ready for testing with real Supabase credentials.
