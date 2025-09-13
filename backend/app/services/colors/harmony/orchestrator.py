"""
StyleSync ColorMatch MVP - Phase 3: Color Suggestion Orchestrator

This module coordinates the entire color suggestion pipeline, from harmony
generation through wearability constraints to final output assembly with
rationales and swatch artifacts.
"""

import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import asdict

from . import (
    generate_harmony_candidates, hex_to_hls, HarmonyCandidate,
)
from .wearability import (
    WearabilityPolicy, GarmentRole, StyleIntent, Season,
    apply_wearability_constraints, check_analogous_separation,
    is_degenerate_base, ClampedSuggestion
)
from .neutrals import generate_neutral_suggestions, get_neutral_pool_info
from .swatches import render_suggestion_swatch, validate_swatch_generation, create_swatch_metadata


def apply_intent_category_limits(
    harmony_candidates: Dict[str, List[HarmonyCandidate]],
    intent: StyleIntent
) -> Dict[str, List[HarmonyCandidate]]:
    """
    Filter harmony candidates based on style intent category preferences.
    
    Args:
        harmony_candidates: Dictionary of harmony candidates by category
        intent: Style intent affecting category breadth
        
    Returns:
        Filtered candidates respecting intent limits
    """
    limits = {
        StyleIntent.SAFE: {
            "complementary": 1,
            "analogous": 1, 
            "triadic": 0  # Skip triadic in safe mode
        },
        StyleIntent.CLASSIC: {
            "complementary": 1,
            "analogous": 2,
            "triadic": 1
        },
        StyleIntent.BOLD: {
            "complementary": 2,  # Allow multiple complementary variations
            "analogous": 2,
            "triadic": 2
        }
    }
    
    intent_limits = limits[intent]
    filtered = {}
    
    for category, candidates in harmony_candidates.items():
        max_count = intent_limits.get(category, 0)
        if max_count > 0:
            filtered[category] = candidates[:max_count]
    
    return filtered


def process_degenerate_base(
    base_hex: str,
    role: GarmentRole,
    intent: StyleIntent,
    season: Season,
    policy: WearabilityPolicy,
    max_neutrals: int
) -> Tuple[Dict[str, List[ClampedSuggestion]], List[str]]:
    """
    Handle degenerate base colors with neutral-focused suggestions.
    
    Args:
        base_hex: Degenerate base color
        role: Target garment role
        intent: Style intent
        season: Seasonal bias
        policy: Wearability policy
        max_neutrals: Maximum neutral suggestions
        
    Returns:
        Tuple of (suggestions_by_category, processing_notes)
    """
    notes = ["degenerate_base_detected", "neutral_focused_mode"]
    
    # Generate neutral-heavy suggestions
    neutral_suggestions = generate_neutral_suggestions(
        base_hex, season, max_neutrals, harmony_suggestions=[]
    )
    
    suggestions_by_category = {"neutral": neutral_suggestions}
    
    # Add minimal harmony suggestions only for bold intent
    if intent == StyleIntent.BOLD:
        try:
            # Generate minimal harmony candidates
            harmony_candidates = generate_harmony_candidates(base_hex)
            
            # Apply constraints to a single complementary if available
            if "complementary" in harmony_candidates:
                complementary_suggestions = apply_wearability_constraints(
                    harmony_candidates["complementary"][:1],  # Just one
                    base_hex, role, intent, season, policy
                )
                if complementary_suggestions:
                    suggestions_by_category["complementary"] = complementary_suggestions
                    notes.append("added_single_complementary_for_bold")
        except Exception:
            # Skip harmony if it fails for degenerate cases
            notes.append("harmony_skipped_for_degenerate")
    
    return suggestions_by_category, notes


