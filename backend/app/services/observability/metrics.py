"""
Observability metrics collection for What2Wear color extraction pipeline.

This module provides comprehensive metrics, logging, and performance monitoring
for the StyleSync ColorMatch MVP implementation in Phase 2.
"""

import time
import psutil
import gc
from typing import Dict, Any, Optional, List
from functools import wraps
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import threading
from collections import defaultdict, deque
import numpy as np
from loguru import logger


@dataclass
class PerformanceMetrics:
    """Performance metrics for color extraction operations."""
    operation_name: str
    duration_ms: float
    memory_usage_mb: float
    cpu_percent: float
    pixel_count: int
    cluster_count: int
    timestamp: float
    error: Optional[str] = None


@dataclass
class ColorExtractionMetrics:
    """Comprehensive metrics for color extraction pipeline."""
    total_duration_ms: float
    clustering_duration_ms: float
    base_selection_duration_ms: float
    palette_construction_duration_ms: float
    
    input_image_size: tuple
    mask_pixel_count: int
    sampled_pixel_count: int
    
    cluster_count: int
    final_palette_size: int
    base_color_index: int
    
    memory_peak_mb: float
    cpu_peak_percent: float
    
    neutral_colors_detected: int
    spatial_cohesion_applied: bool
    
    error_count: int
    warnings: List[str]


class MetricsCollector:
    """Thread-safe metrics collector for color extraction operations."""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self._lock = threading.Lock()
        self._metrics_history: deque = deque(maxlen=max_history)
        self._operation_counts = defaultdict(int)
        self._error_counts = defaultdict(int)
        self._performance_stats = defaultdict(list)
        
    def record_performance(self, metrics: PerformanceMetrics) -> None:
        """Record performance metrics for an operation."""
        with self._lock:
            self._metrics_history.append(metrics)
            self._operation_counts[metrics.operation_name] += 1
            
            if metrics.error:
                self._error_counts[metrics.operation_name] += 1
            
            self._performance_stats[metrics.operation_name].append({
                'duration_ms': metrics.duration_ms,
                'memory_mb': metrics.memory_usage_mb,
                'cpu_percent': metrics.cpu_percent
            })
            
            # Keep only recent stats to prevent memory growth
            if len(self._performance_stats[metrics.operation_name]) > 100:
                self._performance_stats[metrics.operation_name].pop(0)
    
    def get_operation_stats(self, operation_name: str) -> Dict[str, Any]:
        """Get aggregated statistics for a specific operation."""
        with self._lock:
            if operation_name not in self._performance_stats:
                return {}
            
            stats = self._performance_stats[operation_name]
            if not stats:
                return {}
            
            durations = [s['duration_ms'] for s in stats]
            memory_usage = [s['memory_mb'] for s in stats]
            cpu_usage = [s['cpu_percent'] for s in stats]
            
            return {
                'operation_name': operation_name,
                'total_calls': self._operation_counts[operation_name],
                'error_count': self._error_counts[operation_name],
                'error_rate': self._error_counts[operation_name] / max(1, self._operation_counts[operation_name]),
                'duration_stats': {
                    'mean_ms': np.mean(durations),
                    'median_ms': np.median(durations),
                    'p95_ms': np.percentile(durations, 95),
                    'p99_ms': np.percentile(durations, 99),
                    'min_ms': np.min(durations),
                    'max_ms': np.max(durations)
                },
                'memory_stats': {
                    'mean_mb': np.mean(memory_usage),
                    'peak_mb': np.max(memory_usage)
                },
                'cpu_stats': {
                    'mean_percent': np.mean(cpu_usage),
                    'peak_percent': np.max(cpu_usage)
                }
            }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get aggregated statistics for all operations."""
        with self._lock:
            all_stats = {}
            for operation_name in self._operation_counts.keys():
                all_stats[operation_name] = self.get_operation_stats(operation_name)
            
            return {
                'operations': all_stats,
                'total_operations': sum(self._operation_counts.values()),
                'total_errors': sum(self._error_counts.values()),
                'overall_error_rate': sum(self._error_counts.values()) / max(1, sum(self._operation_counts.values()))
            }
    
    def get_recent_metrics(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the most recent performance metrics."""
        with self._lock:
            recent = list(self._metrics_history)[-limit:]
            return [asdict(metric) for metric in recent]


# Global metrics collector instance
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return _metrics_collector


@contextmanager
def performance_monitor(operation_name: str, pixel_count: int = 0, cluster_count: int = 0):
    """Context manager for monitoring performance of operations."""
    start_time = time.time()
    start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
    start_cpu = psutil.cpu_percent()
    
    error_msg = None
    
    try:
        yield
    except Exception as e:
        error_msg = str(e)
        raise
    finally:
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        end_cpu = psutil.cpu_percent()
        
        metrics = PerformanceMetrics(
            operation_name=operation_name,
            duration_ms=(end_time - start_time) * 1000,
            memory_usage_mb=max(end_memory, start_memory),
            cpu_percent=max(end_cpu, start_cpu),
            pixel_count=pixel_count,
            cluster_count=cluster_count,
            timestamp=end_time,
            error=error_msg
        )
        
        _metrics_collector.record_performance(metrics)
        
        # Log performance info
        if error_msg:
            logger.error(f"Operation {operation_name} failed after {metrics.duration_ms:.1f}ms: {error_msg}")
        else:
            logger.info(f"Operation {operation_name} completed in {metrics.duration_ms:.1f}ms "
                       f"(memory: {metrics.memory_usage_mb:.1f}MB, CPU: {metrics.cpu_percent:.1f}%)")


