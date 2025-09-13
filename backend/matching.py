"""
Rule-based outfit matching engine for What2Wear
Implements deterministic, explainable scoring for top ↔ bottom suggestions
"""
from typing import List, Tuple, Set

# Fixed color bins matching backend palette.py
FIXED_BINS = {"red", "orange", "yellow", "green", "teal", "blue", "purple", "pink", "brown", "neutral"}

# Complementary color pairs (strongest harmony)
COMPLEMENTARY_PAIRS = {
    ("blue", "orange"), ("orange", "blue"),
    ("red", "green"), ("green", "red"), 
    ("yellow", "purple"), ("purple", "yellow")
}

# Analogous color pairs (neighbors on color wheel)
ANALOGOUS_PAIRS = {
    ("red", "orange"), ("orange", "red"),
    ("orange", "yellow"), ("yellow", "orange"),
    ("yellow", "green"), ("green", "yellow"),
    ("green", "teal"), ("teal", "green"),
    ("teal", "blue"), ("blue", "teal"),
    ("blue", "purple"), ("purple", "blue"),
    ("purple", "pink"), ("pink", "purple"),
    ("pink", "red"), ("red", "pink")
}


def score_and_reasons(
    src_bins: List[str], 
    src_tags: List[str], 
    cand_bins: List[str], 
    cand_tags: List[str]
) -> Tuple[float, List[str]]:
    """
    Score a candidate garment against source garment using rule-based algorithm
    
    Args:
        src_bins: Source garment color bins
        src_tags: Source garment meta tags  
        cand_bins: Candidate garment color bins
        cand_tags: Candidate garment meta tags
        
    Returns:
        (score: float, reasons: List[str]) - score clamped to 1.0, up to 2 reasons
    """
    score = 0.0
    reasons = []
    
    # Convert to sets for easier operations
    src_bins_set = set(src_bins) & FIXED_BINS  # Only valid bins
    cand_bins_set = set(cand_bins) & FIXED_BINS
    src_tags_set = set(src_tags)
    cand_tags_set = set(cand_tags)
    
    # 1. Complementary colors (+0.6)
    complementary_found = False
    for src_color in src_bins_set:
        for cand_color in cand_bins_set:
            if (src_color, cand_color) in COMPLEMENTARY_PAIRS:
                score += 0.6
                reasons.append(f"complementary colors ({src_color} ↔ {cand_color})")
                complementary_found = True
                break
        if complementary_found:
            break
    
    # 2. Neutral present (+0.4)
    if "neutral" in src_bins_set or "neutral" in cand_bins_set:
        score += 0.4
        reasons.append("neutral pairs with any color")
    
    # 3. Analogous colors (+0.2) - only if no complementary found
    if not complementary_found:
        analogous_found = False
        for src_color in src_bins_set:
            for cand_color in cand_bins_set:
                if (src_color, cand_color) in ANALOGOUS_PAIRS:
                    score += 0.2
                    reasons.append(f"analogous colors ({src_color} ↔ {cand_color})")
                    analogous_found = True
                    break
            if analogous_found:
                break
    
    # 4. Shared tags (+0.1 each, cap +0.2)
    shared_tags = src_tags_set & cand_tags_set
    if shared_tags:
        shared_count = len(shared_tags)
        tag_bonus = min(0.2, 0.1 * shared_count)
        score += tag_bonus
        
        # Show first 2 shared tags in reason
        shared_list = sorted(list(shared_tags))[:2]
        reasons.append(f"shared: {', '.join(shared_list)}")
    
    # Clamp score to 1.0
    final_score = min(1.0, score)
    
    # Return top 2 reasons, or default if none
    final_reasons = reasons[:2] if reasons else ["good color harmony"]
    
    return final_score, final_reasons


def get_opposite_category(category: str) -> str:
    """Get the opposite category for matching"""
    if category == "top":
        return "bottom"
    elif category == "bottom":
        return "top"
    else:
        # one_piece has no opposite
        return None
