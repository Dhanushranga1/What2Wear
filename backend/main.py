from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
import os
import psycopg2
import re
import json
import time
from dotenv import load_dotenv
from pydantic import BaseModel, field_validator
from typing import Optional, List
from supabase import create_client, Client

# Import our modules
from deps import get_user_id, get_user_supabase_client, create_signed_url
from palette import extract_color_bins
from matching import score_and_reasons, get_opposite_category

# Import observability (optional)
try:
    from app.api.observability import router as observability_router
    observability_available = True
except ImportError:
    observability_router = None
    observability_available = False

# Import Phase 4 components (optional)
try:
    from app.config import Config
    config = Config()
except ImportError:
    config = None

try:
    from app.api.v1 import router as v1_router
    v1_available = True
except ImportError:
    v1_router = None
    v1_available = False

# Load environment variables
load_dotenv()

# Environment variables
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
BUCKET = os.environ.get("STORAGE_BUCKET", "wardrobe")
DATABASE_URL = os.environ["DATABASE_URL"]

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SERVICE_KEY)

# Database connection (keep for backwards compatibility with some endpoints)
try:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
except Exception as e:
    print(f"Failed to connect to database: {e}")
    conn = None

# Regular expression for validating image paths
IMAGE_PATH_RE = re.compile(rf"^{BUCKET}/[0-9a-fA-F-]+/[^/]+\.webp$")

app = FastAPI(
    title="StyleSync What2Wear Backend",
    description="Unified API for outfit color matching and suggestions",
    version="1.0.0"
)

# Add CORS middleware with basic configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining", 
        "X-RateLimit-Window"
    ]
)

if config and config.ALLOWED_HOSTS != "*":
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    allowed_hosts = os.environ.get("STYLESYNC_ALLOWED_HOSTS", "*").split(",")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# Include routers (conditionally)
if observability_available and observability_router:
    app.include_router(observability_router, prefix="/api")
    
if v1_available and v1_router:
    app.include_router(v1_router)  # Phase 4 unified API

# Phase 5 routers
try:
    from app.api.profile import router as profile_router
    from app.api.events import router as events_router
    from app.api.phase5_analytics import router as analytics_router
    app.include_router(profile_router)
    app.include_router(events_router)
    app.include_router(analytics_router)
    print("Phase 5 personalization endpoints loaded")
except ImportError as e:
    print(f"Phase 5 endpoints not available: {e}")


# Request/Response models
class GarmentRequest(BaseModel):
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    category: str
    subtype: Optional[str] = None
    meta_tags: List[str] = []

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        if v not in ("top", "bottom", "one_piece"):
            raise ValueError("category must be one of: top, bottom, one_piece")
        return v

    @field_validator("meta_tags")
    @classmethod
    def validate_meta_tags(cls, v):
        if len(v) > 10:
            raise ValueError("maximum 10 meta_tags allowed")
        for tag in v:
            if len(tag) > 24:
                raise ValueError("each meta_tag must be ≤24 characters")
        return v

    @field_validator("subtype")
    @classmethod
    def validate_subtype(cls, v):
        if v is not None and len(v) > 40:
            raise ValueError("subtype must be ≤40 characters")
        return v


class GarmentResponse(BaseModel):
    id: str
    color_bins: List[str]


class SuggestionItem(BaseModel):
    garment_id: str
    image_url: str
    score: float
    reasons: List[str]


class SuggestionResponse(BaseModel):
    source_id: str
    suggestions: List[SuggestionItem]

