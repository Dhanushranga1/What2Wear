"""
Rate limiting service for Phase 5 API protection.
"""

import logging
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import threading
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class RateLimit:
    """Rate limit configuration."""
    requests: int      # Number of requests allowed
    window_seconds: int # Time window in seconds
    burst_requests: int = None  # Burst allowance (defaults to requests)


@dataclass
class RateLimitStatus:
    """Current rate limit status for a client."""
    allowed: bool
    requests_remaining: int
    reset_time: int
    retry_after: Optional[int] = None


class RateLimiter:
    """In-memory rate limiter with sliding window."""
    
    def __init__(self):
        self._windows = defaultdict(list)  # client_key -> [(timestamp, count)]
        self._lock = threading.RLock()
        
        # Default rate limits
        self._limits = {
            'profile_api': RateLimit(requests=60, window_seconds=60),  # 60 requests/minute
            'events_api': RateLimit(requests=1000, window_seconds=60), # 1000 events/minute
            'analytics_api': RateLimit(requests=30, window_seconds=60), # 30 requests/minute
            'default': RateLimit(requests=100, window_seconds=60)       # 100 requests/minute
        }
    
    def check_rate_limit(self, client_id: str, endpoint_category: str = 'default') -> RateLimitStatus:
        """Check if client is within rate limits."""
        
        limit = self._limits.get(endpoint_category, self._limits['default'])
        current_time = int(time.time())
        window_start = current_time - limit.window_seconds
        
        with self._lock:
            # Clean old entries
            client_key = f"{client_id}:{endpoint_category}"
            requests = self._windows[client_key]
            
            # Remove requests outside the current window
            requests[:] = [req for req in requests if req[0] > window_start]
            
            # Count current requests
            current_requests = sum(req[1] for req in requests)
            
            # Check if limit exceeded
            if current_requests >= limit.requests:
                oldest_request = min(req[0] for req in requests) if requests else current_time
                retry_after = max(0, oldest_request + limit.window_seconds - current_time)
                
                return RateLimitStatus(
                    allowed=False,
                    requests_remaining=0,
                    reset_time=oldest_request + limit.window_seconds,
                    retry_after=retry_after
                )
            
            # Allow request and record it
            requests.append((current_time, 1))
            requests_remaining = limit.requests - current_requests - 1
            
            return RateLimitStatus(
                allowed=True,
                requests_remaining=requests_remaining,
                reset_time=current_time + limit.window_seconds
            )
    
    def record_request(self, client_id: str, endpoint_category: str = 'default'):
        """Record a request for rate limiting."""
        # This is called automatically by check_rate_limit
        pass
    
    def get_client_id(self, user_id: str, ip_address: str = None) -> str:
        """Generate a client ID for rate limiting."""
        # Use user_id as primary identifier, fallback to IP
        if user_id:
            return f"user:{user_id}"
        elif ip_address:
            # Hash IP for privacy
            ip_hash = hashlib.md5(ip_address.encode()).hexdigest()[:8]
            return f"ip:{ip_hash}"
        else:
            return "anonymous"
    
    def configure_limit(self, endpoint_category: str, limit: RateLimit):
        """Configure rate limit for an endpoint category."""
        with self._lock:
            self._limits[endpoint_category] = limit
    
    def get_stats(self) -> Dict[str, any]:
        """Get rate limiter statistics."""
        with self._lock:
            stats = {
                'total_clients': len(self._windows),
                'configured_limits': {k: {'requests': v.requests, 'window_seconds': v.window_seconds} 
                                    for k, v in self._limits.items()},
                'active_windows': sum(1 for requests in self._windows.values() if requests)
            }
            return stats
    
    def cleanup_expired(self):
        """Clean up expired rate limit windows."""
        current_time = int(time.time())
        
        with self._lock:
            expired_keys = []
            for client_key, requests in self._windows.items():
                # Find the endpoint category from the key
                endpoint_category = client_key.split(':', 1)[1] if ':' in client_key else 'default'
                limit = self._limits.get(endpoint_category, self._limits['default'])
                window_start = current_time - limit.window_seconds
                
                # Remove expired requests
                requests[:] = [req for req in requests if req[0] > window_start]
                
                # Mark empty windows for removal
                if not requests:
                    expired_keys.append(client_key)
            
            # Remove empty windows
            for key in expired_keys:
                del self._windows[key]
            
            logger.debug(f"Cleaned up {len(expired_keys)} expired rate limit windows")


# Rate limiting middleware for FastAPI
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

def create_rate_limit_dependency(endpoint_category: str = 'default'):
    """Create a FastAPI dependency for rate limiting."""
    
    def rate_limit_dependency(request: Request):
        rate_limiter = get_rate_limiter()
        
        # Extract client information
        user_id = getattr(request.state, 'user_id', None)
        ip_address = request.client.host if request.client else None
        client_id = rate_limiter.get_client_id(user_id, ip_address)
        
        # Check rate limit
        status = rate_limiter.check_rate_limit(client_id, endpoint_category)
        
        if not status.allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "retry_after": status.retry_after,
                    "reset_time": status.reset_time
                },
                headers={
                    "X-RateLimit-Limit": str(rate_limiter._limits[endpoint_category].requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(status.reset_time),
                    "Retry-After": str(status.retry_after)
                }
            )
        
        # Add rate limit headers to response
        request.state.rate_limit_headers = {
            "X-RateLimit-Limit": str(rate_limiter._limits[endpoint_category].requests),
            "X-RateLimit-Remaining": str(status.requests_remaining),
            "X-RateLimit-Reset": str(status.reset_time)
        }
        
        return status
    
    return rate_limit_dependency


# Global rate limiter instance
_rate_limiter = None
_rate_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    global _rate_limiter
    
    if _rate_limiter is None:
        with _rate_limiter_lock:
            if _rate_limiter is None:
                _rate_limiter = RateLimiter()
    
    return _rate_limiter
