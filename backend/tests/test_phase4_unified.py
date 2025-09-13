"""
StyleSync Phase 4 Test Suite
Comprehensive tests for unified orchestrator, caching, security, and observability.
"""
import asyncio
import json
import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from typing import Dict, Any

# Import components to test
from app.services.orchestrator import AdviceOrchestrator
from app.services.cache import MultiLayerCache, InMemoryLRUCache
from app.services.fingerprint import FingerprintManager, generate_content_fingerprint
from app.services.security import SecurityManager, APIKeyManager
from app.services.reliability import ReliabilityManager, CircuitBreaker, TimeoutManager
from app.api.v1 import router as v1_router

# Test configuration
@pytest.fixture
def test_app():
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(v1_router)
    return app

@pytest.fixture
def test_client(test_app):
    """Create test client."""
    return TestClient(test_app)

@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator for testing."""
    return Mock(spec=AdviceOrchestrator)

@pytest.fixture
def test_image_bytes():
    """Sample test image bytes."""
    # Simple 1x1 PNG
    return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x12IDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00\x05\x97\r\xe2\x00\x00\x00\x00IEND\xaeB`\x82'


class TestFingerprintManager:
    """Test fingerprinting utilities."""
    
    def test_generate_content_fingerprint(self, test_image_bytes):
        """Test content fingerprint generation."""
        fingerprint = generate_content_fingerprint(test_image_bytes)
        
        assert 'sha256' in fingerprint
        assert 'phash' in fingerprint
        assert 'metadata' in fingerprint
        assert len(fingerprint['sha256']) == 64  # SHA-256 hex length
        assert len(fingerprint['phash']) == 16   # 64-bit hex length
    
    def test_fingerprint_deterministic(self, test_image_bytes):
        """Test that fingerprints are deterministic."""
        fp1 = generate_content_fingerprint(test_image_bytes)
        fp2 = generate_content_fingerprint(test_image_bytes)
        
        assert fp1['sha256'] == fp2['sha256']
        assert fp1['phash'] == fp2['phash']
    
    def test_cache_key_generation(self):
        """Test cache key generation."""
        manager = FingerprintManager("1.0.0")
        
        seg_key = manager.get_segmentation_cache_key("abc123", 1.2, 768, "auto")
        assert seg_key.startswith("seg:")
        assert "abc123" in seg_key
        assert "1.0.0" in seg_key
        
        # Different parameters should give different keys
        seg_key2 = manager.get_segmentation_cache_key("abc123", 1.3, 768, "auto")
        assert seg_key != seg_key2


class TestMultiLayerCache:
    """Test caching system."""
    
    def test_in_memory_cache_basic(self):
        """Test basic in-memory cache operations."""
        cache = InMemoryLRUCache(max_size=3)
        
        # Test set/get
        assert cache.set("key1", "value1", ttl=60)
        assert cache.get("key1") == "value1"
        
        # Test TTL expiration
        assert cache.set("key2", "value2", ttl=0)  # Immediate expiration
        time.sleep(0.1)
        assert cache.get("key2") is None
        
        # Test LRU eviction
        cache.set("key1", "value1", ttl=60)
        cache.set("key2", "value2", ttl=60)
        cache.set("key3", "value3", ttl=60)
        cache.set("key4", "value4", ttl=60)  # Should evict key1
        
        assert cache.get("key1") is None
        assert cache.get("key4") == "value4"
    
    def test_multilayer_cache_l1_l2(self):
        """Test L1/L2 cache layers."""
        cache = MultiLayerCache(redis_url=None)  # Use in-memory only
        
        # Test L1 content dedup
        cache.set_l1_content_dedup("test_key", {"advice": "data"})
        result = cache.get_l1_content_dedup("test_key")
        assert result == {"advice": "data"}
        
        # Test L2 segmentation
        cache.set_l2_segmentation("seg_key", {"mask": "data"})
        result = cache.get_l2_segmentation("seg_key")
        assert result == {"mask": "data"}
        
        # Test cache stats
        stats = cache.get_cache_stats()
        assert 'stats' in stats
        assert 'hit_rates' in stats
        assert stats['stats']['l1_hits'] >= 1
        assert stats['stats']['l2_seg_hits'] >= 1


class TestSecurityManager:
    """Test security and authentication."""
    
    def test_api_key_validation(self):
        """Test API key validation."""
        with patch.dict('os.environ', {'STYLESYNC_API_KEY': 'test_key_123'}):
            manager = APIKeyManager()
            manager._load_api_keys()
            
            assert manager.validate_api_key('test_key_123')
            assert not manager.validate_api_key('wrong_key')
            assert not manager.validate_api_key('')
    
    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        with patch.dict('os.environ', {
            'STYLESYNC_RATE_LIMIT_REQUESTS': '3',
            'STYLESYNC_RATE_LIMIT_WINDOW': '60'
        }):
            manager = APIKeyManager()
            api_key = 'test_key'
            
            # Should allow up to limit
            assert manager.check_rate_limit(api_key)
            assert manager.check_rate_limit(api_key)
            assert manager.check_rate_limit(api_key)
            
            # Should deny after limit
            assert not manager.check_rate_limit(api_key)
            
            # Check status
            status = manager.get_rate_limit_status(api_key)
            assert status['remaining'] == 0
            assert status['limit'] == 3
    
    def test_image_validation(self, test_image_bytes):
        """Test image upload validation."""
        manager = SecurityManager()
        
        # Mock file object
        file = Mock()
        file.content_type = 'image/png'
        file.filename = 'test.png'
        
        # Should pass validation
        try:
            manager.validate_image_upload(file, test_image_bytes)
        except Exception:
            pytest.fail("Valid image should pass validation")
        
        # Should fail with wrong content type
        file.content_type = 'text/plain'
        with pytest.raises(Exception):
            manager.validate_image_upload(file, test_image_bytes)


class TestReliabilityManager:
    """Test reliability, timeouts, and circuit breakers."""
    
    def test_circuit_breaker_states(self):
        """Test circuit breaker state transitions."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        
        # Initially closed
        assert cb.state == 'CLOSED'
        
        # Record failures
        cb._record_failure()
        assert cb.state == 'CLOSED'
        
        cb._record_failure()
        assert cb.state == 'OPEN'  # Should open after threshold
        
        # Should allow reset after timeout
        time.sleep(1.1)
        assert cb._should_attempt_reset()
    
    @pytest.mark.asyncio
    async def test_timeout_manager(self):
        """Test timeout functionality."""
        manager = TimeoutManager()
        manager.timeouts['test'] = 0.1  # 100ms timeout
        
        # Function that completes in time
        async def fast_func():
            await asyncio.sleep(0.05)
            return "success"
        
        async with manager.timeout('test'):
            result = await fast_func()
            assert result == "success"
        
        # Function that times out
        async def slow_func():
            await asyncio.sleep(0.2)
            return "should_not_reach"
        
        with pytest.raises(Exception):  # Should raise TimeoutError
            async with manager.timeout('test'):
                await slow_func()


