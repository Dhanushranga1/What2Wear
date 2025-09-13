"""
Color Suggestion API Orchestrator

Handles Direct, Phase-2 Passthrough, and One-Shot modes for color suggestion
generation. Coordinates the harmony engine with input validation and response
formatting for the /colors/suggest endpoint.
"""

import time
from typing import Dict, Optional, Any
from fastapi import UploadFile, HTTPException

from app.utils.logging import logger
from app.schemas import (
    ColorSuggestionResponse, ColorSuggestionRequestDirect, 
    ColorExtractRequestDirect, ColorExtractResponse
)
from app.services.colors.harmony.orchestrator import generate_color_suggestions
from app.services.colors.harmony.wearability import (
    GarmentRole, StyleIntent, Season, WearabilityPolicy
)
from app.services.colors.extract_api import handle_extract
from app.utils.ids import generate_request_id
from app.utils.metrics import get_metrics_instance


async def handle_suggest(
    # Mode A: Direct base color
    base_hex: Optional[str] = None,
    palette: Optional[list] = None,
    
    # Mode B: Phase-2 passthrough 
    phase2_response: Optional[dict] = None,
    
    # Mode C: One-shot file upload
    file: Optional[UploadFile] = None,
    
    # Garment roles
    source_role: str = "top",
    target_role: str = "bottom",
    
    # Style parameters
    intent: str = "classic",
    season: str = "all",
    
    # Category toggles
    include_complementary: bool = True,
    include_analogous: bool = True,
    include_triadic: bool = True,
    include_neutrals: bool = True,
    
    # Output parameters
    neutrals_max: int = 4,
    return_swatch: bool = True,
    color_naming: str = "css_basic",
    
    # Phase-1 integration parameters (for One-Shot mode)
    max_edge: int = 768,
    phase1_engine: str = "auto",
    phase1_morph_kernel: int = 3,
    
    # Additional extraction params for one-shot
    **extraction_params
) -> ColorSuggestionResponse:
    """
    Main orchestrator for color suggestion generation supporting multiple input modes.
    
    Args:
        base_hex: Direct base color (Mode A)
        palette: Optional palette from Phase-2 for reference
        phase2_response: Phase-2 response object (Mode B) 
        file: Uploaded image file (Mode C)
        source_role: Role of garment providing base color
        target_role: Role of garment to suggest colors for
        intent: Style intent level
        season: Seasonal bias
        include_*: Category inclusion flags
        neutrals_max: Maximum neutral suggestions
        return_swatch: Whether to generate swatch artifact
        color_naming: Color naming mode (not implemented in MVP)
        max_edge: Maximum edge for Phase-1 (One-Shot mode)
        phase1_engine: Segmentation engine for One-Shot mode
        phase1_morph_kernel: Morphological kernel for One-Shot mode
        **extraction_params: Additional color extraction parameters
        
    Returns:
        ColorSuggestionResponse with categorized suggestions
        
    Raises:
        HTTPException: For invalid inputs or processing failures
    """
    request_id = generate_request_id()
    start_time = time.time()
    
    logger.info(f"Color suggestion request {request_id} started", extra={
        "request_id": request_id,
        "mode": _determine_input_mode(base_hex, phase2_response, file),
        "source_role": source_role,
        "target_role": target_role,
        "intent": intent,
        "season": season
    })
    
    metrics = get_metrics_instance()
    
    try:
        # Determine and validate input mode
        input_mode = _determine_input_mode(base_hex, phase2_response, file)
        
        # Extract base color based on input mode
        if input_mode == "direct":
            final_base_hex = _handle_direct_mode(base_hex)
            extraction_time = 0
            
        elif input_mode == "phase2_passthrough":
            final_base_hex = _handle_phase2_passthrough(phase2_response)
            extraction_time = 0
            
        elif input_mode == "oneshot":
            final_base_hex, extraction_time = await _handle_oneshot_mode(
                file, max_edge, phase1_engine, phase1_morph_kernel, **extraction_params
            )
            
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid input mode. Provide base_hex, phase2_response, or file."
            )
        
        # Validate and convert role/intent/season parameters
        source_role_enum = _validate_garment_role(source_role, "source_role")
        target_role_enum = _validate_garment_role(target_role, "target_role")
        intent_enum = _validate_style_intent(intent)
        season_enum = _validate_season(season)
        
        # Generate color suggestions
        suggestion_start = time.time()
        
        suggestions_response = generate_color_suggestions(
            base_hex=final_base_hex,
            source_role=source_role_enum,
            target_role=target_role_enum,
            intent=intent_enum,
            season=season_enum,
            include_complementary=include_complementary,
            include_analogous=include_analogous,
            include_triadic=include_triadic,
            include_neutrals=include_neutrals,
            neutrals_max=neutrals_max,
            return_swatch=return_swatch,
            policy=WearabilityPolicy()
        )
        
        suggestion_time = time.time() - suggestion_start
        total_time = time.time() - start_time
        
        # Add extraction timing to debug info
        suggestions_response["debug"]["timing_ms"]["extraction"] = round(extraction_time * 1000, 2)
        suggestions_response["debug"]["timing_ms"]["suggestions"] = round(suggestion_time * 1000, 2)
        suggestions_response["debug"]["timing_ms"]["total"] = round(total_time * 1000, 2)
        suggestions_response["debug"]["input_mode"] = input_mode
        suggestions_response["debug"]["request_id"] = request_id
        
        # Log success metrics
        total_suggestions = sum(
            len(category_suggestions) 
            for category_suggestions in suggestions_response["suggestions"].values()
        )
        
        logger.info(f"Color suggestion request {request_id} completed", extra={
            "request_id": request_id,
            "base_hex": final_base_hex,
            "total_suggestions": total_suggestions,
            "total_time_ms": round(total_time * 1000, 2),
            "input_mode": input_mode
        })
        
        # Update metrics
        metrics.record_operation_success(
            "suggest_colors",
            duration_ms=total_time * 1000,
            memory_mb=0,  # Will be filled by metrics decorator if used
            metadata={
                "intent": intent,
                "season": season,
                "input_mode": input_mode,
                "total_suggestions": total_suggestions
            }
        )
        
        return ColorSuggestionResponse(**suggestions_response)
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
        
    except Exception as e:
        error_time = time.time() - start_time
        
        logger.error(f"Color suggestion request {request_id} failed", extra={
            "request_id": request_id,
            "error": str(e),
            "error_time_ms": round(error_time * 1000, 2)
        })
        
        # Update error metrics
        metrics.record_operation_error(
            "suggest_colors",
            str(e),
            duration_ms=error_time * 1000
        )
        
        raise HTTPException(
            status_code=500,
            detail="Internal error during color suggestion generation"
        )


