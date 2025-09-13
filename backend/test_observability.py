"""
Test script for observability features in What2Wear color extraction pipeline.

This script tests the metrics collection, performance monitoring, and logging
functionality for the StyleSync ColorMatch MVP.
"""

import sys
import time
import numpy as np
from pathlib import Path

# Add the backend directory to the path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.services.observability import (
    get_metrics_collector,
    get_extraction_logger,
    performance_monitor,
    performance_tracked,
    log_memory_usage,
    force_garbage_collection
)


@performance_tracked("test_function")
def test_function_with_tracking(n_iterations: int = 1000):
    """Test function to demonstrate performance tracking."""
    result = 0
    for i in range(n_iterations):
        result += i ** 2
    
    # Simulate some memory usage
    large_array = np.random.random((100, 100))
    return result + np.sum(large_array)


def test_manual_performance_monitoring():
    """Test manual performance monitoring with context manager."""
    print("Testing manual performance monitoring...")
    
    with performance_monitor("manual_test_operation", pixel_count=1000, cluster_count=5):
        # Simulate some work
        time.sleep(0.1)
        
        # Log memory at different stages
        log_memory_usage("middle_of_operation")
        
        # More work
        data = np.random.random((500, 500))
        result = np.mean(data)
        
        print(f"Computed mean: {result:.4f}")


def test_extraction_logger():
    """Test the extraction logger functionality."""
    print("Testing extraction logger...")
    
    logger = get_extraction_logger()
    
    # Start extraction
    extraction_id = logger.start_extraction(
        image_size=(256, 256),
        mask_pixel_count=50000
    )
    
    # Log some stages
    logger.log_stage("pixel_sampling", 15.5, pixel_count=25000, erosion_applied=True)
    logger.log_stage("clustering", 45.2, cluster_count=5, algorithm="MiniBatchKMeans")
    logger.log_warning("Low saturation colors detected")
    logger.log_stage("base_selection", 8.7, base_index=2, neutral_count=1)
    logger.log_stage("palette_construction", 3.1, palette_size=5)
    
    # Finish extraction
    metrics = logger.finish_extraction(palette_size=5, base_color_index=2)
    
    print(f"Extraction {extraction_id} completed")
    print(f"Total duration: {metrics.total_duration_ms:.1f}ms")
    print(f"Warnings: {len(metrics.warnings)}")
    
    return metrics


def test_metrics_collection():
    """Test metrics collection and aggregation."""
    print("Testing metrics collection...")
    
    collector = get_metrics_collector()
    
    # Run some tracked functions
    print("Running tracked functions...")
    test_function_with_tracking(500)
    test_function_with_tracking(1000)
    test_function_with_tracking(1500)
    
    # Run manual monitoring
    test_manual_performance_monitoring()
    
    # Get stats
    print("\nOperation Statistics:")
    test_stats = collector.get_operation_stats("test_function")
    if test_stats:
        print(f"- test_function: {test_stats['total_calls']} calls, "
              f"avg {test_stats['duration_stats']['mean_ms']:.1f}ms")
    
    manual_stats = collector.get_operation_stats("manual_test_operation")
    if manual_stats:
        print(f"- manual_test_operation: {manual_stats['total_calls']} calls, "
              f"avg {manual_stats['duration_stats']['mean_ms']:.1f}ms")
    
    # Get overall summary
    all_stats = collector.get_all_stats()
    print(f"\nOverall Summary:")
    print(f"- Total operations: {all_stats['total_operations']}")
    print(f"- Total errors: {all_stats['total_errors']}")
    print(f"- Error rate: {all_stats['overall_error_rate']:.2%}")
    
    # Get recent metrics
    recent = collector.get_recent_metrics(5)
    print(f"\nRecent metrics (last 5):")
    for metric in recent:
        print(f"- {metric['operation_name']}: {metric['duration_ms']:.1f}ms")


def main():
    """Run all observability tests."""
    print("=== Testing What2Wear Observability System ===\n")
    
    # Test 1: Manual performance monitoring
    test_manual_performance_monitoring()
    print()
    
    # Test 2: Extraction logger
    test_extraction_logger()
    print()
    
    # Test 3: Metrics collection
    test_metrics_collection()
    print()
    
    # Test 4: Memory management
    print("Testing memory management...")
    log_memory_usage("before_gc")
    gc_result = force_garbage_collection()
    print(f"Garbage collection freed {gc_result['freed_mb']:.1f}MB")
    log_memory_usage("after_gc")
    
    print("\n=== All observability tests completed successfully! ===")


if __name__ == "__main__":
    main()
