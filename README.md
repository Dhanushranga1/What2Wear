# What2Wear

A wardrobe matching app that helps users upload and tag garments, then suggests matches based on color harmony.

## Architecture

- **Frontend:** Next.js 14+ (App Router, TypeScript)
- **Backend:** FastAPI (Python 3.10+)
- **Database/Auth/Storage:** Supabase (Postgres with RLS, Auth, Storage bucket)

## Project Structure

```
/what2wear
  /backend   # FastAPI service
  /frontend  # Next.js frontend
```

## Prerequisites

- Node.js 18+ and npm
- Python 3.10+
- Supabase account and project

## Environment Setup

### Supabase Setup

1. Create a new project at [Supabase](https://app.supabase.com)
2. Enable **email/password** authentication
3. Create a **private** storage bucket named `wardrobe`
4. Note down your project credentials:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `DATABASE_URL`

### Frontend Environment

Create `/frontend/.env.local`:

```bash
NEXT_PUBLIC_SUPABASE_URL=<your-supabase-url>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-anon-key>
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Backend Environment

Create `/backend/.env`:

```bash
SUPABASE_PROJECT_REF=<project-id.supabase.co>
SUPABASE_URL=<your-supabase-url>
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
DATABASE_URL=postgresql://...
JWT_VERIFY_URL=https://<project-id>.supabase.co/auth/v1/user
```

## Running the Application

### Quick Start (Both Servers)

```bash
# From the project root
./start-dev.sh
```

### Manual Start

### Start the Frontend (Port 3000 or next available)

```bash
cd frontend
npm install
npm run dev
```

Visit: http://localhost:3000

### Start the Backend (Port 8000)

```bash
cd backend
python3 -m pip install fastapi uvicorn requests python-dotenv
python3 -m uvicorn main:app --reload --port 8000
```

Test health check: http://localhost:8000/healthz

## Phase 1 Status ✅

- [x] Authentication system implemented
- [x] Login/signup pages with Supabase Auth
- [x] Protected app shell with route guards
- [x] Session management and persistence
- [x] Header with user email and logout
- [x] Placeholder pages (wardrobe, upload, item detail)
- [ ] Supabase project setup (manual step required)
- [ ] Environment variables configured with real Supabase credentials

## Phase 2 Status ✅

- [x] Image compression utility implemented (WebP, max 1024px, quality 0.6)
- [x] Supabase Storage upload functionality
- [x] File size validation (5MB limit before compression, 500KB after)
- [x] Signed URLs with 7-day expiry for private access
- [x] Upload page UI with file input, preview, and status messages
- [x] Error handling for oversized files and invalid types
- [x] Path structure: `wardrobe/{user_id}/{uuid}.webp`

## Current Setup

### Frontend Status
- ✅ **Running**: http://localhost:3002 (Next.js with TypeScript)
- ✅ **Authentication**: Login/signup forms implemented
- ✅ **Protected Routes**: Wardrobe, upload, item pages  
- ✅ **Session Management**: Auth state persistence
- ⚠️ **Needs real Supabase credentials for testing**

### Backend Status  
- ✅ **Running**: http://localhost:8000 (FastAPI with CORS)
- ✅ **Health Check**: http://localhost:8000/healthz
- ✅ **API Documentation**: http://localhost:8000/docs
- ✅ **No changes required for Phase 1**

## Manual Steps Required

1. **Create Supabase Project**:
   - Go to [Supabase](https://app.supabase.com) and create a new project
   - Enable email/password authentication
   - Create a private storage bucket named `wardrobe`
   - Note down your credentials:
     - Project URL
     - Anon Key  
     - Service Role Key
     - Database URL

2. **Configure Environment Variables**:
   - Update `frontend/.env.local` with your Supabase credentials
   - Update `backend/.env` with your Supabase credentials (copy from .env.example)

3. **Test Authentication Flow**:
   - Visit http://localhost:3002 (redirects to login)
   - Try http://localhost:3002/signup to create account
   - Try http://localhost:3002/login to sign in
   - Test protected routes: /wardrobe, /upload, /item/123

4. **Test Route Protection**:
   - Visit /wardrobe without logging in (should redirect to /login)
   - Log in and verify header shows email and logout button
   - Test logout functionality

## Testing Commands

```bash
# Test authentication pages
open http://localhost:3002/login
open http://localhost:3002/signup

# Test protected routes (should redirect to login if not authenticated)
open http://localhost:3002/wardrobe
open http://localhost:3002/upload  
open http://localhost:3002/item/123

# Test backend health
curl http://localhost:8000/healthz
open http://localhost:8000/docs
```

## Phase 2 Testing (Image Upload)

**Instructions to test image upload:**

1. Run both servers (`./start-dev.sh` or manually start frontend and backend)
2. Log in to the application at http://localhost:3002
3. Navigate to `/upload`
4. Select a photo (try 3–5 MB to test compression)
5. Confirm compressed preview shows and file appears in Supabase Storage

**What to verify:**
- Upload form exists on `/upload`
- Selecting image → compresses → uploads → returns signed URL
- Uploaded file appears in Supabase Storage bucket `wardrobe/{user_id}/...`
- Preview displays immediately in UI (via signed URL)
- File size after compression typically <200 KB
- Errors (too big, wrong type, upload fail) are caught + displayed

**Note:** Files are stored in a private bucket and can only be accessed via signed URL.

## Phase 3 Testing (Garment Creation + Palette Extraction)

**Prerequisites:**
- Phase 2 complete (image upload working)
- Database schema created (run `PHASE_3_DB_SCHEMA.sql` in Supabase)
- Backend dependencies installed (`pip install -r requirements.txt`)
- Environment variables configured with real Supabase credentials

**Instructions to test garment creation:**

1. **Setup Database Schema:**
   ```sql
   -- Run this in Supabase SQL Editor
   -- (Copy from PHASE_3_DB_SCHEMA.sql)
   ```

2. **Install Backend Dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Test Full Flow:**
   - Run both servers (`./start-dev.sh`)
   - Log in to the application at http://localhost:3002
   - Navigate to `/upload`
   - Upload an image (3-5MB recommended for testing compression)
   - Fill in garment details:
     - Category: top/bottom/one_piece
     - Subtype: e.g., "t-shirt", "jeans" (optional)
     - Tags: e.g., "casual,summer" (optional, comma-separated)
   - Click "Save Garment"
   - Verify color bins are extracted and displayed

4. **Manual API Testing:**
   ```bash
   # Get your JWT token from browser dev tools (Application → Local Storage → sb-*-auth-token)
   curl -X POST http://localhost:8000/garments \
     -H "Authorization: Bearer <your_supabase_jwt>" \
     -H "Content-Type: application/json" \
     -d '{
           "image_path": "wardrobe/<user_id>/<uuid>.webp",
           "category":"top",
           "subtype":"t-shirt",
           "meta_tags":["casual","summer"]
         }'
   ```

**What to verify:**
- `POST /garments` endpoint accepts valid requests
- JWT authentication is enforced (401 for invalid/missing tokens)
- Image ownership is verified (400 for wrong user_id in path)
- Color palette extraction works (returns reasonable color_bins)
- Garment is saved to database with correct user_id
- Response includes `{id, color_bins}`
- Invalid requests are rejected with appropriate error codes

**Negative Tests:**
- Try tampering with user_id in image_path → should get 400 "not owned by user"
- Try invalid category → should get 422 validation error
- Try missing authentication → should get 401
- Try malformed image_path → should get 400

**Database Verification:**
- Check Supabase Table Editor for new rows in `garments` table
- Verify RLS is working (only user's own garments visible)
- Check color_bins array contains reasonable values

## Phase 4 Status ✅

- [x] Server-side wardrobe data fetching with RLS security
- [x] Batch signed URL generation for performance
- [x] Filter system (category, color, tags) with URL state
- [x] Pagination (24 items per page) with URL state
- [x] Responsive grid layout with color bin visualization
- [x] Item detail pages with comprehensive garment display
- [x] Loading states and error handling throughout
- [x] Empty state handling for new users and filtered results

## Phase 4 Testing (Wardrobe List + Filters + Pagination)

**Prerequisites:**
- Phase 3 complete (garment creation working)
- At least 5-10 garments uploaded for testing filters/pagination
- Frontend dependencies updated (`@supabase/ssr` package installed)

**Instructions to test wardrobe browsing:**

1. **Setup Test Data:**
   - Upload 10+ garments with different categories (top/bottom/one_piece)
   - Ensure variety in colors and tags for filter testing
   - Mix of garments from different time periods for pagination testing

2. **Test Core Functionality:**
   - Navigate to `/wardrobe` - should see grid of garments
   - Verify images load via signed URLs
   - Check color dots display correctly for each item
   - Test responsive layout (mobile/tablet/desktop)

3. **Test Filtering System:**
   ```bash
   # Category filter
   open http://localhost:3002/wardrobe?category=top
   open http://localhost:3002/wardrobe?category=bottom
   
   # Color filter
   open http://localhost:3002/wardrobe?color=blue
   open http://localhost:3002/wardrobe?color=neutral
   
   # Tag filter  
   open http://localhost:3002/wardrobe?tag=casual
   open http://localhost:3002/wardrobe?tag=summer
   
   # Combined filters
   open http://localhost:3002/wardrobe?category=top&color=blue&tag=casual
   ```

4. **Test Pagination:**
   - Upload 25+ items to test pagination (page size = 24)
   - Navigate through pages: `/wardrobe?page=1`, `/wardrobe?page=2`
   - Test pagination with filters: `/wardrobe?category=top&page=2`
   - Verify URL state persists on browser back/forward

5. **Test Item Detail Pages:**
   - Click any garment card to navigate to `/item/{id}`
   - Verify full-size image displays with signed URL
   - Check all metadata is shown (category, subtype, colors, tags, date)
   - Test back navigation to wardrobe
   - Try direct URL access: `/item/{garment-id}`

6. **Test Error States:**
   - Visit `/item/nonexistent-id` → should show 404 page
   - Test with network disconnected → should show error message
   - Clear all garments and visit `/wardrobe` → should show empty state

**What to verify:**

**Core Features:**
- Grid displays all user's garments (newest first)
- Images load correctly via batch-signed URLs  
- Color bins display as colored dots with correct colors
- Garment cards show category, subtype, tags, and date
- Responsive layout works across screen sizes

**Filtering:**
- Category dropdown filters by top/bottom/one_piece
- Color dropdown filters by color bins (red, blue, neutral, etc.)
- Tag dropdown shows available tags from user's garments  
- Filters combine correctly (AND logic)
- URL updates when filters change
- Filter state persists on page refresh
- "Clear filters" link works when no results

**Pagination:**
- Shows 24 items per page maximum
- Pagination controls appear when >24 items exist
- Page numbers work correctly
- URL updates with page parameter
- Page state persists with filters applied
- Results summary shows correct counts

**Item Detail Pages:**
- Full garment information displays correctly
- Large image shows with proper aspect ratio
- Color palette displays with names and swatches
- Meta tags display as styled badges
- Created date formatted properly
- Back navigation preserves wardrobe state

**Security & Performance:**
- Only user's own garments visible (RLS enforcement)
- Signed URLs expire appropriately (24 hours)
- Server-side rendering provides good performance
- Batch URL signing minimizes API calls
- Navigation is fast with Next.js optimizations

**Error Handling:**
- Loading states show during data fetching
- 404 pages for missing items
- Network error messages are user-friendly
- Empty states guide users to upload first garment
- No JavaScript errors in browser console

**Manual RLS Testing:**
```sql
-- In Supabase SQL Editor, verify RLS is working:
-- 1. Log in as User A, upload garments
-- 2. Log in as User B, upload different garments  
-- 3. Each user should only see their own garments in /wardrobe
-- 4. Direct item URLs should return 404 for other users' garments
```

**Performance Testing:**
- Upload 50+ garments to test pagination performance
- Verify batch signed URL generation completes quickly
- Check server response times in Network tab
- Test on slower network connections (throttling)

## Phase 5 Status ✅

- [x] Rule-based matching algorithm with complementary/neutral/analogous color scoring
- [x] `GET /suggest/{garment_id}` endpoint with JWT authentication
- [x] Top ↔ bottom pairing only (one_piece returns empty suggestions)
- [x] Candidate pre-filtering with color overlap for performance
- [x] Server-side 24h signed URL generation for suggestion images
- [x] Explainable scoring with reasons (complementary colors, shared tags, etc.)
- [x] Suggestions UI integrated into item detail pages
- [x] Score visualization and match strength indicators
- [x] Comprehensive error handling and empty states

## Phase 5 Testing (Matching Suggestions)

**Prerequisites:**
- Phase 4 complete (wardrobe browsing working)
- At least **5-10 garments** uploaded with variety in categories, colors, and tags
- Backend and frontend servers running

**Instructions to test outfit suggestions:**

1. **Setup Test Data:**
   - Upload at least **3 tops** and **3 bottoms** with different colors
   - Include variety: complementary colors (blue/orange, red/green, yellow/purple)
   - Add some items with "neutral" colors (gray, black, white, beige)
   - Use different tags: "casual", "formal", "summer", "winter", etc.
   - Upload at least one "one_piece" item for testing

2. **Test Core Functionality:**
   - Navigate to `/item/{id}` for a **top** item
   - Scroll down to see "Suggested Matches" section
   - Verify **bottom** suggestions appear with images, scores, and reasons
   - Check that suggestions are sorted by score (highest first)

3. **Test Category Logic:**
   ```bash
   # Top item should suggest bottoms
   open http://localhost:3002/item/{top-item-id}
   
   # Bottom item should suggest tops  
   open http://localhost:3002/item/{bottom-item-id}
   
   # One-piece should show no suggestions
   open http://localhost:3002/item/{one-piece-item-id}
   ```

4. **Test API Directly:**
   ```bash
   # Get JWT token from browser dev tools (Application → Local Storage → sb-*-auth-token)
   curl -H "Authorization: Bearer <jwt-token>" \
        http://localhost:8000/suggest/{garment-id}?limit=5
   ```

5. **Test Scoring Logic:**
   - **Complementary colors**: Items with blue + orange should score highest
   - **Neutral pairing**: Items with neutral colors should get good scores
   - **Analogous colors**: Adjacent colors (blue + purple) should score moderately
   - **Shared tags**: Items with matching tags should get bonus points
   - **Score display**: Verify scores show as percentages (e.g., "86%")

6. **Test User Isolation:**
   - Log in as different users
   - Try accessing suggestions for other users' items
   - Should get 404 "not found" responses (RLS protection)

**What to verify:**

**Core Features:**
- Top items suggest bottom items only
- Bottom items suggest top items only  
- One-piece items show "No matches available"
- Suggestions display images via 24h signed URLs
- Scores range from 0-100% and sort correctly
- Reasons explain why items match (colors, tags)

**Scoring Algorithm:**
- Complementary color pairs get highest scores (+60 points)
- Neutral colors pair well with everything (+40 points)
- Analogous colors get moderate scores (+20 points)
- Shared tags provide bonus points (+10 per tag, max +20)
- Final scores are clamped to 100% maximum

**Reasons Display:**
- "complementary colors (blue ↔ orange)"
- "neutral pairs with any color"
- "analogous colors (green ↔ teal)"  
- "shared: casual, summer" (shows up to 2 shared tags)

**Performance:**
- Suggestions load quickly (< 300ms typical)
- Pre-filtering with color overlap keeps queries fast
- Only processes up to 200 candidates maximum
- Batch URL signing minimizes Storage API calls

**Security:**
- JWT authentication required for all suggestions
- Users can only get suggestions for their own items
- 404 error for non-existent or unowned items
- No raw storage paths exposed (signed URLs only)

**Error Handling:**
- Loading states during fetch
- "No matches available" for empty results  
- "Couldn't load suggestions" for API errors
- Graceful fallback if suggestion fetch fails

**Manual Algorithm Testing:**
Create specific test items to verify scoring:

1. **Blue top + Orange bottom**: Should score ~86% (complementary + tags)
2. **Red shirt + Green pants**: Should score ~60% (complementary colors)
3. **Neutral top + Any color bottom**: Should score ~40%+ (neutral bonus)
4. **Blue top + Purple bottom**: Should score ~20%+ (analogous colors)
5. **Casual top + Casual bottom**: Should get tag bonus (+10 points)

**API Response Validation:**
```json
{
  "source_id": "uuid-here",
  "suggestions": [
    {
      "garment_id": "uuid-here", 
      "image_url": "https://...supabase-signed-url...",
      "score": 0.86,
      "reasons": ["complementary colors (blue ↔ orange)", "shared: casual"]
    }
  ]
}
```

**Database Performance Check:**
- Verify GIN index on `color_bins` is being used
- Check query plan: `EXPLAIN ANALYZE SELECT ... WHERE color_bins && $1`
- Should see "Bitmap Index Scan" on `gin_garments_color_bins_idx`
- Query execution time should be < 50ms with hundreds of items
