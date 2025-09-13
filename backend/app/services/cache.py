"""
StyleSync Multi-Layer Caching System
Implements L1 content dedup cache, L2 result cache with Redis + LRU fallback.
"""
import json
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union, Tuple
from functools import lru_cache
import logging

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """Clear all cache entries."""
        pass


class InMemoryLRUCache(CacheBackend):
    """In-memory LRU cache backend for fallback."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache = {}
        self._access_times = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value and update access time."""
        if key in self._cache:
            entry = self._cache[key]
            # Check TTL
            if entry['expires'] > time.time():
                self._access_times[key] = time.time()
                return entry['value']
            else:
                # Expired
                del self._cache[key]
                self._access_times.pop(key, None)
        return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value with TTL and manage LRU eviction."""
        try:
            # Evict if at capacity
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()
            
            self._cache[key] = {
                'value': value,
                'expires': time.time() + ttl
            }
            self._access_times[key] = time.time()
            return True
        except Exception as e:
            logger.error(f"Failed to set cache key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if key in self._cache:
            del self._cache[key]
            self._access_times.pop(key, None)
            return True
        return False
    
    def exists(self, key: str) -> bool:
        """Check if non-expired key exists."""
        return self.get(key) is not None
    
    def clear(self) -> bool:
        """Clear all entries."""
        self._cache.clear()
        self._access_times.clear()
        return True
    
    def _evict_lru(self):
        """Evict least recently used entry."""
        if not self._access_times:
            return
        
        lru_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        self.delete(lru_key)


class RedisCache(CacheBackend):
    """Redis cache backend."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", db: int = 0):
        if not REDIS_AVAILABLE:
            raise ImportError("Redis not available. Install with: pip install redis")
        
        self.redis_client = redis.from_url(redis_url, db=db, decode_responses=True)
        self._test_connection()
    
    def _test_connection(self):
        """Test Redis connection."""
        try:
            self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis get failed for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in Redis with TTL."""
        try:
            serialized = json.dumps(value, default=str)
            return self.redis_client.setex(key, ttl, serialized)
        except Exception as e:
            logger.error(f"Redis set failed for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error(f"Redis delete failed for key {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Redis exists failed for key {key}: {e}")
            return False
    
    def clear(self) -> bool:
        """Clear all keys (use with caution)."""
        try:
            return bool(self.redis_client.flushdb())
        except Exception as e:
            logger.error(f"Redis clear failed: {e}")
            return False


class FallbackCache(CacheBackend):
    """Cache with Redis primary and in-memory fallback."""
    
    def __init__(self, redis_url: Optional[str] = None, fallback_max_size: int = 500):
        self.fallback = InMemoryLRUCache(fallback_max_size)
        self.redis = None
        
        if redis_url and REDIS_AVAILABLE:
            try:
                self.redis = RedisCache(redis_url)
                logger.info("Using Redis cache with fallback")
            except Exception as e:
                logger.warning(f"Redis unavailable, using fallback only: {e}")
        else:
            logger.info("Using in-memory cache only")
    
    def get(self, key: str) -> Optional[Any]:
        """Get from Redis first, then fallback."""
        if self.redis:
            value = self.redis.get(key)
            if value is not None:
                return value
        
        return self.fallback.get(key)
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set in both Redis and fallback."""
        redis_ok = False
        fallback_ok = False
        
        if self.redis:
            redis_ok = self.redis.set(key, value, ttl)
        
        fallback_ok = self.fallback.set(key, value, ttl)
        
        return redis_ok or fallback_ok
    
    def delete(self, key: str) -> bool:
        """Delete from both caches."""
        redis_ok = self.redis.delete(key) if self.redis else True
        fallback_ok = self.fallback.delete(key)
        
        return redis_ok and fallback_ok
    
    def exists(self, key: str) -> bool:
        """Check existence in either cache."""
        if self.redis and self.redis.exists(key):
            return True
        return self.fallback.exists(key)
    
    def clear(self) -> bool:
        """Clear both caches."""
        redis_ok = self.redis.clear() if self.redis else True
        fallback_ok = self.fallback.clear()
        
        return redis_ok and fallback_ok


