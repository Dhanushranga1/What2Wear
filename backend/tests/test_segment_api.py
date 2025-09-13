"""
Test segmentation API endpoints.
"""
import base64
import io
import os
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient

try:
    import cv2
    import numpy as np
    from PIL import Image
except ImportError:
    cv2 = None
    np = None
    Image = None


@pytest.fixture
def simple_test_image():
    """Create a simple test image in memory."""
    if Image is None:
        pytest.skip("PIL not available")
    
    # Create a simple 300x200 image with a purple rectangle on gray background
    img = Image.new('RGB', (300, 200), color=(240, 240, 240))  # Light gray background
    
    # Draw a purple rectangle (simulating garment)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 40, 250, 160], fill=(120, 80, 160))  # Purple rectangle
    
    # Convert to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    
    return img_bytes


@pytest.fixture  
def complex_test_image():
    """Create a complex test image in memory."""
    if Image is None:
        pytest.skip("PIL not available")
    
    # Create a more complex shape
    img = Image.new('RGB', (400, 300), color=(50, 50, 50))  # Dark background
    
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    
    # Main body
    draw.rectangle([100, 80, 300, 220], fill=(80, 140, 200))
    # Sleeves  
    draw.rectangle([70, 120, 100, 180], fill=(80, 140, 200))
    draw.rectangle([300, 120, 330, 180], fill=(80, 140, 200))
    
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    
    return img_bytes


def test_segment_simple_image(test_client, simple_test_image):
    """Test segmentation with simple image."""
    files = {"file": ("test.jpg", simple_test_image, "image/jpeg")}
    
    response = test_client.post("/stylesync/segment", files=files)
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "engine" in data
    assert "width" in data
    assert "height" in data
    assert "mask_area_ratio" in data
    assert "fallback_used" in data
    assert "artifacts" in data
    assert "debug" in data
    
    # Check artifacts
    artifacts = data["artifacts"]
    assert "mask_png_b64" in artifacts
    assert "item_rgba_png_b64" in artifacts
    assert "bbox_xywh" in artifacts
    
    # Validate mask area ratio is reasonable
    mask_ratio = data["mask_area_ratio"]
    assert 0.05 <= mask_ratio <= 0.95, f"Mask ratio {mask_ratio} outside acceptable range"
    
    # Validate bounding box
    bbox = artifacts["bbox_xywh"]
    assert len(bbox) == 4
    assert all(isinstance(x, int) for x in bbox)
    assert bbox[0] >= 0  # x
    assert bbox[1] >= 0  # y
    assert bbox[2] > 0   # width
    assert bbox[3] > 0   # height
    assert bbox[0] + bbox[2] <= data["width"]
    assert bbox[1] + bbox[3] <= data["height"]
    
    # Validate base64 encoded images can be decoded
    try:
        mask_bytes = base64.b64decode(artifacts["mask_png_b64"])
        rgba_bytes = base64.b64decode(artifacts["item_rgba_png_b64"])
        assert len(mask_bytes) > 0
        assert len(rgba_bytes) > 0
    except Exception as e:
        pytest.fail(f"Failed to decode base64 images: {e}")


def test_segment_complex_image(test_client, complex_test_image):
    """Test segmentation with complex image."""
    files = {"file": ("test.jpg", complex_test_image, "image/jpeg")}
    
    response = test_client.post("/stylesync/segment", files=files)
    
    assert response.status_code == 200
    data = response.json()
    
    # Should still produce reasonable results
    mask_ratio = data["mask_area_ratio"]
    assert 0.05 <= mask_ratio <= 0.95


def test_segment_with_parameters(test_client, simple_test_image):
    """Test segmentation with custom parameters."""
    files = {"file": ("test.jpg", simple_test_image, "image/jpeg")}
    params = {
        "max_edge": 512,
        "gamma": 1.3, 
        "engine": "grabcut",
        "morph_kernel": 5,
        "median_blur": 7
    }
    
    response = test_client.post("/stylesync/segment", files=files, params=params)
    
    assert response.status_code == 200
    data = response.json()
    
    # Check that debug info reflects our parameters
    debug = data["debug"]
    assert debug["pre_gamma"] == 1.3
    assert debug["morph_kernel"] == 5
    assert debug["post_blur"] == 7
    
    # Engine should be grabcut since we forced it
    assert data["engine"] == "grabcut"


def test_segment_invalid_file_type(test_client):
    """Test segmentation with unsupported file type."""
    # Create a text file disguised as image
    fake_image = io.BytesIO(b"not an image")
    files = {"file": ("test.txt", fake_image, "text/plain")}
    
    response = test_client.post("/stylesync/segment", files=files)
    
    assert response.status_code == 415  # Unsupported media type


def test_segment_invalid_parameters(test_client, simple_test_image):
    """Test segmentation with invalid parameters."""
    files = {"file": ("test.jpg", simple_test_image, "image/jpeg")}
    
    # Test invalid gamma
    response = test_client.post("/stylesync/segment", files=files, params={"gamma": 5.0})
    assert response.status_code == 422  # Validation error
    
    # Test invalid max_edge
    response = test_client.post("/stylesync/segment", files=files, params={"max_edge": 100})
    assert response.status_code == 422
    
    # Test invalid engine
    response = test_client.post("/stylesync/segment", files=files, params={"engine": "invalid"})
    assert response.status_code == 422


def test_segment_no_file(test_client):
    """Test segmentation without file."""
    response = test_client.post("/stylesync/segment")
    
    assert response.status_code == 422  # Missing required field


def test_metrics_endpoint(test_client):
    """Test metrics endpoint."""
    response = test_client.get("/stylesync/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check metrics structure
    assert "uptime_seconds" in data
    assert "counters" in data
    assert "timing_stats" in data
    assert "mask_ratio_stats" in data
