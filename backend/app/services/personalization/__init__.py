"""
Phase 5 Feature Cache System
Redis-based caching for user personalization features with database fallback.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, asdict
import asyncio

# Optional Redis import with graceful fallback
try:
    import redis
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Database imports
import asyncpg
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


@dataclass
class UserFeatures:
    """User personalization features derived from interaction history."""
    user_id: str
    hue_bias: Dict[int, float]  # Hue bin (0-330 by 30s) to weight mapping
    neutral_affinity: float  # 0.0 to 1.0
    saturation_cap_adjust: float  # -0.1 to +0.1
    lightness_bias: float  # -0.1 to +0.1
    event_count: int  # Number of events used to compute features
    updated_at: datetime
    
    @classmethod
    def default(cls, user_id: str) -> 'UserFeatures':
        """Create default features for cold-start users."""
        return cls(
            user_id=user_id,
            hue_bias={},  # No bias initially
            neutral_affinity=0.5,  # Neutral preference
            saturation_cap_adjust=0.0,  # No adjustment
            lightness_bias=0.0,  # No bias
            event_count=0,
            updated_at=datetime.utcnow()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['updated_at'] = self.updated_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserFeatures':
        """Create from dictionary loaded from JSON."""
        # Convert hue_bias keys from strings back to integers
        if 'hue_bias' in data and isinstance(data['hue_bias'], dict):
            data['hue_bias'] = {int(k): v for k, v in data['hue_bias'].items()}
        
        # Parse datetime
        if 'updated_at' in data:
            if isinstance(data['updated_at'], str):
                data['updated_at'] = datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
        
        return cls(**data)


class FeatureCacheManager:
    """
    Manages user feature caching with Redis primary and database fallback.
    """
    
    def __init__(self, 
                 redis_url: Optional[str] = None,
                 db_url: Optional[str] = None,
                 ttl_days: int = 7,
                 enable_redis: bool = True):
        self.redis_url = redis_url
        self.db_url = db_url
        self.ttl_seconds = ttl_days * 24 * 3600
        self.enable_redis = enable_redis and REDIS_AVAILABLE
        
        # Redis connections (lazy initialized)
        self._redis_pool = None
        self._async_redis_pool = None
        
        # Database connection pool (lazy initialized)
        self._db_pool = None
        
        # Stats
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'db_hits': 0,
            'db_misses': 0,
            'cache_sets': 0,
            'cache_errors': 0
        }
    
    def _get_redis_pool(self):
        """Get or create Redis connection pool."""
        if not self.enable_redis or not self.redis_url:
            return None
        
        if self._redis_pool is None:
            try:
                self._redis_pool = redis.ConnectionPool.from_url(
                    self.redis_url,
                    decode_responses=True,
                    max_connections=20
                )
            except Exception as e:
                logger.warning(f"Failed to create Redis pool: {e}")
                return None
        
        return self._redis_pool
    
    def _get_async_redis_pool(self):
        """Get or create async Redis connection pool."""
        if not self.enable_redis or not self.redis_url:
            return None
        
        if self._async_redis_pool is None:
            try:
                self._async_redis_pool = aioredis.ConnectionPool.from_url(
                    self.redis_url,
                    decode_responses=True,
                    max_connections=20
                )
            except Exception as e:
                logger.warning(f"Failed to create async Redis pool: {e}")
                return None
        
        return self._async_redis_pool
    
    def _get_cache_key(self, user_id: str) -> str:
        """Generate Redis cache key for user features."""
        return f"feat:{user_id}"
    
    def get_features_sync(self, user_id: str) -> UserFeatures:
        """
        Get user features synchronously.
        Tries Redis cache first, then database, then defaults.
        """
        # Try cache first
        if self.enable_redis:
            try:
                pool = self._get_redis_pool()
                if pool:
                    redis_client = redis.Redis(connection_pool=pool)
                    cache_key = self._get_cache_key(user_id)
                    cached_data = redis_client.get(cache_key)
                    
                    if cached_data:
                        try:
                            data = json.loads(cached_data)
                            features = UserFeatures.from_dict(data)
                            self.stats['cache_hits'] += 1
                            logger.debug(f"Cache hit for user {user_id}")
                            return features
                        except (json.JSONDecodeError, KeyError, ValueError) as e:
                            logger.warning(f"Invalid cached data for user {user_id}: {e}")
                    
                    self.stats['cache_misses'] += 1
            except Exception as e:
                logger.warning(f"Redis cache error for user {user_id}: {e}")
                self.stats['cache_errors'] += 1
        
        # Fallback to database
        features = self._get_features_from_db_sync(user_id)
        
        # Cache the result if we got it from DB
        if features.event_count > 0:
            self._cache_features_sync(features)
        
        return features
    
    async def get_features_async(self, user_id: str) -> UserFeatures:
        """
        Get user features asynchronously.
        Tries Redis cache first, then database, then defaults.
        """
        # Try cache first
        if self.enable_redis:
            try:
                pool = self._get_async_redis_pool()
                if pool:
                    async_redis = aioredis.Redis(connection_pool=pool)
                    cache_key = self._get_cache_key(user_id)
                    cached_data = await async_redis.get(cache_key)
                    
                    if cached_data:
                        try:
                            data = json.loads(cached_data)
                            features = UserFeatures.from_dict(data)
                            self.stats['cache_hits'] += 1
                            logger.debug(f"Cache hit for user {user_id}")
                            return features
                        except (json.JSONDecodeError, KeyError, ValueError) as e:
                            logger.warning(f"Invalid cached data for user {user_id}: {e}")
                    
                    self.stats['cache_misses'] += 1
            except Exception as e:
                logger.warning(f"Redis cache error for user {user_id}: {e}")
                self.stats['cache_errors'] += 1
        
        # Fallback to database
        features = await self._get_features_from_db_async(user_id)
        
        # Cache the result if we got it from DB
        if features.event_count > 0:
            await self._cache_features_async(features)
        
        return features
    
    def _get_features_from_db_sync(self, user_id: str) -> UserFeatures:
        """Get features from database synchronously."""
        if not self.db_url:
            logger.warning("No database URL configured, returning default features")
            return UserFeatures.default(user_id)
        
        try:
            conn = psycopg2.connect(self.db_url)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT hue_bias_json, neutral_affinity, saturation_cap_adjust, 
                           lightness_bias, event_count, updated_at
                    FROM features WHERE user_id = %s
                """, (user_id,))
                
                row = cur.fetchone()
                if row:
                    features = UserFeatures(
                        user_id=user_id,
                        hue_bias=row['hue_bias_json'] or {},
                        neutral_affinity=row['neutral_affinity'],
                        saturation_cap_adjust=row['saturation_cap_adjust'],
                        lightness_bias=row['lightness_bias'],
                        event_count=row['event_count'],
                        updated_at=row['updated_at']
                    )
                    self.stats['db_hits'] += 1
                    return features
                else:
                    self.stats['db_misses'] += 1
                    return UserFeatures.default(user_id)
        
        except Exception as e:
            logger.error(f"Database error getting features for user {user_id}: {e}")
            return UserFeatures.default(user_id)
    
    async def _get_features_from_db_async(self, user_id: str) -> UserFeatures:
        """Get features from database asynchronously."""
        if not self.db_url:
            logger.warning("No database URL configured, returning default features")
            return UserFeatures.default(user_id)
        
        try:
            # For async, we'll use a simple asyncpg connection
            # In production, you'd want a proper connection pool
            conn = await asyncpg.connect(self.db_url)
            try:
                row = await conn.fetchrow("""
                    SELECT hue_bias_json, neutral_affinity, saturation_cap_adjust, 
                           lightness_bias, event_count, updated_at
                    FROM features WHERE user_id = $1
                """, user_id)
                
                if row:
                    features = UserFeatures(
                        user_id=user_id,
                        hue_bias=row['hue_bias_json'] or {},
                        neutral_affinity=row['neutral_affinity'],
                        saturation_cap_adjust=row['saturation_cap_adjust'],
                        lightness_bias=row['lightness_bias'],
                        event_count=row['event_count'],
                        updated_at=row['updated_at']
                    )
                    self.stats['db_hits'] += 1
                    return features
                else:
                    self.stats['db_misses'] += 1
                    return UserFeatures.default(user_id)
            finally:
                await conn.close()
        
        except Exception as e:
            logger.error(f"Database error getting features for user {user_id}: {e}")
            return UserFeatures.default(user_id)
    
    def _cache_features_sync(self, features: UserFeatures) -> bool:
        """Cache features in Redis synchronously."""
        if not self.enable_redis:
            return False
        
        try:
            pool = self._get_redis_pool()
            if not pool:
                return False
            
            redis_client = redis.Redis(connection_pool=pool)
            cache_key = self._get_cache_key(features.user_id)
            data = json.dumps(features.to_dict())
            
            redis_client.setex(cache_key, self.ttl_seconds, data)
            self.stats['cache_sets'] += 1
            logger.debug(f"Cached features for user {features.user_id}")
            return True
        
        except Exception as e:
            logger.warning(f"Failed to cache features for user {features.user_id}: {e}")
            self.stats['cache_errors'] += 1
            return False
    
    async def _cache_features_async(self, features: UserFeatures) -> bool:
        """Cache features in Redis asynchronously."""
        if not self.enable_redis:
            return False
        
        try:
            pool = self._get_async_redis_pool()
            if not pool:
                return False
            
            async_redis = aioredis.Redis(connection_pool=pool)
            cache_key = self._get_cache_key(features.user_id)
            data = json.dumps(features.to_dict())
            
            await async_redis.setex(cache_key, self.ttl_seconds, data)
            self.stats['cache_sets'] += 1
            logger.debug(f"Cached features for user {features.user_id}")
            return True
        
        except Exception as e:
            logger.warning(f"Failed to cache features for user {features.user_id}: {e}")
            self.stats['cache_errors'] += 1
            return False
    
    def update_features_sync(self, features: UserFeatures) -> bool:
        """Update features in database and cache synchronously."""
        if not self.db_url:
            logger.warning("No database URL configured")
            return False
        
        try:
            conn = psycopg2.connect(self.db_url)
            with conn.cursor() as cur:
                # Upsert features
                cur.execute("""
                    INSERT INTO features (
                        user_id, hue_bias_json, neutral_affinity, 
                        saturation_cap_adjust, lightness_bias, event_count, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        hue_bias_json = EXCLUDED.hue_bias_json,
                        neutral_affinity = EXCLUDED.neutral_affinity,
                        saturation_cap_adjust = EXCLUDED.saturation_cap_adjust,
                        lightness_bias = EXCLUDED.lightness_bias,
                        event_count = EXCLUDED.event_count,
                        updated_at = EXCLUDED.updated_at
                """, (
                    features.user_id,
                    json.dumps(features.hue_bias),
                    features.neutral_affinity,
                    features.saturation_cap_adjust,
                    features.lightness_bias,
                    features.event_count,
                    features.updated_at
                ))
                conn.commit()
            
            # Update cache
            self._cache_features_sync(features)
            logger.info(f"Updated features for user {features.user_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to update features for user {features.user_id}: {e}")
            return False
    
    async def update_features_async(self, features: UserFeatures) -> bool:
        """Update features in database and cache asynchronously."""
        if not self.db_url:
            logger.warning("No database URL configured")
            return False
        
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Upsert features
                await conn.execute("""
                    INSERT INTO features (
                        user_id, hue_bias_json, neutral_affinity, 
                        saturation_cap_adjust, lightness_bias, event_count, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (user_id) DO UPDATE SET
                        hue_bias_json = EXCLUDED.hue_bias_json,
                        neutral_affinity = EXCLUDED.neutral_affinity,
                        saturation_cap_adjust = EXCLUDED.saturation_cap_adjust,
                        lightness_bias = EXCLUDED.lightness_bias,
                        event_count = EXCLUDED.event_count,
                        updated_at = EXCLUDED.updated_at
                """, 
                    features.user_id,
                    json.dumps(features.hue_bias),
                    features.neutral_affinity,
                    features.saturation_cap_adjust,
                    features.lightness_bias,
                    features.event_count,
                    features.updated_at
                )
            finally:
                await conn.close()
            
            # Update cache
            await self._cache_features_async(features)
            logger.info(f"Updated features for user {features.user_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to update features for user {features.user_id}: {e}")
            return False
    
    def invalidate_cache_sync(self, user_id: str) -> bool:
        """Remove user features from cache synchronously."""
        if not self.enable_redis:
            return False
        
        try:
            pool = self._get_redis_pool()
            if not pool:
                return False
            
            redis_client = redis.Redis(connection_pool=pool)
            cache_key = self._get_cache_key(user_id)
            deleted = redis_client.delete(cache_key)
            
            if deleted:
                logger.debug(f"Invalidated cache for user {user_id}")
            return bool(deleted)
        
        except Exception as e:
            logger.warning(f"Failed to invalidate cache for user {user_id}: {e}")
            return False
    
    async def invalidate_cache_async(self, user_id: str) -> bool:
        """Remove user features from cache asynchronously."""
        if not self.enable_redis:
            return False
        
        try:
            pool = self._get_async_redis_pool()
            if not pool:
                return False
            
            async_redis = aioredis.Redis(connection_pool=pool)
            cache_key = self._get_cache_key(user_id)
            deleted = await async_redis.delete(cache_key)
            
            if deleted:
                logger.debug(f"Invalidated cache for user {user_id}")
            return bool(deleted)
        
        except Exception as e:
            logger.warning(f"Failed to invalidate cache for user {user_id}: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_requests = self.stats['cache_hits'] + self.stats['cache_misses']
        cache_hit_rate = self.stats['cache_hits'] / total_requests if total_requests > 0 else 0.0
        
        total_db_requests = self.stats['db_hits'] + self.stats['db_misses']
        db_hit_rate = self.stats['db_hits'] / total_db_requests if total_db_requests > 0 else 0.0
        
        return {
            'cache_enabled': self.enable_redis,
            'cache_hit_rate': cache_hit_rate,
            'db_hit_rate': db_hit_rate,
            'stats': self.stats.copy(),
            'ttl_seconds': self.ttl_seconds
        }


# Global instance (initialized in app startup)
feature_cache: Optional[FeatureCacheManager] = None


def init_feature_cache(redis_url: Optional[str] = None, 
                      db_url: Optional[str] = None,
                      ttl_days: int = 7) -> FeatureCacheManager:
    """Initialize global feature cache manager."""
    global feature_cache
    feature_cache = FeatureCacheManager(
        redis_url=redis_url,
        db_url=db_url,
        ttl_days=ttl_days
    )
    return feature_cache


def get_feature_cache() -> FeatureCacheManager:
    """Get global feature cache manager."""
    if feature_cache is None:
        raise RuntimeError("Feature cache not initialized. Call init_feature_cache() first.")
    return feature_cache