def generate_color_suggestions(
    base_hex: str,
    source_role: GarmentRole = GarmentRole.TOP,
    target_role: GarmentRole = GarmentRole.BOTTOM,
    intent: StyleIntent = StyleIntent.CLASSIC,
    season: Season = Season.ALL,
    include_complementary: bool = True,
    include_analogous: bool = True,
    include_triadic: bool = True,
    include_neutrals: bool = True,
    neutrals_max: int = 4,
    return_swatch: bool = True,
    policy: Optional[WearabilityPolicy] = None
) -> Dict[str, Any]:
    """
    Generate complete color suggestions for outfit coordination.
    
    Args:
        base_hex: Base color in format #RRGGBB
        source_role: Role of the garment providing the base color
        target_role: Role of the garment to suggest colors for
        intent: Style intent affecting saturation and category breadth
        season: Seasonal bias for lightness and neutral selection
        include_complementary: Whether to include complementary suggestions
        include_analogous: Whether to include analogous suggestions
        include_triadic: Whether to include triadic suggestions
        include_neutrals: Whether to include neutral suggestions
        neutrals_max: Maximum number of neutral suggestions
        return_swatch: Whether to generate swatch artifact
        policy: Wearability policy (uses default if None)
        
    Returns:
        Dictionary with suggestions, metadata, and optional artifacts
    """
    start_time = time.time()
    
    # Initialize policy if not provided
    if policy is None:
        policy = WearabilityPolicy()
    
    # Validate base color format
    if not base_hex.startswith('#') or len(base_hex) != 7:
        raise ValueError(f"Invalid base color format: {base_hex}")
    
    # Get base color HLS for metadata
    base_h, base_l, base_s = hex_to_hls(base_hex)
    
    # Check for degenerate base color
    if is_degenerate_base(base_hex, policy):
        suggestions_by_category, processing_notes = process_degenerate_base(
            base_hex, target_role, intent, season, policy, neutrals_max
        )
        harmony_time = time.time() - start_time
    else:
        processing_notes = ["normal_processing"]
        
        # Generate harmony candidates
        harmony_start = time.time()
        harmony_candidates = generate_harmony_candidates(base_hex)
        
        # Filter by inclusion flags
        if not include_complementary:
            harmony_candidates.pop("complementary", None)
        if not include_analogous:
            harmony_candidates.pop("analogous", None)
        if not include_triadic:
            harmony_candidates.pop("triadic", None)
        
        # Apply analogous separation for safe mode
        if "analogous" in harmony_candidates:
            harmony_candidates["analogous"] = check_analogous_separation(
                harmony_candidates["analogous"], base_h, intent, policy
            )
        
        # Apply intent-based category limits
        harmony_candidates = apply_intent_category_limits(harmony_candidates, intent)
        
        # Apply wearability constraints to harmony candidates
        suggestions_by_category = {}
        for category, candidates in harmony_candidates.items():
            if candidates:
                constrained_suggestions = apply_wearability_constraints(
                    candidates, base_hex, target_role, intent, season, policy
                )
                if constrained_suggestions:
                    suggestions_by_category[category] = constrained_suggestions
        
        harmony_time = time.time() - harmony_start
        
        # Generate neutral suggestions
        if include_neutrals:
            harmony_suggestions = []
            for category_suggestions in suggestions_by_category.values():
                harmony_suggestions.extend(category_suggestions)
            
            neutral_suggestions = generate_neutral_suggestions(
                base_hex, season, neutrals_max, harmony_suggestions
            )
            if neutral_suggestions:
                suggestions_by_category["neutral"] = neutral_suggestions
    
    # Generate swatch artifact if requested
    swatch_time = 0
    swatch_b64 = None
    swatch_metadata = None
    
    if return_swatch:
        swatch_start = time.time()
        try:
            swatch_validation = validate_swatch_generation()
            if swatch_validation["available"]:
                swatch_b64 = render_suggestion_swatch(
                    suggestions_by_category, format_type="grouped"
                )
                swatch_metadata = create_swatch_metadata(
                    suggestions_by_category, "grouped", 40, 2
                )
            else:
                processing_notes.append("swatch_unavailable_no_pil")
        except Exception as e:
            processing_notes.append(f"swatch_error:{str(e)[:50]}")
        
        swatch_time = time.time() - swatch_start
    
    total_time = time.time() - start_time
    
    # Assemble response
    response = {
        "meta": {
            "base_hex": base_hex,
            "base_hls": {
                "h": round(base_h, 3),
                "l": round(base_l, 3), 
                "s": round(base_s, 3)
            },
            "source_role": source_role.value,
            "target_role": target_role.value,
            "intent": intent.value,
            "season": season.value
        },
        "suggestions": {},
        "policy": {
            "delta_l_min": policy.delta_l_min,
            "role_l_bands": dict(policy.role_l_bands),
            "role_s_caps": dict(policy.role_s_caps),
            "analogous_min_sep_degrees": policy.analogous_min_sep_degrees,
            "seasonal_l_nudge": policy.seasonal_l_nudge,
            "hyper_sat_threshold": policy.hyper_sat_threshold,
            "degenerate_s_threshold": policy.degenerate_s_threshold,
            "neutral_pool": get_neutral_pool_info()
        },
        "artifacts": {
            "swatch_png_b64": swatch_b64,
            "swatch_metadata": swatch_metadata
        },
        "debug": {
            "processing_notes": processing_notes,
            "timing_ms": {
                "harmony": round(harmony_time * 1000, 2),
                "swatch": round(swatch_time * 1000, 2),
                "total": round(total_time * 1000, 2)
            },
            "category_counts": {
                category: len(suggestions)
                for category, suggestions in suggestions_by_category.items()
            }
        }
    }
    
    # Format suggestions for output
    category_order = ["complementary", "analogous", "triadic", "neutral"]
    for category in category_order:
        if category in suggestions_by_category:
            response["suggestions"][category] = [
                {
                    "hex": suggestion.hex,
                    "category": suggestion.category,
                    "role_target": suggestion.role_target,
                    "hls": {
                        "h": suggestion.hls[0],
                        "l": suggestion.hls[1],
                        "s": suggestion.hls[2]
                    },
                    "rationale": suggestion.rationale
                }
                for suggestion in suggestions_by_category[category]
            ]
    
    return response


def get_default_policy() -> WearabilityPolicy:
    """Get the default wearability policy with all standard constants."""
    return WearabilityPolicy()
