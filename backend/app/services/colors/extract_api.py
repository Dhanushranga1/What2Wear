"""
Color Extraction API Orchestrator

Handles Direct and One-Shot modes for color extraction. Coordinates the full
pipeline from input validation through color clustering to base color selection.
"""

import time
import numpy as np
from typing import Dict, Optional, Tuple, Any
from fastapi import UploadFile

try:
    import cv2
except ImportError:
    cv2 = None

from app.utils.logging import logger
from app.schemas import ColorExtractResponse, ColorExtractRequestDirect
from app.services.colors.extraction import (
    sample_garment_pixels, cluster_palette, decode_base64_image,
    validate_mask_binary, validate_dimensions_match, process_rgba_to_rgb_and_mask
)
from app.services.colors.base_selection import choose_base_color, analyze_color_harmony
from app.services.colors.swatches import render_swatch_strip, validate_swatch_params
from app.services.segmentation.pipeline import run_segmentation
from app.utils.ids import generate_request_id
from app.utils.metrics import get_metrics_instance


async def handle_extract(
    file: Optional[UploadFile] = None,
    direct: Optional[ColorExtractRequestDirect] = None,
    params: Dict[str, Any] = None
) -> ColorExtractResponse:
    """
    Main orchestrator for color extraction supporting both Direct and One-Shot modes.
    
    Args:
        file: Uploaded image file for One-Shot mode
        direct: Direct mode request with mask and image data
        params: Dictionary of extraction parameters
        
    Returns:
        ColorExtractResponse with palette and base color
        
    Raises:
        ValueError: For invalid inputs or parameter combinations
        RuntimeError: For processing failures
    """
    request_id = generate_request_id("color")
    start_time = time.time()
    
    logger.info(f"Starting color extraction", extra={"request_id": request_id})
    
    # Validate input modes
    if file is None and direct is None:
        raise ValueError("Either 'file' (One-Shot) or 'direct' mode data must be provided")
    
    if file is not None and direct is not None:
        raise ValueError("Cannot specify both 'file' and 'direct' mode simultaneously")
    
    # Extract parameters with defaults
    k = params.get('k', 5)
    max_samples = params.get('max_samples', 20000)
    gamma = params.get('gamma', 1.2)
    erode_for_sampling = params.get('erode_for_sampling', 1)
    
    # Filter parameters
    filter_shadow_v_lt = params.get('filter_shadow_v_lt', 0.12)
    filter_specular_s_lt = params.get('filter_specular_s_lt', 0.10)
    filter_specular_v_gt = params.get('filter_specular_v_gt', 0.95)
    min_saturation = params.get('min_saturation', 0.0)
    
    # Neutral penalty parameters
    neutral_v_low = params.get('neutral_v_low', 0.15)
    neutral_v_high = params.get('neutral_v_high', 0.95)
    neutral_s_low = params.get('neutral_s_low', 0.12)
    neutral_penalty_weight = params.get('neutral_penalty_weight', 0.5)
    
    # Spatial cohesion parameters
    enable_spatial_cohesion = params.get('enable_spatial_cohesion', True)
    cohesion_weight = params.get('cohesion_weight', 0.10)
    
    # Artifacts
    include_swatch = params.get('include_swatch', True)
    
    try:
        # Determine processing mode and get image + mask
        if direct is not None:
            mode = "direct"
            item_bgr, mask_u8, width, height = await _process_direct_mode(direct, gamma)
            mask_area_ratio = np.sum(mask_u8 > 0) / (width * height)
        else:
            mode = "oneshot" 
            item_bgr, mask_u8, width, height, mask_area_ratio = await _process_oneshot_mode(
                file, gamma, params
            )
        
        decode_time = time.time() - start_time
        logger.info(f"Input processing complete: {mode} mode", 
                   extra={"request_id": request_id, "ms_decode": decode_time * 1000})
        
        # Sample and filter garment pixels
        filter_start = time.time()
        filtered_pixels = sample_garment_pixels(
            item_bgr=item_bgr,
            mask_u8=mask_u8,
            erode_px=erode_for_sampling,
            gamma=gamma,
            max_samples=max_samples,
            shadow_v_lt=filter_shadow_v_lt,
            spec_s_lt=filter_specular_s_lt,
            spec_v_gt=filter_specular_v_gt,
            min_saturation=min_saturation,
            rng_seed=42
        )
        filter_time = time.time() - filter_start
        sampled_pixels = len(filtered_pixels)
        
        logger.info(f"Pixel sampling complete: {sampled_pixels} pixels",
                   extra={"request_id": request_id, "ms_filter": filter_time * 1000})
        
        # Cluster colors into palette
        cluster_start = time.time()
        palette, ordered_centers, ordered_ratios, ordered_indices = cluster_palette(
            filtered_pixels, k=k, rng_seed=42
        )
        cluster_time = time.time() - cluster_start
        
        logger.info(f"Clustering complete: {len(palette)} colors",
                   extra={"request_id": request_id, "ms_kmeans": cluster_time * 1000})
        
        # Select base color using scoring algorithm
        cohesion_start = time.time()
        
        neutral_params = {
            'v_low': neutral_v_low,
            'v_high': neutral_v_high,
            's_low': neutral_s_low,
            'penalty_weight': neutral_penalty_weight
        }
        
        cohesion_params = {
            'enabled': enable_spatial_cohesion,
            'weight': cohesion_weight
        }
        
        base_index, score_breakdown = choose_base_color(
            ordered_centers=ordered_centers,
            ordered_ratios=ordered_ratios,
            item_bgr=item_bgr,
            mask_u8=mask_u8,
            neutral_params=neutral_params,
            cohesion_params=cohesion_params
        )
        
        cohesion_time = time.time() - cohesion_start
        
        base_color_info = {
            "hex": palette[base_index]["hex"],
            "cluster_index": base_index,
            "score_breakdown": score_breakdown
        }
        
        logger.info(f"Base color selection complete: {base_color_info['hex']}",
                   extra={"request_id": request_id, "ms_cohesion": cohesion_time * 1000})
        
        # Generate optional artifacts
        artifacts = None
        if include_swatch or True:  # Always include for now
            swatch_b64 = None
            harmony_analysis = None
            
            if include_swatch:
                try:
                    hex_colors = [entry["hex"] for entry in palette]
                    validate_swatch_params(hex_colors, 40, base_index)
                    swatch_b64 = render_swatch_strip(hex_colors, highlight_index=base_index)
                except Exception as e:
                    logger.warning(f"Swatch generation failed: {str(e)}", 
                                 extra={"request_id": request_id})
            
            # Generate color harmony analysis
            try:
                harmony_analysis = analyze_color_harmony(palette)
            except Exception as e:
                logger.warning(f"Harmony analysis failed: {str(e)}", 
                             extra={"request_id": request_id})
            
            artifacts = {
                "swatch_png_b64": swatch_b64,
                "mask_area_ratio": float(mask_area_ratio),
                "harmony_analysis": harmony_analysis
            }
        
        # Build debug information
        debug_info = {
            "gamma": gamma,
            "erode_for_sampling": erode_for_sampling,
            "filters": {
                "shadow_v_lt": filter_shadow_v_lt,
                "specular_s_lt": filter_specular_s_lt,
                "specular_v_gt": filter_specular_v_gt,
                "min_saturation": min_saturation
            },
            "neutral_thresholds": {
                "v_low": neutral_v_low,
                "v_high": neutral_v_high,
                "s_low": neutral_s_low,
                "penalty_weight": neutral_penalty_weight
            },
            "cohesion": {
                "enabled": enable_spatial_cohesion,
                "weight": cohesion_weight
            },
            "processing_mode": mode
        }
        
        # Build response
        total_time = time.time() - start_time
        
        response = ColorExtractResponse(
            width=width,
            height=height,
            k=k,
            sampled_pixels=sampled_pixels,
            palette=palette,
            base_color=base_color_info,
            debug=debug_info,
            artifacts=artifacts
        )
        
        # Log completion
        logger.info(f"Color extraction completed successfully",
                   extra={
                       "request_id": request_id,
                       "mode": mode,
                       "dims": f"{width}x{height}",
                       "k": k,
                       "sampled_pixels": sampled_pixels,
                       "base_hex": base_color_info["hex"],
                       "base_score": score_breakdown["final_score"],
                       "ms_decode": decode_time * 1000,
                       "ms_filter": filter_time * 1000,
                       "ms_kmeans": cluster_time * 1000,
                       "ms_cohesion": cohesion_time * 1000,
                       "ms_total": total_time * 1000,
                       "result": "ok"
                   })
        
        # Update metrics
        metrics = get_metrics_instance()
        metrics.increment_counter("color_extract_requests_total")
        metrics.increment_counter(f"color_extract_mode_total_{mode}")
        metrics.record_timing("color_extract_duration_ms", total_time * 1000)
        metrics.record_timing("kmeans_duration_ms", cluster_time * 1000)
        if enable_spatial_cohesion:
            metrics.record_timing("cohesion_duration_ms", cohesion_time * 1000)
        
        return response
        
    except Exception as e:
        error_time = time.time() - start_time
        logger.error(f"Color extraction failed: {str(e)}",
                    extra={
                        "request_id": request_id,
                        "ms_total": error_time * 1000,
                        "result": "error",
                        "error_type": type(e).__name__
                    })
        
        # Update error metrics
        metrics = get_metrics_instance()
        metrics.increment_counter("color_extract_failed_total")
        metrics.increment_counter(f"color_extract_error_{type(e).__name__.lower()}")
        
        raise


