"""
StyleSync Phase 4 Unified API Routes
Implements /v1/advice endpoint and supporting routes.
"""
import asyncio
import uuid
import time
from typing import Any, Dict, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Form, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import Config
from app.services.orchestrator import AdviceOrchestrator
from app.services.security import security_manager, idempotency_manager
from app.services.observability import observability
from app.schemas import *

config = Config()
router = APIRouter(prefix="/v1", tags=["Phase 4 - Unified Orchestrator"])

# Initialize orchestrator
orchestrator = AdviceOrchestrator(
    redis_url=config.REDIS_URL,
    policy_version=config.POLICY_VERSION
)


class AdviceRequestBody(BaseModel):
    """Request body for advice endpoint in JSON mode."""
    phase2_response: Optional[Dict[str, Any]] = Field(None, description="Phase 2 response for passthrough mode")
    base_hex: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$", description="Base color for direct mode")
    mask_png_b64: Optional[str] = Field(None, description="Base64 encoded mask PNG")
    item_rgba_png_b64: Optional[str] = Field(None, description="Base64 encoded item RGBA PNG")
    asset_url: Optional[str] = Field(None, description="URL to pre-uploaded asset")


class PresignRequest(BaseModel):
    """Request for presigned upload URL."""
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., description="MIME type of the file")


class PresignResponse(BaseModel):
    """Response for presigned upload URL."""
    asset_id: str
    upload_url: str
    expires_at: int
    max_file_size: int


@router.post("/advice", 
            summary="Unified Outfit Advice",
            description="Get outfit color suggestions through complete Phase 1→2→3 pipeline")
