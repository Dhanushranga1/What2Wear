"""
Unit tests for color extraction module.

Tests the core color extraction pipeline components:
- pixel sampling with HSV filtering
- MiniBatchKMeans clustering 
- palette generation with deterministic results
"""

import pytest
import numpy as np
import cv2
import base64
from pathlib import Path

from app.services.colors.extraction import (
    sample_garment_pixels, cluster_palette, rgb_to_hex, decode_base64_image,
    validate_mask_binary, validate_dimensions_match, process_rgba_to_rgb_and_mask
)

class TestRgbToHex:
    """Test RGB to hex conversion utility"""
    
    def test_rgb_to_hex_basic_colors(self):
        """Test conversion of basic RGB colors to hex"""
        assert rgb_to_hex(np.array([255, 0, 0])) == "#FF0000"  # Red
        assert rgb_to_hex(np.array([0, 255, 0])) == "#00FF00"  # Green  
        assert rgb_to_hex(np.array([0, 0, 255])) == "#0000FF"  # Blue
        assert rgb_to_hex(np.array([0, 0, 0])) == "#000000"    # Black
        assert rgb_to_hex(np.array([255, 255, 255])) == "#FFFFFF"  # White
    
    def test_rgb_to_hex_custom_colors(self):
        """Test conversion of specific project colors"""
        # Test colors from synthetic assets
        assert rgb_to_hex(np.array([31, 78, 121])) == "#1F4E79"    # Blue
        assert rgb_to_hex(np.array([211, 181, 143])) == "#D3B58F"  # Camel
        assert rgb_to_hex(np.array([45, 117, 96])) == "#2D7560"   # Teal
        assert rgb_to_hex(np.array([10, 42, 67])) == "#0A2A43"    # Navy

class TestDecodeBase64Image:
    """Test base64 image decoding"""
    
    def test_decode_base64_image_png(self):
        """Test decoding of a simple PNG image"""
        # Create a small test image
        test_img = np.zeros((32, 32, 3), dtype=np.uint8)
        test_img[:, :] = (100, 150, 200)  # BGR
        
        # Encode to PNG base64
        success, buffer = cv2.imencode('.png', test_img)
        assert success
        b64_str = base64.b64encode(buffer).decode('ascii')
        
        # Decode and verify
        decoded = decode_base64_image(b64_str)
        assert decoded.shape == (32, 32, 3)
        np.testing.assert_array_equal(decoded, test_img)
    
    def test_decode_base64_image_invalid(self):
        """Test handling of invalid base64 data"""
        with pytest.raises(Exception):
            decode_base64_image("invalid_base64_data")

class TestValidateMaskBinary:
    """Test mask validation utilities"""
    
    def test_validate_mask_binary_valid(self):
        """Test validation of proper binary masks"""
        # Valid binary mask (0 and 255 only)
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[25:75, 25:75] = 255
        
        validated = validate_mask_binary(mask)
        assert validated.shape == (100, 100)
        assert validated.dtype == np.uint8
        assert np.all((validated == 0) | (validated == 255))
    
    def test_validate_mask_binary_grayscale_input(self):
        """Test handling of grayscale input that needs conversion"""
        # Create grayscale mask with intermediate values
        mask = np.ones((50, 50, 3), dtype=np.uint8) * 128
        mask[10:40, 10:40] = 255
        
        validated = validate_mask_binary(mask)
        assert validated.shape == (50, 50)
        assert validated.dtype == np.uint8

