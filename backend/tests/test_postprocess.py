"""
Test post-processing functions.
"""
import pytest
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from app.services.segmentation.postprocess import (
    clean_mask, tight_bbox, cutout_rgba, calculate_mask_area_ratio,
    validate_mask_quality, fill_holes
)


def test_calculate_mask_area_ratio():
    """Test mask area ratio calculation."""
    # Create test mask: 100x100 with 50x50 white square
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[25:75, 25:75] = 255
    
    ratio = calculate_mask_area_ratio(mask)
    expected_ratio = (50 * 50) / (100 * 100)  # 0.25
    
    assert abs(ratio - expected_ratio) < 0.01


def test_validate_mask_quality():
    """Test mask quality validation."""
    # Good mask (25% area)
    good_mask = np.zeros((100, 100), dtype=np.uint8)
    good_mask[25:75, 25:75] = 255
    assert validate_mask_quality(good_mask)
    
    # Too small mask (1% area)
    small_mask = np.zeros((100, 100), dtype=np.uint8)
    small_mask[48:52, 48:52] = 255
    assert not validate_mask_quality(small_mask)
    
    # Too large mask (99% area)
    large_mask = np.ones((100, 100), dtype=np.uint8) * 255
    large_mask[0:2, 0:2] = 0  # Small black corner
    assert not validate_mask_quality(large_mask)


def test_tight_bbox():
    """Test bounding box calculation."""
    # Create mask with known bounding box
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[20:60, 30:80] = 255  # Rectangle from (30,20) to (80,60)
    
    x, y, w, h = tight_bbox(mask)
    
    assert x == 30
    assert y == 20
    assert w == 50  # 80 - 30
    assert h == 40  # 60 - 20


def test_tight_bbox_empty_mask():
    """Test bounding box with empty mask."""
    mask = np.zeros((100, 100), dtype=np.uint8)
    
    with pytest.raises(ValueError, match="Mask is empty"):
        tight_bbox(mask)


@pytest.mark.skipif(cv2 is None, reason="OpenCV not available")
def test_clean_mask():
    """Test mask cleaning operations."""
    # Create noisy mask with small holes
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[20:80, 20:80] = 255
    
    # Add some noise (small holes)
    mask[30:32, 30:32] = 0
    mask[50:52, 50:52] = 0
    
    cleaned = clean_mask(mask, kernel=3, blur=3)
    
    # Cleaned mask should be same size
    assert cleaned.shape == mask.shape
    
    # Should be binary
    assert np.all((cleaned == 0) | (cleaned == 255))
    
    # Should have filled some holes (more non-zero pixels)
    assert np.count_nonzero(cleaned) >= np.count_nonzero(mask)


@pytest.mark.skipif(cv2 is None, reason="OpenCV not available")
def test_fill_holes():
    """Test hole filling functionality."""
    # Create mask with hole in center
    mask = np.zeros((50, 50), dtype=np.uint8)
    
    # Outer rectangle
    mask[10:40, 10:40] = 255
    
    # Inner hole
    mask[20:30, 20:30] = 0
    
    filled = fill_holes(mask)
    
    # Should fill the hole
    assert np.count_nonzero(filled) > np.count_nonzero(mask)
    
    # Center should now be filled
    assert filled[25, 25] == 255


@pytest.mark.skipif(cv2 is None, reason="OpenCV not available")
def test_cutout_rgba():
    """Test RGBA cutout generation."""
    # Create test image and mask
    img_bgr = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[25:75, 25:75] = 255
    
    rgba = cutout_rgba(img_bgr, mask)
    
    # Check shape
    assert rgba.shape == (100, 100, 4)
    
    # Check alpha channel matches mask
    assert np.array_equal(rgba[:, :, 3], mask)
    
    # Check RGB conversion (should be different from BGR)
    # Note: BGR to RGB conversion means B and R channels are swapped
    assert np.array_equal(rgba[:, :, 0], img_bgr[:, :, 2])  # R = B
    assert np.array_equal(rgba[:, :, 2], img_bgr[:, :, 0])  # B = R


def test_cutout_rgba_dimension_mismatch():
    """Test RGBA cutout with mismatched dimensions."""
    img_bgr = np.zeros((100, 100, 3), dtype=np.uint8)
    mask = np.zeros((50, 50), dtype=np.uint8)  # Different size
    
    with pytest.raises(ValueError, match="Image and mask dimensions must match"):
        cutout_rgba(img_bgr, mask)
