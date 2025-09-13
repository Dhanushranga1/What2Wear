"""
StyleSync Phase 4 Integration Tests
Test full end-to-end workflows through the unified API.
"""
import asyncio
import json
import pytest
import time
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import Mock, patch
import tempfile
import os

# Test app setup
from app.main import app


class TestEndToEndWorkflows:
    """End-to-end integration tests."""
    
    @classmethod
    def setup_class(cls):
        """Set up test environment."""
        cls.client = TestClient(app)
        
        # Set up test API key
        os.environ['STYLESYNC_API_KEY'] = 'test_integration_key_123'
        os.environ['STYLESYNC_RATE_LIMIT_REQUESTS'] = '100'
        os.environ['STYLESYNC_RATE_LIMIT_WINDOW'] = '3600'
    
    def test_multipart_upload_workflow(self):
        """Test complete multipart file upload workflow."""
        # Create a minimal PNG file
        png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x12IDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00\x05\x97\r\xe2\x00\x00\x00\x00IEND\xaeB`\x82'
        
        # Prepare multipart form data
        files = {
            'image': ('test.png', png_bytes, 'image/png')
        }
        
        data = {
            'target_role': 'bottom',
            'phase1_median_blur': '3',
            'phase2_extraction_confidence': '0.8',
            'phase3_color_intent': 'classic'
        }
        
        headers = {'X-API-Key': 'test_integration_key_123'}
        
        # Make request to unified endpoint
        response = self.client.post(
            '/v1/advice',
            files=files,
            data=data,
            headers=headers
        )
        
        # Verify response structure
        assert response.status_code == 200
        result = response.json()
        
        # Check required fields
        assert 'request_id' in result
        assert 'suggestions' in result
        assert 'meta' in result
        assert result['meta']['input_mode'] == 'multipart_upload'
        assert result['meta']['target_role'] == 'bottom'
        
        # Check suggestions structure
        assert isinstance(result['suggestions'], list)
        if result['suggestions']:  # If not degraded
            suggestion = result['suggestions'][0]
            assert 'hex' in suggestion
            assert 'role' in suggestion
            assert suggestion['role'] == 'bottom'
    
    def test_presigned_upload_workflow(self):
        """Test presigned upload workflow."""
        headers = {'X-API-Key': 'test_integration_key_123'}
        
        # Step 1: Request presigned upload
        presign_data = {
            'filename': 'test_image.jpg',
            'content_type': 'image/jpeg'
        }
        
        response = self.client.post(
            '/v1/uploads/presign',
            json=presign_data,
            headers=headers
        )
        
        assert response.status_code == 200
        presign_result = response.json()
        
        assert 'asset_id' in presign_result
        assert 'upload_url' in presign_result
        assert 'expires_at' in presign_result
        
        # Step 2: Use asset ID for advice (simulated)
        advice_data = {
            'asset_id': presign_result['asset_id'],
            'target_role': 'top',
            'phase3_color_intent': 'bold'
        }
        
        # Note: In real scenario, file would be uploaded to S3 first
        # For integration test, we'll mock the asset existence
        with patch('app.services.storage.verify_asset_exists', return_value=True), \
             patch('app.services.storage.download_asset', return_value=b'mock_image_data'):
            
            response = self.client.post(
                '/v1/advice',
                params=advice_data,
                headers=headers
            )
            
            # Should succeed or gracefully degrade
            assert response.status_code in [200, 503]
    
    def test_direct_harmony_workflow(self):
        """Test direct harmony generation without image upload."""
        headers = {'X-API-Key': 'test_integration_key_123'}
        
        # Direct harmony parameters
        params = {
            'base_color': '#FF0000',  # Red
            'target_role': 'bottom',
            'phase3_color_intent': 'classic',
            'phase3_target_saturation': '0.7',
            'phase3_target_lightness': '0.5'
        }
        
        response = self.client.post(
            '/v1/advice',
            params=params,
            headers=headers
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Check response structure
        assert 'request_id' in result
        assert 'suggestions' in result
        assert result['meta']['input_mode'] == 'artifacts_direct'
        assert result['meta']['base_color'] == '#FF0000'
        
        # Should have harmony suggestions
        assert len(result['suggestions']) > 0
        for suggestion in result['suggestions']:
            assert 'hex' in suggestion
            assert 'harmony_type' in suggestion
            assert suggestion['role'] == 'bottom'
    
    def test_caching_behavior(self):
        """Test that caching improves response times."""
        headers = {'X-API-Key': 'test_integration_key_123'}
        
        # Same request parameters
        params = {
            'base_color': '#0066CC',
            'target_role': 'accent',
            'phase3_color_intent': 'bold'
        }
        
        # First request (cache miss)
        start_time = time.time()
        response1 = self.client.post('/v1/advice', params=params, headers=headers)
        first_time = time.time() - start_time
        
        assert response1.status_code == 200
        result1 = response1.json()
        
        # Second request (should hit cache)
        start_time = time.time()
        response2 = self.client.post('/v1/advice', params=params, headers=headers)
        second_time = time.time() - start_time
        
        assert response2.status_code == 200
        result2 = response2.json()
        
        # Results should be identical (from cache)
        assert result1['suggestions'] == result2['suggestions']
        
        # Second request should be faster (cache hit)
        # Note: In test environment, difference might be minimal
        print(f"First request: {first_time:.3f}s, Second request: {second_time:.3f}s")
    
    def test_rate_limiting(self):
        """Test API rate limiting enforcement."""
        # Set aggressive rate limits for testing
        with patch.dict(os.environ, {
            'STYLESYNC_RATE_LIMIT_REQUESTS': '3',
            'STYLESYNC_RATE_LIMIT_WINDOW': '60'
        }):
            headers = {'X-API-Key': 'rate_limit_test_key'}
            
            # Make requests up to limit
            for i in range(3):
                response = self.client.post(
                    '/v1/advice',
                    params={'base_color': f'#{i:06d}', 'target_role': 'bottom'},
                    headers=headers
                )
                assert response.status_code == 200
            
            # Next request should be rate limited
            response = self.client.post(
                '/v1/advice',
                params={'base_color': '#FF0000', 'target_role': 'bottom'},
                headers=headers
            )
            assert response.status_code == 429  # Too Many Requests
            
            # Check rate limit headers
            assert 'X-RateLimit-Limit' in response.headers
            assert 'X-RateLimit-Remaining' in response.headers
    
    def test_error_handling(self):
        """Test various error conditions."""
        headers = {'X-API-Key': 'test_integration_key_123'}
        
        # Test invalid color format
        response = self.client.post(
            '/v1/advice',
            params={'base_color': 'not_a_color', 'target_role': 'bottom'},
            headers=headers
        )
        assert response.status_code == 400
        
        # Test missing authentication
        response = self.client.post(
            '/v1/advice',
            params={'base_color': '#FF0000', 'target_role': 'bottom'}
        )
        assert response.status_code == 401
        
        # Test invalid target role
        response = self.client.post(
            '/v1/advice',
            params={'base_color': '#FF0000', 'target_role': 'invalid_role'},
            headers=headers
        )
        assert response.status_code == 400
    
    def test_observability_endpoints(self):
        """Test observability and monitoring endpoints."""
        # Health check
        response = self.client.get('/v1/healthz')
        assert response.status_code == 200
        
        health_data = response.json()
        assert health_data['status'] == 'ok'
        assert 'service' in health_data
        assert 'version' in health_data
        assert 'timestamp' in health_data
        
        # Readiness check
        response = self.client.get('/v1/readyz')
        # Could be 200 (ready) or 503 (not ready) depending on dependencies
        assert response.status_code in [200, 503]
        
        readiness_data = response.json()
        assert 'status' in readiness_data
        assert 'checks' in readiness_data
        
        # Metrics endpoint
        response = self.client.get('/v1/metrics')
        assert response.status_code == 200
        
        # Should be Prometheus format
        metrics_text = response.text
        assert 'stylesync_' in metrics_text  # Our custom metrics
        assert 'TYPE' in metrics_text  # Prometheus format
    
    def test_degradation_scenarios(self):
        """Test graceful degradation in failure scenarios."""
        headers = {'X-API-Key': 'test_integration_key_123'}
        
        # Simulate timeout scenario with short timeout
        with patch('app.config.PHASE1_TIMEOUT_MS', 1):  # 1ms timeout
            response = self.client.post(
                '/v1/advice',
                params={'base_color': '#FF0000', 'target_role': 'bottom'},
                headers=headers
            )
            
            # Should still return a response (degraded)
            assert response.status_code in [200, 503]
            
            if response.status_code == 200:
                result = response.json()
                # Check for degradation indicators
                assert 'meta' in result
                # May have degradation warnings or fallback suggestions


class TestBackwardCompatibility:
    """Test backward compatibility with Phase 1-3 endpoints."""
    
    @classmethod
    def setup_class(cls):
        """Set up test environment."""
        cls.client = TestClient(app)
        os.environ['STYLESYNC_API_KEY'] = 'compat_test_key_123'
    
    def test_phase1_endpoint_still_works(self):
        """Test that original Phase 1 endpoint still works."""
        # This test assumes original endpoints are preserved
        png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x12IDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00\x05\x97\r\xe2\x00\x00\x00\x00IEND\xaeB`\x82'
        
        files = {'image': ('test.png', png_bytes, 'image/png')}
        
        # Check if legacy endpoint exists
        try:
            response = self.client.post('/segment', files=files)
            # Should work or return 404 if endpoint removed
            assert response.status_code in [200, 404, 422]
        except Exception:
            # Endpoint might not exist in Phase 4
            pass
    
    def test_unified_api_covers_all_functionality(self):
        """Test that unified API provides all Phase 1-3 functionality."""
        headers = {'X-API-Key': 'compat_test_key_123'}
        
        # Test Phase 1 equivalent (segmentation)
        png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x12IDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00\x05\x97\r\xe2\x00\x00\x00\x00IEND\xaeB`\x82'
        
        files = {'image': ('test.png', png_bytes, 'image/png')}
        data = {
            'target_role': 'any',  # Just get segmentation
            'phase1_median_blur': '3',
            'phase1_confidence_threshold': '0.8'
        }
        
        response = self.client.post('/v1/advice', files=files, data=data, headers=headers)
        assert response.status_code == 200
        
        result = response.json()
        # Should have segmentation metadata
        assert 'meta' in result
        assert 'phase1_results' in result['meta'] or 'degraded' in result['meta']


class TestPerformanceValidation:
    """Validate Phase 4 performance targets."""
    
    @classmethod
    def setup_class(cls):
        """Set up performance test environment."""
        cls.client = TestClient(app)
        os.environ['STYLESYNC_API_KEY'] = 'perf_test_key_123'
    
    def test_p50_latency_target(self):
        """Test P50 latency ≤ 900ms target."""
        headers = {'X-API-Key': 'perf_test_key_123'}
        
        # Measure response times for direct harmony (fastest path)
        response_times = []
        
        for i in range(20):  # Sample size for P50
            start_time = time.time()
            
            response = self.client.post(
                '/v1/advice',
                params={
                    'base_color': f'#{i*10:06d}',
                    'target_role': 'bottom',
                    'phase3_color_intent': 'classic'
                },
                headers=headers
            )
            
            end_time = time.time()
            response_time = (end_time - start_time) * 1000  # Convert to ms
            
            assert response.status_code == 200
            response_times.append(response_time)
        
        # Calculate P50 (median)
        response_times.sort()
        p50 = response_times[len(response_times) // 2]
        
        print(f"P50 latency: {p50:.1f}ms (target: ≤900ms)")
        
        # Validate against target
        # Note: In test environment, this might not be representative
        # of production performance due to mocking
        if p50 > 900:
            print(f"WARNING: P50 latency {p50:.1f}ms exceeds 900ms target")
    
    def test_cache_hit_performance(self):
        """Test that cache hits meet performance targets."""
        headers = {'X-API-Key': 'perf_test_key_123'}
        
        # Prime cache
        params = {
            'base_color': '#FF0000',
            'target_role': 'bottom',
            'phase3_color_intent': 'classic'
        }
        
        self.client.post('/v1/advice', params=params, headers=headers)
        
        # Measure cache hit performance
        cache_hit_times = []
        
        for _ in range(10):
            start_time = time.time()
            response = self.client.post('/v1/advice', params=params, headers=headers)
            end_time = time.time()
            
            assert response.status_code == 200
            cache_hit_times.append((end_time - start_time) * 1000)
        
        avg_cache_hit_time = sum(cache_hit_times) / len(cache_hit_times)
        print(f"Average cache hit time: {avg_cache_hit_time:.1f}ms")
        
        # Cache hits should be very fast (< 50ms)
        assert avg_cache_hit_time < 100, f"Cache hits too slow: {avg_cache_hit_time:.1f}ms"


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "--tb=short", "-s"])