async def get_advice(
    # Authentication
    api_key: str = Depends(security_manager.authenticate_request),
    
    # File upload (multipart mode)
    file: Optional[UploadFile] = File(None, description="Image file for multipart mode"),
    
    # JSON body (other modes)
    request_body: Optional[AdviceRequestBody] = None,
    
    # Cache control
    cache_ok: bool = Query(True, description="Allow cache usage"),
    force_recompute: bool = Query(False, description="Force recomputation"),
    idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    
    # Phase 1 parameters
    max_edge: int = Query(768, ge=256, le=4096, description="Maximum edge size"),
    gamma: float = Query(1.2, ge=0.8, le=2.2, description="Gamma correction"),
    phase1_engine: str = Query("auto", pattern="^(auto|u2netp|grabcut)$", description="Segmentation engine"),
    phase1_morph_kernel: int = Query(3, ge=1, le=7, description="Morphological kernel size"),
    phase1_median_blur: int = Query(5, ge=0, le=9, description="Median blur kernel (odd)"),
    
    # Phase 2 parameters
    k: int = Query(5, ge=2, le=12, description="Number of color clusters"),
    max_samples: int = Query(20000, ge=1000, le=50000, description="Maximum pixels to sample"),
    erode_for_sampling: int = Query(1, ge=0, le=5, description="Mask erosion for sampling"),
    filter_shadow_v_lt: float = Query(0.12, ge=0.0, le=1.0, description="Shadow filter threshold"),
    filter_specular_s_lt: float = Query(0.25, ge=0.0, le=1.0, description="Specular filter saturation"),
    filter_specular_v_gt: float = Query(0.85, ge=0.0, le=1.0, description="Specular filter value"),
    min_saturation: float = Query(0.15, ge=0.0, le=1.0, description="Minimum saturation"),
    neutral_v_low: float = Query(0.2, ge=0.0, le=1.0, description="Neutral value low threshold"),
    neutral_v_high: float = Query(0.8, ge=0.0, le=1.0, description="Neutral value high threshold"),
    neutral_s_low: float = Query(0.3, ge=0.0, le=1.0, description="Neutral saturation threshold"),
    neutral_penalty_weight: float = Query(2.0, ge=0.0, le=10.0, description="Neutral penalty weight"),
    enable_spatial_cohesion: bool = Query(True, description="Enable spatial cohesion"),
    cohesion_weight: float = Query(1.5, ge=0.0, le=5.0, description="Spatial cohesion weight"),
    
    # Phase 3 parameters
    source_role: str = Query("top", pattern="^(top|bottom|dress|outerwear)$", description="Source garment role"),
    target_role: str = Query("bottom", pattern="^(bottom|top|outerwear|accessory)$", description="Target garment role"),
    intent: str = Query("classic", pattern="^(safe|classic|bold)$", description="Style intent"),
    season: str = Query("all", pattern="^(all|spring_summer|autumn_winter)$", description="Seasonal bias"),
    include_complementary: bool = Query(True, description="Include complementary suggestions"),
    include_analogous: bool = Query(True, description="Include analogous suggestions"),
    include_triadic: bool = Query(True, description="Include triadic suggestions"),
    include_neutrals: bool = Query(True, description="Include neutral suggestions"),
    neutrals_max: int = Query(4, ge=2, le=6, description="Maximum neutral suggestions"),
    return_swatch: bool = Query(True, description="Generate swatch artifacts"),
    color_naming: str = Query("css_basic", pattern="^(css_basic|extended)$", description="Color naming scheme")
) -> Dict[str, Any]:
    """
    Unified outfit advice endpoint supporting multiple input modes:
    
    **Mode A - Multipart File Upload:**
    - Provide `file` parameter with image
    - Complete Phase 1→2→3 pipeline
    
    **Mode B - By URL (requires presign):**
    - Provide `asset_url` in request body
    - Download and process image
    
    **Mode C - Artifacts Direct:**
    - Provide `base_hex` to skip to Phase 3
    - Provide `mask_png_b64` + `item_rgba_png_b64` to skip Phase 1
    - Provide `phase2_response` for passthrough mode
    """
    
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    try:
        # Determine input mode
        input_mode = None
        if file:
            input_mode = "multipart"
        elif request_body:
            if request_body.asset_url:
                input_mode = "by_url"
            elif request_body.base_hex or request_body.mask_png_b64 or request_body.phase2_response:
                input_mode = "artifacts_direct"
        
        if not input_mode:
            raise HTTPException(
                status_code=400,
                detail="Invalid request. Provide file, asset_url, or artifacts."
            )
        
        # Validate median blur (must be odd)
        if phase1_median_blur > 0 and phase1_median_blur % 2 == 0:
            raise HTTPException(
                status_code=400,
                detail="phase1_median_blur must be odd"
            )
        
        # Check idempotency
        if idempotency_key and cache_ok and not force_recompute:
            cached_response = idempotency_manager.get_response(idempotency_key)
            if cached_response:
                return cached_response
        
        # Validate file if provided
        if file:
            content = await file.read()
            security_manager.validate_image_upload(file, content)
            # Reset file position for orchestrator
            await file.seek(0)
        
        # Collect all parameters
        params = {
            'input_mode': input_mode,
            'max_edge': max_edge,
            'gamma': gamma,
            'phase1_engine': phase1_engine,
            'phase1_morph_kernel': phase1_morph_kernel,
            'phase1_median_blur': phase1_median_blur,
            'k': k,
            'max_samples': max_samples,
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
            'source_role': source_role,
            'target_role': target_role,
            'intent': intent,
            'season': season,
            'include_complementary': include_complementary,
            'include_analogous': include_analogous,
            'include_triadic': include_triadic,
            'include_neutrals': include_neutrals,
            'neutrals_max': neutrals_max,
            'return_swatch': return_swatch,
            'color_naming': color_naming
        }
        
        # Process with observability
        with observability.observe_request(request_id, input_mode, api_key=api_key[:8]) as span:
            # Call orchestrator
            result = await orchestrator.process_advice_request(
                input_mode=input_mode,
                file=file,
                asset_url=request_body.asset_url if request_body else None,
                phase2_response=request_body.phase2_response if request_body else None,
                base_hex=request_body.base_hex if request_body else None,
                mask_png_b64=request_body.mask_png_b64 if request_body else None,
                item_rgba_png_b64=request_body.item_rgba_png_b64 if request_body else None,
                idempotency_key=idempotency_key,
                cache_ok=cache_ok,
                force_recompute=force_recompute,
                **params
            )
            
            # Store for idempotency
            if idempotency_key:
                idempotency_manager.store_response(idempotency_key, result)
            
            # Add response headers for rate limiting
            rate_status = security_manager.api_key_manager.get_rate_limit_status(api_key)
            
            return JSONResponse(
                content=result,
                headers={
                    "X-Request-ID": request_id,
                    "X-RateLimit-Limit": str(rate_status["limit"]),
                    "X-RateLimit-Remaining": str(rate_status["remaining"]),
                    "X-RateLimit-Window": str(rate_status["window_seconds"])
                }
            )
    
    except HTTPException:
        raise
    except Exception as e:
        observability.logger.log_error(request_id, "orchestration_error", str(e))
        raise HTTPException(
            status_code=500,
            detail="Internal orchestration error"
        )