async def _process_direct_mode(direct: ColorExtractRequestDirect, gamma: float) -> Tuple[np.ndarray, np.ndarray, int, int]:
    """
    Process Direct mode input: decode mask and image from base64.
    
    Returns:
        Tuple of (item_bgr, mask_u8, width, height)
    """
    logger.debug("Processing Direct mode input")
    
    # Decode and validate mask
    mask_image = decode_base64_image(direct.mask_png_b64)
    mask_u8 = validate_mask_binary(mask_image)
    
    # Decode item image
    item_bgr = None
    
    if direct.item_rgba_png_b64 is not None:
        # RGBA mode: extract RGB and cross-check alpha with mask
        rgba_image = decode_base64_image(direct.item_rgba_png_b64)
        item_bgr, alpha_mask = process_rgba_to_rgb_and_mask(rgba_image)
        
        # Cross-check alpha consistency with provided mask
        alpha_area_ratio = np.sum(alpha_mask > 0) / alpha_mask.size
        mask_area_ratio = np.sum(mask_u8 > 0) / mask_u8.size
        
        if abs(alpha_area_ratio - mask_area_ratio) > 0.1:  # 10% tolerance
            logger.warning(f"Alpha mask inconsistency: alpha_ratio={alpha_area_ratio:.3f}, "
                         f"mask_ratio={mask_area_ratio:.3f}")
        
    elif direct.item_png_b64 is not None:
        # RGB mode: decode RGB image directly
        item_bgr = decode_base64_image(direct.item_png_b64)
        
    else:
        raise ValueError("Either item_rgba_png_b64 or item_png_b64 must be provided in Direct mode")
    
    # Validate dimensions match
    validate_dimensions_match(item_bgr, mask_u8)
    
    height, width = mask_u8.shape
    
    logger.debug(f"Direct mode processing complete: {width}x{height}")
    
    return item_bgr, mask_u8, width, height