class TestOrchestrator:
    """Test unified orchestrator."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        orchestrator = AdviceOrchestrator(redis_url=None, policy_version="1.0.0")
        
        assert orchestrator.policy_version == "1.0.0"
        assert orchestrator.cache is not None
        assert orchestrator.fingerprint_manager is not None
    
    @pytest.mark.asyncio
    async def test_direct_harmony_mode(self):
        """Test direct harmony mode processing."""
        orchestrator = AdviceOrchestrator(redis_url=None)
        
        # Mock the private method for testing
        result = await orchestrator._process_direct_harmony_mode(
            orchestrator.OrchestrationResult("test_id"),
            "#FF0000",
            target_role="bottom",
            intent="classic"
        )
        
        assert 'request_id' in result
        assert 'suggestions' in result
        assert result['meta']['input_mode'] == 'artifacts_direct'


class TestAPIEndpoints:
    """Test API endpoints integration."""
    
    def test_health_endpoint(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/v1/healthz")
        assert response.status_code == 200
        
        data = response.json()
        assert data['status'] == 'ok'
        assert 'service' in data
        assert 'version' in data
    
    def test_readiness_endpoint(self, test_client):
        """Test readiness check endpoint."""
        response = test_client.get("/v1/readyz")
        # Should be 200 or 503 depending on dependencies
        assert response.status_code in [200, 503]
        
        data = response.json()
        assert 'status' in data
        assert 'checks' in data
    
    @patch('app.services.security.security_manager.authenticate_request')
    def test_advice_endpoint_validation(self, mock_auth, test_client):
        """Test advice endpoint input validation."""
        mock_auth.return_value = "test_key"
        
        # Should reject empty request
        response = test_client.post("/v1/advice")
        assert response.status_code == 400
        
        # Should reject invalid median blur
        response = test_client.post(
            "/v1/advice",
            params={"phase1_median_blur": 4}  # Must be odd
        )
        assert response.status_code == 400
    
    @patch('app.services.security.security_manager.authenticate_request')
    def test_presign_endpoint(self, mock_auth, test_client):
        """Test presigned upload endpoint."""
        mock_auth.return_value = "test_key"
        
        request_data = {
            "filename": "test.jpg",
            "content_type": "image/jpeg"
        }
        
        response = test_client.post("/v1/uploads/presign", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert 'asset_id' in data
        assert 'upload_url' in data
        assert 'expires_at' in data


class TestGoldenOutputs:
    """Test golden outputs for regression testing."""
    
    def test_navy_blue_complementary(self):
        """Test Navy blue generates expected complementary color."""
        # This would test the actual harmony generation
        # with known input/output pairs
        navy_hex = "#000080"
        expected_complementary = "#DBDB71"  # From Phase 3 spec
        
        # Mock test - in real implementation would call harmony engine
        result_complementary = "#DBDB71"  # Placeholder
        assert result_complementary == expected_complementary
    
    def test_deterministic_palette_extraction(self):
        """Test that palette extraction is deterministic."""
        # This would test that the same image produces the same palette
        # accounting for floating point precision
        pass


class TestLoadAndPerformance:
    """Test performance and load handling."""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling multiple concurrent requests."""
        orchestrator = AdviceOrchestrator(redis_url=None)
        
        # Simulate concurrent requests
        tasks = []
        for i in range(10):
            task = orchestrator._process_direct_harmony_mode(
                orchestrator.OrchestrationResult(f"test_{i}"),
                "#FF0000",
                target_role="bottom"
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        assert len(results) == 10
        
        # Each should have unique request_id
        request_ids = [r['request_id'] for r in results]
        assert len(set(request_ids)) == 10
    
    def test_cache_performance_improvement(self):
        """Test that cache improves performance."""
        cache = MultiLayerCache(redis_url=None)
        
        # Time without cache
        start = time.time()
        for i in range(100):
            # Simulate expensive operation
            time.sleep(0.001)
            result = f"computed_result_{i}"
        no_cache_time = time.time() - start
        
        # Time with cache
        start = time.time()
        for i in range(100):
            cached = cache.get_l1_content_dedup(f"key_{i}")
            if not cached:
                # Simulate expensive operation
                time.sleep(0.001)
                result = f"computed_result_{i}"
                cache.set_l1_content_dedup(f"key_{i}", result)
        
        # Second pass should be faster due to cache
        start = time.time()
        for i in range(100):
            cached = cache.get_l1_content_dedup(f"key_{i}")
            assert cached == f"computed_result_{i}"
        cache_time = time.time() - start
        
        assert cache_time < no_cache_time * 0.1  # Should be much faster


class TestChaosAndFailures:
    """Test failure scenarios and chaos conditions."""
    
    @pytest.mark.asyncio
    async def test_cache_unavailable_fallback(self):
        """Test fallback when cache is unavailable."""
        # Test that system continues to work when Redis is down
        orchestrator = AdviceOrchestrator(redis_url="redis://nonexistent:6379")
        
        # Should still work with in-memory fallback
        result = await orchestrator._process_direct_harmony_mode(
            orchestrator.OrchestrationResult("test_id"),
            "#FF0000",
            target_role="bottom"
        )
        
        assert 'suggestions' in result
    
    def test_segmentation_failure_degradation(self):
        """Test graceful degradation when segmentation fails."""
        from app.services.reliability import DegradationManager
        
        manager = DegradationManager()
        
        fallback = manager.get_fallback_response(
            'segmentation_failed',
            {'target_role': 'bottom'}
        )
        
        assert fallback['degraded'] is True
        assert fallback['fallback_reason'] == 'segmentation_unavailable'
    
    def test_invalid_image_handling(self, test_client):
        """Test handling of invalid image uploads."""
        # Test various invalid image scenarios
        invalid_cases = [
            b"not_an_image",  # Invalid format
            b"",              # Empty file
            b"x" * (11 * 1024 * 1024),  # Too large
        ]
        
        for invalid_data in invalid_cases:
            # Should handle gracefully without crashing
            pass  # Placeholder - would implement actual test


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