class TestPixelSampling:
    """Test pixel sampling and filtering pipeline"""
    
    @pytest.fixture
    def simple_test_image(self):
        """Create a simple test image with known colors"""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        # Left half blue, right half red
        img[:, :50] = (255, 0, 0)  # Blue in BGR
        img[:, 50:] = (0, 0, 255)  # Red in BGR
        return img
    
    @pytest.fixture  
    def simple_test_mask(self):
        """Create a simple test mask"""
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:80, 20:80] = 255  # Central region
        return mask
    
    def test_sample_garment_pixels_basic(self, simple_test_image, simple_test_mask):
        """Test basic pixel sampling without filters"""
        pixels = sample_garment_pixels(
            item_bgr=simple_test_image,
            mask_u8=simple_test_mask,
            erode_px=0,
            gamma=1.0,  # No gamma correction
            max_samples=5000,  # Increase to ensure enough pixels
            shadow_v_lt=0.0,  # No shadow filter
            spec_s_lt=0.0,    # No specular filter
            spec_v_gt=1.0,    # No specular filter
            min_saturation=0.0,  # No saturation filter
            rng_seed=42
        )
        
        assert pixels.shape[1] == 3  # RGB pixels
        assert pixels.dtype == np.uint8
        assert len(pixels) > 0
        
        # Should contain both blue and red pixels
        unique_colors = np.unique(pixels.reshape(-1, 3), axis=0)
        assert len(unique_colors) >= 2
    
    def test_sample_garment_pixels_with_erosion(self, simple_test_image, simple_test_mask):
        """Test pixel sampling with mask erosion"""
        pixels_no_erode = sample_garment_pixels(
            simple_test_image, simple_test_mask, erode_px=0, 
            gamma=1.0, max_samples=5000, rng_seed=42
        )
        
        pixels_with_erode = sample_garment_pixels(
            simple_test_image, simple_test_mask, erode_px=2,
            gamma=1.0, max_samples=5000, rng_seed=42
        )
        
        # Erosion should reduce number of available pixels
        assert len(pixels_with_erode) < len(pixels_no_erode)
    
    def test_sample_garment_pixels_max_samples_limit(self, simple_test_image, simple_test_mask):
        """Test that max_samples limit is respected"""
        max_samples = 500  # Increase to meet minimum requirements
        pixels = sample_garment_pixels(
            simple_test_image, simple_test_mask, 
            max_samples=max_samples, rng_seed=42
        )
        
        assert len(pixels) <= max_samples
    
    def test_sample_garment_pixels_shadow_filter(self):
        """Test shadow filtering removes dark pixels"""
        # Create image with dark and bright regions
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[:50, :] = (10, 10, 10)    # Dark region (shadow)
        img[50:, :] = (200, 200, 200) # Bright region
        
        mask = np.full((100, 100), 255, dtype=np.uint8)
        
        # With shadow filter
        pixels = sample_garment_pixels(
            img, mask, shadow_v_lt=0.15, gamma=1.0, rng_seed=42
        )
        
        # Convert to HSV to check V values
        hsv = cv2.cvtColor(pixels.reshape(-1, 1, 3), cv2.COLOR_RGB2HSV)
        v_values = hsv[:, 0, 2] / 255.0
        
        # All remaining pixels should have V >= 0.15
        assert np.all(v_values >= 0.15)

class TestClusterPalette:
    """Test MiniBatchKMeans clustering for palette generation"""
    
    def test_cluster_palette_deterministic(self):
        """Test that clustering produces deterministic results"""
        # Create test pixels with two distinct colors
        pixels = np.vstack([
            np.full((100, 3), [255, 0, 0], dtype=np.uint8),  # Red
            np.full((100, 3), [0, 0, 255], dtype=np.uint8)   # Blue
        ])
        
        # Run clustering twice with same seed
        palette1, centers1, ratios1, indices1 = cluster_palette(pixels, k=2, rng_seed=42)
        palette2, centers2, ratios2, indices2 = cluster_palette(pixels, k=2, rng_seed=42)
        
        # Results should be identical
        assert palette1 == palette2
        np.testing.assert_array_equal(centers1, centers2)
        np.testing.assert_array_equal(ratios1, ratios2)
        assert indices1 == indices2
    
    def test_cluster_palette_two_colors(self):
        """Test clustering on two distinct colors"""
        # Create pixels: 75% red, 25% blue
        red_pixels = np.full((150, 3), [255, 0, 0], dtype=np.uint8)
        blue_pixels = np.full((50, 3), [0, 0, 255], dtype=np.uint8)
        pixels = np.vstack([red_pixels, blue_pixels])
        
        palette, centers, ratios, indices = cluster_palette(pixels, k=2, rng_seed=42)
        
        assert len(palette) == 2
        assert len(centers) == 2
        assert len(ratios) == 2
        
        # Palette should be sorted by dominance (red first)
        assert ratios[0] > ratios[1]
        assert abs(ratios[0] - 0.75) < 0.05  # ~75% red
        assert abs(ratios[1] - 0.25) < 0.05  # ~25% blue
        
        # Check hex colors (allow small variations due to clustering)
        hex_colors = [entry["hex"] for entry in palette]
        
        # Check if colors are close to expected values
        found_red = any(color_hex_distance(hex_color, "#FF0000") < 10 for hex_color in hex_colors)
        found_blue = any(color_hex_distance(hex_color, "#0000FF") < 10 for hex_color in hex_colors)
        
        assert found_red, f"Red color not found in {hex_colors}"
        assert found_blue, f"Blue color not found in {hex_colors}"
    
    def test_cluster_palette_insufficient_pixels(self):
        """Test handling of insufficient pixels for clustering"""
        # Very few pixels for k=5
        pixels = np.array([[255, 0, 0], [0, 255, 0]], dtype=np.uint8)
        
        with pytest.raises(RuntimeError):
            cluster_palette(pixels, k=5, rng_seed=42)