@app.get("/healthz")
def health_check():
    """Health check endpoint for Phase 5"""
    return {
        "status": "ok",
        "service": "what2wear-backend",
        "version": "0.1.0",
        "phase": "Phase 5 - Matching Suggestions (Rule-Based)"
    }


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "What2Wear Backend API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.post("/garments", response_model=GarmentResponse)
def create_garment(
    body: GarmentRequest, 
    user_id: str = Depends(get_user_id)
):
    """
    Create a new garment with palette extraction
    """
    # 1) Validate inputs
    if not body.image_path and not body.image_url:
        raise HTTPException(status_code=400, detail="Provide either image_path or image_url")

    signed_url = None
    image_path = None

    if body.image_path:
        # Validate image path format
        if not IMAGE_PATH_RE.match(body.image_path):
            raise HTTPException(status_code=400, detail="Invalid image_path format")
        
        # Ownership check: extract user_id from path
        path_parts = body.image_path.split("/")
        if len(path_parts) < 3:
            raise HTTPException(status_code=400, detail="Invalid image_path structure")
        
        path_user_id = path_parts[1]  # wardrobe/{user_id}/{filename}
        if path_user_id != user_id:
            raise HTTPException(status_code=400, detail="Image path not owned by user")
        
        image_path = body.image_path
        print(f"DEBUG: Creating signed URL for image_path: {image_path}")
        signed_url = create_signed_url(image_path, seconds=120)
        print(f"DEBUG: Successfully created signed URL")

    elif body.image_url:
        # Best-effort ownership check for signed URLs
        if f"/{user_id}/" not in body.image_url:
            raise HTTPException(status_code=400, detail="Image URL not owned by user")
        signed_url = body.image_url
        # Try to derive a normalized path if possible
        image_path = None

    # 2) Palette extraction
    try:
        color_bins = extract_color_bins(signed_url)
    except Exception as e:
        print(f"Palette extraction failed: {e}")
        raise HTTPException(status_code=422, detail="Could not extract color bins")

    # 3) Sanitize inputs
    meta_tags = [tag.strip()[:24] for tag in (body.meta_tags or [])][:10]
    subtype = body.subtype[:40] if body.subtype else None

    # 4) Insert using service role client (bypasses RLS issues)
    try:
        # Debug: Print user info
        print(f"DEBUG: Attempting to insert garment for user_id: {user_id}")
        
        # Use service role supabase client (bypasses RLS)
        result = supabase.table("garments").insert({
            "user_id": user_id,
            "category": body.category,
            "subtype": subtype,
            "image_path": image_path,
            "image_url": signed_url,
            "color_bins": color_bins,
            "meta_tags": meta_tags
        }).execute()
        
        print(f"DEBUG: Insert result: {result}")
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to save garment")
        
        garment_id = result.data[0]["id"]
        return GarmentResponse(id=str(garment_id), color_bins=color_bins)

    except Exception as e:
        print(f"Database insertion failed: {e}")
        print(f"Exception type: {type(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save garment: {str(e)}")