async def _process_oneshot_mode(file: UploadFile, gamma: float, params: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray, int, int, float]:
    """
    Process One-Shot mode: call Phase-1 segmentation then extract color data.
    
    Returns:
        Tuple of (item_bgr, mask_u8, width, height, mask_area_ratio)
    """
    logger.debug("Processing One-Shot mode input")
    
    # Extract Phase-1 parameters from color extraction params
    phase1_params = {
        'max_edge': params.get('max_edge', 768),
        'gamma': gamma,
        'engine': params.get('phase1_engine', 'auto'),
        'morph_kernel': params.get('phase1_morph_kernel', 3),
        'median_blur': params.get('phase1_median_blur', 5)
    }
    
    # Call Phase-1 segmentation pipeline
    try:
        segmentation_result = await run_segmentation(file, **phase1_params)
    except Exception as e:
        raise RuntimeError(f"Phase-1 segmentation failed: {str(e)}")
    
    # Extract item image and mask from segmentation result
    # Note: This requires implementing run_segmentation_internal to return the processed data
    # For now, we'll simulate this - in real implementation, modify segmentation pipeline
    
    # Decode artifacts from segmentation result
    mask_b64 = segmentation_result["artifacts"]["mask_png_b64"]
    item_rgba_b64 = segmentation_result["artifacts"]["item_rgba_png_b64"]
    
    # Process like Direct mode RGBA
    mask_image = decode_base64_image(mask_b64)
    mask_u8 = validate_mask_binary(mask_image)
    
    rgba_image = decode_base64_image(item_rgba_b64)
    item_bgr, _ = process_rgba_to_rgb_and_mask(rgba_image)
    
    width = segmentation_result["width"]
    height = segmentation_result["height"]
    mask_area_ratio = segmentation_result["mask_area_ratio"]
    
    logger.debug(f"One-Shot mode processing complete: {width}x{height}, "
                f"mask_ratio={mask_area_ratio:.3f}")
    
    return item_bgr, mask_u8, width, height, mask_area_ratio
