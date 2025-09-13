"""
StyleSync Metrics Collection
In-process metrics collection for monitoring and performance tracking.
"""
import time
from collections import defaultdict, Counter
from typing import Dict, List, Optional
from threading import Lock


class MetricsCollector:
    """Simple in-process metrics collector."""
    
    def __init__(self):
        """Initialize metrics collector."""
        self._lock = Lock()
        self._counters: Dict[str, int] = Counter()
        self._timings: Dict[str, List[float]] = defaultdict(list)
        self._mask_ratios: List[float] = []
        self._start_time = time.time()
    
    def increment_request_count(self):
        """Increment total request counter."""
        with self._lock:
            self._counters["seg_requests_total"] += 1
    
    def increment_engine_count(self, engine: str):
        """Increment engine usage counter."""
        with self._lock:
            self._counters[f"seg_engine_used_total_{engine}"] += 1
    
    def increment_fallback_count(self):
        """Increment fallback usage counter."""
        with self._lock:
            self._counters["seg_fallback_total"] += 1
    
    def increment_failure_count(self, error_type: str):
        """Increment failure counter by error type."""
        with self._lock:
            self._counters[f"seg_failed_total_{error_type}"] += 1
    
    def record_timing(self, operation: str, duration_ms: float):
        """Record timing for an operation."""
        with self._lock:
            self._timings[f"{operation}_duration_ms"].append(duration_ms)
    
    def record_mask_ratio(self, ratio: float):
        """Record mask area ratio."""
        with self._lock:
            self._mask_ratios.append(ratio)
    
    def get_counters(self) -> Dict[str, int]:
        """Get current counter values."""
        with self._lock:
            return dict(self._counters)
    
    def get_timing_stats(self) -> Dict[str, Dict[str, float]]:
        """Get timing statistics."""
        with self._lock:
            stats = {}
            for operation, timings in self._timings.items():
                if timings:
                    stats[operation] = {
                        "count": len(timings),
                        "mean": sum(timings) / len(timings),
                        "min": min(timings),
                        "max": max(timings),
                        "p50": self._percentile(timings, 50),
                        "p95": self._percentile(timings, 95)
                    }
            return stats
    
    def get_mask_ratio_stats(self) -> Dict[str, float]:
        """Get mask ratio statistics."""
        with self._lock:
            if not self._mask_ratios:
                return {}
            
            return {
                "count": len(self._mask_ratios),
                "mean": sum(self._mask_ratios) / len(self._mask_ratios),
                "min": min(self._mask_ratios),
                "max": max(self._mask_ratios),
                "p50": self._percentile(self._mask_ratios, 50),
                "p95": self._percentile(self._mask_ratios, 95)
            }
    
    def get_uptime_seconds(self) -> float:
        """Get service uptime in seconds."""
        return time.time() - self._start_time
    
    def get_summary(self) -> Dict[str, any]:
        """Get complete metrics summary."""
        return {
            "uptime_seconds": self.get_uptime_seconds(),
            "counters": self.get_counters(),
            "timing_stats": self.get_timing_stats(),
            "mask_ratio_stats": self.get_mask_ratio_stats()
        }
    
    def reset(self):
        """Reset all metrics (for testing)."""
        with self._lock:
            self._counters.clear()
            self._timings.clear()
            self._mask_ratios.clear()
            self._start_time = time.time()
    
    @staticmethod
    def _percentile(data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * percentile / 100
        f = int(k)
        c = k - f
        
        if f + 1 < len(sorted_data):
            return sorted_data[f] + c * (sorted_data[f + 1] - sorted_data[f])
        else:
            return sorted_data[f]


# Global metrics instance
_metrics: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Get or create global metrics collector."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


def reset_metrics():
    """Reset global metrics (for testing)."""
    global _metrics
    if _metrics is not None:
        _metrics.reset()
