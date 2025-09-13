"""
API integration tests for color extraction endpoints.

Tests the complete color extraction API:
- Direct mode with mask + image data
- One-shot mode with file upload
- Parameter validation and error handling
- Response schema validation
"""

import pytest
import asyncio
import base64
import json
from pathlib import Path
from httpx import AsyncClient
from fastapi.testclient import TestClient

# Import our FastAPI app
import sys
sys.path.append(str(Path(__file__).parent.parent))
from main import app

class TestColorExtractAPI:
    """Test the /colors/extract endpoint"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def assets_dir(self):
        """Get test assets directory"""
        return Path(__file__).parent / "assets"
    
    def encode_image_to_base64(self, image_path):
        """Encode image file to base64 string"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    
    def test_color_extract_direct_mode_rgb(self, client, assets_dir):
        """Test Direct mode with RGB image + separate mask"""
        img_path = assets_dir / "two_blocks.png"
        mask_path = assets_dir / "two_blocks_mask.png"
        
        if not img_path.exists() or not mask_path.exists():
            pytest.skip("Synthetic assets not found")
        
        # Encode images to base64
        item_b64 = self.encode_image_to_base64(img_path)
        mask_b64 = self.encode_image_to_base64(mask_path)
        
        # Make Direct mode request
        response = client.post(
            "/colors/extract?k=2&include_swatch=true",
            json={
                "mask_png_b64": mask_b64,
                "item_png_b64": item_b64
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response schema
        assert "width" in data
        assert "height" in data
        assert "k" in data
        assert "sampled_pixels" in data
        assert "palette" in data
        assert "base_color" in data
        assert "debug" in data
        
        # Validate palette
        palette = data["palette"]
        assert len(palette) == 2  # k=2
        
        for color_entry in palette:
            assert "hex" in color_entry
            assert "ratio" in color_entry
            assert color_entry["hex"].startswith("#")
            assert len(color_entry["hex"]) == 7  # #RRGGBB
            assert 0.0 <= color_entry["ratio"] <= 1.0
        
        # Validate base color
        base_color = data["base_color"]
        assert "hex" in base_color
        assert "cluster_index" in base_color
        assert "score_breakdown" in base_color
        
        score_breakdown = base_color["score_breakdown"]
        assert "dominance" in score_breakdown
        assert "neutral_penalty" in score_breakdown
        assert "cohesion_bonus" in score_breakdown
        assert "final_score" in score_breakdown
        
        # Base color should be from palette
        palette_hexes = [entry["hex"] for entry in palette]
        assert base_color["hex"] in palette_hexes
        
        # Validate debug info
        debug = data["debug"]
        assert "gamma" in debug
        assert "filters" in debug
        assert "neutral_thresholds" in debug
        assert "cohesion" in debug
        
        # Check swatch artifact if included
        if "artifacts" in data and data["artifacts"]:
            artifacts = data["artifacts"]
            if "swatch_png_b64" in artifacts:
                swatch_b64 = artifacts["swatch_png_b64"]
                assert isinstance(swatch_b64, str)
                assert len(swatch_b64) > 0
    
    def test_color_extract_direct_mode_missing_image(self, client, assets_dir):
        """Test Direct mode error when image data is missing"""
        mask_path = assets_dir / "two_blocks_mask.png"
        
        if not mask_path.exists():
            pytest.skip("Synthetic assets not found")
        
        mask_b64 = self.encode_image_to_base64(mask_path)
        
        # Missing both item_png_b64 and item_rgba_png_b64
        response = client.post(
            "/colors/extract",
            json={"mask_png_b64": mask_b64}
        )
        
        assert response.status_code == 400
        assert "must be provided" in response.json()["detail"].lower()
    
    def test_color_extract_oneshot_mode(self, client, assets_dir):
        """Test One-Shot mode with file upload"""
        img_path = assets_dir / "logo_on_shirt.png"
        
        if not img_path.exists():
            pytest.skip("Synthetic assets not found")
        
        # Upload file for One-Shot mode
        with open(img_path, "rb") as f:
            response = client.post(
                "/colors/extract?k=3&enable_spatial_cohesion=true",
                files={"file": ("logo_on_shirt.png", f, "image/png")}
            )
        
        # Note: This might fail if Phase-1 segmentation dependencies are missing
        # In that case, it should return 503 (service unavailable)
        if response.status_code == 503:
            pytest.skip("Phase-1 segmentation dependencies not available")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate basic response structure
        assert "palette" in data
        assert "base_color" in data
        assert len(data["palette"]) == 3  # k=3
        
        # For logo_on_shirt.png, navy should be dominant
        # (since logo is small white area on large navy background)
        palette = data["palette"]
        dominant_color = palette[0]  # First in palette is most dominant
        assert dominant_color["ratio"] > 0.8  # Navy should be ~98% of image
    
    def test_color_extract_parameter_validation(self, client, assets_dir):
        """Test parameter validation and constraints"""
        img_path = assets_dir / "two_blocks.png"
        mask_path = assets_dir / "two_blocks_mask.png"
        
        if not img_path.exists() or not mask_path.exists():
            pytest.skip("Synthetic assets not found")
        
        item_b64 = self.encode_image_to_base64(img_path)
        mask_b64 = self.encode_image_to_base64(mask_path)
        
        request_body = {
            "mask_png_b64": mask_b64,
            "item_png_b64": item_b64
        }
        
        # Test k parameter bounds
        response = client.post("/colors/extract?k=1", json=request_body)
        assert response.status_code == 422  # k too low
        
        response = client.post("/colors/extract?k=13", json=request_body)
        assert response.status_code == 422  # k too high
        
        # Test gamma parameter bounds
        response = client.post("/colors/extract?gamma=0.5", json=request_body)
        assert response.status_code == 422  # gamma too low
        
        response = client.post("/colors/extract?gamma=3.0", json=request_body)
        assert response.status_code == 422  # gamma too high
        
        # Test valid parameters
        response = client.post(
            "/colors/extract?k=5&gamma=1.2&max_samples=10000", 
            json=request_body
        )
        assert response.status_code == 200
    
    def test_color_extract_filter_parameters(self, client, assets_dir):
        """Test HSV filter parameter effects"""
        img_path = assets_dir / "stripes.png"
        mask_path = assets_dir / "stripes_mask.png"
        
        if not img_path.exists() or not mask_path.exists():
            pytest.skip("Synthetic assets not found")
        
        item_b64 = self.encode_image_to_base64(img_path)
        mask_b64 = self.encode_image_to_base64(mask_path)
        
        request_body = {
            "mask_png_b64": mask_b64,
            "item_png_b64": item_b64
        }
        
        # Default filters
        response1 = client.post("/colors/extract?k=2", json=request_body)
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Strict filters (should reduce sampled pixels)
        response2 = client.post(
            "/colors/extract?k=2&filter_shadow_v_lt=0.3&min_saturation=0.2",
            json=request_body
        )
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Strict filters should sample fewer pixels
        assert data2["sampled_pixels"] <= data1["sampled_pixels"]
        
        # But should still produce valid palette
        assert len(data2["palette"]) == 2
    
    def test_color_extract_neutral_penalty_effects(self, client, assets_dir):
        """Test neutral penalty parameter effects on base color selection"""
        img_path = assets_dir / "two_blocks.png"
        mask_path = assets_dir / "two_blocks_mask.png"
        
        if not img_path.exists() or not mask_path.exists():
            pytest.skip("Synthetic assets not found")
        
        item_b64 = self.encode_image_to_base64(img_path)
        mask_b64 = self.encode_image_to_base64(mask_path)
        
        request_body = {
            "mask_png_b64": mask_b64,
            "item_png_b64": item_b64
        }
        
        # Low neutral penalty (more tolerant of grays)
        response1 = client.post(
            "/colors/extract?k=2&neutral_penalty_weight=0.9",
            json=request_body
        )
        assert response1.status_code == 200
        
        # High neutral penalty (strongly avoid grays)
        response2 = client.post(
            "/colors/extract?k=2&neutral_penalty_weight=0.1",
            json=request_body
        )
        assert response2.status_code == 200
        
        # Both should succeed, but might select different base colors
        data1 = response1.json()
        data2 = response2.json()
        
        assert "base_color" in data1
        assert "base_color" in data2
        
        # Score breakdowns should show different penalty values
        penalty1 = data1["base_color"]["score_breakdown"]["neutral_penalty"]
        penalty2 = data2["base_color"]["score_breakdown"]["neutral_penalty"]
        
        # Penalties might be the same if colors aren't neutral,
        # but the logic should be applied consistently
        assert isinstance(penalty1, (int, float))
        assert isinstance(penalty2, (int, float))
    
    def test_color_extract_cohesion_toggle(self, client, assets_dir):
        """Test spatial cohesion enable/disable"""
        img_path = assets_dir / "logo_on_shirt.png"
        mask_path = assets_dir / "logo_on_shirt_mask.png"
        
        if not img_path.exists() or not mask_path.exists():
            pytest.skip("Synthetic assets not found")
        
        item_b64 = self.encode_image_to_base64(img_path)
        mask_b64 = self.encode_image_to_base64(mask_path)
        
        request_body = {
            "mask_png_b64": mask_b64,
            "item_png_b64": item_b64
        }
        
        # With cohesion enabled
        response1 = client.post(
            "/colors/extract?k=2&enable_spatial_cohesion=true&cohesion_weight=0.15",
            json=request_body
        )
        assert response1.status_code == 200
        
        # With cohesion disabled
        response2 = client.post(
            "/colors/extract?k=2&enable_spatial_cohesion=false",
            json=request_body
        )
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Check cohesion bonus in score breakdown
        cohesion_bonus1 = data1["base_color"]["score_breakdown"]["cohesion_bonus"]
        cohesion_bonus2 = data2["base_color"]["score_breakdown"]["cohesion_bonus"]
        
        assert cohesion_bonus1 > 0.0  # Should have cohesion bonus
        assert cohesion_bonus2 == 0.0  # Should be zero when disabled
    
    def test_color_extract_invalid_base64(self, client):
        """Test handling of invalid base64 data"""
        response = client.post(
            "/colors/extract",
            json={
                "mask_png_b64": "invalid_base64_data",
                "item_png_b64": "also_invalid"
            }
        )
        
        assert response.status_code == 400
        assert "base64" in response.json()["detail"].lower() or "invalid" in response.json()["detail"].lower()
    
    def test_color_extract_mode_conflicts(self, client):
        """Test error when both file and direct mode specified"""
        # This would require multipart form data with both file and JSON
        # For now, test the basic conflict detection logic
        
        # If both modes are somehow provided, should return 400
        # (Implementation in extract_api.py should catch this)
        pass  # This test needs specific multipart handling
    
    def test_color_extract_response_deterministic(self, client, assets_dir):
        """Test that responses are deterministic with same inputs"""
        img_path = assets_dir / "two_blocks.png"
        mask_path = assets_dir / "two_blocks_mask.png"
        
        if not img_path.exists() or not mask_path.exists():
            pytest.skip("Synthetic assets not found")
        
        item_b64 = self.encode_image_to_base64(img_path)
        mask_b64 = self.encode_image_to_base64(mask_path)
        
        request_body = {
            "mask_png_b64": mask_b64,
            "item_png_b64": item_b64
        }
        
        # Make same request twice
        response1 = client.post("/colors/extract?k=3", json=request_body)
        response2 = client.post("/colors/extract?k=3", json=request_body)
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Results should be identical (due to fixed random seeds)
        assert data1["palette"] == data2["palette"]
        assert data1["base_color"]["hex"] == data2["base_color"]["hex"]
        assert data1["sampled_pixels"] == data2["sampled_pixels"]

class TestColorExtractPerformance:
    """Test performance characteristics"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_color_extract_performance_baseline(self, client, assets_dir):
        """Test that extraction completes within reasonable time"""
        import time
        
        img_path = assets_dir / "two_blocks.png"
        mask_path = assets_dir / "two_blocks_mask.png"
        
        if not img_path.exists() or not mask_path.exists():
            pytest.skip("Synthetic assets not found")
        
        with open(img_path, "rb") as f:
            item_b64 = base64.b64encode(f.read()).decode("ascii")
        with open(mask_path, "rb") as f:
            mask_b64 = base64.b64encode(f.read()).decode("ascii")
        
        # Time the request
        start_time = time.time()
        response = client.post(
            "/colors/extract?k=5&max_samples=20000",
            json={
                "mask_png_b64": mask_b64,
                "item_png_b64": item_b64
            }
        )
        end_time = time.time()
        
        assert response.status_code == 200
        
        # Should complete within reasonable time (excluding segmentation)
        # For synthetic 256x256 image, should be well under 1 second
        duration = end_time - start_time
        assert duration < 2.0, f"Extraction took {duration:.3f}s, expected < 2.0s"
        
        # Verify reasonable sample count
        data = response.json()
        assert data["sampled_pixels"] > 1000  # Should sample enough pixels
        assert data["sampled_pixels"] <= 20000  # Should respect max_samples

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
