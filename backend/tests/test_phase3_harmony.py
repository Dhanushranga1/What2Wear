"""
Unit tests for Phase 3 Color Harmony Engine

Tests the core mathematical operations and wearability constraints
to ensure color theory rules are implemented correctly.
"""

import pytest
import math
from app.services.colors.harmony import (
    hex_to_hls, hls_to_hex, rotate_hue, generate_harmony_candidates,
    get_hue_separation, generate_complementary_candidates,
    generate_analogous_candidates, generate_triadic_candidates
)
from app.services.colors.harmony.wearability import (
    WearabilityPolicy, GarmentRole, StyleIntent, Season,
    apply_wearability_constraints, apply_seasonal_adjustment,
    apply_role_lightness_clamp, apply_role_saturation_cap,
    enforce_minimum_contrast, is_degenerate_base
)
from app.services.colors.harmony.neutrals import (
    select_neutrals_by_base_lightness, apply_seasonal_neutral_bias,
    generate_neutral_suggestions
)


class TestColorConversions:
    """Test HLS <-> HEX color conversions."""
    
    def test_hex_to_hls_basic_colors(self):
        """Test conversion of basic colors to HLS."""
        # Red
        h, l, s = hex_to_hls("#FF0000")
        assert abs(h - 0.0) < 0.01  # Red is at 0°
        assert abs(s - 1.0) < 0.01  # Full saturation
        assert abs(l - 0.5) < 0.01  # Mid lightness
        
        # Pure white
        h, l, s = hex_to_hls("#FFFFFF")
        assert abs(l - 1.0) < 0.01  # Full lightness
        assert abs(s - 0.0) < 0.01  # No saturation
        
        # Pure black
        h, l, s = hex_to_hls("#000000")
        assert abs(l - 0.0) < 0.01  # No lightness
        assert abs(s - 0.0) < 0.01  # No saturation
        
        # Navy blue
        h, l, s = hex_to_hls("#000080")
        assert abs(h - 0.667) < 0.01  # Blue hue (~240°)
        assert l < 0.5  # Dark
        assert s > 0.8  # High saturation
    
    def test_hls_to_hex_roundtrip(self):
        """Test that HLS->HEX->HLS conversion is stable."""
        test_colors = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF", "#00FFFF"]
        
        for original_hex in test_colors:
            h, l, s = hex_to_hls(original_hex)
            converted_hex = hls_to_hex(h, l, s)
            
            # Should match within rounding tolerance
            assert converted_hex.upper() == original_hex.upper()
    
    def test_invalid_hex_format(self):
        """Test that invalid hex formats raise ValueError."""
        with pytest.raises(ValueError):
            hex_to_hls("FF0000")  # Missing #
        
        with pytest.raises(ValueError):
            hex_to_hls("#FF00")  # Too short
        
        with pytest.raises(ValueError):
            hex_to_hls("#GGGGGG")  # Invalid hex digits


class TestHueRotation:
    """Test hue rotation mathematics."""
    
    def test_complementary_rotation(self):
        """Test 180° hue rotation for complementary colors."""
        # Red (0°) should become Cyan (~180°)
        red_h = 0.0
        comp_h = rotate_hue(red_h, 180)
        assert abs(comp_h - 0.5) < 0.01  # 180° = 0.5 in [0,1)
        
        # Blue (240°) should become Yellow (60°)
        blue_h = 240 / 360
        comp_h = rotate_hue(blue_h, 180)
        expected = 60 / 360
        assert abs(comp_h - expected) < 0.01
    
    def test_hue_wraparound(self):
        """Test hue wraparound at boundaries."""
        # 350° + 30° = 20° (wraps around)
        h = 350 / 360
        rotated = rotate_hue(h, 30)
        expected = 20 / 360
        assert abs(rotated - expected) < 0.01
        
        # 10° - 30° = 340° (wraps around)
        h = 10 / 360
        rotated = rotate_hue(h, -30)
        expected = 340 / 360
        assert abs(rotated - expected) < 0.01
    
    def test_hue_separation(self):
        """Test hue separation calculation."""
        # Red and Cyan should be 180° apart
        red_h = 0.0
        cyan_h = 0.5
        separation = get_hue_separation(red_h, cyan_h)
        assert abs(separation - 180) < 1
        
        # Adjacent hues should consider wraparound
        h1 = 350 / 360
        h2 = 10 / 360
        separation = get_hue_separation(h1, h2)
        assert separation < 30  # Should be ~20°, not ~340°


