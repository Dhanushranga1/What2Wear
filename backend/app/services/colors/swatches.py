"""
Swatch Rendering Module

Provides utilities for creating visual color palette representations.
Generates color swatch strips for quick palette visualization and QA.
"""

import cv2
import numpy as np
import base64
from typing import List, Optional, Tuple
from loguru import logger


def hex_to_bgr(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color to BGR tuple for OpenCV."""
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return (b, g, r)  # BGR for OpenCV


def render_swatch_strip(hex_colors: List[str], 
                       chip_size: int = 40, 
                       highlight_index: Optional[int] = None,
                       border_color: Tuple[int, int, int] = (0, 0, 0),
                       border_width: int = 2) -> str:
    """
    Render a horizontal strip of color swatches.
    
    Args:
        hex_colors: List of hex color strings
        chip_size: Size of each color chip in pixels
        highlight_index: Index of color to highlight with border (base color)
        border_color: BGR color for highlight border
        border_width: Width of highlight border in pixels
        
    Returns:
        Base64-encoded PNG image string
    """
    if not hex_colors:
        raise ValueError("Empty hex_colors list provided")
    
    k = len(hex_colors)
    logger.debug(f"Rendering swatch strip with {k} colors, chip_size={chip_size}")
    
    # Create image: height = chip_size, width = chip_size * k
    img_height = chip_size
    img_width = chip_size * k
    img = np.zeros((img_height, img_width, 3), dtype=np.uint8)
    
    # Fill each color chip
    for i, hex_color in enumerate(hex_colors):
        try:
            bgr_color = hex_to_bgr(hex_color)
            
            # Calculate chip boundaries
            x_start = i * chip_size
            x_end = (i + 1) * chip_size
            
            # Fill the chip with solid color
            img[:, x_start:x_end, :] = bgr_color
            
            logger.debug(f"Chip {i}: {hex_color} -> BGR{bgr_color} at x={x_start}-{x_end}")
            
        except Exception as e:
            logger.warning(f"Failed to render color {hex_color}: {str(e)}")
            # Fill with gray as fallback
            img[:, x_start:x_end, :] = (128, 128, 128)
    
    # Add highlight border to base color if specified
    if highlight_index is not None and 0 <= highlight_index < k:
        x_start = highlight_index * chip_size
        x_end = (highlight_index + 1) * chip_size
        
        # Draw border rectangle
        cv2.rectangle(
            img, 
            (x_start, 0), 
            (x_end - 1, img_height - 1), 
            border_color, 
            border_width
        )
        
        logger.debug(f"Added highlight border to chip {highlight_index}")
    
    # Encode as PNG and return base64
    try:
        success, buffer = cv2.imencode('.png', img)
        if not success:
            raise RuntimeError("Failed to encode image as PNG")
        
        b64_string = base64.b64encode(buffer.tobytes()).decode('ascii')
        logger.debug(f"Encoded swatch strip: {img_width}×{img_height} -> {len(b64_string)} chars")
        
        return b64_string
        
    except Exception as e:
        logger.error(f"Failed to encode swatch strip: {str(e)}")
        raise RuntimeError(f"Swatch encoding failed: {str(e)}")


def render_palette_grid(hex_colors: List[str], 
                       ratios: List[float],
                       chip_size: int = 60,
                       cols: int = 3,
                       show_ratios: bool = True,
                       font_scale: float = 0.4) -> str:
    """
    Render a grid layout of color swatches with optional ratio labels.
    
    Args:
        hex_colors: List of hex color strings
        ratios: Corresponding dominance ratios
        chip_size: Size of each color chip
        cols: Number of columns in grid
        show_ratios: Whether to overlay ratio text
        font_scale: Font scale for ratio text
        
    Returns:
        Base64-encoded PNG image string
    """
    if not hex_colors or len(hex_colors) != len(ratios):
        raise ValueError("hex_colors and ratios must have same length")
    
    k = len(hex_colors)
    rows = (k + cols - 1) // cols  # Ceiling division
    
    logger.debug(f"Rendering palette grid: {k} colors, {rows}×{cols}, chip_size={chip_size}")
    
    # Create image
    img_height = rows * chip_size
    img_width = cols * chip_size
    img = np.zeros((img_height, img_width, 3), dtype=np.uint8)
    
    # Fill background with light gray
    img.fill(240)
    
    for i, (hex_color, ratio) in enumerate(zip(hex_colors, ratios)):
        row = i // cols
        col = i % cols
        
        # Calculate chip position
        y_start = row * chip_size
        y_end = y_start + chip_size
        x_start = col * chip_size
        x_end = x_start + chip_size
        
        try:
            bgr_color = hex_to_bgr(hex_color)
            
            # Fill chip
            img[y_start:y_end, x_start:x_end, :] = bgr_color
            
            # Add ratio text if requested
            if show_ratios:
                ratio_text = f"{ratio:.1%}"
                text_color = (255, 255, 255) if sum(bgr_color) < 384 else (0, 0, 0)
                
                # Calculate text position (centered)
                text_size = cv2.getTextSize(ratio_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)[0]
                text_x = x_start + (chip_size - text_size[0]) // 2
                text_y = y_start + (chip_size + text_size[1]) // 2
                
                cv2.putText(
                    img, ratio_text, (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_color, 1
                )
            
            # Add border
            cv2.rectangle(img, (x_start, y_start), (x_end-1, y_end-1), (200, 200, 200), 1)
            
        except Exception as e:
            logger.warning(f"Failed to render grid chip {i} ({hex_color}): {str(e)}")
    
    # Encode and return
    try:
        success, buffer = cv2.imencode('.png', img)
        if not success:
            raise RuntimeError("Failed to encode grid as PNG")
        
        return base64.b64encode(buffer.tobytes()).decode('ascii')
        
    except Exception as e:
        logger.error(f"Failed to encode palette grid: {str(e)}")
        raise RuntimeError(f"Grid encoding failed: {str(e)}")


def create_color_comparison(original_hex: str, 
                          palette_hexes: List[str],
                          chip_size: int = 50) -> str:
    """
    Create a visual comparison showing an original color alongside palette colors.
    Useful for debugging color extraction accuracy.
    
    Args:
        original_hex: The target/reference color
        palette_hexes: List of extracted palette colors
        chip_size: Size of color chips
        
    Returns:
        Base64-encoded PNG comparison image
    """
    total_chips = 1 + len(palette_hexes)
    img_width = total_chips * chip_size
    img_height = chip_size
    
    img = np.zeros((img_height, img_width, 3), dtype=np.uint8)
    
    # Render original color (first chip)
    try:
        original_bgr = hex_to_bgr(original_hex)
        img[:, 0:chip_size, :] = original_bgr
        
        # Add "ORIG" label
        cv2.putText(img, "ORIG", (5, chip_size//2), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
        
    except Exception as e:
        logger.warning(f"Failed to render original color {original_hex}: {str(e)}")
    
    # Render palette colors
    for i, hex_color in enumerate(palette_hexes):
        x_start = (i + 1) * chip_size
        x_end = x_start + chip_size
        
        try:
            bgr_color = hex_to_bgr(hex_color)
            img[:, x_start:x_end, :] = bgr_color
            
            # Add index label
            cv2.putText(img, str(i), (x_start + 5, chip_size//2), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
            
        except Exception as e:
            logger.warning(f"Failed to render palette color {hex_color}: {str(e)}")
    
    # Add borders
    for i in range(total_chips):
        x_start = i * chip_size
        cv2.rectangle(img, (x_start, 0), (x_start + chip_size - 1, chip_size - 1), (100, 100, 100), 1)
    
    # Encode and return
    success, buffer = cv2.imencode('.png', img)
    if not success:
        raise RuntimeError("Failed to encode comparison image")
    
    return base64.b64encode(buffer.tobytes()).decode('ascii')


def validate_swatch_params(hex_colors: List[str], chip_size: int, highlight_index: Optional[int]) -> None:
    """Validate swatch rendering parameters."""
    if not hex_colors:
        raise ValueError("hex_colors cannot be empty")
    
    if chip_size <= 0:
        raise ValueError("chip_size must be positive")
    
    if highlight_index is not None and (highlight_index < 0 or highlight_index >= len(hex_colors)):
        raise ValueError(f"highlight_index {highlight_index} out of range [0, {len(hex_colors)})")
    
    # Validate hex color format
    for i, hex_color in enumerate(hex_colors):
        if not isinstance(hex_color, str):
            raise ValueError(f"Color at index {i} is not a string: {type(hex_color)}")
        
        if not hex_color.startswith('#') or len(hex_color) != 7:
            raise ValueError(f"Invalid hex color format at index {i}: {hex_color}")
        
        try:
            int(hex_color[1:], 16)  # Validate hex digits
        except ValueError:
            raise ValueError(f"Invalid hex color digits at index {i}: {hex_color}")


def generate_test_swatch() -> str:
    """Generate a test swatch with known colors for validation."""
    test_colors = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF"]
    return render_swatch_strip(test_colors, chip_size=30, highlight_index=2)