def performance_tracked(operation_name: str):
    """Decorator for automatically tracking function performance."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Try to extract pixel/cluster count from args/kwargs
            pixel_count = 0
            cluster_count = 0
            
            # Look for common parameter names
            for arg in args:
                if hasattr(arg, 'shape') and len(getattr(arg, 'shape', [])) >= 2:
                    # Looks like an image array
                    shape = arg.shape
                    pixel_count = shape[0] * shape[1] if len(shape) >= 2 else 0
                    break
            
            if 'n_clusters' in kwargs:
                cluster_count = kwargs['n_clusters']
            elif 'cluster_count' in kwargs:
                cluster_count = kwargs['cluster_count']
            
            with performance_monitor(operation_name, pixel_count, cluster_count):
                return func(*args, **kwargs)
        return wrapper
    return decorator


class ColorExtractionLogger:
    """Enhanced logger for color extraction operations."""
    
    def __init__(self):
        self._current_extraction: Optional[Dict[str, Any]] = None
        self._extraction_id_counter = 0
    
    def start_extraction(self, image_size: tuple, mask_pixel_count: int) -> str:
        """Start logging a new color extraction operation."""
        self._extraction_id_counter += 1
        extraction_id = f"extraction_{self._extraction_id_counter}"
        
        self._current_extraction = {
            'id': extraction_id,
            'start_time': time.time(),
            'image_size': image_size,
            'mask_pixel_count': mask_pixel_count,
            'warnings': [],
            'stages': {}
        }
        
        logger.info(f"Starting color extraction {extraction_id} "
                   f"(image: {image_size}, mask pixels: {mask_pixel_count})")
        
        return extraction_id
    
    def log_stage(self, stage_name: str, duration_ms: float, **kwargs):
        """Log completion of an extraction stage."""
        if self._current_extraction:
            self._current_extraction['stages'][stage_name] = {
                'duration_ms': duration_ms,
                'timestamp': time.time(),
                **kwargs
            }
            
            logger.debug(f"Extraction {self._current_extraction['id']} - "
                        f"{stage_name} completed in {duration_ms:.1f}ms")
    
    def log_warning(self, message: str):
        """Log a warning for the current extraction."""
        if self._current_extraction:
            self._current_extraction['warnings'].append(message)
        logger.warning(f"Color extraction warning: {message}")
    
    def finish_extraction(self, palette_size: int, base_color_index: int) -> ColorExtractionMetrics:
        """Finish logging and return comprehensive metrics."""
        if not self._current_extraction:
            raise ValueError("No active extraction to finish")
        
        total_duration = (time.time() - self._current_extraction['start_time']) * 1000
        stages = self._current_extraction['stages']
        
        metrics = ColorExtractionMetrics(
            total_duration_ms=total_duration,
            clustering_duration_ms=stages.get('clustering', {}).get('duration_ms', 0),
            base_selection_duration_ms=stages.get('base_selection', {}).get('duration_ms', 0),
            palette_construction_duration_ms=stages.get('palette_construction', {}).get('duration_ms', 0),
            
            input_image_size=self._current_extraction['image_size'],
            mask_pixel_count=self._current_extraction['mask_pixel_count'],
            sampled_pixel_count=stages.get('sampling', {}).get('pixel_count', 0),
            
            cluster_count=stages.get('clustering', {}).get('cluster_count', 0),
            final_palette_size=palette_size,
            base_color_index=base_color_index,
            
            memory_peak_mb=stages.get('memory_peak', {}).get('mb', 0),
            cpu_peak_percent=stages.get('cpu_peak', {}).get('percent', 0),
            
            neutral_colors_detected=stages.get('base_selection', {}).get('neutral_count', 0),
            spatial_cohesion_applied=stages.get('base_selection', {}).get('cohesion_enabled', False),
            
            error_count=0,
            warnings=self._current_extraction['warnings']
        )
        
        logger.info(f"Extraction {self._current_extraction['id']} completed in {total_duration:.1f}ms "
                   f"(palette: {palette_size} colors, base: {base_color_index})")
        
        if metrics.warnings:
            logger.warning(f"Extraction completed with {len(metrics.warnings)} warnings")
        
        self._current_extraction = None
        return metrics


# Global extraction logger instance
_extraction_logger = ColorExtractionLogger()


def get_extraction_logger() -> ColorExtractionLogger:
    """Get the global extraction logger instance."""
    return _extraction_logger


def log_memory_usage(stage_name: str):
    """Log current memory usage for a specific stage."""
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    cpu_percent = process.cpu_percent()
    
    logger.debug(f"Memory usage at {stage_name}: {memory_mb:.1f}MB (CPU: {cpu_percent:.1f}%)")
    
    return {
        'stage': stage_name,
        'memory_mb': memory_mb,
        'cpu_percent': cpu_percent,
        'timestamp': time.time()
    }


def force_garbage_collection():
    """Force garbage collection and log memory recovery."""
    before_mb = psutil.Process().memory_info().rss / 1024 / 1024
    collected = gc.collect()
    after_mb = psutil.Process().memory_info().rss / 1024 / 1024
    
    freed_mb = before_mb - after_mb
    
    if freed_mb > 1:  # Only log if significant memory was freed
        logger.debug(f"Garbage collection freed {freed_mb:.1f}MB "
                    f"(collected {collected} objects)")
    
    return {
        'before_mb': before_mb,
        'after_mb': after_mb,
        'freed_mb': freed_mb,
        'objects_collected': collected
    }