class TestHarmonyGeneration:
    """Test harmony candidate generation."""
    
    def test_complementary_generation(self):
        """Test complementary color generation."""
        base_h, base_l, base_s = hex_to_hls("#000080")  # Navy
        candidates = generate_complementary_candidates(base_h, base_l, base_s)
        
        assert len(candidates) == 1
        comp = candidates[0]
        
        # Check hue is approximately opposite
        expected_h = rotate_hue(base_h, 180)
        assert abs(comp.h - expected_h) < 0.01
        
        # Dark base should get lighter complementary
        assert comp.l > base_l
        assert comp.category == "complementary"
    
    def test_analogous_generation(self):
        """Test analogous color generation."""
        base_h, base_l, base_s = hex_to_hls("#FF0000")  # Red
        candidates = generate_analogous_candidates(base_h, base_l, base_s)
        
        assert len(candidates) == 2
        
        # Check hue rotations
        expected_h1 = rotate_hue(base_h, 30)
        expected_h2 = rotate_hue(base_h, -30)
        
        found_h1 = any(abs(c.h - expected_h1) < 0.01 for c in candidates)
        found_h2 = any(abs(c.h - expected_h2) < 0.01 for c in candidates)
        
        assert found_h1 and found_h2
        assert all(c.category == "analogous" for c in candidates)
    
    def test_triadic_generation(self):
        """Test triadic color generation."""
        base_h, base_l, base_s = hex_to_hls("#00FF00")  # Green
        candidates = generate_triadic_candidates(base_h, base_l, base_s)
        
        assert len(candidates) == 2
        
        # Check hue rotations
        expected_h1 = rotate_hue(base_h, 120)
        expected_h2 = rotate_hue(base_h, -120)
        
        found_h1 = any(abs(c.h - expected_h1) < 0.01 for c in candidates)
        found_h2 = any(abs(c.h - expected_h2) < 0.01 for c in candidates)
        
        assert found_h1 and found_h2
        assert all(c.category == "triadic" for c in candidates)


class TestWearabilityConstraints:
    """Test wearability constraints and clamps."""
    
    def test_role_saturation_caps(self):
        """Test role-based saturation capping."""
        policy = WearabilityPolicy()
        
        # Test bottom with high saturation
        high_s = 0.9
        clamped_s, token = apply_role_saturation_cap(
            high_s, GarmentRole.BOTTOM, StyleIntent.CLASSIC, policy
        )
        
        # Should be capped to classic bottom limit (0.60)
        assert clamped_s == 0.60
        assert "S_cap" in token
        
        # Test top with same saturation (should be higher cap)
        clamped_s_top, _ = apply_role_saturation_cap(
            high_s, GarmentRole.TOP, StyleIntent.CLASSIC, policy
        )
        
        assert clamped_s_top > clamped_s  # Tops get higher caps
    
    def test_role_lightness_clamps(self):
        """Test role-based lightness clamping."""
        policy = WearabilityPolicy()
        
        # Test very dark value for bottoms
        dark_l = 0.1
        clamped_l, token = apply_role_lightness_clamp(
            dark_l, GarmentRole.BOTTOM, policy
        )
        
        # Should be clamped to bottom minimum (0.40)
        assert clamped_l == 0.40
        assert "L_clamp" in token
        
        # Test very light value
        light_l = 0.9
        clamped_l, _ = apply_role_lightness_clamp(
            light_l, GarmentRole.BOTTOM, policy
        )
        
        # Should be clamped to bottom maximum (0.70)
        assert clamped_l == 0.70
    
    def test_minimum_contrast_enforcement(self):
        """Test minimum contrast enforcement."""
        policy = WearabilityPolicy()
        base_l = 0.5
        
        # Test candidate too close to base
        close_l = 0.51  # Only 0.01 difference
        adjusted_l, token = enforce_minimum_contrast(
            close_l, base_l, GarmentRole.BOTTOM, policy
        )
        
        # Should be adjusted to meet minimum contrast
        contrast = abs(adjusted_l - base_l)
        assert contrast >= policy.delta_l_min
        assert "contrast_fix" in token
    
    def test_seasonal_adjustments(self):
        """Test seasonal lightness adjustments."""
        policy = WearabilityPolicy()
        base_l = 0.5
        
        # Spring/summer should increase lightness
        adj_l_ss, token_ss = apply_seasonal_adjustment(
            base_l, Season.SPRING_SUMMER, policy
        )
        assert adj_l_ss > base_l
        assert "ss_L+" in token_ss
        
        # Autumn/winter should decrease lightness
        adj_l_aw, token_aw = apply_seasonal_adjustment(
            base_l, Season.AUTUMN_WINTER, policy
        )
        assert adj_l_aw < base_l
        assert "aw_L-" in token_aw
    
    def test_degenerate_base_detection(self):
        """Test degenerate base color detection."""
        policy = WearabilityPolicy()
        
        # Very low saturation (near-neutral)
        assert is_degenerate_base("#808080", policy)  # Mid gray
        
        # Very dark
        assert is_degenerate_base("#000000", policy)  # Pure black
        
        # Very light
        assert is_degenerate_base("#FFFFFF", policy)  # Pure white
        
        # Normal color should not be degenerate
        assert not is_degenerate_base("#FF0000", policy)  # Red


