"""
StyleSync Phase 4 Observability System
Structured logging, metrics, and tracing for production monitoring.
"""
import asyncio
import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional
from functools import wraps

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CollectorRegistry
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False


class MetricsCollector:
    """Prometheus metrics collector for StyleSync."""
    
    def __init__(self):
        if not PROMETHEUS_AVAILABLE:
            self.enabled = False
            return
            
        self.enabled = True
        self.registry = CollectorRegistry()
        
        # Counters
        self.advice_requests_total = Counter(
            'advice_requests_total',
            'Total advice requests',
            ['mode'],
            registry=self.registry
        )
        
        self.advice_errors_total = Counter(
            'advice_errors_total', 
            'Total advice errors',
            ['type'],
            registry=self.registry
        )
        
        self.advice_degraded_total = Counter(
            'advice_degraded_total',
            'Total degraded responses',
            ['phase'],
            registry=self.registry
        )
        
        self.cache_hits_total = Counter(
            'cache_hits_total',
            'Total cache hits',
            ['layer'],
            registry=self.registry
        )
        
        self.cache_misses_total = Counter(
            'cache_misses_total',
            'Total cache misses', 
            ['layer'],
            registry=self.registry
        )
        
        # Histograms
        self.advice_total_duration_ms = Histogram(
            'advice_total_duration_ms',
            'Total advice duration in milliseconds',
            registry=self.registry,
            buckets=[50, 100, 250, 500, 750, 1000, 1500, 2000, 3000, 5000]
        )
        
        self.segmentation_duration_ms = Histogram(
            'segmentation_duration_ms',
            'Segmentation duration in milliseconds',
            registry=self.registry,
            buckets=[100, 200, 400, 600, 800, 1000, 1200, 1500, 2000]
        )
        
        self.extraction_duration_ms = Histogram(
            'extraction_duration_ms',
            'Color extraction duration in milliseconds',
            registry=self.registry,
            buckets=[50, 100, 150, 200, 250, 300, 400, 500]
        )
        
        self.harmony_duration_ms = Histogram(
            'harmony_duration_ms',
            'Harmony generation duration in milliseconds',
            registry=self.registry,
            buckets=[10, 20, 50, 100, 150, 200, 300]
        )
        
        self.mask_area_ratio = Histogram(
            'mask_area_ratio',
            'Distribution of mask area ratios',
            registry=self.registry,
            buckets=[0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 0.95, 0.99]
        )
        
        # Gauges
        self.requests_in_flight = Gauge(
            'requests_in_flight',
            'Number of requests currently being processed',
            registry=self.registry
        )
    
    def record_request(self, mode: str):
        """Record a new request."""
        if self.enabled:
            self.advice_requests_total.labels(mode=mode).inc()
            self.requests_in_flight.inc()
    
    def record_request_complete(self):
        """Record request completion."""
        if self.enabled:
            self.requests_in_flight.dec()
    
    def record_error(self, error_type: str):
        """Record an error."""
        if self.enabled:
            self.advice_errors_total.labels(type=error_type).inc()
    
    def record_degraded(self, phase: str):
        """Record a degraded response."""
        if self.enabled:
            self.advice_degraded_total.labels(phase=phase).inc()
    
    def record_cache_hit(self, layer: str):
        """Record a cache hit."""
        if self.enabled:
            self.cache_hits_total.labels(layer=layer).inc()
    
    def record_cache_miss(self, layer: str):
        """Record a cache miss."""
        if self.enabled:
            self.cache_misses_total.labels(layer=layer).inc()
    
    def record_duration(self, metric_name: str, duration_ms: float):
        """Record a duration metric."""
        if not self.enabled:
            return
            
        metric = getattr(self, metric_name, None)
        if metric:
            metric.observe(duration_ms)
    
    def record_mask_area_ratio(self, ratio: float):
        """Record mask area ratio."""
        if self.enabled:
            self.mask_area_ratio.observe(ratio)
    
    def get_metrics(self) -> str:
        """Get Prometheus metrics in text format."""
        if self.enabled:
            return generate_latest(self.registry).decode('utf-8')
        return ""


class StructuredLogger:
    """Structured logger for StyleSync with JSON output."""
    
    def __init__(self, name: str = "stylesync", level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Create JSON formatter
        handler = logging.StreamHandler()
        formatter = JSONFormatter()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # Prevent propagation to avoid duplicate logs
        self.logger.propagate = False
    
    def log_request_start(self, request_id: str, input_mode: str, **kwargs):
        """Log request start."""
        self.logger.info("Request started", extra={
            'request_id': request_id,
            'input_mode': input_mode,
            'event': 'request_start',
            **kwargs
        })
    
    def log_request_complete(self, request_id: str, duration_ms: float, degraded: bool = False, **kwargs):
        """Log request completion."""
        self.logger.info("Request completed", extra={
            'request_id': request_id,
            'duration_ms': duration_ms,
            'degraded': degraded,
            'event': 'request_complete',
            **kwargs
        })
    
    def log_phase_start(self, request_id: str, phase: str, **kwargs):
        """Log phase start."""
        self.logger.debug(f"Phase {phase} started", extra={
            'request_id': request_id,
            'phase': phase,
            'event': 'phase_start',
            **kwargs
        })
    
    def log_phase_complete(self, request_id: str, phase: str, duration_ms: float, cache_hit: bool = False, **kwargs):
        """Log phase completion."""
        self.logger.info(f"Phase {phase} completed", extra={
            'request_id': request_id,
            'phase': phase,
            'duration_ms': duration_ms,
            'cache_hit': cache_hit,
            'event': 'phase_complete',
            **kwargs
        })
    
    def log_cache_event(self, request_id: str, layer: str, operation: str, key: str, hit: bool = None, **kwargs):
        """Log cache operations."""
        self.logger.debug(f"Cache {operation}", extra={
            'request_id': request_id,
            'cache_layer': layer,
            'cache_operation': operation,
            'cache_key': key[:20] + "..." if len(key) > 20 else key,
            'cache_hit': hit,
            'event': 'cache_operation',
            **kwargs
        })
    
    def log_error(self, request_id: str, error_type: str, error_message: str, **kwargs):
        """Log errors."""
        self.logger.error(f"Error: {error_type}", extra={
            'request_id': request_id,
            'error_type': error_type,
            'error_message': error_message,
            'event': 'error',
            **kwargs
        })


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        import json
        
        log_entry = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                          'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process', 'getMessage']:
                log_entry[key] = value
        
        return json.dumps(log_entry)


