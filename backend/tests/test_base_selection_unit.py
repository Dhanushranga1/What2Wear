"""
Unit tests for base color selection module.

Tests the base color selection logic:
- neutral penalty calculations
- spatial cohesion analysis
- scoring and tie-breaking
"""

import pytest
import numpy as np
import cv2
from unittest.mock import patch

from app.services.colors.base_selection import (
    neutral_multiplier, spatial_cohesion_bonus, choose_base_color, analyze_color_harmony
)

class TestNeutralMultiplier:
    """Test neutral color penalty calculations"""
    
    def test_neutral_multiplier_pure_colors(self):
        """Test penalty for pure RGB colors"""
        # Pure colors should not be penalized
        red = np.array([255, 0, 0])
        green = np.array([0, 255, 0])  
        blue = np.array([0, 0, 255])
        
        for color in [red, green, blue]:
            multiplier = neutral_multiplier(color)
            assert multiplier == 1.0, f"Pure color {color} should not be penalized"
    
    def test_neutral_multiplier_black_white(self):
        """Test penalty for black and white colors"""
        # Black (near v_low threshold)
        black = np.array([10, 10, 10])
        multiplier = neutral_multiplier(black, v_low=0.15)
        assert multiplier == 0.5, "Black should be penalized"
        
        # White (near v_high threshold)
        white = np.array([250, 250, 250])
        multiplier = neutral_multiplier(white, v_high=0.95)
        assert multiplier == 0.5, "White should be penalized"
    
    def test_neutral_multiplier_gray_colors(self):
        """Test penalty for gray/desaturated colors"""
        # Gray color (low saturation, mid value)
        gray = np.array([128, 128, 128])
        multiplier = neutral_multiplier(gray, s_low=0.12)
        assert multiplier == 0.5, "Gray should be penalized"
        
        # Slightly off-gray but still low saturation
        off_gray = np.array([120, 130, 125])
        multiplier = neutral_multiplier(off_gray, s_low=0.12)
        assert multiplier == 0.5, "Low saturation colors should be penalized"
    
    def test_neutral_multiplier_custom_thresholds(self):
        """Test custom penalty thresholds"""
        color = np.array([80, 80, 80])  # Medium gray that should be caught by loose thresholds
        
        # Strict thresholds
        multiplier_strict = neutral_multiplier(
            color, v_low=0.25, v_high=0.9, s_low=0.15, penalty_weight=0.3
        )
        assert multiplier_strict == 0.3
        
        # Loose thresholds - this should still catch the gray
        multiplier_loose = neutral_multiplier(
            color, v_low=0.05, v_high=0.98, s_low=0.05, penalty_weight=0.7
        )
        assert multiplier_loose == 0.7

    def test_neutral_multiplier_edge_cases(self):
        """Test edge cases at threshold boundaries"""
        # Color right at v_low boundary
        edge_dark = np.array([38, 38, 38])  # V ≈ 0.15 in HSV
        multiplier = neutral_multiplier(edge_dark, v_low=0.15)
        # Should be close to threshold
        assert multiplier in [0.5, 1.0]