def _determine_input_mode(base_hex: Optional[str], phase2_response: Optional[dict], file: Optional[UploadFile]) -> str:
    """Determine which input mode is being used."""
    modes_provided = sum([
        base_hex is not None,
        phase2_response is not None,
        file is not None
    ])
    
    if modes_provided == 0:
        raise HTTPException(
            status_code=400,
            detail="Must provide base_hex, phase2_response, or file"
        )
    
    if modes_provided > 1:
        raise HTTPException(
            status_code=400,
            detail="Provide only one input mode: base_hex, phase2_response, or file"
        )
    
    if base_hex is not None:
        return "direct"
    elif phase2_response is not None:
        return "phase2_passthrough"
    else:
        return "oneshot"


def _handle_direct_mode(base_hex: str) -> str:
    """Handle direct base color input mode."""
    if not base_hex.startswith('#') or len(base_hex) != 7:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid base_hex format: {base_hex}. Expected #RRGGBB"
        )
    
    try:
        # Validate hex digits
        int(base_hex[1:], 16)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid hex color: {base_hex}"
        )
    
    return base_hex.upper()


def _handle_phase2_passthrough(phase2_response: dict) -> str:
    """Handle Phase-2 response passthrough mode."""
    if not isinstance(phase2_response, dict):
        raise HTTPException(
            status_code=400,
            detail="phase2_response must be a valid JSON object"
        )
    
    # Extract base color from Phase-2 response
    base_color = phase2_response.get("base_color")
    if not base_color:
        raise HTTPException(
            status_code=400,
            detail="phase2_response missing base_color field"
        )
    
    base_hex = base_color.get("hex")
    if not base_hex:
        raise HTTPException(
            status_code=400,
            detail="phase2_response.base_color missing hex field"
        )
    
    return _handle_direct_mode(base_hex)  # Validate format


async def _handle_oneshot_mode(
    file: UploadFile,
    max_edge: int,
    phase1_engine: str,
    phase1_morph_kernel: int,
    **extraction_params
) -> tuple:
    """Handle one-shot file upload mode by calling Phase-1 → Phase-2."""
    if not file:
        raise HTTPException(
            status_code=400,
            detail="File required for one-shot mode"
        )
    
    extraction_start = time.time()
    
    try:
        # Call Phase-1 → Phase-2 pipeline
        extraction_response = await handle_extract(
            file=file,
            direct=None,
            params={
                "max_edge": max_edge,
                "phase1_engine": phase1_engine,
                "phase1_morph_kernel": phase1_morph_kernel,
                **extraction_params
            }
        )
        
        extraction_time = time.time() - extraction_start
        
        # Extract base color from response
        base_hex = extraction_response.base_color.hex
        return base_hex, extraction_time
        
    except Exception as e:
        logger.error("One-shot Phase-1→Phase-2 failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=422,
            detail=f"Failed to extract colors from uploaded image: {str(e)}"
        )


def _validate_garment_role(role: str, param_name: str) -> GarmentRole:
    """Validate and convert garment role parameter."""
    try:
        return GarmentRole(role)
    except ValueError:
        valid_roles = [r.value for r in GarmentRole]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {param_name}: {role}. Valid options: {valid_roles}"
        )


def _validate_style_intent(intent: str) -> StyleIntent:
    """Validate and convert style intent parameter."""
    try:
        return StyleIntent(intent)
    except ValueError:
        valid_intents = [i.value for i in StyleIntent]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid intent: {intent}. Valid options: {valid_intents}"
        )


def _validate_season(season: str) -> Season:
    """Validate and convert season parameter."""
    try:
        return Season(season)
    except ValueError:
        valid_seasons = [s.value for s in Season]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid season: {season}. Valid options: {valid_seasons}"
        )
