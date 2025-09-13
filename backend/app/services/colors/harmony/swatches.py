"""
StyleSync ColorMatch MVP - Phase 3: Swatch Generation

This module creates PNG swatch artifacts grouped by category for UI preview,
consistent with Phase 2 format. Provides visual representation of color
suggestions organized by harmony category.
"""

import base64
import io
from typing import List, Dict, Any, Optional, Union

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = ImageDraw = ImageFont = None

from .wearability import ClampedSuggestion


def hex_to_rgb(hex_color: str) -> tuple:
    """
    Convert hex color to RGB tuple.
    
    Args:
        hex_color: Color in format #RRGGBB
        
    Returns:
        RGB tuple (r, g, b) with values 0-255
    """
    hex_clean = hex_color.lstrip('#')
    return tuple(int(hex_clean[i:i+2], 16) for i in (0, 2, 4))


def create_color_chip(color_hex: str, chip_size: int = 40) -> Any:
    """
    Create a single color chip image.
    
    Args:
        color_hex: Hex color to render
        chip_size: Size of the square chip in pixels
        
    Returns:
        PIL Image of the color chip
    """
    if Image is None:
        raise RuntimeError("PIL not available for swatch generation")
    
    # Create solid color image
    rgb = hex_to_rgb(color_hex)
    chip = Image.new('RGB', (chip_size, chip_size), rgb)
    
    return chip


def create_category_row(suggestions: List[ClampedSuggestion], chip_size: int = 40, spacing: int = 2) -> Any:
    """
    Create a horizontal row of color chips for a category.
    
    Args:
        suggestions: List of color suggestions for this category
        chip_size: Size of each chip in pixels
        spacing: Spacing between chips in pixels
        
    Returns:
        PIL Image of the category row
    """
    if Image is None:
        raise RuntimeError("PIL not available for swatch generation")
    
    if not suggestions:
        # Return empty 1x1 transparent image
        return Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    
    # Calculate row dimensions
    num_chips = len(suggestions)
    row_width = num_chips * chip_size + (num_chips - 1) * spacing
    row_height = chip_size
    
    # Create row image
    row = Image.new('RGB', (row_width, row_height), (255, 255, 255))
    
    # Add chips to row
    x_pos = 0
    for suggestion in suggestions:
        chip = create_color_chip(suggestion.hex, chip_size)
        row.paste(chip, (x_pos, 0))
        x_pos += chip_size + spacing
    
    return row


def create_labeled_swatch(
    suggestions_by_category: Dict[str, List[ClampedSuggestion]],
    chip_size: int = 40,
    spacing: int = 2,
    row_spacing: int = 4,
    include_labels: bool = True
) -> Any:
    """
    Create a swatch with labeled category rows.
    
    Args:
        suggestions_by_category: Dictionary mapping category names to suggestions
        chip_size: Size of each color chip
        spacing: Horizontal spacing between chips
        row_spacing: Vertical spacing between category rows
        include_labels: Whether to include category labels (requires font)
        
    Returns:
        PIL Image of the complete swatch
    """
    if Image is None:
        raise RuntimeError("PIL not available for swatch generation")
    
    # Define category order for consistent layout
    category_order = ["complementary", "analogous", "triadic", "neutral"]
    
    # Create rows for each category
    category_rows = []
    max_row_width = 0
    
    for category in category_order:
        if category in suggestions_by_category and suggestions_by_category[category]:
            row = create_category_row(
                suggestions_by_category[category], 
                chip_size, 
                spacing
            )
            category_rows.append((category, row))
            max_row_width = max(max_row_width, row.width)
    
    if not category_rows:
        # Return minimal empty image
        return Image.new('RGB', (chip_size, chip_size), (255, 255, 255))
    
    # Calculate final swatch dimensions
    label_height = 16 if include_labels else 0
    total_height = sum(
        label_height + row.height + row_spacing 
        for _, row in category_rows
    ) - row_spacing  # Remove spacing after last row
    
    swatch_width = max_row_width
    swatch_height = total_height
    
    # Create final swatch image
    swatch = Image.new('RGB', (swatch_width, swatch_height), (255, 255, 255))
    
    # Add category rows
    y_pos = 0
    for category, row in category_rows:
        # Add label if requested
        if include_labels:
            try:
                # Try to add text label (may fail if font not available)
                draw = ImageDraw.Draw(swatch)
                draw.text((2, y_pos), category.title(), fill=(0, 0, 0))
                y_pos += label_height
            except (OSError, AttributeError):
                # Skip labels if font loading fails
                pass
        
        # Add color row
        swatch.paste(row, (0, y_pos))
        y_pos += row.height + row_spacing
    
    return swatch