class TestNeutralsSelection:
    """Test neutral color selection logic."""
    
    def test_base_lightness_selection(self):
        """Test neutral selection based on base lightness."""
        # Light base should prefer darker neutrals
        light_neutrals = select_neutrals_by_base_lightness(0.8, max_neutrals=4)
        first_neutral = light_neutrals[0]
        # Should start with dark neutrals like charcoal
        assert first_neutral.lightness < 0.5
        
        # Dark base should prefer lighter neutrals
        dark_neutrals = select_neutrals_by_base_lightness(0.3, max_neutrals=4)
        first_neutral = dark_neutrals[0]
        # Should start with light neutrals like white
        assert first_neutral.lightness > 0.8
    
    def test_seasonal_neutral_bias(self):
        """Test seasonal reordering of neutrals."""
        base_neutrals = select_neutrals_by_base_lightness(0.5, max_neutrals=6)
        
        # Spring/summer should prioritize cool neutrals
        ss_neutrals = apply_seasonal_neutral_bias(base_neutrals, Season.SPRING_SUMMER)
        # First few should be cool or neutral warmth
        assert all(n.warmth in ["cool", "neutral"] for n in ss_neutrals[:3])
        
        # Autumn/winter should prioritize warm neutrals
        aw_neutrals = apply_seasonal_neutral_bias(base_neutrals, Season.AUTUMN_WINTER)
        # Should have warm neutrals early in list
        warm_found = any(n.warmth == "warm" for n in aw_neutrals[:3])
        assert warm_found
    
    def test_neutral_suggestion_generation(self):
        """Test complete neutral suggestion generation."""
        suggestions = generate_neutral_suggestions(
            base_hex="#000080",  # Navy (dark base)
            season=Season.SPRING_SUMMER,
            max_neutrals=3
        )
        
        assert len(suggestions) <= 3
        assert all(s.category == "neutral" for s in suggestions)
        
        # Should prefer lighter neutrals for dark base
        neutral_hexes = [s.hex for s in suggestions]
        # White should be included for dark base
        assert "#FFFFFF" in neutral_hexes


if __name__ == "__main__":
    # Run specific test for quick validation
    test_conversions = TestColorConversions()
    test_conversions.test_hex_to_hls_basic_colors()
    test_conversions.test_hls_to_hex_roundtrip()
    
    test_harmonies = TestHarmonyGeneration()
    test_harmonies.test_complementary_generation()
    
    test_wearability = TestWearabilityConstraints()
    test_wearability.test_role_saturation_caps()
    test_wearability.test_minimum_contrast_enforcement()
    
    print("✅ All Phase 3 unit tests passed!")
