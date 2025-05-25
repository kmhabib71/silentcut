#!/usr/bin/env python3
"""
TDD Workflow Runner for Video Silence Cutter
Automates the test-driven development process
"""

import subprocess
import sys
import os
import time
from datetime import datetime

def run_command(cmd):
    """Run a command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def print_header(title):
    """Print a formatted header"""
    print("\n" + "="*80)
    print(f"TEST: {title}")
    print("="*80)

def print_status(status, message):
    """Print status with appropriate symbols"""
    symbol = "[PASS]" if status else "[FAIL]"
    print(f"{symbol} {message}")

def main():
    """Main TDD workflow runner"""
    print_header("TDD WORKFLOW RUNNER - VIDEO SILENCE CUTTER")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Run Tests
    print_header("STEP 1: RUNNING COMPREHENSIVE TEST SUITE")
    success, stdout, stderr = run_command("python test_silence_cutter.py")
    
    if success:
        print_status(True, "ALL TESTS PASSED!")
        print("\nTest Summary:")
        lines = stdout.split('\n')
        for line in lines:
            if 'Total Tests Run:' in line or 'Passed:' in line or 'Failed:' in line or 'Errors:' in line:
                print(f"  {line}")
        
        print_header("STEP 2: APPLICATION READY FOR DEVELOPMENT")
        print_status(True, "Core functionality verified")
        print_status(True, "Timeline accuracy confirmed") 
        print_status(True, "Preview mode working correctly")
        print_status(True, "Audio-video sync verified")
        
        print("\nREADY FOR NEXT DEVELOPMENT CYCLE:")
        print("  1. Add new test cases for new features")
        print("  2. Run this script to verify tests fail")
        print("  3. Implement features to make tests pass")
        print("  4. Run this script to verify all tests pass")
        print("  5. Refactor safely with test protection")
        
        print("\nTO RUN APPLICATION:")
        print("  python silence_cutter.py")
        
    else:
        print_status(False, "TESTS FAILED!")
        print("\nDEVELOPMENT BLOCKED - Fix failing tests first")
        print("\nTest Output:")
        print(stdout)
        if stderr:
            print("\nErrors:")
            print(stderr)
            
        print("\nNEXT STEPS:")
        print("  1. Review failing test output above")
        print("  2. Fix the identified issues") 
        print("  3. Run this script again")
        print("  4. Repeat until all tests pass")
    
    # Step 3: Optional - Show current status
    print_header("CURRENT PROJECT STATUS")
    
    # Check if main application exists
    if os.path.exists("silence_cutter.py"):
        print_status(True, "Main application: silence_cutter.py")
    else:
        print_status(False, "Main application: silence_cutter.py NOT FOUND")
    
    # Check if test suite exists  
    if os.path.exists("test_silence_cutter.py"):
        print_status(True, "Test suite: test_silence_cutter.py")
    else:
        print_status(False, "Test suite: test_silence_cutter.py NOT FOUND")
        
    # Check documentation
    if os.path.exists("README_TDD_WORKFLOW.md"):
        print_status(True, "TDD Documentation: README_TDD_WORKFLOW.md")
    else:
        print_status(False, "TDD Documentation: README_TDD_WORKFLOW.md NOT FOUND")
    
    print(f"\nTDD WORKFLOW COMPLETED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main()) 