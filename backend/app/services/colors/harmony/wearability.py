"""
StyleSync ColorMatch MVP - Phase 3: Wearability Constraints

This module implements role-aware saturation caps, lightness bands, minimum contrast
enforcement, and seasonal adjustments to ensure generated color suggestions are
practical and wearable.
"""

import math
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from . import HarmonyCandidate, hls_to_hex


class GarmentRole(str, Enum):
    """Supported garment roles with different wearability constraints."""
    TOP = "top"
    BOTTOM = "bottom" 
    DRESS = "dress"
    OUTERWEAR = "outerwear"
    ACCESSORY = "accessory"


class StyleIntent(str, Enum):
    """Style intent levels affecting saturation and category breadth."""
    SAFE = "safe"        # Conservative, neutrals prioritized
    CLASSIC = "classic"  # Balanced, wardrobe staples
    BOLD = "bold"        # Higher saturation/contrast allowed


class Season(str, Enum):
    """Seasonal bias for lightness and neutral selection."""
    ALL = "all"
    SPRING_SUMMER = "spring_summer"
    AUTUMN_WINTER = "autumn_winter"


@dataclass
class WearabilityPolicy:
    """Centralized policy constants for wearability constraints."""
    
    # Minimum contrast constraint
    delta_l_min: float = 0.12
    
    # Role-aware lightness bands
    role_l_bands: Dict[str, Tuple[float, float]] = None
    
    # Role-aware saturation caps by intent
    role_s_caps: Dict[str, Dict[str, float]] = None
    
    # Analogous minimum hue separation (safe mode)
    analogous_min_sep_degrees: float = 25.0
    
    # Seasonal lightness adjustments
    seasonal_l_nudge: float = 0.05
    
    # Hyper-saturation reduction threshold
    hyper_sat_threshold: float = 0.80
    hyper_sat_reduction: float = 0.15
    
    # Degenerate base handling
    degenerate_s_threshold: float = 0.12
    degenerate_l_low: float = 0.08
    degenerate_l_high: float = 0.92
    
    def __post_init__(self):
        """Initialize default policy values."""
        if self.role_l_bands is None:
            self.role_l_bands = {
                "top": (0.45, 0.75),
                "bottom": (0.40, 0.70),
                "dress": (0.45, 0.75),
                "outerwear": (0.45, 0.75),
                "accessory": (0.30, 0.85)
            }
        
        if self.role_s_caps is None:
            self.role_s_caps = {
                "bottom": {
                    "safe": 0.50,
                    "classic": 0.60,
                    "bold": 0.75
                },
                "top": {
                    "safe": 0.55,
                    "classic": 0.65,
                    "bold": 0.80
                },
                "dress": {
                    "safe": 0.55,
                    "classic": 0.65,
                    "bold": 0.80
                },
                "outerwear": {
                    "safe": 0.55,
                    "classic": 0.65,
                    "bold": 0.80
                },
                "accessory": {
                    "safe": 0.60,
                    "classic": 0.70,
                    "bold": 0.85
                }
            }


@dataclass 
class ClampedSuggestion:
    """A harmony candidate after wearability constraints have been applied."""
    hex: str
    category: str
    role_target: str
    hls: Tuple[float, float, float]  # Final H, L, S after all clamps
    rationale: List[str]  # Tokens documenting decisions made


def apply_seasonal_adjustment(l: float, season: Season, policy: WearabilityPolicy) -> Tuple[float, str]:
    """
    Apply seasonal lightness bias before role clamping.
    
    Args:
        l: Original lightness [0, 1]
        season: Seasonal bias to apply
        policy: Wearability policy with constants
        
    Returns:
        Tuple of (adjusted_lightness, rationale_token)
    """
    if season == Season.SPRING_SUMMER:
        adjusted_l = l + policy.seasonal_l_nudge
        token = f"season:ss_L+{policy.seasonal_l_nudge}"
    elif season == Season.AUTUMN_WINTER:
        adjusted_l = l - policy.seasonal_l_nudge
        token = f"season:aw_L-{policy.seasonal_l_nudge}"
    else:
        adjusted_l = l
        token = "season:all"
    
    # Keep in valid range
    adjusted_l = max(0.0, min(1.0, adjusted_l))
    
    return adjusted_l, token