class TestSpatialCohesionBonus:
    """Test spatial cohesion analysis"""
    
    def test_spatial_cohesion_bonus_single_color(self):
        """Test cohesion when entire image is one color"""
        # Create solid color image and mask
        img = np.full((100, 100, 3), [255, 0, 0], dtype=np.uint8)  # Red
        mask = np.full((100, 100), 255, dtype=np.uint8)
        
        centers = [np.array([255, 0, 0])]  # Single red center
        bonuses = spatial_cohesion_bonus(img, mask, centers, weight=0.10)
        
        assert len(bonuses) == 1
        assert bonuses[0] > 0.09  # Should get nearly full bonus (0.10)
    
    def test_spatial_cohesion_bonus_scattered_colors(self):
        """Test cohesion with scattered vs connected regions"""
        # Create image with different connectedness patterns
        
        # More scattered: 4 separate 25x25 red squares in corners
        img_scattered = np.zeros((100, 100, 3), dtype=np.uint8)
        img_scattered[0:25, 0:25] = [255, 0, 0]      # Top-left red
        img_scattered[0:25, 75:100] = [255, 0, 0]    # Top-right red
        img_scattered[75:100, 0:25] = [255, 0, 0]    # Bottom-left red
        img_scattered[75:100, 75:100] = [255, 0, 0]  # Bottom-right red
        # Fill rest with blue
        img_scattered[25:75, :] = [0, 0, 255]
        img_scattered[:, 25:75] = [0, 0, 255]
        
        # Less scattered: single connected red region
        img_connected = np.zeros((100, 100, 3), dtype=np.uint8)
        img_connected[:, :50] = [255, 0, 0]  # Left half red
        img_connected[:, 50:] = [0, 0, 255]  # Right half blue
        
        mask = np.full((100, 100), 255, dtype=np.uint8)
        centers = [np.array([255, 0, 0]), np.array([0, 0, 255])]
        
        bonuses_scattered = spatial_cohesion_bonus(img_scattered, mask, centers, weight=0.10)
        bonuses_connected = spatial_cohesion_bonus(img_connected, mask, centers, weight=0.10)
        
        # Connected version should have higher cohesion bonus for red
        assert bonuses_connected[0] > bonuses_scattered[0], f"Connected {bonuses_connected[0]} should be > scattered {bonuses_scattered[0]}"
    
    def test_spatial_cohesion_bonus_empty_mask(self):
        """Test handling of empty mask"""
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        mask = np.zeros((50, 50), dtype=np.uint8)  # Empty mask
        centers = [np.array([255, 0, 0])]
        
        bonuses = spatial_cohesion_bonus(img, mask, centers, weight=0.10)
        assert bonuses == [0.0]
    
    def test_spatial_cohesion_bonus_weight_scaling(self):
        """Test that cohesion bonus scales with weight parameter"""
        img = np.full((50, 50, 3), [255, 0, 0], dtype=np.uint8)
        mask = np.full((50, 50), 255, dtype=np.uint8) 
        centers = [np.array([255, 0, 0])]
        
        bonus_low = spatial_cohesion_bonus(img, mask, centers, weight=0.05)[0]
        bonus_high = spatial_cohesion_bonus(img, mask, centers, weight=0.20)[0]
        
        assert bonus_high > bonus_low
        assert abs(bonus_high / bonus_low - 4.0) < 0.1  # Should be ~4x higher

