"""
StyleSync ColorMatch MVP - Phase 3: Neutrals Selection

This module implements neutral color pool selection and ordering based on base
lightness and seasonal preferences. Provides curated neutral colors that work
well with any base color for outfit coordination.
"""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

from .wearability import Season, ClampedSuggestion


@dataclass
class NeutralColor:
    """A neutral color with metadata for selection logic."""
    hex: str
    name: str
    lightness: float  # Pre-computed for ordering
    warmth: str  # "cool", "warm", or "neutral"
    category: str  # "white", "gray", "beige", "brown"


# Fixed neutral color pool
NEUTRAL_POOL = [
    NeutralColor("#FFFFFF", "White", 1.0, "neutral", "white"),
    NeutralColor("#F5F5F5", "Off-White", 0.96, "neutral", "white"), 
    NeutralColor("#D3D3D3", "Light Gray", 0.83, "cool", "gray"),
    NeutralColor("#808080", "Mid Gray", 0.50, "neutral", "gray"),
    NeutralColor("#333333", "Charcoal", 0.20, "cool", "gray"),
    NeutralColor("#F5F5DC", "Beige", 0.95, "warm", "beige"),
    NeutralColor("#C19A6B", "Camel", 0.70, "warm", "brown"),
    NeutralColor("#E5E4E2", "Stone", 0.89, "cool", "beige"),
    NeutralColor("#8B8589", "Taupe", 0.55, "warm", "brown")
]


def create_neutral_pool_map() -> Dict[str, NeutralColor]:
    """Create a lookup map for neutral colors by hex value."""
    return {neutral.hex: neutral for neutral in NEUTRAL_POOL}


def select_neutrals_by_base_lightness(base_l: float, max_neutrals: int = 4) -> List[NeutralColor]:
    """
    Select neutral colors based on base lightness for contrast.
    
    Args:
        base_l: Base color lightness [0, 1]
        max_neutrals: Maximum number of neutrals to select
        
    Returns:
        List of neutral colors ordered by preference
    """
    if base_l > 0.60:  # Light base
        # Prefer darker neutrals for contrast
        priority_order = [
            "#333333",  # Charcoal
            "#808080",  # Mid Gray
            "#8B8589",  # Taupe
            "#C19A6B",  # Camel
            "#D3D3D3",  # Light Gray
            "#E5E4E2",  # Stone
            "#F5F5DC",  # Beige
            "#F5F5F5",  # Off-White
            "#FFFFFF"   # White
        ]
    else:  # Dark base (L <= 0.60)
        # Prefer lighter neutrals for contrast
        priority_order = [
            "#FFFFFF",  # White
            "#F5F5F5",  # Off-White
            "#E5E4E2",  # Stone
            "#D3D3D3",  # Light Gray
            "#F5F5DC",  # Beige
            "#C19A6B",  # Camel
            "#808080",  # Mid Gray
            "#8B8589",  # Taupe
            "#333333"   # Charcoal
        ]
    
    # Create lookup for neutrals
    neutral_map = create_neutral_pool_map()
    
    # Select top neutrals based on priority order
    selected = []
    for hex_color in priority_order:
        if len(selected) >= max_neutrals:
            break
        if hex_color in neutral_map:
            selected.append(neutral_map[hex_color])
    
    return selected


def apply_seasonal_neutral_bias(neutrals: List[NeutralColor], season: Season) -> List[NeutralColor]:
    """
    Reorder neutrals based on seasonal preferences.
    
    Args:
        neutrals: List of neutral colors to reorder
        season: Seasonal bias to apply
        
    Returns:
        Reordered list with seasonal preferences applied
    """
    if season == Season.SPRING_SUMMER:
        # Prioritize cool and light neutrals
        def season_sort_key(neutral: NeutralColor) -> Tuple[int, float]:
            # Primary: cool/neutral warmth preference
            warmth_priority = 0 if neutral.warmth == "cool" else (1 if neutral.warmth == "neutral" else 2)
            # Secondary: lighter first
            lightness_priority = -neutral.lightness  # Negative for descending
            return (warmth_priority, lightness_priority)
            
    elif season == Season.AUTUMN_WINTER:
        # Prioritize warm neutrals and allow darker options
        def season_sort_key(neutral: NeutralColor) -> Tuple[int, float]:
            # Primary: warm warmth preference
            warmth_priority = 0 if neutral.warmth == "warm" else (1 if neutral.warmth == "neutral" else 2)
            # Secondary: mid-range lightness preferred
            lightness_priority = abs(neutral.lightness - 0.60)  # Distance from mid-range
            return (warmth_priority, lightness_priority)
            
    else:  # Season.ALL
        # No reordering - keep base lightness order
        return neutrals
    
    # Sort and return
    return sorted(neutrals, key=season_sort_key)