class MultiLayerCache:
    """Multi-layer cache system for StyleSync."""
    
    # Cache TTLs (seconds)
    TTL_L1_CONTENT_DEDUP = 7 * 24 * 3600  # 7 days
    TTL_L2_SEGMENTATION = 24 * 3600       # 1 day
    TTL_L2_EXTRACTION = 24 * 3600         # 1 day  
    TTL_L2_ADVICE = 12 * 3600             # 12 hours
    TTL_IDEMPOTENCY = 5 * 60              # 5 minutes
    
    def __init__(self, redis_url: Optional[str] = None):
        # L1: Content deduplication cache (full advice responses)
        self.l1_cache = FallbackCache(redis_url, fallback_max_size=100)
        
        # L2: Result caches per phase
        self.l2_segmentation = FallbackCache(redis_url, fallback_max_size=200)
        self.l2_extraction = FallbackCache(redis_url, fallback_max_size=200) 
        self.l2_advice = FallbackCache(redis_url, fallback_max_size=300)
        
        # Idempotency cache
        self.idempotency_cache = FallbackCache(redis_url, fallback_max_size=100)
        
        self.stats = {
            'l1_hits': 0, 'l1_misses': 0,
            'l2_seg_hits': 0, 'l2_seg_misses': 0,
            'l2_ext_hits': 0, 'l2_ext_misses': 0,
            'l2_adv_hits': 0, 'l2_adv_misses': 0,
            'idempotency_hits': 0, 'idempotency_misses': 0
        }
    
    def get_l1_content_dedup(self, key: str) -> Optional[Any]:
        """Get from L1 content deduplication cache."""
        value = self.l1_cache.get(f"l1:{key}")
        if value:
            self.stats['l1_hits'] += 1
        else:
            self.stats['l1_misses'] += 1
        return value
    
    def set_l1_content_dedup(self, key: str, value: Any) -> bool:
        """Set in L1 content deduplication cache."""
        return self.l1_cache.set(f"l1:{key}", value, self.TTL_L1_CONTENT_DEDUP)
    
    def get_l2_segmentation(self, key: str) -> Optional[Any]:
        """Get from L2 segmentation cache."""
        value = self.l2_segmentation.get(f"l2_seg:{key}")
        if value:
            self.stats['l2_seg_hits'] += 1
        else:
            self.stats['l2_seg_misses'] += 1
        return value
    
    def set_l2_segmentation(self, key: str, value: Any) -> bool:
        """Set in L2 segmentation cache."""
        return self.l2_segmentation.set(f"l2_seg:{key}", value, self.TTL_L2_SEGMENTATION)
    
    def get_l2_extraction(self, key: str) -> Optional[Any]:
        """Get from L2 extraction cache."""
        value = self.l2_extraction.get(f"l2_ext:{key}")
        if value:
            self.stats['l2_ext_hits'] += 1
        else:
            self.stats['l2_ext_misses'] += 1
        return value
    
    def set_l2_extraction(self, key: str, value: Any) -> bool:
        """Set in L2 extraction cache."""
        return self.l2_extraction.set(f"l2_ext:{key}", value, self.TTL_L2_EXTRACTION)
    
    def get_l2_advice(self, key: str) -> Optional[Any]:
        """Get from L2 advice cache."""
        value = self.l2_advice.get(f"l2_adv:{key}")
        if value:
            self.stats['l2_adv_hits'] += 1
        else:
            self.stats['l2_adv_misses'] += 1
        return value
    
    def set_l2_advice(self, key: str, value: Any) -> bool:
        """Set in L2 advice cache."""
        return self.l2_advice.set(f"l2_adv:{key}", value, self.TTL_L2_ADVICE)
    
    def get_idempotency(self, key: str) -> Optional[Any]:
        """Get from idempotency cache."""
        value = self.idempotency_cache.get(f"idem:{key}")
        if value:
            self.stats['idempotency_hits'] += 1
        else:
            self.stats['idempotency_misses'] += 1
        return value
    
    def set_idempotency(self, key: str, value: Any) -> bool:
        """Set in idempotency cache."""
        return self.idempotency_cache.set(f"idem:{key}", value, self.TTL_IDEMPOTENCY)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = sum([
            self.stats['l1_hits'] + self.stats['l1_misses'],
            self.stats['l2_seg_hits'] + self.stats['l2_seg_misses'],
            self.stats['l2_ext_hits'] + self.stats['l2_ext_misses'],
            self.stats['l2_adv_hits'] + self.stats['l2_adv_misses']
        ])
        
        hit_rates = {}
        for layer in ['l1', 'l2_seg', 'l2_ext', 'l2_adv', 'idempotency']:
            hits = self.stats[f'{layer}_hits']
            misses = self.stats[f'{layer}_misses']
            total = hits + misses
            hit_rates[layer] = hits / total if total > 0 else 0.0
        
        return {
            'stats': self.stats.copy(),
            'hit_rates': hit_rates,
            'total_requests': total_requests
        }
    
    def clear_all(self) -> bool:
        """Clear all cache layers."""
        results = [
            self.l1_cache.clear(),
            self.l2_segmentation.clear(),
            self.l2_extraction.clear(),
            self.l2_advice.clear(),
            self.idempotency_cache.clear()
        ]
        
        # Reset stats
        for key in self.stats:
            self.stats[key] = 0
            
        return all(results)