@app.get("/suggest/{garment_id}", response_model=SuggestionResponse)
def get_suggestions(garment_id: str, limit: int = 10, user_id: str = Depends(get_user_id)):
    """
    Get outfit suggestions for a garment using rule-based matching with Phase 5 personalization
    """
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection unavailable")
    
    # Validate and clamp limit
    if limit <= 0 or limit > 50:
        limit = 10
    
    # Track start time for performance monitoring
    start_time = time.time()
    
    try:
        with conn.cursor() as cur:
            # 1. Load source garment (must be owned by user)
            cur.execute("""
                SELECT id, category, image_path, color_bins, meta_tags
                FROM garments 
                WHERE id = %s AND user_id = %s
            """, (garment_id, user_id))
            
            source_row = cur.fetchone()
            if not source_row:
                raise HTTPException(status_code=404, detail="Garment not found or not owned")
            
            source_id, source_category, source_image_path, source_bins, source_tags = source_row
            
            # 2. Handle one_piece category (no suggestions)
            target_category = get_opposite_category(source_category)
            if target_category is None:
                return SuggestionResponse(source_id=garment_id, suggestions=[])
            
            # 3. Build candidate pool with color overlap pre-filter
            cur.execute("""
                SELECT id, image_path, color_bins, meta_tags
                FROM garments
                WHERE user_id = %s 
                  AND category = %s 
                  AND color_bins && %s::text[]
                ORDER BY created_at DESC
                LIMIT 200
            """, (user_id, target_category, source_bins))
            
            candidates = cur.fetchall()
    
    except Exception as e:
        print(f"Database query failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch suggestions")
    
    # 4. Score all candidates using Phase 3 rule-based matching
    scored_candidates = []
    for cand_id, cand_image_path, cand_bins, cand_tags in candidates:
        score, reasons = score_and_reasons(
            source_bins or [], 
            source_tags or [], 
            cand_bins or [], 
            cand_tags or []
        )
        
        # Only include candidates with positive scores
        if score > 0:
            scored_candidates.append({
                "suggestion_id": f"sugg_{garment_id}_{cand_id}",
                "garment_id": str(cand_id),
                "image_path": cand_image_path,
                "colors": cand_bins or [],
                "score": round(score, 2),
                "reasons": reasons,
                "metadata": {
                    "source_category": source_category,
                    "target_category": target_category,
                    "tags": cand_tags or []
                }
            })
    
    # 5. Apply Phase 5 personalized re-ranking
    personalized_suggestions = scored_candidates
    personalization_applied = False
    experiment_variant = None
    
    try:
        # Load user features and check opt-out status
        from app.services.personalization import get_feature_cache
        from app.services.personalization.ranking import get_personalized_ranker
        
        feature_cache = get_feature_cache()
        user_features = feature_cache.get_features_sync(user_id)
        
        # Check if user has opted out of personalization
        cur.execute("""
            SELECT opt_out_personalization, opt_out_experiments 
            FROM users WHERE user_id = %s
        """, (user_id,))
        user_prefs = cur.fetchone()
        
        opt_out_personalization = user_prefs[0] if user_prefs else False
        opt_out_experiments = user_prefs[1] if user_prefs else False
        
        if not opt_out_personalization and len(scored_candidates) > 1:
            # Apply personalized re-ranking
            ranker = get_personalized_ranker()
            context = {
                "source_garment_id": garment_id,
                "source_category": source_category,
                "target_category": target_category,
                "user_age_days": 30  # TODO: Calculate actual user age
            }
            
            if opt_out_experiments:
                context["force_control"] = True
            
            reranking_result = ranker.rerank_with_personalization(
                suggestions=scored_candidates,
                user_id=user_id,
                user_features=user_features,
                context=context
            )
            
            personalized_suggestions = [
                {
                    "suggestion_id": item.suggestion_id,
                    "garment_id": item.suggestion_id.split("_")[-1],
                    "image_path": item.metadata.get("image_path", ""),
                    "colors": item.colors,
                    "score": round(item.base_score, 2),
                    "reasons": item.metadata.get("reasons", [])
                }
                for item in reranking_result.suggestions
            ]
            
            personalization_applied = reranking_result.personalization_applied
            experiment_variant = reranking_result.experiment_variant
            
            # Log advice session for analytics
            session_id = f"session_{user_id}_{int(time.time())}"
            cur.execute("""
                INSERT INTO advice_sessions (
                    session_id, user_id, source_garment_id, target_category,
                    suggestion_count, personalized, experiment_variant,
                    reranking_time_ms, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                session_id,
                user_id,
                garment_id,
                target_category,
                len(personalized_suggestions),
                personalization_applied,
                experiment_variant,
                reranking_result.reranking_time_ms
            ))
            
            # Log individual suggestions for tracking
            for i, suggestion in enumerate(personalized_suggestions[:limit]):
                cur.execute("""
                    INSERT INTO suggestions (
                        session_id, user_id, suggestion_id, garment_id,
                        rank_position, base_score, personalized_score,
                        colors, metadata, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    session_id,
                    user_id,
                    suggestion["suggestion_id"],
                    suggestion["garment_id"],
                    i + 1,
                    suggestion["score"],
                    suggestion["score"],  # Same for now since we update score in-place
                    suggestion["colors"],
                    json.dumps({"reasons": suggestion["reasons"]}),
                ))
            
            conn.commit()
            
    except Exception as e:
        print(f"Personalization failed, falling back to basic ranking: {e}")
        # Continue with basic ranking if personalization fails
        personalized_suggestions = scored_candidates
    
    # 6. Take top N suggestions and generate signed URLs
    top_candidates = personalized_suggestions[:limit]
    
    suggestions = []
    for candidate in top_candidates:
        try:
            # Get image path from candidate data
            image_path = candidate.get("image_path")
            if not image_path:
                # Find image path from original candidates
                for orig_cand in candidates:
                    if str(orig_cand[0]) == candidate["garment_id"]:
                        image_path = orig_cand[1]
                        break
            
            if image_path:
                # Create 24h signed URL for the image
                signed_url = create_signed_url(image_path, seconds=86400)
                
                suggestions.append(SuggestionItem(
                    garment_id=candidate["garment_id"],
                    image_url=signed_url,
                    score=candidate["score"],
                    reasons=candidate["reasons"]
                ))
        except Exception as e:
            print(f"Failed to sign URL for {candidate['garment_id']}: {e}")
            # Skip this candidate if URL signing fails
            continue
    
    # Add personalization metadata to response headers (if available in FastAPI)
    total_time_ms = (time.time() - start_time) * 1000
    print(f"Suggestion request completed in {total_time_ms:.2f}ms, personalization: {personalization_applied}")
    
    return SuggestionResponse(source_id=garment_id, suggestions=suggestions)