@router.post("/uploads/presign",
            response_model=PresignResponse,
            summary="Generate Presigned Upload URL",
            description="Get temporary upload URL for large assets")
async def create_presigned_upload(
    request: PresignRequest,
    api_key: str = Depends(security_manager.authenticate_request)
) -> PresignResponse:
    """
    Generate presigned upload URL for large assets.
    Client uploads to the returned URL, then uses asset_id in /v1/advice.
    """
    
    # Validate content type
    if request.content_type not in config.SUPPORTED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type: {request.content_type}"
        )
    
    # Generate asset ID and signed URL
    asset_id = f"upload_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    
    # In a real implementation, this would generate a signed URL to cloud storage
    # For MVP, we'll return a placeholder
    upload_url = f"https://storage.example.com/temp/{asset_id}"
    expires_at = int(time.time()) + 3600  # 1 hour
    
    return PresignResponse(
        asset_id=asset_id,
        upload_url=upload_url,
        expires_at=expires_at,
        max_file_size=config.MAX_FILE_MB * 1024 * 1024
    )


@router.get("/healthz",
           summary="Health Check",
           description="Liveness probe for orchestrator")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "stylesync-orchestrator", 
        "version": "v1",
        "phase": "Phase 4 - Unified Orchestrator",
        "timestamp": int(time.time())
    }


@router.get("/readyz",
           summary="Readiness Check", 
           description="Readiness probe for orchestrator")
async def readiness_check() -> Dict[str, Any]:
    """Readiness check endpoint."""
    
    # Check dependencies
    checks = {
        "orchestrator": True,  # Always ready if endpoint responds
        "cache": True,  # TODO: Add cache connectivity check
        "metrics": observability.metrics.enabled if hasattr(observability, 'metrics') else False
    }
    
    all_ready = all(checks.values())
    status_code = 200 if all_ready else 503
    
    response = {
        "status": "ready" if all_ready else "not_ready",
        "checks": checks,
        "timestamp": int(time.time())
    }
    
    return JSONResponse(content=response, status_code=status_code)


@router.get("/metrics",
           summary="Prometheus Metrics",
           description="Metrics endpoint for monitoring")
async def get_metrics(
    api_key: str = Depends(security_manager.authenticate_request)
) -> str:
    """Get Prometheus metrics."""
    
    metrics_data = observability.get_metrics_endpoint()
    return JSONResponse(
        content=metrics_data,
        media_type="text/plain"
    )


@router.get("/cache/stats",
           summary="Cache Statistics",
           description="Get cache performance statistics")
async def get_cache_stats(
    api_key: str = Depends(security_manager.authenticate_request)
) -> Dict[str, Any]:
    """Get cache statistics."""
    
    return orchestrator.cache.get_cache_stats()


@router.post("/cache/clear",
            summary="Clear Cache",
            description="Clear all cache layers (admin only)")
async def clear_cache(
    api_key: str = Depends(security_manager.authenticate_request),
    confirm: bool = Query(False, description="Confirmation required")
) -> Dict[str, Any]:
    """Clear all cache layers."""
    
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required: set confirm=true"
        )
    
    success = orchestrator.cache.clear_all()
    
    return {
        "status": "cleared" if success else "failed",
        "timestamp": int(time.time())
    }