class TracingManager:
    """OpenTelemetry tracing manager."""
    
    def __init__(self, service_name: str = "stylesync", jaeger_endpoint: Optional[str] = None):
        self.enabled = OPENTELEMETRY_AVAILABLE
        
        if not self.enabled:
            return
        
        # Configure tracer
        trace.set_tracer_provider(TracerProvider())
        self.tracer = trace.get_tracer(service_name)
        
        # Configure Jaeger exporter if endpoint provided
        if jaeger_endpoint:
            jaeger_exporter = JaegerExporter(
                agent_host_name=jaeger_endpoint.split(':')[0],
                agent_port=int(jaeger_endpoint.split(':')[1]) if ':' in jaeger_endpoint else 14268,
            )
            
            span_processor = BatchSpanProcessor(jaeger_exporter)
            trace.get_tracer_provider().add_span_processor(span_processor)
    
    @contextmanager
    def trace_span(self, name: str, **attributes):
        """Create a traced span."""
        if not self.enabled:
            yield None
            return
        
        with self.tracer.start_as_current_span(name) as span:
            for key, value in attributes.items():
                span.set_attribute(key, str(value))
            yield span
    
    def instrument_fastapi(self, app):
        """Instrument FastAPI application."""
        if self.enabled:
            FastAPIInstrumentor.instrument_app(app)


class ObservabilityManager:
    """Main observability manager combining metrics, logging, and tracing."""
    
    def __init__(self, 
                 service_name: str = "stylesync",
                 log_level: str = "INFO",
                 jaeger_endpoint: Optional[str] = None):
        self.metrics = MetricsCollector()
        self.logger = StructuredLogger(service_name, log_level)
        self.tracing = TracingManager(service_name, jaeger_endpoint)
    
    @contextmanager
    def observe_request(self, request_id: str, input_mode: str, **kwargs):
        """Observe a complete request with metrics, logging, and tracing."""
        start_time = time.time()
        
        # Start observability
        self.metrics.record_request(input_mode)
        self.logger.log_request_start(request_id, input_mode, **kwargs)
        
        with self.tracing.trace_span("advice_request", 
                                   request_id=request_id, 
                                   input_mode=input_mode) as span:
            try:
                yield span
                
                # Success
                duration_ms = (time.time() - start_time) * 1000
                self.metrics.record_duration('advice_total_duration_ms', duration_ms)
                self.logger.log_request_complete(request_id, duration_ms, **kwargs)
                
            except Exception as e:
                # Error
                duration_ms = (time.time() - start_time) * 1000
                error_type = type(e).__name__
                
                self.metrics.record_error(error_type)
                self.logger.log_error(request_id, error_type, str(e))
                
                if span:
                    span.set_attribute("error", True)
                    span.set_attribute("error.type", error_type)
                    span.set_attribute("error.message", str(e))
                
                raise
            finally:
                self.metrics.record_request_complete()
    
    @contextmanager  
    def observe_phase(self, request_id: str, phase: str, cache_key: Optional[str] = None):
        """Observe a processing phase."""
        start_time = time.time()
        
        self.logger.log_phase_start(request_id, phase)
        
        with self.tracing.trace_span(f"phase_{phase}", 
                                   request_id=request_id,
                                   phase=phase) as span:
            try:
                cache_hit = False
                yield {'cache_hit': lambda: setattr(self, '_cache_hit', True)}
                
                # Check if cache hit was recorded
                cache_hit = getattr(self, '_cache_hit', False)
                if hasattr(self, '_cache_hit'):
                    delattr(self, '_cache_hit')
                
                duration_ms = (time.time() - start_time) * 1000
                
                # Record metrics
                metric_name = f"{phase}_duration_ms"
                self.metrics.record_duration(metric_name, duration_ms)
                
                if cache_hit:
                    self.metrics.record_cache_hit(phase)
                else:
                    self.metrics.record_cache_miss(phase)
                
                # Log completion
                self.logger.log_phase_complete(request_id, phase, duration_ms, cache_hit)
                
                if span:
                    span.set_attribute("duration_ms", duration_ms)
                    span.set_attribute("cache_hit", cache_hit)
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                error_type = type(e).__name__
                
                self.logger.log_error(request_id, f"phase_{phase}", str(e))
                
                if span:
                    span.set_attribute("error", True)
                    span.set_attribute("error.type", error_type)
                
                raise
    
    def get_metrics_endpoint(self):
        """Get metrics for Prometheus scraping."""
        return self.metrics.get_metrics()


# Global observability instance
observability = ObservabilityManager()


def instrumented(phase: str):
    """Decorator for instrumenting functions with observability."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            request_id = kwargs.get('request_id', 'unknown')
            
            with observability.observe_phase(request_id, phase):
                return await func(*args, **kwargs)
        
        @wraps(func) 
        def sync_wrapper(*args, **kwargs):
            request_id = kwargs.get('request_id', 'unknown')
            
            with observability.observe_phase(request_id, phase):
                return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator
