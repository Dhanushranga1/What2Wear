"""
Color extraction service for garment items.

This module implements the core color extraction pipeline for What2Wear,
including clustering, filtering, and base color selection.
"""

import time
import base64
from collections import Counter
import cv2
import numpy as np
from io import BytesIO
from PIL import Image
from sklearn.cluster import MiniBatchKMeans
from typing import List, Dict, Any, Tuple, Optional
from loguru import logger

from .utils import rgb_to_hex, calculate_color_distance
from .base_selection import choose_base_color, analyze_color_harmony
from ..observability import (
    performance_monitor, 
    performance_tracked,
    get_extraction_logger,
    log_memory_usage,
    force_garbage_collection
)


def rgb_to_hex(rgb_u8: np.ndarray) -> str:
    """Convert RGB uint8 array to hex color string."""
    r, g, b = [int(x) for x in rgb_u8]
    return f"#{r:02X}{g:02X}{b:02X}"


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def apply_gamma_correction(image_bgr: np.ndarray, gamma: float = 1.2) -> np.ndarray:
    """Apply gamma correction using lookup table for efficiency."""
    lut = np.array([((i/255.0)**(1.0/gamma))*255 for i in range(256)], dtype=np.uint8)
    return cv2.LUT(image_bgr, lut)


def sample_garment_pixels(item_bgr: np.ndarray, mask_u8: np.ndarray, 
                         erode_px: int = 1, gamma: float = 1.2, 
                         max_samples: int = 20000,
                         shadow_v_lt: float = 0.12, 
                         spec_s_lt: float = 0.10, 
                         spec_v_gt: float = 0.95,
                         min_saturation: float = 0.0, 
                         rng_seed: int = 42) -> np.ndarray:
    """
    Sample and filter garment pixels for color analysis.
    
    Args:
        item_bgr: Input image in BGR format
        mask_u8: Binary mask (0/255) indicating garment pixels
        erode_px: Pixels to erode mask for sampling (avoid edge bleeding)
        gamma: Gamma correction factor for lighting normalization
        max_samples: Maximum number of pixels to sample
        shadow_v_lt: HSV V threshold below which pixels are considered shadows
        spec_s_lt: HSV S threshold below which high-V pixels are specular
        spec_v_gt: HSV V threshold above which low-S pixels are specular
        min_saturation: Minimum saturation threshold (0.0 disables)
        rng_seed: Random seed for deterministic sampling
        
    Returns:
        Filtered RGB pixels array (N, 3) uint8
        
    Raises:
        ValueError: If no garment pixels remain after erosion
        RuntimeError: If insufficient pixels remain after filtering
    """
    logger.info(f"Starting pixel sampling with erode_px={erode_px}, gamma={gamma}")
    
    # 1) Erode mask for sampling to avoid edge artifacts
    if erode_px > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (erode_px*2+1, erode_px*2+1))
        mask_eroded = cv2.erode(mask_u8, kernel, iterations=1)
        logger.debug(f"Eroded mask from {np.sum(mask_u8 > 0)} to {np.sum(mask_eroded > 0)} pixels")
    else:
        mask_eroded = mask_u8
    
    # 2) Apply gamma correction for lighting stability
    bgr_corrected = apply_gamma_correction(item_bgr, gamma)
    rgb = cv2.cvtColor(bgr_corrected, cv2.COLOR_BGR2RGB)
    
    # 3) Extract garment pixels
    garment_pixels = rgb[mask_eroded > 0]
    if garment_pixels.size == 0:
        raise ValueError("Empty garment after mask erosion")
    
    initial_count = garment_pixels.shape[0]
    logger.info(f"Extracted {initial_count} garment pixels")
    
    # 4) Downsample if needed (deterministic)
    if initial_count > max_samples:
        rng = np.random.default_rng(rng_seed)
        indices = rng.choice(initial_count, size=max_samples, replace=False)
        garment_pixels = garment_pixels[indices]
        logger.info(f"Downsampled to {max_samples} pixels")
    
    # 5) Apply HSV-based filtering
    # Convert to HSV for filtering
    hsv = cv2.cvtColor(garment_pixels.reshape(-1, 1, 3), cv2.COLOR_RGB2HSV).reshape(-1, 3).astype(np.float32)
    s_normalized = hsv[:, 1] / 255.0  # Saturation [0,1]
    v_normalized = hsv[:, 2] / 255.0  # Value [0,1]
    
    # Start with all pixels
    keep_mask = np.ones(len(garment_pixels), dtype=bool)
    
    # Filter shadows (low value)
    shadow_mask = v_normalized >= shadow_v_lt
    keep_mask &= shadow_mask
    logger.debug(f"Shadow filter: kept {np.sum(shadow_mask)}/{len(shadow_mask)} pixels")
    
    # Filter specular highlights (low saturation + high value)
    specular_mask = ~((s_normalized < spec_s_lt) & (v_normalized > spec_v_gt))
    keep_mask &= specular_mask
    logger.debug(f"Specular filter: kept {np.sum(specular_mask)}/{len(specular_mask)} pixels")
    
    # Optional minimum saturation filter
    if min_saturation > 0.0:
        sat_mask = s_normalized >= min_saturation
        keep_mask &= sat_mask
        logger.debug(f"Min saturation filter: kept {np.sum(sat_mask)}/{len(sat_mask)} pixels")
    
    # Apply combined filter
    filtered_pixels = garment_pixels[keep_mask]
    final_count = filtered_pixels.shape[0]
    
    logger.info(f"Filtering: {initial_count} → {final_count} pixels")
    
    # 6) Validate sufficient data for clustering  
    # Use reasonable minimum for stable clustering
    min_required = max(200, final_count // 20)  # At least 200 pixels or 5% of samples
    if final_count < 50:  # Absolute minimum
        raise RuntimeError(
            f"Insufficient garment pixels after filtering: {final_count} < {min_required}. "
            "Try better lighting or relax filter parameters."
        )
    
    return filtered_pixels


def cluster_palette(pixels_rgb_u8: np.ndarray, k: int = 5, rng_seed: int = 42) -> Tuple[List[Dict], List[np.ndarray], List[float], List[int]]:
    """
    Cluster pixels into color palette using MiniBatchKMeans.
    
    Args:
        pixels_rgb_u8: Filtered RGB pixels (N, 3) uint8
        k: Number of clusters
        rng_seed: Random seed for deterministic clustering
        
    Returns:
        Tuple of:
        - palette: List of {"hex": str, "ratio": float} entries
        - ordered_centers: List of RGB cluster centers (uint8)
        - ordered_ratios: List of dominance ratios
        - ordered_indices: List of original cluster indices
        
    Raises:
        RuntimeError: If clustering fails or insufficient unique colors
    """
    logger.info(f"Starting clustering with k={k}, {len(pixels_rgb_u8)} pixels")
    
    # Check for sufficient unique colors
    unique_colors = np.unique(pixels_rgb_u8.view(np.void), return_counts=True)
    n_unique = len(unique_colors[0])
    if n_unique < k:
        raise RuntimeError(f"Insufficient unique colors: {n_unique} < {k}")
    
    try:
        # Use MiniBatchKMeans for efficiency and stability
        kmeans = MiniBatchKMeans(
            n_clusters=k, 
            random_state=rng_seed, 
            batch_size=min(2048, len(pixels_rgb_u8)),
            n_init="auto",
            max_iter=100
        )
        
        # Fit and predict
        labels = kmeans.fit_predict(pixels_rgb_u8.astype(np.float32))
        centers = np.clip(kmeans.cluster_centers_, 0, 255).astype(np.uint8)
        
        # Calculate cluster statistics
        label_counts = Counter(labels)
        total_pixels = len(labels)
        
        # Sort clusters by dominance (descending)
        cluster_stats = []
        for i in range(k):
            count = label_counts.get(i, 0)
            ratio = count / total_pixels
            cluster_stats.append((ratio, centers[i], i))
        
        # Sort by dominance descending
        cluster_stats.sort(key=lambda x: -x[0])
        
        # Extract ordered results
        ordered_ratios = [stat[0] for stat in cluster_stats]
        ordered_centers = [stat[1] for stat in cluster_stats]
        ordered_indices = [stat[2] for stat in cluster_stats]
        
        # Build palette entries
        palette = []
        for ratio, center, _ in cluster_stats:
            palette.append({
                "hex": rgb_to_hex(center),
                "ratio": float(ratio)
            })
        
        ratios_str = [f"{p['ratio']:.3f}" for p in palette]
        logger.info(f"Clustering successful: {ratios_str}")
        
        return palette, ordered_centers, ordered_ratios, ordered_indices
        
    except Exception as e:
        logger.error(f"Clustering failed: {str(e)}")
        raise RuntimeError(f"K-means clustering failed: {str(e)}")


def decode_base64_image(b64_data: str) -> np.ndarray:
    """Decode base64 image data to numpy array."""
    try:
        # Remove data URL prefix if present
        if ',' in b64_data:
            b64_data = b64_data.split(',')[1]
        
        # Decode base64
        img_bytes = base64.b64decode(b64_data)
        
        # Convert to numpy array and decode
        nparr = np.frombuffer(img_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
        
        if image is None:
            raise ValueError("Failed to decode image data")
        
        return image
        
    except Exception as e:
        raise ValueError(f"Invalid base64 image data: {str(e)}")


def validate_mask_binary(mask: np.ndarray) -> np.ndarray:
    """Ensure mask is strictly binary (0/255)."""
    if len(mask.shape) == 3:
        # Convert to grayscale if needed
        mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
    
    # Ensure binary values
    mask = np.where(mask > 127, 255, 0).astype(np.uint8)
    return mask


def validate_dimensions_match(image: np.ndarray, mask: np.ndarray) -> None:
    """Validate that image and mask have compatible dimensions."""
    img_h, img_w = image.shape[:2]
    mask_h, mask_w = mask.shape[:2]
    
    if img_h != mask_h or img_w != mask_w:
        raise ValueError(
            f"Image and mask dimension mismatch: "
            f"image={img_w}×{img_h}, mask={mask_w}×{mask_h}"
        )


def process_rgba_to_rgb_and_mask(rgba_image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract RGB image and alpha mask from RGBA image.
    
    Returns:
        Tuple of (rgb_bgr, alpha_mask) where alpha_mask is binary 0/255
    """
    if rgba_image.shape[2] != 4:
        raise ValueError("Expected RGBA image with 4 channels")
    
    # Extract RGB and alpha
    bgr = rgba_image[:, :, :3]  # Keep BGR order
    alpha = rgba_image[:, :, 3]
    
    # Convert alpha to binary mask
    alpha_mask = np.where(alpha > 127, 255, 0).astype(np.uint8)
    
    return bgr, alpha_mask


def extract_colors_from_image(
    image_data: str,
    mask_data: str, 
    n_clusters: int = 5,
    erosion_iterations: int = 2,
    max_samples: int = 10000,
    shadow_threshold: float = 0.3,
    neutral_penalty_weight: float = 0.5,
    cohesion_enabled: bool = True,
    cohesion_weight: float = 0.10
) -> Dict[str, Any]:
    """
    Extract dominant colors from a garment image with comprehensive observability.
    
    This is the main entry point for color extraction with full performance monitoring,
    logging, and metrics collection for the StyleSync ColorMatch MVP.
    """
    logger.info("Starting color extraction with observability")
    
    # Initialize extraction logging
    extraction_logger = get_extraction_logger()
    
    # Decode and validate inputs
    with performance_monitor("image_decoding"):
        img_bgr = decode_base64_image(image_data)
        mask_u8 = decode_base64_image(mask_data)
        
        if img_bgr is None or mask_u8 is None:
            raise ValueError("Failed to decode image or mask data")
        
        # Validate mask as binary
        mask_u8 = validate_mask_binary(mask_u8)
        log_memory_usage("image_decode_complete")
    
    # Start extraction tracking
    extraction_id = extraction_logger.start_extraction(
        image_size=img_bgr.shape[:2],
        mask_pixel_count=int(np.sum(mask_u8 > 0))
    )
    
    try:
        # Stage 1: Sample garment pixels with performance tracking
        with performance_monitor("pixel_sampling", pixel_count=np.sum(mask_u8 > 0)):
            start_time = time.time()
            pixels_rgb = sample_garment_pixels(
                img_bgr, mask_u8, 
                erode_px=erosion_iterations,
                max_samples=max_samples,
                shadow_v_lt=shadow_threshold
            )
            sampling_duration = (time.time() - start_time) * 1000
            
            if len(pixels_rgb) < 200:
                extraction_logger.log_warning(f"Low pixel count after sampling: {len(pixels_rgb)}")
            
            extraction_logger.log_stage("sampling", sampling_duration, 
                                      pixel_count=len(pixels_rgb),
                                      erosion_iterations=erosion_iterations,
                                      shadow_filtered=shadow_threshold > 0)
            
            log_memory_usage("pixel_sampling_complete")
        
        # Stage 2: Cluster colors with performance tracking  
        with performance_monitor("color_clustering", pixel_count=len(pixels_rgb), cluster_count=n_clusters):
            start_time = time.time()
            centers_rgb_u8, labels = cluster_palette(pixels_rgb, n_clusters=n_clusters)
            clustering_duration = (time.time() - start_time) * 1000
            
            extraction_logger.log_stage("clustering", clustering_duration,
                                      cluster_count=len(centers_rgb_u8),
                                      algorithm="MiniBatchKMeans")
            
            log_memory_usage("clustering_complete")
            force_garbage_collection()  # Clean up after clustering
        
        # Stage 3: Calculate cluster ratios
        with performance_monitor("ratio_calculation"):
            start_time = time.time()
            cluster_counts = Counter(labels)
            total_pixels = len(labels)
            ratios = [cluster_counts[i] / total_pixels for i in range(len(centers_rgb_u8))]
            ratio_duration = (time.time() - start_time) * 1000
            
            extraction_logger.log_stage("ratio_calculation", ratio_duration)
        
        # Stage 4: Base color selection with performance tracking
        with performance_monitor("base_color_selection", cluster_count=len(centers_rgb_u8)):
            start_time = time.time()
            
            neutral_params = {
                "v_low": 0.15, "v_high": 0.95, "s_low": 0.12, 
                "penalty_weight": neutral_penalty_weight
            }
            cohesion_params = {
                "enabled": cohesion_enabled, 
                "weight": cohesion_weight
            }
            
            base_index, score_breakdown = choose_base_color(
                centers_rgb_u8, ratios, img_bgr, mask_u8,
                neutral_params, cohesion_params
            )
            
            base_selection_duration = (time.time() - start_time) * 1000
            
            # Count neutral colors for metrics
            neutral_count = sum(1 for center in centers_rgb_u8 
                              if len(center) >= 3)  # Simplified neutral count
            
            extraction_logger.log_stage("base_selection", base_selection_duration,
                                      base_index=base_index,
                                      neutral_count=neutral_count,
                                      cohesion_enabled=cohesion_enabled)
            
            log_memory_usage("base_selection_complete")
        
        # Stage 5: Palette construction with performance tracking
        with performance_monitor("palette_construction"):
            start_time = time.time()
            
            # Build color palette
            palette = []
            for i, (center, ratio) in enumerate(zip(centers_rgb_u8, ratios)):
                color_hex = rgb_to_hex(center)
                
                palette.append({
                    "hex": color_hex,
                    "rgb": center.tolist(),
                    "ratio": float(ratio),
                    "is_base": i == base_index
                })
            
            # Analyze color harmony
            harmony_metrics = analyze_color_harmony(palette)
            
            palette_duration = (time.time() - start_time) * 1000
            
            extraction_logger.log_stage("palette_construction", palette_duration,
                                      palette_size=len(palette),
                                      harmony_type=harmony_metrics.get('harmony_type', 'unknown'))
            
            log_memory_usage("palette_construction_complete")
        
        # Finish extraction logging and get comprehensive metrics
        extraction_metrics = extraction_logger.finish_extraction(
            palette_size=len(palette),
            base_color_index=base_index
        )
        
        # Final memory cleanup
        force_garbage_collection()
        
        logger.info(f"Color extraction {extraction_id} completed successfully")
        
        return {
            "palette": palette,
            "base_color": palette[base_index],
            "base_color_index": base_index,
            "harmony_analysis": harmony_metrics,
            "metadata": {
                "cluster_count": len(centers_rgb_u8),
                "total_pixels_analyzed": len(pixels_rgb),
                "mask_pixel_count": int(np.sum(mask_u8 > 0)),
                "extraction_id": extraction_id,
                "performance": {
                    "total_duration_ms": extraction_metrics.total_duration_ms,
                    "clustering_duration_ms": extraction_metrics.clustering_duration_ms,
                    "base_selection_duration_ms": extraction_metrics.base_selection_duration_ms,
                    "memory_peak_mb": extraction_metrics.memory_peak_mb
                },
                "algorithm_params": {
                    "n_clusters": n_clusters,
                    "erosion_iterations": erosion_iterations,
                    "max_samples": max_samples,
                    "shadow_threshold": shadow_threshold,
                    "neutral_penalty_weight": neutral_penalty_weight,
                    "cohesion_enabled": cohesion_enabled,
                    "cohesion_weight": cohesion_weight
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Color extraction {extraction_id} failed: {e}")
        # Record error metrics
        if 'extraction_logger' in locals():
            extraction_logger.log_warning(f"Extraction failed: {str(e)}")
        raise