class TestSyntheticAssets:
    """Test color extraction on synthetic test assets"""
    
    @pytest.fixture
    def assets_dir(self):
        """Get path to test assets directory"""
        return Path(__file__).parent / "assets"
    
    def test_two_blocks_extraction(self, assets_dir):
        """Test extraction on two_blocks.png synthetic asset"""
        img_path = assets_dir / "two_blocks.png"
        mask_path = assets_dir / "two_blocks_mask.png"
        
        if not img_path.exists() or not mask_path.exists():
            pytest.skip("Synthetic assets not found - run generate_synthetic_assets.py")
        
        # Load test data
        img_bgr = cv2.imread(str(img_path))
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        
        assert img_bgr is not None
        assert mask is not None
        
        # Extract pixels and cluster
        pixels = sample_garment_pixels(
            img_bgr, mask, gamma=1.0, max_samples=10000, rng_seed=42
        )
        
        palette, centers, ratios, indices = cluster_palette(pixels, k=2, rng_seed=42)
        
        # Should find 2 dominant colors with roughly equal ratios
        assert len(palette) == 2
        assert abs(ratios[0] - 0.5) < 0.1  # ~50% dominant color
        assert abs(ratios[1] - 0.5) < 0.1  # ~50% second color
        
        # Check that expected colors are found (blue and camel)
        hex_colors = [entry["hex"] for entry in palette]
        # Allow some tolerance in color detection
        expected_colors = {"#1F4E79", "#D3B58F"}  # Blue, Camel
        
        # At least one of the expected colors should be close
        found_expected = False
        for hex_color in hex_colors:
            for expected in expected_colors:
                if color_hex_distance(hex_color, expected) < 30:  # RGB distance threshold
                    found_expected = True
                    break
        assert found_expected, f"Expected colors not found in {hex_colors}"
    
    def test_logo_on_shirt_extraction(self, assets_dir):
        """Test extraction on logo_on_shirt.png - base color should be navy"""
        img_path = assets_dir / "logo_on_shirt.png"
        mask_path = assets_dir / "logo_on_shirt_mask.png"
        
        if not img_path.exists() or not mask_path.exists():
            pytest.skip("Synthetic assets not found")
        
        img_bgr = cv2.imread(str(img_path))
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        
        pixels = sample_garment_pixels(
            img_bgr, mask, gamma=1.0, max_samples=10000, rng_seed=42
        )
        
        palette, centers, ratios, indices = cluster_palette(pixels, k=2, rng_seed=42)
        
        # Navy should be dominant (~98.4%), white should be minor (~1.6%)
        assert ratios[0] > 0.9  # Navy dominant
        assert ratios[1] < 0.1  # White minor
        
        # Most dominant color should be close to navy
        dominant_hex = palette[0]["hex"]
        navy_distance = color_hex_distance(dominant_hex, "#0A2A43")
        assert navy_distance < 30, f"Dominant color {dominant_hex} not close to navy #0A2A43"

def color_hex_distance(hex1, hex2):
    """Calculate RGB distance between two hex colors"""
    def hex_to_rgb(hex_str):
        hex_str = hex_str.lstrip('#')
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    
    rgb1 = np.array(hex_to_rgb(hex1))
    rgb2 = np.array(hex_to_rgb(hex2))
    return np.linalg.norm(rgb1 - rgb2)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
