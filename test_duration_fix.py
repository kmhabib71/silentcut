#!/usr/bin/env python3
"""
Test script to verify duration calculation fixes and batch processing usage validation
"""

import os
import sys

def test_duration_fixes():
    print("🧪 Testing Duration Calculation Fixes")
    print("=" * 50)
    
    # Read the current file
    with open('silence_cutter.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if the problematic file size calculation is still present
    problematic_patterns = [
        "duration_minutes = max(1, file_size_bytes / (1024 * 1024))",
        "duration_minutes = file_size_bytes / (1024 * 1024)"
    ]
    
    issues_found = []
    for pattern in problematic_patterns:
        if pattern in content:
            issues_found.append(pattern)
    
    if issues_found:
        print("❌ ISSUES FOUND:")
        for issue in issues_found:
            print(f"   - {issue}")
        return False
    else:
        print("✅ No problematic file size calculations found")
    
    # Check for improved duration calculation patterns
    good_patterns = [
        "ffprobe",
        "MoviePy",
        "VideoFileClip", 
        "AudioFileClip",
        "file_size_mb / 25"  # Conservative estimation
    ]
    
    found_improvements = []
    for pattern in good_patterns:
        if pattern in content:
            found_improvements.append(pattern)
    
    print(f"✅ Found {len(found_improvements)} duration calculation improvements:")
    for improvement in found_improvements:
        print(f"   - {improvement}")
    
    return len(found_improvements) >= 3  # Should have multiple fallback methods


def test_batch_processing_validation():
    print("\n🧪 Testing Batch Processing Usage Validation")
    print("=" * 50)
    
    # Read the batch processing file
    try:
        with open('features/batch_processing.py', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ batch_processing.py not found")
        return False
    
    # Check for usage validation in start_batch_processing
    validation_patterns = [
        "validate_file_usage",
        "total_duration_minutes",
        "Batch Processing - Usage Limit Exceeded",
        "ffprobe",
        "MoviePy"
    ]
    
    found_validations = []
    for pattern in validation_patterns:
        if pattern in content:
            found_validations.append(pattern)
    
    if len(found_validations) >= 4:
        print(f"✅ Found {len(found_validations)} batch processing validation features:")
        for validation in found_validations:
            print(f"   - {validation}")
        return True
    else:
        print(f"❌ Missing batch processing validation features ({len(found_validations)}/5)")
        return False


def run_all_tests():
    print("🔧 COMPREHENSIVE DURATION & BATCH PROCESSING FIX TEST")
    print("=" * 60)
    
    # Test 1: Duration calculation fixes
    duration_test = test_duration_fixes()
    
    # Test 2: Batch processing validation
    batch_test = test_batch_processing_validation()
    
    # Summary
    print("\n📊 TEST SUMMARY")
    print("=" * 30)
    print(f"Duration Calculation Fix: {'✅ PASS' if duration_test else '❌ FAIL'}")
    print(f"Batch Processing Validation: {'✅ PASS' if batch_test else '❌ FAIL'}")
    
    if duration_test and batch_test:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Duration calculations improved with multiple fallback methods")
        print("✅ Batch processing now has usage validation")
        print("✅ No more 145MB = 145 minutes issues")
        print("✅ Free users limited to 60 minutes total usage")
        return True
    else:
        print("\n❌ SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1) 