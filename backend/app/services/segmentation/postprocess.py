"""
StyleSync Post-Processing
Mask cleaning, bounding box calculation, and RGBA cutout generation.
"""
import numpy as np
from typing import Tuple

try:
    import cv2
except ImportError:
    cv2 = None


def clean_mask(
    mask: np.ndarray, 
    kernel: int = 3, 
    blur: int = 5
) -> np.ndarray:
    """
    Clean binary mask using morphological operations and hole filling.
    
    Args:
        mask: Binary mask (0/255)
        kernel: Morphological kernel size (odd number)
        blur: Median blur kernel size (odd number, 0 to disable)
        
    Returns:
        Cleaned binary mask
    """
    if cv2 is None:
        raise RuntimeError("OpenCV not available")
    
    # Ensure mask is binary
    cleaned = np.where(mask > 127, 255, 0).astype("uint8")
    
    # Step 1: Morphological closing to seal small gaps
    if kernel > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel, kernel))
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, k, iterations=1)
    
    # Step 2: Median blur to smooth ragged edges
    if blur > 1:
        cleaned = cv2.medianBlur(cleaned, blur)
    
    # Step 3: Hole filling using flood fill
    cleaned = fill_holes(cleaned)
    
    return cleaned


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """
    Fill interior holes in binary mask.
    
    Args:
        mask: Binary mask (0/255)
        
    Returns:
        Mask with filled holes
    """
    if cv2 is None:
        raise RuntimeError("OpenCV not available")
    
    height, width = mask.shape
    
    # Create a copy for flood fill
    flood_fill = mask.copy()
    
    # Create flood fill mask (needs to be 2 pixels larger)
    ff_mask = np.zeros((height + 2, width + 2), np.uint8)
    
    # Flood fill from (0,0) - fills background
    cv2.floodFill(flood_fill, ff_mask, (0, 0), 255)
    
    # Invert flood filled image
    flood_fill_inv = cv2.bitwise_not(flood_fill)
    
    # Combine original mask with inverted flood fill to get holes
    holes = cv2.bitwise_and(flood_fill_inv, cv2.bitwise_not(mask))
    
    # Fill holes by adding them to original mask
    filled = cv2.bitwise_or(mask, holes)
    
    return filled


def tight_bbox(mask: np.ndarray) -> Tuple[int, int, int, int]:
    """
    Calculate tight bounding box around non-zero mask pixels.
    
    Args:
        mask: Binary mask
        
    Returns:
        Bounding box as (x, y, width, height)
        
    Raises:
        ValueError: If mask is empty
    """
    # Find all non-zero pixel coordinates
    nonzero_coords = np.where(mask > 0)
    
    if len(nonzero_coords[0]) == 0:
        raise ValueError("Mask is empty - cannot compute bounding box")
    
    # Get min/max coordinates
    y_coords, x_coords = nonzero_coords
    y_min, y_max = int(y_coords.min()), int(y_coords.max())
    x_min, x_max = int(x_coords.min()), int(x_coords.max())
    
    # Calculate width and height
    width = x_max - x_min + 1
    height = y_max - y_min + 1
    
    return x_min, y_min, width, height


def cutout_rgba(image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Create RGBA cutout with transparent background.
    
    Args:
        image_bgr: Original image in BGR format
        mask: Binary mask (0/255)
        
    Returns:
        RGBA image with transparent background
    """
    if cv2 is None:
        raise RuntimeError("OpenCV not available")
    
    # Convert BGR to RGB
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    
    # Ensure mask matches image dimensions
    if image_rgb.shape[:2] != mask.shape[:2]:
        raise ValueError("Image and mask dimensions must match")
    
    # Create RGBA by adding mask as alpha channel
    rgba = np.dstack([image_rgb, mask])
    
    return rgba


def calculate_mask_area_ratio(mask: np.ndarray) -> float:
    """
    Calculate the ratio of mask area to total image area.
    
    Args:
        mask: Binary mask
        
    Returns:
        Ratio between 0.0 and 1.0
    """
    total_pixels = mask.shape[0] * mask.shape[1]
    mask_pixels = np.count_nonzero(mask > 0)
    return mask_pixels / total_pixels if total_pixels > 0 else 0.0


def validate_mask_quality(mask: np.ndarray, min_ratio: float = 0.03, max_ratio: float = 0.98) -> bool:
    """
    Validate mask quality based on area ratio.
    
    Args:
        mask: Binary mask
        min_ratio: Minimum acceptable area ratio
        max_ratio: Maximum acceptable area ratio
        
    Returns:
        True if mask quality is acceptable
    """
    ratio = calculate_mask_area_ratio(mask)
    return min_ratio <= ratio <= max_ratio


def encode_mask_to_png_base64(mask: np.ndarray) -> str:
    """
    Encode binary mask to base64 PNG string.
    
    Args:
        mask: Binary mask (0/255)
        
    Returns:
        Base64 encoded PNG string
    """
    import base64
    
    if cv2 is None:
        raise RuntimeError("OpenCV not available")
    
    # Encode mask as PNG
    success, buffer = cv2.imencode('.png', mask)
    if not success:
        raise RuntimeError("Failed to encode mask as PNG")
    
    # Convert to base64
    png_base64 = base64.b64encode(buffer).decode('utf-8')
    
    return png_base64


def encode_rgba_to_png_base64(rgba: np.ndarray) -> str:
    """
    Encode RGBA image to base64 PNG string.
    
    Args:
        rgba: RGBA image
        
    Returns:
        Base64 encoded PNG string
    """
    import base64
    
    if cv2 is None:
        raise RuntimeError("OpenCV not available")
    
    # Convert RGBA to BGRA for OpenCV
    bgra = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
    
    # Encode as PNG
    success, buffer = cv2.imencode('.png', bgra)
    if not success:
        raise RuntimeError("Failed to encode RGBA as PNG")
    
    # Convert to base64
    png_base64 = base64.b64encode(buffer).decode('utf-8')
    
    return png_base64
