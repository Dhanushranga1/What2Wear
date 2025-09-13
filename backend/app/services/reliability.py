"""
StyleSync Reliability & Timeout Management
Implements timeouts, circuit breakers, and graceful degradation.
"""
import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, Optional, TypeVar, Union
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TimeoutError(Exception):
    """Custom timeout exception."""
    pass


class CircuitBreakerError(Exception):
    """Circuit breaker open exception."""
    pass


class CircuitBreaker:
    """Simple circuit breaker implementation."""
    
    def __init__(self, 
                 failure_threshold: int = 5, 
                 recovery_timeout: int = 60,
                 expected_exception: type = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def __call__(self, func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await self._execute(func, *args, **kwargs)
        
        @wraps(func) 
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(self._execute_sync(func, *args, **kwargs))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    async def _execute(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerError(f"Circuit breaker is OPEN")
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success - reset failure count
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
            self.failure_count = 0
            
            return result
            
        except self.expected_exception as e:
            self._record_failure()
            raise e
    
    async def _execute_sync(self, func, *args, **kwargs):
        """Execute sync function in async context."""
        return await self._execute(func, *args, **kwargs)
    
    def _record_failure(self):
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        
        return time.time() - self.last_failure_time >= self.recovery_timeout


class TimeoutManager:
    """Manages timeouts for different operations."""
    
    def __init__(self, default_timeout: float = 30.0):
        self.default_timeout = default_timeout
        self.timeouts = {
            'segmentation': 1.2,  # 1200ms
            'extraction': 0.3,    # 300ms  
            'harmony': 0.1,       # 100ms
            'total': 2.5          # 2500ms
        }
    
    @asynccontextmanager
    async def timeout(self, operation: str, custom_timeout: Optional[float] = None):
        """Context manager for timeout handling."""
        timeout_value = custom_timeout or self.timeouts.get(operation, self.default_timeout)
        
        try:
            async with asyncio.timeout(timeout_value):
                yield
        except asyncio.TimeoutError:
            logger.error(f"Timeout in {operation} after {timeout_value}s")
            raise TimeoutError(f"Operation {operation} timed out after {timeout_value}s")
    
    def with_timeout(self, operation: str, timeout: Optional[float] = None):
        """Decorator for adding timeouts to functions."""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                async with self.timeout(operation, timeout):
                    return await func(*args, **kwargs)
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # For sync functions, we can't use asyncio timeout
                # This is a simplified implementation
                return func(*args, **kwargs)
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        
        return decorator


class DegradationManager:
    """Manages graceful degradation scenarios."""
    
    def __init__(self):
        self.fallback_responses = {
            'segmentation_failed': self._segmentation_fallback,
            'extraction_failed': self._extraction_fallback,
            'harmony_failed': self._harmony_fallback
        }
    
    def get_fallback_response(self, failure_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get fallback response for failure type."""
        fallback_func = self.fallback_responses.get(failure_type)
        if fallback_func:
            return fallback_func(context)
        
        return self._generic_fallback(context)
    
    def _segmentation_fallback(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback for segmentation failures."""
        return {
            'mask_png_b64': None,
            'item_rgba_png_b64': None,
            'mask_area_ratio': 0.0,
            'engine_used': 'degraded',
            'fallback_used': True,
            'degraded': True,
            'fallback_reason': 'segmentation_unavailable'
        }
    
    def _extraction_fallback(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback for color extraction failures."""
        # Try to infer rough color from image metadata or use neutral
        fallback_color = context.get('fallback_color', '#808080')
        
        return {
            'palette': [
                {'hex': fallback_color, 'ratio': 0.6},
                {'hex': '#FFFFFF', 'ratio': 0.25},
                {'hex': '#F5F5F5', 'ratio': 0.15}
            ],
            'base_color': {
                'hex': fallback_color,
                'cluster_index': 0,
                'score_breakdown': {
                    'fallback': True,
                    'confidence': 0.1
                }
            },
            'degraded': True,
            'fallback_reason': 'extraction_failed',
            'sampled_pixels': 0
        }
    
    def _harmony_fallback(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback for harmony generation failures."""
        base_hex = context.get('base_hex', '#808080')
        target_role = context.get('target_role', 'bottom')
        
        # Return base color + neutrals only
        return {
            'suggestions': {
                'neutral': [
                    {
                        'hex': '#FFFFFF',
                        'category': 'neutral',
                        'role_target': target_role,
                        'rationale': ['category:neutral', 'fallback_mode']
                    },
                    {
                        'hex': '#F5F5F5',
                        'category': 'neutral',
                        'role_target': target_role,
                        'rationale': ['category:neutral', 'fallback_mode']
                    }
                ]
            },
            'degraded': True,
            'fallback_reason': 'harmony_generation_failed'
        }
    
    def _generic_fallback(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generic fallback for unknown failures."""
        return {
            'degraded': True,
            'fallback_reason': 'unknown_failure',
            'suggestions': {
                'neutral': [
                    {
                        'hex': '#FFFFFF',
                        'category': 'neutral',
                        'role_target': context.get('target_role', 'bottom'),
                        'rationale': ['category:neutral', 'generic_fallback']
                    }
                ]
            }
        }


class ReliabilityManager:
    """Main reliability manager combining timeouts, circuit breakers, and degradation."""
    
    def __init__(self):
        self.timeout_manager = TimeoutManager()
        self.degradation_manager = DegradationManager()
        
        # Circuit breakers for different components
        self.circuit_breakers = {
            'segmentation': CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=30,
                expected_exception=(TimeoutError, RuntimeError)
            ),
            'extraction': CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=60,
                expected_exception=(TimeoutError, ValueError)
            ),
            'harmony': CircuitBreaker(
                failure_threshold=10,
                recovery_timeout=120,
                expected_exception=(TimeoutError, Exception)
            )
        }
    
    async def execute_with_reliability(self, 
                                     operation: str,
                                     func: Callable,
                                     context: Dict[str, Any],
                                     *args, **kwargs) -> Dict[str, Any]:
        """Execute operation with full reliability protection."""
        
        try:
            # Apply circuit breaker
            circuit_breaker = self.circuit_breakers.get(operation)
            if circuit_breaker:
                # Apply timeout and circuit breaker
                async with self.timeout_manager.timeout(operation):
                    return await circuit_breaker(func)(*args, **kwargs)
            else:
                # Just apply timeout
                async with self.timeout_manager.timeout(operation):
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                    
        except (TimeoutError, CircuitBreakerError, Exception) as e:
            logger.warning(f"Operation {operation} failed: {e}")
            
            # Return degraded response
            fallback_response = self.degradation_manager.get_fallback_response(
                f"{operation}_failed",
                context
            )
            
            # Add error metadata
            fallback_response.update({
                'error_type': type(e).__name__,
                'error_message': str(e),
                'timestamp': time.time()
            })
            
            return fallback_response
    
    def get_circuit_breaker_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers."""
        status = {}
        
        for name, cb in self.circuit_breakers.items():
            status[name] = {
                'state': cb.state,
                'failure_count': cb.failure_count,
                'last_failure_time': cb.last_failure_time,
                'failure_threshold': cb.failure_threshold,
                'recovery_timeout': cb.recovery_timeout
            }
        
        return status
    
    def reset_circuit_breaker(self, operation: str) -> bool:
        """Manually reset a circuit breaker."""
        if operation in self.circuit_breakers:
            cb = self.circuit_breakers[operation]
            cb.state = 'CLOSED'
            cb.failure_count = 0
            cb.last_failure_time = None
            
            logger.info(f"Circuit breaker {operation} manually reset")
            return True
        
        return False
    
    def configure_timeouts(self, timeout_config: Dict[str, float]) -> None:
        """Update timeout configuration."""
        self.timeout_manager.timeouts.update(timeout_config)
        logger.info(f"Updated timeouts: {timeout_config}")


# Global reliability manager instance
reliability_manager = ReliabilityManager()
