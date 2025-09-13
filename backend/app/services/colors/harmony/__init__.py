"""
StyleSync ColorMatch MVP - Phase 3: Color Harmony Engine

This module implements color theory rules for generating complementary, analogous,
and triadic color suggestions based on fundamental color harmony principles.
"""

import colorsys
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass


@dataclass
class HarmonyCandidate:
    """A color harmony candidate with its generation metadata."""
    h: float  # Hue [0, 1)
    l: float  # Lightness [0, 1]
    s: float  # Saturation [0, 1]
    category: str  # "complementary", "analogous", "triadic"
    generation_rule: str  # Human-readable generation rule for rationale


def hex_to_hls(hex_color: str) -> Tuple[float, float, float]:
    """
    Convert hex color to HLS color space.
    
    Args:
        hex_color: Color in format #RRGGBB
        
    Returns:
        Tuple of (H, L, S) where H ∈ [0,1), L ∈ [0,1], S ∈ [0,1]
    """
    # Remove # prefix and convert to RGB
    hex_clean = hex_color.lstrip('#')
    if len(hex_clean) != 6:
        raise ValueError(f"Invalid hex color format: {hex_color}")
    
    try:
        r = int(hex_clean[0:2], 16) / 255.0
        g = int(hex_clean[2:4], 16) / 255.0
        b = int(hex_clean[4:6], 16) / 255.0
    except ValueError:
        raise ValueError(f"Invalid hex color format: {hex_color}")
    
    # Convert RGB to HLS using Python's colorsys
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h, l, s


def hls_to_hex(h: float, l: float, s: float) -> str:
    """
    Convert HLS color to hex format.
    
    Args:
        h: Hue [0, 1)
        l: Lightness [0, 1] 
        s: Saturation [0, 1]
        
    Returns:
        Hex color string in format #RRGGBB (uppercase)
    """
    # Convert HLS to RGB using Python's colorsys
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    
    # Convert to 8-bit integers and format as hex
    r_int = max(0, min(255, round(r * 255)))
    g_int = max(0, min(255, round(g * 255)))
    b_int = max(0, min(255, round(b * 255)))
    
    return f"#{r_int:02X}{g_int:02X}{b_int:02X}"


def rotate_hue(h: float, degrees: float) -> float:
    """
    Rotate hue by specified degrees.
    
    Args:
        h: Original hue [0, 1)
        degrees: Rotation in degrees (can be negative)
        
    Returns:
        Rotated hue [0, 1) with proper wraparound
    """
    # Convert degrees to hue units and add
    h_rotated = h + (degrees / 360.0)
    
    # Ensure wraparound to [0, 1)
    while h_rotated >= 1.0:
        h_rotated -= 1.0
    while h_rotated < 0.0:
        h_rotated += 1.0
        
    return h_rotated


def generate_complementary_candidates(base_h: float, base_l: float, base_s: float) -> List[HarmonyCandidate]:
    """
    Generate complementary color candidates using +180° hue rotation.
    
    Args:
        base_h: Base hue [0, 1)
        base_l: Base lightness [0, 1]
        base_s: Base saturation [0, 1]
        
    Returns:
        List of complementary harmony candidates
    """
    # Complementary hue is +180 degrees
    comp_h = rotate_hue(base_h, 180.0)
    
    # Apparel heuristic: adjust lightness for contrast
    if base_l < 0.45:  # Dark base
        target_l = 0.65  # Make lighter for contrast
        rule = "h_rot:+180°; L→0.65 (dark base contrast)"
    else:  # Mid/light base
        target_l = 0.47  # Make darker for contrast
        rule = "h_rot:+180°; L→0.47 (light base contrast)"
    
    # Preliminary saturation (before intent/role clamps)
    target_s = min(0.70, base_s * 0.95)
    
    return [HarmonyCandidate(
        h=comp_h,
        l=target_l,
        s=target_s,
        category="complementary",
        generation_rule=rule
    )]


def generate_analogous_candidates(base_h: float, base_l: float, base_s: float) -> List[HarmonyCandidate]:
    """
    Generate analogous color candidates using ±30° hue rotations.
    
    Args:
        base_h: Base hue [0, 1)
        base_l: Base lightness [0, 1]
        base_s: Base saturation [0, 1]
        
    Returns:
        List of analogous harmony candidates
    """
    candidates = []
    
    # Two analogous hues: +30° and -30°
    for degrees, direction in [(30, "positive"), (-30, "negative")]:
        ana_h = rotate_hue(base_h, degrees)
        
        # Keep lightness near base (±0.05)
        target_l = base_l
        
        # Reduce saturation slightly for wearability (before role caps)
        target_s = base_s * 0.90
        
        rule = f"h_rot:{degrees:+d}°; L≈base; S×0.90"
        
        candidates.append(HarmonyCandidate(
            h=ana_h,
            l=target_l,
            s=target_s,
            category="analogous",
            generation_rule=rule
        ))
    
    return candidates


def generate_triadic_candidates(base_h: float, base_l: float, base_s: float) -> List[HarmonyCandidate]:
    """
    Generate triadic color candidates using ±120° hue rotations.
    
    Args:
        base_h: Base hue [0, 1)
        base_l: Base lightness [0, 1]
        base_s: Base saturation [0, 1]
        
    Returns:
        List of triadic harmony candidates
    """
    candidates = []
    
    # Two triadic hues: +120° and -120°
    for degrees, direction in [(120, "tri1"), (-120, "tri2")]:
        tri_h = rotate_hue(base_h, degrees)
        
        # Keep lightness in mid-range for wearability
        target_l = 0.55  # Mid-tone for balanced appearance
        
        # Moderate saturation (before intent/role caps)
        target_s = min(0.65, base_s * 0.85)
        
        rule = f"h_rot:{degrees:+d}°; L→0.55 (mid-tone); S×0.85"
        
        candidates.append(HarmonyCandidate(
            h=tri_h,
            l=target_l,
            s=target_s,
            category="triadic",
            generation_rule=rule
        ))
    
    return candidates


def generate_harmony_candidates(base_hex: str) -> Dict[str, List[HarmonyCandidate]]:
    """
    Generate all harmony candidates for a base color.
    
    Args:
        base_hex: Base color in format #RRGGBB
        
    Returns:
        Dictionary mapping category names to lists of harmony candidates
    """
    # Convert base color to HLS
    base_h, base_l, base_s = hex_to_hls(base_hex)
    
    # Generate candidates for each harmony type
    complementary = generate_complementary_candidates(base_h, base_l, base_s)
    analogous = generate_analogous_candidates(base_h, base_l, base_s)
    triadic = generate_triadic_candidates(base_h, base_l, base_s)
    
    return {
        "complementary": complementary,
        "analogous": analogous,
        "triadic": triadic
    }


def get_hue_separation(h1: float, h2: float) -> float:
    """
    Calculate the minimum angular separation between two hues.
    
    Args:
        h1: First hue [0, 1)
        h2: Second hue [0, 1)
        
    Returns:
        Minimum separation in degrees [0, 180]
    """
    # Calculate direct difference
    diff = abs(h1 - h2)
    
    # Consider wraparound (smaller of direct or wraparound distance)
    wraparound_diff = 1.0 - diff
    min_diff = min(diff, wraparound_diff)
    
    # Convert to degrees
    return min_diff * 360.0