# =============================================================================
# StyleSync Segmentation Endpoints (Phase 1)
# =============================================================================

# StyleSync imports (conditional to avoid breaking existing functionality)
try:
    from app.schemas import SegmentResponse, HealthResponse
    from app.services.segmentation.pipeline import run_segmentation
    from app.utils.metrics import get_metrics
    
    STYLESYNC_AVAILABLE = True
except ImportError as e:
    print(f"StyleSync segmentation not available: {e}")
    STYLESYNC_AVAILABLE = False


if STYLESYNC_AVAILABLE:
    @app.get("/stylesync/healthz", response_model=HealthResponse)
    def stylesync_health_check():
        """StyleSync segmentation service health check."""
        return HealthResponse(
            ok=True,
            version="v1.0.0",
            service="stylesync-segmentation"
        )

    @app.post("/stylesync/segment", response_model=SegmentResponse)
    async def stylesync_segment(
        file: UploadFile = File(...),
        max_edge: int = Query(768, ge=256, le=4096, description="Maximum edge size for resizing"),
        gamma: float = Query(1.2, ge=0.8, le=2.2, description="Gamma correction value"),
        engine: str = Query("auto", pattern="^(auto|u2netp|grabcut)$", description="Segmentation engine"),
        morph_kernel: int = Query(3, ge=1, le=7, description="Morphological kernel size (odd)"),
        median_blur: int = Query(5, ge=0, le=9, description="Median blur size (odd, 0=disabled)")
    ):
        """
        Segment clothing item from uploaded image.
        
        - **file**: JPG or PNG image file
        - **max_edge**: Resize long edge to this max size (256-4096 px)
        - **gamma**: Gamma correction for shadow lifting (0.8-2.2) 
        - **engine**: auto (rembg→grabcut), u2netp (rembg only), grabcut (opencv only)
        - **morph_kernel**: Morphological close kernel size (1-7, odd)
        - **median_blur**: Median blur for edge smoothing (0-9, odd)
        
        Returns segmentation artifacts: binary mask, RGBA cutout, bounding box.
        """
        # Validate odd kernel sizes
        if morph_kernel > 0 and morph_kernel % 2 == 0:
            raise HTTPException(status_code=400, detail="morph_kernel must be odd")
        if median_blur > 0 and median_blur % 2 == 0:
            raise HTTPException(status_code=400, detail="median_blur must be odd")
        
        return await run_segmentation(
            file=file,
            max_edge=max_edge,
            gamma=gamma,
            engine=engine,
            morph_kernel=morph_kernel,
            median_blur=median_blur
        )

    @app.get("/stylesync/metrics")
    def stylesync_metrics():
        """Get StyleSync segmentation metrics."""
        try:
            metrics = get_metrics()
            return metrics.get_summary()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

    # =============================================================================
    # StyleSync Color Extraction Endpoints (Phase 2)
    # =============================================================================

    try:
        from app.schemas import ColorExtractResponse, ColorExtractRequestDirect
        from app.services.colors.extract_api import handle_extract

        @app.post("/colors/extract", response_model=ColorExtractResponse)
        async def extract_colors(
            # One-Shot mode: Upload file directly
            file: Optional[UploadFile] = File(None),
            
            # Direct mode: JSON request body with mask and image data
            direct: Optional[ColorExtractRequestDirect] = None,
            
            # Color extraction parameters
            k: int = Query(5, ge=2, le=12, description="Number of color clusters"),
            max_samples: int = Query(20000, ge=1000, le=50000, description="Maximum pixels to sample"),
            gamma: float = Query(1.2, ge=0.8, le=2.2, description="Gamma correction value"),
            erode_for_sampling: int = Query(1, ge=0, le=5, description="Mask erosion pixels for sampling"),
            
            # HSV filter parameters
            filter_shadow_v_lt: float = Query(0.12, ge=0.0, le=1.0, description="Shadow filter: V < threshold"),
            filter_specular_s_lt: float = Query(0.10, ge=0.0, le=1.0, description="Specular filter: S < threshold"),
            filter_specular_v_gt: float = Query(0.95, ge=0.0, le=1.0, description="Specular filter: V > threshold"),
            min_saturation: float = Query(0.0, ge=0.0, le=1.0, description="Minimum saturation threshold"),
            
            # Neutral penalty parameters
            neutral_v_low: float = Query(0.15, ge=0.0, le=1.0, description="Neutral penalty V low threshold"),
            neutral_v_high: float = Query(0.95, ge=0.0, le=1.0, description="Neutral penalty V high threshold"),
            neutral_s_low: float = Query(0.12, ge=0.0, le=1.0, description="Neutral penalty S low threshold"),
            neutral_penalty_weight: float = Query(0.5, ge=0.0, le=2.0, description="Neutral penalty multiplier"),
            
            # Spatial cohesion parameters
            enable_spatial_cohesion: bool = Query(True, description="Enable spatial cohesion bonus"),
            cohesion_weight: float = Query(0.10, ge=0.0, le=1.0, description="Spatial cohesion weight"),
            
            # Phase-1 integration parameters (for One-Shot mode)
            max_edge: int = Query(768, ge=256, le=4096, description="Maximum edge for Phase-1 segmentation"),
            phase1_engine: str = Query("auto", pattern="^(auto|u2netp|grabcut)$", description="Phase-1 segmentation engine"),
            phase1_morph_kernel: int = Query(3, ge=1, le=7, description="Phase-1 morphological kernel"),
            phase1_median_blur: int = Query(5, ge=0, le=9, description="Phase-1 median blur"),
            
            # Artifacts
            include_swatch: bool = Query(True, description="Include color swatch PNG in response")
        ):
            """
            Extract dominant colors and select base color from clothing item.
            
            **Two modes supported:**
            
            1. **One-Shot Mode**: Upload image file directly, Phase-1 segmentation runs automatically
               - Use 'file' parameter with JPG/PNG image
               - Segmentation → Color extraction in single API call
               
            2. **Direct Mode**: Provide pre-segmented mask and item data
               - Use 'direct' JSON body with mask_png_b64 and item image data
               - Requires mask from previous Phase-1 segmentation call
            
            **Parameters:**
            - **k**: Number of color clusters to extract (2-12)
            - **max_samples**: Maximum pixels to sample for clustering (1K-50K)
            - **gamma**: Gamma correction for shadow/highlight adjustment (0.8-2.2)
            - **erode_for_sampling**: Mask erosion for stable sampling (0-5 px)
            
            **HSV Filtering:**
            - **filter_shadow_v_lt**: Remove dark shadows (V < threshold)
            - **filter_specular_s_lt**: Remove specular highlights (S < threshold) 
            - **filter_specular_v_gt**: Remove bright highlights (V > threshold)
            - **min_saturation**: Minimum color saturation (0.0-1.0)
            
            **Base Color Selection:**
            - **neutral_penalty_weight**: Penalty for neutral/gray colors (0.0-2.0)
            - **enable_spatial_cohesion**: Use spatial analysis for color scoring
            - **cohesion_weight**: Weight for spatial cohesion bonus (0.0-1.0)
            
            **Returns:** Color palette with ratios, base color selection, and optional artifacts.
            """
            # Validate odd kernel sizes for Phase-1 integration
            if phase1_morph_kernel > 0 and phase1_morph_kernel % 2 == 0:
                raise HTTPException(status_code=400, detail="phase1_morph_kernel must be odd")
            if phase1_median_blur > 0 and phase1_median_blur % 2 == 0:
                raise HTTPException(status_code=400, detail="phase1_median_blur must be odd")
            
            # Build parameters dictionary
            params = {
                'k': k,
                'max_samples': max_samples,
                'gamma': gamma,
                'erode_for_sampling': erode_for_sampling,
                'filter_shadow_v_lt': filter_shadow_v_lt,
                'filter_specular_s_lt': filter_specular_s_lt,
                'filter_specular_v_gt': filter_specular_v_gt,
                'min_saturation': min_saturation,
                'neutral_v_low': neutral_v_low,
                'neutral_v_high': neutral_v_high,
                'neutral_s_low': neutral_s_low,
                'neutral_penalty_weight': neutral_penalty_weight,
                'enable_spatial_cohesion': enable_spatial_cohesion,
                'cohesion_weight': cohesion_weight,
                'max_edge': max_edge,
                'phase1_engine': phase1_engine,
                'phase1_morph_kernel': phase1_morph_kernel,
                'phase1_median_blur': phase1_median_blur,
                'include_swatch': include_swatch
            }
            
            return await handle_extract(file=file, direct=direct, params=params)

        # Color Suggestion Endpoint (Phase 3)
        try:
            from app.schemas import ColorSuggestionResponse, ColorSuggestionRequestDirect
            from app.services.colors.suggest_api import handle_suggest

            @app.post("/colors/suggest", response_model=ColorSuggestionResponse)
            async def suggest_colors(
                # Mode A: Direct base color
                base_hex: Optional[str] = Query(None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Base color in format #RRGGBB"),
                palette: Optional[str] = Query(None, description="JSON-encoded Phase-2 palette for reference"),
                
                # Mode B: Phase-2 passthrough (via request body)
                phase2_response: Optional[dict] = None,
                
                # Mode C: One-shot file upload
                file: Optional[UploadFile] = File(None),
                
                # Garment roles
                source_role: str = Query("top", pattern="^(top|bottom|dress|outerwear)$", description="Source garment role"),
                target_role: str = Query("bottom", pattern="^(bottom|top|outerwear|accessory)$", description="Target garment role"),
                
                # Style parameters  
                intent: str = Query("classic", pattern="^(safe|classic|bold)$", description="Style intent level"),
                season: str = Query("all", pattern="^(all|spring_summer|autumn_winter)$", description="Seasonal bias"),
                
                # Category toggles
                include_complementary: bool = Query(True, description="Include complementary suggestions"),
                include_analogous: bool = Query(True, description="Include analogous suggestions"),
                include_triadic: bool = Query(True, description="Include triadic suggestions"),
                include_neutrals: bool = Query(True, description="Include neutral suggestions"),
                
                # Output parameters
                neutrals_max: int = Query(4, ge=2, le=6, description="Maximum neutral suggestions"),
                return_swatch: bool = Query(True, description="Generate swatch artifact"),
                color_naming: str = Query("css_basic", pattern="^(none|css_basic|compact)$", description="Color naming mode"),
                
                # Phase-1 integration parameters (for One-Shot mode)
                max_edge: int = Query(768, ge=256, le=4096, description="Maximum edge for Phase-1 segmentation"),
                phase1_engine: str = Query("auto", pattern="^(auto|u2netp|grabcut)$", description="Phase-1 segmentation engine"),
                phase1_morph_kernel: int = Query(3, ge=1, le=7, description="Phase-1 morphological kernel"),
                
                # Color extraction parameters (for One-Shot mode) 
                k: int = Query(5, ge=2, le=12, description="Number of color clusters"),
                max_samples: int = Query(20000, ge=1000, le=50000, description="Maximum pixels to sample"),
                gamma: float = Query(1.2, ge=0.8, le=2.2, description="Gamma correction value"),
                erode_for_sampling: int = Query(1, ge=0, le=5, description="Mask erosion pixels for sampling"),
                filter_shadow_v_lt: float = Query(0.12, ge=0.0, le=1.0, description="Shadow filter threshold"),
                filter_specular_s_lt: float = Query(0.10, ge=0.0, le=1.0, description="Specular filter S threshold"),
                filter_specular_v_gt: float = Query(0.95, ge=0.0, le=1.0, description="Specular filter V threshold"),
                min_saturation: float = Query(0.0, ge=0.0, le=1.0, description="Minimum saturation threshold"),
                neutral_v_low: float = Query(0.15, ge=0.0, le=1.0, description="Neutral penalty V low threshold"),
                neutral_v_high: float = Query(0.95, ge=0.0, le=1.0, description="Neutral penalty V high threshold"),
                neutral_s_low: float = Query(0.12, ge=0.0, le=1.0, description="Neutral penalty S low threshold"),
                neutral_penalty_weight: float = Query(0.5, ge=0.0, le=2.0, description="Neutral penalty multiplier"),
                enable_spatial_cohesion: bool = Query(True, description="Enable spatial cohesion bonus"),
                cohesion_weight: float = Query(0.10, ge=0.0, le=1.0, description="Spatial cohesion weight"),
                include_swatch: bool = Query(True, description="Include swatch artifact in extraction")
            ):
                """
                **Color Suggestion Generation (Phase 3)**
                
                Generate wearable color suggestions for outfit coordination using color harmony theory.
                Supports three input modes:
                
                **Mode A - Direct Base Color:**
                - Provide `base_hex` parameter with color in #RRGGBB format
                - Optional: Include `palette` from Phase-2 for reference
                
                **Mode B - Phase-2 Passthrough:**
                - Send Phase-2 response object in request body as `phase2_response`
                - Base color extracted from `phase2_response.base_color.hex`
                
                **Mode C - One-Shot:**
                - Upload image file directly; runs Phase-1→Phase-2→Phase-3 pipeline
                - Slower but convenient for single-step processing
                
                **Harmony Categories:**
                - **Complementary**: +180° hue rotation with contrast adjustments
                - **Analogous**: ±30° hue rotations with similar tones  
                - **Triadic**: ±120° hue rotations with balanced lightness
                - **Neutrals**: Curated neutral colors with base-lightness ordering
                
                **Style Intent:**
                - **safe**: Conservative, neutrals prioritized, lower saturation caps
                - **classic**: Balanced wardrobe staples with moderate saturation
                - **bold**: Higher saturation/contrast, more category variety
                
                **Wearability Constraints:**
                - Role-aware saturation caps and lightness bands
                - Minimum contrast enforcement (ΔL ≥ 0.12)
                - Seasonal lightness bias (±0.05)
                - Hyper-saturation reduction for extreme base colors
                
                **Returns:** Categorized color suggestions with rationale, policy disclosure, and optional swatch.
                """
                # Parse palette JSON if provided
                parsed_palette = None
                if palette:
                    try:
                        import json
                        parsed_palette = json.loads(palette)
                    except (json.JSONDecodeError, TypeError):
                        raise HTTPException(
                            status_code=400, 
                            detail="Invalid palette JSON format"
                        )
                
                # Validate Phase-1 kernel parameters
                if phase1_morph_kernel > 0 and phase1_morph_kernel % 2 == 0:
                    raise HTTPException(
                        status_code=400, 
                        detail="phase1_morph_kernel must be odd"
                    )
                
                return await handle_suggest(
                    base_hex=base_hex,
                    palette=parsed_palette,
                    phase2_response=phase2_response,
                    file=file,
                    source_role=source_role,
                    target_role=target_role,
                    intent=intent,
                    season=season,
                    include_complementary=include_complementary,
                    include_analogous=include_analogous,
                    include_triadic=include_triadic,
                    include_neutrals=include_neutrals,
                    neutrals_max=neutrals_max,
                    return_swatch=return_swatch,
                    color_naming=color_naming,
                    max_edge=max_edge,
                    phase1_engine=phase1_engine,
                    phase1_morph_kernel=phase1_morph_kernel,
                    k=k,
                    max_samples=max_samples,
                    gamma=gamma,
                    erode_for_sampling=erode_for_sampling,
                    filter_shadow_v_lt=filter_shadow_v_lt,
                    filter_specular_s_lt=filter_specular_s_lt,
                    filter_specular_v_gt=filter_specular_v_gt,
                    min_saturation=min_saturation,
                    neutral_v_low=neutral_v_low,
                    neutral_v_high=neutral_v_high,
                    neutral_s_low=neutral_s_low,
                    neutral_penalty_weight=neutral_penalty_weight,
                    enable_spatial_cohesion=enable_spatial_cohesion,
                    cohesion_weight=cohesion_weight,
                    include_swatch=include_swatch
                )

        except ImportError as e:
            @app.post("/colors/suggest")
            async def colors_suggest_unavailable():
                """Color suggestion service unavailable due to missing dependencies."""
                raise HTTPException(
                    status_code=503,
                    detail="Color suggestion service unavailable: missing dependencies"
                )

    except ImportError as e:
        @app.post("/colors/extract")
        async def colors_extract_unavailable():
            """Color extraction service unavailable due to missing dependencies."""
            raise HTTPException(
                status_code=503,
                detail="Color extraction service unavailable: missing dependencies"
            )

else:
    @app.get("/stylesync/healthz")
    def stylesync_health_unavailable():
        """StyleSync segmentation service unavailable."""
        return {
            "ok": False,
            "version": "v1.0.0",
            "service": "stylesync-segmentation",
            "error": "StyleSync dependencies not installed"
        }