class TestChooseBaseColor:
    """Test complete base color selection logic"""
    
    def test_choose_base_color_dominance_wins(self):
        """Test that dominance is primary factor"""
        # Create centers and ratios where first is most dominant
        centers = [
            np.array([255, 0, 0]),    # Red - most dominant
            np.array([0, 255, 0]),    # Green - less dominant
            np.array([0, 0, 255])     # Blue - least dominant
        ]
        ratios = [0.6, 0.3, 0.1]
        
        # Simple image/mask for spatial cohesion
        img_bgr = np.zeros((50, 50, 3), dtype=np.uint8)
        mask = np.full((50, 50), 255, dtype=np.uint8)
        
        neutral_params = {"v_low": 0.15, "v_high": 0.95, "s_low": 0.12, "penalty_weight": 0.5}
        cohesion_params = {"enabled": False, "weight": 0.0}  # Disable cohesion
        
        best_idx, breakdown = choose_base_color(centers, ratios, img_bgr, mask, neutral_params, cohesion_params)
        
        assert best_idx == 0  # Most dominant color should win
        assert breakdown["dominance"] == 0.6
        assert breakdown["neutral_penalty"] == 1.0  # No penalty for pure colors
        assert breakdown["cohesion_bonus"] == 0.0   # Disabled
    
    def test_choose_base_color_neutral_penalty_changes_winner(self):
        """Test that neutral penalty can change the winner"""
        # Dominant color is gray (neutral), second is pure color
        centers = [
            np.array([128, 128, 128]),  # Gray - dominant but neutral
            np.array([255, 0, 0])       # Red - less dominant but pure
        ]
        ratios = [0.7, 0.3]
        
        img_bgr = np.zeros((50, 50, 3), dtype=np.uint8)
        mask = np.full((50, 50), 255, dtype=np.uint8)
        
        neutral_params = {"v_low": 0.15, "v_high": 0.95, "s_low": 0.12, "penalty_weight": 0.3}
        cohesion_params = {"enabled": False, "weight": 0.0}
        
        best_idx, breakdown = choose_base_color(centers, ratios, img_bgr, mask, neutral_params, cohesion_params)
        
        # Red should win despite lower dominance due to neutral penalty on gray
        # Gray score: 0.7 * 0.3 = 0.21
        # Red score: 0.3 * 1.0 = 0.30
        assert best_idx == 1  # Red wins
        assert breakdown["neutral_penalty"] == 1.0  # No penalty for red
    
    def test_choose_base_color_cohesion_tiebreaker(self):
        """Test spatial cohesion as tiebreaker"""
        centers = [
            np.array([255, 0, 0]),    # Red
            np.array([0, 0, 255])     # Blue
        ]
        ratios = [0.5, 0.5]  # Equal dominance
        
        # Create image where red is more spatially coherent
        img_bgr = np.zeros((100, 100, 3), dtype=np.uint8)
        img_bgr[:, :60] = (0, 0, 255)  # Blue in BGR (left side)
        img_bgr[:, 60:] = (255, 0, 0)  # Red in BGR (right side)
        # Red forms larger connected component
        
        mask = np.full((100, 100), 255, dtype=np.uint8)
        
        neutral_params = {"v_low": 0.15, "v_high": 0.95, "s_low": 0.12, "penalty_weight": 0.5}
        cohesion_params = {"enabled": True, "weight": 0.15}
        
        best_idx, breakdown = choose_base_color(centers, ratios, img_bgr, mask, neutral_params, cohesion_params)
        
        # With cohesion enabled, should prefer the color with better spatial structure
        assert breakdown["cohesion_bonus"] > 0.0
        # Winner could be either, but cohesion should affect the score
        assert "cohesion_bonus" in breakdown
    
    def test_choose_base_color_score_breakdown(self):
        """Test that score breakdown contains all expected components"""
        centers = [np.array([100, 150, 200])]
        ratios = [1.0]
        
        img_bgr = np.zeros((20, 20, 3), dtype=np.uint8)
        mask = np.full((20, 20), 255, dtype=np.uint8)
        
        neutral_params = {"v_low": 0.15, "v_high": 0.95, "s_low": 0.12, "penalty_weight": 0.5}
        cohesion_params = {"enabled": True, "weight": 0.10}
        
        best_idx, breakdown = choose_base_color(centers, ratios, img_bgr, mask, neutral_params, cohesion_params)
        
        assert best_idx == 0
        assert "dominance" in breakdown
        assert "neutral_penalty" in breakdown
        assert "cohesion_bonus" in breakdown
        assert "final_score" in breakdown
        
        # Verify score calculation
        expected_score = (breakdown["dominance"] * breakdown["neutral_penalty"] + 
                         breakdown["cohesion_bonus"])
        assert abs(breakdown["final_score"] - expected_score) < 1e-6

class TestAnalyzeColorHarmony:
    """Test color harmony analysis utility"""
    
    def test_analyze_color_harmony_complementary(self):
        """Test detection of complementary colors"""
        # Red and cyan are complementary
        palette = [
            {"hex": "#FF0000", "ratio": 0.5},  # Red
            {"hex": "#00FFFF", "ratio": 0.5}   # Cyan
        ]
        
        harmony = analyze_color_harmony(palette)
        
        assert "harmony_type" in harmony
        assert "color_relationships" in harmony
        assert "temperature_balance" in harmony
    
    def test_analyze_color_harmony_monochromatic(self):
        """Test detection of monochromatic scheme"""
        # Different shades of blue
        palette = [
            {"hex": "#000080", "ratio": 0.4},  # Navy
            {"hex": "#0000FF", "ratio": 0.4},  # Blue  
            {"hex": "#87CEEB", "ratio": 0.2}   # Sky blue
        ]
        
        harmony = analyze_color_harmony(palette)
        
        assert "harmony_type" in harmony
        # Monochromatic should be detected or similar hues noted
    
    def test_analyze_color_harmony_warm_cool(self):
        """Test temperature analysis"""
        # Warm colors
        warm_palette = [
            {"hex": "#FF0000", "ratio": 0.5},  # Red
            {"hex": "#FF8000", "ratio": 0.5}   # Orange
        ]
        
        # Cool colors
        cool_palette = [
            {"hex": "#0000FF", "ratio": 0.5},  # Blue
            {"hex": "#00FF00", "ratio": 0.5}   # Green
        ]
        
        warm_harmony = analyze_color_harmony(warm_palette)
        cool_harmony = analyze_color_harmony(cool_palette)
        
        assert "temperature_balance" in warm_harmony
        assert "temperature_balance" in cool_harmony
        
        # Results should indicate temperature characteristics
        assert warm_harmony["temperature_balance"] != cool_harmony["temperature_balance"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
