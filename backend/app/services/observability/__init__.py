"""
Observability module for What2Wear color extraction pipeline.

This module provides comprehensive monitoring, logging, and metrics collection
for the StyleSync ColorMatch MVP implementation.
"""

from .metrics import (
    PerformanceMetrics,
    ColorExtractionMetrics,
    MetricsCollector,
    ColorExtractionLogger,
    get_metrics_collector,
    get_extraction_logger,
    performance_monitor,
    performance_tracked,
    log_memory_usage,
    force_garbage_collection
)

# Phase 4 observability manager (graceful fallback)
try:
    from .observability import ObservabilityManager
    observability = ObservabilityManager()
except ImportError:
    # Fallback for testing
    class MockObservability:
        def setup_logging(self): pass
        def setup_metrics(self): pass
        def setup_tracing(self): pass
        def log_request(self, **kwargs): pass
        def record_metric(self, name, value, **kwargs): pass
        def start_trace(self, name): return self
        def __enter__(self): return self
        def __exit__(self, *args): pass
    
    observability = MockObservability()

__all__ = [
    'PerformanceMetrics',
    'ColorExtractionMetrics', 
    'MetricsCollector',
    'ColorExtractionLogger',
    'get_metrics_collector',
    'get_extraction_logger',
    'performance_monitor',
    'performance_tracked',
    'log_memory_usage',
    'force_garbage_collection'
]