def apply_role_lightness_clamp(l: float, role: GarmentRole, policy: WearabilityPolicy) -> Tuple[float, str]:
    """
    Clamp lightness to role-appropriate bounds.
    
    Args:
        l: Input lightness [0, 1]
        role: Target garment role
        policy: Wearability policy with role bands
        
    Returns:
        Tuple of (clamped_lightness, rationale_token)
    """
    l_min, l_max = policy.role_l_bands[role.value]
    
    if l < l_min:
        clamped_l = l_min
        token = f"L_clamp:{l:.3f}→{l_min}(role_min)"
    elif l > l_max:
        clamped_l = l_max
        token = f"L_clamp:{l:.3f}→{l_max}(role_max)"
    else:
        clamped_l = l
        token = f"L_ok:{l:.3f}"
    
    return clamped_l, token


def apply_role_saturation_cap(s: float, role: GarmentRole, intent: StyleIntent, policy: WearabilityPolicy) -> Tuple[float, str]:
    """
    Cap saturation based on role and style intent.
    
    Args:
        s: Input saturation [0, 1]
        role: Target garment role
        intent: Style intent level
        policy: Wearability policy with saturation caps
        
    Returns:
        Tuple of (capped_saturation, rationale_token)
    """
    s_cap = policy.role_s_caps[role.value][intent.value]
    
    if s > s_cap:
        capped_s = s_cap
        token = f"S_cap:{s:.3f}→{s_cap}({role.value}_{intent.value})"
    else:
        capped_s = s
        token = f"S_ok:{s:.3f}"
    
    return capped_s, token


def enforce_minimum_contrast(candidate_l: float, base_l: float, role: GarmentRole, policy: WearabilityPolicy) -> Tuple[float, str]:
    """
    Ensure minimum contrast between candidate and base lightness.
    
    Args:
        candidate_l: Candidate lightness [0, 1]
        base_l: Base color lightness [0, 1]
        role: Target garment role for bounds checking
        policy: Wearability policy with contrast minimum
        
    Returns:
        Tuple of (contrast_adjusted_lightness, rationale_token)
    """
    delta_l = abs(candidate_l - base_l)
    
    if delta_l >= policy.delta_l_min:
        return candidate_l, f"contrast_ok:ΔL={delta_l:.3f}"
    
    # Need to adjust - move away from base toward role bounds
    l_min, l_max = policy.role_l_bands[role.value]
    
    if candidate_l > base_l:
        # Try moving higher first
        adjusted_l = base_l + policy.delta_l_min
        if adjusted_l <= l_max:
            token = f"contrast_fix:L→{adjusted_l:.3f}(+ΔL_min)"
        else:
            # Move lower instead
            adjusted_l = base_l - policy.delta_l_min
            adjusted_l = max(l_min, adjusted_l)
            token = f"contrast_fix:L→{adjusted_l:.3f}(-ΔL_min,bounded)"
    else:
        # Try moving lower first
        adjusted_l = base_l - policy.delta_l_min
        if adjusted_l >= l_min:
            token = f"contrast_fix:L→{adjusted_l:.3f}(-ΔL_min)"
        else:
            # Move higher instead
            adjusted_l = base_l + policy.delta_l_min
            adjusted_l = min(l_max, adjusted_l)
            token = f"contrast_fix:L→{adjusted_l:.3f}(+ΔL_min,bounded)"
    
    return adjusted_l, token


def apply_hyper_saturation_guard(s: float, base_s: float, policy: WearabilityPolicy) -> Tuple[float, str]:
    """
    Reduce saturation if base color is hyper-saturated.
    
    Args:
        s: Candidate saturation [0, 1]
        base_s: Base color saturation [0, 1]
        policy: Wearability policy with hyper-saturation settings
        
    Returns:
        Tuple of (adjusted_saturation, rationale_token)
    """
    if base_s > policy.hyper_sat_threshold:
        reduced_s = s * (1.0 - policy.hyper_sat_reduction)
        token = f"hyper_sat_guard:S×{1.0 - policy.hyper_sat_reduction:.2f}"
        return reduced_s, token
    else:
        return s, "hyper_sat_ok"


