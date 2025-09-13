"""
Base Color Selection Module

Provides scoring and selection logic for choosing the most representative
base color from a palette. Includes neutral penalties and spatial cohesion analysis.
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
from loguru import logger


def neutral_multiplier(c_rgb_u8: np.ndarray, 
                      v_low: float = 0.15, 
                      v_high: float = 0.95, 
                      s_low: float = 0.12, 
                      penalty_weight: float = 0.5) -> float:
    """
    Calculate neutral penalty multiplier for a color.
    
    A color is considered neutral if:
    - V < v_low (near black)
    - V > v_high (near white)  
    - S < s_low AND 0.2 < V < 0.9 (grayish)
    
    Args:
        c_rgb_u8: RGB color as uint8 array [R, G, B]
        v_low: Value threshold for near-black colors
        v_high: Value threshold for near-white colors
        s_low: Saturation threshold for gray colors
        penalty_weight: Multiplier applied to neutral colors (< 1.0 penalizes)
        
    Returns:
        Penalty multiplier (1.0 for non-neutral, penalty_weight for neutral)
    """
    # Convert single RGB pixel to HSV
    rgb_pixel = np.uint8([[c_rgb_u8]])  # Shape (1, 1, 3)
    hsv_pixel = cv2.cvtColor(rgb_pixel, cv2.COLOR_RGB2HSV)[0, 0].astype(np.float32)
    
    # Normalize HSV values
    h = hsv_pixel[0]  # Hue [0, 179] in OpenCV
    s = hsv_pixel[1] / 255.0  # Saturation [0, 1]
    v = hsv_pixel[2] / 255.0  # Value [0, 1]
    
    # Check neutral conditions
    is_near_black = v < v_low
    is_near_white = (v > v_high) and (s < s_low)  # Only low-saturation high-value is "white"
    is_grayish = (s < s_low) and (0.2 < v < 0.9)
    
    is_neutral = is_near_black or is_near_white or is_grayish
    
    multiplier = penalty_weight if is_neutral else 1.0
    
    logger.debug(f"Color {c_rgb_u8} HSV=({h:.1f}, {s:.3f}, {v:.3f}) "
                f"neutral={is_neutral} multiplier={multiplier:.3f}")
    
    return multiplier


def spatial_cohesion_bonus(item_rgb: np.ndarray, 
                          mask_u8: np.ndarray,
                          centers_rgb_u8: List[np.ndarray], 
                          weight: float = 0.10) -> List[float]:
    """
    Calculate spatial cohesion bonus for each cluster based on largest connected component.
    
    Assigns each garment pixel to the nearest cluster center, then finds the largest
    connected component for each cluster and calculates its fraction of total garment pixels.
    
    Args:
        item_rgb: RGB image (H, W, 3)
        mask_u8: Binary mask indicating garment pixels
        centers_rgb_u8: List of cluster centers as RGB uint8 arrays
        weight: Weight for cohesion bonus in final scoring
        
    Returns:
        List of cohesion bonuses for each cluster
    """
    logger.debug(f"Computing spatial cohesion for {len(centers_rgb_u8)} clusters")
    
    # Find garment pixel coordinates
    ys, xs = np.where(mask_u8 > 0)
    total_garment_pixels = len(ys)
    
    if total_garment_pixels == 0:
        return [0.0] * len(centers_rgb_u8)
    
    # Extract garment pixel colors
    garment_colors = item_rgb[ys, xs, :]  # Shape (N, 3)
    
    # Convert centers to numpy array for efficient distance computation
    centers_array = np.stack(centers_rgb_u8).astype(np.float32)  # Shape (k, 3)
    garment_colors_f = garment_colors.astype(np.float32)  # Shape (N, 3)
    
    # Compute distances from each pixel to each center (Euclidean in RGB space)
    # Broadcasting: (N, 1, 3) - (1, k, 3) -> (N, k, 3) -> (N, k)
    distances = np.linalg.norm(
        garment_colors_f[:, None, :] - centers_array[None, :, :], 
        axis=2
    )
    
    # Assign each pixel to nearest center
    cluster_assignments = distances.argmin(axis=1)  # Shape (N,)
    
    # Calculate cohesion bonus for each cluster
    bonuses = []
    h, w = mask_u8.shape
    
    for cluster_idx in range(len(centers_rgb_u8)):
        # Create binary mask for this cluster's pixels
        cluster_mask = np.zeros((h, w), dtype=np.uint8)
        
        # Find pixels assigned to this cluster
        cluster_pixel_indices = np.where(cluster_assignments == cluster_idx)[0]
        
        if len(cluster_pixel_indices) == 0:
            bonuses.append(0.0)
            continue
        
        # Set cluster pixels in mask
        cluster_ys = ys[cluster_pixel_indices]
        cluster_xs = xs[cluster_pixel_indices]
        cluster_mask[cluster_ys, cluster_xs] = 255
        
        # Find connected components
        num_labels, labels = cv2.connectedComponents(cluster_mask)
        
        if num_labels <= 1:  # Only background, no components
            largest_component_size = 0
        else:
            # Find size of each component (excluding background label 0)
            component_sizes = []
            for label in range(1, num_labels):
                component_size = np.sum(labels == label)
                component_sizes.append(component_size)
            
            largest_component_size = max(component_sizes) if component_sizes else 0
        
        # Calculate cohesion as fraction of total garment pixels
        cohesion_fraction = largest_component_size / total_garment_pixels
        cohesion_bonus = weight * cohesion_fraction
        
        bonuses.append(float(cohesion_bonus))
        
        logger.debug(f"Cluster {cluster_idx}: {len(cluster_pixel_indices)} pixels, "
                    f"largest component: {largest_component_size}, "
                    f"cohesion: {cohesion_fraction:.3f}, bonus: {cohesion_bonus:.3f}")
    
    return bonuses


def choose_base_color(ordered_centers: List[np.ndarray], 
                     ordered_ratios: List[float],
                     item_bgr: np.ndarray, 
                     mask_u8: np.ndarray,
                     neutral_params: Dict, 
                     cohesion_params: Dict) -> Tuple[int, Dict]:
    """
    Choose the best base color from ordered palette using scoring algorithm.
    
    Scoring formula: final_score = dominance × neutral_multiplier + cohesion_bonus
    
    Args:
        ordered_centers: Cluster centers ordered by dominance (RGB uint8)
        ordered_ratios: Dominance ratios corresponding to centers
        item_bgr: Original image in BGR format
        mask_u8: Binary garment mask
        neutral_params: Dict with neutral penalty parameters
        cohesion_params: Dict with spatial cohesion parameters
        
    Returns:
        Tuple of (best_cluster_index, score_breakdown_dict)
    """
    logger.info(f"Choosing base color from {len(ordered_centers)} candidates")
    
    # Extract parameters
    neutral_config = {
        'v_low': neutral_params.get('v_low', 0.15),
        'v_high': neutral_params.get('v_high', 0.95),
        's_low': neutral_params.get('s_low', 0.12),
        'penalty_weight': neutral_params.get('penalty_weight', 0.5)
    }
    
    cohesion_enabled = cohesion_params.get('enabled', True)
    cohesion_weight = cohesion_params.get('weight', 0.10)
    
    # Calculate neutral penalty multipliers for each cluster
    neutral_multipliers = []
    for center in ordered_centers:
        multiplier = neutral_multiplier(
            center, 
            v_low=neutral_config['v_low'],
            v_high=neutral_config['v_high'],
            s_low=neutral_config['s_low'],
            penalty_weight=neutral_config['penalty_weight']
        )
        neutral_multipliers.append(multiplier)
    
    # Calculate spatial cohesion bonuses if enabled
    if cohesion_enabled:
        item_rgb = cv2.cvtColor(item_bgr, cv2.COLOR_BGR2RGB)
        cohesion_bonuses = spatial_cohesion_bonus(
            item_rgb, mask_u8, ordered_centers, weight=cohesion_weight
        )
    else:
        cohesion_bonuses = [0.0] * len(ordered_centers)
    
    # Calculate final scores
    scores = []
    score_details = []
    
    for i, (dominance, neutral_mult, cohesion_bonus) in enumerate(
        zip(ordered_ratios, neutral_multipliers, cohesion_bonuses)
    ):
        final_score = dominance * neutral_mult + cohesion_bonus
        scores.append(final_score)
        
        score_details.append({
            'dominance': dominance,
            'neutral_penalty': neutral_mult,
            'cohesion_bonus': cohesion_bonus,
            'final_score': final_score
        })
        
        logger.debug(f"Cluster {i}: dom={dominance:.3f}, neutral={neutral_mult:.3f}, "
                    f"cohesion={cohesion_bonus:.3f}, final={final_score:.3f}")
    
    # Choose cluster with highest score
    # In case of exact ties, prefer earlier in dominance order (lower index)
    best_index = int(np.argmax(scores))
    
    # Handle exact ties deterministically by preferring lower index
    max_score = scores[best_index]
    for i, score in enumerate(scores):
        if abs(score - max_score) < 1e-10 and i < best_index:
            best_index = i
            break
    
    best_breakdown = score_details[best_index]
    
    logger.info(f"Selected cluster {best_index} with score {best_breakdown['final_score']:.3f}")
    
    return best_index, best_breakdown


def calculate_color_distance(color1_rgb: np.ndarray, color2_rgb: np.ndarray) -> float:
    """Calculate Euclidean distance between two RGB colors."""
    return float(np.linalg.norm(color1_rgb.astype(np.float32) - color2_rgb.astype(np.float32)))


def validate_base_color_selection(palette: List[Dict], base_color_info: Dict) -> None:
    """Validate that base color selection is consistent with palette."""
    if not palette:
        raise ValueError("Empty palette provided")
    
    base_index = base_color_info.get('cluster_index')
    if base_index is None or base_index < 0 or base_index >= len(palette):
        raise ValueError(f"Invalid base color index: {base_index}")
    
    expected_hex = palette[base_index]['hex']
    actual_hex = base_color_info['hex']
    
    if expected_hex != actual_hex:
        raise ValueError(f"Base color hex mismatch: expected {expected_hex}, got {actual_hex}")


def analyze_color_harmony(palette: List[Dict]) -> Dict:
    """
    Analyze color harmony metrics for the palette.
    
    Returns basic color analysis that could be useful for Phase 3 matching.
    """
    if len(palette) < 2:
        return {
            "harmony_type": "monochromatic", 
            "diversity_score": 0.0,
            "color_relationships": [],
            "temperature_balance": "neutral"
        }
    
    # Convert hex colors to RGB for analysis
    rgb_colors = []
    for color_entry in palette:
        hex_color = color_entry['hex']
        rgb = np.array([int(hex_color[i:i+2], 16) for i in (1, 3, 5)])
        rgb_colors.append(rgb)
    
    # Calculate pairwise distances
    distances = []
    color_relationships = []
    for i in range(len(rgb_colors)):
        for j in range(i + 1, len(rgb_colors)):
            dist = calculate_color_distance(rgb_colors[i], rgb_colors[j])
            distances.append(dist)
            color_relationships.append({
                "color1": palette[i]['hex'],
                "color2": palette[j]['hex'],
                "distance": float(dist)
            })
    
    diversity_score = np.mean(distances) / 255.0 if distances else 0.0
    
    # Simple harmony classification based on diversity
    if diversity_score < 0.1:
        harmony_type = "monochromatic"
    elif diversity_score < 0.3:
        harmony_type = "analogous"
    elif diversity_score < 0.6:
        harmony_type = "complementary"
    else:
        harmony_type = "triadic"
    
    # Analyze temperature balance (simplified)
    warm_count = 0
    cool_count = 0
    for rgb in rgb_colors:
        # Simple warm/cool classification based on dominant channel
        if rgb[0] > max(rgb[1], rgb[2]):  # Red dominant
            warm_count += 1
        elif rgb[2] > max(rgb[0], rgb[1]):  # Blue dominant
            cool_count += 1
        elif rgb[1] > max(rgb[0], rgb[2]):  # Green dominant (can be either)
            if rgb[0] > rgb[2]:  # More red than blue
                warm_count += 1
            else:
                cool_count += 1
    
    if warm_count > cool_count:
        temperature_balance = "warm"
    elif cool_count > warm_count:
        temperature_balance = "cool"
    else:
        temperature_balance = "balanced"
    
    return {
        "harmony_type": harmony_type,
        "diversity_score": float(diversity_score),
        "mean_distance": float(np.mean(distances)) if distances else 0.0,
        "max_distance": float(np.max(distances)) if distances else 0.0,
        "color_relationships": color_relationships,
        "temperature_balance": temperature_balance
    }
