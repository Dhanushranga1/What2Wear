"""
StyleSync Segmentation Pipeline
Main orchestration of the segmentation workflow.
"""
import time
from typing import Dict, Any

import numpy as np
try:
    import cv2
except ImportError:
    cv2 = None

from fastapi import HTTPException, UploadFile

from app.config import config
from app.services.imaging import (
    read_image, validate_file_upload, resize_long_edge, 
    gamma_correct, maybe_grayworld_wb, get_image_dimensions
)
from app.services.segmentation.engines.rembg_engine import get_rembg_engine
from app.services.segmentation.engines.grabcut_engine import get_grabcut_engine
from app.services.segmentation.postprocess import (
    clean_mask, tight_bbox, cutout_rgba, calculate_mask_area_ratio,
    validate_mask_quality, encode_mask_to_png_base64, encode_rgba_to_png_base64
)
from app.utils.logging import get_logger
from app.utils.metrics import get_metrics
from app.utils.ids import generate_request_id


async def run_segmentation(
    file: UploadFile,
    max_edge: int = 768,
    gamma: float = 1.2,
    engine: str = "auto",
    morph_kernel: int = 3,
    median_blur: int = 5
) -> Dict[str, Any]:
    """
    Main segmentation pipeline that orchestrates the entire workflow.
    
    Args:
        file: Uploaded image file
        max_edge: Maximum edge size for resizing
        gamma: Gamma correction value
        engine: Segmentation engine ("auto", "u2netp", "grabcut")
        morph_kernel: Morphological kernel size
        median_blur: Median blur kernel size
        
    Returns:
        Dictionary matching SegmentResponse schema
        
    Raises:
        HTTPException: For various error conditions
    """
    request_id = generate_request_id()
    logger = get_logger()
    metrics = get_metrics()
    
    start_time = time.time()
    
    # Validate parameters
    if not config.validate_max_edge(max_edge):
        raise HTTPException(status_code=400, detail="Invalid max_edge value")
    if not config.validate_gamma(gamma):
        raise HTTPException(status_code=400, detail="Invalid gamma value")
    if not config.validate_engine(engine):
        raise HTTPException(status_code=400, detail="Invalid engine value")
    if not config.validate_kernel_size(morph_kernel):
        raise HTTPException(status_code=400, detail="Invalid morph_kernel value")
    if not config.validate_blur_size(median_blur):
        raise HTTPException(status_code=400, detail="Invalid median_blur value")
    
    metrics.increment_request_count()
    
    try:
        # Step 1: File validation and image reading
        logger.info(f"Starting segmentation pipeline", extra={"request_id": request_id})
        
        validate_file_upload(file)
        decode_start = time.time()
        image_bgr = await read_image(file)
        decode_time = int((time.time() - decode_start) * 1000)
        
        # Step 2: Image preprocessing
        image_bgr = resize_long_edge(image_bgr, max_edge)
        image_bgr = gamma_correct(image_bgr, gamma)
        
        if config.ENABLE_GRAYWORLD_WB:
            image_bgr = maybe_grayworld_wb(image_bgr)
        
        width, height = get_image_dimensions(image_bgr)
        
        # Step 3: Segmentation
        segment_start = time.time()
        engine_used, fallback_used, mask = await _perform_segmentation(
            image_bgr, engine, request_id
        )
        segment_time = int((time.time() - segment_start) * 1000)
        
        metrics.increment_engine_count(engine_used)
        if fallback_used:
            metrics.increment_fallback_count()
        
        # Step 4: Post-processing
        postproc_start = time.time()
        cleaned_mask = clean_mask(mask, morph_kernel, median_blur)
        
        # Calculate mask quality
        mask_area_ratio = calculate_mask_area_ratio(cleaned_mask)
        
        # Validate mask quality
        if not validate_mask_quality(cleaned_mask, config.MIN_MASK_AREA_RATIO, config.MAX_MASK_AREA_RATIO):
            error_msg = f"Segmentation failed: mask unusable (ratio: {mask_area_ratio:.3f}). Try simpler background, better lighting."
            logger.warning(error_msg, extra={
                "request_id": request_id,
                "mask_area_ratio": mask_area_ratio
            })
            metrics.increment_failure_count("mask_quality")
            raise HTTPException(status_code=422, detail=error_msg)
        
        # Calculate bounding box
        try:
            bbox_x, bbox_y, bbox_w, bbox_h = tight_bbox(cleaned_mask)
            bbox_xywh = [bbox_x, bbox_y, bbox_w, bbox_h]
        except ValueError as e:
            logger.error(f"Bounding box calculation failed: {str(e)}", extra={"request_id": request_id})
            metrics.increment_failure_count("bbox_calculation")
            raise HTTPException(status_code=422, detail="Failed to calculate bounding box")
        
        # Create RGBA cutout
        rgba_cutout = cutout_rgba(image_bgr, cleaned_mask)
        
        postproc_time = int((time.time() - postproc_start) * 1000)
        
        # Step 5: Encode artifacts
        try:
            mask_png_b64 = encode_mask_to_png_base64(cleaned_mask)
            item_rgba_png_b64 = encode_rgba_to_png_base64(rgba_cutout)
        except Exception as e:
            logger.error(f"Encoding failed: {str(e)}", extra={"request_id": request_id})
            metrics.increment_failure_count("encoding")
            raise HTTPException(status_code=500, detail="Failed to encode output artifacts")
        
        total_time = int((time.time() - start_time) * 1000)
        
        # Step 6: Build response
        response = {
            "engine": engine_used,
            "width": width,
            "height": height,
            "mask_area_ratio": mask_area_ratio,
            "fallback_used": fallback_used,
            "artifacts": {
                "mask_png_b64": mask_png_b64,
                "item_rgba_png_b64": item_rgba_png_b64,
                "bbox_xywh": bbox_xywh
            },
            "debug": {
                "pre_gamma": gamma,
                "morph_kernel": morph_kernel,
                "post_blur": median_blur
            }
        }
        
        # Log success
        logger.info("Segmentation completed successfully", extra={
            "request_id": request_id,
            "engine": engine_used,
            "fallback_used": fallback_used,
            "dims": f"{width}x{height}",
            "mask_area_ratio": mask_area_ratio,
            "bbox": bbox_xywh,
            "ms_decode": decode_time,
            "ms_segment": segment_time,
            "ms_postproc": postproc_time,
            "ms_total": total_time,
            "result": "ok"
        })
        
        metrics.record_timing("total", total_time)
        metrics.record_timing("segment", segment_time)
        metrics.record_timing("postproc", postproc_time)
        metrics.record_mask_ratio(mask_area_ratio)
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log and convert unexpected errors to 500
        total_time = int((time.time() - start_time) * 1000)
        logger.error(f"Unexpected error in segmentation pipeline: {str(e)}", extra={
            "request_id": request_id,
            "ms_total": total_time,
            "result": "error",
            "error_type": "unexpected"
        })
        metrics.increment_failure_count("unexpected")
        raise HTTPException(status_code=500, detail="Internal segmentation error")


