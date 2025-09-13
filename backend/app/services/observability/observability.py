"""
Phase 4 Observability Manager
Comprehensive monitoring, logging, and tracing for StyleSync unified API.
"""

import json
import logging
import time
from typing import Dict, Any, Optional, Union
from datetime import datetime
import os

# Optional dependencies with graceful fallback
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

try:
    from opentelemetry import trace
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False


class ObservabilityManager:
    """
    Unified observability manager for Phase 4.
    Handles logging, metrics, and distributed tracing.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("stylesync.phase4")
        self.metrics = {}
        self.tracer = None
        
        self.setup_logging()
        if PROMETHEUS_AVAILABLE:
            self.setup_metrics()
        if TRACING_AVAILABLE:
            self.setup_tracing()
    
    def setup_logging(self):
        """Configure structured JSON logging."""
        # Create formatter for structured logs
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_obj = {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                }
                
                # Add extra fields
                if hasattr(record, 'request_id'):
                    log_obj['request_id'] = record.request_id
                if hasattr(record, 'user_id'):
                    log_obj['user_id'] = record.user_id
                if hasattr(record, 'endpoint'):
                    log_obj['endpoint'] = record.endpoint
                if hasattr(record, 'processing_time_ms'):
                    log_obj['processing_time_ms'] = record.processing_time_ms
                
                return json.dumps(log_obj)
        
        # Configure handler
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(handler)
        
        # Prevent duplicate logs
        self.logger.propagate = False
    
    def setup_metrics(self):
        """Initialize Prometheus metrics."""
        if not PROMETHEUS_AVAILABLE:
            return
        
        # Request metrics
        self.metrics['requests_total'] = Counter(
            'stylesync_requests_total',
            'Total requests processed',
            ['method', 'endpoint', 'status']
        )
        
        self.metrics['request_duration'] = Histogram(
            'stylesync_request_duration_seconds',
            'Request processing time',
            ['endpoint'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
        )
        
        # Cache metrics
        self.metrics['cache_hits'] = Counter(
            'stylesync_cache_hits_total',
            'Cache hits',
            ['layer']
        )
        
        self.metrics['cache_misses'] = Counter(
            'stylesync_cache_misses_total',
            'Cache misses',
            ['layer']
        )
        
        self.metrics['cache_hit_ratio'] = Gauge(
            'stylesync_cache_hit_ratio',
            'Cache hit ratio',
            ['layer']
        )
        
        # Phase metrics
        self.metrics['phase_duration'] = Histogram(
            'stylesync_phase_duration_seconds',
            'Phase processing time',
            ['phase'],
            buckets=[0.05, 0.1, 0.3, 0.6, 1.2, 2.4, 5.0]
        )
        
        # Error metrics
        self.metrics['errors_total'] = Counter(
            'stylesync_errors_total',
            'Total errors',
            ['type']
        )
    
    def setup_tracing(self):
        """Initialize distributed tracing."""
        if not TRACING_AVAILABLE:
            return
        
        # Configure tracer
        trace.set_tracer_provider(TracerProvider())
        self.tracer = trace.get_tracer("stylesync.phase4")
        
        # Configure exporter if endpoint provided
        tracing_endpoint = os.getenv('STYLESYNC_TRACING_ENDPOINT')
        if tracing_endpoint:
            jaeger_exporter = JaegerExporter(
                agent_host_name="localhost",
                agent_port=6831,
            )
            span_processor = BatchSpanProcessor(jaeger_exporter)
            trace.get_tracer_provider().add_span_processor(span_processor)
    
    def log_request(self, 
                   request_id: str,
                   endpoint: str,
                   method: str = "POST",
                   status: int = 200,
                   processing_time_ms: float = 0,
                   user_id: Optional[str] = None,
                   input_mode: Optional[str] = None,
                   cache_hits: Optional[Dict[str, bool]] = None,
                   **kwargs):
        """Log request with structured data."""
        extra = {
            'request_id': request_id,
            'endpoint': endpoint,
            'method': method,
            'status': status,
            'processing_time_ms': processing_time_ms,
        }
        
        if user_id:
            extra['user_id'] = user_id
        if input_mode:
            extra['input_mode'] = input_mode
        if cache_hits:
            extra['cache_hits'] = cache_hits
        
        # Add any additional fields
        extra.update(kwargs)
        
        # Log with appropriate level
        if status >= 500:
            level = logging.ERROR
        elif status >= 400:
            level = logging.WARNING
        else:
            level = logging.INFO
        
        message = f"Request {request_id} completed in {processing_time_ms:.1f}ms with status {status}"
        self.logger.log(level, message, extra=extra)
    
    def record_metric(self, 
                     name: str, 
                     value: Union[int, float], 
                     labels: Optional[Dict[str, str]] = None,
                     metric_type: str = "counter"):
        """Record metric value."""
        if not PROMETHEUS_AVAILABLE or name not in self.metrics:
            return
        
        metric = self.metrics[name]
        labels = labels or {}
        
        if metric_type == "counter":
            if labels:
                metric.labels(**labels).inc(value)
            else:
                metric.inc(value)
        elif metric_type == "histogram":
            if labels:
                metric.labels(**labels).observe(value)
            else:
                metric.observe(value)
        elif metric_type == "gauge":
            if labels:
                metric.labels(**labels).set(value)
            else:
                metric.set(value)
    
    def start_trace(self, operation_name: str, **attributes):
        """Start a new trace span."""
        if not self.tracer:
            return MockSpan()
        
        span = self.tracer.start_span(operation_name)
        
        # Add attributes
        for key, value in attributes.items():
            span.set_attribute(key, value)
        
        return span
    
    def get_metrics_output(self) -> str:
        """Get Prometheus metrics output."""
        if not PROMETHEUS_AVAILABLE:
            return "# Prometheus not available\n"
        
        return generate_latest()
    
    def get_metrics_content_type(self) -> str:
        """Get metrics content type."""
        if not PROMETHEUS_AVAILABLE:
            return "text/plain"
        
        return CONTENT_TYPE_LATEST


class MockSpan:
    """Mock span for when tracing is not available."""
    
    def __init__(self):
        pass
    
    def set_attribute(self, key, value):
        pass
    
    def set_status(self, status):
        pass
    
    def end(self):
        pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# Module-level utilities
def performance_timer():
    """Context manager for timing operations."""
    class Timer:
        def __init__(self):
            self.start_time = None
            self.duration = None
        
        def __enter__(self):
            self.start_time = time.time()
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.duration = (time.time() - self.start_time) * 1000  # Convert to ms
    
    return Timer()


def log_performance(operation: str, duration_ms: float, **kwargs):
    """Log performance data."""
    logger = logging.getLogger("stylesync.performance")
    extra = {
        'operation': operation,
        'duration_ms': duration_ms,
        **kwargs
    }
    logger.info(f"Operation {operation} completed in {duration_ms:.1f}ms", extra=extra)