def create_simple_strip(suggestions: List[ClampedSuggestion], chip_size: int = 40, spacing: int = 2) -> Any:
    """
    Create a simple horizontal strip of all suggestions without category labels.
    
    Args:
        suggestions: List of all color suggestions
        chip_size: Size of each color chip
        spacing: Spacing between chips
        
    Returns:
        PIL Image of the color strip
    """
    if Image is None:
        raise RuntimeError("PIL not available for swatch generation")
    
    if not suggestions:
        return Image.new('RGB', (chip_size, chip_size), (255, 255, 255))
    
    # Calculate strip dimensions
    num_chips = len(suggestions)
    strip_width = num_chips * chip_size + (num_chips - 1) * spacing
    strip_height = chip_size
    
    # Create strip image
    strip = Image.new('RGB', (strip_width, strip_height), (255, 255, 255))
    
    # Add chips
    x_pos = 0
    for suggestion in suggestions:
        chip = create_color_chip(suggestion.hex, chip_size)
        strip.paste(chip, (x_pos, 0))
        x_pos += chip_size + spacing
    
    return strip


def render_suggestion_swatch(
    suggestions_by_category: Dict[str, List[ClampedSuggestion]],
    format_type: str = "grouped",
    chip_size: int = 40,
    spacing: int = 2
) -> str:
    """
    Render color suggestions as a base64-encoded PNG swatch.
    
    Args:
        suggestions_by_category: Dictionary mapping category names to suggestions
        format_type: "grouped" for labeled categories or "strip" for simple strip
        chip_size: Size of each color chip in pixels
        spacing: Spacing between chips in pixels
        
    Returns:
        Base64-encoded PNG image string
        
    Raises:
        RuntimeError: If PIL is not available
    """
    if Image is None:
        raise RuntimeError("PIL not available for swatch generation. Install Pillow package.")
    
    if format_type == "strip":
        # Create simple strip with all suggestions
        all_suggestions = []
        category_order = ["complementary", "analogous", "triadic", "neutral"]
        for category in category_order:
            if category in suggestions_by_category:
                all_suggestions.extend(suggestions_by_category[category])
        
        swatch = create_simple_strip(all_suggestions, chip_size, spacing)
    else:  # grouped format
        swatch = create_labeled_swatch(
            suggestions_by_category, 
            chip_size, 
            spacing,
            include_labels=True
        )
    
    # Convert to base64
    buffer = io.BytesIO()
    swatch.save(buffer, format='PNG')
    buffer.seek(0)
    
    png_data = buffer.getvalue()
    return base64.b64encode(png_data).decode('utf-8')


def validate_swatch_generation() -> Dict[str, Any]:
    """
    Validate that swatch generation is available and return capabilities.
    
    Returns:
        Dictionary with swatch generation capabilities and status
    """
    status = {
        "available": Image is not None,
        "formats_supported": ["grouped", "strip"] if Image is not None else [],
        "features": {
            "color_chips": Image is not None,
            "category_labels": Image is not None and ImageDraw is not None,
            "custom_sizing": Image is not None
        }
    }
    
    if Image is None:
        status["error"] = "PIL/Pillow not available. Install with: pip install Pillow"
    
    return status


def create_swatch_metadata(
    suggestions_by_category: Dict[str, List[ClampedSuggestion]],
    format_type: str,
    chip_size: int,
    spacing: int
) -> Dict[str, Any]:
    """
    Create metadata for swatch generation parameters and content.
    
    Args:
        suggestions_by_category: Dictionary mapping category names to suggestions
        format_type: Swatch format type used
        chip_size: Size of each color chip
        spacing: Spacing between chips
        
    Returns:
        Dictionary with swatch metadata
    """
    total_suggestions = sum(len(suggestions) for suggestions in suggestions_by_category.values())
    
    return {
        "format": format_type,
        "chip_size_px": chip_size,
        "spacing_px": spacing,
        "total_colors": total_suggestions,
        "categories": {
            category: len(suggestions)
            for category, suggestions in suggestions_by_category.items()
            if suggestions
        },
        "color_mapping": {
            category: [s.hex for s in suggestions]
            for category, suggestions in suggestions_by_category.items()
            if suggestions
        }
    }
