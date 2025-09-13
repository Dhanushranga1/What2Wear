"""
Observability endpoints for What2Wear color extraction pipeline.

This module provides FastAPI endpoints for accessing metrics, performance data,
and system health information for the StyleSync ColorMatch MVP.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import psutil
import time

from ..services.observability import get_metrics_collector, get_extraction_logger


router = APIRouter(prefix="/metrics", tags=["observability"])


class SystemHealthResponse(BaseModel):
    """System health and resource usage information."""
    timestamp: float
    memory_usage_mb: float
    memory_percent: float
    cpu_percent: float
    disk_usage_percent: float
    uptime_seconds: float
    status: str


class OperationStatsResponse(BaseModel):
    """Performance statistics for a specific operation."""
    operation_name: str
    total_calls: int
    error_count: int
    error_rate: float
    duration_stats: Dict[str, float]
    memory_stats: Dict[str, float]
    cpu_stats: Dict[str, float]


class MetricsSummaryResponse(BaseModel):
    """Summary of all metrics and performance data."""
    total_operations: int
    total_errors: int
    overall_error_rate: float
    operations: Dict[str, Dict[str, Any]]
    system_health: SystemHealthResponse


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health():
    """Get current system health and resource usage."""
    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()
        cpu_percent = process.cpu_percent()
        
        # Disk usage for current working directory
        disk_usage = psutil.disk_usage('/')
        disk_percent = (disk_usage.used / disk_usage.total) * 100
        
        # System uptime approximation
        uptime = time.time() - psutil.boot_time()
        
        # Determine status based on resource usage
        status = "healthy"
        if memory_percent > 80 or cpu_percent > 80 or disk_percent > 90:
            status = "warning"
        if memory_percent > 95 or cpu_percent > 95 or disk_percent > 95:
            status = "critical"
        
        return SystemHealthResponse(
            timestamp=time.time(),
            memory_usage_mb=memory_info.rss / 1024 / 1024,
            memory_percent=memory_percent,
            cpu_percent=cpu_percent,
            disk_usage_percent=disk_percent,
            uptime_seconds=uptime,
            status=status
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system health: {str(e)}")


@router.get("/suggestions/summary")
async def get_suggestion_metrics_summary():
    """Get summary metrics for color suggestion operations."""
    try:
        metrics_collector = get_metrics_collector()
        
        # Get overall suggestion statistics
        suggest_stats = metrics_collector.get_operation_stats("suggest_colors") or {}
        
        # Extract metadata for detailed analysis
        all_operations = metrics_collector.get_all_operations()
        suggestion_data = {
            "total_requests": suggest_stats.get("total_calls", 0),
            "error_rate": suggest_stats.get("error_rate", 0.0),
            "avg_duration_ms": suggest_stats.get("duration_stats", {}).get("mean", 0.0),
            "input_modes": {},
            "intent_distribution": {},
            "season_distribution": {}
        }
        
        # Aggregate metadata from all suggestion operations
        for operation_data in all_operations.get("suggest_colors", {}).get("calls", []):
            metadata = operation_data.get("metadata", {})
            
            # Track input mode distribution
            input_mode = metadata.get("input_mode", "unknown")
            suggestion_data["input_modes"][input_mode] = suggestion_data["input_modes"].get(input_mode, 0) + 1
            
            # Track intent distribution  
            intent = metadata.get("intent", "unknown")
            suggestion_data["intent_distribution"][intent] = suggestion_data["intent_distribution"].get(intent, 0) + 1
            
            # Track season distribution
            season = metadata.get("season", "unknown") 
            suggestion_data["season_distribution"][season] = suggestion_data["season_distribution"].get(season, 0) + 1
        
        return suggestion_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get suggestion metrics: {str(e)}")


@router.get("/suggestions/performance")
async def get_suggestion_performance():
    """Get detailed performance metrics for color suggestion pipeline."""
    try:
        metrics_collector = get_metrics_collector()
        
        # Get timing breakdowns for different components
        suggest_stats = metrics_collector.get_operation_stats("suggest_colors") or {}
        
        performance_data = {
            "overall": {
                "total_requests": suggest_stats.get("total_calls", 0),
                "avg_duration_ms": suggest_stats.get("duration_stats", {}).get("mean", 0.0),
                "median_duration_ms": suggest_stats.get("duration_stats", {}).get("median", 0.0),
                "p95_duration_ms": suggest_stats.get("duration_stats", {}).get("p95", 0.0)
            },
            "components": {
                "harmony_generation": {"avg_ms": 0.0, "count": 0},
                "wearability_constraints": {"avg_ms": 0.0, "count": 0},
                "swatch_generation": {"avg_ms": 0.0, "count": 0},
                "oneshot_extraction": {"avg_ms": 0.0, "count": 0}
            }
        }
        
        # This would be enhanced with more detailed timing collection in production
        return performance_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")


@router.get("/operations/{operation_name}", response_model=OperationStatsResponse)
async def get_operation_stats(operation_name: str):
    """Get performance statistics for a specific operation."""
    try:
        metrics_collector = get_metrics_collector()
        stats = metrics_collector.get_operation_stats(operation_name)
        
        if not stats:
            raise HTTPException(
                status_code=404, 
                detail=f"No statistics found for operation: {operation_name}"
            )
        
        return OperationStatsResponse(**stats)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get operation stats: {str(e)}"
        )


@router.get("/operations", response_model=List[str])
async def list_operations():
    """List all tracked operations."""
    try:
        metrics_collector = get_metrics_collector()
        all_stats = metrics_collector.get_all_stats()
        return list(all_stats.get('operations', {}).keys())
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to list operations: {str(e)}"
        )


@router.get("/summary", response_model=MetricsSummaryResponse)
async def get_metrics_summary():
    """Get comprehensive metrics summary including system health."""
    try:
        # Get performance metrics
        metrics_collector = get_metrics_collector()
        all_stats = metrics_collector.get_all_stats()
        
        # Get system health
        health_response = await get_system_health()
        
        return MetricsSummaryResponse(
            total_operations=all_stats.get('total_operations', 0),
            total_errors=all_stats.get('total_errors', 0),
            overall_error_rate=all_stats.get('overall_error_rate', 0.0),
            operations=all_stats.get('operations', {}),
            system_health=health_response
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get metrics summary: {str(e)}"
        )


@router.get("/recent")
async def get_recent_metrics(limit: int = Query(10, ge=1, le=100)):
    """Get recent performance metrics."""
    try:
        metrics_collector = get_metrics_collector()
        recent_metrics = metrics_collector.get_recent_metrics(limit)
        
        return {
            "count": len(recent_metrics),
            "metrics": recent_metrics
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get recent metrics: {str(e)}"
        )


@router.get("/performance/top")
async def get_top_performing_operations(
    metric: str = Query("duration_ms", description="Metric to sort by"),
    limit: int = Query(5, ge=1, le=20)
):
    """Get top performing operations by specified metric."""
    try:
        metrics_collector = get_metrics_collector()
        all_stats = metrics_collector.get_all_stats()
        operations = all_stats.get('operations', {})
        
        # Sort operations by the specified metric
        if metric == "duration_ms":
            sorted_ops = sorted(
                operations.items(),
                key=lambda x: x[1].get('duration_stats', {}).get('mean_ms', 0),
                reverse=True
            )
        elif metric == "error_rate":
            sorted_ops = sorted(
                operations.items(),
                key=lambda x: x[1].get('error_rate', 0),
                reverse=True
            )
        elif metric == "total_calls":
            sorted_ops = sorted(
                operations.items(),
                key=lambda x: x[1].get('total_calls', 0),
                reverse=True
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid metric: {metric}. Use 'duration_ms', 'error_rate', or 'total_calls'"
            )
        
        return {
            "metric": metric,
            "top_operations": dict(sorted_ops[:limit])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get top performing operations: {str(e)}"
        )


@router.delete("/reset")
async def reset_metrics():
    """Reset all collected metrics (for testing/debugging)."""
    try:
        # Create new metrics collector to reset data
        from ..observability.metrics import MetricsCollector
        global _metrics_collector
        from ..observability.metrics import _metrics_collector
        _metrics_collector = MetricsCollector()
        
        return {"message": "Metrics reset successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to reset metrics: {str(e)}"
        )
