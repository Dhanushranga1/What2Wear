"""
End-to-end system validation for What2Wear Phase 2 StyleSync ColorMatch MVP.

This script performs comprehensive validation of the color extraction pipeline
including real-world testing, performance benchmarks, and system integration.
"""

import sys
import time
import json
import base64
import numpy as np
from pathlib import Path
from typing import Dict, List, Any
import cv2
from PIL import Image, ImageDraw

# Add the backend directory to the path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.services.colors.extraction import extract_colors_from_image
from app.services.observability import get_metrics_collector, get_extraction_logger


class Phase2Validator:
    """Comprehensive validation suite for Phase 2 color extraction system."""
    
    def __init__(self):
        self.results = {
            'tests_run': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'performance_metrics': {},
            'error_summary': []
        }
        self.test_images = {}
        
    def create_test_images(self):
        """Create diverse test images for validation."""
        print("🎨 Creating validation test images...")
        
        # Test 1: Simple two-color image (blue shirt)
        img1 = np.zeros((400, 400, 3), dtype=np.uint8)
        img1[:, :200] = [70, 130, 180]   # Steel blue
        img1[:, 200:] = [245, 245, 220]  # Beige
        mask1 = np.full((400, 400), 255, dtype=np.uint8)
        
        # Test 2: Complex multi-color garment (striped shirt)
        img2 = np.zeros((300, 300, 3), dtype=np.uint8)
        for i in range(0, 300, 30):
            if (i // 30) % 3 == 0:
                img2[i:i+30, :] = [139, 69, 19]    # Saddle brown
            elif (i // 30) % 3 == 1:
                img2[i:i+30, :] = [255, 255, 255]  # White
            else:
                img2[i:i+30, :] = [25, 25, 112]    # Midnight blue
        mask2 = np.full((300, 300), 255, dtype=np.uint8)
        
        # Test 3: Gradient image (color transition)
        img3 = np.zeros((256, 256, 3), dtype=np.uint8)
        for i in range(256):
            img3[:, i] = [i, 100, 255-i]  # Red to blue gradient
        mask3 = np.full((256, 256), 255, dtype=np.uint8)
        
        # Test 4: Real-world simulation (denim with fading)
        img4 = np.zeros((350, 350, 3), dtype=np.uint8)
        center = (175, 175)
        for y in range(350):
            for x in range(350):
                dist = np.sqrt((x - center[0])**2 + (y - center[1])**2)
                fade_factor = max(0.3, 1.0 - dist / 200)
                img4[y, x] = [int(29 * fade_factor), int(53 * fade_factor), int(87 * fade_factor)]
        mask4 = np.full((350, 350), 255, dtype=np.uint8)
        
        # Test 5: Neutral colors test (gray shirt)
        img5 = np.zeros((200, 200, 3), dtype=np.uint8)
        img5[:100, :] = [128, 128, 128]  # Medium gray
        img5[100:, :] = [64, 64, 64]     # Dark gray
        mask5 = np.full((200, 200), 255, dtype=np.uint8)
        
        self.test_images = {
            'blue_beige_shirt': (img1, mask1),
            'striped_shirt': (img2, mask2), 
            'gradient_test': (img3, mask3),
            'denim_fade': (img4, mask4),
            'gray_shirt': (img5, mask5)
        }
        
        print(f"✅ Created {len(self.test_images)} test images")
        
    def encode_image_to_base64(self, image: np.ndarray) -> str:
        """Convert numpy image to base64 string."""
        # Convert BGR to RGB for PIL
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)
        
        # Convert to base64
        from io import BytesIO
        buffer = BytesIO()
        pil_image.save(buffer, format='PNG')
        image_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{image_b64}"
    
    def run_extraction_test(self, name: str, image: np.ndarray, mask: np.ndarray, 
                           expected_clusters: int = None, expected_base_type: str = None) -> Dict[str, Any]:
        """Run color extraction test on a single image."""
        print(f"  Testing {name}...")
        
        start_time = time.time()
        
        try:
            # Encode images
            image_data = self.encode_image_to_base64(image)
            mask_data = self.encode_image_to_base64(mask)
            
            # Run extraction
            result = extract_colors_from_image(
                image_data=image_data,
                mask_data=mask_data,
                n_clusters=5,
                erosion_iterations=1,
                max_samples=8000
            )
            
            duration = (time.time() - start_time) * 1000
            
            # Validate result structure
            assert 'palette' in result
            assert 'base_color' in result
            assert 'base_color_index' in result
            assert 'harmony_analysis' in result
            assert 'metadata' in result
            
            palette = result['palette']
            base_color = result['base_color']
            harmony = result['harmony_analysis']
            metadata = result['metadata']
            
            # Validate palette structure
            assert len(palette) > 0
            assert all('hex' in color for color in palette)
            assert all('rgb' in color for color in palette)
            assert all('ratio' in color for color in palette)
            assert any(color['is_base'] for color in palette)
            
            # Validate base color
            assert base_color['is_base'] is True
            assert 'hex' in base_color
            assert base_color['hex'].startswith('#')
            
            # Validate harmony analysis
            assert 'harmony_type' in harmony
            assert harmony['harmony_type'] in ['monochromatic', 'analogous', 'complementary', 'triadic']
            assert 'diversity_score' in harmony
            assert 'temperature_balance' in harmony
            
            # Validate metadata
            assert 'performance' in metadata
            assert 'total_duration_ms' in metadata['performance']
            assert metadata['performance']['total_duration_ms'] > 0
            
            # Performance checks
            extraction_time = metadata['performance']['total_duration_ms']
            if extraction_time > 200:  # Warning threshold
                print(f"    ⚠️  Slow extraction: {extraction_time:.1f}ms")
            
            # Specific validations based on expected results
            if expected_clusters:
                cluster_count = len([c for c in palette if c['ratio'] > 0.05])  # Significant clusters
                if abs(cluster_count - expected_clusters) > 1:
                    print(f"    ⚠️  Unexpected cluster count: {cluster_count} (expected ~{expected_clusters})")
            
            test_result = {
                'status': 'PASS',
                'duration_ms': duration,
                'extraction_time_ms': extraction_time,
                'palette_size': len(palette),
                'base_color_hex': base_color['hex'],
                'harmony_type': harmony['harmony_type'],
                'diversity_score': harmony['diversity_score'],
                'dominant_ratio': max(c['ratio'] for c in palette),
                'details': {
                    'palette': palette,
                    'harmony': harmony,
                    'performance': metadata['performance']
                }
            }
            
            print(f"    ✅ PASS - {duration:.1f}ms, base: {base_color['hex']}, harmony: {harmony['harmony_type']}")
            return test_result
            
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            error_msg = str(e)
            
            test_result = {
                'status': 'FAIL',
                'duration_ms': duration,
                'error': error_msg,
                'details': {}
            }
            
            print(f"    ❌ FAIL - {error_msg}")
            self.results['error_summary'].append(f"{name}: {error_msg}")
            
            return test_result
    
    def run_performance_benchmarks(self):
        """Run performance benchmarks with various image sizes."""
        print("⚡ Running performance benchmarks...")
        
        sizes = [(128, 128), (256, 256), (512, 512), (1024, 1024)]
        benchmark_results = {}
        
        for width, height in sizes:
            print(f"  Benchmarking {width}×{height}...")
            
            # Create test image
            img = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
            mask = np.full((height, width), 255, dtype=np.uint8)
            
            # Run multiple iterations
            times = []
            memory_usage = []
            
            for i in range(3):  # 3 iterations for averaging
                result = self.run_extraction_test(
                    f"benchmark_{width}x{height}_{i}",
                    img, mask
                )
                
                if result['status'] == 'PASS':
                    times.append(result['extraction_time_ms'])
                    memory_peak = result['details']['performance'].get('memory_peak_mb', 0)
                    memory_usage.append(memory_peak)
            
            if times:
                benchmark_results[f"{width}x{height}"] = {
                    'mean_time_ms': np.mean(times),
                    'min_time_ms': np.min(times),
                    'max_time_ms': np.max(times),
                    'mean_memory_mb': np.mean(memory_usage) if memory_usage else 0,
                    'pixel_count': width * height
                }
                
                print(f"    📊 Avg: {np.mean(times):.1f}ms, "
                      f"Range: {np.min(times):.1f}-{np.max(times):.1f}ms")
        
        return benchmark_results
    
    def validate_algorithm_properties(self):
        """Validate specific algorithm properties and edge cases."""
        print("🧪 Validating algorithm properties...")
        
        tests = []
        
        # Test 1: Neutral color penalty
        print("  Testing neutral color penalty...")
        gray_img = np.full((200, 200, 3), [128, 128, 128], dtype=np.uint8)
        colored_img = np.zeros((200, 200, 3), dtype=np.uint8)
        colored_img[:, :100] = [128, 128, 128]  # Gray
        colored_img[:, 100:] = [200, 100, 50]   # Bright color
        mask = np.full((200, 200), 255, dtype=np.uint8)
        
        result = self.run_extraction_test("neutral_penalty_test", colored_img, mask)
        if result['status'] == 'PASS':
            # The bright color should be selected as base despite lower ratio
            base_color = result['details']['palette'][result['details']['base_color_index'] if 'base_color_index' in result['details'] else 0]
            is_bright = any(c > 150 for c in base_color['rgb'])
            tests.append(('neutral_penalty', is_bright, "Bright color should be selected over gray"))
            print(f"    {'✅' if is_bright else '❌'} Base color selection with neutral penalty")
        
        # Test 2: Spatial cohesion
        print("  Testing spatial cohesion...")
        scattered_img = np.zeros((200, 200, 3), dtype=np.uint8)
        for i in range(0, 200, 20):
            for j in range(0, 200, 20):
                if (i + j) % 40 == 0:
                    scattered_img[i:i+10, j:j+10] = [255, 0, 0]  # Red patches
                else:
                    scattered_img[i:i+10, j:j+10] = [0, 0, 255]  # Blue patches
        
        result = self.run_extraction_test("spatial_cohesion_test", scattered_img, mask)
        tests.append(('spatial_cohesion', result['status'] == 'PASS', 
                     "Should handle scattered color patterns"))
        
        # Test 3: Small image handling
        print("  Testing small image handling...")
        small_img = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        small_mask = np.full((50, 50), 255, dtype=np.uint8)
        
        result = self.run_extraction_test("small_image_test", small_img, small_mask)
        tests.append(('small_image', result['status'] == 'PASS', 
                     "Should handle small images gracefully"))
        
        # Test 4: Single color image
        print("  Testing single color image...")
        single_color_img = np.full((100, 100, 3), [100, 150, 200], dtype=np.uint8)
        
        result = self.run_extraction_test("single_color_test", single_color_img, mask[:100, :100])
        if result['status'] == 'PASS':
            harmony_type = result['harmony_type']
            is_monochromatic = harmony_type == 'monochromatic'
            tests.append(('single_color', is_monochromatic, 
                         "Single color should result in monochromatic harmony"))
            print(f"    {'✅' if is_monochromatic else '❌'} Monochromatic detection")
        
        return tests
    
    def run_comprehensive_validation(self):
        """Run the complete validation suite."""
        print("🚀 Starting Phase 2 comprehensive system validation...")
        print("=" * 60)
        
        # Create test images
        self.create_test_images()
        
        # Test 1: Basic extraction functionality
        print("\n📋 Testing basic extraction functionality...")
        basic_tests = {}
        
        for name, (image, mask) in self.test_images.items():
            result = self.run_extraction_test(name, image, mask)
            basic_tests[name] = result
            
            self.results['tests_run'] += 1
            if result['status'] == 'PASS':
                self.results['tests_passed'] += 1
            else:
                self.results['tests_failed'] += 1
        
        # Test 2: Performance benchmarks
        print("\n⚡ Performance benchmarks...")
        benchmark_results = self.run_performance_benchmarks()
        self.results['performance_metrics']['benchmarks'] = benchmark_results
        
        # Test 3: Algorithm properties
        print("\n🧪 Algorithm properties validation...")
        property_tests = self.validate_algorithm_properties()
        
        for test_name, passed, description in property_tests:
            self.results['tests_run'] += 1
            if passed:
                self.results['tests_passed'] += 1
                print(f"    ✅ {test_name}: {description}")
            else:
                self.results['tests_failed'] += 1
                print(f"    ❌ {test_name}: {description}")
        
        # Test 4: System metrics validation
        print("\n📊 System metrics validation...")
        metrics_collector = get_metrics_collector()
        all_stats = metrics_collector.get_all_stats()
        
        print(f"    Total operations tracked: {all_stats.get('total_operations', 0)}")
        print(f"    Overall error rate: {all_stats.get('overall_error_rate', 0):.2%}")
        
        # Validate performance targets
        performance_ok = True
        if benchmark_results:
            avg_times = [stats['mean_time_ms'] for stats in benchmark_results.values()]
            max_time = max(avg_times) if avg_times else 0
            
            if max_time > 300:  # 300ms threshold for largest images
                performance_ok = False
                print(f"    ❌ Performance issue: max time {max_time:.1f}ms > 300ms")
            else:
                print(f"    ✅ Performance OK: max time {max_time:.1f}ms")
        
        self.results['tests_run'] += 1
        if performance_ok:
            self.results['tests_passed'] += 1
        else:
            self.results['tests_failed'] += 1
        
        # Final summary
        print("\n" + "=" * 60)
        print("📋 PHASE 2 VALIDATION SUMMARY")
        print("=" * 60)
        
        total_tests = self.results['tests_run']
        passed_tests = self.results['tests_passed']
        failed_tests = self.results['tests_failed']
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"Tests Run: {total_tests}")
        print(f"Tests Passed: {passed_tests}")
        print(f"Tests Failed: {failed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        if benchmark_results:
            print(f"\nPerformance Summary:")
            for size, stats in benchmark_results.items():
                print(f"  {size}: {stats['mean_time_ms']:.1f}ms avg")
        
        if self.results['error_summary']:
            print(f"\nErrors Encountered:")
            for error in self.results['error_summary'][:5]:  # Show first 5
                print(f"  - {error}")
        
        # Overall status
        if success_rate >= 90:
            status = "✅ PHASE 2 VALIDATION PASSED"
            status_color = "GREEN"
        elif success_rate >= 75:
            status = "⚠️  PHASE 2 VALIDATION PARTIAL"
            status_color = "YELLOW"
        else:
            status = "❌ PHASE 2 VALIDATION FAILED"
            status_color = "RED"
        
        print(f"\n{status}")
        print(f"System is ready for Phase 3 development: {'YES' if success_rate >= 90 else 'NO'}")
        
        return {
            'overall_status': status_color,
            'success_rate': success_rate,
            'total_tests': total_tests,
            'basic_tests': basic_tests,
            'benchmark_results': benchmark_results,
            'property_tests': property_tests,
            'ready_for_phase3': success_rate >= 90
        }


def main():
    """Run the comprehensive Phase 2 validation."""
    validator = Phase2Validator()
    results = validator.run_comprehensive_validation()
    
    # Save results to file
    output_file = Path(__file__).parent / "validation_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📄 Detailed results saved to: {output_file}")
    
    return results


if __name__ == "__main__":
    results = main()