def deduplicate_neutrals_vs_harmonies(
    neutrals: List[NeutralColor], 
    harmony_suggestions: List[ClampedSuggestion],
    color_distance_threshold: float = 0.15
) -> List[NeutralColor]:
    """
    Remove neutrals that are too similar to harmony suggestions.
    
    Args:
        neutrals: List of neutral colors to filter
        harmony_suggestions: List of harmony suggestions to check against
        color_distance_threshold: Minimum lightness distance to keep neutrals
        
    Returns:
        Filtered list of neutrals avoiding conflicts with harmonies
    """
    from . import hex_to_hls
    
    # Extract harmony lightness values
    harmony_lightness = []
    for suggestion in harmony_suggestions:
        h, l, s = hex_to_hls(suggestion.hex)
        harmony_lightness.append(l)
    
    # Filter neutrals that are too close to any harmony color
    filtered_neutrals = []
    for neutral in neutrals:
        neutral_l = neutral.lightness
        
        # Check distance to all harmony colors
        too_close = False
        for harmony_l in harmony_lightness:
            if abs(neutral_l - harmony_l) < color_distance_threshold:
                too_close = True
                break
        
        if not too_close:
            filtered_neutrals.append(neutral)
    
    return filtered_neutrals


def generate_neutral_suggestions(
    base_hex: str,
    season: Season = Season.ALL,
    max_neutrals: int = 4,
    harmony_suggestions: List[ClampedSuggestion] = None
) -> List[ClampedSuggestion]:
    """
    Generate neutral color suggestions with seasonal bias and conflict avoidance.
    
    Args:
        base_hex: Base color for lightness-based selection
        season: Seasonal bias for neutral ordering
        max_neutrals: Maximum number of neutral suggestions
        harmony_suggestions: Harmony suggestions to avoid conflicts with
        
    Returns:
        List of neutral suggestions as ClampedSuggestion objects
    """
    from . import hex_to_hls
    
    # Get base lightness for selection logic
    base_h, base_l, base_s = hex_to_hls(base_hex)
    
    # Select neutrals based on base lightness
    selected_neutrals = select_neutrals_by_base_lightness(base_l, max_neutrals * 2)  # Get extra for filtering
    
    # Apply seasonal bias to ordering
    seasonal_neutrals = apply_seasonal_neutral_bias(selected_neutrals, season)
    
    # Deduplicate against harmony suggestions if provided
    if harmony_suggestions:
        final_neutrals = deduplicate_neutrals_vs_harmonies(seasonal_neutrals, harmony_suggestions)
    else:
        final_neutrals = seasonal_neutrals
    
    # Limit to requested count
    final_neutrals = final_neutrals[:max_neutrals]
    
    # Convert to ClampedSuggestion format
    neutral_suggestions = []
    for neutral in final_neutrals:
        # Create rationale
        selection_reason = "dark_base" if base_l <= 0.60 else "light_base"
        seasonal_token = f"season:{season.value}" if season != Season.ALL else "season:all"
        
        rationale = [
            "category:neutral",
            f"selection:{selection_reason}",
            seasonal_token,
            f"neutral:{neutral.name.lower().replace(' ', '_')}"
        ]
        
        # Get HLS for consistency (though neutrals don't need complex HLS processing)
        n_h, n_l, n_s = hex_to_hls(neutral.hex)
        
        neutral_suggestions.append(ClampedSuggestion(
            hex=neutral.hex,
            category="neutral",
            role_target="any",  # Neutrals work for any role
            hls=(round(n_h, 3), round(n_l, 3), round(n_s, 3)),
            rationale=rationale
        ))
    
    return neutral_suggestions


def get_neutral_pool_info() -> Dict[str, Any]:
    """
    Get information about the neutral color pool for policy disclosure.
    
    Returns:
        Dictionary with neutral pool metadata
    """
    return {
        "total_neutrals": len(NEUTRAL_POOL),
        "categories": list(set(neutral.category for neutral in NEUTRAL_POOL)),
        "warmth_types": list(set(neutral.warmth for neutral in NEUTRAL_POOL)),
        "lightness_range": (
            min(neutral.lightness for neutral in NEUTRAL_POOL),
            max(neutral.lightness for neutral in NEUTRAL_POOL)
        ),
        "pool_hex_values": [neutral.hex for neutral in NEUTRAL_POOL]
    }