def check_analogous_separation(candidates: List[HarmonyCandidate], base_h: float, intent: StyleIntent, policy: WearabilityPolicy) -> List[HarmonyCandidate]:
    """
    Filter analogous candidates to ensure minimum hue separation in safe mode.
    
    Args:
        candidates: List of analogous harmony candidates
        base_h: Base hue [0, 1)
        intent: Style intent level
        policy: Wearability policy with separation requirements
        
    Returns:
        Filtered list of analogous candidates meeting separation requirements
    """
    if intent != StyleIntent.SAFE:
        return candidates
    
    filtered = []
    for candidate in candidates:
        # Calculate hue separation from base
        diff = abs(candidate.h - base_h)
        wraparound_diff = 1.0 - diff
        min_diff_degrees = min(diff, wraparound_diff) * 360.0
        
        if min_diff_degrees >= policy.analogous_min_sep_degrees:
            filtered.append(candidate)
        # Skip candidates that are too close in safe mode
    
    return filtered


def apply_wearability_constraints(
    candidates: List[HarmonyCandidate], 
    base_hex: str,
    role: GarmentRole,
    intent: StyleIntent, 
    season: Season,
    policy: WearabilityPolicy
) -> List[ClampedSuggestion]:
    """
    Apply all wearability constraints to harmony candidates.
    
    Args:
        candidates: List of harmony candidates to process
        base_hex: Base color for contrast checking
        role: Target garment role
        intent: Style intent level
        season: Seasonal bias
        policy: Wearability policy with all constants
        
    Returns:
        List of clamped suggestions with rationale tokens
    """
    from . import hex_to_hls
    
    base_h, base_l, base_s = hex_to_hls(base_hex)
    results = []
    
    for candidate in candidates:
        rationale = [f"category:{candidate.category}", candidate.generation_rule]
        
        # Start with candidate values
        current_h = candidate.h
        current_l = candidate.l
        current_s = candidate.s
        
        # Apply hyper-saturation guard
        current_s, hyper_token = apply_hyper_saturation_guard(current_s, base_s, policy)
        rationale.append(hyper_token)
        
        # Apply seasonal adjustment
        current_l, season_token = apply_seasonal_adjustment(current_l, season, policy)
        rationale.append(season_token)
        
        # Apply role saturation cap
        current_s, s_cap_token = apply_role_saturation_cap(current_s, role, intent, policy)
        rationale.append(s_cap_token)
        
        # Apply role lightness clamp
        current_l, l_clamp_token = apply_role_lightness_clamp(current_l, role, policy)
        rationale.append(l_clamp_token)
        
        # Enforce minimum contrast
        current_l, contrast_token = enforce_minimum_contrast(current_l, base_l, role, policy)
        rationale.append(contrast_token)
        
        # Convert final HLS to hex
        final_hex = hls_to_hex(current_h, current_l, current_s)
        
        results.append(ClampedSuggestion(
            hex=final_hex,
            category=candidate.category,
            role_target=role.value,
            hls=(round(current_h, 3), round(current_l, 3), round(current_s, 3)),
            rationale=rationale
        ))
    
    return results


def is_degenerate_base(base_hex: str, policy: WearabilityPolicy) -> bool:
    """
    Check if base color is degenerate (near-neutral or extreme lightness).
    
    Args:
        base_hex: Base color to check
        policy: Wearability policy with degenerate thresholds
        
    Returns:
        True if base is considered degenerate for harmony generation
    """
    from . import hex_to_hls
    
    h, l, s = hex_to_hls(base_hex)
    
    # Check for low saturation (near-neutral)
    if s < policy.degenerate_s_threshold:
        return True
    
    # Check for extreme lightness
    if l < policy.degenerate_l_low or l > policy.degenerate_l_high:
        return True
    
    return False