async def _perform_segmentation(
    image_bgr: np.ndarray, 
    engine: str, 
    request_id: str
) -> tuple[str, bool, np.ndarray]:
    """
    Perform segmentation with fallback logic.
    
    Args:
        image_bgr: Input image in BGR format
        engine: Requested engine
        request_id: Request ID for logging
        
    Returns:
        Tuple of (engine_used, fallback_used, mask)
    """
    logger = get_logger()
    
    # Convert BGR to RGB for rembg
    if cv2 is None:
        raise RuntimeError("OpenCV not available")
    
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    
    # Force GrabCut if configured
    if config.SEGMENT_FORCE_GRABCUT or engine == "grabcut":
        logger.info("Using GrabCut engine (forced or requested)", extra={"request_id": request_id})
        grabcut_engine = get_grabcut_engine()
        mask = grabcut_engine.segment(image_bgr)
        return "grabcut", False, mask
    
    # Try rembg first (for "auto" or "u2netp")
    fallback_used = False
    try:
        logger.info("Attempting rembg segmentation", extra={"request_id": request_id})
        rembg_engine = get_rembg_engine()
        mask = rembg_engine.segment(image_rgb)
        
        # Check if mask is too small (triggers fallback)
        mask_ratio = calculate_mask_area_ratio(mask)
        if mask_ratio < config.MIN_MASK_AREA_RATIO:
            logger.warning(f"rembg mask too small (ratio: {mask_ratio:.3f}), falling back to GrabCut", 
                         extra={"request_id": request_id})
            raise RuntimeError("Mask too small")
        
        logger.info(f"rembg segmentation successful (ratio: {mask_ratio:.3f})", 
                   extra={"request_id": request_id})
        return "u2netp", False, mask
        
    except Exception as e:
        logger.warning(f"rembg failed: {str(e)}, falling back to GrabCut", 
                      extra={"request_id": request_id})
        fallback_used = True
        
        try:
            grabcut_engine = get_grabcut_engine()
            mask = grabcut_engine.segment(image_bgr)
            
            # Double-check fallback mask quality
            mask_ratio = calculate_mask_area_ratio(mask)
            logger.info(f"GrabCut fallback successful (ratio: {mask_ratio:.3f})", 
                       extra={"request_id": request_id})
            
            return "grabcut", True, mask
            
        except Exception as fallback_error:
            logger.error(f"Both rembg and GrabCut failed: {str(fallback_error)}", 
                        extra={"request_id": request_id})
            raise RuntimeError("All segmentation engines failed")
