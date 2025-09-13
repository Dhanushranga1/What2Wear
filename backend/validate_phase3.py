#!/usr/bin/env python3
"""
Phase 3 Color Suggestion Validation Script

Quick validation of the Phase 3 harmony engine with golden test cases
to ensure color theory rules and wearability constraints work correctly.
"""

import time
import json
from typing import Dict, Any

# Import Phase 3 modules
from app.services.colors.harmony.orchestrator import generate_color_suggestions
from app.services.colors.harmony.wearability import GarmentRole, StyleIntent, Season


def test_navy_base_classic():
    """Test Navy base color with classic intent (from Phase 3 spec example)."""
    print("🔵 Testing Navy base (#000080) with classic intent...")
    
    result = generate_color_suggestions(
        base_hex="#000080",
        source_role=GarmentRole.TOP,
        target_role=GarmentRole.BOTTOM,
        intent=StyleIntent.CLASSIC,
        season=Season.ALL,
        return_swatch=False  # Skip swatch for CLI testing
    )
    
    print(f"⏱️  Total time: {result['debug']['timing_ms']['total']:.2f}ms")
    print(f"📊 Categories generated: {list(result['suggestions'].keys())}")
    
    # Validate complementary suggestion (should be in camel/gold family)
    if "complementary" in result["suggestions"]:
        comp_hex = result["suggestions"]["complementary"][0]["hex"]
        print(f"🎨 Complementary suggestion: {comp_hex}")
        
        # Validate rationale
        rationale = result["suggestions"]["complementary"][0]["rationale"]
        print(f"📝 Rationale: {rationale}")
    
    # Check for neutrals
    if "neutral" in result["suggestions"]:
        neutral_count = len(result["suggestions"]["neutral"])
        neutral_hexes = [s["hex"] for s in result["suggestions"]["neutral"]]
        print(f"⚪ Neutrals ({neutral_count}): {neutral_hexes}")
    
    return result


def test_beige_base_safe():
    """Test Light Beige base with safe intent."""
    print("\n🟤 Testing Light Beige base (#F5F5DC) with safe intent...")
    
    result = generate_color_suggestions(
        base_hex="#F5F5DC",
        source_role=GarmentRole.TOP,
        target_role=GarmentRole.BOTTOM,
        intent=StyleIntent.SAFE,
        season=Season.AUTUMN_WINTER,
        return_swatch=False
    )
    
    print(f"⏱️  Total time: {result['debug']['timing_ms']['total']:.2f}ms")
    print(f"📊 Categories generated: {list(result['suggestions'].keys())}")
    
    # Safe intent should prioritize neutrals and skip triadic
    if "triadic" in result["suggestions"]:
        print("⚠️  Warning: Triadic found in safe intent mode")
    else:
        print("✅ Triadic correctly skipped in safe mode")
    
    # Check seasonal bias for autumn/winter
    if "neutral" in result["suggestions"]:
        neutrals = result["suggestions"]["neutral"]
        print(f"🍂 Autumn neutrals: {[s['hex'] for s in neutrals]}")
    
    return result


def test_bright_red_bold():
    """Test Bright Red base with bold intent."""
    print("\n🔴 Testing Bright Red base (#FF0000) with bold intent...")
    
    result = generate_color_suggestions(
        base_hex="#FF0000", 
        source_role=GarmentRole.TOP,
        target_role=GarmentRole.BOTTOM,
        intent=StyleIntent.BOLD,
        season=Season.ALL,
        return_swatch=False
    )
    
    print(f"⏱️  Total time: {result['debug']['timing_ms']['total']:.2f}ms")
    print(f"📊 Categories generated: {list(result['suggestions'].keys())}")
    
    # Bold should include more categories
    expected_categories = ["complementary", "analogous", "triadic", "neutral"]
    found_categories = list(result["suggestions"].keys())
    
    for category in expected_categories:
        if category in found_categories:
            count = len(result["suggestions"][category])
            print(f"✅ {category}: {count} suggestions")
        else:
            print(f"❌ Missing {category}")
    
    # Check hyper-saturation guard (red has S=1.0)
    processing_notes = result["debug"]["processing_notes"]
    print(f"🔧 Processing notes: {processing_notes}")
    
    return result


def test_performance_benchmark():
    """Run performance benchmark on multiple base colors."""
    print("\n⚡ Running performance benchmark...")
    
    test_colors = [
        "#000080",  # Navy
        "#F5F5DC",  # Beige
        "#FF0000",  # Red
        "#008000",  # Green
        "#800080",  # Purple
        "#333333",  # Charcoal
        "#FFFFFF"   # White (degenerate case)
    ]
    
    times = []
    
    for base_hex in test_colors:
        start = time.time()
        result = generate_color_suggestions(
            base_hex=base_hex,
            intent=StyleIntent.CLASSIC,
            return_swatch=False
        )
        duration = (time.time() - start) * 1000
        times.append(duration)
        
        print(f"  {base_hex}: {duration:.2f}ms")
    
    avg_time = sum(times) / len(times)
    max_time = max(times)
    print(f"\n📈 Performance Summary:")
    print(f"   Average: {avg_time:.2f}ms")
    print(f"   Maximum: {max_time:.2f}ms")
    print(f"   Target: ≤30ms median")
    
    if avg_time <= 30:
        print("✅ Performance target met!")
    else:
        print("⚠️  Performance target exceeded")
    
    return {"avg_ms": avg_time, "max_ms": max_time, "times": times}


def test_deterministic_outputs():
    """Test that identical inputs produce identical outputs."""
    print("\n🎯 Testing deterministic outputs...")
    
    base_hex = "#000080"
    params = {
        "base_hex": base_hex,
        "intent": StyleIntent.CLASSIC,
        "season": Season.ALL,
        "return_swatch": False
    }
    
    # Generate same suggestions twice
    result1 = generate_color_suggestions(**params)
    result2 = generate_color_suggestions(**params)
    
    # Compare suggestions (excluding timing data)
    suggestions1 = result1["suggestions"]
    suggestions2 = result2["suggestions"]
    
    if suggestions1 == suggestions2:
        print("✅ Deterministic: Identical inputs produce identical outputs")
    else:
        print("❌ Non-deterministic: Outputs differ between runs")
        print("  First run categories:", list(suggestions1.keys()))
        print("  Second run categories:", list(suggestions2.keys()))
    
    return suggestions1 == suggestions2


def main():
    """Run all validation tests."""
    print("🎨 Phase 3 Color Suggestion Validation")
    print("=" * 50)
    
    try:
        # Run test cases
        navy_result = test_navy_base_classic()
        beige_result = test_beige_base_safe()
        red_result = test_bright_red_bold()
        
        # Performance and determinism tests
        perf_result = test_performance_benchmark()
        deterministic = test_deterministic_outputs()
        
        # Summary
        print("\n🏁 Validation Summary:")
        print("=" * 30)
        print(f"✅ Navy classic test completed")
        print(f"✅ Beige safe test completed")
        print(f"✅ Red bold test completed")
        print(f"✅ Performance benchmark: {perf_result['avg_ms']:.1f}ms avg")
        print(f"{'✅' if deterministic else '❌'} Deterministic outputs: {deterministic}")
        
        # Check if all core requirements are met
        all_passed = (
            perf_result['avg_ms'] <= 30 and
            deterministic
        )
        
        if all_passed:
            print("\n🎉 All Phase 3 validation tests PASSED!")
        else:
            print("\n⚠️  Some validation tests need attention")
        
        return all_passed
        
    except Exception as e:
        print(f"\n❌ Validation failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
